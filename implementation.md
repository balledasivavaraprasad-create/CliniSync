# CLINSYNC — FRONTEND IMPLEMENTATION PLAN

> **Audience:** Antigravity (coding agent). **Owner:** Developer C.
> **Product name:** **ClinSync** (never "ClinicSync" in UI text, code identifiers, or docs).
> **Companion files:** `reference.jpg` (the 3-screen UI reference image, attached by the owner) and `audit.md` (backend spec). The reference image is the **visual source of truth**.
> **This document is a plan. Do not treat any "Current repository findings" as known fact: the author of this plan had NO access to the repository.** Every repo-dependent statement is marked `[VERIFY]` and is resolved in Phase 0 by inspection.

---

## 0. READ THIS FIRST — RULES OF ENGAGEMENT

### 0.1 Mission
Build the entire ClinSync mobile frontend **from scratch** in Flutter so that it **replicates the design in the reference image exactly** (layout, components, shapes, spacing rhythm, typography style, colour language, iconography style, motion feel), while changing **only content**: text, images, data, and screen purposes — translated into ClinSync's clinical domain. The old frontend UI is removed. Backend intelligence (Developer A and B logic) is **reused, not rewritten**.

### 0.2 Hard rules
1. **Do not redesign.** If the reference image shows a component, build that component with the same structure. Only labels, icons' meaning, images, and data change.
2. **Do not hallucinate.** Report only what you actually find in the repo. If something is absent, write "absent" in the findings doc. Never invent files, endpoints, assets, or landing-page effects.
3. **Do not write to the repo during Phase 0.** Phase 0 tasks (C01–C03) are read-only except for new docs under `docs/frontend/`.
4. **No login, no authentication, no profile/account screens.** The prototype is single-user.
5. **Clinical safety UI rules (non-negotiable, see §6.6):** AI content is always labelled as unverified until doctor approval; the UI never presents a "correct" dose when sources conflict; confidence is always visible; evidence is always one tap away; a persistent AI/clinical disclaimer exists.
6. **Do not modify backend A/B intelligence logic.** Backend changes are limited to contract gap-filling (Task C34) and seed/fallback wiring (C35), and must follow `audit.md` §8 or the repo's existing contract if one exists.
7. **Never hardcode** API base URL, keys, or demo flags. Use a config layer (C11).
8. **Verify package versions** with `flutter pub add <pkg>` at install time. Do not paste version numbers from memory.
9. Every task ends with: `flutter analyze` clean, app launches, task acceptance criteria met, `docs/frontend/PROGRESS.md` updated.
10. **Image-vs-landing-page conflicts:** the reference image wins for layout, component structure, shapes, and the tokens in §7. Landing-page fonts/colours may be adopted only if the landing page actually uses them **and** they are visually compatible; log every deviation in `docs/frontend/DECISIONS.md`.

### 0.3 Priority order (hackathon)
Working app > integration > mandatory functionality > reliability > visual polish > architecture perfection.
Polish tasks (motion pass, ambient video) come **after** the end-to-end flow works, but the design tokens and shared components are built **first** so nothing needs restyling later.

---

## 1. EXECUTIVE ARCHITECTURE

```text
Flutter (UI, state, navigation, camera/voice capture)
   │  REST /api/v1  (JSON envelope: {success, data, meta} | {success:false, error})
FastAPI (existing; gaps filled only where UI needs them)
   ├─ Developer B: OCR → classify → extract → evidence → confidence
   ├─ Persistence: SQLite/SQLAlchemy + local filesystem
   └─ Developer A: timeline, reconciliation, lab trends, contradictions, missing info, brief, memory
```

Data/integrity chain the UI must always make visible:
`Source → Evidence → Clinical Fact → Clinical Object → Synthesis → Doctor Review → Verification`

Frontend layers: **Presentation (screens/widgets) → State (providers) → Repositories → API client → Backend.** Screens never call the API client directly.

---

## 2. CURRENT REPOSITORY FINDINGS — TO BE FILLED BY ANTIGRAVITY (Phase 0)

> Create `docs/frontend/REPO_FINDINGS.md` with the sections below. **Only record what you see.** Use "ABSENT" when something does not exist.

| # | Inspect | Record |
|---|---|---|
| 1 | Flutter project root, `pubspec.yaml`, SDK constraints, platforms present (android/ios) | Paths, Dart/Flutter versions, dependency list |
| 2 | Existing screens | File list + one-line purpose each |
| 3 | Routing approach (Navigator 1/2, go_router, other) | Where defined |
| 4 | Existing widgets | File list, reuse candidates |
| 5 | Existing theme | Colors/fonts/ThemeData location |
| 6 | Networking layer | HTTP package, base URL handling, error handling |
| 7 | Existing models | List + whether they match backend JSON |
| 8 | State management | Provider/Riverpod/Bloc/setState |
| 9 | FastAPI app | `main.py`, router list, CORS, run command |
| 10 | Existing API routes | Full table: method, path, request, response |
| 11 | SQLAlchemy models | Tables + columns |
| 12 | DB setup | URL, creation/migrations, seed |
| 13 | Storage | Paths, upload handling |
| 14 | Developer A code | Module paths, public function signatures, inputs/outputs |
| 15 | Developer B code | Module paths, public function signatures, inputs/outputs |
| 16 | Demo data | Seed script/fixtures, which patient, which documents |
| 17 | Fallback logic | Where AI failure falls back, what it returns |
| 18 | Landing page | Framework, file paths, entry point |
| 19 | `lightNoWatermark` assets | Exact filenames, formats (mp4/webm/image), resolution, duration, size |
| 20 | Existing animations/transitions | Flutter side and landing side |

Also produce `docs/frontend/API_MISMATCHES.md` (C03): a table of every place where the existing backend contract differs from what the screens in §9 require (field names, missing endpoints, envelope shape, enum values). **Do not "fix" mismatches by inventing a second contract.** Prefer adapting the Flutter models to the existing backend; add backend endpoints only for true gaps.

---

## 3. EXISTING FRONTEND — DISPOSITION RULES

Decision matrix to apply to every old Flutter file after inspection:

| Class | Rule |
|---|---|
| Old screens, old widgets, old theme, old routing | **REMOVE** after the new shell compiles (C04). Keep nothing visual. |
| Networking client / models / repositories that already match the backend contract and are clean | **REUSE** by moving into `core/networking`, `core/models` (restyle nothing, they are non-visual). |
| Networking/models that mismatch the contract or are messy | **REPLACE** (rewrite per §10–§12). |
| Platform folders (`android/`, `ios/`), app id, icons, permissions | **PRESERVE**; add camera/mic/storage permissions. |
| Tests that test removed UI | **REMOVE**; keep tests for reused non-visual code. |

Safety procedure before deleting (C04): `git tag pre-redesign-frontend` and create branch `frontend-redesign`. Deleted files must be listed in `docs/frontend/REMOVED_FILES.md`.

---

## 4. EXISTING FUNCTIONALITY TO PRESERVE (backend)
- All Developer A and B logic (OCR, classification, extraction, evidence, confidence, timeline, medication reconciliation, labs, contradictions, missing info, brief, memory). `[VERIFY]` exact modules.
- Existing DB schema and data (migrate additively only).
- Existing demo data and fallback behaviour (extend, never remove).
- Existing API routes that already satisfy a screen. Do not rename them.

---

## 5. LANDING PAGE ANALYSIS (TO BE PRODUCED IN C02)

> The landing page was not available when this plan was written. Antigravity must analyze the **actual implementation** and write `docs/frontend/LANDING_ANALYSIS.md`. **Report only effects that exist** (read CSS/JS/components; do not infer from screenshots alone).

### 5.1 What to document (each item: "exists / absent" + source file + exact values)
Typography (families, weights, sizes, line-heights, letter-spacing) · font hierarchy · colours (hex) · spacing scale · surfaces · cards · borders · shadows · blur/backdrop-filter · gradients · glow · background effects (incl. `lightNoWatermark` usage: where, how, overlay, opacity, loop/mute) · animations (keyframes, durations, easings) · transitions · scroll effects (reveal, parallax, sticky) · hover/interaction effects · visual hierarchy · component patterns.

### 5.2 Translation rules (apply only to effects that actually exist)
| Landing effect | Mobile translation |
|---|---|
| Hover lift/glow on cards | Press feedback: scale 0.98 + shadow reduction, 120 ms ease-out; release restores |
| Hover underline/colour on links | Pressed colour shift + ripple-less opacity 0.7 |
| Scroll-reveal (fade/translate in) | Staggered section reveal on first build of a screen (fade + 12 px upward translate, 280 ms, 40 ms stagger, play once) |
| Large parallax | Lightweight parallax on hero only (≤ 0.25 factor, driven by scroll offset, disabled when reduce-motion) |
| Cursor-follow / mouse glow | Not translated; replace with touch-down ripple highlight only if it exists on the landing page |
| Sticky nav blur | Sticky top bar with backdrop blur only where the reference shows a floating bar (bottom nav/CTA bar) |
| Page transitions | Shared fade-through / slide-up transitions (see §7.9) |
| Background video | Ambient video layer (see §7.8) |
| Gradient text | Only if present on landing; reference uses solid green + black two-tone serif headline, so default to that |

