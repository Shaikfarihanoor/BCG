import math
from typing import List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Certificate, CertificateStatus, Job, JobStatus
from app.schemas import (
    CertificateItemResponse,
    JobCreateRequest,
    JobCreateResponse,
    JobListSummary,
    JobStatusResponse,
    PaginationMeta,
)
from app.services.job_service import create_job, process_job
from app.storage import certificate_exists, create_job_zip, get_certificate_path

router = APIRouter(prefix="/api/v1/jobs", tags=["Jobs"])


@router.post(
    "",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a bulk certificate generation job",
    description="Accepts a list of recipients, validates the payload, initializes job records, and initiates background processing.",
)
def submit_job(
    request: JobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Request-level validation: max recipient cap
    if len(request.recipients) > settings.MAX_RECIPIENTS_PER_JOB:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Batch exceeds maximum limit of {settings.MAX_RECIPIENTS_PER_JOB} recipients. "
                f"Received: {len(request.recipients)}"
            ),
        )

    # Create job and certificate records
    job = create_job(db=db, request=request)

    # Schedule background processing
    background_tasks.add_task(process_job, job.id)

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        total=job.total_count,
        status_url=f"/api/v1/jobs/{job.id}",
    )


@router.get(
    "/{job_id}",
    response_model=JobStatusResponse,
    summary="Get job status and progress",
    description="Retrieve aggregate progress counters and individual recipient certificate statuses with pagination.",
)
def get_job_status(
    job_id: str,
    page: int = Query(1, ge=1, description="Page number for certificates list"),
    limit: int = Query(
        settings.DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.MAX_PAGE_SIZE,
        description="Number of certificates to return per page",
    ),
    include_certificates: bool = Query(
        True,
        description="Include certificate details in response",
    ),
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job with id '{job_id}' not found",
        )

    # Compute live counters directly from Certificate rows
    total_count = db.query(Certificate).filter(Certificate.job_id == job_id).count()
    completed_count = (
        db.query(Certificate)
        .filter(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.COMPLETED.value,
        )
        .count()
    )
    failed_count = (
        db.query(Certificate)
        .filter(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.FAILED.value,
        )
        .count()
    )
    pending_count = (
        db.query(Certificate)
        .filter(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.PENDING.value,
        )
        .count()
    )

    cert_responses: List[CertificateItemResponse] = []
    pagination_meta: Optional[PaginationMeta] = None

    if include_certificates:
        offset = (page - 1) * limit
        total_pages = math.ceil(total_count / limit) if total_count > 0 else 1

        certs_query = (
            db.query(Certificate)
            .filter(Certificate.job_id == job_id)
            .order_by(Certificate.created_at)
            .offset(offset)
            .limit(limit)
            .all()
        )

        for cert in certs_query:
            download_url = (
                f"/api/v1/jobs/{job_id}/certificates/{cert.id}"
                if cert.status == CertificateStatus.COMPLETED.value
                else None
            )
            cert_responses.append(
                CertificateItemResponse(
                    id=cert.id,
                    recipient_name=cert.recipient_name,
                    recipient_email=cert.recipient_email,
                    status=cert.status,
                    download_url=download_url,
                    error=cert.error_message,
                )
            )

        pagination_meta = PaginationMeta(
            total=total_count,
            page=page,
            limit=limit,
            total_pages=total_pages,
            has_next=page < total_pages,
            has_prev=page > 1,
        )

    download_all_url = (
        f"/api/v1/jobs/{job_id}/download" if completed_count > 0 else None
    )

    return JobStatusResponse(
        job_id=job.id,
        event_name=job.event_name,
        status=job.status,
        total=total_count,
        completed=completed_count,
        failed=failed_count,
        pending=pending_count,
        created_at=job.created_at,
        completed_at=job.completed_at,
        certificates=cert_responses,
        download_url=download_all_url,
        pagination=pagination_meta,
    )


