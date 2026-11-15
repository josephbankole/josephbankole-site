/* josephbankole.ca /lab — cinematic prototype behaviour.
   No libraries. Animate transform + opacity only. Reduced-motion safe.
   PostHog events: hero_skip. Link clicks are bound centrally by
   /assets/analytics.js. The waitlist, its floating pill and the
   configurator's waitlist button were removed on 2026-09-23, and the
   configurator itself on 2026-11-15: it sized a client build, and he is
   not taking client work. */
(function () {
  "use strict";

  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var clamp = function (v, a, b) { return v < a ? a : v > b ? b : v; };
  var $ = function (id) { return document.getElementById(id); };

  function cap(name, props) {
    if (window.posthog && posthog.capture) {
      var p = { site: "josephbankole.ca", surface: "lab" };
      if (props) for (var k in props) p[k] = props[k];
      try { posthog.capture(name, p); } catch (e) {}
    }
  }

  document.body.classList.remove("preload");

  var heroBand = $("top");

  /* ---------------------------------------------------------
     ACT 1 · COLD OPEN
     --------------------------------------------------------- */
  var overlay = $("coldOpen");
  var feed = $("coFeed");
  var headline = $("coHeadline");
  var skipBtn = $("coSkip");
  var finished = false, cancelled = false;

  var PASS1 = [
    { t: "02:00:14", s: "  SWIFT MT103 batch failure. 4,112 records held." },
    { t: "02:01:02", s: "  paging on-call" },
    { t: "02:03:19", s: "  poison record found: malformed field 59" },
    { t: "02:04:50", s: "  batch resubmitted, bad record quarantined" },
    { t: "05:47:08", s: "  settlement released. loss: none. sleep: none." }
  ];
  var PASS2 = [
    { t: "02:00:14", s: "  SWIFT MT103 batch failure. 4,112 records held." },
    { t: "02:00:16", s: "  agent: poison record isolated", agent: true },
    { t: "02:00:31", s: "  agent: batch resubmitted", agent: true },
    { t: "02:00:52", s: "  settled. human asleep.", agent: true }
  ];

  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  async function typeLine(line, perChar) {
    var el = document.createElement("span");
    el.className = "fl" + (line.agent ? " agent" : "");
    var b = document.createElement("b");
    b.textContent = line.t;
    el.appendChild(b);
    var txt = document.createTextNode("");
    el.appendChild(txt);
    var caret = document.createElement("span");
    caret.className = "caret";
    el.appendChild(caret);
    feed.appendChild(el);
    for (var i = 0; i < line.s.length; i++) {
      if (cancelled) { txt.textContent = line.s; break; }
      txt.textContent += line.s.charAt(i);
      await sleep(perChar);
    }
    if (el.contains(caret)) el.removeChild(caret);
  }

  async function runColdOpen() {
    var i;
    for (i = 0; i < PASS1.length; i++) {
      if (cancelled) break;
      await typeLine(PASS1[i], 26);
      await sleep(300);
    }
    if (!cancelled) await sleep(1100);
    if (!cancelled) { feed.innerHTML = ""; await sleep(300); }
    for (i = 0; i < PASS2.length; i++) {
      if (cancelled) break;
      await typeLine(PASS2[i], 13);
      await sleep(130);
    }
    if (!cancelled) await sleep(450);
    headline.classList.add("show");
    if (!cancelled) await sleep(3300);
    finishColdOpen();
  }

  function litHero() {
    if (heroBand) heroBand.classList.add("lit");
  }

  function finishColdOpen() {
    if (finished) return;
    finished = true;
    cancelled = true;
    if (headline) headline.classList.add("show");
    litHero();
    if (overlay) overlay.classList.add("done");
    document.documentElement.style.overflow = "";
    document.body.style.overflow = "";
    setTimeout(function () { if (overlay) overlay.classList.remove("play"); }, 760);
  }

  if (skipBtn) {
    skipBtn.addEventListener("click", function () {
      if (!finished) cap("hero_skip", {});
      finishColdOpen();
    });
  }

  if (reduce || !overlay || !feed) {
    litHero();
  } else {
    overlay.classList.add("play");
    document.documentElement.style.overflow = "hidden";
    document.body.style.overflow = "hidden";
    setTimeout(function () { if (!finished) finishColdOpen(); }, 20000); // safety net
    runColdOpen();
  }

  /* ---------------------------------------------------------
     ACT 2 · ENGAGEMENT RUN (scroll-driven + scrubber)
     --------------------------------------------------------- */
  var scrollEl = $("act2Scroll");
  var dio = $("diorama");
  var pulse = $("railPulse");
  var rail = $("rail");
  var track = $("scrubTrack");
  var handle = $("scrubHandle");
  var replayBtn = $("act2Replay");
  var stations = Array.prototype.slice.call(document.querySelectorAll(".station"));
  var NAMES = ["Scope", "Build", "Verify", "Ship", "Run"];
  var THRESH = [0, 0.24, 0.48, 0.72, 0.94];

  if (scrollEl && dio && pulse && rail && track && handle) {
    var vAxis = false, railLen = 0, scrubLen = 0, ticking = false, dragging = false;

    function measure() {
      vAxis = window.matchMedia("(max-width:760px)").matches;
      railLen = vAxis ? rail.clientHeight : rail.clientWidth;
      scrubLen = track.clientWidth;
    }

    function activeIndex(p) {
      var idx = 0;
      for (var i = 0; i < THRESH.length; i++) if (p >= THRESH[i] - 0.001) idx = i;
      return idx;
    }

    function applyP(p) {
      dio.style.setProperty("--p", p.toFixed(4));
      var px = p * railLen;
      pulse.style.transform = vAxis ? ("translateY(" + px + "px)") : ("translateX(" + px + "px)");
      handle.style.transform = "translateX(" + (p * scrubLen) + "px)";
      for (var i = 0; i < stations.length; i++) {
        stations[i].classList.toggle("lit", p >= THRESH[i] - 0.001);
      }
      handle.setAttribute("aria-valuenow", Math.round(p * 100));
      handle.setAttribute("aria-valuetext", NAMES[activeIndex(p)]);
    }

    function scrollProgress() {
      var r = scrollEl.getBoundingClientRect();
      var dist = scrollEl.offsetHeight - window.innerHeight;
      if (dist <= 0) return 0;
      return clamp(-r.top / dist, 0, 1);
    }

    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () { applyP(scrollProgress()); ticking = false; });
    }

    function sectionTop() {
      // absolute document Y of the scroll wrapper, correct even though
      // .act2 is a positioned ancestor (offsetTop would be relative to it)
      return scrollEl.getBoundingClientRect().top + window.pageYOffset;
    }

    function scrollToP(p) {
      var dist = scrollEl.offsetHeight - window.innerHeight;
      var y = sectionTop() + p * dist;
      // bypass CSS smooth-scroll so scrubbing tracks the pointer 1:1
      var prev = document.documentElement.style.scrollBehavior;
      document.documentElement.style.scrollBehavior = "auto";
      window.scrollTo(0, y);
      document.documentElement.style.scrollBehavior = prev;
    }

    function scrubFromX(clientX) {
      var r = track.getBoundingClientRect();
      var p = clamp((clientX - r.left) / r.width, 0, 1);
      scrollToP(p);
      applyP(p);
    }

    track.addEventListener("pointerdown", function (e) {
      dragging = true;
      if (track.setPointerCapture) track.setPointerCapture(e.pointerId);
      handle.focus();
      scrubFromX(e.clientX);
    });
    track.addEventListener("pointermove", function (e) { if (dragging) scrubFromX(e.clientX); });
    track.addEventListener("pointerup", function () { dragging = false; });
    track.addEventListener("pointercancel", function () { dragging = false; });

    handle.addEventListener("keydown", function (e) {
      var p = scrollProgress(), np = null, step = 0.02;
      if (e.key === "ArrowRight" || e.key === "ArrowUp") np = clamp(p + step, 0, 1);
      else if (e.key === "ArrowLeft" || e.key === "ArrowDown") np = clamp(p - step, 0, 1);
      else if (e.key === "PageUp") np = clamp(p + 0.12, 0, 1);
      else if (e.key === "PageDown") np = clamp(p - 0.12, 0, 1);
      else if (e.key === "Home") np = 0;
      else if (e.key === "End") np = 1;
      if (np !== null) { e.preventDefault(); scrollToP(np); applyP(np); }
    });

    if (replayBtn) {
      replayBtn.addEventListener("click", function () {
        window.scrollTo({ top: sectionTop(), behavior: reduce ? "auto" : "smooth" });
      });
    }

    var rt;
    window.addEventListener("resize", function () {
      clearTimeout(rt);
      rt = setTimeout(function () { measure(); applyP(scrollProgress()); }, 150);
    });
    window.addEventListener("scroll", onScroll, { passive: true });

    measure();
    applyP(scrollProgress());
  }

  /* ---------------------------------------------------------
     ACT 4 · proof-card pointer tilt (transform only)
     --------------------------------------------------------- */
  if (!reduce) {
    Array.prototype.forEach.call(document.querySelectorAll(".proof-card"), function (card) {
      card.addEventListener("pointermove", function (e) {
        if (e.pointerType === "touch") return;
        var r = card.getBoundingClientRect();
        var x = (e.clientX - r.left) / r.width - 0.5;
        var y = (e.clientY - r.top) / r.height - 0.5;
        card.style.transform = "perspective(720px) rotateX(" + (-y * 6).toFixed(2) +
          "deg) rotateY(" + (x * 8).toFixed(2) + "deg) translateY(-4px)";
      });
      function level() { card.style.transform = ""; }
      card.addEventListener("pointerleave", level);
      card.addEventListener("blur", level);
    });
  }
})();
