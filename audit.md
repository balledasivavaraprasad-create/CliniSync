# CLINSYNC — BACKEND AUDIT & BUILD SPECIFICATION

> **Audience:** Antigravity (AI coding agent) + the human owner (Developer C).
> **Purpose:** Single source of truth to build the entire ClinSync backend, in depth, in phases, with acceptance criteria.
> **Product name:** **ClinSync** (never "ClinicSync").
> **Status:** Foundation document. If code and this file disagree, this file wins until it is deliberately updated.

---

## 0. HOW ANTIGRAVITY MUST USE THIS FILE

1. Read the whole file once before writing code.
2. Build strictly in the phase order of **Section 22**. Do not start a phase until the previous phase's acceptance checks pass.
3. Every phase ends with: runnable app, passing tests, updated `docs/PROGRESS.md`.
4. Never invent endpoints, tables, or fields not listed here. If something is missing, add it to `docs/OPEN_QUESTIONS.md` and pick the safest default.
5. **Never hardcode model names or API keys.** Everything comes from `.env` / `config.py` (Section 5).
6. **Model identifiers in this document are placeholders.** Provider model names change often. Verify the exact current IDs in the Gemini and Groq docs before first run and put them in `.env`.
7. Every AI call goes through the **LLM Gateway** (Section 9). No direct SDK calls from services.
8. Every write to `clinical_memory` and every generated brief/summary passes the **Validation Layer** (Section 12). No exceptions, no bypass flags in production mode.

### Non‑negotiable build rules ("utmost sincerity" rules)
- Patient safety beats demo polish. When unsure, flag, do not assert.
- The AI never decides doses, diagnoses, or treatment. It organizes, compares, and surfaces.
- No silent failures: every failure is logged, surfaced with a typed error code, and (where safe) degraded to a clearly labeled fallback.
- Fallback/demo data must always be labeled `source: "fallback"` in the response and never written to verified memory.
- Type everything (Pydantic v2 + type hints). Lint with `ruff`, type-check with `mypy` (or `pyright`).

---

## 1. WHAT CLINSYNC IS

ClinSync is an **AI-powered longitudinal clinical intelligence platform**. A patient's information is scattered across prescriptions, lab reports, consultation notes, diagnostic reports, discharge summaries, scans, images, voice notes, and older records. Doctors reconstruct history mentally before every consultation.

ClinSync converts fragmented records into a **unified, evidence-linked patient context** that preserves provenance and keeps the clinician in control.

It is **not** just OCR, **not** a medical chatbot, **not** a record dashboard.

### Product transformation
```text
Fragmented Records
 → Document Intelligence → Structured Evidence → Clinical Facts
 → Longitudinal Clinical Context → Medication + Investigation Intelligence
 → Contradictions + Missing Information → 60-Second Doctor Brief
 → Doctor Review → Consultation → Doctor Approval → Verified Clinical Memory
```

### Team split (for context)
| Role | Owns |
|---|---|
| Developer B | Document intelligence: OCR → classification → extraction → evidence |
| Developer A | Clinical intelligence: timeline, meds, labs, contradictions, missing info, brief |
| Developer C | Flutter app + FastAPI spine + SQLite + storage + integration (this backend) |

> This backend must **contain working implementations of A and B's modules** (via `services/` and `ai/`) behind clean interfaces, so that A and B can later swap in their improved logic without touching routes.

---

## 2. CORE ARCHITECTURAL PRINCIPLES (INVARIANTS)

### 2.1 Provenance chain
```text
RAW SOURCE → EVIDENCE → CLINICAL FACT → LONGITUDINAL OBJECT
→ CLINICAL SYNTHESIS → DOCTOR REVIEW → APPROVAL → VERIFIED CLINICAL MEMORY
```

### 2.2 Invariants (must be enforced in code AND tested)
| ID | Invariant |
|---|---|
| INV-1 | AI output can never write directly to `clinical_memory`. Only the **approve** endpoint (after Gate 1) can. |
| INV-2 | Every clinical fact has: `source_document_id` (or voice/consultation source), `source_text`, `source_page` (nullable for voice), `confidence`, `verification_status`. |
| INV-3 | `source_text` must be verifiable against the stored OCR/transcript text of the source (substring / fuzzy match ≥ threshold). Otherwise confidence is capped and fact is flagged. |
| INV-4 | The system never states a "correct" dose/frequency when sources conflict. It emits a **conflict**, never a resolution. |
| INV-5 | Missing information is a **prompt to the clinician**, never a guessed value. |
| INV-6 | Trends are described (direction/magnitude), never explained causally. |
| INV-7 | Generated text never contains treatment directives ("start", "stop", "increase", "prescribe", "you should") — it may only report what sources say. |
| INV-8 | AI-generated ≠ doctor-edited ≠ doctor-approved. Every consultation version carries an explicit `origin`. |
| INV-9 | Every state-changing action writes an `audit_log` row. |
| INV-10 | Fallback data is never persisted as verified and is always labeled. |

---

## 3. TECHNOLOGY STACK

| Concern | Choice |
|---|---|
| Language | Python 3.11+ |
| API | FastAPI + Uvicorn |
| Validation/schemas | Pydantic v2 |
| ORM | SQLAlchemy 2.x (typed, sync sessions OK for prototype; keep repository layer so async/Postgres swap is possible) |
| Migrations | Alembic (even for SQLite) |
| DB | SQLite (WAL mode, foreign keys ON) |
| File storage | Local filesystem under `storage/` |
| LLM gateway | **LiteLLM** (SDK `Router` in-process; optionally LiteLLM Proxy later) |
| Primary LLM provider | Google Gemini (API key in env) |
| Secondary LLM provider | Groq (API key in env) |
| Speech-to-text | Gemini transcribe-capable model (primary) → Groq Whisper (fallback) |
| PDF text | PyMuPDF (`fitz`) |
| OCR / scans | Gemini multimodal (primary vision OCR) → Groq vision-capable model or Tesseract (fallback, optional) |
| Image prep | Pillow (resize, rotate, normalize) |
| Guardrails | LiteLLM guardrail hooks + custom deterministic validators (Section 12) |
| HTTP client | httpx |
| Testing | pytest, pytest-asyncio, httpx TestClient, `respx` for mocking |
| Lint/format | ruff, mypy |
| Logging | structlog (JSON logs) |
| Config | pydantic-settings |

