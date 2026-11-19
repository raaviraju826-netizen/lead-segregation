from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Select, asc, desc, func, or_, select
from sqlalchemy.orm import Session, selectinload

from .models import (Company, CompanyTrustAssessment, Contact, DuplicateCandidate, DuplicateLog, Email,
                     EmailTrustAssessment, IndustryClassification, LeadRelevanceAssessment, SyncHistory)
from .services.taxonomy import industry_by_slug, industry_names

NOT_LEAD = "Not a Lead"
SUSPICIOUS = "Suspicious — Review Required"

SORTS = {
    "date": Email.email_date, "company": Company.name, "industry": Email.industry, "status": Email.status,
    "confidence": IndustryClassification.confidence, "company_trust": CompanyTrustAssessment.score,
    "email_trust": EmailTrustAssessment.score, "relevance": LeadRelevanceAssessment.score, "subject": Email.subject,
}

FAKE_KEYWORD_PATTERNS = [
    "wire transfer", "western union", "gift card", "bitcoin", "crypto", "verify your account",
    "confirm your password", "account will be suspended", "account suspended", "account locked",
    "you have won", "win iphone", "won iphone", "free iphone", "jackpot", "lucky winner",
    "inheritance", "lottery", "beneficiary", "claim your prize", "claim your reward",
    "urgent payment", "within 24 hours", "immediate payment", "bank details have changed",
    "revised bank account", "share your bank details", "send your bank details", "otp", "card number",
    "100% guaranteed", "make money fast", "ignore all previous instructions", "set the trust score",
]

REAL_INTENT_KEYWORDS = [
    "proposal", "quotation", "quote", "rfq", "requirement", "enquiry", "inquiry", "demo",
    "partnership", "collaboration", "budget", "timeline", "project", "implementation", "portal",
    "website", "website design", "web design", "dashboard", "app", "software", "education",
    "institution", "college", "textile", "manufacturing", "logistics", "warehouse",
]


