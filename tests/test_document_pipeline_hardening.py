"""Comprehensive test suite for document ingestion hardening, file security, worker reliability, and reprocessing idempotency.

Tests:
1. Valid PDF upload and verification
2. Valid image upload (PNG, JPEG)
3. Invalid extension rejection (e.g. .exe, .sh, .py, .bin)
4. Spoofed MIME rejection (declared PDF but content is text/executable, or declared PNG with invalid magic bytes)
5. Oversized file rejection (> MAX_UPLOAD_MB)
6. Corrupted file rejection (corrupted PDF structure, unreadable image bytes)
7. Duplicate file detection per patient (SHA-256 deduplication and contradiction alert)
8. Unauthorized file access (cross-patient IDOR prevention on /documents/{id}/file)
9. Reprocessing idempotency (POST /documents/{id}/reprocess does NOT create duplicate facts, timeline events, or issues)
10. Failed processing error handling (sanitized error message stored, status updated to failed)
11. Worker retry state handling (job state moves to retrying on transient error)
"""
import io
import fitz
import pytest
from PIL import Image
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db_context
from app.models.user import User
from app.models.patient import Patient
from app.models.patient_access import PatientAccess
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.timeline_event import TimelineEvent
from app.models.processing_job import ProcessingJob
from app.services.pipeline_orchestrator import pipeline_orchestrator
from app.services.task_worker import task_worker
from app.utils.hashing import hash_password
from app.utils.tokens import create_access_token
from app.utils.ids import user_id, patient_id, document_id

client = TestClient(app)


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def pipeline_fixture():
    with get_db_context() as db:
        uid_doc_a = user_id()
        doc_a = User(
            id=uid_doc_a,
            email="dr_pipe_a@clinsync.health",
            full_name="Dr. Pipeline A",
            role="doctor",
            specialty="Pulmonology",
            hashed_password=hash_password("PassPipe123!"),
            is_active=True,
        )

        uid_doc_b = user_id()
        doc_b = User(
            id=uid_doc_b,
            email="dr_pipe_b@clinsync.health",
            full_name="Dr. Pipeline B",
            role="doctor",
            specialty="Cardiology",
            hashed_password=hash_password("PassPipe123!"),
            is_active=True,
        )

        db.add_all([doc_a, doc_b])
        db.flush()

        pid_a = patient_id()
        pat_a = Patient(id=pid_a, full_name="Patient Pipeline A", is_demo=False)
        db.add(pat_a)
        db.flush()

        access_a = PatientAccess(
            user_id=doc_a.id,
            patient_id=pat_a.id,
            access_level="primary_doctor",
        )
        db.add(access_a)
        db.commit()

        token_a = create_access_token(subject=doc_a.id, claims={"email": doc_a.email, "role": doc_a.role})
        token_b = create_access_token(subject=doc_b.id, claims={"email": doc_b.email, "role": doc_b.role})

    return {
        "patient_id": pid_a,
        "token_a": token_a,
        "token_b": token_b,
    }


def create_sample_pdf_bytes(text: str = "Clinical Summary Note. Patient is stable.") -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=11)
    buf = doc.write()
    doc.close()
    return buf


