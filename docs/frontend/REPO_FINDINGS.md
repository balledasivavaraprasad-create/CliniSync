# Repository findings — plan C01 / §2

> §2: *"Only record what you see. Use **ABSENT** when something does not exist."*

Recorded on the state of the repo at the start of the frontend rebuild. Where a
statement is an inference rather than a reading, it is marked *(inferred)*.

---

## 1. Flutter project root, SDK, platforms

| Item | Value |
|---|---|
| Project root | repository root (`pubspec.yaml` at the same level as `backend/`) |
| Flutter | **3.47.6** stable · Dart **3.13.5** · `macos_arm64` |
| `pubspec.yaml` `name` | `clinicsync` |
| SDK constraint | `>=3.0.0 <4.0.0` |
| Platforms present | `android/`, `macos/`, `web/` — **`ios/` ABSENT** (added during this work, see `DECISIONS.md` FD-13) |
| Publish | `publish_to: "none"` |

Dependencies as shipped before the rebuild:

| Purpose | Package |
|---|---|
| state | `flutter_riverpod ^2.5.1` |
| routing | `go_router ^14.2.7` |
| http | `dio ^5.4.3+1`, `http ^1.6.0` |
| capture | `image_picker ^1.1.2`, `file_picker ^8.1.2`, `record ^5.1.2`, `permission_handler ^11.3.0` |
| media | `video_player ^2.8.7` |
| charts | `fl_chart ^0.68.0` |
| storage | `shared_preferences ^2.3.2`, `path_provider ^2.1.6` |
| fonts / icons | `google_fonts ^8.2.1`, `lucide_icons_flutter ^3.1.21` (replaced the unusable `lucide_icons`, FD-01) |
| utils | `intl ^0.19.0` |

Dev: `flutter_test`, `flutter_lints ^5.0.0`.

## 2. Existing screens

The previous frontend was **never tracked in git** — `git ls-files` before this
work returned 14 paths (`index.html`, `readme.md`, `assets/css/style.css`,
`assets/js/main.js`, the four `assets/video/*.mp4` + posters, and the two
`*NoWatermark.mp4` files). The Flutter sources existed only on disk, so there is
**no git history for them and no way to recover them**; the tag
`pre-redesign-frontend` therefore snapshots the landing page only.

Removed screens (full list in `REMOVED_FILES.md`):

| Group | Files | Purpose |
|---|---|---|
| `lib/features/modern/screens/` | `modern_home_screen`, `modern_brief_screen`, `modern_consultation_screen`, `modern_hospitals_screen`, `modern_intake_screen`, `modern_medications_screen`, `modern_patient_profile_screen`, `modern_settings_screen`, `modern_timeline_screen`, `modern_trends_screen` | the dashboard being replaced |
| `lib/features/auth/screens/` | 10 files (`auth_entry`, `doctor_professional`, `doctor_signup`, `doctor_verification`, `forgot_password`, `otp_verify`, `patient_signup`, `pending_review`, `reset_password`, `session`) | login/OTP/signup — forbidden by §0.2 rule 4/11 |
| `lib/main.dart` | — | entry point wiring the two above |

## 3. Routing approach

`Navigator`-based `MaterialPageRoute` pushes with hand-written paths in
`lib/core/constants/app_routes.dart`. **No `go_router`**, no named-route
reflection, no deep-link handling. Replaced (§12 decision FD-03).

## 4. Existing widgets

`lib/core/widgets/clin_*.dart` — `clin_atmosphere`, `clin_auth_chrome`,
`clin_brand`, `clin_button`, `clin_field`, `clin_headline`, `clin_motion`,
`clin_surface`, plus `lib/features/modern/widgets/modern_card.dart` and
`modern_pill.dart`. These were **CSS ports of the landing page** (a `dark`/
`ember` theme) and were all removed. Reuse candidates: **none** — §3's matrix
says old screens/widgets/theme are removed, keep nothing visual.

## 5. Existing theme

