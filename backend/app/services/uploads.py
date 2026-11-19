from __future__ import annotations

import csv
import email as pyemail
import hashlib
import io
import mailbox
import re
import tempfile
from datetime import datetime, timezone
from email.message import Message
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Email, UploadBatch
from .email_parser import KEPT_HEADERS, ParsedEmail, parse_message
from .pipeline import STATUS_REVIEW, STATUS_SUSPICIOUS, process_email

CSV_COLUMN_SYNONYMS = {
    "sender_name": ["sender_name", "sender name", "name", "from_name", "contact_name", "contact", "full_name", "author"],
    "sender_email": ["sender_email", "sender email", "email", "from", "from_email", "email_address", "mail", "sender"],
    "subject": ["subject", "subject_line", "title", "topic", "email_subject"],
    "body": ["body", "email_body", "message", "content", "text", "description", "body_text"],
    "received_at": ["received_at", "date", "email_date", "timestamp", "sent_at", "created_at", "time"],
}


def detect_csv_mapping(headers: list[str], explicit: dict[str, str] | None = None) -> dict[str, str]:
    """Map canonical keys (sender_name, sender_email, subject, body, received_at) to actual CSV column names."""
    explicit = {k: v for k, v in (explicit or {}).items() if v}
    lower_map = {h.strip().lower(): h for h in headers if h}
    resolved: dict[str, str] = {}
    for field, candidates in CSV_COLUMN_SYNONYMS.items():
        if field in explicit and explicit[field] in headers:
            resolved[field] = explicit[field]
            continue
        if field in explicit and explicit[field].strip().lower() in lower_map:
            resolved[field] = lower_map[explicit[field].strip().lower()]
            continue
        for cand in candidates:
            if cand in lower_map:
                resolved[field] = lower_map[cand]
                break
    return resolved


def _parse_date(val: str | None) -> datetime:
    if not val or not str(val).strip():
        return datetime.now(timezone.utc)
    s = str(val).strip()
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.now(timezone.utc)


def _msg_id(prefix: str, content: str) -> str:
    return f"{prefix}-{hashlib.sha256(content.encode('utf-8', 'ignore')).hexdigest()[:16]}"


def parse_csv_bytes(data: bytes, column_mapping: dict[str, str] | None = None) -> tuple[list[ParsedEmail], dict[str, str], list[str]]:
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = list(reader.fieldnames or [])
    if not headers:
        raise ValueError("CSV file has no header row")
    mapping = detect_csv_mapping(headers, column_mapping)
    if "body" not in mapping and "subject" not in mapping:
        raise ValueError(f"Could not map CSV columns for 'body' or 'subject'. Found headers: {headers}")
    parsed: list[ParsedEmail] = []
    errors: list[str] = []
    for idx, row in enumerate(reader, start=1):
        try:
            sname = (row.get(mapping.get("sender_name", ""), "") or "").strip()
            semail = (row.get(mapping.get("sender_email", ""), "") or "").strip()
            subj = (row.get(mapping.get("subject", ""), "") or "").strip()
            body = (row.get(mapping.get("body", ""), "") or "").strip()
            rdate = (row.get(mapping.get("received_at", ""), "") or "").strip()
            if not subj and not body and not semail:
                continue
            from_hdr = f"{sname} <{semail}>".strip() if "<" not in semail and semail else (semail or sname)
            mid = _msg_id("csv", f"{semail}|{subj}|{body[:200]}")
            has_html = bool(re.search(r"<(html|body|p|div|br|table|a)\b", body, re.I))
            parsed.append(
                parse_message(
                    message_id=mid,
                    thread_id=f"thread-{mid}",
                    from_header=from_hdr,
                    subject=subj,
                    text=None if has_html else body,
                    html=body if has_html else None,
                    headers={},
                    date=_parse_date(rdate),
                )
            )
        except Exception as e:
            errors.append(f"Row {idx}: {e}")
    return parsed, mapping, errors


