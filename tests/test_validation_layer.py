import json
import pytest
import datetime
from sqlalchemy.orm import Session

from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.consultation import Consultation, ConsultationVersion
from app.models.clinical_fact import ClinicalFact
from app.models.contradiction import Contradiction
from app.models.medication import Medication
from app.schemas.common import ValidationOutcome, ConsultationOrigin, Severity, FactType
from app.utils.ids import patient_id, consultation_id, version_id, fact_id, contradiction_id, medication_id
from app.validation.gate1_memory import gate1_validator
from app.validation.gate2_output import gate2_validator

def test_adversarial_directive_language_blocked():
    """Adversarial fixture: generated brief with treatment directive 'increase Metformin to 1000 mg' MUST block."""
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Adversarial Test Patient")
        db.add(p)
        db.flush()

        f1 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="medication",
            value="metformin 500 mg",
            source_text="metformin 500 mg",
            provenance_verified=True
        )
        db.add(f1)
        db.commit()

        # Brief containing directive
        brief = {
            "id": "brf_test_dir",
            "allergies": [],
            "chief_complaint": {"text": "Patient has high sugars. Increase Metformin to 1000 mg daily.", "evidence_ids": [f1.id]}
        }

        outcome, checks, _ = gate2_validator.validate_brief(db, pid, brief, run_judge=False)
        assert outcome == ValidationOutcome.blocked
        dir_check = next(c for c in checks if c["name"] == "directive_language")
        assert dir_check["passed"] is False
        assert dir_check["severity"] == "block"

def test_adversarial_causality_language_blocked():
    """Adversarial fixture: causal sentence 'HbA1c improved due to Metformin' MUST block."""
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Adversarial Causality Patient")
        db.add(p)
        db.flush()

        f1 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="medication",
            value="metformin 500 mg",
            source_text="metformin 500 mg",
            provenance_verified=True
        )
        db.add(f1)
        db.commit()

        brief = {
            "id": "brf_test_caus",
            "allergies": [],
            "chief_complaint": {"text": "HbA1c level improved due to Metformin treatment.", "evidence_ids": [f1.id]}
        }

        outcome, checks, _ = gate2_validator.validate_brief(db, pid, brief, run_judge=False)
        assert outcome == ValidationOutcome.blocked
        caus_check = next(c for c in checks if c["name"] == "causality_language")
        assert caus_check["passed"] is False

def test_adversarial_fabricated_drug_hallucination_blocked():
    """Adversarial fixture: fabricated drug (Sitagliptin) not in facts MUST block."""
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Adversarial Hallucination Patient")
        db.add(p)
        db.flush()

        f1 = ClinicalFact(
            id=fact_id(),
            patient_id=pid,
            fact_type="medication",
            value="metformin 500 mg",
            source_text="metformin 500 mg",
            provenance_verified=True
        )
        db.add(f1)
        db.commit()

        # Sitagliptin is NOT in patient facts
        brief = {
            "id": "brf_test_hal",
            "allergies": [],
            "chief_complaint": {"text": "Patient is taking Sitagliptin for glycemic control.", "evidence_ids": [f1.id]}
        }

        outcome, checks, _ = gate2_validator.validate_brief(db, pid, brief, run_judge=False)
        assert outcome == ValidationOutcome.blocked
        hal_check = next(c for c in checks if c["name"] == "hallucination_check")
        assert hal_check["passed"] is False

def test_adversarial_missing_evidence_ids_blocked():
    """Adversarial fixture: statement with no evidence ids MUST block."""
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Adversarial Evidence Patient")
        db.add(p)
        db.commit()

        brief = {
            "id": "brf_test_no_ev",
            "allergies": [],
            "chief_complaint": {"text": "Patient has uncontrolled diabetes."}  # Missing evidence_ids!
        }

        outcome, checks, _ = gate2_validator.validate_brief(db, pid, brief, run_judge=False)
        assert outcome == ValidationOutcome.blocked
        prov_check = next(c for c in checks if c["name"] == "provenance_check")
        assert prov_check["passed"] is False

def test_gate1_untouched_ai_draft_blocked_without_ack():
    """Gate 1: Untouched AI draft approval without explicit acknowledgment MUST block."""
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Gate 1 Untouched Patient")
        db.add(p)
        db.flush()

        cid = consultation_id()
        vid = version_id()
        cns = Consultation(
            id=cid,
            patient_id=pid,
            specialty="general_medicine",
            status="draft",
            current_version_id=vid
        )
        ver = ConsultationVersion(
            id=vid,
            consultation_id=cid,
            version_number=1,
            origin=ConsultationOrigin.ai_generated.value,  # Untouched AI draft!
            content_json=json.dumps({"chief_complaint": "Fatigue and high sugars"})
        )
        db.add_all([cns, ver])
        db.commit()

        # Approval attempt without acknowledged_unedited
        outcome, checks, _ = gate1_validator.validate_approval(
            db, cid, acknowledged_unedited=False, run_judge=False
        )
        assert outcome == ValidationOutcome.blocked
        auth_check = next(c for c in checks if c["name"] == "authorship_state_check")
        assert auth_check["passed"] is False

def test_gate1_open_high_conflict_blocked():
    """Gate 1: Unacknowledged high-severity clinical conflict MUST block."""
    with get_db_context() as db:
        pid = patient_id()
        p = Patient(id=pid, full_name="Gate 1 Conflict Patient")
        db.add(p)
        db.flush()

        # Add open high severity contradiction
        iss = Contradiction(
            id=contradiction_id(),
            patient_id=pid,
            issue_type="medication_conflict",
            severity=Severity.high.value,
            title="Dangerous dose discrepancy",
            description="2x difference in recorded doses",
            status="open"
        )
        db.add(iss)

        cid = consultation_id()
        vid = version_id()
        cns = Consultation(
            id=cid,
            patient_id=pid,
            specialty="general_medicine",
            status="draft",
            current_version_id=vid
        )
        ver = ConsultationVersion(
            id=vid,
            consultation_id=cid,
            version_number=2,
            origin=ConsultationOrigin.doctor_edited.value,
            content_json=json.dumps({"chief_complaint": "Reviewed with patient"})
        )
        db.add_all([cns, ver])
        db.commit()

        outcome, checks, _ = gate1_validator.validate_approval(
            db, cid, acknowledged_unedited=False, run_judge=False
        )
        assert outcome == ValidationOutcome.blocked
        conf_check = next(c for c in checks if c["name"] == "unacknowledged_high_conflict")
        assert conf_check["passed"] is False
