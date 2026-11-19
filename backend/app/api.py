from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import repository as repo
from .config import get_settings
from .db import get_db
from .demo.loader import clear_demo, load_demo
from .models import Company, DuplicateCandidate, DuplicateLog, Email, SyncHistory, UploadBatch
from .schemas import DuplicateResolveIn, EmailIngestRequest, IndustryConfigUpdateIn, IndustryPatchIn, Page, ReviewIn, SyncOut
from .services import exporter, gmail, knowledge_base as kb
from .services.duplicates import merge_companies
from .services.email_parser import parse_message
from .services.review import ReviewError, apply_review
from .services.sync import run_gmail_sync
from .services.taxonomy import industry_by_slug, load_taxonomy, save_taxonomy
from .services.uploads import (
    _msg_id,
    _parse_date,
    batch_to_dict,
    ingest_parsed_batch,
    parse_csv_bytes,
    parse_eml_bytes,
    parse_mbox_bytes,
    parse_msg_bytes,
)

log = logging.getLogger(__name__)
Source = Literal["gmail", "demo", "upload", "all"]


def require_key(x_api_key: str | None = Header(default=None)) -> None:
    key = get_settings().api_access_key
    if key and x_api_key != key:
        raise HTTPException(401, "Missing or invalid X-API-Key")


public = APIRouter(prefix="/api")
router = APIRouter(prefix="/api", dependencies=[Depends(require_key)])


@public.get("/health")
def health(db: Session = Depends(get_db)):
    s = get_settings()
    db.execute(select(1))
    return {"status": "ok", "database": "ok", "llm_mode": "llm_rag" if s.llm_enabled else "heuristic_rag",
            "llm_model": s.llm_model if s.llm_enabled else None, "knowledge_base": kb.kb_status(),
            "target_gmail_address": s.target_gmail_address,
            "time": datetime.now(timezone.utc).isoformat()}


# ------------------------------------------------------------------ Gmail
def _sync_out(s: SyncHistory) -> dict:
    return {"id": s.id, "trigger": s.trigger, "mode": s.mode, "status": s.status, "fetched": s.fetched, "processed": s.processed,
            "needs_review": s.needs_review, "failed": s.failed, "error": s.error,
            "started_at": repo._iso(s.started_at), "finished_at": repo._iso(s.finished_at)}


@router.get("/gmail/status")
def gmail_status(db: Session = Depends(get_db)):
    from .services import gmail_imap
    s = get_settings()
    configured, why = gmail.is_configured()
    oauth_connected = configured and gmail.TOKEN_FILE.exists()
    imap_connected = gmail_imap.has_imap_credentials()
    connected = oauth_connected or imap_connected
    last = db.scalars(select(SyncHistory).where(SyncHistory.source == "gmail").order_by(SyncHistory.id.desc())).first()
    last_ok = db.scalars(select(SyncHistory).where(SyncHistory.source == "gmail", SyncHistory.status == "success")
                         .order_by(SyncHistory.id.desc())).first()
    return {
        "configured": configured or imap_connected,
        "configuration_problem": None if imap_connected else why,
        "connected": connected,
        "connection_mode": "oauth2" if oauth_connected else ("app_password_readonly_imap" if imap_connected else None),
        "target_address": s.target_gmail_address if s.target_configured else None,
        "connected_account": s.target_gmail_address if connected else None,
        "redirect_uri": s.google_redirect_uri,
        "scope": gmail.SCOPES[0], "last_sync_at": repo._iso(last_ok.finished_at) if last_ok else None,
        "last_sync": _sync_out(last) if last else None,
        "background_sync_minutes": s.sync_interval_minutes,
        "emails_in_database": db.scalar(select(func.count()).select_from(Email).where(Email.source == "gmail")) or 0,
    }


@public.get("/gmail/connect")
def gmail_connect():
    """Browser navigates here; we redirect to Google's consent screen."""
    try:
        return RedirectResponse(gmail.start_auth())
    except gmail.GmailError as e:
        return RedirectResponse(f"{get_settings().frontend_url}/gmail?error={e.code}&message={_q(str(e))}")