def _decode_hdr(val: str | None) -> str:
    if not val:
        return ""
    from email.header import decode_header
    parts = []
    for chunk, enc in decode_header(str(val)):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(str(chunk))
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def _mime_to_parsed(msg: Message, fallback_prefix: str = "eml") -> ParsedEmail:
    hdrs: dict[str, str] = {}
    for k in KEPT_HEADERS + ["Subject", "Date"]:
        if msg.get(k):
            hdrs[k] = _decode_hdr(msg.get(k)) if k in ("Subject", "From") else str(msg.get(k))
    text_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[dict] = []
    if msg.is_multipart():
        for part in msg.walk():
            cdisp = str(part.get("Content-Disposition") or "")
            fname = part.get_filename()
            ctype = part.get_content_type()
            if fname or "attachment" in cdisp.lower():
                payload = part.get_payload(decode=True) or b""
                attachments.append({"filename": fname or "attachment", "mime_type": ctype, "size": len(payload)})
            elif ctype == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    text_parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
            elif ctype == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    html_parts.append(payload.decode(part.get_content_charset() or "utf-8", errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        raw = payload.decode(msg.get_content_charset() or "utf-8", errors="replace") if payload else str(msg.get_payload() or "")
        if msg.get_content_type() == "text/html":
            html_parts.append(raw)
        else:
            text_parts.append(raw)
    from_hdr = hdrs.get("From", "")
    subj = hdrs.get("Subject", "")
    body_join = "\n".join(text_parts) or "\n".join(html_parts)
    raw_mid = (hdrs.get("Message-ID") or "").strip("<> ")
    mid = f"{fallback_prefix}-{raw_mid}" if raw_mid else _msg_id(fallback_prefix, f"{from_hdr}|{subj}|{body_join[:200]}")
    return parse_message(
        message_id=mid,
        thread_id=f"thread-{mid}",
        from_header=from_hdr,
        subject=subj,
        text="\n".join(text_parts) or None,
        html="\n".join(html_parts) or None,
        headers=hdrs,
        attachments=attachments,
        date=_parse_date(hdrs.get("Date")),
    )


def parse_eml_bytes(data: bytes) -> list[ParsedEmail]:
    msg = pyemail.message_from_bytes(data)
    return [_mime_to_parsed(msg, "eml")]


def parse_mbox_bytes(data: bytes) -> list[ParsedEmail]:
    with tempfile.NamedTemporaryFile(suffix=".mbox", delete=True) as tmp:
        tmp.write(data)
        tmp.flush()
        box = mailbox.mbox(tmp.name)
        return [_mime_to_parsed(m, "mbox") for m in box]


def parse_msg_bytes(data: bytes, filename: str = "message.msg") -> list[ParsedEmail]:
    """Parse Outlook .msg files (supports RFC822-wrapped .msg or OLE2 binary stream extraction)."""
    if not data.startswith(b"\xd0\xcf\x11\xe0"):
        return [_mime_to_parsed(pyemail.message_from_bytes(data), "msg")]
    # Extract readable UTF-16LE and ASCII strings from OLE2 compound file
    utf16_chunks = [m.group(0).decode("utf-16le", errors="ignore") for m in re.finditer(rb"(?:[\x20-\x7e\r\n\t]\x00){6,}", data)]
    ascii_chunks = [m.group(0).decode("latin1", errors="ignore") for m in re.finditer(rb"[\x20-\x7e\r\n\t]{12,}", data)]
    combined = "\n".join(utf16_chunks + ascii_chunks)
    emails_found = re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", combined)
    sender = emails_found[0] if emails_found else "unknown@unknown.invalid"
    subj_match = re.search(r"Subject:\s*([^\r\n]+)", combined, re.I)
    subject = subj_match.group(1).strip() if subj_match else Path(filename).stem
    mid = _msg_id("msg", f"{sender}|{subject}|{combined[:300]}")
    return [
        parse_message(
            message_id=mid,
            thread_id=f"thread-{mid}",
            from_header=sender,
            subject=subject,
            text=combined[:8000],
            html=None,
            headers={},
            date=datetime.now(timezone.utc),
        )
    ]


def ingest_parsed_batch(
    db: Session,
    *,
    filename: str,
    file_type: str,
    parsed_emails: list[ParsedEmail],
    source: str = "upload",
    column_mapping: dict[str, str] | None = None,
    parse_errors: list[str] | None = None,
) -> UploadBatch:
    batch = UploadBatch(
        filename=filename,
        file_type=file_type,
        source=source,
        status="running",
        total_records=len(parsed_emails),
        column_mapping=column_mapping or {},
        errors=list(parse_errors or []),
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)

    email_ids: list[int] = []
    for idx, p in enumerate(parsed_emails, start=1):
        try:
            existing = db.scalar(select(Email).where(Email.source == source, Email.gmail_message_id == p.message_id))
            if existing:
                batch.duplicate_records += 1
                email_ids.append(existing.id)
                continue
            em = process_email(db, p, source)
            batch.processed_records += 1
            if em.status in (STATUS_REVIEW, STATUS_SUSPICIOUS):
                batch.needs_review_records += 1
            email_ids.append(em.id)
        except Exception as e:
            db.rollback()
            batch.failed_records += 1
            batch.errors = [*batch.errors, f"Item {idx}: {e}"]
    batch.email_ids = email_ids
    batch.status = "completed" if batch.failed_records == 0 or batch.processed_records > 0 else "failed"
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return batch


def batch_to_dict(b: UploadBatch) -> dict[str, Any]:
    return {
        "id": b.id,
        "filename": b.filename,
        "file_type": b.file_type,
        "source": b.source,
        "status": b.status,
        "total_records": b.total_records,
        "processed_records": b.processed_records,
        "duplicate_records": b.duplicate_records,
        "needs_review_records": b.needs_review_records,
        "failed_records": b.failed_records,
        "column_mapping": b.column_mapping,
        "email_ids": b.email_ids,
        "errors": b.errors,
        "created_at": b.created_at.isoformat() if b.created_at else None,
    }
