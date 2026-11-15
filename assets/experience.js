/* josephbankole.ca — homepage experience behaviour. No libraries.
   Animate transform and colour only. Reduced-motion safe.
   No PostHog events of its own: link clicks are bound centrally by
   /assets/analytics.js. The waitlist, its floating pill and the
   configurator's waitlist button were removed on 2026-09-23, and the
   configurator itself on 2026-11-15: it sized a client build, and he is
   not taking client work.

   The cold open was cut on 2026-08-09 (founder ruling). It held scroll for
   13.9 seconds behind an overlay that covered the navigation, on every
   visit, with no session guard. The page now opens on content and nothing
   replaces the animation. */
(function () {
  "use strict";

  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var clamp = function (v, a, b) { return v < a ? a : v > b ? b : v; };
  var $ = function (id) { return document.getElementById(id); };

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
})();
