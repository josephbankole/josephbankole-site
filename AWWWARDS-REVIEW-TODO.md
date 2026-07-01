# josephbankole.ca — review findings and action list

This is a consultation-booking and newsletter-signup page for a solo operator, not an Awwwards entry. The informal review verdict is correct. This file separates the few things worth fixing from the long list of things not worth touching.

## What the code actually shows (checked against index.html, style.css, site.js)

The verdict holds up. The page has canvas gold-dust particles in the hero, a scroll progress bar, nav scroll-spy (an `.active` class toggled via IntersectionObserver), and reveal-on-scroll with a staggered variant for lists. All of it is the same polish layer already running on thearchv.ca.

There's one reveal pattern site-wide (fade plus translateY, via `.reveal` and `.reveal.stagger`) and one hover pattern (lift, underline-wipe, or padding-shift depending on the element). No exceptions anywhere in the CSS.

The "math" section (`.math`, `.bignum`) is one large serif number in gold sitting next to two paragraphs. No counter animation, no drawn element, nothing beyond font size. It works as a pull-quote. It isn't a data visualization and doesn't need to be.

Project cards (`.project`) are a logo circle plus text in a row. On hover, only the border and shadow around the logo pulse. No tilt, no per-line reveal, nothing that separates it from a plain content block.

Blog and news post-rows (`.post-row`) are a three-column grid: date, title with a dek, arrow. Hover shifts the row 8px left and slides the arrow over. That's the whole interaction.

The credrow (`ex-HSBC`, `Société Générale`, `McGill`, `Montreal`) is bare `<span>` text: mono font, uppercase, letter-spaced, dimmed cream color. No pills, no borders, no separator glyph beyond the flex gap, sitting under one thin hairline. Of everything on the page, this is the least visually resolved element relative to how much trust-building work it needs to do in the first three seconds a cold visitor spends here.

There's no custom cursor, no kinetic or split type, no SVG or WebGL anywhere on this page. That treatment lives on thearchv.ca, and it should stay there since this page has a different job.

## Do (ranked by effort against payoff, credibility and conversion only)

1. **Fix the credrow now. It's cheap.** Add visible separators between the four credentials, a small dot or a thin vertical rule in `--gold-soft` would do it, and give the affiliations a touch more weight than dimmed mono text. Bumping the color to `--cream` instead of `--cream-dim`, or adding a small gold tick before each item, would work. This is the one spot on the page where a ten-minute CSS change measurably helps a cold LinkedIn visitor's first impression, because it's the first credibility signal they hit, and right now it reads like an afterthought line of small caps.

2. **Wire up the newsletter form for real.** The `access_key` in the subscribe form is still `REPLACE_WITH_WEB3FORMS_KEY`, so every submission currently falls through to a mailto link, and most people won't finish that step. That's a direct hole in one of the two goals this site exists for. Get a Web3Forms key, or swap in whatever email tool will actually capture subscribers, and drop it in. This is the highest-payoff item here because the current setup is quietly losing every subscriber who tries.

3. **Add a visible response-time or availability signal near the Calendly CTA.** Something plain, like "usually replies within a day" or a live next-available-slot pulled from the Calendly embed, cuts the hesitation a cold visitor feels about whether there's a real, responsive person on the other end. It's a copy change, no new design system needed.

4. **Consider one proof line under the hero CTA**, something like "booked 30+ consultations with founders shipping AI into production," but only if the number is real and specific. People arriving from LinkedIn respond to specifics, not polish. Skip this if there's no real number yet. A vague version would hurt more than it helps.

5. **Keep the blog and news dates current.** All three blog teasers still say "Jun 2026" while the site's current date has moved to July 1. It's minor, but visibly stale dates undercut the "I write here a few times a week" line in the About copy. Handle this as part of normal upkeep rather than a special pass.

## Skip (design moves that don't serve this site's job)

- **Custom cursor.** Adds friction to a page whose only job is getting someone to Calendly. No evidence it improves conversion, and it's real ongoing cost to build and maintain across breakpoints.
- **Kinetic or split-type animation on headlines.** Would work against the actual pitch here, a plainspoken operator's credibility, and that treatment is already doing its job over on thearchv.ca. Duplicating it here blurs the line between the two brands.
- **Rebuilding the math section into a real data visualization.** The "30 min" band is a pull-quote doing pull-quote work. Building an animated counter or chart here would be effort spent making one number legible, which it already is.
