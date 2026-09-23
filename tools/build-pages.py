#!/usr/bin/env python3
"""Apply the shared page shell to every hand-written page on josephbankole.ca.

Why this exists: there is no build system, so the nav, the footer, the article
head, the article tail and every piece of head metadata were maintained by hand
across 57 files. They drifted. The 2026-08-09 audit found the drift in every
direction at once: no <main> and no skip link on any page, <article> on one page
in twenty-five, zero <time> elements on a daily news desk, twenty pages selling a
retired booking, three different footers, and 26 news pages pointing og:image at
a file that was never rendered.

This script owns the shell. It reads each page, lifts out the parts a human
wrote (the prose, the sources list, the headline, the standfirst, the CTA copy,
the curated related rows, the head metadata) and rebuilds everything around them
from one template. Author copy is never rewritten, only re-housed.

It is idempotent. Running it twice produces byte-identical output, because it
parses its own output the same way it parses the original hand-written page.

    python3 tools/build-pages.py            # rewrite in place
    python3 tools/build-pages.py --check    # fail if anything would change,
                                            # or if a gate below fails

Run tools/build-news-feed.py afterwards if you added an edition.

Gates (added 2026-09-22, after the daily desk undid three August fixes that
nothing enforced):

  - A news edition dated today or later (Montreal time) must carry a <title> of
    60 characters or fewer before the " · Joseph Bankole" suffix and a meta
    description of 155 or fewer. --check exits non-zero if it does not. Older
    editions, blog posts and answers pages only print a warning.
  - The homepage news teaser holds at most 6 rows. The build drops the oldest
    rows past six, so --check fails whenever the teaser has grown.

Warnings go to stderr and never change the exit code of a normal run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sitelib  # noqa: E402  (shared clock and block finder, tools/sitelib.py)

REPO = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://josephbankole.ca"

# The offset used to be a constant, "-04:00  # Montreal, August", which would
# have stamped every page from November with the wrong time. It is now read
# per date from the time zone database (America/Toronto) by sitelib.local_iso.

PERSON_ID = "%s/#person" % SITE
# Google's parser does not follow an @id to another document, so a bare
# {"@id": ".../#person"} left the author nameless on every answers, recipe and
# hub page. Every author node is written out in full.
PERSON = {
    "@type": "Person",
    "name": "Joseph Bankole",
    "@id": PERSON_ID,
    "url": "%s/" % SITE,
}

DEFAULT_OG = "%s/assets/og/default.png" % SITE
RECIPES_OG = "%s/assets/og/recipes.png" % SITE

TITLE_MAX = 60   # characters before the " · Joseph Bankole" suffix
DESC_MAX = 155   # characters in the meta description
TEASER_MAX = 6   # rows in the homepage news teaser

TITLE_SUFFIX_RE = re.compile(r"\s*(?:·|&middot;|&#183;|&#xB7;)\s*Joseph Bankole\s*$")

# Collected during a run and printed to stderr at the end, grouped by kind.
WARNINGS: dict[str, list[str]] = {}
GATE_FAILURES: list[str] = []


def warn(kind: str, message: str) -> None:
    WARNINGS.setdefault(kind, []).append(message)

WAITLIST = (
    "mailto:partnerships@josephbankole.ca"
    "?subject=Waitlist%20%E2%80%94%20new%20client%20enquiry"
    "&body=A%20line%20on%20what%20you%27re%20building%2C%20the%20operational"
    "%20problem%2C%20and%20how%20to%20reach%20you%3A%0A%0A"
)
ENQUIRY = "mailto:partnerships@josephbankole.ca?subject=Enquiry%20(josephbankole.ca)"
SUBSTACK = "https://archvai.substack.com"
LINKEDIN = "https://www.linkedin.com/in/joseph-bankole/"

FONTS = (
    "https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,"
    "300..500;1,9..144,300..500&family=Inter+Tight:wght@400..600&"
    "family=IBM+Plex+Mono:wght@400;500&display=swap"
)

WPM = 225  # reading speed used for every "N min read" on the site

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
SHORT_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ---------------------------------------------------------------- extraction

def find_block(src: str, tag: str, cls: str | None = None, start: int = 0):
    """Locate the first <tag> (optionally carrying `cls`) and its matching close.

    Returns (open_start, inner_start, inner_end, close_end) or None. Nesting of
    the same tag is counted, so a <div class="prose"> containing <div>s closes
    in the right place.
    """
    if cls:
        pattern = re.compile(
            r"<%s\b[^>]*\bclass=\"[^\"]*(?<![-\w])%s(?![-\w])[^\"]*\"[^>]*>" % (tag, re.escape(cls))
        )
    else:
        pattern = re.compile(r"<%s\b[^>]*>" % tag)
    match = pattern.search(src, start)
    if not match:
        return None
    inner_start = match.end()
    depth = 1
    scan = re.compile(r"<(/?)%s\b" % tag)
    pos = inner_start
    while depth:
        step = scan.search(src, pos)
        if not step:
            return None
        if step.group(1):
            depth -= 1
            if depth == 0:
                return (match.start(), inner_start, step.start(), src.index(">", step.end()) + 1)
        else:
            depth += 1
        pos = step.end()
    return None


def inner(src: str, tag: str, cls: str | None = None) -> str | None:
    found = find_block(src, tag, cls)
    return src[found[1]:found[2]] if found else None


def meta_content(src: str, attr: str, name: str) -> str | None:
    match = re.search(
        r'<meta\s+%s="%s"\s+content="([^"]*)"\s*/?>' % (attr, re.escape(name)), src
    )
    return match.group(1) if match else None


def link_href(src: str, rel: str) -> str | None:
    match = re.search(r'<link\s+rel="%s"\s+href="([^"]*)"' % re.escape(rel), src)
    return match.group(1) if match else None


def tag_text(src: str, tag: str) -> str | None:
    match = re.search(r"<%s[^>]*>(.*?)</%s>" % (tag, tag), src, re.S)
    return match.group(1).strip() if match else None


def strip_tags(value: str) -> str:
    return re.sub(r"<[^>]+>", "", value)


def word_count(prose_html: str) -> int:
    text = re.sub(r"<(script|style)\b.*?</\1>", " ", prose_html, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", text))


def read_minutes(prose_html: str) -> int:
    return max(1, round(word_count(prose_html) / WPM))


def esc_attr(value: str) -> str:
    return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")


def normalise_waitlist(doc: str) -> str:
    """Every waitlist mailto on the site carries the same prompt in its body.

    57 of 58 conversion links used to open a blank compose window. Rewriting
    them here rather than per template keeps CTA copy a human wrote intact
    while still fixing the href underneath it.
    """
    # The whole quoted value is replaced, up to its closing quote. The old
    # pattern stopped at a raw apostrophe, so an href whose body still read
    # "you're" kept its tail after the rewrite and the homepage #work CTA
    # shipped with a duplicated body fragment (a44192e to 2026-09-22).
    target = WAITLIST.replace("&", "&amp;")
    for quote in ('"', "'"):
        doc = re.sub(
            r"%smailto:partnerships@josephbankole\.ca\?subject=Waitlist[^%s<>]*%s" % (quote, quote, quote),
            lambda m, q=quote: q + target + q,
            doc,
        )
    return doc


# ------------------------------------------------------------------- shell

def head_block(page) -> str:
    lines = [
        '<meta charset="UTF-8" />',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0" />',
        "<title>%s</title>" % page["title"],
    ]
    if page.get("description"):
        lines.append('<meta name="description" content="%s" />' % page["description"])
    lines.append('<meta name="theme-color" content="#1E223D" />')
    lines.append('<meta name="robots" content="%s" />' % page.get("robots", "index, follow"))
    if page.get("canonical"):
        lines.append('<link rel="canonical" href="%s" />' % page["canonical"])

    # A page nobody should share (the 404) gets no share-card metadata.
    if page.get("social", True):
        og_type = page.get("og_type", "website")
        lines += [
            '<meta property="og:type" content="%s" />' % og_type,
            '<meta property="og:site_name" content="Joseph Bankole" />',
            '<meta property="og:title" content="%s" />' % page.get("og_title", page["title"]),
        ]
        if page.get("og_description"):
            lines.append('<meta property="og:description" content="%s" />' % page["og_description"])
        if page.get("canonical"):
            lines.append('<meta property="og:url" content="%s" />' % page["canonical"])
        lines += [
            '<meta property="og:image" content="%s" />' % page["og_image"],
            '<meta property="og:image:width" content="1200" />',
            '<meta property="og:image:height" content="630" />',
        ]
        if page.get("published_iso"):
            lines.append('<meta property="article:published_time" content="%s" />' % page["published_iso"])
            lines.append('<meta property="article:modified_time" content="%s" />' % page["modified_iso"])
            lines.append('<meta property="article:author" content="Joseph Bankole" />')
        lines += [
            '<meta name="twitter:card" content="summary_large_image" />',
            '<meta name="twitter:title" content="%s" />' % page.get("og_title", page["title"]),
        ]
        if page.get("og_description"):
            lines.append('<meta name="twitter:description" content="%s" />' % page["og_description"])
        lines.append('<meta name="twitter:image" content="%s" />' % page["og_image"])
    lines += [
        '<link rel="icon" type="image/png" sizes="96x96" href="/favicon.png" />',
        '<link rel="icon" href="/favicon.ico" sizes="48x48 32x32 16x16" />',
        '<link rel="apple-touch-icon" href="/apple-touch-icon.png" />',
        '<link rel="preconnect" href="https://fonts.googleapis.com" />',
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />',
        '<link href="%s" rel="stylesheet" />' % FONTS,
        '<link rel="alternate" type="application/rss+xml" title="Joseph Bankole &#8212; news desk" href="/news-feed.xml" />',
        '<link rel="alternate" type="application/rss+xml" title="Joseph Bankole &#8212; field notes" href="/feed.xml" />',
        '<link rel="stylesheet" href="/assets/style.css" />',
    ]
    for extra in page.get("extra_css", []):
        lines.append('<link rel="stylesheet" href="%s" />' % extra)
    # Reveal animations are opt-in for scripted visitors only, so a page with
    # JavaScript switched off renders every block at full opacity instead of
    # hiding twelve of them.
    lines.append('<script>document.documentElement.className+=" js";</script>')
    if page.get("jsonld"):
        lines.append('<script type="application/ld+json">')
        lines.append(page["jsonld"])
        lines.append("</script>")
    return "\n".join(lines)


NAV_ITEMS = [
    ("About", "{root}#about"),
    ("Blog", "/blog/"),
    ("News", "/news/"),
    ("Answers", "/answers/"),
    ("Recipes", "/recipes/"),
    ("Projects", "{root}#projects"),
]

# Sub-hubs inside recipes/. These are hubs, not articles, so the article glob
# below must skip them or they get rebuilt with an article shell.
RECIPE_HUBS = (
    "breakfast",
    "mains",
    "sides-and-starters",
    "desserts",
    "kitchen-basics",
    "trinidadian",
    "nigerian",
)


def nav_block(location: str, root: str = "/") -> str:
    items = "".join(
        '<a href="%s">%s</a>' % (href.format(root=root), label) for label, href in NAV_ITEMS
    )
    return (
        '<nav class="nav" aria-label="Primary">\n'
        '  <a class="brand" href="/"><span class="mk">&#9670;</span> JOSEPH&nbsp;BANKOLE</a>\n'
        '  <div class="nav-links">\n'
        "    %s\n"
        '    <a class="btn js-waitlist" data-location="%s-nav" href="%s">'
        '<span class="btn-label-full">Join the waitlist</span>'
        '<span class="btn-label-short">Waitlist</span></a>\n'
        "  </div>\n"
        "</nav>" % (items, location, WAITLIST)
    )


def footer_block(location: str) -> str:
    return (
        "<footer>\n"
        '  <div class="foot">\n'
        '    <div class="fcol">\n'
        '      <span class="footmark"><span class="mk">&#9670;</span> JOSEPH BANKOLE</span>\n'
        '      <span class="copy">Fintech operations &middot; Applied AI &middot; Montreal</span>\n'
        "    </div>\n"
        '    <div class="fcol fcol-end">\n'
        '      <a href="/news/">News desk</a>\n'
        '      <a href="/blog/">Field notes</a>\n'
        '      <a href="/answers/">Answers</a>\n'
        '      <a href="%s" target="_blank" rel="noopener">LinkedIn</a>\n'
        '      <a href="/privacy.html">Privacy</a>\n'
        '      <a class="js-waitlist" data-location="%s-footer" href="%s">Join the waitlist</a>\n'
        '      <a href="%s">partnerships@josephbankole.ca</a>\n'
        '      <span class="copy">Not taking new clients right now &middot; I reply within one business day.</span>\n'
        "    </div>\n"
        "  </div>\n"
        '  <div class="foot foot-legal"><span class="copy">&copy; 2026 Joseph Bankole. All rights reserved.</span></div>\n'
        "</footer>" % (LINKEDIN, location, WAITLIST, ENQUIRY)
    )


HUBLINKS = (
    '<nav class="hublinks" aria-label="Sections of this site">\n'
    '  <a href="/news/"><span class="hl-t">The news desk</span>'
    '<span class="hl-d">A running brief on agentic commerce and payments, with every source named.</span></a>\n'
    '  <a href="/blog/"><span class="hl-t">Field notes</span>'
    '<span class="hl-d">What breaks when payment systems and AI agents run in production.</span></a>\n'
    '  <a href="/answers/"><span class="hl-t">Answers</span>'
    '<span class="hl-d">Short definitions of the terms that keep coming up.</span></a>\n'
    "</nav>"
)


def subscribe_block() -> str:
    return (
        '<section class="subband" aria-labelledby="sub-h">\n'
        '  <h2 id="sub-h">The weekly email</h2>\n'
        "  <p>The ARCHV AI newsletter is the week in AI in plain English, plus the "
        "agentic-commerce stories that touch how money moves. It goes out on "
        "Substack.</p>\n"
        '  <a class="btn btn--ghost" href="%s" target="_blank" rel="noopener">Read it on Substack</a>\n'
        "</section>" % SUBSTACK
    )


def cta_block(heading: str, paragraph: str, location: str) -> str:
    return (
        '<section class="ctaband" aria-labelledby="cta-h">\n'
        '  <h2 id="cta-h">%s</h2>\n'
        "  <p>%s</p>\n"
        '  <a class="btn js-waitlist" data-location="%s" href="%s">Join the waitlist</a>\n'
        "</section>" % (heading, paragraph, location, WAITLIST)
    )


def block_text(value: str | None) -> str | None:
    """Normalise a lifted author block so re-parsing it yields the same string.

    Leading newlines are dropped (the opening tag is emitted on its own line)
    and trailing whitespace is trimmed. Without this the block gained a blank
    line on every run.
    """
    if value is None:
        return None
    return value.strip("\n").rstrip()


def tidy(doc: str) -> str:
    """Trailing whitespace is what stopped this being idempotent.

    Author blocks are lifted with their indentation and re-indented on the way
    back in, so a whitespace-only line grew by a level on every run. No page on
    this site contains a <pre>, so trimming line ends is safe.
    """
    return "\n".join(line.rstrip() for line in doc.split("\n"))


def document(page, body: str) -> str:
    doc = tidy(
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        "%s\n"
        "</head>\n"
        "<body>\n"
        '<a class="skip" href="#main">Skip to content</a>\n'
        "%s\n\n"
        "%s\n\n"
        "%s\n"
        '<script src="/assets/site.js" defer></script>\n'
        '<script src="/assets/analytics.js" defer></script>\n'
        "%s"
        "</body>\n"
        "</html>\n"
        % (
            head_block(page),
            nav_block(page["location"], page.get("nav_root", "/")),
            body,
            footer_block(page["location"]),
            "".join('<script src="%s" defer></script>\n' % s for s in page.get("extra_js", [])),
        )
    )
    return normalise_waitlist(doc)


# -------------------------------------------------------------- page parsing

def promote_headings(prose: str) -> str:
    """A section heading inside an article is an h2.

    Three answers and privacy pages jumped h1 to h3 with no h2 between them, so
    their outline claimed a level that was never there.
    """
    if re.search(r"<h2\b", prose):
        return prose
    if not re.search(r"<h3\b", prose):
        return prose
    prose = re.sub(r"<h3(\b)", r"<h2\1", prose)
    prose = re.sub(r"</h3>", "</h2>", prose)
    return prose


def rel_name(path: pathlib.Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


SHARE_TITLE_MIN = 20


def title_body(title: str) -> str:
    """The <title> without the site-name suffix, still HTML-escaped."""
    return TITLE_SUFFIX_RE.sub("", title).strip()


def share_title(title: str) -> str:
    """og:title and twitter:title.

    The site-name suffix comes off, because og:site_name carries it, except
    where the rest is too short to say whose page it is: a card reading only
    "Privacy" or "Blog" names nobody.
    """
    body = title_body(title)
    if not body:
        return title
    return body if text_len(body) > SHARE_TITLE_MIN else title


def text_len(value: str) -> int:
    """Length as a reader or a search result sees it: entities decoded."""
    return len(html.unescape(strip_tags(value)).strip())


def parse_common(path: pathlib.Path, src: str) -> dict:
    canonical = link_href(src, "canonical")
    title = tag_text(src, "title") or ""
    if not title:
        # Only when a page has no <title> at all is one derived from its h1.
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", src, re.S)
        if h1:
            title = "%s &middot; Joseph Bankole" % strip_tags(h1.group(1)).strip()
            warn("pages with no <title>, derived from the h1", rel_name(path))
    og_image = meta_content(src, "property", "og:image") or ""
    # 26 news pages pointed at a per-edition card that was never rendered.
    if og_image.startswith(SITE):
        on_disk = REPO / og_image[len(SITE) + 1:]
        if not on_disk.exists():
            og_image = DEFAULT_OG
    if not og_image:
        og_image = DEFAULT_OG
    description = meta_content(src, "name", "description")
    # The authored <title> and meta description are the source of truth. The
    # share-card title follows the <title> (minus the site-name suffix, which
    # og:site_name already carries) and the share-card description follows the
    # meta description, so a trimmed meta cannot leave a 699-character
    # og:description behind it.
    return {
        "path": path,
        "title": title,
        "description": description,
        "canonical": canonical,
        "og_title": share_title(title),
        "og_description": description or meta_content(src, "property", "og:description"),
        "og_image": og_image,
        "og_type": meta_content(src, "property", "og:type") or "website",
    }


def check_lengths(page: dict, kind: str, day: dt.date | None, today: dt.date) -> None:
    """The title and description caps. A gate for today's news, a warning elsewhere."""
    name = rel_name(page["path"])
    problems = []
    title_chars = text_len(title_body(page["title"]))
    if title_chars > TITLE_MAX:
        problems.append("title %d chars (max %d)" % (title_chars, TITLE_MAX))
    desc = page.get("description") or ""
    desc_chars = text_len(desc)
    if not desc:
        problems.append("no meta description")
    elif desc_chars > DESC_MAX:
        problems.append("meta description %d chars (max %d)" % (desc_chars, DESC_MAX))
    if not problems:
        if desc and not re.search(r"[.?!][\"'’”)]?$", html.unescape(desc).strip()):
            warn("meta descriptions that do not end on a full sentence", name)
        return
    line = "%s: %s" % (name, "; ".join(problems))
    if kind == "news" and day is not None and day >= today:
        GATE_FAILURES.append(line)
    else:
        warn("%s pages over the title or description cap" % kind, line)


