from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: str
    patient_id: str
    original_filename: str
    mime_type: str
    file_size: int
    sha256: str
    page_count: int
    document_type: str
    document_date: Optional[datetime] = None
    classification_confidence: float
    processing_status: str
    processing_error_code: Optional[str] = None
    ocr_method: str
    is_fallback: bool
    uploaded_via: str
    created_at: datetime
    duplicate: bool = False

    class Config:
        from_attributes = True


class DocumentPageResponse(BaseModel):
    page_number: int
    text: str
    ocr_confidence: float
    method: str

    class Config:
        from_attributes = True


class DocumentStatusResponse(BaseModel):
    document_id: str
    status: str
    current_stage: str
    stages: List[dict]
    error_code: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    retry_count: int = 0
    failure_reason: Optional[str] = None
    error_detail: Optional[str] = None

    class Config:
        from_attributes = True