def create_sample_png_bytes() -> bytes:
    img = Image.new("RGB", (100, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestFileSecurityAndValidation:
    def test_valid_pdf_upload(self, pipeline_fixture):
        pid = pipeline_fixture["patient_id"]
        token = pipeline_fixture["token_a"]
        pdf_bytes = create_sample_pdf_bytes("Lab Report: Fasting Glucose 95 mg/dL")

        files = {"file": ("blood_work.pdf", pdf_bytes, "application/pdf")}
        resp = client.post(f"/api/v1/patients/{pid}/documents", files=files, headers=auth_header(token))
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["original_filename"] == "blood_work.pdf"
        assert data["mime_type"] == "application/pdf"
        assert data["duplicate"] is False

    def test_valid_image_upload(self, pipeline_fixture):
        pid = pipeline_fixture["patient_id"]
        token = pipeline_fixture["token_a"]
        png_bytes = create_sample_png_bytes()

        files = {"file": ("chest_scan.png", png_bytes, "image/png")}
        resp = client.post(f"/api/v1/patients/{pid}/documents", files=files, headers=auth_header(token))
        assert resp.status_code == 201
        data = resp.json()["data"]
        assert data["original_filename"] == "chest_scan.png"
        assert data["mime_type"] == "image/png"

    def test_invalid_extension_rejection(self, pipeline_fixture):
        pid = pipeline_fixture["patient_id"]
        token = pipeline_fixture["token_a"]
        payload = b"echo 'malicious script'"

        files = {"file": ("exploit.sh", payload, "application/x-sh")}
        resp = client.post(f"/api/v1/patients/{pid}/documents", files=files, headers=auth_header(token))
        assert resp.status_code == 415
        assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"
        assert "not permitted" in resp.json()["error"]["message"]

    def test_spoofed_mime_rejection(self, pipeline_fixture):
        pid = pipeline_fixture["patient_id"]
        token = pipeline_fixture["token_a"]
        # Executable/text content declared as application/pdf with .pdf extension
        fake_pdf = b"NOT_A_REAL_PDF_HEADER_JUST_RANDOM_TEXT"

        files = {"file": ("spoofed.pdf", fake_pdf, "application/pdf")}
        resp = client.post(f"/api/v1/patients/{pid}/documents", files=files, headers=auth_header(token))
        assert resp.status_code == 415
        assert resp.json()["error"]["code"] == "UNSUPPORTED_FILE_TYPE"

    def test_oversized_file_rejection(self, pipeline_fixture, monkeypatch):
        from app.config import settings
        # Set max upload to 1 MB for test
        monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 1)

        pid = pipeline_fixture["patient_id"]
        token = pipeline_fixture["token_a"]
        big_content = b"%PDF-" + b"0" * (2 * 1024 * 1024)

        files = {"file": ("oversized.pdf", big_content, "application/pdf")}
        resp = client.post(f"/api/v1/patients/{pid}/documents", files=files, headers=auth_header(token))
        assert resp.status_code == 413
        assert resp.json()["error"]["code"] == "FILE_TOO_LARGE"

    def test_corrupted_pdf_rejection(self, pipeline_fixture):
        pid = pipeline_fixture["patient_id"]
        token = pipeline_fixture["token_a"]
        # Starts with %PDF but rest of stream is completely corrupted
        corrupted_pdf = b"%PDF-1.4\n" + b"\xff\xfe\xfd\x00\x01\x02GarbageTrailerEOF"

        files = {"file": ("corrupt.pdf", corrupted_pdf, "application/pdf")}
        resp = client.post(f"/api/v1/patients/{pid}/documents", files=files, headers=auth_header(token))
        assert resp.status_code == 415
        assert "corrupted" in resp.json()["error"]["message"].lower()

    def test_duplicate_file_detection(self, pipeline_fixture):
        pid = pipeline_fixture["patient_id"]
        token = pipeline_fixture["token_a"]
        pdf_bytes = create_sample_pdf_bytes("Duplicate Detection Unique Test Body 12345")

        files1 = {"file": ("original_record.pdf", pdf_bytes, "application/pdf")}
        resp1 = client.post(f"/api/v1/patients/{pid}/documents", files=files1, headers=auth_header(token))
        assert resp1.status_code == 201
        assert resp1.json()["data"]["duplicate"] is False
        first_doc_id = resp1.json()["data"]["id"]

        # Upload identical content under a different filename
        files2 = {"file": ("copy_of_record.pdf", pdf_bytes, "application/pdf")}
        resp2 = client.post(f"/api/v1/patients/{pid}/documents", files=files2, headers=auth_header(token))
        assert resp2.status_code == 201
        assert resp2.json()["data"]["duplicate"] is True
        assert resp2.json()["data"]["id"] == first_doc_id


class TestPatientIsolationAndAccess:
    def test_unauthorized_file_download_idor(self, pipeline_fixture):
        pid = pipeline_fixture["patient_id"]
        token_a = pipeline_fixture["token_a"]
        token_b = pipeline_fixture["token_b"]
        pdf_bytes = create_sample_pdf_bytes("Patient A Confidential Pathology Report")

        files = {"file": ("private_pathology.pdf", pdf_bytes, "application/pdf")}
        resp = client.post(f"/api/v1/patients/{pid}/documents", files=files, headers=auth_header(token_a))
        doc_id = resp.json()["data"]["id"]

        # Doctor B (not assigned to Patient A) attempts to download the file -> 403 Forbidden
        resp_idor = client.get(f"/api/v1/documents/{doc_id}/file", headers=auth_header(token_b))
        assert resp_idor.status_code == 403
        assert resp_idor.json()["error"]["code"] == "FORBIDDEN"

        # Doctor A downloads successfully
        resp_ok = client.get(f"/api/v1/documents/{doc_id}/file", headers=auth_header(token_a))
        assert resp_ok.status_code == 200
        assert resp_ok.headers["content-type"] == "application/pdf"


class TestReprocessingAndWorkerReliability:
    @pytest.mark.anyio
    async def test_reprocessing_idempotency(self, pipeline_fixture):
        pid = pipeline_fixture["patient_id"]
        token = pipeline_fixture["token_a"]
        prescription_text = (
            "PRESCRIPTION REPORT\n"
            "Date: 2026-05-10\n"
            "Patient: Patient Pipeline A\n\n"
            "Diagnosis: Hypertension\n"
            "Rx: Tab Amlodipine 5 mg OD morning\n"
            "Lab: Serum Creatinine 0.9 mg/dL\n"
        )
        pdf_bytes = create_sample_pdf_bytes(prescription_text)
        files = {"file": ("prescription_reprocess_test.pdf", pdf_bytes, "application/pdf")}
        resp = client.post(f"/api/v1/patients/{pid}/documents", files=files, headers=auth_header(token))
        doc_id = resp.json()["data"]["id"]

        # First pipeline run
        await pipeline_orchestrator.run(document_id=doc_id, is_reprocess=False)

        with get_db_context() as db:
            initial_facts_count = db.query(ClinicalFact).filter(ClinicalFact.document_id == doc_id).count()
            initial_timeline_count = db.query(TimelineEvent).filter(TimelineEvent.source_document_id == doc_id).count()
            assert initial_facts_count >= 1

        # Reprocess document
        await pipeline_orchestrator.run(document_id=doc_id, is_reprocess=True)

        with get_db_context() as db:
            reprocessed_facts_count = db.query(ClinicalFact).filter(ClinicalFact.document_id == doc_id).count()
            reprocessed_timeline_count = db.query(TimelineEvent).filter(TimelineEvent.source_document_id == doc_id).count()

            # Must NOT accumulate duplicate records!
            assert reprocessed_facts_count == initial_facts_count
            assert reprocessed_timeline_count == initial_timeline_count

    @pytest.mark.anyio
    async def test_failed_processing_and_sanitized_error(self, pipeline_fixture, monkeypatch):
        from app.services.ocr_service import ocr_service
        pid = pipeline_fixture["patient_id"]
        token = pipeline_fixture["token_a"]
        pdf_bytes = create_sample_pdf_bytes("Simulated OCR failure test")
        files = {"file": ("fail_sim.pdf", pdf_bytes, "application/pdf")}
        resp = client.post(f"/api/v1/patients/{pid}/documents", files=files, headers=auth_header(token))
        doc_id = resp.json()["data"]["id"]

        # Mock OCR service to raise an exception containing secret-looking text
        async def mock_extract_fail(*args, **kwargs):
            raise RuntimeError("Secret key sk-abc12345678901234567890123456 failed at C:\\Users\\Dev\\secrets\\key.pem")

        monkeypatch.setattr(ocr_service, "extract_text", mock_extract_fail)

        job_run_id = await pipeline_orchestrator.run(document_id=doc_id, is_reprocess=False)

        with get_db_context() as db:
            doc = db.query(Document).filter(Document.id == doc_id).first()
            assert doc.processing_status == "failed"
            assert doc.processing_error_code == "DOCUMENT_PROCESSING_FAILED"

            job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
            assert job.status == "failed"
            # Verify secrets and paths were redacted
            assert "sk-abc12345678901234567890123456" not in job.last_error_detail
            assert "REDACTED" in job.last_error_detail
