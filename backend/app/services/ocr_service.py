import json
import os
from pathlib import Path
from typing import Any, Dict, List
import fitz  # PyMuPDF
from PIL import Image
import structlog
from app.config import settings
from app.ai.gateway import llm_gateway
from app.api.errors import OCRFailed

logger = structlog.get_logger(__name__)

class OCRService:
    def __init__(self) -> None:
        self.min_text_chars = 50

    async def extract_text(self, patient_id: str, document_id: str, file_path: str, mime_type: str) -> List[Dict[str, Any]]:
        """
        Extracts text from PDF or images using PyMuPDF and vision OCR fallback.
        Returns list of page dicts: [{page_number, text, ocr_confidence, method}].
        """
        if not os.path.exists(file_path):
            raise OCRFailed(f"File not found for OCR: {file_path}")

        pages: List[Dict[str, Any]] = []

        try:
            if mime_type == "application/pdf":
                doc = fitz.open(file_path)
                has_pdf_text = False
                has_vision = False

                for page_idx in range(len(doc)):
                    page_num = page_idx + 1
                    page = doc[page_idx]
                    page_text = page.get_text("text").strip()

                    if len(page_text) >= self.min_text_chars:
                        pages.append({
                            "page_number": page_num,
                            "text": page_text,
                            "ocr_confidence": 0.95,
                            "method": "pdf_text"
                        })
                        has_pdf_text = True
                    else:
                        # Fallback to vision OCR for this page
                        pix = page.get_pixmap(dpi=150)
                        img_bytes = pix.tobytes("png")
                        try:
                            vision_text = llm_gateway.vision_extract(
                                task="page_ocr",
                                image_bytes=img_bytes,
                                prompt="Extract all text from this medical document page accurately. Preserve line breaks, drug names, dosages, units, and dates exactly as written. Return only the extracted text without introductory or concluding remarks.",
                                mime_type="image/png"
                            )
                            extracted = vision_text.strip() if vision_text else page_text
                            pages.append({
                                "page_number": page_num,
                                "text": extracted,
                                "ocr_confidence": 0.85 if extracted else 0.50,
                                "method": "vision"
                            })
                            has_vision = True
                        except Exception as e:
                            logger.warning("vision_ocr_page_fallback_failed", page=page_num, error=str(e))
                            pages.append({
                                "page_number": page_num,
                                "text": page_text or "[Unreadable or empty page content]",
                                "ocr_confidence": 0.40,
                                "method": "fallback"
                            })

                doc.close()
            elif mime_type.startswith("image/"):
                # Single page image
                with open(file_path, "rb") as f:
                    img_bytes = f.read()

                try:
                    vision_text = llm_gateway.vision_extract(
                        task="image_ocr",
                        image_bytes=img_bytes,
                        prompt="Extract all text from this medical document image verbatim. Return only the extracted text with proper line breaks, preserving numbers, dosages, and dates.",
                        mime_type=mime_type
                    )
                    extracted = vision_text.strip() if vision_text else ""
                    pages.append({
                        "page_number": 1,
                        "text": extracted,
                        "ocr_confidence": 0.88 if extracted else 0.40,
                        "method": "vision"
                    })
                except Exception as e:
                    logger.error("vision_ocr_image_failed", error=str(e))
                    pages.append({
                        "page_number": 1,
                        "text": "[Image text could not be extracted]",
                        "ocr_confidence": 0.30,
                        "method": "fallback"
                    })
            else:
                raise OCRFailed(f"Unsupported MIME type for OCR: {mime_type}")

            # Save full extracted text per page JSON to storage/patients/{patient_id}/ocr/{doc_id}.json
            ocr_dir = Path(settings.STORAGE_ROOT) / "patients" / patient_id / "ocr"
            ocr_dir.mkdir(parents=True, exist_ok=True)
            ocr_file = ocr_dir / f"{document_id}.json"
            with open(ocr_file, "w", encoding="utf-8") as f:
                json.dump(pages, f, indent=2, ensure_ascii=False)

            return pages

        except Exception as e:
            if isinstance(e, OCRFailed):
                raise e
            logger.error("ocr_extraction_error", error=str(e), doc_id=document_id)
            raise OCRFailed(f"Failed to extract text from document: {str(e)}")

ocr_service = OCRService()