If an effect is **absent** on the landing page, do not add it.

---

## 6. PRODUCT TRANSLATION: REFERENCE IMAGE → CLINSYNC

### 6.1 The reference image — exhaustive inventory (what exists; replicate structure exactly)

Overall: three phone mockups on a soft sage/pale-green backdrop; each phone has large rounded corners; status bar shows `9:41`, signal, Wi-Fi, battery. App canvas is near-white/warm off-white with white elevated cards.

**Reference Screen 1 — Home**
1. Top-left: white circular button with a "menu" glyph (two horizontal lines, second shorter).
2. Top-right: circular avatar (photo).
3. Hero headline, large **serif**, three lines: `Your Journey,` (near-black) / `Intelligently` (green) / `Planned.` (green).
4. Subtitle in sans, muted: `AI-powered travel planning made effortless.` (two lines).
5. Hero artwork: soft misty illustrated landscape (mountains, lake, boat, pagoda), pale and desaturated, fading into the background; foliage leaves overlap bottom-left and bottom-right corners.
6. Search field: white pill, elevated, overlapping bottom of hero; magnifier icon left; placeholder `Where do you want to go?`; **solid green circular mic button** at the right end.
7. Section header row: `Inspiring Destinations` (left, medium weight) and `See all` (right, green).
8. Horizontal card carousel: three tall rounded image cards (`Bali / Indonesia`, `Kyoto / Japan`, `Swiss Alps / Switzerland`). Each: full-bleed photo, bottom dark gradient, white bold name + smaller subtitle, **white circular arrow button** bottom-right. Cards bleed to the screen edge (third is partially cut).
9. Page indicator: three small dots under the carousel, middle one active (green), others grey.
10. Section header: `Quick Actions`.
11. Four tiles in a row: white rounded-square icon tile (outlined line icons) with label below: `AI Itinerary` (sparkle), `Smart Route` (route/pin), `Budget Plan` (wallet), `Travel Guide` (map).
12. Bottom banner card: translucent pale green-grey gradient, rounded; left sparkle icon; title `Let AI craft your perfect trip`; subtitle `Personalized. Optimized. Unforgettable.`; right: a small robot mascot illustration. (No bottom nav visible on this screen in the image.)

**Reference Screen 2 — Itinerary**
1. Top bar: circular back button · centred title `Your Itinerary` (serif) · circular bookmark button · circular "more" (vertical three dots) button.
2. Header block: `Bali, Indonesia` (serif-ish, medium) with small pencil (edit) icon; metadata line `7 Days • 6 Nights • 12–18 May`; overlapping circular avatar stack (3 photos) + `+2` chip; at right, rounded-corner thumbnail photo (temple).
3. **AI card** (white, elevated, large radius): green filled circle with check; `AI Route Optimized` (green, semibold); two tiny grey lines `Best time to visit • Less travel time` / `Scenic • Budget friendly`; right: mini map illustration with dashed green route and two green pins; chevron `>` at far right. Inside the lower part of the card, a row of three stats with outline icons: `Distance 142 km`, `Est. Cost $1,240`, `CO₂ Saved 18 kg` (leaf icon). Stats sit in a faint inner rounded strip.
4. Tabs: `Itinerary` (selected: filled green pill, white text), `Transport`, `Stay`, `Recommendations` (unselected: plain grey text, no pill).
5. Day timeline: left rail with tiny `Day` label above a **green filled circle containing the number** (1, 2, 3), connected by a thin vertical dotted line. Right: white rounded card per day with a small green line icon + title + circular small chevron button; two bullet lines (dot-separated items); right-aligned rounded thumbnail photo. Items: `Arrive in Bali` (`Airport Pickup • Hotel Check-in`, `Uluwatu Temple • Sunset View`), `Ubud Exploration` (`Tegallalang Rice Terrace`, `Sacred Monkey Forest • Local Market`), `Nusa Penida Escape` (`Diamond Beach • Kelingking Beach`, `Snorkeling Adventure`).
6. `+ Add Activity` row (small circular plus outline icon + text) at the end of the list.
7. Sticky bottom bar (white, soft top fade): large **green pill button** with sparkle icon `Optimize with AI` + separate white circular **sliders/filter** button on the right.

**Reference Screen 3 — Trip (Bookings)**
1. Top bar: circular back · title `Trip to Bali` with grey sub-line `12 – 18 May, 2025` · circular bell button · circular more button.
2. **Boarding-pass card**: green header band (concave rounded transition into the white body) with `BOARDING PASS` (small caps, white, left) and an `On Time` pill (white-outline/translucent) + plane icon (right). White body: left block small caps `JAKARTA`, large bold `CGK`, time `08:40`, date `12 May`; centre: dotted line with green plane icon and `2h 10m` beneath; right block `BALI`, `DPS`, `11:50`, `12 May`. Dashed horizontal divider. Bottom row: `Flight GA-422`, `Gate A12`, `Seat 24A` (grey label above bold value) and a **QR code** at right.
3. Row card: rounded thumbnail left; `Hotel` (grey label), `Kayon Resort Ubud` (bold), `12 – 18 May • 6 Nights` (grey); chevron right.
4. Two equal cards side by side: **Weather in Bali** (`26°` large, partly-cloudy icon, `Partly Cloudy`, `H: 30° L: 23°`) and **Trip Progress** (green circular progress ring with centre icon, `87%` bold, `Completed`).
5. **Packing Checklist** card: title left, `7 of 10 packed` grey right with chevron; thin green progress bar (rounded); checklist items in two columns with green check circles for done (`Travel Documents`, `Camera`) and empty outline circle for not done (`Swimwear`).
6. Bottom actions: large green pill `View E-Ticket` with download icon + white circular share button.
7. **Bottom navigation** (white rounded floating bar): `Home`, `Itinerary`, `Bookings` (active: green filled icon, green label), `Profile` (inactive: grey outline icons, grey labels).

### 6.2 Visual DNA (applies to every ClinSync screen)
Spacious; editorial serif headlines paired with a clean humanist sans; soft sage-tinted neutral background; **white** elevated surfaces; **one** restrained green accent used for primary actions, active states, progress, and emphasis; large radii; very soft diffuse shadows; thin-stroke line icons inside circular or rounded-square white containers; pill-shaped primary CTA; circular secondary buttons; thumbnails with rounded corners; subtle motion.

### 6.3 Concept mapping
| Reference concept | ClinSync concept |
|---|---|
| Destination | Patient |
| Itinerary | Clinical timeline |
| Trip information | Patient context |
| Travel recommendations | Clinical intelligence |
| "Optimize with AI" | Generate 60-Second Doctor Brief |
| Travel details (boarding pass, hotel) | Clinical records / medication reconciliation / source documents |
| Packing checklist | Missing information / review items |
| Trip progress ring | Verification / review progress |
| Trip completion | Consultation → approval |
| Trip memory | Verified clinical memory |
| Weather card | Latest key investigation (e.g., HbA1c) |
| Avatar stack with `+2` | Source-document type chips with `+2` |
| QR code | Evidence/source link tile (do **not** render a fake QR; use a document glyph tile) |

### 6.4 Text replacement table (reference string → ClinSync copy)
> Keep line count and rhythm of each string. Final copy may be tuned; keep tone: calm, clinical, confident.

| Reference | ClinSync |
|---|---|
| `Your Journey,` / `Intelligently` / `Planned.` | `Every Record,` / `Clinically` / `Connected.` |
| `AI-powered travel planning made effortless.` | `AI-assisted clinical context, always under your review.` |
| `Where do you want to go?` | `Search patients, records, medications` |
| `Inspiring Destinations` / `See all` | `Recent Patients` / `See all` |
| Destination cards | Patient cards (§9 Home) |
| `Quick Actions` | `Quick Actions` |
| `AI Itinerary` / `Smart Route` / `Budget Plan` / `Travel Guide` | `Upload Record` / `Scan Document` / `Voice Note` / `Doctor Brief` |
| `Let AI craft your perfect trip` | `Let AI prepare your consultation` |
| `Personalized. Optimized. Unforgettable.` | `Evidence-linked. Reviewed by you. Verified on approval.` |
| `Your Itinerary` | `Patient Overview` |
| `Bali, Indonesia` | Patient name |
| `7 Days • 6 Nights • 12–18 May` | `54 yrs • Diabetology • Last seen 20 Sep` (from data) |
| `AI Route Optimized` | `Clinical Context Ready` |
| `Best time to visit • Less travel time` / `Scenic • Budget friendly` | `Evidence-linked • Source-traceable` / `Unverified until approved` |
| `Distance` / `Est. Cost` / `CO₂ Saved` | `Documents` / `Clinical Facts` / `Open Issues` |
| `Itinerary` / `Transport` / `Stay` / `Recommendations` | `Timeline` / `Medications` / `Investigations` / `Issues` |
| `Day 1` rail | Month label over day number (e.g., `SEP` over `20`) |
| `+ Add Activity` | `+ Add Record` |
| `Optimize with AI` | `Generate Brief` |
| `Trip to Bali` / dates | Screen title / date range or document date |
| `BOARDING PASS` / `On Time` | `MEDICATION CHANGE` / `Review` (or `CLINICAL BRIEF` / `AI-generated`) |
| `View E-Ticket` | Context-specific primary CTA (`View Evidence`, `Approve & Update Memory`, …) |
| Nav: `Home / Itinerary / Bookings / Profile` | `Home / Patients / Records / Memory` |

