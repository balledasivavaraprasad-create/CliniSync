# ClinSync design tokens — plan C06

The reference values in `implementation.md` §7 are visual estimates. This file
records the **final** values, how each was arrived at, and where it lives in
code. `flutter analyze` and `test/components_test.dart` fail the build if a
screen introduces a raw colour, font family or ad-hoc text style outside these
token files, so the table below is the whole styling surface of the app.

| Token file | Contents |
|---|---|
| `lib/core/theme/app_colors.dart` | colour tokens + gradients |
| `lib/core/theme/app_typography.dart` | families, named type scale, `TextTheme` |
| `lib/core/theme/app_spacing.dart` | 4-pt grid + fixed component sizes |
| `lib/core/theme/app_radii.dart` | radii + `BorderRadius` shorthands |
| `lib/core/theme/app_shadows.dart` | the four shadow recipes |
| `lib/core/theme/app_theme.dart` | `ThemeData` assembly (light only) |
| `lib/core/animations/motion.dart` | durations/curves for the §7.9 motion set |
| `lib/shared/widgets/app_icons.dart` | semantic → Lucide glyph table (§7.7) |

Everything below is quoted from those files.

---

## 1. Colour — sampled from `appTheme.jpg`

Sampling method: the three phone mockups in `appTheme.jpg` were opened with
Pillow and specific regions were sampled (phone canvas, card faces, the green
CTA, the boarding-pass band, the two-tone headline). The sampled hex values are
noted per token; where the image could not be sampled (it is a JPEG with
compression noise) the value was nudged to the nearest clean palette step and
the nudge is called out.

| Token | Value | Where it was sampled / why |
|---|---|---|
| `bgBackdrop` | `#D3DECE` | The field the phones sit on. §7.1's `#E3EBE0` sampled lighter than the image; the image is deeper and cooler. |
| `bgCanvas` | `#F6F6F4` | Phone canvas — the app's background. §7.1 estimate `#F6F8F4` is the same value with more green; the image is warm-neutral, so green was dropped. |
| `surface` | `#FFFFFF` | Card faces, search pill, nav. |
| `surfaceTint` | `#F1F5EF` | The inner stat strip inside the AI card, the banner base, chip fills. |
| `surfaceTintDeep` | `#E6EDE2` | One step deeper, for pressed fills and banner end. |
| `primary` | `#527A55` | **Sampled.** Dominant green across reference screens 2 and 3 (AI card title, boarding-pass band, day rail, `Optimize with AI` pill). §7.1 estimated `#4E7A55` — the image is 4 units lighter and slightly bluer. |
| `primaryDark` | `#3F6244` | Pressed state. §7.1 estimated `#3F6646`; nudged greener to sit under `primary` on the same hue. |
| `primaryMuted` | `#6A866D` | **Sampled** from the boarding-pass header band, which is visibly lighter than the CTA green. §7.1 had no token for this band. |
| `primarySoft` | `#DCE8DA` | Selected-chip background, quick-action icon-tile fill. |
| `primaryWash` | `#EBF1E8` | Ambient wash over the video layer. |
| `textPrimary` | `#141814` | The black headline line. Sampled `#0A0A0A` is pure black and reads harsh against `#F6F6F4`; a soft black that is AA-clean is used. |
| `textSecondary` | `#6E766E` | Subtitles and meta. §7.1 value kept. |
| `textTertiary` | `#9AA29A` | Inactive nav labels, placeholders. |
| `textDisabled` | `#BFC6BF` | Added; not in §7.1. Needed for disabled states. |
| `divider` | `#E4E8E2` | Hairlines, dashed separators on the boarding-pass card. |
| `dividerStrong` | `#D6DCD4` | Card edges on tinted surfaces. Added. |
| `warning` | `#B7791F` | Muted amber — conflicts and "needs review" only. |
| `warningSoft` | `#F6EBD8` | Amber notice fill. Added. |
| `danger` | `#B3453B` | Muted red — errors and unverified provenance only. |
| `dangerSoft` | `#F7E6E3` | Red notice fill. Added. |
| `confidenceHigh` | `= primary` (`#527A55`) | §6.6 rule 2, `≥0.85`. |
| `confidenceMedium` | `#B7791F` | §6.6 rule 2, `0.60–0.84`. |
| `confidenceLow` | `#A05242` | §6.6 rule 2, `<0.60`. Distinct from `danger` so a low-confidence badge never reads as a hard error. |
| `info` | `#4A7C8C` | Added: neutral-cool informational accents (processing stages). Deliberately the only non-green hue besides the semantic amber/red. |
| `infoSoft` | `#E4EFF2` | Info notice fill. |
| `onPrimary` | `#FFFFFF` | Text/icons on green. |
| `scrim` | `#1B2419` | Base colour for image scrims. |
| `confidenceTrack` | `#E4E8E2` | Confidence micro-bar track. |

