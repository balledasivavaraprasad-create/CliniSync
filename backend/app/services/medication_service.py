from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, func, or_
import json
import structlog

from app.models.medication import Medication
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.contradiction import Contradiction
from app.models.timeline_event import TimelineEvent
from app.schemas.common import IssueType, Severity, MedStatus
from app.schemas.medication import (
    ReconciliationChangeType,
    NormalizedMedicationRecord,
    MedicationHistoryStep,
    ReconciledMedicationTimeline,
)
from app.services.normalization_service import normalization_service
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
                    Contradiction.status.in_(["open", "detected", "presented"]),
                ).filter(
                    or_(
                        func.lower(Contradiction.description).contains(key.lower()),
                        func.lower(Contradiction.title).contains(key.lower()),
                        Contradiction.related_fact_ids.contains(m.fact_id if m.fact_id else "___"),
                    )
                ).all()

                grouped[key] = {
                    "id": m.id,
                    "patient_id": m.patient_id,
                    "canonical_name": m.canonical_name,
                    # `group_key` is the column the history endpoint keys on,
                    # and the list payload was omitting it, so a client had to
                    # guess that `canonical_name` would work as the key
                    # (docs/frontend/API_MISMATCHES.md M-07). It is emitted
                    # alongside the existing fields, so nothing breaks.
                    "group_key": m.group_key or m.canonical_name,
                    "raw_name": m.raw_name,
                    "strength_value": m.strength_value,
                    "strength_unit": m.strength_unit,
                    "dose_text": m.dose_text,
                    "frequency_code": m.frequency_code,
                    "frequency_text": m.frequency_text,
                    "route": m.route,
                    "duration_text": m.duration_text,
                    "start_date": m.start_date.isoformat() if m.start_date else None,
                    "stop_date": m.stop_date.isoformat() if m.stop_date else None,
                    "status": m.status,
                    "status_reason": m.status_reason,
                    "confidence": min(m.confidence, 0.45) if len(conflicts) > 0 else m.confidence,
                    "confidence_band": "needs_verification" if len(conflicts) > 0 else ("high" if m.confidence >= 0.85 else ("medium" if m.confidence >= 0.60 else "needs_verification")),
                    "source_document_id": m.source_document_id,
                    "conflict_ids": [c.id for c in conflicts],
                    "has_conflict": len(conflicts) > 0,
                    "semantic_state": "CONFLICTING" if len(conflicts) > 0 else ("DOCUMENTED" if m.confidence >= 0.85 else "UNVERIFIED"),
                    "dose_semantic_state": "DOCUMENTED" if (m.dose_text or m.strength_value is not None) else "MISSING",
                    "history_count": 1
                }
            else:
                grouped[key]["history_count"] += 1

        return list(grouped.values())

    @classmethod
    def reconcile_patient_medications(
        cls,
        db: Session,
        patient_id: str
    ) -> List[Dict[str, Any]]:
        """
        Builds a comprehensive chronological reconciliation history for every medication
        taken by the patient, identifying transitions:
        - new_medication
        - continued
        - dose_change
        - frequency_change
        - route_change
        - discontinued
        - restarted
        - conflicting
        - unknown
        
        Preserves provenance and evidence references on every decision.
        """
        meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        if not meds:
            return []

        # 1. Normalize each medication record
        norm_records: List[tuple] = []
        for m in meds:
            doc = db.query(Document).filter(Document.id == m.source_document_id).first() if m.source_document_id else None
            fact = db.query(ClinicalFact).filter(ClinicalFact.id == m.fact_id).first() if m.fact_id else None
            norm = normalization_service.normalize_medication_record(m, doc=doc, fact=fact)
            norm_records.append((m, norm))

        # 2. Group by canonical name
        grouped: Dict[str, List[tuple]] = {}
        for m, norm in norm_records:
            grouped.setdefault(norm.canonical_name, []).append((m, norm))

        reconciled_timelines: List[Dict[str, Any]] = []

        for canonical_name, items in sorted(grouped.items(), key=lambda x: x[0]):
            def sort_key(item):
                m_obj, n_rec = item
                dt = n_rec.source_date or n_rec.start_date or (m_obj.created_at if m_obj else None) or datetime.min
                if dt and hasattr(dt, "tzinfo") and dt.tzinfo is not None:
                    dt = dt.replace(tzinfo=None)
                return (dt or datetime.min, m_obj.id if m_obj else "")

            sorted_items = sorted(items, key=sort_key)

            steps: List[MedicationHistoryStep] = []
            has_group_conflict = False

            # Check if there is an open contradiction in DB for this drug
            open_conflict = db.query(Contradiction).filter(
                Contradiction.patient_id == patient_id,
                Contradiction.issue_type == IssueType.medication_conflict.value,
                Contradiction.status == "open",
                Contradiction.description.contains(canonical_name)
            ).first()

            for idx, (m_obj, rec) in enumerate(sorted_items):
                step_num = idx + 1
                ev = {
                    "source_document_id": rec.source_document_id,
                    "source_document_name": rec.source_document_name,
                    "source_date": rec.source_date.strftime("%Y-%m-%d") if rec.source_date else None,
                    "source_text": rec.provenance.get("source_text"),
                    "source_page": rec.provenance.get("source_page"),
                    "fact_id": rec.provenance.get("fact_id"),
                    "confidence": rec.extraction_confidence,
                    "provenance_verified": rec.provenance.get("provenance_verified", True),
                }

                if idx == 0:
                    change_type = ReconciliationChangeType.NEW_MEDICATION
                    brand_part = f" ({rec.brand_name})" if rec.brand_name else ""
                    dose_part = rec.dose or "undocumented dose"
                    freq_part = f" {rec.frequency_text or rec.frequency_code}" if (rec.frequency_text or rec.frequency_code) else ""
                    route_part = f" via {rec.route}" if rec.route else ""
                    doc_part = f" in {rec.source_document_name}" if rec.source_document_name else ""
                    change_desc = f"Initial prescription: {rec.canonical_name.title()}{brand_part} {dose_part}{freq_part}{route_part}{doc_part}".strip()
                else:
                    prev_m, prev_rec = sorted_items[idx - 1]
                    d_prev = prev_rec.source_date.date() if prev_rec.source_date else None
                    d_curr = rec.source_date.date() if rec.source_date else None
                    is_same_date = (d_prev is not None and d_curr is not None and d_prev == d_curr) or (d_prev is None and d_curr is None)

                    strength_diff = (
                        rec.strength_value != prev_rec.strength_value
                        and rec.strength_value is not None
                        and prev_rec.strength_value is not None
                    )
                    dose_text_diff = (
                        rec.dose != prev_rec.dose
                        and rec.dose is not None
                        and prev_rec.dose is not None
                        and (rec.strength_value is None or prev_rec.strength_value is None)
                    )
                    dose_diff = strength_diff or dose_text_diff

                    p_freq = (prev_rec.frequency_code or prev_rec.frequency_text or "").lower().strip()
                    c_freq = (rec.frequency_code or rec.frequency_text or "").lower().strip()
                    freq_diff = (
                        p_freq != c_freq
                        and p_freq not in ("", "other")
                        and c_freq not in ("", "other")
                    )

                    route_diff = (
                        rec.route != prev_rec.route
                        and rec.route is not None
                        and prev_rec.route is not None
                    )

                    if is_same_date and (dose_diff or freq_diff) and (rec.status == "current" or prev_rec.status == "current"):
                        change_type = ReconciliationChangeType.CONFLICTING
                        has_group_conflict = True
                        doc_p = prev_rec.source_document_name or "Record 1"
                        doc_c = rec.source_document_name or "Record 2"
                        change_desc = (
                            f"Conflicting instructions on {d_curr.strftime('%Y-%m-%d') if d_curr else 'undated record'}: "
                            f"{prev_rec.raw_name} {prev_rec.dose or ''} {prev_rec.frequency_text or prev_rec.frequency_code or ''} ({doc_p}) vs "
                            f"{rec.raw_name} {rec.dose or ''} {rec.frequency_text or rec.frequency_code or ''} ({doc_c})"
                        )
                    elif rec.status == "previous" or (rec.end_date and rec.end_date <= (rec.source_date or datetime.now())):
                        change_type = ReconciliationChangeType.DISCONTINUED
                        change_desc = f"{rec.canonical_name.title()} discontinued"
                    elif prev_rec.status == "previous" and rec.status == "current":
                        change_type = ReconciliationChangeType.RESTARTED
                        change_desc = f"{rec.canonical_name.title()} restarted at {rec.dose or ''} {rec.frequency_text or rec.frequency_code or ''} {rec.route or ''}".strip()
                    elif rec.status == "uncertain":
                        change_type = ReconciliationChangeType.UNKNOWN
                        change_desc = f"Current status uncertain for {rec.canonical_name.title()}"
                    elif dose_diff:
                        change_type = ReconciliationChangeType.DOSE_CHANGE
                        change_desc = f"Dose changed from {prev_rec.dose or prev_rec.strength_value} to {rec.dose or rec.strength_value}"
                    elif freq_diff:
                        change_type = ReconciliationChangeType.FREQUENCY_CHANGE
                        change_desc = f"Frequency changed from {prev_rec.frequency_text or prev_rec.frequency_code} to {rec.frequency_text or rec.frequency_code}"
                    elif route_diff:
                        change_type = ReconciliationChangeType.ROUTE_CHANGE
                        change_desc = f"Route changed from {prev_rec.route} to {rec.route}"
                    else:
                        change_type = ReconciliationChangeType.CONTINUED
                        change_desc = f"Continued current regimen ({rec.dose or ''} {rec.frequency_text or rec.frequency_code or ''})".strip()

                step = MedicationHistoryStep(
                    step_number=step_num,
                    source_document_id=rec.source_document_id,
                    source_document_name=rec.source_document_name,
                    source_date=rec.source_date.strftime("%Y-%m-%d") if rec.source_date else None,
                    raw_name=rec.raw_name,
                    canonical_name=rec.canonical_name,
                    brand_name=rec.brand_name,
                    dose=rec.dose,
                    strength_value=rec.strength_value,
                    strength_unit=rec.strength_unit,
                    frequency=rec.frequency_text or rec.frequency_code,
                    frequency_code=rec.frequency_code,
                    route=rec.route,
                    status=rec.status,
                    change_type=change_type,
                    change_description=change_desc,
                    evidence=ev,
                    confidence=rec.extraction_confidence,
                    provenance_verified=rec.provenance.get("provenance_verified", True),
                    dose_semantic_state=rec.dose_semantic_state,
                )
                steps.append(step)

            last_m, last_rec = sorted_items[-1]
            if has_group_conflict or open_conflict is not None:
                current_status = "conflicting"
                has_group_conflict = True
            elif steps[-1].change_type == ReconciliationChangeType.DISCONTINUED or last_rec.status == "previous":
                current_status = "discontinued"
            elif steps[-1].change_type == ReconciliationChangeType.UNKNOWN or last_rec.status == "uncertain":
                current_status = "unknown"
            else:
                current_status = "current"

            brand_names = sorted(list({r.brand_name for _, r in sorted_items if r.brand_name}))
            display_name = last_rec.raw_name or canonical_name.title()

            regimen_parts = [p for p in [last_rec.dose, last_rec.frequency_text or last_rec.frequency_code, last_rec.route] if p]
            current_regimen = " ".join(regimen_parts) if regimen_parts else None

            timeline = ReconciledMedicationTimeline(
                canonical_name=canonical_name,
                display_name=display_name,
                generic_name=canonical_name,
                brand_names=brand_names,
                history=steps,
                current_status=current_status,
                current_regimen=current_regimen,
                current_dose=last_rec.dose,
                current_frequency=last_rec.frequency_text or last_rec.frequency_code,
                current_route=last_rec.route,
                latest_change_type=steps[-1].change_type,
                latest_change_reason=steps[-1].change_description,
                has_conflict=has_group_conflict,
                conflict_issue_id=open_conflict.id if open_conflict else None,
                evidence_references=[
                    s.evidence for s in steps
                    if s.evidence.get("source_document_id") or s.evidence.get("source_text") or s.evidence.get("fact_id")
                ],
            )
            reconciled_timelines.append(timeline.model_dump())

        return reconciled_timelines

    @classmethod
    def get_medication_history(
        cls,
        db: Session,
        patient_id: str,
        group_key: str
    ) -> List[Dict[str, Any]]:
        meds = db.query(Medication).filter(
            Medication.patient_id == patient_id,
            (Medication.group_key == group_key) | (Medication.canonical_name == group_key)
        ).order_by(desc(Medication.created_at)).all()

        # Build timeline steps to enrich records
        timelines = cls.reconcile_patient_medications(db, patient_id)
        step_by_id = {}
        for tl in timelines:
            for st in tl.get("history", []):
                ev = st.get("evidence", {})
                f_id = ev.get("fact_id")
                if f_id:
                    step_by_id[f_id] = st

        results = []
        for m in meds:
            doc = db.query(Document).filter(Document.id == m.source_document_id).first() if m.source_document_id else None
            st = step_by_id.get(m.fact_id)
            results.append({
                "id": m.id,
                "canonical_name": m.canonical_name,
                "raw_name": m.raw_name,
                "dose_text": m.dose_text,
                "strength_value": m.strength_value,
                "strength_unit": m.strength_unit,
                "frequency_code": m.frequency_code,
                "frequency_text": m.frequency_text,
                "route": m.route,
                "status": m.status,
                "semantic_state": m.semantic_state,
                "dose_semantic_state": m.dose_semantic_state,
                "change_type": st.get("change_type") if st else None,
                "change_description": st.get("change_description") if st else None,
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
                                    "entity": drug_name.title(),
                                    "clinical_field": "medication",
                                    "difference_class": "CONTRADICTION",
                                    "conflicting_values": {
                                        "source_a": f"{m1.raw_name} {m1.strength_value or ''}{m1.strength_unit or ''} {m1.frequency_text or m1.frequency_code}".strip(),
                                        "source_b": f"{m2.raw_name} {m2.strength_value or ''}{m2.strength_unit or ''} {m2.frequency_text or m2.frequency_code}".strip(),
                                    },
                                    "source_a": {"document_id": doc1.id if doc1 else None, "filename": doc1_name, "date": d1.strftime("%Y-%m-%d") if d1 else None, "source_type": getattr(doc1, "document_type", "prescription")},
                                    "source_b": {"document_id": doc2.id if doc2 else None, "filename": doc2_name, "date": d2.strftime("%Y-%m-%d") if d2 else None, "source_type": getattr(doc2, "document_type", "prescription")},
                                    "dates": {"source_a_date": d1.strftime("%Y-%m-%d") if d1 else None, "source_b_date": d2.strftime("%Y-%m-%d") if d2 else None},
                                    "evidence_spans": {"source_a": {"fact_id": m1.fact_id}, "source_b": {"fact_id": m2.fact_id}},
                                    "confidence": min(m1.confidence, m2.confidence),
                                    "status": "DETECTED",
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