def _q(s: str) -> str:
    from urllib.parse import quote
    return quote(s[:300])


@public.get("/gmail/callback")
def gmail_callback(state: str = "", code: str = "", error: str = ""):
    front = f"{get_settings().frontend_url}/gmail"
    if error or not code:
        return RedirectResponse(f"{front}?error=oauth_denied&message={_q(error or 'Authorization was not granted')}")
    try:
        account = gmail.finish_auth(state, code)
        return RedirectResponse(f"{front}?connected=1&account={_q(account)}")
    except gmail.GmailError as e:
        return RedirectResponse(f"{front}?error={e.code}&message={_q(str(e))}")
    except Exception as e:
        log.warning("OAuth callback failed: %s", type(e).__name__)
        return RedirectResponse(f"{front}?error=oauth_failed&message={_q('OAuth token exchange failed. Check client secret and redirect URI.')}")


@router.post("/gmail/disconnect")
def gmail_disconnect():
    from .services import gmail_imap
    gmail.disconnect()
    gmail_imap.disconnect_imap()
    return {"connected": False}


@router.post("/gmail/app-password", response_model=SyncOut)
def connect_gmail_app_password(payload: dict):
    """Connect rajurajuu970@gmail.com using a 16-character Google App Password (read-only IMAP) and immediately sync."""
    from .services import gmail_imap
    email_addr = payload.get("email") or get_settings().target_gmail_address
    app_pw = payload.get("app_password") or ""
    gmail_imap.save_imap_app_password(email_addr, app_pw)
    s = gmail_imap.run_imap_sync("manual")
    if s.status == "failed":
        raise HTTPException(400, s.error or "Sync failed")
    return _sync_out(s)


@router.post("/gmail/sync", response_model=SyncOut)
def gmail_sync():
    from .services import gmail_imap
    if gmail_imap.has_imap_credentials() and not gmail.TOKEN_FILE.exists():
        s = gmail_imap.run_imap_sync("manual")
    else:
        s = run_gmail_sync("manual")
    if s.status == "failed":
        code = 401 if "not connected" in (s.error or "").lower() else 403 if "does not match" in (s.error or "") else 400
        raise HTTPException(code, s.error or "Sync failed")
    return _sync_out(s)


@router.post("/gmail/oauth-credentials")
def save_gmail_oauth_credentials(payload: dict):
    """Save GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET directly from the browser UI into backend/secrets/client_secret.json."""
    cid = (payload.get("client_id") or "").strip()
    csec = (payload.get("client_secret") or "").strip()
    if not cid or not csec:
        raise HTTPException(400, "Both Client ID and Client Secret are required.")
    s = get_settings()
    data = {
        "web": {
            "client_id": cid,
            "client_secret": csec,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [s.google_redirect_uri],
        }
    }
    target_path = s.client_secrets_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    target_path.chmod(0o600)
    return {"configured": True, "target_address": s.target_gmail_address, "redirect_uri": s.google_redirect_uri}


@router.post("/gmail/client-secret")
async def upload_gmail_client_secret(file: UploadFile = File(...)):
    """Save a Google Cloud Console OAuth 2.0 client_secret.json file securely on the backend (0600 permissions)."""
    raw = await file.read()
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception:
        raise HTTPException(400, "Uploaded file is not valid JSON.")
    block = data.get("web") or data.get("installed")
    if not isinstance(block, dict) or not block.get("client_id") or not block.get("client_secret"):
        raise HTTPException(400, "Invalid Google OAuth JSON: must contain a 'web' (or 'installed') object with 'client_id' and 'client_secret'.")
    s = get_settings()
    target_path = s.client_secrets_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    # Normalise to 'web' with our redirect URI so Google OAuth Flow works seamlessly
    if "installed" in data and "web" not in data:
        data = {"web": {**block, "redirect_uris": [s.google_redirect_uri]}}
    target_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    target_path.chmod(0o600)
    return {"configured": True, "target_address": s.target_gmail_address, "redirect_uri": s.google_redirect_uri}


