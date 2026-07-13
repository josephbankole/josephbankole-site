/* josephbankole.ca — centralised analytics.
   PostHog bootstrap (same project as thearchv.ca; segmented by `site`) plus
   the conversion click-tracking: Calendly bookings, newsletter, outbound
   project links, and founder social links. One file, included on every
   indexable page so events aren't blind on the blog, news, and privacy
   pages the way they used to be. 404 is intentionally excluded (noindex,
   nothing to measure). */
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
  document.querySelectorAll('a[href*="calendly.com"]').forEach(function (a) {
    a.addEventListener('click', function () {
      var u = new URL(a.href);
      if (window.posthog) posthog.capture('calendly_click', { site: 'josephbankole.ca', location: u.searchParams.get('utm_content') || 'unknown' });
    });
  });
  document.querySelectorAll('a[href*="archvai.substack.com"]').forEach(function (a) {
    a.addEventListener('click', function () {
      if (window.posthog) posthog.capture('newsletter_submit', { site: 'josephbankole.ca', href: a.href });
    });
  });
  document.querySelectorAll('a[href*="joeysdr.com"], a[href*="thearchv.ca"]').forEach(function (a) {
    a.addEventListener('click', function () {
      if (window.posthog) posthog.capture('project_link_click', { site: 'josephbankole.ca', href: a.href });
    });
  });
  document.querySelectorAll('a[href*="linkedin.com"], a[href*="instagram.com"]').forEach(function (a) {
    a.addEventListener('click', function () {
      if (window.posthog) posthog.capture('founder_link_click', { site: 'josephbankole.ca', href: a.href });
    });
  });
})();
