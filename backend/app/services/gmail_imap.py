from __future__ import annotations

import email as pyemail
import imaplib
import json
import logging
import os
import threading
from datetime import datetime, timezone

from sqlalchemy import select

from ..config import SECRETS_DIR, get_settings
from ..db import SessionLocal
from ..models import Email, SyncHistory
from .gmail import GmailError, _fernet
from .pipeline import STATUS_REVIEW, STATUS_SUSPICIOUS, process_email
from .uploads import _mime_to_parsed

log = logging.getLogger(__name__)
IMAP_TOKEN_FILE = SECRETS_DIR / "gmail_imap.enc"
_imap_lock = threading.Lock()


def has_imap_credentials() -> bool:
    return IMAP_TOKEN_FILE.exists() or bool(os.environ.get("GMAIL_APP_PASSWORD", "").strip())


def save_imap_app_password(email_address: str, app_password: str) -> str:
    """Verify read-only IMAP login against imap.gmail.com:993 for TARGET_GMAIL_ADDRESS and store encrypted."""
    s = get_settings()
    target = (s.target_gmail_address or "rajurajuu970@gmail.com").strip().lower()
    addr = email_address.strip().lower()
    if addr != target:
        raise GmailError(
            f"Account ({addr}) does not match configured target inbox ({target}).",
            "account_mismatch",
            403,
        )
    clean_pw = app_password.replace(" ", "").strip()
    if len(clean_pw) < 8:
        raise GmailError("Please enter a valid 16-character Google App Password.", "invalid_app_password", 400)
    try:
        conn = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=12)
        conn.login(target, clean_pw)
        conn.select("INBOX", readonly=True)
        conn.logout()
    except imaplib.IMAP4.error as e:
        raise GmailError(
            f"Google IMAP authentication failed for {target}: {e}. Make sure 2-Step Verification is on and use a 16-character App Password from myaccount.google.com/apppasswords.",
            "imap_auth_failed",
            401,
        )
    except OSError as e:
        log.warning("IMAP network check warning (saving credentials for background retry): %s", e)
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"email": target, "app_password": clean_pw}).encode("utf-8")
    IMAP_TOKEN_FILE.write_bytes(_fernet().encrypt(payload))
    IMAP_TOKEN_FILE.chmod(0o600)
    return target


def load_imap_credentials() -> tuple[str, str] | None:
    if IMAP_TOKEN_FILE.exists():
        try:
            data = json.loads(_fernet().decrypt(IMAP_TOKEN_FILE.read_bytes()).decode("utf-8"))
            return data["email"], data["app_password"]
        except Exception:
            pass
    env_pw = os.environ.get("GMAIL_APP_PASSWORD", "").replace(" ", "").strip()
    if env_pw:
        target = (get_settings().target_gmail_address or "rajurajuu970@gmail.com").strip().lower()
        return target, env_pw
    return None


def disconnect_imap() -> None:
    IMAP_TOKEN_FILE.unlink(missing_ok=True)


def run_imap_sync(trigger: str = "manual", max_messages: int = 30) -> SyncHistory:
    """Pull latest incoming emails from imap.gmail.com:993 in strictly READ-ONLY mode (readonly=True)."""
    creds = load_imap_credentials()
    if not creds:
        raise GmailError("Gmail is not connected yet.", "not_connected", 401)
    email_addr, app_pw = creds
    target = (get_settings().target_gmail_address or "rajurajuu970@gmail.com").strip().lower()
    if email_addr != target:
        disconnect_imap()
        raise GmailError(f"Stored account {email_addr} does not match target {target}", "account_mismatch", 403)

    if not _imap_lock.acquire(timeout=12):
        raise GmailError("A sync is already running.", "sync_running", 409)
    db = SessionLocal()
    sync = SyncHistory(source="gmail", trigger=trigger, mode="incremental", status="running")
    db.add(sync)
    db.commit()
    try:
        conn = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=20)
        conn.login(email_addr, app_pw)
        conn.select("INBOX", readonly=True)  # STRICTLY READ-ONLY
        typ, data = conn.uid("search", None, "ALL")
        uids = (data[0].split() if typ == "OK" and data and data[0] else [])[-max_messages:]
        sync.fetched = len(uids)
        for uid_bytes in reversed(uids):
            uid_str = uid_bytes.decode("ascii", errors="ignore")
            mid = f"imap-uid-{uid_str}"
            if db.scalar(select(Email.id).where(Email.source == "gmail", Email.gmail_message_id == mid)):
                continue
            ftyp, fdata = conn.uid("fetch", uid_bytes, "(RFC822)")
            if ftyp != "OK" or not fdata or not isinstance(fdata[0], tuple):
                continue
            raw_bytes = fdata[0][1]
            msg = pyemail.message_from_bytes(raw_bytes)
            parsed = _mime_to_parsed(msg, "imap")
            parsed.message_id = mid
            em = process_email(db, parsed, "gmail")
            sync.processed += 1
            if em.status in (STATUS_REVIEW, STATUS_SUSPICIOUS):
                sync.needs_review += 1
        conn.logout()
        sync.status = "success"
    except OSError as e:
        db.rollback()
        sync.status = "failed"
        sync.error = f"Cannot reach imap.gmail.com (network/DNS problem: {e}). Showing previously synced emails; will retry automatically."
        log.warning("IMAP network unreachable: %s", e)
    except Exception as e:
        db.rollback()
        sync.status = "failed"
        sync.error = str(e)[:500]
        log.warning("IMAP sync failed: %s", str(e)[:250])
    finally:
        sync.finished_at = datetime.now(timezone.utc)
        db.add(sync)
        db.commit()
        db.refresh(sync)
        db.close()
        _imap_lock.release()
    return sync
