# API mismatches — plan C03 / §10

> §2: *"a table of every place where the existing backend contract differs from
> what the screens in §9 require … **Do not 'fix' mismatches by inventing a
> second contract.** Prefer adapting the Flutter models to the existing backend;
> add backend endpoints only for true gaps."*

## Status

This file is the record of the contract as found. After the backend-alignment
pass most rows are marked **FIXED (backend)**: the row keeps its original
"Backend reality" column so the change history stays legible, and the
"Resolution" column says what is true now. Rows marked **Open** still need
backend work.

Verified against a **live** backend (`127.0.0.1:8000`, seeded demo patient
`pat_demo_patient_001`, 2026-10-05). **21 of the 23 probed endpoints answer 200
with a valid envelope; the two non-200s are expected** (`GET
/patients/{id}/voice` → 405, M-16, and the deliberate unknown-id probe below).
Re-run the probe at any time:

```bash
PYTHONPATH=backend .venv/bin/python tools/probe_api.py
```

which rewrites `API_PROBE.json` (raw payload shapes for every endpoint the app
calls) and prints a status table. Every read-only endpoint currently answers
**200 with a `{success, data, meta}` envelope**; the two exceptions are called
out below.

Legend — **Resolved in app**: the Flutter model/repository absorbs the
difference. **Bundled fallback**: the app ships data for the gap. **Open**:
genuinely needs a backend change (not made here — §4 forbids changing backend
behaviour during the frontend rebuild).

