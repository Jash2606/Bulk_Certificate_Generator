"""The JSON shape of every error response: {"error": {"code": ..., "message": ..., "details": [...]}}."""
from pydantic import BaseModel

from app.core.errors import ErrorCode


class ErrorDetail(BaseModel):
    field: str | None = None  # where the problem is, e.g. "body.recipients" or "query.limit"
    message: str
    type: str | None = None  # machine-readable reason, e.g. "missing", "string_too_short"


class ErrorBody(BaseModel):
    code: ErrorCode
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_responses(*status_codes: int) -> dict[int | str, dict]:
    """OpenAPI documentation for the error statuses an endpoint (or router) can return."""
    return {status_code: {"model": ErrorResponse} for status_code in status_codes}
