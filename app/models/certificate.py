import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.errors import ErrorCode

if TYPE_CHECKING:
    from app.models.job import CertificateJob

MAX_ERROR_MESSAGE_LENGTH = 500


class CertificateStatus(StrEnum):
    INVALID = "INVALID"  # recipient data failed validation, so it is never generated
    PENDING = "PENDING"  # waiting for a worker
    GENERATED = "GENERATED"  # PDF created and downloadable
    FAILED = "FAILED"  # generation raised an error (can be retried)


class Certificate(Base):
    """One recipient of a job, i.e. one certificate to generate."""

    __tablename__ = "certificates"
    __table_args__ = (
        UniqueConstraint("job_id", "row_index"),
        # Serves "pending certificates of job X" and the per-status counts.
        Index("ix_certificates_job_id_status", "job_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("certificate_jobs.id", ondelete="CASCADE"))
    row_index: Mapped[int]  # position of the recipient in the submitted list (0 = first)
    # Raw values are kept even for INVALID rows so the client can see which row was rejected.
    recipient_name: Mapped[str | None] = mapped_column(String(255))
    recipient_email: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[CertificateStatus] = mapped_column(Enum(CertificateStatus, native_enum=False, length=32))
    # Why the certificate is INVALID or FAILED: a code from app/core/errors.py plus a readable message.
    error_code: Mapped[ErrorCode | None] = mapped_column(Enum(ErrorCode, native_enum=False, length=40))
    error_message: Mapped[str | None] = mapped_column(Text)
    file_path: Mapped[str | None] = mapped_column(String(500))  # relative to STORAGE_DIR
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    job: Mapped["CertificateJob"] = relationship(back_populates="certificates")

    def mark_generated(self, file_path: str) -> None:
        self.status = CertificateStatus.GENERATED
        self.file_path = file_path
        self.generated_at = func.now()
        self.error_code = None
        self.error_message = None

    def mark_failed(self, code: ErrorCode, message: str) -> None:
        self.status = CertificateStatus.FAILED
        self.error_code = code
        self.error_message = message[:MAX_ERROR_MESSAGE_LENGTH]
