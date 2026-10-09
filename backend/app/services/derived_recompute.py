import structlog
from app.db.database import get_db_context
from app.services.medication_service import medication_service
from app.services.contradiction_service import contradiction_service
from app.services.missing_info_service import missing_info_service

logger = structlog.get_logger(__name__)

async def run_patient_recompute(patient_id: str) -> None:
    """
    Deterministically recomputes patient clinical state:
    1. Medication reconciliation (conflict detection)
    2. Contradiction engine (diagnosis, dates, status)
    3. Missing information engine (checklist prompts)
    """
    logger.info("running_patient_recompute", patient_id=patient_id)
    with get_db_context() as db:
        try:
            medication_service.reconcile(db, patient_id)
            contradiction_service.recompute(db, patient_id)
            missing_info_service.recompute(db, patient_id)
        except Exception as e:
            from app.utils.logging_sanitizer import sanitize_error_message
            logger.error("error_in_patient_recompute", patient_id=patient_id, error=sanitize_error_message(e))
