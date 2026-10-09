"""harden_database_schema

Revision ID: 2acbf98ac5c3
Revises: 4c1d44f6a4e8
Create Date: 2026-10-07 22:00:01.718178

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2acbf98ac5c3'
down_revision: Union[str, Sequence[str], None] = '4c1d44f6a4e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with hardened constraints, foreign keys, and indexes."""
    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_audit_log_patient_id',
            'patients',
            ['patient_id'],
            ['id'],
            ondelete='SET NULL'
        )

    with op.batch_alter_table('briefs', schema=None) as batch_op:
        batch_op.create_index('ix_briefs_patient_created', ['patient_id', 'created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_briefs_validation_report_id'), ['validation_report_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_briefs_validation_report_id',
            'validation_reports',
            ['validation_report_id'],
            ['id'],
            ondelete='SET NULL'
        )

    with op.batch_alter_table('clinical_facts', schema=None) as batch_op:
        batch_op.create_index('ix_clinical_facts_patient_date', ['patient_id', 'fact_date'], unique=False)
        batch_op.create_index('ix_clinical_facts_patient_fact_type', ['patient_id', 'fact_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_clinical_facts_voice_note_id'), ['voice_note_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_clinical_facts_voice_note_id',
            'voice_notes',
            ['voice_note_id'],
            ['id'],
            ondelete='SET NULL'
        )

    with op.batch_alter_table('clinical_memory', schema=None) as batch_op:
        batch_op.create_index('ix_clinical_memory_patient_type', ['patient_id', 'memory_type'], unique=False)
        batch_op.create_index('ix_clinical_memory_patient_verified', ['patient_id', 'verified'], unique=False)
        batch_op.create_index(batch_op.f('ix_clinical_memory_source_consultation_id'), ['source_consultation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_clinical_memory_source_version_id'), ['source_version_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_clinical_memory_supersedes_id'), ['supersedes_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_clinical_memory_validation_report_id'), ['validation_report_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_clinical_memory_supersedes_id',
            'clinical_memory',
            ['supersedes_id'],
            ['id'],
            ondelete='SET NULL'
        )
        batch_op.create_foreign_key(
            'fk_clinical_memory_source_version_id',
            'consultation_versions',
            ['source_version_id'],
            ['id'],
            ondelete='SET NULL'
        )
        batch_op.create_foreign_key(
            'fk_clinical_memory_validation_report_id',
            'validation_reports',
            ['validation_report_id'],
            ['id'],
            ondelete='SET NULL'
        )

    with op.batch_alter_table('consultation_versions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_consultation_versions_validation_report_id'), ['validation_report_id'], unique=False)
        batch_op.create_unique_constraint('uq_consultation_version_num', ['consultation_id', 'version_number'])
        batch_op.create_foreign_key(
            'fk_consultation_versions_validation_report_id',
            'validation_reports',
            ['validation_report_id'],
            ['id'],
            ondelete='SET NULL'
        )

    with op.batch_alter_table('consultations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_consultations_brief_id'), ['brief_id'], unique=False)
        batch_op.create_index('ix_consultations_patient_status', ['patient_id', 'status'], unique=False)
        batch_op.create_foreign_key(
            'fk_consultations_brief_id',
            'briefs',
            ['brief_id'],
            ['id'],
            ondelete='SET NULL'
        )

    with op.batch_alter_table('contradictions', schema=None) as batch_op:
        batch_op.create_index('ix_contradictions_patient_status', ['patient_id', 'status'], unique=False)

    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.create_index('ix_documents_patient_status', ['patient_id', 'processing_status'], unique=False)

    with op.batch_alter_table('investigations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_investigations_fact_id'), ['fact_id'], unique=False)
        batch_op.create_index('ix_investigations_patient_canonical', ['patient_id', 'test_name_canonical'], unique=False)
        batch_op.create_index(batch_op.f('ix_investigations_source_document_id'), ['source_document_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_investigations_source_document_id',
            'documents',
            ['source_document_id'],
            ['id'],
            ondelete='SET NULL'
        )

    with op.batch_alter_table('medications', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_medications_fact_id'), ['fact_id'], unique=False)
        batch_op.create_index('ix_medications_patient_status', ['patient_id', 'status'], unique=False)
        batch_op.create_index(batch_op.f('ix_medications_source_document_id'), ['source_document_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_medications_source_document_id',
            'documents',
            ['source_document_id'],
            ['id'],
            ondelete='SET NULL'
        )

    with op.batch_alter_table('patients', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_patients_is_demo'), ['is_demo'], unique=False)

    with op.batch_alter_table('timeline_events', schema=None) as batch_op:
        batch_op.create_index('ix_timeline_events_patient_date', ['patient_id', 'event_date'], unique=False)
        batch_op.create_index(batch_op.f('ix_timeline_events_source_document_id'), ['source_document_id'], unique=False)
        batch_op.create_foreign_key(
            'fk_timeline_events_source_document_id',
            'documents',
            ['source_document_id'],
            ['id'],
            ondelete='SET NULL'
        )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_users_role'), ['role'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_users_role'))

    with op.batch_alter_table('timeline_events', schema=None) as batch_op:
        batch_op.drop_constraint('fk_timeline_events_source_document_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_timeline_events_source_document_id'))
        batch_op.drop_index('ix_timeline_events_patient_date')

    with op.batch_alter_table('patients', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_patients_is_demo'))

    with op.batch_alter_table('medications', schema=None) as batch_op:
        batch_op.drop_constraint('fk_medications_source_document_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_medications_source_document_id'))
        batch_op.drop_index('ix_medications_patient_status')
        batch_op.drop_index(batch_op.f('ix_medications_fact_id'))

    with op.batch_alter_table('investigations', schema=None) as batch_op:
        batch_op.drop_constraint('fk_investigations_source_document_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_investigations_source_document_id'))
        batch_op.drop_index('ix_investigations_patient_canonical')
        batch_op.drop_index(batch_op.f('ix_investigations_fact_id'))

    with op.batch_alter_table('documents', schema=None) as batch_op:
        batch_op.drop_index('ix_documents_patient_status')

    with op.batch_alter_table('contradictions', schema=None) as batch_op:
        batch_op.drop_index('ix_contradictions_patient_status')

    with op.batch_alter_table('consultations', schema=None) as batch_op:
        batch_op.drop_constraint('fk_consultations_brief_id', type_='foreignkey')
        batch_op.drop_index('ix_consultations_patient_status')
        batch_op.drop_index(batch_op.f('ix_consultations_brief_id'))

    with op.batch_alter_table('consultation_versions', schema=None) as batch_op:
        batch_op.drop_constraint('fk_consultation_versions_validation_report_id', type_='foreignkey')
        batch_op.drop_constraint('uq_consultation_version_num', type_='unique')
        batch_op.drop_index(batch_op.f('ix_consultation_versions_validation_report_id'))

    with op.batch_alter_table('clinical_memory', schema=None) as batch_op:
        batch_op.drop_constraint('fk_clinical_memory_validation_report_id', type_='foreignkey')
        batch_op.drop_constraint('fk_clinical_memory_source_version_id', type_='foreignkey')
        batch_op.drop_constraint('fk_clinical_memory_supersedes_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_clinical_memory_validation_report_id'))
        batch_op.drop_index(batch_op.f('ix_clinical_memory_supersedes_id'))
        batch_op.drop_index(batch_op.f('ix_clinical_memory_source_version_id'))
        batch_op.drop_index(batch_op.f('ix_clinical_memory_source_consultation_id'))
        batch_op.drop_index('ix_clinical_memory_patient_verified')
        batch_op.drop_index('ix_clinical_memory_patient_type')

    with op.batch_alter_table('clinical_facts', schema=None) as batch_op:
        batch_op.drop_constraint('fk_clinical_facts_voice_note_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_clinical_facts_voice_note_id'))
        batch_op.drop_index('ix_clinical_facts_patient_fact_type')
        batch_op.drop_index('ix_clinical_facts_patient_date')

    with op.batch_alter_table('briefs', schema=None) as batch_op:
        batch_op.drop_constraint('fk_briefs_validation_report_id', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_briefs_validation_report_id'))
        batch_op.drop_index('ix_briefs_patient_created')

    with op.batch_alter_table('audit_log', schema=None) as batch_op:
        batch_op.drop_constraint('fk_audit_log_patient_id', type_='foreignkey')
