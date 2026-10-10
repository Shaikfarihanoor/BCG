from fastapi import status
from app.models import Certificate, CertificateStatus, Job, JobStatus
import app.services.job_service as job_service_module


def test_generator_runtime_failure_isolation(client, db_session, monkeypatch):
    """Test that when ReportLab generator raises an exception for one recipient,
    only that recipient is marked FAILED, the other recipients complete successfully,
    and the overall job transitions to COMPLETED_WITH_ERRORS.
    """
    real_generator = job_service_module.generate_certificate_pdf

    def mock_generator(output_path, recipient_name, event_name, issue_date, cert_id):
        # Intentionally fail for Bob
        if "Bob" in recipient_name:
            raise RuntimeError("Simulated PDF renderer crash for Bob")
        return real_generator(output_path, recipient_name, event_name, issue_date, cert_id)

    monkeypatch.setattr(job_service_module, "generate_certificate_pdf", mock_generator)

    payload = {
        "event_name": "Resilience Testing Workshop",
        "issue_date": "2026-10-10",
        "recipients": [
            {"name": "Alice Healthy", "email": "alice@healthy.com"},
            {"name": "Bob Crashing", "email": "bob@crash.com"},
            {"name": "Charlie Healthy", "email": "charlie@healthy.com"},
        ],
    }

    response = client.post("/api/v1/jobs", json=payload)
    assert response.status_code == status.HTTP_202_ACCEPTED
    job_id = response.json()["job_id"]

    # Verify status via API
    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == status.HTTP_200_OK
    data = status_res.json()

    assert data["status"] == "COMPLETED_WITH_ERRORS"
    assert data["total"] == 3
    assert data["completed"] == 2
    assert data["failed"] == 1

    bob_cert = next(c for c in data["certificates"] if c["recipient_name"] == "Bob Crashing")
    assert bob_cert["status"] == "FAILED"
    assert "Simulated PDF renderer crash" in bob_cert["error"]
    assert bob_cert["download_url"] is None

    alice_cert = next(c for c in data["certificates"] if c["recipient_name"] == "Alice Healthy")
    assert alice_cert["status"] == "COMPLETED"
    assert alice_cert["download_url"] is not None

    charlie_cert = next(c for c in data["certificates"] if c["recipient_name"] == "Charlie Healthy")
    assert charlie_cert["status"] == "COMPLETED"
    assert charlie_cert["download_url"] is not None

    # Now restore generator and test RETRY
    monkeypatch.setattr(job_service_module, "generate_certificate_pdf", real_generator)
    retry_res = client.post(f"/api/v1/jobs/{job_id}/retry")
    assert retry_res.status_code == status.HTTP_202_ACCEPTED

    # Re-check status: Bob should now be COMPLETED, overall status COMPLETED
    updated_status = client.get(f"/api/v1/jobs/{job_id}").json()
    assert updated_status["status"] == "COMPLETED"
    assert updated_status["completed"] == 3
    assert updated_status["failed"] == 0

