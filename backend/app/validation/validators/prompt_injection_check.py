import re
from typing import Tuple

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+(all\s+)?(prior|previous)\s+(instructions|directives)",
    r"you\s+are\s+now\s+(an?\s+)?unrestricted",
    r"as\s+an?\s+ai\s+(language\s+)?model",
    r"<script\b",
    r"curl\s+http",
    r"wget\s+http",
    r"system\s*prompt\s*override",
]

def check_prompt_injection(text: str) -> Tuple[bool, str, str]:
    if not text:
        return True, "info", "Clean"

    lower = text.lower()
    for pat in INJECTION_PATTERNS:
        match = re.search(pat, lower)
        if match:
            return False, "block", f"Potential prompt injection pattern detected: '{match.group(0)}'"

    return True, "info", "No prompt injection patterns found"
