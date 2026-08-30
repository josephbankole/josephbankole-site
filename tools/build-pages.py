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
    python3 tools/build-pages.py --check    # fail if anything would change

Run tools/build-news-feed.py afterwards if you added an edition.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
SITE = "https://josephbankole.ca"

TZ = "-04:00"  # Montreal, August

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
    return re.sub(
        r"mailto:partnerships@josephbankole\.ca\?subject=Waitlist(?:%20|&amp;|[^\"'\s])*",
        WAITLIST.replace("&", "&amp;"),
        doc,
    )


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
    lines += [
        '<meta name="twitter:image" content="%s" />' % page["og_image"],
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


def parse_common(path: pathlib.Path, src: str) -> dict:
    canonical = link_href(src, "canonical")
    title = tag_text(src, "title") or ""
    og_image = meta_content(src, "property", "og:image") or ""
    # 26 news pages pointed at a per-edition card that was never rendered.
    if og_image.startswith(SITE):
        on_disk = REPO / og_image[len(SITE) + 1:]
        if not on_disk.exists():
            og_image = "%s/assets/og/default.png" % SITE
    if not og_image:
        og_image = "%s/assets/og/default.png" % SITE
    return {
        "path": path,
        "title": title,
        "description": meta_content(src, "name", "description"),
        "canonical": canonical,
        "og_title": meta_content(src, "property", "og:title") or title,
        "og_description": meta_content(src, "property", "og:description")
        or meta_content(src, "name", "description"),
        "og_image": og_image,
        "og_type": meta_content(src, "property", "og:type") or "website",
    }


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
    prose = promote_headings(block_text(inner(src, "div", "prose")) or "")

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
    if kind == "news":
        edition = ctx["edition"]
        date_attr = edition["iso"]
        date_display = human_date(edition["date"])
        published_iso = "%sT08:00:00%s" % (edition["iso"], TZ)
    else:
        raw = existing_published(src)
        if raw and re.match(r"^\d{4}-\d{2}-\d{2}", raw):
            date_attr = raw[:10]
            day = dt.date.fromisoformat(date_attr)
            date_display = human_date(day)
            published_iso = "%sT09:00:00%s" % (date_attr, TZ)

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
        modified = "%sT09:00:00%s" % (modified, TZ)

    page["published_iso"] = published_iso
    page["modified_iso"] = modified
    page["location"] = location
    page["og_type"] = "article"

    # ---- schema
    if kind in ("answers", "recipes"):
        # The answers @graph (DefinedTerm + FAQPage + BreadcrumbList) is the
        # best-built schema on the site. It is lifted through untouched.
        # Recipes joined it 2026-08-30: their @graph carries Article +
        # BreadcrumbList + FAQPage, generated per page, and rebuilding it here
        # would silently drop the FAQPage node.
        existing = re.search(
            r'<script type="application/ld\+json">\s*(.*?)\s*</script>', src, re.S
        )
        page["jsonld"] = existing.group(1) if existing else ""
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

    # ---- pager (news only): the desk now reads in both directions
    if kind == "news":
        pager = ctx["pager"]
        if pager["prev"] or pager["next"]:
            parts.append('  <nav class="pager" aria-label="Neighbouring editions">')
            if pager["prev"]:
                parts.append(
                    '    <a class="pager-prev" href="%s"><span class="pager-dir">'
                    "&larr; Earlier edition</span><span class=\"pager-ttl\">%s</span>"
                    '<span class="pager-date">%s</span></a>'
                    % (pager["prev"]["href"], pager["prev"]["title"], pager["prev"]["date"])
                )
            if pager["next"]:
                parts.append(
                    '    <a class="pager-next" href="%s"><span class="pager-dir">'
                    "Later edition &rarr;</span><span class=\"pager-ttl\">%s</span>"
                    '<span class="pager-date">%s</span></a>'
                    % (pager["next"]["href"], pager["next"]["title"], pager["next"]["date"])
                )
            parts.append("  </nav>")

    # ---- related
    related_rows = ctx.get("related_rows")
    if related_rows is None:
        block = inner(src, "div", "related") or inner(src, "section", "related")
        related_rows = inner(block or "", "div", "postlist")
        if related_rows:
            related_rows = block_text(related_rows)
    if related_rows:
        parts.append('  <section class="related" aria-labelledby="related-h">')
        parts.append('    <h2 id="related-h">%s</h2>' % ctx["related_heading"])
        parts.append('    <div class="postlist">')
        parts.append(related_rows)
        parts.append("    </div>")
        parts.append("  </section>")

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
                "author": {"@id": "%s/#person" % SITE},
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


def shell_pass(path: pathlib.Path, location: str, nav_root: str = "/") -> str:
    """Swap the nav and footer on a bespoke page without touching its body."""
    src = path.read_text(encoding="utf-8")

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

def build(check: bool) -> int:
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
            "title": meta_content(src, "property", "og:title") or "",
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
                },
            ),
        )

    # ---- blog posts
    for path in sorted((REPO / "blog").glob("*.html")):
        if path.name == "index.html":
            continue
        emit(
            path,
            render_article(
                path,
                "blog",
                {
                    "crumb": ("Field notes", "/blog/"),
                    "related_rows": None,
                    "related_heading": "Related",
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
                },
            ),
        )

    # ---- recipes
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

    print(("would rewrite " if check else "rewrote ") + "%d page(s)" % len(changed))
    for name in changed:
        print("  " + name)
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args()
    sys.exit(build(args.check))
