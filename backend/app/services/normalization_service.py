from typing import Any, Dict, Optional, Tuple
from datetime import datetime

from app.utils.units import (
    normalize_drug_name,
    normalize_drug_name_with_brand,
    normalize_route,
    parse_strength,
    normalize_frequency,
    canonicalize_lab_name,
    parse_numeric_value,
    parse_reference_range,
    determine_abnormal_flag
)
from app.utils.dates import parse_clinical_date
from app.schemas.medication import NormalizedMedicationRecord

class NormalizationService:
    def normalize_medication(
        self,
        raw_name: str,
        raw_strength: Optional[str] = None,
        raw_frequency: Optional[str] = None,
        raw_start_date: Optional[str] = None,
        raw_stop_date: Optional[str] = None,
        raw_route: Optional[str] = None,
        source_document_id: Optional[str] = None,
        source_document_name: Optional[str] = None,
        source_date: Optional[Any] = None,
        confidence: float = 1.0,
        provenance: Optional[Dict[str, Any]] = None,
        status: str = "current",
    ) -> Dict[str, Any]:
        canonical_name, _, brand_name = normalize_drug_name_with_brand(raw_name)
        strength_val, strength_unit = parse_strength(raw_strength) if raw_strength else (None, None)
        freq_code, freq_text = normalize_frequency(raw_frequency) if raw_frequency else ("other", None)
        norm_route = normalize_route(raw_route)

        start_date = None
        if raw_start_date:
            parsed, _, _ = parse_clinical_date(raw_start_date)
            start_date = parsed

        stop_date = None
        if raw_stop_date:
            parsed_stop, _, _ = parse_clinical_date(raw_stop_date)
            stop_date = parsed_stop

        parsed_source_date = None
        if source_date:
            if isinstance(source_date, datetime):
                parsed_source_date = source_date
            elif isinstance(source_date, str):
                parsed_sd, _, _ = parse_clinical_date(source_date)
                parsed_source_date = parsed_sd

        dose_text = None
        if strength_val is not None:
            dose_text = f"{strength_val:g}{strength_unit or ''}"
        elif raw_strength:
            dose_text = raw_strength.strip()

        return {
            "canonical_name": canonical_name,
            "raw_name": raw_name,
            "brand_name": brand_name,
            "dose": dose_text,
            "strength_value": strength_val,
            "strength_unit": strength_unit,
            "frequency_code": freq_code,
            "frequency_text": freq_text or raw_frequency,
            "route": norm_route,
            "start_date": start_date,
            "stop_date": stop_date,
            "source_document_id": source_document_id,
            "source_document_name": source_document_name,
            "source_date": parsed_source_date,
            "confidence": confidence,
            "provenance": provenance or {},
            "status": status,
            "dose_semantic_state": "DOCUMENTED" if dose_text else "MISSING",
        }

    def normalize_medication_record(
        self,
        med: Any,
        doc: Optional[Any] = None,
        fact: Optional[Any] = None,
    ) -> NormalizedMedicationRecord:
        """Normalizes a Medication DB model row or dict into NormalizedMedicationRecord."""
        raw_name = getattr(med, "raw_name", None) or getattr(med, "canonical_name", "")
        canonical_name, _, brand_name = normalize_drug_name_with_brand(raw_name)

        strength_val = getattr(med, "strength_value", None)
        strength_unit = getattr(med, "strength_unit", None)
        dose_text = getattr(med, "dose_text", None)
        if dose_text is None and strength_val is not None:
            dose_text = f"{strength_val:g}{strength_unit or ''}"

        freq_code = getattr(med, "frequency_code", None)
        freq_text = getattr(med, "frequency_text", None)
        if not freq_code or freq_code == "other":
            f_code, f_text = normalize_frequency(freq_text)
            if f_code != "other":
                freq_code = f_code
                freq_text = f_text or freq_text

        route = normalize_route(getattr(med, "route", None))
        start_date = getattr(med, "start_date", None)
        end_date = getattr(med, "stop_date", None)
        status = getattr(med, "status", "current") or "current"
        confidence = getattr(med, "confidence", 1.0) or 1.0

        doc_id = getattr(med, "source_document_id", None) or (doc.id if doc else None)
        doc_name = getattr(doc, "original_filename", None) if doc else None
        source_date = getattr(doc, "document_date", None) if doc else getattr(fact, "fact_date", None)

        prov = {}
        if fact:
            prov = {
                "fact_id": fact.id,
                "source_text": getattr(fact, "source_text", None),
                "source_page": getattr(fact, "source_page", None),
                "span_start": getattr(fact, "source_span_start", None),
                "span_end": getattr(fact, "source_span_end", None),
                "provenance_verified": getattr(fact, "provenance_verified", False),
            }

        return NormalizedMedicationRecord(
            id=getattr(med, "id", None),
            patient_id=getattr(med, "patient_id", None),
            raw_name=raw_name,
            canonical_name=canonical_name,
            brand_name=brand_name,
            dose=dose_text,
            strength_value=strength_val,
            strength_unit=strength_unit,
            frequency_code=freq_code,
            frequency_text=freq_text,
            route=route,
            start_date=start_date,
            end_date=end_date,
            source_document_id=doc_id,
            source_document_name=doc_name,
            source_date=source_date,
            extraction_confidence=confidence,
            provenance=prov,
            status=status,
            dose_semantic_state="DOCUMENTED" if dose_text else "MISSING",
        )

    def normalize_investigation(
        self,
        raw_test_name: str,
        raw_value: str,
        raw_unit: Optional[str] = None,
        raw_reference_range: Optional[str] = None,
        raw_flag: Optional[str] = None,
        raw_date: Optional[str] = None
    ) -> Dict[str, Any]:
        canonical_test = canonicalize_lab_name(raw_test_name)
        numeric_val = parse_numeric_value(raw_value)
        ref_low, ref_high = parse_reference_range(raw_reference_range) if raw_reference_range else (None, None)

        abnormal = determine_abnormal_flag(numeric_val, ref_low, ref_high, raw_flag)

        observed_date = None
        if raw_date:
            parsed_d, _, _ = parse_clinical_date(raw_date)
            observed_date = parsed_d

        return {
            "test_name_canonical": canonical_test,
            "test_name_raw": raw_test_name,
            "value_numeric": numeric_val,
            "value_text": str(raw_value),
            "unit": raw_unit or "",
            "reference_low": ref_low,
            "reference_high": ref_high,
            "reference_text": raw_reference_range,
            "abnormal_flag": abnormal,
            "observed_date": observed_date
        }

    def normalize_date(self, raw_date_str: str) -> Tuple[Optional[str], str, bool]:
        """Returns (parsed_date, precision, is_ambiguous)"""
        return parse_clinical_date(raw_date_str)

normalization_service = NormalizationService()
