from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urlparse

import phonenumbers

from ..config import get_settings
from .email_parser import ParsedEmail
from .taxonomy import domain_of, is_free_mail, load_taxonomy

ORG_SUFFIX = r"(?:Pvt\.?\s*Ltd\.?|Private Limited|Limited|Ltd\.?|LLP|LLC|Inc\.?|Corp\.?|Corporation|GmbH)"
ORG_WORDS = (r"(?:College|University|School|Institute|Academy|Technologies|Technology|Industries|Logistics|Transport|Motors|"
             r"Textiles|Systems|Solutions|Softwares?|Labs|Enterprises|Exports|Group|Foods|Chemicals|Packaging|Freight|Courier|"
             r"Cargo|Warehousing|Fleet|Infotech|Tech|Mills|Electronics|Machinery|Cloud|Security|Analytics|Carriers|Movers|Learning|Coaching|Classes)")
ORG_RE = re.compile(rf"\b(?:{ORG_SUFFIX}|{ORG_WORDS})\b", re.I)
BODY_ORG_RE = re.compile(
    rf"((?:[A-Z][\w&'.-]*\s+){{0,4}}[A-Z][\w&'.-]*\s+(?:{ORG_WORDS}|{ORG_SUFFIX})(?:\s+(?:{ORG_SUFFIX}))?)")
TITLE_RE = re.compile(
    r"\b(manager|director|ceo|cto|coo|cfo|founder|co-founder|head|professor|principal|dean|registrar|officer|president|"
    r"vp|vice president|coordinator|executive|engineer|lead|administrator|proprietor|owner|partner|consultant|"
    r"associate|supervisor|chairman|procurement|admissions|hod)\b", re.I)
