"""
Deterministic source-priority policy for conflicting clinical information.

Provides a configurable source hierarchy appropriate for clinical prototypes:

1. Doctor-approved consultation information (e.g. approved consultation, verified clinical memory)
2. Doctor-entered information (e.g. doctor notes, direct clinical entries)
3. Official clinical document (e.g. consultation note, discharge summary, diagnostic report)
4. Laboratory report (e.g. lab report, pathology)
5. Prescription (e.g. written/signed prescription)
6. Patient-reported information (e.g. voice intake, patient statement)
7. AI inference (e.g. unverified entity extraction, inferred diagnosis)

IMPORTANT INVARIANTS:
- NEVER silently overwrite conflicting clinical information.
- All underlying sources must be retained with full provenance.
- Determine which source is more authoritative (source priority ranking).
- Determine which source should be shown first (authoritative/preferred presentation order).
- Determine whether doctor review is required (any genuine contradiction requires doctor review).
- Configurable via `settings.SOURCE_PRIORITY_HIERARCHY` and dynamic overrides.
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.config import settings


class SourceAuthorityLevel(str, Enum):
    DOCTOR_APPROVED_CONSULTATION = "doctor_approved_consultation"
    DOCTOR_ENTERED = "doctor_entered"
    OFFICIAL_CLINICAL_DOCUMENT = "official_clinical_document"
    LAB_REPORT = "lab_report"
    PRESCRIPTION = "prescription"
    PATIENT_REPORTED = "patient_reported"
    AI_INFERENCE = "ai_inference"
    UNKNOWN = "unknown"


class SourceEvaluation(BaseModel):
    source_key: str  # identifier or key (e.g. 'source_a', 'source_b')
    label: str  # human-readable descriptor
    raw_source_type: Optional[str] = None
    authority_level: SourceAuthorityLevel
    authority_rank: int  # lower integer = higher priority (0 is highest)
    is_doctor_verified: bool = False
    evidence: Dict[str, Any] = Field(default_factory=dict)
    value: Any = None
    date: Optional[str] = None


class ConflictSourcePriorityResult(BaseModel):
    entity: str
    clinical_field: str
    is_contradiction: bool
    requires_doctor_review: bool
    authoritative_source_key: Optional[str] = None
    authoritative_level: Optional[SourceAuthorityLevel] = None
    preferred_display_order: List[str] = Field(default_factory=list)  # e.g. ['source_a', 'source_b']
    explanation: str
    sources: Dict[str, SourceEvaluation] = Field(default_factory=dict)
    retained_all_sources: bool = True


class SourcePriorityPolicy:
    """
    Evaluates source hierarchy deterministically based on configuration.
    Does not use LLMs to guess or silently discard conflicting items.
    """

    def __init__(self, hierarchy: Optional[List[str]] = None):
        self._hierarchy = hierarchy or list(settings.SOURCE_PRIORITY_HIERARCHY)

    @property
    def hierarchy(self) -> List[str]:
        return list(self._hierarchy)

    def set_hierarchy(self, hierarchy: List[str]) -> None:
        """Allows dynamic configuration or test-level adjustment."""
        self._hierarchy = list(hierarchy)

    def reset_hierarchy_to_default(self) -> None:
        self._hierarchy = list(settings.SOURCE_PRIORITY_HIERARCHY)

    def classify_source_type(
        self,
        source_type: Optional[str] = None,
        is_doctor_verified: bool = False,
        is_doctor_entered: bool = False,
        is_patient_reported: bool = False,
        is_ai_inferred: bool = False,
    ) -> SourceAuthorityLevel:
        """
        Maps source indicators to a canonical SourceAuthorityLevel.
        """
        if is_doctor_verified:
            return SourceAuthorityLevel.DOCTOR_APPROVED_CONSULTATION

        if is_doctor_entered:
            return SourceAuthorityLevel.DOCTOR_ENTERED

        if is_ai_inferred:
            return SourceAuthorityLevel.AI_INFERENCE

        if is_patient_reported:
            return SourceAuthorityLevel.PATIENT_REPORTED

        st = (source_type or "").lower().strip()

        # Doctor consultation & official summaries
        if st in ("consultation_note", "consultation", "discharge_summary", "diagnostic_report", "official_clinical_document"):
            return SourceAuthorityLevel.OFFICIAL_CLINICAL_DOCUMENT

        # Lab reports
        if st in ("lab_report", "laboratory_report", "pathology", "blood_test", "lab"):
            return SourceAuthorityLevel.LAB_REPORT

        # Prescriptions
        if st in ("prescription", "rx", "written_prescription"):
            return SourceAuthorityLevel.PRESCRIPTION

        # Patient reported
        if st in ("voice_note", "patient_reported", "patient_statement", "patient_history"):
            return SourceAuthorityLevel.PATIENT_REPORTED

        # AI inference
        if st in ("ai_inference", "inferred", "nlp_extraction", "unverified_model"):
            return SourceAuthorityLevel.AI_INFERENCE

        # Default fallback if unknown
        return SourceAuthorityLevel.UNKNOWN

    def get_authority_rank(self, level: SourceAuthorityLevel) -> int:
        """
        Returns rank index in hierarchy.
        0 = highest priority.
        If level is not found, assigns a high rank number (least authoritative).
        """
        key = level.value
        try:
            return self._hierarchy.index(key)
        except ValueError:
            return len(self._hierarchy) + 10

    def evaluate_sources(
        self,
        entity: str,
        clinical_field: str,
        sources: Dict[str, Dict[str, Any]],
        is_contradiction: bool = True,
    ) -> ConflictSourcePriorityResult:
        """
        Compares multiple sources for a clinical entity:
        - Never discards or overwrites any source.
        - Calculates authority levels and ranks.
        - Identifies the authoritative source.
        - Establishes preferred display order (most authoritative first, chronological secondary).
        - Determines if doctor review is required.
        """
        evaluated_sources: Dict[str, SourceEvaluation] = {}

        for key, s_meta in sources.items():
            st_raw = s_meta.get("source_type") or s_meta.get("document_type") or s_meta.get("type")
            is_doc_ver = bool(s_meta.get("is_doctor_verified") or s_meta.get("verified"))
            is_doc_ent = bool(s_meta.get("is_doctor_entered") or s_meta.get("doctor_entered"))
            is_pat_rep = bool(s_meta.get("is_patient_reported") or s_meta.get("patient_reported"))
            is_inferred = bool(s_meta.get("is_inferred") or s_meta.get("is_ai_inferred"))

            # Auto-detect from raw type if boolean flags not explicitly set
            if not is_doc_ver and st_raw in ("doctor_approved_consultation", "approved_consultation"):
                is_doc_ver = True
            elif not is_doc_ent and st_raw in ("doctor_entered", "doctor_note"):
                is_doc_ent = True
            elif not is_pat_rep and st_raw in ("patient_reported", "voice_intake", "voice_note"):
                is_pat_rep = True

            auth_level = self.classify_source_type(
                source_type=st_raw,
                is_doctor_verified=is_doc_ver,
                is_doctor_entered=is_doc_ent,
                is_patient_reported=is_pat_rep,
                is_ai_inferred=is_inferred,
            )
            rank = self.get_authority_rank(auth_level)

            label = s_meta.get("filename") or s_meta.get("label") or s_meta.get("doc") or key
            val = s_meta.get("value") or s_meta.get("dose") or s_meta.get("val")
            dt = s_meta.get("date") or s_meta.get("recorded_date") or s_meta.get("document_date")

            evaluated_sources[key] = SourceEvaluation(
                source_key=key,
                label=label,
                raw_source_type=st_raw,
                authority_level=auth_level,
                authority_rank=rank,
                is_doctor_verified=is_doc_ver,
                evidence=s_meta.get("evidence", {}),
                value=val,
                date=str(dt) if dt else None,
            )

        if not evaluated_sources:
            return ConflictSourcePriorityResult(
                entity=entity,
                clinical_field=clinical_field,
                is_contradiction=is_contradiction,
                requires_doctor_review=is_contradiction,
                explanation="No source records provided for priority evaluation.",
                retained_all_sources=True,
            )

        # Sort sources by rank (lower rank = higher priority), then date descending
        def sort_key(item: Tuple[str, SourceEvaluation]) -> Tuple[int, str]:
            _, eval_obj = item
            date_str = eval_obj.date or ""
            # Invert date string sort for descending order
            return (eval_obj.authority_rank, f"-{date_str}")

        sorted_items = sorted(evaluated_sources.items(), key=sort_key)
        preferred_order = [k for k, _ in sorted_items]

        top_key, top_eval = sorted_items[0]

        # Check if multiple sources share the exact top rank
        same_rank_keys = [k for k, ev in evaluated_sources.items() if ev.authority_rank == top_eval.authority_rank]
        is_tied = len(same_rank_keys) > 1

        # Doctor review is required whenever there is an open contradiction,
        # or when sources of equal authority disagree.
        requires_doctor_review = is_contradiction or is_tied

        if is_tied:
            explanation = (
                f"Conflicting records share equivalent authority level ({top_eval.authority_level.value}). "
                f"Doctor review is mandatory to resolve clinical discrepancy. Displaying in chronological/intake order."
            )
        else:
            explanation = (
                f"Source '{top_eval.label}' ({top_eval.authority_level.value}) is prioritized as more authoritative "
                f"under configured clinical source hierarchy. All conflicting sources are preserved for doctor review."
            )

        return ConflictSourcePriorityResult(
            entity=entity,
            clinical_field=clinical_field,
            is_contradiction=is_contradiction,
            requires_doctor_review=requires_doctor_review,
            authoritative_source_key=top_key,
            authoritative_level=top_eval.authority_level,
            preferred_display_order=preferred_order,
            explanation=explanation,
            sources=evaluated_sources,
            retained_all_sources=True,
        )


source_priority_policy = SourcePriorityPolicy()
