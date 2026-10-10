from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field, field_validator


class RecipientInput(BaseModel):
    """Input representation of a certificate recipient.
    Validation happens at recipient level so invalid individual rows
    do not reject the entire bulk request.
    """
    name: Optional[str] = Field(default="", description="Recipient full name")
    email: Optional[str] = Field(default="", description="Recipient email address")


class JobCreateRequest(BaseModel):
    """Request payload for creating a bulk certificate generation job."""
    event_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the event or course for the certificate",
    )
    issue_date: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Date of issuance (e.g. YYYY-MM-DD or October 10, 2026)",
    )
    recipients: List[RecipientInput] = Field(
        ...,
        min_length=1,
        description="List of recipients (up to configured maximum, e.g. 1000)",
    )

    @field_validator("event_name")
    @classmethod
    def validate_event_name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("event_name cannot be blank or empty whitespace")
        return v.strip()

    @field_validator("issue_date")
    @classmethod
    def validate_issue_date_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("issue_date cannot be blank or empty whitespace")
        return v.strip()


class JobCreateResponse(BaseModel):
    """Immediate 202 Accepted response upon job creation."""
    job_id: str
    status: str
    total: int
    status_url: str


class CertificateItemResponse(BaseModel):
    """Per-certificate status and download details."""
    id: str
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    status: str
    download_url: Optional[str] = None
    error: Optional[str] = None


class PaginationMeta(BaseModel):
    """Pagination metadata for certificate listings."""
    total: int
    page: int
    limit: int
    total_pages: int
    has_next: bool
    has_prev: bool


class JobStatusResponse(BaseModel):
    """Complete job status with aggregate counts and per-certificate details."""
    job_id: str
    event_name: str
    status: str
    total: int
    completed: int
    failed: int
    pending: int
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    certificates: List[CertificateItemResponse]
    download_url: Optional[str] = None
    pagination: Optional[PaginationMeta] = None


class JobListSummary(BaseModel):
    """Summary of a job in the list jobs endpoint."""
    job_id: str
    event_name: str
    status: str
    total: int
    completed: int
    failed: int
    pending: int
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status_url: str
