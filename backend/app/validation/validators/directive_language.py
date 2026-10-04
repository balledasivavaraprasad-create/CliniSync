import re
from typing import Dict, Any, Tuple

DIRECTIVE_PATTERNS = [
    r"\b(start|stop|increase|decrease|reduce|titrate|prescribe|discontinue)\s+(tab|tablet|cap|capsule|metformin|insulin|dose|\d+\s*mg)\b",
    r"\byou should\s+(take|start|stop|increase|reduce|prescribe)\b",
    r"\brecommend(ed)?\s+(starting|stopping|taking|increasing|reducing|prescribing)\b",
    r"\bpatient must take\b",
    r"\bincrease\s+[A-Za-z0-9]+\s+to\s+\d+",
    r"\bpatient should be started on\b",
]

def check_directive_language(text: str) -> Tuple[bool, str, str]:
    """
    Enforces INV-7: Generated text must NEVER contain treatment directives.
    Returns (passed, severity, detail_message).
    """
    if not text:
        return True, "info", "No text to check"

    lower_text = text.lower()
    for pattern in DIRECTIVE_PATTERNS:
        match = re.search(pattern, lower_text)
        if match:
            return False, "block", f"Prohibited directive language detected: '{match.group(0)}'"

    return True, "info", "No directive language detected"