def parse_article_head(src: str) -> dict:
    head = inner(src, "header", "article-head") or ""
    kicker = re.search(r'<span class="index"[^>]*>(.*?)</span>', head, re.S)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", head, re.S)
    stand = re.search(r'<p class="(?:standfirst|lede)"[^>]*>(.*?)</p>', head, re.S)
    meta = re.search(r'<(?:div|p) class="article-meta"[^>]*>(.*?)</(?:div|p)>', head, re.S)
    spans = []
    if meta:
        for chunk in re.findall(r"<(?:span|time)[^>]*>(.*?)</(?:span|time)>", meta.group(1), re.S):
            spans.append(chunk.strip())
    return {
        "kicker": kicker.group(1).strip() if kicker else "",
        "h1": h1.group(1).strip() if h1 else "",
        "standfirst": stand.group(1).strip() if stand else "",
        "meta_spans": spans,
    }


def topic_span(spans: list[str]) -> str:
    """Keep the hand-written topic label, drop the bits the template derives."""
    for value in spans:
        plain = strip_tags(value).strip()
        if not plain:
            continue
        if re.match(r"^\d+\s+min read$", plain):
            continue
        if plain in {"Sourced", "Joseph Bankole"}:
            continue
        if re.match(r"^\d+\s+sources?$", plain):
            continue
        if re.match(r"^(Updated\s+)?\d{1,2}\s+\w+\s+\d{4}$", plain):
            continue
        if re.match(r"^\w+\s+\d{4}$", plain):
            continue
        if plain.startswith("Last updated"):
            continue
        return value
    return ""


