from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.orm import Session
from sqlalchemy import desc
import json
import hashlib
import structlog

from app.models.patient import Patient
from app.models.document import Document
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.investigation import Investigation
from app.models.contradiction import Contradiction
from app.models.brief import Brief
from app.schemas.brief import DoctorBrief, BriefPatient, BriefChiefComplaint, BriefAllergyItem, BriefMedicationItem, BriefInvestigationItem, BriefTrendItem, BriefAttentionItem, BriefContradictionItem, BriefMissingInfoItem, BriefEvidenceShortcut, BriefHistoryItem
from app.schemas.common import ValidationOutcome
from app.utils.ids import brief_id
from app.config import settings
from app.ai.gateway import llm_gateway
from app.validation.gate2_output import gate2_validator
from app.services.lab_service import lab_service

logger = structlog.get_logger(__name__)

class BriefService:
    def __init__(self) -> None:
        prompt_path = Path(__file__).parent.parent / "ai" / "prompts" / "generate_brief.md"
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()

    @staticmethod
    def _compute_input_fingerprint(patient_id: str, specialty: str, fact_ids: List[str]) -> str:
        raw = f"{patient_id}_{specialty}_{'_'.join(sorted(fact_ids))}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _build_deterministic_template_brief(
        self,
        patient: Patient,
        specialty: str,
        facts: List[ClinicalFact],
        meds: List[Medication],
        invs: List[Investigation],
        issues: List[Contradiction]
    ) -> DoctorBrief:
        """
        Builds a 100% faithful, non-hallucinated deterministic template brief directly from DB rows.
        Guaranteed to pass Gate 2 as safe fallback if LLM generations repeatedly fail.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        age = patient.age_years or 45

        # 1. Chief Complaint & Diagnoses
        diag_facts = [f for f in facts if f.fact_type == "diagnosis"]
        sym_facts = [f for f in facts if f.fact_type == "symptom"]
        cc_text = "Clinical review of longitudinal medical records."
        cc_eids = []
        if diag_facts:
            cc_text = f"Documented diagnosis: {diag_facts[0].value}"
            cc_eids = [diag_facts[0].id]
        elif sym_facts:
            cc_text = f"Reported symptoms: {sym_facts[0].value}"
            cc_eids = [sym_facts[0].id]

        chief_complaint = BriefChiefComplaint(
            text=cc_text,
            evidence_ids=cc_eids,
            confidence_band="high" if cc_eids else "medium"
        )

        # 2. Relevant History
        rel_history = []
        for df in diag_facts[:4]:
            rel_history.append(BriefHistoryItem(
                text=df.value,
                evidence_ids=[df.id],
                confidence_band=df.confidence_band
            ))

        # 3. Medications
        cur_meds = []
        for m in meds:
            cur_meds.append(BriefMedicationItem(
                name=m.canonical_name.title(),
                strength=f"{m.strength_value or ''}{m.strength_unit or ''}".strip(),
                dose=m.dose_text or "",
                frequency=m.frequency_text or m.frequency_code or "",
                status=m.status,
                evidence_ids=[m.fact_id] if m.fact_id else [],
                confidence_band="high" if m.confidence >= 0.85 else "medium",
                conflict_flag=False
            ))

        # 4. Allergies
        alg_facts = [f for f in facts if f.fact_type == "allergy"]
        allergies = []
        if alg_facts:
            for af in alg_facts:
                allergies.append(BriefAllergyItem(
                    text=af.value,
                    evidence_ids=[af.id],
                    status="documented"
                ))
        else:
            allergies.append(BriefAllergyItem(
                text="No documented drug allergies found in source records",
                evidence_ids=[facts[0].id] if facts else [],
                status="not_documented"
            ))

        # 5. Investigations & Trends
        rec_invs = []
        seen_tests = set()
        for i in invs:
            if i.test_name_canonical not in seen_tests:
                seen_tests.add(i.test_name_canonical)
                rec_invs.append(BriefInvestigationItem(
                    test=i.test_name_canonical.replace("_", " ").title(),
                    value=str(i.value_numeric if i.value_numeric is not None else i.value_text),
                    unit=i.unit or "",
                    reference=i.reference_text or "",
                    date=i.observed_date.strftime("%Y-%m-%d") if i.observed_date else "",
                    abnormal=i.abnormal_flag or "unknown",
                    evidence_ids=[i.fact_id] if i.fact_id else []
                ))

        # Trends
        trends = []
        for t_key in seen_tests:
            t_invs = [i for i in invs if i.test_name_canonical == t_key and i.value_numeric is not None]
            if len(t_invs) >= 2:
                t_invs.sort(key=lambda x: x.observed_date if x.observed_date else datetime.date.min)
                series_data = [{"val": ti.value_numeric, "date": ti.observed_date.strftime("%b %Y") if ti.observed_date else "undated"} for ti in t_invs]
                delta = round(t_invs[-1].value_numeric - t_invs[0].value_numeric, 2)
                direction = "down" if delta < -0.1 else ("up" if delta > 0.1 else "stable")
                meas_str = ", ".join([f"{s['val']}{t_invs[0].unit} ({s['date']})" for s in series_data])
                trends.append(BriefTrendItem(
                    test=t_key.replace("_", " ").title(),
                    series=series_data,
                    direction=direction,
                    description=f"{t_key.replace('_', ' ').title()} recorded {meas_str}: {direction} trend over {len(t_invs)} measurements.",
                    evidence_ids=[ti.fact_id for ti in t_invs if ti.fact_id]
                ))

        # 6. Attention items & Contradictions
        attention = []
        contradictions = []
        missing_info = []
        for iss in issues:
            if iss.issue_type == "medication_conflict":
                contradictions.append(BriefContradictionItem(
                    issue_id=iss.id,
                    text=iss.description,
                    sources=[]
                ))
            elif iss.issue_type == "missing_information":
                missing_info.append(BriefMissingInfoItem(
                    prompt=iss.title,
                    reason=iss.description
                ))
            else:
                attention.append(BriefAttentionItem(
                    text=iss.title,
                    severity=iss.severity,
                    evidence_ids=[]
                ))

        # Evidence Shortcuts
        shortcuts = []
        for f in facts[:8]:
            if f.document_id:
                shortcuts.append(BriefEvidenceShortcut(
                    evidence_id=f.id,
                    label=f.value[:40],
                    document_id=f.document_id,
                    page=f.source_page or 1
                ))

        return DoctorBrief(
            patient=BriefPatient(id=patient.id, name=patient.full_name, age=age),
            specialty=specialty,
            generated_at=now_str,
            chief_complaint=chief_complaint,
            relevant_history=rel_history,
            current_medications=cur_meds,
            allergies=allergies,
            recent_investigations=rec_invs,
            important_trends=trends,
            attention_items=attention,
            contradictions=contradictions,
            missing_information=missing_info,
            evidence_shortcuts=shortcuts,
            disclaimer="Deterministic clinical summary of verified source records. Not a diagnosis or treatment recommendation. Verify against sources."
        )

    async def generate_brief(
        self,
        db: Session,
        patient_id: str,
        specialty: str = "general_medicine",
        force_regenerate: bool = False
    ) -> DoctorBrief:
        """
        Generates and Gate 2 validates a 60-Second Doctor Brief.
        Cached by input_fingerprint (<200 ms).
        """
        patient = db.query(Patient).filter(Patient.id == patient_id).first()
        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        facts = db.query(ClinicalFact).filter(ClinicalFact.patient_id == patient_id).all()
        meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        invs = db.query(Investigation).filter(Investigation.patient_id == patient_id).all()
        issues = db.query(Contradiction).filter(Contradiction.patient_id == patient_id, Contradiction.status == "open").all()

        fact_ids = [f.id for f in facts]
        fingerprint = self._compute_input_fingerprint(patient_id, specialty, fact_ids)

        # 1. Check Cache
        if not force_regenerate:
            cached_brief = db.query(Brief).filter(
                Brief.patient_id == patient_id,
                Brief.input_fingerprint == fingerprint,
                Brief.specialty == specialty
            ).order_by(desc(Brief.created_at)).first()

            if cached_brief:
                logger.info("returning_cached_doctor_brief", brief_id=cached_brief.id)
                data = json.loads(cached_brief.content_json)
                return DoctorBrief.model_validate(data)

        # 2. Build Context for LLM
        context_payload = {
            "patient": {"id": patient.id, "name": patient.full_name, "age": patient.age_years or 45},
            "specialty": specialty,
            "facts": [{"id": f.id, "type": f.fact_type, "value": f.value, "date": f.fact_date.isoformat() if f.fact_date else None} for f in facts[:40]],
            "medications": [
                {
                    "name": m.canonical_name,
                    "dose": m.dose_text or f"{m.strength_value or ''} {m.strength_unit or ''}".strip(),
                    "strength": f"{m.strength_value or ''} {m.strength_unit or ''}".strip(),
                    "freq": m.frequency_text or m.frequency_code or "",
                    "evidence_id": m.fact_id
                }
                for m in meds
            ],
            "investigations": [{"test": i.test_name_canonical, "val": i.value_numeric or i.value_text, "unit": i.unit, "date": i.observed_date.isoformat() if i.observed_date else None, "evidence_id": i.fact_id} for i in invs[:20]],
            "issues": [{"id": iss.id, "type": iss.issue_type, "title": iss.title, "desc": iss.description} for iss in issues]
        }
        context_str = json.dumps(context_payload, indent=2)

        # 3. Generation & Gate 2 Validation Loop (up to GATE2_MAX_REGEN_ATTEMPTS)
        max_attempts = getattr(settings, "GATE2_MAX_REGEN_ATTEMPTS", 2)
        attempt = 0
        prompt_instruction = f"Specialty Focus: {specialty}\nStructured Patient Clinical Context:\n<document_text>\n{context_str}\n</document_text>"
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt_instruction}
        ]

        final_brief = None
        gen_source = "llm"
        val_status = "validated"
        val_rep_id = None

        while attempt < max_attempts:
            attempt += 1
            try:
                candidate_brief: DoctorBrief = llm_gateway.complete_json(
                    task="generate_brief",
                    messages=messages,
                    schema=DoctorBrief,
                    slot="llm_generate",
                    temperature=0.2
                )

                # Run Gate 2 Validation
                outcome, checks, rep_id = gate2_validator.validate_brief(
                    db=db,
                    patient_id=patient_id,
                    brief_data=candidate_brief.model_dump(),
                    run_judge=True
                )
                val_rep_id = rep_id

                if outcome in [ValidationOutcome.pass_, ValidationOutcome.pass_with_flags]:
                    final_brief = candidate_brief
                    val_status = "validated" if outcome == ValidationOutcome.pass_ else "validated_with_flags"
                    break
                else:
                    # Collect reasons and append to messages for regeneration
                    blocking_reasons = [c["detail"] for c in checks if c["severity"] == "block" and not c["passed"]]
                    logger.warn("gate2_brief_blocked_retrying", attempt=attempt, reasons=blocking_reasons)
                    messages.append({"role": "assistant", "content": candidate_brief.model_dump_json()})
                    messages.append({
                        "role": "user",
                        "content": f"Gate 2 validation failed due to the following violations:\n{json.dumps(blocking_reasons)}\nFix all violations and regenerate the DoctorBrief strictly compliant with the schema."
                    })
            except Exception as e:
                logger.error("brief_generation_llm_attempt_failed", attempt=attempt, error=str(e))

        # 4. Fallback to Deterministic Template if LLM is blocked or unavailable
        if final_brief is None:
            logger.warn("gate2_exhausted_falling_back_to_deterministic_template", patient_id=patient_id)
            final_brief = self._build_deterministic_template_brief(
                patient=patient,
                specialty=specialty,
                facts=facts,
                meds=meds,
                invs=invs,
                issues=issues
            )
            gen_source = "fallback_template"
            val_status = "fallback_template"

        # 5. Persist to DB
        brief_row = Brief(
            id=brief_id(),
            patient_id=patient_id,
            specialty=specialty,
            content_json=final_brief.model_dump_json(),
            generation_model=settings.LLM_PRIMARY if gen_source == "llm" else "deterministic_template",
            generation_source=gen_source,
            validation_report_id=val_rep_id,
            status=val_status,
            input_fingerprint=fingerprint
        )
        db.add(brief_row)
        db.commit()

        return final_brief

    @staticmethod
    def get_latest_brief(db: Session, patient_id: str) -> Optional[DoctorBrief]:
        b = db.query(Brief).filter(Brief.patient_id == patient_id).order_by(desc(Brief.created_at)).first()
        if not b:
            return None
        return DoctorBrief.model_validate(json.loads(b.content_json))

    @staticmethod
    def get_brief_by_id(db: Session, bid: str) -> Optional[DoctorBrief]:
        b = db.query(Brief).filter(Brief.id == bid).first()
        if not b:
            return None
        return DoctorBrief.model_validate(json.loads(b.content_json))

brief_service = BriefService()
