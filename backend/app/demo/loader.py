from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models import (Company, CompanyTrustAssessment, Contact, DuplicateCandidate, DuplicateLog, Email,
                      EmailTrustAssessment, IndustryClassification, LeadRelevanceAssessment, ReviewHistory)
from ..services.email_parser import parse_message
from ..services.pipeline import process_email
from .dataset import DATASET


def parsed_from_case(case: dict):
    return parse_message(
        message_id=f"demo-{case['id']}", thread_id=f"demo-thread-{case['id']}", from_header=case["from"], subject=case["subject"],
        text=None if case.get("html") and False else case["body"], html=case.get("html"), headers=dict(case["headers"]),
        attachments=list(case["attachments"]), date=datetime.fromisoformat(case["date"]),
    )


def load_demo(db: Session) -> list[Email]:
    """Run the REAL pipeline over the synthetic emails. Rows are tagged source='demo' and kept separate from Gmail data."""
    return [process_email(db, parsed_from_case(c), "demo") for c in DATASET]


def clear_demo(db: Session) -> int:
    ids = list(db.scalars(select(Email.id).where(Email.source == "demo")))
    comp_ids = list(db.scalars(select(Company.id).where(Company.source == "demo")))
    if ids:
        for model in (DuplicateLog, DuplicateCandidate, ReviewHistory, LeadRelevanceAssessment, EmailTrustAssessment, CompanyTrustAssessment, IndustryClassification):
            db.execute(delete(model).where(model.email_id.in_(ids)))
        db.execute(delete(Email).where(Email.id.in_(ids)))
    if comp_ids:
        db.execute(delete(DuplicateLog).where(DuplicateLog.company_id.in_(comp_ids)))
        db.execute(delete(DuplicateLog).where(DuplicateLog.matched_company_id.in_(comp_ids)))
    db.execute(delete(Contact).where(Contact.source == "demo"))
    db.execute(delete(Company).where(Company.source == "demo"))
    db.commit()
    try:
        from ..services.knowledge_base import remove_reviewed_example
        for i in ids:
            remove_reviewed_example(i)
    except Exception:  # pragma: no cover
        pass
    return len(ids)
