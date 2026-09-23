/* josephbankole.ca — centralised analytics.
   PostHog bootstrap (same project as thearchv.ca; segmented by `site`) plus
   click-tracking: subscribe clicks to The ARCHV AI on Substack, other
   newsletter links, the neutral contact address, outbound project and
   source links, founder social links, and the 404 page. One file, included
   on every page. The 404 page loads it too: a broken inbound link is only
   visible through the referrer it arrives with.
   2026-09-23: waitlist tracking removed with the waitlist itself. */
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
  var SITE = 'josephbankole.ca';
  function cap(name, props) {
    if (!window.posthog) return;
    props.site = SITE;
    posthog.capture(name, props);
  }
  function host(a) { return (a.hostname || '').toLowerCase(); }

  /* Subscribe: any link whose host is archvai.substack.com, the site's
     primary ask. A click, not a signup: the homepage Substack iframe is
     cross-origin, so real signups only show in Substack's own stats.
     location is the link's data-location, else the page path. utm_medium
     is read from the link itself, so the event and Substack's referral
     report agree. These links fire subscribe_click only, never
     newsletter_click or outbound_click. */
  var SUBSCRIBE_HOST = 'archvai.substack.com';
  function isSubscribe(a) { return host(a) === SUBSCRIBE_HOST; }
  function utmMedium(a) {
    try { return new URL(a.href).searchParams.get('utm_medium') || '(none)'; }
    catch (e) { return '(none)'; }
  }
  /* Any other Substack newsletter link (the ARCHV Dispatch). Kept so a
     Dispatch link, if one is ever placed, is not lost in outbound_click. */
  function isNewsletter(a) { return !isSubscribe(a) && host(a) === 'thearchvdispatch.substack.com'; }
  var PROJECT = 'a[href*="thearchv.ca"]';
  var FOUNDER = 'a[href*="linkedin.com"], a[href*="instagram.com"]';

  document.querySelectorAll('a[href]').forEach(function (a) {
    if (isSubscribe(a)) {
      a.addEventListener('click', function () {
        cap('subscribe_click', {
          location: a.getAttribute('data-location') || location.pathname,
          utm_medium: utmMedium(a),
          path: location.pathname
        });
      });
    } else if (isNewsletter(a)) {
      a.addEventListener('click', function () {
        cap('newsletter_click', { href: a.href, path: location.pathname });
      });
    }
  });
  document.querySelectorAll(PROJECT).forEach(function (a) {
    a.addEventListener('click', function () {
      cap('project_link_click', { href: a.href });
    });
  });
  document.querySelectorAll(FOUNDER).forEach(function (a) {
    a.addEventListener('click', function () {
      cap('founder_link_click', { href: a.href });
    });
  });

  /* Neutral contact: every mailto (the footer address, the privacy
     contact, the lab enquiry). */
  document.querySelectorAll('a[href^="mailto:"]').forEach(function (a) {
    a.addEventListener('click', function () {
      cap('contact_click', { location: a.getAttribute('data-location') || location.pathname });
    });
  });

  /* Outbound: any http(s) link to another host that the events above do
     not already name, so the cited sources in news editions and answers
     are counted without double-counting subscribe, newsletter, project or
     founder clicks. Carries the link's hostname, never the full URL. */
  document.querySelectorAll('a[href^="http"]').forEach(function (a) {
    if (!a.hostname || a.hostname === location.hostname) return;
    if (isSubscribe(a) || isNewsletter(a) || a.matches(PROJECT + ', ' + FOUNDER)) return;
    a.addEventListener('click', function () {
      cap('outbound_click', { hostname: a.hostname, path: location.pathname });
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
    cap('page_404', { path: location.pathname, referrer: document.referrer || '(none)' });
  }
})();
