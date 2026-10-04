from typing import Optional, Tuple
from rapidfuzz import fuzz


def verify_provenance_text(
    source_text: str,
    page_text: str,
    threshold: int = 85,
) -> Tuple[bool, float, Optional[int]]:
    """
    Verifies if source_text is present in page_text via exact or fuzzy substring search.
    Returns (is_verified, score, match_start_index).
    """
    if not source_text or not page_text:
        return False, 0.0, None

    clean_source = source_text.strip().lower()
    clean_page = page_text.strip().lower()

    # Exact substring check
    exact_idx = clean_page.find(clean_source)
    if exact_idx != -1:
        return True, 100.0, exact_idx

    # Fuzzy partial ratio match
    score = fuzz.partial_ratio(clean_source, clean_page)
    is_verified = score >= threshold
    return is_verified, float(score), None
