import io
import zipfile
from fastapi import status


def test_download_single_pdf_success(client):
    payload = {
        "event_name": "Download Test Event",
        "issue_date": "2026-10-10",
        "recipients": [{"name": "Dana Scully", "email": "scully@fbi.gov"}],
    }
    create_res = client.post("/api/v1/jobs", json=payload)
    job_id = create_res.json()["job_id"]

    status_res = client.get(f"/api/v1/jobs/{job_id}")
    cert_id = status_res.json()["certificates"][0]["id"]

    download_res = client.get(f"/api/v1/jobs/{job_id}/certificates/{cert_id}")
    assert download_res.status_code == status.HTTP_200_OK
    assert "application/pdf" in download_res.headers["content-type"]
    assert download_res.content.startswith(b"%PDF")


def test_download_failed_certificate_returns_404(client):
    payload = {
        "event_name": "Failed Download Test",
        "issue_date": "2026-10-10",
        "recipients": [{"name": "", "email": "noname@example.com"}],
    }
    create_res = client.post("/api/v1/jobs", json=payload)
    job_id = create_res.json()["job_id"]

    status_res = client.get(f"/api/v1/jobs/{job_id}")
    cert_id = status_res.json()["certificates"][0]["id"]

    download_res = client.get(f"/api/v1/jobs/{job_id}/certificates/{cert_id}")
    assert download_res.status_code == status.HTTP_404_NOT_FOUND
    assert "not in COMPLETED status" in download_res.json()["detail"]


def test_download_unknown_certificate_returns_404(client):
    res = client.get("/api/v1/jobs/unknown-job-id/certificates/unknown-cert-id")
    assert res.status_code == status.HTTP_404_NOT_FOUND


def test_download_all_zip_archive(client):
    payload = {
        "event_name": "Zip Archive Event",
        "issue_date": "2026-10-10",
        "recipients": [
            {"name": "Fox Mulder", "email": "mulder@fbi.gov"},
            {"name": "Walter Skinner", "email": "skinner@fbi.gov"},
        ],
    }
    create_res = client.post("/api/v1/jobs", json=payload)
    job_id = create_res.json()["job_id"]

    zip_res = client.get(f"/api/v1/jobs/{job_id}/download")
    assert zip_res.status_code == status.HTTP_200_OK
    assert "application/zip" in zip_res.headers["content-type"]

    # Verify that content is a valid ZIP containing 2 PDF files
    with zipfile.ZipFile(io.BytesIO(zip_res.content)) as zf:
        namelist = zf.namelist()
        assert len(namelist) == 2
        for name in namelist:
            assert name.endswith(".pdf")
            data = zf.read(name)
            assert data.startswith(b"%PDF")


def test_frontend_index_and_assets(client):
    index_res = client.get("/")
    assert index_res.status_code == status.HTTP_200_OK
    assert "text/html" in index_res.headers["content-type"]
    assert "CertiCraft Studio" in index_res.text

    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == status.HTTP_200_OK

    js_res = client.get("/static/js/app.js")
    assert js_res.status_code == status.HTTP_200_OK

