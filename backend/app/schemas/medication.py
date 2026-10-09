from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReconciliationChangeType(str, Enum):
    NEW_MEDICATION = "new_medication"
    CONTINUED = "continued"
    DOSE_CHANGE = "dose_change"
    FREQUENCY_CHANGE = "frequency_change"
    ROUTE_CHANGE = "route_change"
    DISCONTINUED = "discontinued"
    RESTARTED = "restarted"
    CONFLICTING = "conflicting"
    UNKNOWN = "unknown"


class NormalizedMedicationRecord(BaseModel):
    id: Optional[str] = None
    patient_id: Optional[str] = None
    raw_name: str
    canonical_name: str
    brand_name: Optional[str] = None
    dose: Optional[str] = None
    strength_value: Optional[float] = None
    strength_unit: Optional[str] = None
    frequency_code: Optional[str] = None
    frequency_text: Optional[str] = None
    route: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    source_document_id: Optional[str] = None
    source_document_name: Optional[str] = None
    source_date: Optional[datetime] = None
    extraction_confidence: float = 1.0
    provenance: Dict[str, Any] = Field(default_factory=dict)
    status: str = "current"  # current | previous | uncertain
    dose_semantic_state: str = "DOCUMENTED"


class MedicationHistoryStep(BaseModel):
    step_number: int
    source_document_id: Optional[str] = None
    source_document_name: Optional[str] = None
    source_date: Optional[str] = None
    raw_name: str
    canonical_name: str
    brand_name: Optional[str] = None
    dose: Optional[str] = None
    strength_value: Optional[float] = None
    strength_unit: Optional[str] = None
    frequency: Optional[str] = None
    frequency_code: Optional[str] = None
    route: Optional[str] = None
    status: str = "current"
    change_type: ReconciliationChangeType
    change_description: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0
    provenance_verified: bool = True
    dose_semantic_state: str = "DOCUMENTED"


class ReconciledMedicationTimeline(BaseModel):
    canonical_name: str
    display_name: str
    generic_name: str
    brand_names: List[str] = Field(default_factory=list)
    history: List[MedicationHistoryStep] = Field(default_factory=list)
    current_status: str  # current | discontinued | conflicting | unknown
    current_regimen: Optional[str] = None
    current_dose: Optional[str] = None
    current_frequency: Optional[str] = None
    current_route: Optional[str] = None
    latest_change_type: ReconciliationChangeType
    latest_change_reason: str
    has_conflict: bool = False
    conflict_issue_id: Optional[str] = None
    evidence_references: List[Dict[str, Any]] = Field(default_factory=list)