`requirements.txt` (minimum): `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `sqlalchemy`, `alembic`, `litellm`, `pymupdf`, `pillow`, `python-multipart`, `httpx`, `structlog`, `tenacity`, `rapidfuzz`, `python-dateutil`, `pytest`, `respx`, `ruff`, `mypy`.

---

## 4. REPOSITORY STRUCTURE

```text
backend/
├── app/
│   ├── main.py                    # app factory, middleware, router mounting, lifespan
│   ├── config.py                  # pydantic-settings
│   ├── api/
│   │   ├── deps.py                # db session, current_user stub, request_id
│   │   ├── errors.py              # exception handlers → standard error envelope
│   │   └── routes/
│   │       ├── health.py
│   │       ├── patients.py
│   │       ├── documents.py
│   │       ├── facts.py           # facts + evidence viewer
│   │       ├── timeline.py
│   │       ├── medications.py
│   │       ├── investigations.py
│   │       ├── issues.py          # contradictions + missing + low-confidence
│   │       ├── briefs.py
│   │       ├── consultations.py
│   │       ├── memory.py
│   │       ├── voice.py
│   │       └── audit.py
│   ├── models/                    # SQLAlchemy models
│   │   ├── base.py
│   │   ├── patient.py
│   │   ├── document.py
│   │   ├── clinical_fact.py
│   │   ├── medication.py
│   │   ├── investigation.py
│   │   ├── timeline_event.py
│   │   ├── contradiction.py
│   │   ├── consultation.py
│   │   ├── clinical_memory.py
│   │   ├── brief.py
│   │   ├── voice_note.py
│   │   ├── processing_job.py
│   │   ├── validation_report.py
│   │   └── audit_log.py
│   ├── schemas/                   # Pydantic request/response + AI JSON contracts
│   │   ├── common.py              # envelope, enums, pagination
│   │   ├── patient.py
│   │   ├── document.py
│   │   ├── clinical.py
│   │   ├── ai_contracts.py        # strict JSON schemas the LLMs must return
│   │   ├── brief.py
│   │   ├── consultation.py
│   │   └── validation.py
│   ├── repositories/              # DB access only (no business logic)
│   ├── services/
│   │   ├── patient_service.py
│   │   ├── document_service.py        # upload, store, dedupe, status
│   │   ├── ocr_service.py             # text extraction (pdf text / vision OCR)
│   │   ├── classification_service.py
│   │   ├── extraction_service.py
│   │   ├── normalization_service.py   # drug names, units, frequencies, dates
│   │   ├── evidence_service.py
│   │   ├── timeline_service.py
│   │   ├── medication_service.py      # tracking + reconciliation
│   │   ├── lab_service.py             # grouping + trends
│   │   ├── contradiction_service.py
│   │   ├── missing_info_service.py
│   │   ├── confidence_service.py
│   │   ├── brief_service.py
│   │   ├── consultation_service.py
│   │   ├── memory_service.py
│   │   ├── voice_service.py
│   │   ├── pipeline_orchestrator.py   # runs the doc pipeline state machine
│   │   └── audit_service.py
│   ├── ai/
│   │   ├── gateway.py                 # LiteLLM Router wrapper (THE ONLY LLM entry point)
│   │   ├── models_registry.py         # logical model names → provider IDs from env
│   │   ├── stt.py                     # speech-to-text w/ fallback chain
│   │   ├── vision.py                  # image/scan → text
│   │   ├── document_ai.py             # Dev B interface
│   │   ├── clinical_ai.py             # Dev A interface
│   │   ├── json_utils.py              # robust JSON parse/repair
│   │   ├── prompts/
│   │   │   ├── classify_document.md
│   │   │   ├── extract_entities.md
│   │   │   ├── normalize.md
│   │   │   ├── generate_brief.md
│   │   │   ├── draft_consultation.md
│   │   │   ├── judge_gate1.md
│   │   │   └── judge_gate2.md
│   │   └── fallbacks/                 # structured fallback JSON per task
│   ├── validation/                    # THE VALIDATION LAYER
│   │   ├── pipeline.py                # orchestrates validators, returns ValidationReport
│   │   ├── gate1_memory.py            # Gate 1: pre-clinical-memory
│   │   ├── gate2_output.py            # Gate 2: post-brief/summary
│   │   ├── validators/
│   │   │   ├── schema_validator.py
│   │   │   ├── provenance_validator.py
│   │   │   ├── numeric_consistency.py
│   │   │   ├── directive_language.py
│   │   │   ├── causality_language.py
│   │   │   ├── hallucination_check.py
│   │   │   ├── completeness_check.py
│   │   │   ├── pii_scope_check.py
│   │   │   └── llm_judge.py
│   │   └── policies.yaml              # thresholds, banned patterns, severities
│   ├── db/
│   │   ├── database.py
│   │   ├── seed.py                    # demo patient
│   │   └── migrations/ (alembic)
│   └── utils/ (dates.py, ids.py, hashing.py, text.py, units.py)
├── storage/patients/{patient_id}/{documents,images,voice}/
├── tests/ (unit, integration, e2e, golden)
├── docs/ (PROGRESS.md, OPEN_QUESTIONS.md, DECISIONS.md)
├── .env.example
├── alembic.ini
├── pyproject.toml
└── requirements.txt
```

Layering rule: **routes → services → repositories → models**. Routes contain no business logic. Services never import from routes. Only `ai/gateway.py` imports `litellm`.

---

## 5. CONFIGURATION (`.env.example`)

```ini
# ── App
APP_ENV=development                 # development | demo | production
APP_NAME=ClinSync
API_PREFIX=/api/v1
LOG_LEVEL=INFO
CORS_ORIGINS=*
DEMO_FALLBACKS_ENABLED=true         # allow labeled fallback data when ALL AI providers fail

# ── Storage / DB
DATABASE_URL=sqlite:///./clinsync.db
STORAGE_ROOT=./storage
MAX_UPLOAD_MB=25
ALLOWED_MIME=application/pdf,image/jpeg,image/png,image/webp,audio/mpeg,audio/wav,audio/mp4,audio/webm

# ── Provider keys
GEMINI_API_KEY=
GROQ_API_KEY=

# ── Logical model slots (VERIFY exact IDs in provider docs before first run)
# Format for LiteLLM: gemini/<model>  |  groq/<model>
LLM_PRIMARY=gemini/<gemini-flash-class-model>
LLM_SECONDARY=gemini/<gemini-pro-class-model>
LLM_FALLBACK_1=groq/<llama-70b-class-model>
LLM_FALLBACK_2=groq/<smaller-fast-model>
LLM_JUDGE_PRIMARY=groq/<llama-70b-class-model>     # judge SHOULD differ from generator provider
LLM_JUDGE_FALLBACK=gemini/<gemini-flash-class-model>
VISION_PRIMARY=gemini/<gemini-multimodal-model>
VISION_FALLBACK=gemini/<gemini-alt-multimodal-model>
STT_PRIMARY=gemini/<gemini-3.5-transcribe-class-model>
STT_FALLBACK_1=gemini/<gemini-alt-audio-capable-model>
STT_FALLBACK_2=groq/whisper-large-v3               # verify current Groq Whisper ID

# ── Gateway behavior
LLM_TIMEOUT_S=45
LLM_MAX_RETRIES=2
LLM_TEMPERATURE_EXTRACT=0.0
LLM_TEMPERATURE_SYNTH=0.2
LLM_COOLDOWN_S=30                   # router cooldown after failures

