import os

import structlog
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db_session, get_request_id
from app.config import settings
from app.db.database import db_health

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(request_id: str = Depends(get_request_id)):
    """Liveness. Deliberately does not touch the database.

    A liveness probe that touches the DB reports the process as unhealthy when
    the database is merely slow or briefly locked, which restarts a perfectly
    good server. Reachability is `/health/deep`'s job.
    """
    return {
        "success": True,
        "data": {
            "status": "healthy",
            "app": settings.APP_NAME,
            "env": settings.APP_ENV,
        },
        "meta": {
            "request_id": request_id,
            "source": "system",
        },
    }


@router.get("/health/deep")
def deep_health_check(
    response: Response,
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    """Readiness: database, schema, storage and provider configuration.

    Returns 503 when a dependency the app needs is unavailable, so an orchestrator
    can act on the status code rather than parsing the body. The body is still the
    same `{success, data, meta}` envelope, which is what the Flutter client parses.
    """
    db_state = db_health()

    # Legacy connectivity probe kept for the case where a session-level failure
    # (rather than an engine-level one) is what is wrong.
    db_ok = db_state["connected"]
    if not db_ok:
        try:
            db.execute(text("SELECT 1"))
            db_ok = True
            db_state["connected"] = True
        except Exception as exc:
            db_state["error"] = str(exc)

    storage_ok = False
    storage_error = None
    test_file = settings.storage_path / ".health_test"
    try:
        test_file.write_text("ok")
        storage_ok = test_file.read_text() == "ok"
    except Exception as exc:
        storage_error = str(exc)
    finally:
        try:
            test_file.unlink(missing_ok=True)
        except Exception:
            pass

    gemini_configured = bool(settings.GEMINI_API_KEY)
    groq_configured = bool(settings.GROQ_API_KEY)
    schema_ok = db_state["schema_complete"]

    # A missing schema means every clinical endpoint will 500, so it is treated
    # as unhealthy rather than degraded.
    healthy = db_ok and schema_ok and storage_ok
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        logger.warning(
            "deep_health_degraded",
            db_ok=db_ok,
            schema_ok=schema_ok,
            storage_ok=storage_ok,
        )

    return {
        "success": True,
        "data": {
            "app": settings.APP_NAME,
            "status": "operational" if healthy else "degraded",
            "database": "connected" if db_ok else "unreachable",
            "schema_complete": schema_ok,
            "missing_tables": db_state["missing_tables"],
            "storage_writable": storage_ok,
            "validation_enabled": settings.VALIDATION_ENABLED,
            "providers": {
                "gemini": "configured" if gemini_configured else "missing_key",
                "groq": "configured" if groq_configured else "missing_key",
            },
            "llm_available": gemini_configured or groq_configured,
        },
        "meta": {
            "request_id": request_id,
            "source": "system",
        },
    }


@router.get("/metrics")
@router.get("/metrics/ai")
def get_ai_and_pipeline_metrics(request_id: str = Depends(get_request_id)):
    """Returns AI and document pipeline observability metrics."""
    from app.services.metrics_service import metrics_service
    summary = metrics_service.get_summary()
    return {
        "success": True,
        "data": summary,
        "meta": {
            "request_id": request_id,
            "source": "metrics_service",
        },
    }
