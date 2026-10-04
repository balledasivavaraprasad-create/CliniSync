from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import structlog

from app.config import settings
from app.api.errors import (
    ClinSyncError,
    clinsync_error_handler,
    validation_error_handler,
    http_error_handler,
    uncaught_error_handler,
)
from app.utils.ids import request_id as generate_request_id
from app.api.routes import health, patients, documents

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup checks (Section 5)
    if settings.APP_ENV != "development":
        if not settings.GEMINI_API_KEY or not settings.GROQ_API_KEY:
            raise RuntimeError("CRITICAL: GEMINI_API_KEY and GROQ_API_KEY must be provided in non-development mode.")
        if not settings.VALIDATION_ENABLED:
            raise RuntimeError("CRITICAL: VALIDATION_ENABLED cannot be false in non-development environments.")

    # Storage writable check
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    test_probe = settings.storage_path / ".probe"
    try:
        test_probe.write_text("probe")
        test_probe.unlink(missing_ok=True)
    except Exception as e:
        raise RuntimeError(f"Storage path {settings.storage_path} is not writable: {e}")

    # Log provider configuration safely (never print keys)
    logger.info(
        "ClinSync backend initialized",
        app_name=settings.APP_NAME,
        env=settings.APP_ENV,
        gemini_configured=bool(settings.GEMINI_API_KEY),
        groq_configured=bool(settings.GROQ_API_KEY),
        validation_enabled=settings.VALIDATION_ENABLED,
    )

    yield

    logger.info("ClinSync backend shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title="ClinSync API",
        description="ClinSync — AI-powered longitudinal clinical intelligence platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or generate_request_id()
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

    # Exception Handlers
    app.add_exception_handler(ClinSyncError, clinsync_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, uncaught_error_handler)

    # Routes
    from app.api.routes import health, patients, documents, facts, timeline, medications, investigations, issues, briefs, consultations, memory, voice, audit, specialties
    app.include_router(health.router)
    app.include_router(health.router, prefix=settings.API_PREFIX)
    app.include_router(patients.router, prefix=settings.API_PREFIX)
    app.include_router(documents.router, prefix=settings.API_PREFIX)
    app.include_router(facts.router, prefix=settings.API_PREFIX)
    app.include_router(timeline.router, prefix=settings.API_PREFIX)
    app.include_router(medications.router, prefix=settings.API_PREFIX)
    app.include_router(investigations.router, prefix=settings.API_PREFIX)
    app.include_router(issues.router, prefix=settings.API_PREFIX)
    app.include_router(briefs.router, prefix=settings.API_PREFIX)
    app.include_router(consultations.router, prefix=settings.API_PREFIX)
    app.include_router(memory.router, prefix=settings.API_PREFIX)
    app.include_router(voice.router, prefix=settings.API_PREFIX)
    app.include_router(audit.router, prefix=settings.API_PREFIX)
    app.include_router(specialties.router, prefix=settings.API_PREFIX)

    return app


app = create_app()
