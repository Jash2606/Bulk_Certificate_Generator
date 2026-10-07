import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.certificate import Certificate


class JobStatus(StrEnum):
    PENDING = "PENDING"  # queued, waiting for a worker
    PROCESSING = "PROCESSING"  # claimed by a worker
    COMPLETED = "COMPLETED"  # every certificate was generated
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"  # some generated, some invalid or failed
    FAILED = "FAILED"  # nothing could be generated


class CertificateJob(Base):
    """One bulk request. This table is also the work queue: a PENDING row is a job waiting for a worker."""

    __tablename__ = "certificate_jobs"
    # Serves the worker's claim query: "oldest job with status X".
    __table_args__ = (Index("ix_certificate_jobs_status_created_at", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    course_name: Mapped[str] = mapped_column(String(200))
    issue_date: Mapped[date]
    issued_by: Mapped[str | None] = mapped_column(String(100))
    # native_enum=False stores the status as VARCHAR, so adding a status later needs no ALTER TYPE.
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, native_enum=False, length=32), default=JobStatus.PENDING
    )
    attempts: Mapped[int] = mapped_column(default=0, server_default="0")  # times a worker has claimed this job
    error_message: Mapped[str | None] = mapped_column(Text)  # set only if the whole job aborted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # last sign of life from its worker
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    certificates: Mapped[list["Certificate"]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="Certificate.row_index"
    )
