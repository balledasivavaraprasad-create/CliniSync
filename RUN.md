# Running ClinSync

Three things live in this repository: a **FastAPI backend**, a **Flutter app**
(mobile + desktop + web), and a **static marketing landing page** at `index.html`.
`readme.md` is the product brief; this file is the run guide.

---

## 1. Backend

```bash
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

* Interactive API docs: <http://127.0.0.1:8000/docs> (there is **no** `/api/docs`).
* Health: `curl http://127.0.0.1:8000/health`
* Every response uses the envelope `{success, data, meta}`; errors use
  `{success, false, error: {code, message, details}, meta}`.

Configuration comes from `.env` in the repository root (pydantic-settings).

### Seed the demo patient

```bash
PYTHONPATH=backend .venv/bin/python -m app.db.seed --reset
```

Creates `pat_demo_patient_001` ("Demo Patient", 52) with 6 documents, 7 lab
results (HbA1c 8.4 → 8.0 → 7.8), 4 medications including the **deliberate
conflict** (metformin 1000 mg BD vs 500 mg BD), a seeded brief, an approved
consultation and 2 verified memory rows. Re-running is safe.

> Two backend caveats worth knowing: the schema is **not** created by any
> migration or `create_all`, so a fresh clone needs the tables created once
> before the API can answer; and `--reset` is currently always on regardless of
> the flag. Both are recorded in `docs/frontend/REPO_FINDINGS.md` §12 and
> `API_MISMATCHES.md` O-01/O-03.

### Backend tests

```bash
PYTHONPATH=backend .venv/bin/python -m pytest tests/ -q     # 23 passed
```

---

## 2. Flutter app

```bash
flutter pub get
flutter run
```

The API base URL is **never hardcoded**. It resolves in this order:

1. a value you set at runtime (**Home → menu**, persisted with
   `shared_preferences`);
2. `--dart-define=CLINSYNC_API_BASE_URL=…`;
3. a platform-aware default.

| Target | Default origin |
|---|---|
| Android emulator | `http://10.0.2.2:8000` |
| iOS simulator / macOS / desktop | `http://127.0.0.1:8000` |
| Web | `http://localhost:8000` |

Point it somewhere else at build time:

```bash
flutter run --dart-define=CLINSYNC_API_BASE_URL=http://192.168.1.10:8000
flutter build apk --release --dart-define=CLINSYNC_API_BASE_URL=http://192.168.1.10:8000
```

The menu sheet also lists those hints as one-tap presets. `/api/v1` is appended
automatically, so both `host:port` and a full `http://host:port` work.

### Demo mode

Toggle **Demo mode** in the same menu sheet. When the backend is unreachable,
repositories serve the bundled fictional payloads in `assets/demo/` and tag every
card `Demo data`, so the full clinical flow is walkable with no server at all.
With the toggle off, an unreachable backend produces a retry state instead.

### Camera and microphone

Both are requested at runtime and both screens degrade to their own
denied-state, so neither permission is required for the app to run. Declarations
are in place for every platform: `CAMERA`, `RECORD_AUDIO`, `READ_MEDIA_IMAGES`,
`READ_EXTERNAL_STORAGE`, `READ_MEDIA_DOCUMENTS` and non-required
`<uses-feature>` entries on Android; `NSCameraUsageDescription`,
`NSMicrophoneUsageDescription`, `NSPhotoLibraryUsageDescription` on iOS and
macOS, plus the matching `permission_handler` macros in `ios/Podfile`.

Plain-http development against `127.0.0.1`/`10.0.2.2`/LAN is permitted on all
three platforms (`usesCleartextTraffic` on Android, `NSAllowsLocalNetworking` on
Apple). Public hosts still require https.

### Web

```bash
flutter build web --release
.venv/bin/python tools/serve_web.py --port 8090
```

**Deep links need an SPA fallback.** `flutter build web` uses Flutter's default
*hash* URL strategy, so routes are `/#/patients/<id>` and any static host works
with zero configuration. `tools/serve_web.py` adds the `index.html` fallback
anyway, so it also works if you switch to path-based URLs later. Plain
`python -m http.server` will **not** serve deep links.

Two web-specific notes: the ambient video layer is skipped on web (a
`video_player` platform view composites above the Flutter canvas and would paint
over the search pill — see `docs/frontend/DECISIONS.md` FD-04), and the still
that replaces it is a frame of the same loop, so the transition is invisible on
mobile.

---

## 3. Quality gates

```bash
flutter analyze      # No issues found!
flutter test         # 112 tests, All tests passed!
```

Design-system discipline is enforced by tests rather than convention: raw colour
literals, raw font families and ad-hoc text styles outside `lib/core/theme/`
fail the suite, as does any reference to a photograph of a person.

## 4. Documentation

| Path | Contents |
|---|---|
| `readme.md` | the product brief |
| `RUN.md` | this file |
| `implementation.md` | the governing frontend specification |
| `docs/frontend/` | inventory, landing analysis, API mismatches, design tokens, decisions, progress, QA |
| `docs/` | backend phase documents from the previous build |
