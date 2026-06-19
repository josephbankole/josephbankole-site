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

  /* ---- hero gold-dust canvas (only where #dust exists) ---- */
  var canvas = document.getElementById("dust");
  if (canvas && !reduce && canvas.getContext) {
    var ctx = canvas.getContext("2d");
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var particles = [];
    function size() {
      var r = canvas.getBoundingClientRect();
      canvas.width = r.width * dpr; canvas.height = r.height * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    function seed() {
      var r = canvas.getBoundingClientRect();
      var n = Math.min(70, Math.round(r.width / 16));
      particles = [];
      for (var i = 0; i < n; i++) {
        particles.push({
          x: Math.random() * r.width, y: Math.random() * r.height,
          rad: Math.random() * 1.6 + 0.4,
          vx: (Math.random() - 0.5) * 0.18, vy: -(Math.random() * 0.22 + 0.05),
          a: Math.random() * 0.5 + 0.15
        });
      }
    }
    function tick() {
      var r = canvas.getBoundingClientRect();
      ctx.clearRect(0, 0, r.width, r.height);
      for (var i = 0; i < particles.length; i++) {
        var p = particles[i];
        p.x += p.vx; p.y += p.vy;
        if (p.y < -4) { p.y = r.height + 4; p.x = Math.random() * r.width; }
        if (p.x < -4) p.x = r.width + 4; if (p.x > r.width + 4) p.x = -4;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.rad, 0, Math.PI * 2);
        ctx.fillStyle = "rgba(201,161,74," + p.a + ")";
        ctx.fill();
      }
      raf = requestAnimationFrame(tick);
    }
    var raf;
    size(); seed(); tick();
    var rt;
    window.addEventListener("resize", function () {
      clearTimeout(rt); rt = setTimeout(function () { size(); seed(); }, 200);
    });
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) { cancelAnimationFrame(raf); } else { tick(); }
    });
  }
})();
