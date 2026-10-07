"""Application settings, loaded by pydantic-settings from environment variables and an optional .env file.

Each setting can be overridden with an environment variable of the same name in upper case, e.g.
DATABASE_URL. The defaults match docker-compose.yml, so local development needs no configuration.
"""
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://certgen:certgen@localhost:5432/certgen"

    # Generated PDFs are written here by workers and served from here by the API.
    storage_dir: Path = BASE_DIR / "storage" / "certificates"

    max_recipients_per_job: int = Field(default=1000, ge=1)

    # How long an idle worker waits before checking the queue again.
    worker_poll_interval_seconds: float = Field(default=1.0, gt=0)

    # A PROCESSING job whose worker hasn't sent a heartbeat for this long is treated as abandoned
    # (worker crashed or was killed) and becomes claimable again.
    job_stale_after_seconds: int = Field(default=300, gt=0)


settings = Settings()
