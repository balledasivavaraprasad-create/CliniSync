from typing import Any, Dict, List, Optional, Tuple, NamedTuple, Set
from enum import Enum
import re
from rapidfuzz import fuzz
from app.utils.text import verify_provenance_text
from app.config import settings


class EvidenceSupportStatus(str, Enum):
    SUPPORTS = "supports"              # Evidence supports claim
    CONTRADICTS = "contradicts"        # Evidence contradicts claim (e.g. negation, mutually exclusive)
    INSUFFICIENT = "insufficient"      # Evidence found or partially matched but insufficient to support claim
    NOT_FOUND = "not_found"            # Evidence text not found in document


class EvidenceVerificationResult(NamedTuple):
    verified: bool
    score: float
    page: Optional[int]
    span_start: Optional[int]
    span_end: Optional[int]
    unsupported_reason: Optional[str] = None
    verification_level: int = 4  # 1: Exact, 2: Fuzzy, 3: Semantic, 4: Unverified
    support_status: EvidenceSupportStatus = EvidenceSupportStatus.INSUFFICIENT
    evidence_found: bool = False
    evidence_supports_claim: bool = False
    evidence_contradicts_claim: bool = False
    evidence_insufficient: bool = False


# Negation cues commonly encountered in clinical narratives
NEGATION_PATTERNS = [
    r"\bno\s+evidence\s+of\b",
    r"\bno\s+signs?\s+of\b",
    r"\bno\s+history\s+of\b",
    r"\bno\s+report\s+of\b",
    r"\bnegative\s+for\b",
    r"\bruled?\s+out\b",
    r"\brules?\s+out\b",
    r"\bdenies\b",
    r"\bdenied\b",
    r"\bwithout\b",
    r"\bw/o\b",
    r"\bnot\s+present\b",
    r"\bnot\s+detected\b",
    r"\bnot\s+seen\b",
    r"\bnot\s+diagnosed\b",
    r"\bnot\s+identified\b",
    r"\bunremarkable\s+for\b",
    r"\bfree\s+of\b",
    r"\babsence\s+of\b",
    r"\babsent\b",
    r"\bnone\s+noted\b",
    r"\bnil\b",
    r"\bzero\b",
    r"\bno\b",
    r"\bnot\b",
]

# Modifiers indicating clinical state/severity/acuity that must not be hallucinated
CRITICAL_MODIFIERS = [
    "uncontrolled",
    "decompensated",
    "acute",
    "severe",
    "critical",
    "malignant",
    "refractory",
    "resistant",
    "end-stage",
    "stage 4",
    "stage iv",
    "active bleeding",
    "intractable",
]


