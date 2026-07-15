/* josephbankole.ca /lab — cinematic prototype behaviour.
   No libraries. Animate transform + opacity only. Reduced-motion safe.
   PostHog events: hero_skip, configurator_select, configurator_cta
   (calendly_click is bound centrally by /assets/analytics.js). */
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

  var pill = $("bookPill");
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
     Floating book pill — appears once the hero scrolls away
     --------------------------------------------------------- */
  if (pill && "IntersectionObserver" in window && heroBand) {
    var pillIO = new IntersectionObserver(function (es) {
      es.forEach(function (en) { if (!en.isIntersecting) pill.classList.add("show"); });
    }, { threshold: 0 });
    pillIO.observe(heroBand);
  } else if (pill) {
    pill.classList.add("show");
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
     ACT 3 · CONFIGURATOR
     --------------------------------------------------------- */
  var CTA_BASE = "https://calendly.com/josephbankole/30min?utm_source=josephbankole.ca&utm_medium=lab";
  var KEYS = ["ops", "hours", "mode"];
  var OF = {
    spreadsheets: "It runs on spreadsheets",
    saas: "It is spread across your SaaS tools",
    custom: "It runs on your own custom systems"
  };
  var HF = {
    reporting: "the reporting",
    replies: "the customer replies",
    dataentry: "the data entry between systems",
    monitoring: "the monitoring"
  };
  var HH = {
    reporting: "pulled, checked, and written the same way every time",
    replies: "drafted against your own answers, with the unsure ones held for you",
    dataentry: "moved between systems idempotently, so nothing posts twice",
    monitoring: "checked on a schedule, speaking up only when something is off"
  };
  var MF = {
    alongside: "built alongside your team so they own it after",
    handover: "built, documented, and handed over so it runs without me"
  };

  var state = { ops: null, hours: null, mode: null };
  var readEl = $("sketchRead");
  var cta = $("sketchCta");

  function compose() {
    if (!state.ops && !state.hours && !state.mode)
      return "Pick the three above and the two-week sketch fills in.";
    var parts = [];
    if (state.hours) parts.push("Week one takes " + HF[state.hours] + " off your plate, " + HH[state.hours] + ".");
    if (state.ops) parts.push(OF[state.ops] + ", so we start there.");
    if (state.mode) parts.push("It is " + MF[state.mode] + ".");
    return parts.join(" ");
  }

  function ctaUrl() {
    var uc = "configurator";
    if (state.ops && state.hours && state.mode)
      uc = "configurator-" + state.ops + "-" + state.hours + "-" + state.mode;
    return CTA_BASE + "&utm_content=" + uc;
  }

  function render() {
    if (readEl) {
      readEl.classList.add("swap");
      setTimeout(function () {
        readEl.textContent = compose();
        readEl.classList.remove("swap");
      }, reduce ? 0 : 170);
    }
    if (cta) {
      cta.href = ctaUrl();
      cta.classList.toggle("ready", !!(state.ops && state.hours && state.mode));
    }
  }

  function selectChip(group, val, fromUser) {
    if (KEYS.indexOf(group) < 0) return;
    state[group] = val;
    var items = document.querySelectorAll('.q[data-q="' + group + '"] .chip');
    Array.prototype.forEach.call(items, function (c) {
      var on = c.getAttribute("data-val") === val;
      c.setAttribute("aria-checked", on ? "true" : "false");
      c.tabIndex = on ? 0 : -1;
    });
    render();
    updateHash();
    if (fromUser) cap("configurator_select", { question: group, choice: val });
  }

  function updateHash() {
    var parts = [];
    KEYS.forEach(function (k) { if (state[k]) parts.push(k + "=" + state[k]); });
    var h = parts.length ? "#" + parts.join("&") : "";
    try { history.replaceState(null, "", location.pathname + location.search + h); } catch (e) {}
  }

  function initGroup(group) {
    var items = Array.prototype.slice.call(document.querySelectorAll('.q[data-q="' + group + '"] .chip'));
    items.forEach(function (c, i) {
      c.tabIndex = i === 0 ? 0 : -1;
      c.addEventListener("click", function () { selectChip(group, c.getAttribute("data-val"), true); });
      c.addEventListener("keydown", function (e) {
        var ni = null;
        if (e.key === "ArrowRight" || e.key === "ArrowDown") ni = (i + 1) % items.length;
        else if (e.key === "ArrowLeft" || e.key === "ArrowUp") ni = (i - 1 + items.length) % items.length;
        if (ni !== null) {
          e.preventDefault();
          items[ni].focus();
          selectChip(group, items[ni].getAttribute("data-val"), true);
        }
      });
    });
  }

  if (readEl && cta) {
    KEYS.forEach(function (k) {
      if (document.querySelector('.q[data-q="' + k + '"]')) initGroup(k);
    });

    // restore state from URL hash so a refresh keeps the sketch
    var h = location.hash.replace(/^#/, "");
    if (h) {
      h.split("&").forEach(function (pair) {
        var kv = pair.split("=");
        var k = kv[0], v = kv[1];
        if (KEYS.indexOf(k) >= 0 && v && document.querySelector('.q[data-q="' + k + '"] .chip[data-val="' + v + '"]'))
          selectChip(k, v, false);
      });
    }
    render();

    cta.addEventListener("click", function () {
      cap("configurator_cta", {
        ops: state.ops, hours: state.hours, mode: state.mode,
        complete: !!(state.ops && state.hours && state.mode)
      });
    });
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
