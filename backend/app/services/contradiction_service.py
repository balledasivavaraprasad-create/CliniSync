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
from app.models.investigation import Investigation
from app.schemas.common import IssueType, Severity
from app.schemas.contradiction import (
    DifferenceClassification,
    DifferenceEvaluationResult,
    ContradictionLifecycle,
)
from app.services.difference_evaluator import difference_evaluator
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
            status_lower = status.lower().strip()
            if status_lower in ("open", "detected"):
                query = query.filter(Contradiction.status.in_(["open", "detected", "DETECTED"]))
            elif status_lower in ("presented", "presented to doctor", "presented_to_doctor"):
                query = query.filter(Contradiction.status.in_(["presented", "PRESENTED TO DOCTOR"]))
            elif status_lower in ("acknowledged", "doctor resolves", "doctor_resolves"):
                query = query.filter(Contradiction.status.in_(["acknowledged", "DOCTOR RESOLVES"]))
            elif status_lower in ("resolved", "resolved_by_doctor"):
                query = query.filter(Contradiction.status.in_(["resolved", "resolved_by_doctor", "RESOLVED"]))
            else:
                query = query.filter(Contradiction.status == status)
        if severity:
            query = query.filter(Contradiction.severity == severity)

        issues = query.order_by(Contradiction.created_at.desc()).all()
        results = []
        for iss in issues:
            doc_ids = []
            fact_ids = []
            details: Dict[str, Any] = {}
            try:
                if iss.related_document_ids:
                    doc_ids = json.loads(iss.related_document_ids)
                if iss.related_fact_ids:
                    fact_ids = json.loads(iss.related_fact_ids)
                if iss.detail_json:
                    details = json.loads(iss.detail_json)
            except Exception:
                pass

            lifecycle_status = details.get("status") or (
                "RESOLVED" if iss.status in ("resolved", "resolved_by_doctor", "dismissed")
                else ("DOCTOR RESOLVES" if iss.status == "acknowledged"
                else ("PRESENTED TO DOCTOR" if iss.status == "presented"
                else "DETECTED"))
            )
            details["status"] = lifecycle_status

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
                "lifecycle_status": lifecycle_status,
                "entity": details.get("entity") or iss.title,
                "conflicting_values": details.get("conflicting_values") or {},
                "source_a": details.get("source_a") or {},
                "source_b": details.get("source_b") or {},
                "dates": details.get("dates") or {},
                "evidence_spans": details.get("evidence_spans") or {},
                "authoritative_source": details.get("authoritative_source"),
                "preferred_display_order": details.get("preferred_display_order") or ["source_a", "source_b"],
                "requires_doctor_review": details.get("requires_doctor_review", True),
                "source_priority_explanation": details.get("source_priority_explanation"),
                "confidence": details.get("confidence", 1.0),
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
        doctor_note: Optional[str] = None,
        actor: str = "doctor",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        iss = db.query(Contradiction).filter(Contradiction.id == issue_id).first()
        if not iss:
            raise IssueNotFoundError(
                f"Review item {issue_id} is no longer in the queue. "
                "It may have been recomputed or removed."
            )

        details: Dict[str, Any] = {}
        try:
            if iss.detail_json:
                details = json.loads(iss.detail_json)
        except Exception:
            pass

        before_state = {
            "status": iss.status,
            "lifecycle_status": details.get("status", "DETECTED"),
            "doctor_note": iss.doctor_note,
        }

        norm_lifecycle = details.get("status", "DETECTED")
        if status:
            iss.status = status
            key = status.lower().strip()
            if key in ("open", "detected"):
                norm_lifecycle = "DETECTED"
            elif key in ("presented", "presented to doctor", "presented_to_doctor"):
                norm_lifecycle = "PRESENTED TO DOCTOR"
            elif key in ("acknowledged", "doctor resolves", "doctor_resolves"):
                norm_lifecycle = "DOCTOR RESOLVES"
            elif key in ("resolved", "resolved_by_doctor", "dismissed"):
                norm_lifecycle = "RESOLVED"
            else:
                norm_lifecycle = status.upper()

            details["status"] = norm_lifecycle
            iss.detail_json = json.dumps(details)

        if doctor_note is not None:
            iss.doctor_note = doctor_note

        after_state = {
            "status": iss.status,
            "lifecycle_status": norm_lifecycle,
            "doctor_note": iss.doctor_note,
        }

        from app.services.audit_service import audit_service
        audit_service.log(
            db=db,
            actor=actor,
            action="contradiction_status_updated",
            entity_type="contradiction",
            entity_id=iss.id,
            patient_id=iss.patient_id,
            before_state=before_state,
            after_state=after_state,
            request_id=request_id,
        )

        db.commit()
        db.refresh(iss)

        return {
            "id": iss.id,
            "status": iss.status,
            "lifecycle_status": norm_lifecycle,
            "doctor_note": iss.doctor_note,
            "title": iss.title,
            "severity": iss.severity,
            "entity": details.get("entity") or iss.title,
            "conflicting_values": details.get("conflicting_values") or {},
            "source_a": details.get("source_a") or {},
            "source_b": details.get("source_b") or {},
            "dates": details.get("dates") or {},
            "evidence_spans": details.get("evidence_spans") or {},
            "authoritative_source": details.get("authoritative_source"),
            "preferred_display_order": details.get("preferred_display_order") or ["source_a", "source_b"],
            "requires_doctor_review": details.get("requires_doctor_review", False),
            "source_priority_explanation": details.get("source_priority_explanation"),
            "confidence": details.get("confidence", 1.0),
        }

    @classmethod
    def evaluate_patient_differences(
        cls,
        db: Session,
        patient_id: str
    ) -> List[DifferenceEvaluationResult]:
        """
        Evaluates differences across all clinical records for a patient using the 7 dimensions,
        classifying each into TREND, CHANGE, SUPERSESSION, CONTRADICTION, DUPLICATE, or AMBIGUOUS.
        """
        results: List[DifferenceEvaluationResult] = []

        # 1. Investigations
        invs = db.query(Investigation).filter(Investigation.patient_id == patient_id).all()
        by_test: Dict[str, List[Investigation]] = {}
        for inv in invs:
            by_test.setdefault(inv.test_name_canonical, []).append(inv)

        for test_canonical, inv_list in by_test.items():
            if len(inv_list) >= 2:
                for i in range(len(inv_list)):
                    for j in range(i + 1, len(inv_list)):
                        inv1, inv2 = inv_list[i], inv_list[j]
                        doc1 = db.query(Document).filter(Document.id == inv1.source_document_id).first() if inv1.source_document_id else None
                        doc2 = db.query(Document).filter(Document.id == inv2.source_document_id).first() if inv2.source_document_id else None
                        fact1 = db.query(ClinicalFact).filter(ClinicalFact.id == inv1.fact_id).first() if inv1.fact_id else None
                        fact2 = db.query(ClinicalFact).filter(ClinicalFact.id == inv2.fact_id).first() if inv2.fact_id else None

                        d1 = inv1.observed_date or (doc1.document_date if doc1 else None)
                        d2 = inv2.observed_date or (doc2.document_date if doc2 else None)

                        res = difference_evaluator.evaluate_investigation_difference(
                            entity=inv1.test_name_raw or test_canonical.upper(),
                            val_a=inv1.value_numeric if inv1.value_numeric is not None else inv1.value_text,
                            val_b=inv2.value_numeric if inv2.value_numeric is not None else inv2.value_text,
                            unit_a=inv1.unit,
                            unit_b=inv2.unit,
                            date_a=d1,
                            date_b=d2,
                            doc_a_meta={"document_id": doc1.id if doc1 else None, "filename": doc1.original_filename if doc1 else "Source A", "source_type": doc1.document_type if doc1 else "lab_report"},
                            doc_b_meta={"document_id": doc2.id if doc2 else None, "filename": doc2.original_filename if doc2 else "Source B", "source_type": doc2.document_type if doc2 else "lab_report"},
                            evidence_a={"fact_id": fact1.id if fact1 else None, "source_text": fact1.source_text if fact1 else None, "source_page": fact1.source_page if fact1 else None},
                            evidence_b={"fact_id": fact2.id if fact2 else None, "source_text": fact2.source_text if fact2 else None, "source_page": fact2.source_page if fact2 else None},
                            conf_a=inv1.confidence,
                            conf_b=inv2.confidence,
                        )
                        results.append(res)

        # 2. Medications
        meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        by_drug: Dict[str, List[Medication]] = {}
        for m in meds:
            by_drug.setdefault(m.canonical_name, []).append(m)

        for drug_canonical, m_list in by_drug.items():
            if len(m_list) >= 2:
                for i in range(len(m_list)):
                    for j in range(i + 1, len(m_list)):
                        m1, m2 = m_list[i], m_list[j]
                        doc1 = db.query(Document).filter(Document.id == m1.source_document_id).first() if m1.source_document_id else None
                        doc2 = db.query(Document).filter(Document.id == m2.source_document_id).first() if m2.source_document_id else None
                        fact1 = db.query(ClinicalFact).filter(ClinicalFact.id == m1.fact_id).first() if m1.fact_id else None
                        fact2 = db.query(ClinicalFact).filter(ClinicalFact.id == m2.fact_id).first() if m2.fact_id else None

                        d1 = doc1.document_date if doc1 else m1.start_date
                        d2 = doc2.document_date if doc2 else m2.start_date

                        res = difference_evaluator.evaluate_medication_difference(
                            entity=m1.canonical_name.title(),
                            dose_a=m1.dose_text or (f"{m1.strength_value:g}{m1.strength_unit or ''}" if m1.strength_value is not None else None),
                            dose_b=m2.dose_text or (f"{m2.strength_value:g}{m2.strength_unit or ''}" if m2.strength_value is not None else None),
                            freq_a=m1.frequency_text or m1.frequency_code,
                            freq_b=m2.frequency_text or m2.frequency_code,
                            route_a=m1.route,
                            route_b=m2.route,
                            status_a=m1.status,
                            status_b=m2.status,
                            date_a=d1,
                            date_b=d2,
                            doc_a_meta={"document_id": doc1.id if doc1 else None, "filename": doc1.original_filename if doc1 else "Source A", "source_type": doc1.document_type if doc1 else "prescription"},
                            doc_b_meta={"document_id": doc2.id if doc2 else None, "filename": doc2.original_filename if doc2 else "Source B", "source_type": doc2.document_type if doc2 else "prescription"},
                            evidence_a={"fact_id": fact1.id if fact1 else None, "source_text": fact1.source_text if fact1 else None, "source_page": fact1.source_page if fact1 else None},
                            evidence_b={"fact_id": fact2.id if fact2 else None, "source_text": fact2.source_text if fact2 else None, "source_page": fact2.source_page if fact2 else None},
                            conf_a=m1.confidence,
                            conf_b=m2.confidence,
                        )
                        results.append(res)

        return results

    @classmethod
    def recompute(cls, db: Session, patient_id: str) -> List[Dict[str, Any]]:
        """
        Runs rule-based detectors for contradictory clinical records using 7 dimensions.
        Preserves existing issues that doctors have already acknowledged or resolved.
        """
        existing_issues = db.query(Contradiction).filter(Contradiction.patient_id == patient_id).all()
        status_map: Dict[str, Dict[str, Any]] = {}
        for ex in existing_issues:
            fp = cls._compute_fingerprint(ex.issue_type, ex.title, patient_id)
            status_map[fp] = {
                "id": ex.id,
                "status": ex.status,
                "doctor_note": ex.doctor_note
            }

        docs = db.query(Document).filter(Document.patient_id == patient_id).all()
        facts = db.query(ClinicalFact).filter(ClinicalFact.patient_id == patient_id).all()

        detected: List[Contradiction] = []

        # 1. Diagnosis conflict: Type 1 vs Type 2 diabetes
        diag_facts = [f for f in facts if f.fact_type == "diagnosis"]
        diag_values = [f.value.lower() for f in diag_facts]
        has_t1 = any("type 1" in v for v in diag_values)
        has_t2 = any("type 2" in v for v in diag_values)
        if has_t1 and has_t2:
            f_t1 = next(f for f in diag_facts if "type 1" in f.value.lower())
            f_t2 = next(f for f in diag_facts if "type 2" in f.value.lower())
            doc_t1 = db.query(Document).filter(Document.id == f_t1.document_id).first() if f_t1.document_id else None
            doc_t2 = db.query(Document).filter(Document.id == f_t2.document_id).first() if f_t2.document_id else None

            eval_res = difference_evaluator.evaluate_diagnosis_difference(
                entity="Diabetes Mellitus",
                diag_a=f_t1.value,
                diag_b=f_t2.value,
                date_a=doc_t1.document_date if doc_t1 else None,
                date_b=doc_t2.document_date if doc_t2 else None,
                doc_a_meta={"document_id": doc_t1.id if doc_t1 else None, "filename": doc_t1.original_filename if doc_t1 else "Doc 1", "source_type": doc_t1.document_type if doc_t1 else "consultation_note"},
                doc_b_meta={"document_id": doc_t2.id if doc_t2 else None, "filename": doc_t2.original_filename if doc_t2 else "Doc 2", "source_type": doc_t2.document_type if doc_t2 else "consultation_note"},
                evidence_a={"fact_id": f_t1.id, "source_text": f_t1.source_text, "source_page": f_t1.source_page},
                evidence_b={"fact_id": f_t2.id, "source_text": f_t2.source_text, "source_page": f_t2.source_page},
                conf_a=f_t1.confidence,
                conf_b=f_t2.confidence,
            )

            title = "Contradictory Diabetes Diagnoses (Type 1 vs Type 2)"
            desc = "Patient records contain both Type 1 Diabetes and Type 2 Diabetes diagnoses across different documents."
            fp = cls._compute_fingerprint(IssueType.diagnosis_conflict.value, title, patient_id)
            prev = status_map.get(fp)

            detail_dict = eval_res.model_dump()
            detail_dict["diagnoses"] = ["Type 1 Diabetes", "Type 2 Diabetes"]
            detail_dict["status"] = prev["status"] if prev else "DETECTED"

            iss = Contradiction(
                id=prev["id"] if prev else contradiction_id(),
                patient_id=patient_id,
                issue_type=IssueType.diagnosis_conflict.value,
                severity=Severity.medium.value,
                title=title,
                description=desc,
                related_document_ids=json.dumps([d for d in [f_t1.document_id, f_t2.document_id] if d]),
                related_fact_ids=json.dumps([f_t1.id, f_t2.id]),
                detail_json=json.dumps(detail_dict),
                status=prev["status"] if prev else "open",
                doctor_note=prev["doctor_note"] if prev else None
            )
            detected.append(iss)

        # 2. Date conflicts: Document date in the future or before DOB
        now_dt = datetime.now(timezone.utc)
        for d in docs:
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
                detail_dict = {
                    "entity": "Document Date",
                    "clinical_field": "document_metadata",
                    "classification": "CONTRADICTION",
                    "reason": desc,
                    "conflicting_values": {
                        "recorded_date": doc_date.strftime("%Y-%m-%d"),
                        "current_date": now_dt.strftime("%Y-%m-%d"),
                    },
                    "source_a": {"document_id": d.id, "filename": d.original_filename, "source_type": d.document_type},
                    "source_b": {"source": "system_clock"},
                    "dates": {"recorded_date": doc_date.strftime("%Y-%m-%d"), "current_date": now_dt.strftime("%Y-%m-%d")},
                    "evidence_spans": {},
                    "confidence": 1.0,
                    "status": prev["status"] if prev else "DETECTED",
                    "date": doc_date.isoformat(),
                }
                iss = Contradiction(
                    id=prev["id"] if prev else contradiction_id(),
                    patient_id=patient_id,
                    issue_type=IssueType.date_conflict.value,
                    severity=Severity.low.value,
                    title=title,
                    description=desc,
                    related_document_ids=json.dumps([d.id]),
                    related_fact_ids=json.dumps([]),
                    detail_json=json.dumps(detail_dict),
                    status=prev["status"] if prev else "open",
                    doctor_note=prev["doctor_note"] if prev else None
                )
                detected.append(iss)

        # 3. Investigation / Lab conflicts & trends:
        invs = db.query(Investigation).filter(Investigation.patient_id == patient_id).all()
        by_test: Dict[str, List[Investigation]] = {}
        for inv in invs:
            by_test.setdefault(inv.test_name_canonical, []).append(inv)

        for test_canonical, inv_list in by_test.items():
            if len(inv_list) >= 2:
                for i in range(len(inv_list)):
                    for j in range(i + 1, len(inv_list)):
                        inv1, inv2 = inv_list[i], inv_list[j]
                        doc1 = db.query(Document).filter(Document.id == inv1.source_document_id).first() if inv1.source_document_id else None
                        doc2 = db.query(Document).filter(Document.id == inv2.source_document_id).first() if inv2.source_document_id else None
                        fact1 = db.query(ClinicalFact).filter(ClinicalFact.id == inv1.fact_id).first() if inv1.fact_id else None
                        fact2 = db.query(ClinicalFact).filter(ClinicalFact.id == inv2.fact_id).first() if inv2.fact_id else None

                        d1 = inv1.observed_date or (doc1.document_date if doc1 else None)
                        d2 = inv2.observed_date or (doc2.document_date if doc2 else None)

                        eval_res = difference_evaluator.evaluate_investigation_difference(
                            entity=inv1.test_name_raw or test_canonical.upper(),
                            val_a=inv1.value_numeric if inv1.value_numeric is not None else inv1.value_text,
                            val_b=inv2.value_numeric if inv2.value_numeric is not None else inv2.value_text,
                            unit_a=inv1.unit,
                            unit_b=inv2.unit,
                            date_a=d1,
                            date_b=d2,
                            doc_a_meta={"document_id": doc1.id if doc1 else None, "filename": doc1.original_filename if doc1 else "Source A", "source_type": doc1.document_type if doc1 else "lab_report"},
                            doc_b_meta={"document_id": doc2.id if doc2 else None, "filename": doc2.original_filename if doc2 else "Source B", "source_type": doc2.document_type if doc2 else "lab_report"},
                            evidence_a={"fact_id": fact1.id if fact1 else None, "source_text": fact1.source_text if fact1 else None, "source_page": fact1.source_page if fact1 else None},
                            evidence_b={"fact_id": fact2.id if fact2 else None, "source_text": fact2.source_text if fact2 else None, "source_page": fact2.source_page if fact2 else None},
                            conf_a=inv1.confidence,
                            conf_b=inv2.confidence,
                        )

                        # Only true CONTRADICTION is emitted (TREND and DUPLICATE are never contradictions!)
                        if eval_res.is_contradiction:
                            entity_name = eval_res.entity
                            title = f"Conflicting lab results for {entity_name}"
                            desc = eval_res.reason
                            fp = cls._compute_fingerprint(IssueType.lab_conflict.value, title, patient_id)
                            prev = status_map.get(fp)
                            detail_dict = eval_res.model_dump()
                            detail_dict["status"] = prev["status"] if prev else "DETECTED"

                            iss = Contradiction(
                                id=prev["id"] if prev else contradiction_id(),
                                patient_id=patient_id,
                                issue_type=IssueType.lab_conflict.value,
                                severity=Severity.high.value if (inv1.abnormal_flag != inv2.abnormal_flag and inv1.abnormal_flag != "unknown") else Severity.medium.value,
                                title=title,
                                description=desc,
                                related_document_ids=json.dumps([d for d in [inv1.source_document_id, inv2.source_document_id] if d]),
                                related_fact_ids=json.dumps([f for f in [inv1.fact_id, inv2.fact_id] if f]),
                                detail_json=json.dumps(detail_dict),
                                status=prev["status"] if prev else "open",
                                doctor_note=prev["doctor_note"] if prev else None
                            )
                            detected.append(iss)

        # 4. Medication conflicts & status:
        meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        by_drug: Dict[str, List[Medication]] = {}
        for m in meds:
            by_drug.setdefault(m.canonical_name, []).append(m)

        for drug_name, m_list in by_drug.items():
            if len(m_list) >= 2:
                for i in range(len(m_list)):
                    for j in range(i + 1, len(m_list)):
                        m1, m2 = m_list[i], m_list[j]
                        doc1 = db.query(Document).filter(Document.id == m1.source_document_id).first() if m1.source_document_id else None
                        doc2 = db.query(Document).filter(Document.id == m2.source_document_id).first() if m2.source_document_id else None
                        fact1 = db.query(ClinicalFact).filter(ClinicalFact.id == m1.fact_id).first() if m1.fact_id else None
                        fact2 = db.query(ClinicalFact).filter(ClinicalFact.id == m2.fact_id).first() if m2.fact_id else None

                        d1 = doc1.document_date if doc1 else m1.start_date
                        d2 = doc2.document_date if doc2 else m2.start_date

                        d1_dose = m1.dose_text or (f"{m1.strength_value:g}{m1.strength_unit or ''}" if m1.strength_value is not None else "")
                        d2_dose = m2.dose_text or (f"{m2.strength_value:g}{m2.strength_unit or ''}" if m2.strength_value is not None else "")

                        eval_res = difference_evaluator.evaluate_medication_difference(
                            entity=drug_name.title(),
                            dose_a=d1_dose,
                            dose_b=d2_dose,
                            freq_a=m1.frequency_text or m1.frequency_code,
                            freq_b=m2.frequency_text or m2.frequency_code,
                            route_a=m1.route,
                            route_b=m2.route,
                            status_a=m1.status,
                            status_b=m2.status,
                            date_a=d1,
                            date_b=d2,
                            doc_a_meta={"document_id": doc1.id if doc1 else None, "filename": doc1.original_filename if doc1 else "Document A", "source_type": doc1.document_type if doc1 else "prescription"},
                            doc_b_meta={"document_id": doc2.id if doc2 else None, "filename": doc2.original_filename if doc2 else "Document B", "source_type": doc2.document_type if doc2 else "prescription"},
                            evidence_a={"fact_id": fact1.id if fact1 else None, "source_text": fact1.source_text if fact1 else None, "source_page": fact1.source_page if fact1 else None},
                            evidence_b={"fact_id": fact2.id if fact2 else None, "source_text": fact2.source_text if fact2 else None, "source_page": fact2.source_page if fact2 else None},
                            conf_a=m1.confidence,
                            conf_b=m2.confidence,
                        )

                        # Only true CONTRADICTION is emitted (CHANGE across distinct dates is NOT a contradiction!)
                        if eval_res.is_contradiction and (m1.status == "current" or m2.status == "current"):
                            doc1_name = doc1.original_filename if doc1 else "Document A"
                            doc2_name = doc2.original_filename if doc2 else "Document B"
                            title = f"Conflicting dosage instructions for {drug_name.title()}"
                            desc = f"Different instructions for {drug_name.title()} detected across documents: {d1_dose} {m1.frequency_text or m1.frequency_code} ({doc1_name}) vs {d2_dose} {m2.frequency_text or m2.frequency_code} ({doc2_name})."
                            fp = cls._compute_fingerprint(IssueType.medication_conflict.value, title, patient_id)
                            prev = status_map.get(fp)

                            strength_diff = (m1.strength_value != m2.strength_value and m1.strength_value is not None and m2.strength_value is not None)
                            detail_dict = eval_res.model_dump()
                            detail_dict["drug"] = drug_name
                            detail_dict["source_1"] = {"doc": doc1_name, "dose": d1_dose, "freq": m1.frequency_text or m1.frequency_code}
                            detail_dict["source_2"] = {"doc": doc2_name, "dose": d2_dose, "freq": m2.frequency_text or m2.frequency_code}
                            detail_dict["status"] = prev["status"] if prev else "DETECTED"

                            iss = Contradiction(
                                id=prev["id"] if prev else contradiction_id(),
                                patient_id=patient_id,
                                issue_type=IssueType.medication_conflict.value,
                                severity=Severity.high.value if strength_diff else Severity.medium.value,
                                title=title,
                                description=desc,
                                related_document_ids=json.dumps([d for d in [m1.source_document_id, m2.source_document_id] if d]),
                                related_fact_ids=json.dumps([f for f in [m1.fact_id, m2.fact_id] if f]),
                                detail_json=json.dumps(detail_dict),
                                status=prev["status"] if prev else "open",
                                doctor_note=prev["doctor_note"] if prev else None
                            )
                            detected.append(iss)

                # Unclear active status: Drug stopped without stop date, or marked uncertain
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
                        detail_json=json.dumps({"drug": drug_name, "status": prev["status"] if prev else "DETECTED"}),
                        status=prev["status"] if prev else "open",
                        doctor_note=prev["doctor_note"] if prev else None
                    )
                    detected.append(iss)

        # Merge detected issues and update conflicting facts confidence
        for iss in detected:
            db.merge(iss)
            if iss.status in ("open", "detected", "presented", "DETECTED", "PRESENTED TO DOCTOR") and iss.related_fact_ids:
                try:
                    fids = json.loads(iss.related_fact_ids)
                    if isinstance(fids, list):
                        for fid in fids:
                            fact = db.query(ClinicalFact).filter(ClinicalFact.id == fid).first()
                            if fact and fact.verification_status != "doctor_verified":
                                from app.services.confidence_service import confidence_service
                                re_eval = confidence_service.evaluate_confidence(
                                    model_confidence=fact.confidence,
                                    provenance_verified=fact.provenance_verified,
                                    has_contradiction=True,
                                    evidence_match_level=1 if fact.provenance_verified else 4,
                                )
                                fact.confidence = re_eval.final_score
                                fact.confidence_band = re_eval.confidence_band.value
                                fact.verification_status = "conflicting"
                except Exception:
                    pass
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
