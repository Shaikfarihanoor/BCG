from fastapi import status


def test_get_status_unknown_job_404(client):
    response = client.get("/api/v1/jobs/non-existent-uuid-12345")
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()


def test_get_status_all_succeeded(client):
    payload = {
        "event_name": "Full Success Workshop",
        "issue_date": "2026-10-10",
        "recipients": [
            {"name": "Alice Wonderland", "email": "alice@example.com"},
            {"name": "Bob Builder", "email": "bob@example.com"},
        ],
    }
    create_res = client.post("/api/v1/jobs", json=payload)
    assert create_res.status_code == status.HTTP_202_ACCEPTED
    job_id = create_res.json()["job_id"]

    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == status.HTTP_200_OK
    data = status_res.json()

    assert data["job_id"] == job_id
    assert data["status"] == "COMPLETED"
    assert data["total"] == 2
    assert data["completed"] == 2
    assert data["failed"] == 0
    assert data["pending"] == 0
    assert data["download_url"] == f"/api/v1/jobs/{job_id}/download"
    assert len(data["certificates"]) == 2
    for cert in data["certificates"]:
        assert cert["status"] == "COMPLETED"
        assert cert["download_url"] is not None
        assert cert["error"] is None


def test_get_status_all_failed(client):
    payload = {
        "event_name": "Failed Workshop",
        "issue_date": "2026-10-10",
        "recipients": [
            {"name": "", "email": "invalid-email"},
            {"name": "   ", "email": "bad-email-2"},
        ],
    }
    create_res = client.post("/api/v1/jobs", json=payload)
    assert create_res.status_code == status.HTTP_202_ACCEPTED
    job_id = create_res.json()["job_id"]

    status_res = client.get(f"/api/v1/jobs/{job_id}")
    assert status_res.status_code == status.HTTP_200_OK
    data = status_res.json()

    assert data["status"] == "FAILED"
    assert data["total"] == 2
    assert data["completed"] == 0
    assert data["failed"] == 2
    assert data["pending"] == 0


def test_status_pagination(client):
    recipients = [
        {"name": f"Student {i}", "email": f"student{i}@example.com"}
        for i in range(15)
    ]
    payload = {
        "event_name": "Pagination Course",
        "issue_date": "2026-10-10",
        "recipients": recipients,
    }
    create_res = client.post("/api/v1/jobs", json=payload)
    job_id = create_res.json()["job_id"]

    # Request page 1 with limit 5
    page1_res = client.get(f"/api/v1/jobs/{job_id}?page=1&limit=5")
    assert page1_res.status_code == status.HTTP_200_OK
    data1 = page1_res.json()
    assert len(data1["certificates"]) == 5
    assert data1["pagination"]["total"] == 15
    assert data1["pagination"]["page"] == 1
    assert data1["pagination"]["limit"] == 5
    assert data1["pagination"]["total_pages"] == 3
    assert data1["pagination"]["has_next"] is True
    assert data1["pagination"]["has_prev"] is False

    # Request page 3 with limit 5
    page3_res = client.get(f"/api/v1/jobs/{job_id}?page=3&limit=5")
    assert page3_res.status_code == status.HTTP_200_OK
    data3 = page3_res.json()
    assert len(data3["certificates"]) == 5
    assert data3["pagination"]["page"] == 3
    assert data3["pagination"]["has_next"] is False
    assert data3["pagination"]["has_prev"] is True
