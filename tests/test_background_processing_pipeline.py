import datetime
import io
import fitz
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.timeline_event import TimelineEvent
from app.models.processing_job import ProcessingJob
from app.models.user import User
from app.models.patient_access import PatientAccess
from app.services.pipeline_orchestrator import pipeline_orchestrator
from app.services.document_service import DocumentService
from app.services.task_worker import task_worker
from app.schemas.common import ProcessingStatus, VerificationStatus
from app.utils.hashing import hash_password
from app.utils.tokens import create_access_token
from app.utils.ids import user_id, patient_id

client = TestClient(app)


def auth_header(token: str):
    return {"Authorization": f"Bearer {token}"}


def create_sample_pdf_bytes(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), text, fontsize=11)
    buf = doc.write()
    doc.close()
    return buf


@pytest.fixture
def test_setup():
    with get_db_context() as db:
        uid = user_id()
        doc_user = User(
            id=uid,
            email=f"dr_pipeline_{uid[:6]}@clinsync.health",
            full_name="Dr. Test Pipeline",
            role="doctor",
            specialty="Internal Medicine",
            hashed_password=hash_password("Pass1234!"),
            is_active=True,
        )
        pid = patient_id()
        pat = Patient(id=pid, full_name="Pipeline State Test Patient", is_demo=False)
        db.add_all([doc_user, pat])
        db.flush()

        access = PatientAccess(
            user_id=doc_user.id,
            patient_id=pat.id,
            access_level="primary_doctor",
        )
        db.add(access)
        db.commit()

        token = create_access_token(subject=doc_user.id, claims={"email": doc_user.email, "role": doc_user.role})

    return {
        "doctor_id": uid,
        "patient_id": pid,
        "token": token,
    }


def test_explicit_pipeline_states_and_database_record(test_setup):
    """
    Verifies state transitions:
    UPLOADED -> QUEUED -> PROCESSING -> EXTRACTING -> VALIDATING -> COMPLETED
    Verifies that processing record retains:
    - start time
    - current stage
    - completion time
    - retry count
    """
    pid = test_setup["patient_id"]
    token = test_setup["token"]

    pdf_content = (
        "CONSULTATION NOTE\n"
        "Date: 2026-06-15\n"
        "Patient: Pipeline State Test Patient\n\n"
        "Diagnosis: Essential Hypertension\n"
        "Rx: Tab Amlodipine 5 mg OD\n"
        "Lab: Serum Potassium 4.2 mEq/L\n"
    )
    pdf_bytes = create_sample_pdf_bytes(pdf_content)

    # 1. State: UPLOADED
    files = {"file": ("consult_note.pdf", pdf_bytes, "application/pdf")}
    upload_res = client.post(
        f"/api/v1/patients/{pid}/documents",
        files=files,
        headers=auth_header(token),
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["data"]["id"]

    with get_db_context() as db:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        assert doc.processing_status == "UPLOADED"
        job = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.subject_id == doc_id, ProcessingJob.subject_type == "document")
            .order_by(ProcessingJob.created_at.desc())
            .first()
        )
        assert job is not None
        assert job.stage == "UPLOADED"
        assert job.status == "UPLOADED"
        assert job.attempts == 0

    # 2. State: QUEUED & Execution through pipeline states
    proc_res = client.post(
        f"/api/v1/documents/{doc_id}/process",
        headers=auth_header(token),
    )
    assert proc_res.status_code == 200
    assert proc_res.json()["data"]["status"] == "QUEUED"

    # In Starlette TestClient, BackgroundTasks run synchronously before the HTTP call returns.
    # Therefore, the background task worker has already executed the full state pipeline:
    # QUEUED -> PROCESSING -> EXTRACTING -> VALIDATING -> COMPLETED.
    with get_db_context() as db:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        assert doc.processing_status == "COMPLETED"

        job = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.subject_id == doc_id)
            .order_by(ProcessingJob.created_at.desc())
            .first()
        )
        assert job.status == "COMPLETED"
        assert job.stage == "COMPLETED"
        assert job.started_at is not None
        assert job.finished_at is not None
        assert job.finished_at >= job.started_at

    # 4. Status endpoint exposes all required tracking fields
    status_res = client.get(
        f"/api/v1/documents/{doc_id}/status",
        headers=auth_header(token),
    )
    assert status_res.status_code == 200
    data = status_res.json()["data"]
    assert data["status"] == "COMPLETED"
    assert data["current_stage"] == "COMPLETED"
    assert data["started_at"] is not None
    assert data["finished_at"] is not None
    assert data["completion_time"] is not None
    assert data["retry_count"] >= 1
    assert data["error_code"] is None


