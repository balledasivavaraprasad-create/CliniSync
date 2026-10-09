"""Idempotency and Concurrency Hardening Test Suite for ClinSync.

Audits and verifies that backend operations that may be executed more than once
never create duplicate records or corrupted state across retries:
1. Document upload deduplication (SHA-256 fingerprint, no duplicate contradictions, race handling).
2. Pipeline reprocessing idempotency (OCR pages, facts, medications, investigations, timeline events).
3. Consultation creation deduplication (client refresh via brief_id or Idempotency-Key).
4. Brief generation idempotency (cached fingerprint lookup, no duplicate brief rows).
5. Consultation double-approval prevention (HTTP 409 rejection, no duplicate memory updates or timeline notes).
6. Clinical memory service direct idempotency (same consultation/type, identical current content values).
"""

import json
import fitz
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db_context
from app.models.user import User
from app.models.patient import Patient
from app.models.patient_access import PatientAccess
from app.models.document import Document, DocumentPage
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.contradiction import Contradiction
from app.models.brief import Brief
from app.models.consultation import Consultation, ConsultationVersion
from app.models.clinical_memory import ClinicalMemory
from app.models.timeline_event import TimelineEvent
from app.schemas.ai_contracts import (
    DocClassification,
    ExtractionResult,
    ExtractionMedication,
    ExtractionDiagnosis,
    ExtractionInvestigation,
    EvidenceReference,
)
from app.services.document_service import DocumentService
from app.services.pipeline_orchestrator import pipeline_orchestrator
from app.services.brief_service import brief_service
from app.services.memory_service import memory_service
from app.utils.hashing import hash_password
from app.utils.tokens import create_access_token
from app.utils.ids import (
    user_id,
    patient_id,
    brief_id,
    consultation_id,
    version_id,
)

client = TestClient(app)


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


def create_sample_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=11)
    buf = doc.write()
    doc.close()
    return buf


@pytest.fixture(scope="module")
def idempotency_fixture():
    with get_db_context() as db:
        doc_uid = user_id()
        doctor = User(
            id=doc_uid,
            email=f"dr_idempotent_{doc_uid}@clinsync.health",
            full_name="Dr. Idempotent Specialist",
            role="doctor",
            specialty="Internal Medicine",
            hashed_password=hash_password("DoctorPass123!"),
            is_active=True,
        )
        db.add(doctor)
        db.flush()

        pid = patient_id()
        pat = Patient(
            id=pid,
            full_name="Idempotency Test Patient",
            date_of_birth="1980-05-15",
            age_years=46,
            sex="female",
            is_demo=False,
        )
        db.add(pat)
        db.flush()

        access = PatientAccess(
            user_id=doctor.id,
            patient_id=pat.id,
            access_level="full",
        )
        db.add(access)
        db.commit()

        token = create_access_token(subject=doctor.id, claims={"email": doctor.email, "role": doctor.role})

        return {
            "doctor_id": doctor.id,
            "patient_id": pat.id,
            "token": token,
        }


