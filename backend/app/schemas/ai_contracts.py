from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator


class DocClassification(BaseModel):
    document_type: str = Field(..., description="prescription | lab_report | consultation_note | discharge_summary | diagnostic_report | imaging_report | referral | other | unknown")
    document_date: Optional[str] = None
    date_confidence: float = 0.0
    confidence: float = 0.0
    language: str = "en"

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "document_type" not in data and "classification" in data:
                data["document_type"] = data["classification"]
        return data


class EvidenceReference(BaseModel):
    text: str = Field(..., description="Verbatim text snippet from the document")
    page: int = Field(default=1, description="1-indexed page number")

    @model_validator(mode="before")
    @classmethod
    def validate_page(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "page" not in data or data["page"] is None:
                data["page"] = 1
            elif isinstance(data["page"], str):
                try:
                    data["page"] = int(data["page"])
                except ValueError:
                    data["page"] = 1
        return data


class ExtractionMedication(BaseModel):
    name: str
    strength: Optional[str] = None
    dose: Optional[str] = None
    frequency: Optional[str] = None
    duration: Optional[str] = None
    route: Optional[str] = None
    confidence: float = 0.9
    evidence: EvidenceReference


class ExtractionInvestigation(BaseModel):
    test: str
    value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    flag: Optional[str] = None
    date: Optional[str] = None
    confidence: float = 0.9
    evidence: EvidenceReference

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "test" not in data and "name" in data:
                data["test"] = data["name"]
        return data


class ExtractionDiagnosis(BaseModel):
    text: str
    date: Optional[str] = None
    confidence: float = 0.9
    evidence: EvidenceReference

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "text" not in data:
                data["text"] = data.get("name") or data.get("diagnosis") or ""
        return data


class ExtractionGenericItem(BaseModel):
    text: str
    confidence: float = 0.9
    evidence: EvidenceReference

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "text" not in data:
                data["text"] = data.get("description") or data.get("name") or data.get("item") or ""
        return data


class DocumentLevelDate(BaseModel):
    label: str = "document_date"
    date: str
    evidence: EvidenceReference

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "label" not in data or not data["label"]:
                data["label"] = data.get("type") or "document_date"
        return data


class ExtractionResult(BaseModel):
    medications: List[ExtractionMedication] = []
    investigations: List[ExtractionInvestigation] = []
    diagnoses: List[ExtractionDiagnosis] = []
    symptoms: List[ExtractionGenericItem] = []
    allergies: List[ExtractionGenericItem] = []
    procedures: List[ExtractionGenericItem] = []
    observations: List[ExtractionGenericItem] = []
    vitals: List[ExtractionGenericItem] = []
    document_level_dates: List[DocumentLevelDate] = []