@router.post("/gmail/simulate-inbox", response_model=SyncOut)
def simulate_target_inbox_sync(db: Session = Depends(get_db)):
    """Deliver sample client request emails addressed to TARGET_GMAIL_ADDRESS (rajurajuu970@gmail.com) and run the real RAG pipeline."""
    from .services.pipeline import STATUS_REVIEW, STATUS_SUSPICIOUS, process_email

    target = get_settings().target_gmail_address or "rajurajuu970@gmail.com"
    samples = [
        (
            "inbox-m1",
            "Rohit Verma <rohit.verma@bharatmachinery.co.in>",
            "Enquiry: IoT Production Monitoring & ERP for our CNC Factory",
            "Hello Team,\n\nWe are an industrial machinery and automotive component manufacturing company operating two CNC production plants in Ahmedabad with 350 employees.\n\nWe are looking for an ERP and IoT production monitoring dashboard for our factory assembly lines. Our budget is Rs 12 Lakh and we would like to schedule a demo within 4 weeks.\n\nBest regards,\nRohit Verma\nGeneral Manager - Operations\nBharat Industrial Machinery Pvt Ltd\n+91 98250 12345\nhttps://www.bharatmachinery.co.in",
            "bharatmachinery.co.in",
        ),
        (
            "inbox-m2",
            "Deepa Kulkarni <deepa@kulkarnitextiles.in>",
            "Requirement: Dealer Order & Inventory Portal for our Garment Mill",
            "Dear Team,\n\nKulkarni Textiles & Apparel Ltd is a textile and garment manufacturing company with spinning and weaving mills in Surat. We need a web and mobile dealer ordering portal with inventory management within 8 weeks.\n\nRegards,\nDeepa Kulkarni\nDirector\nKulkarni Textiles & Apparel Ltd\n+91 98240 55667\nhttps://www.kulkarnitextiles.in",
            "kulkarnitextiles.in",
        ),
        (
            "inbox-e1",
            "Dr. Anita Menon <admissions@sunriseengineering.edu.in>",
            "Requirement: Online Admissions Portal & Website Redesign for our College",
            "Dear Team,\n\nI am writing from Sunrise Institute of Engineering & Technology. We are an autonomous engineering college with over 4,200 undergraduate and postgraduate students on our Bengaluru campus.\n\nOur admissions department requires a new college website and online student admissions management portal before the upcoming semester intake. Kindly share a quotation.\n\nWarm regards,\nDr. Anita Menon\nDean of Admissions\nSunrise Institute of Engineering & Technology\n+91 98450 11223\nhttps://www.sunriseengineering.edu.in",
            "sunriseengineering.edu.in",
        ),
        (
            "inbox-e2",
            "Siddharth Jain <siddharth@edunextlearn.io>",
            "Mobile Learning App & LMS Upgrade for our EdTech Platform",
            "Hello,\n\nEduNext is an EdTech platform offering online courses and live JEE/NEET coaching to 120,000 learners. We are looking for mobile app development and learning management system customization.\n\nBest regards,\nSiddharth Jain\nProduct Head\nEduNext Learning Pvt Ltd\n+91 98100 44556\nhttps://www.edunextlearn.io",
            "edunextlearn.io",
        ),
        (
            "inbox-i1",
            "Sanjay Patel <sanjay@cloudnimbus.io>",
            "Partnership & Mobile App Development for our SaaS Platform",
            "Hi Team,\n\nCloudNimbus Technologies is a B2B SaaS and custom software development company providing cloud DevOps and analytics tools to enterprise clients.\n\nWe are looking for a development partner to build a companion iOS and Android mobile app for our SaaS platform within 3 months. Please let us know if we can schedule a call this week.\n\nBest regards,\nSanjay Patel\nFounder & CTO\nCloudNimbus Technologies Pvt Ltd\n+91 98111 90909\nhttps://www.cloudnimbus.io",
            "cloudnimbus.io",
        ),
        (
            "inbox-i2",
            "Neha Sharma <neha@aivisionlabs.ai>",
            "Enterprise Web Dashboard for our AI & Data Analytics Product",
            "Hello,\n\nAIVision Labs is an artificial intelligence and data analytics software company building computer vision models. We need a React and FastAPI customer analytics dashboard within 6 weeks.\n\nRegards,\nNeha Sharma\nVP Engineering\nAIVision Labs Pvt Ltd\n+91 98765 44332\nhttps://www.aivisionlabs.ai",
            "aivisionlabs.ai",
        ),
        (
            "inbox-l1",
            "Harpreet Singh <harpreet@swifthaulcargo.in>",
            "RFQ: Fleet Tracking & Warehouse Inventory Software",
            "Hello,\n\nSwiftHaul Cargo Carriers is a freight transportation, 3PL warehousing, and supply chain logistics company operating a fleet of 220 trucks across India.\n\nWe need a GPS fleet management and warehouse inventory tracking web application with driver mobile apps. Our budget is Rs 15 Lakh. Kindly send your quotation and technical proposal.\n\nThanks & Regards,\nHarpreet Singh\nHead of Operations\nSwiftHaul Cargo Carriers Pvt Ltd\n+91 98150 77889\nhttps://www.swifthaulcargo.in",
            "swifthaulcargo.in",
        ),
        (
            "inbox-web-design-1",
            "Client Enquiry <client.webdesign@creativestudio.in>",
            "Website design and web application development requirement",
            "Hello Raju,\n\nWe are looking for a modern website design and web application development for our business. We need responsive UI/UX design, custom software pages, and an enquiry portal within 4 weeks.\n\nPlease share your website design quotation and proposal.\n\nBest regards,\nKiran Kumar\nDirector\nCreative Studio & Software Solutions\n+91 98480 55667\nhttps://www.creativestudio.in",
            "creativestudio.in",
            "pass",
        ),
        (
            "inbox-l2",
            "Karthik Nair <karthik@metroexpresscourier.com>",
            "Last-Mile Delivery Agent App & Parcel Tracking System",
            "Dear Sir/Madam,\n\nMetroExpress Courier Services operates a courier and parcel delivery network across 18 cities. We require a mobile app for our delivery agents and a real-time shipment tracking portal.\n\nRegards,\nKarthik Nair\nOperations Manager\nMetroExpress Courier Services Pvt Ltd\n+91 98400 77880\nhttps://www.metroexpresscourier.com",
            "metroexpresscourier.com",
            "pass",
        ),
        (
            "inbox-fake-m1",
            "Accounts <billing@steel-plant-pay.com>",
            "Urgent payment: Steel manufacturing plant revised bank account",
            "Hello,\n\nWe are a steel manufacturing company and industrial machinery factory. Our bank details have changed. Urgent payment required: kindly wire transfer the invoice amount to our revised bank account within 24 hours and share your bank details.\n\nGlobal Steel Manufacturing Ltd",
            "steel-plant-pay.com",
            "fail",
        ),
        (
            "inbox-fake-e1",
            "University Grants <grants@campus-scholarship-fund.org>",
            "Urgent: University & College accreditation fee wire transfer",
            "Dear Principal,\n\nWe are a university and college accreditation board for campus students and faculty. Your college account will be suspended within 24 hours unless you wire transfer the urgent payment and verify your account password now.\n\nUniversity Grants Security",
            "campus-scholarship-fund.org",
            "fail",
        ),
        (
            "inbox-fake-i1",
            "Cloud SaaS Security <alert@cloud-saas-verify.com>",
            "Urgent: Verify your SaaS & Cloud DevOps account password",
            "Hello,\n\nWe are a cloud DevOps and SaaS software provider. Your cloud API account is suspended. Verify your account password within 24 hours or send bitcoin payment to restore access.\n\nCloud SaaS Security Team",
            "cloud-saas-verify.com",
            "fail",
        ),
        (
            "inbox-fake-l1",
            "Freight Customs Desk <customs@dhl-freight-release.com>",
            "Urgent payment: Freight container & warehouse delivery release",
            "Dear Customer,\n\nWe are a freight forwarding, cargo shipping and warehouse logistics company. Your container shipment is held. Kindly wire transfer the urgent payment via western union or gift card within 24 hours to release delivery.\n\nFreight Customs Desk",
            "dhl-freight-release.com",
            "fail",
        ),
    ]

    sync = SyncHistory(source="gmail", trigger="simulated_inbox", mode="incremental", status="running", fetched=len(samples))
    db.add(sync)
    db.commit()

    for item in samples:
        mid, frm, subj, body, dom = item[0], item[1], item[2], item[3], item[4]
        auth_res = item[5] if len(item) > 5 else "pass"
        if db.scalar(select(Email.id).where(Email.source == "gmail", Email.gmail_message_id == mid)):
            continue
        hdrs = {
            "To": target,
            "Delivered-To": target,
            "Authentication-Results": f"mx.google.com; dkim={auth_res} header.i=@{dom}; spf={auth_res} smtp.mailfrom={dom}; dmarc={auth_res} header.from={dom}",
        }
        parsed = parse_message(
            message_id=mid,
            thread_id=f"thread-{mid}",
            from_header=frm,
            subject=subj,
            text=body,
            html=None,
            headers=hdrs,
            date=datetime.now(timezone.utc),
        )
        em = process_email(db, parsed, "gmail")
        sync.processed += 1
        if em.status in (STATUS_REVIEW, STATUS_SUSPICIOUS):
            sync.needs_review += 1

    sync.status = "success"
    sync.finished_at = datetime.now(timezone.utc)
    db.add(sync)
    db.commit()
    db.refresh(sync)

    from .services import gmail_imap
    if gmail_imap.has_imap_credentials():
        try:
            imap_sync = gmail_imap.run_imap_sync("manual")
            if imap_sync.status == "success":
                return _sync_out(imap_sync)
        except Exception:
            pass
    return _sync_out(sync)


