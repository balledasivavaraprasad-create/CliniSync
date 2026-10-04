from typing import Tuple
from app.schemas.common import ConfidenceBand

class ConfidenceService:
    def calculate_confidence(
        self,
        model_confidence: float,
        provenance_verified: bool,
        ocr_confidence: float = 1.0,
        unknown_mapping: bool = False
    ) -> Tuple[float, ConfidenceBand]:
        """
        Calculates final fact confidence and band according to Section 11.7:
        Final confidence = min(model_confidence, ocr_quality_cap, provenance_cap)
        - provenance not verified -> cap 0.59 (needs_verification)
        - OCR quality low (< 0.7) -> cap 0.70
        - unknown normalization mapping -> penalty -0.10
        """
        conf = model_confidence

        if ocr_confidence < 0.70:
            conf = min(conf, 0.70)

        if unknown_mapping:
            conf = max(0.0, conf - 0.10)

        if not provenance_verified:
            conf = min(conf, 0.59)

        # Determine band
        if conf >= 0.85:
            band = ConfidenceBand.high
        elif conf >= 0.60:
            band = ConfidenceBand.medium
        else:
            band = ConfidenceBand.needs_verification

        return round(conf, 2), band

confidence_service = ConfidenceService()