`lib/core/theme/` — `clin_tokens.dart`, `clin_theme.dart`, `app_colors.dart`,
`app_typography.dart`, `clin_typography.dart`, `theme_controller.dart`. A dark
"ember" theme with a `ThemeController` (light/dark switching). Not built from
§7 tokens. Removed and rewritten.

## 6. Networking layer

`lib/core/networking/api_client.dart` + `clinical_api_service.dart`.

* Hardcoded `http://127.0.0.1:8000` in `lib/core/constants/api_constants.dart`.
* 8 of its 14 endpoint paths **did not exist** on the backend.
* Its error parser read `message`/`detail` at the wrong level of the envelope,
  so backend errors would surface as raw Python strings.
* Replaced by `lib/core/networking/api_client.dart` (dio, envelope-aware,
  GET-only single retry, typed `ApiException`) + `app_config.dart` (§11.2).

## 7. Existing models

`lib/core/models/clinical_models.dart` + `patient_model.dart`. Field names
mismatched the backend (`name`/`gender`/`last_activity` vs
`full_name`/`sex`/`last_activity_at`) and there was one god-model file. Replaced
by `lib/core/models/*.dart` — one file per aggregate, each `fromJson` tolerant
of missing/odd fields (§8).

## 8. State management

**No state management library.** `setState` inside widgets plus a
`ClinAuthScope` `InheritedWidget` in `lib/features/auth/state/auth_scope.dart`.
Replaced with Riverpod.

## 9. FastAPI app

| Item | Value |
|---|---|
| Entry | `backend/app/main.py`, factory `create_app()` |
| Title / version | `ClinSync API` / `0.1.0` |
| Docs | `/docs` and `/redoc` — **`/api/docs` ABSENT** |
| CORS | `CORSMiddleware` with `settings.cors_origins_list`, `allow_credentials=True`, all methods, all headers |
| Request id | `@app.middleware("http")` echoes `X-Request-ID` or generates one, stores it on `request.state`, returns it in the response header |
| Lifespan | refuses to boot when `APP_ENV != development` and keys/validation are unset; **probes that `storage_path` is writable**, else raises |
| Health router | registered **twice** — bare and under `API_PREFIX` |
| Run command | `PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` |
| Env | `.env` at repo root (pydantic-settings), `APP_ENV=development` |

## 10. Existing API routes

