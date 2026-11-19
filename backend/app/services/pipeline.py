from __future__ import annotations

import logging
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (CompanyTrustAssessment, Email, EmailTrustAssessment, IndustryClassification,
                      LeadRelevanceAssessment)
from . import classifier as clf
from .company_trust import assess_company
from .duplicates import flag_duplicates, resolve_company, resolve_contact
from .email_parser import ParsedEmail
from .email_trust import assess_email
from .extractor import extract
from .lead_scoring import detect_type, score_lead

log = logging.getLogger(__name__)

STATUS_CLASSIFIED = "Classified"
STATUS_REVIEW = "Needs Review"
STATUS_OTHER = "Other / Unknown"
STATUS_NOT_LEAD = "Not a Lead"
STATUS_SUSPICIOUS = "Suspicious — Review Required"
NOT_LEAD_TYPES = {"Automatic reply", "Newsletter", "Irrelevant message", "Vendor communication"}
SKIP_CLASSIFICATION_TYPES = {"Automatic reply", "Newsletter"}


def decide_status(lead_type: str, risk: str, decision: str, email_flags: list[str], company_conflicts: list[str]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if lead_type == "Spam or suspicious message" or risk == "High" or any(f.startswith("Suspicious wording") for f in email_flags):
        reasons.append("High email-risk score" if risk == "High" else "Spam/suspicious wording")
        reasons += email_flags[:4]
        return STATUS_SUSPICIOUS, reasons
    if lead_type in NOT_LEAD_TYPES:
        return STATUS_NOT_LEAD, [f"Message type: {lead_type}"]
    status = {clf.CLASSIFIED: STATUS_CLASSIFIED, clf.NEEDS_REVIEW: STATUS_REVIEW, clf.OTHER: STATUS_OTHER}[decision]
    if decision == clf.NEEDS_REVIEW:
        reasons.append("Classification confidence below 0.75 or evidence insufficient")
    if decision == clf.OTHER:
        reasons.append("Sender does not match any of the four target industries")
    if status == STATUS_CLASSIFIED and (email_flags or company_conflicts):
        status = STATUS_REVIEW
        reasons += email_flags[:3] + [f"Company evidence conflict: {c}" for c in company_conflicts]
    return status, reasons


def process_email(db: Session, parsed: ParsedEmail, source: str) -> Email:
    existing = db.scalar(select(Email).where(Email.source == source, Email.gmail_message_id == parsed.message_id))
    if existing:
        return existing
    t0 = time.perf_counter()
    ex = extract(parsed)
    et = assess_email(parsed, ex)
    lead_type, type_detail = detect_type(parsed, ex, et["flags"])

    if lead_type in SKIP_CLASSIFICATION_TYPES:
        cls = clf.ClassificationResult(clf.OTHER, None, 0.0, 0.0, 0.0, 0.0,
                                       f"Classification skipped: message is a {lead_type.lower()}.", [], ex.requested_service,
                                       "skipped", False, clf.OTHER, [], ["Not sent to LLM (data minimisation)"])
    else:
        cls = clf.classify(parsed, ex)
    ct = assess_company(parsed, ex)
    lr = score_lead(parsed, ex, cls.industry, cls.confidence, lead_type, type_detail)
    status, reasons = decide_status(lead_type, et["risk"], cls.decision, et["flags"], ct["conflicts"])

    company, cands = resolve_company(db, source, ex.company_name, ex.sender_domain, ex.website)
    contact = resolve_contact(db, source, parsed.sender_email, ex.contact_name or parsed.sender_name or None, ex.job_title, ex.phone, company)

    email = Email(
        source=source, gmail_message_id=parsed.message_id, thread_id=parsed.thread_id, sender_name=parsed.sender_name,
        sender_email=parsed.sender_email, reply_to=parsed.reply_to, subject=parsed.subject, body_text=(parsed.body or "")[:20000],
        body_html_present=parsed.html_present, headers=parsed.headers, attachments=parsed.attachments, email_date=parsed.date,
        company_id=company.id if company else None, contact_id=contact.id if contact else None,
        extracted={**ex.to_dict(), "forwarded": parsed.is_forwarded, "forwarded_from": parsed.forwarded_from,
                   "message_type_detail": type_detail},
        industry=cls.industry, sub_industry=cls.sub_industry, status=status, status_reasons=reasons, lead_type=lead_type,
    )
    db.add(email)
    db.flush()
    db.add(IndustryClassification(
        email_id=email.id, industry=cls.industry, sub_industry=cls.sub_industry, sub_industry_confidence=cls.sub_industry_confidence,
        confidence=cls.confidence, llm_confidence=cls.llm_confidence, retrieval_similarity=cls.retrieval_similarity,
        reason=cls.reason, evidence=cls.evidence, interest_area=cls.interest_area, method=cls.method, llm_used=cls.llm_used,
        retrieved_chunks=cls.chunks))
    db.add(CompanyTrustAssessment(email_id=email.id, company_id=company.id if company else None, score=ct["score"], label=ct["label"],
                                  signals=ct["signals"], note=ct["note"]))
    db.add(EmailTrustAssessment(email_id=email.id, score=et["score"], risk=et["risk"], signals=et["signals"], flags=et["flags"]))
    db.add(LeadRelevanceAssessment(email_id=email.id, score=lr["score"], priority=lr["priority"], lead_type=lead_type,
                                   breakdown=lr["breakdown"]))
    if company and cands:
        flag_duplicates(db, email.id, company, cands)
    email.processing_ms = int((time.perf_counter() - t0) * 1000)
    db.commit()
    return email
