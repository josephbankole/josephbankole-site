#!/usr/bin/env python3
"""Rebuild /news-feed.xml from the pages in /news.

Why this exists: news-feed.xml was written once, by hand, in commit 1f94d3f
(2026-07-14) and never again. The daily publishing routine touches the edition
page, news/index.html, the homepage teaser and sitemap.xml, but not the feed,
so 25 consecutive editions (2026-07-15 to 2026-08-08) never entered it. This
script derives the whole feed from the pages themselves, so the feed can never
drift from what is published.

Run it after adding an edition, and after tools/build-pages.py, from the repo
root:

    python3 tools/build-news-feed.py

It rewrites news-feed.xml in place and prints the item count.

Two fixes from the 2026-09-22 review:
  - pubDate is the page's own article:published_time converted to GMT. It used
    to write 08:00 Montreal time as if it were 08:00 GMT, four hours early on
    every item.
  - Each item carries the full edition in content:encoded (the prose and the
    sources list), so <description> can stay a short summary without shrinking
    what subscribers read.
"""

from __future__ import annotations

import datetime as dt
import html
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sitelib  # noqa: E402  (shared clock and block finder, tools/sitelib.py)

REPO = pathlib.Path(__file__).resolve().parent.parent
NEWS_DIR = REPO / "news"
FEED_PATH = REPO / "news-feed.xml"

SITE = "https://josephbankole.ca"
CHANNEL_TITLE = "Joseph Bankole's news desk"
CHANNEL_LINK = f"{SITE}/news/"
CHANNEL_DESC = (
    "A running digest of payments, agentic commerce, and the AI stories that "
    "touch how money moves. Sourced, edited, and written plainly, by Joseph Bankole."
)

# news/2026-08-08-agentic-commerce.html
FILENAME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-.+\.html$")
OG_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]*)"')
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"')

TITLE_SUFFIX = " · Joseph Bankole"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


def unescape(value: str) -> str:
    return html.unescape(value).strip()


def esc(value: str) -> str:
    """Escape for XML text content."""
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def read_edition(path: pathlib.Path) -> dict | None:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None
    year, month, day = (int(part) for part in match.groups())
    source = path.read_text(encoding="utf-8")

    title_match = OG_TITLE_RE.search(source) or TITLE_RE.search(source)
    if not title_match:
        print(f"  skipped (no title): {path.name}", file=sys.stderr)
        return None
    title = unescape(title_match.group(1))
    if title.endswith(TITLE_SUFFIX):
        title = title[: -len(TITLE_SUFFIX)].strip()

    desc_match = DESC_RE.search(source)
    if not desc_match:
        print(f"  skipped (no description): {path.name}", file=sys.stderr)
        return None

    stamp = sitelib.meta_property(source, "article:published_time")
    published = sitelib.parse_iso(stamp) if stamp else None
    if published is None:
        # No stamp on the page yet: 08:00 in Montreal, the desk's publish time.
        published = sitelib.parse_iso(sitelib.local_iso(dt.date(year, month, day), 8))
        print(f"  no article:published_time, used 08:00 Montreal: {path.name}", file=sys.stderr)

    content = sitelib.article_html(source)
    if content is None:
        print(f"  no prose block, feed item has no content:encoded: {path.name}", file=sys.stderr)

    return {
        "url": f"{SITE}/news/{path.name}",
        "title": title,
        "description": unescape(desc_match.group(1)),
        "published": published,
        "content": content,
    }


def rfc822(moment: dt.datetime) -> str:
    return sitelib.rfc822(moment)


def build() -> int:
    editions = []
    for path in sorted(NEWS_DIR.glob("*.html")):
        edition = read_edition(path)
        if edition:
            editions.append(edition)
    if not editions:
        raise SystemExit("no editions found in news/ — refusing to write an empty feed")

    editions.sort(key=lambda item: item["published"], reverse=True)
    last_build = editions[0]["published"]

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="{CONTENT_NS}">',
        "<channel>",
        f"  <title>{esc(CHANNEL_TITLE)}</title>",
        f"  <link>{CHANNEL_LINK}</link>",
        f"  <description>{esc(CHANNEL_DESC)}</description>",
        "  <language>en</language>",
        f"  <lastBuildDate>{rfc822(last_build)}</lastBuildDate>",
        f'  <atom:link href="{SITE}/news-feed.xml" rel="self" type="application/rss+xml" />',
    ]
    for edition in editions:
        lines += [
            "  <item>",
            f"    <title>{esc(edition['title'])}</title>",
            f"    <link>{edition['url']}</link>",
            f"    <guid>{edition['url']}</guid>",
            f"    <pubDate>{rfc822(edition['published'])}</pubDate>",
            f"    <description>{esc(edition['description'])}</description>",
        ]
        if edition["content"]:
            lines.append(f"    <content:encoded>{sitelib.cdata(edition['content'])}</content:encoded>")
        lines.append("  </item>")
    lines += ["</channel>", "</rss>", ""]

    FEED_PATH.write_text("\n".join(lines), encoding="utf-8")
    return len(editions)


if __name__ == "__main__":
    count = build()
    print(f"news-feed.xml rebuilt: {count} editions")
