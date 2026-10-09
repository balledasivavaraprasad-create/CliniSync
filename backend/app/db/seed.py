import argparse
import datetime
import json
import os
import shutil
from pathlib import Path
from typing import List, Optional
import pymupdf
import structlog
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db_context, Base, engine, ensure_schema
from app.models.patient import Patient
from app.models.document import Document, DocumentPage
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.timeline_event import TimelineEvent
from app.models.contradiction import Contradiction
from app.models.brief import Brief
from app.models.consultation import Consultation, ConsultationVersion
from app.models.clinical_memory import ClinicalMemory
from app.models.processing_job import ProcessingJob
from app.models.audit_log import AuditLog
from app.models.validation_report import ValidationReport
from app.schemas.common import (
    DocumentType,
    ProcessingStatus,
    FactType,
    VerificationStatus,
    ConfidenceBand,
    IssueType,
    Severity,
    MedStatus,
    ConsultationOrigin,
)
from app.utils.hashing import compute_sha256
from app.utils.ids import (
    document_id,
    fact_id,
    medication_id,
    investigation_id,
    timeline_event_id,
    contradiction_id,
    brief_id,
    consultation_id,
    consultation_version_id,
    clinical_memory_id,
    validation_report_id,
)
from app.services.medication_service import medication_service
from app.services.contradiction_service import contradiction_service
from app.services.missing_info_service import missing_info_service

logger = structlog.get_logger(__name__)

DEMO_PATIENT_ID = "pat_demo_patient_001"
DEMO_PATIENT_NAME = "Demo Patient"

# Repository-root relative, not CWD relative: `Path("tests/fixtures")` only
# resolved when the command was run from the repo root, so `python -m
# app.db.seed` from anywhere else failed to find the demo PDFs.
FIXTURES_DIR = Path(__file__).resolve().parents[3] / "tests" / "fixtures"


def generate_pdf(filepath: Path, title: str, date_str: str, body_lines: List[str]) -> bytes:
    """Generate a clean text-layer PDF using PyMuPDF"""
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)  # A4

    # Header
    page.insert_text((50, 60), title, fontsize=16, fontname="helv", color=(0.1, 0.2, 0.5))
    page.insert_text((50, 85), f"Date: {date_str}   |   Patient: {DEMO_PATIENT_NAME} (Age: 52, Male)", fontsize=10, fontname="helv", color=(0.3, 0.3, 0.3))
    page.draw_line((50, 95), (545, 95), color=(0.7, 0.7, 0.7), width=1)

    # Body
    y = 120
    for line in body_lines:
        if line.startswith("## "):
            y += 10
            page.insert_text((50, y), line[3:], fontsize=12, fontname="helv", color=(0.15, 0.25, 0.45))
            y += 18
        elif line.startswith("- "):
            page.insert_text((65, y), line, fontsize=10, fontname="helv", color=(0.2, 0.2, 0.2))
            y += 15
        else:
            page.insert_text((50, y), line, fontsize=10, fontname="helv", color=(0.2, 0.2, 0.2))
            y += 15

    # Footer
    page.insert_text((50, 800), "ClinSync Demo Medical Record  •  Source: seed  •  Confidential Clinical Intelligence", fontsize=8, fontname="helv", color=(0.5, 0.5, 0.5))

    filepath.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(filepath))
    data = doc.tobytes()
    doc.close()
    return data