All 15 routers are mounted under `/api/v1` (`settings.API_PREFIX`), except
`health`, which is also mounted bare. 57 endpoints:

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/health`, `/api/v1/health` | — | status envelope |
| GET | `/api/v1/health/deep` | — | deep health |
| POST | `/api/v1/patients` | patient body | 201 |
| GET | `/api/v1/patients` | `query`, `limit`, `offset` | list |
| GET | `/api/v1/patients/{id}` | — | patient |
| GET | `/api/v1/patients/{id}/overview` | — | overview aggregate |
| POST | `/api/v1/patients/{id}/documents` | multipart | 201 |
| POST | `/api/v1/documents/upload` | multipart | 201 |
| GET | `/api/v1/patients/{id}/documents` | `type`, `status`, `limit`, `offset` | list |
| GET | `/api/v1/documents` | `patient_id`, … | list |
| GET | `/api/v1/documents/{id}` | — | document |
| GET | `/api/v1/documents/{id}/file` | — | **raw bytes, no envelope** |
| GET | `/api/v1/documents/{id}/pages/{n}` | — | page text |
| GET | `/api/v1/documents/{id}/status` | — | processing status |
| POST | `/api/v1/documents/{id}/process` | — | job |
| POST | `/api/v1/documents/{id}/reprocess` | — | job |
| GET | `/api/v1/patients/{id}/facts` | `type`, `verification_status`, `limit`, `offset` | list |
| GET | `/api/v1/facts/{id}/evidence` | — | evidence |
| PATCH | `/api/v1/facts/{id}` | verification body | updated fact |
| GET | `/api/v1/patients/{id}/timeline` | `from`, `to`, `type`, `limit` | list |
| GET | `/api/v1/patients/{id}/medications` | `status` | list |
| GET | `/api/v1/patients/{id}/medications/reconciliation` | — | reconciliation |
| GET | `/api/v1/patients/{id}/medications/{group_key}/history` | — | history |
| GET | `/api/v1/patients/{id}/investigations` | `flag`, `limit` | list |
| GET | `/api/v1/patients/{id}/investigations/trends` | — | trend list |
| GET | `/api/v1/patients/{id}/investigations/{group_key}/trend` | — | single trend |
| GET | `/api/v1/patients/{id}/issues` | `type`, `status`, `severity` | list |
| GET | `/api/v1/patients/{id}/contradictions` | — | list |
| PATCH | `/api/v1/issues/{id}` | `status`, `doctor_note` | patched issue |
| POST | `/api/v1/patients/{id}/issues/recompute` | — | recomputed list |
| POST | `/api/v1/patients/{id}/brief` | `{specialty}` | generated brief |
| GET | `/api/v1/patients/{id}/brief/latest` | — | latest brief |
| GET | `/api/v1/patients/{id}/doctor-briefs/latest` | — | alias |
| GET | `/api/v1/briefs/{brief_id}` | — | brief |
| GET | `/api/v1/patients/{id}/consultations` | `status` | list |
| POST | `/api/v1/patients/{id}/consultations` | `{brief_id, specialty}` | 201 |
| GET | `/api/v1/consultations/{id}` | — | consultation |
| PUT | `/api/v1/consultations/{id}` | content | consultation |
| POST | `/api/v1/consultations/{id}/versions` | content, origin, summary | new version |
| GET | `/api/v1/consultations/{id}/versions` | — | versions |
| POST | `/api/v1/consultations/{id}/approve/preview` | content | validation preview |
| POST | `/api/v1/consultations/{id}/approve` | content | approved + memory update |
| GET | `/api/v1/patients/{id}/memory` | — | verified memory |
| GET | `/api/v1/patients/{id}/memories` | alias | list |
| GET | `/api/v1/patients/{id}/memory/history` | — | history |
| GET | `/api/v1/patients/{id}/memories/review-queue` | — | queue |
| POST | `/api/v1/patients/{id}/memories/proposals` | memory body | proposal |
| POST | `/api/v1/memories/{id}/approve` | doctor body | approved memory |
| POST | `/api/v1/memories/{id}/reject` | reason | rejected |
| POST | `/api/v1/patients/{id}/voice` | multipart audio, `language_hint` | 201 |
| POST | `/api/v1/voice/transcribe` | multipart | 201 |
| POST | `/api/v1/voice/{id}/review` | `edited_transcript` | reviewed |
| GET | `/api/v1/patients/{id}/audit` | `limit` | audit rows |
| GET | `/api/v1/specialties` | — | 7 static rows |

Envelope: `{"success": true, "data": …, "meta": {"request_id", "source"}}`; errors
are `{"success": false, "error": {"code", "message", "details"}, "meta": {…}}`.
`meta.source` ∈ `db | llm | system | stt`.

## 11. SQLAlchemy models

18 tables, all id-string PKs, declarative base with `created_at`/`updated_at`:

| Table | Columns |
|---|---|
| `patients` | id, full_name, date_of_birth, age_years, sex, contact_ref, is_demo, last_activity_at, deleted_at |
| `documents` | id, patient_id, original_filename, stored_path, mime_type, file_size, sha256, page_count, document_type, document_date, classification_confidence, processing_status, processing_error_code, extracted_text_path, ocr_method, is_fallback, uploaded_via |
| `document_pages` | id, document_id, page_number, text, ocr_confidence, method |
| `clinical_facts` | id, patient_id, document_id, voice_note_id, fact_type, value, normalized_value, fact_date, confidence, confidence_band, source_text, source_page, source_span_start, source_span_end, provenance_verified, verification_status, extraction_model, extraction_run_id |
| `medications` | id, patient_id, fact_id, canonical_name, raw_name, strength_value, strength_unit, dose_text, frequency_code, frequency_text, route, duration_text, start_date, stop_date, status, status_reason, group_key, confidence, source_document_id |
| `investigations` | id, patient_id, fact_id, test_name_raw, test_name_canonical, value_numeric, value_text, unit, reference_low, reference_high, reference_text, abnormal_flag, observed_date, source_document_id, confidence, group_key |
| `timeline_events` | id, patient_id, event_type, event_date, date_precision, title, summary, related_fact_ids, source_document_id, sort_key |
| `contradictions` | id, patient_id, issue_type, severity, title, description, related_document_ids, related_fact_ids, detail_json, status, doctor_note, detected_run_id |
| `briefs` | id, patient_id, specialty, content_json, generation_model, generation_source, validation_report_id, status, input_fingerprint |
| `consultations` | id, patient_id, brief_id, specialty, status, current_version_id, approved_at, approved_by |
| `consultation_versions` | id, consultation_id, version_number, origin, content_json, change_summary, edited_by, validation_report_id |
| `clinical_memory` | id, patient_id, memory_type, content_json, source_consultation_id, source_version_id, verified, validation_report_id, supersedes_id |
| `voice_notes` | id, patient_id, stored_path, duration_s, transcript_raw, transcript_normalized, stt_model, stt_confidence, language, status, review_status |
| `processing_jobs` | id, subject_type, subject_id, stage, status, attempts, last_error_code, last_error_detail, started_at, finished_at |
| `validation_reports` | id, gate, subject_type, subject_id, outcome, checks_json, judge_model, judge_verdict_json, attempt_number |
| `audit_log` | id, timestamp, actor, action, entity_type, entity_id, patient_id, before_json, after_json, request_id, ip |
| `llm_call_log` | id, request_id, task, logical_slot, provider_model_used, fallback_depth, latency_ms, input_tokens, output_tokens, success, error_code, created_at |

> Note `medications.group_key` and `investigations.group_key` **do** exist as
> columns — see `API_MISMATCHES.md` M-07, the API does not expose them in the
> medication list payload.

## 12. DB setup

| Item | Value |
|---|---|
| URL | `sqlite:///./clinsync.db` (relative to CWD) → repo-root `clinsync.db` (+ `-wal`, `-shm`) |
| Engine | `create_engine(..., connect_args={"check_same_thread": False})` for SQLite, `echo` only at DEBUG |
| Pragmas | `PRAGMA foreign_keys=ON`, `PRAGMA journal_mode=WAL` on every connect |
| Session | `SessionLocal = sessionmaker(autocommit=False, autoflush=False)`; `get_db()` generator and `get_db_context()` contextmanager |
| Migrations | **ABSENT** — no Alembic, no `migrations/`, no `alembic.ini` |
| Schema creation | **ABSENT from the codebase** — there is no `Base.metadata.create_all(...)` anywhere in project code, so the tables in the committed `clinsync.db` were created out-of-band. A fresh clone therefore cannot serve a single endpoint until the schema is created. Recorded as an observation in `API_MISMATCHES.md` (O-01); not fixed here because §4 forbids changing backend behaviour as part of the frontend rebuild. |

