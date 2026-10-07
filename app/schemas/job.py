"""Request and response shapes for certificate generation jobs."""
import uuid
from collections.abc import Mapping
from datetime import date, datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.core.config import settings
from app.models import CertificateStatus, JobStatus
from app.schemas.certificate import CertificateOut, ensure_printable

CourseName = Annotated[str, StringConstraints(min_length=1, max_length=200), AfterValidator(ensure_printable)]
IssuerName = Annotated[str, StringConstraints(min_length=1, max_length=100), AfterValidator(ensure_printable)]


class JobCreate(BaseModel):
    """Body of POST /jobs.

    The request as a whole must be well formed (otherwise 422). The recipients are accepted as raw
    objects and checked one by one against RecipientIn, so one bad row doesn't reject the whole batch.
    """

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "course_name": "FastAPI Bootcamp",
                    "issue_date": "2026-10-08",
                    "issued_by": "Aero Academy",
                    "recipients": [
                        {"name": "Asha Rao", "email": "asha@example.com"},
                        {"name": "José Müller", "email": "jose@example.com"},
                        {"name": "", "email": "not-an-email"},
                    ],
                }
            ]
        },
    )

    course_name: CourseName
    issue_date: date = Field(default_factory=date.today)
    issued_by: IssuerName | None = None
    recipients: list[dict[str, Any]] = Field(
        min_length=1,
        max_length=settings.max_recipients_per_job,
        description="Objects with `name` and `email`. Invalid rows are reported as INVALID, not rejected.",
    )


class JobProgress(BaseModel):
    total: int
    pending: int
    generated: int
    failed: int
    invalid: int
    percent_complete: float  # share of certificates that are finished, whatever the outcome

    @classmethod
    def from_counts(cls, counts: Mapping[CertificateStatus, int]) -> "JobProgress":
        total = sum(counts.values())
        pending = counts.get(CertificateStatus.PENDING, 0)
        return cls(
            total=total,
            pending=pending,
            generated=counts.get(CertificateStatus.GENERATED, 0),
            failed=counts.get(CertificateStatus.FAILED, 0),
            invalid=counts.get(CertificateStatus.INVALID, 0),
            percent_complete=round((total - pending) / total * 100, 1) if total else 100.0,
        )


class JobCreatedResponse(BaseModel):
    job_id: uuid.UUID
    status: JobStatus
    status_url: str
    progress: JobProgress


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: JobStatus
    course_name: str
    issue_date: date
    issued_by: str | None
    attempts: int
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class JobStatusResponse(BaseModel):
    job: JobOut
    progress: JobProgress
    certificates: list[CertificateOut]
