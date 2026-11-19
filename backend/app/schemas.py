from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ReviewIn(BaseModel):
    reviewer: str = Field("reviewer", min_length=1, max_length=120)
    industry: str | None = Field(None, max_length=64)
    sub_industry: str | None = Field(None, max_length=128)
    is_genuine: bool | None = None
    company_name: str | None = Field(None, min_length=1, max_length=255)
    company_decision: Literal["confirm", "reject"] | None = None
    notes: str | None = Field(None, max_length=2000)

    @field_validator("industry", "sub_industry", "company_name", "notes", mode="before")
    @classmethod
    def _blank_to_none(cls, v):
        return None if isinstance(v, str) and not v.strip() else v


class IndustryPatchIn(BaseModel):
    industry: str = Field(..., min_length=1, max_length=64)
    sub_industry: str | None = Field(None, max_length=128)
    is_genuine: bool | None = True
    reviewer: str = Field("reviewer", min_length=1, max_length=120)
    notes: str | None = Field(None, max_length=2000)


class EmailIngestItem(BaseModel):
    message_id: str | None = None
    sender_name: str | None = ""
    sender_email: str = Field(..., min_length=3, max_length=320)
    reply_to: str | None = None
    subject: str = ""
    body: str = ""
    html: str | None = None
    received_at: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class EmailIngestRequest(BaseModel):
    source: str = "upload"
    emails: list[EmailIngestItem] | None = None
    # Also allow single-email fields directly at top-level
    sender_name: str | None = None
    sender_email: str | None = None
    subject: str | None = None
    body: str | None = None
    received_at: str | None = None


class IndustryConfigUpdateIn(BaseModel):
    description: str | None = None
    keywords: list[str] | None = None
    sub_industries: dict[str, list[str]] | None = None


class DuplicateResolveIn(BaseModel):
    action: Literal["merge", "dismiss"]


class LeadSummary(BaseModel):
    id: int
    source: str
    company_name: str | None
    contact_name: str | None
    email: str
    phone: str | None
    website: str | None
    subject: str
    industry: str
    sub_industry: str | None
    interest_area: str | None
    confidence: float
    company_trust_score: float
    company_trust_label: str
    email_trust_score: float
    email_risk: str
    relevance_score: float
    priority: str
    lead_type: str | None
    status: str
    status_reasons: list[str]
    reviewed: bool
    email_date: str | None
    reason: str
    classification_method: str
    verdict: str = "REAL"
    real_fake_score: float = 80.0
    accuracy_score: float = 80.0
    real_keywords: list[str] = Field(default_factory=list)
    fake_keywords: list[str] = Field(default_factory=list)
    verdict_reason: str = ""


class Page(BaseModel):
    items: list[LeadSummary]
    total: int
    page: int
    page_size: int
    pages: int


class SyncOut(BaseModel):
    id: int
    trigger: str
    mode: str
    status: str
    fetched: int
    processed: int
    needs_review: int
    failed: int
    error: str | None
    started_at: str | None
    finished_at: str | None