### 6.5 Imagery rules
- **No patient photographs, ever** (privacy + no source). Patient cards and thumbnails use: (a) stills extracted from `lightNoWatermark` `[VERIFY]` or other existing landing-page imagery, tinted to the sage palette; or (b) the deterministic fallback: a soft sage gradient with a serif monogram of initials.
- Document thumbnails: first-page render of the stored PDF/image if available, else a typed document-glyph tile (prescription, lab, note, discharge, imaging, other).
- Hero artwork on Home = ambient layer from `lightNoWatermark` (see §7.8), faded into the background with the same misty fade as the reference.
- The robot mascot in the banner: use a ClinSync logo mark/asset **if one exists in the repo**; otherwise a plain logo-mark in a soft circle. Do not generate or invent a mascot character.

### 6.6 Clinical safety UI rules
1. Any AI-produced text/object shows an **"AI-generated · Unverified"** marker until doctor approval, then **"Doctor approved"**.
2. Confidence is always shown beside AI-extracted facts: `≥0.85 High`, `0.60–0.84 Medium`, `<0.60 Needs verification` (thresholds come from the backend; display band returned by API, compute only if absent).
3. Medication conflicts show **both sources side by side**. Never highlight one as correct. No recommendation verbs in generated UI copy.
4. Missing information is phrased `Potentially missing: …` and presented as a question to the doctor.
5. Trends are described, never explained causally.
6. Persistent small disclaimer on Brief, Consultation, Approval: `AI-assisted summary of source records. Not a diagnosis or treatment recommendation.`
7. Raw backend exceptions are never shown; map error codes to human text (§11.4).
8. Fallback data shows a subtle `Demo data` tag (when `meta.source == "fallback"`).

---

## 7. MOBILE DESIGN SYSTEM

> **Values below are visual estimates from the reference image** (no source file exists). In C06 Antigravity must **sample the image** (e.g., colour-pick key surfaces) and fine-tune; record final values in `docs/frontend/DESIGN_TOKENS.md`. Structure and relationships (white on sage, one green, big radii, soft shadow) are fixed; exact hex values may be adjusted by sampling.

### 7.1 Colour tokens (`core/theme/app_colors.dart`)
| Token | Approx. value | Use |
|---|---|---|
| `bgBackdrop` | `#E3EBE0` | Scaffold backdrop / outer sage tint |
| `bgCanvas` | `#F6F8F4` | Main screen canvas (warm off-white) |
| `surface` | `#FFFFFF` | Cards, buttons, search, nav |
| `surfaceTint` | `#EEF3EC` | Inner stat strip, banner base, chips, progress track |
| `primary` | `#4E7A55` | CTA pill, active tab, progress, checks, links, accent text |
| `primaryDark` | `#3F6646` | Pressed state, boarding-pass header |
| `primarySoft` | `#DCE8DA` | Soft fills, selected-chip background |
| `textPrimary` | `#1B1F1B` | Headlines (black line), body strong |
| `textSecondary` | `#6E766E` | Subtitles, meta, labels |
| `textTertiary` | `#9AA29A` | Inactive nav, placeholder |
| `divider` | `#E4E8E2` | Hairlines, dashed dividers |
| `onPrimary` | `#FFFFFF` | Text/icons on green |
| `warning` / `danger` | muted amber `#B7791F` / muted red `#B3453B` | **Only** for conflicts/errors; desaturated to fit palette |
| Confidence | high = `primary`; medium = muted amber; needs-verification = muted red-brown | Badges |

Gradients: (a) **photo scrim** — transparent → `rgba(0,0,0,0.65)` bottom 55% on image cards; (b) **hero fade** — transparent → `bgCanvas` bottom of hero; (c) **banner** — `surfaceTint` → slightly darker sage, diagonal.

### 7.2 Typography (`app_typography.dart`)
- **Serif (display/headlines):** a refined transitional serif. Use the landing page's serif if it has one `[VERIFY]`; otherwise **Newsreader** or **Source Serif 4** (bundle fonts as assets; do not depend on runtime download for demos).
- **Sans (UI/body):** **Inter** (or landing-page sans if present).
| Style | Font | Size/Weight (approx.) | Use |
|---|---|---|---|
| `displayHero` | Serif | 40 / 400–500, line-height 1.08 | Home hero (3 lines; line 1 `textPrimary`, lines 2–3 `primary`) |
| `titleScreen` | Serif | 18–20 / 400 | Top-bar titles |
| `titleHeader` | Serif | 20–22 / 500 | Patient name in header block |
| `titleSection` | Sans | 17 / 600 | Section headers (`Recent Patients`) |
| `titleCard` | Sans | 16 / 600 | Card titles |
| `body` | Sans | 14 / 400 | Body |
| `bodyBullet` | Sans | 12.5 / 400 `textSecondary` | Dot-separated bullet lines |
| `label` | Sans | 12 / 500 `textSecondary` | Labels (Flight/Gate/Seat-style) |
| `caption` | Sans | 11 / 400 | Meta, tab labels in nav |
| `capsLabel` | Sans | 11 / 600, letter-spacing +0.8, UPPERCASE | `BOARDING PASS`-style headers |
| `numberLarge` | Sans (or Inter tabular) | 28–32 / 700 | `CGK/DPS`-style codes, `26°`-style values |
| `numberStat` | Sans | 15 / 600 | Stat values |
| `button` | Sans | 16 / 600 | CTA text |
| `link` | Sans | 14 / 500 `primary` | `See all` |

### 7.3 Spacing (4-pt grid)
`4, 8, 12, 16, 20, 24, 32, 40`. Screen horizontal padding **20**. Vertical gap between sections **24**. Gap inside cards **12–16**. Carousel item gap **12**. Bottom safe padding = nav/CTA height + 16.

### 7.4 Radii
`sm 12` (thumbnails inside cards), `md 16` (image thumbnails, chips), `lg 22` (cards), `xl 28` (hero/pass/banner/phone-like containers), `pill 999` (buttons, search, tabs, status pills), `circle` (icon buttons, avatars, step nodes). Icon tile (Quick Actions) radius ~18.

### 7.5 Elevation & shadows
Soft, diffuse, slightly green-grey tinted; never hard. Tokens: `shadowCard` (y 6, blur 20, `rgba(40,60,40,0.07)`), `shadowFloat` (y 10, blur 28, `rgba(40,60,40,0.10)` — search pill, nav bar, sticky CTA bar), `shadowButton` (primary pill: y 6, blur 16, `primary` @ 25%). Borders: avoid; if used, 1 px `divider`.

