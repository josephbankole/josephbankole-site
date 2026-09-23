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
import re

SITE = "https://josephbankole.ca"

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
