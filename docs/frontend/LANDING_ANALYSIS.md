# ClinSync landing page analysis — plan C02 / §5

> §5: *"The landing page was not available when this plan was written. Analyse
> the **actual** implementation … **Report only effects that exist** (read
> CSS/JS/components; do not infer from screenshots alone)."*

Everything below was read out of `index.html`, `assets/css/style.css` and
`assets/js/main.js`. Where an effect does not exist it is marked **ABSENT**, and
where the code contains an effect that never fires it is marked **DEAD** — the
plan's translation rules say an absent effect must not be copied into the app, so
the distinction matters.

File map:

| File | Lines | Role |
|---|---|---|
| `index.html` | 989 | whole page |
| `assets/css/style.css` | 888 | all styling, one flat stylesheet |
| `assets/js/main.js` | 740 | all behaviour, one IIFE |

---

## 1. Stack

| Question | Answer | Evidence |
|---|---|---|
| Framework | **ABSENT** — no React/Vue/Svelte/Astro/Angular/HTMX | only `<script src="assets/js/main.js">` (`index.html:987`) |
| Build step / bundler | **ABSENT** — no `package.json`, no vite/webpack/rollup/esbuild/tailwind config, no lockfile | glob over the repo root |
| CSS preprocessor | **ABSENT** — flat CSS, no `@import`, no nesting | `style.css` |
| Third-party JS | **ABSENT — zero.** 100 % hand-rolled vanilla | `main.js:1-4` comment: *"Hand-rolled: preloader, smooth reveals, parallax, dynamic UI"* |
| Animation library (GSAP/Lenis/AOS) | **ABSENT** — custom `smoothTo()` rAF tween instead | `main.js:204-221` |
| Server-side | **ABSENT** — static only | the single outbound link is `http://127.0.0.1:3000/#/login`, i.e. a Flutter dev server (`index.html:98,111,161,949`) |
| Hosting | Vercel static project, **no build config** (`.vercel/project.json` → `clinsync-landing`; no `vercel.json`) | |

`web/index.html` is the Flutter Web bootstrap and is unrelated to the landing
page. The two are fully independent.

Two inline scripts in the head: `index.html:16-22` **hard-locks the theme to
light** (`data-theme="light"` + `localStorage`) and `index.html:27` adds `.js`
for progressive enhancement. `<noscript>` overrides at `index.html:28-39`.

## 2. Typography

Loaded from Google Fonts only (`index.html:13-15`); **no `@font-face` rules and
no local font files** — `assets/fonts/*.ttf` belong to the Flutter app.

| Family | Weights | Role |
|---|---|---|
| **Plus Jakarta Sans** | 300–700 + italic 400 | primary sans / UI / body |
| **Cormorant Garamond** | 300–700 + italic 300–700 | display serif — the gradient-clipped `<em>` emphasis device |
| **JetBrains Mono** | 400–600 | every label, kicker, HUD line, "code-like" caption |

CSS variables (`style.css:70-72`): `--font`, `--serif`, `--mono`.
Base type (`style.css:138-149`): 400 weight, `line-height 1.68`,
`letter-spacing -0.012em`, antialiased.

Hierarchy (representative):

| Role | Selector | Size | Weight | Family |
|---|---|---|---|---|
| Hero display | `.hero__title` | `clamp(2.6rem, 7.4vw, 6.2rem)` / lh 1.02 / `-.035em` | 300 | sans |
| Hero display accent | `.hero__title em` | 1.06em | 500 italic | **serif** |
| Section title | `.sec-title` | `clamp(1.9rem, 4.4vw, 3.6rem)` / 1.08 / `-.03em` | 300 | sans |
| Kicker | `.sec-tag` | `11px`, `.2em`, uppercase | 500 | mono |
| Lead | `.sec-lead` | `clamp(15px, 1.4vw, 17.5px)` | 300 | sans |
| Stat numeral | `.stat__num` | `clamp(2.4rem, 4.6vw, 3.8rem)`, tabular | 300 | sans |
| Card title | `.pcard h3` | 19px | 500 | sans |
| Card body | `.pcard p` | 14px | 400 | sans |
| Button | `.btn` | 14px | 500 | sans |