### 7.6 Component catalogue (`shared/widgets`, built in C08 and C14; **names are fixed**)
| Component | Spec (from reference) |
|---|---|
| `CircleIconButton` | 44 px white circle, `shadowCard`, 20 px line icon `textPrimary`; used for back/bookmark/more/bell/menu/filter/share. Has `filled` (green) variant for mic. |
| `PrimaryPillButton` | Height 56, full pill, `primary`, white icon+text centred (icon 20 left of label), `shadowButton`, pressed → `primaryDark` + scale .98. Disabled → `primary` @ 40%. |
| `SectionHeader` | Left `titleSection`, optional right `link` text with no icon. |
| `SearchPill` | Height 56 white pill `shadowFloat`; leading search icon; hint `textTertiary`; trailing 44 px filled-green circular mic button. |
| `PatientCard` (from destination card) | 104×140, radius 22, full-bleed image or gradient+monogram, photo scrim, bottom-left white name (16/700) + subtitle (12), bottom-right 32 px white circular arrow button. Horizontal list, edge-bleeding, with `PageDots`. |
| `PageDots` | 3 dots; active = `primary` (slightly wider or same size per image), inactive = `divider`/grey. |
| `QuickActionTile` | 64×64 white rounded-square (r≈18), 26 px thin-line icon `textPrimary`, 12 px label centred under, 4-up row with equal spacing. |
| `AIBanner` | Gradient `surfaceTint` card r 22, left sparkle icon, two-line text, right logo mark; subtle `shadowCard`. |
| `TopBar` | Row: leading `CircleIconButton`, centred `titleScreen` (+ optional grey sub-line), trailing 1–2 `CircleIconButton`s. Transparent over canvas. |
| `HeaderBlock` | Title (`titleHeader`) + edit pencil, meta line, `AvatarStack` below, trailing rounded thumbnail (≈ 110×84, r 16). |
| `AvatarStack` | Overlapping 28 px circles with white 2 px ring, plus `+N` chip. In ClinSync: document-type glyph circles. |
| `InsightCard` (AI card) | White, r 22, `shadowCard`; check-circle + green title + 2 meta lines + trailing mini illustration + chevron; bottom inner `surfaceTint` strip with 3 `StatItem`s. |
| `StatItem` | Outline icon (20) + `label` over `numberStat`. |
| `PillTabs` | Row; selected = `primary` pill, white text 14/600; unselected = `textSecondary` text, no background. Horizontally scrollable if overflow. |
| `TimelineRail` | Left column: tiny label (`label`), 32 px `primary` circle with white bold number/day, 2 px dotted vertical connector in `divider`/`primarySoft` down to next node. |
| `TimelineCard` | White r 20, 14 padding; leading small green line icon; `titleCard`; trailing 28 px circular chevron button; two `bodyBullet` lines; trailing 72×64 rounded thumbnail (r 14). |
| `AddRow` | 28 px outline circle with `+` and `link`-style text. |
| `StickyActionBar` | Bottom bar over canvas with top fade: `PrimaryPillButton` (flex) + 56 px `CircleIconButton`. |
| `TicketCard` (boarding pass) | Green `primaryDark/primary` header band (`capsLabel` white + status pill + icon), concave rounded transition into white body (custom clipper); body with 3-column route layout, dotted connector with centred icon + caption, dashed `divider`, 3-column key/value row, trailing 64 px tile. |
| `LinkRowCard` (hotel row) | White r 20; 64×64 rounded thumbnail; `label` + bold title + meta; trailing chevron. |
| `MetricCard` | White r 22, title row, big number + icon, caption lines (weather card). |
| `ProgressRingCard` | White r 22; 64 px ring (stroke 7, track `surfaceTint`, value `primary`, centre glyph), `numberStat`-bold % + caption. |
| `ChecklistCard` | Title + `body` count + chevron; rounded 6 px progress bar; two-column items with 18 px circle (filled-green check / empty outline). |
| `BottomNav` | Floating white bar, r 28, `shadowFloat`, 4 items: 24 px line icon + 11 px label; active = `primary` filled icon + `primary` label; inactive = `textTertiary`. |
| `StatusPill` | Pill, 11/600; variants: `aiGenerated` (primarySoft/primary), `approved` (primary/white), `needsReview` (muted amber), `conflict` (muted red), `demo` (surfaceTint/textSecondary). |
| `ConfidenceBadge` | Small pill + 3-segment micro-bar; shows `High / Medium / Needs verification`. |
| `EvidenceCard` | Source row (`LinkRowCard` style) + quoted text block in `surfaceTint` with highlight of exact `source_text`, page chip, confidence badge. |
| `AmbientBackground` | Video/still layer; see §7.8. |
| `Skeleton*`, `EmptyState`, `ErrorState` | See §11. |

### 7.7 Iconography
Thin-stroke (≈1.5 px) rounded line icons consistent with the reference (sparkle, route, wallet, map, leaf, plane, bell, bookmark, sliders, mic, download, share, chevron, check). Use **one** icon family (Lucide via `lucide_icons` or Phosphor `phosphor_flutter`, whichever is available and closest; log the choice). Do not mix filled Material icons except the active nav icon state.

### 7.8 Ambient video (`lightNoWatermark`) `[VERIFY asset]`
- Locate the asset(s). If video: copy a **mobile-optimised, muted, loop** version to `assets/video/`; if too heavy (> ~8 MB or > 1080p), produce a compressed copy (document the command) — do not ship the original if oversized.
- Use `video_player`: muted, looping, `BoxFit.cover`, no controls. **Always** provide a pre-rendered **poster still** (extracted first frame, tinted) shown instantly and as a fallback when the video fails/initialises slowly or when reduce-motion/low-power conditions apply.
- Placement: Home hero (full-width top ≈ 38% of height, with bottom `hero fade` gradient into `bgCanvas`, and the leaf/foliage overlap only if an asset exists), and a very subtle low-opacity layer behind Brief and Approval headers. **Not** behind dense data screens.
- Overlay: sage wash (`bgCanvas` @ 35–55%) to keep text contrast ≥ WCAG AA for the headline.
- Dispose controllers on leaving; one controller shared via provider; pause when app is backgrounded.

### 7.9 Motion
| Pattern | Spec |
|---|---|
| Route transition | Forward: fade-through + 16 px upward slide, 280 ms `easeOutCubic`; Back: reverse, 220 ms |
| Section reveal | Fade + 12 px translate, 280 ms, 40 ms stagger, once per screen build |
| Press feedback | Scale 0.98, 120 ms |
| Tab switch | Pill background slides (`AnimatedContainer`/`AnimatedAlign`) 220 ms; content cross-fades 200 ms |
| Progress ring/bar | Animate from 0 → value, 700 ms `easeOutCubic` |
| Processing stepper | Active node pulses softly (1.0→1.08, 900 ms loop) |
| Hero parallax | ≤ 0.25 factor, only Home |
| Reduce motion | Respect `MediaQuery.disableAnimations`: remove parallax/pulse, shorten transitions to 100 ms |
Keep all motion subtle; no bouncy/elastic curves.

---

## 8. FLUTTER ARCHITECTURE

Adapt to repo after C01; default target:

```text
lib/
├── main.dart
├── app.dart                      # MaterialApp.router, theme, global providers
├── core/
│   ├── constants/                # api paths, specialty list, enums, asset paths
│   ├── config/                   # env/base URL/demo flag (persisted)
│   ├── networking/               # api_client, envelope parser, api_exception, interceptors
│   ├── models/                   # patient, document, clinical_fact, evidence, medication,
│   │                             # investigation, timeline_event, issue, brief, consultation,
│   │                             # consultation_version, clinical_memory, processing_status
│   ├── repositories/             # one per API family
│   ├── theme/                    # app_colors, app_typography, app_spacing, app_radii,
│   │                             # app_shadows, app_theme
│   ├── animations/               # transitions, reveal, press_scale, parallax
│   └── utils/                    # date_format, confidence_band, error_text, debounce
├── features/
│   ├── home/ patients/ documents/ processing/ evidence/ timeline/ medications/
│   ├── reconciliation/ investigations/ trends/ issues/ specialty/ brief/
│   ├── consultation/ versions/ approval/ memory/ camera/ voice/
│   │     each: presentation/ (screens, widgets) · state/ (providers) 
└── shared/
    ├── widgets/                  # §7.6 components
    ├── cards/
    ├── navigation/               # app_router, shell, bottom_nav, route_names
    ├── loading/                  # skeletons
    └── error/                    # error_state, empty_state, snackbars
```

Decisions (confirm/override after C01; record in `DECISIONS.md`):
- **State management:** keep what the repo uses if clean; otherwise **Riverpod**. Immutable state objects; `AsyncValue`-style loading/data/error.
- **Routing:** **go_router** with a `ShellRoute` for the 4-tab bottom nav; detail routes pushed above the shell.
- **Active patient:** a global `activePatientProvider` (persisted via `shared_preferences`). Tabs `Records` and `Memory` operate on it; if none selected, show a styled prompt to pick a patient.
- **Networking:** `dio`; single `ApiClient`; envelope parsing `{success,data,meta}`; maps errors to `ApiException(code,message)`.
- **Models:** plain Dart with `fromJson/toJson` (hand-written or `json_serializable`; pick one, stay consistent). Tolerant parsing: unknown fields ignored, missing optional fields null.
- **Capture:** `image_picker` or `camera` for camera, `file_picker` for upload, `record` for audio, `permission_handler`.
- **Charts:** `fl_chart` (line chart styled with `primary`, rounded stroke, soft gradient fill) for lab trends.
- **Dependencies to add (verify each with `flutter pub add`):** `go_router`, `flutter_riverpod`, `dio`, `video_player`, `fl_chart`, `image_picker` (or `camera`), `file_picker`, `record`, `permission_handler`, `shared_preferences`, `intl`, an icon package (§7.7). Fonts bundled as assets.

Navigation map:
```text
Shell (BottomNav: Home · Patients · Records · Memory)
 ├ /home
 ├ /patients ─ /patients/:id (Overview)
 │            ├ /patients/:id/timeline | /medications | /investigations | /issues   (Overview tabs)
 │            ├ /patients/:id/medications/:groupKey/reconcile
 │            ├ /patients/:id/investigations/:groupKey/trend
 │            ├ /patients/:id/documents
 │            ├ /patients/:id/specialty
 │            ├ /patients/:id/brief
 │            ├ /patients/:id/consultation/:cid  (editor) ─ /versions ─ /approve
 │            └ /patients/:id/memory
 ├ /records  (active patient documents)
 ├ /memory   (active patient memory)
 └ push-only: /documents/:id/processing, /facts/:id/evidence, /camera, /voice
```

---

## 9. SCREEN-BY-SCREEN UX PLAN

> Shared across all screens: use the `AmbientBackground`/canvas, `TopBar` on detail screens, section reveal motion, skeleton on load, `ErrorState` with Retry, `EmptyState` with a primary action. `data` fields are ClinSync API fields; names follow the repo's contract `[VERIFY]` or `audit.md` §8.

