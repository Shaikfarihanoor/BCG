from fastapi import status
from app.models import Certificate, CertificateStatus, Job, JobStatus


def test_create_valid_job(client, db_session):
    payload = {
        "event_name": "Python Bootcamp 2026",
        "issue_date": "2026-10-01",
        "recipients": [
            {"name": "Asha Rao", "email": "asha@example.com"},
            {"name": "Ravi Kumar", "email": "ravi@example.com"},
        ],
    }

    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()

    assert "job_id" in data
    assert data["total"] == 2
    assert data["status_url"] == f"/api/v1/jobs/{data['job_id']}"

    # Verify rows in DB
    job_id = data["job_id"]
    job = db_session.query(Job).filter(Job.id == job_id).first()
    assert job is not None
    assert job.event_name == "Python Bootcamp 2026"
    assert job.total_count == 2

    # Because TestClient processes background tasks before response returns:
    assert job.status == JobStatus.COMPLETED.value

    certs = db_session.query(Certificate).filter(Certificate.job_id == job_id).all()
    assert len(certs) == 2
    for cert in certs:
        assert cert.status == CertificateStatus.COMPLETED.value
        assert cert.file_path is not None
