#!/usr/bin/env python3
"""Rebuild /feed.xml from the posts in /blog.

Why this exists: build-news-feed.py owns news-feed.xml, but nothing owned
feed.xml, the blog feed. It was hand-written and every new essay meant
hand-copying an <item> and getting the RFC-822 pubDate right by eye. That is
the same drift that let 25 news editions fall out of news-feed.xml before its
generator was written.

Every item is derived from its page. Until 2026-09-22 an item already in the
feed kept its hand-written pubDate and description verbatim, which is how the
Xcode 27 post came to say 19:12 GMT while its page said 09:00 Montreal (13:00
GMT). Most readers deduplicate on <guid>, which does not change, so fixing a
pubDate does not re-deliver a post. pubDate is now the page's own
article:published_time converted to GMT, <description> is the page's meta
description, and content:encoded carries the full post. Only the channel
description comes from elsewhere, blog/index.html, so the hub and the feed
cannot drift apart.

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

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import sitelib  # noqa: E402  (shared clock and block finder, tools/sitelib.py)

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

TITLE_SUFFIX = " · Joseph Bankole"
CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"


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
    return sitelib.rfc822(moment)


def read_post(path: pathlib.Path) -> dict | None:
    url = f"{SITE}/blog/{path.name}"
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
        published_match = PUBLISHED_RE.search(source)
        published = sitelib.parse_iso(published_match.group(1)) if published_match else None
    if published is None:
        raise SystemExit(
            f"{label(path)} carries no article:published_time and no datePublished with an offset.\n"
            "Add one. This script will not invent a date for it."
        )

    content = sitelib.article_html(source)
    if content is None:
        print(f"  no prose block, feed item has no content:encoded: {path.name}", file=sys.stderr)

    return {
        "url": url,
        "title": title,
        "description": unescape(desc_match.group(1)),
        "published": published,
        "content": content,
    }


def channel_description() -> str:
    """Kept in sync with the blog hub so the two cannot drift."""
    match = DESC_RE.search(HUB.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit("blog/index.html carries no meta description")
    return unescape(match.group(1))


def build() -> int:
    posts = []
    for path in sorted(BLOG_DIR.glob("*.html")):
        if path.name == "index.html":
            continue
        post = read_post(path)
        if post:
            posts.append(post)
    if not posts:
        raise SystemExit("no posts found in blog/. Refusing to write an empty feed.")

    posts.sort(key=lambda item: (item["published"], item["url"]), reverse=True)

    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:content="{CONTENT_NS}">',
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
        ]
        if post["content"]:
            lines.append(f"    <content:encoded>{sitelib.cdata(post['content'])}</content:encoded>")
        lines.append("  </item>")
    lines += ["</channel>", "</rss>", ""]

    FEED_PATH.write_text("\n".join(lines), encoding="utf-8")
    return len(posts)


if __name__ == "__main__":
    count = build()
    print(f"feed.xml rebuilt: {count} posts")
