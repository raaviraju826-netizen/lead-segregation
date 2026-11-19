from __future__ import annotations

import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

from rapidfuzz import fuzz

from ..config import get_settings
from .email_parser import ParsedEmail
from .extractor import Extracted
from .taxonomy import domain_of, is_free_mail

log = logging.getLogger(__name__)
LEGAL_SUFFIX = re.compile(r"\b(pvt\.?\s*ltd|private limited|limited|ltd|llp|llc|inc|corp|corporation|gmbh)\b\.?", re.I)

W = {"registration": 25, "website": 20, "domain": 15, "consistency": 15, "contact": 10, "presence": 15}


def registry_verify(company_name: str | None, registration_ids: list[str]) -> bool | None:
    """Extension point for an authorised business-registry API (MCA, Companies House, OpenCorporates, ...).

    Returns True/False when an external registry was actually queried, or None when no registry is configured.
    No registry is configured in this MVP, so registration is NEVER reported as verified.
    """
    return None


def _root(host: str) -> str:
    host = host.lower().removeprefix("www.")
    parts = host.split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "ac", "edu", "org", "gov"):
        return ".".join(parts[-3:])
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def _host(url: str) -> str:
    return urlparse(url if "//" in url else "//" + url).netloc.lower().split(":")[0]


def _norm_name(name: str) -> str:
    n = LEGAL_SUFFIX.sub(" ", name or "")
    return re.sub(r"[^a-z0-9 ]", " ", n.lower()).strip()


def _live_check(url: str, company_name: str | None) -> tuple[bool | None, str]:
    """Optional homepage fetch (ENABLE_WEBSITE_CHECK=true). Returns (passed|None, detail)."""
    import httpx

    host = _host(url)
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return None, "skipped: host resolves to a private address"
        r = httpx.get(url if url.startswith("http") else "https://" + url, timeout=6, follow_redirects=True,
                      headers={"User-Agent": "LeadSenseBot/1.0"})
        if r.status_code >= 400:
            return False, f"website returned HTTP {r.status_code}"
        text = r.text[:60000].lower()
        tok = _norm_name(company_name or "")
        if tok and (tok in text or fuzz.partial_ratio(tok, text[:5000]) >= 90):
            return True, "website reachable and mentions the company name"
        return None, "website reachable but company name not found on homepage"
    except Exception as e:
        return None, f"website check failed ({type(e).__name__})"


