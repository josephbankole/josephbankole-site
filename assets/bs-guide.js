/* The BS guide (blog/the-bs-guide.html): the win tally and task checklist,
   then the snowfall canvas. Moved out of the page on 2026-11-15 so the site's
   Content-Security-Policy can refuse inline scripts. Loaded with defer at the
   end of the article, so every element it reads already exists. */
(function () {
  var KEY = 'bsguide.v1';
  function load() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } }
  function save(st) { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} }
  var state = load();
  state.wins = state.wins || {};
  state.tasks = state.tasks || [false, false, false, false, false];

  var winButtons = document.querySelectorAll('[data-win]');
  var doneLabels = { account: 'Win 1 of 3 banked', copy: 'Copied. Win 2 of 3 banked', follow: 'Win 3 of 3 banked' };

  function winCount() {
    var n = 0;
    ['account', 'copy', 'follow'].forEach(function (k) { if (state.wins[k]) n++; });
    return n;
  }
  function paint() {
    winButtons.forEach(function (btn) {
      var k = btn.getAttribute('data-win');
      if (state.wins[k]) {
        btn.textContent = doneLabels[k];
        btn.setAttribute('aria-pressed', 'true');
        var box = btn.closest('.bsg-win');
        if (box) box.classList.add('is-done');
      }
    });
    var tally = document.getElementById('bsg-tally-n');
    if (tally) tally.textContent = winCount() + ' of 3';
    var list = document.getElementById('bsg-tasks');
    if (list) {
      var items = list.querySelectorAll('li');
      var done = 0;
      items.forEach(function (li, i) {
        li.classList.toggle('is-done', !!state.tasks[i]);
        li.setAttribute('aria-checked', state.tasks[i] ? 'true' : 'false');
        if (state.tasks[i]) done++;
      });
      var count = document.getElementById('bsg-tasks-n');
      if (count) count.textContent = done + ' of 5';
    }
  }
  function bank(k) { if (!state.wins[k]) { state.wins[k] = true; save(state); paint(); } }

  winButtons.forEach(function (btn) {
    var k = btn.getAttribute('data-win');
    btn.addEventListener('click', function () {
      if (k === 'copy') {
        var pre = document.getElementById('bsg-template');
        var text = pre ? pre.textContent : '';
        function done() { bank('copy'); }
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(text).then(done, function () { fallback(); });
        } else { fallback(); }
        function fallback() {
          var ta = document.createElement('textarea');
          ta.value = text; document.body.appendChild(ta); ta.select();
          try { document.execCommand('copy'); } catch (e) {}
          document.body.removeChild(ta); done();
        }
      } else {
        bank(k);
      }
    });
  });

  var list = document.getElementById('bsg-tasks');
  if (list) {
    list.setAttribute('role', 'group');
    list.querySelectorAll('li').forEach(function (li, i) {
      li.setAttribute('role', 'checkbox');
      li.setAttribute('tabindex', '0');
      function toggle() { state.tasks[i] = !state.tasks[i]; save(state); paint(); }
      li.addEventListener('click', toggle);
      li.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
      });
    });
  }
  paint();
})();
(function () {
  if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  var canvas = document.createElement('canvas');
  canvas.setAttribute('aria-hidden', 'true');
  canvas.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:1;';
  document.body.appendChild(canvas);
  var ctx = canvas.getContext('2d');
  var dpr = Math.min(window.devicePixelRatio || 1, 2);
  var flakes = [];
  var running = true;
  function size() {
    canvas.width = window.innerWidth * dpr;
    canvas.height = window.innerHeight * dpr;
  }
  function make(randomY) {
    return {
      x: Math.random() * canvas.width,
      y: randomY ? Math.random() * canvas.height : -10 * dpr,
      r: (0.8 + Math.random() * 1.9) * dpr,
      vy: (0.25 + Math.random() * 0.55) * dpr,
      drift: Math.random() * 2 * Math.PI,
      driftSpeed: 0.003 + Math.random() * 0.006,
      alpha: 0.18 + Math.random() * 0.35
    };
  }
  function reset() {
    size();
    flakes = [];
    var count = Math.min(70, Math.floor(window.innerWidth / 18));
    for (var i = 0; i < count; i++) flakes.push(make(true));
  }
  function tick() {
    if (!running) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (var i = 0; i < flakes.length; i++) {
      var f = flakes[i];
      f.drift += f.driftSpeed;
      f.x += Math.sin(f.drift) * 0.3 * dpr;
      f.y += f.vy;
      if (f.y > canvas.height + 10 * dpr) flakes[i] = f = make(false);
      ctx.beginPath();
      ctx.arc(f.x, f.y, f.r, 0, 2 * Math.PI);
      ctx.fillStyle = 'rgba(245,242,243,' + f.alpha + ')';
      ctx.fill();
    }
    requestAnimationFrame(tick);
  }
  document.addEventListener('visibilitychange', function () {
    running = !document.hidden;
    if (running) requestAnimationFrame(tick);
  });
  window.addEventListener('resize', reset);
  reset();
  requestAnimationFrame(tick);
})();
