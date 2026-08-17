#!/usr/bin/env python3
"""
seo_audit.py — daily SEO/AEO diagnostic + safe-fix pass for josephbankole.ca

Built for the Perplexity-hosted "JB Site Desk" scheduled task (v1, Lane C only).
Mirrors the SAFE / JUDGEMENT split from fifa.archv/routines-v2/josephbankole-site-desk.md
STEP 3, scoped to what a deterministic script can do responsibly:

SAFE (applied automatically):
  - insert a missing <link rel="canonical"> using the page's known site-relative path
  - insert a missing <meta property="og:url"> using the same canonical URL

JUDGEMENT (reported only, never auto-applied):
  - title length outside ~50-60 chars, or not unique across the site
  - meta description length outside ~140-160 chars, or not unique
  - missing alt text on <img>
  - JSON-LD present but fails to parse, or missing datePublished/dateModified
  - internal links pointing at a path with no matching file in the repo
  - pages present on disk but absent from sitemap.xml (or vice versa)

Never touches: page prose, headings, JSON-LD content, feed.xml, news-feed.xml,
llms.txt, or anything under news/ (that lane belongs to a different desk).

Usage:
  python3 tools/seo_audit.py            # scan + apply safe fixes, print JSON report
  python3 tools/seo_audit.py --dry-run  # scan only, no writes
"""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_BASE = "https://josephbankole.ca"
SKIP_DIRS = {".git", "tools", "node_modules", "news"}  # news/ prose is not ours
DRY_RUN = "--dry-run" in sys.argv

TITLE_RE = re.compile(r"<title>(.*?)</title>", re.S | re.I)
DESC_RE = re.compile(r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']', re.S | re.I)
CANON_RE = re.compile(r'<link\s+rel=["\']canonical["\']\s+href=["\'](.*?)["\']', re.S | re.I)
OGURL_RE = re.compile(r'<meta\s+property=["\']og:url["\']\s+content=["\'](.*?)["\']', re.S | re.I)
IMG_RE = re.compile(r"<img\b([^>]*)>", re.I)
ALT_RE = re.compile(r'alt=["\'](.*?)["\']', re.I)
JSONLD_RE = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)
HEAD_CLOSE_RE = re.compile(r"</head>", re.I)
LINK_RE = re.compile(r'href=["\'](/[^"\'#?]*)', re.I)


def site_pages():
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        rel_dir = Path(dirpath).relative_to(REPO_ROOT)
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if rel_dir.parts and rel_dir.parts[0] in SKIP_DIRS:
            continue
        for fn in filenames:
            if fn == "index.html" or (fn.endswith(".html") and "index" not in filenames):
                yield Path(dirpath) / fn


def url_path_for(page: Path) -> str:
    rel = page.relative_to(REPO_ROOT)
    if rel.name == "index.html":
        rel = rel.parent
        p = "/" + str(rel).replace(os.sep, "/")
        if p == "/.":
            p = "/"
        if not p.endswith("/"):
            p += "/"
        return p
    # standalone .html file (e.g. 404.html, blog/foo.html): no trailing slash
    return "/" + str(rel).replace(os.sep, "/")


def load_sitemap_urls():
    sm = REPO_ROOT / "sitemap.xml"
    if not sm.exists():
        return set()
    try:
        tree = ET.parse(sm)
        ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        return {loc.text.strip() for loc in tree.iter() if loc.tag.endswith("loc") and loc.text}
    except ET.ParseError:
        return set()


