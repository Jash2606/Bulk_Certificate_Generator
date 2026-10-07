"""API process. Run with: uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.controllers import certificate_controller, job_controller
from app.core.database import init_db
from app.core.error_handlers import register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Bulk Certificate Generator",
        description=(
            "Submit one request for many recipients, follow the job's progress, and download the certificates. "
            "Generation runs in a separate worker process (`python -m app.worker`)."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    register_error_handlers(app)
    app.include_router(job_controller.router)
    app.include_router(certificate_controller.router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
