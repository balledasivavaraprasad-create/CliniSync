"""
Comprehensive Confidence Calculation Audit Test Suite for ClinSync.

Audits:
1. LLM Self-Report Distrust:
   - LLM stating confidence = 0.95 or 0.99 is NEVER trusted on its own.
   - Composite confidence is derived mathematically from observable factors.
2. Multi-Factor Observable Inputs:
   - extraction confidence & method
   - source quality & OCR confidence
   - evidence match quality (Level 1 exact, Level 2 fuzzy, Level 3 semantic, Level 4 unverified)
   - provenance verification
   - structured validation (normalization, canonical codes, valid units)
   - contradiction presence / conflicting sources
   - clinical ambiguity (missing dosage, unmapped frequency)
   - temporal consistency (valid date vs undated vs future/anachronistic date)
3. Mandated Scenarios:
   - Documented + exact evidence + no contradiction -> High confidence (>= 0.85, band high)
   - LLM inference + weak evidence -> Lower confidence (< 0.85, band medium)
   - Conflicting sources -> Confidence reflects conflict (<= 0.45, band needs_verification, state CONFLICTING)
   - No evidence -> UNVERIFIED, not high confidence (<= 0.35, band needs_verification, state UNVERIFIED)
4. Explainability:
   - Detailed factor breakdown and human-readable explanation.
   - Preserved on ClinicalFact model and exposed in facts and evidence APIs.
"""

import pytest
import json
from app.services.confidence_service import confidence_service, ConfidenceFactorBreakdown
from app.schemas.common import ConfidenceBand, FactType, VerificationStatus
from app.models.patient import Patient
from app.models.clinical_fact import ClinicalFact
from app.models.medication import Medication
from app.models.contradiction import Contradiction
from app.db.database import get_db_context
from app.utils.ids import patient_id, fact_id, medication_id, contradiction_id


