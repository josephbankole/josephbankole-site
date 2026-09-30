"""Helpers shared by build-pages.py and the two feed builders.

Why this exists: the page builder and the feeds each carried their own idea of
what time a page was published. The page said 08:00 in Montreal with a
hard-coded -04:00, and the news feed wrote the same 08:00 as if it were GMT, so
every feed item landed four hours early. From November the hard-coded offset
would have been wrong on the pages as well. One clock, read from the time zone
database, now serves all three scripts.

It also holds the block finder the builder already used, so the feeds can lift
the same article HTML the page carries into content:encoded.
"""

from __future__ import annotations

import datetime as dt
import html
import re
import urllib.parse

SITE = "https://josephbankole.ca"
SITE_HOSTS = {"josephbankole.ca", "www.josephbankole.ca"}

# ------------------------------------------------------------ shared limits
#
# One definition for build-pages.py and seo_audit.py, so the gate and the
# audit cannot drift apart again (they did: the gate measured the title before
# the " · Joseph Bankole" suffix while the audit measured all of it). The rule,
# from the desk specs since 2026-09-22: the WHOLE <title> is 60 characters or
# fewer, as a reader sees it (entities decoded), and the site-name suffix goes
# on only when it still fits. The meta description is 155 or fewer and ends on
# a full sentence.
TITLE_MAX = 60
DESC_MAX = 155
TITLE_SUFFIX_RE = re.compile(r"\s*(?:·|&middot;|&#183;|&#xB7;)\s*Joseph Bankole\s*$")
FULL_SENTENCE_RE = re.compile(r"[.?!][\"'’”)]?$")


def text_len(value: str) -> int:
    """Length as a reader or a search result sees it: tags gone, entities decoded."""
    return len(html.unescape(re.sub(r"<[^>]+>", "", value)).strip())


def title_body(title: str) -> str:
    """The <title> without the site-name suffix, still HTML-escaped."""
    return TITLE_SUFFIX_RE.sub("", title).strip()


def ends_full_sentence(desc: str) -> bool:
    return bool(FULL_SENTENCE_RE.search(html.unescape(desc).strip()))


# ------------------------------------------------------ links into recipes/

HREF_RE = re.compile(r"""\bhref\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>"']+))""", re.I)


def recipe_links(rel: str, text: str) -> list[str]:
    """Every href in `text` that resolves to a /recipes/ URL on this site.

    `rel` is the page's path relative to the site root, so a relative href
    ("recipes/", "../recipes/x/", "./recipes/") is resolved the way a browser
    would resolve it. Protocol-relative, dot-segment and unquoted hrefs are
    caught too. The old gate only matched hrefs starting "/recipes" or the
    absolute URL, so all of those slipped past it. A path is flagged only when
    it is exactly /recipes or sits under /recipes/, so a future
    /recipes-archive/ is not.
    """
    base = "%s/%s" % (SITE, rel.lstrip("/"))
    hits = []
    for match in HREF_RE.finditer(text):
        href = html.unescape(next(g for g in match.groups() if g is not None)).strip()
        if not href:
            continue
        parts = urllib.parse.urlsplit(urllib.parse.urljoin(base, href))
        if parts.scheme not in ("http", "https", ""):
            continue
        if parts.netloc.lower() not in SITE_HOSTS:
            continue
        path = parts.path
        if path == "/recipes" or path.startswith("/recipes/"):
            hits.append(href)
    return hits


def robots_blocks_recipes(robots_txt: str) -> list[str]:
    """Disallow patterns in robots.txt that would stop a crawler reading /recipes/.

    Recipes carry noindex,follow, and a crawler only reads the noindex if it
    may fetch the page, so a block in robots.txt would leave them indexable
    from inbound links. Any user-agent group counts: the order is "never
    blocked". A bare "Disallow:" means allow all and is skipped.
    """
    blocked = []
    for line in robots_txt.splitlines():
        line = line.split("#", 1)[0].strip()
        match = re.match(r"(?i)^disallow\s*:\s*(\S*)", line)
        if not match or not match.group(1):
            continue
        pattern = match.group(1)
        anchored = pattern.endswith("$")
        body = pattern[:-1] if anchored else pattern
        regex = "".join(".*" if ch == "*" else re.escape(ch) for ch in body)
        if re.match(regex + ("$" if anchored else ""), "/recipes/"):
            blocked.append(pattern)
    return blocked

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        MONTREAL = ZoneInfo("America/Toronto")
    except ZoneInfoNotFoundError:  # no tz database on this machine
        MONTREAL = None
