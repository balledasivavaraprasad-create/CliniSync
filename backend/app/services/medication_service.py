from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
import json
import structlog

from app.models.medication import Medication
from app.models.document import Document
from app.models.contradiction import Contradiction
from app.models.timeline_event import TimelineEvent
from app.schemas.common import IssueType, Severity, MedStatus
from app.utils.ids import contradiction_id, timeline_event_id

logger = structlog.get_logger(__name__)

class MedicationService:
    @staticmethod
    def get_patient_medications(
        db: Session,
        patient_id: str,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = db.query(Medication).filter(Medication.patient_id == patient_id)
        if status:
            query = query.filter(Medication.status == status)

        meds = query.order_by(desc(Medication.created_at)).all()

        # Group by canonical name to present deduplicated current state
        grouped: Dict[str, Dict[str, Any]] = {}
        for m in meds:
            key = m.canonical_name
            if key not in grouped:
                # Find conflicts for this drug
                conflicts = db.query(Contradiction).filter(
                    Contradiction.patient_id == patient_id,
                    Contradiction.issue_type == IssueType.medication_conflict.value,
                    Contradiction.status == "open",
                    Contradiction.description.contains(key)
                ).all()

                grouped[key] = {
                    "id": m.id,
                    "patient_id": m.patient_id,
                    "canonical_name": m.canonical_name,
                    "raw_name": m.raw_name,
                    "strength_value": m.strength_value,
                    "strength_unit": m.strength_unit,
                    "dose_text": m.dose_text,
                    "frequency_code": m.frequency_code,
                    "frequency_text": m.frequency_text,
                    "route": m.route,
                    "duration_text": m.duration_text,
                    "status": m.status,
                    "status_reason": m.status_reason,
                    "confidence": m.confidence,
                    "confidence_band": "high" if m.confidence >= 0.85 else ("medium" if m.confidence >= 0.60 else "needs_verification"),
                    "source_document_id": m.source_document_id,
                    "conflict_ids": [c.id for c in conflicts],
                    "has_conflict": len(conflicts) > 0,
                    "history_count": 1
                }
            else:
                grouped[key]["history_count"] += 1

        return list(grouped.values())

    @staticmethod
    def get_medication_history(
        db: Session,
        patient_id: str,
        group_key: str
    ) -> List[Dict[str, Any]]:
        meds = db.query(Medication).filter(
            Medication.patient_id == patient_id,
            (Medication.group_key == group_key) | (Medication.canonical_name == group_key)
        ).order_by(desc(Medication.created_at)).all()

        results = []
        for m in meds:
            doc = db.query(Document).filter(Document.id == m.source_document_id).first() if m.source_document_id else None
            results.append({
                "id": m.id,
                "canonical_name": m.canonical_name,
                "raw_name": m.raw_name,
                "dose_text": m.dose_text,
                "strength_value": m.strength_value,
                "strength_unit": m.strength_unit,
                "frequency_code": m.frequency_code,
                "frequency_text": m.frequency_text,
                "status": m.status,
                "document_date": doc.document_date.isoformat() if (doc and doc.document_date) else None,
                "source_document_filename": doc.original_filename if doc else None,
                "source_document_id": m.source_document_id,
                "created_at": m.created_at.isoformat() if m.created_at else None
            })
        return results

    @staticmethod
    def reconcile(db: Session, patient_id: str) -> List[Dict[str, Any]]:
        """
        Reconciles medications per Section 11.3:
        - If dates distinct and ordered -> informational change
        - If dates equal/unknown and instructions conflict -> medication_conflict issue
        - Strict adherence to INV-4: NEVER state a correct dose. Output comparison template only.
        """
        meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        # Group by canonical name
        by_drug: Dict[str, List[Medication]] = {}
        for m in meds:
            by_drug.setdefault(m.canonical_name, []).append(m)

        detected_issues = []

        for drug_name, drug_meds in by_drug.items():
            if len(drug_meds) < 2:
                continue

            # Fetch associated document dates
            med_with_date = []
            for m in drug_meds:
                doc = db.query(Document).filter(Document.id == m.source_document_id).first() if m.source_document_id else None
                doc_date = doc.document_date if (doc and doc.document_date) else None
                med_with_date.append((m, doc_date, doc))

            # Compare pairs
            for i in range(len(med_with_date)):
                for j in range(i + 1, len(med_with_date)):
                    m1, d1, doc1 = med_with_date[i]
                    m2, d2, doc2 = med_with_date[j]

                    # Check for conflicting frequency or strength
                    strength_diff = (m1.strength_value != m2.strength_value and m1.strength_value is not None and m2.strength_value is not None)
                    freq_diff = (m1.frequency_code != m2.frequency_code and m1.frequency_code != "other" and m2.frequency_code != "other")

                    if strength_diff or freq_diff:
                        # If dates are identical or missing, emit medication_conflict
                        if d1 == d2 or d1 is None or d2 is None:
                            doc1_name = doc1.original_filename if doc1 else "Record 1"
                            doc2_name = doc2.original_filename if doc2 else "Record 2"
                            d1_str = d1.strftime("%d %b %Y") if d1 else "undated"
                            d2_str = d2.strftime("%d %b %Y") if d2 else "undated"

                            # Severity: high if strength differs >= 2x, else medium
                            sev = Severity.medium.value
                            if m1.strength_value and m2.strength_value:
                                ratio = max(m1.strength_value, m2.strength_value) / min(m1.strength_value, m2.strength_value)
                                if ratio >= 2.0:
                                    sev = Severity.high.value

                            # Template per INV-4
                            desc_text = (
                                f"Two records contain different {drug_name.title()} instructions: "
                                f"{m1.raw_name} {m1.strength_value or ''}{m1.strength_unit or ''} {m1.frequency_text or m1.frequency_code} ({doc1_name}, {d1_str}) vs "
                                f"{m2.raw_name} {m2.strength_value or ''}{m2.strength_unit or ''} {m2.frequency_text or m2.frequency_code} ({doc2_name}, {d2_str})."
                            )

                            issue = Contradiction(
                                id=contradiction_id(),
                                patient_id=patient_id,
                                issue_type=IssueType.medication_conflict.value,
                                severity=sev,
                                title=f"Conflicting dosage instructions for {drug_name.title()}",
                                description=desc_text,
                                related_document_ids=json.dumps([doc1.id if doc1 else "", doc2.id if doc2 else ""]),
                                related_fact_ids=json.dumps([m1.fact_id, m2.fact_id]),
                                detail_json=json.dumps({
                                    "drug": drug_name,
                                    "source_1": {"doc": doc1_name, "dose": f"{m1.strength_value}{m1.strength_unit}", "freq": m1.frequency_code},
                                    "source_2": {"doc": doc2_name, "dose": f"{m2.strength_value}{m2.strength_unit}", "freq": m2.frequency_code},
                                }),
                                status="open"
                            )
                            db.add(issue)
                            detected_issues.append(issue)

        db.flush()
        return detected_issues

medication_service = MedicationService()
