import re
from typing import Dict, Any, List, Tuple

def check_conflict_integrity(text: str, active_conflicts: List[Dict[str, Any]]) -> Tuple[bool, str, str]:
    """
    Enforces INV-4: If conflicts exist, output must not assert a single 'correct' resolution.
    """
    if not active_conflicts:
        return True, "info", "No active conflicts"

    lower = text.lower()
    for conf in active_conflicts:
        title = conf.get("title", "")
        desc = conf.get("description", "")
        # If text claims a conflict is resolved or asserts a single dose without mentioning discrepancy
        if "correct dose is" in lower or "take only" in lower:
            return False, "block", f"Conflict integrity violation: output attempted to unilaterally resolve a conflict: '{title}'"

    return True, "info", "Conflict integrity preserved"
