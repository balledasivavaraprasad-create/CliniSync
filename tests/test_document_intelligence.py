import asyncio
import os
import fitz
import pytest
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.services.pipeline_orchestrator import pipeline_orchestrator
from app.services.document_service import DocumentService
from app.utils.ids import patient_id

@pytest.mark.anyio
async def test_document_pipeline_e2e(tmp_path):
    # 1. Create a dummy patient
    with get_db_context() as db:
        p = Patient(id=patient_id(), full_name="Document Pipeline Test Patient")
        db.add(p)
        db.commit()
        pid = p.id

    # 2. Create a test PDF with medical prescription content
    pdf_path = tmp_path / "test_prescription.pdf"
    doc = fitz.open()
    page = doc.new_page()
    text = (
        "CLINICAL CONSULTATION & PRESCRIPTION\n"
        "Date: 2026-09-20\n"
        "Patient: Document Pipeline Test Patient\n\n"
        "Chief Complaint: Elevated blood sugars and fatigue\n"
        "Diagnosis: Type 2 Diabetes Mellitus, Essential Hypertension\n\n"
        "Rx:\n"
        "1. Tab Metformin 500 mg BD after meals\n"
        "2. Tab Telmisartan 40 mg OD morning\n\n"
        "Lab Investigations:\n"
        "HbA1c: 7.8 % (Ref: < 5.7 %)\n"
        "Fasting Blood Sugar: 142 mg/dL (Ref: 70-100 mg/dL)\n\n"
        "Advice: Regular exercise and low carbohydrate diet."
    )
    page.insert_text((50, 72), text, fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    # 3. Store document via DocumentService
    with open(pdf_path, "rb") as f:
        content = f.read()

    with get_db_context() as db:
        saved_doc, is_dup = DocumentService.store_document(
            db=db,
            patient_id=pid,
            filename="test_prescription.pdf",
            content=content,
            declared_mime="application/pdf",
            uploaded_via="upload",
            actor="test_runner"
        )
        doc_id = saved_doc.id

    # 4. Run pipeline
    job_id = await pipeline_orchestrator.run(doc_id)
    assert job_id is not None

    # 5. Verify persisted results
    with get_db_context() as db:
        d = db.query(Document).filter(Document.id == doc_id).first()
        assert d is not None
        assert d.processing_status in ["complete", "needs_review"]
        assert d.page_count == 1

        # Check facts
        facts = db.query(ClinicalFact).filter(ClinicalFact.document_id == doc_id).all()
        assert len(facts) >= 3, f"Expected at least 3 clinical facts, found {len(facts)}"
        
        # Check that provenance was verified
        for f in facts:
            assert f.source_text != ""
            assert f.source_page == 1
            assert f.provenance_verified is True

        # Check medications
        meds = db.query(Medication).filter(Medication.patient_id == pid).all()
        assert len(meds) >= 1
        med_names = [m.canonical_name for m in meds]
        assert "metformin" in med_names or "telmisartan" in med_names

        # Check investigations
        invs = db.query(Investigation).filter(Investigation.patient_id == pid).all()
        assert len(invs) >= 1
        inv_keys = [i.test_name_canonical for i in invs]
        assert "hba1c" in inv_keys or "fasting_glucose" in inv_keys

    print("\n✓ Phase 4 Document Intelligence pipeline verified successfully!")
