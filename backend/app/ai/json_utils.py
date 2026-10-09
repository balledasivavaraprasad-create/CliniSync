import json
import re
from typing import Any, Dict, Optional


def extract_json_str(text: str) -> str:
    """Extract raw JSON string from LLM response which might have markdown fences or extra text."""
    clean = text.strip()

    # Look for fenced markdown blocks
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", clean)
    if match:
        clean = match.group(1).strip()

    # If it starts with '{' and ends with '}', locate the outermost pair
    start = clean.find("{")
    end = clean.rfind("}")
    if start != -1 and end != -1 and end > start:
        return clean[start : end + 1]

    # Array case
    start_arr = clean.find("[")
    end_arr = clean.rfind("]")
    if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
        return clean[start_arr : end_arr + 1]

    return clean


def repair_and_parse_json(text: str) -> Dict[str, Any]:
    """Attempt robust parsing with common syntax fixups."""
    raw = extract_json_str(text)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Common fix 1: remove trailing commas before closing braces/brackets
        fixed = re.sub(r",\s*([\]}])", r"\1", raw)
        try:
            return json.loads(fixed)
        except json.JSONDecodeError:
            # Common fix 2: balance braces
            open_curlies = fixed.count("{") - fixed.count("}")
            if open_curlies > 0:
                fixed += "}" * open_curlies
            return json.loads(fixed)