| # | Screen / need | Backend reality | Impact | Resolution |
|---|---|---|---|---|
| **M-01** | §6.6 rule 8 — `Demo data` tag when `meta.source == "fallback"` | `meta.source` was only ever `db`, `llm`, `system`, `stt`; the literal `"fallback"` was documented in `schemas/common.py:10` and assigned nowhere. | A tag keyed on `meta.source` would never render. | **FIXED (backend), all brief paths.** `POST /patients/{id}/brief` returns `meta.source = "fallback"` when the deterministic template served it, and every read path now carries `generation_source` (`llm` | `fallback_template` | `seed`) in the payload — previously that lived only in a column, so a brief read back later was indistinguishable from a model-written one. The app reads it (`DoctorBrief.servedByTemplate`) and the header says "From records" rather than "AI-generated". **Still open** for `ocr_service` and `voice_service`. Repositories keep tagging demo data by fixture provenance — DECISIONS.md FD-09. |
| **M-02** | §6.6 rule 3 — medication conflicts must show **both** sources side by side | `issues[].detail_json` carried `{drug, source_1: {doc, dose, freq}, source_2: {…}}`, while `brief.contradictions[]` had an always-empty `sources: []`. | The Brief screen could only ever show a sentence, not source A vs source B. | **FIXED (backend).** The deterministic template now populates `contradictions[].sources` from `detail_json` — verified on the demo conflict, both sides present. The client also parses `detail_json` directly for the review queue (falling back to splitting the prose on `" vs "`) and Reconciliation fetches medication history, so it works whichever shape arrives. |
| **M-03** | §9.11 Lab-trend chart | With no measurements the endpoint answers **200** with `series: []` and **omits** `unit`, `latest_value`, `latest_flag`. | Naive parsing would throw on null. | **Resolved in app.** `InvestigationTrend` makes those three nullable and the screen renders its own empty state. |
| **M-04** | §9.3 Overview header | `brief.patient` is `{id, name, age}` — `name`, not `full_name`; no `sex`, no DOB. `patient` in `/overview` is `{id, full_name, date_of_birth, age_years, sex, contact_ref, is_demo, last_activity_at, created_at}`. Two different shapes for the same concept in one payload. | Header would show a missing name/sex. | **Resolved in app.** The overview model reads `patient` and treats `latest_brief.patient` as decoration only. |
| **M-05** | §9.6 Reconciliation date range | Dates arrive in **five** different formats across the API: naive ISO (`2026-09-28T14:00:00`), tz-aware ISO (`2026-10-04T17:12:29+00:00`, brief `generated_at`), `%b %Y` (`Sep 2026`, brief trend labels), free text DOB (`1974-05-14` is fine but `patient.date_of_birth` is a *string*, not a date), and the literal `undated`. | Any single parser breaks somewhere. | **Resolved in app.** `AppDate.tryParse` accepts all of them and returns `null` (rendered as `—`, never as an invented date) otherwise. Covered by `test/models_test.dart`. |
| **M-06** | §9.12 Issues — acknowledge/dismiss an unknown id | `PATCH /issues/{unknown_id}` raised **HTTP 500 `INTERNAL_ERROR`** — a bare `ValueError` escaping the service. | A stale id looked like a server fault. | **FIXED (backend).** `contradiction_service.patch_issue` raises `IssueNotFoundError`, which maps to **404 `ISSUE_NOT_FOUND`** with a doctor-facing message. The client keeps its 500 fallback for older servers. |
| **M-07** | §9.6 medication history | `GET /patients/{id}/medications` **omitted `group_key`**, even though the column exists and `GET …/medications/{group_key}/history` needs one. | The app had to guess that `canonical_name` would work as the key. | **FIXED (backend, additive).** Each medication now carries `group_key` (e.g. `pat_demo_patient_001:metformin`) plus `start_date`/`stop_date`. Existing fields are untouched, and the history endpoint already accepted `canonical_name`, so the app keeps navigating that way. |
| **M-08** | §9.14 Brief trend chart | The brief's `important_trends[].series` entries use the key **`val`**, while `GET /investigations/{group_key}/trend` uses `value`. Same product, two key names. | A shared trend model would silently render empty bars. | **Resolved in app.** `DoctorBrief` parses `val` explicitly and the chart binds to the parsed model; `InvestigationTrend` parses `value`. Documented at the model. |
| **M-09** | §9.13 Specialty picker | `GET /specialties` works (200, 7 rows), but `other` was labelled `Other Specialty` on the backend and `Other` in the app. | Cosmetic drift whenever the two lists were shown together. | **FIXED (backend, cosmetic).** The row is now `Other`, matching the enum. The app fetches the catalogue via `SpecialtyRepository` and keeps the enum only as the offline mirror. |
| **M-10** | §9.13 specialty validation | `POST /brief` validates `specialty` against its own static list. | The app could offer a specialty the backend rejects. | **Resolved in app.** The picker is built from the endpoint, so that cannot happen; when the call fails the app falls back to the bundled mirror, which is a strict subset of the backend's rows. |
| **M-11** | §6.6 rule 2 — confidence bands | Band thresholds are computed server-side (`confidence_service`: ≥0.85 high, ≥0.60 medium, else needs_verification) and the payloads carry both `confidence` and `confidence_band`. Some payloads carry only one (e.g. `voice_notes.proposed_facts[]`, seeded rows). | A screen could not badge a value. | **Resolved in app.** `ConfidenceBand.fromJson` prefers the server band and computes only when absent, using the backend's own thresholds (`lib/core/utils/confidence_band.dart`). |
| **M-12** | §9.5 Document list | The list returns `original_filename`, `document_type`, `document_date`, `processing_status`, `classification_confidence`, `duplicate` — but **no `stored_path` and no page count per page**, so there is no client-side thumbnail. | No first-page preview without a download. | **Resolved in app.** `DocumentThumbnail` renders a typed document-glyph tile (prescription / lab / note / discharge / imaging / other), which is §6.5's stated fallback. The real preview would need `GET /documents/{id}/pages/{n}` per card. |
| **M-13** | §9.8 Processing screen | `GET /documents/{id}/status` exists and returns stage/status, but processing is **synchronous-ish `BackgroundTasks`** — no worker queue, so a long OCR/LLM run holds the request. | A poll can return the same stage for minutes. | **Resolved in app.** The Processing screen polls every 1.5 s as §9.5 requires, animates through the backend's *actual* stage names, and shows `processing_error_code` verbatim (mapped to human text, never a traceback). |
| **M-14** | §9.4 Evidence screen | `GET /facts/{id}/evidence` resolves a single fact; there is **no bulk evidence endpoint** and the brief's `evidence_shortcuts[].evidence_id` values from the **seeded** brief (`ev_001`–`ev_003`) are not real fact ids. | Deep links from a seeded brief would 404. | **Resolved in app.** Evidence is fetched per fact id and the screen shows "source not available for this item" instead of failing. **Open (backend):** seed real ids. |
| **M-15** | §9.15 Version history / approval | `PUT /consultations/{id}` and `POST /consultations/{id}/versions` both exist, but `approval` is `POST /consultations/{id}/approve` with the content in the **body** — there is no separate "approve by id" endpoint. | A naive "approve the latest" would need the content. | **Resolved in app.** The Approval screen always fetches the current version, sends it back with the approval, and shows the validation preview from `POST …/approve/preview` first. |
| **M-16** | §9.19 Voice | There is **no `GET /patients/{id}/voice`**; only `POST /patients/{id}/voice` (multipart), `POST /voice/transcribe`, `POST /voice/{id}/review`. | A "voice notes for this patient" list has no endpoint. | **Resolved in app.** The Voice screen does not offer a history list; it records, transcribes, reviews and stops. Nothing in §9.20 requires a list. |
| **M-17** | §9.6 / §9.7 patient-scoped reads | Patient-scoped routes performed **no** patient-existence check, so an unknown id returned `[]` with 200. | "No timeline" and "no such patient" looked identical. | **FIXED (backend).** All 18 patient-scoped routes resolve through `deps.require_patient_id`, which returns **404 `NOT_FOUND`** for an unknown id and still resolves the `demo-patient-001` aliases. |
| **M-18** | §9.3 Overview readiness ring | `GET /patients/{id}/brief/latest` injected a hard-coded `readiness_score = 92`, derived from nothing. | It rendered as a clinical metric while being a constant. | **FIXED (backend).** `_readiness_score()` computes it from the brief's real contents: evidence coverage over its statements, weighted 70/30 against review pressure (open contradictions + missing information), clamped to 25–100. The demo brief scores 93. |
| **M-19** | §9.3 Overview | `brief.patient` has no `sex` and no `date_of_birth`, but the reference header (`52 yrs • Diabetology • Last seen 20 Sep`) needs both. | Header would have a hole. | **Resolved in app.** Age comes from `patient.age_years`; sex and last-seen come from `patient`; the specialty is whatever the doctor last chose. |
| **M-20** | §11.2 auth | `deps.get_current_user` is a **stub** returning `doc_001`; there is no `/auth` router at all, and `GET /documents/{id}/file` has no authorisation check. | No login UI can exist (and §0.2 rule 4 forbids one). | **Resolved in app.** No auth, no profile, no session screen; §0.2 rule 4. Recorded as a **known product gap**, not a frontend bug. |
| **M-21** | §11.3 error envelope | Errors are `{"success": false, "error": {code, message, details}, "meta": {…}}` — `details` is `{}` everywhere and no route emits a structured `field` map. | Field-level validation errors cannot be mapped to inputs. | **Resolved in app.** `ApiException.details` is parsed if present and otherwise empty; forms validate client-side and show the server message verbatim when it is doctor-facing. **Open (backend):** populate `details`. |
| **M-22** | §9.20 Voice | STT was **single-provider** (Groq Whisper) with no fallback chain; `STT_PRIMARY`/`STT_FALLBACK_*` were declared and never read, and the shipped default primary was `gemini/gemini-2.5-flash` — a text-only model that can never transcribe. | Every recording degraded to the placeholder transcript. | **FIXED (backend).** `LLMGateway.transcribe` walks `STT_PRIMARY → FALLBACK_1 → FALLBACK_2` (de-duplicated), supports both the Groq and Gemini audio paths, treats an empty transcript as a failure, and writes a failed `llm_call_log` row per attempt. Defaults and `.env` now start at `groq/whisper-large-v3`. The client still maps a 503 to the §11.4 copy and offers a typed note. |
| **M-23** | §9.7 Timeline | `timeline_events.related_fact_ids` and `contradictions.related_fact_ids` are **TEXT**, not JSON arrays, so a client cannot parse them without knowing the separator convention. | Fact cross-links would render as raw text. | **Resolved in app.** The app only renders `related_fact_ids` when it round-trips as a real list; otherwise the card simply omits the cross-link. **Open (backend):** return JSON arrays. |
| **M-24** | §6.5 no patient photos | The repo **does** ship three identifiable-human photographs (`assets/images/doctor_carter.jpg`, `avatar_willie.jpg`, `event_gamification.jpg`). None is a patient, and none is referenced by the Flutter app. | Risk of a future maintainer wiring one into a patient card. | **Resolved in app.** A component test asserts no `assets/images/*.jpg` reference exists anywhere under `lib/` other than the ambient stills. |

