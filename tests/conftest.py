"""Shared test setup: a dedicated PostgreSQL database (certgen_test) and a throwaway storage folder.

The environment variables are set BEFORE anything from `app` is imported, because the settings are read
at import time. Requires the database from docker-compose.yml: `docker compose up -d db`.
"""
import os
import shutil
import tempfile

import pytest

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql+psycopg://certgen:certgen@localhost:5432/certgen_test"
)
TEST_STORAGE_DIR = tempfile.mkdtemp(prefix="certgen-test-storage-")
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["STORAGE_DIR"] = TEST_STORAGE_DIR

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from app import worker  # noqa: E402
from app.core.database import engine, init_db  # noqa: E402
from app.main import app  # noqa: E402


def _create_test_database_if_missing() -> None:
    url = make_url(TEST_DATABASE_URL)
    # The suite wipes this database, so never let it loose on one that isn't meant for tests.
    if not (url.database or "").endswith("_test"):
        pytest.exit(f"Refusing to run: the test database name must end with '_test' (got {url.database!r})")
    assert engine.url.database == url.database, "the app engine must point at the test database"

    admin_engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": url.database})
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{url.database}"'))
    except OperationalError as exc:
        pytest.exit(
            f"PostgreSQL is not reachable at {url.render_as_string(hide_password=True)}.\n"
            f"Start it with `docker compose up -d db`.\n{exc}"
        )
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def database():
    _create_test_database_if_missing()
    # Start from an empty schema every run, so the tables always match the current models.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    init_db()
    yield
    engine.dispose()
    shutil.rmtree(TEST_STORAGE_DIR, ignore_errors=True)


@pytest.fixture(autouse=True)
def empty_tables(database):
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE certificates, certificate_jobs CASCADE"))


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def run_worker():
    """Process every queued job synchronously, the same way `python -m app.worker` does. Returns the job count."""

    def _run() -> int:
        jobs_processed = 0
        while worker.run_once():
            jobs_processed += 1
        return jobs_processed

    return _run
