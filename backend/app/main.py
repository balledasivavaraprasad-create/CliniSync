from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import structlog

from app.config import settings
from app.api.errors import (
    ClinSyncError,
    clinsync_error_handler,
    validation_error_handler,
    http_error_handler,
    uncaught_error_handler,
)
from app.db.database import ensure_schema
from app.utils.ids import request_id as generate_request_id
from app.utils.logging_sanitizer import phi_sanitizer_processor
from app.api.routes import health, patients, documents

# Global structlog configuration with PHI & sensitive data sanitization
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        phi_sanitizer_processor,
        structlog.dev.ConsoleRenderer() if settings.APP_ENV == "development" else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=False,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup checks (Production & Non-Development Hardening)
    if settings.APP_ENV != "development":
        if not settings.GEMINI_API_KEY or not settings.GROQ_API_KEY:
            raise RuntimeError("CRITICAL: GEMINI_API_KEY and GROQ_API_KEY must be provided in non-development mode.")
        if not settings.VALIDATION_ENABLED:
            raise RuntimeError("CRITICAL: VALIDATION_ENABLED cannot be false in non-development environments.")
        if (
            settings.JWT_SECRET_KEY in ("clinsync-default-insecure-dev-secret-key-change-me", "secret", "changeme", "default-secret")
            or len(settings.JWT_SECRET_KEY) < 32
        ):
            raise RuntimeError("CRITICAL: JWT_SECRET_KEY must be configured with a secure key (>=32 characters) in non-development mode.")
        if settings.AUTH_DEMO_FALLBACK_ENABLED:
            raise RuntimeError("CRITICAL: AUTH_DEMO_FALLBACK_ENABLED cannot be true in non-development mode.")
        if settings.APP_ENV == "production":
            if settings.DATABASE_URL.startswith("sqlite"):
                raise RuntimeError("CRITICAL: Production environment requires a persistent relational database (e.g., PostgreSQL). SQLite is prohibited in production.")
            if settings.CORS_ORIGINS == "*":
                raise RuntimeError("CRITICAL: Wildcard CORS ('*') is prohibited in production.")

    # Storage writable check
    settings.storage_path.mkdir(parents=True, exist_ok=True)
    test_probe = settings.storage_path / ".probe"
    try:
        test_probe.write_text("probe")
        test_probe.unlink(missing_ok=True)
    except Exception as e:
        raise RuntimeError(f"Storage path {settings.storage_path} is not writable: {e}")

    # Schema: Managed through Alembic migrations (applied cleanly on boot)
    schema_ok = ensure_schema()
    if not schema_ok:
        logger.error(
            "database_schema_incomplete",
            hint="run `alembic upgrade head` or inspect migration status",
        )
    else:
        logger.info("database_schema_ready")
        try:
            from app.services.document_service import DocumentService
            from app.db.database import get_db_context
            with get_db_context() as db:
                stale_recovered = DocumentService.mark_stale_jobs_as_failed(db, max_age_seconds=300)
                if stale_recovered:
                    logger.info("stale_jobs_recovered_on_startup", count=len(stale_recovered), documents=stale_recovered)
        except Exception as exc:
            logger.warning("stale_job_recovery_on_startup_skipped", error=str(exc))

    # Log provider configuration safely (never print keys)
    logger.info(
        "ClinSync backend initialized",
        app_name=settings.APP_NAME,
        env=settings.APP_ENV,
        gemini_configured=bool(settings.GEMINI_API_KEY),
        groq_configured=bool(settings.GROQ_API_KEY),
        validation_enabled=settings.VALIDATION_ENABLED,
        schema_ready=schema_ok,
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

    # There used to be a middleware here that collapsed a doubled
    # `/api/v1/api/v1` prefix. It existed because the Flutter client appended
    # `/api/v1` to its base URL *and* carried it in every path, so every request
    # went out doubled — and the rewrite hid that from `flutter analyze`, from
    # the tests, and from anyone reading the network tab. The client is fixed and
    # pinned by tests, so the rewrite is gone: a misconfigured base URL should
    # produce a 404 that is obvious, not a silent success.

    # CORS
    cors_origins = settings.cors_origins_list
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=("*" not in cors_origins),
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID and Observability middleware
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        import time
        start_time = time.time()
        req_id = request.headers.get("X-Request-ID") or generate_request_id()
        request.state.request_id = req_id

        user_id = getattr(request.state, "user_id", None)
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            duration_ms = (time.time() - start_time) * 1000
            # A failure inside `call_next` never reaches the exception handlers,
            # so it is logged here with the request id before re-raising into
            # Starlette. Without this, an unhandled error is invisible in the
            # logs and the client only sees a bare 500.
            logger.exception(
                "unhandled_request_error",
                request_id=req_id,
                path=request.url.path,
                method=request.method,
                duration_ms=round(duration_ms, 2),
                status=500,
            )
            raise

        duration_ms = (time.time() - start_time) * 1000
        response.headers["X-Request-ID"] = req_id

        # Security & PHI hardening headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        if request.url.path.startswith(settings.API_PREFIX):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"

        # Observability: structured HTTP access log
        # Exclude high-frequency health probes from spamming logs unless degraded
        if request.url.path not in ("/health", "/api/v1/health"):
            logger.info(
                "http_request_finished",
                request_id=req_id,
                method=request.method,
                endpoint=request.url.path,
                status=status_code,
                duration_ms=round(duration_ms, 2),
                user_id=getattr(request.state, "user_id", None),
            )

        return response

    # Exception Handlers
    app.add_exception_handler(ClinSyncError, clinsync_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, uncaught_error_handler)

    # Routes
    from app.api.deps import get_current_user
    from app.api.routes import health, auth, patients, documents, facts, timeline, medications, investigations, issues, briefs, consultations, memory, voice, audit, specialties, mongo

    # Public routes
    app.include_router(health.router)
    app.include_router(health.router, prefix=settings.API_PREFIX)
    app.include_router(auth.router)
    app.include_router(auth.router, prefix=settings.API_PREFIX)
    app.include_router(specialties.router, prefix=settings.API_PREFIX)
    app.include_router(mongo.router, prefix=settings.API_PREFIX)

    # Protected clinical routes
    auth_deps = [Depends(get_current_user)]
    app.include_router(patients.router, prefix=settings.API_PREFIX, dependencies=auth_deps)
    app.include_router(documents.router, prefix=settings.API_PREFIX, dependencies=auth_deps)
    app.include_router(facts.router, prefix=settings.API_PREFIX, dependencies=auth_deps)
    app.include_router(timeline.router, prefix=settings.API_PREFIX, dependencies=auth_deps)
    app.include_router(medications.router, prefix=settings.API_PREFIX, dependencies=auth_deps)
    app.include_router(investigations.router, prefix=settings.API_PREFIX, dependencies=auth_deps)
    app.include_router(issues.router, prefix=settings.API_PREFIX, dependencies=auth_deps)
    app.include_router(briefs.router, prefix=settings.API_PREFIX, dependencies=auth_deps)
    app.include_router(consultations.router, prefix=settings.API_PREFIX, dependencies=auth_deps)
    app.include_router(memory.router, prefix=settings.API_PREFIX, dependencies=auth_deps)
    app.include_router(voice.router, prefix=settings.API_PREFIX, dependencies=auth_deps)
    app.include_router(audit.router, prefix=settings.API_PREFIX, dependencies=auth_deps)

    return app


app = create_app()
