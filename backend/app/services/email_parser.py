from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime

from bs4 import BeautifulSoup

KEPT_HEADERS = [
    "From", "To", "Delivered-To", "Reply-To", "Return-Path", "Authentication-Results", "Received-SPF", "DKIM-Signature", "List-Unsubscribe",
    "Auto-Submitted", "Precedence", "X-Auto-Response-Suppress", "Message-ID", "X-Failed-Recipients",
]

_FWD_RE = re.compile(r"-{3,}\s*(Forwarded message|Original Message)\s*-{3,}|^Begin forwarded message:", re.I | re.M)
_REPLY_HDR_RE = re.compile(r"^(On .{5,200}wrote:|Le .{5,200}a écrit :)\s*$", re.I)
_CLOSERS = re.compile(
    r"^(best regards|kind regards|warm regards|regards|thanks & regards|thanks and regards|thanks|thank you|sincerely|"
    r"yours sincerely|yours faithfully|with regards|cheers|best|respectfully)[,.!]?\s*$", re.I)


@dataclass
class ParsedEmail:
    message_id: str
    thread_id: str | None
    sender_name: str
    sender_email: str
    reply_to: str | None
    subject: str
    body: str                      # cleaned top-level message (quoted replies removed)
    signature: str
    html_present: bool
    headers: dict[str, str]
    attachments: list[dict]
    date: datetime | None
    links: list[tuple[str, str]] = field(default_factory=list)  # (visible text, href)
    is_forwarded: bool = False
    forwarded_from: str | None = None
    forwarded_body: str = ""


def html_to_text(html: str) -> tuple[str, list[tuple[str, str]]]:
    soup = BeautifulSoup(html or "", "html.parser")
    for t in soup(["script", "style", "head"]):
        t.decompose()
    links = [(a.get_text(" ", strip=True), a["href"]) for a in soup.find_all("a", href=True)]
    for br in soup.find_all("br"):
        br.replace_with("\n")
    text = soup.get_text("\n")
    text = re.sub(r"[ \t\xa0]+", " ", text)
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    return text.strip(), links


def strip_quoted(text: str) -> str:
    """Drop quoted reply history (but not forwarded content, which is handled separately)."""
    out: list[str] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if _REPLY_HDR_RE.match(s):
            break
        if s.startswith("On ") and i + 1 < len(lines) and lines[i + 1].strip().endswith("wrote:"):
            break
        if re.match(r"^-{2,}\s*Original Message\s*-{2,}", s, re.I):
            break
        if re.match(r"^From:.*", s) and i + 1 < len(lines) and re.match(r"^(Sent|Date):", lines[i + 1].strip()) and out:
            break
        if s.startswith(">"):
            continue
        out.append(line)
    return "\n".join(out).strip()


def find_signature(text: str) -> str:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s == "--" or s == "-- " or _CLOSERS.match(s):
            sig = [l.strip() for l in lines[i + 1:i + 12] if l.strip()]
            if sig:
                return "\n".join(sig)
    # fallback: last 6 non-empty lines when they look signature-like (phones, urls, titles)
    tail = [l.strip() for l in lines if l.strip()][-6:]
    if any(re.search(r"(\+?\d[\d\s\-()]{8,}|www\.|https?://|@)", l) for l in tail):
        return "\n".join(tail)
    return ""


def _split_forward(text: str) -> tuple[str, str, str | None]:
    m = _FWD_RE.search(text)
    if not m:
        return text, "", None
    head, fwd = text[:m.start()], text[m.end():]
    fm = re.search(r"^From:\s*(.+)$", fwd, re.M)
    return head, fwd.strip(), (fm.group(1).strip() if fm else None)


def parse_message(*, message_id: str, thread_id: str | None, from_header: str, subject: str, text: str | None,
                  html: str | None, headers: dict[str, str], attachments: list[dict] | None = None,
                  date: datetime | None = None) -> ParsedEmail:
    links: list[tuple[str, str]] = []
    if text and text.strip():
        body_raw = text
        if html:
            _, links = html_to_text(html)
    elif html:
        body_raw, links = html_to_text(html)
    else:
        body_raw = ""
    body_raw = body_raw.replace("\r\n", "\n")
    head, fwd, fwd_from = _split_forward(body_raw)
    body = strip_quoted(head)
    name, addr = parseaddr(from_header or "")
    rt = parseaddr(headers.get("Reply-To", ""))[1] or None
    sig_source = body if body else fwd
    return ParsedEmail(
        message_id=message_id, thread_id=thread_id, sender_name=name.strip().strip('"'), sender_email=addr.lower(),
        reply_to=rt.lower() if rt else None, subject=(subject or "").strip(), body=body or fwd,
        signature=find_signature(sig_source), html_present=bool(html), headers=headers,
        attachments=attachments or [], date=date, links=links, is_forwarded=bool(fwd),
        forwarded_from=fwd_from, forwarded_body=fwd,
    )


def parse_gmail_api_message(msg: dict) -> ParsedEmail:
    """Convert a Gmail API `format=full` message resource into a ParsedEmail."""
    payload = msg.get("payload", {})
    hdrs = {h["name"]: h["value"] for h in payload.get("headers", []) if h["name"] in KEPT_HEADERS or h["name"] == "Subject" or h["name"] == "Date"}
    # Authentication-Results can appear several times; keep the first one that Gmail's MX added.
    for h in payload.get("headers", []):
        if h["name"] == "Authentication-Results" and "google.com" in h["value"].split(";")[0]:
            hdrs["Authentication-Results"] = h["value"]
            break
    text_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[dict] = []

    def walk(part: dict) -> None:
        mime = part.get("mimeType", "")
        fname = part.get("filename") or ""
        body = part.get("body", {})
        if fname:
            attachments.append({"filename": fname, "mime_type": mime, "size": body.get("size", 0)})
        elif mime in ("text/plain", "text/html") and body.get("data"):
            data = base64.urlsafe_b64decode(body["data"] + "=" * (-len(body["data"]) % 4)).decode("utf-8", "replace")
            (text_parts if mime == "text/plain" else html_parts).append(data)
        for sub in part.get("parts", []) or []:
            walk(sub)

    walk(payload)
    try:
        dt = parsedate_to_datetime(hdrs.get("Date", "")) if hdrs.get("Date") else None
    except (TypeError, ValueError):
        dt = None
    if dt is None and msg.get("internalDate"):
        dt = datetime.fromtimestamp(int(msg["internalDate"]) / 1000, tz=timezone.utc)
    if dt is not None and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return parse_message(
        message_id=msg["id"], thread_id=msg.get("threadId"), from_header=hdrs.get("From", ""),
        subject=hdrs.get("Subject", ""), text="\n".join(text_parts) or None, html="\n".join(html_parts) or None,
        headers=hdrs, attachments=attachments, date=dt,
    )
