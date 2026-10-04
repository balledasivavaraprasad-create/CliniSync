import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.clinical_fact import ClinicalFact
from app.models.voice_note import VoiceNote
from app.models.clinical_memory import ClinicalMemory
from app.utils.ids import patient_id

client = TestClient(app)

@pytest.mark.anyio
async def test_voice_pipeline_and_review():
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Voice Test Patient")
        db.add(p)
        db.commit()

    # Mock audio bytes (dummy wav header)
    dummy_wav = b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"

    # Mock transcribe response to test predictable extraction without relying on mic audio
    mock_transcript = "Patient reports history of Type 2 Diabetes Mellitus. Started taking Metformin 500 mg once daily."
    with patch("app.ai.gateway.llm_gateway.transcribe", return_value={"text": mock_transcript, "model": "groq/whisper-large-v3", "confidence": 0.95}):
        files = {"file": ("test_voice.wav", dummy_wav, "audio/wav")}
        res = client.post(f"/api/v1/patients/{pid}/voice", files=files)
        assert res.status_code == 201
        data = res.json()["data"]
        vid = data["id"]
        assert data["review_status"] == "pending_review"
        assert data["transcript_raw"] == mock_transcript
        assert len(data["proposed_facts"]) >= 1

        # Invariant check: voice-derived facts must start with needs_verification
        for f in data["proposed_facts"]:
            assert f["verification_status"] == "needs_verification"
            assert f["confidence_band"] == "needs_verification"

    # Verify NO voice facts entered verified clinical memory directly (INV-1)
    with get_db_context() as db:
        memories = db.query(ClinicalMemory).filter(ClinicalMemory.patient_id == pid).all()
        assert len(memories) == 0, "Voice facts must never enter verified clinical memory directly"

    # Doctor Reviews & Confirms Transcript
    res_review = client.post(
        f"/api/v1/voice/{vid}/review",
        json={"edited_transcript": "Patient reports Type 2 Diabetes Mellitus on Metformin 500 mg OD."}
    )
    assert res_review.status_code == 200
    rev_data = res_review.json()["data"]
    assert rev_data["review_status"] == "reviewed"

    # Verify facts are now promoted to ordinary unverified facts
    with get_db_context() as db:
        confirmed_facts = db.query(ClinicalFact).filter(ClinicalFact.voice_note_id == vid).all()
        assert len(confirmed_facts) >= 1
        for cf in confirmed_facts:
            assert cf.verification_status == "unverified"
            assert cf.confidence_band == "medium"

    print("\n✓ Phase 9 Voice Pipeline & Doctor Review workflow verified successfully!")