**Design rule:** the italic serif `<em>` clipped to a gradient
(`background-clip:text; color:transparent`) is the universal emphasis device
(`.hero__title em`, `.sec-title em`, `.metric__title em`, `.promise__lines em`,
`.cta__title em`).

## 3. Colours

All colours are CSS custom properties in `:root` (dark default, `style.css:7-73`)
overridden by `[data-theme="light"]` (`style.css:76-122`).

| Role | Dark | Light (the one that actually renders) |
|---|---|---|
| `--bg-rgb` | `5,7,13` | `244,235,223` (warm cream) |
| `--bg2-rgb` | `8,11,20` | `235,223,205` |
| `--ink-rgb` | `233,238,247` | `38,26,20` (espresso) |
| `--accent-rgb` | `56,189,248` (sky) | **`226,110,58` (burnt orange)** |
| `--ink-2` | `#aab6c8` | `#5c4a3d` |
| `--ink-3` | `#7c8aa0` | `#6b5645` |
| `--panel` | `rgba(surface,.035)` | same mechanism |
| `--line` / `--line-2` | `rgba(surface,.09)` / `.16` | same |
| `--grad` | sky → indigo → violet | coffee → burnt orange |
| `--shadow-card` | `0 40px 80px -50px rgba(0,0,0,.9)` | `0 40px 80px -50px rgba(74,48,28,.26)` |

Accounting:

* **Exactly one accent channel** (`--accent-rgb`, re-exposed as `--cyan`).
* Only **two named greys** (`--ink-2`, `--ink-3`) plus four alpha ramps.
* Six further semantic hues (`--mint`, `--amber`, `--rose`, `--violet`,
  `--indigo`, `--warm`) that encode *state*, not brand.
* **DEAD tokens** — declared, never referenced: `--scrim`, `--glass`, `--sheet`,
  `--glow`, `--shadow`, `--ease-spring`.
* Two literal colours in the markup that contradict the tokens:
  `var(--accent,#ea580c)` on `index.html:99,111` — `--accent` (without `-rgb`)
  **is never defined**, so the orange fallback always wins — and a hard-coded
  `#0284c7` sky blue one line below it (`index.html:112`).

> **Consequence for ClinSync: none of these colours are adoptable.** The landing
> page's rendered palette is espresso-on-cream with a burnt-orange accent; the
> reference image mandates a sage canvas with a muted green. §0.2 rule 10 keeps
> the reference for the tokens, so ClinSync adopts only the landing page's
> *font families*, never its colours.

## 4. Spacing / radii / shadows

* **No spacing scale.** Section padding is `clamp(80px,12vh,150px) 0`; the
  container is `min(1240px, 92vw)`; card padding is 30/28/26/24px; grid gaps are
  8–44px hand-authored.
* **Radii:** `--radius 18px`, `--radius-lg 26px`, plus 99px pills, `50%`
  circles, and 4–16px on small elements.
* **Shadows:** two large soft ones (`0 40px 80px -50px`, `0 60px 120px -60px`) —
  both warm-brown tinted in light mode — plus small accent glows
  (`0 0 18px rgba(accent,.6)`), a halo ring on active flow nodes, and a
  `drop-shadow` on the preloader dot.

## 5. Surfaces, blur, gradients, glow

* `backdrop-filter` in **4** places: sticky nav `blur(18px) saturate(140%)`
  (`style.css:228`, transitioned `.5s`), mobile menu `blur(20px)` (264), hero
  eyebrow chip `blur(8px)` (285), brief document `blur(14px)` (526).
  `backdrop-filter:none` at 821 is **DEAD** (those selectors never set it).
