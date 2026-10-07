"""Every error the service can report: one list of error codes and the exceptions that carry them.

- API errors are raised as AppError subclasses from anywhere (services, dependencies) and turned into the
  same JSON response in one place: app/core/error_handlers.py. Controllers never build error responses.
- Problems with individual certificates are not exceptions: they are stored on the certificate row
  (error_code + error_message) using codes from the same ErrorCode list.
"""
from enum import StrEnum


class ErrorCode(StrEnum):
    # The request itself
    VALIDATION_ERROR = "VALIDATION_ERROR"  # malformed request body / query / path
    NOT_FOUND = "NOT_FOUND"  # unknown URL
    METHOD_NOT_ALLOWED = "METHOD_NOT_ALLOWED"
    HTTP_ERROR = "HTTP_ERROR"  # any other HTTP error raised by the framework
    INTERNAL_ERROR = "INTERNAL_ERROR"  # unexpected server error

    # Jobs and certificates
    JOB_NOT_FOUND = "JOB_NOT_FOUND"
    CERTIFICATE_NOT_FOUND = "CERTIFICATE_NOT_FOUND"
    CERTIFICATE_NOT_READY = "CERTIFICATE_NOT_READY"  # not GENERATED (yet), so nothing to download
    CERTIFICATE_FILE_MISSING = "CERTIFICATE_FILE_MISSING"  # GENERATED, but the PDF is gone from storage

    # Outcome of an individual certificate (stored in certificates.error_code)
    INVALID_RECIPIENT = "INVALID_RECIPIENT"  # recipient row failed validation
    DUPLICATE_EMAIL = "DUPLICATE_EMAIL"  # same email as an earlier row of the job
    GENERATION_FAILED = "GENERATION_FAILED"  # rendering the PDF raised an error
    JOB_ABORTED = "JOB_ABORTED"  # the job stopped before this certificate was generated


class AppError(Exception):
    """An error that reaches the client as {"error": {"code", "message", "details"}} with status_code."""

    status_code: int = 500
    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(self, message: str, *, details: list[dict[str, str]] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    """The request is valid, but the resource isn't in a state that allows it (e.g. not generated yet)."""

    status_code = 409


class JobNotFound(NotFoundError):
    code = ErrorCode.JOB_NOT_FOUND

    def __init__(self, job_id: object) -> None:
        super().__init__(f"Job {job_id} not found")


class CertificateNotFound(NotFoundError):
    code = ErrorCode.CERTIFICATE_NOT_FOUND

    def __init__(self, certificate_id: object) -> None:
        super().__init__(f"Certificate {certificate_id} not found")


class CertificateNotReady(ConflictError):
    code = ErrorCode.CERTIFICATE_NOT_READY

    def __init__(self, certificate_id: object, status: str) -> None:
        super().__init__(f"Certificate {certificate_id} is {status}; only GENERATED certificates can be downloaded")


class CertificateFileMissing(NotFoundError):
    code = ErrorCode.CERTIFICATE_FILE_MISSING

    def __init__(self, certificate_id: object) -> None:
        super().__init__(f"The PDF of certificate {certificate_id} is missing from storage")