def compute_verdict_info(e: Email) -> dict[str, Any]:
    """Determine REAL vs FAKE verdict, keyword evidence, authenticity score (0-100), and industry accuracy (0-100)."""
    c, ct, et = e.classification, e.company_trust, e.email_trust
    ex = e.extracted or {}
    text_low = f"{e.subject or ''}\n{e.body_text or ''}".lower()

    fake_kws: list[str] = []
    for kw in FAKE_KEYWORD_PATTERNS:
        if kw in text_low:
            fake_kws.append(kw)
    for flag in (et.flags or []):
        short_flag = flag.split(":")[0].strip()
        if short_flag and short_flag not in fake_kws:
            fake_kws.append(short_flag)

    real_kws: list[str] = []
    ind_sigs = ex.get("industry_signals") or {}
    for kws in ind_sigs.values():
        for kw in kws:
            if kw not in real_kws:
                real_kws.append(kw)
    for kw in REAL_INTENT_KEYWORDS:
        if re.search(rf"\b{re.escape(kw)}\b", text_low) and kw not in real_kws:
            real_kws.append(kw)

    is_fake = (
        e.status == SUSPICIOUS
        or et.risk in ("High", "Medium")
        or e.lead_type == "Spam or suspicious message"
        or len(fake_kws) > 0
    )

    raw_score = round(0.60 * et.score + 0.40 * ct.score - (12.0 * len(fake_kws)), 1)
    if is_fake:
        real_fake_score = max(5.0, min(42.0, raw_score))
        verdict = "FAKE"
        verdict_reason = (
            f"Detected FAKE / Suspicious indicators ({', '.join(fake_kws[:4]) or 'high email risk'}). "
            f"Authenticity score {real_fake_score}% is below the 50% safety threshold."
        )
    else:
        real_fake_score = max(55.0, min(98.0, round(0.55 * et.score + 0.45 * max(ct.score, 45.0), 1)))
        verdict = "REAL"
        verdict_reason = (
            f"Verified REAL business enquiry matching industry & intent keywords ({', '.join(real_kws[:5]) or 'clean headers'}) "
            f"with zero scam/phishing keywords and {real_fake_score}% authenticity score."
        )

    accuracy_score = round((c.confidence if c else 0.0) * 100.0, 1)
    return {
        "verdict": verdict,
        "real_fake_score": real_fake_score,
        "accuracy_score": accuracy_score,
        "real_keywords": real_kws[:8],
        "fake_keywords": fake_kws[:8],
        "verdict_reason": verdict_reason,
    }


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _parse_date_filter(val: str | None, end_of_day: bool = False) -> datetime | None:
    if not val:
        return None
    try:
        if len(val) == 10:
            dt = datetime.fromisoformat(val + ("T23:59:59+00:00" if end_of_day else "T00:00:00+00:00"))
        else:
            dt = datetime.fromisoformat(val.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def base_query() -> Select:
    return (
        select(Email)
        .join(IndustryClassification, IndustryClassification.email_id == Email.id)
        .join(CompanyTrustAssessment, CompanyTrustAssessment.email_id == Email.id)
        .join(EmailTrustAssessment, EmailTrustAssessment.email_id == Email.id)
        .join(LeadRelevanceAssessment, LeadRelevanceAssessment.email_id == Email.id)
        .outerjoin(Company, Company.id == Email.company_id)
        .outerjoin(Contact, Contact.id == Email.contact_id)
    )


def apply_filters(q: Select, *, source: str | None = None, industry: str | None = None, sub_industry: str | None = None,
                  status: str | None = None, priority: str | None = None, company_trust: str | None = None,
                  email_risk: str | None = None, search: str | None = None, only_leads: bool = False,
                  lead_type: str | None = None, date_from: str | None = None, date_to: str | None = None,
                  verdict: str | None = None) -> Select:
    if source and source != "all":
        q = q.where(Email.source == source)
    if industry:
        ind = industry_by_slug(industry)
        q = q.where(Email.industry == (ind["name"] if ind else industry))
    if sub_industry:
        q = q.where(Email.sub_industry == sub_industry)
    if status:
        q = q.where(Email.status == status)
    if verdict == "REAL":
        if not industry:
            q = q.where(Email.industry.in_(industry_names()))
        q = q.where(Email.status.notin_([NOT_LEAD, SUSPICIOUS]), EmailTrustAssessment.risk.notin_(["High", "Medium"]),
                    Email.lead_type != "Spam or suspicious message")
    elif verdict == "FAKE":
        if not industry:
            q = q.where(Email.industry.in_(industry_names()))
        q = q.where(Email.status != NOT_LEAD,
                    or_(Email.status == SUSPICIOUS, EmailTrustAssessment.risk.in_(["High", "Medium"]),
                        Email.lead_type == "Spam or suspicious message"))
    elif verdict == "ALL":
        if not industry:
            q = q.where(Email.industry.in_(industry_names()))
        q = q.where(Email.status != NOT_LEAD)
    elif only_leads:
        q = q.where(Email.status.notin_([NOT_LEAD, SUSPICIOUS]))
    if priority:
        q = q.where(LeadRelevanceAssessment.priority == priority)
    if company_trust:
        q = q.where(CompanyTrustAssessment.label == company_trust)
    if email_risk:
        q = q.where(EmailTrustAssessment.risk == email_risk)
    if lead_type:
        q = q.where(Email.lead_type == lead_type)
    dt_from = _parse_date_filter(date_from, end_of_day=False)
    if dt_from:
        q = q.where(Email.email_date >= dt_from)
    dt_to = _parse_date_filter(date_to, end_of_day=True)
    if dt_to:
        q = q.where(Email.email_date <= dt_to)
    if search:
        like = f"%{search.strip().lower()}%"
        q = q.where(or_(func.lower(Email.subject).like(like), func.lower(Email.sender_email).like(like),
                        func.lower(func.coalesce(Company.name, "")).like(like), func.lower(func.coalesce(Contact.name, "")).like(like),
                        func.lower(func.coalesce(IndustryClassification.interest_area, "")).like(like)))
    return q


def list_emails(db: Session, *, sort: str = "date", order: str = "desc", page: int = 1, page_size: int = 25, **filters) -> dict:
    q = apply_filters(base_query(), **filters)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    col = SORTS.get(sort, Email.email_date)
    q = q.order_by((desc if order == "desc" else asc)(col).nulls_last(), Email.id.desc())
    q = q.options(selectinload(Email.classification), selectinload(Email.company_trust), selectinload(Email.email_trust),
                  selectinload(Email.lead_relevance), selectinload(Email.company), selectinload(Email.contact))
    rows = db.scalars(q.offset((page - 1) * page_size).limit(page_size)).all()
    return {"items": [summary(e) for e in rows], "total": total or 0, "page": page, "page_size": page_size,
            "pages": max(1, -(-(total or 0) // page_size))}


def all_emails(db: Session, **filters) -> list[Email]:
    q = apply_filters(base_query(), **filters).order_by(Email.email_date.desc().nulls_last())
    q = q.options(selectinload(Email.classification), selectinload(Email.company_trust), selectinload(Email.email_trust),
                  selectinload(Email.lead_relevance), selectinload(Email.company), selectinload(Email.contact))
    return list(db.scalars(q))


def summary(e: Email) -> dict[str, Any]:
    c, ct, et, lr = e.classification, e.company_trust, e.email_trust, e.lead_relevance
    vinfo = compute_verdict_info(e)
    return {
        "id": e.id, "source": e.source, "company_name": e.company.name if e.company else None,
        "contact_name": (e.contact.name if e.contact else None) or e.sender_name or None, "email": e.sender_email,
        "phone": e.contact.phone if e.contact else None, "website": (e.extracted or {}).get("website"),
        "subject": e.subject, "industry": e.industry, "sub_industry": e.sub_industry, "interest_area": c.interest_area,
        "confidence": round(c.confidence, 3), "company_trust_score": ct.score, "company_trust_label": ct.label,
        "email_trust_score": et.score, "email_risk": et.risk, "relevance_score": lr.score, "priority": lr.priority,
        "lead_type": e.lead_type, "status": e.status, "status_reasons": e.status_reasons or [], "reviewed": e.reviewed,
        "email_date": _iso(e.email_date), "reason": c.reason, "classification_method": c.method,
        **vinfo,
    }


def detail(db: Session, e: Email) -> dict[str, Any]:
    c, ct, et, lr = e.classification, e.company_trust, e.email_trust, e.lead_relevance
    dups = db.scalars(select(DuplicateCandidate).where(DuplicateCandidate.email_id == e.id)).all()
    other = {d.other_company_id: db.get(Company, d.other_company_id) for d in dups}
    ex = dict(e.extracted or {})
    ex.pop("classification_text", None)
    return {
        **summary(e),
        "thread_id": e.thread_id, "gmail_message_id": e.gmail_message_id, "sender_name": e.sender_name, "reply_to": e.reply_to,
        "body": e.body_text, "html_present": e.body_html_present, "attachments": e.attachments, "headers": e.headers,
        "extracted": ex, "company_id": e.company_id, "job_title": e.contact.job_title if e.contact else None,
        "classification": {
            "industry": c.industry, "sub_industry": c.sub_industry, "sub_industry_confidence": c.sub_industry_confidence,
            "confidence": c.confidence, "llm_confidence": c.llm_confidence, "retrieval_similarity": c.retrieval_similarity,
            "reason": c.reason, "evidence": c.evidence, "interest_area": c.interest_area, "method": c.method, "llm_used": c.llm_used,
            "retrieved_chunks": c.retrieved_chunks,
            "formula": "final = 0.6 x model confidence + 0.4 x top retrieval similarity (of predicted industry)",
        },
        "company_trust": {"score": ct.score, "label": ct.label, "signals": ct.signals, "note": ct.note},
        "email_trust": {"score": et.score, "risk": et.risk, "signals": et.signals, "flags": et.flags},
        "lead_relevance": {"score": lr.score, "priority": lr.priority, "lead_type": lr.lead_type, "breakdown": lr.breakdown},
        "reviews": [{"id": r.id, "reviewer": r.reviewer, "action": r.action, "previous": r.previous, "new": r.new, "notes": r.notes,
                     "created_at": _iso(r.created_at)} for r in e.reviews],
        "duplicates": [{"id": d.id, "similarity": d.similarity, "reason": d.reason, "status": d.status,
                        "other_company": {"id": d.other_company_id, "name": other[d.other_company_id].name if other[d.other_company_id] else None}}
                       for d in dups],
    }


def stats(db: Session, source: str = "gmail") -> dict[str, Any]:
    q = apply_filters(base_query(), source=source)
    emails = list(db.scalars(q.options(selectinload(Email.classification), selectinload(Email.company_trust),
                                       selectinload(Email.email_trust), selectinload(Email.lead_relevance))))
    leads = [e for e in emails if e.status not in (NOT_LEAD, SUSPICIOUS)]
    by_ind = {n: sum(1 for e in leads if e.industry == n) for n in industry_names()}

    # Per-industry Real vs Fake breakdown + Accuracy score
    industry_verdict_stats: dict[str, dict[str, Any]] = {}
    all_acc: list[float] = []
    for ind_name in industry_names():
        ind_emails = [e for e in emails if e.industry == ind_name and e.status != NOT_LEAD]
        real_list = []
        fake_list = []
        acc_list = []
        for e in ind_emails:
            vi = compute_verdict_info(e)
            acc_list.append(vi["accuracy_score"])
            all_acc.append(vi["accuracy_score"])
            if vi["verdict"] == "FAKE":
                fake_list.append(vi["real_fake_score"])
            else:
                real_list.append(vi["real_fake_score"])
        industry_verdict_stats[ind_name] = {
            "total": len(ind_emails),
            "real": len(real_list),
            "fake": len(fake_list),
            "avg_accuracy": round(sum(acc_list) / len(acc_list), 1) if acc_list else 0.0,
            "avg_real_score": round(sum(real_list) / len(real_list), 1) if real_list else 0.0,
            "avg_fake_score": round(sum(fake_list) / len(fake_list), 1) if fake_list else 0.0,
        }

    total_real_mails = sum(v["real"] for v in industry_verdict_stats.values())
    total_fake_mails = sum(v["fake"] for v in industry_verdict_stats.values())
    overall_accuracy = round(sum(all_acc) / len(all_acc), 1) if all_acc else 0.0

    by_sub: dict[str, int] = {}
    for e in leads:
        if e.industry in industry_names():
            sub_name = e.sub_industry or "General"
            key = f"{e.industry} · {sub_name}"
            by_sub[key] = by_sub.get(key, 0) + 1
    prio = {p: sum(1 for e in leads if e.industry in industry_names() and e.lead_relevance.priority == p) for p in ("High", "Medium", "Low")}
    ctrust: dict[str, int] = {}
    erisk: dict[str, int] = {}
    conf_buckets = {"0.00–0.49": 0, "0.50–0.74": 0, "0.75–1.00": 0}
    active_ind_emails = [e for e in emails if e.industry in industry_names() and e.status != NOT_LEAD]
    target_pool = active_ind_emails if active_ind_emails else emails
    for e in target_pool:
        ctrust[e.company_trust.label] = ctrust.get(e.company_trust.label, 0) + 1
        erisk[e.email_trust.risk] = erisk.get(e.email_trust.risk, 0) + 1
        cval = e.classification.confidence
        if cval >= 0.75:
            conf_buckets["0.75–1.00"] += 1
        elif cval >= 0.50:
            conf_buckets["0.50–0.74"] += 1
        else:
            conf_buckets["0.00–0.49"] += 1
    by_day: dict[str, dict[str, int]] = {}
    for e in emails:
        d = (e.email_date or e.created_at).date().isoformat()
        row = by_day.setdefault(d, {"date": d, "emails": 0, "leads": 0})
        row["emails"] += 1
        row["leads"] += e in leads
    statuses: dict[str, int] = {}
    for e in emails:
        statuses[e.status] = statuses.get(e.status, 0) + 1

    unique_comp_ids = {e.company_id for e in emails if e.company_id is not None}
    open_dups = db.scalar(select(func.count()).select_from(DuplicateCandidate).where(DuplicateCandidate.status == "open")) or 0
    dup_log_count = db.scalar(select(func.count()).select_from(DuplicateLog)) or 0
    last = db.scalars(select(SyncHistory).where(SyncHistory.source == "gmail", SyncHistory.status == "success")
                      .order_by(SyncHistory.finished_at.desc())).first()
    by_source = {
        s: db.scalar(select(func.count()).select_from(Email).where(Email.source == s)) or 0
        for s in ("gmail", "upload", "demo")
    }
    return {
        "source": source,
        "total_emails": len(emails),
        "unique_companies": len(unique_comp_ids),
        "total_leads": len(leads),
        "total_real_mails": total_real_mails,
        "total_fake_mails": total_fake_mails,
        "overall_accuracy": overall_accuracy,
        "by_industry": by_ind,
        "industry_verdict_stats": industry_verdict_stats,
        "by_sub_industry": by_sub,
        "needs_review": statuses.get("Needs Review", 0),
        "suspicious": statuses.get(SUSPICIOUS, 0),
        "other_unknown": statuses.get("Other / Unknown", 0),
        "not_a_lead": statuses.get(NOT_LEAD, 0),
        "duplicate_records": max(open_dups, dup_log_count),
        "open_duplicates": open_dups,
        "high_priority": prio["High"],
        "priority_distribution": prio,
        "company_trust_distribution": ctrust,
        "email_risk_distribution": erisk,
        "status_distribution": statuses,
        "confidence_distribution": conf_buckets,
        "by_source": by_source,
        "trend": sorted(by_day.values(), key=lambda r: r["date"]),
        "last_sync": _iso(last.finished_at) if last else None,
    }
