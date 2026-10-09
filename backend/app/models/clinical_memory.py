import json

from sqlalchemy import Boolean, Column, ForeignKey, String, Text, Index
from sqlalchemy.orm import relationship
from app.db.database import Base
from app.models.base import TimestampMixin
from app.utils.ids import memory_id


class ClinicalMemory(Base, TimestampMixin):
    __tablename__ = "clinical_memory"

    id = Column(String(32), primary_key=True, default=memory_id)
    patient_id = Column(String(32), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    memory_type = Column(String(64), nullable=False)  # diagnosis | medication | allergy | history | investigation_summary | plan_note
    content_json = Column(Text, nullable=False)
    source_consultation_id = Column(String(32), ForeignKey("consultations.id", ondelete="SET NULL"), nullable=True, index=True)
    source_version_id = Column(String(32), ForeignKey("consultation_versions.id", ondelete="SET NULL"), nullable=True, index=True)
    verified = Column(Boolean, default=True, nullable=False)
    validation_report_id = Column(String(32), ForeignKey("validation_reports.id", ondelete="SET NULL"), nullable=True, index=True)
    supersedes_id = Column(String(32), ForeignKey("clinical_memory.id", ondelete="SET NULL"), nullable=True, index=True)

    __table_args__ = (
        Index("ix_clinical_memory_patient_type", "patient_id", "memory_type"),
        Index("ix_clinical_memory_patient_verified", "patient_id", "verified"),
    )

    patient = relationship("Patient", back_populates="clinical_memories")
    source_consultation = relationship("Consultation", foreign_keys=[source_consultation_id])
    source_version = relationship("ConsultationVersion", foreign_keys=[source_version_id])
    validation_report = relationship("ValidationReport", foreign_keys=[validation_report_id])
    supersedes = relationship("ClinicalMemory", remote_side=[id], foreign_keys=[supersedes_id])

    @property
    def payload(self) -> dict:
        if self.content_json:
            try:
                data = json.loads(self.content_json)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
        return {}

    @property
    def semantic_state(self) -> str:
        data = self.payload
        if "semantic_state" in data:
            return str(data["semantic_state"]).upper()
        if "status" in data and str(data["status"]).upper() in ("DOCUMENTED", "INFERRED", "UNVERIFIED", "CONFLICTING", "MISSING", "UNKNOWN", "CURRENT", "HISTORICAL", "SUPERSEDED"):
            return str(data["status"]).upper()
        return "DOCUMENTED" if self.verified else "UNVERIFIED"

    @property
    def memory_state(self) -> str:
        """Resolves the clinical memory lifecycle state:

        CURRENT, HISTORICAL, SUPERSEDED, CONFLICTING, UNVERIFIED.
        """
        data = self.payload
        # If explicitly marked in content
        explicit_state = data.get("memory_state") or data.get("lifecycle_state")
        if explicit_state and str(explicit_state).upper() in ("CURRENT", "HISTORICAL", "SUPERSEDED", "CONFLICTING", "UNVERIFIED"):
            return str(explicit_state).upper()

        if not self.verified:
            return "UNVERIFIED"

        if data.get("conflict_flag") or data.get("conflicting") or self.semantic_state == "CONFLICTING":
            return "CONFLICTING"

        # If this item has been superseded by another memory record
        if data.get("superseded_by") or data.get("superseded_at") or data.get("is_superseded"):
            return "SUPERSEDED"

        # If explicitly designated as historical or discontinued/resolved
        if data.get("is_historical") or str(data.get("status", "")).lower() in ("historical", "discontinued", "resolved", "superseded"):
            return "HISTORICAL"

        return "CURRENT"

    @property
    def status(self) -> str:
        return self.memory_state

    @property
    def provenance(self) -> dict:
        data = self.payload
        prov = data.get("provenance")
        if isinstance(prov, dict):
            return prov
        return {
            "source_consultation_id": self.source_consultation_id,
            "source_version_id": self.source_version_id,
            "validation_report_id": self.validation_report_id,
            "supersedes_id": self.supersedes_id,
            "verified": self.verified,
        }
