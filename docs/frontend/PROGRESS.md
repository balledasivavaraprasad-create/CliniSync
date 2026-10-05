# Frontend build progress

Task graph C01–C39 from `implementation.md` §16. **All 39 tasks complete.**
Branch `frontend-redesign` · safety tag `pre-redesign-frontend`.

Verification gate for every task, per §0.2 rule 9:

```bash
flutter analyze     # No issues found!
flutter test        # 127 tests, All tests passed!
flutter build web --release
PYTHONPATH=backend .venv/bin/python -m pytest tests/ -q   # 61 passed
.venv/bin/python tools/capture_screens.py   # 21 routes, 0 Dart/JS exceptions
```

---

## Phase 0 — Inventory and contract (C01–C03)

| Task | Objective | Deliverable | Status |
|---|---|---|---|
| C01 | Repository inventory | `REPO_FINDINGS.md` — 20 numbered §2 items, ABSENT marked | **Done** |
| C02 | Landing page & asset analysis | `LANDING_ANALYSIS.md` — typography/colour/motion/hover inventories, `lightNoWatermark` measured, translation table applied | **Done** |
| C03 | API contract reconciliation | `API_MISMATCHES.md` — 24 mismatches (M-01…M-24), 10 observations (O-01…O-10), backed by `tools/probe_api.py` → `API_PROBE.json` | **Done** |

Notable C01 finding: the old Flutter frontend was **never tracked in git**, so
`pre-redesign-frontend` preserves the landing page only. `REMOVED_FILES.md` is
the sole record of what was deleted.

## Phase 1 — Safety and skeleton (C04)

| Task | Objective | Status | Notes |
|---|---|---|---|
| C04 | Tag, branch, delete old UI, scaffold new `lib/` | **Done** | Tag `pre-redesign-frontend`, branch `frontend-redesign`, 53 Dart files removed per the §3 matrix, platform folders preserved, `ios/` generated (FD-14) |

## Phase 2 — Design system (C05–C08)

| Task | Objective | Status | Notes |
|---|---|---|---|
| C05 | Dependencies, fonts, assets | **Done** | Cormorant Garamond / Inter / JetBrains Mono as local static TTFs; `lucide_icons_flutter` substituted for the dart2js-breaking `lucide_icons` (FD-01) |
| C06 | Design tokens §7.1–7.5 | **Done** | `app_colors/typography/spacing/radii/shadows`; three token values differ from the §7.1 estimates after sampling `appTheme.jpg` — logged in `DESIGN_TOKENS.md` + FD-09; `/galleries/tokens` renders every token |
| C07 | `ThemeData` assembly | **Done** | Light only, no splash, fade-through page transitions, full component-theme coverage |
| C08 | Core primitives §7.6 | **Done** | `CircleIconButton, PrimaryPillButton, SectionHeader, StatusPill, ConfidenceBadge, ProgressRing, ProgressBar, SurfaceCard, AddRow, AvatarStack, PageDots` |

## Phase 3 — Shell, data and shared states (C09–C14)

| Task | Objective | Status | Notes |
|---|---|---|---|
| C09 | go_router + `ShellRoute` + `BottomNav` | **Done** | `Home · Patients · Records · Memory`; `activePatientProvider` persisted; 21 named routes |
| C10 | Composite components | **Done** | 19 composites incl. `TicketCard` with a custom clipper for the concave green band and dashed divider — **no fake QR** (§6.3) |
| C11 | `ApiClient` + config | **Done** | Envelope parser, `ApiException`, §11.4 error map, runtime base URL + demo flag, GET-only single retry. 8 unit tests with a stub dio adapter |
| C12 | Models | **Done** | 10 model files; every `fromJson` tolerant of missing fields; fixtures in `test/fixtures/` captured from **real** responses by `tools/capture_fixtures.py` |
| C13 | Repositories & providers | **Done** | 11 repositories, `AsyncSlice<T>` for every feature, invalidation after mutations |
| C14 | Shared states | **Done** | Skeletons, `EmptyState`, `ErrorState`, snackbars, reveal/press helpers — all honouring reduce-motion |