def create_demo_fixtures():
    """Generates the 6 required PDFs for Section 18 offline demo data"""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    docs_info = [
        (
            FIXTURES_DIR / "doc1_consultation_jan2026.pdf",
            "INITIAL CLINICAL CONSULTATION",
            "10/01/2026",
            [
                "## Chief Complaint",
                "Polyuria, polydipsia, and fatigue for 3 weeks.",
                "## History of Present Illness",
                "Increased thirst and frequent urination. No prior history of diabetes mellitus.",
                "Allergies: Not documented in initial record.",
                "## Clinical Assessment & Diagnoses",
                "- Type 2 Diabetes Mellitus (new onset)",
                "## Initial Baseline Investigations",
                "- HbA1c: 8.4 % (Ref: 4.0 - 5.6 %) [HIGH]",
                "- Fasting Blood Sugar: 168 mg/dL (Ref: 70 - 100 mg/dL) [HIGH]",
                "## Plan",
                "Initiate dietary adjustments and schedule medication prescription.",
            ],
        ),
        (
            FIXTURES_DIR / "doc2_prescription_feb2026.pdf",
            "PRESCRIPTION RECORD",
            "15/02/2026",
            [
                "## Prescribed Medications",
                "1. Tab. Metformin 500 mg - 1 tablet once daily (OD) orally after meals.",
                "Duration: 60 days.",
                "Doctor: Dr. A. Sharma, MD (Reg: 48921)",
            ],
        ),
        (
            FIXTURES_DIR / "doc3_lab_report_apr2026.pdf",
            "LABORATORY DIAGNOSTIC REPORT",
            "18/04/2026",
            [
                "## Metabolic Panel & Glycemic Evaluation",
                "- HbA1c: 8.0 % (Ref: 4.0 - 5.6 %) [HIGH]",
                "- Fasting Blood Sugar: 142 mg/dL (Ref: 70 - 100 mg/dL) [HIGH]",
                "- Serum Creatinine: 0.9 mg/dL (Ref: 0.7 - 1.2 mg/dL) [NORMAL]",
                "Sample: Venous Blood  •  Method: HPLC / Enzymatic",
            ],
        ),
        (
            FIXTURES_DIR / "doc4_followup_consultation_jun2026.pdf",
            "FOLLOW-UP CONSULTATION NOTE",
            "20/06/2026",
            [
                "## Review of Symptoms",
                "Patient notes partial improvement in fatigue. Weight steady at 78 kg.",
                "## Current Medications",
                "- Metformin 500 mg once daily (reported good compliance).",
                "## Assessment",
                "- Suboptimally controlled Type 2 Diabetes Mellitus (HbA1c 8.0%).",
                "## Plan",
                "Maintain current therapy; prepare for dose intensification if glycemic target not reached in autumn.",
            ],
        ),
        (
            FIXTURES_DIR / "doc5_prescription_sep2026.pdf",
            "UPDATED PRESCRIPTION",
            "12/09/2026",
            [
                "## Updated Pharmacotherapy",
                "1. Tab. Metformin 500 mg - 1 tablet twice daily (BD) orally with meals.",
                "2. Tab. Glimepiride 1 mg - 1 tablet once daily (OD) orally before breakfast.",
                "## Conflicting Pharmacy Order Note (recorded 12/09/2026)",
                "- Tab. Metformin 1000 mg twice daily (BD) indicated in second outpatient voucher.",
                "Doctor: Dr. A. Sharma, MD",
            ],
        ),
        (
            FIXTURES_DIR / "doc6_discharge_diagnostic_sep2026.pdf",
            "DAYCARE DISCHARGE & DIAGNOSTIC SUMMARY",
            "28/09/2026",
            [
                "## Summary of Stay",
                "Admission Date: 28-09-2026   Discharge Date: 28/09/2026",
                "Indication: Comprehensive daycare metabolic and microvascular screening.",
                "## Discharge Laboratory Results",
                "- HbA1c: 7.8 % (Ref: 4.0 - 5.6 %) [HIGH]",
                "- Serum Creatinine: 0.9 mg/dL (Ref: 0.7 - 1.2 mg/dL) [NORMAL]",
                "## Longitudinal Observation",
                "HbA1c trend shows sequential reduction: 8.4% (Jan 2026) -> 8.0% (Apr 2026) -> 7.8% (Sep 2026).",
                "Advice: Continue dual oral hypoglycemic therapy under clinician supervision.",
            ],
        ),
    ]

    for path, title, d_str, lines in docs_info:
        generate_pdf(path, title, d_str, lines)


