#!/usr/bin/env python3
"""Capture live ClinSync API responses as JSON fixtures.

Real responses feed `test/fixtures/` (unit tests, plan C12) and
`assets/demo/` (offline Demo mode, plan §14 fallback tier 4).

Usage:  .venv/bin/python tools/capture_fixtures.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
PREFIX = "/api/v1"
PATIENT = "pat_demo_patient_001"
DOCUMENT = "doc_demo_005_rx_sep"
FACT = "fact_e013b241a11043b9"

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "test" / "fixtures"
DEMO = ROOT / "assets" / "demo"

# name -> (method, path, body)
TARGETS = [
    ("patients_list", "GET", f"/patients?limit=6", None),
    ("patient", "GET", f"/patients/{PATIENT}", None),
    ("patient_overview", "GET", f"/patients/{PATIENT}/overview", None),
    ("documents", "GET", f"/patients/{PATIENT}/documents", None),
    ("timeline", "GET", f"/patients/{PATIENT}/timeline", None),
    ("medications", "GET", f"/patients/{PATIENT}/medications", None),
    ("medication_history", "GET", f"/patients/{PATIENT}/medications/metformin/history", None),
    ("investigations", "GET", f"/patients/{PATIENT}/investigations", None),
    ("investigation_trend", "GET",
     f"/patients/{PATIENT}/investigations/{PATIENT}:hba1c/trend", None),
    ("issues", "GET", f"/patients/{PATIENT}/issues", None),
    ("facts", "GET", f"/patients/{PATIENT}/facts", None),
    ("memory", "GET", f"/patients/{PATIENT}/memory", None),
    ("memory_history", "GET", f"/patients/{PATIENT}/memory/history", None),
    ("brief_latest", "GET", f"/patients/{PATIENT}/brief/latest", None),
    ("document_status", "GET", f"/documents/{DOCUMENT}/status", None),
    ("fact_evidence", "GET", f"/facts/{FACT}/evidence", None),
]

# Fixtures that also ship inside the app bundle for offline Demo mode.
DEMO_COPIES = {
    "patients_list": "patients",
    "patient_overview": "overview",
    "documents": "documents",
    "timeline": "timeline",
    "medications": "medications",
    "medication_history": "medication_history",
    "investigations": "investigations",
    "investigation_trend": "trend_hba1c",
    "issues": "issues",
    "facts": "facts",
    "memory": "memory",
    "brief_latest": "brief",
    "document_status": "document_status",
    "fact_evidence": "evidence",
}


def request(method: str, path: str, body: dict | None) -> tuple[int, bytes]:
    url = BASE + (PREFIX + path if path.startswith("/") else path)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()
    except Exception as exc:  # noqa: BLE001
        print(f"  ! {method} {path}: {exc}", file=sys.stderr)
        return 0, b""


def write(path: pathlib.Path, raw: bytes, *, demo: bool = False) -> int:
    """Write a fixture.

    Bundled demo copies are tagged ``meta.source = "fallback"`` so the app can
    label them "Demo data" (plan §6.6 rule 8) — the backend never emits it.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if demo:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
            meta["source"] = "fallback"
            meta["request_id"] = "req_demo_bundle"
            payload["meta"] = meta
            raw = (json.dumps(payload, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return len(raw)


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    DEMO.mkdir(parents=True, exist_ok=True)

    consultation_id = None
    status, raw = request("POST", f"/patients/{PATIENT}/consultations",
                          {"specialty": "diabetology"})
    if status < 300:
        consultation_id = json.loads(raw)["data"]["id"]

    targets = list(TARGETS)
    if consultation_id:
        targets += [
            ("consultation", "GET", f"/consultations/{consultation_id}", None),
            ("consultation_versions", "GET", f"/consultations/{consultation_id}/versions", None),
            ("approve_preview", "POST", f"/consultations/{consultation_id}/approve/preview", {}),
        ]

    failures = 0
    for name, method, path, body in targets:
        status, raw = request(method, path, body)
        if status >= 300 or not raw:
            print(f"  ✗ {name:<24} HTTP {status}")
            failures += 1
            continue
        n = write(FIXTURES / f"{name}.json", raw)
        note = ""
        if name in DEMO_COPIES:
            m = write(DEMO / f"{DEMO_COPIES[name]}.json", raw, demo=True)
            note = f"  -> assets/demo ({m} B)"
        print(f"  ✓ {name:<24} {n} B{note}")

    print(f"\n{len(targets) - failures}/{len(targets)} captured.")
    if consultation_id:
        print(f"consultation_id={consultation_id}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
