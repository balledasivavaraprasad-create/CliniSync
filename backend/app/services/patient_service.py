import json
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.patient import Patient
from app.models.document import Document
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.timeline_event import TimelineEvent
from app.models.contradiction import Contradiction
from app.models.brief import Brief
from app.models.clinical_memory import ClinicalMemory
from app.schemas.patient import PatientCreate, PatientUpdate
from app.api.errors import NotFoundError
from app.services.audit_service import write_audit


class PatientService:
    @staticmethod
    def create(db: Session, data: PatientCreate, actor: str = "doctor", request_id: Optional[str] = None) -> Patient:
        patient = Patient(
            full_name=data.full_name,
            date_of_birth=data.date_of_birth,
            age_years=data.age_years,
            sex=data.sex,
            contact_ref=data.contact_ref,
            is_demo=data.is_demo,
        )
        db.add(patient)
        db.flush()

        write_audit(
            db,
            actor=actor,
            action="patient.created",
            entity_type="patient",
            entity_id=patient.id,
            patient_id=patient.id,
            after={"full_name": patient.full_name},
            request_id=request_id,
        )
        db.commit()
        db.refresh(patient)
        return patient

    @staticmethod
    def get(db: Session, patient_id: str) -> Patient:
        lookup_id = "pat_demo_patient_001" if patient_id in ("demo-patient-001", "demo_patient_001") else patient_id
        patient = db.query(Patient).filter(
            (Patient.id == lookup_id) | (Patient.id == patient_id),
            Patient.deleted_at.is_(None)
        ).first()
        if not patient and patient_id in ("demo-patient-001", "pat_demo_patient_001"):
            # Fallback to any demo patient if available
            patient = db.query(Patient).filter(Patient.is_demo == True, Patient.deleted_at.is_(None)).first()
        if not patient:
            raise NotFoundError(f"Patient with ID {patient_id} not found")
        return patient


    @staticmethod
    def list(
        db: Session,
        query: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Patient]:
        q = db.query(Patient).filter(Patient.deleted_at.is_(None))
        if query:
            q = q.filter(Patient.full_name.ilike(f"%{query.strip()}%"))
        return q.order_by(Patient.last_activity_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def get_overview(db: Session, patient_id: str) -> dict:
        patient = PatientService.get(db, patient_id)
        patient_id = patient.id

        # 1. Source count
        source_count = db.query(Document).filter(Document.patient_id == patient_id).count()

        # 2. Latest brief
        latest_brief_row = (
            db.query(Brief)
            .filter(Brief.patient_id == patient_id)
            .order_by(Brief.created_at.desc())
            .first()
        )
        latest_brief = json.loads(latest_brief_row.content_json) if latest_brief_row else None

        # 3. Attention items (from open high/medium severity issues)
        attention_rows = (
            db.query(Contradiction)
            .filter(
                Contradiction.patient_id == patient_id,
                Contradiction.status == "open",
            )
            .order_by(Contradiction.severity.desc(), Contradiction.created_at.desc())
            .limit(5)
            .all()
        )
        attention_items = [
            {
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "severity": c.severity,
                "issue_type": c.issue_type,
            }
            for c in attention_rows
        ]

        # 4. Timeline preview (most recent 5 events)
        events = (
            db.query(TimelineEvent)
            .filter(TimelineEvent.patient_id == patient_id)
            .order_by(TimelineEvent.event_date.desc(), TimelineEvent.created_at.desc())
            .limit(5)
            .all()
        )
        timeline_preview = [
            {
                "id": e.id,
                "event_type": e.event_type,
                "event_date": e.event_date.isoformat() if e.event_date else None,
                "title": e.title,
                "summary": e.summary,
            }
            for e in events
        ]

        # 5. Current medications
        meds = (
            db.query(Medication)
            .filter(Medication.patient_id == patient_id, Medication.status == "current")
            .order_by(Medication.canonical_name.asc())
            .all()
        )
        current_medications = [
            {
                "id": m.id,
                "canonical_name": m.canonical_name,
                "raw_name": m.raw_name,
                "dose_text": m.dose_text or f"{m.strength_value or ''} {m.strength_unit or ''}".strip(),
                "frequency_text": m.frequency_text or m.frequency_code,
                "status": m.status,
            }
            for m in meds
        ]

        # 6. Latest investigations
        invs = (
            db.query(Investigation)
            .filter(Investigation.patient_id == patient_id)
            .order_by(Investigation.observed_date.desc())
            .limit(6)
            .all()
        )
        latest_investigations = [
            {
                "id": i.id,
                "test_name_canonical": i.test_name_canonical,
                "value_text": i.value_text,
                "unit": i.unit,
                "abnormal_flag": i.abnormal_flag,
                "observed_date": i.observed_date.isoformat() if i.observed_date else None,
            }
            for i in invs
        ]

        # 7. Memory summary (verified)
        memories = (
            db.query(ClinicalMemory)
            .filter(ClinicalMemory.patient_id == patient_id, ClinicalMemory.verified == True)
            .order_by(ClinicalMemory.created_at.desc())
            .all()
        )
        memory_summary = [
            {
                "id": mem.id,
                "memory_type": mem.memory_type,
                "content": json.loads(mem.content_json) if mem.content_json.startswith("{") else mem.content_json,
                "created_at": mem.created_at.isoformat(),
            }
            for mem in memories
        ]

        # 8. Open issue counts
        open_issues = (
            db.query(Contradiction.issue_type, func.count(Contradiction.id))
            .filter(Contradiction.patient_id == patient_id, Contradiction.status == "open")
            .group_by(Contradiction.issue_type)
            .all()
        )
        open_issue_counts = {t: count for t, count in open_issues}

        return {
            "patient": patient,
            "source_count": source_count,
            "latest_brief": latest_brief,
            "attention_items": attention_items,
            "timeline_preview": timeline_preview,
            "current_medications": current_medications,
            "latest_investigations": latest_investigations,
            "memory_summary": memory_summary,
            "open_issue_counts": open_issue_counts,
        }