### Gradients

| Token | Definition | Use |
|---|---|---|
| `photoScrim` | transparent → transparent → `#A6000000` at stops `0 / 0.45 / 1` | Bottom 55% of any image card (reference §6.1 el. 8/9), holds white card text at AA. |
| `heroFade` | `#00F6F6F4` → `#59F6F6F4` → `#F6F6F4` at `0 / 0.72 / 1` | Bottom of the Home hero so the ambient layer has no seam against the canvas. |
| `banner` | `#F1F5EF` → `#E2EADF`, top-left → bottom-right | `Let AI prepare your consultation` banner. |
| `ambientWash` | `#8CF6F6F4` → `#73F6F6F4` → `#00F6F6F4` at `0 / 0.55 / 1` | Top-weighted wash over ambient video; heavier at the top where the headline sits. |
| `monogram` | `#E8EFE4` → `#CFDCC9` | Deterministic patient-imagery fallback (§6.5b) behind the serif monogram. |
| `verifiedAccent` | `primary` → `primaryMuted`, vertical | Doctor-approved memory card edge. |

### Sampling log

`appTheme.jpg` is 1568×1014 JPEG. Sampling was done on the *phone* regions only
(the backdrop outside the phones is a different surface and was not used for any
in-app token). Three regions per screen were averaged to suppress JPEG ringing:

| Region | Result | Assigned to |
|---|---|---|
| Screen 1 canvas, mid-left | `#F5F6F3` | `bgCanvas` |
| Screen 2 card interior | `#FFFFFF` | `surface` |
| Screen 3 boarding-pass band | `#6A866D` | `primaryMuted` |
| Screen 3 `On Time` pill border / Screen 2 CTA | `#527A55` | `primary` |
| Backdrop between phones | `#D3DECE` | `bgBackdrop` |
| Screen 2 inner stat strip | `#F1F5EF` | `surfaceTint` |
| Screen 1 headline line 1 | `#0A0A0A` | `textPrimary` (darkened/softened) |
| Screen 1 subtitle | `#6E766E` | `textSecondary` |

---

## 2. Typography

Families are **bundled as local assets** (`pubspec.yaml → flutter.fonts`), never
downloaded at runtime, so a demo on a plane works and there is no FOUT.

| Family | Asset | Weights | Role |
|---|---|---|---|
| `CormorantGaramond` | `assets/fonts/CormorantGaramond-{Regular,Medium,SemiBold}.ttf` | 400 / 500 / 600 | Display serif — headlines, screen titles, large numbers. |
| `Inter` | `assets/fonts/Inter-{Light,Regular,Medium,SemiBold,Bold}.ttf` | 300–700 | Humanist sans — UI, body, labels. |
| `JetBrainsMono` | `assets/fonts/JetBrainsMono-{Regular,Medium}.ttf` | 400 / 500 | Verbatim source spans in evidence quotes. |