* `filter: blur()` — **ABSENT** everywhere.
* **13 linear + 11 radial gradients**: hero vignette, hero scrim, hero grid
  lines, workflow background banding, ruled-paper source panes, trend bars,
  confidence bars, scan beam, card sheen sweep, and radial glows for ambient
  orbs / cursor spotlight / CTA / manifesto.
* **Ambient field:** `.ambient` is `position:fixed; inset:0` with three
  `radial-gradient` orbs drifting on 31 s / 37 s / 43 s loops (`driftA/B/C`).
* **Film grain:** fixed SVG `feTurbulence` overlay, `opacity .05`,
  `mix-blend-mode:overlay`, jittered by `grainShift` `8s steps(6) infinite`.
* **Cards:** translucent `rgba(surface,.035)` fill, 18px radius, 1px
  `rgba(surface,.09)` border, shadow only on hover.

## 6. Background video — the `lightNoWatermark` question

### 6.1 Headline finding

> **`lightNoWatermark.mp4` and `darkNoWatermark.mp4` are not referenced anywhere
> in the landing page.** A repo-wide grep for `NoWatermark` across `*.html`,
> `*.css`, `*.js` returns zero matches. The page plays four *different* files
> from `assets/video/`.
>
> `lightNoWatermark.mp4` is referenced only by `tools/extract_ambient_stills.py`
> — the tool this frontend work added to satisfy plan §6.5(a). `darkNoWatermark.mp4`
> is unreferenced anywhere in the repo.

So §5's `[VERIFY]` resolves as: the *name* `lightNoWatermark` is an orphan, but
the artwork it contains is the same ambient chrome-ribbon loop that
`assets/video/hero-light.mp4` and `assets/video/ribbon-light.mp4` are cut from.
That is what made it the correct source for the app's ambient stills.

### 6.2 Where the videos are used

**Hero — two stacked `<video>` elements** (`index.html:126-135`):

| | `#heroVideo` | `#heroVideoLight` |
|---|---|---|
| classes | `hero__video hero__video--dark` | `hero__video hero__video--light` |
| attributes | `autoplay muted loop playsinline preload="auto"` | same |
| poster | `assets/video/hero-dark-poster.jpg` | `assets/video/hero-light-poster.jpg` |
| source | `hero-dark.mp4` | `hero-light.mp4` |
| no | `controls`, no `width`/`height` attrs | |

CSS: `.hero__media{position:absolute;inset:0;z-index:0}`,
`.hero__video{position:absolute;inset:0;object-fit:cover;transform:scale(1.08);
opacity:0;transition:opacity .7s var(--ease)}` (275-276).

Two overlays above the video, then a grid-line layer at `z-index:1` and the
content at `z-index:3`:

| Overlay | Definition |
|---|---|
| `.hero__scrim` | `radial-gradient(120% 90% at 50% 20%, transparent 0%, rgba(bg,.35) 45%, rgba(bg,.9) 80%, bg 100%)` (light override `rgba(bg,.15) 42%` / `rgba(bg,.72) 78%`) |
| `.hero__vignette` | `linear-gradient(180deg, rgba(bg,.55) 0%, transparent 28%, transparent 60%, bg 100%)` |
| `.hero__grid-lines` | 6-column `linear-gradient(90deg, var(--line) 1px, transparent 1px)`, `opacity .5`, top/bottom masked |

**Brief section — two more `<video>` elements** (`index.html:700-707`):
`.brief__bg{position:absolute;inset:0;z-index:0;opacity:.14}` (light `.10`),
`preload="none"` + `autoplay`, and the scrim is a pure `::after`
`radial-gradient(80% 60% at 50% 40%, transparent, bg 85%)` (`style.css:524`).
⚠️ The element classed `--dark` loads `ribbon-**light**.mp4` and the one classed
`--light` loads `ribbon-**dark**.mp4` — the modifiers are crossed relative to the
hero pattern.

### 6.3 How light/dark is chosen