class TestDocumentUploadIdempotency:
    def test_upload_same_document_thrice_no_duplicate_contradictions(self, idempotency_fixture):
        """Uploading the exact same document 3 times detects duplicate and does not multiply contradiction issues."""
        pid = idempotency_fixture["patient_id"]
        pdf_bytes = create_sample_pdf("Patient Jane Doe. Metformin 500mg daily. HbA1c 6.8%.")

        # 1. First upload
        with get_db_context() as db:
            doc1, is_dup1 = DocumentService.store_document(
                db=db,
                patient_id=pid,
                filename="lab_report.pdf",
                content=pdf_bytes,
                declared_mime="application/pdf",
            )
            assert is_dup1 is False
            doc1_id = doc1.id

        # 2. Second upload (duplicate)
        with get_db_context() as db:
            doc2, is_dup2 = DocumentService.store_document(
                db=db,
                patient_id=pid,
                filename="lab_report_copy.pdf",
                content=pdf_bytes,
                declared_mime="application/pdf",
            )
            assert is_dup2 is True
            assert doc2.id == doc1_id

        # 3. Third upload (duplicate retry)
        with get_db_context() as db:
            doc3, is_dup3 = DocumentService.store_document(
                db=db,
                patient_id=pid,
                filename="lab_report_retry.pdf",
                content=pdf_bytes,
                declared_mime="application/pdf",
            )
            assert is_dup3 is True
            assert doc3.id == doc1_id

        # Check database records
        with get_db_context() as db:
            docs = db.query(Document).filter(Document.patient_id == pid, Document.sha256 == doc1.sha256).all()
            assert len(docs) == 1

            dup_issues = db.query(Contradiction).filter(
                Contradiction.patient_id == pid,
                Contradiction.issue_type == "duplicate_record",
            ).all()
            # Contradiction row must NOT be duplicated for the same uploaded document!
            assert len(dup_issues) == 1

    def test_upload_concurrent_commit_race_handled_gracefully(self, idempotency_fixture):
        """Simulate a concurrent upload commit race where DB integrity constraint triggers."""
        pid = idempotency_fixture["patient_id"]
        pdf_bytes = create_sample_pdf("Patient Jane Doe. Lisinopril 10mg daily.")

        with get_db_context() as db:
            doc1, is_dup1 = DocumentService.store_document(
                db=db,
                patient_id=pid,
                filename="lisinopril_presc.pdf",
                content=pdf_bytes,
                declared_mime="application/pdf",
            )
            assert is_dup1 is False

        # Simulate race: both passed initial check (seeing None), first commits, second hits commit error and finds first
        with get_db_context() as db:
            from sqlalchemy.orm import Query
            orig_first = Query.first
            doc_calls = {"count": 0}

            def mock_first(self):
                if self.column_descriptions and self.column_descriptions[0].get("entity") == Document:
                    doc_calls["count"] += 1
                    if doc_calls["count"] == 1:
                        return None  # First Document check returns None (simulating race)
                    return doc1     # Recovery check finds committed doc
                return orig_first(self)

            with patch("sqlalchemy.orm.Query.first", mock_first):
                with patch.object(db, "commit", side_effect=Exception("UNIQUE constraint failed: documents.patient_id, documents.sha256")):
                    doc_race, is_dup_race = DocumentService.store_document(
                        db=db,
                        patient_id=pid,
                        filename="lisinopril_presc_concurrent.pdf",
                        content=pdf_bytes,
                        declared_mime="application/pdf",
                    )
                    assert is_dup_race is True
                    assert doc_race.id == doc1.id


class TestPipelineReprocessingIdempotency:
    @pytest.mark.asyncio
    async def test_reprocessing_pipeline_does_not_duplicate_entities_or_timeline(self, idempotency_fixture):
        """Reprocessing the document pipeline purges previous unapproved entities and leaves no duplicates."""
        pid = idempotency_fixture["patient_id"]
        pdf_bytes = create_sample_pdf("Prescription: Atorvastatin 20mg OD. Lab: Fasting Blood Sugar: 110 mg/dL.")

        with get_db_context() as db:
            doc, _ = DocumentService.store_document(
                db=db,
                patient_id=pid,
                filename="pipeline_test.pdf",
                content=pdf_bytes,
                declared_mime="application/pdf",
            )
            doc_id = doc.id

        mock_ocr = [{"page_number": 1, "text": "Prescription: Atorvastatin 20mg OD. Lab: Fasting Blood Sugar: 110 mg/dL.", "ocr_confidence": 0.98, "method": "pdf_text"}]
        mock_class = DocClassification(document_type="prescription", confidence=0.95, document_date="2026-03-01")
        mock_extract = ExtractionResult(
            medications=[
                ExtractionMedication(name="Atorvastatin", strength="20mg", frequency="OD", confidence=0.95, evidence=EvidenceReference(page=1, text="Atorvastatin 20mg OD"))
            ],
            investigations=[
                ExtractionInvestigation(test="Fasting Blood Sugar", value="110", unit="mg/dL", confidence=0.92, evidence=EvidenceReference(page=1, text="Fasting Blood Sugar: 110 mg/dL"))
            ],
            diagnoses=[
                ExtractionDiagnosis(text="Hyperlipidemia", confidence=0.90, evidence=EvidenceReference(page=1, text="Atorvastatin 20mg OD"))
            ],
            symptoms=[],
            allergies=[],
        )

        with patch("app.services.ocr_service.ocr_service.extract_text", AsyncMock(return_value=mock_ocr)), \
             patch("app.services.classification_service.classification_service.classify", AsyncMock(return_value=mock_class)), \
             patch("app.services.extraction_service.extraction_service.extract", AsyncMock(return_value=mock_extract)):

            # First pipeline run
            await pipeline_orchestrator.run(document_id=doc_id, is_reprocess=False)

            with get_db_context() as db:
                pages_count_1 = db.query(DocumentPage).filter(DocumentPage.document_id == doc_id).count()
                facts_count_1 = db.query(ClinicalFact).filter(ClinicalFact.document_id == doc_id).count()
                meds_count_1 = db.query(Medication).filter(Medication.source_document_id == doc_id).count()
                invs_count_1 = db.query(Investigation).filter(Investigation.source_document_id == doc_id).count()
                events_count_1 = db.query(TimelineEvent).filter(TimelineEvent.source_document_id == doc_id).count()

                assert pages_count_1 == 1
                assert facts_count_1 == 3
                assert meds_count_1 == 1
                assert invs_count_1 == 1
                assert events_count_1 == 3

            # Second pipeline run (reprocessing)
            await pipeline_orchestrator.run(document_id=doc_id, is_reprocess=True)

            with get_db_context() as db:
                pages_count_2 = db.query(DocumentPage).filter(DocumentPage.document_id == doc_id).count()
                facts_count_2 = db.query(ClinicalFact).filter(ClinicalFact.document_id == doc_id).count()
                meds_count_2 = db.query(Medication).filter(Medication.source_document_id == doc_id).count()
                invs_count_2 = db.query(Investigation).filter(Investigation.source_document_id == doc_id).count()
                events_count_2 = db.query(TimelineEvent).filter(TimelineEvent.source_document_id == doc_id).count()

                # Exactly identical counts, zero duplicates!
                assert pages_count_2 == pages_count_1
                assert facts_count_2 == facts_count_1
                assert meds_count_2 == meds_count_1
                assert invs_count_2 == invs_count_1
                assert events_count_2 == events_count_1


