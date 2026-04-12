from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlparse


TAG_LINK_PATTERN = re.compile(r'href="/tags/([^"#?]+)"', re.IGNORECASE)
TABLE_OPEN_PATTERN = re.compile(r"<table\b(?![^>]*\bdata-sortable\b)([^>]*)>", re.IGNORECASE)
HTML_URL_ATTRIBUTE_PATTERN = re.compile(
    r'(?P<prefix>\b(?:href|src)\s*=\s*)(?P<quote>["\'])(?P<url>.*?)(?P=quote)',
    re.IGNORECASE,
)
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")
SCHEMELESS_EXTERNAL_HOST_PATTERN = re.compile(
    r"^(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?::\d+)?$",
    re.IGNORECASE,
)
NON_HOST_SUFFIXES = (
    ".7z",
    ".avi",
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".htm",
    ".html",
    ".jpeg",
    ".jpg",
    ".json",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".php",
    ".png",
    ".rar",
    ".svg",
    ".txt",
    ".webm",
    ".webp",
    ".wmv",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
)
LEGACY_SECTION_ROUTE_PREFIXES = {
    "alien-photos": "/ufog/alien-photos",
    "best-ufo-cases": "/ufog/best-ufo-cases",
    "starter-pack": "/ufog/starter-pack",
    "tags": "/tags",
    "ufo": "/ufo-history/ufo",
    "ufo-books": "/ufo-history/ufo-books",
    "ufo-personalities": "/ufo-history/ufo-personalities",
    "ufo-videos": "/ufog/ufo-videos",
    "ufog": "/ufog",
}
SITE_TITLE = "Isaac Koi Archive"
SITE_SUBTITLE = "Static migration preview assembled from normalized Joomla content."


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_timestamp(value: str | None) -> datetime:
    if not value or value in {"0000-00-00 00:00:00", "0000-00-00"}:
        return datetime.min
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.min


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    cleaned = HTML_TAG_PATTERN.sub(" ", value)
    cleaned = html.unescape(cleaned)
    return WHITESPACE_PATTERN.sub(" ", cleaned).strip()


def excerpt(value: str | None, limit: int = 220) -> str:
    text = strip_html(value)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def route_search_text(route: str) -> str:
    cleaned = route.strip("/")
    if not cleaned:
        return ""
    return cleaned.replace("/", " ").replace("-", " ").replace("_", " ")


def extract_headings(body: str, limit: int = 6) -> list[str]:
    headings = re.findall(r"<h[23]\b[^>]*>(.*?)</h[23]>", body, flags=re.IGNORECASE | re.DOTALL)
    cleaned: list[str] = []
    for heading in headings:
        text = strip_html(heading)
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= limit:
            break
    return cleaned