def assess_company(parsed: ParsedEmail, ex: Extracted) -> dict:
    s = get_settings()
    signals: list[dict] = []
    conflicts: list[str] = []
    external = registry_verify(ex.company_name, ex.registration_ids)

    def sig(name: str, key: str, points: float, status: str, detail: str):
        signals.append({"name": name, "weight": W[key], "points": round(min(points, W[key]), 1), "status": status, "detail": detail})

    sender_dom = ex.sender_domain
    corp = bool(sender_dom) and not ex.free_mail

    # 1. Registration evidence
    if external is True:
        sig("Registration evidence", "registration", 25, "Verified", "Confirmed against an external registry.")
    elif ex.registration_ids:
        sig("Registration evidence", "registration", 8, "Claimed", f"Registration identifier(s) quoted in the email ({', '.join(ex.registration_ids[:2])}); NOT verified against any registry.")
    elif ex.company_name and LEGAL_SUFFIX.search(ex.company_name):
        sig("Registration evidence", "registration", 4, "Claimed", "Legal-form suffix in company name; no registry check performed.")
    else:
        sig("Registration evidence", "registration", 0, "Unknown", "No registration evidence in the email and no registry configured.")

    # 2. Website consistency
    explicit_site = next((e for e in ex.evidence if e["field"] == "website" and e["source"] != "website or domain"), None)
    live_ok: bool | None = None
    live_detail = ""
    if explicit_site:
        site_host = _host(ex.website or "")
        if corp and _root(site_host) != _root(sender_dom):
            conflicts.append("website domain differs from sender domain")
            sig("Website consistency", "website", 0, "Conflict", f"Signature website {site_host} does not match sender domain {sender_dom}.")
        else:
            base = 12 if corp else 8
            if s.enable_website_check:
                live_ok, live_detail = _live_check(ex.website, ex.company_name)
                base += 8 if live_ok else 0
            sig("Website consistency", "website", base, "Pass" if corp else "Claimed",
                (f"Website {site_host} matches the sender domain. " if corp else f"Website {site_host} stated in signature (free-mail sender; unverified). ")
                + (live_detail or "Live website check not enabled."))
    else:
        sig("Website consistency", "website", 0, "Unknown", "No website stated in the email." + (" (A missing website is not treated as a negative.)"))

    # 3. Domain consistency
    if not sender_dom:
        sig("Domain consistency", "domain", 0, "Unknown", "No sender domain.")
    elif ex.free_mail:
        sig("Domain consistency", "domain", 0, "Unknown", f"Free-mail domain ({sender_dom}); neutral, not treated as suspicious on its own.")
    else:
        label = sender_dom.split(".")[-2] if sender_dom.count(".") < 2 else sender_dom.split(".")[-3]
        name_src = ex.src("company_name")
        if name_src == "website or domain":
            sig("Domain consistency", "domain", 6, "Partial", "Company name was derived from the domain itself, so consistency cannot be independently checked.")
        else:
            ratio = fuzz.partial_ratio(_norm_name(ex.company_name or "").replace(" ", ""), label)
            if ratio >= 70:
                sig("Domain consistency", "domain", 15, "Pass", f"Company name matches domain '{sender_dom}' (similarity {ratio:.0f}).")
            else:
                sig("Domain consistency", "domain", 6, "Partial", f"Corporate domain '{sender_dom}' does not obviously reflect the company name (similarity {ratio:.0f}); could be a brand/parent-company difference.")

    # 4. Business information consistency
    if ex.company_name:
        mentions = 0
        n = _norm_name(ex.company_name)
        for text in (parsed.signature, parsed.body, parsed.subject, parsed.sender_name):
            if text and (n in text.lower() or fuzz.partial_ratio(n, text.lower()) >= 90):
                mentions += 1
        if corp and fuzz.partial_ratio(n.replace(" ", ""), sender_dom.split(".")[0]) >= 70:
            mentions += 1
        pts = 10 if mentions >= 2 else 5
        pts += 5 if ex.business_description else 0
        sig("Business information consistency", "consistency", pts, "Pass" if mentions >= 2 else "Partial",
            f"Company name appears in {mentions} independent place(s)" + ("; business description provided." if ex.business_description else "; no business description."))
    else:
        sig("Business information consistency", "consistency", 0, "Unknown", "No company name could be extracted.")

    # 5. Contact information
    pts, parts = 0, []
    if ex.phone: pts += 4; parts.append("valid phone")
    if ex.contact_name: pts += 2; parts.append("contact name")
    if ex.job_title: pts += 2; parts.append("job title")
    if ex.address_present: pts += 2; parts.append("address")
    sig("Contact information", "contact", pts, "Pass" if pts >= 6 else ("Partial" if pts else "Unknown"), ("Found: " + ", ".join(parts)) if parts else "No phone, title or address provided.")

    # 6. Public business presence
    pts, parts = 0, []
    if ex.social_links: pts += 5; parts.append("LinkedIn/social profile link (not opened)")
    if explicit_site: pts += 3; parts.append("website stated")
    if live_ok: pts += 7; parts.append("website live check passed")
    sig("Public business presence", "presence", pts, "Claimed" if pts else "Unknown",
        ("; ".join(parts) + ". Not independently verified.") if parts else "No public-presence evidence available; no external lookup performed.")

    score = round(sum(x["points"] for x in signals), 1)
    if conflicts:
        label = "Conflicting Evidence"
    elif external is True and score >= 70:
        label = "Verified"
    elif score >= 40:
        label = "Partially Verified"
    else:
        label = "Unverified"
    note = ("Preliminary, evidence-based assessment from email content only. No business registry or external verification service was queried, "
            "so registration is not verified and this is not a legal verification." if external is None else "Includes an external registry check.")
    return {"score": score, "label": label, "signals": signals, "note": note, "conflicts": conflicts}
