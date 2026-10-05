# ClinSync Flutter frontend

The Flutter app. Start with the [run guide](#running-it) below.

## Layering (plan §0)

```
screens/widgets  →  providers (Riverpod)  →  repositories  →  ApiClient (dio)  →  backend
```

Screens never import `ApiClient`. `AsyncSlice<T>` in
`lib/features/state/feature_providers.dart` is the only state shape screens see.

## Layout

| Path | Contents |
|---|---|
| `lib/core/theme/` | design tokens — colours, type, spacing, radii, shadows, `ThemeData` |
| `lib/core/animations/` | §7.9 motion primitives + page transitions |
| `lib/core/models/` | one file per aggregate; every `fromJson` is tolerant of missing fields |
| `lib/core/repositories/` | one repository per endpoint family + the offline demo store |
| `lib/core/networking/` | dio client, `ApiException`, §11.4 error-message map |
| `lib/core/config/` | base-URL resolution; nothing is hardcoded |
| `lib/shared/widgets/` | §7.6 primitives (buttons, pills, tabs, sheets, icons) |
| `lib/shared/cards/` | composite cards (Patient, Ticket, Evidence, Checklist, Ambient) |
| `lib/features/` | one directory per §9 screen area |
| `lib/dev/` | token + component galleries (`/galleries/*`) |
| `test/` | 127 Flutter tests across models, design system, components, API client |
| `tools/` | backend probes, fixture capture, screenshot harness, ambient-still generator |

## Docs

| File | Contents |
|---|---|
| `REPO_FINDINGS.md` | C01 inventory of the repo as found, including what was ABSENT |
| `LANDING_ANALYSIS.md` | C02 analysis of `index.html` / `style.css` / `main.js` |
| `API_MISMATCHES.md` | C03 contract differences and how each is resolved |
| `DESIGN_TOKENS.md` | C06 final token values + the `appTheme.jpg` sampling log |
| `DECISIONS.md` | every deviation, with reasons and costs |
| `PROGRESS.md` | task-by-task status against the C01–C39 graph |
| `REMOVED_FILES.md` | every file deleted by C04, with the disposition rule applied |
| `QA/` | reference-vs-implementation mapping and screenshots |
| `API_PROBE.json` | machine-readable dump of every endpoint's real payload shape |
| `../tests/test_api_contract.py` | backend contract tests the app depends on |
| `../tests/conftest.py` | points the suite at a temp database, never the dev one |
| `check_link.py` | drives the built app in Chrome and fails if any API call errors |

## Running it

```bash
# 1. backend
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. app
flutter run                                    # device/emulator
flutter run --dart-define=CLINSYNC_API_BASE_URL=http://192.168.1.10:8000   # physical device
flutter build web --release
```

The base URL can also be changed at runtime from **Home → menu**, which shows
the platform-appropriate hints. See the run guide in the repository README.
