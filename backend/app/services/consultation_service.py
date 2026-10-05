from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json
import structlog

from app.models.consultation import Consultation, ConsultationVersion
from app.models.clinical_memory import ClinicalMemory
from app.models.timeline_event import TimelineEvent
from app.models.patient import Patient
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.schemas.consultation import ConsultationContent, ConsultationFlag
from app.schemas.common import ConsultationOrigin, ValidationOutcome
from app.utils.ids import consultation_id, version_id, memory_id, timeline_event_id
from app.ai.gateway import llm_gateway
from app.validation.gate1_memory import gate1_validator
from app.validation.gate2_output import gate2_validator
from app.services.audit_service import audit_service
from app.api.errors import (
    Gate1BlockedError,
    InvalidStateTransitionError,
    NotFoundError,
    ValidationUnavailableError,
)

logger = structlog.get_logger(__name__)

class ConsultationService:
    def __init__(self) -> None:
        prompt_path = Path(__file__).parent.parent / "ai" / "prompts" / "draft_consultation.md"
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()

    async def create_draft(
        self,
        db: Session,
        patient_id: str,
        specialty: str = "general_medicine",
        brief_id: Optional[str] = None,
        actor: str = "ai"
    ) -> Tuple[Consultation, ConsultationVersion]:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        facts = db.query(ClinicalFact).filter(ClinicalFact.patient_id == patient_id).all()
        meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        invs = db.query(Investigation).filter(Investigation.patient_id == patient_id).all()

        # Build clean initial content directly derived from records
        # AI MUST NEVER draft assessment/plan/examination
        diag_facts = [f for f in facts if f.fact_type == "diagnosis"]
        cc = diag_facts[0].value if diag_facts else "Routine longitudinal consultation review"
        hpi = ", ".join([f.value for f in facts if f.fact_type == "symptom"][:3]) or "No active acute symptoms documented."
        past_hx = "; ".join([f.value for f in diag_facts[:4]])

        cur_meds = [{"name": m.canonical_name.title(), "dose": m.dose_text or f"{m.strength_value or ''}{m.strength_unit or ''}".strip(), "freq": m.frequency_code, "fact_id": m.fact_id} for m in meds]
        allergies = [{"text": f.value, "fact_id": f.id} for f in facts if f.fact_type == "allergy"]
        invs_reviewed = [{"test": i.test_name_canonical, "val": str(i.value_numeric or i.value_text), "unit": i.unit, "fact_id": i.fact_id} for i in invs[:8]]

        evidence_ids = [f.id for f in facts[:20]]

        content = ConsultationContent(
            chief_complaint=cc,
            history_of_present_illness=hpi,
            past_history=past_hx,
            current_medications=cur_meds,
            allergies=allergies,
            examination="",  # Empty for clinician
            investigations_reviewed=invs_reviewed,
            assessment="",   # Empty for clinician
            plan="",         # Empty for clinician
            follow_up="",    # Empty for clinician
            flags=[ConsultationFlag(text="Initial consultation draft generated from source records. Complete assessment and plan before approval.", by="ai")],
            evidence_ids=evidence_ids
        )

        cns_id = consultation_id()
        ver_id = version_id()

        cns = Consultation(
            id=cns_id,
            patient_id=patient_id,
            brief_id=brief_id,
            specialty=specialty,
            status="draft",
            current_version_id=ver_id
        )
        db.add(cns)
        db.flush()

        ver = ConsultationVersion(
            id=ver_id,
            consultation_id=cns_id,
            version_number=1,
            origin=ConsultationOrigin.ai_generated.value,
            content_json=content.model_dump_json(),
            change_summary="Initial AI-generated draft derived from patient records",
            edited_by=actor
        )
        db.add(ver)
        db.commit()
        db.refresh(cns)
        db.refresh(ver)

        return cns, ver

    def get_consultation(self, db: Session, cid: str) -> Tuple[Consultation, Optional[ConsultationVersion]]:
        cns = db.query(Consultation).filter(Consultation.id == cid).first()
        if not cns:
            raise NotFoundError(f"Consultation {cid} not found")
        ver = db.query(ConsultationVersion).filter(ConsultationVersion.id == cns.current_version_id).first()
        return cns, ver

    def list_by_patient(self, db: Session, patient_id: str) -> List[Consultation]:
        return db.query(Consultation).filter(Consultation.patient_id == patient_id).order_by(Consultation.created_at.desc()).all()


    def update_draft(
        self,
        db: Session,
        cid: str,
        content: Dict[str, Any],
        actor: str = "doctor"
    ) -> ConsultationVersion:
        cns = db.query(Consultation).filter(Consultation.id == cid).first()
        if not cns:
            raise NotFoundError(f"Consultation {cid} not found")
        if cns.status == "approved":
            raise InvalidStateTransitionError("Approved consultations are immutable and cannot be edited.")

        current_ver = db.query(ConsultationVersion).filter(ConsultationVersion.id == cns.current_version_id).first()
        if not current_ver:
            raise NotFoundError("Current consultation version not found")

        current_ver.content_json = json.dumps(content)
        current_ver.edited_by = actor
        if cns.status == "draft":
            cns.status = "in_review"

        db.commit()
        db.refresh(current_ver)
        return current_ver

    def create_version(
        self,
        db: Session,
        cid: str,
        content: Dict[str, Any],
        change_summary: Optional[str] = None,
        actor: str = "doctor"
    ) -> ConsultationVersion:
        cns = db.query(Consultation).filter(Consultation.id == cid).first()
        if not cns:
            raise NotFoundError(f"Consultation {cid} not found")
        if cns.status == "approved":
            raise InvalidStateTransitionError("Approved consultations are immutable.")

        # Determine next version number
        latest_ver = db.query(ConsultationVersion).filter(ConsultationVersion.consultation_id == cid).order_by(desc(ConsultationVersion.version_number)).first()
        next_ver_num = (latest_ver.version_number + 1) if latest_ver else 1

        new_ver_id = version_id()
        new_ver = ConsultationVersion(
            id=new_ver_id,
            consultation_id=cid,
            version_number=next_ver_num,
            origin=ConsultationOrigin.doctor_edited.value,
            content_json=json.dumps(content),
            change_summary=change_summary or f"Doctor updated draft (version {next_ver_num})",
            edited_by=actor
        )
        db.add(new_ver)
        cns.current_version_id = new_ver_id
        cns.status = "in_review"

        db.commit()
        db.refresh(new_ver)
        return new_ver

    def list_versions(self, db: Session, cid: str) -> List[Dict[str, Any]]:
        vers = db.query(ConsultationVersion).filter(ConsultationVersion.consultation_id == cid).order_by(ConsultationVersion.version_number.asc()).all()
        return [
            {
                "id": v.id,
                "version_number": v.version_number,
                "origin": v.origin,
                "change_summary": v.change_summary,
                "edited_by": v.edited_by,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "content": json.loads(v.content_json) if v.content_json else {}
            }
            for v in vers
        ]

    def preview_approve(
        self,
        db: Session,
        cid: str,
        acknowledged_unedited: bool = False
    ) -> Dict[str, Any]:
        """Dry-run Gate 1 validation without committing to clinical memory."""
        outcome, checks, rep_id = gate1_validator.validate_approval(
            db=db,
            consultation_id=cid,
            acknowledged_unedited=acknowledged_unedited,
            run_judge=True
        )
        cns, ver = self.get_consultation(db, cid)
        content = json.loads(ver.content_json) if (ver and ver.content_json) else {}

        # Proposed memory items that would be added
        proposed_items = []
        if content.get("chief_complaint"):
            proposed_items.append({"type": "diagnosis", "value": content["chief_complaint"]})
        if content.get("assessment"):
            proposed_items.append({"type": "doctor_assessment", "value": content["assessment"]})
        if content.get("plan"):
            proposed_items.append({"type": "plan_note", "value": content["plan"]})

        return {
            "outcome": outcome.value,
            "can_approve": outcome in [ValidationOutcome.pass_, ValidationOutcome.pass_with_flags],
            "checks": checks,
            "proposed_memory_items": proposed_items
        }

    def approve(
        self,
        db: Session,
        cid: str,
        acknowledged_unedited: bool = False,
        approved_by: str = "doctor"
    ) -> Dict[str, Any]:
        """
        Runs Gate 1. On pass, writes verified clinical_memory and timeline approved_note in ONE transaction.
        Enforces INV-1, INV-8, INV-9.
        """
        outcome, checks, rep_id = gate1_validator.validate_approval(
            db=db,
            consultation_id=cid,
            acknowledged_unedited=acknowledged_unedited,
            approved_by=approved_by,
            run_judge=True
        )

        if outcome == ValidationOutcome.blocked:
            blockers = [c for c in checks if c["severity"] == "block" and not c["passed"]]
            reasons = [c["detail"] for c in blockers]

            # An outage is not a content rejection. Gate 1 still fails closed, but
            # the client needs to be able to tell the difference: 503 is
            # retryable and reads to a doctor as "try again", while 422 GATE1_
            # BLOCKED says their note is not approvable. Previously both arrived
            # as 422, so a provider rate-limit looked like the doctor's fault.
            if blockers and all(c.get("code") == "VALIDATION_UNAVAILABLE" for c in blockers):
                raise ValidationUnavailableError(
                    "The automated faithfulness check is unavailable, so approval "
                    "is paused. No content was written to clinical memory. "
                    "Please try again.",
                    details={"checks": blockers},
                )
            raise Gate1BlockedError(f"Gate 1 blocked approval: {'; '.join(reasons)}")

        cns, ver = self.get_consultation(db, cid)
        content = json.loads(ver.content_json) if (ver and ver.content_json) else {}
        patient_id = cns.patient_id
        now_dt = datetime.now(timezone.utc)

        # 1. Create verified clinical_memory items (Append-only)
        created_memory = []

        # Memory candidate: Diagnoses / Chief Complaint
        if content.get("chief_complaint"):
            mem_diag = ClinicalMemory(
                id=memory_id(),
                patient_id=patient_id,
                memory_type="diagnosis",
                content_json=json.dumps({"diagnosis": content["chief_complaint"]}),
                source_consultation_id=cid,
                source_version_id=ver.id,
                verified=True,
                validation_report_id=rep_id
            )
            db.add(mem_diag)
            created_memory.append(mem_diag)

        # Memory candidate: Assessment & Plan
        if content.get("assessment"):
            mem_assess = ClinicalMemory(
                id=memory_id(),
                patient_id=patient_id,
                memory_type="assessment",
                content_json=json.dumps({"assessment": content["assessment"]}),
                source_consultation_id=cid,
                source_version_id=ver.id,
                verified=True,
                validation_report_id=rep_id
            )
            db.add(mem_assess)
            created_memory.append(mem_assess)

        if content.get("plan"):
            mem_plan = ClinicalMemory(
                id=memory_id(),
                patient_id=patient_id,
                memory_type="plan_note",
                content_json=json.dumps({"plan": content["plan"]}),
                source_consultation_id=cid,
                source_version_id=ver.id,
                verified=True,
                validation_report_id=rep_id
            )
            db.add(mem_plan)
            created_memory.append(mem_plan)

        # 2. Add approved_note to timeline
        evt = TimelineEvent(
            id=timeline_event_id(),
            patient_id=patient_id,
            event_type="approved_note",
            event_date=now_dt,
            date_precision="day",
            title=f"Approved Consultation ({cns.specialty.title()})",
            summary=f"Consultation finalized by {approved_by}. Assessment: {content.get('assessment', 'N/A')[:60]}",
            related_fact_ids=json.dumps(content.get("evidence_ids", [])),
            source_document_id=None,
            sort_key=now_dt.isoformat()
        )
        db.add(evt)

        # 3. Lock consultation
        cns.status = "approved"
        cns.approved_at = now_dt
        cns.approved_by = approved_by

        # 4. Update patient activity
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if patient:
            patient.last_activity_at = now_dt

        # 5. Audit log
        audit_service.log(
            db=db,
            actor=approved_by,
            action="consultation_approved",
            entity_type="consultation",
            entity_id=cid,
            patient_id=patient_id,
            after_state={"memory_items_added": len(created_memory), "report_id": rep_id}
        )

        db.commit()
        db.refresh(cns)

        return {
            "consultation_id": cns.id,
            "status": "approved",
            "approved_at": cns.approved_at.isoformat(),
            "approved_by": cns.approved_by,
            "memory_items_created": len(created_memory),
            "report_id": rep_id,
            "validation_flags": [c["detail"] for c in checks if c["severity"] == "warn" and not c["passed"]]
        }

consultation_service = ConsultationService()
