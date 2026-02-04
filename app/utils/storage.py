import shutil
from pathlib import Path

from app.config import settings


def save_upload(job_id: str, file_bytes: bytes, filename: str) -> str:
    """Save uploaded file to disk. Returns the relative path."""
    job_dir = settings.UPLOAD_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    file_path = job_dir / "model.stl"
    file_path.write_bytes(file_bytes)
    return str(file_path.relative_to(settings.UPLOAD_DIR))


def get_upload_path(relative_path: str) -> Path:
    """Get the absolute path for a stored upload."""
    return settings.UPLOAD_DIR / relative_path


def delete_upload(job_id: str) -> None:
    """Delete all files for a job."""
    job_dir = settings.UPLOAD_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
