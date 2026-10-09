import json
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.db.database import get_db_context
from app.models.patient import Patient
from app.models.patient_access import PatientAccess
from app.models.user import User
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.contradiction import Contradiction
from app.models.timeline_event import TimelineEvent
from app.models.clinical_memory import ClinicalMemory
from app.schemas.common import ClinicalSemanticState, FactType
from app.schemas.brief import DoctorBrief
from app.services.brief_service import brief_service
from app.services.contradiction_service import contradiction_service
from app.services.medication_service import medication_service
from app.services.lab_service import lab_service
from app.services.timeline_service import timeline_service
from app.services.memory_service import memory_service
from app.utils.ids import fact_id, medication_id, investigation_id, contradiction_id, timeline_event_id, memory_id
from app.utils.tokens import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def test_setup():
    pid = "pat_semantic_test_001"
    uid = "usr_semantic_doc_001"
    with get_db_context() as db:
        user = db.query(User).filter(User.id == uid).first()
        if not user:
            user = User(
                id=uid,
                email="semantic_doc@clinsync.health",
                hashed_password="pw",
                full_name="Dr. Semantic Tester",
                role="doctor",
                is_active=True,
            )
            db.add(user)

        pat = db.query(Patient).filter(Patient.id == pid).first()
        if not pat:
            pat = Patient(
                id=pid,
                full_name="Semantic State Patient",
                sex="female",
                age_years=52,
            )
            db.add(pat)

        acc = db.query(PatientAccess).filter(
            PatientAccess.patient_id == pid,
            PatientAccess.user_id == uid,
        ).first()
        if not acc:
            acc = PatientAccess(
                id="acc_sem_001",
                patient_id=pid,
                user_id=uid,
                access_level="write",
            )
            db.add(acc)

        db.commit()

    token = create_access_token(
        subject=uid,
        claims={"role": "doctor", "specialty": "General Medicine"}
    )
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Request-ID": "req-semantic-test"
    }

    return {
        "doctor_id": uid,
        "patient_id": pid,
        "headers": headers,
    }


def make_test_doc(patient_id: str, doc_id: str, filename: str) -> Document:
    return Document(
        id=doc_id,
        patient_id=patient_id,
        original_filename=filename,
        stored_path=f"mock/{filename}",
        mime_type="application/pdf",
        file_size=1024,
        sha256=f"sha256_{doc_id}_{filename[:6]}",
        processing_status="complete",
    )


