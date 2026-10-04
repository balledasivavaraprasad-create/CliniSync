import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy.orm import Session

from app.db.database import get_db_context
from app.models.document import Document, DocumentPage
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.timeline_event import TimelineEvent
from app.models.contradiction import Contradiction
from app.models.processing_job import ProcessingJob
from app.schemas.common import ProcessingStatus, FactType, VerificationStatus, IssueType, Severity, MedStatus
from app.utils.ids import job_id, fact_id, medication_id, investigation_id, timeline_event_id, contradiction_id
from app.services.ocr_service import ocr_service
from app.services.classification_service import classification_service
from app.services.extraction_service import extraction_service
from app.services.normalization_service import normalization_service
from app.services.evidence_service import evidence_service
from app.services.confidence_service import confidence_service
from app.services.audit_service import audit_service
from app.config import settings

logger = structlog.get_logger(__name__)

class PipelineOrchestrator:
    async def run(self, document_id: str, is_reprocess: bool = False) -> str:
        """
        Orchestrates the document processing state machine asynchronously:
        uploaded -> extracting_text -> classifying -> extracting_entities -> normalizing -> validating -> complete
        """
        job = None
        with get_db_context() as db:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                raise ValueError(f"Document {document_id} not found")

            job = ProcessingJob(
                id=job_id(),
                subject_type="document",
                subject_id=document_id,
                stage="extracting_text",
                status="in_progress",
                attempts=1,
                started_at=datetime.datetime.utcnow()
            )
            db.add(job)
            doc.processing_status = ProcessingStatus.extracting_text.value
            db.commit()
            db.refresh(job)
            db.refresh(doc)
            patient_id = doc.patient_id
            stored_path = doc.stored_path
            mime_type = doc.mime_type

        job_run_id = job.id

        try:
            # 1. EXTRACTING TEXT
            pages = await ocr_service.extract_text(
                patient_id=patient_id,
                document_id=document_id,
                file_path=stored_path,
                mime_type=mime_type
            )

            with get_db_context() as db:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if not doc: return job_run_id
                
                # Delete existing pages if reprocess
                db.query(DocumentPage).filter(DocumentPage.document_id == document_id).delete()
                
                methods = set()
                total_conf = 0.0
                pages_dict: Dict[int, str] = {}
                for p in pages:
                    dp = DocumentPage(
                        document_id=document_id,
                        page_number=p["page_number"],
                        text=p["text"],
                        ocr_confidence=p["ocr_confidence"],
                        method=p["method"]
                    )
                    db.add(dp)
                    methods.add(p["method"])
                    total_conf += p["ocr_confidence"]
                    pages_dict[p["page_number"]] = p["text"]

                doc.page_count = len(pages)
                doc.ocr_method = "hybrid" if len(methods) > 1 else (list(methods)[0] if methods else "pdf_text")
                doc.extracted_text_path = str(Path(settings.STORAGE_ROOT) / "patients" / patient_id / "ocr" / f"{document_id}.json")
                doc.processing_status = ProcessingStatus.classifying.value
                
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
                if job: job.stage = "classifying"
                db.commit()

            # 2. CLASSIFYING
            full_text = "\n\n".join([f"Page {p['page_number']}:\n{p['text']}" for p in pages])
            classification = await classification_service.classify(full_text)

            with get_db_context() as db:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if not doc: return job_run_id
                doc.document_type = classification.document_type
                doc.classification_confidence = classification.confidence
                if classification.document_date:
                    norm_date, _, _ = normalization_service.normalize_date(classification.document_date)
                    if norm_date:
                        try:
                            doc.document_date = datetime.datetime.fromisoformat(norm_date)
                        except Exception:
                            pass
                
                doc.processing_status = ProcessingStatus.extracting_entities.value
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
                if job: job.stage = "extracting_entities"
                db.commit()

            # 3. EXTRACTING ENTITIES
            extraction = await extraction_service.extract(pages, classification.document_type)

            # 4. NORMALIZING & PROVENANCE CHECKING
            # (We perform in memory, then persist in a single atomic transaction)
            with get_db_context() as db:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if not doc: return job_run_id
                
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
                if job: job.stage = "persisting"

                # If reprocess, delete older unverified facts from this document
                if is_reprocess:
                    old_facts = db.query(ClinicalFact).filter(
                        ClinicalFact.document_id == document_id,
                        ClinicalFact.verification_status != VerificationStatus.doctor_verified.value
                    ).all()
                    for of in old_facts:
                        db.query(Medication).filter(Medication.fact_id == of.id).delete()
                        db.query(Investigation).filter(Investigation.fact_id == of.id).delete()
                        db.delete(of)

                has_low_confidence = False

                # A. Process Medications
                for m in extraction.medications:
                    norm = normalization_service.normalize_medication(
                        raw_name=m.name,
                        raw_strength=m.strength,
                        raw_frequency=m.frequency
                    )
                    prov_ver, score, span = evidence_service.verify_evidence(
                        source_text=m.evidence.text,
                        page_number=m.evidence.page,
                        pages_dict=pages_dict
                    )
                    conf_score, conf_band = confidence_service.calculate_confidence(
                        model_confidence=m.confidence,
                        provenance_verified=prov_ver
                    )
                    if conf_score < 0.60:
                        has_low_confidence = True

                    fact = ClinicalFact(
                        id=fact_id(),
                        patient_id=patient_id,
                        document_id=document_id,
                        fact_type=FactType.medication.value,
                        value=f"{norm['canonical_name']} {norm['strength_value'] or ''} {norm['strength_unit'] or ''}".strip(),
                        normalized_value=json.dumps(norm, default=str),
                        fact_date=doc.document_date if doc.document_date else None,
                        confidence=conf_score,
                        confidence_band=conf_band.value,
                        source_text=m.evidence.text,
                        source_page=m.evidence.page,
                        source_span_start=span,
                        provenance_verified=prov_ver,
                        verification_status=VerificationStatus.unverified.value,
                        extraction_run_id=job_run_id
                    )
                    db.add(fact)
                    db.flush()

                    med = Medication(
                        id=medication_id(),
                        patient_id=patient_id,
                        fact_id=fact.id,
                        canonical_name=norm["canonical_name"],
                        raw_name=norm["raw_name"],
                        strength_value=norm["strength_value"],
                        strength_unit=norm["strength_unit"],
                        dose_text=m.dose or (f"{norm['strength_value']}{norm['strength_unit']}" if norm["strength_value"] else None),
                        frequency_code=norm["frequency_code"],
                        frequency_text=norm["frequency_text"] or m.frequency,
                        route=m.route,
                        duration_text=m.duration,
                        start_date=norm["start_date"],
                        stop_date=norm["stop_date"],
                        status=MedStatus.current.value,
                        group_key=f"{patient_id}_{norm['canonical_name']}",
                        confidence=conf_score,
                        source_document_id=document_id
                    )
                    db.add(med)

                    # Add timeline event
                    evt = TimelineEvent(
                        id=timeline_event_id(),
                        patient_id=patient_id,
                        event_type="medication_start",
                        event_date=doc.document_date if doc.document_date else datetime.datetime.now(datetime.UTC),
                        date_precision="day" if doc.document_date else "unknown",
                        title=f"Started {norm['canonical_name'].title()}",
                        summary=f"{norm['raw_name']} {norm['strength_value'] or ''}{norm['strength_unit'] or ''} {norm['frequency_code'] or ''}".strip(),
                        related_fact_ids=json.dumps([fact.id]),
                        source_document_id=document_id,
                        sort_key=doc.document_date.isoformat() if doc.document_date else "9999-99-99"
                    )
                    db.add(evt)

                # B. Process Investigations
                for inv in extraction.investigations:
                    norm_inv = normalization_service.normalize_investigation(
                        raw_test_name=inv.test,
                        raw_value=inv.value,
                        raw_unit=inv.unit,
                        raw_reference_range=inv.reference_range,
                        raw_flag=inv.flag,
                        raw_date=inv.date
                    )
                    prov_ver, score, span = evidence_service.verify_evidence(
                        source_text=inv.evidence.text,
                        page_number=inv.evidence.page,
                        pages_dict=pages_dict
                    )
                    conf_score, conf_band = confidence_service.calculate_confidence(
                        model_confidence=inv.confidence,
                        provenance_verified=prov_ver
                    )
                    if conf_score < 0.60:
                        has_low_confidence = True

                    inv_date = None
                    if norm_inv["observed_date"]:
                        try:
                            inv_date = datetime.datetime.fromisoformat(norm_inv["observed_date"])
                        except Exception:
                            pass
                    if not inv_date and doc.document_date:
                        inv_date = doc.document_date

                    fact = ClinicalFact(
                        id=fact_id(),
                        patient_id=patient_id,
                        document_id=document_id,
                        fact_type=FactType.investigation.value,
                        value=f"{norm_inv['test_name_canonical']}: {norm_inv['value_text']} {norm_inv['unit']}".strip(),
                        normalized_value=json.dumps(norm_inv, default=str),
                        fact_date=inv_date,
                        confidence=conf_score,
                        confidence_band=conf_band.value,
                        source_text=inv.evidence.text,
                        source_page=inv.evidence.page,
                        source_span_start=span,
                        provenance_verified=prov_ver,
                        verification_status=VerificationStatus.unverified.value,
                        extraction_run_id=job_run_id
                    )
                    db.add(fact)
                    db.flush()

                    investigation = Investigation(
                        id=investigation_id(),
                        patient_id=patient_id,
                        fact_id=fact.id,
                        test_name_raw=norm_inv["test_name_raw"],
                        test_name_canonical=norm_inv["test_name_canonical"],
                        value_numeric=norm_inv["value_numeric"],
                        value_text=norm_inv["value_text"],
                        unit=norm_inv["unit"],
                        reference_low=norm_inv["reference_low"],
                        reference_high=norm_inv["reference_high"],
                        reference_text=norm_inv["reference_text"],
                        abnormal_flag=norm_inv["abnormal_flag"],
                        observed_date=inv_date,
                        source_document_id=document_id,
                        confidence=conf_score,
                        group_key=f"{patient_id}_{norm_inv['test_name_canonical']}"
                    )
                    db.add(investigation)

                    # Add timeline event
                    evt = TimelineEvent(
                        id=timeline_event_id(),
                        patient_id=patient_id,
                        event_type="investigation",
                        event_date=inv_date if inv_date else datetime.datetime.now(datetime.UTC),
                        date_precision="day" if inv_date else "unknown",
                        title=f"Lab: {norm_inv['test_name_canonical'].title()}",
                        summary=f"{norm_inv['test_name_canonical']}: {norm_inv['value_text']} {norm_inv['unit']} (Ref: {norm_inv['reference_text'] or 'N/A'})".strip(),
                        related_fact_ids=json.dumps([fact.id]),
                        source_document_id=document_id,
                        sort_key=inv_date.isoformat() if inv_date else "9999-99-99"
                    )
                    db.add(evt)

                # C. Process Diagnoses
                for diag in extraction.diagnoses:
                    prov_ver, score, span = evidence_service.verify_evidence(
                        source_text=diag.evidence.text,
                        page_number=diag.evidence.page,
                        pages_dict=pages_dict
                    )
                    conf_score, conf_band = confidence_service.calculate_confidence(
                        model_confidence=diag.confidence,
                        provenance_verified=prov_ver
                    )
                    diag_date = None
                    if diag.date:
                        norm_d, _, _ = normalization_service.normalize_date(diag.date)
                        if norm_d:
                            try: diag_date = datetime.datetime.fromisoformat(norm_d)
                            except Exception: pass
                    if not diag_date and doc.document_date:
                        diag_date = doc.document_date

                    fact = ClinicalFact(
                        id=fact_id(),
                        patient_id=patient_id,
                        document_id=document_id,
                        fact_type=FactType.diagnosis.value,
                        value=diag.text,
                        normalized_value=json.dumps({"diagnosis": diag.text}),
                        fact_date=diag_date,
                        confidence=conf_score,
                        confidence_band=conf_band.value,
                        source_text=diag.evidence.text,
                        source_page=diag.evidence.page,
                        source_span_start=span,
                        provenance_verified=prov_ver,
                        verification_status=VerificationStatus.unverified.value,
                        extraction_run_id=job_run_id
                    )
                    db.add(fact)
                    db.flush()

                    # Add timeline event
                    evt = TimelineEvent(
                        id=timeline_event_id(),
                        patient_id=patient_id,
                        event_type="diagnosis",
                        event_date=diag_date if diag_date else datetime.datetime.now(datetime.UTC),
                        date_precision="day" if diag_date else "unknown",
                        title=f"Diagnosis: {diag.text}",
                        summary=f"Diagnosed with {diag.text}",
                        related_fact_ids=json.dumps([fact.id]),
                        source_document_id=document_id,
                        sort_key=diag_date.isoformat() if diag_date else "9999-99-99"
                    )
                    db.add(evt)

                # D. Process Symptoms
                for sym in extraction.symptoms:
                    prov_ver, score, span = evidence_service.verify_evidence(
                        source_text=sym.evidence.text,
                        page_number=sym.evidence.page,
                        pages_dict=pages_dict
                    )
                    conf_score, conf_band = confidence_service.calculate_confidence(
                        model_confidence=sym.confidence,
                        provenance_verified=prov_ver
                    )
                    fact = ClinicalFact(
                        id=fact_id(),
                        patient_id=patient_id,
                        document_id=document_id,
                        fact_type=FactType.symptom.value,
                        value=sym.text,
                        normalized_value=json.dumps({"symptom": sym.text}),
                        fact_date=doc.document_date,
                        confidence=conf_score,
                        confidence_band=conf_band.value,
                        source_text=sym.evidence.text,
                        source_page=sym.evidence.page,
                        source_span_start=span,
                        provenance_verified=prov_ver,
                        verification_status=VerificationStatus.unverified.value,
                        extraction_run_id=job_run_id
                    )
                    db.add(fact)

                # E. Process Allergies
                for alg in extraction.allergies:
                    prov_ver, score, span = evidence_service.verify_evidence(
                        source_text=alg.evidence.text,
                        page_number=alg.evidence.page,
                        pages_dict=pages_dict
                    )
                    conf_score, conf_band = confidence_service.calculate_confidence(
                        model_confidence=alg.confidence,
                        provenance_verified=prov_ver
                    )
                    fact = ClinicalFact(
                        id=fact_id(),
                        patient_id=patient_id,
                        document_id=document_id,
                        fact_type=FactType.allergy.value,
                        value=alg.text,
                        normalized_value=json.dumps({"allergy": alg.text}),
                        fact_date=doc.document_date,
                        confidence=conf_score,
                        confidence_band=conf_band.value,
                        source_text=alg.evidence.text,
                        source_page=alg.evidence.page,
                        source_span_start=span,
                        provenance_verified=prov_ver,
                        verification_status=VerificationStatus.unverified.value,
                        extraction_run_id=job_run_id
                    )
                    db.add(fact)

                # Flag low confidence issue if any fact has unverified provenance or low score
                if has_low_confidence:
                    issue = Contradiction(
                        id=contradiction_id(),
                        patient_id=patient_id,
                        issue_type=IssueType.low_confidence_fact.value,
                        severity=Severity.low.value,
                        title=f"Low confidence entities in {doc.original_filename}",
                        description=f"Some extracted entities from document {doc.original_filename} could not be verified with high confidence against source text.",
                        related_document_ids=json.dumps([document_id]),
                        related_fact_ids=json.dumps([]),
                        detail_json=json.dumps({}),
                        status="open"
                    )
                    db.add(issue)

                # Update Document and Job status
                doc.processing_status = ProcessingStatus.needs_review.value if has_low_confidence else ProcessingStatus.complete.value
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
                if job:
                    job.status = "completed"
                    job.stage = "complete"
                    job.finished_at = datetime.datetime.utcnow()

                audit_service.log(
                    db=db,
                    actor="system",
                    action="document_processed",
                    entity_type="document",
                    entity_id=document_id,
                    patient_id=patient_id,
                    after_state={"status": doc.processing_status, "page_count": doc.page_count}
                )
                db.commit()

            # 5. DERIVED RECOMPUTE HOOK
            await self._run_derived_recompute(patient_id)

            return job_run_id

        except Exception as e:
            logger.error("pipeline_orchestrator_failed", error=str(e), doc_id=document_id)
            with get_db_context() as db:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.processing_status = ProcessingStatus.failed.value
                    doc.processing_error_code = "DOCUMENT_PROCESSING_FAILED"
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
                if job:
                    job.status = "failed"
                    job.last_error_code = "DOCUMENT_PROCESSING_FAILED"
                    job.last_error_detail = str(e)
                    job.finished_at = datetime.datetime.utcnow()
                db.commit()
            return job_run_id

    async def _run_derived_recompute(self, patient_id: str) -> None:
        """Invokes timeline, medication reconciliation, lab trends, contradictions, and missing info engines."""
        try:
            from app.services.derived_recompute import run_patient_recompute
            await run_patient_recompute(patient_id)
        except ImportError:
            # Derived recompute module will be hooked up in Phase 5
            pass
        except Exception as e:
            logger.error("derived_recompute_error", patient_id=patient_id, error=str(e))

pipeline_orchestrator = PipelineOrchestrator()
