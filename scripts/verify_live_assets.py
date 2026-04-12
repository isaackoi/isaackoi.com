from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen


ASSET_EXTENSION_HINTS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".mp4",
    ".avi",
    ".mov",
)
BARE_EXTERNAL_PATH_PATTERN = re.compile(r"^(?:[a-z0-9-]+\.)+[a-z]{2,}/", re.IGNORECASE)
USER_AGENT = "Mozilla/5.0"


@dataclass
class FetchResult:
    ok: bool
    url: str
    final_url: str | None
    status: int | None
    error: str | None = None
    content_type: str | None = None
    body: str | None = None


class AssetParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.assets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = dict(attrs)
        for key in ("src", "href", "data-src", "data-image", "poster"):
            value = attr_map.get(key)
            if value:
                self.assets.append(value)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_content_identifier(value: str | None) -> int | None:
    if not value:
        return None
    raw = value.split(":")[0]
    if raw.isdigit():
        return int(raw)
    return None


def build_category_route_lookup_by_id(categories: list[dict[str, Any]]) -> dict[int, str]:
    lookup: dict[int, str] = {}
    for row in categories:
        identifier = row.get("id")
        path = str(row.get("path") or "").strip("/")
        if isinstance(identifier, int) and path:
            lookup[identifier] = "/" + path
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
        article_id = parse_content_identifier(raw_id)
        if article_id is not None:
            target = article_routes_by_id.get(article_id)
            if target:
                return target

    if route_type == "com_content_category":
        raw_id = next(iter(parsed.get("id", [])), "")
        category_id = parse_content_identifier(raw_id)
        if category_id is not None:
            target = category_routes_by_id.get(category_id)
            if target:
                return target

    if target_path in built_routes:
        return target_path

    return None


def score_legacy_source(sefurl: str) -> tuple[int, int, int, str]:
    lowered = sefurl.lower()
    penalty = 0
    if not lowered.endswith(".html"):
        penalty += 100
    if "/atom" in lowered or "/rss" in lowered or "feed" in lowered:
        penalty += 50
    if "/page-" in lowered:
        penalty += 25
    return (penalty, lowered.count("/"), len(lowered), lowered)


def build_live_page_lookup(
    items: list[dict[str, Any]],
    categories: list[dict[str, Any]],
    legacy_routes: list[dict[str, Any]],
    site_origin: str,
) -> dict[int, list[str]]:
    article_routes_by_id = build_article_route_lookup_by_id(items)
    route_to_source_id = {route: source_id for source_id, route in article_routes_by_id.items()}
    category_routes_by_id = build_category_route_lookup_by_id(categories)
    built_routes = set(article_routes_by_id.values()) | set(category_routes_by_id.values()) | {"/tags"}

    lookup: dict[int, list[str]] = {}
    for row in legacy_routes:
        source = str(row.get("sefurl") or "").strip()
        if not source:
            continue
        destination = build_legacy_redirect_target(row, article_routes_by_id, category_routes_by_id, built_routes)
        if not destination:
            continue
        source_id = route_to_source_id.get(destination)
        if source_id is None:
            continue
        url = urljoin(site_origin.rstrip("/") + "/", source)
        lookup.setdefault(source_id, []).append(url)

    for source_id, urls in lookup.items():
        ordered = sorted(set(urls), key=lambda value: score_legacy_source(urlparse(value).path.lstrip("/")))
        lookup[source_id] = ordered
    return lookup


def normalize_asset_reference(value: str, site_origin: str) -> str:
    stripped = value.strip()
    if stripped.startswith("http://") or stripped.startswith("https://"):
        return stripped
    if BARE_EXTERNAL_PATH_PATTERN.match(stripped):
        return f"http://{stripped}"
    return urljoin(site_origin.rstrip("/") + "/", stripped.lstrip("/"))


def normalize_asset_key(value: str, site_origin: str) -> str:
    resolved = normalize_asset_reference(value, site_origin)
    parsed = urlparse(resolved)
    if parsed.scheme in {"http", "https"}:
        return f"{parsed.netloc.lower()}{parsed.path.lower()}"
    return resolved.lower()


def fetch_text(url: str, timeout: int) -> FetchResult:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return FetchResult(
                ok=True,
                url=url,
                final_url=response.geturl(),
                status=response.status,
                content_type=response.headers.get_content_type(),
                body=body,
            )
    except Exception as exc:
        status = getattr(exc, "code", None)
        return FetchResult(ok=False, url=url, final_url=None, status=status, error=repr(exc))


def fetch_binary_probe(url: str, timeout: int) -> FetchResult:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=timeout) as response:
            response.read(1)
            return FetchResult(
                ok=True,
                url=url,
                final_url=response.geturl(),
                status=response.status,
                content_type=response.headers.get_content_type(),
            )
    except Exception as exc:
        status = getattr(exc, "code", None)
        return FetchResult(ok=False, url=url, final_url=None, status=status, error=repr(exc))


def extract_page_asset_keys(html_text: str, page_url: str, site_origin: str) -> set[str]:
    parser = AssetParser()
    parser.feed(html_text)
    keys: set[str] = set()
    for asset in parser.assets:
        resolved = urljoin(page_url, asset)
        if any(ext in resolved.lower() for ext in ASSET_EXTENSION_HINTS):
            keys.add(normalize_asset_key(resolved, site_origin))
    return keys


