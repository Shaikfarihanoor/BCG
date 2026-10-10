# Bulk Certificate Generator API

A high-performance, resilient backend API built with **FastAPI**, **SQLAlchemy 2.0**, and **ReportLab** for bulk certificate generation. The system handles large batches of certificate issuance asynchronously with per-recipient failure isolation, real-time status polling, pagination, and ZIP download capabilities.

---

## 1. Quick Start & Setup

### Prerequisites
- Python 3.10+ (tested on Python 3.13)
- pip

### Installation
Clone or navigate to the project directory and create a virtual environment:

```bash
# 1. Create and activate a virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# On Windows (cmd):
.\.venv\Scripts\activate.bat

# 2. Install dependencies
pip install -r requirements.txt
```

### Running the API
Start the development server using Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Once running:
- **Interactive Web Interface Dashboard**: [http://localhost:8000/](http://localhost:8000/)
- **Interactive Swagger Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 2. Running Tests

The test suite covers job creation, request validation, recipient-level failure isolation, PDF rendering, polling, pagination, and download flows using `pytest` and FastAPI `TestClient`:

```bash
pytest -v
```

All tests execute in isolated temporary directories with an in-memory/temp SQLite database without polluting runtime data.

---

## 3. API Usage & Example cURL Commands

### 1. Submit a Bulk Generation Job
Submits a batch of recipients for certificate generation. Returns `202 Accepted` immediately.

```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
  -H "Content-Type: application/json" \
  -d '{
    "event_name": "Full-Stack Python Bootcamp 2026",
    "issue_date": "2026-10-10",
    "recipients": [
      {"name": "Asha Rao", "email": "asha@example.com"},
      {"name": "Ravi Kumar", "email": "ravi@example.com"},
      {"name": "", "email": "bad_entry@example.com"},
      {"name": "Vikram Seth", "email": "invalid-email-address"}
    ]
  }'
```

**Response (`202 Accepted`):**
```json
{
  "job_id": "936d5f47-2cb2-4a0b-9304-48f86feaa809",
  "status": "PENDING",
  "total": 4,
  "status_url": "/api/v1/jobs/936d5f47-2cb2-4a0b-9304-48f86feaa809"
}
```

---

### 2. Check Job Status & Progress (with Pagination)
Poll the status of a job, tracking total, completed, failed, and pending counts:

```bash
curl -X GET "http://localhost:8000/api/v1/jobs/936d5f47-2cb2-4a0b-9304-48f86feaa809?page=1&limit=50"
```

**Response (`200 OK`):**
```json
{
  "job_id": "936d5f47-2cb2-4a0b-9304-48f86feaa809",
  "event_name": "Full-Stack Python Bootcamp 2026",
  "status": "COMPLETED_WITH_ERRORS",
  "total": 4,
  "completed": 2,
  "failed": 2,
  "pending": 0,
  "certificates": [
    {
      "id": "e2da1b60-15cb-424a-b565-d603a985e507",
      "recipient_name": "Asha Rao",
      "recipient_email": "asha@example.com",
      "status": "COMPLETED",
      "download_url": "/api/v1/jobs/936d5f47-2cb2-4a0b-9304-48f86feaa809/certificates/e2da1b60-15cb-424a-b565-d603a985e507",
      "error": null
    },
    {
      "id": "b18b6fc7-0ae0-4b89-a292-cc7484df4612",
      "recipient_name": "",
      "recipient_email": "bad_entry@example.com",
      "status": "FAILED",
      "download_url": null,
      "error": "Recipient name is required and cannot be blank"
    }
  ],
  "download_url": "/api/v1/jobs/936d5f47-2cb2-4a0b-9304-48f86feaa809/download",
  "pagination": {
    "total": 4,
    "page": 1,
    "limit": 50,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

---

### 3. Download a Single Certificate PDF
Downloads the rendered landscape A4 PDF for an individual certificate:

```bash
curl -X GET "http://localhost:8000/api/v1/jobs/936d5f47-2cb2-4a0b-9304-48f86feaa809/certificates/e2da1b60-15cb-424a-b565-d603a985e507" \
  --output "certificate.pdf"
```

---

### 4. Download All Completed Certificates as a ZIP
Downloads a compressed archive containing all successfully generated certificates in the batch:

```bash
curl -X GET "http://localhost:8000/api/v1/jobs/936d5f47-2cb2-4a0b-9304-48f86feaa809/download" \
  --output "certificates_bundle.zip"
```

---

### 5. Retry Failed Certificates (Optional Bonus Endpoint)
Retries generation for certificates that failed due to transient rendering errors:

```bash
curl -X POST "http://localhost:8000/api/v1/jobs/936d5f47-2cb2-4a0b-9304-48f86feaa809/retry"
```

---

## 4. Architecture & Design Decisions

```
Client
  │  POST /api/v1/jobs
  ▼
FastAPI Router  ────────► Request-Level Validation (Pydantic: empty list, caps, missing fields -> 422)
  │
  ▼
Job Service     ────────► Recipient-Level Validation (invalid row -> FAILED row, valid row -> PENDING)
  │                      Database: Inserts Job + Certificate rows
  ▼
Returns 202 Accepted + job_id
  │
  ▼ (Asynchronous)
BackgroundTasks (process_job)
  │
  ├── For each PENDING certificate:
  │     ├── try:
  │     │     render PDF with ReportLab ──► save to ./generated/<job_id>/<cert_id>.pdf
  │     │     mark COMPLETED ──► DB commit
  │     └── except:
  │           mark FAILED + save error_message ──► DB commit (never breaks loop!)
  │
  └── finally:
        Compute aggregate job status (COMPLETED | COMPLETED_WITH_ERRORS | FAILED)
        Record completed_at timestamp
```

### 1. Processing Model: Synchronous vs BackgroundTasks vs Celery
- **Synchronous**: Blocks HTTP request while generating PDFs sequentially. Unacceptable for bulk requests because HTTP requests time out (e.g., 30s gateway timeouts), and client UX degrades severely.
- **FastAPI BackgroundTasks (Current Choice)**:
  - **Pros**: Zero third-party infrastructure required (no Redis, RabbitMQ, or worker daemons needed). Reviewer can clone and run with a single command. High performance for small-to-medium batches.
  - **Cons**: Task state is tied to the local application process. If the server process crashes or restarts during execution, in-flight jobs are interrupted. Does not scale horizontally across multiple worker nodes.
- **Celery + Redis / RQ (Production Scale Alternative)**:
  - Production choice when scaling across multiple servers. Features persistent task queues, distributed worker pools, automatic retry backoffs, and heartbeat monitoring.
  - The business logic in `job_service.process_job(job_id)` is completely decoupled from FastAPI HTTP handlers, making a migration to Celery as simple as decorating `process_job.delay(job_id)`.

### 2. Validation Policy: Request-Level vs Recipient-Level
- **Request-Level (HTTP 422 Unprocessable Content)**:
  - If the entire payload is malformed (missing `event_name`, blank event name, empty `recipients` array, wrong types, or exceeding the batch cap of 1,000 recipients), the entire request is rejected with 422.
- **Recipient-Level (Failure Isolation)**:
  - If an individual recipient within the array has a blank name, an invalid email address format, or is a duplicate within the same batch, the batch is **not rejected**.
  - Instead, the valid recipients are scheduled for generation, while the invalid entry is persisted immediately with status `FAILED` and a specific explanation (`error_message`).
- **Duplicate Email Policy**:
  - Within a single request batch, duplicate email addresses are flagged as `FAILED` (`Duplicate email address in request batch`) while preserving the first instance. This prevents accidental duplicate generation.

### 3. Job Status Lifecycle
- `PENDING`: Job accepted, awaiting execution.
- `PROCESSING`: Background worker has acquired the job and is generating PDFs.
- `COMPLETED`: All recipient certificates were generated successfully.
- `COMPLETED_WITH_ERRORS`: Some certificates succeeded, but one or more failed validation or rendering.
- `FAILED`: All certificates in the job failed, or a fatal job-level error occurred.

### 4. Storage and Security
- Certificate files are stored as `./generated/<job_id>/<cert_id>.pdf` using UUIDs.
- Storing files by UUID (rather than recipient name) completely eliminates path traversal risks (`../../`), invalid filename characters, and name collision issues.
- The single PDF download endpoint provides friendly filenames in `Content-Disposition` header: `f"{recipient_name}_{cert_id[:8]}.pdf"`.

---

## 5. Known Limitations & Production Enhancements

| Area | Current Implementation | Production Upgrade Path |
|---|---|---|
| **Task Queue** | In-process `FastAPI BackgroundTasks` | Celery / Temporal / AWS SQS with distributed worker cluster |
| **Storage** | Local disk (`./generated`) | Object Storage (AWS S3, Google Cloud Storage, Azure Blob) with presigned URLs |
| **Crash Recovery** | Uncaught crashes mark job as FAILED | Resumable jobs: worker picks up certificates with `status = 'PENDING'` upon reboot |
| **Authentication** | Open API endpoints | API Key / OAuth2 Bearer tokens with rate-limiting per API key |
| **Fonts & Unicode** | Standard ReportLab Type 1 fonts with Latin-1 sanitization | Register custom TrueType Fonts (TTF) like Noto Sans or DejaVu Sans for full Devanagari/CJK support |

---

## 6. Interview Preparation: Key Architectural Questions

#### Q1: Why BackgroundTasks over Celery? What breaks at scale?
> **Answer**: `BackgroundTasks` was chosen to keep the assignment portable, self-contained, and easy to review without spinning up external brokers (Redis/RabbitMQ). At scale, `BackgroundTasks` breaks because jobs are held in the server memory; if the container restarts or crashes mid-run, jobs are lost. Furthermore, tasks cannot be distributed across multiple worker machines. In production, Celery or SQS provides durable message persistence, automatic retries with exponential backoff, and horizontal scaling.

#### Q2: How would you make processing resumable?
> **Answer**: Because each certificate is an individual row in the database with its own status (`PENDING`, `COMPLETED`, `FAILED`), a restarted worker can simply run:
> ```sql
> SELECT * FROM certificates WHERE job_id = :job_id AND status = 'PENDING';
> ```
> This prevents regenerating already completed certificates and allows the worker to continue right where it left off.

#### Q3: What if a job has 100,000 recipients?
> **Answer**: 
> 1. Rejecting 100,000 items in a single HTTP JSON body: accept a CSV/S3 file upload instead of a massive JSON payload.
> 2. Chunking: Split the 100,000 items into batches of 500 and enqueue 200 distinct Celery tasks.
> 3. Worker Pool: Distribute rendering across an auto-scaling worker cluster (e.g., Kubernetes / AWS Fargate).
> 4. Storage: Upload PDFs directly to S3 and generate presigned URLs instead of serving multi-gigabyte ZIP files through the API server.
> 5. Database: Paginate all status queries with indexed cursor-based pagination.

#### Q4: Changed requirement: Second template or emailing certificates?
> **Answer**: 
> The code cleanly separates the router, service, and generator layers.
> - To support multiple templates: Add a `template_id` column to `Job`, and implement a Template Registry / Factory pattern in `certificate_generator.py`.
> - To email certificates: Slot a notification/email delivery step into `job_service.py` right after successful PDF generation (e.g. `send_certificate_email(cert)`), keeping it decoupled from PDF rendering.

#### Q5: What if two clients poll status mid-processing?
> **Answer**: 
> Both reads are completely safe. The status endpoint issues read queries against SQLite/PostgreSQL with transactional isolation. Because the background worker commits progress after each individual certificate, polling clients observe real-time incrementing counters without table locks or race conditions.
