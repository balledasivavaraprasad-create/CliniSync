from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, model_validator

class BriefPatient(BaseModel):
    id: str
    name: str
    age: int

class BriefChiefComplaint(BaseModel):
    text: str
    evidence_ids: List[str] = []
    confidence_band: str = "high"

class BriefHistoryItem(BaseModel):
    text: str
    evidence_ids: List[str] = []
    confidence_band: str = "high"

class BriefMedicationItem(BaseModel):
    name: str
    strength: str = ""
    dose: str = ""
    frequency: str = ""
    status: str = "current"
    evidence_ids: List[str] = []
    confidence_band: str = "high"
    conflict_flag: bool = False

class BriefAllergyItem(BaseModel):
    text: str
    evidence_ids: List[str] = []
    status: str = "documented"  # documented | not_documented

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "text" not in data and "allergen" in data:
                data["text"] = data["allergen"]
        return data

class BriefInvestigationItem(BaseModel):
    test: str
    value: str
    unit: str = ""
    reference: str = ""
    date: str = ""
    abnormal: str = ""
    evidence_ids: List[str] = []

class BriefTrendItem(BaseModel):
    test: str
    series: List[Dict[str, Any]] = []
    direction: str = "stable"  # up | down | stable | mixed
    description: str = ""
    evidence_ids: List[str] = []

class BriefAttentionItem(BaseModel):
    text: str
    severity: str = "medium"  # low | medium | high
    evidence_ids: List[str] = []

class BriefContradictionItem(BaseModel):
    issue_id: str
    text: str
    sources: List[str] = []

class BriefMissingInfoItem(BaseModel):
    prompt: str
    reason: str

    @model_validator(mode="before")
    @classmethod
    def handle_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "prompt" not in data:
                data["prompt"] = data.get("field") or data.get("title") or "Missing information"
            if "reason" not in data:
                data["reason"] = data.get("description") or data.get("detail") or "Not documented"
        return data

class BriefEvidenceShortcut(BaseModel):
    evidence_id: str
    label: str
    document_id: str
    page: int

class DoctorBrief(BaseModel):
    patient: BriefPatient
    specialty: str = "general_medicine"
    generated_at: str
    chief_complaint: BriefChiefComplaint
    relevant_history: List[BriefHistoryItem] = []
    current_medications: List[BriefMedicationItem] = []
    allergies: List[BriefAllergyItem] = []
    recent_investigations: List[BriefInvestigationItem] = []
    important_trends: List[BriefTrendItem] = []
    attention_items: List[BriefAttentionItem] = []
    contradictions: List[BriefContradictionItem] = []
    missing_information: List[BriefMissingInfoItem] = []
    evidence_shortcuts: List[BriefEvidenceShortcut] = []
    disclaimer: str = "AI-assisted summary of source records. Not a diagnosis or treatment recommendation. Verify against sources."
    # `llm` | `fallback_template` | `seed`. Optional so briefs stored before this
    # field existed still validate; the read paths fill it in from the DB row, so
    # a client can tell a model-written brief from a deterministically assembled
    # one even when it did not generate the brief itself.
    generation_source: Optional[str] = None