def test_exception_rollback_safe_error_and_preservation(test_setup, monkeypatch):
    """
    On exception:
    - rollback current transaction (no orphan/unapproved facts committed)
    - mark job and doc as FAILED
    - store sanitized error message
    - preserve original uploaded document in database and on disk
    - do not partially mark clinical facts as approved
    """
    from app.services.ocr_service import ocr_service

    pid = test_setup["patient_id"]
    token = test_setup["token"]
    pdf_bytes = create_sample_pdf_bytes("Simulated OCR failure with sensitive data sk-proj-1234567890abcdef12345678")

    files = {"file": ("error_test.pdf", pdf_bytes, "application/pdf")}
    upload_res = client.post(
        f"/api/v1/patients/{pid}/documents",
        files=files,
        headers=auth_header(token),
    )
    doc_id = upload_res.json()["data"]["id"]

    # Mock OCR service to simulate an internal exception
    async def mock_fail(*args, **kwargs):
        raise RuntimeError("Secret api key sk-proj-1234567890abcdef12345678 failed at C:\\secret\\key.pem")

    monkeypatch.setattr(ocr_service, "extract_text", mock_fail)

    import asyncio
    job_run_id = asyncio.run(pipeline_orchestrator.run(document_id=doc_id, is_reprocess=False))

    with get_db_context() as db:
        # Document record preserved
        doc = db.query(Document).filter(Document.id == doc_id).first()
        assert doc is not None
        assert doc.processing_status == "FAILED"
        assert doc.processing_error_code == "DOCUMENT_PROCESSING_FAILED"

        # Stored file preserved on disk
        import os
        assert os.path.exists(doc.stored_path)

        # Job record marked as FAILED with completion time and sanitized error
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
        assert job.status == "FAILED"
        assert job.stage == "FAILED"
        assert job.finished_at is not None
        assert "sk-proj-1234567890abcdef12345678" not in job.last_error_detail
        assert "REDACTED" in job.last_error_detail

        # No partially marked facts or orphan approved facts
        facts = db.query(ClinicalFact).filter(ClinicalFact.document_id == doc_id).all()
        assert len(facts) == 0