## 13. Storage

| Item | Value |
|---|---|
| Root | `settings.storage_path` → `Path(settings.STORAGE_ROOT)`, `mkdir(parents=True, exist_ok=True)` on access; default `storage/` |
| Layout | `storage/patients/{patient_id}/documents/{document_id}__{filename}` and `storage/patients/{patient_id}/voice/{voice_note_id}.{ext}` |
| Upload limit | `MAX_UPLOAD_MB = 25` |
| MIME allow-list | `ALLOWED_MIME`, comma-separated (PDF + images), exposed as `allowed_mime_list` |
| Writes | `services/document_service.store_document` / `services/voice_service.process_voice` |
| Read | `GET /documents/{id}/file` streams `stored_path` raw, **no envelope, no auth check** |

## 14. Developer A code (clinical intelligence)

| Module | Public API | Real or stub |
|---|---|---|
| `services/medication_service.py` | `reconcile(db, patient_id)` → contradictions; the source of the metformin conflict | real |
| `services/contradiction_service.py` | `recompute(db, patient_id)` → `Contradiction` rows | real — but its future-date detector queries `Document.id == patient_id` (`contradiction_service.py:118`), a bug that makes that rule never fire (O-02) |
| `services/missing_info_service.py` | `recompute(db, patient_id)` → missing-information rows | real |
| `services/timeline_service.py` | builds `TimelineEvent`s (diagnosis, medication_start, dose_change, investigation) with `sort_key` | real |
| `services/trend_service.py` | groups investigations by `group_key`, computes direction + deltas | real |
| `services/brief_service.py` | `generate_brief(...)` (real LLM path) and `_build_deterministic_template_brief(...)` fallback; caches on `input_fingerprint` | real |
| `services/clinical_memory_service.py` | builds verified memory rows from an approved consultation | real |
| `validation/gate1_validator.py`, `gate2_validator.py` | Gate 1 fact validation, Gate 2 brief validation (claim extraction → evidence match → consistency → unsupported-claim detection) | real |
| `services/normalization_service.py` | `normalize_medication`, `normalize_investigation`, `normalize_date` (day-first parsing) | real |
| LangGraph intake graph (readme §15 / implementation §15) | **ABSENT** — no `app/ai/nodes`, `app/ai/graph.py`, `app/ai/extractors`, or `ClinicalIntakeState` module exists | — |

