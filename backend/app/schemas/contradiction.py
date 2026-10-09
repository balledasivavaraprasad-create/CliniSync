from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DifferenceClassification(str, Enum):
    TREND = "TREND"
    CHANGE = "CHANGE"
    SUPERSESSION = "SUPERSESSION"
    CONTRADICTION = "CONTRADICTION"
    DUPLICATE = "DUPLICATE"
    AMBIGUOUS = "AMBIGUOUS"


class ContradictionLifecycle(str, Enum):
    DETECTED = "DETECTED"
    PRESENTED_TO_DOCTOR = "PRESENTED TO DOCTOR"
    DOCTOR_RESOLVES = "DOCTOR RESOLVES"
    RESOLVED = "RESOLVED"


class EvidenceSpan(BaseModel):
    fact_id: Optional[str] = None
    source_text: Optional[str] = None
    source_page: Optional[int] = None
    span_start: Optional[int] = None
    span_end: Optional[int] = None
    confidence: Optional[float] = None
    provenance_verified: bool = True


class SourceMetadata(BaseModel):
    document_id: Optional[str] = None
    filename: Optional[str] = None
    date: Optional[str] = None
    source_type: Optional[str] = None


class DifferenceEvaluationResult(BaseModel):
    entity: str
    clinical_field: str  # investigation | medication | diagnosis | document_metadata
    classification: DifferenceClassification
    reason: str
    conflicting_values: Dict[str, Any] = Field(default_factory=dict)
    source_a: Dict[str, Any] = Field(default_factory=dict)
    source_b: Dict[str, Any] = Field(default_factory=dict)
    dates: Dict[str, Optional[str]] = Field(default_factory=dict)
    evidence_spans: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    status: ContradictionLifecycle = ContradictionLifecycle.DETECTED
    is_contradiction: bool = False
    # Source authority and priority policy fields
    authoritative_source: Optional[str] = None  # e.g. 'source_a' or 'source_b'
    preferred_display_order: List[str] = Field(default_factory=list)
    requires_doctor_review: bool = False
    source_priority_explanation: Optional[str] = None
    source_priority_metadata: Dict[str, Any] = Field(default_factory=dict)
