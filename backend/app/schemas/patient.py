from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PatientCreate(BaseModel):
    full_name: str = Field(..., min_length=1)
    date_of_birth: Optional[str] = None
    age_years: Optional[int] = None
    sex: Optional[str] = None
    contact_ref: Optional[str] = None
    is_demo: bool = False


class PatientUpdate(BaseModel):
    full_name: Optional[str] = None
    date_of_birth: Optional[str] = None
    age_years: Optional[int] = None
    sex: Optional[str] = None
    contact_ref: Optional[str] = None


class PatientResponse(BaseModel):
    id: str
    full_name: str
    date_of_birth: Optional[str] = None
    age_years: Optional[int] = None
    sex: Optional[str] = None
    contact_ref: Optional[str] = None
    is_demo: bool
    last_activity_at: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class PatientOverviewResponse(BaseModel):
    patient: PatientResponse
    source_count: int
    latest_brief: Optional[Dict[str, Any]] = None
    attention_items: List[Dict[str, Any]] = []
    timeline_preview: List[Dict[str, Any]] = []
    current_medications: List[Dict[str, Any]] = []
    latest_investigations: List[Dict[str, Any]] = []
    memory_summary: List[Dict[str, Any]] = []
    open_issue_counts: Dict[str, int] = {}
