import json
import time
import urllib.request

base_url = "http://127.0.0.1:8000"

print("--- Step 1: Health Check ---")
with urllib.request.urlopen(f"{base_url}/health") as res:
    print("Health response:", res.status, res.read().decode())

print("\n--- Step 2: Submitting Bulk Job (2 valid recipients, 1 invalid blank name) ---")
payload = {
    "event_name": "Full-Stack Python Bootcamp 2026",
    "issue_date": "2026-10-10",
    "recipients": [
        {"name": "Asha Rao", "email": "asha@example.com"},
        {"name": "Ravi Kumar", "email": "ravi@example.com"},
        {"name": "", "email": "noname@example.com"}
    ]
}

req = urllib.request.Request(
    f"{base_url}/api/v1/jobs",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)

with urllib.request.urlopen(req) as res:
    create_data = json.loads(res.read().decode())
    print("Job submission response:", res.status)
    print(json.dumps(create_data, indent=2))

job_id = create_data["job_id"]

print("\n--- Step 3: Polling Job Status ---")
# Give background task half a second to finish rendering
time.sleep(1.0)

with urllib.request.urlopen(f"{base_url}/api/v1/jobs/{job_id}") as res:
    status_data = json.loads(res.read().decode())
    print(json.dumps(status_data, indent=2))

completed_certs = [c for c in status_data["certificates"] if c["status"] == "COMPLETED"]

if completed_certs:
    first_cert = completed_certs[0]
    print(f"\n--- Step 4: Downloading Individual PDF for {first_cert['recipient_name']} ---")
    download_url = f"{base_url}/api/v1/jobs/{job_id}/certificates/{first_cert['id']}"
    with urllib.request.urlopen(download_url) as res:
        pdf_data = res.read()
        print(f"Status: {res.status}")
        print(f"File size: {len(pdf_data)} bytes")
        print(f"Header: {pdf_data[:5]} (Valid PDF: {pdf_data.startswith(b'%PDF')})")

print("\n--- Step 5: Downloading ZIP Archive of All Completed Certificates ---")
zip_url = f"{base_url}/api/v1/jobs/{job_id}/download"
with urllib.request.urlopen(zip_url) as res:
    zip_data = res.read()
    print(f"Status: {res.status}")
    print(f"ZIP Archive size: {len(zip_data)} bytes")
    print(f"Header: {zip_data[:4]} (Valid ZIP: {zip_data.startswith(b'PK')})")

print("\n--- Live Verification Succeeded! ---")
