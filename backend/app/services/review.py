from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Email, ReviewHistory
from ..schemas import ReviewIn
from . import knowledge_base as kb
from .duplicates import normalize_company
from .pipeline import STATUS_CLASSIFIED, STATUS_NOT_LEAD, STATUS_OTHER
from .taxonomy import canonical_industry_name, industry_names, sub_industries


class ReviewError(ValueError):
    pass


def _snap(e: Email) -> dict:
    return {"industry": e.industry, "sub_industry": e.sub_industry, "status": e.status, "lead_type": e.lead_type,
            "company": e.company.name if e.company else None}


def apply_review(db: Session, e: Email, p: ReviewIn) -> Email:
    prev = _snap(e)
    actions: list[str] = []
    if p.industry is not None:
        canon = canonical_industry_name(p.industry) or p.industry
        if canon not in industry_names() + ["Other / Unknown"]:
            raise ReviewError(f"Unknown industry '{p.industry}'")
        p.industry = canon
        subs = sub_industries(p.industry) + ["General"]
        if p.sub_industry is not None and p.sub_industry not in subs:
            raise ReviewError(f"Sub-industry '{p.sub_industry}' does not belong to {p.industry}")
        e.industry = p.industry
        e.sub_industry = (p.sub_industry or "General") if p.industry in industry_names() else None
        actions.append("industry_confirmed" if prev["industry"] == p.industry else "industry_corrected")
    elif p.sub_industry is not None:
        if p.sub_industry not in sub_industries(e.industry) + ["General"]:
            raise ReviewError(f"Sub-industry '{p.sub_industry}' does not belong to {e.industry}")
        e.sub_industry = p.sub_industry
        actions.append("sub_industry_corrected")

    if p.is_genuine is False:
        e.status, e.lead_type = STATUS_NOT_LEAD, "Irrelevant message"
        actions.append("marked_irrelevant")
        kb.remove_reviewed_example(e.id)
    elif p.is_genuine is True or p.industry is not None:
        e.status = STATUS_CLASSIFIED if e.industry in industry_names() else STATUS_OTHER
        if p.is_genuine is True:
            actions.append("marked_genuine")
            if e.lead_type not in ("Genuine business enquiry", "Potential partnership", "Sales opportunity"):
                e.lead_type = "Genuine business enquiry"
        e.status_reasons = ["Confirmed by human reviewer"]

    if p.company_decision or p.company_name:
        ex = dict(e.extracted or {})
        if p.company_name and e.company:
            e.company.name = p.company_name.strip()
            e.company.normalized_name = normalize_company(p.company_name)
            ex["company_name"] = e.company.name
        ex["company_review"] = p.company_decision or "corrected"
        e.extracted = ex
        actions.append(f"company_{p.company_decision or 'corrected'}")

    if not actions and not p.notes:
        raise ReviewError("Nothing to update")
    e.reviewed = True
    # Reviewer-confirmed industries feed the RAG example store (never unreviewed AI output).
    if e.industry in industry_names() and p.is_genuine is not False and (p.industry is not None):
        ct = (e.extracted or {}).get("classification_text") or {}
        text = " . ".join(ct.get(k, "") for k in ("company name", "email body", "signature", "subject") if ct.get(k)) or e.subject
        kb.add_reviewed_example(e.id, text, e.industry, e.sub_industry)
    db.add(ReviewHistory(email_id=e.id, reviewer=p.reviewer or "reviewer", action=",".join(actions) or "note", previous=prev,
                         new=_snap(e), notes=p.notes))
    db.commit()
    return e
