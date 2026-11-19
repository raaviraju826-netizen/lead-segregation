from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Company(Base, TimestampMixin):
    __tablename__ = "companies"
    __table_args__ = (
        Index("ix_companies_source_domain", "source", "domain"),
        Index("ix_companies_norm_name", "normalized_name"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(16), default="gmail")  # gmail | demo
    name: Mapped[str] = mapped_column(String(255))
    normalized_name: Mapped[str] = mapped_column(String(255), default="")
    domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(512), nullable=True)
    contacts = relationship("Contact", back_populates="company")


class Contact(Base, TimestampMixin):
    __tablename__ = "contacts"
    __table_args__ = (UniqueConstraint("source", "normalized_email", name="uq_contact_source_email"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(16), default="gmail")
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str] = mapped_column(String(320))
    normalized_email: Mapped[str] = mapped_column(String(320), index=True)
    job_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    company = relationship("Company", back_populates="contacts")


class Email(Base, TimestampMixin):
    __tablename__ = "emails"
    __table_args__ = (
        UniqueConstraint("source", "gmail_message_id", name="uq_email_source_msgid"),
        Index("ix_emails_status", "status"),
        Index("ix_emails_industry", "industry"),
        Index("ix_emails_date", "email_date"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(16), default="gmail")
    gmail_message_id: Mapped[str] = mapped_column(String(128))
    thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_email: Mapped[str] = mapped_column(String(320), default="")
    reply_to: Mapped[str | None] = mapped_column(String(320), nullable=True)
    subject: Mapped[str] = mapped_column(Text, default="")
    body_text: Mapped[str] = mapped_column(Text, default="")
    body_html_present: Mapped[bool] = mapped_column(Boolean, default=False)
    headers: Mapped[dict] = mapped_column(JSON, default=dict)  # security-relevant headers only
    attachments: Mapped[list] = mapped_column(JSON, default=list)
    email_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True, index=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id"), nullable=True, index=True)
    # Extracted fields with evidence sources
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)
    # Denormalised fast-filter fields (kept in sync by pipeline / review)
    industry: Mapped[str] = mapped_column(String(64), default="Other / Unknown")
    sub_industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="Needs Review")
    status_reasons: Mapped[list] = mapped_column(JSON, default=list)
    lead_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    processing_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    company = relationship("Company")
    contact = relationship("Contact")
    classification = relationship("IndustryClassification", uselist=False, back_populates="email", cascade="all, delete-orphan")
    company_trust = relationship("CompanyTrustAssessment", uselist=False, cascade="all, delete-orphan")
    email_trust = relationship("EmailTrustAssessment", uselist=False, cascade="all, delete-orphan")
    lead_relevance = relationship("LeadRelevanceAssessment", uselist=False, cascade="all, delete-orphan")
    reviews = relationship("ReviewHistory", cascade="all, delete-orphan", order_by="ReviewHistory.created_at")


class IndustryTaxonomy(Base, TimestampMixin):
    __tablename__ = "industry_taxonomy"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(Text, default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    sub_industries: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class IndustryClassification(Base, TimestampMixin):
    __tablename__ = "industry_classifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), unique=True)
    industry: Mapped[str] = mapped_column(String(64))
    sub_industry: Mapped[str | None] = mapped_column(String(128), nullable=True)
    sub_industry_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)  # final
    llm_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    retrieval_similarity: Mapped[float] = mapped_column(Float, default=0.0)
    reason: Mapped[str] = mapped_column(Text, default="")
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    interest_area: Mapped[str | None] = mapped_column(String(255), nullable=True)
    method: Mapped[str] = mapped_column(String(64), default="heuristic")  # llm_rag | heuristic_rag | heuristic_after_llm_failure
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False)
    retrieved_chunks: Mapped[list] = mapped_column(JSON, default=list)
    email = relationship("Email", back_populates="classification")


class CompanyTrustAssessment(Base, TimestampMixin):
    __tablename__ = "company_trust_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), unique=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    label: Mapped[str] = mapped_column(String(32), default="Unverified")
    signals: Mapped[list] = mapped_column(JSON, default=list)
    note: Mapped[str] = mapped_column(Text, default="")


class EmailTrustAssessment(Base, TimestampMixin):
    __tablename__ = "email_trust_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), unique=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    risk: Mapped[str] = mapped_column(String(16), default="Unknown")
    signals: Mapped[list] = mapped_column(JSON, default=list)
    flags: Mapped[list] = mapped_column(JSON, default=list)


class LeadRelevanceAssessment(Base, TimestampMixin):
    __tablename__ = "lead_relevance_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), unique=True)
    score: Mapped[float] = mapped_column(Float, default=0)
    priority: Mapped[str] = mapped_column(String(16), default="Low")
    lead_type: Mapped[str] = mapped_column(String(64), default="Irrelevant message")
    breakdown: Mapped[list] = mapped_column(JSON, default=list)


class ReviewHistory(Base):
    __tablename__ = "review_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), index=True)
    reviewer: Mapped[str] = mapped_column(String(255), default="reviewer")
    action: Mapped[str] = mapped_column(String(64))
    previous: Mapped[dict] = mapped_column(JSON, default=dict)
    new: Mapped[dict] = mapped_column(JSON, default=dict)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DuplicateCandidate(Base, TimestampMixin):
    __tablename__ = "duplicate_candidates"
    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), index=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    other_company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    similarity: Mapped[float] = mapped_column(Float)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | merged | dismissed


class SyncHistory(Base):
    __tablename__ = "sync_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(16), default="gmail")
    trigger: Mapped[str] = mapped_column(String(16), default="manual")
    mode: Mapped[str] = mapped_column(String(16), default="full")  # full | incremental
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running | success | failed
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    processed: Mapped[int] = mapped_column(Integer, default=0)
    needs_review: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AppState(Base):
    __tablename__ = "app_state"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class SubIndustryRecord(Base, TimestampMixin):
    __tablename__ = "sub_industries"
    __table_args__ = (UniqueConstraint("industry_id", "name", name="uq_sub_industry_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    industry_id: Mapped[int] = mapped_column(ForeignKey("industry_taxonomy.id", ondelete="CASCADE"), index=True)
    industry_name: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(128))
    keywords: Mapped[list] = mapped_column(JSON, default=list)


class UploadBatch(Base, TimestampMixin):
    __tablename__ = "upload_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16))  # csv | eml | msg | mbox | json
    source: Mapped[str] = mapped_column(String(16), default="upload")
    status: Mapped[str] = mapped_column(String(16), default="completed")  # running | completed | failed
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    processed_records: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_records: Mapped[int] = mapped_column(Integer, default=0)
    needs_review_records: Mapped[int] = mapped_column(Integer, default=0)
    failed_records: Mapped[int] = mapped_column(Integer, default=0)
    column_mapping: Mapped[dict] = mapped_column(JSON, default=dict)
    email_ids: Mapped[list] = mapped_column(JSON, default=list)
    errors: Mapped[list] = mapped_column(JSON, default=list)


class DuplicateLog(Base, TimestampMixin):
    __tablename__ = "duplicate_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    email_id: Mapped[int | None] = mapped_column(ForeignKey("emails.id", ondelete="CASCADE"), nullable=True, index=True)
    match_type: Mapped[str] = mapped_column(String(32))  # exact_email | domain_match | fuzzy_company | manual_merge | dismissed
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    matched_company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    similarity: Mapped[float] = mapped_column(Float, default=100.0)
    details: Mapped[str] = mapped_column(Text, default="")
    actor: Mapped[str] = mapped_column(String(64), default="system")

