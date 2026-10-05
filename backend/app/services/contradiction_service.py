from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
import json
import structlog
import hashlib

from app.api.errors import IssueNotFoundError
from app.models.contradiction import Contradiction
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.patient import Patient
from app.models.medication import Medication
from app.schemas.common import IssueType, Severity
from app.utils.ids import contradiction_id

logger = structlog.get_logger(__name__)

class ContradictionService:
    @staticmethod
    def _compute_fingerprint(issue_type: str, title: str, patient_id: str) -> str:
        raw = f"{patient_id}_{issue_type}_{title}".lower().strip()
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @staticmethod
    def get_patient_issues(
        db: Session,
        patient_id: str,
        issue_type: Optional[str] = None,
        status: Optional[str] = None,
        severity: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query = db.query(Contradiction).filter(Contradiction.patient_id == patient_id)
        if issue_type:
            query = query.filter(Contradiction.issue_type == issue_type)
        if status:
            query = query.filter(Contradiction.status == status)
        if severity:
            query = query.filter(Contradiction.severity == severity)

        issues = query.order_by(Contradiction.created_at.desc()).all()
        results = []
        for iss in issues:
            doc_ids = []
            fact_ids = []
            details = {}
            try:
                if iss.related_document_ids:
                    doc_ids = json.loads(iss.related_document_ids)
                if iss.related_fact_ids:
                    fact_ids = json.loads(iss.related_fact_ids)
                if iss.detail_json:
                    details = json.loads(iss.detail_json)
            except Exception:
                pass

            results.append({
                "id": iss.id,
                "patient_id": iss.patient_id,
                "issue_type": iss.issue_type,
                "severity": iss.severity,
                "title": iss.title,
                "description": iss.description,
                "related_document_ids": doc_ids,
                "related_fact_ids": fact_ids,
                "detail_json": details,
                "status": iss.status,
                "doctor_note": iss.doctor_note,
                "created_at": iss.created_at.isoformat() if iss.created_at else None,
                "updated_at": iss.updated_at.isoformat() if iss.updated_at else None,
            })
        return results

    @staticmethod
    def patch_issue(
        db: Session,
        issue_id: str,
        status: Optional[str] = None,
        doctor_note: Optional[str] = None
    ) -> Dict[str, Any]:
        iss = db.query(Contradiction).filter(Contradiction.id == issue_id).first()
        if not iss:
            raise IssueNotFoundError(
                f"Review item {issue_id} is no longer in the queue. "
                "It may have been recomputed or removed."
            )

        if status:
            iss.status = status
        if doctor_note is not None:
            iss.doctor_note = doctor_note

        db.commit()
        db.refresh(iss)

        return {
            "id": iss.id,
            "status": iss.status,
            "doctor_note": iss.doctor_note,
            "title": iss.title,
            "severity": iss.severity
        }

    @classmethod
    def recompute(cls, db: Session, patient_id: str) -> List[Dict[str, Any]]:
        """
        Runs rule-based detectors for contradictory clinical records.
        Preserves existing issues that doctors have already acknowledged or resolved.
        """
        existing_issues = db.query(Contradiction).filter(Contradiction.patient_id == patient_id).all()
        # Map fingerprints to existing status/notes
        status_map: Dict[str, Dict[str, Any]] = {}
        for ex in existing_issues:
            fp = cls._compute_fingerprint(ex.issue_type, ex.title, patient_id)
            status_map[fp] = {
                "id": ex.id,
                "status": ex.status,
                "doctor_note": ex.doctor_note
            }

        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        # Was `Document.id == patient_id`, which matches nothing (a document id
        # is never a patient id), so the date-conflict detector below never had
        # documents to inspect and never fired
        # (docs/frontend/API_MISMATCHES.md O-02).
        docs = db.query(Document).filter(Document.patient_id == patient_id).all()
        facts = db.query(ClinicalFact).filter(ClinicalFact.patient_id == patient_id).all()

        detected = []

        # 1. Diagnosis conflict: Type 1 vs Type 2 diabetes
        diag_values = [f.value.lower() for f in facts if f.fact_type == "diagnosis"]
        has_t1 = any("type 1" in v for v in diag_values)
        has_t2 = any("type 2" in v for v in diag_values)
        if has_t1 and has_t2:
            title = "Contradictory Diabetes Diagnoses (Type 1 vs Type 2)"
            desc = "Patient records contain both Type 1 Diabetes and Type 2 Diabetes diagnoses across different documents."
            fp = cls._compute_fingerprint(IssueType.diagnosis_conflict.value, title, patient_id)
            prev = status_map.get(fp)
            iss = Contradiction(
                id=prev["id"] if prev else contradiction_id(),
                patient_id=patient_id,
                issue_type=IssueType.diagnosis_conflict.value,
                severity=Severity.medium.value,
                title=title,
                description=desc,
                related_document_ids=json.dumps([]),
                related_fact_ids=json.dumps([]),
                detail_json=json.dumps({"diagnoses": ["Type 1 Diabetes", "Type 2 Diabetes"]}),
                status=prev["status"] if prev else "open",
                doctor_note=prev["doctor_note"] if prev else None
            )
            detected.append(iss)

        # 2. Date conflicts: Document date in the future or before DOB
        now_dt = datetime.now(timezone.utc)
        for d in docs:
            # SQLite hands back naive datetimes for columns written without a
            # timezone, while `now_dt` is aware — comparing them raises
            # `TypeError`. This detector never ran before the `Document.patient_id`
            # filter was corrected, so the bug stayed hidden. Stored values are
            # treated as UTC, which is what `utc_now()` writes.
            doc_date = d.document_date
            if doc_date is None:
                continue
            if doc_date.tzinfo is None:
                doc_date = doc_date.replace(tzinfo=timezone.utc)
            if doc_date > now_dt:
                title = f"Future Document Date on {d.original_filename}"
                desc = f"Document {d.original_filename} has a recorded date of {doc_date.strftime('%Y-%m-%d')}, which is in the future."
                fp = cls._compute_fingerprint(IssueType.date_conflict.value, title, patient_id)
                prev = status_map.get(fp)
                iss = Contradiction(
                    id=prev["id"] if prev else contradiction_id(),
                    patient_id=patient_id,
                    issue_type=IssueType.date_conflict.value,
                    severity=Severity.low.value,
                    title=title,
                    description=desc,
                    related_document_ids=json.dumps([d.id]),
                    related_fact_ids=json.dumps([]),
                    detail_json=json.dumps({"date": doc_date.isoformat()}),
                    status=prev["status"] if prev else "open",
                    doctor_note=prev["doctor_note"] if prev else None
                )
                detected.append(iss)

        # 3. Unclear medication status: Drug stopped without stop date, or missing from recent Rx
        meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        by_drug: Dict[str, List[Medication]] = {}
        for m in meds:
            by_drug.setdefault(m.canonical_name, []).append(m)

        for drug_name, m_list in by_drug.items():
            if len(m_list) >= 2:
                # If earlier had it and later has it missing or different without explicit discontinuation note
                statuses = set([m.status for m in m_list])
                if "uncertain" in statuses:
                    title = f"Unclear Active Status for {drug_name.title()}"
                    desc = f"Medication records for {drug_name.title()} do not clearly indicate if the drug is currently active or discontinued."
                    fp = cls._compute_fingerprint(IssueType.unclear_medication_status.value, title, patient_id)
                    prev = status_map.get(fp)
                    iss = Contradiction(
                        id=prev["id"] if prev else contradiction_id(),
                        patient_id=patient_id,
                        issue_type=IssueType.unclear_medication_status.value,
                        severity=Severity.low.value,
                        title=title,
                        description=desc,
                        related_document_ids=json.dumps([m.source_document_id for m in m_list if m.source_document_id]),
                        related_fact_ids=json.dumps([m.fact_id for m in m_list]),
                        detail_json=json.dumps({"drug": drug_name}),
                        status=prev["status"] if prev else "open",
                        doctor_note=prev["doctor_note"] if prev else None
                    )
                    detected.append(iss)

        # Merge detected issues
        for iss in detected:
            db.merge(iss)
        db.commit()

        return [
            {
                "id": i.id,
                "title": i.title,
                "issue_type": i.issue_type,
                "severity": i.severity,
                "status": i.status
            }
            for i in detected
        ]

contradiction_service = ContradictionService()