class TestConfidenceCalculationAudit:
    """Verifies that confidence is derived from observable factors, not LLM self-report."""

    def test_llm_high_claim_distrusted_without_evidence(self):
        """Even if LLM claims confidence=0.99, lack of verified evidence must cap score at <= 0.35."""
        breakdown = confidence_service.evaluate_confidence(
            model_confidence=0.99,
            provenance_verified=False,
            evidence_match_level=4,
            source_quality=1.0,
        )
        assert breakdown.final_score <= 0.35
        assert breakdown.confidence_band == ConfidenceBand.needs_verification
        assert breakdown.semantic_state == "UNVERIFIED"
        assert "unverified provenance" in breakdown.explanation

    def test_scenario_documented_exact_evidence_no_contradiction_high_confidence(self):
        """Scenario 1: Documented + exact evidence (Level 1) + no contradiction -> High confidence (>= 0.85)."""
        breakdown = confidence_service.evaluate_confidence(
            model_confidence=0.95,
            provenance_verified=True,
            evidence_match_level=1,
            evidence_match_score=1.0,
            extraction_method="pdf_text",
            ocr_confidence=0.98,
            source_quality=1.0,
            structured_validation=True,
            has_contradiction=False,
            temporal_consistency=1.0,
        )
        assert breakdown.final_score >= 0.85
        assert breakdown.confidence_band == ConfidenceBand.high
        assert breakdown.semantic_state == "DOCUMENTED"
        assert "High confidence" in breakdown.explanation
        assert "Level 1" in breakdown.explanation

    def test_scenario_llm_inference_weak_evidence_lower_confidence(self):
        """Scenario 2: LLM inference + weak evidence (Level 3 semantic or Level 2 fuzzy) -> Lower confidence (< 0.85)."""
        breakdown = confidence_service.evaluate_confidence(
            model_confidence=0.95,  # LLM overconfident claim
            provenance_verified=True,
            evidence_match_level=3,  # Semantic inference, not verbatim
            evidence_match_score=0.60,
            extraction_method="llm_extract",
            ocr_confidence=0.85,
            source_quality=0.85,
            structured_validation=True,
            has_contradiction=False,
            temporal_consistency=0.90,
        )
        # Even though LLM claimed 0.95, weak evidence and LLM inference lowers confidence
        assert breakdown.final_score < 0.85
        assert breakdown.confidence_band == ConfidenceBand.medium
        assert "semantic inference" in breakdown.explanation.lower()

    def test_scenario_conflicting_sources_reflects_conflict(self):
        """Scenario 3: Conflicting sources -> confidence must reflect conflict (<= 0.45)."""
        breakdown = confidence_service.evaluate_confidence(
            model_confidence=0.98,  # LLM claims extreme confidence
            provenance_verified=True,
            evidence_match_level=1,
            extraction_method="pdf_text",
            has_contradiction=True,  # Conflicting with another record
        )
        assert breakdown.final_score <= 0.45
        assert breakdown.confidence_band == ConfidenceBand.needs_verification
        assert breakdown.semantic_state == "CONFLICTING"
        assert "conflicting" in breakdown.explanation.lower()
        assert breakdown.contradiction_penalty > 0.0

    def test_scenario_no_evidence_unverified(self):
        """Scenario 4: No evidence -> UNVERIFIED, not high confidence."""
        breakdown = confidence_service.evaluate_confidence(
            model_confidence=0.90,
            provenance_verified=False,
            evidence_match_level=4,
            evidence_match_score=0.0,
        )
        assert breakdown.final_score <= 0.35
        assert breakdown.confidence_band == ConfidenceBand.needs_verification
        assert breakdown.semantic_state == "UNVERIFIED"

    def test_source_quality_and_ocr_degradation(self):
        """Low OCR quality (< 0.70) caps confidence regardless of LLM claims."""
        breakdown = confidence_service.evaluate_confidence(
            model_confidence=0.95,
            provenance_verified=True,
            evidence_match_level=1,
            ocr_confidence=0.55,  # Low OCR scan quality
            source_quality=0.60,
        )
        assert breakdown.final_score <= 0.70
        assert breakdown.confidence_band != ConfidenceBand.high
        assert "low source ocr quality" in breakdown.explanation.lower()

    def test_structured_validation_unknown_mapping_penalty(self):
        """Unknown normalization mapping applies a penalty and reduces score."""
        normal_eval = confidence_service.evaluate_confidence(
            model_confidence=0.90,
            provenance_verified=True,
            evidence_match_level=1,
            unknown_mapping=False,
            structured_validation=True,
        )
        unmapped_eval = confidence_service.evaluate_confidence(
            model_confidence=0.90,
            provenance_verified=True,
            evidence_match_level=1,
            unknown_mapping=True,
            structured_validation=True,
        )
        assert unmapped_eval.final_score < normal_eval.final_score

    def test_ambiguity_penalty_for_missing_dosage_or_frequency(self):
        """Ambiguity penalty lowers composite confidence."""
        clear_eval = confidence_service.evaluate_confidence(
            model_confidence=0.90,
            provenance_verified=True,
            evidence_match_level=1,
            ambiguity_penalty=0.0,
        )
        ambig_eval = confidence_service.evaluate_confidence(
            model_confidence=0.90,
            provenance_verified=True,
            evidence_match_level=1,
            ambiguity_penalty=0.15,
        )
        assert ambig_eval.final_score < clear_eval.final_score

    def test_confidence_breakdown_dictionary_explainable(self):
        """Confidence breakdown provides complete explainability for auditing."""
        breakdown = confidence_service.evaluate_confidence(
            model_confidence=0.92,
            provenance_verified=True,
            evidence_match_level=1,
            extraction_method="pdf_text",
            ocr_confidence=0.96,
            structured_validation=True,
        )
        d = breakdown.to_dict()
        assert "score" in d
        assert "band" in d
        assert "semantic_state" in d
        assert "factors" in d
        assert "explanation" in d
        factors = d["factors"]
        assert "extraction" in factors
        assert "source_quality" in factors
        assert "evidence_match" in factors
        assert "provenance_verified" in factors
        assert "structured_validation" in factors
        assert "has_contradiction" in factors
        assert "temporal_consistency" in factors