# ── Validation
VALIDATION_ENABLED=true             # MUST be true in demo/production (enforced at startup)
GATE1_MIN_FACT_CONFIDENCE=0.60
GATE2_MAX_REGEN_ATTEMPTS=2
PROVENANCE_FUZZY_THRESHOLD=85       # rapidfuzz partial_ratio
```

Startup checks (`lifespan`): fail fast if keys missing in non-dev, if `VALIDATION_ENABLED=false` while `APP_ENV != development`, or if storage root is not writable. Log (never print keys) which providers are configured.

---

## 6. DATA MODEL (SQLite via SQLAlchemy)

Conventions: string UUID primary keys with prefix (`pat_`, `doc_`, `fact_`, …); `created_at`, `updated_at` UTC; soft delete via `deleted_at` where noted; enable `PRAGMA foreign_keys=ON; journal_mode=WAL`.

### 6.1 Enums
```text
DocumentType: prescription | lab_report | consultation_note | discharge_summary | diagnostic_report | imaging_report | referral | other | unknown
ProcessingStatus: uploaded | extracting_text | classifying | extracting_entities | normalizing | validating | complete | failed | needs_review
FactType: diagnosis | symptom | medication | investigation | allergy | procedure | observation | vital | history | social | family_history | other
VerificationStatus: unverified | needs_verification | doctor_verified | doctor_rejected
ConfidenceBand: high | medium | needs_verification
Severity: low | medium | high
ConsultationOrigin: ai_generated | doctor_edited | approved
IssueType: medication_conflict | date_conflict | duplicate_record | unclear_medication_status | diagnosis_conflict | low_confidence_fact | missing_information
MedStatus: current | previous | uncertain
Specialty: general_medicine | cardiology | diabetology | orthopedics | pediatrics | neurology | other
ValidationGate: gate1_memory | gate2_output
ValidationOutcome: pass | pass_with_flags | blocked
```

### 6.2 Tables

**patients**
`id, full_name, date_of_birth (nullable), age_years (nullable), sex (nullable), contact_ref (nullable), is_demo (bool), last_activity_at, created_at, updated_at, deleted_at`

**documents**
`id, patient_id FK, original_filename, stored_path, mime_type, file_size, sha256 (dedupe per patient), page_count, document_type, document_date (nullable), classification_confidence, processing_status, processing_error_code, extracted_text_path (full text per page JSON), ocr_method (pdf_text|vision|hybrid|fallback), is_fallback (bool), uploaded_via (upload|camera|voice), created_at, updated_at`

**document_pages**
`id, document_id FK, page_number, text, ocr_confidence, method`
(Page-level text is the ground truth used by provenance validation.)

**clinical_facts**
`id, patient_id FK, document_id FK (nullable for voice/consultation), voice_note_id FK nullable, fact_type, value (display string), normalized_value (JSON), fact_date (nullable), confidence (0–1 float), confidence_band (derived), source_text, source_page, source_span_start/end (nullable), provenance_verified (bool), verification_status, extraction_model, extraction_run_id, created_at, updated_at`

**medications** (longitudinal medication records; each links to a fact)
`id, patient_id FK, fact_id FK, canonical_name, raw_name, strength_value, strength_unit, dose_text, frequency_code (OD|BD|TDS|QID|HS|PRN|weekly|other), frequency_text, route, duration_text, start_date, stop_date, status (MedStatus), status_reason, group_key (patient+canonical_name), confidence, source_document_id, created_at`

**investigations**
`id, patient_id FK, fact_id FK, test_name_raw, test_name_canonical (LOINC-like key optional), value_numeric (nullable), value_text, unit, reference_low, reference_high, reference_text, abnormal_flag (low|high|normal|unknown), observed_date, source_document_id, confidence, group_key`

**timeline_events**
`id, patient_id FK, event_type (consultation|diagnosis|medication_start|medication_stop|dose_change|investigation|procedure|symptom|discharge|approved_note), event_date, date_precision (day|month|year|unknown), title, summary, related_fact_ids (JSON), source_document_id, sort_key, created_at`

**contradictions** (also stores missing-info and low-confidence issues — "issues")
`id, patient_id FK, issue_type, severity, title, description, related_document_ids (JSON), related_fact_ids (JSON), detail_json, status (open|acknowledged|resolved_by_doctor|dismissed), doctor_note, detected_run_id, created_at, updated_at`

**briefs**
`id, patient_id FK, specialty, content_json, generation_model, generation_source (llm|fallback), validation_report_id FK, status (validated|validated_with_flags|fallback_template), input_fingerprint (hash of facts used), created_at`

**consultations**
`id, patient_id FK, brief_id FK nullable, specialty, status (draft|in_review|approved), current_version_id, approved_at, approved_by, created_at, updated_at`

**consultation_versions**
`id, consultation_id FK, version_number, origin (ConsultationOrigin), content_json, change_summary, edited_by, validation_report_id nullable, created_at`

**clinical_memory**
`id, patient_id FK, memory_type (diagnosis|medication|allergy|history|investigation_summary|plan_note|…), content_json, source_consultation_id FK, source_version_id FK, verified (bool, default true only via approve), validation_report_id FK, supersedes_id nullable, created_at, updated_at`
(Append-only with `supersedes_id`; never destructive update, to preserve history.)

**voice_notes**
`id, patient_id FK, stored_path, duration_s, transcript_raw, transcript_normalized, stt_model, stt_confidence, language, status, review_status (pending_review|reviewed), created_at`

**processing_jobs**
`id, subject_type (document|voice|brief), subject_id, stage, status, attempts, last_error_code, last_error_detail, started_at, finished_at`

**validation_reports**
`id, gate, subject_type, subject_id, outcome, checks_json (list of {name, passed, severity, detail}), judge_model, judge_verdict_json, attempt_number, created_at`

**audit_log**
`id, timestamp, actor (doctor_id|system|ai), action, entity_type, entity_id, patient_id, before_json, after_json, request_id, ip (nullable)`

**llm_call_log** (observability + cost + fallback audit)
`id, request_id, task (classify|extract|brief|…), logical_slot, provider_model_used, fallback_depth, latency_ms, input_tokens, output_tokens, success, error_code, created_at`
(Never store raw patient text in this table; store hashes/sizes only.)

### 6.3 Required indexes
`documents(patient_id, sha256)` unique; `clinical_facts(patient_id, fact_type)`; `medications(patient_id, group_key)`; `investigations(patient_id, group_key, observed_date)`; `timeline_events(patient_id, sort_key)`; `contradictions(patient_id, status)`; `audit_log(entity_type, entity_id)`.

---

## 7. FILE STORAGE

```text
storage/patients/{patient_id}/documents/{doc_id}__{safe_filename}
storage/patients/{patient_id}/images/{doc_id}.{ext}      # camera captures (still documents)
storage/patients/{patient_id}/voice/{voice_id}.{ext}
storage/patients/{patient_id}/ocr/{doc_id}.json          # per-page extracted text
```
Rules:
- Sanitize filenames; never trust client paths (prevent path traversal).
- Validate MIME by magic bytes, not only extension; enforce `MAX_UPLOAD_MB`.
- Compute SHA‑256; if the same hash exists for that patient → return existing document with `duplicate: true` (also feeds `duplicate_record` issue).
- SQLite stores only metadata + relative paths.
- Serving files: authenticated endpoint streams file; never expose raw filesystem path.

---

## 8. API CONTRACT (`/api/v1`)

### 8.1 Standard envelopes
Success:
```json
{ "success": true, "data": { }, "meta": { "request_id": "req_...", "source": "llm|fallback|db" } }
```
Error:
```json
{ "success": false, "error": { "code": "DOCUMENT_PROCESSING_FAILED", "message": "Unable to process document", "details": {} }, "meta": { "request_id": "req_..." } }
```
Error codes (minimum): `VALIDATION_ERROR, NOT_FOUND, DUPLICATE_DOCUMENT, UNSUPPORTED_FILE_TYPE, FILE_TOO_LARGE, DOCUMENT_PROCESSING_FAILED, OCR_FAILED, EXTRACTION_FAILED, LLM_UNAVAILABLE, STT_FAILED, GATE1_BLOCKED, GATE2_BLOCKED, CONSULTATION_NOT_APPROVABLE, INVALID_STATE_TRANSITION, INTERNAL_ERROR`.
No stack traces ever reach the client. Every response carries `X-Request-ID`.

### 8.2 Endpoints

**Health**
- `GET /health` → app up. `GET /health/deep` → DB, storage, per-provider reachability (cheap ping), validation enabled.

**Patients**
- `POST /patients` {full_name, date_of_birth?, age_years?, sex?}
- `GET /patients?query=&limit=&cursor=` → name, age, last_activity
- `GET /patients/{id}`
- `GET /patients/{id}/overview` → single aggregate for Flutter's Overview screen: patient, latest brief (if any), attention items, timeline preview, current meds, latest investigations, source count, memory summary, open issue counts.

**Documents**
- `POST /patients/{patient_id}/documents` (multipart: file, `uploaded_via`, optional `document_type_hint`, optional `document_date`) → stores, creates row, returns `document_id`.
- `GET /patients/{patient_id}/documents`
- `GET /documents/{document_id}` → metadata, status, confidence.
- `GET /documents/{document_id}/file` → stream original.
- `GET /documents/{document_id}/pages/{n}` → page text (for evidence viewer).
- `POST /documents/{document_id}/process` → starts pipeline (background task). Returns `job_id`, status `extracting_text`.
- `GET /documents/{document_id}/status` → current stage + stage list for the Processing screen (Uploaded → Extracting → Classifying → Extracting clinical information → Complete).
- `POST /documents/{document_id}/reprocess` (idempotent: supersedes previous run's unverified facts).

**Facts & Evidence**
- `GET /patients/{id}/facts?type=&status=&min_conf=`
- `GET /facts/{fact_id}/evidence` → fact, source document, page, source_text, extraction_confidence, provenance_verified, highlight offsets.
- `PATCH /facts/{fact_id}` → doctor correction/verification (`verification_status`, corrected value); writes audit.

**Timeline / Meds / Investigations**
- `GET /patients/{id}/timeline?from=&to=&type=`
- `GET /patients/{id}/medications?status=` → each item with `changes[]`, `conflict_ids[]`, `confidence_band`.
- `GET /patients/{id}/medications/{group_key}/history`
- `GET /patients/{id}/investigations` → latest value per test.
- `GET /patients/{id}/investigations/{group_key}/trend` → series + direction + `description` (non-causal).

**Issues**
- `GET /patients/{id}/issues?type=&status=&severity=`
- `PATCH /issues/{id}` → acknowledge / dismiss / resolved_by_doctor + note.
- `POST /patients/{id}/issues/recompute` → rerun contradiction + missing-info engines.

**Brief**
- `POST /patients/{patient_id}/brief` {specialty} → generates, runs **Gate 2**, persists, returns DoctorBrief.
- `GET /patients/{patient_id}/brief/latest`
- `GET /briefs/{brief_id}`

**Consultations**
- `POST /patients/{patient_id}/consultations` {specialty, brief_id?} → creates draft (version 1, origin `ai_generated`, Gate 2 applied).
- `GET /consultations/{id}` (with current version)
- `PUT /consultations/{id}` → doctor edits working draft (does not create version until saved).
- `POST /consultations/{id}/versions` {content, change_summary} → new version, origin `doctor_edited`.
- `GET /consultations/{id}/versions`
- `POST /consultations/{id}/approve` → **Gate 1**, then writes clinical_memory + timeline `approved_note`.
- `POST /consultations/{id}/approve/preview` → dry-run Gate 1; returns what *would* enter memory + flags (so UI can show it before commit).

**Clinical memory**
- `GET /patients/{id}/memory` (verified only), `GET /patients/{id}/memory/history`

**Voice**
- `POST /patients/{patient_id}/voice` (multipart audio) → STT → normalize → extraction → returns transcript + proposed facts as `needs_verification`.
- `POST /voice/{id}/review` → doctor confirms/edits transcript; confirmed facts become `unverified` (ordinary facts), still never memory.

**Audit**
- `GET /patients/{id}/audit?entity=&limit=`

**Specialty**
- `GET /specialties` (static list); selection is passed with brief/consultation requests (stored on patient as `preferred_specialty` optional).

### 8.3 DoctorBrief schema (strict)
```json
{
  "patient": {"id": "", "name": "", "age": 0},
  "specialty": "general_medicine",
  "generated_at": "",
  "chief_complaint": {"text": "", "evidence_ids": [], "confidence_band": ""},
  "relevant_history": [{"text": "", "evidence_ids": [], "confidence_band": ""}],
  "current_medications": [{"name": "", "strength": "", "dose": "", "frequency": "", "status": "", "evidence_ids": [], "confidence_band": "", "conflict_flag": false}],
  "allergies": [{"text": "", "evidence_ids": [], "status": "documented|not_documented"}],
  "recent_investigations": [{"test": "", "value": "", "unit": "", "reference": "", "date": "", "abnormal": "", "evidence_ids": []}],
  "important_trends": [{"test": "", "series": [], "direction": "up|down|stable|mixed", "description": "", "evidence_ids": []}],
  "attention_items": [{"text": "", "severity": "", "evidence_ids": []}],
  "contradictions": [{"issue_id": "", "text": "", "sources": []}],
  "missing_information": [{"prompt": "", "reason": ""}],
  "evidence_shortcuts": [{"evidence_id": "", "label": "", "document_id": "", "page": 0}],
  "disclaimer": "AI-assisted summary of source records. Not a diagnosis or treatment recommendation. Verify against sources."
}
```
**Rule:** every statement has `evidence_ids` referencing real `clinical_facts` rows (or issue ids). Statements without evidence are rejected by Gate 2.

### 8.4 Consultation content schema
```json
{
  "chief_complaint": "", "history_of_present_illness": "", "past_history": "",
  "current_medications": [], "allergies": [], "examination": "", "investigations_reviewed": [],
  "assessment": "", "plan": "", "follow_up": "", "flags": [{"text": "", "by": "doctor|ai"}],
  "evidence_ids": []
}
```
AI drafts only pre-fill **record-derived** sections (history, meds, allergies, investigations). `examination`, `assessment`, `plan`, `follow_up` are left **empty for the doctor** (or contain explicitly labeled "doctor to complete" placeholders). The AI must not draft assessment/plan content.

---

## 9. AI ARCHITECTURE & LLM GATEWAY

### 9.1 Two AI stages (behind clean interfaces)
- `ai/document_ai.py` (Dev B): `extract_text(file) → PageTexts`, `classify(text) → DocClassification`, `extract_entities(text, doc_type) → ExtractionResult`.
- `ai/clinical_ai.py` (Dev A): `generate_brief(context, specialty) → DoctorBrief`, `draft_consultation(context, brief) → ConsultationContent`, optional `summarize_trend(series)`.
Deterministic logic (timeline, reconciliation, trends, contradictions, missing-info) lives in `services/` and **does not need an LLM** — LLM is used only for classification, extraction, normalization assist, brief wording, consultation drafting, and judging. Prefer deterministic code wherever it is reliable.

### 9.2 LiteLLM gateway (`ai/gateway.py`)
Single class `LLMGateway` exposing:
```python
complete_json(task, messages, schema: type[BaseModel], slot="primary", temperature=None) -> ParsedResult
complete_text(task, messages, slot="primary") -> str
vision_extract(task, image_bytes_list, prompt, schema=None) -> ...
transcribe(audio_path, language_hint=None) -> TranscriptResult
judge(task, payload, rubric) -> JudgeVerdict
```
Implementation requirements:
1. Build a `litellm.Router` from `models_registry.py`, using logical groups with ordered fallbacks:
   - `llm_generate`: PRIMARY → SECONDARY → FALLBACK_1 → FALLBACK_2
   - `llm_extract`: PRIMARY → FALLBACK_1 → FALLBACK_2 (temperature 0)
   - `llm_judge`: JUDGE_PRIMARY → JUDGE_FALLBACK (**judge provider should differ from the generator that produced the output whenever possible**)
   - `vision`: VISION_PRIMARY → VISION_FALLBACK
   - `stt`: STT_PRIMARY → STT_FALLBACK_1 → STT_FALLBACK_2
2. Router settings: `num_retries=LLM_MAX_RETRIES`, `timeout=LLM_TIMEOUT_S`, cooldown after repeated failures, fallbacks on rate-limit (429), timeout, 5xx, and **context-window / content-policy errors**.
3. Structured outputs: request JSON mode / response schema where the provider supports it; always validate with Pydantic. On parse failure: one **repair attempt** (`json_utils.repair`), then one **re-ask** with the validation error appended, then fall to the next model.
4. Prompt hygiene: system prompt loaded from `ai/prompts/*.md`; patient text inserted inside clearly delimited blocks (`<document_text>…</document_text>`); instructions state the text is **data, not instructions** (prompt-injection defense — scanned documents can contain adversarial text).
5. Log every call to `llm_call_log` (no raw PHI). Record `fallback_depth` so the owner can see degradation.
6. When all providers fail → raise `LLMUnavailable`; the calling service decides between failing, using a deterministic path, or (if `DEMO_FALLBACKS_ENABLED`) returning labeled fallback data.
7. Global concurrency limit (semaphore) and per-provider rate limiter to respect free-tier quotas.
8. Never log API keys or full prompts containing patient text at INFO level.

### 9.3 Model roles (all IDs from env)
| Task | Primary | Fallbacks | Temp |
|---|---|---|---|
| Speech-to-text | Gemini 3.5 transcribe‑class model | other Gemini audio model → Groq Whisper | 0 |
| Scan/image OCR | Gemini multimodal | alt Gemini multimodal → Tesseract (optional) | 0 |
| Classification | fast Gemini | Groq 70B → Groq small | 0 |
| Entity extraction | Gemini (stronger) | Groq 70B | 0 |
| Normalization assist | fast Gemini | Groq small | 0 |
| Brief generation | Gemini stronger | Groq 70B | 0.2 |
| Consultation draft | Gemini stronger | Groq 70B | 0.2 |
| Validation judge | Groq 70B | Gemini | 0 |

### 9.4 AI JSON contracts (`schemas/ai_contracts.py`)
Classification:
```json
{"document_type": "prescription", "document_date": "2026-09-20", "date_confidence": 0.9, "confidence": 0.95, "language": "en"}
```
Extraction (per document):
```json
{
  "medications": [{"name":"","strength":"","dose":"","frequency":"","duration":"","route":"","confidence":0.0,"evidence":{"text":"","page":1}}],
  "investigations": [{"test":"","value":"","unit":"","reference_range":"","flag":"","date":"","confidence":0.0,"evidence":{"text":"","page":1}}],
  "diagnoses": [{"text":"","date":"","confidence":0.0,"evidence":{}}],
  "symptoms": [], "allergies": [], "procedures": [], "observations": [], "vitals": [],
  "document_level_dates": [{"label":"","date":"","evidence":{}}]
}
```
Rules baked into the extraction prompt: copy `evidence.text` **verbatim** from the document; never infer values not present; use `null` for unknown; never "correct" a prescription; output JSON only.

---

## 10. DOCUMENT PIPELINE (STATE MACHINE)

```text
uploaded
  → extracting_text      (PDF text layer via PyMuPDF; if page text < threshold chars → vision OCR for that page; images → vision OCR)
  → classifying          (LLM; deterministic keyword heuristic as cross-check)
  → extracting_entities  (LLM, JSON-schema constrained)
  → normalizing          (deterministic first, LLM assist for unknowns)
  → provenance_checking  (every evidence.text located in page text; sets provenance_verified & caps confidence)
  → persisting           (documents, facts, medications, investigations, timeline_events in ONE transaction)
  → derived_recompute    (timeline, med reconciliation, lab trends, contradictions, missing-info for the patient)
  → complete | needs_review | failed
```
Rules:
- Run as FastAPI `BackgroundTasks` (prototype) behind `pipeline_orchestrator.run(document_id)`; design so it can move to a queue later. Update `processing_jobs` and `documents.processing_status` at every stage (powers `GET /documents/{id}/status`).
- Each stage is **idempotent** and resumable; a retry never duplicates facts (use `extraction_run_id`; reprocess marks older unverified facts `superseded`).
- Partial failure policy: OCR fail → `failed` with `OCR_FAILED`; extraction partial → `needs_review` (keep what succeeded, flag the rest).
- Low OCR quality (very short text, low confidence) → document flagged and a `low_confidence_fact` issue created; confidence capped at 0.59 ("needs verification").
- Hybrid PDFs: process per page, record `ocr_method=hybrid`.
- Multi-page and multi-document-in-one-PDF: classify per document, but prototype may treat the file as one type and flag mixed content.

### 10.1 Normalization rules (`normalization_service.py`)
- **Drug names:** lowercase, strip salt/brand noise via a small curated map (`metformin hcl` → `metformin`); keep `raw_name`. Brand→generic map seeded for common drugs; unknown stays raw with lower confidence.
- **Strength:** parse `500 mg`, `0.5g` → value+unit, normalize unit to mg/mcg/g/ml/IU.
- **Frequency:** map `OD, once daily, 1-0-0, qd` → `OD`; `BD, BID, twice daily, 1-0-1` → `BD`; `TDS/TID/1-1-1` → `TDS`; `HS` → bedtime; `SOS/PRN` → `PRN`. Unknown → `other` + raw text.
- **Dates:** parse with `dateutil`, **explicit dayfirst policy configurable (default dayfirst=True for India)**; record `date_precision`; ambiguous dates (e.g., 03/04/2026) are flagged, not guessed silently.
- **Lab units & test names:** canonical key map (`hba1c`, `glycated hemoglobin`, `a1c` → `hba1c`), unit normalization, parse numeric from text (`7.8 %`), parse reference ranges (`< 5.7`, `4.0–5.6`).
- **Abnormal flag:** computed deterministically from numeric vs reference when both present; else take document's flag, else `unknown`.

---

## 11. CLINICAL INTELLIGENCE SERVICES (DETERMINISTIC-FIRST)

### 11.1 Timeline (`timeline_service`)
Build events from facts: consultations, diagnoses, med start/stop/dose change, investigations, procedures, discharges, approved notes. Sort by `event_date` with `date_precision` tie-breaks; events with unknown dates go to an "undated" bucket and also feed missing-info. Each event keeps `source_document_id` and `related_fact_ids` (evidence shortcut stays near the event).

### 11.2 Medication tracking (`medication_service`)
- Group by `group_key = patient + canonical_name`.
- Build history per group ordered by source document date.
- Status logic: `current` if in the most recent prescription/consultation and not marked stopped; `previous` if explicitly stopped or absent from a later complete prescription **(absence alone → `uncertain`, not `previous`)**; `uncertain` when sources are ambiguous or dates missing.
- Detect **changes** (strength/frequency differences across dates in order) → `dose_change` timeline events labeled as *changes recorded in documents*.

### 11.3 Reconciliation (`medication_service.reconcile`)
Same drug, different strength/frequency across documents:
- If dates are ordered and distinct → report **"Medication instruction changed"** (informational, with both sources).
- If dates are equal/unknown or documents are of conflicting intent → **`medication_conflict`** issue.
- **Never output a "correct" dose.** Output text template: *"Two records contain different {Drug} frequencies: {A} (Doc X, date) vs {B} (Doc Y, date)."*
- Also detect duplicates (same drug twice in one prescription), brand+generic duplication, and unclear status.

### 11.4 Lab intelligence (`lab_service`)
Group by canonical test + unit (flag unit mismatches rather than converting silently unless a safe conversion is defined). Compute series, latest, previous, delta, direction (`up/down/stable/mixed` with tolerance per test), and a **non-causal description**: *"HbA1c recorded 8.4% (Jan 2026), 8.0% (Apr 2026), 7.8% (Sep 2026): decreasing across three measurements."* No causal language; no clinical interpretation beyond reference-range flag.

### 11.5 Contradiction engine (`contradiction_service`)
Rule-based detectors, each producing typed issues with severity and `detail_json`:
| Detector | Example | Default severity |
|---|---|---|
| medication_conflict | different frequency/strength same date | medium (high if strength differs ≥2×) |
| date_conflict | same document two dates; consult before DOB; future dates | low–medium |
| duplicate_record | identical sha256 or near-identical text | low |
| unclear_medication_status | present in old, absent in new, no stop info | low |
| diagnosis_conflict | mutually listed contradictory diagnoses (curated pairs, e.g., "Type 1 vs Type 2 diabetes") | medium |
| low_confidence_fact | confidence < 0.60 or provenance unverified | low |
Issues are **recomputed deterministically** after each document and keyed by a stable fingerprint so doctor acknowledgments persist across recomputes.

### 11.6 Missing information (`missing_info_service`)
Checklist engine (specialty-aware, config in `policies.yaml`): allergy status undocumented, most recent HbA1c older than N months (for diabetes context), medication start date absent, undated documents, no discharge summary where an admission is mentioned, etc. Output is always phrased as **"Potentially missing: …"** with a `reason`. Never populates values.

### 11.7 Confidence (`confidence_service`)
Internal float 0–1 → band: `≥0.85 high`, `0.60–0.84 medium`, `<0.60 needs_verification`. Final confidence = `min(model_confidence, ocr_quality_cap, provenance_cap)`; provenance not verified → cap 0.59; OCR page quality low → cap 0.70; normalized with unknown mapping → −0.10.

### 11.8 Brief generation (`brief_service`)
1. **Assemble context** deterministically from DB (facts, meds, labs, issues, memory) — structured JSON, size-bounded, with ids.
2. LLM writes only the wording of sections using that context (`generate_brief.md` prompt; specialty drives *emphasis/ordering*, not new facts).
3. Output → Pydantic `DoctorBrief` → **Gate 2** (Section 12).
4. Verified-memory facts are labeled `verified` in the brief; unverified AI facts labeled by confidence band.
5. If Gate 2 blocks after max regenerations → deterministic **template brief** built straight from DB (no LLM) with `generation_source="fallback_template"`.
6. Cache by `input_fingerprint`; regenerate when facts change.

---

## 12. VALIDATION LAYER (GUARDRAILS) — RUNS TWICE

Implemented in `app/validation/`, orchestrated by `validation/pipeline.py`, using **LiteLLM guardrail hooks** where applicable plus custom deterministic validators and an **LLM judge** routed through the gateway. Policies/thresholds live in `policies.yaml` (hot-editable, versioned).

```text
        EXTRACTION & CONSULTATION FLOW

 AI facts / draft ──► doctor review/edit ──► [GATE 1] ──► clinical_memory
                                                ▲
 Context ──► LLM Brief/Summary ──► [GATE 2] ──► shown to doctor / saved
```

### 12.1 Common design
- Input: `ValidationRequest{gate, subject, context_snapshot}`; output: `ValidationReport{outcome, checks[], judge_verdict}` persisted in `validation_reports` and linked from the subject.
- Check severities: `info | warn | block`. Any `block` → outcome `blocked`; only `warn` → `pass_with_flags`; none → `pass`.
- Validators run **cheapest first** (schema → deterministic text → numeric/provenance → LLM judge). Skip the LLM judge if a deterministic `block` already occurred.
- The judge model should be a **different provider/model** than the one that generated the content.
- Everything is logged and auditable; `VALIDATION_ENABLED` cannot be false outside development.
- Validation failures of the *validator itself* (e.g., judge API down) → **fail closed for Gate 1** (cannot write memory), **fail to deterministic template for Gate 2**.

### 12.2 Validators
| Validator | What it checks | Applies to |
|---|---|---|
| schema_validator | Strict Pydantic parse; no extra fields; required sections | G1, G2 |
| provenance_validator | Each fact/claim has evidence id; `source_text` fuzzy-found in stored page text (≥ `PROVENANCE_FUZZY_THRESHOLD`) | G1, G2 |
| numeric_consistency | Every number/unit/date in output equals the DB value for the cited evidence (no altered doses, values, dates) | G1, G2 |
| directive_language | Regex + judge: no "start/stop/increase/reduce/prescribe/recommend/should/must" directed at treatment | G2 (and AI-authored G1 parts) |
| causality_language | No "due to, caused by, because of, leading to, resulting from" linking clinical entities | G2 |
| hallucination_check | Entities in output (drug names, tests, diagnoses) must exist in source facts or doctor-authored text | G1, G2 |
| completeness_check | Brief has all required sections; conflicts in DB appear in brief; high-severity issues not omitted | G2 |
| conflict_integrity | If a conflict exists, output must not state a single "correct" value | G1, G2 |
| authorship_check | Content origin clearly tagged (ai_generated / doctor_edited) and unmodified AI-only text isn't presented as verified | G1 |
| pii_scope_check | Output only contains data of the current patient (no cross-patient leakage) | G1, G2 |
| prompt_injection_check | Source text/outputs containing "ignore previous instructions", role-play, URLs to exfiltrate etc. flagged | G1 (on extraction), G2 |
| llm_judge | Rubric-based faithfulness/safety scoring (see below) | G1, G2 |

### 12.3 GATE 1 — Pre-Clinical-Memory (first-ever write to verified memory)
**Trigger:** `POST /consultations/{id}/approve` (and the `/approve/preview` dry run). Also applied to any individual fact the doctor promotes to memory.
**Purpose:** guarantee that what becomes *verified clinical memory* is faithful, provenance-backed, doctor-reviewed, and free of AI assumptions.

Checks:
1. **State check:** consultation status is `in_review`, current version origin is `doctor_edited` (or ai_generated *that doctor explicitly acknowledged*), `approved_by` present. Pure untouched AI draft cannot be approved without an explicit `acknowledged_unedited=true` flag recorded in audit.
2. Schema validity of the consultation content.
3. Memory candidate extraction: derive `memory_items[]` (diagnosis, medications, allergies, history, notes) from the approved version.
4. For each memory item: provenance (evidence ids resolve, or flagged `doctor_authored`), numeric consistency, hallucination check, conflict integrity (open `high` severity issues must be **acknowledged by the doctor**, else `blocked`; medium → `pass_with_flags`).
5. Forbidden: items with `confidence_band=needs_verification` and `verification_status!=doctor_verified` cannot enter memory silently.
6. Directive/causality scan on AI-authored sentences (doctor-authored plan text is allowed to contain directives, because the doctor owns it, but is tagged `doctor_authored`).
7. LLM judge: "Does each memory item faithfully reflect the cited evidence or doctor text? Any added assumption?"
8. Idempotency/duplicate check against existing memory (`supersedes_id` chain).

Outcomes:
- `pass` → write `clinical_memory` rows (`verified=true`), `timeline_events(approved_note)`, audit log, `consultations.status=approved`.
- `pass_with_flags` → same, but flags are stored with the report and returned to the UI.
- `blocked` → **nothing written**; return `GATE1_BLOCKED` with per-check reasons the UI can show; consultation stays `in_review`.
Write is **one DB transaction**; Gate 1 report is created before the write and linked in each memory row.

### 12.4 GATE 2 — Post-Generation (detailed summary / brief / consultation draft)
**Trigger:** immediately after any LLM-generated brief, summary, or consultation draft, before it is persisted/returned.
Checks: schema → provenance (every statement cites real evidence ids) → numeric consistency (compared with DB) → directive language → causality language → hallucination check → completeness (all conflicts/high-severity issues included, allergies section present even if "not documented") → conflict integrity → pii scope → judge.
Judge rubric (0–5 each, thresholds in policy): **faithfulness, completeness, non-directiveness, non-causality, uncertainty preserved, clarity/scan-ability**. Any faithfulness < 4 or non-directiveness < 5 → `blocked`.

Loop:
```text
attempt 1 → Gate 2 → pass ─────────────► persist
          └ blocked → regenerate with violation feedback appended (≤ GATE2_MAX_REGEN_ATTEMPTS)
                      └ still blocked → deterministic template brief (labeled) + log
```
The persisted brief stores `validation_report_id`, `status`, and `generation_source`.

### 12.5 Guardrails via LiteLLM
- Register custom guardrail callbacks (pre-call: prompt-injection/PII-scope scrub of instructions; post-call: directive/causality/JSON-schema enforcement) so protection applies to *every* gateway call, not only the two gates.
- Keep gates as **explicit domain checks** (they need DB access) and LiteLLM guardrails as **generic call-level protection**; document this split in `docs/DECISIONS.md`.
- Gate checks must be unit-tested with adversarial fixtures (Section 19).

---

## 13. CONSULTATION, VERSIONS, APPROVAL, MEMORY

State machine:
```text
draft(v1: ai_generated) → [doctor edits] → in_review(v2+: doctor_edited) → approve → [GATE 1] → approved(v_n: approved)
```
- Invalid transitions → `INVALID_STATE_TRANSITION`.
- Saving a version stores a diff summary (computed server-side: sections changed), `edited_by`, `origin`.
- Approved consultations are **immutable**; amendments create a new consultation referencing the previous (`amends_consultation_id`).
- On approval: write memory items (append-only), update `patients.last_activity_at`, add timeline `approved_note`, invalidate cached briefs, audit log. Return the "Clinical Memory Updated" payload (what was added, flags).
- Doctor flagging inside consultation is stored in `flags` and carried to memory as notes, never as facts.

---

## 14. VOICE & CAMERA

**Camera:** the app uploads a JPEG/PNG via the normal document endpoint with `uploaded_via=camera`. Backend adds Pillow preprocessing (auto-orient via EXIF, downscale to safe max, contrast normalize) then follows the same pipeline. No separate camera AI.

**Voice pipeline:**
```text
audio upload → validate/convert → STT (gateway chain: Gemini transcribe → fallback → Groq Whisper)
→ transcript_raw → normalization (spelling of drugs/units; keep raw too) → clinical extraction (same extractor, source=voice)
→ facts as needs_verification (page=null, source_text = transcript snippet) → doctor review → ordinary unverified facts
```
Rules: store both raw and normalized transcripts; STT confidence recorded; transcript must be reviewable before extraction facts are used in briefs (briefs mark voice-derived facts as "voice, unreviewed" unless reviewed); never auto-promote to memory. Language hint supported (English + Hindi/Tamil common for the user's region); if language not English, keep original and flag for review.

---

## 15. ERROR HANDLING, FALLBACKS & DEMO MODE

- Typed exception hierarchy (`ClinSyncError` → `NotFound`, `ValidationFailed`, `LLMUnavailable`, `OCRFailed`, `Gate1Blocked`, …) mapped by global handlers to the error envelope.
- **Fallback tiers:** (1) provider fallback chain via LiteLLM → (2) deterministic/heuristic path (regex extraction for common prescription/lab formats, template brief) → (3) pre-authored fallback JSON in `ai/fallbacks/` **only if `DEMO_FALLBACKS_ENABLED`**, flagged `meta.source="fallback"` and `documents.is_fallback=true`; fallback-derived facts are `needs_verification` and **blocked from Gate 1**.
- Timeouts everywhere; background task exceptions captured into `processing_jobs.last_error_*`.
- Graceful degradation matrix documented in `docs/DECISIONS.md`.

---

## 16. SECURITY, PRIVACY & COMPLIANCE POSTURE

- Prototype auth: static bearer token / single doctor stub (`current_user` dependency) designed for later JWT/OAuth swap. All routes depend on it (except `/health`).
- Treat all content as PHI: no PHI in logs; `llm_call_log` stores hashes/sizes only; redact in error messages.
- CORS restricted outside dev; request size limits; rate limiting on upload/process/brief routes.
- Upload safety: MIME magic check, size limits, never execute files, sanitize names, PDF parsing in try/except with page limits (e.g., ≤ 100 pages).
- Prompt-injection defense: documents are data; delimiters; instruction-hierarchy statement; injection detector; extraction output restricted to schema so injected text cannot cause side effects.
- Data minimization when calling external LLMs: send only needed text; do not send patient name/contact when not required (replace with `PATIENT`). Note: Gemini/Groq are third-party processors — **document this in `docs/DECISIONS.md` and in the app's disclaimer; production use requires proper agreements/compliance review** (this prototype is not a certified medical device).
- Audit log is append-only; no delete endpoint.
- Backups: copy `clinsync.db` + `storage/` (documented script).

---

## 17. OBSERVABILITY

- structlog JSON, `request_id` propagation into services and `llm_call_log`.
- Metrics (simple counters in `/health/deep` or `/metrics`): documents processed, avg stage latency, fallback depth distribution, Gate 1/2 pass/flag/block counts, regeneration rates.
- Debug endpoint (dev only): `GET /dev/validation/{report_id}`.

---

## 18. DEMO DATA (`db/seed.py`)

Fictional patient **"Demo Patient"** (flagged `is_demo`) with six documents (text fixtures + generated PDFs in `tests/fixtures/`):
1. Initial consultation (Jan 2026) — type 2 diabetes, symptoms, **allergy not documented**.
2. Prescription (Feb 2026) — Metformin 500 mg once daily.
3. Lab report (Apr 2026) — HbA1c 8.0%, fasting glucose.
4. Follow-up consultation (Jun 2026).
5. Updated prescription (Sep 2026) — Metformin 500 mg **twice daily** (+ new drug) → change + conflict scenario.
6. Discharge/diagnostic document (Sep 2026) — HbA1c 7.8%, mixed date formats.
Must visibly demonstrate: medication change, medication conflict (one same-date conflicting pair), repeated labs (8.4 → 8.0 → 7.8), missing information (allergy, start date), multiple dates, longitudinal history. Seed command: `python -m app.db.seed --reset`. Seeding **bypasses LLMs** by loading pre-extracted JSON through the same persistence path (so demo works offline) and labels them `source=seed`.

---

## 19. TESTING STRATEGY

**Unit:** normalization (frequencies, units, dates incl. ambiguity), confidence caps, reconciliation (changed vs conflict vs duplicate), lab trend direction, each validator with pass/fail fixtures.
**Adversarial validation fixtures (must all block):** brief that says "increase Metformin to 1000 mg"; altered dose number; fabricated drug not in facts; causal sentence ("HbA1c improved due to Metformin"); missing evidence ids; cross-patient fact injection; document text containing "ignore previous instructions…"; untouched AI draft approval without acknowledgment; open high-severity conflict not acknowledged.
**Integration:** upload → process → facts → derived outputs (with mocked gateway via `respx`/fake provider); gateway fallback chain (simulate 429/timeout on primary → secondary → Groq); JSON repair path.
**E2E (golden):** seed patient → brief → consultation → edit → version → approve → memory → overview reflects memory. Snapshot-test the DoctorBrief structure.
**Contract tests:** OpenAPI schema snapshot so the Flutter team detects breaking changes.
**Resilience:** all providers down → proper labeled fallback or typed error, never a 500.
Coverage target: ≥ 80% on `services/`, `validation/`, `ai/gateway.py`.

---

## 20. PERFORMANCE TARGETS (PROTOTYPE)
- Upload response < 1 s (processing is async).
- Single-page document full pipeline < 20 s typical.
- Brief generation incl. Gate 2 < 15 s typical; cached brief < 200 ms.
- Overview aggregate endpoint < 300 ms (DB only; no LLM).

---

## 21. ACCEPTANCE CHECKLIST (GLOBAL "DEFINITION OF DONE")
- [ ] All endpoints in Section 8 implemented with schemas, error envelope, request ids.
- [ ] Pipeline works for text-PDF, scanned-PDF, camera image, and voice note.
- [ ] Every fact has evidence; evidence endpoint resolves doc/page/text.
- [ ] Reconciliation never emits a "correct" dose (tested).
- [ ] Gate 2 runs on every brief/draft; Gate 1 on every approval; neither bypassable in demo/production.
- [ ] Gateway fallback chain demonstrated by killing primary key in test.
- [ ] Fallback data is always labeled and never reaches clinical memory (tested).
- [ ] Audit log written for each state change.
- [ ] Seeded demo patient reproduces all demo scenarios offline.
- [ ] `docs/PROGRESS.md` and `docs/DECISIONS.md` current.

---

## 22. PHASED BUILD PLAN (ANTIGRAVITY EXECUTION ORDER)

### Phase 0 — Scaffolding (foundation)
- [ ] Project skeleton per Section 4, `pyproject`, ruff/mypy config, `.env.example`, pydantic-settings, structlog, request-id middleware, error envelope + handlers, `/health`.
- [ ] SQLAlchemy base, DB session, WAL/foreign keys, Alembic init.
**Exit:** `uvicorn` runs, `/health` returns envelope, lint/type clean.

### Phase 1 — Data layer & patients
- [ ] All models in 6.2 + migrations; repositories; audit service; id generators.
- [ ] Patients CRUD + list/search + `/overview` skeleton.
**Exit:** migrations apply on empty DB; patient endpoints tested.

### Phase 2 — Storage & documents
- [ ] Upload (multipart), MIME magic validation, SHA-256 dedupe, filesystem layout, file streaming, document list/get/page endpoints.
**Exit:** upload/list/get/download tested incl. oversize/invalid type/duplicate.

### Phase 3 — LLM Gateway (critical)
- [ ] `models_registry`, `LLMGateway` (LiteLLM Router, groups, fallbacks, retries, cooldown), JSON repair/re-ask, concurrency/rate limits, `llm_call_log`.
- [ ] `stt.py` and `vision.py` wrappers with chains.
- [ ] Fake-provider test harness.
**Exit:** forced primary failure falls through to Groq in tests; structured JSON parse+repair tested; `/health/deep` shows provider status.

### Phase 4 — Document intelligence (Dev B module)
- [ ] `ocr_service` (PyMuPDF text, per-page vision OCR fallback), `classification_service`, `extraction_service` with prompts, `normalization_service`, `evidence_service` (provenance check), `confidence_service`.
- [ ] `pipeline_orchestrator` state machine, `processing_jobs`, `/process`, `/status`, `/reprocess`.
- [ ] Persist facts/meds/investigations/timeline in one transaction.
**Exit:** fixtures for prescription/lab/consult produce expected facts with verified provenance; status endpoint reports stages.

### Phase 5 — Clinical intelligence (Dev A module)
- [ ] `timeline_service`, `medication_service` (tracking+reconcile), `lab_service`, `contradiction_service`, `missing_info_service`; recompute hooks after each document.
- [ ] Endpoints: facts/evidence, timeline, medications(+history), investigations(+trend), issues(+patch/recompute).
**Exit:** seeded scenarios yield exactly the expected conflict/change/trend/missing items; INV-4/5/6 tests pass.

### Phase 6 — Validation Layer & guardrails
- [ ] `policies.yaml`, all validators, `validation/pipeline.py`, `ValidationReport` persistence.
- [ ] LiteLLM call-level guardrail callbacks.
- [ ] Judge prompts/rubrics, adversarial test suite.
**Exit:** all adversarial fixtures block; clean fixtures pass; judge-down behavior verified (G1 fail-closed, G2 template fallback).

### Phase 7 — Brief (Gate 2 integrated)
- [ ] Context assembler, `generate_brief` prompt, specialty emphasis config, regen loop, deterministic template fallback, caching by fingerprint.
- [ ] `POST /brief`, `GET /brief/latest`, overview integration.
**Exit:** brief passes Gate 2 on demo patient; injected bad generation triggers regen then template.

### Phase 8 — Consultations, approval, clinical memory (Gate 1 integrated)
- [ ] Consultation CRUD + versions + state machine, diff summaries, `/approve/preview`, `/approve` with Gate 1, memory writer (append-only), timeline approved_note, cache invalidation.
- [ ] `GET /memory`, `/memory/history`.
**Exit:** untouched AI draft blocked without acknowledgment; unacknowledged high conflict blocked; valid approval writes memory atomically.

### Phase 9 — Voice & camera
- [ ] Voice upload → STT chain → normalization → extraction → review endpoint.
- [ ] Image preprocessing for camera uploads.
**Exit:** voice transcript produces `needs_verification` facts; STT primary failure falls back.

### Phase 10 — Hardening & demo
- [ ] Seed script, fallback JSON, rate limiting, auth stub, audit endpoint, metrics, OpenAPI snapshot, load/resilience tests, docs (`PROGRESS`, `DECISIONS`, `OPEN_QUESTIONS`), `README` run guide, Postman/OpenAPI export for the Flutter team.
**Exit:** global checklist (Section 21) fully ticked; 5-minute demo script runs offline and online.

---

## 23. ASSUMPTIONS & OPEN QUESTIONS (resolve in `docs/OPEN_QUESTIONS.md`)
1. **Exact model IDs** (Gemini transcribe-class, Gemini text/vision, Groq LLM + Whisper) must be verified and set in `.env`; the architecture is ID-agnostic.
2. Date format default (dayfirst) — assumed day-first (India); make configurable per patient.
3. Languages beyond English for OCR/STT (Hindi/Tamil) — best-effort in prototype.
4. Single-doctor prototype (no multi-tenant RBAC) — schema keeps `actor` fields so RBAC can be added.
5. Whether LiteLLM Proxy (separate server) is preferred over the in-process Router — start in-process; the gateway abstraction allows moving to the proxy without changing services.
6. External LLM processing of PHI requires a compliance decision before any real patient data is used.
7. "Utmost sincerity" is interpreted as the safety/rigor rules in Section 0 and the invariants in Section 2. Revise if you meant something additional.

---

## 24. ONE-PARAGRAPH SUMMARY FOR THE AGENT
Build ClinSync's FastAPI backend as a strictly layered, evidence-first system: ingest documents/voice/camera → extract text (PDF text/vision/STT via a LiteLLM gateway with Gemini primary and Groq fallbacks) → classify and extract structured facts with verbatim provenance → normalize and score confidence → compute timeline, medication tracking/reconciliation, lab trends, contradictions and missing-info deterministically → generate a Gate‑2‑validated 60‑second brief → let the doctor draft/edit/version a consultation → pass **Gate 1** and only then write append-only, verified clinical memory. AI never overwrites verified memory, never resolves medication conflicts, never gives treatment directives, never guesses missing data, and everything is audited.