def verify_live_assets(meta_root: Path, site_origin: str, timeout: int) -> dict[str, Any]:
    items = load_json(meta_root / "content-manifest.json")
    categories = load_json(meta_root / "category-index.json")
    legacy_routes = load_json(meta_root / "legacy-routes.json")
    missing_assets = load_json(meta_root / "missing-assets.json")

    items_by_id = {
        row["source_id"]: row
        for row in items
        if isinstance(row.get("source_id"), int)
    }
    live_page_lookup = build_live_page_lookup(items, categories, legacy_routes, site_origin)

    required_source_ids = sorted({
        affected["source_id"]
        for row in missing_assets
        for affected in row.get("affected_items", [])
        if isinstance(affected.get("source_id"), int)
    })

    page_results: dict[int, dict[str, Any]] = {}
    for source_id in required_source_ids:
        candidates = live_page_lookup.get(source_id, [])
        attempts: list[dict[str, Any]] = []
        selected: dict[str, Any] | None = None
        asset_keys: set[str] = set()
        for candidate in candidates:
            fetched = fetch_text(candidate, timeout=timeout)
            attempts.append(
                {
                    "url": candidate,
                    "ok": fetched.ok,
                    "status": fetched.status,
                    "final_url": fetched.final_url,
                    "error": fetched.error,
                }
            )
            if fetched.ok and fetched.body is not None:
                asset_keys = extract_page_asset_keys(fetched.body, candidate, site_origin)
                selected = attempts[-1]
                break
        page_results[source_id] = {
            "source_id": source_id,
            "title": items_by_id.get(source_id, {}).get("title"),
            "normalized_url": items_by_id.get(source_id, {}).get("original_url"),
            "candidate_urls": candidates,
            "selected_page": selected,
            "attempts": attempts,
            "asset_keys": sorted(asset_keys),
        }

    verification_rows: list[dict[str, Any]] = []
    summary = {
        "unique_missing_assets": len(missing_assets),
        "items_checked": len(required_source_ids),
        "page_fetch_successes": sum(1 for row in page_results.values() if row["selected_page"]),
        "page_fetch_failures": sum(1 for row in page_results.values() if not row["selected_page"]),
        "present_in_any_live_page_dom": 0,
        "fetchable_asset_urls": 0,
        "nonfetchable_asset_urls": 0,
        "external_asset_urls": 0,
    }

    for row in missing_assets:
        asset_ref = row["asset_ref"]
        asset_url = normalize_asset_reference(asset_ref, site_origin)
        is_external = not asset_url.startswith(site_origin.rstrip("/"))
        if is_external:
            summary["external_asset_urls"] += 1
        asset_fetch = fetch_binary_probe(asset_url, timeout=timeout)
        if asset_fetch.ok:
            summary["fetchable_asset_urls"] += 1
        else:
            summary["nonfetchable_asset_urls"] += 1

        affected_items: list[dict[str, Any]] = []
        present_in_any_page = False
        asset_key = normalize_asset_key(asset_ref, site_origin)
        for affected in row.get("affected_items", []):
            source_id = affected.get("source_id")
            page_result = page_results.get(source_id, {})
            page_asset_keys = set(page_result.get("asset_keys", []))
            present_in_dom = asset_key in page_asset_keys
            present_in_any_page = present_in_any_page or present_in_dom
            selected_page = page_result.get("selected_page") or {}
            affected_items.append(
                {
                    "source_id": source_id,
                    "title": affected.get("title"),
                    "normalized_url": affected.get("url"),
                    "live_page_url": selected_page.get("url"),
                    "page_fetch_ok": bool(selected_page),
                    "present_in_live_page_dom": present_in_dom,
                }
            )

        if present_in_any_page:
            summary["present_in_any_live_page_dom"] += 1

        verification_rows.append(
            {
                "asset_ref": asset_ref,
                "asset_url": asset_url,
                "classification": row.get("classification"),
                "suggested_action": row.get("suggested_action"),
                "suggested_target": row.get("suggested_target"),
                "count": row.get("count"),
                "is_external": is_external,
                "present_in_any_live_page_dom": present_in_any_page,
                "asset_fetch": {
                    "ok": asset_fetch.ok,
                    "status": asset_fetch.status,
                    "final_url": asset_fetch.final_url,
                    "error": asset_fetch.error,
                    "content_type": asset_fetch.content_type,
                },
                "affected_items": affected_items,
            }
        )

    return {
        "summary": summary,
        "site_origin": site_origin,
        "page_results": [
            {
                "source_id": row["source_id"],
                "title": row["title"],
                "normalized_url": row["normalized_url"],
                "candidate_urls": row["candidate_urls"],
                "selected_page": row["selected_page"],
                "attempts": row["attempts"],
            }
            for row in sorted(page_results.values(), key=lambda entry: entry["source_id"])
        ],
        "assets": verification_rows,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify missing extracted asset references against the live legacy site."
    )
    parser.add_argument(
        "--meta-root",
        default="content/_meta",
        help="Directory containing the extraction metadata JSON files.",
    )
    parser.add_argument(
        "--site-origin",
        default="https://www.isaackoi.com",
        help="Live site origin used for page and asset verification.",
    )
    parser.add_argument(
        "--output-path",
        default="content/_meta/live-asset-verification.json",
        help="JSON output path for the verification artifact.",
    )
    parser.add_argument(
        "--timeout",
        default=20,
        type=int,
        help="Per-request timeout in seconds.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or [])
    meta_root = Path(args.meta_root).resolve()
    output_path = Path(args.output_path).resolve()
    verification = verify_live_assets(meta_root, args.site_origin, args.timeout)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(verification, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = verification["summary"]
    print(
        f"Verified {summary['unique_missing_assets']} missing assets across {summary['items_checked']} pages; "
        f"{summary['present_in_any_live_page_dom']} appear in live page DOM and "
        f"{summary['fetchable_asset_urls']} asset URLs are directly fetchable."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