## Phase 4 — Backend gap-fill and demo data (C35–C36)

| Task | Objective | Status | Notes |
|---|---|---|---|
| C35 | Add only genuinely missing endpoints | **Done — nothing added** | C03 found **no true gap**. Every screen the plan asks for has an endpoint; the differences were field-level, and were absorbed by the models. Mismatches are catalogued with "Open (backend)" markers rather than silently patched |
| C36 | Demo seed + deterministic fallback | **Done** | Backend seed reused as-is; `assets/demo/*.json` holds 14 captured responses; Demo mode serves them tagged `Demo data`; specialty catalogue falls back to a bundled mirror of the backend's seed rows |

## Phase 5 — Screens (C15–C34)

All 20 §9 screens built. Each acceptance criterion met against live data.

| Task | §9 screen | Status | Acceptance evidence |
|---|---|---|---|
| C15 | 9.1 Home | **Done** | All 12 §6.1 elements present — see `QA/README.md` |
| C16 | 9.2 Patient list & create | **Done** | Create persists, search debounced, row sets active patient |
| C17 | 9.3 Patient Overview | **Done** | All 7 §6.1 elements; 4 `PillTabs` each loading independently |
| C18 | 9.4 Documents & upload | **Done** | Multipart upload with progress; type/date/confidence/status shown; process button works |
| C19 | 9.5 Processing | **Done** | Polls `/status` every 1.5 s through the backend's real stage names; failure shows typed error + retry |
| C20 | 9.19 Camera | **Done** | Capture → preview → use → upload → processing; permission-denied state |
| C21 | 9.20 Voice | **Done** | Record → upload → transcript → facts flagged needs-verification; permission and STT-failure states |
| C22 | 9.6 Evidence | **Done** | Fact chip → document/page/quote with highlight + confidence; missing-source state |
| C23 | 9.7 Timeline | **Done** | Chronological, `undated` grouped at the end, evidence links |
| C24 | 9.8 Medications | **Done** | Status tabs; changed/conflict/uncertain tags; no resolution wording anywhere |
| C25 | 9.9 Medication reconciliation | **Done** | `TicketCard` side-by-side matches the reference boarding-pass structure; both source docs linked (M-02 workaround) |
| C26 | 9.10 Investigations | **Done** | Latest value per test with flags |
| C27 | 9.11 Lab trends | **Done** | Chart styled to §7; single-value and empty states |
| C28 | 9.12 Issues | **Done** | Acknowledge/dismiss; unknown-id 500 mapped to a refresh prompt (M-06) |
| C29 | 9.13 Specialty | **Done** | Catalogue fetched from `/specialties`; selection persists and is sent with the brief request |
| C30 | 9.14 Brief | **Done** | All sections from the API; evidence chip per statement; staged loading; disclaimer always visible |
| C31 | 9.15 Consultation editor | **Done** | Draft from brief; edit/remove/flag; Assessment + Plan empty by default; version saved; unsaved guard |
| C32 | 9.16 Version history | **Done** | Origins and change summaries from `consultation_versions` |
| C33 | 9.17 Approval | **Done** | Validation preview first; blocked-state UX; success state |
| C34 | 9.18 Clinical memory | **Done** | Verified memory + history; overview refreshes after approval |

## Phase 6 — Motion, QA and cleanup (C37–C39)

| Task | Objective | Status | Notes |
|---|---|---|---|
| C37 | Motion & ambient pass | **Done** | Ambient layer on Home/Brief/Approval; hero parallax clamped to ≤ 0.25; all §7.9 primitives in place, including `LineReveal` — the landing page's masked line-by-line hero wipe (1100 ms `easeOutExpo`, 90 ms stagger); reduce-motion honoured **including the video** (the landing page does not do this); video paused when backgrounded and disposed on leave. FD-04/FD-05/FD-06 record the three judgement calls |
| C38 | E2E walkthrough & visual QA | **Done** | Full 18-step clinical flow walked on live demo data; 21 routes captured with 0 exceptions; §6.1 inventory mapped element-by-element in `QA/README.md` |
| C39 | Cleanup & documentation | **Done** | This directory; `flutter analyze` clean; every colour/type/spacing value traceable to a token file |

