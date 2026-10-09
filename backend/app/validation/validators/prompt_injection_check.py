"""Prompt injection detection, structured categorization, and untrusted document text sanitization.

Threat model:
Uploaded documents, OCR text, and voice transcripts are UNTRUSTED DATA.
They may contain attempts to:
- Override system prompts ("ignore previous instructions")
- Direct the clinician or model ("tell doctor to prescribe X")
- Impersonate system/developer messages ("<system>", "[SYSTEM]")
- Manipulate patient records or clinical memory
- Leak system prompts or execute tools

Provides:
- `analyze_prompt_injection(text: str) -> PromptInjectionResult` (safe | suspicious | blocked)
- `check_prompt_injection(text: str) -> Tuple[bool, str, str]` (Gate 1 & Gate 2 validator format)
- `sanitize_untrusted_document_text(text: str) -> str` (neutralizes delimiter escapes and injection vectors)
"""
from dataclasses import dataclass, field
import re
from typing import List, Tuple


BLOCKED_INJECTION_PATTERNS = [
    # Direct instruction overrides
    r"ignore\s+(all\s+)?(?:previous|prior|above|system)\s+(?:instructions|rules|prompts|directives)",
    r"disregard\s+(all\s+)?(?:previous|prior|above)\s+(?:instructions|rules|prompts|directives)",
    r"forget\s+(all\s+)?(?:previous|prior|above)\s+(?:rules|instructions|prompts)",
    r"override\s+(?:system\s+)?(?:instructions|rules|directives)",
    r"you\s+must\s+ignore\s+(?:previous|prior)\s+instructions",
    r"system\s*prompt\s*override",
    r"you\s+are\s+now\s+(?:an?\s+)?(?:DAN|unrestricted|jailbroken|developer mode)",
    # Adversarial document instructions & unauthorized status overrides
    r"ignore\s+(?:all\s+)?(?:previous|prior|above|system)\s+instructions\s+and\s+mark\s+(?:this\s+)?patient\s+as\s+healthy",
    r"mark\s+(?:this\s+)?patient\s+as\s+(?:healthy|cured|normal|discharged)",
    r"system\s+instruction\s*:\s*approve(?:\s+this\s+document)?",
    r"doctor\s+(?:has\s+)?approved\s+all\s+(?:information|data|records|facts|diagnoses)",
    r"approve\s+(?:this\s+)?(?:document|record|note|patient)",
    # Security bypass attempts
    r"bypass\s+(?:gate\s*[12]|validation|safety|guardrails?|all\s+verification)",
    r"mark\s+this\s+(?:evidence\s+as\s+verified|fact\s+as\s+doctor_verified)",
    r"approve\s+(?:this\s+)?(?:consultation|clinical\s+memory|memory\s+proposal)",
    r"skip\s+(?:gate\s*[12]|validation|checks)",
    # System / prompt leakage attempts
    r"(?:reveal|print|repeat|show|output|leak|dump)\b.*?\b(?:system\s+prompt|developer\s+instructions|system\s+instructions|secret|api\s*key)",
    r"(?:repeat|print)\s+the\s+instructions\s+you\s+were\s+given",
    r"what\s+(?:are|is)\s+your\s+(?:developer\s+)?(?:system\s+)?(?:prompt|instructions)\b",
    # Tool and command execution attempts
    r"(?:tool_call|call\s+(?:tool|function)|function_call)\s*[:(]",
    r"(?:execute|run)\s+(?:tool|function|command)\s*[:(]",
    r"\beval\s*\(",
    r"\bbash\s*:",
    # Tag and delimiter escape attempts
    r"</?(?:untrusted_clinical_data|document_text|untrusted_document_data|content_to_evaluate|system|developer|user|assistant)>",
    r"<script\b",
    r"javascript:",
]