except ImportError:  # pragma: no cover - Python older than 3.9
    MONTREAL = None


def _nth_sunday(year: int, month: int, nth: int) -> dt.date:
    first = dt.date(year, month, 1)
    offset = (6 - first.weekday()) % 7
    return first + dt.timedelta(days=offset + 7 * (nth - 1))


def utc_offset(day: dt.date, hour: int = 8, minute: int = 0) -> dt.timedelta:
    """Montreal's offset from UTC at a given local wall-clock time."""
    if MONTREAL is not None:
        local = dt.datetime(day.year, day.month, day.day, hour, minute, tzinfo=MONTREAL)
        return local.utcoffset()
    # Fallback: the North American rule since 2007, second Sunday of March to
    # first Sunday of November, both switching at 02:00 local.
    start = dt.datetime.combine(_nth_sunday(day.year, 3, 2), dt.time(2))
    end = dt.datetime.combine(_nth_sunday(day.year, 11, 1), dt.time(2))
    moment = dt.datetime(day.year, day.month, day.day, hour, minute)
    return dt.timedelta(hours=-4) if start <= moment < end else dt.timedelta(hours=-5)


def offset_label(delta: dt.timedelta) -> str:
    minutes = int(delta.total_seconds() // 60)
    sign = "-" if minutes < 0 else "+"
    minutes = abs(minutes)
    return "%s%02d:%02d" % (sign, minutes // 60, minutes % 60)


def local_iso(day: dt.date, hour: int, minute: int = 0) -> str:
    """2026-11-04 at 08:00 in Montreal -> 2026-11-04T08:00:00-05:00."""
    return "%04d-%02d-%02dT%02d:%02d:00%s" % (
        day.year, day.month, day.day, hour, minute,
        offset_label(utc_offset(day, hour, minute)),
    )


def montreal_today() -> dt.date:
    now = dt.datetime.now(dt.timezone.utc)
    if MONTREAL is not None:
        return now.astimezone(MONTREAL).date()
    return (now + utc_offset(now.date(), now.hour)).date()


def parse_iso(value: str) -> dt.datetime | None:
    """An ISO 8601 timestamp with an offset, as article:published_time carries."""
    try:
        moment = dt.datetime.fromisoformat(value.strip())
    except ValueError:
        return None
    if moment.tzinfo is None:
        return None
    return moment


def rfc822(moment: dt.datetime) -> str:
    """RSS pubDate, always converted to GMT first."""
    return moment.astimezone(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


# ------------------------------------------------------------- page reading

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


def meta_property(src: str, name: str) -> str | None:
    match = re.search(r'<meta\s+property="%s"\s+content="([^"]*)"' % re.escape(name), src)
    return match.group(1) if match else None


def absolutise(fragment: str) -> str:
    """Site-relative href and src become absolute, so they work in a reader."""
    return re.sub(r'(\s(?:href|src))="/(?!/)', r'\1="%s/' % SITE, fragment)


def article_html(src: str) -> str | None:
    """The article as a reader should get it: the prose, then the sources.

    Scripts and inline styles are dropped. Everything else is the page's own
    markup, byte for byte, with links made absolute.
    """
    prose = inner(src, "div", "prose")
    if prose is None:
        return None
    parts = [prose.strip()]
    sources = inner(src, "section", "sources") or inner(src, "div", "sources")
    if sources:
        found = find_block(sources, "ol")
        if found:
            parts.append("<h2>Sources</h2>")
            parts.append("<ol>%s</ol>" % sources[found[1]:found[2]].strip())
    body = "\n".join(parts)
    body = re.sub(r"<script\b.*?</script>", "", body, flags=re.S)
    return absolutise(body)


def cdata(value: str) -> str:
    """Wrap in CDATA, splitting any ]]> the content happens to carry."""
    return "<![CDATA[%s]]>" % value.replace("]]>", "]]]]><![CDATA[>")