class TestConsultationCreationIdempotency:
    def test_refresh_consultation_with_brief_id_returns_same_draft(self, idempotency_fixture):
        """Client refreshing consultation creation with same brief_id returns existing draft without duplication."""
        pid = idempotency_fixture["patient_id"]
        token = idempotency_fixture["token"]

        with get_db_context() as db:
            b_id = brief_id()
            br = Brief(
                id=b_id,
                patient_id=pid,
                specialty="cardiology",
                content_json="{}",
                input_fingerprint="test_fp_cardio",
                status="validated",
            )
            db.add(br)
            db.commit()

        # 1. First consultation request
        resp1 = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "cardiology", "brief_id": b_id},
            headers=auth_header(token),
        )
        assert resp1.status_code == 201
        cns_id_1 = resp1.json()["data"]["id"]
        ver_id_1 = resp1.json()["data"]["current_version_id"]

        # 2. Second consultation request (client refreshed page)
        resp2 = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "cardiology", "brief_id": b_id},
            headers=auth_header(token),
        )
        assert resp2.status_code == 201
        cns_id_2 = resp2.json()["data"]["id"]
        ver_id_2 = resp2.json()["data"]["current_version_id"]

        assert cns_id_1 == cns_id_2
        assert ver_id_1 == ver_id_2

        with get_db_context() as db:
            cns_count = db.query(Consultation).filter(
                Consultation.patient_id == pid,
                Consultation.brief_id == b_id,
            ).count()
            assert cns_count == 1

    def test_consultation_creation_with_idempotency_key(self, idempotency_fixture):
        """Client sending same Idempotency-Key header receives identical consultation without duplication."""
        pid = idempotency_fixture["patient_id"]
        token = idempotency_fixture["token"]
        key = "idem-key-consultation-999"

        headers = {**auth_header(token), "Idempotency-Key": key}

        # 1. First request
        resp1 = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "pulmonology"},
            headers=headers,
        )
        assert resp1.status_code == 201
        cid1 = resp1.json()["data"]["id"]

        # 2. Duplicate retry request
        resp2 = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "pulmonology"},
            headers=headers,
        )
        assert resp2.status_code == 201
        cid2 = resp2.json()["data"]["id"]

        assert cid1 == cid2

        with get_db_context() as db:
            cns_count = db.query(Consultation).filter(
                Consultation.patient_id == pid,
                Consultation.specialty == "pulmonology",
            ).count()
            assert cns_count == 1


class TestBriefGenerationIdempotency:
    @pytest.mark.asyncio
    async def test_generate_brief_twice_without_force_regenerate_returns_cached_row(self, idempotency_fixture):
        """Calling generate_brief with force_regenerate=False returns cached brief and does not insert duplicate rows."""
        pid = idempotency_fixture["patient_id"]

        with get_db_context() as db:
            # 1. Generate brief first time
            brief1, source1 = await brief_service.generate_brief(
                db=db,
                patient_id=pid,
                specialty="endocrinology",
                force_regenerate=False,
            )

        with get_db_context() as db:
            count1 = db.query(Brief).filter(
                Brief.patient_id == pid,
                Brief.specialty == "endocrinology",
            ).count()
            assert count1 >= 1

            # 2. Call generate brief a second time with force_regenerate=False
            brief2, source2 = await brief_service.generate_brief(
                db=db,
                patient_id=pid,
                specialty="endocrinology",
                force_regenerate=False,
            )

            count2 = db.query(Brief).filter(
                Brief.patient_id == pid,
                Brief.specialty == "endocrinology",
            ).count()
            # Must remain unchanged, no duplicate brief rows created
            assert count2 == count1
            assert brief1.specialty == brief2.specialty


