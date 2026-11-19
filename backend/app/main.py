from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from .api import public, router
from .config import get_settings
from .db import SessionLocal, init_db
from .logging_conf import setup_logging
from .models import IndustryTaxonomy, ReviewHistory, SubIndustryRecord
from .services import gmail, knowledge_base as kb
from .services.sync import run_gmail_sync
from .services.taxonomy import load_taxonomy

log = logging.getLogger("leadsense")


def seed_taxonomy() -> None:
    from sqlalchemy import delete
    db = SessionLocal()
    try:
        for ind in load_taxonomy()["industries"]:
            row = db.scalar(select(IndustryTaxonomy).where(IndustryTaxonomy.name == ind["name"]))
            data = dict(slug=ind["slug"], description=ind["description"].strip(), keywords=ind["keywords"], sub_industries=ind["sub_industries"], active=True)
            if row:
                for k, v in data.items():
                    setattr(row, k, v)
            else:
                row = IndustryTaxonomy(name=ind["name"], **data)
                db.add(row)
                db.flush()
            db.execute(delete(SubIndustryRecord).where(SubIndustryRecord.industry_id == row.id))
            for sub_name, meta in ind["sub_industries"].items():
                db.add(SubIndustryRecord(
                    industry_id=row.id,
                    industry_name=ind["name"],
                    name=sub_name,
                    keywords=meta.get("keywords", []),
                ))
        db.commit()
    finally:
        db.close()


def reviewed_examples() -> list[tuple[int, str, str, str | None]]:
    from .models import Email
    db = SessionLocal()
    try:
        rows = []
        for e in db.scalars(select(Email).where(Email.reviewed.is_(True))):
            last = e.reviews[-1] if e.reviews else None
            if last and "industry_" in last.action and e.status == "Classified":
                ct = (e.extracted or {}).get("classification_text") or {}
                text = " . ".join(ct.get(k, "") for k in ("company name", "email body", "signature", "subject") if ct.get(k)) or e.subject
                rows.append((e.id, text, e.industry, e.sub_industry))
        return rows
    finally:
        db.close()


async def _background_sync(seconds: int):
    from .services import gmail_imap
    while True:
        await asyncio.sleep(seconds)
        try:
            if gmail.TOKEN_FILE.exists():
                await asyncio.get_running_loop().run_in_executor(None, run_gmail_sync, "auto_poll")
            elif gmail_imap.has_imap_credentials():
                await asyncio.get_running_loop().run_in_executor(None, gmail_imap.run_imap_sync, "auto_poll")
        except Exception as e:  # never kill the loop
            log.warning("Background sync error: %s", str(e)[:200])


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    seed_taxonomy()
    n = kb.ensure_knowledge_base(reviewed_examples())
    s = get_settings()
    log.info("LeadSense AI started: %d KB chunks, LLM %s, target configured: %s", n, "ON" if s.llm_enabled else "OFF (heuristic mode)", s.target_configured)
    interval_sec = (s.sync_interval_minutes * 60) if s.sync_interval_minutes > 0 else 15
    task = asyncio.create_task(_background_sync(interval_sec))
    yield
    if task:
        task.cancel()


app = FastAPI(title="LeadSense AI", version="1.0.0", lifespan=lifespan,
              description="Industry-wise lead segregation & trust intelligence. Gmail access is read-only.")
app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
                   allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["*"])
app.include_router(public)
app.include_router(router)


@app.exception_handler(gmail.GmailError)
async def gmail_error_handler(_: Request, exc: gmail.GmailError):
    return JSONResponse(status_code=exc.status, content={"detail": str(exc), "code": exc.code})


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    return JSONResponse(status_code=422, content={"detail": "Invalid request", "errors": [{"loc": e["loc"], "msg": e["msg"]} for e in exc.errors()]})


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error: %s", type(exc).__name__)  # message only; never request bodies
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