Two elements plus a CSS attribute selector on `html[data-theme]`. There is **no
`prefers-color-scheme` rule for video anywhere** — the only `prefers-*` queries
in the stylesheet are `(hover:hover) and (pointer:fine)` (200) and
`(prefers-reduced-motion:reduce)` (874).

```css
[data-theme="dark"]  .hero__video--dark  { opacity: var(--hero-op, .9) }
[data-theme="light"] .hero__video--light { opacity: var(--hero-op, .9) }
```

`data-theme` is written in three places: the inline head script
(`index.html:16-22`, which **always forces `"light"`**), `applyTheme()`
(`main.js:689-709`), and the OS-preference listener (`main.js:732-736`) — the
last of which is therefore dead.

**Net effect as shipped:** the page always renders `hero-light.mp4` in the hero
and `ribbon-dark.mp4` in the brief; `hero-dark.mp4` and `ribbon-light.mp4` are
still fetched and decoded but never visible.

### 6.4 The only JS that touches video

```js
678:  function syncVideos(theme) {
679:    const active = theme === "light" ? "--light" : "--dark";
680:    $$(".hero__video, .brief__video").forEach((v) => {
681:      const isActive =
682:        v.classList.contains("hero__video" + active) ||
683:        v.classList.contains("brief__video" + active);
684:      if (isActive) v.play().catch(() => {});
685:      else v.pause();
686:    });
687:  }
```

Called from `applyTheme()` (695) and once at boot (739). **No mute/unmute logic**
(`muted` is a static attribute only). **No IntersectionObserver and no
`visibilitychange` handler for video** — the loops play forever, including when
scrolled out of view and when the tab is backgrounded. **No reduced-motion
handling for video**: `prefers-reduced-motion` collapses animation/transition
durations to `.001ms` (`style.css:874-888`) but cannot stop `<video>`
playback, and `main.js:12`'s `reduced` flag guards smooth scroll, parallax, tilt
and spotlight only.

Also: `const heroVideo = $("#heroVideo")` (`main.js:186`) is assigned and never
read; `#heroVideoLight` is never referenced anywhere.

### 6.5 Hero parallax over the video (scroll-linked)

```js
234:  const hp = clamp(y / window.innerHeight, 0, 1);
235:  const op = 0.9 - hp * 0.55;                       // 0.9 → 0.35
236:  heroVideos.forEach((v) => {
237:    v.style.transform = `scale(${1.08 + hp * 0.12}) translateY(${hp * -6}%)`;
238:    v.style.setProperty("--hero-op", op.toFixed(3));
239:  });
```

Scale `1.08 → 1.20`, translate `0 → −6%`, opacity `0.9 → 0.35`, over the first
viewport of scroll. Gated on `!reduced`.

### 6.6 Video file facts (measured with `ffprobe`)

| File | Codec | Resolution | fps | Duration | Size |
|---|---|---|---|---|---|
| `lightNoWatermark.mp4` | h264 (yuv420p) | **1280×720** | 24 | **19.00 s** | **3 250 944 B (3.1 MB)** |
| `darkNoWatermark.mp4` | h264 (yuv420p) | 1920×1080 | 24 | 18.66 s | 12 410 417 B (11.8 MB) |
| `assets/video/hero-light.mp4` | h264 | 1600×900 | 24 | 19.00 s | 1 633 849 B (1.6 MB) |
| `assets/video/hero-dark.mp4` | h264 | 1600×900 | 24 | 18.58 s | 2 459 248 B (2.3 MB) |
| `assets/video/ribbon-light.mp4` | h264 | 1280×720 | 24 | 19.00 s | 1 164 262 B (1.1 MB) |
| `assets/video/ribbon-dark.mp4` | h264 | 1280×720 | 24 | 18.58 s | 1 546 290 B (1.5 MB) |

Content (verified by extracting frames): every light-mode file is the **same
subject** — a polished chrome ribbon / Möbius loop on a near-white studio
backdrop, slowly rotating. The dark files are a glowing blue-violet light arc
over wet rock. **No people appear in any frame.**

