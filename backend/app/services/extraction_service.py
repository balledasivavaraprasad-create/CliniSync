from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import structlog
from app.ai.gateway import llm_gateway
from app.schemas.ai_contracts import (
    ExtractionResult,
    ExtractionMedication,
    ExtractionInvestigation,
    ExtractionDiagnosis,
    ExtractionGenericItem,
    EvidenceReference
)

logger = structlog.get_logger(__name__)

class ExtractionService:
    def __init__(self) -> None:
        prompt_path = Path(__file__).parent.parent / "ai" / "prompts" / "extract_entities.md"
        with open(prompt_path, "r", encoding="utf-8") as f:
            self.system_prompt = f.read()

    def _fallback_deterministic_extract(self, pages: List[Dict[str, Any]]) -> ExtractionResult:
        """
        Regex-based extraction fallback for basic lab tests and common medications.
        Ensures pipeline does not completely fail when LLMs are offline/unavailable.
        """
        result = ExtractionResult()
        
        for p in pages:
            text = p.get("text", "")
            page_num = p.get("page_number", 1)
            
            # Simple HbA1c match
            hba1c_match = re.search(r"(?:hba1c|glycated\s+hemoglobin)[\s:]*([0-9.]+)\s*(%)?", text, re.I)
            if hba1c_match:
                val = hba1c_match.group(1)
                unit = hba1c_match.group(2) or "%"
                result.investigations.append(
                    ExtractionInvestigation(
                        test="HbA1c",
                        value=val,
                        unit=unit,
                        reference_range="< 5.7%",
                        flag="high" if float(val) >= 5.7 else "normal",
                        confidence=0.75,
                        evidence=EvidenceReference(text=hba1c_match.group(0), page=page_num)
                    )
                )

            # Common medications match (Metformin, Glimepiride, Atorvastatin, Telmisartan, etc.)
            med_pattern = r"(?:tab|cap|tablet)?\s*(metformin|glimepiride|atorvastatin|telmisartan|aspirin|amlodipine|losartan)\s*([0-9]+\s*(?:mg|g|mcg))?\s*(od|bd|tds|qid|hs|prn|once daily|twice daily)?"
            for m in re.finditer(med_pattern, text, re.I):
                drug = m.group(1).title()
                strength = m.group(2)
                freq = m.group(3)
                result.medications.append(
                    ExtractionMedication(
                        name=drug,
                        strength=strength,
                        frequency=freq,
                        confidence=0.75,
                        evidence=EvidenceReference(text=m.group(0), page=page_num)
                    )
                )

            # Common Diagnoses
            diag_pattern = r"(type\s*2\s*diabetes|type\s*1\s*diabetes|hypertension|dyslipidemia|hypothyroidism)"
            for d in re.finditer(diag_pattern, text, re.I):
                result.diagnoses.append(
                    ExtractionDiagnosis(
                        text=d.group(1).title(),
                        confidence=0.75,
                        evidence=EvidenceReference(text=d.group(0), page=page_num)
                    )
                )

        return result

    async def extract(self, pages: List[Dict[str, Any]], doc_type: str) -> ExtractionResult:
        """
        Extracts clinical entities from pages using LLMGateway.
        """
        formatted_pages = []
        for p in pages:
            formatted_pages.append(f"--- Page {p.get('page_number', 1)} ---\n{p.get('text', '')}")
        full_text = "\n\n".join(formatted_pages)

        # Limit to avoid exceeding prompt constraints
        truncated_text = full_text[:12000]

        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"Document Type: {doc_type}\nExtract all entities from the following document:\n<document_text>\n{truncated_text}\n</document_text>"
            }
        ]

        try:
            res: ExtractionResult = llm_gateway.complete_json(
                task="extract",
                messages=messages,
                schema=ExtractionResult,
                slot="llm_extract",
                temperature=0.0
            )
            # A gateway can return a schema-valid but empty result — every
            # provider refused and the fallback path produced no matches. Treat
            # that the same as an exception so extraction always degrades to the
            # deterministic regexes instead of silently yielding no facts.
            if res is not None and not _is_empty(res):
                return res
            logger.warning("entity_extraction_returned_empty_falling_back")
        except Exception as e:
            logger.error("entity_extraction_llm_failed_falling_back", error=str(e))
        return self._fallback_deterministic_extract(pages)

def _is_empty(result: ExtractionResult) -> bool:
    """True when an `ExtractionResult` carries nothing at all."""
    return not any(
        getattr(result, field, None)
        for field in (
            "medications",
            "investigations",
            "diagnoses",
            "symptoms",
            "allergies",
            "procedures",
            "observations",
            "vitals",
            "document_level_dates",
        )
    )


extraction_service = ExtractionService()