NAME_RE = re.compile(r"^(?:(?:Dr|Mr|Mrs|Ms|Prof)\.?\s+)?[A-Z][a-zA-Z.'-]+(?:\s+[A-Z][a-zA-Z.'-]+){1,3}$")
SOCIAL = ("linkedin.com", "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com", "wa.me", "t.me")
URL_RE = re.compile(r"(?<![@\w.-])((?:https?://)?(?:www\.)?[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:com|in|org|net|edu|io|co|ai|tech|biz|info|app|dev|cloud|ac\.in|edu\.in|co\.in|org\.in|gov\.in)(?:/[^\s,;)]*)?)", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
SELF_RE = re.compile(
    r"\b(we are|we're|our (?:company|college|university|school|institute|factory|plant|firm|organi[sz]ation|team|students|campus|fleet|warehouse|platform|mill|unit|network)|"
    r"is a (?:leading|premier|global|top|reputed|renowned|well-known|growing)|we (?:manufacture|produce|provide|offer|operate|run|deliver|transport|ship|teach|train|build|develop|specialize|specialise|serve|supply)|"
    r"(?:is|are) an? (?:[a-z-]+ ){0,4}[a-z-]+|operates|manufactures|established in|founded in|located in|based in|affiliated to|with (?:over )?\d[\d,]* (?:students|employees|vehicles|trucks|clients))\b", re.I)
REQ_RE = re.compile(
    r"(?:looking for|needs?|needed|requires?|required|interested in|seeks?|seeking|want to (?:build|get|develop|buy|hire|have|set up|implement)|"
    r"would like(?= an? )|wants?(?! to\b)(?= \w)|would like to (?:build|get|develop|buy|hire|have|implement|know about)|quotation for|quote for|proposal for|"
    r"planning to (?:build|develop|get|buy|implement|set up)|help (?:us )?(?:with|build))\s+(?:a|an|the|to|your)?\s*([^.;\n!?]{3,90})", re.I)
INJECTION_RE = re.compile(
    r"(ignore (?:all |any )?(?:the )?(?:previous|prior|above) (?:instructions|prompts?)|disregard (?:the )?(?:system|previous)|"
    r"you are (?:now )?(?:an? )?(?:ai|assistant|chatgpt|dan)\b|system prompt|act as (?:an? )?(?:different|new)|"
    r"classify (?:this|me|us) as|set (?:the )?(?:trust|score|confidence)|mark (?:this|me) as (?:verified|genuine|trusted)|"
    r"respond only with|override (?:the )?(?:rules|instructions))", re.I)


@dataclass
class Extracted:
    company_name: str | None = None
    contact_name: str | None = None
    job_title: str | None = None
    website: str | None = None
    phone: str | None = None
    business_description: str = ""
    requested_service: str | None = None
    sender_domain: str = ""
    free_mail: bool = False
    registration_ids: list[str] = field(default_factory=list)
    social_links: list[str] = field(default_factory=list)
    address_present: bool = False
    injection_detected: bool = False
    evidence: list[dict] = field(default_factory=list)  # {field, value, source, snippet}
    classification_text: dict[str, str] = field(default_factory=dict)  # source -> text used for industry evidence
    industry_signals: dict[str, list[str]] = field(default_factory=dict)

    def src(self, fieldname: str) -> str | None:
        for e in self.evidence:
            if e["field"] == fieldname:
                return e["source"]
        return None

    def to_dict(self) -> dict:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def detect_injection(text: str) -> list[str]:
    return [m.group(0) for m in INJECTION_RE.finditer(text or "")]


def sanitize_for_llm(text: str, limit: int = 1500) -> str:
    """Remove lines that look like instructions aimed at the AI and bound the size."""
    kept = [l for l in (text or "").splitlines() if not INJECTION_RE.search(l)]
    return "\n".join(kept)[:limit]


def _kw_hits(text: str, keywords: list[str]) -> list[str]:
    hits = []
    for kw in keywords:
        pat = r"(?<![a-z0-9])" + re.escape(kw.lower()) + (r"s?" if len(kw) > 3 else "") + r"(?![a-z0-9])"
        if re.search(pat, text.lower()):
            hits.append(kw)
    return hits


def _clean_org(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip(" ,.-|:;•")
    s = re.sub(r"^(?:from|at|of|with|the)\s+", "", s, flags=re.I)
    return s


def _drop_service_words(text: str, service: str | None) -> str:
    """Remove individual words of the requested service from the subject (subjects usually just name the request)."""
    if not service or not text:
        return text
    words = {w for w in re.findall(r"[a-z]+", service.lower()) if len(w) > 2}
    return " ".join(w for w in text.split() if re.sub(r"[^a-z]", "", w.lower()) not in words)


def _domain_label(domain: str) -> str:
    parts = domain.split(".")
    return parts[-3] if len(parts) >= 3 and parts[-2] in ("co", "ac", "edu", "org") else (parts[-2] if len(parts) >= 2 else domain)


def extract(parsed: ParsedEmail) -> Extracted:
    s = get_settings()
    ex = Extracted()
    ex.sender_domain = domain_of(parsed.sender_email)
    ex.free_mail = is_free_mail(ex.sender_domain)
    body = parsed.body or ""
    sig = parsed.signature or ""
    full = f"{parsed.subject}\n{body}\n{parsed.forwarded_body}"
    ex.injection_detected = bool(detect_injection(full))

    def add(fieldname: str, value, source: str, snippet: str = ""):
        ex.evidence.append({"field": fieldname, "value": value, "source": source, "snippet": snippet[:160]})

    sig_lines = [l.strip() for l in sig.splitlines() if l.strip()]
    # signature lines may be pipe-separated
    flat: list[str] = []
    for l in sig_lines:
        flat.extend([p.strip() for p in l.split("|")] if "|" in l else [l])
    sig_lines = flat

    # ---- contact name / title / company from signature
    name_line = org_line = title_line = None
    for l in sig_lines:
        if EMAIL_RE.search(l) or URL_RE.search(l) or re.search(r"\d{5,}", l):
            continue
        has_org = bool(ORG_RE.search(l))
        has_title = bool(TITLE_RE.search(l))
        if not name_line and NAME_RE.match(l) and not has_org and not has_title:
            name_line = l
        elif has_org and not org_line and len(l) < 90 and not has_title:
            org_line = l
        elif has_title and not title_line and len(l) < 90:
            title_line = l
    if name_line and not title_line:
        # "Name, Title"
        for l in sig_lines:
            if l.startswith(name_line + ",") and TITLE_RE.search(l):
                title_line = l[len(name_line) + 1:].strip()
    if name_line:
        ex.contact_name = name_line
        add("contact_name", name_line, "signature", name_line)
    elif parsed.sender_name and NAME_RE.match(parsed.sender_name) and not ORG_RE.search(parsed.sender_name):
        ex.contact_name = parsed.sender_name
        add("contact_name", parsed.sender_name, "sender display name", parsed.sender_name)
    if title_line:
        ex.job_title = _clean_org(title_line)
        add("job_title", ex.job_title, "signature", title_line)

    # ---- company name (signature > body > subject > forwarded > display name > domain)
    if org_line:
        ex.company_name = _clean_org(org_line)
        add("company_name", ex.company_name, "signature", org_line)
    else:
        for src, text in (("email body", body), ("subject", parsed.subject), ("forwarded content", parsed.forwarded_body)):
            m = BODY_ORG_RE.search(text)
            if m:
                ex.company_name = _clean_org(m.group(1))
                add("company_name", ex.company_name, src, m.group(0))
                break
    if not ex.company_name and parsed.sender_name and ORG_RE.search(parsed.sender_name):
        ex.company_name = _clean_org(parsed.sender_name)
        add("company_name", ex.company_name, "sender display name", parsed.sender_name)
    if not ex.company_name and not ex.free_mail and ex.sender_domain:
        label = _domain_label(ex.sender_domain)
        ex.company_name = label.replace("-", " ").title()
        add("company_name", ex.company_name, "website or domain", ex.sender_domain)

    # ---- website
    sig_body = f"{sig}\n{body}"
    stripped = EMAIL_RE.sub(" ", sig_body)
    urls = [m.group(1) for m in URL_RE.finditer(stripped)]
    for u in urls:
        host = urlparse(u if "//" in u else "//" + u).netloc.lower().removeprefix("www.")
        if any(host.endswith(sd) for sd in SOCIAL):
            ex.social_links.append(u)
            continue
        if not ex.website:
            ex.website = u if u.startswith("http") else "https://" + u
            add("website", ex.website, "signature" if u in EMAIL_RE.sub(" ", sig) else "email body", u)
    if not ex.website and not ex.free_mail and ex.sender_domain:
        ex.website = f"https://{ex.sender_domain}"
        add("website", ex.website, "website or domain", ex.sender_domain)

    # ---- phone
    for src, text in (("signature", sig), ("email body", body)):
        try:
            for m in phonenumbers.PhoneNumberMatcher(text, s.default_phone_region):
                if phonenumbers.is_valid_number(m.number):
                    ex.phone = phonenumbers.format_number(m.number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                    add("phone", ex.phone, src, m.raw_string)
                    break
        except Exception:  # pragma: no cover
            pass
        if ex.phone:
            break

    # ---- registration identifiers claimed in the email (NOT verified)
    for pat in (r"\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b", r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
                r"(?:reg(?:istration)?\.?\s*(?:no|number)\.?|CIN|GSTIN|company no\.?)\s*[:#-]?\s*([A-Z0-9\-/]{6,25})"):
        for m in re.finditer(pat, full):
            ex.registration_ids.append(m.group(0).strip())
    if ex.registration_ids:
        add("registration_ids", ex.registration_ids, "signature" if ex.registration_ids[0] in sig else "email body", ex.registration_ids[0])
    ex.address_present = bool(re.search(r"\b(?:road|street|nagar|sector|floor|avenue|campus|industrial (?:area|estate)|\b\d{6}\b)", sig + body, re.I)
                              and re.search(r"\b\d{5,6}\b|road|street|sector", sig + body, re.I))

    # ---- business description (what the SENDER is) vs requested service (what they WANT)
    sentences = [x.strip() for x in re.split(r"(?<=[.!?])\s+|\n+", body) if x.strip()]
    desc = [x for x in sentences if SELF_RE.search(x)]
    ex.business_description = " ".join(desc)[:500]
    if desc:
        add("business_description", ex.business_description, "email body", desc[0])
    tagline = [l for l in sig_lines if l not in (name_line, org_line, title_line) and not EMAIL_RE.search(l)
               and not URL_RE.search(l) and not re.search(r"\d{5,}", l) and len(l) > 12 and not NAME_RE.match(l)]
    for src, text in (("subject", parsed.subject), ("email body", body)):
        m = REQ_RE.search(text)
        if m:
            svc = re.split(r"\s+(?:for|to|with|that|which|as|from|so that|because|in order)\s+|,", m.group(1), maxsplit=1)[0].strip(" .")
            if len(svc) >= 3:
                ex.requested_service = svc[0].upper() + svc[1:]
                add("requested_service", ex.requested_service, src, m.group(0))
                break
    if not ex.requested_service:
        m = re.search(r"(?:request for|enquiry (?:about|for|regarding)|inquiry (?:about|for|regarding)|rfq[:\s]+|quotation[:\s]+)\s*(.{3,60})", parsed.subject, re.I)
        if m:
            ex.requested_service = m.group(1).strip(" .:-")
            add("requested_service", ex.requested_service, "subject", parsed.subject)

    # ---- text used as industry evidence (requested service excluded only when a separate business description exists)
    _PROTECTED_IND_WORDS = {
        "education", "educational", "institution", "college", "university", "school", "campus", "students", "admissions", "coaching", "edtech",
        "manufacturing", "factory", "plant", "textile", "garment", "automotive", "machinery", "cnc", "industrial", "chemical",
        "logistics", "freight", "warehouse", "warehousing", "courier", "parcel", "fleet", "cargo", "shipping", "transportation",
        "saas", "devops", "cybersecurity", "cloud", "analytics",
    }

    def strip_service(t: str) -> str:
        # Strip the requested service words EXCEPT words that identify the sender's industry
        if not ex.requested_service or not t:
            return t
        svc_words = [w for w in re.findall(r"[a-zA-Z]+", ex.requested_service) if w.lower() not in _PROTECTED_IND_WORDS and len(w) > 2]
        out = t
        for w in svc_words:
            out = re.sub(rf"\b{re.escape(w)}\b", " ", out, flags=re.I)
        return out

    if ex.business_description:
        body_evidence = strip_service(ex.business_description)
        subj_evidence = strip_service(re.sub(REQ_RE, " ", parsed.subject))
    else:
        # Casual/short email without "We are a...": keep body/subject unless another non-target industry (hospital/restaurant) is stated
        body_evidence = body if not re.search(r"\b(hospital|clinic|patient|restaurant|cafe|hotel)\b", body, re.I) else ""
        subj_evidence = parsed.subject if not re.search(r"\b(hospital|clinic|patient|restaurant|cafe|hotel)\b", body + " " + parsed.subject, re.I) else ""

    ex.classification_text = {
        "email body": body_evidence,
        "signature": " ".join(([org_line] if org_line else []) + tagline),
        "company name": ex.company_name or "",
        "domain": _domain_label(ex.sender_domain).replace("-", " ") if not ex.free_mail else "",
        "subject": subj_evidence,
    }
    all_text = " ".join(ex.classification_text.values())
    for ind in load_taxonomy()["industries"]:
        hits = _kw_hits(all_text, ind["keywords"])
        for sub in ind["sub_industries"].values():
            hits += [h for h in _kw_hits(all_text, sub["keywords"]) if h not in hits]
        if hits:
            ex.industry_signals[ind["name"]] = hits
    return ex
