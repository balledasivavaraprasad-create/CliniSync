from typing import Dict, Any, List, Set, Tuple

def check_provenance(
    evidence_ids: List[str],
    valid_fact_ids: Set[str],
    unverified_fact_ids: Set[str]
) -> Tuple[bool, str, str]:
    """
    Ensures every cited evidence id exists and corresponds to a verified source fact.
    """
    if not evidence_ids:
        return False, "block", "Missing evidence citations: statement does not reference any source facts."

    for eid in evidence_ids:
        if eid not in valid_fact_ids:
            return False, "block", f"Invalid evidence citation: fact '{eid}' does not exist for this patient."
        if eid in unverified_fact_ids:
            return False, "warn", f"Evidence citation '{eid}' has unverified text provenance."

    return True, "info", "Provenance citations verified"
