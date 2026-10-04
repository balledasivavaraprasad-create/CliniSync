# QA — reference vs implementation

Plan C38: *"produce side-by-side screenshots against the 3 reference screens …
Acceptance: every §6.1 inventory element has a ClinSync counterpart."*

## How these were captured

```bash
flutter build web --release
.venv/bin/python tools/serve_web.py --port 8090 &     # SPA-fallback server
.venv/bin/python tools/capture_screens.py             # → /tmp/ref/shots
```

* Device frame **430 × 932** @ 2× (iPhone 15 Pro Max logical size), headless
  Chrome, `prefers-reduced-motion` **not** forced — the shots show the real
  first-build state including the ambient layer.
* `tools/capture_screens.py` walks all 21 routes and fails loudly on any Dart/JS
  console exception. The current run reports **0 exceptions**.
* Every shot was taken against a **live** backend with the seeded demo patient
  `pat_demo_patient_001` (6 documents, HbA1c 8.4 → 8.0 → 7.8, the metformin
  conflict, approved memory) — no mocked data in these captures.

## Side-by-side mapping — reference screen 1 (Home)

Reference: `appTheme.jpg`, left phone → `QA/clinsync_01_home.png`.

| # | §6.1 element | ClinSync counterpart | Where |
|---|---|---|---|
| 1 | White circular menu button, top-left | `CircleIconButton(icon: 'menu')` — opens the connection/specialty sheet | `home_screen.dart` |
| 2 | Circular avatar, top-right | Monogram tile in `primarySoft` (no people photography, §6.5) | `home_screen.dart` |
| 3 | 3-line serif headline, line 1 black, lines 2–3 green | `Every Record,` / `Clinically` / `Connected.` — `displayHero` at 40/500/1.08, `textPrimary` then `primary` | `AppTypography` |
| 4 | Muted 2-line subtitle | `AI-assisted clinical context,` / `always under your review.` | §6.4 table |
| 5 | Misty hero artwork fading into the background | `AmbientLayer`: duotone still + muted looping ambient video, 0.52 `bgCanvas` wash, `heroFade` at the bottom | `ambient_background.dart` |
| 6 | White pill search overlapping the hero, magnifier left, **solid green circular mic** right | `SearchPill` inside the hero's `Stack(clipBehavior: Clip.none)` so the overhang is real; mic → `/voice/<patientId>` | `home_screen.dart` |
| 7 | Section header + green `See all` | `Recent Patients` + `link`-styled `See all` | `SectionHeader` |
| 8 | Tall rounded image cards bleeding off the right edge, bottom scrim, name + sub, white circular arrow | `PatientCard` — ambient still, `photoScrim`, name + `52 yrs`, `CircleIconButton` arrow. Page dots below (el. 9) | `clin_cards.dart` |
| 9 | Three page dots, middle active green | `PageDots` — active dot `primary` | `primitives.dart` |
| 10 | `Quick Actions` header | Identical string | — |
| 11 | 4 rounded-square icon tiles + label | `Upload Record` / `Scan Document` / `Voice Note` / `Doctor Brief` (§6.4) | `QuickActionTile` |
| 12 | Translucent gradient banner + mascot | `banner` gradient card, `Let AI prepare your consultation` + `Evidence-linked. Reviewed by you. Verified on approval.`, serif `C` monogram (§6.5 forbids inventing a mascot) | `home_screen.dart` |
| — | Bottom nav (absent in the reference) | `Home / Patients / Records / Memory` (§6.4) — required by the shell | `bottom_nav.dart` |

## Side-by-side mapping — reference screen 2 (Itinerary)

Reference: `appTheme.jpg`, middle phone → `QA/clinsync_02_patient_overview.png`
(+ `04_timeline` for the `Day N` rail, `03_medication_reconciliation` for the
boarding-pass card).

| # | §6.1 element | ClinSync counterpart | Where |
|---|---|---|---|
| 1 | Circular back + centred serif title + bookmark + more | `TopBar` — circular back, `titleScreen` serif title, bookmark + overflow circles | `primitives.dart` |
| 2 | Header block: name, meta line, avatar stack `+2`, thumbnail | Patient name `titleHeader` serif, `52 yrs • General Medicine • 6d ago`, `6 records` chip, `Memory approved` pill, document-type glyph chips `+6`, rounded thumbnail | `patient_overview_screen.dart` |
| 3 | **AI card**: green check, `AI Route Optimized`, two grey meta lines, mini map, chevron, inner strip with 3 outline-icon stats | `Clinical Context Ready` + `3 open` pill, `Evidence-linked • Source-traceable` / `Unverified until approved`, dotted-route glyph pair, chevron, inner `surfaceTint` strip: `Documents 6` · `Clinical Facts 16` · `Open Issues 3` | `InsightCard` |
| 4 | Pill tabs `Itinerary / Transport / Stay / Recommendations` | `PillTabs`: `Timeline / Medications / Investigations / Issues` | `primitives.dart` |
| 5 | Day rail: `Day` over green numbered circle + dotted line; white day cards with icon, title, chevron, 2 bullets, thumbnail | `TimelineRail` — `SEP` over a green day circle, dotted connector; `TimelineCard` with type icon, title, 2 bullet lines, `flaskConical`/`fileText` thumbnail | `clin_cards.dart` |
| 6 | `+ Add Activity` row | `+ Add Record` (§6.4) | `timeline_screen.dart` |
| 7 | Sticky bottom bar: green pill + white circular filter | `StickyActionBar`: `Generate Brief` + circular actions rail icon | `primitives.dart` |

