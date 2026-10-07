"""Worker-side logic: claim the next job from the PostgreSQL table queue and generate its certificates."""
import logging
import uuid
from datetime import timedelta
from pathlib import PurePosixPath

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ErrorCode
from app.models import Certificate, CertificateJob, CertificateStatus, JobStatus
from app.services import certificate_renderer
from app.services.certificate_service import count_by_status

logger = logging.getLogger(__name__)

MAX_ERROR_LENGTH = 500


def claim_next_job(db: Session) -> uuid.UUID | None:
    """Claim the oldest job that needs a worker and return its id, or None if there is nothing to do.

    FOR UPDATE SKIP LOCKED locks the chosen row, and any other worker running the same query at the same
    moment skips that row instead of waiting for it, so two workers never claim the same job. Once the
    job is marked PROCESSING and committed, the lock is released and the status keeps other workers away.

    A PROCESSING job whose heartbeat is older than JOB_STALE_AFTER_SECONDS lost its worker (crash, kill),
    so it is claimable again.
    """
    abandoned = and_(
        CertificateJob.status == JobStatus.PROCESSING,
        CertificateJob.heartbeat_at < func.now() - timedelta(seconds=settings.job_stale_after_seconds),
    )
    job = db.scalars(
        select(CertificateJob)
        .where(or_(CertificateJob.status == JobStatus.PENDING, abandoned))
        .order_by(CertificateJob.created_at)
        .limit(1)
        .with_for_update(skip_locked=True)
    ).first()
    if job is None:
        db.rollback()  # end the transaction instead of leaving it open
        return None

    job.status = JobStatus.PROCESSING
    job.attempts += 1
    if job.started_at is None:
        job.started_at = func.now()
    job.heartbeat_at = func.now()
    db.commit()
    return job.id


def process_job(db: Session, job_id: uuid.UUID) -> None:
    """Generate every PENDING certificate of a claimed job, then record the job's final status.

    Each certificate is committed on its own, so progress is visible while the job runs and one failed
    certificate never undoes or blocks the others. Only PENDING rows are processed, which makes it safe
    to run again on a job that was interrupted halfway.
    """
    job = db.get(CertificateJob, job_id)
    if job is None:
        return
    try:
        pending = db.scalars(
            select(Certificate)
            .where(Certificate.job_id == job_id, Certificate.status == CertificateStatus.PENDING)
            .order_by(Certificate.row_index)
        ).all()
        for certificate in pending:
            _generate(db, job, certificate)
        _finish(db, job)
    except Exception as exc:
        logger.exception("Job %s aborted", job_id)
        db.rollback()
        _abort(db, job, exc)


def _generate(db: Session, job: CertificateJob, certificate: Certificate) -> None:
    """Render one certificate and commit its outcome together with the job's heartbeat."""
    relative_path = PurePosixPath(str(job.id), f"{certificate.id}.pdf")
    try:
        # Rendering happens before any change to the session, so a failure here leaves nothing to roll back.
        certificate_renderer.render_certificate(
            certificate_id=certificate.id,
            recipient_name=certificate.recipient_name,
            course_name=job.course_name,
            issue_date=job.issue_date,
            issued_by=job.issued_by,
            output_path=settings.storage_dir / relative_path,
        )
    except Exception as exc:
        logger.exception("Certificate %s (row %s of job %s) failed", certificate.id, certificate.row_index, job.id)
        certificate.mark_failed(ErrorCode.GENERATION_FAILED, f"Generation failed: {exc}")
    else:
        certificate.mark_generated(str(relative_path))
    job.heartbeat_at = func.now()
    db.commit()


def _finish(db: Session, job: CertificateJob) -> None:
    counts = count_by_status(db, job.id)
    generated = counts.get(CertificateStatus.GENERATED, 0)
    if generated == sum(counts.values()):
        job.status = JobStatus.COMPLETED
    elif generated == 0:
        job.status = JobStatus.FAILED
    else:
        job.status = JobStatus.COMPLETED_WITH_ERRORS
    job.completed_at = func.now()
    db.commit()


def _abort(db: Session, job: CertificateJob, exc: Exception) -> None:
    """Something outside a single certificate broke: fail the job and its unprocessed certificates."""
    db.execute(
        update(Certificate)
        .where(Certificate.job_id == job.id, Certificate.status == CertificateStatus.PENDING)
        .values(
            status=CertificateStatus.FAILED,
            error_code=ErrorCode.JOB_ABORTED,
            error_message="Job aborted before this certificate was generated",
        )
    )
    job.status = JobStatus.FAILED
    job.error_message = f"{type(exc).__name__}: {exc}"[:MAX_ERROR_LENGTH]
    job.completed_at = func.now()
    db.commit()
