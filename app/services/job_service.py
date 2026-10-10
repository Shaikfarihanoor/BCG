import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, Tuple
from email_validator import validate_email, EmailNotValidError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import Certificate, CertificateStatus, Job, JobStatus
from app.schemas import JobCreateRequest
from app.services.certificate_generator import generate_certificate_pdf
from app.storage import get_certificate_path

logger = logging.getLogger(__name__)


def is_valid_email(email_str: Optional[str]) -> Tuple[bool, Optional[str]]:
    """Validate email address format using email-validator."""
    if not email_str or not email_str.strip():
        return False, "Email address is required and cannot be blank"
    try:
        # Check format without sending network check
        validate_email(email_str.strip(), check_deliverability=False)
        return True, None
    except EmailNotValidError as e:
        return False, str(e)


def create_job(db: Session, request: JobCreateRequest) -> Job:
    """Create a new Job and its associated Certificate records.

    Performs recipient-level validation:
    - Empty or invalid recipients are marked as FAILED immediately with a descriptive error.
    - Valid recipients are marked as PENDING and scheduled for PDF rendering.
    - One bad recipient never blocks the creation or processing of others.
    """
    job_id = str(uuid.uuid4())
    total_count = len(request.recipients)

    job = Job(
        id=job_id,
        event_name=request.event_name.strip(),
        status=JobStatus.PENDING.value,
        total_count=total_count,
        created_at=datetime.now(timezone.utc),
    )
    db.add(job)

    seen_emails = set()

    for rec in request.recipients:
        cert_id = str(uuid.uuid4())
        raw_name = (rec.name or "").strip()
        raw_email = (rec.email or "").strip()

        # Recipient-level validation checks
        validation_error: Optional[str] = None

        if not raw_name:
            validation_error = "Recipient name is required and cannot be blank"
        elif len(raw_name) > settings.MAX_NAME_LENGTH:
            validation_error = (
                f"Recipient name exceeds maximum allowed length of {settings.MAX_NAME_LENGTH} characters"
            )
        else:
            valid_email, email_err = is_valid_email(raw_email)
            if not valid_email:
                validation_error = email_err
            elif settings.FLAG_DUPLICATE_EMAILS and raw_email.lower() in seen_emails:
                validation_error = f"Duplicate email address '{raw_email}' in request batch"

        if raw_email:
            seen_emails.add(raw_email.lower())

        if validation_error:
            # Mark certificate as FAILED upfront due to invalid row data
            cert = Certificate(
                id=cert_id,
                job_id=job_id,
                recipient_name=raw_name,
                recipient_email=raw_email,
                event_name=request.event_name.strip(),
                issue_date=request.issue_date.strip(),
                status=CertificateStatus.FAILED.value,
                error_message=validation_error,
                created_at=datetime.now(timezone.utc),
            )
        else:
            # Ready for background generation
            cert = Certificate(
                id=cert_id,
                job_id=job_id,
                recipient_name=raw_name,
                recipient_email=raw_email,
                event_name=request.event_name.strip(),
                issue_date=request.issue_date.strip(),
                status=CertificateStatus.PENDING.value,
                error_message=None,
                created_at=datetime.now(timezone.utc),
            )

        db.add(cert)

    db.commit()
    db.refresh(job)
    return job


def process_job(job_id: str) -> None:
    """Execute background processing for all pending certificates in a job.

    Guarantees:
    - Failure isolation: Each certificate is processed in its own try/except block.
    - Immediate commit per item: Status is updated in real time for polling clients.
    - Complete error recovery: If a worker encounters an unhandled exception,
      the Job is transitioned to FAILED rather than staying stuck in PROCESSING.
    """
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.error("Job %s not found for processing", job_id)
            return

        # Mark job as currently PROCESSING
        job.status = JobStatus.PROCESSING.value
        db.commit()

        # Query all PENDING certificates
        pending_certs = (
            db.query(Certificate)
            .filter(
                Certificate.job_id == job_id,
                Certificate.status == CertificateStatus.PENDING.value,
            )
            .all()
        )

        for cert in pending_certs:
            try:
                pdf_path = get_certificate_path(job.id, cert.id)
                generate_certificate_pdf(
                    output_path=pdf_path,
                    recipient_name=cert.recipient_name or "Recipient",
                    event_name=cert.event_name,
                    issue_date=cert.issue_date,
                    cert_id=cert.id,
                )

                cert.status = CertificateStatus.COMPLETED.value
                cert.file_path = str(pdf_path)
                cert.error_message = None
                db.commit()
            except Exception as item_err:
                logger.warning(
                    "Failed to generate certificate %s for job %s: %s",
                    cert.id,
                    job_id,
                    item_err,
                )
                db.rollback()
                cert.status = CertificateStatus.FAILED.value
                cert.error_message = str(item_err)
                db.commit()

        # Calculate final job state
        total = db.query(Certificate).filter(Certificate.job_id == job_id).count()
        completed = (
            db.query(Certificate)
            .filter(
                Certificate.job_id == job_id,
                Certificate.status == CertificateStatus.COMPLETED.value,
            )
            .count()
        )
        failed = (
            db.query(Certificate)
            .filter(
                Certificate.job_id == job_id,
                Certificate.status == CertificateStatus.FAILED.value,
            )
            .count()
        )

        if completed == total and total > 0:
            job.status = JobStatus.COMPLETED.value
        elif completed > 0 and failed > 0:
            job.status = JobStatus.COMPLETED_WITH_ERRORS.value
        elif completed == 0:
            job.status = JobStatus.FAILED.value
        else:
            job.status = JobStatus.COMPLETED.value

        job.completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info("Job %s finished with status %s", job_id, job.status)

    except Exception as fatal_err:
        logger.exception("Fatal error while processing job %s: %s", job_id, fatal_err)
        try:
            db.rollback()
            job = db.query(Job).filter(Job.id == job_id).first()
            if job:
                job.status = JobStatus.FAILED.value
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()