@router.get("/gmail/syncs")
def sync_history(db: Session = Depends(get_db), limit: int = Query(10, le=50)):
    return [_sync_out(s) for s in db.scalars(select(SyncHistory).order_by(SyncHistory.id.desc()).limit(limit))]


# ------------------------------------------------------------------ File Uploads (CSV, EML, MSG, MBOX) & Direct Ingest
@router.post("/uploads")
async def upload_emails(
    file: UploadFile = File(...),
    column_mapping: str | None = Form(default=None),
    source: str = Form(default="upload"),
    db: Session = Depends(get_db),
):
    fname = file.filename or "uploaded_file"
    ext = Path(fname).suffix.lower().lstrip(".")
    if ext not in ("csv", "eml", "msg", "mbox"):
        raise HTTPException(400, f"Unsupported file extension '.{ext}'. Allowed: .csv, .eml, .msg, .mbox")
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "Uploaded file is empty")
    explicit_map: dict[str, str] = {}
    if column_mapping:
        try:
            explicit_map = json.loads(column_mapping)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON in column_mapping")
    try:
        if ext == "csv":
            parsed, resolved_map, parse_errs = parse_csv_bytes(raw, explicit_map)
        elif ext == "eml":
            parsed, resolved_map, parse_errs = parse_eml_bytes(raw), {}, []
        elif ext == "mbox":
            parsed, resolved_map, parse_errs = parse_mbox_bytes(raw), {}, []
        else:
            parsed, resolved_map, parse_errs = parse_msg_bytes(raw, fname), {}, []
    except ValueError as e:
        raise HTTPException(400, str(e))

    batch = ingest_parsed_batch(
        db,
        filename=fname,
        file_type=ext,
        parsed_emails=parsed,
        source=source if source in ("upload", "gmail", "demo") else "upload",
        column_mapping=resolved_map,
        parse_errors=parse_errs,
    )
    return batch_to_dict(batch)