The app ships the two light loops (`hero-light`, `ribbon-light`, 2.7 MB total) —
inside the ≤ 8 MB / ≤ 1080 p budget §7.8 sets. `darkNoWatermark.mp4` at 11.8 MB
and 1080 p is over budget and is not shipped.

## 7. Animations & transitions

15 `@keyframes`: `themeReveal` (`.62s`, **DEAD** — the theme toggle element does
not exist), `driftA/B/C` (31/37/43 s ambient orbs), `grainShift` (`8s steps(6)`),
`spin` (6 s preloader ring), `pulse` (2.4 s), `scrollLine` (2.2 s),
`marquee` (38 s linear, pauses on hover), `pulse2` (1.4 s recording dot),
`bubbleIn` (`.6s`), `typing` (1.2 s), `srcIn` (`.5s`), `glowBreath` (9 s),
`beam` (1.5 s document-scan line), `iconPop` (**DEAD**).

Easing: `--ease cubic-bezier(.22,.61,.36,1)` (workhorse), `--ease-out
cubic-bezier(.16,1,.3,1)` (reveals/hover), `--ease-spring` **DEAD**.

Durations in use: `.12 .2 .25 .3 .35 .4 .45 .5 .55 .6 .62 .7 .8 1 1.1 1.4 1.6 1.8 s`.
CSS smooth scroll is explicitly **off** (`html{scroll-behavior:initial}`) and
replaced by a hand-rolled `easeInOutCubic` tween (`main.js:204-221`, duration
`clamp(550, 1400, |Δ|·0.55) ms`, with a −70 px offset for the fixed nav).

**Scroll reveal** — one `IntersectionObserver` for everything
(`main.js:109-121`), `{threshold: .16, rootMargin: "0px 0px -8% 0px"}`, adding
the class **`is-in`** once and then unobserving. Base transition
`opacity + translateY(34px) → 0`, `1s var(--ease-out)` (`style.css:338-339`).
Stagger is set from JS as inline `transitionDelay`: 70 ms per card, 60 ms per
flow step, 80 ms per timeline event, 55 ms per split word. Headings are split
word-by-word and each word rises from `translateY(110%) rotate(2deg)`.

Sticky nav: `position:fixed`, `is-stuck` toggled at `scrollY > 40`
(`main.js:230`), which adds `backdrop-filter: blur(18px) saturate(140%)`, a
background, a bottom border, and shrinks padding 20 → 13 px.

Scrollytelling: a 420 vh viewport with a sticky 100 svh stage and six
absolutely-stacked steps; the active step also drives a mock document-scan
widget's status text and percentage. Under reduced motion it degrades to all
steps shown statically.

## 8. Hover & interaction effects

| Effect | Detail |
|---|---|
| Button hover | `translateY(-2px)` + `0 12px 30px -12px rgba(ink,.5)` shadow; the SVG icon nudges `translateX(4px)` over `.4s` |
| Magnetic buttons | JS: button translates toward the cursor by `x*0.12, y*0.2` px |
| Card hover | `translateY(-6px)`, brighter border, `--shadow-card`, plus a 160 px radial `.pcard__glow` fading 0 → 1 |
| Card sheen | `::after` gradient sweeps `translateX(-130%) → 130%` over `1s` on hover |
| 3D tilt | `[data-tilt]` on 7 elements: `perspective(900px) rotateY(±5deg) rotateX(∓5deg)` over `.12s linear`, springing back over `.6s ease-out` |
| Nav link | `::after` underline grows from `width:0;left:50%` to `width:40%;left:30%` in `.35s` |
| Brand mark | rotates `120deg` over `.6s` on hover |
| Custom cursor | 6 px dot follows the mouse directly; a 40 px ring **lerps at 0.16** in a rAF loop; expands to 76 px with a mono label over interactive elements (`a, button, [data-tilt], [data-cursor], .claim, .mini-btn`) |
| Cursor-follow spotlight | 340 px `radial-gradient` glow lerping at **0.07** toward the pointer |
| Grain / orbs / glows | `pointer-events:none` |