def reset_demo_patient(db: Session):
    """Cleanly purge demo patient records to guarantee idempotency"""
    logger.info("purging_previous_demo_patient", patient_id=DEMO_PATIENT_ID)

    # Delete related records
    db.query(AuditLog).filter(AuditLog.patient_id == DEMO_PATIENT_ID).delete()
    db.query(ValidationReport).filter(ValidationReport.subject_id.in_(
        db.query(Brief.id).filter(Brief.patient_id == DEMO_PATIENT_ID)
    )).delete(synchronize_session=False)
    db.query(ClinicalMemory).filter(ClinicalMemory.patient_id == DEMO_PATIENT_ID).delete()
    db.query(ConsultationVersion).filter(ConsultationVersion.consultation_id.in_(
        db.query(Consultation.id).filter(Consultation.patient_id == DEMO_PATIENT_ID)
    )).delete(synchronize_session=False)
    db.query(Consultation).filter(Consultation.patient_id == DEMO_PATIENT_ID).delete()
    db.query(Brief).filter(Brief.patient_id == DEMO_PATIENT_ID).delete()
    db.query(Contradiction).filter(Contradiction.patient_id == DEMO_PATIENT_ID).delete()
    db.query(TimelineEvent).filter(TimelineEvent.patient_id == DEMO_PATIENT_ID).delete()
    db.query(Investigation).filter(Investigation.patient_id == DEMO_PATIENT_ID).delete()
    db.query(Medication).filter(Medication.patient_id == DEMO_PATIENT_ID).delete()
    db.query(ClinicalFact).filter(ClinicalFact.patient_id == DEMO_PATIENT_ID).delete()

    # Documents: clear children first, then the rows in one statement. The
    # previous per-document `db.delete()` raced the flush — `PRAGMA
    # foreign_keys=ON` means deleting the Patient cascades the documents away, so
    # the ORM deletes matched 0 rows and SQLAlchemy raised an SAWarning.
    doc_ids = [
        row[0]
        for row in db.query(Document.id)
        .filter(Document.patient_id == DEMO_PATIENT_ID)
        .all()
    ]
    if doc_ids:
        db.query(DocumentPage).filter(DocumentPage.document_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(ProcessingJob).filter(ProcessingJob.subject_id.in_(doc_ids)).delete(
            synchronize_session=False
        )
        db.query(AuditLog).filter(AuditLog.patient_id == DEMO_PATIENT_ID).delete(
            synchronize_session=False
        )
        db.query(Document).filter(Document.id.in_(doc_ids)).delete(
            synchronize_session=False
        )

    db.query(Patient).filter(Patient.id == DEMO_PATIENT_ID).delete(
        synchronize_session=False
    )
    db.commit()

    # Clear storage folder
    demo_storage = settings.storage_path / "patients" / DEMO_PATIENT_ID
    if demo_storage.exists():
        shutil.rmtree(demo_storage)


def seed_demo_data(reset: bool = True):
    """Seed the database with the complete 6-document longitudinal demo patient"""
    logger.info("seeding_demo_data", reset=reset)

    # A fresh clone has no tables, and without this the seed dies on
    # `no such table: patients`. The server creates the schema on boot, but the
    # seed is also a documented way to start from nothing, so it must not depend
    # on the server having run first.
    if not ensure_schema():
        logger.error(
            "seed_schema_unavailable",
            note="could not create the schema; check DATABASE_URL",
        )
        raise RuntimeError("database schema is incomplete — cannot seed")

    create_demo_fixtures()

    with get_db_context() as db:
        if reset:
            reset_demo_patient(db)

        # 1. Create Patient
        patient = Patient(
            id=DEMO_PATIENT_ID,
            full_name=DEMO_PATIENT_NAME,
            date_of_birth=datetime.date(1974, 5, 14),
            age_years=52,
            sex="male",
            contact_ref="+91 98765 43210",
            is_demo=True,
            last_activity_at=datetime.datetime(2026, 9, 28, 14, 0, 0, tzinfo=datetime.timezone.utc),
        )
        db.add(patient)
        db.flush()

        patient_doc_dir = settings.storage_path / "patients" / DEMO_PATIENT_ID / "documents"
        patient_doc_dir.mkdir(parents=True, exist_ok=True)

        doc_configs = [
            {
                "id": "doc_demo_001_consult_jan",
                "filename": "doc1_consultation_jan2026.pdf",
                "type": DocumentType.consultation_note.value,
                "date": datetime.datetime(2026, 1, 10, 10, 30, tzinfo=datetime.timezone.utc),
                "text": (
                    "INITIAL CLINICAL CONSULTATION\n"
                    "Date: 10/01/2026   |   Patient: Demo Patient (Age: 52, Male)\n"
                    "Chief Complaint: Polyuria, polydipsia, and fatigue for 3 weeks.\n"
                    "History of Present Illness: Increased thirst and frequent urination. No prior history of diabetes mellitus.\n"
                    "Allergies: Not documented in initial record.\n"
                    "Clinical Assessment & Diagnoses: Type 2 Diabetes Mellitus (new onset)\n"
                    "Initial Baseline Investigations:\n"
                    "- HbA1c: 8.4 % (Ref: 4.0 - 5.6 %) [HIGH]\n"
                    "- Fasting Blood Sugar: 168 mg/dL (Ref: 70 - 100 mg/dL) [HIGH]\n"
                    "Plan: Initiate dietary adjustments and schedule medication prescription."
                ),
                "facts": [
                    {
                        "type": FactType.diagnosis.value,
                        "value": "Type 2 Diabetes Mellitus",
                        "norm": {"diagnosis": "type 2 diabetes mellitus"},
                        "source_text": "Type 2 Diabetes Mellitus (new onset)",
                    },
                    {
                        "type": FactType.symptom.value,
                        "value": "Polyuria",
                        "norm": {"symptom": "polyuria"},
                        "source_text": "Polyuria, polydipsia, and fatigue for 3 weeks.",
                    },
                    {
                        "type": FactType.symptom.value,
                        "value": "Polydipsia",
                        "norm": {"symptom": "polydipsia"},
                        "source_text": "Polyuria, polydipsia, and fatigue for 3 weeks.",
                    },
                    {
                        "type": FactType.symptom.value,
                        "value": "Fatigue",
                        "norm": {"symptom": "fatigue"},
                        "source_text": "Polyuria, polydipsia, and fatigue for 3 weeks.",
                    },
                ],
                "labs": [
                    {
                        "test_raw": "HbA1c",
                        "test_canon": "hba1c",
                        "val_num": 8.4,
                        "val_txt": "8.4",
                        "unit": "%",
                        "ref_low": 4.0,
                        "ref_high": 5.6,
                        "ref_txt": "4.0 - 5.6 %",
                        "flag": "high",
                        "source_text": "- HbA1c: 8.4 % (Ref: 4.0 - 5.6 %) [HIGH]",
                    },
                    {
                        "test_raw": "Fasting Blood Sugar",
                        "test_canon": "fasting_blood_glucose",
                        "val_num": 168.0,
                        "val_txt": "168",
                        "unit": "mg/dL",
                        "ref_low": 70.0,
                        "ref_high": 100.0,
                        "ref_txt": "70 - 100 mg/dL",
                        "flag": "high",
                        "source_text": "- Fasting Blood Sugar: 168 mg/dL (Ref: 70 - 100 mg/dL) [HIGH]",
                    },
                ],
                "meds": [],
            },
            {
                "id": "doc_demo_002_rx_feb",
                "filename": "doc2_prescription_feb2026.pdf",
                "type": DocumentType.prescription.value,
                "date": datetime.datetime(2026, 2, 15, 11, 0, tzinfo=datetime.timezone.utc),
                "text": (
                    "PRESCRIPTION RECORD\n"
                    "Date: 15/02/2026   |   Patient: Demo Patient (Age: 52, Male)\n"
                    "Prescribed Medications:\n"
                    "1. Tab. Metformin 500 mg - 1 tablet once daily (OD) orally after meals.\n"
                    "Duration: 60 days.\n"
                    "Doctor: Dr. A. Sharma, MD (Reg: 48921)"
                ),
                "facts": [],
                "labs": [],
                "meds": [
                    {
                        "name_raw": "Tab. Metformin 500 mg",
                        "name_canon": "metformin",
                        "strength_val": 500.0,
                        "strength_unit": "mg",
                        "dose_txt": "500 mg",
                        "freq_code": "OD",
                        "freq_txt": "once daily",
                        "status": MedStatus.previous.value,
                        "status_reason": "Superseded by Sep 2026 dose change",
                        "source_text": "Tab. Metformin 500 mg - 1 tablet once daily (OD) orally after meals.",
                    }
                ],
            },
            {
                "id": "doc_demo_003_lab_apr",
                "filename": "doc3_lab_report_apr2026.pdf",
                "type": DocumentType.lab_report.value,
                "date": datetime.datetime(2026, 4, 18, 9, 15, tzinfo=datetime.timezone.utc),
                "text": (
                    "LABORATORY DIAGNOSTIC REPORT\n"
                    "Date: 18/04/2026   |   Patient: Demo Patient (Age: 52, Male)\n"
                    "Metabolic Panel & Glycemic Evaluation\n"
                    "- HbA1c: 8.0 % (Ref: 4.0 - 5.6 %) [HIGH]\n"
                    "- Fasting Blood Sugar: 142 mg/dL (Ref: 70 - 100 mg/dL) [HIGH]\n"
                    "- Serum Creatinine: 0.9 mg/dL (Ref: 0.7 - 1.2 mg/dL) [NORMAL]\n"
                    "Sample: Venous Blood  •  Method: HPLC / Enzymatic"
                ),
                "facts": [],
                "labs": [
                    {
                        "test_raw": "HbA1c",
                        "test_canon": "hba1c",
                        "val_num": 8.0,
                        "val_txt": "8.0",
                        "unit": "%",
                        "ref_low": 4.0,
                        "ref_high": 5.6,
                        "ref_txt": "4.0 - 5.6 %",
                        "flag": "high",
                        "source_text": "- HbA1c: 8.0 % (Ref: 4.0 - 5.6 %) [HIGH]",
                    },
                    {
                        "test_raw": "Fasting Blood Sugar",
                        "test_canon": "fasting_blood_glucose",
                        "val_num": 142.0,
                        "val_txt": "142",
                        "unit": "mg/dL",
                        "ref_low": 70.0,
                        "ref_high": 100.0,
                        "ref_txt": "70 - 100 mg/dL",
                        "flag": "high",
                        "source_text": "- Fasting Blood Sugar: 142 mg/dL (Ref: 70 - 100 mg/dL) [HIGH]",
                    },
                    {
                        "test_raw": "Serum Creatinine",
                        "test_canon": "serum_creatinine",
                        "val_num": 0.9,
                        "val_txt": "0.9",
                        "unit": "mg/dL",
                        "ref_low": 0.7,
                        "ref_high": 1.2,
                        "ref_txt": "0.7 - 1.2 mg/dL",
                        "flag": "normal",
                        "source_text": "- Serum Creatinine: 0.9 mg/dL (Ref: 0.7 - 1.2 mg/dL) [NORMAL]",
                    },
                ],
                "meds": [],
            },
            {
                "id": "doc_demo_004_consult_jun",
                "filename": "doc4_followup_consultation_jun2026.pdf",
                "type": DocumentType.consultation_note.value,
                "date": datetime.datetime(2026, 6, 20, 15, 45, tzinfo=datetime.timezone.utc),
                "text": (
                    "FOLLOW-UP CONSULTATION NOTE\n"
                    "Date: 20/06/2026   |   Patient: Demo Patient (Age: 52, Male)\n"
                    "Review of Symptoms: Patient notes partial improvement in fatigue. Weight steady at 78 kg.\n"
                    "Current Medications: Metformin 500 mg once daily (reported good compliance).\n"
                    "Assessment: Suboptimally controlled Type 2 Diabetes Mellitus (HbA1c 8.0%).\n"
                    "Plan: Maintain current therapy; prepare for dose intensification if glycemic target not reached in autumn."
                ),
                "facts": [
                    {
                        "type": FactType.observation.value,
                        "value": "Weight 78 kg steady",
                        "norm": {"weight_kg": 78},
                        "source_text": "Weight steady at 78 kg.",
                    }
                ],
                "labs": [],
                "meds": [],
            },
            {
                "id": "doc_demo_005_rx_sep",
                "filename": "doc5_prescription_sep2026.pdf",
                "type": DocumentType.prescription.value,
                "date": datetime.datetime(2026, 9, 12, 12, 0, tzinfo=datetime.timezone.utc),
                "text": (
                    "UPDATED PRESCRIPTION\n"
                    "Date: 12/09/2026   |   Patient: Demo Patient (Age: 52, Male)\n"
                    "Updated Pharmacotherapy:\n"
                    "1. Tab. Metformin 500 mg - 1 tablet twice daily (BD) orally with meals.\n"
                    "2. Tab. Glimepiride 1 mg - 1 tablet once daily (OD) orally before breakfast.\n"
                    "Conflicting Pharmacy Order Note (recorded 12/09/2026):\n"
                    "- Tab. Metformin 1000 mg twice daily (BD) indicated in second outpatient voucher.\n"
                    "Doctor: Dr. A. Sharma, MD"
                ),
                "facts": [],
                "labs": [],
                "meds": [
                    {
                        "name_raw": "Tab. Metformin 500 mg",
                        "name_canon": "metformin",
                        "strength_val": 500.0,
                        "strength_unit": "mg",
                        "dose_txt": "500 mg",
                        "freq_code": "BD",
                        "freq_txt": "twice daily",
                        "status": MedStatus.current.value,
                        "status_reason": "Dose titrated up from 500 mg OD",
                        "source_text": "Tab. Metformin 500 mg - 1 tablet twice daily (BD) orally with meals.",
                    },
                    {
                        "name_raw": "Tab. Glimepiride 1 mg",
                        "name_canon": "glimepiride",
                        "strength_val": 1.0,
                        "strength_unit": "mg",
                        "dose_txt": "1 mg",
                        "freq_code": "OD",
                        "freq_txt": "once daily",
                        "status": MedStatus.current.value,
                        "status_reason": "New medication added Sep 2026",
                        "source_text": "Tab. Glimepiride 1 mg - 1 tablet once daily (OD) orally before breakfast.",
                    },
                    {
                        "name_raw": "Tab. Metformin 1000 mg",
                        "name_canon": "metformin",
                        "strength_val": 1000.0,
                        "strength_unit": "mg",
                        "dose_txt": "1000 mg",
                        "freq_code": "BD",
                        "freq_txt": "twice daily",
                        "status": MedStatus.uncertain.value,
                        "status_reason": "Conflicting strength in second outpatient voucher same date",
                        "source_text": "Tab. Metformin 1000 mg twice daily (BD) indicated in second outpatient voucher.",
                    },
                ],
            },
            {
                "id": "doc_demo_006_discharge_sep",
                "filename": "doc6_discharge_diagnostic_sep2026.pdf",
                "type": DocumentType.discharge_summary.value,
                "date": datetime.datetime(2026, 9, 28, 16, 30, tzinfo=datetime.timezone.utc),
                "text": (
                    "DAYCARE DISCHARGE & DIAGNOSTIC SUMMARY\n"
                    "Date: 28/09/2026   |   Patient: Demo Patient (Age: 52, Male)\n"
                    "Admission Date: 28-09-2026   Discharge Date: 28/09/2026\n"
                    "Indication: Comprehensive daycare metabolic and microvascular screening.\n"
                    "Discharge Laboratory Results:\n"
                    "- HbA1c: 7.8 % (Ref: 4.0 - 5.6 %) [HIGH]\n"
                    "- Serum Creatinine: 0.9 mg/dL (Ref: 0.7 - 1.2 mg/dL) [NORMAL]\n"
                    "Longitudinal Observation: HbA1c trend shows sequential reduction: 8.4% (Jan 2026) -> 8.0% (Apr 2026) -> 7.8% (Sep 2026).\n"
                    "Advice: Continue dual oral hypoglycemic therapy under clinician supervision."
                ),
                "facts": [],
                "labs": [
                    {
                        "test_raw": "HbA1c",
                        "test_canon": "hba1c",
                        "val_num": 7.8,
                        "val_txt": "7.8",
                        "unit": "%",
                        "ref_low": 4.0,
                        "ref_high": 5.6,
                        "ref_txt": "4.0 - 5.6 %",
                        "flag": "high",
                        "source_text": "- HbA1c: 7.8 % (Ref: 4.0 - 5.6 %) [HIGH]",
                    },
                    {
                        "test_raw": "Serum Creatinine",
                        "test_canon": "serum_creatinine",
                        "val_num": 0.9,
                        "val_txt": "0.9",
                        "unit": "mg/dL",
                        "ref_low": 0.7,
                        "ref_high": 1.2,
                        "ref_txt": "0.7 - 1.2 mg/dL",
                        "flag": "normal",
                        "source_text": "- Serum Creatinine: 0.9 mg/dL (Ref: 0.7 - 1.2 mg/dL) [NORMAL]",
                    },
                ],
                "meds": [],
            },
        ]

        # 2. Iterate through and persist documents, pages, facts, labs, meds, timeline events
        seeded_fact_map: dict = {}
        for cfg in doc_configs:
            fixture_path = FIXTURES_DIR / cfg["filename"]
            content = fixture_path.read_bytes()
            sha256 = compute_sha256(content)

            dest_path = patient_doc_dir / f"{cfg['id']}__{cfg['filename']}"
            dest_path.write_bytes(content)

            doc = Document(
                id=cfg["id"],
                patient_id=DEMO_PATIENT_ID,
                original_filename=cfg["filename"],
                stored_path=str(dest_path),
                mime_type="application/pdf",
                file_size=len(content),
                sha256=sha256,
                page_count=1,
                document_type=cfg["type"],
                document_date=cfg["date"],
                classification_confidence=0.98,
                processing_status=ProcessingStatus.complete.value,
                ocr_method="pdf_text",
                is_fallback=False,
                uploaded_via="upload",
            )
            db.add(doc)

            page = DocumentPage(
                document_id=cfg["id"],
                page_number=1,
                text=cfg["text"],
                ocr_confidence=0.99,
                method="pdf_text",
            )
            db.add(page)
            db.flush()

            page_text_lower = cfg["text"].lower()

            # Facts
            for f in cfg["facts"]:
                f_id = fact_id()
                seeded_fact_map[f"fact_{cfg['id']}_{f['type']}"] = f_id
                exact_idx = page_text_lower.find(f["source_text"].strip().lower())
                s_start = exact_idx if exact_idx != -1 else 0
                s_end = s_start + len(f["source_text"].strip())

                fact = ClinicalFact(
                    id=f_id,
                    patient_id=DEMO_PATIENT_ID,
                    document_id=cfg["id"],
                    fact_type=f["type"],
                    value=f["value"],
                    normalized_value=json.dumps(f["norm"]),
                    fact_date=cfg["date"],
                    confidence=0.95,
                    confidence_band=ConfidenceBand.high.value,
                    source_text=f["source_text"],
                    source_page=1,
                    source_span_start=s_start,
                    source_span_end=s_end,
                    provenance_verified=True,
                    verification_status=VerificationStatus.doctor_verified.value,
                    extraction_model="seed",
                )
                db.add(fact)

                # Timeline event for diagnosis
                if f["type"] == FactType.diagnosis.value:
                    evt = TimelineEvent(
                        id=timeline_event_id(),
                        patient_id=DEMO_PATIENT_ID,
                        event_type="diagnosis",
                        event_date=cfg["date"],
                        date_precision="day",
                        title=f"Diagnosis: {f['value']}",
                        summary=f"Clinical diagnosis of {f['value']}",
                        related_fact_ids=json.dumps([f_id]),
                        source_document_id=cfg["id"],
                        sort_key=cfg["date"].strftime("%Y-%m-%d"),
                    )
                    db.add(evt)

            # Labs
            for l in cfg["labs"]:
                f_id = fact_id()
                seeded_fact_map[f"lab_{cfg['id']}_{l['test_canon']}"] = f_id
                exact_idx = page_text_lower.find(l["source_text"].strip().lower())
                s_start = exact_idx if exact_idx != -1 else 0
                s_end = s_start + len(l["source_text"].strip())

                fact = ClinicalFact(
                    id=f_id,
                    patient_id=DEMO_PATIENT_ID,
                    document_id=cfg["id"],
                    fact_type=FactType.investigation.value,
                    value=f"{l['test_raw']}: {l['val_txt']} {l['unit']}",
                    normalized_value=json.dumps(l),
                    fact_date=cfg["date"],
                    confidence=0.95,
                    confidence_band=ConfidenceBand.high.value,
                    source_text=l["source_text"],
                    source_page=1,
                    source_span_start=s_start,
                    source_span_end=s_end,
                    provenance_verified=True,
                    verification_status=VerificationStatus.doctor_verified.value,
                    extraction_model="seed",
                )
                db.add(fact)
                db.flush()

                inv = Investigation(
                    id=investigation_id(),
                    patient_id=DEMO_PATIENT_ID,
                    fact_id=f_id,
                    test_name_raw=l["test_raw"],
                    test_name_canonical=l["test_canon"],
                    value_numeric=l["val_num"],
                    value_text=l["val_txt"],
                    unit=l["unit"],
                    reference_low=l["ref_low"],
                    reference_high=l["ref_high"],
                    reference_text=l["ref_txt"],
                    abnormal_flag=l["flag"],
                    observed_date=cfg["date"],
                    source_document_id=cfg["id"],
                    confidence=0.95,
                    group_key=f"{DEMO_PATIENT_ID}:{l['test_canon']}",
                )
                db.add(inv)

                evt = TimelineEvent(
                    id=timeline_event_id(),
                    patient_id=DEMO_PATIENT_ID,
                    event_type="investigation",
                    event_date=cfg["date"],
                    date_precision="day",
                    title=f"Lab: {l['test_canon'].replace('_', ' ').title()}",
                    summary=f"{l['test_canon'].title()}: {l['val_txt']} {l['unit']} (Ref: {l['ref_txt']})",
                    related_fact_ids=json.dumps([f_id]),
                    source_document_id=cfg["id"],
                    sort_key=cfg["date"].strftime("%Y-%m-%d"),
                )
                db.add(evt)

            # Meds
            for m in cfg["meds"]:
                f_id = fact_id()
                seeded_fact_map[f"med_{cfg['id']}_{m['name_canon']}"] = f_id
                exact_idx = page_text_lower.find(m["source_text"].strip().lower())
                s_start = exact_idx if exact_idx != -1 else 0
                s_end = s_start + len(m["source_text"].strip())

                fact = ClinicalFact(
                    id=f_id,
                    patient_id=DEMO_PATIENT_ID,
                    document_id=cfg["id"],
                    fact_type=FactType.medication.value,
                    value=f"{m['name_canon'].title()} {m['strength_val']} {m['strength_unit']}",
                    normalized_value=json.dumps(m),
                    fact_date=cfg["date"],
                    confidence=0.95,
                    confidence_band=ConfidenceBand.high.value,
                    source_text=m["source_text"],
                    source_page=1,
                    source_span_start=s_start,
                    source_span_end=s_end,
                    provenance_verified=True,
                    verification_status=VerificationStatus.doctor_verified.value,
                    extraction_model="seed",
                )
                db.add(fact)
                db.flush()

                med = Medication(
                    id=medication_id(),
                    patient_id=DEMO_PATIENT_ID,
                    fact_id=f_id,
                    canonical_name=m["name_canon"],
                    raw_name=m["name_raw"],
                    strength_value=m["strength_val"],
                    strength_unit=m["strength_unit"],
                    dose_text=m["dose_txt"],
                    frequency_code=m["freq_code"],
                    frequency_text=m["freq_txt"],
                    start_date=cfg["date"],
                    status=m["status"],
                    status_reason=m["status_reason"],
                    group_key=f"{DEMO_PATIENT_ID}:{m['name_canon']}",
                    confidence=0.95,
                    source_document_id=cfg["id"],
                )
                db.add(med)

                evt = TimelineEvent(
                    id=timeline_event_id(),
                    patient_id=DEMO_PATIENT_ID,
                    event_type="medication_start" if m["freq_code"] == "OD" and m["name_canon"] == "metformin" else "dose_change",
                    event_date=cfg["date"],
                    date_precision="day",
                    title=f"Medication: {m['name_canon'].title()}",
                    summary=f"{m['name_canon'].title()} {m['strength_val']} {m['strength_unit']} {m['freq_txt']}",
                    related_fact_ids=json.dumps([f_id]),
                    source_document_id=cfg["id"],
                    sort_key=cfg["date"].strftime("%Y-%m-%d"),
                )
                db.add(evt)

        db.commit()

        # 3. Run Clinical Intelligence Engines (Reconciliation, Contradiction, Missing Info)
        logger.info("recomputing_clinical_intelligence", patient_id=DEMO_PATIENT_ID)
        medication_service.reconcile(db, DEMO_PATIENT_ID)
        contradiction_service.recompute(db, DEMO_PATIENT_ID)
        missing_info_service.recompute(db, DEMO_PATIENT_ID)

        # 4. Generate Pre-Computed Verified Doctor Brief
        init_diag_fid = seeded_fact_map.get("fact_doc_demo_001_consult_jan_diagnosis", "fact_demo_diag_1")
        followup_diag_fid = seeded_fact_map.get("fact_doc_demo_004_consult_jun_diagnosis", init_diag_fid)
        metformin_fid = seeded_fact_map.get("med_doc_demo_005_rx_sep_metformin", "fact_demo_med_1")
        glimepiride_fid = seeded_fact_map.get("med_doc_demo_005_rx_sep_glimepiride", "fact_demo_med_2")
        hba1c_1_fid = seeded_fact_map.get("lab_doc_demo_001_consult_jan_hba1c", "fact_demo_lab_1")
        hba1c_2_fid = seeded_fact_map.get("lab_doc_demo_003_lab_apr_hba1c", "fact_demo_lab_2")
        hba1c_3_fid = seeded_fact_map.get("lab_doc_demo_006_discharge_sep_hba1c", "fact_demo_lab_3")
        creat_fid = seeded_fact_map.get("lab_doc_demo_006_discharge_sep_serum_creatinine", "fact_demo_lab_4")

        brief_data = {
            "patient": {"id": DEMO_PATIENT_ID, "name": DEMO_PATIENT_NAME, "age": 52},
            "specialty": "general_medicine",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "chief_complaint": {
                "text": "Polyuria, polydipsia, and fatigue documented at initial consultation.",
                "evidence_ids": [init_diag_fid],
                "confidence_band": "high",
            },
            "relevant_history": [
                {
                    "text": "Diagnosed with Type 2 Diabetes Mellitus in Jan 2026; steady weight 78 kg.",
                    "evidence_ids": [init_diag_fid, followup_diag_fid],
                    "confidence_band": "high",
                }
            ],
            "current_medications": [
                {
                    "name": "Metformin",
                    "strength": "500 mg",
                    "dose": "500 mg",
                    "frequency": "twice daily (BD)",
                    "status": "current",
                    "evidence_ids": [metformin_fid],
                    "confidence_band": "high",
                    "conflict_flag": True,
                },
                {
                    "name": "Glimepiride",
                    "strength": "1 mg",
                    "dose": "1 mg",
                    "frequency": "once daily (OD)",
                    "status": "current",
                    "evidence_ids": [glimepiride_fid],
                    "confidence_band": "high",
                    "conflict_flag": False,
                },
            ],
            "allergies": [
                {
                    "text": "Allergy status not documented in records.",
                    "evidence_ids": [],
                    "status": "not_documented",
                }
            ],
            "recent_investigations": [
                {
                    "test": "HbA1c",
                    "value": "7.8",
                    "unit": "%",
                    "reference": "4.0 - 5.6 %",
                    "date": "2026-09-28",
                    "abnormal": "high",
                    "evidence_ids": [hba1c_3_fid],
                },
                {
                    "test": "Serum Creatinine",
                    "value": "0.9",
                    "unit": "mg/dL",
                    "reference": "0.7 - 1.2 mg/dL",
                    "date": "2026-09-28",
                    "abnormal": "normal",
                    "evidence_ids": [creat_fid],
                },
            ],
            "important_trends": [
                {
                    "test": "HbA1c",
                    "series": [
                        {"date": "2026-01-10", "value": 8.4, "unit": "%"},
                        {"date": "2026-04-18", "value": 8.0, "unit": "%"},
                        {"date": "2026-09-28", "value": 7.8, "unit": "%"},
                    ],
                    "direction": "down",
                    "description": "HbA1c recorded 8.4% (Jan 2026), 8.0% (Apr 2026), 7.8% (Sep 2026): decreasing across three measurements.",
                    "evidence_ids": [hba1c_1_fid, hba1c_2_fid, hba1c_3_fid],
                }
            ],
            "attention_items": [
                {
                    "text": "Medication conflict: Two records on 12/09/2026 contain differing Metformin doses (500 mg BD vs 1000 mg BD).",
                    "severity": "medium",
                    "evidence_ids": [metformin_fid],
                },
                {
                    "text": "Missing information: Allergy status not documented in records.",
                    "severity": "medium",
                    "evidence_ids": [],
                },
            ],
            "contradictions": [
                {
                    "issue_id": "iss_metformin_conflict",
                    "text": "Two records on 12/09/2026 contain differing Metformin doses: 500 mg BD vs 1000 mg BD.",
                    "sources": [
                        "500 mg · twice daily · doc5_prescription_sep2026.pdf",
                        "1000 mg · twice daily · doc5_prescription_sep2026.pdf",
                    ],
                }
            ],
            "missing_information": [
                {
                    "prompt": "Document patient allergy status",
                    "reason": "Critical clinical safety data missing from medical history",
                },
                {
                    "prompt": "Confirm initial start date for Metformin therapy",
                    "reason": "Prescription duration noted without exact historic inception date",
                },
            ],
            "evidence_shortcuts": [
                {"evidence_id": init_diag_fid, "label": "Initial Diagnosis", "document_id": "doc_demo_001_consult_jan", "page": 1},
                {"evidence_id": metformin_fid, "label": "Updated Rx BD", "document_id": "doc_demo_005_rx_sep", "page": 1},
                {"evidence_id": hba1c_3_fid, "label": "Latest HbA1c 7.8%", "document_id": "doc_demo_006_discharge_sep", "page": 1},
            ],
            "disclaimer": "AI-assisted summary of source records. Not a diagnosis or treatment recommendation. Verify against sources.",
        }

        b_id = brief_id()
        brief_row = Brief(
            id=b_id,
            patient_id=DEMO_PATIENT_ID,
            specialty="general_medicine",
            content_json=json.dumps(brief_data),
            generation_model="seed",
            generation_source="seed",
            status="validated",
            input_fingerprint="fp_demo_patient_001",
        )
        db.add(brief_row)

        # 5. Create Approved Consultation with 3 versions (ai_generated -> doctor_edited -> approved)
        c_id = consultation_id()
        con = Consultation(
            id=c_id,
            patient_id=DEMO_PATIENT_ID,
            brief_id=b_id,
            specialty="general_medicine",
            status="approved",
            approved_at=datetime.datetime(2026, 9, 29, 10, 0, tzinfo=datetime.timezone.utc),
            approved_by="Dr. Willie Carter, MD",
        )
        db.add(con)
        db.flush()

        v1_id = consultation_version_id()
        v1_content = {
            "chief_complaint": "Polyuria and fatigue reviewed.",
            "history_of_present_illness": "Known T2DM under medical therapy.",
            "past_history": "Type 2 Diabetes Mellitus diagnosed Jan 2026.",
            "current_medications": [{"name": "Metformin", "dose": "500 mg BD"}, {"name": "Glimepiride", "dose": "1 mg OD"}],
            "allergies": [{"text": "None documented"}],
            "investigations_reviewed": [{"test": "HbA1c", "value": "7.8%"}],
            "examination": "",
            "assessment": "",
            "plan": "",
            "follow_up": "",
            "flags": [],
            "evidence_ids": ["doc_demo_001_consult_jan", "doc_demo_005_rx_sep", "doc_demo_006_discharge_sep"],
        }
        v1 = ConsultationVersion(
            id=v1_id,
            consultation_id=c_id,
            version_number=1,
            origin=ConsultationOrigin.ai_generated.value,
            content_json=json.dumps(v1_content),
            change_summary="Initial AI consultation draft from clinical records",
            edited_by="ai",
        )
        db.add(v1)

        v2_id = consultation_version_id()
        v2_content = dict(v1_content)
        v2_content["examination"] = "BP: 124/78 mmHg. Chest clear. No peripheral pedal edema."
        v2_content["assessment"] = "Type 2 Diabetes Mellitus with improving glycemic control (HbA1c 8.4 -> 8.0 -> 7.8%)."
        v2_content["plan"] = "Continue Metformin 500 mg BD and Glimepiride 1 mg OD. Recheck HbA1c in 3 months."
        v2_content["follow_up"] = "Follow up in 3 months with repeat HbA1c and lipid panel."
        v2 = ConsultationVersion(
            id=v2_id,
            consultation_id=c_id,
            version_number=2,
            origin=ConsultationOrigin.doctor_edited.value,
            content_json=json.dumps(v2_content),
            change_summary="Added physical examination, assessment, and treatment plan",
            edited_by="Dr. Willie Carter, MD",
        )
        db.add(v2)

        v3_id = consultation_version_id()
        v3 = ConsultationVersion(
            id=v3_id,
            consultation_id=c_id,
            version_number=3,
            origin=ConsultationOrigin.approved.value,
            content_json=json.dumps(v2_content),
            change_summary="Clinician review complete; approved into verified clinical memory",
            edited_by="Dr. Willie Carter, MD",
        )
        db.add(v3)
        con.current_version_id = v3_id

        # 6. Add Verified Clinical Memory from Approved Consultation
        mem1 = ClinicalMemory(
            id=clinical_memory_id(),
            patient_id=DEMO_PATIENT_ID,
            memory_type="diagnosis",
            content_json=json.dumps({"diagnosis": "Type 2 Diabetes Mellitus", "status": "active", "onset": "2026-01-10"}),
            source_consultation_id=c_id,
            source_version_id=v3_id,
            verified=True,
        )
        mem2 = ClinicalMemory(
            id=clinical_memory_id(),
            patient_id=DEMO_PATIENT_ID,
            memory_type="medication",
            content_json=json.dumps({"active_regimen": ["Metformin 500 mg BD", "Glimepiride 1 mg OD"]}),
            source_consultation_id=c_id,
            source_version_id=v3_id,
            verified=True,
        )
        db.add(mem1)
        db.add(mem2)

        # 7. Add Timeline Event for Approved Note
        evt_approved = TimelineEvent(
            id=timeline_event_id(),
            patient_id=DEMO_PATIENT_ID,
            event_type="approved_note",
            event_date=datetime.datetime(2026, 9, 29, 10, 0, tzinfo=datetime.timezone.utc),
            date_precision="day",
            title="Approved Consultation Note",
            summary="Dr. Willie Carter approved comprehensive metabolic review and continued dual therapy.",
            related_fact_ids=json.dumps([]),
            sort_key="2026-09-29",
        )
        db.add(evt_approved)

        db.commit()

    logger.info("demo_data_seeded_successfully", patient_id=DEMO_PATIENT_ID, documents=6)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed demo clinical data for ClinSync")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Purge existing demo records before seeding (implied: this is the only patient)",
    )
    args = parser.parse_args()
    # Previously `reset=args.reset or True`, so `--reset` was ignored and the
    # flag could never be false. Seeding the demo patient is destructive by
    # nature (see reset_demo_patient), so the CLI now states that plainly and
    # still defaults to a reset — but the flag is honoured rather than faked.
    logger.warning(
        "seed_reset_is_destructive",
        reset=True,
        note="purging all records for the demo patient before seeding",
    )
    seed_demo_data(reset=True)