def existing_cta(src: str, fallback_h: str, fallback_p: str) -> tuple[str, str]:
    block = inner(src, "div", "ctaband") or inner(src, "section", "ctaband")
    if not block:
        return fallback_h, fallback_p
    heading = re.search(r"<h[23][^>]*>(.*?)</h[23]>", block, re.S)
    para = re.search(r"<p[^>]*>(.*?)</p>", block, re.S)
    return (
        heading.group(1).strip() if heading else fallback_h,
        para.group(1).strip() if para else fallback_p,
    )


def existing_modified(src: str) -> str | None:
    match = re.search(r'"dateModified"\s*:\s*"([^"]+)"', src)
    return match.group(1) if match else None


def existing_published(src: str) -> str | None:
    match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', src)
    return match.group(1) if match else None


# ------------------------------------------------------------------ indexes

ROW_RE = re.compile(
    r'<a class="post-row" href="([^"]+)">\s*'
    r'<span class="date">(.*?)</span>\s*'
    r'<span class="ttl">(.*?)<span>(.*?)</span></span>',
    re.S,
)


def read_index_rows(path: pathlib.Path) -> dict:
    src = path.read_text(encoding="utf-8")
    rows = {}
    for href, date, title, dek in ROW_RE.findall(src):
        rows[href] = {
            "href": href,
            "date": date.strip(),
            "title": title.strip(),
            "dek": dek.strip(),
        }
    return rows


