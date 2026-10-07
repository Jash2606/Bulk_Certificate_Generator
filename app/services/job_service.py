"""API-side job logic: validate recipients, create (= enqueue) a job, and read it back."""
import uuid
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errors import ErrorCode, JobNotFound
from app.models import Certificate, CertificateJob, CertificateStatus, JobStatus
from app.schemas.certificate import RecipientIn
from app.schemas.job import JobCreate

MAX_RAW_VALUE_LENGTH = 255  # size of the recipient_name / recipient_email columns


def create_job(db: Session, payload: JobCreate) -> CertificateJob:
    """Save the job and one certificate row per recipient in a single transaction.

    Committing a PENDING job is what puts it on the queue (workers poll this table), so a job can never
    be saved without being enqueued, or enqueued without being saved.
    """
    job = CertificateJob(
        course_name=payload.course_name,
        issue_date=payload.issue_date,
        issued_by=payload.issued_by,
        status=JobStatus.PENDING,
    )
    first_row_by_email: dict[str, int] = {}
    for row_index, row in enumerate(payload.recipients):
        job.certificates.append(_certificate_for_row(row_index, row, first_row_by_email))
    db.add(job)
    db.commit()
    return job


def get_job(db: Session, job_id: uuid.UUID) -> CertificateJob:
    job = db.get(CertificateJob, job_id)
    if job is None:
        raise JobNotFound(job_id)
    return job


def _certificate_for_row(row_index: int, row: dict[str, Any], first_row_by_email: dict[str, int]) -> Certificate:
    """Validate one recipient row: PENDING if it can be generated, INVALID (with the reason) if not."""
    try:
        recipient = RecipientIn.model_validate(row)
    except ValidationError as exc:
        return Certificate(
            row_index=row_index,
            recipient_name=_raw_text(row.get("name")),
            recipient_email=_raw_text(row.get("email")),
            status=CertificateStatus.INVALID,
            error_code=ErrorCode.INVALID_RECIPIENT,
            error_message=_describe(exc),
        )

    email_key = recipient.email.lower()
    if email_key in first_row_by_email:
        return Certificate(
            row_index=row_index,
            recipient_name=recipient.name,
            recipient_email=recipient.email,
            status=CertificateStatus.INVALID,
            error_code=ErrorCode.DUPLICATE_EMAIL,
            error_message=f"email: duplicate of row {first_row_by_email[email_key]}",
        )
    first_row_by_email[email_key] = row_index

    return Certificate(
        row_index=row_index,
        recipient_name=recipient.name,
        recipient_email=recipient.email,
        status=CertificateStatus.PENDING,
    )


def _describe(exc: ValidationError) -> str:
    """'name: String should have at least 1 character; email: value is not a valid email address: ...'"""
    return "; ".join(
        f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}" for error in exc.errors()
    )


def _raw_text(value: Any) -> str | None:
    """Keep what the client sent for an invalid row (so they can find it) in a form the column accepts.

    Any JSON value becomes text, NUL characters are dropped (PostgreSQL text can't hold them) and the
    result is cut to the column size.
    """
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    return text.replace("\x00", "")[:MAX_RAW_VALUE_LENGTH]