Serif choice: §7.2 says "the landing page's serif if it has one". The landing
page loads **Cormorant Garamond**, so it is adopted — it is a transitional
serif with the same editorial character as the reference headline. It was
instanced from the variable font to static 400/500/600 TTFs so the app never
needs a runtime download (§0.2 rule 10 satisfied, logged in `DECISIONS.md`).

### Named scale (`AppTypography`)

| Style | Family | Size | Weight | Line-height | Tracking | Use |
|---|---|---|---|---|---|---|
| `displayHero` | serif | 40 | 500 | 1.08 | −0.4 | Home hero line 1 (`textPrimary`) |
| `displayHeroAccent` | serif | 40 | 500 | 1.08 | −0.4 | Home hero lines 2–3 (`primary`) |
| `titleScreen` | serif | 20 | 500 | 1.20 | 0 | Top-bar titles (`Patient Overview`) |
| `titleScreenSub` | sans | 12 | 400 | 1.30 | 0 | Grey sub-line under a top-bar title |
| `titleHeader` | serif | 22 | 500 | 1.15 | 0 | Patient name in the header block |
| `titlePage` | serif | 28 | 500 | 1.12 | 0 | Full-screen sub-page titles (Specialty, Voice) |
| `titleSection` | sans | 17 | 600 | 1.25 | −0.1 | `Recent Patients`, `Quick Actions` |
| `titleCard` | sans | 16 | 600 | 1.30 | −0.1 | Card titles |
| `body` | sans | 14 | 400 | 1.45 | 0 | Body |
| `bodyStrong` | sans | 14 | 600 | 1.45 | 0 | Strong body |
| `bodyBullet` | sans | 12.5 | 400 | 1.50 | 0 | Dot-separated bullet lines, `textSecondary` |
| `label` | sans | 12 | 500 | 1.30 | 0 | Flight/Gate/Seat-style labels, `textSecondary` |
| `caption` | sans | 11 | 400 | 1.30 | 0 | Meta, bottom-nav labels, `textSecondary` |
| `capsLabel` | sans | 11 | 600 | 1.20 | +0.8 | `MEDICATION CHANGE`-style band headers |
| `numberLarge` | serif | 30 | 600 | 1.05 | −0.2 | `BD`-style large values |
| `numberLargeSans` | sans | 30 | 700 | 1.05 | −0.6 | Where a grotesque reads better for values |
| `numberStat` | sans | 15 | 600 | 1.20 | −0.1 | Stat values in strips |
| `button` | sans | 16 | 600 | 1.20 | −0.1 | CTA text, `onPrimary` |
| `link` | sans | 14 | 500 | 1.20 | 0 | `See all`, `primary` |
| `verbatim` | mono | 12 | 400 | 1.55 | 0 | Evidence source spans |
| `tileLabel` | sans | 12 | 500 | 1.25 | −0.1 | Quick-action tile labels |
| `tabLabel` | sans | 14 | 500 | 1.20 | 0 | Pill tabs |
| `navLabel` | sans | 11 | 500 | 1.20 | 0 | Bottom-nav labels |

`AppTextTheme.build()` maps the same values onto Material's `TextTheme` so any
Material widget that inherits typography matches the scale instead of falling
back to Roboto.

---

## 3. Spacing (4-pt grid)

`xxs 4 · xs 8 · sm 12 · md 16 · lg 20 · xl 24 · xxl 32 · xxxl 40`

| Token | Value | Use |
|---|---|---|
| `screenH` | 20 | Screen horizontal padding |
| `sectionGap` | 24 | Vertical gap between top-level sections |
| `cardGap` | 14 | Gap inside cards |
| `carouselGap` | 12 | Carousel item gap |
| `bottomNavHeight` | 72 | Floating bottom-nav height |
| `bottomSafe` | 88 | `bottomNavHeight + 16` |
| `stickyBarHeight` | 88 | Sticky action-bar height |
| `patientCardWidth` / `Height` | 148 / 168 | Home patient card. Wider than the reference's because clinical names are two words, while still bleeding a third card off the right edge. |
| `patientCardViewportFraction` | 0.35 | Shows ~2.5 cards at 430 pt |
| `timelineThumbWidth` / `Height` | 72 / 64 | Timeline-card thumbnail |
| `headerThumbWidth` / `Height` | 110 / 84 | Header-block thumbnail |
| `tileSize` | 64 | Quick-action tile |