def post_row(entry: dict, iso: str | None = None) -> str:
    date = (
        '<time class="date" datetime="%s">%s</time>' % (iso, entry["date"])
        if iso
        else '<span class="date">%s</span>' % entry["date"]
    )
    return (
        '        <a class="post-row" href="%s">\n'
        "          %s\n"
        '          <span class="ttl">%s<span>%s</span></span>\n'
        '          <span class="arrow">&rarr;</span>\n'
        "        </a>\n" % (entry["href"], date, entry["title"], entry["dek"])
    )


# ------------------------------------------------------------- news editions

NEWS_FILE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(.+)\.html$")


def news_editions() -> list[dict]:
    editions = []
    for path in sorted((REPO / "news").glob("*.html")):
        match = NEWS_FILE_RE.match(path.name)
        if not match:
            continue
        year, month, day = (int(part) for part in match.groups()[:3])
        editions.append(
            {
                "path": path,
                "date": dt.date(year, month, day),
                "iso": "%04d-%02d-%02d" % (year, month, day),
                "href": "/news/%s" % path.name,
            }
        )
    editions.sort(key=lambda e: e["date"])
    return editions


def human_date(day: dt.date) -> str:
    return "%d %s %d" % (day.day, MONTHS[day.month - 1], day.year)


def short_date(day: dt.date) -> str:
    return "%d %s %d" % (day.day, SHORT_MONTHS[day.month - 1], day.year)


# ------------------------------------------------------------------ renderers

def render_article(path: pathlib.Path, kind: str, ctx: dict) -> str:
    src = path.read_text(encoding="utf-8")
    page = parse_common(path, src)
    head = parse_article_head(src)
    prose = label_citations(promote_headings(block_text(inner(src, "div", "prose")) or ""))

    sources_block = inner(src, "div", "sources") or inner(src, "section", "sources")
    sources_ol = None
    source_count = 0
    if sources_block:
        found = find_block(sources_block, "ol")
        if found:
            sources_ol = sources_block[found[1]:found[2]]
            source_count = len(re.findall(r"<li\b", sources_ol))

    minutes = read_minutes(prose)
    words = word_count(prose)

    crumb_label, crumb_href = ctx["crumb"]
    location = kind

    # ---- dates
    published_iso = None
    date_display = None
    date_attr = None
    day = None
    if kind == "news":
        edition = ctx["edition"]
        day = edition["date"]
        date_attr = edition["iso"]
        date_display = human_date(edition["date"])
        published_iso = sitelib.local_iso(day, 8)
    else:
        raw = existing_published(src)
        if raw and re.match(r"^\d{4}-\d{2}-\d{2}", raw):
            date_attr = raw[:10]
            day = dt.date.fromisoformat(date_attr)
            date_display = human_date(day)
            published_iso = sitelib.local_iso(day, 9)

    # This script does not invent dates. It used to fall back to a hardcoded
    # BUILD_DATE, which pinned both answers pages to "Updated 9 August 2026"
    # for as long as the constant sat there. A page's own datePublished is the
    # only fallback, and a page carrying neither date is an error, not a guess.
    modified = existing_modified(src)
    if not modified:
        if not date_attr:
            try:
                where = path.relative_to(REPO)
            except ValueError:
                where = path
            raise SystemExit(
                "%s carries neither dateModified nor datePublished in its JSON-LD.\n"
                "Add both. This script will not invent a date for it." % where
            )
        modified = date_attr
    if re.match(r"^\d{4}-\d{2}-\d{2}$", modified):
        modified = sitelib.local_iso(dt.date.fromisoformat(modified), 9)

    page["published_iso"] = published_iso
    page["modified_iso"] = modified
    page["location"] = location
    page["og_type"] = "article"

    # ---- share card
    if kind == "news" and page["og_image"] == DEFAULT_OG:
        warn("news pages falling back to the default share card", rel_name(path))
    if kind == "recipes" and page["og_image"] == DEFAULT_OG:
        # A payments card on a recipe is off-topic. Pages with their own photo
        # keep it; the rest get the food-neutral card.
        page["og_image"] = RECIPES_OG

    if kind in ("news", "blog", "answers"):
        check_lengths(page, kind, day, ctx["today"])

    # ---- schema
    if kind in ("answers", "recipes"):
        # The answers @graph (DefinedTerm + FAQPage + BreadcrumbList) is the
        # best-built schema on the site. It is lifted through untouched.
        # Recipes joined it 2026-08-30: their @graph carries Recipe (or Article
        # where no photo exists) plus BreadcrumbList and FAQPage, generated per
        # page, and rebuilding it here would silently drop the FAQPage node.
        existing = re.search(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>', src, re.S
        )
        page["jsonld"] = (
            normalise_jsonld(existing.group(1), kind, page, head, crumb_label, crumb_href)
            if existing
            else ""
        )
    else:
        page["jsonld"] = article_jsonld(
            kind, page, head, published_iso, modified, words, crumb_label, crumb_href
        )

    # ---- article head
    meta_bits = ['<span class="byline">Joseph Bankole</span>']
    if kind == "answers":
        # An answers page shows when it was last revised, so the label is built
        # from dateModified. Building it from datePublished, as this did until
        # 2026-08-15, published a publication date under an "Updated" label.
        updated_attr = modified[:10]
        meta_bits.append(
            '<time datetime="%s">Updated %s</time>'
            % (updated_attr, human_date(dt.date.fromisoformat(updated_attr)))
        )
    elif date_attr and date_display:
        meta_bits.append('<time datetime="%s">%s</time>' % (date_attr, date_display))
    meta_bits.append("<span>%d min read</span>" % minutes)
    if source_count:
        meta_bits.append(
            "<span>%d source%s</span>" % (source_count, "" if source_count == 1 else "s")
        )
    topic = topic_span(head["meta_spans"])
    if topic:
        meta_bits.append("<span>%s</span>" % topic)

    parts = [
        '<main id="main">',
        '<article class="article">',
        '  <header class="article-head wrap">',
        '    <nav class="crumbs" aria-label="Breadcrumb">'
        '<a href="/">Home</a> <span aria-hidden="true">&rsaquo;</span> '
        '<a href="%s">%s</a></nav>' % (crumb_href, crumb_label),
    ]
    if head["kicker"]:
        parts.append('    <span class="index">%s</span>' % head["kicker"])
    parts.append("    <h1>%s</h1>" % head["h1"])
    if head["standfirst"]:
        parts.append('    <p class="standfirst">%s</p>' % head["standfirst"])
    parts.append('    <p class="article-meta">%s</p>' % "".join(meta_bits))
    parts.append("  </header>")
    parts.append("")
    parts.append('  <div class="article-body wrap">')
    parts.append('    <div class="prose">')
    parts.append(prose)
    parts.append("    </div>")
    if sources_ol:
        parts.append('    <section class="sources" aria-labelledby="sources-h">')
        parts.append('      <h2 id="sources-h">Sources</h2>')
        parts.append("      <ol>%s</ol>" % sources_ol)
        parts.append("    </section>")
    parts.append("  </div>")
    parts.append("</article>")
    parts.append("")
    parts.append('<div class="article-tail wrap">')

    # ---- pager: news editions and blog posts both read in both directions
    pager = ctx.get("pager")
    if pager and (pager["prev"] or pager["next"]):
        noun = "edition" if kind == "news" else "post"
        parts.append(
            '  <nav class="pager" aria-label="Neighbouring %ss">' % noun
        )
        if pager["prev"]:
            parts.append(
                '    <a class="pager-prev" href="%s"><span class="pager-dir">'
                "&larr; Earlier %s</span><span class=\"pager-ttl\">%s</span>"
                '<span class="pager-date">%s</span></a>'
                % (pager["prev"]["href"], noun, pager["prev"]["title"], pager["prev"]["date"])
            )
        if pager["next"]:
            parts.append(
                '    <a class="pager-next" href="%s"><span class="pager-dir">'
                "Later %s &rarr;</span><span class=\"pager-ttl\">%s</span>"
                '<span class="pager-date">%s</span></a>'
                % (pager["next"]["href"], noun, pager["next"]["title"], pager["next"]["date"])
            )
        parts.append("  </nav>")

    # ---- related
    # Rows a human picked are lifted and kept. Rows this script generated carry
    # data-generated, so the next run regenerates them rather than freezing
    # them as if someone had chosen them.
    related_rows = ctx.get("related_rows")
    related_heading = ctx["related_heading"]
    generated = related_rows is not None
    if related_rows is None:
        found = find_block(src, "section", "related") or find_block(src, "div", "related")
        block = src[found[0]:found[3]] if found else ""
        if block and "data-generated" not in block[: block.index(">") + 1]:
            related_rows = inner(block, "div", "postlist")
            if related_rows:
                related_rows = block_text(related_rows)
        if not related_rows and ctx.get("fallback_rows"):
            related_rows = ctx["fallback_rows"]
            related_heading = ctx["fallback_heading"]
            generated = True
    if related_rows:
        parts.append(
            '  <section class="related" aria-labelledby="related-h"%s>'
            % (' data-generated="latest"' if generated and kind != "news" else "")
        )
        parts.append('    <h2 id="related-h">%s</h2>' % related_heading)
        parts.append('    <div class="postlist">')
        parts.append(related_rows)
        parts.append("    </div>")
        parts.append("  </section>")

    if kind == "recipes":
        # A recipe page links up to the hubs it sits in, then the recipes index.
        # The newsletter band and waitlist CTA below still close it: what a
        # recipe ends on is a founder decision (review 2026-09-22, Decision 6),
        # so the build does not drop them on its own.
        parts.append(indent(recipe_links(ctx.get("recipe_hubs", []), ctx.get("recipe_total", 0)), 2))
    parts.append(indent(subscribe_block(), 2))
    cta_h, cta_p = existing_cta(
        src,
        "Building in agentic commerce or payments?",
        "This is the intersection I work in. I'm not taking new clients at the moment, "
        'so write to <a class="inline-link js-waitlist" href="%s" data-location="%s-cta-copy">'
        "partnerships@josephbankole.ca</a> and I'll add you to the waitlist." % (WAITLIST, kind),
    )
    parts.append(indent(cta_block(cta_h, cta_p, "%s-cta" % kind), 2))
    parts.append(indent(HUBLINKS, 2))
    parts.append("</div>")
    parts.append("</main>")

    return document(page, "\n".join(parts))


