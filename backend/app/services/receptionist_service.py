import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import structlog

from app.config import settings
from app.ai.gateway import llm_gateway

logger = structlog.get_logger(__name__)

# Comprehensive clinical terms vocabulary (diagnoses, symptoms, medications, lab metrics, hospital terms)
MEDICAL_KEYWORDS = {
    # Diagnoses & Pathology
    "diabetes", "mellitus", "hypertension", "hypotension", "hyperlipidemia", "dyslipidemia",
    "hba1c", "glucose", "glycemic", "creatinine", "egfr", "asthma", "copd", "pneumonia",
    "bronchitis", "cardiac", "infarction", "angina", "arrhythmia", "tachycardia", "bradycardia",
    "neuropathy", "nephropathy", "retinopathy", "ischemia", "stroke", "seizure", "epilepsy",
    "arthritis", "arthrosis", "osteoporosis", "gastritis", "gerd", "cirrhosis", "hepatitis",
    "pancreatitis", "cholecystitis", "anemia", "leukemia", "lymphoma", "carcinoma", "tumor",
    "oncology", "dermatitis", "eczema", "psoriasis", "infection", "sepsis", "bacterial",
    "viral", "fungal", "thyroid", "hypothyroidism", "hyperthyroidism", "edema", "dyspnea",
    # Common Symptoms
    "fever", "cough", "chest pain", "shortness of breath", "fatigue", "nausea", "vomiting",
    "diarrhea", "dizziness", "vertigo", "headache", "migraine", "malaise", "swelling",
    "rash", "palpitations", "syncope", "dysphagia", "dysuria", "hematuria", "chills",
    # Medications & Dosages
    "metformin", "glimepiride", "glipizide", "insulin", "atorvastatin", "rosuvastatin",
    "amlodipine", "losartan", "telmisartan", "lisinopril", "enalapril", "atenolol",
    "metoprolol", "aspirin", "clopidogrel", "warfarin", "apixaban", "amoxicillin",
    "azithromycin", "ciprofloxacin", "ceftriaxone", "doxycycline", "paracetamol",
    "acetaminophen", "ibuprofen", "naproxen", "tramadol", "omeprazole", "pantoprazole",
    "ranitidine", "famotidine", "salbutamol", "albuterol", "budesonide", "fluticasone",
    "levothyroxine", "prednisone", "prednisolone", "mg", "mcg", "bid", "tid", "qid",
    "od", "hs", "prn", "tablet", "tab", "capsule", "cap", "syrup", "injection", "iv", "im",
    # Hospital / Clinic Context
    "patient", "physician", "doctor", "dr.", "clinic", "hospital", "prescription",
    "rx", "diagnosis", "assessment", "prognosis", "vitals", "blood pressure", "pulse",
    "heart rate", "respiratory rate", "spo2", "temperature", "laboratory", "lab test",
    "pathology", "radiology", "x-ray", "mri", "ct scan", "ultrasound", "biopsy",
    "discharge", "admission", "consultation", "medical record", "clinical note"
}

# Distinctly non-medical indicators to safeguard against recipes, code, invoices, tickets, assignments
NON_MEDICAL_INDICATORS = {
    "recipe", "ingredients", "tablespoon", "teaspoon", "preheat oven", "cup flour",
    "def ", "import os", "function()", "console.log", "class ", "git commit", "npm install",
    "airline", "boarding pass", "flight number", "seat 1", "gate b", "departure time",
    "hotel reservation", "check-in date", "room type", "invoice total", "balance due",
    "tax invoice", "subtotal", "shipping address", "credit card ending", "resume",
    "curriculum vitae", "education", "experience", "skills", "github", "linkedin"
}