class TestClinicalSemanticStates:
    def test_documented_state_for_provenance_verified_facts(self, test_setup):
        """DOCUMENTED: Explicitly supported by a source document or verified input."""
        pid = test_setup["patient_id"]
        with get_db_context() as db:
            doc = make_test_doc(pid, "doc_sem_1", "consultation_note.pdf")
            db.add(doc)
            db.commit()

            # Documented symptom
            fact_sym = ClinicalFact(
                id=fact_id(),
                patient_id=pid,
                document_id=doc.id,
                fact_type=FactType.symptom.value,
                value="chest pain",
                source_text="Patient reports chest pain since 2 days",
                source_page=1,
                provenance_verified=True,
                verification_status="documented",
                confidence=0.95,
            )
            # Documented medication
            fact_med = ClinicalFact(
                id=fact_id(),
                patient_id=pid,
                document_id=doc.id,
                fact_type=FactType.medication.value,
                value="Aspirin 75mg",
                source_text="Aspirin 75mg OD",
                source_page=1,
                provenance_verified=True,
                verification_status="documented",
                confidence=0.95,
            )
            db.add_all([fact_sym, fact_med])
            db.commit()

            assert fact_sym.semantic_state == ClinicalSemanticState.DOCUMENTED.value
            assert fact_sym.status == ClinicalSemanticState.DOCUMENTED.value
            assert fact_sym.fact_type == "symptom"
            # Symptom must NOT be converted to diagnosis
            assert fact_sym.fact_type != "diagnosis"

            assert fact_med.semantic_state == ClinicalSemanticState.DOCUMENTED.value

    def test_inferred_state_is_never_confused_with_documented_fact(self, test_setup):
        """INFERRED: Derived from available information; must never be presented as documented fact."""
        pid = test_setup["patient_id"]
        with get_db_context() as db:
            inferred_fact = ClinicalFact(
                id=fact_id(),
                patient_id=pid,
                document_id=None,
                fact_type=FactType.diagnosis.value,
                value="Suspected Cardiac Disease",
                source_text="Inferred from reported chest pain symptom",
                provenance_verified=False,
                verification_status="INFERRED",
                confidence=0.60,
            )
            db.add(inferred_fact)
            db.commit()

            assert inferred_fact.semantic_state == ClinicalSemanticState.INFERRED.value
            assert inferred_fact.status == ClinicalSemanticState.INFERRED.value
            assert inferred_fact.semantic_state != ClinicalSemanticState.DOCUMENTED.value

    def test_unverified_state_when_provenance_verification_fails(self, test_setup):
        """UNVERIFIED: Extracted by AI but evidence verification has not succeeded."""
        pid = test_setup["patient_id"]
        with get_db_context() as db:
            doc = make_test_doc(pid, "doc_unver_1", "noisy_scan.pdf")
            db.add(doc)
            db.commit()

            unverified_fact = ClinicalFact(
                id=fact_id(),
                patient_id=pid,
                document_id=doc.id,
                fact_type=FactType.diagnosis.value,
                value="Asthma",
                source_text="Asthma indicated in illegible handwritten margin",
                source_page=1,
                provenance_verified=False,
                verification_status="unverified",
                confidence=0.55,
            )
            db.add(unverified_fact)
            db.commit()

            assert unverified_fact.semantic_state == ClinicalSemanticState.UNVERIFIED.value
            assert unverified_fact.status == ClinicalSemanticState.UNVERIFIED.value

    def test_conflicting_state_for_incompatible_medication_regimens(self, test_setup):
        """
        CONFLICTING: Multiple sources contain incompatible information.
        Doc A: Metformin 500mg OD vs Doc B: Metformin 500mg BD.
        System must mark medication = Metformin, status = CONFLICTING, sources = [Doc A, Doc B].
        Must NOT silently pick one.
        """
        pid = test_setup["patient_id"]
        with get_db_context() as db:
            doc_a = make_test_doc(pid, "doc_rx_a_test", "prescription_clinic_a.pdf")
            doc_b = make_test_doc(pid, "doc_rx_b_test", "prescription_clinic_b.pdf")
            db.add_all([doc_a, doc_b])
            db.commit()

            fact_a = ClinicalFact(
                id=fact_id(),
                patient_id=pid,
                document_id=doc_a.id,
                fact_type="medication",
                value="Metformin 500mg OD",
                source_text="Metformin 500mg OD",
                provenance_verified=True,
                verification_status="documented",
                confidence=0.9,
            )
            fact_b = ClinicalFact(
                id=fact_id(),
                patient_id=pid,
                document_id=doc_b.id,
                fact_type="medication",
                value="Metformin 500mg BD",
                source_text="Metformin 500mg BD",
                provenance_verified=True,
                verification_status="documented",
                confidence=0.9,
            )
            db.add_all([fact_a, fact_b])
            db.commit()

            med_a = Medication(
                id=medication_id(),
                patient_id=pid,
                fact_id=fact_a.id,
                canonical_name="metformin",
                raw_name="Metformin 500mg",
                strength_value=500.0,
                strength_unit="mg",
                frequency_code="OD",
                frequency_text="once daily",
                status="current",
                group_key=f"{pid}_metformin",
                confidence=0.9,
                source_document_id=doc_a.id,
            )
            med_b = Medication(
                id=medication_id(),
                patient_id=pid,
                fact_id=fact_b.id,
                canonical_name="metformin",
                raw_name="Metformin 500mg",
                strength_value=500.0,
                strength_unit="mg",
                frequency_code="BD",
                frequency_text="twice daily",
                status="current",
                group_key=f"{pid}_metformin",
                confidence=0.9,
                source_document_id=doc_b.id,
            )
            db.add_all([med_a, med_b])
            db.commit()

            # Run contradiction detector
            issues = contradiction_service.recompute(db, pid)
            assert any(i["issue_type"] == "medication_conflict" for i in issues)

            # Check brief generation
            patient = db.query(Patient).filter(Patient.id == pid).first()
            contradictions = db.query(Contradiction).filter(Contradiction.patient_id == pid).all()
            brief = brief_service._build_deterministic_template_brief(
                patient=patient,
                specialty="general_medicine",
                facts=[fact_a, fact_b],
                meds=[med_a, med_b],
                invs=[],
                issues=contradictions,
            )

            met_item = next(m for m in brief.current_medications if m.name.lower() == "metformin")
            assert met_item.conflict_flag is True
            assert met_item.semantic_state == ClinicalSemanticState.CONFLICTING.value
            assert met_item.verification_status == "conflicting"

            # Check contradiction item includes both sources side by side
            conflict_item = next(c for c in brief.contradictions if "metformin" in c.text.lower())
            assert conflict_item.semantic_state == ClinicalSemanticState.CONFLICTING.value
            assert len(conflict_item.sources) >= 2
            assert any("prescription_clinic_a" in s or "500" in s for s in conflict_item.sources)
            assert any("prescription_clinic_b" in s or "BD" in s for s in conflict_item.sources)

    def test_missing_state_when_required_clinical_data_is_absent(self):
        """MISSING: The system needs the information but it is not available."""
        with get_db_context() as db:
            pat_no_age = Patient(
                id="pat_no_age_test_002",
                full_name="No Age Patient",
                sex="male",
                age_years=None,
            )
            db.add(pat_no_age)
            db.commit()

            fid = fact_id()
            f_inv = ClinicalFact(
                id=fid,
                patient_id=pat_no_age.id,
                fact_type="investigation",
                value="HbA1c UNKNOWN",
                source_text="HbA1c test ordered",
                provenance_verified=True,
                verification_status="missing",
                confidence=0.9,
            )
            db.add(f_inv)

            # Investigation with null value
            inv_missing = Investigation(
                id=investigation_id(),
                patient_id=pat_no_age.id,
                fact_id=fid,
                test_name_raw="HbA1c",
                test_name_canonical="hba1c",
                value_numeric=None,
                value_text="UNKNOWN",
                unit="%",
                abnormal_flag="unknown",
                group_key="hba1c",
            )
            db.add(inv_missing)
            db.commit()

            assert inv_missing.semantic_state == ClinicalSemanticState.MISSING.value
            assert inv_missing.status == ClinicalSemanticState.MISSING.value

            brief = brief_service._build_deterministic_template_brief(
                patient=pat_no_age,
                specialty="general_medicine",
                facts=[],
                meds=[],
                invs=[inv_missing],
                issues=[],
            )

            assert brief.patient.age is None
            assert brief.patient.age_display == "Not available"
            assert brief.patient.semantic_state == ClinicalSemanticState.MISSING.value

            inv_item = brief.recent_investigations[0]
            assert inv_item.semantic_state == ClinicalSemanticState.MISSING.value

    def test_unknown_state_when_system_cannot_determine_value(self, test_setup):
        """UNKNOWN: The system cannot determine the value (e.g. unknown chief complaint or allergies)."""
        pid = test_setup["patient_id"]
        with get_db_context() as db:
            patient = db.query(Patient).filter(Patient.id == pid).first()
            brief = brief_service._build_deterministic_template_brief(
                patient=patient,
                specialty="general_medicine",
                facts=[],
                meds=[],
                invs=[],
                issues=[],
            )

            assert brief.chief_complaint.semantic_state == ClinicalSemanticState.UNKNOWN.value
            assert brief.chief_complaint.verification_status == "unknown"
            assert brief.allergies[0].semantic_state == ClinicalSemanticState.UNKNOWN.value
            assert brief.allergies[0].verification_status == "unknown"

    def test_clinical_memory_and_timeline_preserve_semantic_states(self, test_setup):
        """Clinical memory and timeline events explicitly distinguish semantic states."""
        pid = test_setup["patient_id"]
        with get_db_context() as db:
            mem_doc = ClinicalMemory(
                id=memory_id(),
                patient_id=pid,
                memory_type="diagnosis",
                content_json=json.dumps({"diagnosis": "Essential Hypertension", "semantic_state": "DOCUMENTED"}),
                verified=True,
            )
            mem_inf = ClinicalMemory(
                id=memory_id(),
                patient_id=pid,
                memory_type="assessment",
                content_json=json.dumps({"assessment": "Cardiovascular risk suspected", "semantic_state": "INFERRED"}),
                verified=False,
            )
            db.add_all([mem_doc, mem_inf])
            db.commit()

            assert mem_doc.semantic_state == "DOCUMENTED"
            assert mem_inf.semantic_state == "INFERRED"

            memories = memory_service.get_patient_memory(db, pid, verified_only=False)
            doc_mem_item = next(m for m in memories if m["id"] == mem_doc.id)
            inf_mem_item = next(m for m in memories if m["id"] == mem_inf.id)
            assert doc_mem_item["semantic_state"] == "DOCUMENTED"
            assert inf_mem_item["semantic_state"] == "INFERRED"

            doc_time = make_test_doc(pid, "doc_time_1", "notes.pdf")
            db.add(doc_time)
            db.commit()

            evt = TimelineEvent(
                id=timeline_event_id(),
                patient_id=pid,
                event_type="diagnosis",
                event_date=datetime.now(timezone.utc),
                date_precision="day",
                title="Hypertension diagnosed",
                summary="Essential Hypertension documented",
                source_document_id=doc_time.id,
                sort_key="2026-01-01",
            )
            db.add(evt)
            db.commit()

            assert evt.semantic_state == "DOCUMENTED"
            timeline_items = timeline_service.get_timeline(db, pid)
            assert timeline_items[0]["semantic_state"] == "DOCUMENTED"