---

## Backend alignment pass (after C39)

The user asked for the backend to fit the rebuilt dashboard and to work
reliably. Plan §4 had forbidden backend edits during the frontend rebuild, so
this was a separate, explicitly requested pass. Every change is **additive or a
bug fix**, and each is pinned by `tests/test_api_contract.py` (38 new tests).

### Reliability

| Change | Why |
|---|---|
| Schema created on boot (`ensure_schema`) | No `create_all` existed anywhere, so a fresh clone had 17 missing tables and every endpoint 500'd. Additive only. **O-01** |
| `pool_pre_ping` + SQLite busy `timeout: 30` + `synchronous=NORMAL` | A writer racing a reader raised `database is locked` immediately instead of waiting |
| `get_db_context` rolls back on exception | A failed recompute left a half-applied transaction for the next reader |
| Unhandled exceptions logged with the request id | Failures inside `call_next` never reached the handlers, so they were invisible |
| Uncaught handler logs the cause, keeps the response generic | §6.6 rule 7 — real cause in the log, nothing internal to the client |
| `/health` no longer touches the DB | A liveness probe that queries the DB restarts a healthy server when the DB is briefly locked |
| `/health/deep` reports `schema_complete`, answers 503 | Readiness must be actionable from the status code |
| Seed works from any directory | `FIXTURES_DIR` was CWD-relative, so seeding only worked from the repo root |
| Seed creates the schema itself | It died on `no such table: patients` on a fresh database unless the server had been booted first |
| Tests use their own database | The suite ran against the dev `clinsync.db` and left ~50 junk patients per few runs, which pushed the demo patient off page 1 of `GET /patients` — the Home screen then showed test fixtures and looked like a frontend bug. Now redirected to a temp DB via `tests/conftest.py`. |
| `path_normalization_middleware` removed | It collapsed `/api/v1/api/v1` → `/api/v1`, hiding a real client bug (the base URL *and* every path carried the prefix) from the analyser, the tests and the network tab. With the client fixed, a wrong base URL should 404 loudly. |
| Seed purge rewritten as ordered bulk deletes | Per-row deletes raced the FK cascade and emitted an `SAWarning` every run |
| `--reset` no longer pretends to be optional | `reset=args.reset or True` could never be false; the CLI now logs its destructiveness |
| STT walks its configured chain | `STT_PRIMARY`/`STT_FALLBACK_*` were never read and the default primary was a text-only model, so every recording degraded to a placeholder transcript. **O-07 / M-22** |
| Extraction and classification fall back on an *empty* LLM result | A gateway that exhausted its providers could still return a schema-valid empty object, silently yielding no facts |
| Date-conflict filter fixed (`Document.patient_id`) | It matched nothing, so the detector never ran. Fixing it exposed a naive-vs-aware datetime `TypeError` the broken filter had been hiding. **O-02** |

### Contract

| Change | Mismatch |
|---|---|
| All 18 patient-scoped routes 404 for an unknown patient | **M-17** |
| `PATCH /issues/{id}` → 404 `ISSUE_NOT_FOUND` instead of 500 | **M-06** |
| Medication list carries `group_key`, `start_date`, `stop_date` | **M-07** |
| Brief `contradictions[].sources` populated from `detail_json` | **M-02** |
| Brief `meta.source` reports `fallback`, and every read path carries `generation_source` | **M-01** |
| `readiness_score` derived from the brief, not a hardcoded `92` | **M-18** |
| Specialty `other` labelled `Other` on both sides | **M-09** |
| Medication doses no longer render as `500 mg · 500.0mg` | display defect found via screenshot |
| Error bodies never leak internals | **M-21** (verified; still open for structured field errors) |
| A validation outage is 503 `VALIDATION_UNAVAILABLE`, not 422 `GATE1_BLOCKED` | **M-25** |

### Client follow-through

