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
    ForbiddenError,
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
        actor: str = "ai",
        request_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Tuple[Consultation, ConsultationVersion]:
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise NotFoundError(f"Patient {patient_id} not found")

        # Verify brief ownership if brief_id is provided (prevent cross-patient parameter substitution)
        if brief_id:
            from app.models.brief import Brief
            brief_row = db.query(Brief).filter(Brief.id == brief_id).first()
            if not brief_row:
                raise NotFoundError(f"Brief {brief_id} not found")
            if brief_row.patient_id != patient_id:
                raise ForbiddenError(f"Brief {brief_id} belongs to patient {brief_row.patient_id}, not {patient_id}")

        # Deduplication 1: If brief_id is provided, return existing active draft for that brief
        if brief_id:
            existing_cns = (
                db.query(Consultation)
                .filter(
                    Consultation.patient_id == patient_id,
                    Consultation.brief_id == brief_id,
                    Consultation.status.in_(["draft", "in_review"]),
                )
                .order_by(desc(Consultation.created_at))
                .first()
            )
            if existing_cns:
                ver = db.query(ConsultationVersion).filter(
                    ConsultationVersion.id == existing_cns.current_version_id
                ).first()
                if ver:
                    logger.info("returning_existing_consultation_draft_for_brief", cid=existing_cns.id, brief_id=brief_id)
                    return existing_cns, ver

        # Deduplication 2: If explicit idempotency_key matches an existing consultation_created audit record for this patient
        if idempotency_key:
            from app.models.audit_log import AuditLog
            audit_rec = (
                db.query(AuditLog)
                .filter(
                    AuditLog.patient_id == patient_id,
                    AuditLog.action == "consultation_created",
                    AuditLog.request_id == idempotency_key,
                )
                .first()
            )
            if audit_rec:
                existing_cns = db.query(Consultation).filter(
                    Consultation.id == audit_rec.entity_id,
                    Consultation.patient_id == patient_id,
                ).first()
                if existing_cns:
                    ver = db.query(ConsultationVersion).filter(
                        ConsultationVersion.id == existing_cns.current_version_id
                    ).first()
                    if ver:
                        logger.info("returning_idempotent_consultation_draft", cid=existing_cns.id, key=idempotency_key)
                        return existing_cns, ver

        facts = db.query(ClinicalFact).filter(ClinicalFact.patient_id == patient_id).all()
        meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        invs = db.query(Investigation).filter(Investigation.patient_id == patient_id).all()
        memories = db.query(ClinicalMemory).filter(
            ClinicalMemory.patient_id == patient_id,
            ClinicalMemory.verified == True,
        ).order_by(desc(ClinicalMemory.created_at)).all()

        # Build clean initial content directly derived from records
        # AI MUST NEVER draft assessment/plan/examination
        diag_facts = [f for f in facts if f.fact_type == "diagnosis"]
        cc = diag_facts[0].value if diag_facts else "Routine longitudinal consultation review"
        hpi = ", ".join([f.value for f in facts if f.fact_type == "symptom"][:3]) or "No active acute symptoms documented."
        past_hx = "; ".join([f.value for f in diag_facts[:4]])

        # Incorporate approved memory summaries into past history if available
        retrieved_memories_data: List[Dict[str, Any]] = []
        memory_hx_additions: List[str] = []
        for mem in memories:
            m_dict = json.loads(mem.content_json) if mem.content_json else {}
            retrieved_memories_data.append({
                "id": mem.id,
                "memory_type": mem.memory_type,
                "content": m_dict,
                "source_consultation_id": mem.source_consultation_id,
                "source_version_id": mem.source_version_id,
                "verified": mem.verified,
                "created_at": mem.created_at.isoformat() if mem.created_at else None,
            })
            for k in ("diagnosis", "assessment", "plan", "plan_note"):
                if m_dict.get(k):
                    val = m_dict[k]
                    summary_text = f"Approved {mem.memory_type}: {val}"
                    if summary_text not in memory_hx_additions:
                        memory_hx_additions.append(summary_text)

        if memory_hx_additions:
            combined_hx = [past_hx] if past_hx else []
            combined_hx.extend(memory_hx_additions[:3])
            past_hx = "; ".join([h for h in combined_hx if h])

        cur_meds = [{"name": m.canonical_name.title(), "dose": m.dose_text or f"{m.strength_value or ''}{m.strength_unit or ''}".strip(), "freq": m.frequency_code, "fact_id": m.fact_id} for m in meds]
        allergies = [{"text": f.value, "fact_id": f.id} for f in facts if f.fact_type == "allergy"]
        invs_reviewed = [{"test": i.test_name_canonical, "val": str(i.value_numeric or i.value_text), "unit": i.unit, "fact_id": i.fact_id} for i in invs[:8]]

        evidence_ids = [f.id for f in facts[:20]]

        flags_list = [ConsultationFlag(text="Initial consultation draft generated from source records. Complete assessment and plan before approval.", by="ai")]
        if memories:
            flags_list.append(ConsultationFlag(text=f"Retrieved {len(memories)} approved clinical memory item(s) from previous consultation records.", by="system"))

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
            flags=flags_list,
            evidence_ids=evidence_ids,
            verified_memories=retrieved_memories_data,
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

        from app.services.audit_service import audit_service
        audit_service.log(
            db=db,
            actor=actor,
            action="consultation_created",
            entity_type="consultation",
            entity_id=cns_id,
            patient_id=patient_id,
            after_state={"specialty": specialty, "version_id": ver_id, "origin": ver.origin},
            request_id=idempotency_key or request_id,
        )

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
        actor: str = "doctor",
        expected_version_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ConsultationVersion:
        cns = db.query(Consultation).filter(Consultation.id == cid).first()
        if not cns:
            raise NotFoundError(f"Consultation {cid} not found")
        if cns.status == "approved":
            raise InvalidStateTransitionError("Approved consultations are immutable and cannot be edited.")
        if expected_version_id and cns.current_version_id != expected_version_id:
            raise InvalidStateTransitionError(
                f"Stale consultation version: client was on {expected_version_id}, but current version is {cns.current_version_id}."
            )

        current_ver = db.query(ConsultationVersion).filter(ConsultationVersion.id == cns.current_version_id).first()
        if not current_ver:
            raise NotFoundError("Current consultation version not found")

        # Preserve the original AI-generated version (v1) even after doctor edits!
        if current_ver.origin == ConsultationOrigin.ai_generated.value:
            latest_ver = db.query(ConsultationVersion).filter(ConsultationVersion.consultation_id == cid).order_by(desc(ConsultationVersion.version_number)).first()
            next_ver_num = (latest_ver.version_number + 1) if latest_ver else 2
            new_ver = ConsultationVersion(
                id=version_id(),
                consultation_id=cid,
                version_number=next_ver_num,
                origin=ConsultationOrigin.doctor_edited.value,
                content_json=json.dumps(content),
                change_summary=f"Doctor updated draft ({actor})",
                edited_by=actor
            )
            db.add(new_ver)
            cns.current_version_id = new_ver.id
            current_ver = new_ver
        else:
            current_ver.content_json = json.dumps(content)
            current_ver.origin = ConsultationOrigin.doctor_edited.value
            current_ver.edited_by = actor
            current_ver.change_summary = f"Doctor updated draft ({actor})"

        if cns.status == "draft":
            cns.status = "in_review"

        from app.services.audit_service import audit_service
        audit_service.log(
            db=db,
            actor=actor,
            action="consultation_draft_updated",
            entity_type="consultation",
            entity_id=cid,
            patient_id=cns.patient_id,
            after_state={"version_id": current_ver.id, "version_number": current_ver.version_number},
            request_id=request_id,
        )

        db.commit()
        db.refresh(current_ver)
        return current_ver

    def create_version(
        self,
        db: Session,
        cid: str,
        content: Dict[str, Any],
        change_summary: Optional[str] = None,
        actor: str = "doctor",
        expected_version_id: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> ConsultationVersion:
        cns = db.query(Consultation).filter(Consultation.id == cid).first()
        if not cns:
            raise NotFoundError(f"Consultation {cid} not found")
        if cns.status == "approved":
            raise InvalidStateTransitionError("Approved consultations are immutable.")
        if expected_version_id and cns.current_version_id != expected_version_id:
            raise InvalidStateTransitionError(
                f"Stale consultation version: client was on {expected_version_id}, but current version is {cns.current_version_id}."
            )

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

        from app.services.audit_service import audit_service
        audit_service.log(
            db=db,
            actor=actor,
            action="consultation_version_created",
            entity_type="consultation_version",
            entity_id=new_ver_id,
            patient_id=cns.patient_id,
            after_state={"consultation_id": cid, "version_number": next_ver_num, "change_summary": new_ver.change_summary},
            request_id=request_id,
        )

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
        approved_by: str = "doctor",
        expected_version_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Runs Gate 1. On pass, writes verified clinical_memory and timeline approved_note in ONE transaction.
        Enforces INV-1, INV-8, INV-9.
        """
        cns = None
        if db is not None:
            cns = db.query(Consultation).filter(Consultation.id == cid).first()
            if not cns:
                raise NotFoundError(f"Consultation {cid} not found")
            if cns.status == "approved":
                raise InvalidStateTransitionError("Consultation has already been approved.")
            if expected_version_id and cns.current_version_id != expected_version_id:
                prior_ver = db.query(ConsultationVersion).filter(ConsultationVersion.id == expected_version_id).first()
                curr_ver = db.query(ConsultationVersion).filter(ConsultationVersion.id == cns.current_version_id).first()
                is_valid_prior = (
                    prior_ver
                    and curr_ver
                    and prior_ver.consultation_id == cid
                    and prior_ver.version_number == curr_ver.version_number - 1
                )
                if not is_valid_prior:
                    raise InvalidStateTransitionError(
                        f"Stale consultation version: client was on {expected_version_id}, but current version is {cns.current_version_id}."
                    )

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

        ver = db.query(ConsultationVersion).filter(ConsultationVersion.id == cns.current_version_id).first()
        if not ver:
            raise NotFoundError(f"Current version '{cns.current_version_id}' not found")
        content = json.loads(ver.content_json) if (ver and ver.content_json) else {}
        patient_id = cns.patient_id
        now_dt = datetime.now(timezone.utc)
        import hashlib
        content_hash = hashlib.sha256(ver.content_json.encode("utf-8")).hexdigest()

        prov_data = {
            "doctor_id": approved_by,
            "consultation_id": cid,
            "version_id": ver.id,
            "approval_timestamp": now_dt.isoformat(),
            "content_hash": content_hash,
            "approved_by": approved_by,
            "specialty": cns.specialty,
            "evidence_ids": content.get("evidence_ids", [])
        }

        # 1. Create verified clinical_memory items (Append-only & Versioned)
        from app.services.memory_service import memory_service
        created_memory = []

        # Memory candidate: Diagnoses / Chief Complaint
        if content.get("chief_complaint"):
            mem_diag = memory_service.record_approved_memory(
                db=db,
                patient_id=patient_id,
                memory_type="diagnosis",
                content={
                    "diagnosis": content["chief_complaint"],
                    "semantic_state": "DOCUMENTED",
                    "status": "DOCUMENTED",
                },
                source_consultation_id=cid,
                source_version_id=ver.id,
                validation_report_id=rep_id,
                approving_actor=approved_by,
                provenance=prov_data
            )
            created_memory.append(mem_diag)

        # Memory candidate: Assessment & Plan
        if content.get("assessment"):
            mem_assess = memory_service.record_approved_memory(
                db=db,
                patient_id=patient_id,
                memory_type="assessment",
                content={
                    "assessment": content["assessment"],
                    "semantic_state": "DOCUMENTED",
                    "status": "DOCUMENTED",
                },
                source_consultation_id=cid,
                source_version_id=ver.id,
                validation_report_id=rep_id,
                approving_actor=approved_by,
                provenance=prov_data
            )
            created_memory.append(mem_assess)

        if content.get("plan"):
            mem_plan = memory_service.record_approved_memory(
                db=db,
                patient_id=patient_id,
                memory_type="plan_note",
                content={
                    "plan": content["plan"],
                    "semantic_state": "DOCUMENTED",
                    "status": "DOCUMENTED",
                },
                source_consultation_id=cid,
                source_version_id=ver.id,
                validation_report_id=rep_id,
                approving_actor=approved_by,
                provenance=prov_data
            )
            created_memory.append(mem_plan)

        # 2. Add approved_note to timeline if not already present
        existing_evt = db.query(TimelineEvent).filter(
            TimelineEvent.patient_id == patient_id,
            TimelineEvent.event_type == "approved_note",
            TimelineEvent.title == f"Approved Consultation ({cns.specialty.title()})",
            TimelineEvent.summary.like(f"Consultation finalized by {approved_by}%"),
        ).first()
        if not existing_evt:
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
            after_state={
                "doctor_id": approved_by,
                "consultation_id": cid,
                "version_id": ver.id,
                "approval_timestamp": now_dt.isoformat(),
                "content_hash": content_hash,
                "memory_items_added": len(created_memory),
                "report_id": rep_id
            }
        )

        db.commit()
        db.refresh(cns)

        return {
            "consultation_id": cns.id,
            "version_id": ver.id,
            "doctor_id": approved_by,
            "approval_timestamp": now_dt.isoformat(),
            "content_hash": content_hash,
            "status": "approved",
            "approved_at": cns.approved_at.isoformat(),
            "approved_by": cns.approved_by,
            "memory_items_created": len(created_memory),
            "report_id": rep_id,
            "validation_flags": [c["detail"] for c in checks if c["severity"] == "warn" and not c["passed"]]
        }

consultation_service = ConsultationService()
