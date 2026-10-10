import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class CertificateStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Job(Base):
    __tablename__ = "jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_name = Column(String(255), nullable=False)
    status = Column(
        String(32),
        default=JobStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    total_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to Certificate records
    certificates = relationship(
        "Certificate",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="Certificate.created_at",
    )

    def __repr__(self) -> str:
        return f"<Job id={self.id} status={self.status} total={self.total_count}>"


class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id = Column(String(36), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_name = Column(String(255), nullable=True)
    recipient_email = Column(String(255), nullable=True)
    event_name = Column(String(255), nullable=False)
    issue_date = Column(String(64), nullable=False)
    status = Column(
        String(32),
        default=CertificateStatus.PENDING.value,
        nullable=False,
        index=True,
    )
    file_path = Column(String(512), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    # Relationship back to Job
    job = relationship("Job", back_populates="certificates")

    def __repr__(self) -> str:
        return f"<Certificate id={self.id} recipient={self.recipient_name} status={self.status}>"
