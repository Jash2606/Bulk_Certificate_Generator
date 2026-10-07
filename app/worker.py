"""Worker process. Run with: python -m app.worker

Polls the certificate_jobs table, claims one job at a time and generates its certificates. Start as many
workers as you like: FOR UPDATE SKIP LOCKED (see queue_service.claim_next_job) gives each job to exactly one.
"""
import logging
import signal
import time

from app.core.config import settings
from app.core.database import SessionLocal, init_db
from app.services import queue_service

logger = logging.getLogger("app.worker")

_stop_requested = False


def run_once() -> bool:
    """Claim and process one job. Returns False if the queue was empty."""
    with SessionLocal() as db:
        job_id = queue_service.claim_next_job(db)
        if job_id is None:
            return False
        logger.info("Claimed job %s", job_id)
        queue_service.process_job(db, job_id)
        logger.info("Finished job %s", job_id)
        return True


def _request_stop(signum: int, frame: object) -> None:
    global _stop_requested
    if _stop_requested:  # second Ctrl+C: quit now; the job is picked up again once its heartbeat goes stale
        raise KeyboardInterrupt
    _stop_requested = True
    logger.info("Stopping after the current job (press Ctrl+C again to quit immediately)")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [worker pid=%(process)d] %(message)s")
    signal.signal(signal.SIGINT, _request_stop)
    signal.signal(signal.SIGTERM, _request_stop)
    init_db()
    logger.info("Worker started, polling every %ss", settings.worker_poll_interval_seconds)
    try:
        while not _stop_requested:
            try:
                found_job = run_once()
            except Exception:  # e.g. database unreachable: log, wait, try again
                logger.exception("Worker loop error")
                found_job = False
            if not found_job:
                time.sleep(settings.worker_poll_interval_seconds)
    except KeyboardInterrupt:
        logger.warning("Worker interrupted")
        return
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
