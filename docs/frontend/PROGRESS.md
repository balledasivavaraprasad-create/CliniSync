# Frontend build progress

Task graph C01–C39 from `implementation.md` §16. **All 39 tasks complete.**
Branch `frontend-redesign` · safety tag `pre-redesign-frontend`.

Verification gate for every task, per §0.2 rule 9:

```bash
flutter analyze     # No issues found!
flutter test        # 112 tests, All tests passed!
flutter build web --release
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
| C04 | Tag, branch, delete old UI, scaffold new `lib/` | **Done** | Tag `pre-redesign-frontend`, branch `frontend-redesign`, 53 Dart files removed per the §3 matrix, platform folders preserved, `ios/` generated (FD-13) |

## Phase 2 — Design system (C05–C08)

| Task | Objective | Status | Notes |
|---|---|---|---|
| C05 | Dependencies, fonts, assets | **Done** | Cormorant Garamond / Inter / JetBrains Mono as local static TTFs; `lucide_icons_flutter` substituted for the dart2js-breaking `lucide_icons` (FD-01) |
| C06 | Design tokens §7.1–7.5 | **Done** | `app_colors/typography/spacing/radii/shadows`; three token values differ from the §7.1 estimates after sampling `appTheme.jpg` — logged in `DESIGN_TOKENS.md` + FD-08; `/galleries/tokens` renders every token |
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
| C37 | Motion & ambient pass | **Done** | Ambient layer on Home/Brief/Approval; hero parallax clamped to ≤ 0.25; all §7.9 primitives in place; reduce-motion honoured **including the video** (the landing page does not do this); video paused when backgrounded and disposed on leave. FD-04/FD-05/FD-06 record the three judgement calls |
| C38 | E2E walkthrough & visual QA | **Done** | Full 18-step clinical flow walked on live demo data; 21 routes captured with 0 exceptions; §6.1 inventory mapped element-by-element in `QA/README.md` |
| C39 | Cleanup & documentation | **Done** | This directory; `flutter analyze` clean; every colour/type/spacing value traceable to a token file |

---

## Verification record

### Tests — 112 passing

| Suite | Tests | Covers |
|---|---|---|
| `test/models_test.dart` | 42 | every model's tolerant parsing, all five date formats, enum wire mapping, conflict-source extraction, specialty catalogue |
| `test/design_system_test.dart` | 24 | token values, `ThemeData`, icon table size, families |
| `test/components_test.dart` | 42 | §7.6 primitives and §7.10 composites render, §6.6 copy rules, token discipline, §6.5 imagery rules |
| `test/api_client_test.dart` | 8 | envelope unwrapping, error mapping, traceback suppression, GET-retries-once vs POST-never-retried |

### Screenshots

21/21 routes captured, **0 Dart/JS console exceptions**. Re-run with
`.venv/bin/python tools/capture_screens.py`.

### Tools written for this work

| Tool | Purpose |
|---|---|
| `tools/probe_api.py` | Calls every endpoint the app uses; writes `API_PROBE.json` + a status table. The evidence behind `API_MISMATCHES.md` |
| `tools/capture_fixtures.py` | Saves real backend responses into `test/fixtures/` and `assets/demo/` |
| `tools/capture_screens.py` | Route→screenshot harness; fails on any console exception |
| `tools/serve_web.py` | SPA-fallback static server for `build/web` (plain `http.server` 404s deep links) |
| `tools/extract_ambient_stills.py` | Regenerates the five ambient stills from the landing page's own loops via a sage duotone ramp (FD-05) |
| `tools/fix_curly.py` | One-off typographic fixer used while building the copy |

## Known gaps and where they are tracked

| Gap | Tracked as |
|---|---|
| No auth in the backend → no login/profile screens | `DECISIONS.md` FD-12, `API_MISMATCHES.md` M-20 |
| Ambient video does not play on web (platform view) | FD-04 |
| No first-page document thumbnails (no bulk page endpoint) | M-12 |
| No voice-note history list (no GET endpoint) | M-16 |
| Backend emits no `meta.source == "fallback"` | M-01 |
| ~14 backend fixes that would remove workarounds | M-01…M-07, M-14, M-17, M-21, M-22 + O-01…O-10 |

None of these block the app: each has a screen-level resolution that shows the
truth rather than faking the missing piece.
