"""The worker: claiming jobs from the PostgreSQL queue, generating certificates, and failure handling."""
import uuid
from datetime import timedelta

from sqlalchemy import func, select, update

from app.core.database import SessionLocal
from app.models import Certificate, CertificateJob, CertificateStatus
from app.services import certificate_renderer
from app.services.queue_service import claim_next_job
from tests.helpers import job_payload, pdf_path, recipients


def create_job(client, *names: str) -> uuid.UUID:
    return uuid.UUID(client.post("/jobs", json=job_payload(recipients(*names))).json()["job_id"])


# --- Certificate generation -----------------------------------------------------------------------------------


def test_worker_generates_a_pdf_for_every_valid_recipient(client, run_worker):
    job_id = create_job(client, "Asha Rao", "Ben Okafor", "Chen Wei")

    assert run_worker() == 1

    status = client.get(f"/jobs/{job_id}").json()
    assert status["job"]["status"] == "COMPLETED"
    for certificate in status["certificates"]:
        assert certificate["status"] == "GENERATED"
        assert certificate["download_url"] == f"/certificates/{certificate['id']}/download"
        assert pdf_path(str(job_id), certificate["id"]).read_bytes().startswith(b"%PDF")


# --- Handling an individual certificate failure -------------------------------------------------------------------


def test_one_failing_certificate_does_not_stop_the_others(client, run_worker, monkeypatch):
    real_render = certificate_renderer.render_certificate

    def render_or_fail(**kwargs):
        if kwargs["recipient_name"] == "Broken Printer":
            raise RuntimeError("printer on fire")
        return real_render(**kwargs)

    monkeypatch.setattr(certificate_renderer, "render_certificate", render_or_fail)
    job_id = create_job(client, "Asha Rao", "Broken Printer", "Chen Wei")

    run_worker()

    status = client.get(f"/jobs/{job_id}").json()
    assert status["job"]["status"] == "COMPLETED_WITH_ERRORS"
    assert status["progress"]["generated"] == 2
    assert status["progress"]["failed"] == 1
    asha, broken, chen = status["certificates"]
    assert asha["status"] == chen["status"] == "GENERATED"  # including the one generated AFTER the failure
    assert broken["status"] == "FAILED"
    assert broken["error_code"] == "GENERATION_FAILED"
    assert broken["error_message"] == "Generation failed: printer on fire"
    assert broken["download_url"] is None


# --- Claiming jobs from the queue -------------------------------------------------------------------------------------


def test_jobs_are_claimed_oldest_first_and_only_once(client):
    first = create_job(client, "Asha Rao")
    second = create_job(client, "Ben Okafor")

    with SessionLocal() as db:
        assert claim_next_job(db) == first
        assert claim_next_job(db) == second
        assert claim_next_job(db) is None  # both are PROCESSING now, nothing left to claim


def test_job_locked_by_another_worker_is_skipped_not_waited_for(client):
    first = create_job(client, "Asha Rao")
    second = create_job(client, "Ben Okafor")

    with SessionLocal() as worker_a, SessionLocal() as worker_b:
        # Worker A is in the middle of claiming the oldest job: it holds the row lock, transaction still open.
        worker_a.scalars(select(CertificateJob).where(CertificateJob.id == first).with_for_update()).one()

        # Worker B doesn't block on that lock; it skips the row and takes the next job.
        assert claim_next_job(worker_b) == second

        worker_a.rollback()


def test_job_abandoned_by_a_crashed_worker_is_resumed(client, run_worker):
    job_id = create_job(client, "Asha Rao", "Ben Okafor", "Chen Wei")

    # Simulate a worker that claimed the job, generated row 0, then died 10 minutes ago.
    with SessionLocal() as db:
        assert claim_next_job(db) == job_id
        db.execute(
            update(Certificate)
            .where(Certificate.job_id == job_id, Certificate.row_index == 0)
            .values(status=CertificateStatus.GENERATED, file_path="done-by-the-crashed-worker.pdf")
        )
        db.execute(
            update(CertificateJob)
            .where(CertificateJob.id == job_id)
            .values(heartbeat_at=func.now() - timedelta(minutes=10))
        )
        db.commit()

    assert run_worker() == 1  # the stale job is claimed again

    status = client.get(f"/jobs/{job_id}").json()
    assert status["job"]["status"] == "COMPLETED"
    assert status["job"]["attempts"] == 2
    with SessionLocal() as db:
        row_0 = db.scalars(select(Certificate).where(Certificate.job_id == job_id, Certificate.row_index == 0)).one()
    assert row_0.file_path == "done-by-the-crashed-worker.pdf"  # finished work isn't redone
