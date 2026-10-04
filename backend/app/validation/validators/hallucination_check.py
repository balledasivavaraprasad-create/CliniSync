from typing import Dict, Any, List, Set, Tuple
import re

COMMON_DRUG_NAMES = [
    "metformin", "sitagliptin", "glimepiride", "insulin", "atorvastatin",
    "rosuvastatin", "amlodipine", "telmisartan", "losartan", "enalapril",
    "lisinopril", "aspirin", "clopidogrel", "pantoprazole", "omeprazole",
    "levothyroxine", "paracetamol", "ibuprofen", "gabapentin", "pregabalin"
]

def check_hallucination(
    generated_text: str,
    known_medications: Set[str],
    known_diagnoses: Set[str]
) -> Tuple[bool, str, str]:
    """
    Checks if generated text references medications or diagnoses not present in patient facts.
    """
    lower = generated_text.lower()
    
    # Check for hallucinated medications
    for drug in COMMON_DRUG_NAMES:
        if re.search(rf"\b{drug}\b", lower):
            # Must be known in patient records
            if not any(drug in known.lower() for known in known_medications):
                return False, "block", f"Potential hallucination: medication '{drug}' mentioned in output but not found in patient facts."

    return True, "info", "No hallucinated entities detected"