class TestSemanticStateApiEndpoints:
    def test_facts_endpoint_exposes_semantic_state(self, client: TestClient, test_setup):
        pid = test_setup["patient_id"]
        headers = test_setup["headers"]
        fact_id_val = "f_api_test_sem_01"

        with get_db_context() as db:
            fact = ClinicalFact(
                id=fact_id_val,
                patient_id=pid,
                fact_type="symptom",
                value="shortness of breath",
                source_text="Patient reports shortness of breath",
                provenance_verified=True,
                verification_status="documented",
                confidence=0.92,
            )
            db.add(fact)
            db.commit()

        resp = client.get(f"/api/v1/patients/{pid}/facts", headers=headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        matching = next(f for f in data if f["id"] == fact_id_val)
        assert matching["semantic_state"] == "DOCUMENTED"
        assert matching["status"] == "DOCUMENTED"

    def test_facts_patch_updates_semantic_state(self, client: TestClient, test_setup):
        pid = test_setup["patient_id"]
        headers = test_setup["headers"]
        fact_id_val = "f_patch_test_sem_01"

        with get_db_context() as db:
            fact = ClinicalFact(
                id=fact_id_val,
                patient_id=pid,
                fact_type="diagnosis",
                value="Mild Cough",
                source_text="Mild cough noted",
                provenance_verified=False,
                verification_status="unverified",
                confidence=0.7,
            )
            db.add(fact)
            db.commit()

        resp = client.patch(
            f"/api/v1/facts/{fact_id_val}",
            json={"semantic_state": "DOCUMENTED", "doctor_note": "Confirmed by physician interview"},
            headers=headers
        )
        assert resp.status_code == 200
        res_data = resp.json()["data"]
        assert res_data["semantic_state"] == "DOCUMENTED"
        assert res_data["verification_status"] == "DOCUMENTED"
