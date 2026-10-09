import re
from typing import Tuple

CAUSAL_PATTERNS = [
    r"\bdue to\s+(metformin|insulin|medication|drug|treatment|dose)\b",
    r"\bcaused by\s+(metformin|insulin|medication|drug|treatment|dose)\b",
    r"\bbecause of\s+(metformin|insulin|medication|drug|treatment|dose)\b",
    r"\bresulting from\s+(metformin|insulin|medication|drug|treatment|dose)\b",
    r"\bleading to (an? )?(improvement|increase|decrease|reduction) in\b",
    r"\b(improved|normalized|worsened)\s+(due to|because of|by)\s+[A-Za-z0-9]+\b",
]

def check_causality_language(text: str) -> Tuple[bool, str, str]:
    """
    Enforces INV-6: Generated text must NEVER assert causal relationships between treatments and outcomes.
    Returns (passed, severity, detail_message).
    """
    if not text:
        return True, "info", "No text to check"

    lower_text = text.lower()
    for pattern in CAUSAL_PATTERNS:
        match = re.search(pattern, lower_text)
        if match:
            return False, "block", f"Prohibited clinical causality assertion detected: '{match.group(0)}'"

    return True, "info", "No prohibited causal assertions detected"