## 15. Developer B code (document intelligence)

| Module | Public API | Notes |
|---|---|---|
| `services/ocr_service.py` | `extract_text(...)` — PyMuPDF text layer, else vision OCR | fallback: placeholder text with `ocr_confidence` 0.40 (PDF) / 0.30 (image) and `method="fallback"` |
| `services/classification_service.py` | `classify(...)` → `DocClassification` | `hint` param accepted and unused; fallback = keyword heuristic at confidence 0.60/0.40 |
| `services/extraction_service.py` | `extract(pages, doc_type)` → `ExtractionResult` | LLM with `temperature=0`, JSON repaired once; fallback = 3 hard-coded regexes (HbA1c, 6 drug names, 5 diagnoses) at confidence 0.75, each with an `EvidenceReference` |
| `services/evidence_service.py` | `verify_evidence(source_text, page_number, pages_dict)` → `(bool, score, page)` | exact → RapidFuzz `partial_ratio` ≥ 85; **falls back to any other page** when the requested page misses |
| `services/confidence_service.py` | `calculate_confidence(model_confidence, provenance_verified, ocr_confidence, unknown_mapping)` | real banding (≥0.85 high / ≥0.60 medium / else needs_verification); the pipeline never passes `ocr_confidence` or `unknown_mapping` |
| `services/pipeline_orchestrator.py` | `run(document_id, is_reprocess)` → job id | real state machine (`extracting_text → classifying → extracting_entities → normalize/persist → complete`), FastAPI `BackgroundTasks` — **no Celery/worker**, `ai/fallbacks/` is an empty package |
| `services/voice_service.py` | `process_voice(...)`, `review_voice(...)` | real; STT failure → placeholder transcript, `stt_model="fallback"`, confidence 0.50, facts created at 0.55 `needs_verification`; review promotes to 0.80 `medium` |
| `ai/gateway.py` | `LLMGateway` singleton: `complete_text`, `complete_json`, `vision_extract`, `transcribe`, `judge` | LiteLLM Router over 3 logical slots (`llm_generate` 4-deep, `llm_extract` 2-deep, `llm_judge` 2-deep); vision 2 models manual; **STT is single-provider (Groq Whisper) with no fallback** — `STT_PRIMARY`/`STT_FALLBACK_*` are declared but never read |
| `ai/prompts/*.md` | prompt files per task | real |
| `schemas/ai_contracts.py` | `DocClassification`, `ExtractionResult` (+ 7 list fields), `EvidenceReference` | real Pydantic v2 contracts with alias normalisers |

