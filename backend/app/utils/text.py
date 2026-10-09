import re
from typing import Optional, Tuple
from rapidfuzz import fuzz


def verify_provenance_text(
    source_text: str,
    page_text: str,
    threshold: int = 85,
) -> Tuple[bool, float, Optional[int], Optional[int]]:
    """
    Verifies if source_text is present in page_text via exact or fuzzy substring search.
    Returns (is_verified, score, match_start_index, match_end_index).
    """
    if not source_text or not page_text:
        return False, 0.0, None, None

    clean_source = source_text.strip()
    if not clean_source:
        return False, 0.0, None, None

    # 1. Exact substring check
    exact_idx = page_text.lower().find(clean_source.lower())
    if exact_idx != -1:
        return True, 100.0, exact_idx, exact_idx + len(clean_source)

    # 2. Whitespace-normalized token regex check (handles multi-spaces, newlines, tabs from OCR)
    tokens = [re.escape(t) for t in clean_source.split() if t]
    if tokens:
        pattern = r"\s+".join(tokens)
        m = re.search(pattern, page_text, re.IGNORECASE)
        if m:
            return True, 100.0, m.start(), m.end()

    # 3. Fuzzy partial ratio match with alignment span
    try:
        alignment = fuzz.partial_ratio_alignment(clean_source.lower(), page_text.lower())
        if alignment and alignment.score >= threshold:
            # Snap start/end to word boundaries
            start = alignment.dest_start
            while start > 0 and page_text[start - 1].isalnum():
                start -= 1
            end = alignment.dest_end
            while end < len(page_text) and page_text[end].isalnum():
                end += 1
            return True, float(alignment.score), start, end
        score = float(alignment.score) if alignment else float(fuzz.partial_ratio(clean_source.lower(), page_text.lower()))
    except Exception:
        score = float(fuzz.partial_ratio(clean_source.lower(), page_text.lower()))

    is_verified = score >= threshold
    return is_verified, score, None, None