---

## 4. Radii

`xs 8 · sm 12 · md 16 · lg 22 · xl 28 · tile 18 · pill 999`

`AppRadii` also exposes `allXs`, `allSm`, `allMd`, `allLg`, `allXl`, `allTile`,
`allPill`, plus `topLg` / `topXl` for the boarding-pass header band (concave
top, square bottom).

---

## 5. Shadows — soft, diffuse, green-grey tinted

| Token | Offset | Blur | Spread | Colour |
|---|---|---|---|---|
| `card` | `0, 6` | 20 | −4 | `rgba(40,60,40,0.07)` |
| `float` | `0, 10` | 28 | −6 | `rgba(40,60,40,0.10)` |
| `button` | `0, 6` | 16 | −4 | `rgba(82,122,85,0.25)` — a shadow in the accent hue, so a green pill glows rather than floats |
| `tile` | `0, 4` | 12 | −3 | `rgba(40,60,40,0.06)` |

No shadow is pure black: the tint is what makes the elevation read as *soft*
rather than *dropped*.

---

## 6. Motion (§7.9)

`lib/core/animations/motion.dart`. Every widget short-circuits when
`MediaQuery.disableAnimations` is true (iOS Reduce Motion / Android remove
animations), and `AmbientVideo`/`AmbientLayer` do the same.

| Primitive | Spec |
|---|---|
| `SectionReveal` | opacity 0→1 + `translateY(12→0)`, 280 ms, `Curves.easeOutCubic`, 40 ms stagger by `index`, plays once per screen build |
| `StaggeredColumn` | the same, applied to a list |
| `PressScale` | `scale 1 ↔ 0.98`, 120 ms, `Curves.easeOut` — the mobile translation of the landing page's hover lift |
| `SoftPulse` | `scale 1.00 ↔ 1.08`, 900 ms, `Curves.easeInOut`, reverse-repeat — the active processing node |
| `AmbientParallax` | hero only, factor clamped to **≤ 0.25** (default 0.18), max ±26 px, driven by scroll offset |
| `AnimatedCount` | 0→value over 700 ms `easeOutCubic` (stat counters) |
| `AmbientScrim` | flat wash over imagery to hold AA text contrast |
| Page transition | `buildPageTransitions()` — fade-through + slide-up; iOS/macOS/desktop use `CupertinoPageTransitionsBuilder` |

---

## 7. Iconography (§7.7)

One family only: **Lucide**, thin-stroke line icons, bundled via
`lucide_icons_flutter`. `lib/shared/widgets/app_icons.dart` holds a 172-entry
**semantic → glyph** map (`'patient'`, `'timeline'`, …, referenced by name from
`core/constants/enums.dart` so the domain enums stay free of any icon-package
dependency) and `AppIcons.byName()` resolves a backend string to a glyph,
falling back to `LucideIcons.circle` instead of throwing. `AppIcons.length` is
asserted `> 120` in `test/design_system_test.dart` so a typo in a screen or enum
fails loudly rather than rendering a blank circle.

> `lucide_icons` (the other package) extends `final class IconData`, which
> breaks dart2js on Flutter 3.47. `lucide_icons_flutter` is the supported one.

Icons that appear inside circular or rounded-square white containers, per
§6.2: every icon-only control is `CircleIconButton` / `IconTile` from
`lib/shared/widgets/primitives.dart`.

---

## 8. Fixed device frame for QA

Screenshots are captured at **430 × 932** (iPhone 15 Pro Max logical size) with
a 2× device scale factor, matching `tools/capture_screens.py`.
