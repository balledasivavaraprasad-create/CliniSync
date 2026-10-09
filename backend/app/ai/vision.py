from typing import Optional
from app.ai.gateway import LLMGateway


def extract_text_from_image(
    image_bytes: bytes,
    prompt: str = "Perform complete and verbatim optical character recognition (OCR) of this medical record. Extract all visible printed and handwritten text accurately.",
    mime_type: str = "image/jpeg",
    request_id: Optional[str] = None,
) -> str:
    gateway = LLMGateway.get_instance()
    return gateway.vision_extract(
        task="ocr_vision",
        image_bytes=image_bytes,
        prompt=prompt,
        mime_type=mime_type,
        request_id=request_id,
    )