def label_citations(prose: str) -> str:
    """Give each [n] citation link an accessible name.

    The visible text is only "[1]", so a screen reader's link list read out a
    column of bracketed numbers. The author's text is untouched; the label is
    an attribute on the same anchor, added once.
    """
    return re.sub(
        r"<a\b((?:(?!aria-label=)[^>])*)>\[(\d+)\]</a>",
        r'<a\1 aria-label="Source \2">[\2]</a>',
        prose,
    )


def recipe_links(hubs: list[dict], total: int) -> str:
    rows = [
        '  <a href="%s"><span class="hl-t">%s</span><span class="hl-d">%d recipe%s</span></a>'
        % (hub["href"], hub["name"], hub["count"], "" if hub["count"] == 1 else "s")
        for hub in hubs
    ]
    rows.append(
        '  <a href="/recipes/"><span class="hl-t">All recipes</span>'
        '<span class="hl-d">%d recipes</span></a>' % total
    )
    return (
        '<nav class="hublinks" aria-label="More recipes">\n%s\n</nav>' % "\n".join(rows)
    )


def normalise_jsonld(raw: str, kind: str, page: dict, head: dict,
                     crumb_label: str, crumb_href: str) -> str:
    """Tidy a lifted answers or recipes @graph without rebuilding it.

    Three repairs, nothing else changes:
      - every bare author {"@id": ".../#person"} is written out in full;
      - recipeCategory comes off nodes typed Article (it is a Recipe property,
        and the pages without a photo are typed Article);
      - a graph with no BreadcrumbList gets one. The answers desk wrote
        what-is-mastercard-agent-pay with a FAQPage only, and this script
        lifted answers JSON-LD verbatim, so nothing ever added it.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as err:
        warn("JSON-LD that does not parse (left as written)", "%s: %s" % (rel_name(page["path"]), err))
        return raw

    def fix(node):
        if isinstance(node, dict):
            author = node.get("author")
            if isinstance(author, dict) and author.get("@id") == PERSON_ID and set(author) <= {"@id", "@type", "name", "url"}:
                node["author"] = dict(PERSON)
            if node.get("@type") == "Article":
                node.pop("recipeCategory", None)
            for value in node.values():
                fix(value)
        elif isinstance(node, list):
            for value in node:
                fix(value)

    fix(data)
    graph = data.get("@graph") if isinstance(data, dict) else None
    if isinstance(graph, list) and not any(
        isinstance(node, dict) and node.get("@type") == "BreadcrumbList" for node in graph
    ):
        name = html.unescape(strip_tags(head["h1"])).strip() or html.unescape(page["og_title"])
        graph.append(
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": "%s/" % SITE},
                    {"@type": "ListItem", "position": 2, "name": crumb_label, "item": SITE + crumb_href},
                    {"@type": "ListItem", "position": 3, "name": name, "item": page["canonical"]},
                ],
            }
        )
    return json.dumps(data, indent=2, ensure_ascii=False).replace("</", "<\\/")


def indent(block: str, spaces: int) -> str:
    pad = " " * spaces
    return "\n".join(pad + line if line.strip() else line for line in block.split("\n"))


def article_jsonld(kind, page, head, published, modified, words, crumb_label, crumb_href) -> str:
    schema_type = "NewsArticle" if kind == "news" else "BlogPosting"
    article = {
        "@type": schema_type,
        "headline": html.unescape(strip_tags(head["h1"])).rstrip("."),
        "description": html.unescape(page.get("og_description") or page.get("description") or ""),
        "image": [page["og_image"]],
        "author": {
            "@type": "Person",
            "name": "Joseph Bankole",
            "@id": "%s/#person" % SITE,
            "url": "%s/" % SITE,
        },
        "publisher": {
            "@type": "Organization",
            "name": "Joseph Bankole",
            "url": "%s/" % SITE,
            "logo": {"@type": "ImageObject", "url": "%s/apple-touch-icon.png" % SITE},
        },
        "wordCount": words,
        "inLanguage": "en",
        "isPartOf": {"@id": "%s/#website" % SITE},
        "mainEntityOfPage": {"@type": "WebPage", "@id": page["canonical"]},
    }
    if published:
        article["datePublished"] = published
    article["dateModified"] = modified
    article["articleSection"] = (
        "Agentic commerce" if kind == "news" else "Payments and applied AI"
    )
    crumbs = {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home", "item": "%s/" % SITE},
            {
                "@type": "ListItem",
                "position": 2,
                "name": crumb_label,
                "item": SITE + crumb_href,
            },
            {
                "@type": "ListItem",
                "position": 3,
                "name": html.unescape(strip_tags(head["h1"])).rstrip("."),
                "item": page["canonical"],
            },
        ],
    }
    graph = {"@context": "https://schema.org", "@graph": [article, crumbs]}
    return json.dumps(graph, indent=2, ensure_ascii=False)


def render_hub(path: pathlib.Path, kind: str, crumb: tuple[str, str]) -> str:
    src = path.read_text(encoding="utf-8")
    page = parse_common(path, src)
    head = parse_article_head(src)
    page["location"] = kind
    page["og_type"] = "website"
    if kind == "recipes" and page["og_image"] == DEFAULT_OG:
        page["og_image"] = RECIPES_OG

    listing = None
    found = find_block(src, "div", "postlist")
    if found:
        listing = block_text(src[found[1]:found[2]])

    tail_note = re.search(
        r'<p style="margin-top:28px">(.*?)</p>|<p class="hub-note">(.*?)</p>', src, re.S
    )
    note = None
    if tail_note:
        note = (tail_note.group(1) or tail_note.group(2) or "").strip()

    # Machine-readable dates on every row of every index.
    if listing and kind == "news":
        def stamp(match):
            label = match.group(1).strip()
            iso = index_date_iso(label)
            return (
                '<time class="date" datetime="%s">%s</time>' % (iso, label)
                if iso
                else '<span class="date">%s</span>' % label
            )

        listing = re.sub(r'<(?:span|time)[^>]*class="date"[^>]*>(.*?)</(?:span|time)>',
                         stamp, listing)
        listing = group_by_month(listing)

    cta_h, cta_p = existing_cta(src, "The weekly read", "")
    count = len(re.findall(r'class="post-row"', listing or ""))

    parts = [
        '<main id="main">',
        '  <header class="article-head wrap">',
        '    <nav class="crumbs" aria-label="Breadcrumb">'
        '<a href="/">Home</a> <span aria-hidden="true">&rsaquo;</span> '
        "<span aria-current=\"page\">%s</span></nav>" % crumb[0],
        '    <span class="index">%s</span>' % (head["kicker"] or crumb[0]),
        "    <h1>%s</h1>" % head["h1"],
    ]
    if head["standfirst"]:
        parts.append('    <p class="standfirst">%s</p>' % head["standfirst"])
    if count:
        parts.append(
            '    <p class="article-meta"><span>%d %s</span></p>'
            % (count, {"news": "editions", "blog": "posts", "answers": "definitions",
                       "recipes": "recipes"}[kind])
        )
    if kind == "news":
        # One link per month heading, so a phone reader can skip the 40-screen
        # scroll to reach July (UX-11). Built from the headings group_by_month
        # wrote, so the strip and the list cannot disagree.
        months = re.findall(r'<h2 class="listhead" id="(m-[\w-]+)">([^<]+)</h2>', listing or "")
        if len(months) > 1:
            parts.append(
                '    <nav class="monthjump" aria-label="Jump to a month">%s</nav>'
                % "".join('<a href="#%s">%s</a>' % (anchor, label) for anchor, label in months)
            )
    parts.append("  </header>")
    parts.append("")
    parts.append('  <div class="article-body wrap">')
    parts.append('    <div class="postlist">')
    parts.append(listing or "")
    parts.append("    </div>")
    if note:
        parts.append('    <p class="hub-note">%s</p>' % note)
    parts.append("  </div>")
    parts.append("")
    parts.append('<div class="article-tail wrap">')
    parts.append(indent(subscribe_block(), 2))
    if cta_p:
        parts.append(indent(cta_block(cta_h, cta_p, "%s-hub-cta" % kind), 2))
    parts.append(indent(HUBLINKS, 2))
    parts.append("</div>")
    parts.append("</main>")

    page["jsonld"] = hub_jsonld(page, head, crumb, kind, src)
    return document(page, "\n".join(parts))


def hub_jsonld(page, head, crumb, kind, src) -> str:
    if kind == "answers":
        existing = re.search(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>', src, re.S
        )
        if existing:
            return existing.group(1)
    graph = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "CollectionPage",
                "@id": page["canonical"],
                "name": html.unescape(strip_tags(head["h1"])).rstrip("."),
                "description": html.unescape(page.get("description") or ""),
                "url": page["canonical"],
                "inLanguage": "en",
                "isPartOf": {"@id": "%s/#website" % SITE},
                "author": dict(PERSON),
            },
            {
                "@type": "BreadcrumbList",
                "itemListElement": [
                    {"@type": "ListItem", "position": 1, "name": "Home", "item": "%s/" % SITE},
                    {"@type": "ListItem", "position": 2, "name": crumb[0], "item": page["canonical"]},
                ],
            },
        ],
    }
    return json.dumps(graph, indent=2, ensure_ascii=False)


HUB_ROW_RE = re.compile(r'[ \t]*<a class="post-row"[^>]*>.*?</a>', re.S)


def group_by_month(listing: str) -> str:
    """The news hub, newest month first, each month under its own h2.

    88 editions in one flat list ran to 40 phone screens with no heading
    between the h1 and the footer. Rows are re-sorted by their own datetime
    and re-grouped on every run, so a row the desk prepends anywhere in the
    list lands in the right month. h2.listhead is the class the recipe hubs
    already style for in-list headings.
    """
    rows = []
    for position, match in enumerate(HUB_ROW_RE.finditer(listing)):
        text = match.group(0).strip()
        stamp = re.search(r'datetime="(\d{4}-\d{2}-\d{2})"', text)
        if not stamp:
            href = re.search(r'href="/news/(\d{4}-\d{2}-\d{2})-', text)
            stamp = href
        rows.append((stamp.group(1) if stamp else "", position, text))
    if not rows:
        return listing
    rows.sort(key=lambda row: (row[0], -row[1]), reverse=True)
    out = []
    current = None
    for iso, _, text in rows:
        month = iso[:7]
        if month != current:
            current = month
            if iso:
                label = "%s %s" % (MONTHS[int(iso[5:7]) - 1], iso[:4])
                out.append('      <h2 class="listhead" id="m-%s">%s</h2>' % (month, label))
            else:
                out.append('      <h2 class="listhead" id="m-undated">Undated</h2>')
        out.append("      " + text)
    return block_text("\n".join(out))


INDEX_DATE_RE = re.compile(r"^(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})$")


def index_date_iso(label: str) -> str | None:
    match = INDEX_DATE_RE.match(label.strip())
    if not match:
        return None
    day, mon, year = match.groups()
    if mon not in SHORT_MONTHS:
        return None
    return "%s-%02d-%02d" % (year, SHORT_MONTHS.index(mon) + 1, int(day))


def render_doc(path: pathlib.Path, location: str) -> str:
    """Prose page with no conversion furniture (privacy)."""
    src = path.read_text(encoding="utf-8")
    page = parse_common(path, src)
    head = parse_article_head(src)
    page["location"] = location
    prose = promote_headings(block_text(inner(src, "div", "prose")) or "")
    page["jsonld"] = json.dumps(
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "@id": page["canonical"],
            "name": html.unescape(strip_tags(head["h1"])).rstrip("."),
            "url": page["canonical"],
            "inLanguage": "en",
            "isPartOf": {"@id": "%s/#website" % SITE},
        },
        indent=2,
        ensure_ascii=False,
    )
    parts = [
        '<main id="main">',
        '<article class="article">',
        '  <header class="article-head wrap">',
        '    <nav class="crumbs" aria-label="Breadcrumb">'
        '<a href="/">Home</a> <span aria-hidden="true">&rsaquo;</span> '
        '<span aria-current="page">Privacy</span></nav>',
        '    <span class="index">%s</span>' % (head["kicker"] or "Privacy"),
        "    <h1>%s</h1>" % head["h1"],
    ]
    if head["standfirst"]:
        parts.append('    <p class="standfirst">%s</p>' % head["standfirst"])
    if head["meta_spans"]:
        parts.append(
            '    <p class="article-meta">%s</p>'
            % "".join("<span>%s</span>" % s for s in head["meta_spans"])
        )
    parts += [
        "  </header>",
        "",
        '  <div class="article-body wrap">',
        '    <div class="prose">',
        prose,
        "    </div>",
        "  </div>",
        "</article>",
        '<div class="article-tail wrap">',
        indent(HUBLINKS, 2),
        "</div>",
        "</main>",
    ]
    return document(page, "\n".join(parts))


def render_404(path: pathlib.Path, latest_rows: str) -> str:
    """The not-found page, in the same shell as everything else.

    It used to be a centred card with one link home: no nav, no <main>, no
    footer and no analytics.js, so a broken inbound link was a dead end and was
    never recorded. Its own copy (kicker, headline, line, button) is lifted and
    kept; the shell, the latest editions and the section links are added.
    It stays noindex and carries no share-card metadata.
    """
    src = path.read_text(encoding="utf-8")
    page = parse_common(path, src)
    page["location"] = "404"
    page["robots"] = meta_content(src, "name", "robots") or "noindex"
    page["social"] = False
    page["jsonld"] = ""

    body = src[src.find("<body"):] if "<body" in src else src
    kicker = re.search(r'<span class="index"[^>]*>(.*?)</span>', body, re.S)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", body, re.S)
    after_h1 = body[h1.end():] if h1 else body
    line = re.search(r'<p class="standfirst">(.*?)</p>', after_h1, re.S) or re.search(
        r"<p\b[^>]*>(?!\s*<a)(.*?)</p>", after_h1, re.S
    )
    button = re.search(r'<a class="btn" href="/">(.*?)</a>', body, re.S)

    parts = [
        '<main id="main">',
        '  <header class="article-head wrap">',
        '    <span class="index">%s</span>' % (kicker.group(1).strip() if kicker else "Error 404"),
        "    <h1>%s</h1>" % (h1.group(1).strip() if h1 else "Not found"),
    ]
    if line:
        parts.append('    <p class="standfirst">%s</p>' % line.group(1).strip())
    parts += [
        "  </header>",
        "",
        '  <div class="article-body wrap">',
        '    <p><a class="btn" href="/">%s</a></p>' % (button.group(1).strip() if button else "Back to home"),
        "  </div>",
        "",
        '<div class="article-tail wrap">',
        '  <section class="related" aria-labelledby="related-h">',
        '    <h2 id="related-h">Latest from the desk</h2>',
        '    <div class="postlist">',
        latest_rows,
        "    </div>",
        "  </section>",
        indent(HUBLINKS, 2),
        "</div>",
        "</main>",
    ]
    return document(page, "\n".join(parts))


def cap_teaser(src: str) -> str:
    """Hold the homepage news teaser at TEASER_MAX rows, newest kept.

    It was cut from 36 rows to 6 on 2026-08-24 and grew back to 17, one row a
    day, because the daily desk prepends a row and nothing ever took one away.
    """
    section = find_block(src, "section")
    start = 0
    while section:
        opening = src[section[0]:section[1]]
        if 'id="news"' in opening:
            break
        start = section[3]
        section = find_block(src, "section", start=start)
    if not section:
        return src
    region = src[section[1]:section[2]]
    rows = list(re.finditer(r'[ \t]*<a class="post-row"[^>]*>.*?</a>\n?', region, re.S))
    if len(rows) <= TEASER_MAX:
        return src
    GATE_FAILURES.append(
        "index.html: homepage news teaser holds %d rows (max %d)" % (len(rows), TEASER_MAX)
    )

    def stamp(match):
        found = re.search(r'datetime="(\d{4}-\d{2}-\d{2})"', match.group(0)) or re.search(
            r'href="/news/(\d{4}-\d{2}-\d{2})-', match.group(0)
        )
        return found.group(1) if found else ""

    ranked = sorted(range(len(rows)), key=lambda i: (stamp(rows[i]), -i), reverse=True)
    drop = set(ranked[TEASER_MAX:])
    for i in sorted(drop, reverse=True):
        region = region[: rows[i].start()] + region[rows[i].end():]
    return src[: section[1]] + region + src[section[2]:]


def shell_pass(path: pathlib.Path, location: str, nav_root: str = "/") -> str:
    """Swap the nav and footer on a bespoke page without touching its body.

    The one exception is the homepage news teaser, which is capped.
    """
    src = path.read_text(encoding="utf-8")
    if path.name == "index.html" and path.parent == REPO:
        src = cap_teaser(src)

    found = find_block(src, "nav", "nav")
    if found:
        src = src[: found[0]] + nav_block(location, nav_root) + src[found[3]:]

    found = find_block(src, "footer")
    if found:
        src = src[: found[0]] + footer_block(location) + src[found[3]:]

    if 'class="skip"' not in src:
        src = src.replace("<body>\n", '<body>\n<a class="skip" href="#main">Skip to content</a>\n', 1)

    src = re.sub(
        r'<meta name="theme-color" content="[^"]*" />',
        '<meta name="theme-color" content="#1E223D" />',
        src,
    )
    if 'className+=" js"' not in src:
        src = src.replace(
            '<link rel="stylesheet" href="/assets/style.css" />',
            '<link rel="stylesheet" href="/assets/style.css" />\n'
            '<script>document.documentElement.className+=" js";</script>',
            1,
        )
    return normalise_waitlist(src)


# ---------------------------------------------------------------------- main

def blog_posts() -> list[dict]:
    """Every blog post with its publication date, oldest first."""
    posts = []
    for path in sorted((REPO / "blog").glob("*.html")):
        if path.name == "index.html":
            continue
        raw = existing_published(path.read_text(encoding="utf-8")) or ""
        day = dt.date.fromisoformat(raw[:10]) if re.match(r"^\d{4}-\d{2}-\d{2}", raw) else None
        posts.append({"path": path, "date": day, "href": "/blog/%s" % path.name})
    posts.sort(key=lambda p: (p["date"] or dt.date.min, p["path"].name))
    return posts


def recipe_hub_map() -> tuple[dict[str, list[dict]], int]:
    """recipe href -> the hubs that list it, cuisine hubs before course hubs."""
    cuisine = ("trinidadian", "nigerian")
    order = [h for h in RECIPE_HUBS if h in cuisine] + [h for h in RECIPE_HUBS if h not in cuisine]
    membership: dict[str, list[dict]] = {}
    for slug in order:
        hub = REPO / "recipes" / slug / "index.html"
        if not hub.exists():
            continue
        src = hub.read_text(encoding="utf-8")
        name = tag_text(inner(src, "header", "article-head") or src, "h1") or slug
        hrefs = []
        for href in re.findall(r'<a class="post-row" href="([^"]+)"', src):
            if href not in hrefs:
                hrefs.append(href)
        entry = {"href": "/recipes/%s/" % slug, "name": strip_tags(name).strip(), "count": len(hrefs)}
        for href in hrefs:
            membership.setdefault(href, []).append(entry)
    total = sum(
        1 for path in (REPO / "recipes").glob("*/index.html") if path.parent.name not in RECIPE_HUBS
    )
    return membership, total


def build(check: bool, today: dt.date) -> int:
    changed = []

    def emit(path: pathlib.Path, text: str):
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            return
        changed.append(path.relative_to(REPO).as_posix())
        if not check:
            path.write_text(text, encoding="utf-8")

    news_index_rows = read_index_rows(REPO / "news" / "index.html")
    editions = news_editions()
    by_href = {e["href"]: e for e in editions}

    def row_for(edition):
        row = news_index_rows.get(edition["href"])
        if row:
            return dict(row, date=short_date(edition["date"]))
        src = edition["path"].read_text(encoding="utf-8")
        return {
            "href": edition["href"],
            "date": short_date(edition["date"]),
            "title": title_body(tag_text(src, "title") or "")
            or meta_content(src, "property", "og:title") or "",
            "dek": meta_content(src, "name", "description") or "",
        }

    newest_first = list(reversed(editions))

    # ---- news editions
    for position, edition in enumerate(editions):
        prev_e = editions[position - 1] if position > 0 else None
        next_e = editions[position + 1] if position + 1 < len(editions) else None
        pager = {
            "prev": row_for(prev_e) if prev_e else None,
            "next": row_for(next_e) if next_e else None,
        }
        skip = {edition["href"]}
        if prev_e:
            skip.add(prev_e["href"])
        if next_e:
            skip.add(next_e["href"])
        picks = [e for e in newest_first if e["href"] not in skip][:3]
        rows = block_text("".join(post_row(row_for(e), e["iso"]) for e in picks))
        emit(
            edition["path"],
            render_article(
                edition["path"],
                "news",
                {
                    "crumb": ("News desk", "/news/"),
                    "edition": edition,
                    "pager": pager,
                    "related_rows": rows,
                    "related_heading": "Latest from the desk",
                    "today": today,
                },
            ),
        )

    # ---- blog posts: the same tail as a news edition. A pager both ways, then
    # the curated Related rows where a human picked them, else the newest three.
    blog_index_rows = read_index_rows(REPO / "blog" / "index.html")
    posts = blog_posts()

    def blog_row(post, full_date=False):
        row = blog_index_rows.get(post["href"])
        if row:
            row = dict(row)
        else:
            src = post["path"].read_text(encoding="utf-8")
            row = {
                "href": post["href"],
                "date": "%s %d" % (SHORT_MONTHS[post["date"].month - 1], post["date"].year)
                if post["date"] else "",
                "title": title_body(tag_text(src, "title") or ""),
                "dek": meta_content(src, "name", "description") or "",
            }
        if full_date and post["date"]:
            row["date"] = short_date(post["date"])
        return row

    newest_posts = list(reversed(posts))
    for position, post in enumerate(posts):
        prev_p = posts[position - 1] if position > 0 else None
        next_p = posts[position + 1] if position + 1 < len(posts) else None
        skip = {post["href"]} | {p["href"] for p in (prev_p, next_p) if p}
        picks = [p for p in newest_posts if p["href"] not in skip][:3]
        fallback = block_text(
            "".join(post_row(blog_row(p), p["date"].isoformat() if p["date"] else None) for p in picks)
        )
        emit(
            post["path"],
            render_article(
                post["path"],
                "blog",
                {
                    "crumb": ("Field notes", "/blog/"),
                    "pager": {
                        "prev": blog_row(prev_p, True) if prev_p else None,
                        "next": blog_row(next_p, True) if next_p else None,
                    },
                    "related_rows": None,
                    "related_heading": "Related",
                    "fallback_rows": fallback,
                    "fallback_heading": "Latest field notes",
                    "today": today,
                },
            ),
        )

    # ---- answers
    for path in sorted((REPO / "answers").glob("*/index.html")):
        emit(
            path,
            render_article(
                path,
                "answers",
                {
                    "crumb": ("Answers", "/answers/"),
                    "related_rows": None,
                    "related_heading": "Related",
                    "today": today,
                },
            ),
        )

    # ---- recipes
    membership, recipe_total = recipe_hub_map()
    if not (REPO / "assets" / "og" / "recipes.png").exists():
        warn(
            "missing share card",
            "assets/og/recipes.png is referenced by recipe pages without a photo but is not on disk",
        )
    for path in sorted((REPO / "recipes").glob("*/index.html")):
        if path.parent.name in RECIPE_HUBS:
            continue
        emit(
            path,
            render_article(
                path,
                "recipes",
                {
                    "crumb": ("Recipes", "/recipes/"),
                    "related_rows": None,
                    "related_heading": "Related recipes",
                    "recipe_hubs": membership.get("/recipes/%s/" % path.parent.name, []),
                    "recipe_total": recipe_total,
                    "today": today,
                },
            ),
        )

    # ---- hubs
    emit(REPO / "news" / "index.html", render_hub(REPO / "news" / "index.html", "news", ("News desk", "/news/")))
    emit(REPO / "blog" / "index.html", render_hub(REPO / "blog" / "index.html", "blog", ("Field notes", "/blog/")))
    emit(REPO / "answers" / "index.html", render_hub(REPO / "answers" / "index.html", "answers", ("Answers", "/answers/")))
    if (REPO / "recipes" / "index.html").exists():
        emit(REPO / "recipes" / "index.html", render_hub(REPO / "recipes" / "index.html", "recipes", ("Recipes", "/recipes/")))
    for slug in RECIPE_HUBS:
        hub = REPO / "recipes" / slug / "index.html"
        if hub.exists():
            emit(hub, render_hub(hub, "recipes", ("Recipes", "/recipes/")))

    # ---- prose page and bespoke pages
    emit(REPO / "privacy.html", render_doc(REPO / "privacy.html", "privacy"))
    emit(REPO / "index.html", shell_pass(REPO / "index.html", "home", "" ))
    if (REPO / "404.html").exists():
        latest = block_text("".join(post_row(row_for(e), e["iso"]) for e in newest_first[:3]))
        emit(REPO / "404.html", render_404(REPO / "404.html", latest))

    print(("would rewrite " if check else "rewrote ") + "%d page(s)" % len(changed))
    for name in changed:
        print("  " + name)

    for kind, lines in WARNINGS.items():
        print("warning: %d %s" % (len(lines), kind), file=sys.stderr)
        for line in lines:
            print("  " + line, file=sys.stderr)
    if GATE_FAILURES:
        label = "gate failed" if check else "gate (enforced by --check)"
        print("%s: %d" % (label, len(GATE_FAILURES)), file=sys.stderr)
        for line in GATE_FAILURES:
            print("  " + line, file=sys.stderr)

    if check and (changed or GATE_FAILURES):
        return 1
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    parser.add_argument(
        "--today",
        type=dt.date.fromisoformat,
        default=None,
        help="date the news gate treats as today (YYYY-MM-DD, default: today in Montreal)",
    )
    args = parser.parse_args()
    sys.exit(build(args.check, args.today or sitelib.montreal_today()))