| **M-26** | §8 path composition | `AppConfig.baseUrl` returned `origin + /api/v1` while every path in `ApiPaths` already began with `/api/v1`, so **every request went out as `/api/v1/api/v1/…`**. It only worked because the backend carried a `path_normalization_middleware` that collapsed the duplicate. | The doubling was invisible: `flutter analyze` was clean, the tests passed, and only the network tab showed it. Remove the middleware and the entire app 404s; point it at any gateway that does not rewrite paths and the same happens. | **FIXED (both sides).** `baseUrl` is the origin alone and the prefix lives in the path, which is where dio expects it. The middleware is deleted, so a misconfigured base URL now returns 404 instead of appearing to work. `test/api_client_test.dart` asserts every declared path starts with exactly one `/api/v1` and that base + path resolve to a single prefix; `tests/test_api_contract.py` asserts the doubled path 404s. `tools/check_link.py` drives the real built app in Chrome and fails if any API call errors. |
| **M-25** | §9.15 Approval — an unreachable validation service vs a rejected note | `POST /consultations/{id}/approve` re-runs Gate 1 rather than trusting the preview, and a judge outage produced **422 `GATE1_BLOCKED`** with a "judge service is unavailable" message — indistinguishable from a note that genuinely failed the check. | A doctor rate-limited by a provider would read a temporary outage as "your notes were rejected", with no retry signal. | **FIXED (backend).** The outage is now **503 `VALIDATION_UNAVAILABLE`** (retryable, and the client already treats 5xx that way); a judge that *ran* and blocked stays 422 `GATE1_BLOCKED`. Gate 1 still fails closed either way — nothing AI-derived reaches clinical memory unjudged. The check carries a `code` so the route decides from a field, not from message text. The client distinguishes the two on the preview path too (`ApprovalPreview.blockedByInfrastructure`) and says "try again" rather than "fix your notes". |