The brief header now reads **"From records"** rather than "AI-generated" when
the backend reports the deterministic template served the request — claiming a
model wrote it when it did not is precisely the unverified claim §6.6 forbids.
The Approval screen also separates a validation outage from a blocked note: one
reads "try again in a moment", the other "these items need your review".

### Still open

M-12 (no document thumbnails), M-14 (seeded brief's fake evidence ids), M-16 (no
voice-history endpoint), M-21 (empty `error.details`), plus O-04…O-06, O-09,
O-10. Each is cosmetic or additive, has a screen-level workaround, and is
documented in `API_MISMATCHES.md`.

### Known limitation, deliberately not "fixed"

The **LLM path for brief generation does not currently succeed** — Gemini
rate-limits, and the Groq model's JSON fails `DoctorBrief` schema validation on
both attempts, so every brief is served by the deterministic template. That
path degrades safely and now *says so* in both the envelope and the UI. Making
the model schema-compliant is prompt work with its own regression risk, so it is
recorded rather than attempted here.

---

## Verification record

### Tests — 127 Flutter + 61 backend, all passing

| Suite | Tests | Covers |
|---|---|---|
| `test/models_test.dart` | 45 | tolerant parsing, all five date formats, enum wire mapping, conflict-source extraction, specialty catalogue, brief provenance |
| `test/design_system_test.dart` | 25 | token values, `ThemeData`, icon table size, families, §11.4 copy including outage vs block |
| `test/components_test.dart` | 49 | §7.6 primitives and §7.10 composites, §6.6 copy rules, token discipline, §6.5 imagery rules, `LineReveal` timing and reduce-motion |
| `test/api_client_test.dart` | 8 | envelope unwrapping, error mapping, traceback suppression, GET-retries-once vs POST-never-retried |
| `tests/test_api_contract.py` (backend) | 38 | 404s for unknown patients and issues, `group_key`, honest `meta.source`, brief provenance on read-back, outage-vs-block signalling, both conflict sources, derived readiness score, non-duplicated doses, liveness vs readiness, schema self-healing and additivity, no internals in error bodies |
| backend suite (pre-existing) | 23 | seed, demo flow, validation gates, brief, consultations, documents, voice, routes. The Gate 1 approval test **skips with a reason** when the external judge is rate-limited, rather than reporting a false regression |

### Screenshots

21/21 routes captured, **0 Dart/JS console exceptions**. Re-run with
`.venv/bin/python tools/capture_screens.py`.

### Tools written for this work

| Tool | Purpose |
|---|---|
| `tools/probe_api.py` | Calls every endpoint the app uses; writes `API_PROBE.json` + a status table. The evidence behind `API_MISMATCHES.md` |
| `tools/capture_fixtures.py` | Saves real backend responses into `test/fixtures/` and `assets/demo/` |
| `tools/capture_screens.py` | Route→screenshot harness; fails on any console exception |
| `tools/capture_hero_frames.py` | Films the Home hero reveal frame by frame; pair with `--dart-define=CLINSYNC_MOTION_SCALE` |
| `tools/serve_web.py` | SPA-fallback static server for `build/web` (plain `http.server` 404s deep links) |
| `tools/extract_ambient_stills.py` | Regenerates the five ambient stills from the landing page's own loops via a sage duotone ramp (FD-05) |
| `tools/fix_curly.py` | One-off typographic fixer used while building the copy |

## Known gaps and where they are tracked

| Gap | Tracked as |
|---|---|
| No auth in the backend → no login/profile screens | `DECISIONS.md` FD-13, `API_MISMATCHES.md` M-20 |
| Ambient video does not play on web (platform view) | FD-04 |
| No first-page document thumbnails (no bulk page endpoint) | M-12 |
| No voice-note history list (no GET endpoint) | M-16 |
| Backend emits no `meta.source == "fallback"` | M-01 |
| ~14 backend fixes that would remove workarounds | M-01…M-07, M-14, M-17, M-21, M-22 + O-01…O-10 |

None of these block the app: each has a screen-level resolution that shows the
truth rather than faking the missing piece.