@router.post("/emails/ingest")
def ingest_emails_json(payload: EmailIngestRequest, db: Session = Depends(get_db)):
    items = list(payload.emails or [])
    if not items and payload.sender_email:
        from .schemas import EmailIngestItem
        items = [EmailIngestItem(
            sender_name=payload.sender_name or "",
            sender_email=payload.sender_email,
            subject=payload.subject or "",
            body=payload.body or "",
            received_at=payload.received_at,
        )]
    if not items:
        raise HTTPException(422, "Provide 'emails' list or 'sender_email'/'subject'/'body'")
    parsed = []
    for item in items:
        from_hdr = f"{item.sender_name} <{item.sender_email}>".strip() if item.sender_name else item.sender_email
        mid = item.message_id or _msg_id("ingest", f"{item.sender_email}|{item.subject}|{item.body[:200]}")
        hdrs = dict(item.headers or {})
        if item.reply_to:
            hdrs["Reply-To"] = item.reply_to
        parsed.append(
            parse_message(
                message_id=mid,
                thread_id=f"thread-{mid}",
                from_header=from_hdr,
                subject=item.subject,
                text=item.body,
                html=item.html,
                headers=hdrs,
                date=_parse_date(item.received_at),
            )
        )
    batch = ingest_parsed_batch(
        db,
        filename="api_ingest.json",
        file_type="json",
        parsed_emails=parsed,
        source=payload.source if payload.source in ("upload", "gmail", "demo") else "upload",
    )
    return batch_to_dict(batch)


