# API mismatches — plan C03 / §10

> §2: *"a table of every place where the existing backend contract differs from
> what the screens in §9 require … **Do not 'fix' mismatches by inventing a
> second contract.** Prefer adapting the Flutter models to the existing backend;
> add backend endpoints only for true gaps."*

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
| **M-01** | §6.6 rule 8 — `Demo data` tag when `meta.source == "fallback"` | `meta.source` is only ever `db`, `llm`, `system`, `stt`. The literal `"fallback"` is documented in `schemas/common.py:10` and assigned **nowhere**. The three places that genuinely fall back (`brief_service` template, `ocr_service` placeholder, `voice_service` placeholder) record it in *columns* (`briefs.generation_source`, page `method`, `voice_notes.stt_model`) that the API does not expose. | A tag keyed on `meta.source` would never render. | **Bundled fallback.** `ApiMeta.isFallback` still reads the field (correct, forward-compatible), but repositories tag a payload as demo data when they actually served a fixture from `assets/demo/`. DECISIONS.md FD-09. **Open (backend, cosmetic):** emit `meta.source="fallback"` in the three fall-back paths. |
| **M-02** | §6.6 rule 3 — medication conflicts must show **both** sources side by side | Two different shapes, both usable: `issues[].detail_json` carries `{drug, source_1: {doc, dose, freq}, source_2: {…}}` (structured, verified), while `brief.contradictions[]` has `issue_id`, `text` and an always-empty `sources: []`. | The Brief screen could only ever show a sentence, not source A vs source B. | **Resolved in app, both ways.** The Issues/review queue parses `detail_json.source_1/source_2` into two labelled columns and falls back to splitting the prose on `" vs "` when the detail block is absent (covered by tests). The Brief and Reconciliation screens fetch `GET /patients/{id}/medications/{canonical_name}/history` and render each recorded instruction as its own column, with no ordering implied. Verified on the demo conflict (1000 mg BD vs 500 mg BD). **Open (backend):** populate `contradictions[].sources`. |
| **M-03** | §9.11 Lab-trend chart | With no measurements the endpoint answers **200** with `series: []` and **omits** `unit`, `latest_value`, `latest_flag`. | Naive parsing would throw on null. | **Resolved in app.** `InvestigationTrend` makes those three nullable and the screen renders its own empty state. |
| **M-04** | §9.3 Overview header | `brief.patient` is `{id, name, age}` — `name`, not `full_name`; no `sex`, no DOB. `patient` in `/overview` is `{id, full_name, date_of_birth, age_years, sex, contact_ref, is_demo, last_activity_at, created_at}`. Two different shapes for the same concept in one payload. | Header would show a missing name/sex. | **Resolved in app.** The overview model reads `patient` and treats `latest_brief.patient` as decoration only. |
| **M-05** | §9.6 Reconciliation date range | Dates arrive in **five** different formats across the API: naive ISO (`2026-09-28T14:00:00`), tz-aware ISO (`2026-10-04T17:12:29+00:00`, brief `generated_at`), `%b %Y` (`Sep 2026`, brief trend labels), free text DOB (`1974-05-14` is fine but `patient.date_of_birth` is a *string*, not a date), and the literal `undated`. | Any single parser breaks somewhere. | **Resolved in app.** `AppDate.tryParse` accepts all of them and returns `null` (rendered as `—`, never as an invented date) otherwise. Covered by `test/models_test.dart`. |
| **M-06** | §9.12 Issues — acknowledge/dismiss an unknown id | `PATCH /issues/{unknown_id}` raises **HTTP 500 `INTERNAL_ERROR`**, not 404. | A stale id would look like a server fault. | **Resolved in app.** `IssueRepository.patch` maps `HTTP_ERROR`+500 to the "this item is no longer in the list" message and the list refreshes. **Open (backend):** return 404. |
| **M-07** | §9.6 medication history | `GET /patients/{id}/medications` **omits `group_key`**, even though the `medications` table has that column and `GET …/medications/{group_key}/history` needs one. The list returns `canonical_name` instead. | The app cannot ask "history of the medication the doctor tapped" without knowing the right key. | **Resolved in app.** The app navigates with `canonical_name` and the repository queries history by it. **Open (backend, additive):** include `group_key` in the list payload. |
| **M-08** | §9.14 Brief trend chart | The brief's `important_trends[].series` entries use the key **`val`**, while `GET /investigations/{group_key}/trend` uses `value`. Same product, two key names. | A shared trend model would silently render empty bars. | **Resolved in app.** `DoctorBrief` parses `val` explicitly and the chart binds to the parsed model; `InvestigationTrend` parses `value`. Documented at the model. |
| **M-09** | §9.13 Specialty picker | `GET /specialties` **works** (200, 7 rows) — verified. But `other` is labelled `Other Specialty` on the backend and `Other` in the app. | Cosmetic drift if the two lists are ever shown together. | **Resolved in app.** The catalogue is fetched (`SpecialtyRepository`); the bundled enum is only the offline mirror. **Open (backend, cosmetic):** align the label. |
| **M-10** | §9.13 specialty validation | `POST /brief` validates `specialty` against its own static list. | The app could offer a specialty the backend rejects. | **Resolved in app.** The picker is built from the endpoint, so that cannot happen; when the call fails the app falls back to the bundled mirror, which is a strict subset of the backend's rows. |
| **M-11** | §6.6 rule 2 — confidence bands | Band thresholds are computed server-side (`confidence_service`: ≥0.85 high, ≥0.60 medium, else needs_verification) and the payloads carry both `confidence` and `confidence_band`. Some payloads carry only one (e.g. `voice_notes.proposed_facts[]`, seeded rows). | A screen could not badge a value. | **Resolved in app.** `ConfidenceBand.fromJson` prefers the server band and computes only when absent, using the backend's own thresholds (`lib/core/utils/confidence_band.dart`). |
| **M-12** | §9.5 Document list | The list returns `original_filename`, `document_type`, `document_date`, `processing_status`, `classification_confidence`, `duplicate` — but **no `stored_path` and no page count per page**, so there is no client-side thumbnail. | No first-page preview without a download. | **Resolved in app.** `DocumentThumbnail` renders a typed document-glyph tile (prescription / lab / note / discharge / imaging / other), which is §6.5's stated fallback. The real preview would need `GET /documents/{id}/pages/{n}` per card. |
| **M-13** | §9.8 Processing screen | `GET /documents/{id}/status` exists and returns stage/status, but processing is **synchronous-ish `BackgroundTasks`** — no worker queue, so a long OCR/LLM run holds the request. | A poll can return the same stage for minutes. | **Resolved in app.** The Processing screen polls every 1.5 s as §9.5 requires, animates through the backend's *actual* stage names, and shows `processing_error_code` verbatim (mapped to human text, never a traceback). |
| **M-14** | §9.4 Evidence screen | `GET /facts/{id}/evidence` resolves a single fact; there is **no bulk evidence endpoint** and the brief's `evidence_shortcuts[].evidence_id` values from the **seeded** brief (`ev_001`–`ev_003`) are not real fact ids. | Deep links from a seeded brief would 404. | **Resolved in app.** Evidence is fetched per fact id and the screen shows "source not available for this item" instead of failing. **Open (backend):** seed real ids. |
| **M-15** | §9.15 Version history / approval | `PUT /consultations/{id}` and `POST /consultations/{id}/versions` both exist, but `approval` is `POST /consultations/{id}/approve` with the content in the **body** — there is no separate "approve by id" endpoint. | A naive "approve the latest" would need the content. | **Resolved in app.** The Approval screen always fetches the current version, sends it back with the approval, and shows the validation preview from `POST …/approve/preview` first. |
| **M-16** | §9.19 Voice | There is **no `GET /patients/{id}/voice`**; only `POST /patients/{id}/voice` (multipart), `POST /voice/transcribe`, `POST /voice/{id}/review`. | A "voice notes for this patient" list has no endpoint. | **Resolved in app.** The Voice screen does not offer a history list; it records, transcribes, reviews and stops. Nothing in §9.20 requires a list. |
| **M-17** | §9.6 / §9.7 | `GET /patients/{id}/timeline` performs **no patient-existence check**: an unknown patient id returns `[]` with 200. | "No timeline" and "no such patient" look identical. | **Resolved in app.** The router resolves the patient from the active-patient provider and the screens show their own empty state with the patient name in the title. **Open (backend):** 404 unknown ids. |
| **M-18** | §9.3 Overview readiness ring | `GET /patients/{id}/brief/latest` injects a hard-coded `readiness_score = 92` (`briefs.py:50`). It is not derived from anything. | Showing it as a "score" would be a fabricated metric. | **Resolved in app.** The ring is labelled from what it actually counts — verified memory items and review progress — not from `readiness_score`. The field is parsed and ignored, with a comment. **Open (backend):** derive or remove it. |
| **M-19** | §9.3 Overview | `brief.patient` has no `sex` and no `date_of_birth`, but the reference header (`52 yrs • Diabetology • Last seen 20 Sep`) needs both. | Header would have a hole. | **Resolved in app.** Age comes from `patient.age_years`; sex and last-seen come from `patient`; the specialty is whatever the doctor last chose. |
| **M-20** | §11.2 auth | `deps.get_current_user` is a **stub** returning `doc_001`; there is no `/auth` router at all, and `GET /documents/{id}/file` has no authorisation check. | No login UI can exist (and §0.2 rule 4 forbids one). | **Resolved in app.** No auth, no profile, no session screen; §0.2 rule 4. Recorded as a **known product gap**, not a frontend bug. |
| **M-21** | §11.3 error envelope | Errors are `{"success": false, "error": {code, message, details}, "meta": {…}}` — `details` is `{}` everywhere and no route emits a structured `field` map. | Field-level validation errors cannot be mapped to inputs. | **Resolved in app.** `ApiException.details` is parsed if present and otherwise empty; forms validate client-side and show the server message verbatim when it is doctor-facing. **Open (backend):** populate `details`. |
| **M-22** | §9.20 Voice | STT is **single-provider** (Groq Whisper) with no fallback chain, and `STT_PRIMARY`/`STT_FALLBACK_*` settings are never read. A failure raises 503. | The Voice screen would show a hard error. | **Resolved in app.** The repository maps 503 `LLM_UNAVAILABLE` to the §11.4 "we couldn't process the recording — record again or type instead" copy, and the screen offers a typed-note path. **Open (backend):** wire the configured fallbacks. |
| **M-23** | §9.7 Timeline | `timeline_events.related_fact_ids` and `contradictions.related_fact_ids` are **TEXT**, not JSON arrays, so a client cannot parse them without knowing the separator convention. | Fact cross-links would render as raw text. | **Resolved in app.** The app only renders `related_fact_ids` when it round-trips as a real list; otherwise the card simply omits the cross-link. **Open (backend):** return JSON arrays. |
| **M-24** | §6.5 no patient photos | The repo **does** ship three identifiable-human photographs (`assets/images/doctor_carter.jpg`, `avatar_willie.jpg`, `event_gamification.jpg`). None is a patient, and none is referenced by the Flutter app. | Risk of a future maintainer wiring one into a patient card. | **Resolved in app.** A component test asserts no `assets/images/*.jpg` reference exists anywhere under `lib/` other than the ambient stills. |