⚠️ The custom cursor **never hides the native one** — there is no `*{cursor:none}`.

## 9. Component patterns

27 distinct patterns; the ones that matter for a mobile translation are the
**nav** (fixed, blur-on-scroll), **hero** (2 videos + scrim + vignette + grid
lines + HUD), **stat counters** (`1-(1-t)³`, 1500 ms), **card grids**
(problem/trust, with `grid-template-rows:subgrid` so cards share row tracks),
**workflow timeline** (rail + nodes + chips), **clinical timeline**
(year groups + event dots + kind chips), **evidence claim/source pair**
(click a claim → its source pane lights up with a `<mark>` highlight),
**brief document mock** (a mac-window chrome with 7 sections, a trend bar and an
evidence footer), **chapter navigator** (10 JS-generated dots), **ambient field**
(3 orbs), **grain**, **cursor**, **spotlight**, **preloader** (fake progress,
finishes on `load + 500 ms`, hard safety net at 4200 ms).

**ABSENT:** modal/dialog, accordion, tabs, carousel, pricing table, testimonial,
logo wall, cookie banner, `<form>` (there is none anywhere), table, breadcrumb,
pagination, skeleton.

## 10. Page structure (19 sections)

`nav` → `hero` → `marquee band` → `stats` (4 counters) → `scrolly` processing
pipeline (6 steps) → `problem` (6 cards) → `manifesto` → `workflow` (8 steps) →
`patient` (voice card) → `intake` (chat mock) → `memory` (timeline + trend) →
`evidence` (3 claims ↔ 3 sources) → `brief` (the north-star document) →
`trust` (6 cards) → `architecture` → `metric` (2 meters) → `promise` (4 lines) →
`cta` → `footer`.

Copy anchors worth keeping for ClinSync's own voice: *"Know the patient before
you meet the patient"*, *"ClinSync is not an AI doctor … the doctor remains the
final authority"*, *"The patient tells the story once / ClinSync remembers it /
The doctor gets the relevant picture / The doctor makes the decision"*.

## 11. Imagery — the patient-photo question

> **`index.html` contains zero `<img>` tags.** The landing page renders **no
> photographs and no raster images at all**: 4 `<video>` elements, 4 poster JPEGs,
> and 13 inline `<svg>` elements. The only `url()` in the CSS is an inline SVG
> data-URI for the grain filter.

`assets/images/` holds nine files. **The landing page references none of them.**

| File | Identifiable person? | Note |
|---|---|---|
| `doctor_carter.jpg` | **YES** — clinician headshot, hospital corridor | must never stand in for a patient |
| `avatar_willie.jpg` | **YES** — profile portrait | must never stand in for a patient |
| `event_gamification.jpg` | **YES** — lifestyle shot, people in frame | must never stand in for a patient |
| `hospital_building.jpg` | no — architecture only | |
| `ambient-hero.jpg` | no — duotone still of `hero-light.mp4` frame 96 | app asset |
| `ambient-ribbon.jpg` | no — duotone still of `ribbon-light.mp4` frame 132 | app asset |
| `ambient-mist.jpg` | no — duotone still of `lightNoWatermark.mp4` frame 48 | app asset |
| `ambient-mist-alt.jpg` | no — frame 216 | app asset |
| `ambient-mist-third.jpg` | no — frame 408 | app asset |

The Flutter app references **none** of the three human photographs
(`grep doctor_carter|avatar_willie|event_gamification lib/` → 0 hits), which is
the §6.5 requirement satisfied by construction.

## 12. Brand

