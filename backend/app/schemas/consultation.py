from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ConsultationFlag(BaseModel):
    text: str
    by: str = "ai"  # doctor | ai

class ConsultationContent(BaseModel):
    chief_complaint: str = ""
    history_of_present_illness: str = ""
    past_history: str = ""
    current_medications: List[Dict[str, Any]] = []
    allergies: List[Dict[str, Any]] = []
    examination: str = ""  # Left empty for doctor
    investigations_reviewed: List[Dict[str, Any]] = []
    assessment: str = ""   # Left empty for doctor
    plan: str = ""         # Left empty for doctor
    follow_up: str = ""    # Left empty for doctor
    flags: List[ConsultationFlag] = []
    evidence_ids: List[str] = []

class ConsultationCreateRequest(BaseModel):
    specialty: str = "general_medicine"
    brief_id: Optional[str] = None

class ConsultationUpdateRequest(BaseModel):
    content: Dict[str, Any]

class ConsultationVersionCreateRequest(BaseModel):
    content: Dict[str, Any]
    change_summary: Optional[str] = None

class ConsultationApproveRequest(BaseModel):
    acknowledged_unedited: bool = False
    notes: Optional[str] = None
