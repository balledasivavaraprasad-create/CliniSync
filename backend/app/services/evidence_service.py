from typing import Any, Dict, List, Optional, Tuple
from app.utils.text import verify_provenance_text
from app.config import settings

class EvidenceService:
    def verify_evidence(
        self,
        source_text: str,
        page_number: int,
        pages_dict: Dict[int, str]
    ) -> Tuple[bool, float, Optional[int]]:
        """
        Verifies that source_text is faithfully present in the specified page (or adjacent pages)
        using exact substring or fuzzy matching >= PROVENANCE_FUZZY_THRESHOLD.
        """
        if not source_text:
            return False, 0.0, None

        page_text = pages_dict.get(page_number, "")
        verified, score, start_idx = verify_provenance_text(
            source_text=source_text,
            page_text=page_text,
            threshold=settings.PROVENANCE_FUZZY_THRESHOLD
        )

        if verified:
            return True, score, start_idx

        # If not verified on requested page, check other pages (page number error tolerance)
        for p_num, p_text in pages_dict.items():
            if p_num == page_number:
                continue
            v, s, idx = verify_provenance_text(
                source_text=source_text,
                page_text=p_text,
                threshold=settings.PROVENANCE_FUZZY_THRESHOLD
            )
            if v:
                return True, s, idx

        return False, score, None

evidence_service = EvidenceService()
