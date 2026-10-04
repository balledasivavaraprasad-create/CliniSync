import os
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.api.deps import get_db_session, get_request_id
from app.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(request_id: str = Depends(get_request_id)):
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
    db: Session = Depends(get_db_session),
    request_id: str = Depends(get_request_id),
):
    # 1. DB check
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass

    # 2. Storage writable check
    storage_ok = False
    test_file = settings.storage_path / ".health_test"
    try:
        test_file.write_text("ok")
        if test_file.read_text() == "ok":
            storage_ok = True
        test_file.unlink(missing_ok=True)
    except Exception:
        pass

    # 3. Provider keys configured
    gemini_configured = bool(settings.GEMINI_API_KEY)
    groq_configured = bool(settings.GROQ_API_KEY)

    return {
        "success": True,
        "data": {
            "app": settings.APP_NAME,
            "status": "operational" if (db_ok and storage_ok) else "degraded",
            "database": "connected" if db_ok else "unreachable",
            "storage_writable": storage_ok,
            "validation_enabled": settings.VALIDATION_ENABLED,
            "providers": {
                "gemini": "configured" if gemini_configured else "missing_key",
                "groq": "configured" if groq_configured else "missing_key",
            },
        },
        "meta": {
            "request_id": request_id,
            "source": "system",
        },
    }
