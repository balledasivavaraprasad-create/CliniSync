from typing import Any, Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException


class ClinSyncError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("NOT_FOUND", message, status.HTTP_404_NOT_FOUND, details)


class DuplicateDocumentError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("DUPLICATE_DOCUMENT", message, status.HTTP_409_CONFLICT, details)


class UnsupportedFileTypeError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("UNSUPPORTED_FILE_TYPE", message, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, details)


class FileTooLargeError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("FILE_TOO_LARGE", message, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, details)


class DocumentProcessingError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("DOCUMENT_PROCESSING_FAILED", message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class OCRFailedError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("OCR_FAILED", message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class ExtractionFailedError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("EXTRACTION_FAILED", message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class LLMUnavailableError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("LLM_UNAVAILABLE", message, status.HTTP_503_SERVICE_UNAVAILABLE, details)


# Aliases for convenience
OCRFailed = OCRFailedError
ExtractionFailed = ExtractionFailedError
DocumentProcessingFailed = DocumentProcessingError
LLMUnavailable = LLMUnavailableError


class STTFailedError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("STT_FAILED", message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class Gate1BlockedError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("GATE1_BLOCKED", message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class Gate2BlockedError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("GATE2_BLOCKED", message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class ConsultationNotApprovableError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("CONSULTATION_NOT_APPROVABLE", message, status.HTTP_422_UNPROCESSABLE_ENTITY, details)


class InvalidStateTransitionError(ClinSyncError):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__("INVALID_STATE_TRANSITION", message, status.HTTP_409_CONFLICT, details)


def make_error_response(
    request: Request,
    code: str,
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "req_unknown")
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
            "meta": {
                "request_id": request_id,
            },
        },
    )


async def clinsync_error_handler(request: Request, exc: ClinSyncError) -> JSONResponse:
    return make_error_response(
        request,
        code=exc.code,
        message=exc.message,
        status_code=exc.status_code,
        details=exc.details,
    )


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return make_error_response(
        request,
        code="VALIDATION_ERROR",
        message="Request payload validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        details={"errors": exc.errors()},
    )


async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
    return make_error_response(
        request,
        code=code,
        message=str(exc.detail),
        status_code=exc.status_code,
    )


async def uncaught_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return make_error_response(
        request,
        code="INTERNAL_ERROR",
        message="An unexpected server error occurred",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
