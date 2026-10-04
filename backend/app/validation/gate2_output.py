from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
import json
import structlog

from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.contradiction import Contradiction
from app.models.validation_report import ValidationReport
from app.schemas.common import ValidationOutcome, ValidationGate, Severity
from app.utils.ids import report_id
from app.validation.validators.directive_language import check_directive_language
from app.validation.validators.causality_language import check_causality_language
from app.validation.validators.conflict_integrity import check_conflict_integrity
from app.validation.validators.hallucination_check import check_hallucination
from app.validation.validators.provenance_validator import check_provenance
from app.validation.validators.numeric_consistency import check_numeric_consistency
from app.validation.validators.llm_judge import evaluate_with_judge

logger = structlog.get_logger(__name__)

class Gate2OutputValidator:
    def validate_brief(
        self,
        db: Session,
        patient_id: str,
        brief_data: Dict[str, Any],
        run_judge: bool = True
    ) -> Tuple[ValidationOutcome, List[Dict[str, Any]], Optional[str]]:
        """
        Runs Gate 2 post-generation validation on DoctorBrief.
        Returns (outcome, checks, report_id).
        """
        checks = []

        # 1. Fetch DB facts for provenance & numeric comparisons
        facts = db.query(ClinicalFact).filter(ClinicalFact.patient_id == patient_id).all()
        valid_fact_ids = {f.id for f in facts}
        unverified_fact_ids = {f.id for f in facts if not f.provenance_verified}
        fact_values = [f.value for f in facts]

        meds = db.query(Medication).filter(Medication.patient_id == patient_id).all()
        known_drugs = {m.canonical_name for m in meds} | {m.raw_name for m in meds}
        known_diags = {f.value for f in facts if f.fact_type == "diagnosis"}

        conflicts = db.query(Contradiction).filter(
            Contradiction.patient_id == patient_id,
            Contradiction.status == "open"
        ).all()
        conflicts_dict = [{"title": c.title, "description": c.description} for c in conflicts]

        brief_str = json.dumps(brief_data)

        # 2. Directive Language Check (INV-7)
        passed_dir, sev_dir, msg_dir = check_directive_language(brief_str)
        checks.append({"name": "directive_language", "passed": passed_dir, "severity": sev_dir, "detail": msg_dir})

        # 3. Causality Language Check (INV-6)
        passed_caus, sev_caus, msg_caus = check_causality_language(brief_str)
        checks.append({"name": "causality_language", "passed": passed_caus, "severity": sev_caus, "detail": msg_caus})

        # 4. Conflict Integrity Check (INV-4)
        passed_conf, sev_conf, msg_conf = check_conflict_integrity(brief_str, conflicts_dict)
        checks.append({"name": "conflict_integrity", "passed": passed_conf, "severity": sev_conf, "detail": msg_conf})

        # 5. Hallucination Check
        passed_hal, sev_hal, msg_hal = check_hallucination(brief_str, known_drugs, known_diags)
        checks.append({"name": "hallucination_check", "passed": passed_hal, "severity": sev_hal, "detail": msg_hal})

        # 6. Numeric Consistency Check
        passed_num, sev_num, msg_num = check_numeric_consistency(brief_str, fact_values)
        checks.append({"name": "numeric_consistency", "passed": passed_num, "severity": sev_num, "detail": msg_num})

        # 7. Provenance Citations Check
        # Collect all evidence_ids cited across brief sections
        cited_eids = []
        for sec_name, sec_val in brief_data.items():
            if isinstance(sec_val, dict) and "evidence_ids" in sec_val:
                cited_eids.extend(sec_val["evidence_ids"])
            elif isinstance(sec_val, list):
                for item in sec_val:
                    if isinstance(item, dict) and "evidence_ids" in item:
                        cited_eids.extend(item["evidence_ids"])

        if cited_eids:
            passed_prov, sev_prov, msg_prov = check_provenance(cited_eids, valid_fact_ids, unverified_fact_ids)
            checks.append({"name": "provenance_check", "passed": passed_prov, "severity": sev_prov, "detail": msg_prov})
        else:
            checks.append({
                "name": "provenance_check",
                "passed": False,
                "severity": "block",
                "detail": "DoctorBrief contains no evidence citations linking to source records."
            })

        # 8. Completeness Check: allergies section must exist even if empty or 'not documented'
        if "allergies" not in brief_data:
            checks.append({
                "name": "completeness_allergies",
                "passed": False,
                "severity": "block",
                "detail": "DoctorBrief missing mandatory allergies section."
            })
        else:
            checks.append({"name": "completeness_allergies", "passed": True, "severity": "info", "detail": "Allergies section present"})

        # 9. LLM Judge Evaluation
        judge_verdict = {}
        if run_judge and not any(c["severity"] == "block" and not c["passed"] for c in checks):
            j_pass, j_sev, verdict = evaluate_with_judge(
                content_to_judge=f"DoctorBrief:\n{brief_str}",
                task="gate2_brief_judge"
            )
            judge_verdict = verdict
            if not j_pass and j_sev == "judge_unavailable":
                # For Gate 2: warning if judge is offline, allows graceful fallback template
                checks.append({
                    "name": "llm_judge_score",
                    "passed": False,
                    "severity": "warn",
                    "detail": "Judge unavailable, proceeding with caution."
                })
            elif not j_pass:
                checks.append({
                    "name": "llm_judge_score",
                    "passed": False,
                    "severity": "block",
                    "detail": f"Judge blocked brief: {verdict.get('reason', 'Failed rubric thresholds')}"
                })
            else:
                checks.append({"name": "llm_judge_score", "passed": True, "severity": "info", "detail": "Judge passed"})

        # Determine outcome
        has_block = any(c["severity"] == "block" and not c["passed"] for c in checks)
        has_warn = any(c["severity"] == "warn" and not c["passed"] for c in checks)

        if has_block:
            outcome = ValidationOutcome.blocked
        elif has_warn:
            outcome = ValidationOutcome.pass_with_flags
        else:
            outcome = ValidationOutcome.pass_

        # Persist report
        rep = ValidationReport(
            id=report_id(),
            gate=ValidationGate.gate2_output.value,
            subject_type="brief",
            subject_id=brief_data.get("id", "temp_brief"),
            outcome=outcome.value,
            checks_json=json.dumps(checks),
            judge_model="llm_judge",
            judge_verdict_json=json.dumps(judge_verdict)
        )
        db.add(rep)
        db.commit()

        return outcome, checks, rep.id

gate2_validator = Gate2OutputValidator()
