from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
import json
import structlog

from app.models.consultation import Consultation, ConsultationVersion
from app.models.contradiction import Contradiction
from app.models.clinical_fact import ClinicalFact
from app.models.validation_report import ValidationReport
from app.schemas.common import ValidationOutcome, ValidationGate, Severity, ConsultationOrigin
from app.utils.ids import report_id
from app.validation.validators.directive_language import check_directive_language
from app.validation.validators.causality_language import check_causality_language
from app.validation.validators.conflict_integrity import check_conflict_integrity
from app.validation.validators.hallucination_check import check_hallucination
from app.validation.validators.provenance_validator import check_provenance
from app.validation.validators.numeric_consistency import check_numeric_consistency
from app.validation.validators.llm_judge import evaluate_gate1_judge

logger = structlog.get_logger(__name__)

class Gate1MemoryValidator:
    def validate_approval(
        self,
        db: Session,
        consultation_id: str,
        acknowledged_unedited: bool = False,
        approved_by: str = "doctor",
        run_judge: bool = True
    ) -> Tuple[ValidationOutcome, List[Dict[str, Any]], Optional[str]]:
        """
        Runs Gate 1 pre-clinical-memory verification.
        Returns (outcome, checks, report_id).
        """
        cns = db.query(Consultation).filter(Consultation.id == consultation_id).first()
        if not cns:
            return ValidationOutcome.blocked, [{"name": "consultation_exists", "passed": False, "severity": "block", "detail": "Consultation not found"}], None

        current_ver = db.query(ConsultationVersion).filter(ConsultationVersion.id == cns.current_version_id).first()
        if not current_ver:
            return ValidationOutcome.blocked, [{"name": "version_exists", "passed": False, "severity": "block", "detail": "Current consultation version not found"}], None

        checks = []
        patient_id = cns.patient_id

        # 1. State check: untouched AI draft cannot be approved without explicit acknowledged_unedited
        if current_ver.origin == ConsultationOrigin.ai_generated.value and not acknowledged_unedited:
            checks.append({
                "name": "authorship_state_check",
                "passed": False,
                "severity": "block",
                "detail": "Untouched AI-generated draft cannot be approved into clinical memory without explicit doctor acknowledgment."
            })
        else:
            checks.append({"name": "authorship_state_check", "passed": True, "severity": "info", "detail": f"Origin: {current_ver.origin}"})

        # 2. Check open high-severity conflicts
        high_conflicts = db.query(Contradiction).filter(
            Contradiction.patient_id == patient_id,
            Contradiction.severity == Severity.high.value,
            Contradiction.status == "open"
        ).all()
        if high_conflicts:
            checks.append({
                "name": "unacknowledged_high_conflict",
                "passed": False,
                "severity": "block",
                "detail": f"Patient has {len(high_conflicts)} open high-severity clinical conflict(s) that must be acknowledged before approving into memory."
            })
        else:
            checks.append({"name": "unacknowledged_high_conflict", "passed": True, "severity": "info", "detail": "No unacknowledged high-severity conflicts"})

        # Check medium severity conflicts (emits warning / pass_with_flags)
        med_conflicts = db.query(Contradiction).filter(
            Contradiction.patient_id == patient_id,
            Contradiction.severity == Severity.medium.value,
            Contradiction.status == "open"
        ).all()
        if med_conflicts:
            checks.append({
                "name": "open_medium_conflict",
                "passed": False,
                "severity": "warn",
                "detail": f"Patient has {len(med_conflicts)} open medium-severity conflict(s)."
            })

        # 3. Content checks
        content = current_ver.content_json if isinstance(current_ver.content_json, dict) else json.loads(current_ver.content_json or "{}")
        content_text = json.dumps(content)

        # AI-authored sections directive/causality check
        # (Doctor's assessment and plan can contain doctor instructions, but history/meds derived from AI must be clean)
        history_text = f"{content.get('chief_complaint', '')} {content.get('history_of_present_illness', '')} {content.get('past_history', '')}"
        passed_dir, sev_dir, msg_dir = check_directive_language(history_text)
        checks.append({"name": "directive_language", "passed": passed_dir, "severity": sev_dir, "detail": msg_dir})

        passed_caus, sev_caus, msg_caus = check_causality_language(history_text)
        checks.append({"name": "causality_language", "passed": passed_caus, "severity": sev_caus, "detail": msg_caus})

        # 4. Check facts and provenance
        facts = db.query(ClinicalFact).filter(ClinicalFact.patient_id == patient_id).all()
        valid_fact_ids = {f.id for f in facts}
        unverified_fact_ids = {f.id for f in facts if not f.provenance_verified}

        evidence_ids = content.get("evidence_ids", [])
        if evidence_ids:
            passed_prov, sev_prov, msg_prov = check_provenance(evidence_ids, valid_fact_ids, unverified_fact_ids)
            checks.append({"name": "provenance_check", "passed": passed_prov, "severity": sev_prov, "detail": msg_prov})

        # 5. LLM Judge Faithfulness Check
        judge_verdict = {}
        if run_judge and not any(c["severity"] == "block" and not c["passed"] for c in checks):
            j_pass, j_sev, verdict = evaluate_gate1_judge(
                content_to_judge=f"Consultation Content:\n{content_text}",
                task="gate1_memory_judge"
            )
            judge_verdict = verdict
            if not j_pass and j_sev == "judge_unavailable":
                # Fail closed for Gate 1 if judge fails per Section 12.1.
                # `code` lets the approve route tell an outage apart from a
                # content rejection without pattern-matching the message, so it
                # can answer 503 (retryable) instead of 422.
                checks.append({
                    "name": "llm_judge_faithfulness",
                    "passed": False,
                    "severity": "block",
                    "code": "VALIDATION_UNAVAILABLE",
                    "detail": "Gate 1 validation failed closed: validation judge service is unavailable."
                })
            elif not j_pass:
                checks.append({
                    "name": "llm_judge_faithfulness",
                    "passed": False,
                    "severity": "block",
                    "detail": f"Judge blocked content: {verdict.get('reason', 'Failed rubric thresholds')}"
                })
            else:
                checks.append({"name": "llm_judge_faithfulness", "passed": True, "severity": "info", "detail": "Judge passed"})

        # Determine overall outcome
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
            gate=ValidationGate.gate1_memory.value,
            subject_type="consultation",
            subject_id=consultation_id,
            outcome=outcome.value,
            checks_json=json.dumps(checks),
            judge_model="llm_judge",
            judge_verdict_json=json.dumps(judge_verdict)
        )
        db.add(rep)
        db.commit()

        return outcome, checks, rep.id

gate1_validator = Gate1MemoryValidator()