### 9.1 Home (template: Reference Screen 1)
- **Purpose:** Patient workspace entry; get to the active patient, recent patients, quick capture, and brief.
- **Hierarchy/layout:** top row (menu `CircleIconButton`, specialty circle at right — replaces avatar since there is no login) → hero (ambient video/still + 3-line serif headline + subtitle) → `SearchPill` (mic = Voice Note) → `SectionHeader` `Recent Patients` + `See all` → `PatientCard` carousel + `PageDots` → `SectionHeader` `Quick Actions` → 4 `QuickActionTile`s (`Upload Record`, `Scan Document`, `Voice Note`, `Doctor Brief`) → `AIBanner` (`Let AI prepare your consultation`). Bottom nav present (floating).
- **Data:** `GET /patients?limit=6` (name, age, last_activity, preferred specialty).
- **Interactions:** Menu → bottom sheet (API base URL, Demo mode toggle, about/disclaimer). Specialty circle → Specialty (§9.13). Search tap → Patients with focus; typing filters patients (debounced). Mic → Voice for active patient (if none, patient picker sheet first). Patient card → Overview and sets active patient. Tiles act on the active patient (picker if none). Banner → Brief for active patient.
- **Loading:** skeleton cards + shimmer under hero (hero still renders from poster). **Empty:** carousel replaced by a `PatientCard`-shaped "Create your first patient" card. **Error:** inline `ErrorState` in carousel region; rest stays usable.
- **Motion:** hero parallax, staggered reveal. **Mobile:** carousel snaps; safe-area top; text over hero must pass contrast. **Nav:** per above.

### 9.2 Patient List
- **Purpose:** Find/create a patient. **Layout:** `TopBar` ("Patients", filter/more), `SearchPill`, vertical list of `LinkRowCard`s (monogram thumbnail, name, `Age • last activity`, chevron), `+ Add Patient` `AddRow`/FAB-style pill.
- **Data:** `GET /patients?query=`, `POST /patients`. **Create:** bottom sheet form (name, DOB or age, sex optional) with `PrimaryPillButton`.
- **States:** skeleton rows / empty "No patients yet" + Create / error + Retry. **Motion:** list stagger, sheet slide-up. **Nav:** row → Overview (sets active).

### 9.3 Patient Overview (template: Reference Screen 2)
- **Purpose:** The central screen — "what changed, what matters, what conflicts, what's missing, where's the evidence, what next".
- **Layout:** `TopBar` (back, title `Patient Overview`, bookmark → pin patient, more). `HeaderBlock` (name + edit, `54 yrs • Specialty • Last seen …`, `AvatarStack` of document types `+N`, trailing thumbnail). `InsightCard` `Clinical Context Ready` with `Documents / Clinical Facts / Open Issues` stats (chevron → Issues). `PillTabs` (`Timeline · Medications · Investigations · Issues`) with tab content below: Timeline tab shows `TimelineRail`+`TimelineCard`s; Medications tab shows medication cards; Investigations tab shows latest-value cards; Issues tab shows issue cards. `AddRow` `+ Add Record`. `StickyActionBar`: `Generate Brief` + sliders `CircleIconButton` (→ Specialty).
- **Data:** `GET /patients/{id}/overview` (preferred aggregate; fall back to composing `/timeline`, `/medications`, `/investigations`, `/issues`, `/documents`) .
- **Interactions:** tabs swipe/tap; cards open detail/evidence; `+ Add Record` → Documents upload sheet (Upload / Camera / Voice).
- **States:** skeleton for header + card + 3 timeline rows; empty tabs with action; per-tab error; Brief button disabled with tooltip when no facts yet.
- **Motion:** pill slide, reveal, ring/stat count-up. **Nav:** per tabs/CTA.

### 9.4 Documents (template: S2 cards)
- **Purpose:** Evidence library. **Layout:** `TopBar` (`Records`), `PillTabs` filter (`All · Prescription · Lab · Notes · Other`), list of `TimelineCard`-style document cards (type glyph, name, date, `ConfidenceBadge`, processing `StatusPill`, thumbnail), `StickyActionBar`: `Upload` primary + circle `Camera` + circle `Voice`.
- **Data:** `GET /patients/{id}/documents`; `POST …/documents` (multipart); `POST /documents/{id}/process`. **Interactions:** card → Evidence/doc detail; unprocessed card shows `Process` button; upload → file picker → progress → auto Processing screen.
- **States:** skeleton / empty "No records yet — upload or scan" / error. **Mobile:** large touch targets; share/open source file.

### 9.5 Document Processing (template: S3 progress ring + S2 rail)
- **Purpose:** Show what ClinSync is doing. **Layout:** `TopBar`, big `ProgressRingCard`, vertical `TimelineRail` stepper: `Uploaded → Extracting text → Classifying → Extracting clinical information → Validating → Complete`, caption under active step, final `PrimaryPillButton` `View Extracted Facts`.
- **Data:** `GET /documents/{id}/status` polling every 1.5 s until terminal. If the repo lacks a status endpoint, fall back to client-side staged progress while awaiting `POST /process` response (log in `API_MISMATCHES`).
- **States:** failed → `ErrorState` with typed message + `Retry` (reprocess); needs_review → amber banner + `Review facts`. **Motion:** ring animates, pulsing active node.

### 9.6 Evidence (trust layer)
- **Purpose:** Answer "Why does the system believe this?" **Layout:** `TopBar` (`Evidence`), fact summary card (value, `ConfidenceBadge`, verification `StatusPill`), `LinkRowCard` source (document name, type, date, page chip) → opens source file, `EvidenceCard` with quoted `source_text` highlighted, extraction confidence, provenance-verified indicator. Actions: `Mark verified` / `Flag` (if API supports `PATCH /facts/{id}`; else hide).
- **Data:** `GET /facts/{id}/evidence` (or contract equivalent), `GET /documents/{id}/pages/{n}` optional. **States:** skeleton / error / "Source text unavailable" empty.

### 9.7 Timeline (full-screen of Overview tab)
- **Layout:** `TimelineRail` + `TimelineCard` per event (rail label month over day-number node; title; two bullet lines of facts; document thumbnail; chevron → evidence). Type filter `PillTabs`. Undated events grouped under `Undated`.
- **Data:** `GET /patients/{id}/timeline`. **States:** skeleton rail / empty "No events yet" / error. **Motion:** stagger reveal; nodes fade in sequentially.

### 9.8 Medications
- **Layout:** `PillTabs` `Current · Previous · Uncertain`; medication cards (name, strength/dose/frequency, `ConfidenceBadge`, status, tags `Changed` / `Potential conflict` / `Uncertain status` as `StatusPill`s, source thumbnail); conflict cards have a prominent chevron → Reconciliation.
- **Data:** `GET /patients/{id}/medications?status=`. **States:** standard. **Rule:** discrepancies surfaced, never resolved.

### 9.9 Medication Reconciliation (template: Reference Screen 3 boarding pass)
- **Purpose:** Side-by-side comparison of conflicting/changed instructions. **Layout:** `TopBar` (`Metformin`, date range sub-line, bell → none/removed, more), `TicketCard`: header `MEDICATION CHANGE` + status pill (`Review`); body left = Source A (`label` doc + date, `numberLarge` frequency e.g. `OD`, strength line), centre = dotted connector with swap/compare icon and caption `Changed` or `Conflict`, right = Source B (`BD`). Dashed divider; bottom row `Drug · Strength · Status` + evidence tile. Below: two `LinkRowCard`s for both source documents. `ChecklistCard` titled `Clinician review` with items (`Confirm current instruction`, `Check patient adherence`, `Update record`) as **doctor tasks, unchecked by default** (local state or `PATCH /issues`). Primary CTA `View Evidence` + circular share.
- **Copy rule:** neutral text `Two records contain different frequencies.` No "correct dose".
- **Data:** `GET /patients/{id}/medications/{group_key}/history` + related issue. **States:** standard.

### 9.10 Investigations (template: S3 cards)
- **Layout:** grid of `MetricCard`s (test, latest value large, unit, reference range, abnormal flag chip, date); first row two-up like Weather/Progress; tap → Lab Trend. Optional `PillTabs` by category.
- **Data:** `GET /patients/{id}/investigations`. **States:** standard; abnormal indicated with muted amber chip (not alarmist).

### 9.11 Lab Trends
- **Layout:** `TopBar` (test name), large `MetricCard` (latest value, delta vs previous, descriptive text from API), `fl_chart` line card (points with dates; reference-range band if available; `primary` line, soft fill), history list rows (`LinkRowCard` with value/date/source). Sentence is the backend's non-causal description.
- **Data:** `GET /patients/{id}/investigations/{group_key}/trend`. **Empty:** "Only one measurement — trend needs at least two."
- **Motion:** line draws left→right 700 ms.

### 9.12 Issues (clinical review queue; template: S3 checklist + S2 cards)
- **Layout:** `PillTabs` `Conflicts · Missing · Low confidence`; `ProgressRingCard`/`ChecklistCard` header (`3 of 7 reviewed`); issue cards: severity `StatusPill`, title, description, `Source A / Source B` rows for conflicts, `Potentially missing: …` for missing info, actions `Acknowledge` / `Dismiss`.
- **Data:** `GET /patients/{id}/issues`; `PATCH /issues/{id}` (if absent in repo: local-only state, log mismatch). **States:** empty = positive "Nothing needs review" (still neutral wording).

