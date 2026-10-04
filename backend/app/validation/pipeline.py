from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from app.schemas.common import ValidationGate, ValidationOutcome
from app.validation.gate1_memory import gate1_validator
from app.validation.gate2_output import gate2_validator

class ValidationPipeline:
    @staticmethod
    def run_gate1(
        db: Session,
        consultation_id: str,
        acknowledged_unedited: bool = False,
        approved_by: str = "doctor",
        run_judge: bool = True
    ) -> Tuple[ValidationOutcome, List[Dict[str, Any]], Optional[str]]:
        return gate1_validator.validate_approval(
            db=db,
            consultation_id=consultation_id,
            acknowledged_unedited=acknowledged_unedited,
            approved_by=approved_by,
            run_judge=run_judge
        )

    @staticmethod
    def run_gate2(
        db: Session,
        patient_id: str,
        brief_data: Dict[str, Any],
        run_judge: bool = True
    ) -> Tuple[ValidationOutcome, List[Dict[str, Any]], Optional[str]]:
        return gate2_validator.validate_brief(
            db=db,
            patient_id=patient_id,
            brief_data=brief_data,
            run_judge=run_judge
        )

validation_pipeline = ValidationPipeline()
