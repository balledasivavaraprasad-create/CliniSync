from typing import Any, Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc
import structlog

from app.models.investigation import Investigation
from app.models.document import Document

logger = structlog.get_logger(__name__)

class LabService:
    @staticmethod
    def get_latest_investigations(db: Session, patient_id: str) -> List[Dict[str, Any]]:
        """Returns the most recent reading for each canonical lab test."""
        invs = db.query(Investigation).filter(
            Investigation.patient_id == patient_id
        ).order_by(desc(Investigation.observed_date), desc(Investigation.created_at)).all()

        seen_tests = set()
        latest = []
        for i in invs:
            key = i.test_name_canonical
            if key not in seen_tests:
                seen_tests.add(key)
                latest.append({
                    "id": i.id,
                    "test_name": i.test_name_canonical,
                    "test_name_raw": i.test_name_raw,
                    "value_numeric": i.value_numeric,
                    "value_text": i.value_text,
                    "unit": i.unit,
                    "reference_low": i.reference_low,
                    "reference_high": i.reference_high,
                    "reference_text": i.reference_text,
                    "abnormal_flag": i.abnormal_flag,
                    "observed_date": i.observed_date.isoformat() if i.observed_date else None,
                    "confidence": i.confidence,
                    "source_document_id": i.source_document_id,
                    "group_key": i.group_key
                })
        return latest

    @staticmethod
    def get_investigation_trend(db: Session, patient_id: str, group_key: str) -> Dict[str, Any]:
        """
        Computes series, direction, delta, and non-causal description conforming to INV-6.
        """
        invs = db.query(Investigation).filter(
            Investigation.patient_id == patient_id,
            (Investigation.group_key == group_key) | (Investigation.test_name_canonical == group_key)
        ).order_by(asc(Investigation.observed_date), asc(Investigation.created_at)).all()

        if not invs:
            return {
                "test": group_key,
                "series": [],
                "direction": "stable",
                "delta": 0.0,
                "description": f"No recorded measurements for {group_key}."
            }

        series = []
        for i in invs:
            date_str = i.observed_date.strftime("%b %Y") if i.observed_date else "undated"
            series.append({
                "id": i.id,
                "value": i.value_numeric if i.value_numeric is not None else i.value_text,
                "unit": i.unit,
                "date": date_str,
                "abnormal_flag": i.abnormal_flag,
                "iso_date": i.observed_date.isoformat() if i.observed_date else None
            })

        # Calculate direction from numeric values
        num_vals = [s["value"] for s in series if isinstance(s["value"], (int, float))]
        direction = "stable"
        delta = 0.0

        if len(num_vals) >= 2:
            delta = round(num_vals[-1] - num_vals[0], 2)
            is_increasing = all(num_vals[idx] <= num_vals[idx+1] for idx in range(len(num_vals)-1))
            is_decreasing = all(num_vals[idx] >= num_vals[idx+1] for idx in range(len(num_vals)-1))

            if is_decreasing and delta < -0.1:
                direction = "down"
            elif is_increasing and delta > 0.1:
                direction = "up"
            else:
                direction = "mixed" if (max(num_vals) - min(num_vals) > 0.5) else "stable"

        # Construct non-causal descriptive sentence conforming to INV-6
        # Example: "HbA1c recorded 8.4% (Jan 2026), 8.0% (Apr 2026), 7.8% (Sep 2026): decreasing across three measurements."
        test_title = invs[0].test_name_canonical.replace("_", " ").title()
        measurements_str = ", ".join([f"{s['value']}{s['unit']} ({s['date']})" for s in series])
        
        dir_word = {
            "down": "decreasing",
            "up": "increasing",
            "stable": "stable",
            "mixed": "fluctuating"
        }.get(direction, "stable")

        count_words = {1: "single measurement", 2: "two measurements", 3: "three measurements", 4: "four measurements"}.get(len(series), f"{len(series)} measurements")
        description = f"{test_title} recorded {measurements_str}: {dir_word} across {count_words}."

        return {
            "test": invs[0].test_name_canonical,
            "unit": invs[0].unit,
            "series": series,
            "direction": direction,
            "delta": delta,
            "description": description,
            "latest_value": series[-1]["value"],
            "latest_flag": series[-1]["abnormal_flag"]
        }

lab_service = LabService()