### 9.13 Specialty Selection (template: S1 tiles)
- **Layout:** `TopBar` (`Specialty`), serif title `Choose a specialty`, 2-column grid of selectable tiles (white rounded squares, icon, label): General Medicine, Cardiology, Diabetology, Orthopedics, Pediatrics, Neurology, Other; selected tile gets `primary` border/check and `primarySoft` fill. `PrimaryPillButton` `Continue`.
- **Data:** static list (from constants / `GET /specialties`); stored per patient in local state (and backend if supported). Result feeds Brief request. **Nav:** returns to caller or → Brief.

### 9.14 60-Second Brief (template: S3 pass + S2 AI card)
- **Purpose:** Rapid-scan clinical brief — **scannable, not an essay**.
- **Layout:** `TopBar` (`60-Second Brief`, sub-line `Specialty • generated time`), subtle ambient header. `TicketCard`-style summary header (`CLINICAL BRIEF` + `AI-generated · Unverified` pill) with chief complaint. Then compact section cards in order: Relevant History, Current Medications (with conflict tags), Allergies (`Not documented` shown explicitly), Recent Investigations, Important Trends (mini sparkline), Attention Items, Contradictions, Missing Information (`ChecklistCard`), Evidence shortcuts (chips → Evidence). Every line has a tiny evidence chip. Footer disclaimer. `StickyActionBar`: `Start Consultation` + sliders (specialty).
- **Data:** `POST /patients/{id}/brief {specialty}` then `GET …/brief/latest`. **Loading:** staged skeleton with message sequence (`Collecting evidence → Comparing records → Preparing brief`). **Error:** typed message + `Retry` + `Use last brief` if cached. **If backend returned fallback/template:** show `Demo data`/`Template brief` tag.
- **Motion:** sections reveal top→bottom within first second.

### 9.15 Consultation Editor
- **Layout:** `TopBar` (`Consultation`, version chip `v2 • Doctor edited`, more → Version History), `StatusPill` row (`AI generated` / `Doctor edited`), editable section cards (Chief complaint, HPI, Past history, Medications, Allergies, Examination, Investigations reviewed, Assessment, Plan, Follow-up). AI-prefilled sections carry an `AI` tag; Assessment/Plan/Follow-up start empty with placeholder `Doctor to complete`. Per-section actions: edit, remove, flag. `AddRow` `+ Add Section/Note`. `StickyActionBar`: `Save Version` + circular `Review & Approve`.
- **Data:** `POST /patients/{id}/consultations`, `PUT /consultations/{id}`, `POST /consultations/{id}/versions`. **States:** autosave-draft indicator; unsaved-changes guard; error on save with Retry (content retained).

### 9.16 Version History (template: S2 timeline)
- **Layout:** `TimelineRail` nodes `v1, v2, v3`; card per version: origin `StatusPill` (`AI generated`, `Doctor edited`, `Approved`), time, change summary bullets, `View` (read-only) and `Restore as draft` (creates new version). **Data:** `GET /consultations/{id}/versions`.

### 9.17 Approval (template: S3)
- **Purpose:** Make the Draft → Review → Approve → Verified Memory transition unmistakable. **Layout:** `TopBar` (`Approval`), `TicketCard` summarising what will enter memory (header `READY FOR REVIEW`, counts), `ProgressRingCard` (`Review progress` — items acknowledged), `ChecklistCard` of required acknowledgements (open high-severity conflicts acknowledged, unedited AI sections acknowledged), preview list of memory items (`GET …/approve/preview` if present), disclaimer. Primary CTA `Approve & Update Memory` (disabled until required checks done) + share/export. On success: celebratory-but-subtle success state — check circle animation, text `Clinical memory updated`, summary of items added, button `Back to Patient`.
- **Errors:** blocked approval (`GATE1_BLOCKED` or equivalent) → list reasons in plain language; nothing marked approved. **Data:** `POST /consultations/{id}/approve`.

### 9.18 Clinical Memory
- **Layout:** `TopBar` (`Clinical Memory`), badge `Doctor approved`, `PillTabs` by memory type (`Diagnoses · Medications · Allergies · History · Notes`), cards with `Verified` pill, approval date, source consultation link; `Memory history` row → list. Empty: "No verified memory yet — approve a consultation to create it."
- **Data:** `GET /patients/{id}/memory` (+`/history`). Visually distinct from AI facts (white card with `primary` left accent + check).

### 9.19 Camera
- **Layout:** full-screen camera preview, translucent white circular controls (close, flash), large white shutter circle with green ring, gallery shortcut; after capture: preview with `Retake` (secondary) and `Use Image` (`PrimaryPillButton`). Upload → Processing.
- **Permissions:** request camera; denied → `ErrorState` with `Open Settings`. **Data:** `POST …/documents` with `uploaded_via=camera`.

### 9.20 Voice
- **Layout:** bottom sheet/full screen: serif prompt `Dictate a clinical note`, large pulsing filled-green mic circle, timer, waveform (simple animated bars), `Stop` → upload → transcript view (editable text, `AI transcript · review before use` pill) with `Save` / `Discard`. Extracted facts appear as `Needs verification`.
- **Data:** `POST /patients/{id}/voice`. **Permissions:** microphone; denied handling as Camera. **Error:** STT failure → typed message + retry; keep audio local until success.

---

## 10. BACKEND PLAN (SUMMARY; full spec in `audit.md`)
- **Do not rebuild.** Inspect existing FastAPI/SQLAlchemy; map each §9 screen to an existing endpoint; list gaps in `API_MISMATCHES.md`.
- **Likely gaps to verify:** `GET /patients/{id}/overview` aggregate · `GET /documents/{id}/status` · `GET /facts/{id}/evidence` · `GET /patients/{id}/issues` + `PATCH /issues/{id}` · `GET …/investigations/{key}/trend` · `GET …/medications/{key}/history` · `…/approve/preview` · `GET /patients/{id}/memory` · `GET /specialties`.
- Required concepts (must exist; add additively if missing): Patient, Document, Evidence, ClinicalFact, Medication, Investigation, TimelineEvent, Contradiction, MissingInformation, DoctorBrief, Consultation, ConsultationVersion, ClinicalMemory.
- Enable **CORS** for the device/emulator; document the LAN base URL for physical devices (e.g., `http://<host-ip>:8000`; Android emulator `10.0.2.2`). Run command documented in `README`.
- Envelope: `{success, data, meta}` / `{success:false, error:{code,message}}`. If the repo uses a different envelope, **adapt the Flutter parser**, don't change the backend.

## 11. API / ERROR / STATE ARCHITECTURE
### 11.1 Families
`/api/v1/patients`, `/documents`, `/timeline`, `/medications`, `/investigations`, `/brief`, `/consultations`, `/voice` (+ `facts`, `issues`, `memory` if present).
### 11.2 Client behaviour
Timeout 30 s default, 120 s for process/brief/voice; one retry on network/5xx for GETs only; never retry POST approve. Upload with progress. Base URL configurable at runtime (Home menu) and persisted.
### 11.3 State pattern
Each feature: `Provider → Repository → ApiClient`. Providers expose loading/data/error; manual `refresh()`; invalidate dependent providers after mutations (e.g., after document processed → refresh overview, timeline, meds, investigations, issues; after approve → refresh overview + memory).
### 11.4 Error → human text map
`DOCUMENT_PROCESSING_FAILED` → "We couldn't read this document. Try a clearer scan." · `OCR_FAILED` → same · `LLM_UNAVAILABLE` → "AI is temporarily unavailable. Showing the last available information." · `STT_FAILED` → "We couldn't transcribe that recording." · `GATE1_BLOCKED` → "Approval is on hold: some items need your review." · network/timeout → "Can't reach the server. Check your connection." · unknown → "Something went wrong." Never show raw exceptions.
### 11.5 Reusable states
`SkeletonCard/Row/Rail` (shimmer in `surfaceTint`), `EmptyState` (glyph in soft circle + serif title + body + optional primary pill), `ErrorState` (same layout + Retry).

## 12. DATABASE ARCHITECTURE (SUMMARY)
Preserve the existing schema. Expected tables (audit.md §6): patients, documents, clinical_facts, medications, investigations, timeline_events, contradictions (issues incl. missing info), briefs, consultations, consultation_versions, clinical_memory, voice_notes. Add only additive migrations required by C34. Storage layout: `storage/patients/{patient_id}/{documents,images,voice}/`.

## 13. A/B/C INTEGRATION ARCHITECTURE
```text
Developer B (OCR → classify → extract → evidence → confidence → voice normalisation)
   └─ output: structured extraction JSON  (shared contract = existing B output schema [VERIFY])
        └─ persistence adapter (C): documents, clinical_facts, medications, investigations, timeline_events (SQLite)
             └─ Developer A input: structured facts from DB
                  └─ A output: timeline, reconciliation, lab trends, contradictions, missing info, brief, memory
                       └─ FastAPI routes (C) → JSON envelope
                            └─ Flutter repositories/models (C) → screens
```
Rules: do not change A/B function signatures; write adapters in `services/` if shapes differ; any A/B contract mismatch goes to `API_MISMATCHES.md` and is resolved by an adapter. Camera = another document source. Voice = B's normalisation → same extraction path.

