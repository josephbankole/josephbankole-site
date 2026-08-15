#!/usr/bin/env python3
"""Rebuild /feed.xml from the posts in /blog.

Why this exists: build-news-feed.py owns news-feed.xml, but nothing owned
feed.xml, the blog feed. It was hand-written and every new essay meant
hand-copying an <item> and getting the RFC-822 pubDate right by eye. That is
the same drift that let 25 news editions fall out of news-feed.xml before its
generator was written.

One rule makes this safe to run on a feed that already exists: an item already
in the feed keeps its published pubDate and description verbatim. Those were
written by hand, they are what subscribers already received, and rederiving
them would re-date old posts in every reader. Only posts absent from the feed
are derived from the page, and only the channel description is resynced, from
blog/index.html, so the hub and the feed cannot drift apart.

It is deterministic. lastBuildDate is taken from the newest item rather than
from the clock, so running it twice produces byte-identical output.

Run it after adding an essay, from the repo root:

    python3 tools/build-blog-feed.py

It rewrites feed.xml in place and prints the item count.
"""

from __future__ import annotations

import datetime as dt
import html
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
BLOG_DIR = REPO / "blog"
FEED_PATH = REPO / "feed.xml"
HUB = BLOG_DIR / "index.html"

SITE = "https://josephbankole.ca"
CHANNEL_TITLE = "Joseph Bankole's blog"
CHANNEL_LINK = SITE

OG_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]*)"')
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)
DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"')
PUBLISHED_RE = re.compile(r'"datePublished"\s*:\s*"([^"]+)"')

ITEM_RE = re.compile(r"<item>(.*?)</item>", re.S)
LINK_RE = re.compile(r"<link>(.*?)</link>", re.S)
PUBDATE_RE = re.compile(r"<pubDate>(.*?)</pubDate>", re.S)
ITEM_DESC_RE = re.compile(r"<description>(.*?)</description>", re.S)
ITEM_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S)

TITLE_SUFFIX = " · Joseph Bankole"


def unescape(value: str) -> str:
    return html.unescape(value).strip()


def esc(value: str) -> str:
    """Escape for XML text content."""
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def label(path: pathlib.Path) -> str:
    """Repo-relative where possible. Never raises: this is used inside errors."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def rfc822(moment: dt.datetime) -> str:
    return moment.astimezone(dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def parse_rfc822(value: str) -> dt.datetime:
    return dt.datetime.strptime(value.strip(), "%a, %d %b %Y %H:%M:%S GMT").replace(
        tzinfo=dt.timezone.utc
    )


def read_existing() -> dict[str, dict]:
    """Map url -> the item exactly as subscribers already received it."""
    if not FEED_PATH.exists():
        return {}
    source = FEED_PATH.read_text(encoding="utf-8")
    kept = {}
    for body in ITEM_RE.findall(source):
        link = LINK_RE.search(body)
        pub = PUBDATE_RE.search(body)
        desc = ITEM_DESC_RE.search(body)
        title = ITEM_TITLE_RE.search(body)
        if not (link and pub):
            continue
        kept[link.group(1).strip()] = {
            "title": unescape(title.group(1)) if title else "",
            "description": unescape(desc.group(1)) if desc else "",
            "published": parse_rfc822(pub.group(1)),
        }
    return kept


def read_post(path: pathlib.Path, existing: dict[str, dict]) -> dict | None:
    url = f"{SITE}/blog/{path.name}"
    source = path.read_text(encoding="utf-8")

    title_match = OG_TITLE_RE.search(source) or TITLE_RE.search(source)
    if not title_match:
        print(f"  skipped (no title): {path.name}", file=sys.stderr)
        return None
    title = unescape(title_match.group(1))
    if title.endswith(TITLE_SUFFIX):
        title = title[: -len(TITLE_SUFFIX)].strip()

    was = existing.get(url)
    if was:
        # Already published to subscribers. Its pubDate and description stand.
        return {
            "url": url,
            "title": was["title"] or title,
            "description": was["description"],
            "published": was["published"],
        }

    desc_match = DESC_RE.search(source)
    if not desc_match:
        print(f"  skipped (no description): {path.name}", file=sys.stderr)
        return None
    published_match = PUBLISHED_RE.search(source)
    if not published_match:
        raise SystemExit(
            f"{label(path)} carries no datePublished in its JSON-LD.\n"
            "Add one. This script will not invent a date for it."
        )
    return {
        "url": url,
        "title": title,
        "description": unescape(desc_match.group(1)),
        "published": dt.datetime.fromisoformat(published_match.group(1)),
    }


def channel_description() -> str:
    """Kept in sync with the blog hub so the two cannot drift."""
    match = DESC_RE.search(HUB.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit("blog/index.html carries no meta description")
    return unescape(match.group(1))


def build() -> int:
    existing = read_existing()
    posts = []
    for path in sorted(BLOG_DIR.glob("*.html")):
        if path.name == "index.html":
            continue
        post = read_post(path, existing)
        if post:
            posts.append(post)
    if not posts:
        raise SystemExit("no posts found in blog/. Refusing to write an empty feed.")

    posts.sort(key=lambda item: item["published"], reverse=True)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        f"  <title>{esc(CHANNEL_TITLE)}</title>",
        f"  <link>{CHANNEL_LINK}</link>",
        f"  <description>{esc(channel_description())}</description>",
        "  <language>en</language>",
        f"  <lastBuildDate>{rfc822(posts[0]['published'])}</lastBuildDate>",
        f'  <atom:link href="{SITE}/feed.xml" rel="self" type="application/rss+xml" />',
    ]
    for post in posts:
        lines += [
            "  <item>",
            f"    <title>{esc(post['title'])}</title>",
            f"    <link>{post['url']}</link>",
            f"    <guid>{post['url']}</guid>",
            f"    <pubDate>{rfc822(post['published'])}</pubDate>",
            f"    <description>{esc(post['description'])}</description>",
            "  </item>",
        ]
    lines += ["</channel>", "</rss>", ""]

    FEED_PATH.write_text("\n".join(lines), encoding="utf-8")
    return len(posts)


if __name__ == "__main__":
    count = build()
    print(f"feed.xml rebuilt: {count} posts")