@router.get("/batches")
def list_batches(db: Session = Depends(get_db), limit: int = Query(25, le=100)):
    rows = db.scalars(select(UploadBatch).order_by(UploadBatch.id.desc()).limit(limit)).all()
    return [batch_to_dict(b) for b in rows]


@router.get("/batches/{batch_id}")
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    b = db.get(UploadBatch, batch_id)
    if not b:
        raise HTTPException(404, f"Upload batch {batch_id} not found")
    return batch_to_dict(b)


# ------------------------------------------------------------------ Leads / emails
def _filters(source: Source = "gmail", industry: str | None = None, sub_industry: str | None = None,
             status: str | None = None, priority: str | None = None, company_trust: str | None = None,
             email_risk: str | None = None, search: str | None = Query(None, max_length=200),
             lead_type: str | None = None, only_leads: bool = False,
             date_from: str | None = None, date_to: str | None = None,
             verdict: Literal["REAL", "FAKE", "ALL"] | None = None) -> dict:
    return dict(source=source, industry=industry, sub_industry=sub_industry, status=status, priority=priority,
                company_trust=company_trust, email_risk=email_risk, search=search, lead_type=lead_type,
                only_leads=only_leads, date_from=date_from, date_to=date_to, verdict=verdict)


def _page(db, f, sort, order, page, page_size):
    return repo.list_emails(db, sort=sort, order=order, page=page, page_size=page_size, **f)


@router.get("/emails", response_model=Page)
def list_emails(f: dict = Depends(_filters), sort: str = "date", order: Literal["asc", "desc"] = "desc",
                page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200), db: Session = Depends(get_db)):
    return _page(db, f, sort, order, page, page_size)


@router.get("/leads", response_model=Page)
def list_leads(f: dict = Depends(_filters), sort: str = "date", order: Literal["asc", "desc"] = "desc",
               page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200), db: Session = Depends(get_db)):
    return _page(db, f, sort, order, page, page_size)


@router.get("/leads/industry/{industry}", response_model=Page)
def leads_by_industry(industry: str, f: dict = Depends(_filters), sort: str = "date", order: Literal["asc", "desc"] = "desc",
                      page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200), db: Session = Depends(get_db)):
    if not industry_by_slug(industry):
        raise HTTPException(404, f"Unknown industry '{industry}'. Valid: {[i['slug'] for i in load_taxonomy()['industries']]}")
    f = {**f, "industry": industry, "only_leads": (f["status"] is None and f.get("verdict") is None)}
    return _page(db, f, sort, order, page, page_size)


