from fastapi import status
from app.models import Certificate, CertificateStatus, Job, JobStatus


def test_empty_recipients_list_rejected(client):
    payload = {
        "event_name": "FastAPI Workshop",
        "issue_date": "2026-10-10",
        "recipients": [],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_missing_event_name_rejected(client):
    payload = {
        "issue_date": "2026-10-10",
        "recipients": [{"name": "John Doe", "email": "john@example.com"}],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_blank_event_name_rejected(client):
    payload = {
        "event_name": "   ",
        "issue_date": "2026-10-10",
        "recipients": [{"name": "John Doe", "email": "john@example.com"}],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


def test_exceeding_max_recipients_rejected(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "MAX_RECIPIENTS_PER_JOB", 5)

    recipients = [{"name": f"User {i}", "email": f"user{i}@example.com"} for i in range(6)]
    payload = {
        "event_name": "Scale Testing",
        "issue_date": "2026-10-10",
        "recipients": recipients,
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "exceeds maximum limit" in response.json()["detail"]


def test_recipient_level_validation_blank_name_and_bad_email(client, db_session):
    payload = {
        "event_name": "Validation Test Event",
        "issue_date": "2026-10-10",
        "recipients": [
            {"name": "Valid User", "email": "valid@example.com"},
            {"name": "", "email": "noname@example.com"},
            {"name": "Bad Email User", "email": "not-an-email"},
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED
    job_id = response.json()["job_id"]

    # Job status should be COMPLETED_WITH_ERRORS
    job = db_session.query(Job).filter(Job.id == job_id).first()
    assert job.status == JobStatus.COMPLETED_WITH_ERRORS.value

    certs = db_session.query(Certificate).filter(Certificate.job_id == job_id).all()
    assert len(certs) == 3

    # Check valid user
    valid_cert = next(c for c in certs if c.recipient_name == "Valid User")
    assert valid_cert.status == CertificateStatus.COMPLETED.value
    assert valid_cert.error_message is None

    # Check blank name user
    blank_cert = next(c for c in certs if c.recipient_email == "noname@example.com")
    assert blank_cert.status == CertificateStatus.FAILED.value
    assert "name is required" in blank_cert.error_message.lower()

    # Check bad email user
    bad_email_cert = next(c for c in certs if c.recipient_name == "Bad Email User")
    assert bad_email_cert.status == CertificateStatus.FAILED.value
    assert bad_email_cert.error_message is not None


def test_recipient_duplicate_email_flagged(client, db_session):
    payload = {
        "event_name": "Duplicate Check Event",
        "issue_date": "2026-10-10",
        "recipients": [
            {"name": "First Instance", "email": "duplicate@example.com"},
            {"name": "Second Instance", "email": "duplicate@example.com"},
        ],
    }
    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED
    job_id = response.json()["job_id"]

    certs = (
        db_session.query(Certificate)
        .filter(Certificate.job_id == job_id)
        .order_by(Certificate.created_at)
        .all()
    )
    assert len(certs) == 2

    # First one succeeds
    assert certs[0].status == CertificateStatus.COMPLETED.value
    # Second duplicate is flagged as FAILED with duplicate error
    assert certs[1].status == CertificateStatus.FAILED.value
    assert "Duplicate email address" in certs[1].error_message
