from __future__ import annotations

import argparse
import mimetypes
import urllib.request
from pathlib import Path

from build_jekyll_site import (
    BOOK_COVER_CACHE_ROOT,
    build_book_metadata,
    deep_clean,
    load_json,
    normalize_route_prefixes,
    route_matches_prefixes,
)


USER_AGENT = "Mozilla/5.0 (compatible; IsaacKoiMigration/1.0)"
CONTENT_TYPE_SUFFIXES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


def fetch_cover(url: str, timeout: int) -> tuple[bytes, str | None, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = str(response.headers.get("Content-Type") or "").split(";")[0].strip().lower() or None
        body = response.read()
        final_url = response.geturl()
    return body, content_type, final_url


def infer_suffix(content_type: str | None, final_url: str, identifier: str) -> str:
    if content_type in CONTENT_TYPE_SUFFIXES:
        return CONTENT_TYPE_SUFFIXES[content_type]
    guessed, _ = mimetypes.guess_type(final_url)
    if guessed in CONTENT_TYPE_SUFFIXES:
        return CONTENT_TYPE_SUFFIXES[guessed]
    if identifier.upper().endswith(".PNG"):
        return ".png"
    return ".jpg"


def is_isbn_identifier(identifier: str) -> bool:
    normalized = str(identifier or "").strip().upper()
    if len(normalized) == 10:
        return normalized[:9].isdigit() and (normalized[-1].isdigit() or normalized[-1] == "X")
    if len(normalized) == 13:
        return normalized.isdigit()
    return False


def openlibrary_cover_url(identifier: str) -> str:
    return f"https://covers.openlibrary.org/b/isbn/{identifier}-L.jpg?default=false"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cache book cover images locally for the Jekyll preview/build pipeline.")
    parser.add_argument("--content-root", type=Path, default=Path("content"))
    parser.add_argument("--route-prefix", action="append", default=[], help="Only cache covers for this route prefix.")
    parser.add_argument("--limit-items", type=int, default=None, help="Limit the number of book pages processed.")
    parser.add_argument("--force", action="store_true", help="Re-download covers even when a cached local file already exists.")
    parser.add_argument("--timeout", type=int, default=30, help="Per-request timeout in seconds.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    content_root = args.content_root.resolve()
    meta_root = content_root / "_meta"
    cache_root = content_root / BOOK_COVER_CACHE_ROOT
    cache_root.mkdir(parents=True, exist_ok=True)

    route_prefixes = normalize_route_prefixes(args.route_prefix)
    items = [
        item
        for item in deep_clean(load_json(meta_root / "content-manifest.json"))
        if item.get("status") == "published" and item.get("original_url")
    ]
    if route_prefixes:
        items = [item for item in items if route_matches_prefixes(str(item["original_url"]), route_prefixes)]
    if args.limit_items is not None:
        items = items[: max(args.limit_items, 0)]

    processed = 0
    downloaded = 0
    skipped_existing = 0
    skipped_no_cover = 0

    for item in items:
        book = build_book_metadata(item, content_root=None)
        if not book:
            continue
        candidate_identifiers = [
            str(identifier).strip().upper()
            for identifier in book.get("identifiers", [])
            if is_isbn_identifier(str(identifier).strip().upper())
        ]
        if not candidate_identifiers:
            skipped_no_cover += 1
            continue
        processed += 1

        existing_identifiers = []
        for identifier in candidate_identifiers:
            for suffix in (".jpg", ".jpeg", ".png", ".webp"):
                candidate = cache_root / f"{identifier}{suffix}"
                if candidate.exists():
                    existing_identifiers.append(identifier)
                    break
        if existing_identifiers and not args.force:
            skipped_existing += 1
            continue

        downloaded_cover = False
        for identifier in candidate_identifiers:
            try:
                body, content_type, final_url = fetch_cover(openlibrary_cover_url(identifier), args.timeout)
            except Exception:
                continue
            if not body:
                continue
            suffix = infer_suffix(content_type, final_url, identifier)
            destination = cache_root / f"{identifier}{suffix}"
            destination.write_bytes(body)
            downloaded += 1
            downloaded_cover = True
            break
        if not downloaded_cover:
            skipped_no_cover += 1

    print(
        f"Processed {processed} book pages, downloaded {downloaded} cover files, "
        f"skipped {skipped_existing} existing and {skipped_no_cover} unavailable."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