SUSPICIOUS_PATTERNS = [
    # Fake authority / system impersonation
    r"(?:\[SYSTEM\]|\[DEVELOPER\]|\[ADMIN\])",
    r"<<SYS>>|<</SYS>>",
    r"SYSTEM\s+MESSAGE:",
    r"(?:^|\n)\s*system:\s*",
    r"(?:^|\n)\s*human:\s*",
    r"(?:^|\n)\s*assistant:\s*",
    r"(?:as\s+an?\s+ai\s+(?:language\s+)?model)",
    # Imperative directives disguised as clinician orders
    r"(?:tell|command|order|instruct)\s+the\s+doctor\s+to\s+(?:prescribe|administer|give|discontinue)",
    r"dr\.\s*\w+\s+(?:instructed|ordered|directive):\s*(?:automatically\s+)?(?:prescribe|administer|give)",
    r"doctor\s+directive:\s*(?:update|change|prescribe)",
    r"prescribe\s+this\s+immediately\s+without\s+review",
    r"delete\s+all\s+prior\s+(?:diagnoses|allergies|records)",
    r"curl\s+https?://",
    r"wget\s+https?://",
]


@dataclass
class PromptInjectionResult:
    status: str  # "safe" | "suspicious" | "blocked"
    matched_patterns: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    detail: str = "Clean"

    @property
    def is_safe(self) -> bool:
        return self.status == "safe"


def analyze_prompt_injection(text: str) -> PromptInjectionResult:
    """Analyze text for prompt injection and classify as safe, suspicious, or blocked."""
    if not text or not text.strip():
        return PromptInjectionResult(status="safe", matched_patterns=[], risk_score=0.0, detail="Clean")

    lower = text.lower()
    blocked_matches = []
    for pat in BLOCKED_INJECTION_PATTERNS:
        match = re.search(pat, lower, re.IGNORECASE)
        if match:
            blocked_matches.append(match.group(0))

    if blocked_matches:
        return PromptInjectionResult(
            status="blocked",
            matched_patterns=blocked_matches,
            risk_score=1.0,
            detail=f"Prompt injection blocked: detected pattern(s) {blocked_matches[:3]}",
        )

    suspicious_matches = []
    for pat in SUSPICIOUS_PATTERNS:
        match = re.search(pat, lower, re.IGNORECASE)
        if match:
            suspicious_matches.append(match.group(0))

    if suspicious_matches:
        return PromptInjectionResult(
            status="suspicious",
            matched_patterns=suspicious_matches,
            risk_score=0.6,
            detail=f"Suspicious prompt pattern detected: {suspicious_matches[:3]}",
        )

    return PromptInjectionResult(status="safe", matched_patterns=[], risk_score=0.0, detail="Clean")


def check_prompt_injection(text: str) -> Tuple[bool, str, str]:
    """Gate 1 & Gate 2 validator compatibility format.
    Returns: (passed, severity, detail)
    """
    res = analyze_prompt_injection(text)
    if res.status == "blocked":
        return False, "block", res.detail
    elif res.status == "suspicious":
        return True, "warn", res.detail
    return True, "info", "No prompt injection patterns found"


def sanitize_untrusted_document_text(text: str) -> str:
    """Sanitize and neutralize delimiter breakout attempts in untrusted text."""
    if not text:
        return ""

    # Neutralize XML tag escapes that might break prompt boundaries
    sanitized = text
    tags_to_escape = [
        "untrusted_clinical_data",
        "document_text",
        "untrusted_document_data",
        "content_to_evaluate",
        "system",
        "developer",
        "user",
        "assistant",
    ]
    for tag in tags_to_escape:
        sanitized = re.sub(rf"<{tag}\b[^>]*>", f"[{tag.upper()}_START]", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(rf"</{tag}>", f"[{tag.upper()}_END]", sanitized, flags=re.IGNORECASE)

    # Neutralize script tags
    sanitized = re.sub(r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", "[REDACTED_SCRIPT]", sanitized, flags=re.IGNORECASE)

    return sanitized