## 16. Demo data

| Item | Value |
|---|---|
| Seed | `backend/app/db/seed.py`, `seed_demo_data(reset=True)`; CLI `python -m app.db.seed --reset` (**the CLI has a bug: `reset=args.reset or True`, so `--reset` is always on** — O-03) |
| Fixtures dir | `Path("tests/fixtures")` — **CWD-relative**, so seeding only works from the repo root |
| Patient | `pat_demo_patient_001` / "Demo Patient" / DOB 1974-05-14 / 52 / male / `is_demo=True` / last activity 2026-09-28. Aliases `demo-patient-001`, `demo_patient_001` resolve to it |
| Documents | 6 generated PDFs: `doc_demo_001_consult_jan`, `002_rx_feb`, `003_lab_apr`, `004_consult_jun`, `005_rx_sep`, `006_discharge_sep` — all `complete`, `page_count=1` |
| Facts | 1 diagnosis, 3 symptoms, 1 observation, 7 investigations (HbA1c 8.4 → 8.0 → 7.8 all flagged high; fasting glucose 168/142 high; creatinine 0.9 ×2) |
| Medications | 4 rows incl. **the deliberate conflict**: metformin 1000 mg BD marked `uncertain` with a reason string, against metformin 500 mg BD `current` |
| Issues | Produced by running the real reconcile/contradiction/missing-info engines after seeding |
| Brief | 1 seeded brief, `generation_source="seed"`, content hard-coded; its `evidence_shortcuts` reference `ev_001`–`ev_003`, which **are not real fact ids** (O-04) |
| Consultation | 1 approved consultation + 3 versions (`ai_generated → doctor_edited → approved`) |
| Memory | 2 verified memory rows (diagnosis + active regimen) linked to that version |
| Idempotency | `reset_demo_patient()` purges every clinical table and the patient's storage folder; covered by `tests/test_seed_and_demo.py::test_seed_idempotency` |

## 17. Fallback logic

| Layer | On failure the backend returns |
|---|---|
| LLM generate / judge | raises `LLMUnavailableError` → **503 `LLM_UNAVAILABLE`** with a human message |
| Vision | both models tried, then 503 |
| STT | one provider only, then 503 |
| Brief | **real fallback**: after `GATE2_MAX_REGEN_ATTEMPTS`, `_build_deterministic_template_brief(...)`, persisted with `generation_source="fallback_template"`, `status="fallback_template"` |
| Classification | keyword heuristic, confidence 0.60 (0.40 with no hit) |
| Extraction | 3 hard-coded regexes at 0.75 |
| OCR | placeholder text, `ocr_confidence` 0.40/0.30, `method="fallback"` |
| Voice | placeholder transcript, `stt_model="fallback"`, 0.50, request still 201 |

**`meta.source == "fallback"` is never emitted.** `schemas/common.py:10` comments
the value in, but no code path assigns it — see `API_MISMATCHES.md` M-01, which
is why the app derives its `Demo data` tag from fixture provenance instead.

## 18. Landing page

| Item | Value |
|---|---|
| Framework | **ABSENT** — static HTML/CSS/vanilla-JS, one 989-line `index.html`, one 888-line flat `assets/css/style.css`, one 740-line IIFE `assets/js/main.js`. No `package.json`, no bundler, no third-party JS |
| Entry | `index.html`; the only external request is the Google Fonts CSS |
| Hosting | Vercel static project `clinsync-landing`, no build config |
| Theme | hard-locked to light by an inline head script (`index.html:16-22`), which makes the whole dark palette, the theme toggle and the `::view-transition` reveal unreachable |

Full detail, including what was and was not translated, in
`LANDING_ANALYSIS.md`.

## 19. `lightNoWatermark` assets

Measured with `ffprobe`:

