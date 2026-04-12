from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0"
DEFAULT_TIMESTAMP = "20100101"
DEFAULT_FROM_YEAR = 2008
DEFAULT_TO_YEAR = 2012
CDX_FIELDS = "timestamp,original,statuscode,mimetype"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_json(url: str, timeout: int) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def build_cdx_url(url: str) -> str:
    return (
        "https://web.archive.org/cdx/search/cdx"
        f"?output=json&fl={quote(CDX_FIELDS, safe=',')}"
        "&filter=statuscode:200"
        "&limit=-10"
        f"&url={quote(url, safe='')}"
    )


def fetch_wayback_rows(url: str, timeout: int) -> list[list[str]]:
    payload = fetch_json(build_cdx_url(url), timeout)
    if not payload:
        return []
    return payload[1:]


def fetch_wayback_rows_with_retries(
    url: str,
    *,
    timeout: int,
    retries: int,
    sleep_seconds: float,
) -> list[list[str]]:
    last_error: Exception | None = None
    attempts = max(1, retries + 1)
    for attempt in range(attempts):
        try:
            rows = fetch_wayback_rows(url, timeout)
            if sleep_seconds:
                time.sleep(sleep_seconds)
            return rows
        except Exception as exc:
            last_error = exc
            if sleep_seconds:
                time.sleep(sleep_seconds)
            if attempt + 1 >= attempts:
                break
    if last_error is not None:
        raise last_error
    return []


def timestamp_in_window(timestamp: str, from_year: int, to_year: int) -> bool:
    if len(timestamp) < 4 or not timestamp[:4].isdigit():
        return False
    year = int(timestamp[:4])
    return from_year <= year <= to_year


def timestamp_distance(timestamp: str, preferred_timestamp: str) -> int:
    try:
        return abs(int(timestamp[:14].ljust(14, "0")) - int(preferred_timestamp[:14].ljust(14, "0")))
    except ValueError:
        return 10**18


def choose_capture(
    rows: list[list[str]],
    *,
    preferred_timestamp: str,
    from_year: int,
    to_year: int,
) -> tuple[dict[str, str] | None, bool]:
    if not rows:
        return None, False

    normalized_rows = [
        {
            "timestamp": str(row[0]),
            "original": str(row[1]),
            "statuscode": str(row[2]) if len(row) > 2 else "200",
            "mimetype": str(row[3]) if len(row) > 3 else "",
        }
        for row in rows
        if len(row) >= 2
    ]
    if not normalized_rows:
        return None, False

    in_window = [
        row
        for row in normalized_rows
        if timestamp_in_window(row["timestamp"], from_year, to_year)
    ]
    candidate_rows = in_window or normalized_rows
    chosen = min(
        candidate_rows,
        key=lambda row: (
            timestamp_distance(row["timestamp"], preferred_timestamp),
            row["timestamp"],
        ),
    )
    return chosen, bool(in_window)


def build_wayback_url(timestamp: str, original: str) -> str:
    return f"https://web.archive.org/web/{timestamp}/{original}"


def build_rewrites(
    *,
    dead_report_path: Path,
    output_path: Path,
    hosts: set[str],
    preferred_timestamp: str,
    from_year: int,
    to_year: int,
    timeout: int,
    retries: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    report = load_json(dead_report_path)
    dead_rows = [
        row
        for row in report["external"]["dead"]
        if row.get("host") in hosts
    ]

    existing_rows: list[dict[str, Any]] = load_json(output_path) if output_path.exists() else []
    preserved_rows = [
        row
        for row in existing_rows
        if (
            str(urlparse(str(row.get("original_url") or "")).netloc).lower() not in hosts
            or str(row.get("source") or "").lower() != "wayback"
        )
    ]

    generated_rows: list[dict[str, Any]] = []
    stats = {
        "requested_dead_urls": len(dead_rows),
        "rewritten_urls": 0,
        "preferred_window_urls": 0,
        "fallback_any_urls": 0,
        "unresolved_urls": 0,
        "errors": 0,
    }

    for row in dead_rows:
        original_url = str(row.get("url") or "").strip()
        host = str(row.get("host") or "").strip().lower()
        if not original_url:
            continue
        try:
            cdx_rows = fetch_wayback_rows_with_retries(
                original_url,
                timeout=timeout,
                retries=retries,
                sleep_seconds=sleep_seconds,
            )
            chosen, preferred_window = choose_capture(
                cdx_rows,
                preferred_timestamp=preferred_timestamp,
                from_year=from_year,
                to_year=to_year,
            )
            if not chosen:
                stats["unresolved_urls"] += 1
                continue
            replacement_url = build_wayback_url(
                str(chosen.get("timestamp") or ""),
                str(chosen.get("original") or original_url),
            )
            generated_rows.append(
                {
                    "original_url": original_url,
                    "replacement_url": replacement_url,
                    "host": host,
                    "occurrences": int(row.get("occurrences") or 0),
                    "snapshot_timestamp": str(chosen.get("timestamp") or ""),
                    "preferred_window": preferred_window,
                    "source": "wayback",
                }
            )
            stats["rewritten_urls"] += 1
            if preferred_window:
                stats["preferred_window_urls"] += 1
            else:
                stats["fallback_any_urls"] += 1
        except Exception:
            stats["errors"] += 1

    merged_rows = sorted(
        preserved_rows + generated_rows,
        key=lambda row: (str(row.get("host") or ""), str(row.get("original_url") or "")),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(merged_rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "hosts": sorted(hosts),
        "stats": stats,
        "output_path": str(output_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build external-link rewrite mappings to Wayback Machine captures.")
    parser.add_argument(
        "--dead-report",
        type=Path,
        default=Path("artifacts/dead-links-report.json"),
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path("content/_meta/external-link-rewrites.json"),
    )
    parser.add_argument(
        "--hosts",
        nargs="+",
        required=True,
        help="One or more dead-link hosts to process.",
    )
    parser.add_argument("--preferred-timestamp", default=DEFAULT_TIMESTAMP)
    parser.add_argument("--from-year", type=int, default=DEFAULT_FROM_YEAR)
    parser.add_argument("--to-year", type=int, default=DEFAULT_TO_YEAR)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=0.5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    summary = build_rewrites(
        dead_report_path=args.dead_report,
        output_path=args.output_path,
        hosts={host.lower() for host in args.hosts},
        preferred_timestamp=args.preferred_timestamp,
        from_year=args.from_year,
        to_year=args.to_year,
        timeout=args.timeout,
        retries=args.retries,
        sleep_seconds=args.sleep_seconds,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