class TestConfidenceInDatabaseAndRoutes:
    """Verifies that confidence explanations and conflict caps persist in DB and routes."""

    def test_clinical_fact_confidence_explanation_property(self):
        """ClinicalFact parses confidence_explanation from normalized_value JSON."""
        explanation_payload = {
            "score": 0.92,
            "band": "high",
            "semantic_state": "DOCUMENTED",
            "explanation": "High confidence: verified exact match",
            "factors": {"extraction": {"score": 0.95}}
        }
        fact = ClinicalFact(
            id="f_test_expl",
            patient_id="p1",
            fact_type="medication",
            value="Metformin 500mg",
            source_text="Metformin 500mg daily",
            normalized_value=json.dumps({
                "canonical_name": "metformin",
                "confidence_explanation": explanation_payload
            }),
            confidence=0.92,
            confidence_band="high",
            provenance_verified=True,
        )
        assert fact.confidence_explanation is not None
        assert fact.confidence_explanation["score"] == 0.92
        assert fact.confidence_explanation["band"] == "high"

    def test_conflicting_medications_capped_in_service(self):
        """Medication service caps confidence for medications involved in active conflict."""
        with get_db_context() as db:
            pid = patient_id()
            p = Patient(id=pid, full_name="Conflict Test Patient")
            db.add(p)

            f1 = ClinicalFact(
                id=fact_id(),
                patient_id=pid,
                fact_type="medication",
                value="Metformin 500mg",
                source_text="Metformin 500mg BD",
                confidence=0.95,
                confidence_band="high",
                provenance_verified=True,
            )
            f2 = ClinicalFact(
                id=fact_id(),
                patient_id=pid,
                fact_type="medication",
                value="Metformin 1000mg",
                source_text="Metformin 1000mg OD",
                confidence=0.95,
                confidence_band="high",
                provenance_verified=True,
            )
            db.add(f1)
            db.add(f2)
            db.flush()

            m1 = Medication(
                id=medication_id(),
                patient_id=pid,
                fact_id=f1.id,
                canonical_name="metformin",
                raw_name="Metformin",
                strength_value=500.0,
                strength_unit="mg",
                dose_text="500mg",
                frequency_code="bd",
                group_key=f"{pid}_metformin",
                confidence=0.95,
            )
            m2 = Medication(
                id=medication_id(),
                patient_id=pid,
                fact_id=f2.id,
                canonical_name="metformin",
                raw_name="Metformin",
                strength_value=1000.0,
                strength_unit="mg",
                dose_text="1000mg",
                frequency_code="od",
                group_key=f"{pid}_metformin",
                confidence=0.95,
            )
            db.add(m1)
            db.add(m2)

            # Add an active conflict between m1 and m2
            c = Contradiction(
                id=contradiction_id(),
                patient_id=pid,
                issue_type="medication_conflict",
                severity="high",
                title="Metformin dose discrepancy",
                description="Conflicting doses: 500mg vs 1000mg",
                related_fact_ids=json.dumps([f1.id, f2.id]),
                status="open",
            )
            db.add(c)
            db.commit()

            from app.services.medication_service import medication_service
            med_list = medication_service.get_patient_medications(db, pid)

            assert len(med_list) >= 1
            met_med = next(m for m in med_list if m["canonical_name"] == "metformin")
            assert met_med["has_conflict"] is True
            # Conflicting source MUST NOT receive high confidence merely because LLM claimed 0.95
            assert met_med["confidence"] <= 0.45
            assert met_med["confidence_band"] == "needs_verification"
            assert met_med["semantic_state"] == "CONFLICTING"
