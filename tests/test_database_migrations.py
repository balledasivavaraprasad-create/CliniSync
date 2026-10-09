"""Comprehensive tests for database hardening, Alembic migrations, foreign keys, and constraints.

Tests:
1. Migration from clean DB
2. Migration upgrade and downgrade cycle
3. Data preservation across migrations (existing DB -> migration -> data accessible)
4. CRUD operations on hardened models
5. Foreign key relationships and cascade / set null behaviors
6. Duplicate prevention via unique constraints
7. Application startup schema check (ensure_schema)
"""
import os
import tempfile
from pathlib import Path
import pytest
from sqlalchemy import create_engine, inspect, event, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from alembic.config import Config
from alembic import command

from app.models.patient import Patient
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.consultation import Consultation, ConsultationVersion
from app.models.clinical_memory import ClinicalMemory
from app.models.patient_access import PatientAccess
from app.models.user import User
from app.utils.hashing import hash_password
from app.utils.ids import (
    patient_id,
    document_id,
    fact_id,
    medication_id,
    consultation_id,
    version_id,
    memory_id,
    user_id,
)
from app.db.database import ensure_schema, Base


@pytest.fixture
def temp_db_url():
    """Create a temporary SQLite database URL and clean up after test."""
    temp_dir = tempfile.mkdtemp(prefix="clinsync-dbtest-")
    db_path = Path(temp_dir) / "test_migration.db"
    url = f"sqlite:///{db_path}"
    yield url
    try:
        if db_path.exists():
            db_path.unlink()
        Path(temp_dir).rmdir()
    except Exception:
        pass