def main():
    report = {
        "pages_checked": 0,
        "safe_fixes_applied": [],
        "judgement_findings": [],
    }
    titles, descs = {}, {}
    all_files = set()

    pages = list(site_pages())
    report["pages_checked"] = len(pages)

    for page in pages:
        rel = str(page.relative_to(REPO_ROOT))
        all_files.add(url_path_for(page))
        try:
            html = page.read_text(encoding="utf-8")
        except Exception as e:
            report["judgement_findings"].append(f"{rel}: could not read file ({e})")
            continue

        canonical_url = SITE_BASE + url_path_for(page)

        # --- title ---
        m = TITLE_RE.search(html)
        title = m.group(1).strip() if m else None
        if not title:
            report["judgement_findings"].append(f"{rel}: missing <title>")
        else:
            if not (50 <= len(title) <= 60):
                report["judgement_findings"].append(
                    f"{rel}: title length {len(title)} chars (target 50-60): \"{title}\""
                )
            titles.setdefault(title, []).append(rel)

        # --- meta description ---
        m = DESC_RE.search(html)
        desc = m.group(1).strip() if m else None
        if not desc:
            report["judgement_findings"].append(f"{rel}: missing meta description")
        else:
            if not (140 <= len(desc) <= 160):
                report["judgement_findings"].append(
                    f"{rel}: meta description length {len(desc)} chars (target 140-160)"
                )
            descs.setdefault(desc, []).append(rel)

        # --- canonical (SAFE fix if missing) ---
        m = CANON_RE.search(html)
        if not m:
            if DRY_RUN:
                report["judgement_findings"].append(f"{rel}: missing canonical (would insert {canonical_url})")
            else:
                new_tag = f'<link rel="canonical" href="{canonical_url}">\n'
                html2 = HEAD_CLOSE_RE.sub(new_tag + "</head>", html, count=1)
                if html2 != html:
                    page.write_text(html2, encoding="utf-8")
                    html = html2
                    report["safe_fixes_applied"].append(f"{rel}: inserted canonical -> {canonical_url}")

        # --- og:url (SAFE fix if missing) ---
        m = OGURL_RE.search(html)
        if not m:
            if DRY_RUN:
                report["judgement_findings"].append(f"{rel}: missing og:url (would insert {canonical_url})")
            else:
                new_tag = f'<meta property="og:url" content="{canonical_url}">\n'
                html2 = HEAD_CLOSE_RE.sub(new_tag + "</head>", html, count=1)
                if html2 != html:
                    page.write_text(html2, encoding="utf-8")
                    html = html2
                    report["safe_fixes_applied"].append(f"{rel}: inserted og:url -> {canonical_url}")

        # --- alt text ---
        for img_tag in IMG_RE.findall(html):
            if not ALT_RE.search(img_tag):
                report["judgement_findings"].append(f"{rel}: <img> missing alt text ({img_tag[:60]})")

        # --- JSON-LD sanity ---
        for block in JSONLD_RE.findall(html):
            try:
                data = json.loads(block)
            except json.JSONDecodeError as e:
                report["judgement_findings"].append(f"{rel}: JSON-LD parse error ({e})")
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") in ("Article", "BlogPosting", "FAQPage"):
                    if not item.get("datePublished"):
                        report["judgement_findings"].append(f"{rel}: JSON-LD missing datePublished")
                    if not item.get("dateModified"):
                        report["judgement_findings"].append(f"{rel}: JSON-LD missing dateModified")

        # --- internal links point somewhere real ---
        for href in LINK_RE.findall(html):
            target = href.split("?")[0].split("#")[0]
            if not target.endswith("/") and "." not in Path(target).name:
                target += "/"
            candidate_dir = REPO_ROOT / target.lstrip("/")
            candidate_file = REPO_ROOT / href.lstrip("/")
            if not (candidate_dir / "index.html").exists() and not candidate_file.exists():
                report["judgement_findings"].append(f"{rel}: internal link to missing path {href}")

    # duplicate titles/descriptions across pages
    for t, files in titles.items():
        if len(files) > 1:
            report["judgement_findings"].append(f"duplicate title \"{t}\" on: {', '.join(files)}")
    for d, files in descs.items():
        if len(files) > 1:
            report["judgement_findings"].append(f"duplicate meta description on: {', '.join(files)}")

    # sitemap coverage
    sitemap_urls = load_sitemap_urls()
    sitemap_paths = {u.replace(SITE_BASE, "") or "/" for u in sitemap_urls}
    missing_from_sitemap = sorted(p for p in (all_files - sitemap_paths) if not p.startswith("/news/"))
    missing_from_repo = sorted(
        p for p in (sitemap_paths - all_files)
        if not p.startswith("/news/") and not (REPO_ROOT / p.lstrip("/") / "index.html").exists()
        and not (REPO_ROOT / p.lstrip("/")).exists()
    )
    if missing_from_sitemap:
        report["judgement_findings"].append(f"pages on disk but not in sitemap.xml: {missing_from_sitemap}")
    if missing_from_repo:
        report["judgement_findings"].append(f"sitemap.xml URLs with no matching page on disk: {missing_from_repo}")

    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    main()
