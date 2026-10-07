"""HTTP endpoints for certificate generation jobs."""
import uuid

from fastapi import APIRouter, status

from app.core.database import DbSession
from app.schemas.error import error_responses
from app.schemas.job import JobCreate, JobCreatedResponse, JobProgress, JobStatusResponse
from app.services import certificate_service, job_service

router = APIRouter(prefix="/jobs", tags=["jobs"], responses=error_responses(422, 500))


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobCreate, db: DbSession) -> JobCreatedResponse:
    """Submit certificates for many recipients at once.

    Returns immediately with the job id; a worker generates the certificates in the background.
    """
    job = job_service.create_job(db, payload)
    return JobCreatedResponse(
        job_id=job.id,
        status=job.status,
        status_url=f"/jobs/{job.id}",
        progress=JobProgress.from_counts(certificate_service.count_by_status(db, job.id)),
    )


@router.get("/{job_id}", responses=error_responses(404))
def get_job_status(job_id: uuid.UUID, db: DbSession) -> JobStatusResponse:
    """Job status, progress counts and the result for every recipient."""
    job = job_service.get_job(db, job_id)
    return JobStatusResponse(
        job=job,
        progress=JobProgress.from_counts(certificate_service.count_by_status(db, job_id)),
        certificates=job.certificates,
    )