## Observations (backend, not blocking the app)

| # | Finding |
|---|---|
| O-01 | No migration tooling and **no `Base.metadata.create_all(...)` anywhere in project code** — the tables in the committed `clinsync.db` were created out-of-band, so a fresh clone cannot serve a request until the schema is created. |
| O-02 | `contradiction_service.recompute` filters `Document.id == patient_id` where it means `Document.patient_id == patient_id`, so the future-date contradiction rule never fires. |
| O-03 | `seed.py` CLI calls `seed_demo_data(reset=args.reset or True)` — `--reset` is always true. |
| O-04 | The **seeded** brief's `evidence_shortcuts` reference `ev_001`–`ev_003`, which are not real fact ids (a freshly generated brief returns real ones). |
| O-05 | `clinical_facts.source_span_end` is never populated; only `source_span_start`. Evidence highlights can therefore only span to end-of-span. |
| O-06 | `validation/policies.yaml` and `validation/validators/prompt_injection_check.py` exist but are never read; `ai/fallbacks/` is an empty package. |
| O-07 | Settings `STT_PRIMARY`, `STT_FALLBACK_1`, `STT_FALLBACK_2`, `DEMO_FALLBACKS_ENABLED`, `GATE1_MIN_FACT_CONFIDENCE` are declared and never read. |
| O-08 | `GET /health` is mounted twice (bare and under `/api/v1`) — harmless, but the bare mount is why `/health` also answers 200. |
| O-09 | `investigation.trend` returns `series[].iso_date` while the brief's trend labels return `%b %Y`; two date formats for the same concept. |
| O-10 | `contradictions[].sources` is declared in the payload but always `[]` (see M-02). |

## Contract decisions worth stating explicitly

1. **No second contract was invented.** Every Flutter model parses the backend's
   own field names. Where the backend is internally inconsistent (M-04, M-08,
   M-09) the *model* handles both spellings; no endpoint was renamed and no
   response was reshaped client-side.
2. **No backend file was modified** by this frontend work, per §4.
3. **Tolerant parsing everywhere** (§8): a missing field yields `null` and a
   sensible screen, never an exception and never an invented value.
4. **Nothing is silently dropped.** Where the app could not show something the
   plan asks for (M-12 thumbnails, M-16 voice history), the screen states what it
   does not have instead of faking it.