class EvidenceService:
    @staticmethod
    def _extract_core_terms(text: str) -> Set[str]:
        """Extracts medical entity keywords by stripping stop words and common verbs."""
        stop_words = {
            "patient", "has", "reports", "with", "and", "the", "a", "an", "is", "was",
            "present", "presents", "noted", "diagnosed", "diagnosis", "status", "history",
            "of", "for", "in", "to", "current", "currently", "on", "evidence", "findings",
            "examination", "shows", "showed", "revealed", "reveals", "confirmed", "confirming",
        }
        tokens = re.findall(r"\b[a-z]{3,}\b", text.lower())
        return {t for t in tokens if t not in stop_words}

    def check_claim_support(
        self,
        source_text: str,
        claim_text: str,
    ) -> Tuple[EvidenceSupportStatus, bool, str]:
        """
        Evaluates whether source_text supports, contradicts, or is insufficient for claim_text.
        Returns (support_status, is_supported, reason).
        """
        if not source_text or not source_text.strip():
            return EvidenceSupportStatus.NOT_FOUND, False, "Source text is empty"
        if not claim_text or not claim_text.strip():
            return EvidenceSupportStatus.SUPPORTS, True, "Claim text is empty"

        src = source_text.strip().lower()
        clm = claim_text.strip().lower()

        core_terms = self._extract_core_terms(clm)

        # 1. Negation detection: Does source negate the core entity?
        is_source_negated = False
        negated_term = None

        for term in core_terms:
            # Check if source contains negation preceding or attached to this term
            # e.g. "no fever", "no evidence of pneumonia", "denies chest pain", "negative for covid"
            for neg_pat in NEGATION_PATTERNS:
                # Direct pattern like "no evidence of pneumonia" or "no fever"
                combined_pat = rf"{neg_pat}\s+(?:[a-z]+\s+){{0,3}}{re.escape(term)}\b"
                if re.search(combined_pat, src):
                    is_source_negated = True
                    negated_term = term
                    break
                # Suffix pattern like "pneumonia: none" or "fever: absent"
                suffix_pat = rf"\b{re.escape(term)}\s*:\s*(?:none|nil|no|negative|absent)\b"
                if re.search(suffix_pat, src):
                    is_source_negated = True
                    negated_term = term
                    break
            if is_source_negated:
                break

        # Check if the claim itself is negative (e.g. "no fever", "absence of pneumonia")
        is_claim_negated = any(re.search(rf"{neg_pat}\s+(?:[a-z]+\s+){{0,2}}{re.escape(t)}\b", clm)
                              for neg_pat in NEGATION_PATTERNS for t in core_terms)

        if is_source_negated and not is_claim_negated:
            # Source negates, claim asserts presence -> CONTRADICTION
            return (
                EvidenceSupportStatus.CONTRADICTS,
                False,
                f"Evidence explicitly negates the claim: source states '{source_text}' which contradicts claim '{claim_text}'"
            )

        if is_claim_negated and not is_source_negated and any(t in src for t in core_terms):
            # Source affirms, claim negates -> CONTRADICTION
            return (
                EvidenceSupportStatus.CONTRADICTS,
                False,
                f"Evidence contradicts negative claim: source affirms presence in '{source_text}'"
            )

        # 2. Critical Modifier / Acuity check (e.g. "history of diabetes" vs "current uncontrolled diabetes")
        for modifier in CRITICAL_MODIFIERS:
            if modifier in clm and modifier not in src:
                return (
                    EvidenceSupportStatus.INSUFFICIENT,
                    False,
                    f"Evidence states '{source_text}' does not support claim '{claim_text}': lacks required clinical modifier '{modifier}'"
                )

        # 3. Temporal mismatch (past history vs acute/current active complication)
        if "history of" in src and ("current uncontrolled" in clm or "acute" in clm):
            return (
                EvidenceSupportStatus.INSUFFICIENT,
                False,
                f"Source indicates history ('{source_text}') does not support acute claim '{claim_text}'"
            )

        # 4. Term containment & semantic overlap check
        if clm in src:
            return EvidenceSupportStatus.SUPPORTS, True, "Exact semantic containment"

        if core_terms and any(t in src for t in core_terms):
            # Term found and not negated
            sem_score = float(fuzz.partial_ratio(clm, src))
            if sem_score >= 60.0 or any(re.search(rf"\b{re.escape(t)}\b", src) for t in core_terms):
                return EvidenceSupportStatus.SUPPORTS, True, f"Positive entity match (score {sem_score:.1f})"

        # 5. Fuzzy match fallback
        fuzz_score = float(fuzz.partial_ratio(clm, src))
        if fuzz_score >= 70.0:
            return EvidenceSupportStatus.SUPPORTS, True, f"Fuzzy semantic match (score {fuzz_score:.1f})"

        return (
            EvidenceSupportStatus.INSUFFICIENT,
            False,
            f"Evidence text '{source_text}' does not support claim '{claim_text}' (score {fuzz_score:.1f})"
        )

    def verify_evidence(
        self,
        source_text: Optional[str] = None,
        page_number: Optional[int] = 1,
        pages_dict: Optional[Dict[int, str]] = None,
        expected_content: Optional[str] = None,
        document_id: Optional[str] = None,
        db: Optional[Any] = None,
        source_page: Optional[int] = None,
    ) -> EvidenceVerificationResult:
        """
        Executes layered evidence verification:
        LEVEL 1: Exact or normalized text match in document.
        LEVEL 2: Fuzzy textual match in document.
        LEVEL 3: Semantic/support & negation check.
        LEVEL 4: If evidence cannot sufficiently support the claim -> mark UNVERIFIED.

        Distinguishes:
        - Evidence found
        - Evidence supports claim
        - Evidence contradicts claim
        - Evidence insufficient
        """
        if source_page is not None:
            page_number = source_page

        if pages_dict is None:
            if db and document_id:
                from app.models.document import DocumentPage
                pages = db.query(DocumentPage).filter(DocumentPage.document_id == document_id).all()
                pages_dict = {p.page_number: p.text for p in pages}
            else:
                pages_dict = {}

        if not source_text or not source_text.strip():
            return EvidenceVerificationResult(
                verified=False,
                score=0.0,
                page=page_number,
                span_start=None,
                span_end=None,
                unsupported_reason="Empty source evidence text",
                verification_level=4,
                support_status=EvidenceSupportStatus.NOT_FOUND,
                evidence_found=False,
                evidence_supports_claim=False,
                evidence_contradicts_claim=False,
                evidence_insufficient=True,
            )

        threshold = getattr(settings, "PROVENANCE_FUZZY_THRESHOLD", 85)

        # ---------------------------------------------------------
        # LEVEL 1 & 2: Text Match in Document (Exact -> Normalized -> Fuzzy)
        # ---------------------------------------------------------
        page_text = pages_dict.get(page_number, "")
        verified, score, start_idx, end_idx = verify_provenance_text(
            source_text=source_text,
            page_text=page_text,
            threshold=threshold
        )
        resolved_page = page_number

        # Fallback to other pages if not on primary page
        if not verified:
            for p_num, p_text in pages_dict.items():
                if p_num == page_number:
                    continue
                v, s, s_idx, e_idx = verify_provenance_text(
                    source_text=source_text,
                    page_text=p_text,
                    threshold=threshold
                )
                if v:
                    verified = True
                    score = s
                    start_idx = s_idx
                    end_idx = e_idx
                    resolved_page = p_num
                    break

        # If text is not located in the document at all -> LEVEL 4 UNVERIFIED
        if not verified:
            return EvidenceVerificationResult(
                verified=False,
                score=score,
                page=page_number,
                span_start=None,
                span_end=None,
                unsupported_reason=f"Evidence text not found in document (score {score:.1f} < threshold {threshold})",
                verification_level=4,
                support_status=EvidenceSupportStatus.NOT_FOUND,
                evidence_found=False,
                evidence_supports_claim=False,
                evidence_contradicts_claim=False,
                evidence_insufficient=True,
            )

        evidence_found = True
        matched_level = 1 if score >= 99.0 else 2

        # ---------------------------------------------------------
        # LEVEL 3: Semantic / Negation / Support Check
        # ---------------------------------------------------------
        if expected_content and expected_content.strip():
            support_status, is_supported, reason = self.check_claim_support(
                source_text=source_text,
                claim_text=expected_content,
            )

            if support_status == EvidenceSupportStatus.CONTRADICTS:
                # Evidence negates the positive claim -> LEVEL 4 UNVERIFIED
                return EvidenceVerificationResult(
                    verified=False,
                    score=score,
                    page=resolved_page,
                    span_start=start_idx,
                    span_end=end_idx,
                    unsupported_reason=reason,
                    verification_level=4,
                    support_status=EvidenceSupportStatus.CONTRADICTS,
                    evidence_found=True,
                    evidence_supports_claim=False,
                    evidence_contradicts_claim=True,
                    evidence_insufficient=False,
                )

            if support_status == EvidenceSupportStatus.INSUFFICIENT:
                # Evidence is insufficient to support claim -> LEVEL 4 UNVERIFIED
                return EvidenceVerificationResult(
                    verified=False,
                    score=score,
                    page=resolved_page,
                    span_start=start_idx,
                    span_end=end_idx,
                    unsupported_reason=reason,
                    verification_level=4,
                    support_status=EvidenceSupportStatus.INSUFFICIENT,
                    evidence_found=True,
                    evidence_supports_claim=False,
                    evidence_contradicts_claim=False,
                    evidence_insufficient=True,
                )

            # Verified at Level 1, 2, or 3
            final_level = min(matched_level, 3)
            return EvidenceVerificationResult(
                verified=True,
                score=score,
                page=resolved_page,
                span_start=start_idx,
                span_end=end_idx,
                unsupported_reason=None,
                verification_level=final_level,
                support_status=EvidenceSupportStatus.SUPPORTS,
                evidence_found=True,
                evidence_supports_claim=True,
                evidence_contradicts_claim=False,
                evidence_insufficient=False,
            )

        # No expected_content given: text existence alone was requested
        return EvidenceVerificationResult(
            verified=True,
            score=score,
            page=resolved_page,
            span_start=start_idx,
            span_end=end_idx,
            unsupported_reason=None,
            verification_level=matched_level,
            support_status=EvidenceSupportStatus.SUPPORTS,
            evidence_found=True,
            evidence_supports_claim=True,
            evidence_contradicts_claim=False,
            evidence_insufficient=False,
        )


evidence_service = EvidenceService()