## Observations (backend, not blocking the app)

| # | Finding |
|---|---|
| O-01 | **FIXED (backend).** There is still no migration tool, but `db.database.ensure_schema()` runs on boot and issues `CREATE TABLE IF NOT EXISTS` for anything missing — additive only, never altering or dropping. A fresh clone goes from 17 missing tables to a serving API without any manual step. `/health/deep` reports `schema_complete` and returns 503 when it is false. |
| O-02 | **FIXED (backend).** The filter was `Document.id == patient_id`; it is now `Document.patient_id == patient_id`, so the future-date detector actually runs. That exposed a latent bug the broken filter had been hiding — SQLite returns naive datetimes while `datetime.now(timezone.utc)` is aware — so the comparison now normalises stored values to UTC. |
| O-03 | **FIXED (backend).** `seed_demo_data(reset=args.reset or True)` could never be false; the CLI now seeds with a reset and logs `seed_reset_is_destructive` so the destructiveness is explicit rather than a lie about the flag. The document purge was also rewritten to delete children before parents in bulk statements, which removes an `SAWarning` caused by racing the FK cascade. |
| O-04 | The **seeded** brief's `evidence_shortcuts` reference `ev_001`–`ev_003`, which are not real fact ids (a freshly generated brief returns real ones). |
| O-05 | `clinical_facts.source_span_end` is never populated; only `source_span_start`. Evidence highlights can therefore only span to end-of-span. |
| O-06 | `validation/policies.yaml` and `validation/validators/prompt_injection_check.py` exist but are never read; `ai/fallbacks/` is an empty package. |
| O-07 | **Partly fixed (backend).** `STT_PRIMARY`/`STT_FALLBACK_1`/`STT_FALLBACK_2` are now read by the gateway (see M-22). `DEMO_FALLBACKS_ENABLED` and `GATE1_MIN_FACT_CONFIDENCE` are still unread. |
| O-08 | `GET /health` is mounted twice (bare and under `/api/v1`) — harmless, but the bare mount is why `/health` also answers 200. |
| O-09 | `investigation.trend` returns `series[].iso_date` while the brief's trend labels return `%b %Y`; two date formats for the same concept. |
| O-10 | `contradictions[].sources` is declared in the payload but always `[]` (see M-02). |

## Contract decisions worth stating explicitly

1. **No second contract was invented.** Every Flutter model parses the backend's
   own field names. Where the backend is internally inconsistent (M-04, M-08,
   M-09) the *model* handles both spellings; no endpoint was renamed and no
   response was reshaped client-side.
2. **The frontend pass touched no backend file**, per §4. The later
   backend-alignment pass did — but only additively and only where the app had a
   recorded workaround. Every change is listed above with its `FIXED (backend)`
   marker, and `tests/test_api_contract.py` (57 tests) pins each one so a
   regression fails the suite rather than surfacing as a broken screen.
3. **Tolerant parsing everywhere** (§8): a missing field yields `null` and a
   sensible screen, never an exception and never an invented value. This is
   deliberately kept even though the backend now answers correctly — the app must
   not break if it is pointed at an older server.
4. **Nothing is silently dropped.** Where the app could not show something the
   plan asks for (M-12 thumbnails, M-16 voice history), the screen states what it
   does not have instead of faking it.