@router.get(
    "/{job_id}/certificates/{cert_id}",
    summary="Download individual certificate PDF",
    description="Stream the generated PDF for a specific completed certificate.",
)
def download_certificate(
    job_id: str,
    cert_id: str,
    db: Session = Depends(get_db),
):
    cert = (
        db.query(Certificate)
        .filter(Certificate.job_id == job_id, Certificate.id == cert_id)
        .first()
    )

    if not cert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Certificate '{cert_id}' not found for job '{job_id}'",
        )

    if cert.status != CertificateStatus.COMPLETED.value:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Certificate '{cert_id}' is not in COMPLETED status (current status: {cert.status}). "
                f"Error: {cert.error_message or 'Still pending or generation failed'}"
            ),
        )

    file_path = get_certificate_path(job_id, cert_id)
    if not file_path.exists() or file_path.stat().st_size == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate PDF file is missing on storage",
        )

    filename = f"{cert.recipient_name or 'certificate'}_{cert_id[:8]}.pdf".replace(
        " ", "_"
    )
    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=filename,
    )


@router.get(
    "/{job_id}/download",
    summary="Download ZIP archive of all completed certificates",
    description="Compresses all generated PDFs for a job into a single ZIP file for download.",
)
def download_all_certificates(
    job_id: str,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    zip_path = create_job_zip(job_id)
    if not zip_path or not zip_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No completed certificates found for this job to package into a ZIP",
        )

    return FileResponse(
        path=str(zip_path),
        media_type="application/zip",
        filename=f"certificates_{job_id}.zip",
    )


@router.get(
    "",
    response_model=List[JobListSummary],
    summary="List all certificate jobs",
    description="Optional management endpoint to list jobs with overall status and metrics.",
)
def list_jobs(
    skip: int = Query(0, ge=0, description="Offset"),
    limit: int = Query(20, ge=1, le=100, description="Limit"),
    db: Session = Depends(get_db),
):
    jobs = (
        db.query(Job)
        .order_by(Job.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    summaries = []
    for job in jobs:
        total = job.total_count
        completed = (
            db.query(Certificate)
            .filter(
                Certificate.job_id == job.id,
                Certificate.status == CertificateStatus.COMPLETED.value,
            )
            .count()
        )
        failed = (
            db.query(Certificate)
            .filter(
                Certificate.job_id == job.id,
                Certificate.status == CertificateStatus.FAILED.value,
            )
            .count()
        )
        pending = (
            db.query(Certificate)
            .filter(
                Certificate.job_id == job.id,
                Certificate.status == CertificateStatus.PENDING.value,
            )
            .count()
        )

        summaries.append(
            JobListSummary(
                job_id=job.id,
                event_name=job.event_name,
                status=job.status,
                total=total,
                completed=completed,
                failed=failed,
                pending=pending,
                created_at=job.created_at,
                completed_at=job.completed_at,
                status_url=f"/api/v1/jobs/{job.id}",
            )
        )

    return summaries


@router.post(
    "/{job_id}/retry",
    response_model=JobCreateResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Retry failed certificates in a job",
    description="Resets certificates that failed during processing back to PENDING and triggers background re-generation.",
)
def retry_failed_certificates(
    job_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found",
        )

    # Only retry certificates that have valid names and emails (failed due to rendering/transient errors)
    failed_certs = (
        db.query(Certificate)
        .filter(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.FAILED.value,
        )
        .all()
    )

    if not failed_certs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No failed certificates found to retry in this job",
        )

    # Reset retryable certificates to PENDING
    retried_count = 0
    for cert in failed_certs:
        # If failure was due to empty name or invalid email, cannot auto-retry without data fix
        if cert.recipient_name and cert.recipient_email:
            cert.status = CertificateStatus.PENDING.value
            cert.error_message = None
            retried_count += 1

    if retried_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed certificates have permanent validation errors (missing name or invalid email) and cannot be retried.",
        )

    job.status = JobStatus.PROCESSING.value
    db.commit()

    background_tasks.add_task(process_job, job.id)

    return JobCreateResponse(
        job_id=job.id,
        status=job.status,
        total=job.total_count,
        status_url=f"/api/v1/jobs/{job.id}",
    )
