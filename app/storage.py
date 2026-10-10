import re
import zipfile
from pathlib import Path
from typing import Optional

from app.config import settings

SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def validate_identifier(identifier: str) -> str:
    """Ensure identifier does not contain directory traversal characters."""
    if not identifier or not SAFE_ID_PATTERN.match(identifier):
        raise ValueError(f"Invalid identifier for storage path: '{identifier}'")
    return identifier


def get_storage_root() -> Path:
    """Return resolved storage directory root."""
    return settings.storage_path


def get_job_dir(job_id: str) -> Path:
    """Return the directory path for a given job and ensure it exists."""
    safe_id = validate_identifier(job_id)
    job_dir = get_storage_root() / safe_id
    job_dir.mkdir(parents=True, exist_ok=True)
    return job_dir


def get_certificate_path(job_id: str, cert_id: str) -> Path:
    """Return the absolute path for a certificate PDF."""
    safe_job_id = validate_identifier(job_id)
    safe_cert_id = validate_identifier(cert_id)
    return get_storage_root() / safe_job_id / f"{safe_cert_id}.pdf"


def certificate_exists(job_id: str, cert_id: str) -> bool:
    """Check if the certificate PDF exists and has non-zero size."""
    try:
        path = get_certificate_path(job_id, cert_id)
        return path.exists() and path.is_file() and path.stat().st_size > 0
    except ValueError:
        return False


def create_job_zip(job_id: str) -> Optional[Path]:
    """Compress all completed PDF certificates in the job directory into a ZIP archive.
    Returns the Path to the zip file, or None if no PDFs exist.
    """
    safe_job_id = validate_identifier(job_id)
    job_dir = get_job_dir(safe_job_id)
    pdf_files = list(job_dir.glob("*.pdf"))

    if not pdf_files:
        return None

    zip_path = job_dir / f"certificates_{safe_job_id}.zip"
    # Create or overwrite the zip archive
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for pdf_path in pdf_files:
            if pdf_path.is_file() and pdf_path.stat().st_size > 0:
                zf.write(pdf_path, arcname=pdf_path.name)

    return zip_path
