from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json
import structlog

from app.models.clinical_memory import ClinicalMemory

logger = structlog.get_logger(__name__)

class MemoryService:
    @staticmethod
    def get_patient_memory(db: Session, patient_id: str, verified_only: bool = True) -> List[Dict[str, Any]]:
        query = db.query(ClinicalMemory).filter(ClinicalMemory.patient_id == patient_id)
        if verified_only:
            query = query.filter(ClinicalMemory.verified == True)

        memories = query.order_by(desc(ClinicalMemory.created_at)).all()
        results = []
        for m in memories:
            content_dict = json.loads(m.content_json) if m.content_json else {}
            results.append({
                "id": m.id,
                "memory_type": m.memory_type,
                "content": content_dict,
                "source_consultation_id": m.source_consultation_id,
                "source_version_id": m.source_version_id,
                "verified": m.verified,
                "validation_report_id": m.validation_report_id,
                "supersedes_id": m.supersedes_id,
                "semantic_state": m.semantic_state,
                "memory_state": m.memory_state,
                "status": m.status,
                "provenance": m.provenance,
                "created_at": m.created_at.isoformat() if m.created_at else None
            })
        return results

    @staticmethod
    def get_memory_history(db: Session, patient_id: str) -> List[Dict[str, Any]]:
        return MemoryService.get_patient_memory(db, patient_id, verified_only=False)

    @staticmethod
    def record_approved_memory(
        db: Session,
        patient_id: str,
        memory_type: str,
        content: Dict[str, Any],
        source_consultation_id: Optional[str] = None,
        source_version_id: Optional[str] = None,
        validation_report_id: Optional[str] = None,
        approving_actor: Optional[str] = None,
        supersedes_id: Optional[str] = None,
        provenance: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> ClinicalMemory:
        """Creates an approved ClinicalMemory item version.

        If it supersedes an older memory item, marks the previous item as SUPERSEDED,
        retaining its complete historical state and linking them chronologically.
        """
        from datetime import datetime, timezone
        from app.utils.ids import memory_id

        now_str = datetime.now(timezone.utc).isoformat()

        # Build payload with provenance and lifecycle state
        payload = dict(content)
        prov = provenance or {}
        prov.setdefault("doctor_id", approving_actor)
        prov.setdefault("source_consultation_id", source_consultation_id)
        prov.setdefault("source_version_id", source_version_id)
        prov.setdefault("validation_report_id", validation_report_id)
        prov.setdefault("approved_by", approving_actor)
        prov.setdefault("approved_at", now_str)
        if reason:
            prov["supersede_reason"] = reason

        payload["provenance"] = prov
        payload["semantic_state"] = "DOCUMENTED"
        payload["memory_state"] = "CURRENT"

        new_mem_id = memory_id()

        # Deduplication 1: Check if an approved memory for this consultation and memory_type already exists
        if source_consultation_id:
            existing_cns_mem = db.query(ClinicalMemory).filter(
                ClinicalMemory.source_consultation_id == source_consultation_id,
                ClinicalMemory.memory_type == memory_type,
                ClinicalMemory.verified == True,
            ).first()
            if existing_cns_mem:
                logger.info(
                    "returning_existing_approved_memory_for_consultation",
                    cid=source_consultation_id,
                    memory_type=memory_type,
                    memory_id=existing_cns_mem.id,
                )
                return existing_cns_mem

        # Check supersession
        old_mem = None
        if supersedes_id:
            old_mem = db.query(ClinicalMemory).filter(ClinicalMemory.id == supersedes_id).first()
        else:
            # Check for existing memory of identical entity type and key (e.g. same diagnosis or same medication)
            target_key = content.get("diagnosis") or content.get("canonical_name") or content.get("test_name")
            if target_key:
                existing_matches = db.query(ClinicalMemory).filter(
                    ClinicalMemory.patient_id == patient_id,
                    ClinicalMemory.memory_type == memory_type,
                    ClinicalMemory.verified == True
                ).order_by(desc(ClinicalMemory.created_at)).all()
                for em in existing_matches:
                    em_data = em.payload
                    em_key = em_data.get("diagnosis") or em_data.get("canonical_name") or em_data.get("test_name")
                    if em_key and str(em_key).lower().strip() == str(target_key).lower().strip() and em.memory_state == "CURRENT":
                        old_mem = em
                        break

        if old_mem:
            # Deduplication 2: If the content is identical to the current active memory, return existing record
            old_val = (old_mem.payload.get(memory_type) or old_mem.payload.get("diagnosis") or old_mem.payload.get("assessment") or old_mem.payload.get("plan"))
            new_val = (content.get(memory_type) or content.get("diagnosis") or content.get("assessment") or content.get("plan"))
            if old_val and new_val and str(old_val).strip() == str(new_val).strip():
                logger.info("returning_existing_identical_current_memory", memory_id=old_mem.id)
                return old_mem

        if old_mem:
            # Mark previous item as superseded without destroying its historical value
            old_data = old_mem.payload
            old_data["memory_state"] = "SUPERSEDED"
            old_data["is_superseded"] = True
            old_data["superseded_by"] = new_mem_id
            old_data["superseded_at"] = now_str
            old_data["superseded_by_consultation"] = source_consultation_id
            old_data["superseded_by_doctor"] = approving_actor
            if reason:
                old_data["supersession_reason"] = reason
            old_mem.content_json = json.dumps(old_data)
            supersedes_id = old_mem.id

            # Retain previous value reference in new memory
            prov["previous_value"] = old_data
            prov["previous_memory_id"] = old_mem.id
            payload["supersedes_id"] = old_mem.id

        new_mem = ClinicalMemory(
            id=new_mem_id,
            patient_id=patient_id,
            memory_type=memory_type,
            content_json=json.dumps(payload),
            source_consultation_id=source_consultation_id,
            source_version_id=source_version_id,
            verified=True,
            validation_report_id=validation_report_id,
            supersedes_id=supersedes_id
        )
        db.add(new_mem)
        return new_mem

memory_service = MemoryService()
