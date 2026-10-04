from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
import json
import structlog
import hashlib

from app.models.contradiction import Contradiction
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.schemas.common import IssueType, Severity
from app.utils.ids import contradiction_id

logger = structlog.get_logger(__name__)

class MissingInfoService:
    @staticmethod
    def _compute_fingerprint(title: str, patient_id: str) -> str:
        raw = f"{patient_id}_missing_{title}".lower().strip()
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    @classmethod
    def recompute(cls, db: Session, patient_id: str) -> List[Dict[str, Any]]:
        """
        Checklist engine for missing clinical data per Section 11.6.
        Strict adherence to INV-5: Phrased as 'Potentially missing: ...' with reason. Never guesses values.
        """
        facts = db.query(ClinicalFact).filter(ClinicalFact.patient_id == patient_id).all()
        meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        invs = db.query(Investigation).filter(Investigation.patient_id == patient_id).all()
        docs = db.query(Document).filter(Document.patient_id == patient_id).all()

        missing_prompts = []

        # 1. Allergy status undocumented
        has_allergies = any(f.fact_type == "allergy" for f in facts)
        if not has_allergies:
            missing_prompts.append({
                "title": "Allergy status undocumented",
                "prompt": "Potentially missing: Drug or environmental allergy status",
                "reason": "No documented drug or environmental allergy records found across uploaded clinical files."
            })

        # 2. Check if diabetic patient has recent HbA1c
        is_diabetic = any("diabetes" in f.value.lower() for f in facts if f.fact_type == "diagnosis")
        if is_diabetic:
            hba1c_invs = [i for i in invs if i.test_name_canonical == "hba1c" and i.observed_date]
            if not hba1c_invs:
                missing_prompts.append({
                    "title": "Missing baseline HbA1c",
                    "prompt": "Potentially missing: Recent HbA1c test result",
                    "reason": "Patient is diagnosed with diabetes, but no baseline or recent HbA1c measurement is recorded."
                })
            else:
                hba1c_invs.sort(key=lambda x: x.observed_date, reverse=True)
                raw_latest = hba1c_invs[0].observed_date
                latest_date = raw_latest.date() if isinstance(raw_latest, datetime) else raw_latest
                now_date = datetime.now(timezone.utc).date()
                if (now_date - latest_date).days > 180:
                    missing_prompts.append({
                        "title": "Overdue HbA1c monitoring",
                        "prompt": "Potentially missing: Updated HbA1c (>6 months old)",
                        "reason": f"Most recent recorded HbA1c was observed on {latest_date.strftime('%Y-%m-%d')}, which is older than 6 months."
                    })

        # 3. Medication start dates absent
        meds_without_dates = [m for m in meds if not m.start_date]
        if meds_without_dates:
            missing_prompts.append({
                "title": "Medication start dates undocumented",
                "prompt": f"Potentially missing: Start dates for {len(meds_without_dates)} active medication(s)",
                "reason": f"Initial prescription dates or start durations are absent for: {', '.join([m.canonical_name.title() for m in meds_without_dates[:3]])}."
            })

        # 4. Undated documents
        undated_docs = [d for d in docs if not d.document_date]
        if undated_docs:
            missing_prompts.append({
                "title": "Undated source documents",
                "prompt": f"Potentially missing: Consultation/test date for {len(undated_docs)} document(s)",
                "reason": f"Document(s) {', '.join([d.original_filename for d in undated_docs[:2]])} do not carry a clear clinical consultation date."
            })

        # Persist as Contradiction rows with issue_type="missing_information"
        existing = db.query(Contradiction).filter(
            Contradiction.patient_id == patient_id,
            Contradiction.issue_type == IssueType.missing_information.value
        ).all()
        status_map = {cls._compute_fingerprint(ex.title, patient_id): ex for ex in existing}

        created = []
        for p in missing_prompts:
            fp = cls._compute_fingerprint(p["title"], patient_id)
            prev = status_map.get(fp)
            iss = Contradiction(
                id=prev.id if prev else contradiction_id(),
                patient_id=patient_id,
                issue_type=IssueType.missing_information.value,
                severity=Severity.low.value,
                title=p["title"],
                description=f"{p['prompt']}. Reason: {p['reason']}",
                related_document_ids=json.dumps([]),
                related_fact_ids=json.dumps([]),
                detail_json=json.dumps({"prompt": p["prompt"], "reason": p["reason"]}),
                status=prev.status if prev else "open",
                doctor_note=prev.doctor_note if prev else None
            )
            db.merge(iss)
            created.append(iss)

        db.commit()
        return [
            {
                "id": c.id,
                "title": c.title,
                "prompt": p["prompt"],
                "reason": p["reason"]
            }
            for c, p in zip(created, missing_prompts)
        ]

missing_info_service = MissingInfoService()
