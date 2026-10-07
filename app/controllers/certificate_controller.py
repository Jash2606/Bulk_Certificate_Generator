"""HTTP endpoints for retrieving generated certificates."""
import uuid

from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.core.database import DbSession
from app.schemas.error import error_responses
from app.services import certificate_service

router = APIRouter(prefix="/certificates", tags=["certificates"], responses=error_responses(422, 500))


@router.get(
    "/{certificate_id}/download",
    response_class=FileResponse,
    responses={200: {"content": {"application/pdf": {}}, "description": "The certificate PDF"}, **error_responses(404, 409)},
)
def download_certificate(certificate_id: uuid.UUID, db: DbSession) -> FileResponse:
    """Download one generated certificate as a PDF."""
    certificate, path = certificate_service.get_downloadable_file(db, certificate_id)
    return FileResponse(path, media_type="application/pdf", filename=f"certificate-{certificate.id}.pdf")
