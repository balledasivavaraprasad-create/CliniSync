import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.brief import Brief
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.contradiction import Contradiction
from app.models.audit_log import AuditLog
from app.schemas.brief import DoctorBrief
from app.services.brief_service import brief_service
from app.services.extraction_service import extraction_service
from app.services.patient_service import PatientService
from app.services.voice_service import voice_service
from app.api.errors import NotFoundError, LLMUnavailableError


class TestFallbackMechanismsHardening:
    @pytest.mark.asyncio
    async def test_brief_service_safe_deterministic_fallback_on_llm_failure(self):
        """When LLM generation fails, fallback must be deterministic, derived from DB rows,
        explicitly marked as fallback_template, carry clear disclaimer, and log full audit metadata.
        """
        with get_db_context() as db_session:
            # Create a test patient with known facts
            pat = Patient(
                id="pat_fallback_test_01",
                full_name="Fallback Test Patient",
                age_years=58,
                sex="male",
                is_demo=False
            )
            db_session.add(pat)

            fact = ClinicalFact(
                id="fact_fb_diag_01",
                patient_id=pat.id,
                fact_type="diagnosis",
                value="Type 2 Diabetes Mellitus",
                source_text="Assessment: Type 2 Diabetes Mellitus",
                confidence=0.95,
                confidence_band="high",
                provenance_verified=True,
                verification_status="DOCUMENTED",
            )
            db_session.add(fact)

            med = Medication(
                id="med_fb_01",
                patient_id=pat.id,
                canonical_name="Metformin",
                raw_name="Metformin 500mg",
                dose_text="500 mg",
                strength_value=500.0,
                strength_unit="mg",
                frequency_code="bd",
                frequency_text="twice daily",
                status="current",
                confidence=0.95,
                group_key=f"{pat.id}_metformin",
                fact_id=fact.id
            )
            db_session.add(med)

            inv = Investigation(
                id="inv_fb_01",
                patient_id=pat.id,
                test_name_canonical="hba1c",
                test_name_raw="HbA1c",
                value_numeric=7.8,
                value_text="7.8",
                unit="%",
                abnormal_flag="high",
                confidence=0.95,
                group_key=f"{pat.id}_hba1c",
                fact_id=fact.id
            )
            db_session.add(inv)
            db_session.commit()

            # Mock LLM gateway to fail
            with patch("app.services.brief_service.llm_gateway.complete_json_async", side_effect=LLMUnavailableError("LLM providers unreachable")):
                brief, source = await brief_service.generate_brief(
                    db=db_session,
                    patient_id=pat.id,
                    specialty="general_medicine",
                    force_regenerate=True
                )

                assert source == "fallback_template"
                assert brief.generation_source == "fallback_template"
                # Must have explicit safe disclaimer
                assert "Deterministic clinical summary generated from verified source records because AI generation was unavailable" in brief.disclaimer
                # Chief complaint is derived from verified diagnosis, not fabricated
                assert "Type 2 Diabetes Mellitus" in brief.chief_complaint.text
                assert brief.chief_complaint.semantic_state == "DOCUMENTED"
                # Medications are from verified DB rows
                assert len(brief.current_medications) == 1
                assert brief.current_medications[0].name.lower() == "metformin"
                # Labs are from verified DB rows
                assert len(brief.recent_investigations) == 1
                assert brief.recent_investigations[0].value == "7.8"

                # Check DB audit log
                audit_entry = db_session.query(AuditLog).filter(
                    AuditLog.patient_id == pat.id,
                    AuditLog.action == "brief_generated"
                ).order_by(AuditLog.timestamp.desc()).first()
                assert audit_entry is not None
                assert audit_entry.after_json is not None
                import json
                audit_dict = json.loads(audit_entry.after_json)
                assert audit_dict.get("generation_source") == "fallback_template"
                assert "fallback_details" in audit_dict
                fb_det = audit_dict["fallback_details"]
                assert fb_det["primary_method"] == "llm"
                assert fb_det["fallback_method"] == "deterministic_template"
                assert "LLM providers unreachable" in fb_det["failure_reason"]
                assert fb_det["resulting_confidence"] == "high"

    def test_brief_service_deterministic_template_never_guesses_missing_data(self):
        """When age or labs or complaints are missing, deterministic template marks them MISSING/UNKNOWN, never fabricates."""
        with get_db_context() as db_session:
            pat_empty = Patient(
                id="pat_fallback_empty_02",
                full_name="Empty Patient",
                age_years=None,  # Missing age
                sex="unknown",
                is_demo=False
            )
            db_session.add(pat_empty)
            db_session.commit()

            brief = brief_service._build_deterministic_template_brief(
                patient=pat_empty,
                specialty="general_medicine",
                facts=[],
                meds=[],
                invs=[],
                issues=[]
            )

            # Age is not guessed or populated with 45 or 50
            assert brief.patient.age is None
            assert brief.patient.semantic_state == "MISSING"
            # Chief complaint explicitly indicates missing source records
            assert "No chief complaint documented" in brief.chief_complaint.text
            assert brief.chief_complaint.semantic_state == "UNKNOWN"
            # Allergies explicitly state no documented allergies
            assert brief.allergies[0].semantic_state == "UNKNOWN"
            assert len(brief.current_medications) == 0
            assert len(brief.recent_investigations) == 0

    def test_extraction_deterministic_fallback_strictly_preserves_nulls(self):
        """_fallback_deterministic_extract extracts literal matches and never invents missing dose/flags."""
        pages = [
            {
                "page_number": 1,
                "text": "Patient was evaluated today. HbA1c 6.5%. Advised Tab Metformin."
            }
        ]
        result = extraction_service._fallback_deterministic_extract(pages)
        assert len(result.investigations) == 1
        inv = result.investigations[0]
        assert inv.test == "HbA1c"
        assert inv.value == "6.5"
        # Reference range and flag were NOT in text, must NOT be fabricated
        assert inv.reference_range is None
        assert inv.flag is None

        assert len(result.medications) == 1
        med = result.medications[0]
        assert med.name == "Metformin"
        # Strength and frequency were NOT in text, must NOT be guessed
        assert med.strength is None
        assert med.frequency is None

    def test_patient_service_nonexistent_patient_raises_not_found(self):
        """PatientService.get must raise NotFoundError and NOT fall back to an arbitrary demo patient."""
        with get_db_context() as db_session:
            with pytest.raises(NotFoundError):
                PatientService.get(db_session, "nonexistent_patient_id_99999")

    @pytest.mark.asyncio
    async def test_voice_service_fallback_on_stt_failure_does_not_invent_facts(self):
        """When STT transcription fails, voice service fallback records empty transcript and 0 facts, logging failure."""
        with get_db_context() as db_session:
            pat = Patient(
                id="pat_voice_fallback_03",
                full_name="Voice Patient",
                age_years=40,
                sex="female",
                is_demo=False
            )
            db_session.add(pat)
            db_session.commit()

            # Mock STT to fail
            with patch("app.services.voice_service.llm_gateway.transcribe_async", side_effect=Exception("STT Engine Timeout")):
                res = await voice_service.process_voice(
                    db=db_session,
                    patient_id=pat.id,
                    audio_bytes=b"fake_audio_bytes",
                    filename="test.wav"
                )

                assert res["stt_model"] == "fallback"
                assert res["stt_confidence"] == 0.0
                assert len(res["proposed_facts"]) == 0

                # Verify audit log recorded fallback details
                audit_entry = db_session.query(AuditLog).filter(
                    AuditLog.patient_id == pat.id,
                    AuditLog.action == "voice_note_uploaded"
                ).first()
                assert audit_entry is not None
                assert audit_entry.after_json is not None
                import json
                audit_after = json.loads(audit_entry.after_json)
                fb_det = audit_after.get("fallback_details")
                assert fb_det is not None
                assert fb_det["primary_method"] == "whisper_stt"
                assert "STT Engine Timeout" in fb_det["failure_reason"]
