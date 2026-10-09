import datetime
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog
from sqlalchemy import func
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
from app.validation.validators.prompt_injection_check import analyze_prompt_injection
from app.config import settings

logger = structlog.get_logger(__name__)

class PipelineOrchestrator:
    async def run(
        self,
        document_id: str,
        is_reprocess: bool = False,
        attempt: int = 1,
        raise_on_error: bool = False,
    ) -> str:
        """
        Orchestrates the document processing state machine asynchronously:
        UPLOADED -> QUEUED -> PROCESSING -> EXTRACTING -> VALIDATING -> COMPLETED
        Failure states: FAILED, RETRY_PENDING
        """
        job = None
        with get_db_context() as db:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if not doc:
                raise ValueError(f"Document {document_id} not found")

            job = (
                db.query(ProcessingJob)
                .filter(ProcessingJob.subject_id == document_id, ProcessingJob.subject_type == "document")
                .order_by(ProcessingJob.created_at.desc())
                .first()
            )
            now = datetime.datetime.now(datetime.UTC)
            if not job or job.status in ("COMPLETED", "FAILED"):
                job = ProcessingJob(
                    id=job_id(),
                    subject_type="document",
                    subject_id=document_id,
                    stage=ProcessingStatus.PROCESSING.value,
                    status=ProcessingStatus.PROCESSING.value,
                    attempts=attempt,
                    started_at=now,
                )
                db.add(job)
            else:
                job.stage = ProcessingStatus.PROCESSING.value
                job.status = ProcessingStatus.PROCESSING.value
                job.attempts = attempt
                if not job.started_at:
                    job.started_at = now

            doc.processing_status = ProcessingStatus.PROCESSING.value
            doc.processing_error_code = None
            db.commit()
            db.refresh(job)
            db.refresh(doc)
            patient_id = doc.patient_id
            stored_path = doc.stored_path
            mime_type = doc.mime_type

        job_run_id = job.id

        try:
            import time
            from app.services.metrics_service import metrics_service

            # 1. EXTRACTING STAGE (OCR Text Extraction)
            with get_db_context() as db:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.processing_status = ProcessingStatus.EXTRACTING.value
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
                if job:
                    job.stage = ProcessingStatus.EXTRACTING.value
                    job.status = ProcessingStatus.PROCESSING.value
                db.commit()

            t_ocr_start = time.time()
            pages = await ocr_service.extract_text(
                patient_id=patient_id,
                document_id=document_id,
                file_path=stored_path,
                mime_type=mime_type
            )
            metrics_service.record_stage_duration("ocr_extract_text", (time.time() - t_ocr_start) * 1000)

            with get_db_context() as db:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if not doc: return job_run_id
                
                # Delete existing pages if reprocess
                db.query(DocumentPage).filter(DocumentPage.document_id == document_id).delete()
                
                methods = set()
                total_conf = 0.0
                pages_dict: Dict[int, str] = {}
                pages_meta: Dict[int, Dict[str, Any]] = {}
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
                    pages_meta[p["page_number"]] = p

                doc.page_count = len(pages)
                doc.ocr_method = "hybrid" if len(methods) > 1 else (list(methods)[0] if methods else "pdf_text")
                doc.extracted_text_path = str(Path(settings.STORAGE_ROOT) / "patients" / patient_id / "ocr" / f"{document_id}.json")
                doc.processing_status = ProcessingStatus.EXTRACTING.value
                
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
                if job:
                    job.stage = ProcessingStatus.EXTRACTING.value
                    job.status = ProcessingStatus.PROCESSING.value
                db.commit()

            # 2. CLASSIFYING & UNTRUSTED CONTENT ANALYSIS
            full_text = "\n\n".join([f"Page {p['page_number']}:\n{p['text']}" for p in pages])

            # Analyze untrusted document content for prompt injection
            with get_db_context() as db:
                old_sec = db.query(Contradiction).filter(
                    Contradiction.patient_id == patient_id,
                    Contradiction.issue_type == IssueType.prompt_injection_attempt.value,
                ).all()
                for os_issue in old_sec:
                    if document_id in (os_issue.related_document_ids or ""):
                        db.delete(os_issue)
                db.commit()

            inj_analysis = analyze_prompt_injection(full_text)
            if inj_analysis.status in ("blocked", "suspicious"):
                logger.warning(
                    "untrusted_document_prompt_injection_detected",
                    document_id=document_id,
                    patient_id=patient_id,
                    status=inj_analysis.status,
                    risk_score=inj_analysis.risk_score,
                    matched_patterns=inj_analysis.matched_patterns,
                )
                with get_db_context() as db:
                    sec_issue = Contradiction(
                        id=contradiction_id(),
                        patient_id=patient_id,
                        issue_type=IssueType.prompt_injection_attempt.value,
                        severity=Severity.high.value,
                        title="Untrusted Prompt Injection Detected in Document",
                        description=(
                            f"Security analysis identified adversarial prompt injection patterns in document: "
                            f"{', '.join(inj_analysis.matched_patterns[:3])}. "
                            "Content was safely isolated as passive data and all instruction execution was denied."
                        ),
                        related_document_ids=json.dumps([document_id]),
                        related_fact_ids="[]",
                        detail_json=json.dumps({
                            "status": inj_analysis.status,
                            "risk_score": inj_analysis.risk_score,
                            "matched_patterns": inj_analysis.matched_patterns,
                        }),
                        status="open",
                        detected_run_id=job_run_id,
                    )
                    db.add(sec_issue)
                    db.commit()

            t_class_start = time.time()
            classification = await classification_service.classify(full_text)
            metrics_service.record_stage_duration("classification", (time.time() - t_class_start) * 1000)

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
                
                doc.processing_status = ProcessingStatus.EXTRACTING.value
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
                if job:
                    job.stage = ProcessingStatus.EXTRACTING.value
                    job.status = ProcessingStatus.PROCESSING.value
                db.commit()

            # 3. EXTRACTING ENTITIES
            t_ext_start = time.time()
            extraction = await extraction_service.extract(pages, classification.document_type)
            metrics_service.record_stage_duration("entity_extraction", (time.time() - t_ext_start) * 1000)

            # 4. VALIDATING & NORMALIZING (Evidence check, safety gate, atomic persistence)
            with get_db_context() as db:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if not doc: return job_run_id
                
                doc.processing_status = ProcessingStatus.VALIDATING.value
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
                if job:
                    job.stage = ProcessingStatus.VALIDATING.value
                    job.status = ProcessingStatus.PROCESSING.value

                # IDEMPOTENCY GUARANTEE:
                # Before inserting newly extracted facts, medications, investigations, or timeline events,
                # unconditionally purge any previous unapproved extracted records for this document.
                # Doctor-approved facts are strictly preserved and never duplicated.
                old_facts = db.query(ClinicalFact).filter(
                    ClinicalFact.document_id == document_id,
                    ClinicalFact.verification_status != VerificationStatus.doctor_verified.value
                ).all()
                for of in old_facts:
                    db.query(Medication).filter(Medication.fact_id == of.id).delete()
                    db.query(Investigation).filter(Investigation.fact_id == of.id).delete()
                    db.delete(of)

                # Delete any medications/investigations referencing this document
                db.query(Medication).filter(Medication.source_document_id == document_id).delete()
                db.query(Investigation).filter(Investigation.source_document_id == document_id).delete()

                # Delete timeline events linked to this document
                db.query(TimelineEvent).filter(TimelineEvent.source_document_id == document_id).delete()

                # Delete previous low-confidence alerts for this document
                old_contradictions = db.query(Contradiction).filter(
                    Contradiction.patient_id == patient_id,
                    Contradiction.issue_type == IssueType.low_confidence_fact.value,
                ).all()
                for oc in old_contradictions:
                    if document_id in (oc.related_document_ids or ""):
                        db.delete(oc)

                has_low_confidence = False

                # A. Process Medications
                for m in extraction.medications:
                    norm = normalization_service.normalize_medication(
                        raw_name=m.name,
                        raw_strength=m.strength,
                        raw_frequency=m.frequency
                    )
                    ev_res = evidence_service.verify_evidence(
                        source_text=m.evidence.text,
                        page_number=m.evidence.page,
                        pages_dict=pages_dict,
                        expected_content=norm["canonical_name"] or m.name
                    )
                    prov_ver = ev_res.verified

                    page_meta = pages_meta.get(m.evidence.page or 1, {})
                    page_ocr_conf = page_meta.get("ocr_confidence", 1.0)
                    page_method = page_meta.get("method", doc.ocr_method or "pdf_text")

                    has_conflict = db.query(Contradiction).filter(
                        Contradiction.patient_id == patient_id,
                        Contradiction.issue_type == "medication_conflict",
                        Contradiction.status.in_(["open", "detected", "presented"]),
                        Contradiction.title.ilike(f"%{norm['canonical_name']}%")
                    ).first() is not None

                    ambig = 0.10 if (not norm.get("strength_value") or norm.get("frequency_code") == "other") else 0.0
                    unk_map = norm.get("canonical_name") is None or norm.get("raw_name") == norm.get("canonical_name")

                    conf_eval = confidence_service.evaluate_confidence(
                        model_confidence=m.confidence,
                        provenance_verified=prov_ver,
                        ocr_confidence=page_ocr_conf,
                        unknown_mapping=unk_map,
                        source_quality=0.95 if doc.document_type else 0.80,
                        ambiguity_penalty=ambig,
                        evidence_match_level=ev_res.verification_level,
                        evidence_match_score=(ev_res.score / 100.0) if ev_res.score else None,
                        extraction_method=page_method,
                        has_contradiction=has_conflict,
                        structured_validation=(norm.get("canonical_name") is not None),
                        temporal_consistency=1.0 if doc.document_date else 0.90,
                    )
                    conf_score = conf_eval.final_score
                    conf_band = conf_eval.confidence_band
                    norm["confidence_explanation"] = conf_eval.to_dict()

                    if conf_score < 0.60 or not prov_ver:
                        has_low_confidence = True

                    med_val = f"{norm['canonical_name']} {norm['strength_value'] or ''} {norm['strength_unit'] or ''}".strip()
                    existing_fact = db.query(ClinicalFact).filter(
                        ClinicalFact.document_id == document_id,
                        ClinicalFact.fact_type == FactType.medication.value,
                        ClinicalFact.verification_status == VerificationStatus.doctor_verified.value,
                        func.lower(ClinicalFact.value) == med_val.lower(),
                    ).first()

                    if existing_fact:
                        fact = existing_fact
                        fact.extraction_run_id = job_run_id
                    else:
                        fact = ClinicalFact(
                            id=fact_id(),
                            patient_id=patient_id,
                            document_id=document_id,
                            fact_type=FactType.medication.value,
                            value=med_val,
                            normalized_value=json.dumps(norm, default=str),
                            fact_date=doc.document_date if doc.document_date else None,
                            confidence=conf_score,
                            confidence_band=conf_band.value,
                            source_text=m.evidence.text,
                            source_page=ev_res.page,
                            source_span_start=ev_res.span_start,
                            source_span_end=ev_res.span_end,
                            provenance_verified=prov_ver,
                            verification_status=(
                                VerificationStatus.unverified.value
                                if prov_ver
                                else VerificationStatus.needs_verification.value
                            ),
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
                        event_date=doc.document_date if doc.document_date else None,
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
                    ev_res = evidence_service.verify_evidence(
                        source_text=inv.evidence.text,
                        page_number=inv.evidence.page,
                        pages_dict=pages_dict,
                        expected_content=norm_inv["test_name_canonical"] or inv.test
                    )
                    prov_ver = ev_res.verified

                    page_meta = pages_meta.get(inv.evidence.page or 1, {})
                    page_ocr_conf = page_meta.get("ocr_confidence", 1.0)
                    page_method = page_meta.get("method", doc.ocr_method or "pdf_text")

                    ambig_inv = 0.10 if (not norm_inv.get("unit") or norm_inv.get("flag") == "unknown") else 0.0
                    unk_inv = norm_inv.get("test_name_canonical") is None or norm_inv.get("test_name_raw") == norm_inv.get("test_name_canonical")

                    inv_date = None
                    if norm_inv["observed_date"]:
                        try:
                            inv_date = datetime.datetime.fromisoformat(norm_inv["observed_date"])
                        except Exception:
                            pass
                    if not inv_date and doc.document_date:
                        inv_date = doc.document_date

                    conf_eval = confidence_service.evaluate_confidence(
                        model_confidence=inv.confidence,
                        provenance_verified=prov_ver,
                        ocr_confidence=page_ocr_conf,
                        unknown_mapping=unk_inv,
                        source_quality=0.95 if doc.document_type else 0.80,
                        ambiguity_penalty=ambig_inv,
                        evidence_match_level=ev_res.verification_level,
                        evidence_match_score=(ev_res.score / 100.0) if ev_res.score else None,
                        extraction_method=page_method,
                        has_contradiction=False,
                        structured_validation=(norm_inv.get("test_name_canonical") is not None and (norm_inv.get("value_numeric") is not None or norm_inv.get("value_text") is not None)),
                        temporal_consistency=1.0 if inv_date else 0.90,
                    )
                    conf_score = conf_eval.final_score
                    conf_band = conf_eval.confidence_band
                    norm_inv["confidence_explanation"] = conf_eval.to_dict()

                    if conf_score < 0.60 or not prov_ver:
                        has_low_confidence = True

                    inv_val = f"{norm_inv['test_name_canonical']}: {norm_inv['value_text']} {norm_inv['unit']}".strip()
                    existing_fact = db.query(ClinicalFact).filter(
                        ClinicalFact.document_id == document_id,
                        ClinicalFact.fact_type == FactType.investigation.value,
                        ClinicalFact.verification_status == VerificationStatus.doctor_verified.value,
                        func.lower(ClinicalFact.value) == inv_val.lower(),
                    ).first()

                    if existing_fact:
                        fact = existing_fact
                        fact.extraction_run_id = job_run_id
                    else:
                        fact = ClinicalFact(
                            id=fact_id(),
                            patient_id=patient_id,
                            document_id=document_id,
                            fact_type=FactType.investigation.value,
                            value=inv_val,
                            normalized_value=json.dumps(norm_inv, default=str),
                            fact_date=inv_date,
                            confidence=conf_score,
                            confidence_band=conf_band.value,
                            source_text=inv.evidence.text,
                            source_page=ev_res.page,
                            source_span_start=ev_res.span_start,
                            source_span_end=ev_res.span_end,
                            provenance_verified=prov_ver,
                            verification_status=(
                                VerificationStatus.unverified.value
                                if prov_ver
                                else VerificationStatus.needs_verification.value
                            ),
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
                        event_date=inv_date if inv_date else None,
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
                    ev_res = evidence_service.verify_evidence(
                        source_text=diag.evidence.text,
                        page_number=diag.evidence.page,
                        pages_dict=pages_dict,
                        expected_content=diag.text
                    )
                    prov_ver = ev_res.verified

                    page_meta = pages_meta.get(diag.evidence.page or 1, {})
                    page_ocr_conf = page_meta.get("ocr_confidence", 1.0)
                    page_method = page_meta.get("method", doc.ocr_method or "pdf_text")

                    diag_conflict = db.query(Contradiction).filter(
                        Contradiction.patient_id == patient_id,
                        Contradiction.issue_type == "diagnosis_conflict",
                        Contradiction.status.in_(["open", "detected", "presented"]),
                    ).first() is not None

                    diag_date = None
                    if diag.date:
                        norm_d, _, _ = normalization_service.normalize_date(diag.date)
                        if norm_d:
                            try: diag_date = datetime.datetime.fromisoformat(norm_d)
                            except Exception: pass
                    if not diag_date and doc.document_date:
                        diag_date = doc.document_date

                    conf_eval = confidence_service.evaluate_confidence(
                        model_confidence=diag.confidence,
                        provenance_verified=prov_ver,
                        ocr_confidence=page_ocr_conf,
                        source_quality=0.95 if doc.document_type else 0.80,
                        evidence_match_level=ev_res.verification_level,
                        evidence_match_score=(ev_res.score / 100.0) if ev_res.score else None,
                        extraction_method=page_method,
                        has_contradiction=diag_conflict,
                        temporal_consistency=1.0 if diag_date else 0.90,
                    )
                    conf_score = conf_eval.final_score
                    conf_band = conf_eval.confidence_band

                    if conf_score < 0.60 or not prov_ver:
                        has_low_confidence = True

                    existing_fact = db.query(ClinicalFact).filter(
                        ClinicalFact.document_id == document_id,
                        ClinicalFact.fact_type == FactType.diagnosis.value,
                        ClinicalFact.verification_status == VerificationStatus.doctor_verified.value,
                        func.lower(ClinicalFact.value) == diag.text.lower(),
                    ).first()

                    if existing_fact:
                        fact = existing_fact
                        fact.extraction_run_id = job_run_id
                    else:
                        fact = ClinicalFact(
                            id=fact_id(),
                            patient_id=patient_id,
                            document_id=document_id,
                            fact_type=FactType.diagnosis.value,
                            value=diag.text,
                            normalized_value=json.dumps({"diagnosis": diag.text, "confidence_explanation": conf_eval.to_dict()}),
                            fact_date=diag_date,
                            confidence=conf_score,
                            confidence_band=conf_band.value,
                            source_text=diag.evidence.text,
                            source_page=ev_res.page,
                            source_span_start=ev_res.span_start,
                            source_span_end=ev_res.span_end,
                            provenance_verified=prov_ver,
                            verification_status=(
                                VerificationStatus.unverified.value
                                if prov_ver
                                else VerificationStatus.needs_verification.value
                            ),
                            extraction_run_id=job_run_id
                        )
                        db.add(fact)
                        db.flush()

                    # Add timeline event
                    evt = TimelineEvent(
                        id=timeline_event_id(),
                        patient_id=patient_id,
                        event_type="diagnosis",
                        event_date=diag_date if diag_date else None,
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
                    ev_res = evidence_service.verify_evidence(
                        source_text=sym.evidence.text,
                        page_number=sym.evidence.page,
                        pages_dict=pages_dict,
                        expected_content=sym.text
                    )
                    prov_ver = ev_res.verified

                    page_meta = pages_meta.get(sym.evidence.page or 1, {})
                    page_ocr_conf = page_meta.get("ocr_confidence", 1.0)
                    page_method = page_meta.get("method", doc.ocr_method or "pdf_text")

                    conf_eval = confidence_service.evaluate_confidence(
                        model_confidence=sym.confidence,
                        provenance_verified=prov_ver,
                        ocr_confidence=page_ocr_conf,
                        source_quality=0.95 if doc.document_type else 0.80,
                        evidence_match_level=ev_res.verification_level,
                        evidence_match_score=(ev_res.score / 100.0) if ev_res.score else None,
                        extraction_method=page_method,
                        has_contradiction=False,
                        temporal_consistency=1.0 if doc.document_date else 0.90,
                    )
                    conf_score = conf_eval.final_score
                    conf_band = conf_eval.confidence_band

                    if conf_score < 0.60 or not prov_ver:
                        has_low_confidence = True

                    existing_fact = db.query(ClinicalFact).filter(
                        ClinicalFact.document_id == document_id,
                        ClinicalFact.fact_type == FactType.symptom.value,
                        ClinicalFact.verification_status == VerificationStatus.doctor_verified.value,
                        func.lower(ClinicalFact.value) == sym.text.lower(),
                    ).first()

                    if existing_fact:
                        fact = existing_fact
                        fact.extraction_run_id = job_run_id
                    else:
                        fact = ClinicalFact(
                            id=fact_id(),
                            patient_id=patient_id,
                            document_id=document_id,
                            fact_type=FactType.symptom.value,
                            value=sym.text,
                            normalized_value=json.dumps({"symptom": sym.text, "confidence_explanation": conf_eval.to_dict()}),
                            fact_date=doc.document_date,
                            confidence=conf_score,
                            confidence_band=conf_band.value,
                            source_text=sym.evidence.text,
                            source_page=ev_res.page,
                            source_span_start=ev_res.span_start,
                            source_span_end=ev_res.span_end,
                            provenance_verified=prov_ver,
                            verification_status=(
                                VerificationStatus.unverified.value
                                if prov_ver
                                else VerificationStatus.needs_verification.value
                            ),
                            extraction_run_id=job_run_id
                        )
                        db.add(fact)

                # E. Process Allergies
                for alg in extraction.allergies:
                    ev_res = evidence_service.verify_evidence(
                        source_text=alg.evidence.text,
                        page_number=alg.evidence.page,
                        pages_dict=pages_dict,
                        expected_content=alg.text
                    )
                    prov_ver = ev_res.verified

                    page_meta = pages_meta.get(alg.evidence.page or 1, {})
                    page_ocr_conf = page_meta.get("ocr_confidence", 1.0)
                    page_method = page_meta.get("method", doc.ocr_method or "pdf_text")

                    conf_eval = confidence_service.evaluate_confidence(
                        model_confidence=alg.confidence,
                        provenance_verified=prov_ver,
                        ocr_confidence=page_ocr_conf,
                        source_quality=0.95 if doc.document_type else 0.80,
                        evidence_match_level=ev_res.verification_level,
                        evidence_match_score=(ev_res.score / 100.0) if ev_res.score else None,
                        extraction_method=page_method,
                        has_contradiction=False,
                        temporal_consistency=1.0 if doc.document_date else 0.90,
                    )
                    conf_score = conf_eval.final_score
                    conf_band = conf_eval.confidence_band

                    if conf_score < 0.60 or not prov_ver:
                        has_low_confidence = True

                    existing_fact = db.query(ClinicalFact).filter(
                        ClinicalFact.document_id == document_id,
                        ClinicalFact.fact_type == FactType.allergy.value,
                        ClinicalFact.verification_status == VerificationStatus.doctor_verified.value,
                        func.lower(ClinicalFact.value) == alg.text.lower(),
                    ).first()

                    if existing_fact:
                        fact = existing_fact
                        fact.extraction_run_id = job_run_id
                    else:
                        fact = ClinicalFact(
                            id=fact_id(),
                            patient_id=patient_id,
                            document_id=document_id,
                            fact_type=FactType.allergy.value,
                            value=alg.text,
                            normalized_value=json.dumps({"allergy": alg.text, "confidence_explanation": conf_eval.to_dict()}),
                            fact_date=doc.document_date,
                            confidence=conf_score,
                            confidence_band=conf_band.value,
                            source_text=alg.evidence.text,
                            source_page=ev_res.page,
                            source_span_start=ev_res.span_start,
                            source_span_end=ev_res.span_end,
                            provenance_verified=prov_ver,
                            verification_status=(
                                VerificationStatus.unverified.value
                                if prov_ver
                                else VerificationStatus.needs_verification.value
                            ),
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

                # Update Document and Job status to COMPLETED
                doc.processing_status = ProcessingStatus.COMPLETED.value
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
                if job:
                    job.status = ProcessingStatus.COMPLETED.value
                    job.stage = ProcessingStatus.COMPLETED.value
                    job.finished_at = datetime.datetime.now(datetime.UTC)

                audit_service.log(
                    db=db,
                    actor="system",
                    action="document_processed",
                    entity_type="document",
                    entity_id=document_id,
                    patient_id=patient_id,
                    after_state={"status": str(doc.processing_status), "page_count": doc.page_count}
                )
                db.commit()

            # 5. DERIVED RECOMPUTE HOOK
            await self._run_derived_recompute(patient_id)

            return job_run_id

        except Exception as e:
            from app.services.task_worker import sanitize_error_message
            clean_err = sanitize_error_message(e)
            logger.error("pipeline_orchestrator_failed", error=clean_err, doc_id=document_id)
            with get_db_context() as db:
                doc = db.query(Document).filter(Document.id == document_id).first()
                if doc:
                    doc.processing_status = ProcessingStatus.FAILED.value
                    doc.processing_error_code = "DOCUMENT_PROCESSING_FAILED"
                job = db.query(ProcessingJob).filter(ProcessingJob.id == job_run_id).first()
                if job:
                    job.status = ProcessingStatus.FAILED.value
                    job.stage = ProcessingStatus.FAILED.value
                    job.last_error_code = "DOCUMENT_PROCESSING_FAILED"
                    job.last_error_detail = clean_err
                    job.finished_at = datetime.datetime.now(datetime.UTC)
                db.commit()
            if raise_on_error:
                raise
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
            from app.utils.logging_sanitizer import sanitize_error_message
            logger.error("derived_recompute_error", patient_id=patient_id, error=sanitize_error_message(e))

pipeline_orchestrator = PipelineOrchestrator()