The mark is a 32×32 inline SVG drawn in three primitives: a faint full ring
(`r=12.5`, `stroke-width 1.6`, `opacity .35`), a bold quarter-arc from 12 o'clock
to 3 o'clock (`stroke-width 2.4`, round cap), and a solid centre dot (`r=3.4`).
All strokes use `currentColor`, and the container is coloured `var(--cyan)` =
the accent channel — so the mark is **orange in the rendered light theme**. The
favicon is an inline data-URI SVG hard-coded to the *dark-theme* sky blue
`#38bdf8`, so it does not match the page. The wordmark is text, not an image:
`ClinSync` at `18.5px / 600 / -.02em` in the sans. The preloader renders the
wordmark in the serif, uppercase, at `36px / letter-spacing .12em`.

> **ClinSync uses a serif `C` monogram in a soft circle instead of this mark**,
> because §6.5 says to use a repo logo asset "if one exists" and a drawing of the
> SVG mark would have to be hand-recreated in Flutter. Logged as a deviation in
> `DECISIONS.md`. The brand name is spelled `ClinSync` everywhere; the favicon is
> the only place the accent colour is frozen at a value that no longer matches
> the page.

---

## 13. What got translated into the Flutter app

§5.2's translation table, applied to the effects that actually exist:

| Landing effect (exists?) | ClinSync translation |
|---|---|
| Background video — **yes** | `AmbientLayer` + `AmbientVideo`: muted, looping, `BoxFit.cover`, no controls, poster always painted underneath, paused when backgrounded, disabled under reduce-motion. Skipped on web (platform view). `DECISIONS.md` FD-04/FD-05. |
| Hero video scrim + vignette — **yes** | `AppColors.ambientWash` over the video, plus `AmbientLayer`'s three-stop `bgCanvas` wash; hero `washOpacity: 0.52`. FD-06. |
| Scroll reveal (`is-in`, fade + translate) — **yes** | `SectionReveal`: fade + 12 px upward translate, 280 ms, 40 ms stagger, once per screen build, honouring reduce-motion. |
| Hero parallax — **yes** | `AmbientParallax`, factor clamped to ≤ 0.25 (default 0.18), hero only, off under reduce-motion. |
| Sticky nav blur — **yes** (but the reference image shows a floating bottom bar, not a top bar) | `StickyActionBar` / bottom nav are opaque white with `AppShadows.float`; **no backdrop blur**, because §5.2 only allows it "where the reference shows a floating bar" and the reference's own nav is solid white. |
| Hover lift/glow on cards — **yes** | `PressScale`: scale 0.98, 120 ms ease-out. |
| Hover underline on links — **yes** | `AppButton.link`/`link` colour shift, no underline animation. |
| Counters — **yes** | `AnimatedCount`: 0 → value over 700 ms `easeOutCubic`. |
| Active-node pulse — **yes** (`pulse`) | `SoftPulse`: 1.00 ↔ 1.08, 900 ms, processing nodes only. |
| Card sheen sweep — **yes** | **not translated**: it is a hover-only effect on a desktop grid of 6 cards; the app has no equivalent surface and §5.2 says absent/untranslatable effects stay out. |
| Cursor-follow glow, custom cursor, 3D tilt, magnetic buttons, grain, marquee, scrollytelling — **yes on the landing page** | **not translated**: pointer-driven, with no touch equivalent. §5.2 explicitly says cursor-follow / mouse glow is "not translated". |
| Gradient-clipped italic serif `<em>` — **yes** | **not translated as a gradient**: the reference headline is a solid two-tone serif (`textPrimary` line 1, `primary` lines 2–3), and §5.2 says to default to solid green + near-black serif. |
| Landing page colours — **yes** | **not adopted**: espresso/cream/burnt-orange contradicts the reference's sage palette. Only the *font families* are adopted. |
| Theme toggle, dark theme — **DEAD on the landing page** (locked to light) | ClinSync is light-only, which is consistent. |
| Reduced-motion support — **partial** (CSS only; video keeps playing) | ClinSync honours `MediaQuery.disableAnimations` in **every** motion primitive *including* the video, which the landing page does not. |
