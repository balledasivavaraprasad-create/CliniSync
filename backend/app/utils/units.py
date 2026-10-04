import re
from typing import Any, Optional, Tuple

# Curated Brand -> Generic dictionary
BRAND_TO_GENERIC = {
    "glycomet": "metformin",
    "glucophage": "metformin",
    "januvia": "sitagliptin",
    "zestril": "lisinopril",
    "prinivil": "lisinopril",
    "prilosec": "omeprazole",
    "norvasc": "amlodipine",
    "lipitor": "atorvastatin",
    "augmentin": "amoxicillin-clavulanate",
    "advil": "ibuprofen",
    "motrin": "ibuprofen",
    "tylenol": "acetaminophen",
    "paracetamol": "acetaminophen",
    "metformin hcl": "metformin",
    "metformin hydrochloride": "metformin",
}

# Standard Frequency mappings
FREQUENCY_MAP = {
    "od": "OD",
    "qd": "OD",
    "once daily": "OD",
    "once a day": "OD",
    "1-0-0": "OD",
    "0-1-0": "OD",
    "0-0-1": "OD",
    "bd": "BD",
    "bid": "BD",
    "twice daily": "BD",
    "twice a day": "BD",
    "1-0-1": "BD",
    "tds": "TDS",
    "tid": "TDS",
    "three times daily": "TDS",
    "1-1-1": "TDS",
    "qid": "QID",
    "four times daily": "QID",
    "1-1-1-1": "QID",
    "hs": "HS",
    "bedtime": "HS",
    "at bedtime": "HS",
    "prn": "PRN",
    "sos": "PRN",
    "as needed": "PRN",
    "weekly": "weekly",
    "once a week": "weekly",
}

# Standard Lab test canonical keys
LAB_CANONICAL_MAP = {
    "hba1c": "hba1c",
    "glycated hemoglobin": "hba1c",
    "a1c": "hba1c",
    "hemoglobin a1c": "hba1c",
    "fasting blood sugar": "fasting_glucose",
    "fasting blood glucose": "fasting_glucose",
    "fbs": "fasting_glucose",
    "postprandial blood sugar": "pp_glucose",
    "ppbs": "pp_glucose",
    "random blood sugar": "rbs",
    "rbs": "rbs",
    "serum creatinine": "creatinine",
    "creatinine": "creatinine",
    "blood urea nitrogen": "bun",
    "bun": "bun",
    "estimated gfr": "egfr",
    "egfr": "egfr",
    "total cholesterol": "total_cholesterol",
    "ldl": "ldl_cholesterol",
    "ldl cholesterol": "ldl_cholesterol",
    "hdl": "hdl_cholesterol",
    "hdl cholesterol": "hdl_cholesterol",
    "triglycerides": "triglycerides",
    "tsh": "tsh",
    "thyroid stimulating hormone": "tsh",
}


def normalize_drug_name(raw_name: str) -> Tuple[str, str]:
    """Returns (canonical_name, raw_name)"""
    clean = raw_name.strip().lower()
    # Strip salt qualifiers
    clean = re.sub(r"\b(hcl|hydrochloride|sodium|potassium|maleate|succinate)\b", "", clean).strip()
    canonical = BRAND_TO_GENERIC.get(clean, clean)
    return canonical, raw_name.strip()


def normalize_frequency(freq_text: Optional[str]) -> Tuple[str, str]:
    """Returns (code: 'OD'|'BD'|'TDS'|'QID'|'HS'|'PRN'|'weekly'|'other', raw_text)"""
    if not freq_text:
        return "other", ""
    clean = freq_text.strip().lower()
    code = FREQUENCY_MAP.get(clean, "other")
    return code, freq_text.strip()


def normalize_strength(strength_str: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """Extracts numeric value and unit from strings like '500 mg', '0.5g', '10ml'"""
    if not strength_str:
        return None, None
    match = re.search(r"([\d\.]+)\s*([a-zA-Z/%]+)", strength_str.strip())
    if match:
        try:
            val = float(match.group(1))
            unit = match.group(2).lower()
            return val, unit
        except ValueError:
            pass
    return None, None


def normalize_lab_test(test_name: str) -> str:
    """Returns canonical test key"""
    clean = test_name.strip().lower()
    return LAB_CANONICAL_MAP.get(clean, clean.replace(" ", "_"))


parse_strength = normalize_strength
canonicalize_lab_name = normalize_lab_test


def parse_numeric_value(val_str: Any) -> Optional[float]:
    if val_str is None:
        return None
    if isinstance(val_str, (int, float)):
        return float(val_str)
    match = re.search(r"[-+]?\d*\.?\d+", str(val_str).strip())
    if match:
        try:
            return float(match.group(0))
        except ValueError:
            pass
    return None


def parse_reference_range(ref_str: Optional[str]) -> Tuple[Optional[float], Optional[float]]:
    if not ref_str:
        return None, None
    clean = ref_str.strip()
    # Pattern like "4.0 - 5.6" or "70-100"
    range_match = re.search(r"([\d\.]+)\s*(?:-|to)\s*([\d\.]+)", clean, re.I)
    if range_match:
        try:
            return float(range_match.group(1)), float(range_match.group(2))
        except ValueError:
            pass
    # Pattern like "< 5.7"
    less_match = re.search(r"<\s*([\d\.]+)", clean)
    if less_match:
        try:
            return None, float(less_match.group(1))
        except ValueError:
            pass
    # Pattern like "> 60"
    greater_match = re.search(r">\s*([\d\.]+)", clean)
    if greater_match:
        try:
            return float(greater_match.group(1)), None
        except ValueError:
            pass
    return None, None


def determine_abnormal_flag(
    val: Optional[float],
    low: Optional[float],
    high: Optional[float],
    doc_flag: Optional[str] = None
) -> str:
    if val is not None:
        if low is not None and val < low:
            return "low"
        if high is not None and val > high:
            return "high"
        if (low is not None or high is not None):
            return "normal"
    if doc_flag:
        clean = doc_flag.strip().lower()
        if clean in ["high", "h", "abnormal high"]: return "high"
        if clean in ["low", "l", "abnormal low"]: return "low"
        if clean in ["normal", "n"]: return "normal"
    return "unknown"