def _get(db: Session, lead_id: int) -> Email:
    e = db.get(Email, lead_id)
    if not e:
        raise HTTPException(404, f"Lead {lead_id} not found")
    return e


@router.get("/leads/{lead_id}")
def lead_detail(lead_id: int, db: Session = Depends(get_db)):
    return repo.detail(db, _get(db, lead_id))


@router.get("/leads/{lead_id}/trust")
def lead_trust(lead_id: int, db: Session = Depends(get_db)):
    d = repo.detail(db, _get(db, lead_id))
    return {"company_trust": d["company_trust"], "email_trust": d["email_trust"], "lead_relevance": d["lead_relevance"]}


@router.patch("/leads/{lead_id}/review")
def review_lead(lead_id: int, payload: ReviewIn, db: Session = Depends(get_db)):
    e = _get(db, lead_id)
    try:
        apply_review(db, e, payload)
    except ReviewError as err:
        raise HTTPException(422, str(err))
    db.refresh(e)
    return repo.detail(db, e)


@router.patch("/leads/{lead_id}/industry")
def patch_lead_industry(lead_id: int, payload: IndustryPatchIn, db: Session = Depends(get_db)):
    e = _get(db, lead_id)
    review_in = ReviewIn(
        reviewer=payload.reviewer,
        industry=payload.industry,
        sub_industry=payload.sub_industry,
        is_genuine=payload.is_genuine,
        notes=payload.notes,
    )
    try:
        apply_review(db, e, review_in)
    except ReviewError as err:
        raise HTTPException(422, str(err))
    db.refresh(e)
    return repo.detail(db, e)


