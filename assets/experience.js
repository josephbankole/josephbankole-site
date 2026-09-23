/* josephbankole.ca — homepage experience behaviour. No libraries.
   Animate transform and colour only. Reduced-motion safe.
   PostHog events: configurator_select. Link clicks are bound centrally
   by /assets/analytics.js. The waitlist, its floating pill and the
   configurator's waitlist button were removed on 2026-09-23.

   The cold open was cut on 2026-08-09 (founder ruling). It held scroll for
   13.9 seconds behind an overlay that covered the navigation, on every
   visit, with no session guard. The page now opens on content and nothing
   replaces the animation. */
(function () {
  "use strict";

  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var clamp = function (v, a, b) { return v < a ? a : v > b ? b : v; };
  var $ = function (id) { return document.getElementById(id); };

  function cap(name, props) {
    if (window.posthog && posthog.capture) {
      var p = { site: "josephbankole.ca", surface: "home" };
      if (props) for (var k in props) p[k] = props[k];
      try { posthog.capture(name, p); } catch (e) {}
    }
  }

  /* JS is running: unlock the JS-only states (station card dimming,
     hero underline draw, scrubber). Without this class the page is
     fully static and fully visible. */
  document.body.classList.add("xp-js");

  var heroBand = $("top");
  if (heroBand) heroBand.classList.add("lit");

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
  var navEl = document.querySelector(".nav");
  /* Below 760px the diorama is not pinned (experience.css). It stacks in
     normal flow and each station lights as its top crosses this line,
     measured as a share of the viewport height from the top. */
  var READ_LINE = 0.7;

  if (scrollEl && dio && pulse && rail && track && handle) {
    var vAxis = false, railLen = 0, scrubLen = 0, navH = 0, cur = 0, ticking = false, dragging = false;

    function measure() {
      vAxis = window.matchMedia("(max-width:760px)").matches;
      /* the pin sticks below the sticky nav; the CSS reads this value */
      navH = navEl ? navEl.offsetHeight : 0;
      document.documentElement.style.setProperty("--xp-nav-h", navH + "px");
      railLen = vAxis ? rail.clientHeight : rail.clientWidth;
      scrubLen = track.clientWidth;
    }

    function activeIndex(p) {
      var idx = 0;
      for (var i = 0; i < THRESH.length; i++) if (p >= THRESH[i] - 0.001) idx = i;
      return idx;
    }

    /* fromScroll: on the unpinned phone layout a station lights when its
       own top crosses the reading line, so each one lights while it is on
       screen. Dragging the scrubber or using the keys lights by THRESH. */
    function applyP(p, fromScroll) {
      cur = p;
      dio.style.setProperty("--p", p.toFixed(4));
      var px = p * railLen;
      pulse.style.transform = vAxis ? ("translateY(" + px + "px)") : ("translateX(" + px + "px)");
      handle.style.transform = "translateX(" + (p * scrubLen) + "px)";
      var line = window.innerHeight * READ_LINE, lastLit = 0;
      for (var i = 0; i < stations.length; i++) {
        var on = (vAxis && fromScroll)
          ? stations[i].getBoundingClientRect().top <= line
          : p >= THRESH[i] - 0.001;
        stations[i].classList.toggle("lit", on);
        if (on) lastLit = i;
      }
      handle.setAttribute("aria-valuenow", Math.round(p * 100));
      handle.setAttribute("aria-valuetext", NAMES[(vAxis && fromScroll) ? lastLit : activeIndex(p)]);
    }

    /* Desktop: the pin holds from the moment the wrapper's top reaches the
       nav's bottom edge until its bottom reaches the viewport's, so that
       stretch is 0 to 1. Phone: how far the reading line has travelled
       down the rail. */
    function scrollProgress() {
      if (vAxis) {
        var rr = rail.getBoundingClientRect();
        if (rr.height <= 0) return 0;
        return clamp((window.innerHeight * READ_LINE - rr.top) / rr.height, 0, 1);
      }
      var r = scrollEl.getBoundingClientRect();
      var dist = scrollEl.offsetHeight - window.innerHeight + navH;
      if (dist <= 0) return 0;
      return clamp((navH - r.top) / dist, 0, 1);
    }

    function onScroll() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () { applyP(scrollProgress(), true); ticking = false; });
    }

    function sectionTop() {
      // absolute document Y of the scroll wrapper, correct even though
      // .act2 is a positioned ancestor (offsetTop would be relative to it)
      return scrollEl.getBoundingClientRect().top + window.pageYOffset;
    }

    function scrollToP(p) {
      /* unpinned on phones: the scrubber lights the stations in place and
         leaves the page where the reader put it */
      if (vAxis) return;
      var dist = scrollEl.offsetHeight - window.innerHeight + navH;
      var y = sectionTop() - navH + p * dist;
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
      var p = cur, np = null, step = 0.02;
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
        window.scrollTo({ top: sectionTop() - navH, behavior: reduce ? "auto" : "smooth" });
      });
    }

    var rt;
    window.addEventListener("resize", function () {
      clearTimeout(rt);
      rt = setTimeout(function () { measure(); applyP(scrollProgress(), true); }, 150);
    });
    window.addEventListener("scroll", onScroll, { passive: true });

    measure();
    applyP(scrollProgress(), true);
  }

  /* ---------------------------------------------------------
     ACT 3 · CONFIGURATOR
     --------------------------------------------------------- */
  /* A demo of how a two-week build is scoped. It has no button: the
     answers only rewrite the sketch on the page. */
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

  function compose() {
    if (!state.ops && !state.hours && !state.mode)
      return "Pick the three above and the two-week sketch fills in.";
    var parts = [];
    if (state.hours) parts.push("Week one takes " + HF[state.hours] + " off your plate, " + HH[state.hours] + ".");
    if (state.ops) parts.push(OF[state.ops] + ", so we start there.");
    if (state.mode) parts.push("It is " + MF[state.mode] + ".");
    return parts.join(" ");
  }

  function render() {
    if (readEl) {
      readEl.classList.add("swap");
      setTimeout(function () {
        readEl.textContent = compose();
        readEl.classList.remove("swap");
      }, reduce ? 0 : 170);
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

  if (readEl) {
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
  }
})();
