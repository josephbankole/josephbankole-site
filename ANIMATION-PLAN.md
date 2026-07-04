# josephbankole.ca animation pass - work plan (EXECUTE NOW)

Founder brief (2026-07-04): "go to the max, I want it to be impressive." Analyst
ruling: maximal showcase treatment is approved for this site ONLY, with a hard
conversion floor. This plan is self-contained; any model can execute it cold.

## Read first
index.html, assets/style.css, assets/site.js (existing dust canvas + reveal
observer), one blog article page (blog/*.html) and blog/index.html + news/index.html
to see what they include. The repo deploys to GitHub Pages on push to main.

## Brand and stack
Navy #0c2a3e family background, cream text, gold accents (tokens already in
style.css, e.g. --cream-soft). Fonts already loaded: Fraunces (serif), Inter Tight,
IBM Plex Mono. Plain HTML/CSS/JS; NO frameworks, NO external scripts (PostHog is the
only third-party script and stays). All motion = transform/opacity only.

## Hard floors (violating any of these fails the pass)
1. Mobile LCP must not regress past 2.5s; hero renders readable text immediately
   (no content hidden behind JS on first paint; entrance animations start from
   opacity 0 ONLY on elements below the fold or after content is painted).
2. `prefers-reduced-motion: reduce` disables every effect (static page, marquee
   becomes a static row, pill still appears but without entrance animation).
3. No per-character DOM spans (screen readers); word-level splits maximum, and any
   split element carries the original text as aria-label.
4. No fake proof of any kind. No testimonials (founder confirmed none exist).
5. Calendly conversion is king: nothing may cover, delay, or distract from booking
   CTAs. The Web3Forms-free Substack embed, feed.xml link, OG tags, PostHog snippet
   and all UTM-tagged Calendly URLs must survive byte-identical in behaviour.
6. Keyboard navigation and focus states intact; marquee duplicates aria-hidden.

## The moves (in build order)

### 1. Floating bottom CTA pill (ship first; the conversion win)
Fixed bottom-center pill: serif "J" mark + "Book a consultation" button.
- Link: https://calendly.com/josephbankole/30min?utm_source=josephbankole.ca&utm_medium=site&utm_content=pill
- PostHog: onclick capture `calendly_click` {site:'josephbankole.ca', location:'pill'}.
- Appears after ~600px scroll (translateY entrance), hides while the hero CTA block
  or the footer is in the viewport (IntersectionObserver on both), respects
  env(safe-area-inset-bottom), z-index above content but never over form fields.
- Style: white/cream pill on navy pages, layered shadow (see move 6), radius full.
- Must also appear on blog article pages and news pages (see move 8).

### 2. Hero act
- Word pull-up reveal on the H1: split into words, each wrapped in an overflow-hidden
  mask line, translateY(110%) -> 0, 600ms, cubic-bezier(0.16,1,0.3,1), 60ms stagger,
  on load (not on scroll). Keep the existing <em> emphasis and style it Fraunces
  italic if not already.
- Staggered entrances after the H1: eyebrow, lede, CTA row, hero-note, credrow,
  scrollcue fade-up in sequence (80ms apart, starting 300ms after H1 begins).
- Densify the existing #dust canvas slightly (more particles, slower drift); it must
  stay subtle and pause under reduced motion (it may already; verify).

### 3. Scroll-linked narrative reveal (the "amaze" moment)
On the About section's first paragraph ("For ten years my job was to know how money
actually moves..."): split into WORDS, each word's opacity animates 0.25 -> 1 mapped
to scroll progress through the paragraph (rAF scroll handler or IntersectionObserver
ratio; no library). The paragraph must read normally with JS off and under reduced
motion (full opacity). Apply to that one paragraph only; restraint is the craft.

### 4. Blog artwork marquee
Infinite horizontal CSS marquee of the branded per-article OG cards in assets/og/
(navy/cream/gold 1200x630 PNGs, 37-51KB each; there are 5 + default). Each card
links to its article and fires PostHog `blog_card_click` {slug}. Place it as a band
inside or directly under the #blog section header. CSS keyframes translateX(-50%)
loop, duplicated track aria-hidden, pause on hover, ~420px card width desktop /
~280px mobile, lazy-loaded images, static single row under reduced motion.

### 5. Unified entrance system
Replace/extend the existing .reveal usage into one choreography: fade-up 24px,
500ms, cubic-bezier(0.16,1,0.3,1), IntersectionObserver (threshold 0.15, once),
group stagger 80ms. Apply to: section headers, project cards, post-rows, news list
items, footer columns. Cap: no more than ~6 animated groups per page.

### 6. CTA weight
Primary .btn: layered shadow stack (small crisp + medium soft + faint wide, plus a
subtle inset top highlight), hover lift 1px + shadow deepen. Hero primary CTA gains
a gold icon-circle with an arrow that nudges right on hover (gap grows). Post-rows
get a gold rule that slides in on hover. Nav links get an underline slide.

### 7. Parallax seasoning + footer wordmark
- Section index labels ("01 / About" etc.) drift slower than scroll (max 24px,
  transform-only, rAF, skipped on touch devices and reduced motion).
- Footer: giant "JOSEPH BANKOLE" wordmark, Fraunces, ~12-14vw, very low contrast
  (cream at ~6-8% opacity), word pull-up on view. Pure texture, not a link.

### 8. Blog + news pages inherit the system
Verify article/news pages include assets/style.css and assets/site.js; add the pill
and the entrance system there (article body itself does NOT animate; only header,
footer and the pill). If pages do not share site.js, refactor so they do.

## Verification checklist (all required before "done")
1. Local preview at 375px and 1280px; screenshot both.
2. Toggle prefers-reduced-motion: everything static, page fully readable.
3. JS disabled: page fully readable, no invisible content.
4. grep the built pages: PostHog snippet, feed.xml link, OG tags, all Calendly UTM
   URLs, Substack embed all intact.
5. Keyboard-tab through the page: focus visible, pill reachable, marquee links
   focusable without hijacking scroll.
6. Deploy: commit main, push, verify live with curl (grep for the pill class and
   marquee class). GitHub Pages flakes: empty commit retriggers.
7. PostHog: confirm calendly_click {location:'pill'} and blog_card_click fire
   (click once on the live site if possible, or verify the handler wiring).

## KPIs (note in commit message body for the record)
Booking clicks per session, pill share of total calendly_click events, mobile
bounce rate, LCP no-regression. Baseline = PostHog before this ships.

Commit style: plain one-line messages ending with
"Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>".