class TestConsultationDoubleApprovalAndMemoryIdempotency:
    def test_retrying_approval_rejected_with_409_and_no_duplicate_updates(self, idempotency_fixture):
        """Retrying doctor approval on an approved consultation is rejected with 409 and does not duplicate memory or timeline notes."""
        pid = idempotency_fixture["patient_id"]
        token = idempotency_fixture["token"]

        # Create draft
        res = client.post(
            f"/api/v1/patients/{pid}/consultations",
            json={"specialty": "general_medicine"},
            headers=auth_header(token),
        )
        cid = res.json()["data"]["id"]
        vid = res.json()["data"]["current_version_id"]

        # Doctor edits draft
        client.put(
            f"/api/v1/consultations/{cid}",
            json={
                "content": {
                    "chief_complaint": "Persistent fatigue",
                    "assessment": "Chronic fatigue syndrome evaluation",
                    "plan": "Order complete blood count and thyroid panel",
                },
                "expected_version_id": vid,
            },
            headers=auth_header(token),
        )

        with patch("app.validation.gate1_memory.evaluate_gate1_judge", return_value=(True, "info", {"passed": True})):
            # First approval succeeds
            appr1 = client.post(
                f"/api/v1/consultations/{cid}/approve",
                headers=auth_header(token),
            )
            assert appr1.status_code == 200

            with get_db_context() as db:
                mem_count_1 = db.query(ClinicalMemory).filter(ClinicalMemory.source_consultation_id == cid).count()
                tl_count_1 = db.query(TimelineEvent).filter(
                    TimelineEvent.patient_id == pid,
                    TimelineEvent.event_type == "approved_note",
                ).count()
                assert mem_count_1 > 0
                assert tl_count_1 > 0

            # Second approval attempt fails with 409 Conflict
            appr2 = client.post(
                f"/api/v1/consultations/{cid}/approve",
                headers=auth_header(token),
            )
            assert appr2.status_code == 409
            assert "INVALID_STATE_TRANSITION" in appr2.json()["error"]["code"]

            with get_db_context() as db:
                mem_count_2 = db.query(ClinicalMemory).filter(ClinicalMemory.source_consultation_id == cid).count()
                tl_count_2 = db.query(TimelineEvent).filter(
                    TimelineEvent.patient_id == pid,
                    TimelineEvent.event_type == "approved_note",
                ).count()
                # Zero duplicate memory items or timeline notes created!
                assert mem_count_2 == mem_count_1
                assert tl_count_2 == tl_count_1

    def test_memory_service_record_approved_memory_direct_idempotency(self, idempotency_fixture):
        """record_approved_memory is idempotent across retries for the same consultation or identical current content."""
        pid = idempotency_fixture["patient_id"]

        with get_db_context() as db:
            cns = Consultation(
                id=consultation_id(),
                patient_id=pid,
                specialty="general_medicine",
                status="in_review",
            )
            db.add(cns)
            db.commit()
            real_cid = cns.id

        with get_db_context() as db:
            # 1. Record approved memory for real_cid
            mem1 = memory_service.record_approved_memory(
                db=db,
                patient_id=pid,
                memory_type="diagnosis",
                content={"diagnosis": "Type 2 Diabetes Mellitus"},
                source_consultation_id=real_cid,
                approving_actor="dr_test",
            )
            db.commit()

            # 2. Retrying record_approved_memory with same real_cid and memory_type
            mem2 = memory_service.record_approved_memory(
                db=db,
                patient_id=pid,
                memory_type="diagnosis",
                content={"diagnosis": "Type 2 Diabetes Mellitus"},
                source_consultation_id=real_cid,
                approving_actor="dr_test",
            )
            assert mem1.id == mem2.id

            # 3. Retrying with identical content value without consultation ID returns current item
            mem3 = memory_service.record_approved_memory(
                db=db,
                patient_id=pid,
                memory_type="diagnosis",
                content={"diagnosis": "Type 2 Diabetes Mellitus"},
                approving_actor="dr_test",
            )
            assert mem3.id == mem1.id
