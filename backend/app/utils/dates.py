from datetime import datetime, date
from typing import Optional, Tuple
from dateutil import parser


def parse_date_with_precision(
    date_str: Optional[str],
    dayfirst: bool = True,
) -> Tuple[Optional[datetime], str, bool]:
    """
    Parses date_str and returns:
    (parsed_datetime, precision: 'day'|'month'|'year'|'unknown', is_ambiguous: bool)
    """
    if not date_str or not date_str.strip():
        return None, "unknown", False

    clean_str = date_str.strip()
    try:
        # Check if year only (e.g., '2024')
        if clean_str.isdigit() and len(clean_str) == 4:
            return datetime(int(clean_str), 1, 1), "year", False

        # Attempt fuzzy parse
        parsed = parser.parse(clean_str, dayfirst=dayfirst)
        
        # Check for ambiguity in numeric slash dates like 03/04/2026
        is_ambiguous = False
        parts = [p for p in clean_str.replace("-", "/").split("/") if p.isdigit()]
        if len(parts) >= 2 and int(parts[0]) <= 12 and int(parts[1]) <= 12 and int(parts[0]) != int(parts[1]):
            is_ambiguous = True

        precision = "day"
        if len(parts) == 2:
            precision = "month"

        return parsed, precision, is_ambiguous
    except Exception:
        return None, "unknown", True


def parse_clinical_date(date_str: Optional[str], dayfirst: bool = True) -> Tuple[Optional[str], str, bool]:
    dt, prec, amb = parse_date_with_precision(date_str, dayfirst=dayfirst)
    return dt.strftime("%Y-%m-%d") if dt else None, prec, amb
