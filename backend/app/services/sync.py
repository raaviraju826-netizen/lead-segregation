from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from sqlalchemy import select

from ..config import get_settings
from ..db import SessionLocal
from ..models import AppState, Email, SyncHistory
from . import gmail
from .email_parser import parse_gmail_api_message
from .pipeline import STATUS_REVIEW, STATUS_SUSPICIOUS, process_email

log = logging.getLogger(__name__)
_sync_lock = threading.Lock()
HISTORY_KEY = "gmail_history_id"


def _get_state(db, key: str) -> str | None:
    row = db.get(AppState, key)
    return row.value if row else None


def _set_state(db, key: str, value: str) -> None:
    row = db.get(AppState, key)
    if row:
        row.value = value
    else:
        db.add(AppState(key=key, value=value))


def run_gmail_sync(trigger: str = "manual") -> SyncHistory:
    """Incremental, read-only sync. Safe against concurrent calls (second caller gets an error)."""
    if not _sync_lock.acquire(blocking=False):
        raise gmail.GmailError("A sync is already running.", "sync_running", 409)
    db = SessionLocal()
    sync = SyncHistory(source="gmail", trigger=trigger)
    db.add(sync)
    db.commit()
    try:
        svc, prof = gmail.get_verified_service()  # re-verifies the mailbox equals TARGET_GMAIL_ADDRESS on every sync
        start_id = _get_state(db, HISTORY_KEY)
        ids = gmail.list_new_ids(svc, start_id) if start_id else None
        sync.mode = "incremental" if ids is not None else "full"
        if ids is None:
            ids = gmail.list_inbox_ids(svc, get_settings().sync_max_messages)
        sync.fetched = len(ids)
        for mid in ids:
            if db.scalar(select(Email.id).where(Email.source == "gmail", Email.gmail_message_id == mid)):
                continue  # already processed -> never reprocess
            try:
                parsed = parse_gmail_api_message(gmail.get_message(svc, mid))
                email = process_email(db, parsed, "gmail")
                sync.processed += 1
                if email.status in (STATUS_REVIEW, STATUS_SUSPICIOUS):
                    sync.needs_review += 1
            except Exception as e:
                db.rollback()
                sync.failed += 1
                log.exception("Failed to process message %s: %s", mid, type(e).__name__)
        _set_state(db, HISTORY_KEY, str(prof["historyId"]))
        sync.status = "success"
    except Exception as e:
        db.rollback()
        sync.status = "failed"
        sync.error = str(e)[:500]
        log.warning("Gmail sync failed: %s", str(e)[:300])
    finally:
        sync.finished_at = datetime.now(timezone.utc)
        db.add(sync)
        db.commit()
        db.refresh(sync)
        db.close()
        _sync_lock.release()
    return sync
