"""Small builders and helpers shared by the tests."""
from pathlib import Path

from app.core.config import settings


def recipients(*names: str) -> list[dict[str, str]]:
    """Valid recipient rows: recipients("Asha Rao") -> [{"name": "Asha Rao", "email": "asha.rao@example.com"}]"""
    return [{"name": name, "email": f"{name.lower().replace(' ', '.')}@example.com"} for name in names]


def job_payload(recipient_rows: list[dict], **overrides) -> dict:
    return {
        "course_name": "FastAPI Bootcamp",
        "issue_date": "2026-10-08",
        "issued_by": "Aero Academy",
        "recipients": recipient_rows,
        **overrides,
    }


def pdf_path(job_id: str, certificate_id: str) -> Path:
    """Where the worker stores a certificate's PDF."""
    return settings.storage_dir / job_id / f"{certificate_id}.pdf"


def error_of(response) -> dict:
    """The {"code", "message", "details"} part of an error response."""
    return response.json()["error"]
