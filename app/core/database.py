"""Database engine, session factory, the declarative base, and the per-request session dependency."""
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# pool_pre_ping replaces connections that died (e.g. the database restarted) instead of failing a request.
engine = create_engine(settings.database_url, pool_pre_ping=True)

# expire_on_commit=False: objects stay readable after commit without reloading them from the database.
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, always closed afterwards."""
    with SessionLocal() as db:
        yield db


DbSession = Annotated[Session, Depends(get_db)]


def init_db() -> None:
    """Create any missing tables. Called when the API and the workers start.

    Kept simple on purpose: there are no migrations, so after changing a model, recreate the database
    (`docker compose down -v`, then `docker compose up -d db`).
    """
    import app.models  # noqa: F401 - registers every model on Base.metadata

    Base.metadata.create_all(bind=engine)
