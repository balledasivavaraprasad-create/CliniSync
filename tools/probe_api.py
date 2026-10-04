"""Probe every backend endpoint the Flutter app uses and record what it returns.

This is the evidence behind `docs/frontend/API_MISMATCHES.md`. It performs no
writes to clinical data except the two idempotent POSTs the app itself makes when
generating a brief (`POST /patients/{id}/brief`) and recomputing issues
(`POST /patients/{id}/issues/recompute`) — both are safe to repeat on demo data.

Usage:
    PYTHONPATH=backend .venv/bin/python tools/probe_api.py
    PYTHONPATH=backend .venv/bin/python tools/probe_api.py --base http://127.0.0.1:8000

Output: stdout markdown table + `docs/frontend/API_PROBE.json` with the raw
shapes, so the mismatch table can be re-verified after any backend change.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
PATIENT = 'pat_demo_patient_001'

# (label, method, path, body) — mirrors lib/core/constants/api_paths.dart
CALLS: list[tuple[str, str, str, dict | None]] = [
    ('health', 'GET', '/api/v1/health', None),
    ('healthDeep', 'GET', '/api/v1/health/deep', None),
    ('patients.list', 'GET', '/api/v1/patients', None),
    ('patients.get', 'GET', f'/api/v1/patients/{PATIENT}', None),
    ('patients.overview', 'GET', f'/api/v1/patients/{PATIENT}/overview', None),
    ('patients.audit', 'GET', f'/api/v1/patients/{PATIENT}/audit', None),
    ('patients.memory', 'GET', f'/api/v1/patients/{PATIENT}/memory', None),
    ('patients.memoryHistory', 'GET', f'/api/v1/patients/{PATIENT}/memory/history', None),
    ('documents.list', 'GET', f'/api/v1/patients/{PATIENT}/documents', None),
    ('facts.list', 'GET', f'/api/v1/patients/{PATIENT}/facts', None),
    ('timeline.list', 'GET', f'/api/v1/patients/{PATIENT}/timeline', None),
    ('medications.list', 'GET', f'/api/v1/patients/{PATIENT}/medications', None),
    ('medications.history',
     'GET', f'/api/v1/patients/{PATIENT}/medications/metformin/history', None),
    ('investigations.list', 'GET', f'/api/v1/patients/{PATIENT}/investigations', None),
    ('investigations.trend',
     'GET', f'/api/v1/patients/{PATIENT}/investigations/{PATIENT}:hba1c/trend', None),
    ('investigations.trendEmpty',
     'GET', f'/api/v1/patients/{PATIENT}/investigations/{PATIENT}:unknown/trend', None),
    ('issues.list', 'GET', f'/api/v1/patients/{PATIENT}/issues', None),
    ('brief.latest', 'GET', f'/api/v1/patients/{PATIENT}/brief/latest', None),
    ('consultations.list', 'GET', f'/api/v1/patients/{PATIENT}/consultations', None),
    ('specialties.list', 'GET', '/api/v1/specialties', None),
    # No `GET /patients/{id}/voice` exists on the backend — only the three
    # POSTs (see API_MISMATCHES.md M-16). Probed as a 405 so the absence is
    # on the record rather than an oversight in this script.
    ('voice.list (expect 405)', 'GET', f'/api/v1/patients/{PATIENT}/voice', None),
    # Mutating / creation endpoints exercised read-only where possible.
    ('issues.recompute', 'POST', f'/api/v1/patients/{PATIENT}/issues/recompute', {}),
    ('brief.generate', 'POST', f'/api/v1/patients/{PATIENT}/brief',
     {'specialty': 'general_medicine'}),
]


def call(base: str, method: str, path: str, body: dict | None) -> dict:
    url = f'{base.rstrip("/")}{path}'
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Accept', 'application/json')
    if data is not None:
        req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return {'status': resp.status, 'payload': json.loads(resp.read() or b'{}')}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw or b'{}')
        except json.JSONDecodeError:
            payload = {'_raw': raw[:200].decode('utf-8', 'replace')}
        return {'status': exc.code, 'payload': payload}
    except Exception as exc:  # noqa: BLE001 - diagnostic tool
        return {'status': 0, 'payload': {'_error': f'{type(exc).__name__}: {exc}'}}


def shape(value: object, depth: int = 0) -> object:
    """Reduce a payload to its shape: keys of objects, types of list members."""
    if isinstance(value, dict):
        if depth >= 3:
            return '…'
        return {k: shape(v, depth + 1) for k, v in list(value.items())[:40]}
    if isinstance(value, list):
        if not value:
            return '[]'
        return [shape(value[0], depth + 1), f'×{len(value)}']
    return type(value).__name__


def sources(payload: object) -> list[str]:
    """Every distinct meta.source observed anywhere in the payload."""
    found: set[str] = set()

    def walk(node: object, key: str | None = None) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k == 'source' and isinstance(v, str):
                    found.add(v)
                walk(v, k)
        elif isinstance(node, list):
            for item in node[:50]:
                walk(item, key)

    walk(payload)
    return sorted(found)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://127.0.0.1:8000')
    ap.add_argument('--out', default=str(ROOT / 'docs/frontend/API_PROBE.json'))
    args = ap.parse_args()

    results: dict[str, dict] = {}
    print(f'# ClinSync API probe — {dt.datetime.now(dt.UTC).isoformat(timespec="seconds")}\n')
    print(f'Base: `{args.base}` · patient: `{PATIENT}`\n')
    print('| Endpoint | Method | Status | `success` | `meta.source` | Envelope keys |')
    print('|---|---|---|---|---|---|')
    for label, method, path, body in CALLS:
        res = call(args.base, method, path, body)
        payload = res['payload']
        success = payload.get('success') if isinstance(payload, dict) else None
        meta = payload.get('meta') if isinstance(payload, dict) else None
        src = (meta or {}).get('source') if isinstance(meta, dict) else None
        keys = ','.join(payload.keys()) if isinstance(payload, dict) else '(non-json)'
        results[label] = {
            'method': method,
            'path': path,
            'body': body,
            'status': res['status'],
            'envelope_keys': list(payload.keys()) if isinstance(payload, dict) else None,
            'success': success,
            'meta': meta,
            'all_sources': sources(payload),
            'error_code': (payload.get('error') or {}).get('code')
            if isinstance(payload, dict) and isinstance(payload.get('error'), dict)
            else None,
            'shape': shape(payload.get('data') if isinstance(payload, dict) else payload),
        }
        print(f'| `{label}` | {method} | {res["status"]} | {success} | '
              f'{src or "—"} | `{keys}` |')

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, default=str) + '\n')
    print(f'\nShapes written to `{out.relative_to(ROOT)}`')


if __name__ == '__main__':
    main()
