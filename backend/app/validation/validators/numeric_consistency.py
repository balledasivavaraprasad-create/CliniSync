from typing import Dict, Any, List, Tuple
import re

def check_numeric_consistency(
    generated_text: str,
    cited_fact_values: List[str]
) -> Tuple[bool, str, str]:
    """
    Verifies that numbers/dosages mentioned in output correspond to values in cited evidence facts.
    """
    # Extract numbers associated with units (e.g. 500 mg, 7.8 %)
    cited_combined = " ".join(cited_fact_values).lower()
    
    # Check for dosage patterns like "\d+ mg" in generated text
    gen_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(mg|mcg|g|ml|%)", generated_text.lower())
    for num_str, unit in gen_matches:
        full_mention = f"{num_str} {unit}"
        full_mention_compact = f"{num_str}{unit}"
        if full_mention not in cited_combined and full_mention_compact not in cited_combined:
            # Check if this exact number exists in cited values
            if num_str not in cited_combined:
                return False, "block", f"Numeric inconsistency: value '{num_str} {unit}' in output not found in cited evidence."

    return True, "info", "Numeric consistency verified"