## 14. DEMO & FALLBACK ARCHITECTURE
**Demo patient ("Demo Patient", fictional)** with six documents: (1) initial consultation (Jan 2026; T2DM; allergy undocumented) · (2) prescription (Feb 2026; Metformin 500 mg once daily) · (3) laboratory report (Apr 2026; HbA1c 8.0%) · (4) follow-up consultation (Jun 2026) · (5) updated prescription (Sep 2026; Metformin 500 mg twice daily — change, plus a conflicting same-date pair) · (6) discharge/diagnostic document (Sep 2026; HbA1c 7.8%, mixed date formats). HbA1c series 8.4 → 8.0 → 7.8. Must show: multiple dates, medication change, conflict, repeated labs, missing info (allergy, start date), evidence + confidence, timeline, brief, a pre-created consultation with 2–3 versions, and one approved consultation producing visible clinical memory.
**Fallback tiers:** (1) real AI → (2) backend deterministic/template path → (3) backend structured fallback JSON labelled `meta.source="fallback"` → (4) Flutter **Demo mode**: if the server is unreachable and Demo mode is on, repositories read bundled JSON from `assets/demo/*.json` (same shape as API), tagged `Demo data`. Fallback data is never presented as doctor-approved unless it is the seeded approved memory.
**Seed:** one command resets/seeds DB (documented). Demo toggle in Home menu.

---

## 15. TASK DEPENDENCY GRAPH
```text
C01 ─┬─ C02
     └─ C03 ──────────────────────────────┐
C04 (backup + remove old UI + scaffold) ◄─┘(needs C01–C03)
 └ C05 → C06 → C07 → C08 → C09 → C10
              C11 → C12 → C13 → C14
 (C09,C13,C14) → C15 Home → C16 Patients → C17 Overview
 C17 → C18 Docs → C19 Processing → C20 Camera, C21 Voice
 C17 → C22 Evidence → C23 Timeline → C24 Meds → C25 Reconcile
 C17 → C26 Investigations → C27 Trends → C28 Issues
 C28 → C29 Specialty → C30 Brief → C31 Consultation → C32 Versions → C33 Approval → C34 Memory
 C03 → C35 Backend gap-fill (can start after C03, must land before C17/C26–C34 integrate)
 C35 + C36 Demo seed/fallback → C37 Motion/ambient polish → C38 E2E + visual QA vs reference → C39 Cleanup/docs
```
(Numbering below follows this graph; tasks C01–C39.)

---

## 16. TASK BACKLOG

> Format per task: **Objective · Why · Files · Depends · Requirements · Output · Acceptance · Testing · Risks.** Keep each execution small; do not merge tasks.

### PHASE 0 — INSPECTION (read-only)

**C01 — Repository inventory**
- Objective: Produce `docs/frontend/REPO_FINDINGS.md` per §2. Why: plan depends on facts. Files: new docs only. Depends: none.
- Requirements: inspect all 20 items; list exact paths; mark ABSENT honestly; capture A/B public function signatures and outputs; capture current run commands.
- Output: findings doc. Acceptance: every §2 row filled; no repo file modified. Testing: `git status` clean except `docs/frontend/`. Risks: assuming instead of verifying.

**C02 — Landing page & asset analysis**
- Objective: `docs/frontend/LANDING_ANALYSIS.md` per §5 incl. `lightNoWatermark` details (path, format, resolution, duration, size, where/how used). Depends: C01.
- Requirements: cite file+line for each effect; exact hex/px/ms values; translation line for each existing effect using §5.2; list fonts actually used.
- Acceptance: only existing effects listed; every effect has a mobile translation. Risks: reporting effects that don't exist; video too heavy for mobile (note compression need).

**C03 — API contract reconciliation**
- Objective: `docs/frontend/API_MISMATCHES.md`. Depends: C01.
- Requirements: table of each §9 screen → required endpoint → existing endpoint (or MISSING) → field/enum/envelope differences → resolution (adapt Flutter / add backend endpoint). Include list of conflicting field names and date formats.
- Acceptance: all 20 screens covered; resolutions chosen. Risks: inventing a competing contract.

### PHASE 1 — FOUNDATION

**C04 — Safety snapshot, removal of old frontend, fresh scaffold**
- Objective: Tag, branch, delete old UI, create new `lib/` skeleton (§8) that compiles to a blank themed screen. Depends: C01–C03.
- Files: `lib/**`, `pubspec.yaml`, tests. Requirements: `git tag pre-redesign-frontend`; branch `frontend-redesign`; apply §3 matrix; list removals in `REMOVED_FILES.md`; keep platform folders; reuse non-visual code only if C03 says compatible.
- Acceptance: `flutter analyze` clean; `flutter run` shows empty app shell; no old screen/widget/theme file remains. Testing: build debug on one platform. Risks: deleting reusable networking; do it only after listing.

**C05 — Dependencies, fonts, assets**
- Objective: add packages (§8), bundle serif+sans fonts, register `assets/` (images, video, demo json). Depends: C04. Requirements: verify versions via `flutter pub add`; fonts as local assets; icon family chosen. Acceptance: `flutter pub get` OK; fonts render in a test screen. Risks: font licensing/availability—prefer OFL fonts.

**C06 — Design tokens**
- Objective: implement §7.1–7.5 as `app_colors/typography/spacing/radii/shadows`. Why: single styling source. Depends: C05.
- Requirements: sample reference image to refine hex values; write `DESIGN_TOKENS.md`; no raw colours/sizes elsewhere in code. Acceptance: tokens file complete; a `TokenGallery` debug screen shows all tokens. Risks: arbitrary values.

**C07 — Theme assembly**
- Objective: `ThemeData` (light only), scaffold backdrop, text theme, ripple/splash minimal, page transitions (§7.9). Depends: C06. Acceptance: gallery looks like reference palette; transitions set. Testing: widget test builds app.

**C08 — Core component primitives**
- Objective: build `CircleIconButton, PrimaryPillButton, SectionHeader, StatusPill, ConfidenceBadge, ProgressRing, ProgressBar, SurfaceCard, AddRow, AvatarStack, PageDots` per §7.6. Depends: C07.
- Acceptance: `ComponentGallery` debug screen renders each in all states; pixel-compare side-by-side with reference crops by eye; press feedback works. Testing: golden tests for 3 key components. Risks: drifting radii/shadows.

**C09 — Navigation shell**
- Objective: go_router, `ShellRoute` with floating `BottomNav` (`Home · Patients · Records · Memory`), route names, `activePatientProvider`, top-level transitions. Depends: C08.
- Acceptance: 4 tabs switch with correct active styling (green filled icon + label); detail routes hide/show nav per §9 rules; active patient persists. Testing: widget test for tab switching.

**C10 — Composite components**
- Objective: `SearchPill, PatientCard, QuickActionTile, AIBanner, TopBar, HeaderBlock, InsightCard, StatItem, PillTabs, TimelineRail, TimelineCard, StickyActionBar, TicketCard, LinkRowCard, MetricCard, ProgressRingCard, ChecklistCard, EvidenceCard`. Depends: C08.
- Requirements: `TicketCard` custom clipper for green header with concave transition + dashed divider (no fake QR); all take plain data props. Acceptance: gallery shows each, matching §6.1 structure. Risks: clipper complexity—start simple, refine in C37.

**C11 — Networking & config**
- Objective: `ApiClient` (dio), envelope parser, `ApiException`, error-text map (§11.4), runtime base URL + demo flag persisted. Depends: C04 (and C03 decisions). Acceptance: calls `/health` (or equivalent) successfully against running backend; errors map correctly. Testing: unit tests with mocked dio for success/error/timeout.

**C12 — Models**
- Objective: implement §8 models tolerant to contract (per C03). Depends: C11. Acceptance: parse sample JSON fixtures (from real backend responses saved in `test/fixtures/`) without error; unknown fields ignored. Testing: unit tests per model.

**C13 — Repositories & providers**
- Objective: repositories per API family + providers (loading/data/error, refresh, invalidation). Depends: C12. Acceptance: provider unit tests with fake repositories; invalidation after mutations works.

**C14 — Shared states**
- Objective: skeletons, `EmptyState`, `ErrorState`, snackbars, section-reveal and press-scale animation helpers. Depends: C08, C10. Acceptance: gallery shows all states; reveal respects reduce-motion.

### PHASE 2 — BACKEND READINESS

**C35 — Backend contract gap-fill**  *(execute right after C03/C13, before screens that need it)*
- Objective: add only the endpoints/fields marked MISSING in `API_MISMATCHES.md` (likely list §10), following `audit.md` §8 shapes, using existing services/data. Depends: C03. Files: `backend/app/api/routes/*`, `schemas/*`. Requirements: additive; envelope-consistent; no A/B logic edits; CORS ok. Acceptance: each new endpoint returns demo data in Swagger. Testing: pytest/TestClient per endpoint. Risks: breaking existing routes—run existing tests first.