| File | Codec | Resolution | fps | Duration | Size |
|---|---|---|---|---|---|
| `lightNoWatermark.mp4` | h264 / yuv420p | **1280×720** | 24 | **19.00 s** (456 frames) | **3 250 944 B** |
| `darkNoWatermark.mp4` | h264 / yuv420p | 1920×1080 | 24 | 18.66 s (446 frames) | 12 410 417 B |
| `assets/video/hero-light.mp4` | h264 | 1600×900 | 24 | 19.00 s | 1 633 849 B |
| `assets/video/hero-dark.mp4` | h264 | 1600×900 | 24 | 18.58 s | 2 459 248 B |
| `assets/video/ribbon-light.mp4` | h264 | 1280×720 | 24 | 19.00 s | 1 164 262 B |
| `assets/video/ribbon-dark.mp4` | h264 | 1280×720 | 24 | 18.58 s | 1 546 290 B |

Content: a polished chrome ribbon / Möbius loop rotating on a near-white studio
backdrop (light files) or a glowing blue-violet arc over wet rock (dark files).
**No people in any frame.**

Referenced by: `index.html:128,131,702,705` for the four `assets/video` files
(as `poster` + `<source>`, `autoplay muted loop playsinline`, plus two scrim
overlays). **`lightNoWatermark.mp4` / `darkNoWatermark.mp4` are referenced nowhere
in the landing page** — a repo-wide grep for `NoWatermark` across `*.html`,
`*.css`, `*.js` returns zero hits. `lightNoWatermark.mp4` is used by
`tools/extract_ambient_stills.py`, which the app uses for its ambient stills
(§6.5a); `darkNoWatermark.mp4` is unused and is 11.8 MB, over the §7.8 budget,
so it is not shipped in the app.

## 20. Existing animations / transitions

**Flutter side (before):** `lib/core/widgets/clin_motion.dart` — a CSS port of
the landing page's reveal/parallax, tied to the removed dark theme. Removed.

**Flutter side (after):** `lib/core/animations/motion.dart` +
`page_transitions.dart` — the §7.9 set (section reveal, press scale, soft pulse,
hero parallax ≤ 0.25, animated count, ambient scrim, fade-through page
transition), every one of them honouring `MediaQuery.disableAnimations`. The
ambient video loops on top of that. Described in `DESIGN_TOKENS.md` §6.

**Landing side:** 15 `@keyframes` (two of them dead), a single
`IntersectionObserver` reveal with an `is-in` class and JS-set stagger delays,
word-by-word heading splits, sticky-nav blur past 40 px, hero-video parallax
(`scale 1.08 → 1.20`, `translateY 0 → −6%`, opacity `0.9 → 0.35`), 420 vh
scrollytelling, a 38 s marquee, a lerped custom cursor ring and spotlight, and
3D tilt + magnetic buttons. Full inventory in `LANDING_ANALYSIS.md` §7–§8.

---

## Also found (not asked for, but load-bearing)

| # | Finding |
|---|---|
| 1 | `backend/app/ai/fallbacks/` exists but is an **empty package** (0 lines). |
| 2 | `validation/policies.yaml` and `validation/validators/prompt_injection_check.py` are declared but never read. |
| 3 | `settings` declares `STT_PRIMARY`, `STT_FALLBACK_1`, `STT_FALLBACK_2`, `DEMO_FALLBACKS_ENABLED`, `GATE1_MIN_FACT_CONFIDENCE` — all unread. |
| 4 | `clinical_facts.source_span_end` is never populated (only `source_span_start`). |
| 5 | `GET /patients/{id}/brief/latest` injects a hard-coded `readiness_score = 92` (`briefs.py:50`) — not a model output. The app renders it as a progress ring without implying it is derived. |
| 6 | Backend tests live in `tests/` at the repo root (23 tests in 8 files), have no `conftest.py`, and assume the schema already exists. `.pytest_cache/v/cache/lastfailed` still lists `test_document_pipeline_e2e` as failing — the one test that needs a live vision call. |
| 7 | `docs/PROGRESS.md`, `docs/DECISIONS.md`, `docs/OPEN_QUESTIONS.md` at the repo root are **backend** documents from the previous phase. This frontend work adds `docs/frontend/`. |
