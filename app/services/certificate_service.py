"""Certificate-level reads: progress counts and the files clients download."""
import uuid
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import CertificateFileMissing, CertificateNotFound, CertificateNotReady
from app.models import Certificate, CertificateStatus


def count_by_status(db: Session, job_id: uuid.UUID) -> dict[CertificateStatus, int]:
    """Number of the job's certificates in each status, from one GROUP BY query."""
    rows = db.execute(
        select(Certificate.status, func.count())
        .where(Certificate.job_id == job_id)
        .group_by(Certificate.status)
    ).all()
    return {status: count for status, count in rows}


def get_downloadable_file(db: Session, certificate_id: uuid.UUID) -> tuple[Certificate, Path]:
    """The certificate and its PDF on disk, or an error explaining why it can't be downloaded."""
    certificate = db.get(Certificate, certificate_id)
    if certificate is None:
        raise CertificateNotFound(certificate_id)
    if certificate.status != CertificateStatus.GENERATED:
        raise CertificateNotReady(certificate_id, certificate.status)
    # The path comes from our own database (job id / certificate id), never from the request.
    path = settings.storage_dir / certificate.file_path
    if not path.is_file():
        raise CertificateFileMissing(certificate_id)
    return certificate, path