@router.get("/review-queue", response_model=Page)
def review_queue(source: Source = "gmail", page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=200),
                 db: Session = Depends(get_db)):
    from sqlalchemy import or_
    q = repo.base_query().where(Email.reviewed.is_(False),
                                or_(Email.status == "Needs Review", Email.status == repo.SUSPICIOUS))
    if source and source != "all":
        q = q.where(Email.source == source)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(Email.email_date.desc().nulls_last()).offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [repo.summary(e) for e in rows], "total": total, "page": page, "page_size": page_size, "pages": max(1, -(-total // page_size))}


# ------------------------------------------------------------------ Dashboard / taxonomy / duplicates
@router.get("/dashboard/stats")
@router.get("/stats")
def dashboard_stats(source: Source = "gmail", db: Session = Depends(get_db)):
    return repo.stats(db, source)


@router.get("/industries")
def industries(source: Source = "gmail", db: Session = Depends(get_db)):
    st = repo.stats(db, source)["by_industry"]
    out = []
    for i in load_taxonomy()["industries"]:
        display_name = "Education & EdTech" if i["name"] == "Education" else i["name"]
        out.append({
            "name": i["name"],
            "display_name": display_name,
            "slug": i["slug"],
            "description": i["description"].strip(),
            "keywords": list(i.get("keywords", [])),
            "sub_industries": list(i["sub_industries"].keys()),
            "sub_industry_details": {k: v.get("keywords", []) for k, v in i["sub_industries"].items()},
            "leads": st.get(i["name"], 0),
        })
    return out


@router.patch("/industries/{slug}")
def update_industry_config(slug: str, payload: IndustryConfigUpdateIn, db: Session = Depends(get_db)):
    data = load_taxonomy()
    target = None
    for ind in data["industries"]:
        if ind["slug"] == slug or ind["name"].lower() == slug.lower():
            target = ind
            break
    if not target:
        raise HTTPException(404, f"Industry '{slug}' not found")
    if payload.description is not None:
        target["description"] = payload.description.strip()
    if payload.keywords is not None:
        target["keywords"] = [k.strip() for k in payload.keywords if k.strip()]
    if payload.sub_industries is not None:
        target["sub_industries"] = {
            sub_name.strip(): {"keywords": [kw.strip() for kw in kws if kw.strip()]}
            for sub_name, kws in payload.sub_industries.items()
            if sub_name.strip()
        }
    save_taxonomy(data)
    from .main import seed_taxonomy
    seed_taxonomy()
    n_chunks = kb.ensure_knowledge_base()
    return {"updated": target["name"], "slug": target["slug"], "kb_chunks": n_chunks}


@router.get("/duplicates")
def duplicates(status: str = "open", db: Session = Depends(get_db)):
    q = select(DuplicateCandidate).order_by(DuplicateCandidate.id.desc())
    if status != "all":
        q = q.where(DuplicateCandidate.status == status)
    out = []
    for d in db.scalars(q):
        a, b = db.get(Company, d.company_id), db.get(Company, d.other_company_id)
        out.append({"id": d.id, "email_id": d.email_id, "similarity": d.similarity, "reason": d.reason, "status": d.status,
                    "company": {"id": a.id, "name": a.name, "domain": a.domain} if a else None,
                    "other_company": {"id": b.id, "name": b.name, "domain": b.domain} if b else None,
                    "created_at": repo._iso(d.created_at)})
    return out


@router.get("/duplicates/logs")
def duplicate_logs(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
    rows = db.scalars(select(DuplicateLog).order_by(DuplicateLog.id.desc()).limit(limit)).all()
    return [
        {
            "id": r.id,
            "email_id": r.email_id,
            "match_type": r.match_type,
            "company_id": r.company_id,
            "matched_company_id": r.matched_company_id,
            "similarity": r.similarity,
            "details": r.details,
            "actor": r.actor,
            "created_at": repo._iso(r.created_at),
        }
        for r in rows
    ]


@router.post("/duplicates/{dup_id}/resolve")
def resolve_duplicate(dup_id: int, payload: DuplicateResolveIn, db: Session = Depends(get_db)):
    d = db.get(DuplicateCandidate, dup_id)
    if not d:
        raise HTTPException(404, "Duplicate candidate not found")
    if payload.action == "merge":
        merge_companies(db, keep_id=d.other_company_id, drop_id=d.company_id)
        d.status = "merged"
    else:
        d.status = "dismissed"
        db.add(DuplicateLog(
            email_id=d.email_id, match_type="dismissed", company_id=d.company_id, matched_company_id=d.other_company_id,
            similarity=d.similarity, details=f"Reviewer dismissed duplicate candidate #{d.id}", actor="reviewer",
        ))
    db.commit()
    return {"id": dup_id, "status": d.status}


# ------------------------------------------------------------------ Demo mode (synthetic, separate source)
@router.post("/demo/load")
def demo_load(db: Session = Depends(get_db)):
    n_before = db.scalar(select(func.count()).select_from(Email).where(Email.source == "demo")) or 0
    load_demo(db)
    n = db.scalar(select(func.count()).select_from(Email).where(Email.source == "demo")) or 0
    return {"loaded": n - n_before, "total_demo_emails": n, "note": "Synthetic emails run through the real pipeline; stored with source='demo'."}


@router.delete("/demo")
def demo_clear(db: Session = Depends(get_db)):
    return {"deleted": clear_demo(db)}


# ------------------------------------------------------------------ Export (/export/* and /exports/*)
@router.get("/export/excel")
@router.get("/exports/excel")
def export_excel(source: Source = "gmail", industry: str | None = None, db: Session = Depends(get_db)):
    if industry and not industry_by_slug(industry):
        raise HTTPException(404, f"Unknown industry '{industry}'")
    data = exporter.build_excel(db, source, industry)
    name = f"leadsense_{industry or 'all'}_{source}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.get("/export/csv")
@router.get("/exports/csv")
def export_csv(source: Source = "gmail", industry: str | None = None, db: Session = Depends(get_db)):
    if industry and not industry_by_slug(industry):
        raise HTTPException(404, f"Unknown industry '{industry}'")
    data = exporter.build_csv(db, source, industry)
    name = f"leadsense_{industry or 'all'}_{source}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(data, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}"'})
