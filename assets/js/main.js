/* ============================================================
   ClinSync — interaction layer
   Hand-rolled: preloader, smooth reveals, parallax, dynamic UI
   ============================================================ */
(function () {
  "use strict";

  const $  = (s, c = document) => c.querySelector(s);
  const $$ = (s, c = document) => Array.from(c.querySelectorAll(s));
  const clamp = (v, a, b) => Math.min(b, Math.max(a, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fine = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  document.body.classList.add("is-loading");

  /* cross-module scroll hooks (set by later modules) */
  var scrollyHook = null;
  var chapterHook = null;

  /* ----------------------------------------------------------
     1. PRELOADER
     ---------------------------------------------------------- */
  const preloader = $("#preloader");
  const plBar = $("#plBar");
  const plPct = $("#plPct");
  let prog = 0;
  const tick = setInterval(() => {
    prog = Math.min(94, prog + Math.random() * 9 + 3);
    paintPreloader(prog);
  }, 130);

  function paintPreloader(p) {
    p = Math.round(p);
    if (plBar) plBar.style.width = p + "%";
    if (plPct) plPct.textContent = p + "%";
  }

  function finishPreloader() {
    clearInterval(tick);
    paintPreloader(100);
    setTimeout(() => {
      preloader && preloader.classList.add("is-done");
      document.body.classList.remove("is-loading");
      document.body.classList.add("is-ready");
    }, 420);
  }

  if (document.readyState === "complete") {
    setTimeout(finishPreloader, 900);
  } else {
    window.addEventListener("load", () => setTimeout(finishPreloader, 500));
    // safety net
    setTimeout(finishPreloader, 4200);
  }

  /* ----------------------------------------------------------
     2. WORD SPLITTING for editorial headings
     ---------------------------------------------------------- */
  function splitWords(root) {
    const ATOMIC = { EM: 1, I: 1, STRONG: 1 };
    const makeWord = (text) => {
      const outer = document.createElement("span");
      outer.className = "word";
      const inner = document.createElement("span");
      inner.className = "word__in";
      inner.textContent = text;
      outer.appendChild(inner);
      return outer;
    };
    const walk = (node) => {
      Array.from(node.childNodes).forEach((child) => {
        if (child.nodeType === 3) {
          const parts = child.textContent.split(/(\s+)/);
          const frag = document.createDocumentFragment();
          parts.forEach((w) => {
            if (w.trim() === "") frag.appendChild(document.createTextNode(w));
            else frag.appendChild(makeWord(w));
          });
          node.replaceChild(frag, child);
        } else if (child.nodeType === 1) {
          if (ATOMIC[child.tagName]) {
            const outer = document.createElement("span");
            outer.className = "word";
            const inner = document.createElement("span");
            inner.className = "word__in";
            outer.appendChild(inner);
            node.replaceChild(outer, child); // swap in place first
            inner.appendChild(child);         // then move the element in
          } else {
            walk(child);
          }
        }
      });
    };
    walk(root);
    root.classList.add("split-words");
    root.classList.remove("reveal");
    $$(".word", root).forEach((w, i) => {
      $(".word__in", w).style.transitionDelay = (i * 55) + "ms";
    });
  }

  $$(".sec-title, .metric__title, .cta__title, .promise__lines p").forEach(splitWords);

  /* ----------------------------------------------------------
     3. REVEAL ON SCROLL
     ---------------------------------------------------------- */
  const revealTargets = $$(".reveal, .split-words");
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.classList.add("is-in");
          io.unobserve(e.target);
        }
      });
    },
    { threshold: 0.16, rootMargin: "0px 0px -8% 0px" }
  );
  revealTargets.forEach((t) => io.observe(t));

  /* stagger siblings inside grids */
  $$(".problem__grid, .trust__grid, .stats__grid, .evidence__pillars").forEach((grid) => {
    $$(".reveal", grid).forEach((el, i) => {
      el.style.transitionDelay = (i * 70) + "ms";
    });
  });
  $$(".flow").forEach((flow) => {
    $$(".flow__step", flow).forEach((el, i) => (el.style.transitionDelay = (i * 60) + "ms"));
  });
  $$("#timeline").forEach((tl) => {
    $$(".tl-event", tl).forEach((el, i) => (el.style.transitionDelay = (i * 80) + "ms"));
  });

  /* ----------------------------------------------------------
     4. COUNTERS
     ---------------------------------------------------------- */
  const counters = $$("[data-counter]");
  const counterIO = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        const el = e.target;
        const target = parseFloat(el.dataset.counter);
        const suffix = el.dataset.suffix || "";
        const valEl = $(".stat__val", el);
        const dur = 1500;
        let start = null;
        function step(ts) {
          if (!start) start = ts;
          const t = clamp((ts - start) / dur, 0, 1);
          const eased = 1 - Math.pow(1 - t, 3);
          valEl.textContent = Math.round(eased * target) + suffix;
          if (t < 1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
        counterIO.unobserve(el);
      });
    },
    { threshold: 0.5 }
  );
  counters.forEach((c) => counterIO.observe(c));

  /* metric bars */
  const metricIO = new IntersectionObserver(
    (entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        $$(".meter__fill", e.target).forEach((f, i) => {
          setTimeout(() => (f.style.width = f.dataset.w), i * 220);
        });
        metricIO.unobserve(e.target);
      });
    },
    { threshold: 0.4 }
  );
  const metricSection = $("#metric");
  metricSection && metricIO.observe(metricSection);

  /* ----------------------------------------------------------
     5. SCROLL ENGINE (progress, nav, parallax, rails)
     ---------------------------------------------------------- */
  const nav = $("#nav");
  const scrollBar = $("#scrollBar");
  const heroVideo = $("#heroVideo");
  const heroVideos = $$(".hero__video");
  const heroEl = $("#hero");
  const flowEl = $("#workflow");
  const flowRail = $("#flowRail");
  const tlEl = $("#timeline");
  const tlRail = $("#tlRail");
  const briefDoc = $("#briefDoc");

  let ticking = false;
  function onScroll() {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(update);
  }

  /* dynamic resize-safe smooth scrolling */
  let smoothTarget = null;
  function smoothTo(top, dur) {
    if (reduced) {
      window.scrollTo(0, top);
      return;
    }
    const startY = window.scrollY;
    const dist = top - startY;
    const d = dur || Math.min(1400, Math.max(550, Math.abs(dist) * 0.55));
    let t0 = null;
    function step(ts) {
      if (t0 === null) t0 = ts;
      const t = clamp((ts - t0) / d, 0, 1);
      const eased = t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      window.scrollTo(0, startY + dist * eased);
      if (t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  function update() {
    ticking = false;
    const y = window.scrollY;
    const h = document.documentElement.scrollHeight - window.innerHeight;
    const p = h > 0 ? clamp(y / h, 0, 1) : 0;

    if (scrollBar) scrollBar.style.width = (p * 100) + "%";
    if (nav) nav.classList.toggle("is-stuck", y > 40);

    // hero parallax + zoom out
    if (heroEl && !reduced) {
      const hp = clamp(y / window.innerHeight, 0, 1);
      const op = 0.9 - hp * 0.55;
      heroVideos.forEach((v) => {
        v.style.transform = `scale(${1.08 + hp * 0.12}) translateY(${hp * -6}%)`;
        v.style.setProperty("--hero-op", op.toFixed(3));
      });
    }

    // rails fill
    fillRail(flowEl, flowRail);
    fillRail(tlEl, tlRail);

    // brief floating parallax
    if (briefDoc && !reduced) {
      const r = briefDoc.getBoundingClientRect();
      const c = (r.top + r.height / 2 - window.innerHeight / 2) / window.innerHeight;
      briefDoc.style.transform = `translateY(${clamp(c, -1, 1) * -18}px)`;
    }

    // scrollytelling pipeline hook
    if (scrollyHook) scrollyHook();

    // chapter navigator hook
    if (chapterHook) chapterHook(y);

    // top nav active-link hook
    if (navHook) navHook(y);
  }

  function fillRail(section, rail) {
    if (!section || !rail) return;
    const r = section.getBoundingClientRect();
    const total = r.height;
    const progress = clamp((window.innerHeight * 0.5 - r.top) / total, 0, 1);
    rail.style.height = (progress * 100) + "%";
  }

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("resize", onScroll);
  update();

  /* ----------------------------------------------------------
     6. NAV: burger, active link
     ---------------------------------------------------------- */
  const burger = $("#burger");
  const mobileMenu = $("#mobileMenu");
  burger &&
    burger.addEventListener("click", () => {
      const open = mobileMenu.classList.toggle("is-open");
      burger.classList.toggle("is-open", open);
      document.body.style.overflow = open ? "hidden" : "";
    });
  $$("#mobileMenu a").forEach((a) =>
    a.addEventListener("click", () => {
      mobileMenu.classList.remove("is-open");
      burger.classList.remove("is-open");
      document.body.style.overflow = "";
    })
  );

  const navLinks = $$(".nav__links a");
  const navSections = navLinks
    .map((a) => ({ a, el: document.querySelector(a.getAttribute("href")) }))
    .filter((x) => x.el);
  let currentNav = "";
  function updateNavActive(y) {
    const line = y + window.innerHeight * 0.35;
    const ordered = navSections
      .slice()
      .sort((a, b) => a.el.offsetTop - b.el.offsetTop);
    let active = "";
    for (const s of ordered) {
      if (s.el.offsetTop <= line) active = s.a.getAttribute("href");
    }
    const h = document.documentElement.scrollHeight - window.innerHeight;
    if (y >= h - 4 && ordered.length) active = ordered[ordered.length - 1].a.getAttribute("href");
    if (active === currentNav) return;
    currentNav = active;
    navLinks.forEach((l) => l.classList.toggle("is-current", l.getAttribute("href") === active));
  }
  // run on the shared scroll loop
  var navHook = updateNavActive;
  updateNavActive(window.scrollY);

  /* smooth anchor scroll with offset */
  $$('a[href^="#"]').forEach((a) => {
    a.addEventListener("click", (e) => {
      const id = a.getAttribute("href");
      if (id.length < 2) return;
      const target = document.querySelector(id);
      if (!target) return;
      e.preventDefault();
      const top = target.getBoundingClientRect().top + window.scrollY - 70;
      smoothTo(top);
    });
  });

  /* ----------------------------------------------------------
     7. CUSTOM CURSOR
     ---------------------------------------------------------- */
  if (fine) {
    const dot = $("#cursor");
    const ring = $("#cursorRing");
    const label = $(".cursor-ring__label", ring);
    let mx = window.innerWidth / 2, my = window.innerHeight / 2;
    let rx = mx, ry = my;

    window.addEventListener("mousemove", (e) => {
      mx = e.clientX;
      my = e.clientY;
      dot.style.transform = `translate(${mx}px, ${my}px) translate(-50%,-50%)`;
    });
    (function ringLoop() {
      rx = lerp(rx, mx, 0.16);
      ry = lerp(ry, my, 0.16);
      ring.style.transform = `translate(${rx}px, ${ry}px) translate(-50%,-50%)`;
      requestAnimationFrame(ringLoop);
    })();

    const interactive = "a, button, [data-tilt], [data-cursor], .claim, .mini-btn";
    document.addEventListener("mouseover", (e) => {
      const t = e.target.closest(interactive);
      if (!t) return;
      const txt = t.dataset.cursor || "";
      label.textContent = txt;
      ring.classList.toggle("is-active", !!txt);
      ring.style.width = txt ? "" : "58px";
      ring.style.height = txt ? "" : "58px";
    });
    document.addEventListener("mouseout", (e) => {
      if (!e.relatedTarget || !e.relatedTarget.closest(interactive)) {
        ring.classList.remove("is-active");
        label.textContent = "";
        ring.style.width = "";
        ring.style.height = "";
      }
    });
  }

  /* ----------------------------------------------------------
     8. TILT CARDS
     ---------------------------------------------------------- */
  if (fine && !reduced) {
    $$("[data-tilt]").forEach((card) => {
      card.addEventListener("mousemove", (e) => {
        const r = card.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width - 0.5;
        const py = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform = `perspective(900px) rotateY(${px * 5}deg) rotateX(${-py * 5}deg) translateY(-6px)`;
        card.style.transition = "transform .12s linear";
      });
      card.addEventListener("mouseleave", () => {
        card.style.transition = "transform .6s cubic-bezier(.16,1,.3,1)";
        card.style.transform = "";
      });
    });

    /* magnetic buttons */
    $$(".btn").forEach((btn) => {
      btn.addEventListener("mousemove", (e) => {
        const r = btn.getBoundingClientRect();
        const x = e.clientX - (r.left + r.width / 2);
        const y = e.clientY - (r.top + r.height / 2);
        btn.style.transform = `translate(${x * 0.12}px, ${y * 0.2}px)`;
      });
      btn.addEventListener("mouseleave", () => (btn.style.transform = ""));
    });
  }

  /* ----------------------------------------------------------
     9. VOICE WAVEFORM
     ---------------------------------------------------------- */
  const wave = $("#voiceWave");
  if (wave) {
    const bars = 42;
    const els = [];
    for (let i = 0; i < bars; i++) {
      const s = document.createElement("span");
      wave.appendChild(s);
      els.push(s);
    }
    let t = 0;
    setInterval(() => {
      t += 0.28;
      els.forEach((s, i) => {
        const v = Math.abs(Math.sin(i * 0.45 + t)) * Math.abs(Math.sin(t * 0.7 + i));
        s.style.height = (8 + v * 44) + "px";
        s.style.opacity = 0.45 + v * 0.55;
      });
    }, 70);
  }

  /* ----------------------------------------------------------
     10. DYNAMIC INTAKE CHAT
     ---------------------------------------------------------- */
  const chat = $("#chat");
  const chatLog = $("#chatLog");
  const chatPhase = $("#chatPhase");
  const chatScript = [
    { who: "ai", text: "Hi — I'm ClinSync. Tell us what's bothering you today.", phase: "listening", fields: [] },
    { who: "patient", text: "I have stomach pain.", phase: "extracting known information", fields: ["chief_complaint"] },
    { who: "ai", text: "When did the pain begin?", phase: "missing → duration", fields: ["chief_complaint"] },
    { who: "patient", text: "About a week ago.", phase: "extracting known information", fields: ["chief_complaint", "duration"] },
    { who: "ai", text: "Where do you feel the pain most strongly?", phase: "missing → location", fields: ["chief_complaint", "duration"] },
    { who: "patient", text: "Upper abdomen.", phase: "extracting known information", fields: ["chief_complaint", "duration", "location"] },
    { who: "ai", text: "Does anything make it worse?", phase: "missing → triggers", fields: ["chief_complaint", "duration", "location"] },
    { who: "patient", text: "After eating.", phase: "extracting known information", fields: ["chief_complaint", "duration", "location", "triggers"] },
    { who: "ai", text: "Have you experienced nausea or vomiting?", phase: "missing → associated symptoms", fields: ["chief_complaint", "duration", "location", "triggers"] },
    { who: "patient", text: "A little nausea, no vomiting.", phase: "sufficient information collected", fields: ["chief_complaint", "duration", "location", "triggers", "associated"] },
  ];

  function setFields(list) {
    $$(".cf", chat).forEach((c) =>
      c.classList.toggle("is-known", list.includes(c.dataset.f))
    );
  }

  function runChat() {
    let i = 0;
    const next = () => {
      if (i >= chatScript.length) return;
      const step = chatScript[i++];
      chatPhase.textContent = step.phase;
      setFields(step.fields);

      if (step.who === "ai") {
        const typing = document.createElement("div");
        typing.className = "chat__typing";
        typing.innerHTML = "<span></span><span></span><span></span>";
        chatLog.appendChild(typing);
        chatLog.scrollTop = chatLog.scrollHeight;
        setTimeout(() => {
          typing.remove();
          addBubble(step);
          setTimeout(next, 900);
        }, 750);
      } else {
        addBubble(step);
        setTimeout(next, 1000);
      }
    };
    next();
  }

  function addBubble(step) {
    const b = document.createElement("div");
    b.className = "bubble bubble--" + (step.who === "ai" ? "ai" : "patient");
    b.textContent = step.text;
    chatLog.appendChild(b);
    chatLog.scrollTop = chatLog.scrollHeight;
  }

  if (chat) {
    let played = false;
    const chatIO = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting && !played) {
            played = true;
            runChat();
            chatIO.disconnect();
          }
        });
      },
      { threshold: 0.35 }
    );
    chatIO.observe(chat);
  }

  /* ----------------------------------------------------------
     11. EVIDENCE CLAIM SWITCHING
     ---------------------------------------------------------- */
  const claims = $$(".claim");
  const sources = $$(".source");
  claims.forEach((c) => {
    c.addEventListener("click", () => {
      claims.forEach((x) => x.classList.toggle("is-active", x === c));
      sources.forEach((s) => s.classList.toggle("is-active", s.dataset.src === c.dataset.src));
    });
  });

  /* ----------------------------------------------------------
     12. COUNT-UP for brief trend bars (reduced-motion safe)
     ---------------------------------------------------------- */
  if (reduced) {
    $$(".meter__fill").forEach((f) => (f.style.width = f.dataset.w));
  }

  /* ----------------------------------------------------------
     13. CHAPTER NAVIGATOR
     ---------------------------------------------------------- */
  const chapterData = [
    { id: "hero", label: "Overview" },
    { id: "problem", label: "The problem" },
    { id: "manifesto", label: "Philosophy" },
    { id: "workflow", label: "Workflow" },
    { id: "intake", label: "Dynamic intake" },
    { id: "memory", label: "Clinical memory" },
    { id: "evidence", label: "Evidence" },
    { id: "brief", label: "Doctor brief" },
    { id: "architecture", label: "Architecture" },
    { id: "cta", label: "Get started" },
  ];
  const chaptersNav = $("#chapters");
  const chaptersTrack = $("#chaptersTrack");
  if (chaptersNav && chaptersTrack) {
    chapterData.forEach((c) => {
      const a = document.createElement("a");
      a.className = "chapter";
      a.href = "#" + c.id;
      a.dataset.chapter = c.id;
      a.innerHTML = `<span class="chapter__dot"></span><span class="chapter__tip">${c.label}</span>`;
      chaptersTrack.appendChild(a);
    });
    const chapterEls = $$(".chapter", chaptersTrack);
    const chapterPts = chapterData
      .map((c) => {
        const el = document.getElementById(c.id);
        return el ? { id: c.id, el } : null;
      })
      .filter(Boolean);
    let currentChapter = "";

    function updateChapter(y) {
      // line sits at 42% viewport height
      const line = y + window.innerHeight * 0.42;
      let id = chapterPts[0] && chapterPts[0].id;
      for (const c of chapterPts) {
        if (c.el.offsetTop <= line) id = c.id;
      }
      // pin last chapter once near page bottom
      const h = document.documentElement.scrollHeight - window.innerHeight;
      if (y >= h - 4) id = chapterPts[chapterPts.length - 1].id;
      if (id === currentChapter) return;
      currentChapter = id;
      chapterEls.forEach((el) => el.classList.toggle("is-current", el.dataset.chapter === id));
    }

    chapterHook = updateChapter;
    updateChapter(window.scrollY);

    const heroSec = document.getElementById("hero");
    const heroWatch = new IntersectionObserver(
      (entries) => entries.forEach((e) => chaptersNav.classList.toggle("is-visible", !e.isIntersecting)),
      { threshold: 0.55 }
    );
    heroSec && heroWatch.observe(heroSec);
  }

  /* ----------------------------------------------------------
     14. MOUSE SPOTLIGHT
     ---------------------------------------------------------- */
  if (fine && !reduced) {
    const spot = $("#spotlight");
    if (spot) {
      spot.classList.add("is-on");
      let sx = 0, sy = 0, tx = window.innerWidth / 2, ty = window.innerHeight / 2;
      window.addEventListener("mousemove", (e) => {
        tx = e.clientX;
        ty = e.clientY;
      });
      (function spotLoop() {
        sx = lerp(sx, tx, 0.07);
        sy = lerp(sy, ty, 0.07);
        spot.style.setProperty("--mx", sx + "px");
        spot.style.setProperty("--my", sy + "px");
        requestAnimationFrame(spotLoop);
      })();
    }
  }

  /* ----------------------------------------------------------
     15. SCROLL-LIT MANIFESTO
     ---------------------------------------------------------- */
  const manifesto = $("#manifestoText");
  if (manifesto) {
    const sentinel = ["doctor", "authority", "final", "AI", "doctor."];
    const words = manifesto.textContent.trim().split(/\s+/);
    manifesto.innerHTML = words
      .map((w) => {
        const accent = /doctor|authority|AI/i.test(w.replace(/[.,—]/g, ""));
        return `<span class="mword${accent ? " mword--accent" : ""}">${w}</span>`;
      })
      .join(" ");
    const mwords = $$(".mword", manifesto);
    const mIO = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            mwords.forEach((w, i) => setTimeout(() => w.classList.add("is-lit"), i * 26));
            mIO.disconnect();
          }
        });
      },
      { threshold: 0.35 }
    );
    mIO.observe(manifesto);
  }

  /* ----------------------------------------------------------
     16. SCROLLYTELLING PIPELINE
     ---------------------------------------------------------- */
  const scrolly = $("#scrolly");
  if (scrolly) {
    const viewport = $(".scrolly__viewport", scrolly);
    const steps = $$(".sc-step", scrolly);
    const docscan = $("#docscan");
    const docStatus = $("#docscanStatus");
    const docPct = $("#docscanPct");
    const scBar = $("#scrollyBar");
    const statusByStep = ["UPLOADED", "CLASSIFYING", "OCR / VISION", "EXTRACTING", "VALIDATING", "CLINICAL MEMORY"];
    const pctByStep = [8, 26, 48, 70, 88, 100];
    let current = -1;

    function setScrollyStep(i) {
      if (i === current) return;
      current = i;
      steps.forEach((s, k) => s.classList.toggle("is-active", k === i));
      if (docscan) {
        docscan.dataset.active = i;
        docscan.classList.toggle("is-scanning", i === 2);
      }
      if (docStatus) docStatus.textContent = statusByStep[i] || statusByStep[0];
      if (docPct) docPct.textContent = (pctByStep[i] || 0) + "%";
    }

    function updateScrolly() {
      const r = viewport.getBoundingClientRect();
      const total = r.height - window.innerHeight;
      const p = clamp(-r.top / (total || 1), 0, 1);
      if (scBar) scBar.style.width = p * 100 + "%";
      const i = Math.min(steps.length - 1, Math.floor(p * steps.length));
      setScrollyStep(i);
    }
    scrollyHook = updateScrolly;
    setScrollyStep(0);
  }

  /* ----------------------------------------------------------
     17. THEME SWITCHING (dark ⇄ light)
     ---------------------------------------------------------- */
  const root = document.documentElement;
  const toggles = $$("#themeToggle, #themeToggleMobile");

  function syncVideos(theme) {
    const active = theme === "light" ? "--light" : "--dark";
    $$(".hero__video, .brief__video").forEach((v) => {
      const isActive =
        v.classList.contains("hero__video" + active) ||
        v.classList.contains("brief__video" + active);
      if (isActive) v.play().catch(() => {});
      else v.pause();
    });
  }

  function applyTheme(theme, origin) {
    const set = () => {
      root.setAttribute("data-theme", theme);
      try { localStorage.setItem("clinsync-theme", theme); } catch (e) {}
      const meta = document.getElementById("themeColorMeta");
      if (meta) meta.setAttribute("content", theme === "light" ? "#f6f8fc" : "#05070d");
      syncVideos(theme);
      updateToggleUI(theme);
    };

    root.classList.add("theme-anim");
    setTimeout(() => root.classList.remove("theme-anim"), 520);

    if (document.startViewTransition && origin && !reduced) {
      root.style.setProperty("--tx", origin.x + "px");
      root.style.setProperty("--ty", origin.y + "px");
      document.startViewTransition(set);
    } else {
      set();
    }
  }

  function updateToggleUI(theme) {
    const next = theme === "light" ? "dark" : "light";
    toggles.forEach((t) => {
      t.setAttribute("aria-pressed", theme === "light" ? "true" : "false");
      t.setAttribute("aria-label", "Switch to " + next + " mode");
    });
  }

  function currentTheme() {
    return root.getAttribute("data-theme") === "light" ? "light" : "dark";
  }

  toggles.forEach((t) => {
    t.addEventListener("click", (e) => {
      const r = t.getBoundingClientRect();
      const origin = { x: Math.round(r.left + r.width / 2), y: Math.round(r.top + r.height / 2) };
      applyTheme(currentTheme() === "light" ? "dark" : "light", origin);
    });
  });

  // follow OS changes only if the user hasn't chosen explicitly
  window.matchMedia("(prefers-color-scheme: light)").addEventListener?.("change", (e) => {
    let stored = null;
    try { stored = localStorage.getItem("clinsync-theme"); } catch (err) {}
    if (!stored) applyTheme(e.matches ? "light" : "dark", { x: innerWidth / 2, y: 40 });
  });

  updateToggleUI(currentTheme());
  syncVideos(currentTheme());
})();
