import pytest
import json
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.consultation import Consultation
from app.models.clinical_memory import ClinicalMemory
from app.services.memory_service import memory_service
from app.services.consultation_service import consultation_service
from app.utils.ids import patient_id, consultation_id, consultation_version_id
from app.models.consultation import ConsultationVersion


class TestClinicalMemoryLifecycleAndVersioning:
    def test_second_consultation_preserves_first_consultation_memory(self):
        """Proves that approving a second consultation does NOT destroy or overwrite

        the historical memory from the first consultation.
        """
        with get_db_context() as db:
            pid = patient_id()
            patient = Patient(
                id=pid,
                full_name="Multi-Consultation Patient",
                age_years=52,
                sex="male",
                is_demo=False
            )
            db.add(patient)

            # Grant explicit patient access to doctors
            from app.models.patient_access import PatientAccess
            db.add(PatientAccess(user_id="usr_doctor_001", patient_id=pid, access_level="primary_doctor"))
            db.add(PatientAccess(user_id="usr_doctor_002", patient_id=pid, access_level="read_write"))

            # --- CONSULTATION 1 ---
            cid_1 = consultation_id()
            cns_1 = Consultation(
                id=cid_1,
                patient_id=pid,
                specialty="General Medicine",
                status="draft",
            )
            db.add(cns_1)
            vid_1 = consultation_version_id()
            ver_1 = ConsultationVersion(
                id=vid_1,
                consultation_id=cid_1,
                version_number=1,
                origin="doctor_edited",
                content_json=json.dumps({
                    "chief_complaint": "Polyuria and polydipsia for 3 weeks",
                    "assessment": "Suspected new onset Type 2 Diabetes Mellitus",
                    "plan": "Start Metformin 500mg BD. Order HbA1c test.",
                    "evidence_ids": []
                }),
                edited_by="usr_doctor_001"
            )
            db.add(ver_1)
            cns_1.current_version_id = vid_1
            db.commit()

            # Mock evaluate_gate1_judge so test runs cleanly without needing live Gemini credentials
            from unittest.mock import patch
            with patch("app.validation.gate1_memory.evaluate_gate1_judge", return_value=(True, "info", {"verdict": "pass"})):
                # Approve Consultation 1
                res_1 = consultation_service.approve(
                    db=db,
                    cid=cid_1,
                    approved_by="usr_doctor_001",
                    acknowledged_unedited=True
                )
                assert res_1["status"] == "approved"

                # Verify memory after consultation 1
                memories_c1 = memory_service.get_patient_memory(db, pid, verified_only=True)
                assert len(memories_c1) == 3
                c1_diag = next(m for m in memories_c1 if m["memory_type"] == "diagnosis")
                assert c1_diag["memory_state"] == "CURRENT"
                assert c1_diag["source_consultation_id"] == cid_1
                assert c1_diag["provenance"]["approved_by"] == "usr_doctor_001"
                diag_1_id = c1_diag["id"]

                # --- CONSULTATION 2 (3 Months Later) ---
                cid_2 = consultation_id()
                cns_2 = Consultation(
                    id=cid_2,
                    patient_id=pid,
                    specialty="Endocrinology",
                    status="draft",
                )
                db.add(cns_2)
                vid_2 = consultation_version_id()
                ver_2 = ConsultationVersion(
                    id=vid_2,
                    consultation_id=cid_2,
                    version_number=1,
                    origin="doctor_edited",
                    content_json=json.dumps({
                        "chief_complaint": "Follow-up for Type 2 Diabetes Mellitus with good glycemic control",
                        "assessment": "Type 2 Diabetes Mellitus well controlled on Metformin",
                        "plan": "Continue Metformin 500mg BD. Recheck HbA1c in 6 months.",
                        "evidence_ids": []
                    }),
                    edited_by="usr_doctor_002"
                )
                db.add(ver_2)
                cns_2.current_version_id = vid_2
                db.commit()

                # Approve Consultation 2
                res_2 = consultation_service.approve(
                    db=db,
                    cid=cid_2,
                    approved_by="usr_doctor_002",
                    acknowledged_unedited=True
                )
                assert res_2["status"] == "approved"

            # Verify that consultation 1's memory items are STILL INTACT
            all_memories = memory_service.get_memory_history(db, pid)
            # Both consultations must have their records in memory (3 + 3 = 6)
            assert len(all_memories) == 6

            c1_items = [m for m in all_memories if m["source_consultation_id"] == cid_1]
            c2_items = [m for m in all_memories if m["source_consultation_id"] == cid_2]
            assert len(c1_items) == 3
            assert len(c2_items) == 3

            # Verify C1 diagnosis was not deleted or mutated into C2's content
            orig_c1_diag = next(m for m in c1_items if m["memory_type"] == "diagnosis")
            assert orig_c1_diag["id"] == diag_1_id
            assert "Polyuria and polydipsia" in orig_c1_diag["content"]["diagnosis"]
            assert orig_c1_diag["provenance"]["approved_by"] == "usr_doctor_001"

            # Verify C2 diagnosis is recorded independently with its own provenance
            new_c2_diag = next(m for m in c2_items if m["memory_type"] == "diagnosis")
            assert "Follow-up for Type 2 Diabetes" in new_c2_diag["content"]["diagnosis"]
            assert new_c2_diag["provenance"]["approved_by"] == "usr_doctor_002"
            assert new_c2_diag["source_consultation_id"] == cid_2

    def test_superseded_memory_preserves_previous_state_and_provenance(self):
        """When an existing memory item is updated/superseded by a newer approved value:

        - Previous memory retains its previous value and is marked SUPERSEDED
        - New memory retains the new value, references the superseded ID, and records provenance
        - Full historical audit trail is intact
        """
        with get_db_context() as db:
            pid = patient_id()
            patient = Patient(
                id=pid,
                full_name="Supersede Test Patient",
                age_years=60,
                sex="female",
                is_demo=False
            )
            db.add(patient)

            # Create dummy consultations so foreign key constraints pass
            cns_jan = Consultation(id="cns_jan_01", patient_id=pid, specialty="general_medicine", status="approved")
            cns_mar = Consultation(id="cns_mar_02", patient_id=pid, specialty="endocrinology", status="approved")
            db.add(cns_jan)
            db.add(cns_mar)
            db.commit()

            # 1. Initial Memory (January)
            mem_v1 = memory_service.record_approved_memory(
                db=db,
                patient_id=pid,
                memory_type="medication",
                content={
                    "canonical_name": "Metformin",
                    "dose": "500 mg",
                    "frequency": "OD",
                    "status": "active"
                },
                source_consultation_id="cns_jan_01",
                approving_actor="usr_doctor_001",
                reason="Initial therapy for newly diagnosed T2DM"
            )
            db.commit()

            assert mem_v1.memory_state == "CURRENT"
            assert mem_v1.supersedes_id is None
            v1_id = mem_v1.id

            # 2. Newer Memory (March - Dose increased to BD)
            mem_v2 = memory_service.record_approved_memory(
                db=db,
                patient_id=pid,
                memory_type="medication",
                content={
                    "canonical_name": "Metformin",
                    "dose": "500 mg",
                    "frequency": "BD",
                    "status": "active"
                },
                source_consultation_id="cns_mar_02",
                approving_actor="usr_doctor_002",
                supersedes_id=v1_id,
                reason="Dose escalated due to suboptimal fasting blood glucose"
            )
            db.commit()

            # Re-read v1 from DB
            db.refresh(mem_v1)

            # Previous memory MUST be marked SUPERSEDED and must preserve its original values
            assert mem_v1.memory_state == "SUPERSEDED"
            v1_payload = mem_v1.payload
            assert v1_payload["dose"] == "500 mg"
            assert v1_payload["frequency"] == "OD"
            assert v1_payload["is_superseded"] is True
            assert v1_payload["superseded_by"] == mem_v2.id
            assert v1_payload["superseded_by_doctor"] == "usr_doctor_002"
            assert v1_payload["superseded_by_consultation"] == "cns_mar_02"
            assert "suboptimal fasting" in v1_payload["supersession_reason"]

            # New memory MUST be CURRENT, link back to previous item, and retain previous value in provenance
            assert mem_v2.memory_state == "CURRENT"
            assert mem_v2.supersedes_id == v1_id
            v2_payload = mem_v2.payload
            assert v2_payload["frequency"] == "BD"
            assert v2_payload["provenance"]["approved_by"] == "usr_doctor_002"
            assert v2_payload["provenance"]["previous_memory_id"] == v1_id
            assert v2_payload["provenance"]["previous_value"]["frequency"] == "OD"

    def test_unverified_candidate_memory_distinguished_from_approved_memory(self):
        """Unverified proposed memory is marked UNVERIFIED and only promoted to CURRENT upon doctor approval."""
        with get_db_context() as db:
            pid = patient_id()
            patient = Patient(
                id=pid,
                full_name="Candidate Memory Patient",
                age_years=45,
                sex="male",
                is_demo=False
            )
            db.add(patient)
            db.commit()

            # Proposed memory
            candidate = ClinicalMemory(
                id="mem_candidate_01",
                patient_id=pid,
                memory_type="plan_note",
                content_json=json.dumps({
                    "content": "Patient considering low carb diet",
                    "memory_state": "UNVERIFIED",
                    "semantic_state": "UNVERIFIED"
                }),
                verified=False
            )
            db.add(candidate)
            db.commit()

            # Query verified only: candidate must NOT be present
            verified_list = memory_service.get_patient_memory(db, pid, verified_only=True)
            assert len(verified_list) == 0

            # Query history: candidate is present with UNVERIFIED state
            history_list = memory_service.get_memory_history(db, pid)
            assert len(history_list) == 1
            assert history_list[0]["memory_state"] == "UNVERIFIED"
            assert history_list[0]["verified"] is False
