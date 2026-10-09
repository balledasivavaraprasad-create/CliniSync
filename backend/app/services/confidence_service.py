"""
Observable, Multi-Factor Clinical Confidence Service.

Confidence is NEVER simply taken from an LLM self-report (e.g. `confidence = 0.95`).
Instead, confidence is derived mathematically from observable, verifiable factors:
1. Extraction method & confidence (deterministic, direct PDF text, vision OCR, LLM inference)
2. Source document quality (OCR clarity, document classification confidence)
3. Evidence match quality (Level 1: Exact, Level 2: Fuzzy, Level 3: Semantic, Level 4: Unverified)
4. Provenance verification (whether verified against verbatim text in source document)
5. Structured validation (successful normalization, standard canonical codes, valid units/ranges)
6. Contradiction presence (conflicting sources/doses/diagnoses cap confidence)
7. Clinical ambiguity (missing frequency, vague dosage, unmapped clinical terms)
8. Temporal consistency (valid past/present date vs undated vs anachronistic/future date)

Clinical Invariants:
- A clinically conflicting fact MUST NOT receive a high confidence score.
- Unverified facts (no verified evidence) MUST NOT receive a high or medium confidence score.
- Confidence is made explainable with human-readable factor breakdowns.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from app.schemas.common import ConfidenceBand


@dataclass
class ConfidenceFactorBreakdown:
    extraction_score: float
    extraction_method: str
    source_quality_score: float
    evidence_match_score: float
    evidence_match_level: int
    provenance_verified: bool
    structured_validation_score: float
    has_contradiction: bool
    contradiction_penalty: float
    ambiguity_penalty: float
    temporal_consistency_score: float
    raw_model_confidence: Optional[float]
    base_score: float
    final_score: float
    confidence_band: ConfidenceBand
    semantic_state: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.final_score,
            "band": self.confidence_band.value,
            "semantic_state": self.semantic_state,
            "factors": {
                "extraction": {
                    "score": round(self.extraction_score, 2),
                    "method": self.extraction_method,
                    "model_claim": self.raw_model_confidence,
                },
                "source_quality": round(self.source_quality_score, 2),
                "evidence_match": {
                    "score": round(self.evidence_match_score, 2),
                    "level": self.evidence_match_level,
                },
                "provenance_verified": self.provenance_verified,
                "structured_validation": round(self.structured_validation_score, 2),
                "has_contradiction": self.has_contradiction,
                "contradiction_penalty": round(self.contradiction_penalty, 2),
                "ambiguity_penalty": round(self.ambiguity_penalty, 2),
                "temporal_consistency": round(self.temporal_consistency_score, 2),
            },
            "explanation": self.explanation,
        }


class ConfidenceService:
    def evaluate_confidence(
        self,
        model_confidence: float = 0.85,
        provenance_verified: bool = False,
        ocr_confidence: float = 1.0,
        unknown_mapping: bool = False,
        source_quality: float = 1.0,
        ambiguity_penalty: float = 0.0,
        evidence_match_level: int = 1,
        evidence_match_score: Optional[float] = None,
        extraction_method: str = "pdf_text",
        has_contradiction: bool = False,
        structured_validation: bool = True,
        temporal_consistency: float = 1.0,
    ) -> ConfidenceFactorBreakdown:
        """
        Calculates explainable confidence from observable factors.
        """
        # 1. Extraction method factor
        method_lower = (extraction_method or "pdf_text").lower()
        if "deterministic" in method_lower:
            ext_score = 1.0
        elif "pdf_text" in method_lower or "digital" in method_lower:
            ext_score = 0.95
        elif "vision" in method_lower or "ocr" in method_lower:
            ext_score = 0.85
        elif "llm" in method_lower or "ai" in method_lower:
            # LLM inference: do not blindly trust self-report
            # Base credibility 0.82; if model itself lacked confidence, respect the doubt
            ext_score = min(0.85, model_confidence) if model_confidence is not None else 0.80
        else:
            ext_score = 0.75

        # 2. Source quality factor (OCR quality * source quality)
        src_score = min(1.0, max(0.0, (ocr_confidence if ocr_confidence is not None else 1.0) * (source_quality if source_quality is not None else 1.0)))

        # 3. Evidence match quality
        if not provenance_verified or evidence_match_level == 4:
            ev_score = 0.0
        elif evidence_match_level == 1:
            ev_score = 1.0
        elif evidence_match_level == 2:
            ev_score = max(0.75, (evidence_match_score if evidence_match_score is not None else 0.85))
        elif evidence_match_level == 3:
            # Semantic inference / support
            ev_score = 0.60
        else:
            ev_score = 0.0

        # 4. Structured validation factor
        if not structured_validation:
            struct_score = 0.60
        elif unknown_mapping:
            struct_score = 0.80
        else:
            struct_score = 1.0

        # 5. Temporal consistency factor
        temp_score = min(1.0, max(0.0, temporal_consistency if temporal_consistency is not None else 1.0))

        # 6. Weighted Observable Composite Base Score
        # Evidence match (35%) and source quality (25%) account for 60% of the score.
        composite = (
            0.20 * ext_score +
            0.25 * src_score +
            0.35 * ev_score +
            0.10 * struct_score +
            0.10 * temp_score
        )

        contradiction_penalty = 0.0
        score = composite

        # Model doubt bounding: If model itself was skeptical (< composite), respect model doubt
        if model_confidence is not None and model_confidence < score and provenance_verified and not has_contradiction:
            score = min(score, model_confidence)

        # 7. Apply Penalties
        if unknown_mapping and structured_validation:
            score = max(0.0, score - 0.08)

        if ambiguity_penalty > 0.0:
            score = max(0.0, score - ambiguity_penalty)

        # 8. Apply Critical Caps & Safety Invariants
        semantic_state = "DOCUMENTED"
        reasons: List[str] = []

        # INVARIANT 1: No evidence / Unverified provenance -> strict cap <= 0.35, UNVERIFIED
        if not provenance_verified or evidence_match_level == 4 or ev_score == 0.0:
            score = min(score, 0.35)
            semantic_state = "UNVERIFIED"
            reasons.append("unverified provenance (no supporting evidence found in document)")

        # INVARIANT 2: Conflicting sources / Contradiction presence -> strict cap <= 0.45, CONFLICTING
        if has_contradiction:
            contradiction_penalty = 0.25
            score = min(score, 0.45)
            semantic_state = "CONFLICTING"
            reasons.append("conflicting clinical sources detected across records")

        # INVARIANT 3: Low source / OCR quality (< 0.70) -> cap at 0.70
        if src_score < 0.70:
            score = min(score, 0.70)
            reasons.append(f"low source OCR quality ({src_score:.2f})")

        # INVARIANT 4: Semantic inference (Level 3) -> cap at 0.70
        if evidence_match_level == 3 and provenance_verified and not has_contradiction:
            score = min(score, 0.70)
            reasons.append("semantic inference rather than verbatim match")

        final_score = round(max(0.0, min(1.0, score)), 2)

        # Determine Confidence Band
        if not provenance_verified or has_contradiction or final_score < 0.60:
            band = ConfidenceBand.needs_verification
        elif final_score >= 0.85:
            band = ConfidenceBand.high
        else:
            band = ConfidenceBand.medium

        # Generate Explainable Summary
        if band == ConfidenceBand.high:
            explanation = (
                f"High confidence ({final_score:.2f}): verified exact match (Level {evidence_match_level}) "
                f"from high-quality source ({src_score:.2f}) with structured normalization and no clinical contradictions."
            )
        elif band == ConfidenceBand.medium:
            caveats = "; ".join(reasons) if reasons else "moderate textual match or minor ambiguity"
            explanation = (
                f"Medium confidence ({final_score:.2f}): supported by {method_lower} extraction with "
                f"Level {evidence_match_level} evidence match ({caveats})."
            )
        else:
            cause = "; ".join(reasons) if reasons else f"composite score ({final_score:.2f}) below threshold"
            explanation = (
                f"Needs verification ({final_score:.2f}): {cause}. Fact requires clinical review."
            )

        return ConfidenceFactorBreakdown(
            extraction_score=ext_score,
            extraction_method=method_lower,
            source_quality_score=src_score,
            evidence_match_score=ev_score,
            evidence_match_level=evidence_match_level,
            provenance_verified=provenance_verified,
            structured_validation_score=struct_score,
            has_contradiction=has_contradiction,
            contradiction_penalty=contradiction_penalty,
            ambiguity_penalty=ambiguity_penalty,
            temporal_consistency_score=temp_score,
            raw_model_confidence=model_confidence,
            base_score=round(composite, 2),
            final_score=final_score,
            confidence_band=band,
            semantic_state=semantic_state,
            explanation=explanation,
        )

    def calculate_confidence(
        self,
        model_confidence: float = 0.85,
        provenance_verified: bool = False,
        ocr_confidence: float = 1.0,
        unknown_mapping: bool = False,
        source_quality: float = 1.0,
        ambiguity_penalty: float = 0.0,
        evidence_match_level: int = 1,
        evidence_match_score: Optional[float] = None,
        extraction_method: str = "pdf_text",
        has_contradiction: bool = False,
        structured_validation: bool = True,
        temporal_consistency: float = 1.0,
    ) -> Tuple[float, ConfidenceBand]:
        """
        Calculates final fact confidence and band according to observable factors.
        Returns (score, band).
        """
        res = self.evaluate_confidence(
            model_confidence=model_confidence,
            provenance_verified=provenance_verified,
            ocr_confidence=ocr_confidence,
            unknown_mapping=unknown_mapping,
            source_quality=source_quality,
            ambiguity_penalty=ambiguity_penalty,
            evidence_match_level=evidence_match_level,
            evidence_match_score=evidence_match_score,
            extraction_method=extraction_method,
            has_contradiction=has_contradiction,
            structured_validation=structured_validation,
            temporal_consistency=temporal_consistency,
        )
        return res.final_score, res.confidence_band


confidence_service = ConfidenceService()
