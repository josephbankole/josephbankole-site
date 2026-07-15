/* josephbankole.ca — front-end behaviour. Brand-faithful, reduced-motion safe. */
(function () {
  "use strict";
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---- scroll progress bar (injected so every page gets it) ---- */
  var bar = document.createElement("div");
  bar.className = "scrollbar";
  document.body.appendChild(bar);
  function onScroll() {
    var h = document.documentElement;
    var max = h.scrollHeight - h.clientHeight;
    bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + "%";
  }
  window.addEventListener("scroll", onScroll, { passive: true });
  onScroll();

  /* ---- reveal on scroll (supports .stagger) ---- */
  var els = document.querySelectorAll(".reveal");
  if (!("IntersectionObserver" in window) || reduce) {
    els.forEach(function (e) { e.classList.add("in"); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) { en.target.classList.add("in"); io.unobserve(en.target); }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -8% 0px" });
    els.forEach(function (e) { io.observe(e); });
  }

  /* ---- scroll-spy: highlight the nav link for the section in view ---- */
  var navLinks = Array.prototype.slice.call(document.querySelectorAll('.nav-links a[href^="#"], .nav-links a[href^="/#"]'));
  var ids = navLinks.map(function (a) {
    var h = a.getAttribute("href"); var i = h.indexOf("#");
    return i >= 0 ? h.slice(i + 1) : null;
  });
  var sections = ids.map(function (id) { return id ? document.getElementById(id) : null; });
  if (sections.some(Boolean) && "IntersectionObserver" in window) {
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var idx = sections.indexOf(en.target);
        navLinks.forEach(function (a, i) { a.classList.toggle("active", i === idx); });
      });
    }, { threshold: 0.5 });
    sections.forEach(function (s) { if (s) spy.observe(s); });
  }

  /* The hero gold-dust canvas block used to live here. The homepage hero
     was replaced by the cinematic experience (assets/experience.js) and no
     page carries a #dust canvas any more, so the block is gone. */
})();
