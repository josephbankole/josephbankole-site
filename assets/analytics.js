/* josephbankole.ca — centralised analytics.
   PostHog bootstrap (same project as thearchv.ca; segmented by `site`) plus
   the conversion click-tracking: waitlist clicks, newsletter link clicks,
   the neutral contact address, outbound project and source links, founder
   social links, and the 404 page. One file, included on every page so
   events aren't blind on the blog, news, and privacy pages the way they
   used to be. The 404 page loads it too: a broken inbound link is only
   visible through the referrer it arrives with. */
(function () {
  "use strict";

  /* ---- PostHog init ---- */
  !function (t, e) {
    var o, n, p, r;
    e.__SV || (window.posthog = e, e._i = [], e.init = function (i, s, a) {
      function g(t, e) {
        var o = e.split(".");
        2 == o.length && (t = t[o[0]], e = o[1]);
        t[e] = function () { t.push([e].concat(Array.prototype.slice.call(arguments, 0))); };
      }
      (p = t.createElement("script")).type = "text/javascript";
      p.crossOrigin = "anonymous"; p.async = !0;
      p.src = s.api_host.replace(".i.posthog.com", "-assets.i.posthog.com") + "/static/array.js";
      (r = t.getElementsByTagName("script")[0]).parentNode.insertBefore(p, r);
      var u = e;
      for (void 0 !== a ? u = e[a] = [] : a = "posthog", u.people = u.people || [],
        u.toString = function (t) { var e = "posthog"; return "posthog" !== a && (e += "." + a), t || (e += " (stub)"), e; },
        u.people.toString = function () { return u.toString(1) + ".people (stub)"; },
        o = "init capture register register_once unregister opt_in_capturing opt_out_capturing".split(" "),
        n = 0; n < o.length; n++) g(u, o[n]);
      e._i.push([i, s, a]);
    }, e.__SV = 1);
  }(document, window.posthog || []);
  posthog.init('phc_kg8nXCp4TJMcRjBQAVZTQoubijYWeBRMHU9PHYgiUagm', {
    api_host: 'https://us.i.posthog.com',
    autocapture: false,
    capture_pageview: true,
    persistence: 'localStorage',
    respect_dnt: true
  });

  /* ---- conversion click-tracking ----
     Loaded with `defer`, after the DOM is parsed, so every link below
     already exists when this runs. */
  /* Waitlist interest — replaces the retired calendly_click event now that
     bookings are closed. Fires on any waitlist mailto CTA (nav, hero, work
     band, footer, pill), tagged by data-location so Fola can see which
     surface drives interest. */
  document.querySelectorAll('.js-waitlist').forEach(function (a) {
    a.addEventListener('click', function () {
      if (window.posthog) posthog.capture('waitlist_click', { site: 'josephbankole.ca', location: a.getAttribute('data-location') || 'unknown' });
    });
  });
  /* A click on a newsletter link, not a signup. It was called
     newsletter_submit until 2026-09-22, which read as a conversion. The
     Substack iframe on the homepage is cross-origin, so real signups only
     show in Substack's own subscriber stats. */
  var NEWSLETTER = 'a[href*="archvai.substack.com"], a[href*="thearchvdispatch.substack.com"]';
  var PROJECT = 'a[href*="joeysdr.com"], a[href*="thearchv.ca"]';
  var FOUNDER = 'a[href*="linkedin.com"], a[href*="instagram.com"]';
  document.querySelectorAll(NEWSLETTER).forEach(function (a) {
    a.addEventListener('click', function () {
      if (window.posthog) posthog.capture('newsletter_click', { site: 'josephbankole.ca', href: a.href });
    });
  });
  document.querySelectorAll(PROJECT).forEach(function (a) {
    a.addEventListener('click', function () {
      if (window.posthog) posthog.capture('project_link_click', { site: 'josephbankole.ca', href: a.href });
    });
  });
  document.querySelectorAll(FOUNDER).forEach(function (a) {
    a.addEventListener('click', function () {
      if (window.posthog) posthog.capture('founder_link_click', { site: 'josephbankole.ca', href: a.href });
    });
  });

  /* Neutral contact: every mailto that is not a waitlist CTA (the footer
     address, the privacy contact, the lab enquiry). Without this the only
     non-client way to reach Joseph was untracked. */
  document.querySelectorAll('a[href^="mailto:"]:not(.js-waitlist)').forEach(function (a) {
    a.addEventListener('click', function () {
      if (window.posthog) posthog.capture('contact_click', { site: 'josephbankole.ca', location: a.getAttribute('data-location') || location.pathname });
    });
  });

  /* Outbound: any http(s) link to another host that the events above do
     not already name, so the cited sources in news editions and answers
     are counted without double-counting project, founder or newsletter
     clicks. Carries the link's hostname, never the full URL. */
  document.querySelectorAll('a[href^="http"]').forEach(function (a) {
    if (!a.hostname || a.hostname === location.hostname) return;
    if (a.matches(NEWSLETTER + ', ' + PROJECT + ', ' + FOUNDER)) return;
    a.addEventListener('click', function () {
      if (window.posthog) posthog.capture('outbound_click', { site: 'josephbankole.ca', hostname: a.hostname, path: location.pathname });
    });
  });

  /* 404. GitHub Pages serves 404.html under the missing URL, so the path
     is no signal. The page is recognised by its canonical, a body class
     or data-page hook if the template adds one, or its title. */
  var canon = document.querySelector('link[rel="canonical"]');
  var is404 = (canon && /\/404\.html$/.test(canon.getAttribute('href') || '')) ||
    (document.body && document.body.classList.contains('page-404')) ||
    (document.body && document.body.getAttribute('data-page') === '404') ||
    /^(Not found|404)\b/i.test(document.title);
  if (is404 && window.posthog) {
    posthog.capture('page_404', { site: 'josephbankole.ca', path: location.pathname, referrer: document.referrer || '(none)' });
  }
})();
