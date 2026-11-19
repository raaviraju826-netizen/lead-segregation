from __future__ import annotations

import re

from rapidfuzz import fuzz

from .email_parser import ParsedEmail
from .extractor import Extracted
from .taxonomy import industry_names, load_business_profile

LEAD_TYPES_REAL = {"Genuine business enquiry", "Potential partnership", "Sales opportunity"}

_VENDOR = re.compile(r"\b(we offer|we provide|our services|we can help you|we would like to introduce|our team can|boost your|special offer|limited[- ]time offer|"
                     r"we specialize in helping|grow your business|increase your (?:traffic|sales)|free (?:audit|consultation) for)\b", re.I)
_PARTNER = re.compile(r"\b(partnership|collaborat\w+|joint venture|reseller|channel partner|strategic alliance|tie-?up|mou)\b", re.I)
_SALES = re.compile(r"\b(purchase order|rfq|request for quotation|quotation|quote|proposal|budget|place an order|procure\w*|tender|bulk order|price list|pricing)\b", re.I)
_ENQ = re.compile(r"\b(enquir\w+|inquir\w+|proposal|quote|quotation|pricing|cost|demo|interested in|would like to know|looking for|we need|need a|need\b|require|requirement|seeking|website|web design|website design|web app|mobile app|dashboard|portal|erp|crm|lms)\b", re.I)
_NEWS = re.compile(r"\b(newsletter|view (?:this email )?in (?:your )?browser|manage (?:your )?(?:email )?preferences|weekly digest|monthly digest)\b", re.I)
_AUTO_SUBJ = re.compile(r"^\s*(automatic reply|auto[- ]?reply|autoreply|out of office|ooo\b|vacation reply)", re.I)
_SYS_SUBJ = re.compile(r"\b(2-step verification|security alert|new sign-in|verify your google|google account|password changed|app password)\b", re.I)
_BOUNCE_SUBJ = re.compile(r"(delivery status notification|undeliverable|mail delivery (?:failed|subsystem)|returned mail|delivery has failed)", re.I)
_INTENT = re.compile(r"\b(quote|quotation|proposal|budget|schedule (?:a )?(?:call|meeting|demo)|call me|purchase|place an order|timeline|asap|please send|get back to us|at the earliest|kindly share|please provide)\b", re.I)
_SPECIFIC = re.compile(r"\b(\d+\s*(?:users|students|vehicles|units|pages|modules|locations|branches|employees)|within \d+|\d+\s*(?:weeks|months|days)|deadline|by (?:january|february|march|april|may|june|july|august|september|october|november|december|q[1-4])|budget|(?:rs\.?|inr|usd|\$|₹)\s?\d)", re.I)


def detect_type(parsed: ParsedEmail, ex: Extracted, email_flags: list[str]) -> tuple[str, str]:
    h = parsed.headers
    addr = (parsed.sender_email or "").lower()
    local = addr.split("@")[0]
    domain = addr.split("@")[1] if "@" in addr else ""
    text = f"{parsed.subject}\n{parsed.body}"
    if local in ("mailer-daemon", "postmaster") or _BOUNCE_SUBJ.search(parsed.subject) or h.get("X-Failed-Recipients"):
        return "Automatic reply", "Bounce / delivery-failure notification"
    if (local in ("no-reply", "noreply", "donotreply", "google-noreply", "account-security-noreply")
            or domain in ("accounts.google.com", "google.com") and _SYS_SUBJ.search(parsed.subject)):
        return "Automatic reply", "Automated system / security notification"
    if _AUTO_SUBJ.search(parsed.subject) or (h.get("Auto-Submitted", "no").lower() not in ("no", "")) or h.get("X-Auto-Response-Suppress"):
        return "Automatic reply", "Auto-responder / out-of-office"
    if h.get("List-Unsubscribe") or h.get("Precedence", "").lower() in ("bulk", "list", "junk") or _NEWS.search(text):
        return "Newsletter", "Bulk mailing indicators (List-Unsubscribe / newsletter wording)"
    wording_hits = [f for f in email_flags if f.startswith("Suspicious wording")]
    if wording_hits:
        return "Spam or suspicious message", wording_hits[0]
    if _VENDOR.search(text) and not re.search(r"(?:we|our \w+) (?:need|require|are looking for|would like to (?:buy|hire|build))", text, re.I):
        return "Vendor communication", "Sender is promoting its own services to us"
    if _PARTNER.search(text):
        return "Potential partnership", "Partnership / collaboration wording"
    if ex.requested_service and _SALES.search(text):
        return "Sales opportunity", "Explicit purchase / quotation intent"
    if ex.requested_service or _ENQ.search(text):
        return "Genuine business enquiry", "Sender asks for a product or service"
    return "Irrelevant message", "No business requirement detected"


def score_lead(parsed: ParsedEmail, ex: Extracted, industry: str, class_conf: float, lead_type: str, type_detail: str) -> dict:
    profile = load_business_profile()
    text = f"{parsed.subject}\n{parsed.body}"
    br: list[dict] = []

    def add(name: str, weight: int, pts: float, detail: str):
        br.append({"name": name, "weight": weight, "points": round(min(pts, weight), 1), "detail": detail})

    # Service / product fit (35)
    if ex.requested_service:
        best, best_r = None, 0
        for svc in profile["services"]:
            r = fuzz.token_set_ratio(ex.requested_service.lower(), svc.lower())
            if r > best_r:
                best, best_r = svc, r
        add("Service or product fit", 35, 35 * max(0.0, min(1.0, (best_r - 40) / 50)),
            f"Requested '{ex.requested_service}' vs our service '{best}' (similarity {best_r:.0f}).")
    else:
        add("Service or product fit", 35, 0, "No specific requested service identified.")
    # Clear requirement (25)
    pts, why = 0, []
    if ex.requested_service:
        pts += 10; why.append("service stated")
        if len(ex.requested_service.split()) >= 3: pts += 5; why.append("descriptive requirement")
    n_spec = len(set(m.group(0).lower() for m in _SPECIFIC.finditer(text)))
    if n_spec: pts += min(10, 5 * n_spec); why.append(f"{n_spec} specific detail(s) (quantity/timeline/budget)")
    add("Clear business requirement", 25, pts, ", ".join(why) or "No clear requirement.")
    # Industry relevance (20)
    if industry in industry_names():
        add("Industry relevance", 20, 20 * min(1.0, class_conf / 0.75), f"Sender is in a target industry ({industry}); scaled by classification confidence {class_conf:.2f}.")
    else:
        add("Industry relevance", 20, 0, "Sender is not in one of the four target industries (or industry unclear).")
    # Contact completeness (10)
    pts = (3 if ex.contact_name else 0) + (3 if ex.phone else 0) + (2 if ex.job_title else 0) + (2 if ex.company_name else 0)
    add("Contact completeness", 10, pts, f"{pts}/10 of name, phone, title, company present.")
    # Business intent (10)
    hits = {m.group(0).lower() for m in _INTENT.finditer(text)}
    add("Business intent", 10, 5 * len(hits), ("Intent cues: " + ", ".join(sorted(hits))) if hits else "No explicit buying/intent cues.")

    score = sum(b["points"] for b in br)
    if lead_type not in LEAD_TYPES_REAL:
        score = round(score * 0.25, 1)
        type_detail += " — not a lead, relevance heavily discounted"
    score = round(score, 1)
    priority = "High" if score >= 80 else "Medium" if score >= 60 else "Low"
    return {"score": score, "priority": priority, "lead_type": lead_type, "type_detail": type_detail, "breakdown": br}
