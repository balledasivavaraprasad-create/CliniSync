from datetime import datetime
from typing import Any, Dict, List, Optional
import structlog

from app.schemas.contradiction import (
    DifferenceClassification,
    DifferenceEvaluationResult,
    ContradictionLifecycle,
)
from app.services.source_priority_policy import source_priority_policy

logger = structlog.get_logger(__name__)


class DifferenceEvaluator:
    """
    Evaluates clinical differences using:
    1. Entity identity
    2. Temporal context
    3. Source type
    4. Source date
    5. Clinical field
    6. Evidence
    7. Confidence

    Classifies differences into:
    - TREND: Longitudinal measurement change over time (e.g. HbA1c 7.1 in Jan vs 8.2 in Jun)
    - CHANGE: Regimen or symptom transition across distinct dates (e.g. Metformin 500mg in Jan vs 1000mg in Mar)
    - SUPERSESSION: Newer record explicitly replacing or revising an older record
    - CONTRADICTION: Genuine incompatible values in the same temporal context (e.g. same date)
    - DUPLICATE: Same entity and identical value
    - AMBIGUOUS: Values cannot be compared due to missing dates or low extraction confidence
    """

    @staticmethod
    def parse_date(val: Any) -> Optional[datetime]:
        if val is None:
            return None
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            val_clean = val.strip()
            try:
                return datetime.fromisoformat(val_clean.replace("Z", "+00:00"))
            except Exception:
                try:
                    from app.utils.units import parse_clinical_date
                    parsed, _, _ = parse_clinical_date(val_clean)
                    if parsed:
                        return datetime.fromisoformat(parsed)
                except Exception:
                    pass
        return None

    @staticmethod
    def _apply_source_priority(
        res: DifferenceEvaluationResult,
        doc_a_meta: Dict[str, Any],
        doc_b_meta: Dict[str, Any],
        val_a: Any,
        val_b: Any,
        date_a: Optional[str] = None,
        date_b: Optional[str] = None,
        evidence_a: Optional[Dict[str, Any]] = None,
        evidence_b: Optional[Dict[str, Any]] = None,
    ) -> DifferenceEvaluationResult:
        """
        Applies configurable source-priority hierarchy without discarding conflicting data.
        Determines authoritative source, preferred display order, and review requirements.
        """
        source_inputs = {
            "source_a": {
                **doc_a_meta,
                "value": val_a,
                "date": date_a,
                "evidence": evidence_a or {},
            },
            "source_b": {
                **doc_b_meta,
                "value": val_b,
                "date": date_b,
                "evidence": evidence_b or {},
            },
        }
        policy_res = source_priority_policy.evaluate_sources(
            entity=res.entity,
            clinical_field=res.clinical_field,
            sources=source_inputs,
            is_contradiction=res.is_contradiction,
        )
        res.authoritative_source = policy_res.authoritative_source_key
        res.preferred_display_order = policy_res.preferred_display_order
        res.requires_doctor_review = policy_res.requires_doctor_review
        res.source_priority_explanation = policy_res.explanation
        res.source_priority_metadata = policy_res.model_dump()
        return res

    def evaluate_investigation_difference(
        self,
        entity: str,
        val_a: Any,
        val_b: Any,
        unit_a: Optional[str] = None,
        unit_b: Optional[str] = None,
        date_a: Optional[Any] = None,
        date_b: Optional[Any] = None,
        doc_a_meta: Optional[Dict[str, Any]] = None,
        doc_b_meta: Optional[Dict[str, Any]] = None,
        evidence_a: Optional[Dict[str, Any]] = None,
        evidence_b: Optional[Dict[str, Any]] = None,
        conf_a: float = 1.0,
        conf_b: float = 1.0,
    ) -> DifferenceEvaluationResult:
        dt_a = self.parse_date(date_a)
        dt_b = self.parse_date(date_b)

        str_a = f"{val_a} {unit_a or ''}".strip()
        str_b = f"{val_b} {unit_b or ''}".strip()

        # Check for numeric equality if applicable
        is_same_val = False
        try:
            num_a = float(val_a)
            num_b = float(val_b)
            is_same_val = abs(num_a - num_b) < 1e-4 and (unit_a or "").lower() == (unit_b or "").lower()
        except (ValueError, TypeError):
            is_same_val = str(val_a).strip().lower() == str(val_b).strip().lower()

        doc_a_meta = doc_a_meta or {}
        doc_b_meta = doc_b_meta or {}
        evidence_a = evidence_a or {}
        evidence_b = evidence_b or {}

        min_conf = min(conf_a, conf_b)
        dates_dict = {
            "source_a_date": dt_a.strftime("%Y-%m-%d") if dt_a else None,
            "source_b_date": dt_b.strftime("%Y-%m-%d") if dt_b else None,
        }
        conflicting_vals = {"source_a": str_a, "source_b": str_b}
        evidence_spans = {"source_a": evidence_a, "source_b": evidence_b}

        # 1. Identical value -> DUPLICATE
        if is_same_val:
            res = DifferenceEvaluationResult(
                entity=entity,
                clinical_field="investigation",
                classification=DifferenceClassification.DUPLICATE,
                reason=f"Identical {entity} result ({str_a}) across records",
                conflicting_values=conflicting_vals,
                source_a=doc_a_meta,
                source_b=doc_b_meta,
                dates=dates_dict,
                evidence_spans=evidence_spans,
                confidence=min_conf,
                is_contradiction=False,
            )
            return self._apply_source_priority(res, doc_a_meta, doc_b_meta, str_a, str_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

        # 2. Low confidence -> AMBIGUOUS
        if min_conf < 0.60:
            res = DifferenceEvaluationResult(
                entity=entity,
                clinical_field="investigation",
                classification=DifferenceClassification.AMBIGUOUS,
                reason=f"Low extraction confidence ({min_conf:.2f}) for differing {entity} results: {str_a} vs {str_b}",
                conflicting_values=conflicting_vals,
                source_a=doc_a_meta,
                source_b=doc_b_meta,
                dates=dates_dict,
                evidence_spans=evidence_spans,
                confidence=min_conf,
                is_contradiction=False,
            )
            return self._apply_source_priority(res, doc_a_meta, doc_b_meta, str_a, str_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

        # 3. Differing values with distinct dates -> TREND (NOT a contradiction!)
        if dt_a and dt_b and dt_a.date() != dt_b.date():
            d1_fmt = dt_a.strftime("%Y-%m-%d")
            d2_fmt = dt_b.strftime("%Y-%m-%d")
            res = DifferenceEvaluationResult(
                entity=entity,
                clinical_field="investigation",
                classification=DifferenceClassification.TREND,
                reason=f"Longitudinal {entity} trend across dates: {str_a} ({d1_fmt}) vs {str_b} ({d2_fmt})",
                conflicting_values=conflicting_vals,
                source_a=doc_a_meta,
                source_b=doc_b_meta,
                dates=dates_dict,
                evidence_spans=evidence_spans,
                confidence=min_conf,
                is_contradiction=False,
            )
            return self._apply_source_priority(res, doc_a_meta, doc_b_meta, str_a, str_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

        # 4. Differing values on same date -> CONTRADICTION
        if dt_a and dt_b and dt_a.date() == dt_b.date():
            same_d_fmt = dt_a.strftime("%Y-%m-%d")
            doc_a_name = doc_a_meta.get("filename") or "Source A"
            doc_b_name = doc_b_meta.get("filename") or "Source B"
            res = DifferenceEvaluationResult(
                entity=entity,
                clinical_field="investigation",
                classification=DifferenceClassification.CONTRADICTION,
                reason=f"Conflicting {entity} results on the same date ({same_d_fmt}): {str_a} ({doc_a_name}) vs {str_b} ({doc_b_name})",
                conflicting_values=conflicting_vals,
                source_a=doc_a_meta,
                source_b=doc_b_meta,
                dates=dates_dict,
                evidence_spans=evidence_spans,
                confidence=min_conf,
                is_contradiction=True,
            )
            return self._apply_source_priority(res, doc_a_meta, doc_b_meta, str_a, str_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

        # 5. Missing / undated records
        # If dates are missing, flag as CONTRADICTION if confident, else AMBIGUOUS
        if dt_a is None or dt_b is None:
            if min_conf >= 0.85:
                res = DifferenceEvaluationResult(
                    entity=entity,
                    clinical_field="investigation",
                    classification=DifferenceClassification.CONTRADICTION,
                    reason=f"Conflicting {entity} results across undated records: {str_a} vs {str_b}",
                    conflicting_values=conflicting_vals,
                    source_a=doc_a_meta,
                    source_b=doc_b_meta,
                    dates=dates_dict,
                    evidence_spans=evidence_spans,
                    confidence=min_conf,
                    is_contradiction=True,
                )
                return self._apply_source_priority(res, doc_a_meta, doc_b_meta, str_a, str_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)
            res = DifferenceEvaluationResult(
                entity=entity,
                clinical_field="investigation",
                classification=DifferenceClassification.AMBIGUOUS,
                reason=f"Undated {entity} results with unverified chronology: {str_a} vs {str_b}",
                conflicting_values=conflicting_vals,
                source_a=doc_a_meta,
                source_b=doc_b_meta,
                dates=dates_dict,
                evidence_spans=evidence_spans,
                confidence=min_conf,
                is_contradiction=False,
            )
            return self._apply_source_priority(res, doc_a_meta, doc_b_meta, str_a, str_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

        res = DifferenceEvaluationResult(
            entity=entity,
            clinical_field="investigation",
            classification=DifferenceClassification.AMBIGUOUS,
            reason="Unable to determine difference relationship",
            conflicting_values=conflicting_vals,
            source_a=doc_a_meta,
            source_b=doc_b_meta,
            dates=dates_dict,
            evidence_spans=evidence_spans,
            confidence=min_conf,
            is_contradiction=False,
        )
        return self._apply_source_priority(res, doc_a_meta, doc_b_meta, str_a, str_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

    def evaluate_medication_difference(
        self,
        entity: str,
        dose_a: Optional[str],
        dose_b: Optional[str],
        freq_a: Optional[str],
        freq_b: Optional[str],
        route_a: Optional[str] = None,
        route_b: Optional[str] = None,
        status_a: str = "current",
        status_b: str = "current",
        date_a: Optional[Any] = None,
        date_b: Optional[Any] = None,
        doc_a_meta: Optional[Dict[str, Any]] = None,
        doc_b_meta: Optional[Dict[str, Any]] = None,
        evidence_a: Optional[Dict[str, Any]] = None,
        evidence_b: Optional[Dict[str, Any]] = None,
        conf_a: float = 1.0,
        conf_b: float = 1.0,
    ) -> DifferenceEvaluationResult:
        dt_a = self.parse_date(date_a)
        dt_b = self.parse_date(date_b)

        str_a = f"{dose_a or ''} {freq_a or ''} {route_a or ''}".strip()
        str_b = f"{dose_b or ''} {freq_b or ''} {route_b or ''}".strip()

        doc_a_meta = doc_a_meta or {}
        doc_b_meta = doc_b_meta or {}
        evidence_a = evidence_a or {}
        evidence_b = evidence_b or {}

        min_conf = min(conf_a, conf_b)
        dates_dict = {
            "source_a_date": dt_a.strftime("%Y-%m-%d") if dt_a else None,
            "source_b_date": dt_b.strftime("%Y-%m-%d") if dt_b else None,
        }
        conflicting_vals = {"source_a": str_a, "source_b": str_b}
        evidence_spans = {"source_a": evidence_a, "source_b": evidence_b}

        # Check difference in regimen
        dose_diff = (dose_a or "").strip().lower() != (dose_b or "").strip().lower() and bool(dose_a and dose_b)
        f_a_clean = (freq_a or "").strip().lower()
        f_b_clean = (freq_b or "").strip().lower()
        freq_diff = f_a_clean != f_b_clean and f_a_clean not in ("", "other") and f_b_clean not in ("", "other")
        route_diff = (route_a or "").strip().lower() != (route_b or "").strip().lower() and bool(route_a and route_b)
        has_regimen_diff = dose_diff or freq_diff or route_diff

        # Check supersession / discontinuation
        if dt_a and dt_b and dt_b > dt_a and status_b == "previous":
            res = DifferenceEvaluationResult(
                entity=entity,
                clinical_field="medication",
                classification=DifferenceClassification.SUPERSESSION,
                reason=f"Medication {entity} explicitly discontinued or superseded on {dt_b.strftime('%Y-%m-%d')}",
                conflicting_values=conflicting_vals,
                source_a=doc_a_meta,
                source_b=doc_b_meta,
                dates=dates_dict,
                evidence_spans=evidence_spans,
                confidence=min_conf,
                is_contradiction=False,
            )
            return self._apply_source_priority(res, doc_a_meta, doc_b_meta, str_a, str_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

        # Regimens identical -> DUPLICATE
        if not has_regimen_diff:
            res = DifferenceEvaluationResult(
                entity=entity,
                clinical_field="medication",
                classification=DifferenceClassification.DUPLICATE,
                reason=f"Consistent {entity} regimen across records ({str_a})",
                conflicting_values=conflicting_vals,
                source_a=doc_a_meta,
                source_b=doc_b_meta,
                dates=dates_dict,
                evidence_spans=evidence_spans,
                confidence=min_conf,
                is_contradiction=False,
            )
            return self._apply_source_priority(res, doc_a_meta, doc_b_meta, str_a, str_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

        # Regimens differ across distinct dates -> CHANGE (NOT a contradiction!)
        if dt_a and dt_b and dt_a.date() != dt_b.date():
            d1_fmt = dt_a.strftime("%Y-%m-%d")
            d2_fmt = dt_b.strftime("%Y-%m-%d")
            res = DifferenceEvaluationResult(
                entity=entity,
                clinical_field="medication",
                classification=DifferenceClassification.CHANGE,
                reason=f"Medication regimen change across visits: {str_a} ({d1_fmt}) to {str_b} ({d2_fmt})",
                conflicting_values=conflicting_vals,
                source_a=doc_a_meta,
                source_b=doc_b_meta,
                dates=dates_dict,
                evidence_spans=evidence_spans,
                confidence=min_conf,
                is_contradiction=False,
            )
            return self._apply_source_priority(res, doc_a_meta, doc_b_meta, str_a, str_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

        # Regimens differ on the same date or without dates -> CONTRADICTION
        same_date_str = dt_a.strftime("%Y-%m-%d") if dt_a else "undated record"
        doc_a_name = doc_a_meta.get("filename") or "Source A"
        doc_b_name = doc_b_meta.get("filename") or "Source B"
        res = DifferenceEvaluationResult(
            entity=entity,
            clinical_field="medication",
            classification=DifferenceClassification.CONTRADICTION,
            reason=f"Conflicting medication instructions on {same_date_str}: {str_a} ({doc_a_name}) vs {str_b} ({doc_b_name})",
            conflicting_values=conflicting_vals,
            source_a=doc_a_meta,
            source_b=doc_b_meta,
            dates=dates_dict,
            evidence_spans=evidence_spans,
            confidence=min_conf,
            is_contradiction=True,
        )
        return self._apply_source_priority(res, doc_a_meta, doc_b_meta, str_a, str_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

    def evaluate_diagnosis_difference(
        self,
        entity: str,
        diag_a: str,
        diag_b: str,
        date_a: Optional[Any] = None,
        date_b: Optional[Any] = None,
        doc_a_meta: Optional[Dict[str, Any]] = None,
        doc_b_meta: Optional[Dict[str, Any]] = None,
        evidence_a: Optional[Dict[str, Any]] = None,
        evidence_b: Optional[Dict[str, Any]] = None,
        conf_a: float = 1.0,
        conf_b: float = 1.0,
    ) -> DifferenceEvaluationResult:
        dt_a = self.parse_date(date_a)
        dt_b = self.parse_date(date_b)

        doc_a_meta = doc_a_meta or {}
        doc_b_meta = doc_b_meta or {}
        evidence_a = evidence_a or {}
        evidence_b = evidence_b or {}

        min_conf = min(conf_a, conf_b)
        dates_dict = {
            "source_a_date": dt_a.strftime("%Y-%m-%d") if dt_a else None,
            "source_b_date": dt_b.strftime("%Y-%m-%d") if dt_b else None,
        }
        conflicting_vals = {"source_a": diag_a, "source_b": diag_b}
        evidence_spans = {"source_a": evidence_a, "source_b": evidence_b}

        # Check if identical
        if diag_a.strip().lower() == diag_b.strip().lower():
            res = DifferenceEvaluationResult(
                entity=entity,
                clinical_field="diagnosis",
                classification=DifferenceClassification.DUPLICATE,
                reason=f"Consistent diagnosis ({diag_a}) across records",
                conflicting_values=conflicting_vals,
                source_a=doc_a_meta,
                source_b=doc_b_meta,
                dates=dates_dict,
                evidence_spans=evidence_spans,
                confidence=min_conf,
                is_contradiction=False,
            )
            return self._apply_source_priority(res, doc_a_meta, doc_b_meta, diag_a, diag_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

        # Mutually exclusive conditions (e.g. Type 1 vs Type 2 diabetes)
        d_a_low = diag_a.lower()
        d_b_low = diag_b.lower()
        is_diabetes_conflict = ("type 1" in d_a_low and "type 2" in d_b_low) or ("type 2" in d_a_low and "type 1" in d_b_low)

        if is_diabetes_conflict:
            res = DifferenceEvaluationResult(
                entity=entity,
                clinical_field="diagnosis",
                classification=DifferenceClassification.CONTRADICTION,
                reason=f"Mutually exclusive diagnoses detected across documents: {diag_a} vs {diag_b}",
                conflicting_values=conflicting_vals,
                source_a=doc_a_meta,
                source_b=doc_b_meta,
                dates=dates_dict,
                evidence_spans=evidence_spans,
                confidence=min_conf,
                is_contradiction=True,
            )
            return self._apply_source_priority(res, doc_a_meta, doc_b_meta, diag_a, diag_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)

        # Unrelated or distinct non-contradictory diagnoses
        res = DifferenceEvaluationResult(
            entity=entity,
            clinical_field="diagnosis",
            classification=DifferenceClassification.CHANGE,
            reason=f"Distinct clinical conditions noted: {diag_a} and {diag_b}",
            conflicting_values=conflicting_vals,
            source_a=doc_a_meta,
            source_b=doc_b_meta,
            dates=dates_dict,
            evidence_spans=evidence_spans,
            confidence=min_conf,
            is_contradiction=False,
        )
        return self._apply_source_priority(res, doc_a_meta, doc_b_meta, diag_a, diag_b, dates_dict["source_a_date"], dates_dict["source_b_date"], evidence_a, evidence_b)


difference_evaluator = DifferenceEvaluator()