**C36 — Demo seed & deterministic fallback**
- Objective: seed script for the demo patient (§14) loading pre-extracted JSON through the normal persistence path; backend fallback tiers; Flutter `assets/demo/*.json` + Demo mode repository switch. Depends: C13, C35. Acceptance: fresh DB + seed reproduces all demo scenarios; disabling network with Demo mode on still shows full flow; fallback data tagged. Testing: seed idempotency test; repository demo-mode test.

### PHASE 3 — SCREENS (in flow order)

**C15 — Home screen** (§9.1). Depends: C09, C10, C13, C14. Requirements: static hero with poster still first (video added in C37); search filters; quick actions routed with active-patient guard; menu sheet. Acceptance: visually matches Reference Screen 1 structure (all 12 elements present); live data; empty/error handled. Testing: widget test + manual compare with image. Risks: text contrast over hero.

**C16 — Patient list & create** (§9.2). Acceptance: create patient persists; search debounced; row selects active patient.

**C17 — Patient Overview** (§9.3). Depends: C16, C35. Requirements: header, `InsightCard`, 4 `PillTabs` with embedded tab content widgets (reuse in later screens), sticky bar. Acceptance: matches Reference Screen 2 structure (all 7 elements); stats from data; each tab loads independently.

**C18 — Documents & upload** (§9.4). Acceptance: upload PDF/image works with progress; list shows type/date/confidence/status; process button works.

**C19 — Processing screen** (§9.5). Acceptance: stages update from status endpoint (or staged fallback); completion navigates; failure shows typed error + retry.

**C20 — Camera** (§9.19). Acceptance: capture → preview → use → upload → processing; permission-denied state.

**C21 — Voice** (§9.20). Acceptance: record → upload → transcript → facts flagged needs-verification; permission/STT errors handled.

**C22 — Evidence** (§9.6). Acceptance: from any fact chip reaches doc/page/quote with highlight and confidence.

**C23 — Timeline** (§9.7). Acceptance: chronological, undated group, evidence links.

**C24 — Medications** (§9.8). Acceptance: status tabs, tags for changed/conflict/uncertain, no resolution wording.

**C25 — Medication Reconciliation** (§9.9). Acceptance: `TicketCard` side-by-side matches Reference Screen 3 pass structure; neutral copy; links to both source docs.

**C26 — Investigations** (§9.10). **C27 — Lab Trends** (§9.11; chart styled; single-value empty state). **C28 — Issues** (§9.12; acknowledge/dismiss persisted or local with logged mismatch).

**C29 — Specialty** (§9.13). Acceptance: selection persists and is sent with brief request.

**C30 — Brief** (§9.14). Depends: C29, C36. Acceptance: all sections render from API; every statement has evidence chip; staged loading; fallback/template tagging; disclaimer visible.

**C31 — Consultation editor** (§9.15). Acceptance: create draft from brief; edit/remove/flag; Assessment/Plan empty by default; save version works; unsaved guard.

**C32 — Version history** (§9.16). **C33 — Approval** (§9.17; blocked-state UX; disabled CTA logic; success state). **C34 — Clinical memory** (§9.18; refresh overview after approve).

### PHASE 4 — POLISH & QA

**C37 — Motion & ambient pass**
- Objective: integrate `lightNoWatermark` ambient layer (§7.8) on Home/Brief/Approval; hero parallax; reveal, tab, ring animations (§7.9); refine `TicketCard` clipper. Depends: C15–C34 functional. Acceptance: 60 fps on a mid-range device in profile mode for Home; poster fallback works; reduce-motion honoured; video disposed properly. Risks: performance — fall back to still image.

**C38 — E2E walkthrough & visual QA**
- Objective: run the complete flow (Launch → Home → select patient → overview → upload/process → evidence → timeline → meds → reconcile → labs → issues → specialty → brief → consultation → edit → version → approve → memory updated) on demo data; produce side-by-side screenshots against the 3 reference screens in `docs/frontend/QA/`. Acceptance: every §6.1 inventory element has a ClinSync counterpart; checklist in §18 satisfied; list deviations with reasons. Testing: integration test for happy path with demo mode.

**C39 — Cleanup & documentation**
- Objective: remove dead code/assets, `flutter analyze` + format clean, finalize `README` (run backend, run app, base URL, demo mode), `PROGRESS.md`, `DECISIONS.md`. Acceptance: no unused old-UI remnants; fresh clone runs per README.

---

## 17. CRITICAL IMPLEMENTATION RISKS
1. **Repo unknowns** — plan assumes nothing about existing code; Phase 0 must finish before any deletion.
2. **Contract drift** between Flutter models and backend — mitigated by C03, tolerant parsing, saved JSON fixtures.
3. **Design fidelity drift** — enforce tokens-only styling, component gallery, side-by-side QA vs reference (C38).
4. **Ambient video performance/size** — poster-first, compression, single controller, disposal.
5. **Font availability/licensing** — bundle OFL fonts or the landing page's fonts.
6. **Clinical safety wording** — conflict/trend/missing copy must stay non-directive and non-causal; review all strings.
7. **Device networking** — emulator vs physical device base URL, CORS, cleartext HTTP on Android debug (`usesCleartextTraffic` for dev only) and iOS ATS exception for dev.
8. **Long AI latency** — staged loaders, long timeouts, never block the whole UI.
9. **Permissions** — camera/mic/storage handling on both platforms (Info.plist strings, Android manifest).
10. **No patient photos** — enforce monogram/ambient imagery to avoid privacy issues.
11. **Scope creep** — no login/profile, no extra features beyond §9.

## 18. DEFINITION OF DONE
- [ ] Old frontend UI removed; no competing theme/widgets remain; `pre-redesign-frontend` tag exists.
- [ ] All 20 screens in §9 implemented with loading, empty, and error states.
- [ ] Every element in the §6.1 reference inventory has a counterpart (same structure, ClinSync content); deviations documented.
- [ ] Design tokens are the only source of colour/type/spacing/radius/shadow; no hardcoded styling in screens.
- [ ] Bottom nav, sticky CTA bar, pass card, timeline rail, pill tabs, progress ring, checklist card all present and consistent.
- [ ] Full flow works end-to-end on demo data, online and with Demo mode offline.
- [ ] Confidence, evidence, AI/Doctor-approved markers, and disclaimers present per §6.6; no "correct dose" language anywhere.
- [ ] Camera and voice work with permission handling.
- [ ] Ambient `lightNoWatermark` layer used on Home (and optionally Brief/Approval) with poster fallback.
- [ ] `flutter analyze` clean; tests pass; README accurate.
- [ ] No hardcoded API URL/keys; ClinSync spelled correctly everywhere; no login/auth UI.

## 19. RECOMMENDED EXECUTION ORDER FOR ANTIGRAVITY
`C01 → C02 → C03` (stop; review findings) → `C04 → C05 → C06 → C07 → C08 → C09 → C10 → C11 → C12 → C13 → C14` → `C35` (backend gaps) → `C36` (seed/fallback) → `C15 → C16 → C17` (first demoable slice: Home → Patients → Overview) → `C18 → C19` (upload/process) → `C22 → C23 → C24 → C25` → `C26 → C27 → C28` → `C29 → C30` (brief) → `C31 → C32 → C33 → C34` (consultation → memory) → `C20 → C21` (camera, voice) → `C37 → C38 → C39`.

Milestones: **M1** after C14 (design system gallery matches reference) · **M2** after C17 (demoable shell with live data) · **M3** after C30 (brief) · **M4** after C34 (full loop) · **M5** after C39 (polished, documented).

---

## APPENDIX A — REFERENCE FIDELITY CHECKLIST (use in C38)
For each reference screen, tick when the ClinSync equivalent exists with the same structure:
- **S1:** menu button · avatar slot (specialty circle) · 3-line two-tone serif headline · subtitle · hero art · overlapping search pill + green mic · section header + link · edge-bleeding image cards with scrim + arrow · page dots · Quick Actions 4 tiles · AI banner with right-side mark.
- **S2:** back/title/bookmark/more bar · name + edit · meta line · avatar stack + `+N` · thumbnail · AI card (check, title, 2 meta lines, mini illustration, chevron) · 3-stat strip · pill tabs · rail with numbered green nodes + dotted line · cards (icon, title, chevron, 2 bullets, thumbnail) · add row · sticky green pill + circular filter.
- **S3:** back/title+sub/bell/more bar · pass card (green header, caps label, status pill, 3-column route, connector, dashed divider, 3 key-values, trailing tile) · link row card · two-up metric + progress ring cards · checklist card with bar · green pill CTA + circular share · floating 4-item nav with green active state.

## APPENDIX B — THINGS THE REFERENCE DOES NOT SHOW (do not invent without logging in DECISIONS.md)
Dark mode · tablet layouts · landscape · exact fonts and hex values (estimated only) · bottom nav on Screen 1 and 2 (shown only on Screen 3; this plan applies it to top-level tabs) · pressed/disabled/focus states · empty/loading/error visuals · input form styling · dialogs/sheets · camera/voice UIs. For these, extend the same tokens and component grammar conservatively.
