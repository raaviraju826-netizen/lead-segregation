from __future__ import annotations

import re

from rapidfuzz import fuzz
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import Company, Contact, DuplicateCandidate, DuplicateLog
from .taxonomy import is_free_mail

_LEGAL = re.compile(r"\b(pvt\.?\s*ltd|private limited|limited|ltd|llp|llc|inc|corp|corporation|gmbh|co)\b\.?", re.I)


def normalize_email(email: str) -> str:
    e = (email or "").lower().strip()
    if "@" not in e:
        return e
    local, dom = e.rsplit("@", 1)
    local = local.split("+", 1)[0]
    if dom in ("gmail.com", "googlemail.com"):
        local, dom = local.replace(".", ""), "gmail.com"
    return f"{local}@{dom}"


def normalize_company(name: str | None) -> str:
    n = _LEGAL.sub(" ", name or "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", n.lower())).strip()


def resolve_company(db: Session, source: str, name: str | None, domain: str, website: str | None
                    ) -> tuple[Company | None, list[tuple[Company, float, str]]]:
    """Return (company, uncertain_duplicates). Same corporate domain => same company (certain).
    Similar names on different/unknown domains are only *flagged*, never merged."""
    if not name:
        return None, []
    thr = get_settings().duplicate_threshold
    corp = bool(domain) and not is_free_mail(domain)
    if corp:
        hit = db.scalar(select(Company).where(Company.source == source, Company.domain == domain))
        if hit:
            db.add(DuplicateLog(
                match_type="domain_match", company_id=hit.id, matched_company_id=hit.id, similarity=100.0,
                details=f"Corporate domain '{domain}' matched existing company '{hit.name}' (#{hit.id})",
            ))
            return hit, []
    norm = normalize_company(name)
    cands: list[tuple[Company, float, str]] = []
    if norm:
        for other in db.scalars(select(Company).where(Company.source == source)):
            if not other.normalized_name:
                continue
            ratio = max(fuzz.token_set_ratio(norm, other.normalized_name), fuzz.token_sort_ratio(norm, other.normalized_name))
            if ratio >= thr:
                if corp and other.domain and other.domain != domain:
                    cands.append((other, ratio, f"Similar name ({ratio:.0f}% token_set_ratio) but different domains ({other.domain} vs {domain})"))
                elif not corp or not other.domain:
                    cands.append((other, ratio, f"Similar name ({ratio:.0f}% token_set_ratio); domain cannot confirm they are the same company"))
    company = Company(source=source, name=name, normalized_name=norm, domain=domain if corp else None, website=website)
    db.add(company)
    db.flush()
    return company, cands


def resolve_contact(db: Session, source: str, email: str, name: str | None, title: str | None, phone: str | None,
                    company: Company | None) -> Contact | None:
    if not email:
        return None
    ne = normalize_email(email)
    c = db.scalar(select(Contact).where(Contact.source == source, Contact.normalized_email == ne))
    if c:
        c.name = c.name or name
        c.job_title = c.job_title or title
        c.phone = c.phone or phone
        c.company_id = c.company_id or (company.id if company else None)
        db.add(DuplicateLog(
            match_type="exact_email", company_id=c.company_id, matched_company_id=company.id if company else c.company_id,
            similarity=100.0, details=f"Exact normalized email '{ne}' matched existing contact #{c.id}",
        ))
        return c
    c = Contact(source=source, email=email, normalized_email=ne, name=name, job_title=title, phone=phone,
                company_id=company.id if company else None)
    db.add(c)
    db.flush()
    return c


def flag_duplicates(db: Session, email_id: int, company: Company, cands: list[tuple[Company, float, str]]) -> None:
    for other, ratio, reason in cands:
        db.add(DuplicateCandidate(email_id=email_id, company_id=company.id, other_company_id=other.id, similarity=ratio, reason=reason))
        db.add(DuplicateLog(
            email_id=email_id, match_type="fuzzy_company", company_id=company.id, matched_company_id=other.id,
            similarity=ratio, details=reason,
        ))


def merge_companies(db: Session, keep_id: int, drop_id: int, actor: str = "reviewer") -> None:
    """Human-approved merge only (never automatic). Records an audit log entry in duplicate_log."""
    from ..models import Email

    keep = db.get(Company, keep_id)
    dropped = db.get(Company, drop_id)
    keep_name = keep.name if keep else f"#{keep_id}"
    drop_name = dropped.name if dropped else f"#{drop_id}"

    for e in db.scalars(select(Email).where(Email.company_id == drop_id)):
        e.company_id = keep_id
    for c in db.scalars(select(Contact).where(Contact.company_id == drop_id)):
        c.company_id = keep_id
    for d in db.scalars(select(DuplicateCandidate).where(DuplicateCandidate.company_id == drop_id)):
        d.company_id = keep_id
    for d in db.scalars(select(DuplicateCandidate).where(DuplicateCandidate.other_company_id == drop_id)):
        d.other_company_id = keep_id
    db.add(DuplicateLog(
        match_type="manual_merge", company_id=keep_id, matched_company_id=keep_id, similarity=100.0,
        details=f"Merged company '{drop_name}' (#{drop_id}) into '{keep_name}' (#{keep_id})", actor=actor,
    ))
    if dropped:
        db.delete(dropped)