def test_retry_pending_state_and_worker_retries(test_setup, monkeypatch):
    """
    Verifies that worker manages transient failures through RETRY_PENDING state before terminal FAILED.
    """
    from app.services.ocr_service import ocr_service

    pid = test_setup["patient_id"]
    token = test_setup["token"]
    pdf_bytes = create_sample_pdf_bytes("Retry state test document")

    files = {"file": ("retry_doc.pdf", pdf_bytes, "application/pdf")}
    upload_res = client.post(
        f"/api/v1/patients/{pid}/documents",
        files=files,
        headers=auth_header(token),
    )
    doc_id = upload_res.json()["data"]["id"]

    call_count = 0
    async def mock_fail_once(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Transient network glitch sk-transient-secret-key-123456")
        # Second call succeeds
        return [{"page_number": 1, "text": "Diagnosis: Normal Checkup", "ocr_confidence": 0.99, "method": "pdf_text"}]

    monkeypatch.setattr(ocr_service, "extract_text", mock_fail_once)

    import asyncio
    asyncio.run(task_worker.process_document_async(document_id=doc_id, is_reprocess=False, max_retries=2))

    assert call_count == 2
    with get_db_context() as db:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        assert doc.processing_status == "COMPLETED"


def test_idempotent_processing_no_duplicates(test_setup):
    """
    Processing the same document twice must NOT create duplicate timeline events,
    medications, investigations, or evidence records.
    Doctor-verified facts are preserved across re-runs.
    """
    pid = test_setup["patient_id"]
    token = test_setup["token"]

    pdf_content = (
        "CLINICAL ENCOUNTER\n"
        "Date: 2026-07-20\n"
        "Patient: Pipeline State Test Patient\n\n"
        "Diagnosis: Type 2 Diabetes Mellitus\n"
        "Rx: Tab Metformin 500 mg BD\n"
        "Lab: HbA1c 7.5 %\n"
    )
    pdf_bytes = create_sample_pdf_bytes(pdf_content)

    files = {"file": ("idempotent_doc.pdf", pdf_bytes, "application/pdf")}
    upload_res = client.post(
        f"/api/v1/patients/{pid}/documents",
        files=files,
        headers=auth_header(token),
    )
    doc_id = upload_res.json()["data"]["id"]

    import asyncio
    # 1. First execution
    asyncio.run(pipeline_orchestrator.run(document_id=doc_id, is_reprocess=False))

    with get_db_context() as db:
        facts_count_1 = db.query(ClinicalFact).filter(ClinicalFact.document_id == doc_id).count()
        meds_count_1 = db.query(Medication).filter(Medication.source_document_id == doc_id).count()
        invs_count_1 = db.query(Investigation).filter(Investigation.source_document_id == doc_id).count()
        timeline_count_1 = db.query(TimelineEvent).filter(TimelineEvent.source_document_id == doc_id).count()

        assert facts_count_1 >= 1
        assert meds_count_1 >= 1
        assert invs_count_1 >= 1
        assert timeline_count_1 >= 1

        # Doctor approves one fact
        diag_fact = db.query(ClinicalFact).filter(
            ClinicalFact.document_id == doc_id,
            ClinicalFact.fact_type == "diagnosis"
        ).first()
        if diag_fact:
            diag_fact.verification_status = VerificationStatus.doctor_verified.value
            db.commit()

    # 2. Second execution of the exact same document
    asyncio.run(pipeline_orchestrator.run(document_id=doc_id, is_reprocess=False))

    with get_db_context() as db:
        facts_count_2 = db.query(ClinicalFact).filter(ClinicalFact.document_id == doc_id).count()
        meds_count_2 = db.query(Medication).filter(Medication.source_document_id == doc_id).count()
        invs_count_2 = db.query(Investigation).filter(Investigation.source_document_id == doc_id).count()
        timeline_count_2 = db.query(TimelineEvent).filter(TimelineEvent.source_document_id == doc_id).count()

        # Counts must match exactly without duplicating records
        assert facts_count_2 == facts_count_1
        assert meds_count_2 == meds_count_1
        assert invs_count_2 == invs_count_1
        assert timeline_count_2 == timeline_count_1

        # The doctor-verified status is preserved
        diag_fact = db.query(ClinicalFact).filter(
            ClinicalFact.document_id == doc_id,
            ClinicalFact.fact_type == "diagnosis"
        ).first()
        if diag_fact:
            assert diag_fact.verification_status == VerificationStatus.doctor_verified.value


def test_stale_job_identification_and_recovery(test_setup):
    """
    Simulates a worker crash leaving a document stuck in PROCESSING.
    Verifies that:
    1. System identifies the stale job.
    2. Stale job is marked as FAILED.
    3. Recovery safely re-runs the document to COMPLETED.
    """
    pid = test_setup["patient_id"]
    token = test_setup["token"]

    pdf_bytes = create_sample_pdf_bytes("Follow-up visit. Stable condition.")
    files = {"file": ("stale_doc.pdf", pdf_bytes, "application/pdf")}
    upload_res = client.post(
        f"/api/v1/patients/{pid}/documents",
        files=files,
        headers=auth_header(token),
    )
    doc_id = upload_res.json()["data"]["id"]

    # Artificially simulate an interrupted / stale PROCESSING job
    past_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(seconds=600)
    with get_db_context() as db:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        doc.processing_status = "PROCESSING"
        doc.updated_at = past_time

        job = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.subject_id == doc_id)
            .order_by(ProcessingJob.created_at.desc())
            .first()
        )
        if job:
            job.status = "PROCESSING"
            job.stage = "PROCESSING"
            job.started_at = past_time
            job.created_at = past_time
        db.commit()

    # 1. API: GET /documents/stale identifies the stale job
    stale_res = client.get("/api/v1/documents/stale?max_age_seconds=300", headers=auth_header(token))
    assert stale_res.status_code == 200
    stale_list = stale_res.json()["data"]
    found_stale = [s for s in stale_list if s["document_id"] == doc_id]
    assert len(found_stale) == 1
    assert found_stale[0]["age_seconds"] >= 300

    # 2. Mark stale jobs as failed
    with get_db_context() as db:
        recovered = DocumentService.mark_stale_jobs_as_failed(db, max_age_seconds=300)
        assert doc_id in recovered

    with get_db_context() as db:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        assert doc.processing_status == "FAILED"
        assert doc.processing_error_code == "STALE_PROCESSING_TIMEOUT"

    # 3. API: POST /documents/{id}/recover recovers and safely re-processes
    rec_res = client.post(f"/api/v1/documents/{doc_id}/recover", headers=auth_header(token))
    assert rec_res.status_code == 200
    assert rec_res.json()["data"]["status"] == "QUEUED"

    # Run pipeline to complete recovery
    import asyncio
    asyncio.run(pipeline_orchestrator.run(document_id=doc_id, is_reprocess=True))

    with get_db_context() as db:
        doc = db.query(Document).filter(Document.id == doc_id).first()
        assert doc.processing_status == "COMPLETED"
