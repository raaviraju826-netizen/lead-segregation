from __future__ import annotations

import re
from urllib.parse import urlparse

from rapidfuzz import fuzz

from .email_parser import ParsedEmail
from .extractor import Extracted, detect_injection, URL_RE, EMAIL_RE
from .taxonomy import domain_of, is_free_mail

SHORTENERS = {"bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "cutt.ly", "rb.gy", "shorturl.at", "tiny.cc"}
BAD_TLDS = (".zip", ".mov", ".top", ".click", ".loan", ".work", ".gq", ".tk")
DANGEROUS_EXT = {"exe", "scr", "bat", "cmd", "js", "vbs", "jar", "msi", "iso", "img", "lnk", "docm", "xlsm", "pptm", "hta", "ps1", "com"}
ARCHIVE_EXT = {"zip", "rar", "7z", "gz"}
BRANDS = ["paypal", "microsoft", "google", "amazon", "apple", "netflix", "hdfc", "icici", "sbi", "axis bank", "dhl", "fedex", "linkedin"]
WORDING = [
    (r"wire transfer|western union|gift cards?|bitcoin|crypto(?:currency)? (?:payment|wallet)", "asks for unusual payment method", 15),
    (r"verify your (?:account|password|identity)|confirm your (?:password|credentials)|account (?:suspended|locked|will be closed)|login (?:here|now) to", "credential-phishing wording", 20),
    (r"you(?:'ve| have) won|\bwin (?:an? )?iphone\b|\bwon (?:an? )?iphone\b|\bfree iphone\b|lottery|inheritance|claim your (?:prize|reward)|beneficiary|jackpot", "prize / giveaway / advance-fee wording", 30),
    (r"urgent(?:ly)? (?:action|response|payment)|act (?:now|immediately)|within 24 hours|immediate payment", "artificial urgency", 8),
    (r"(?:send|share) (?:me )?(?:your )?(?:bank details|otp|pin|password|card number)", "requests sensitive information", 25),
    (r"guaranteed (?:income|returns|profit)|100% (?:guaranteed|risk[- ]free)|make money fast|earn \$?\d+ (?:per|a) day", "get-rich wording", 20),
]
AUTH_RE = {k: re.compile(rf"\b{k}=(\w+)", re.I) for k in ("spf", "dkim", "dmarc")}


def _trusted_auth(parsed: ParsedEmail) -> dict[str, str | None]:
    """Only read results from a trusted authserv (Gmail's own MX). Never infer or invent results."""
    res: dict[str, str | None] = {"spf": None, "dkim": None, "dmarc": None}
    ar = parsed.headers.get("Authentication-Results", "")
    if ar and "google.com" in ar.split(";")[0].lower():
        for k, rx in AUTH_RE.items():
            m = rx.search(ar)
            if m:
                res[k] = m.group(1).lower()
    return res


def _host(u: str) -> str:
    return urlparse(u if "//" in u else "//" + u).netloc.lower().split(":")[0].removeprefix("www.")


def assess_email(parsed: ParsedEmail, ex: Extracted) -> dict:
    signals: list[dict] = []
    flags: list[str] = []
    penalty = 0.0

    def add(name: str, status: str, detail: str, pen: float = 0.0, flag: bool = False):
        nonlocal penalty
        penalty += pen
        signals.append({"name": name, "status": status, "detail": detail, "penalty": pen})
        if flag:
            flags.append(f"{name}: {detail}")

    sender_dom = ex.sender_domain
    auth = _trusted_auth(parsed)
    any_auth = any(v for v in auth.values())
    for k, v in auth.items():
        if v is None:
            add(k.upper(), "Unknown", "No authentication result available from a trusted source.")
        elif v == "pass":
            add(k.upper(), "Pass", f"{k.upper()} = pass (reported by Gmail's receiving server).")
        elif v in ("fail", "permerror"):
            add(k.upper(), "Fail", f"{k.upper()} = {v} (reported by Gmail's receiving server).", 25 if k != "dkim" else 20, True)
        else:
            add(k.upper(), "Weak", f"{k.upper()} = {v}.", 10 if v == "softfail" else 3, v == "softfail")

    # Reply-To
    if parsed.reply_to:
        rd = domain_of(parsed.reply_to)
        if rd != sender_dom:
            extra = 5 if (is_free_mail(rd) and not is_free_mail(sender_dom)) else 0
            add("Reply-To mismatch", "Warning", f"Replies go to {rd}, not {sender_dom}.", 15 + extra, True)
        else:
            add("Reply-To", "Pass", "Reply-To matches sender domain.")
    else:
        add("Reply-To", "Pass", "No separate Reply-To address.")

    # Impersonation
    disp = (parsed.sender_name or "").lower()
    label = sender_dom.split(".")[-2] if sender_dom.count(".") else sender_dom
    imp = None
    embedded = EMAIL_RE.search(disp)
    if embedded and domain_of(embedded.group(0)) != sender_dom:
        imp = "display name contains a different email address"
    for b in BRANDS:
        bl = b.replace(" ", "")
        if b in disp and bl not in sender_dom.replace("-", ""):
            imp = f"display name uses '{b}' but sender domain is {sender_dom}"
        elif label != bl and sender_dom and not is_free_mail(sender_dom) and fuzz.ratio(label, bl) >= 85:
            imp = f"domain '{sender_dom}' resembles '{b}' (possible look-alike)"
    if imp:
        add("Possible impersonation", "Warning", imp.capitalize() + ".", 20, True)
    else:
        add("Possible impersonation", "Pass", "No brand or address impersonation pattern detected.")

    # Links
    links = list(parsed.links)
    links += [(u, u) for u in (m.group(1) for m in URL_RE.finditer(EMAIL_RE.sub(" ", parsed.body)))]
    bad: list[str] = []
    for text, href in links:
        h = _host(href)
        if not h or h.startswith("mailto"):
            continue
        if h in SHORTENERS:
            bad.append(f"URL shortener ({h})")
        elif re.fullmatch(r"\d{1,3}(\.\d{1,3}){3}", h):
            bad.append(f"IP-address link ({h})")
        elif "xn--" in h:
            bad.append(f"punycode domain ({h})")
        elif h.endswith(BAD_TLDS):
            bad.append(f"high-risk TLD ({h})")
        elif "@" in urlparse(href).netloc:
            bad.append("credentials-in-URL trick")
        elif text and URL_RE.fullmatch(text.strip()) and _host(text) != h:
            bad.append(f"link text shows {_host(text)} but goes to {h}")
    if bad:
        add("Suspicious links", "Warning", "; ".join(sorted(set(bad))[:3]), min(10 * len(set(bad)), 25), True)
    else:
        add("Suspicious links", "Pass", f"{len(links)} link(s) checked; none matched suspicious patterns (links were not visited).")

    # Attachments
    risky = []
    for a in parsed.attachments:
        parts = a["filename"].lower().split(".")
        ext = parts[-1] if len(parts) > 1 else ""
        if ext in DANGEROUS_EXT or (len(parts) > 2 and parts[-2] in ("pdf", "doc", "docx", "xls", "xlsx", "jpg", "png") and ext in DANGEROUS_EXT | ARCHIVE_EXT):
            risky.append(a["filename"])
        elif ext in ARCHIVE_EXT:
            add("Archive attachment", "Info", f"{a['filename']} is an archive (contents not inspected).", 5)
    if risky:
        add("Suspicious attachments", "Warning", "Potentially dangerous attachment type: " + ", ".join(risky[:3]), 30, True)
    elif parsed.attachments:
        add("Attachments", "Pass", f"{len(parsed.attachments)} attachment(s); no dangerous file types.")

    # Wording
    text = f"{parsed.subject}\n{parsed.body}"
    wording_pen, hits = 0, []
    for pat, desc, pen in WORDING:
        if re.search(pat, text, re.I):
            hits.append(desc)
            wording_pen += pen
    if hits:
        add("Suspicious wording", "Warning", "; ".join(hits), min(wording_pen, 35), True)
    else:
        add("Suspicious wording", "Pass", "No scam/phishing wording patterns found.")
    if detect_injection(text):
        add("Prompt-injection attempt", "Warning", "Email contains text trying to instruct an AI system; it was ignored and stripped from LLM input.", 15, True)

    # Signature consistency
    if ex.company_name and ex.src("company_name") == "signature" and sender_dom and not ex.free_mail:
        n = re.sub(r"[^a-z0-9]", "", ex.company_name.lower())
        lab = sender_dom.split(".")[-2] if sender_dom.count(".") < 2 else sender_dom.split(".")[-3]
        r = fuzz.partial_ratio(n, lab)
        if r < 35:
            add("Signature consistency", "Notice", f"Signature company '{ex.company_name}' is not reflected in sender domain '{sender_dom}'.", 5, True)
        else:
            add("Signature consistency", "Pass", "Signature company matches sender domain.")

    score = max(0.0, round(100 - penalty, 1))
    if not parsed.sender_email:
        risk = "Unknown"
    elif not any_auth and not flags:
        risk = "Unknown"  # nothing to anchor trust on, and nothing suspicious found
    elif score >= 75:
        risk = "Low"
    elif score >= 50:
        risk = "Medium"
    else:
        risk = "High"
    return {"score": score, "risk": risk, "signals": signals, "flags": flags, "auth": auth,
            "note": "Authentication results come only from Gmail's receiving server headers; nothing is assumed when absent."}