def absolutize_schemeless_external_url(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw or raw.startswith(("#", "/", "//")):
        return raw
    lowered = raw.lower()
    if lowered.startswith(("http://", "https://", "mailto:", "tel:", "data:", "javascript:")):
        return raw
    authority = raw.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    if not authority or "." not in authority or any(char.isspace() for char in authority):
        return raw
    authority_no_port = re.sub(r":\d+$", "", authority)
    if authority_no_port.lower().endswith(NON_HOST_SUFFIXES):
        return raw
    if SCHEMELESS_EXTERNAL_HOST_PATTERN.fullmatch(authority):
        return f"http://{raw}"
    return raw


def normalize_external_html_urls(body: str) -> str:
    def replace(match: re.Match[str]) -> str:
        normalized = normalize_html_url(match.group("url"))
        return f'{match.group("prefix")}{match.group("quote")}{normalized}{match.group("quote")}'

    return HTML_URL_ATTRIBUTE_PATTERN.sub(replace, body)


def rewrite_external_html_urls(body: str, external_link_rewrites: dict[str, str] | None) -> str:
    if not external_link_rewrites:
        return body

    def replace(match: re.Match[str]) -> str:
        normalized = normalize_html_url(match.group("url"))
        rewritten = external_link_rewrites.get(normalized, normalized)
        return f'{match.group("prefix")}{match.group("quote")}{rewritten}{match.group("quote")}'

    return HTML_URL_ATTRIBUTE_PATTERN.sub(replace, body)


def normalize_html_url(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    if raw.lower().startswith("vhttp://") or raw.lower().startswith("vhttps://"):
        raw = raw[1:]
    if raw == "undefined/":
        return "/"
    if raw.startswith("documents/"):
        return "/" + raw.lstrip("/")
    if raw.startswith("wiki/"):
        return "https://en.wikipedia.org/" + raw.lstrip("/")
    if "imdb.com/title/tt0824290/" in raw and not raw.lower().startswith(("http://", "https://")):
        return "https://www.imdb.com/title/tt0824290/"
    if raw.startswith(("#", "/", "//")):
        return raw

    parsed = urlparse(raw)
    if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
        return raw
    if parsed.path.lower() == "search.html":
        params = parse_qs(parsed.query)
        query = (params.get("searchword") or params.get("q") or [""])[0].strip()
        if not query:
            return "/search/"
        return "/search/?" + urlencode({"q": query})

    normalized = absolutize_schemeless_external_url(raw)
    if normalized != raw:
        return normalized

    cleaned_path = unquote(parsed.path or "").strip().lstrip("/").rstrip(" '\"")
    if cleaned_path.lower().endswith(".html"):
        stem = cleaned_path[:-5]
        first_segment = stem.split("/", 1)[0].lower()
        if first_segment in LEGACY_SECTION_ROUTE_PREFIXES:
            base_route = LEGACY_SECTION_ROUTE_PREFIXES[first_segment]
            remainder = stem.split("/", 1)[1] if "/" in stem else ""
            route = base_route if not remainder else f"{base_route}/{remainder}"
            if parsed.fragment:
                route += f"#{parsed.fragment}"
            return route
        route = "/" + stem
        if parsed.fragment:
            route += f"#{parsed.fragment}"
        return route

    first_segment = cleaned_path.split("/", 1)[0].lower() if cleaned_path else ""
    if first_segment in LEGACY_SECTION_ROUTE_PREFIXES:
        base_route = LEGACY_SECTION_ROUTE_PREFIXES[first_segment]
        remainder = cleaned_path.split("/", 1)[1] if "/" in cleaned_path else ""
        route = base_route if not remainder else f"{base_route}/{remainder}"
        if parsed.fragment:
            route += f"#{parsed.fragment}"
        return route

    return raw


def ensure_sortable_tables(body: str, external_link_rewrites: dict[str, str] | None = None) -> str:
    normalized = normalize_external_html_urls(body)
    rewritten = rewrite_external_html_urls(normalized, external_link_rewrites)
    return TABLE_OPEN_PATTERN.sub(r"<table\1 data-sortable>", rewritten)


def route_to_output_path(output_root: Path, route: str) -> Path:
    cleaned = route.strip("/")
    if not cleaned:
        return output_root / "index.html"
    return output_root.joinpath(*cleaned.split("/")) / "index.html"


def relative_route(route: str) -> str:
    cleaned = route.strip("/")
    if not cleaned:
        return "/"
    return f"/{cleaned}"


def format_timestamp(value: str | None) -> str | None:
    parsed = parse_timestamp(value)
    if parsed == datetime.min:
        return None
    return parsed.strftime("%d %B %Y")


def slug_to_label(slug: str) -> str:
    if slug.isdigit():
        return slug
    words = slug.replace("-", " ").replace("_", " ").split()
    if not words:
        return slug
    return " ".join(word.capitalize() for word in words)


def first_preview_image(item: dict[str, Any]) -> str | None:
    for ref in item.get("asset_resolution", {}).get("resolved", []):
        suffix = Path(ref).suffix.lower()
        if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"}:
            return "/" + str(ref).lstrip("/")
    return None


def render_layout(title: str, description: str, body: str, body_class: str = "") -> str:
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{html.escape(title)} | {SITE_TITLE}</title>
    <meta name="description" content="{html.escape(description)}">
    <link rel="stylesheet" href="/assets/css/site.css">
    <base href="/">
  </head>
  <body class="{html.escape(body_class)}">
    <header class="masthead">
      <div class="masthead-inner">
        <a class="brand" href="/">{SITE_TITLE}</a>
        <nav class="masthead-nav" aria-label="Primary">
          <a href="/search/">Search</a>
          <a href="/sitemap">Sitemap</a>
          <a href="/tags">Tags</a>
        </nav>
      </div>
    </header>
    {body}
    <script src="/assets/js/table-sort.js"></script>
    <script src="/assets/js/archive-search.js"></script>
  </body>
</html>
"""


def render_redirect_page(destination: str) -> str:
    escaped_destination = html.escape(destination)
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta http-equiv="refresh" content="0; url={escaped_destination}">
    <link rel="canonical" href="{escaped_destination}">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Redirecting | {SITE_TITLE}</title>
    <script>window.location.replace({json.dumps(destination)});</script>
  </head>
  <body>
    <p>Redirecting to <a href="{escaped_destination}">{escaped_destination}</a>...</p>
  </body>
</html>
"""


def render_breadcrumbs(segments: list[tuple[str, str]]) -> str:
    links = ['<a href="/">Home</a>']
    links.extend(f'<a href="{html.escape(route)}">{html.escape(label)}</a>' for label, route in segments[:-1])
    if segments:
        links.append(f'<span aria-current="page">{html.escape(segments[-1][0])}</span>')
    return '<nav class="breadcrumbs" aria-label="Breadcrumbs">' + "".join(links) + "</nav>"


def render_article_page(
    item: dict[str, Any],
    related_items: list[dict[str, Any]],
    category_route_lookup: dict[str, str],
    external_link_rewrites: dict[str, str] | None = None,
) -> str:
    category_name = item.get("category") or "Uncategorized"
    category_route = category_route_lookup.get(category_name, "")
    breadcrumb_segments: list[tuple[str, str]] = []
    if category_route:
        breadcrumb_segments.append((category_name, category_route))
    breadcrumb_segments.append((item["title"], item["original_url"]))

    metadata: list[str] = []
    formatted_updated = format_timestamp(item.get("updated_at"))
    if formatted_updated:
        metadata.append(f"<span>Updated {html.escape(formatted_updated)}</span>")
    metadata.append(f"<span>Source ID {item['source_id']}</span>")
    if item.get("author"):
        metadata.append(f"<span>{html.escape(str(item['author']))}</span>")

    missing_assets = item.get("asset_resolution", {}).get("missing", [])
    missing_block = ""
    if missing_assets:
        missing_block = (
            '<div class="note warning"><strong>Missing extracted assets:</strong> '
            + ", ".join(html.escape(asset) for asset in missing_assets[:8])
            + (" ..." if len(missing_assets) > 8 else "")
            + "</div>"
        )

    related_block = ""
    if related_items:
        related_links = "\n".join(
            f'<li><a href="{html.escape(other["original_url"])}">{html.escape(other["title"])}</a></li>'
            for other in related_items[:12]
            if other["original_url"] != item["original_url"]
        )
        if related_links:
            related_block = f"""
      <aside class="side-panel">
        <div class="panel-card">
          <p class="eyebrow">More In {html.escape(category_name)}</p>
          <ul class="link-list">
            {related_links}
          </ul>
        </div>
      </aside>
"""

    summary = excerpt(item.get("summary"), limit=320)
    summary_block = f'<p class="standfirst">{html.escape(summary)}</p>' if summary else ""
    body_html = ensure_sortable_tables(
        sanitize_article_body(item.get("body", ""), item["original_url"]),
        external_link_rewrites=external_link_rewrites,
    )

    return render_layout(
        title=item["title"],
        description=summary or SITE_SUBTITLE,
        body=f"""
    <main class="page-shell article-shell">
      {render_breadcrumbs(breadcrumb_segments)}
      <section class="content-grid">
        <article class="article-card">
          <header class="article-head">
            <p class="eyebrow">Migration Preview</p>
            <h1>{html.escape(item["title"])}</h1>
            <p class="meta-row">{''.join(metadata)}</p>
            {summary_block}
            {missing_block}
          </header>
          <div class="article-body prose">
            {body_html}
          </div>
        </article>
        {related_block}
      </section>
    </main>
""",
        body_class="page-article",
    )


def render_link_cards(rows: list[tuple[str, str, str]]) -> str:
    cards = []
    for title, route, detail in rows:
        cards.append(
            f"""
        <a class="link-card" href="{html.escape(route)}">
          <strong>{html.escape(title)}</strong>
          <span>{html.escape(detail)}</span>
        </a>
"""
        )
    return "".join(cards)


def render_index_page(
    items: list[dict[str, Any]],
    report: dict[str, Any],
    categories: list[dict[str, Any]],
    category_counts: Counter[str],
    category_route_lookup: dict[str, str],
) -> str:
    top_category_rows = []
    for category in categories:
        title = str(category.get("title") or "")
        path = str(category.get("path") or "")
        if not title or not path:
            continue
        count = category_counts.get(path, 0)
        if count == 0:
            continue
        top_category_rows.append((title, relative_route(path), f"{count} pages"))
    top_category_rows.sort(key=lambda row: (-int(row[2].split()[0]), row[0]))

    recent_rows = [
        (
            item["title"],
            item["original_url"],
            f'{item.get("category") or "Uncategorized"} - {format_timestamp(item.get("updated_at")) or "Unknown date"}',
        )
        for item in sorted(items, key=lambda row: parse_timestamp(row.get("updated_at")), reverse=True)[:12]
    ]

    metrics = [
        ("Pages", str(report["normalized_counts"]["content_items"])),
        ("Resolved assets", str(report["asset_counts"]["resolved"])),
        ("Missing assets", str(report["asset_counts"]["missing"])),
        ("Templates inventoried", str(report["template_inventory"]["template_count"])),
    ]
    metric_html = "".join(
        f"""
        <div class="metric-card">
          <span>{html.escape(label)}</span>
          <strong>{html.escape(value)}</strong>
        </div>
"""
        for label, value in metrics
    )

    return render_layout(
        title="Home",
        description=SITE_SUBTITLE,
        body=f"""
    <main class="page-shell home-shell">
      <section class="hero">
        <p class="eyebrow">Extraction-First Migration</p>
        <h1>{SITE_TITLE}</h1>
        <p class="intro">{SITE_SUBTITLE}</p>
        <div class="metrics-grid">
          {metric_html}
        </div>
      </section>

      <section class="panel-card">
        <div class="section-head">
          <h2>Browse By Section</h2>
          <a href="/sitemap">Full sitemap</a>
        </div>
        <div class="link-card-grid">
          {render_link_cards(top_category_rows[:12])}
        </div>
      </section>

      <section class="panel-card">
        <div class="section-head">
          <h2>Recently Updated</h2>
        </div>
        <div class="link-card-grid">
          {render_link_cards(recent_rows)}
        </div>
      </section>
    </main>
""",
        body_class="page-home",
    )


def render_listing_page(title: str, description: str, rows: list[tuple[str, str, str]], eyebrow: str) -> str:
    return render_layout(
        title=title,
        description=description,
        body=f"""
    <main class="page-shell listing-shell">
      <section class="hero compact">
        <p class="eyebrow">{html.escape(eyebrow)}</p>
        <h1>{html.escape(title)}</h1>
        <p class="intro">{html.escape(description)}</p>
      </section>
      <section class="panel-card">
        <div class="link-card-grid">
          {render_link_cards(rows)}
        </div>
      </section>
    </main>
""",
        body_class="page-listing",
    )


def sanitize_article_body(body: str | None, route: str) -> str:
    cleaned = str(body or "")
    if route == "/ufog/best-ufo-cases/11-consensus-lists-the-rockefeller-briefing-document":
        cleaned = cleaned.replace('href="v"', 'href="/ufo-history/ufo/19731011-pascagoula-abduction"')
    if route == "/ufog/ufo-videos/koi-ufo-video-070":
        cleaned = re.sub(
            r'<a\s+href="/ufog/alien-photos/koi-alien-photo-34"[^>]*>(.*?)</a>',
            r"\1",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
    return cleaned


def render_search_page(total_entries: int) -> str:
    return render_layout(
        title="Search",
        description="Search titles, sections, tags, and page summaries across the Isaac Koi archive.",
        body=f"""
    <main class="page-shell search-shell">
      <section class="hero compact archive-search-shell" data-archive-search data-search-source="/search-index.json" data-search-page-size="48">
        <p class="eyebrow">Archive Search</p>
        <h1>Search the archive</h1>
        <p class="intro">Search titles, summaries, headings, tags, and section labels across {total_entries} indexed entries.</p>
        <form class="archive-search-form" role="search" data-archive-search-form>
          <label class="archive-search-label" for="archive-search-input">Keywords</label>
          <div class="archive-search-row">
            <input id="archive-search-input" class="archive-search-input" type="search" name="q" placeholder="Try 1952, Hynek, Pascagoula, or SETI" autocomplete="off" data-archive-search-input>
            <button type="submit">Search</button>
            <button type="button" data-archive-search-clear hidden>Clear</button>
          </div>
          <p class="archive-search-help">Try years, case names, authors, books, personalities, places, or recurring tags.</p>
          <p class="archive-search-status" data-archive-search-status aria-live="polite">Loading search index...</p>
        </form>
      </section>
      <section class="panel-card">
        <div class="search-results-grid archive-search-results" data-archive-search-results></div>
      </section>
    </main>
""",
        body_class="page-search",
    )


def build_search_index(
    items: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    category_counts: Counter[str],
    category_route_lookup: dict[str, str],
    tag_groups: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    search_index: list[dict[str, Any]] = [
        {
            "kind": "overview",
            "kicker": "Overview",
            "title": SITE_TITLE,
            "url": "/",
            "summary": SITE_SUBTITLE,
            "section": "Overview",
            "tags": [],
            "preview_image": None,
            "search_text": " ".join([SITE_TITLE, SITE_SUBTITLE, "overview archive search"]),
        }
    ]

    tag_labels_by_source: dict[int, list[str]] = defaultdict(list)
    for tag_slug, tag_items in tag_groups.items():
        label = slug_to_label(tag_slug)
        for item in tag_items:
            source_id = item.get("source_id")
            if isinstance(source_id, int) and label not in tag_labels_by_source[source_id]:
                tag_labels_by_source[source_id].append(label)

    for item in items:
        route = str(item.get("original_url") or "").strip()
        if not route:
            continue
        category_name = str(item.get("category") or "Page")
        tag_labels = tag_labels_by_source.get(int(item.get("source_id") or 0), [])
        summary = excerpt(str(item.get("summary") or item.get("body") or ""), 220)
        body_excerpt = excerpt(str(item.get("body") or ""), 420)
        headings = extract_headings(str(item.get("body") or ""), limit=6)
        route_text = route_search_text(route)
        tags_text = " ".join(tag_labels)
        headings_text = " ".join(headings)
        search_index.append(
            {
                "kind": "page",
                "kicker": "Page",
                "title": str(item.get("title") or route),
                "url": route,
                "summary": summary,
                "section": category_name,
                "tags": tag_labels[:6],
                "preview_image": first_preview_image(item),
                "search_text": " ".join(
                    [
                        str(item.get("title") or route),
                        route_text,
                        summary,
                        body_excerpt,
                        category_name,
                        tags_text,
                        headings_text,
                    ]
                ),
            }
        )

    for category in categories:
        title = str(category.get("title") or "").strip()
        path = str(category.get("path") or "").strip("/")
        if not title or not path:
            continue
        count = category_counts.get(path, 0)
        if count <= 0:
            continue
        route = category_route_lookup.get(title, relative_route(path))
        summary = f"{count} published pages in this section."
        search_index.append(
            {
                "kind": "section",
                "kicker": "Section",
                "title": title,
                "url": route,
                "summary": summary,
                "section": "Section",
                "tags": [],
                "preview_image": None,
                "search_text": " ".join([title, route_search_text(route), summary, "section"]),
            }
        )

    for tag_slug, tag_items in tag_groups.items():
        label = slug_to_label(tag_slug)
        route = f"/tags/{tag_slug}"
        summary = f"{len(tag_items)} published pages reference this tag."
        search_index.append(
            {
                "kind": "tag",
                "kicker": "Tag",
                "title": label,
                "url": route,
                "summary": summary,
                "section": "Tags",
                "tags": [label],
                "preview_image": None,
                "search_text": " ".join([label, route_search_text(route), summary, "tag tags"]),
            }
        )

    return search_index


def file_route_to_output_path(output_root: Path, route: str) -> Path:
    cleaned = route.strip("/")
    if not cleaned:
        return output_root / "index.html"
    return output_root.joinpath(*cleaned.split("/"))


def build_category_route_lookup_by_id(categories: list[dict[str, Any]]) -> dict[int, str]:
    lookup: dict[int, str] = {}
    for category in categories:
        identifier = category.get("id")
        path = str(category.get("path") or "").strip("/")
        if isinstance(identifier, int) and path:
            lookup[identifier] = relative_route(path)
    return lookup


def build_article_route_lookup_by_id(items: list[dict[str, Any]]) -> dict[int, str]:
    lookup: dict[int, str] = {}
    for item in items:
        identifier = item.get("source_id")
        route = item.get("original_url")
        if isinstance(identifier, int) and isinstance(route, str) and route:
            lookup[identifier] = route
    return lookup


def build_legacy_redirect_target(
    row: dict[str, Any],
    article_routes_by_id: dict[int, str],
    category_routes_by_id: dict[int, str],
    built_routes: set[str],
) -> str | None:
    route_type = str(row.get("route_type") or "")
    target_path = str(row.get("target_path") or "").strip()
    origurl = str(row.get("origurl") or "")
    parsed = parse_qs(urlparse(origurl).query)

    if route_type == "com_content_article":
        raw_id = next(iter(parsed.get("id", []) or parsed.get("a_id", [])), "")
        raw_id = raw_id.split(":")[0]
        if raw_id.isdigit():
            target = article_routes_by_id.get(int(raw_id))
            if target:
                return target

    if route_type == "com_content_category":
        raw_id = next(iter(parsed.get("id", [])), "")
        raw_id = raw_id.split(":")[0]
        if raw_id.isdigit():
            target = category_routes_by_id.get(int(raw_id))
            if target:
                return target

    if target_path in built_routes:
        return target_path

    return None


def build_category_groups(
    items: list[dict[str, Any]],
    categories: list[dict[str, Any]],
) -> tuple[dict[str, list[dict[str, Any]]], Counter[str], dict[str, str]]:
    by_route: dict[str, list[dict[str, Any]]] = defaultdict(list)
    counts: Counter[str] = Counter()
    title_to_route: dict[str, str] = {}

    valid_paths = {
        str(category.get("path") or "").strip("/")
        for category in categories
        if str(category.get("path") or "").strip("/")
    }

    for category in categories:
        title = str(category.get("title") or "")
        path = str(category.get("path") or "").strip("/")
        if title and path and title not in title_to_route:
            title_to_route[title] = relative_route(path)

    for item in items:
        route = item["original_url"].strip("/")
        segments = route.split("/") if route else []
        for index in range(len(segments) - 1, 0, -1):
            candidate = "/".join(segments[:index])
            if candidate in valid_paths:
                by_route[candidate].append(item)
                counts[candidate] += 1
                break

    for route_items in by_route.values():
        route_items.sort(key=lambda row: (row["title"].lower(), row["original_url"]))

    return by_route, counts, title_to_route


def build_category_children(categories: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    children: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for category in categories:
        parent_id = category.get("parent_id")
        if isinstance(parent_id, int):
            children[parent_id].append(category)
    for rows in children.values():
        rows.sort(key=lambda row: str(row.get("title") or "").lower())
    return children


def build_tag_groups(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    tag_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        seen: set[str] = set()
        explicit_tags = [str(tag).strip().strip("/") for tag in item.get("tags", []) if str(tag).strip()]
        body_tags = [tag_slug.strip().strip("/") for tag_slug in TAG_LINK_PATTERN.findall(item.get("body", ""))]
        for tag_slug in explicit_tags or body_tags:
            cleaned = tag_slug.strip().strip("/")
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            tag_groups[cleaned].append(item)

    for tag_items in tag_groups.values():
        tag_items.sort(key=lambda row: (row["title"].lower(), row["original_url"]))
    return dict(sorted(tag_groups.items()))


def reset_output_root(output_root: Path) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    for child in output_root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def build_site(
    content_root: Path,
    output_root: Path,
    template_root: Path,
) -> dict[str, int]:
    meta_root = content_root / "_meta"
    manifest_path = meta_root / "content-manifest.json"
    report_path = meta_root / "extraction-report.json"
    category_index_path = meta_root / "category-index.json"
    legacy_routes_path = meta_root / "legacy-routes.json"
    redirects_path = meta_root / "redirects.json"
    external_link_rewrites_path = meta_root / "external-link-rewrites.json"

    items = [item for item in load_json(manifest_path) if item.get("status") == "published" and item.get("original_url")]
    report = load_json(report_path)
    categories = [
        row
        for row in load_json(category_index_path)
        if row.get("extension") == "com_content" and row.get("published") in (1, "1", True)
    ]
    legacy_routes = load_json(legacy_routes_path) if legacy_routes_path.exists() else []
    redirects = load_json(redirects_path) if redirects_path.exists() else []
    external_link_rewrites = (
        {
            str(row.get("original_url") or "").strip(): str(row.get("replacement_url") or "").strip()
            for row in load_json(external_link_rewrites_path)
            if str(row.get("original_url") or "").strip() and str(row.get("replacement_url") or "").strip()
        }
        if external_link_rewrites_path.exists()
        else {}
    )

    category_groups, category_counts, category_route_lookup = build_category_groups(items, categories)
    category_children = build_category_children(categories)
    category_route_lookup_by_id = build_category_route_lookup_by_id(categories)
    article_route_lookup_by_id = build_article_route_lookup_by_id(items)
    tag_groups = build_tag_groups(items)
    article_routes = {item["original_url"] for item in items}
    built_routes = {"/", "/search", "/sitemap", "/tags"} | set(article_routes) | set(category_route_lookup.values())

    reset_output_root(output_root)
    write_text(output_root / ".nojekyll", "")

    template_assets_root = template_root / "assets"
    if template_assets_root.exists():
        shutil.copytree(template_assets_root, output_root / "assets", dirs_exist_ok=True)

    content_assets_root = content_root / "assets" / "source"
    copied_asset_dirs = 0
    if content_assets_root.exists():
        for child in content_assets_root.iterdir():
            destination = output_root / child.name
            if child.is_dir():
                shutil.copytree(child, destination, dirs_exist_ok=True)
            else:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(child, destination)
            copied_asset_dirs += 1

    write_text(
        output_root / "index.html",
        render_index_page(items, report, categories, category_counts, category_route_lookup),
    )
    search_index = build_search_index(items, categories, category_counts, category_route_lookup, tag_groups)
    write_text(output_root / "search-index.json", json.dumps(search_index, indent=2, ensure_ascii=False))
    write_text(
        route_to_output_path(output_root, "/search"),
        render_search_page(len(search_index)),
    )

    category_pages = 0
    for category in categories:
        path = str(category.get("path") or "").strip("/")
        title = str(category.get("title") or "").strip()
        if not path or not title or relative_route(path) in article_routes:
            continue
        category_items = category_groups.get(path, [])
        child_rows = []
        for child in category_children.get(int(category.get("id") or -1), []):
            child_path = str(child.get("path") or "").strip("/")
            child_title = str(child.get("title") or "").strip()
            if not child_path or not child_title:
                continue
            child_count = category_counts.get(child_path, 0)
            child_rows.append(
                (
                    child_title,
                    relative_route(child_path),
                    f"{child_count} pages" if child_count else "Section",
                )
            )
        rows = [
            (
                item["title"],
                item["original_url"],
                format_timestamp(item.get("updated_at")) or "Undated",
            )
            for item in category_items
        ] or child_rows
        description = (
            f"{len(category_items)} published pages in this section."
            if category_items
            else (
                f"{len(child_rows)} child sections in this part of the archive."
                if child_rows
                else "Section landing page for this part of the archive."
            )
        )
        write_text(
            route_to_output_path(output_root, path),
            render_listing_page(
                title=title,
                description=description,
                rows=rows,
                eyebrow="Section",
            ),
        )
        category_pages += 1

    article_pages = 0
    for item in items:
        category_name = str(item.get("category") or "")
        related_items = []
        category_route = category_route_lookup.get(category_name)
        if category_route:
            related_items = category_groups.get(category_route.strip("/"), [])
        write_text(
            route_to_output_path(output_root, item["original_url"]),
            render_article_page(
                item,
                related_items,
                category_route_lookup,
                external_link_rewrites=external_link_rewrites,
            ),
        )
        article_pages += 1

    tag_pages = 0
    tag_listing_rows: list[tuple[str, str, str]] = []
    for tag_slug, tag_items in tag_groups.items():
        title = slug_to_label(tag_slug)
        rows = [
            (
                item["title"],
                item["original_url"],
                item.get("category") or "Uncategorized",
            )
            for item in tag_items
        ]
        route = f"/tags/{tag_slug}"
        write_text(
            route_to_output_path(output_root, route),
            render_listing_page(
                title=title,
                description=f"{len(rows)} pages reference this tag or year.",
                rows=rows,
                eyebrow="Tag",
            ),
        )
        tag_listing_rows.append((title, route, f"{len(rows)} pages"))
        tag_pages += 1
        built_routes.add(route)

    tag_listing_rows.sort(key=lambda row: row[0].lower())
    write_text(
        route_to_output_path(output_root, "/tags"),
        render_listing_page(
            title="Tags",
            description=f"{len(tag_listing_rows)} generated tag pages from internal tag links.",
            rows=tag_listing_rows,
            eyebrow="Index",
        ),
    )

    sitemap_rows = [
        (
            str(category.get("title") or ""),
            relative_route(str(category.get("path") or "").strip("/")),
            f"{category_counts.get(str(category.get('path') or '').strip('/'), 0)} pages",
        )
        for category in categories
        if str(category.get("path") or "").strip("/") and category_counts.get(str(category.get("path") or "").strip("/"), 0)
    ]
    sitemap_rows.sort(key=lambda row: row[0].lower())
    sitemap_html = render_listing_page(
        title="Sitemap",
        description="Generated section index for the current migration preview.",
        rows=sitemap_rows,
        eyebrow="Navigation",
    )
    write_text(route_to_output_path(output_root, "/sitemap"), sitemap_html)
    write_text(
        output_root / "sitemap.html",
        '<!doctype html><html><head><meta http-equiv="refresh" content="0; url=/sitemap/"></head><body></body></html>',
    )

    redirect_pages = 0
    seen_redirect_sources: set[str] = set()
    for row in legacy_routes:
        if row.get("enabled") not in (1, "1", True):
            continue
        source = str(row.get("sefurl") or "").strip().lstrip("/")
        if not source or source in seen_redirect_sources:
            continue
        destination = build_legacy_redirect_target(
            row,
            article_route_lookup_by_id,
            category_route_lookup_by_id,
            built_routes,
        )
        if not destination:
            continue
        if not source.endswith(".html") and relative_route(source) == destination:
            continue
        write_text(file_route_to_output_path(output_root, source), render_redirect_page(destination))
        seen_redirect_sources.add(source)
        redirect_pages += 1

    for row in redirects:
        source = str(row.get("source") or "").strip()
        destination = str(row.get("destination") or "").strip()
        if not source or not destination:
            continue
        source_key = source.lstrip("/")
        if not source_key or source_key in seen_redirect_sources:
            continue
        output_path = (
            file_route_to_output_path(output_root, source_key)
            if source_key.endswith(".html")
            else route_to_output_path(output_root, source_key)
        )
        write_text(output_path, render_redirect_page(destination))
        seen_redirect_sources.add(source_key)
        redirect_pages += 1

    return {
        "article_pages": article_pages,
        "category_pages": category_pages,
        "tag_pages": tag_pages,
        "copied_asset_roots": copied_asset_dirs,
        "redirect_pages": redirect_pages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a static preview site from normalized Joomla content.")
    parser.add_argument("--content-root", type=Path, default=Path("content"))
    parser.add_argument("--output-root", type=Path, default=Path("site"))
    parser.add_argument("--template-root", type=Path, default=Path("templates/static-preview"))
    args = parser.parse_args()

    result = build_site(
        content_root=args.content_root.resolve(),
        output_root=args.output_root.resolve(),
        template_root=args.template_root.resolve(),
    )
    print(
        f"Built {result['article_pages']} article pages, {result['category_pages']} category pages, "
        f"{result['tag_pages']} tag pages, and {result['redirect_pages']} redirects into "
        f"{args.output_root.resolve()}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
