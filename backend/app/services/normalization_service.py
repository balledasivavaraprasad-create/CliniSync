from typing import Any, Dict, Optional, Tuple
from app.utils.units import (
    normalize_drug_name,
    parse_strength,
    normalize_frequency,
    canonicalize_lab_name,
    parse_numeric_value,
    parse_reference_range,
    determine_abnormal_flag
)
from app.utils.dates import parse_clinical_date

class NormalizationService:
    def normalize_medication(
        self,
        raw_name: str,
        raw_strength: Optional[str] = None,
        raw_frequency: Optional[str] = None,
        raw_start_date: Optional[str] = None,
        raw_stop_date: Optional[str] = None
    ) -> Dict[str, Any]:
        canonical_name, _ = normalize_drug_name(raw_name)
        strength_val, strength_unit = parse_strength(raw_strength) if raw_strength else (None, None)
        freq_code, freq_text = normalize_frequency(raw_frequency) if raw_frequency else ("other", None)

        start_date = None
        if raw_start_date:
            parsed, _, _ = parse_clinical_date(raw_start_date)
            start_date = parsed

        stop_date = None
        if raw_stop_date:
            parsed_stop, _, _ = parse_clinical_date(raw_stop_date)
            stop_date = parsed_stop

        return {
            "canonical_name": canonical_name,
            "raw_name": raw_name,
            "strength_value": strength_val,
            "strength_unit": strength_unit,
            "frequency_code": freq_code,
            "frequency_text": freq_text,
            "start_date": start_date,
            "stop_date": stop_date
        }

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
