"""Per-recipient schemas: the rules one recipient row must pass, and a certificate as the client sees it."""
import unicodedata
import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, StringConstraints, computed_field
from pydantic_core import PydanticCustomError

from app.core.errors import ErrorCode
from app.models import CertificateStatus


def ensure_printable(value: str) -> str:
    """Reject text the certificate can't print.

    Certificates use the PDF standard fonts, which only cover Windows-1252 (Latin) characters. Anything
    else would silently come out as black boxes, so it is rejected up front instead.
    """
    try:
        value.encode("cp1252")
    except UnicodeEncodeError:
        raise PydanticCustomError(
            "unsupported_characters", "contains characters the certificate font cannot render"
        ) from None
    if any(unicodedata.category(char) == "Cc" for char in value):
        raise PydanticCustomError("control_characters", "contains control characters")
    return value


# Whitespace is stripped first (str_strip_whitespace on the model), then the length and printability checks run.
RecipientName = Annotated[str, StringConstraints(min_length=1, max_length=100), AfterValidator(ensure_printable)]


class RecipientIn(BaseModel):
    """Rules for one recipient row.

    Each row is validated on its own (see job_service.create_job): a row that breaks these rules is stored
    as INVALID with the reason, instead of rejecting the whole request.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: RecipientName
    email: EmailStr


class CertificateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    row_index: int
    recipient_name: str | None
    recipient_email: str | None
    status: CertificateStatus
    error_code: ErrorCode | None
    error_message: str | None

    @computed_field
    @property
    def download_url(self) -> str | None:
        if self.status == CertificateStatus.GENERATED:
            return f"/certificates/{self.id}/download"
        return None