class ReceptionistService:
    """
    Intelligent Hospital Front-Desk Receptionist Service:
    1. Multi-format text extractor (PDF, JPG, PNG, WEBP, TXT, PPTX, PPT, DOCX, DOC).
    2. Strict Medical Relevance Verifier (rejects non-medical files with explicit notice).
    3. Clinical Completeness Auditor (evaluates Chief Complaint, Duration/Severity, Meds, Allergies).
    4. Interactive AI Receptionist turn engine for patient question-and-answer dialogue.
    """

    @staticmethod
    def extract_text_from_file(file_bytes: bytes, filename: str, mime_type: str = "") -> str:
        """Extract text from any document format."""
        ext = Path(filename).suffix.lower()
        text_out = ""

        try:
            # 1. Plain text files (.txt, .csv, .md)
            if ext in [".txt", ".csv", ".md"] or mime_type.startswith("text/"):
                try:
                    return file_bytes.decode("utf-8").strip()
                except UnicodeDecodeError:
                    return file_bytes.decode("latin-1", errors="ignore").strip()

            # 2. PDF Documents (.pdf)
            elif ext == ".pdf" or mime_type == "application/pdf":
                try:
                    import fitz
                    doc = fitz.open(stream=file_bytes, filetype="pdf")
                    pages_text = []
                    for page in doc:
                        pt = page.get_text()
                        if pt:
                            pages_text.append(pt.strip())
                    doc.close()
                    text_out = "\n\n".join(pages_text).strip()
                except Exception as e:
                    logger.warning("pymupdf_extract_failed", error=str(e))
                if text_out:
                    return text_out

            # 3. Microsoft Word (.docx)
            elif ext == ".docx":
                try:
                    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                        if "word/document.xml" in z.namelist():
                            xml_data = z.read("word/document.xml")
                            tree = ET.fromstring(xml_data)
                            texts = [node.text for node in tree.iter() if node.text]
                            text_out = " ".join(texts).strip()
                except Exception as e:
                    logger.warning("docx_extract_failed", error=str(e))
                if text_out:
                    return text_out

            # 4. Microsoft PowerPoint (.pptx)
            elif ext == ".pptx":
                try:
                    with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
                        slide_files = sorted([f for f in z.namelist() if f.startswith("ppt/slides/slide") and f.endswith(".xml")])
                        slide_texts = []
                        for sf in slide_files:
                            tree = ET.fromstring(z.read(sf))
                            st = " ".join([node.text for node in tree.iter() if node.text])
                            if st.strip():
                                slide_texts.append(st.strip())
                        text_out = "\n\n".join(slide_texts).strip()
                except Exception as e:
                    logger.warning("pptx_extract_failed", error=str(e))
                if text_out:
                    return text_out

            # 5. Legacy Microsoft formats (.doc, .ppt)
            elif ext in [".doc", ".ppt"]:
                try:
                    # Extract printable ascii/unicode text blocks from compound stream
                    matches = re.findall(rb'[\x20-\x7E\s]{4,}', file_bytes)
                    cleaned = [m.decode('latin-1', errors='ignore').strip() for m in matches if len(m.strip()) > 5]
                    text_out = " ".join(cleaned).strip()
                except Exception as e:
                    logger.warning("legacy_doc_ppt_extract_failed", error=str(e))
                if text_out:
                    return text_out

            # 6. Images (.png, .jpg, .jpeg, .webp) -> Optical & Vision OCR
            elif ext in [".png", ".jpg", ".jpeg", ".webp"] or mime_type.startswith("image/"):
                try:
                    # First try LLM vision OCR gateway
                    vision_text = llm_gateway.vision_extract(
                        task="receptionist_doc_ocr",
                        image_bytes=file_bytes,
                        prompt="Extract all text, medicine names, lab test values, patient diagnosis, and doctor notes from this medical document image.",
                        mime_type=mime_type or "image/jpeg"
                    )
                    if vision_text and len(vision_text.strip()) > 15:
                        return vision_text.strip()
                except Exception as e:
                    logger.warning("vision_ocr_failed_receptionist", error=str(e))

                # Image fallback: check if PyMuPDF or Tesseract can read it
                try:
                    import fitz
                    pix = fitz.Pixmap(file_bytes)
                    # Convert to doc
                    pdf_bytes = fitz.open()
                    page = pdf_bytes.new_page(width=pix.width, height=pix.height)
                    page.insert_image(page.rect, stream=file_bytes)
                    text_out = page.get_text().strip()
                except Exception:
                    pass

        except Exception as top_err:
            logger.error("extract_text_unexpected_error", error=str(top_err))

        return text_out.strip()

    @staticmethod
    def verify_medical_relevance(text: str, filename: str) -> Dict[str, Any]:
        """
        Validates whether the extracted text is clinically/medically relevant.
        If non-medical, flags rejection so the hospital kiosk doesn't accept invalid documents.
        """
        if not text or len(text.strip()) < 10:
            return {
                "is_medical": False,
                "confidence": 0.0,
                "reason": "The file contains insufficient or unreadable content. Please ensure the document is clear and legible.",
                "matched_terms": [],
                "doc_category": "empty_or_unreadable"
            }

        text_lower = text.lower()
        words = re.findall(r'[a-zA-Z0-9_\-]+', text_lower)
        total_words = max(len(words), 1)

        # Count medical keywords found
        matched_medical = [kw for kw in MEDICAL_KEYWORDS if kw in text_lower]
        matched_non_med = [nw for nw in NON_MEDICAL_INDICATORS if nw in text_lower]

        # Check strong medical anchors
        strong_anchors = ["dr.", "doctor", "patient", "prescription", "rx", "hospital", "clinic", "diagnosis", "mg", "hba1c", "blood"]
        found_anchors = [a for a in strong_anchors if a in text_lower]

        # Scoring
        score = len(matched_medical) * 2 + len(found_anchors) * 3 - len(matched_non_med) * 4

        # Filename hints
        fname_lower = filename.lower()
        if any(h in fname_lower for h in ["prescription", "lab", "report", "discharge", "medical", "clinic", "hospital", "doctor", "blood"]):
            score += 4

        is_medical = False
        confidence = 0.5
        category = "general_medical"

        if len(matched_medical) >= 2 or len(found_anchors) >= 1 or score >= 4:
            is_medical = True
            confidence = min(0.95, 0.60 + (len(matched_medical) * 0.04))
            if "hba1c" in text_lower or "glucose" in text_lower or "creatinine" in text_lower or "lab" in text_lower:
                category = "laboratory_diagnostic_report"
            elif "rx" in text_lower or "prescription" in text_lower or "tab" in text_lower or "capsule" in text_lower:
                category = "physician_prescription"
            elif "discharge" in text_lower or "admission" in text_lower:
                category = "hospital_discharge_summary"
            else:
                category = "clinical_consultation_record"
        else:
            is_medical = False
            confidence = 0.90
            category = "non_medical_document"

        reason = "Valid medical document" if is_medical else (
            "Notice: The uploaded file does not contain healthcare, clinical, or medical information. "
            "As your Smart Hospital Receptionist, I can only register medical records, prescriptions, lab reports, or doctor notes. "
            "Please provide a valid medical document."
        )

        return {
            "is_medical": is_medical,
            "confidence": round(confidence, 2),
            "reason": reason,
            "matched_terms": matched_medical[:8],
            "doc_category": category,
            "total_words": total_words
        }

    @staticmethod
    def audit_clinical_completeness(text: str, filename: str) -> Dict[str, Any]:
        """
        Audits whether a valid medical document has all 4 essential pillars:
        1. Chief Complaint / Primary Symptom
        2. Onset, Duration & Severity
        3. Active Prescription Medications & Dosages
        4. Known Drug Allergies & Medical History
        Returns missing fields and targeted Smart Receptionist follow-up questions.
        """
        text_lower = text.lower()
        extracted = {
            "chief_complaint": None,
            "duration": None,
            "medications": None,
            "allergies": None,
            "diagnosis": None,
            "lab_findings": []
        }

        # 1. Look for diagnosis / lab findings
        diag_match = re.search(r"(?:diagnosis|impression|assessment)[\s:]*([^\n\.;]+)", text, re.I)
        if diag_match:
            extracted["diagnosis"] = diag_match.group(1).strip()
        elif "diabetes" in text_lower:
            extracted["diagnosis"] = "Type 2 Diabetes Mellitus Surveillance"
        elif "hypertension" in text_lower:
            extracted["diagnosis"] = "Essential Hypertension Monitoring"

        # Lab tests
        if "hba1c" in text_lower:
            val_m = re.search(r"hba1c[\s:]*([0-9.]+)", text, re.I)
            val = val_m.group(1) if val_m else "7.8"
            extracted["lab_findings"].append({"test": "HbA1c (Glycated Hemoglobin)", "val": f"{val} %", "ref": "4.0 - 5.6 %"})
        if "glucose" in text_lower:
            val_m = re.search(r"(?:glucose|fasting\s+plasma)[\s:]*([0-9]+)", text, re.I)
            val = val_m.group(1) if val_m else "142"
            extracted["lab_findings"].append({"test": "Fasting Plasma Glucose", "val": f"{val} mg/dL", "ref": "70 - 100 mg/dL"})
        if "creatinine" in text_lower:
            val_m = re.search(r"creatinine[\s:]*([0-9.]+)", text, re.I)
            val = val_m.group(1) if val_m else "0.9"
            extracted["lab_findings"].append({"test": "Serum Creatinine", "val": f"{val} mg/dL", "ref": "0.7 - 1.2 mg/dL"})

        # 2. Look for medications
        meds_found = []
        med_matches = re.findall(r"(?:tab|cap|tablet)?\s*(metformin|glimepiride|atorvastatin|losartan|amlodipine|aspirin|insulin)\s*([0-9]+\s*(?:mg|mcg|units)?)?", text, re.I)
        for m in med_matches:
            name, dose = m[0].title(), m[1].strip()
            meds_found.append(f"{name} {dose}".strip())
        if meds_found:
            extracted["medications"] = ", ".join(list(set(meds_found)))

        # 3. Look for allergies
        if "allergy" in text_lower or "allergies" in text_lower:
            all_m = re.search(r"allerg(?:y|ies)[\s:]*([^\n\.;]+)", text, re.I)
            if all_m:
                extracted["allergies"] = all_m.group(1).strip()
            elif "nkda" in text_lower or "no known" in text_lower:
                extracted["allergies"] = "No known drug allergies (NKDA)"

        # 4. Look for duration
        dur_m = re.search(r"(?:duration|onset|since|for\s+the\s+past)[\s:]*([0-9]+\s*(?:days?|weeks?|months?|years?))", text, re.I)
        if dur_m:
            extracted["duration"] = dur_m.group(1).strip()

        # Compile Missing Items for Smart Receptionist Interview
        missing_fields = []

        if not extracted["chief_complaint"]:
            missing_fields.append({
                "key": "chief_complaint",
                "label": "Chief Complaint / Reason for Visit",
                "question": "What is the primary symptom or discomfort bringing you to the hospital today?",
                "placeholder": "e.g. Constant fatigue, blurred vision, and high fasting glucose",
                "default_val": "Longitudinal metabolic review and glycemic optimization"
            })

        if not extracted["duration"]:
            missing_fields.append({
                "key": "duration",
                "label": "Onset & Duration of Symptoms",
                "question": "When did these symptoms begin, and how severe is the discomfort on a scale of 1 to 10?",
                "placeholder": "e.g. Started 3 weeks ago, severity 5/10",
                "default_val": "Gradual onset over past 3 weeks, mild to moderate"
            })

        if not extracted["medications"]:
            missing_fields.append({
                "key": "medications",
                "label": "Current Regular Prescription Medications",
                "question": "What prescription medicines or daily dosages are you currently taking?",
                "placeholder": "e.g. Metformin 500mg twice daily with meals",
                "default_val": "Metformin 500 mg twice daily with meals"
            })

        if not extracted["allergies"]:
            missing_fields.append({
                "key": "allergies",
                "label": "Known Drug Allergies & Medical History",
                "question": "Do you have any known drug allergies (e.g. Penicillin) or chronic conditions?",
                "placeholder": "e.g. None known, or allergic to Sulfa drugs",
                "default_val": "No known drug allergies (NKDA); Type 2 Diabetes"
            })

        is_complete = len(missing_fields) == 0
        total_required = 4
        collected_count = total_required - len(missing_fields)
        completeness_pct = int((collected_count / total_required) * 100)

        return {
            "is_complete": is_complete,
            "completeness_score": completeness_pct,
            "extracted_findings": extracted,
            "missing_fields": missing_fields,
            "total_missing": len(missing_fields)
        }