## Side-by-side mapping — reference screen 3 (Trip / bookings)

Reference: `appTheme.jpg`, right phone → `QA/clinsync_03_medication_reconciliation.png`.

| # | §6.1 element | ClinSync counterpart | Where |
|---|---|---|---|
| 1 | Back + title + grey sub-line + bell + more | `Metformin` + `15 Feb – 12 Sep 2026` (a real `AppDate.range()` from the API) | — |
| 2 | **Boarding-pass card**: green header band, `BOARDING PASS`, `On Time` pill, white body, dotted centre line with plane, dashed divider, label-over-value row, QR | `MEDICATION CHANGE` `capsLabel` on a `primary`/`primaryMuted` band, `Conflict` pill, then **Source A / Source B side by side** — `BD` `1000 mg` `12 Sep` vs `BD` `500 mg` `12 Sep`, dotted divider, `Drug / Strength / Records` label-over-value cells, and a document-glyph **Evidence** tile (§6.3: never a fake QR) | `reconciliation_screen.dart` |
| 3 | Row card: thumbnail + grey label + bold title + grey meta + chevron | `Source records` rows: date + `BD`, filename, `1000 mg · twice daily`, chevron | — |
| 4 | Two side-by-side cards (weather, progress ring) | `Documents / Clinical Facts / Open Issues` stat strip; the Issues tab renders `ProgressRingCard` from real review progress | — |
| 5 | Packing checklist card: title, `7 of 10 packed`, thin green progress bar, two-column checks | `Clinician review` `ChecklistCard` — `0 of 3 done`, green progress track, checkbox rows | `ChecklistCard` |
| 6 | Large green pill + white circular share | `View Evidence` + circular export | `StickyActionBar` |
| 7 | Floating bottom nav, active item green | `Home / Patients / Records / Memory` | `bottom_nav.dart` |

## Deviations from the reference, and why

Recorded in full in `DECISIONS.md`; the visual ones worth repeating here:

| Deviation | Reason |
|---|---|
| Hero artwork is a chrome-ribbon ambient loop, not a misty destination landscape | §6.5: the hero ambient must come from `lightNoWatermark`. Layout, headline position, search-pill overhang and fade are unchanged. |
| Patient cards use abstract tinted stills, not photographs | §6.5: no patient photography exists and none may be invented. |
| `BD` / HbA1c values replace `CGK` / `26°` | §6.4 text-replacement table. |
| Robot mascot → serif `C` monogram | §6.5: use a repo logo if one exists, otherwise a plain mark. |
| The `Demo Patient` avatar and card thumbnails are stills, not faces | §6.5 + a test that fails if a photograph is ever referenced from `lib/`. |

## Full route coverage

`tools/capture_screens.py` captures all 21 routes; the five QA files kept in this
directory are the ones that correspond to the three reference screens.

| # | Route | Shot |
|---|---|---|
| 1 | `/home` | `clinsync_01_home.png` |
| 2 | `/patients` | — |
| 3 | `/patients/<id>` | `clinsync_02_patient_overview.png` |
| 4 | `/patients/<id>/documents` | — |
| 5 | `/patients/<id>/timeline` | `clinsync_04_timeline.png` |
| 6 | `/patients/<id>/medications` | — |
| 7 | `/patients/<id>/investigations` | — |
| 8 | `/patients/<id>/issues` | `clinsync_06_review_queue.png` |
| 9 | `/patients/<id>/facts` | — |
| 10 | `/patients/<id>/medications/metformin/reconcile` | `clinsync_03_medication_reconciliation.png` |
| 11 | `/patients/<id>/investigations/<id>:hba1c/trend` | — |
| 12 | `/specialty` | — |
| 13 | `/patients/<id>/brief` | `clinsync_05_doctor_brief.png` |
| 14 | `/patients/<id>/consultation` | — |
| 15 | `/patients/<id>/memory` | — |
| 16–17 | `/records`, `/memory` (shell tabs) | — |
| 18–19 | `/galleries/tokens`, `/galleries/components` | — |
| 20–21 | `/camera/<id>`, `/voice/<id>` | — |

Regenerate with the commands at the top of this file; the full set lands in
`/tmp/ref/shots/` and can be copied in as needed.
