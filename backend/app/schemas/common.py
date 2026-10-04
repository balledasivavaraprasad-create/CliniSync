from enum import Enum
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class Meta(BaseModel):
    request_id: str = "req_direct"
    source: str = "db"  # db | llm | fallback


class SuccessResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    meta: Meta = Field(default_factory=Meta)



class DocumentType(str, Enum):
    prescription = "prescription"
    lab_report = "lab_report"
    consultation_note = "consultation_note"
    discharge_summary = "discharge_summary"
    diagnostic_report = "diagnostic_report"
    imaging_report = "imaging_report"
    referral = "referral"
    other = "other"
    unknown = "unknown"


class ProcessingStatus(str, Enum):
    uploaded = "uploaded"
    extracting_text = "extracting_text"
    classifying = "classifying"
    extracting_entities = "extracting_entities"
    normalizing = "normalizing"
    validating = "validating"
    complete = "complete"
    failed = "failed"
    needs_review = "needs_review"


class FactType(str, Enum):
    diagnosis = "diagnosis"
    symptom = "symptom"
    medication = "medication"
    investigation = "investigation"
    allergy = "allergy"
    procedure = "procedure"
    observation = "observation"
    vital = "vital"
    history = "history"
    social = "social"
    family_history = "family_history"
    other = "other"


class VerificationStatus(str, Enum):
    unverified = "unverified"
    needs_verification = "needs_verification"
    doctor_verified = "doctor_verified"
    doctor_rejected = "doctor_rejected"


class ConfidenceBand(str, Enum):
    high = "high"
    medium = "medium"
    needs_verification = "needs_verification"


class Severity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ConsultationOrigin(str, Enum):
    ai_generated = "ai_generated"
    doctor_edited = "doctor_edited"
    approved = "approved"


class IssueType(str, Enum):
    medication_conflict = "medication_conflict"
    date_conflict = "date_conflict"
    duplicate_record = "duplicate_record"
    unclear_medication_status = "unclear_medication_status"
    diagnosis_conflict = "diagnosis_conflict"
    low_confidence_fact = "low_confidence_fact"
    missing_information = "missing_information"


class MedStatus(str, Enum):
    current = "current"
    previous = "previous"
    uncertain = "uncertain"


class Specialty(str, Enum):
    general_medicine = "general_medicine"
    cardiology = "cardiology"
    diabetology = "diabetology"
    orthopedics = "orthopedics"
    pediatrics = "pediatrics"
    neurology = "neurology"
    other = "other"


class ValidationGate(str, Enum):
    gate1_memory = "gate1_memory"
    gate2_output = "gate2_output"


class ValidationOutcome(str, Enum):
    pass_ = "pass"
    pass_with_flags = "pass_with_flags"
    blocked = "blocked"