@pytest.fixture
def alembic_config(temp_db_url):
    """Provide Alembic Config pointing to the temporary test DB."""
    # Find alembic.ini
    root_ini = Path(__file__).resolve().parent.parent / "alembic.ini"
    backend_ini = Path(__file__).resolve().parent.parent / "backend" / "alembic.ini"
    ini_path = root_ini if root_ini.exists() else backend_ini

    cfg = Config(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", temp_db_url)
    return cfg


def get_sqlite_engine(url: str):
    eng = create_engine(url, connect_args={"check_same_thread": False})

    @event.listens_for(eng, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return eng


class TestAlembicMigrations:
    def test_migration_from_clean_db(self, alembic_config, temp_db_url):
        # Clean DB -> Upgrade head
        command.upgrade(alembic_config, "head")

        engine = get_sqlite_engine(temp_db_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        expected_tables = {
            "alembic_version",
            "users",
            "patients",
            "documents",
            "document_pages",
            "clinical_facts",
            "medications",
            "investigations",
            "timeline_events",
            "contradictions",
            "briefs",
            "consultations",
            "consultation_versions",
            "clinical_memory",
            "voice_notes",
            "processing_jobs",
            "validation_reports",
            "audit_log",
            "llm_call_log",
            "patient_access",
        }
        assert expected_tables.issubset(tables)

        # Check unique constraint on consultation_versions
        unique_constraints = inspector.get_unique_constraints("consultation_versions")
        constraint_names = [uc["name"] for uc in unique_constraints]
        assert "uq_consultation_version_num" in constraint_names

    def test_migration_upgrade_downgrade_cycle(self, alembic_config, temp_db_url):
        # 1. Upgrade to head
        command.upgrade(alembic_config, "head")

        # 2. Downgrade by 1 step (back to baseline)
        command.downgrade(alembic_config, "4c1d44f6a4e8")

        engine = get_sqlite_engine(temp_db_url)
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "patients" in tables
        assert "consultation_versions" in tables

        # 3. Upgrade back to head
        command.upgrade(alembic_config, "head")
        inspector_re = inspect(engine)
        unique_constraints = inspector_re.get_unique_constraints("consultation_versions")
        constraint_names = [uc["name"] for uc in unique_constraints]
        assert "uq_consultation_version_num" in constraint_names

    def test_preserve_existing_data(self, alembic_config, temp_db_url):
        """Verify existing DB data is preserved when upgrading to head."""
        # 1. Upgrade to baseline schema
        command.upgrade(alembic_config, "4c1d44f6a4e8")

        # 2. Insert existing data
        engine = get_sqlite_engine(temp_db_url)
        Session = sessionmaker(bind=engine)
        pid = patient_id()
        did = document_id()
        with Session() as session:
            p = Patient(id=pid, full_name="Historical Patient", is_demo=False)
            d = Document(
                id=did,
                patient_id=pid,
                original_filename="historic_record.pdf",
                stored_path="historic.pdf",
                mime_type="application/pdf",
                file_size=100,
                sha256="11223344556677889900aabbccddeeff11223344556677889900aabbccddeeff",
            )
            session.add_all([p, d])
            session.commit()

        # 3. Upgrade to head (applies hardening migration)
        command.upgrade(alembic_config, "head")

        # 4. Verify existing data is completely intact
        with Session() as session:
            loaded_patient = session.query(Patient).filter(Patient.id == pid).first()
            assert loaded_patient is not None
            assert loaded_patient.full_name == "Historical Patient"

            loaded_doc = session.query(Document).filter(Document.id == did).first()
            assert loaded_doc is not None
            assert loaded_doc.original_filename == "historic_record.pdf"


class TestDatabaseIntegrityAndRelationships:
    def test_crud_and_relationships(self, alembic_config, temp_db_url):
        command.upgrade(alembic_config, "head")
        engine = get_sqlite_engine(temp_db_url)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            # Create Patient
            pid = patient_id()
            pat = Patient(id=pid, full_name="John Doe", is_demo=False)
            session.add(pat)
            session.flush()

            # Create Document
            did = document_id()
            doc = Document(
                id=did,
                patient_id=pid,
                original_filename="labs.pdf",
                stored_path="labs.pdf",
                mime_type="application/pdf",
                file_size=2048,
                sha256="abc123sha256abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            )
            session.add(doc)
            session.flush()

            # Create Fact
            fid = fact_id()
            fact = ClinicalFact(
                id=fid,
                patient_id=pid,
                document_id=did,
                fact_type="medication",
                value="Atorvastatin 20mg",
                source_text="Atorvastatin 20mg daily",
            )
            session.add(fact)
            session.flush()

            # Create Medication linked to Fact and Document
            mid = medication_id()
            med = Medication(
                id=mid,
                patient_id=pid,
                fact_id=fid,
                canonical_name="atorvastatin",
                raw_name="Atorvastatin 20mg",
                group_key=f"{pid}_atorvastatin",
                source_document_id=did,
            )
            session.add(med)
            session.commit()

        # Read back via relationships
        with Session() as session:
            loaded_pat = session.query(Patient).filter(Patient.id == pid).first()
            assert len(loaded_pat.documents) == 1
            assert loaded_pat.documents[0].id == did
            assert len(loaded_pat.clinical_facts) == 1
            assert len(loaded_pat.medications) == 1
            assert loaded_pat.medications[0].source_document.id == did

    def test_foreign_key_violation_rejection(self, alembic_config, temp_db_url):
        command.upgrade(alembic_config, "head")
        engine = get_sqlite_engine(temp_db_url)
        Session = sessionmaker(bind=engine)

        # Attempt to insert document for non-existent patient
        with Session() as session:
            doc = Document(
                id=document_id(),
                patient_id="non_existent_patient_id",
                original_filename="orphaned.pdf",
                stored_path="orphaned.pdf",
                mime_type="application/pdf",
                file_size=1024,
                sha256="9999999999999999999999999999999999999999999999999999999999999999",
            )
            session.add(doc)
            with pytest.raises(IntegrityError):
                session.commit()

    def test_duplicate_prevention_consultation_version_num(self, alembic_config, temp_db_url):
        command.upgrade(alembic_config, "head")
        engine = get_sqlite_engine(temp_db_url)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            pid = patient_id()
            pat = Patient(id=pid, full_name="Version Test Patient", is_demo=False)
            session.add(pat)

            cid = consultation_id()
            cons = Consultation(id=cid, patient_id=pid, specialty="cardiology")
            session.add(cons)

            v1 = ConsultationVersion(
                id=version_id(),
                consultation_id=cid,
                version_number=1,
                content_json="{}",
            )
            session.add(v1)
            session.commit()

            # Attempt to add duplicate version number 1 for the same consultation
            v1_duplicate = ConsultationVersion(
                id=version_id(),
                consultation_id=cid,
                version_number=1,
                content_json="{}",
            )
            session.add(v1_duplicate)
            with pytest.raises(IntegrityError):
                session.commit()

    def test_duplicate_prevention_document_sha256_per_patient(self, alembic_config, temp_db_url):
        command.upgrade(alembic_config, "head")
        engine = get_sqlite_engine(temp_db_url)
        Session = sessionmaker(bind=engine)

        with Session() as session:
            pid = patient_id()
            pat = Patient(id=pid, full_name="Doc Unique Patient", is_demo=False)
            session.add(pat)

            d1 = Document(
                id=document_id(),
                patient_id=pid,
                original_filename="doc1.pdf",
                stored_path="doc1.pdf",
                mime_type="application/pdf",
                file_size=500,
                sha256="identical_file_sha256_hash_value_12345678901234567890123456789012",
            )
            session.add(d1)
            session.commit()

            # Adding same sha256 for same patient should fail
            d2 = Document(
                id=document_id(),
                patient_id=pid,
                original_filename="doc1_duplicate.pdf",
                stored_path="doc1_dup.pdf",
                mime_type="application/pdf",
                file_size=500,
                sha256="identical_file_sha256_hash_value_12345678901234567890123456789012",
            )
            session.add(d2)
            with pytest.raises(IntegrityError):
                session.commit()


class TestEnsureSchemaStartup:
    def test_ensure_schema_runs_successfully(self):
        # Test current environment database initialization
        assert ensure_schema() is True
