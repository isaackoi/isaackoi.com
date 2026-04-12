from __future__ import annotations

import argparse
import json
import time
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen


USER_AGENT = "Mozilla/5.0"
CDX_FIELDS = "timestamp,original,statuscode,mimetype"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def is_external_reference(asset_ref: str) -> bool:
    parsed = urlparse(asset_ref)
    if parsed.scheme in {"http", "https"}:
        return True
    return not asset_ref.startswith("/") and "." in asset_ref.split("/", 1)[0]


def normalize_asset_url(asset_ref: str, site_origin: str) -> str:
    parsed = urlparse(asset_ref)
    if parsed.scheme in {"http", "https"}:
        return asset_ref
    if is_external_reference(asset_ref):
        return f"http://{asset_ref}"
    return site_origin.rstrip("/") + "/" + asset_ref.lstrip("/")


def build_cdx_url(asset_url: str) -> str:
    return (
        "https://web.archive.org/cdx/search/cdx"
        f"?output=json&fl={quote(CDX_FIELDS, safe=',')}"
        "&filter=statuscode:200"
        f"&url={quote(asset_url, safe='')}"
    )


def fetch_json(url: str, timeout: int) -> Any:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def choose_capture(rows: list[list[str]]) -> dict[str, str] | None:
    if not rows:
        return None
    rows = sorted(rows, key=lambda row: row[0])
    timestamp, original, statuscode, mimetype = rows[-1]
    return {
        "timestamp": timestamp,
        "original": original,
        "statuscode": statuscode,
        "mimetype": mimetype,
    }


def build_raw_capture_url(timestamp: str, original: str) -> str:
    return f"https://web.archive.org/web/{timestamp}id_/{original}"


def fetch_binary(url: str, timeout: int) -> tuple[bytes, str | None]:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        return response.read(), response.headers.get("Content-Type")


def internal_output_path(asset_ref: str, output_root: Path) -> Path:
    return output_root.joinpath(*PurePosixPath(asset_ref.lstrip("/")).parts)


def external_output_path(asset_url: str, output_root: Path) -> Path:
    parsed = urlparse(asset_url)
    path = parsed.path.lstrip("/")
    return output_root.joinpath(parsed.netloc, *PurePosixPath(path).parts)


def recover_assets(
    missing_assets: list[dict[str, Any]],
    site_origin: str,
    internal_output_root: Path,
    external_output_root: Path | None,
    timeout: int,
    sleep_seconds: float,
) -> dict[str, Any]:
    recovered: list[dict[str, Any]] = []
    skipped_existing: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for item in missing_assets:
        asset_ref = item["asset_ref"]
        asset_url = normalize_asset_url(asset_ref, site_origin)
        if is_external_reference(asset_ref):
            destination = (
                external_output_path(asset_url, external_output_root)
                if external_output_root is not None
                else None
            )
        else:
            destination = internal_output_path(asset_ref, internal_output_root)

        if destination is not None and destination.exists():
            skipped_existing.append(
                {
                    "asset_ref": asset_ref,
                    "asset_url": asset_url,
                    "destination": str(destination),
                }
            )
            continue

        try:
            cdx_rows = fetch_json(build_cdx_url(asset_url), timeout=timeout)
            rows = cdx_rows[1:] if cdx_rows else []
            capture = choose_capture(rows)
            if not capture:
                unavailable.append(
                    {
                        "asset_ref": asset_ref,
                        "asset_url": asset_url,
                        "reason": "not_in_wayback",
                    }
                )
                continue

            raw_url = build_raw_capture_url(capture["timestamp"], capture["original"])
            payload, content_type = fetch_binary(raw_url, timeout=timeout)

            if is_external_reference(asset_ref):
                if external_output_root is None:
                    recovered.append(
                        {
                            "asset_ref": asset_ref,
                            "asset_url": asset_url,
                            "saved": False,
                            "reason": "external_capture_only",
                            "capture": capture,
                            "raw_url": raw_url,
                            "content_type": content_type,
                            "size_bytes": len(payload),
                        }
                    )
                    continue
                destination = external_output_path(asset_url, external_output_root)
            else:
                destination = internal_output_path(asset_ref, internal_output_root)

            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
            recovered.append(
                {
                    "asset_ref": asset_ref,
                    "asset_url": asset_url,
                    "saved": True,
                    "destination": str(destination),
                    "capture": capture,
                    "raw_url": raw_url,
                    "content_type": content_type,
                    "size_bytes": len(payload),
                }
            )
        except Exception as exc:
            errors.append(
                {
                    "asset_ref": asset_ref,
                    "asset_url": asset_url,
                    "error": repr(exc),
                }
            )
        finally:
            if sleep_seconds:
                time.sleep(sleep_seconds)

    return {
        "site_origin": site_origin,
        "attempted": len(missing_assets),
        "recovered": recovered,
        "skipped_existing": skipped_existing,
        "unavailable": unavailable,
        "errors": errors,
        "counts": {
            "recovered": len(recovered),
            "skipped_existing": len(skipped_existing),
            "saved_internal_or_external": sum(1 for row in recovered if row.get("saved")),
            "external_capture_only": sum(1 for row in recovered if row.get("reason") == "external_capture_only"),
            "unavailable": len(unavailable),
            "errors": len(errors),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recover missing site assets from the Wayback Machine.",
    )
    parser.add_argument(
        "--missing-assets",
        type=Path,
        default=Path("content/_meta/missing-assets.json"),
    )
    parser.add_argument(
        "--site-origin",
        default="https://www.isaackoi.com",
    )
    parser.add_argument(
        "--internal-output-root",
        type=Path,
        default=Path("backups/extracted/joomla-site"),
    )
    parser.add_argument(
        "--external-output-root",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path("content/_meta/wayback-recovery.json"),
    )
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--sleep-seconds", type=float, default=0.25)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    missing_assets = load_json(args.missing_assets)
    report = recover_assets(
        missing_assets=missing_assets,
        site_origin=args.site_origin,
        internal_output_root=args.internal_output_root,
        external_output_root=args.external_output_root or args.internal_output_root,
        timeout=args.timeout,
        sleep_seconds=args.sleep_seconds,
    )
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "Recovered",
        report["counts"]["saved_internal_or_external"],
        "assets from Wayback with",
        report["counts"]["unavailable"],
        "unavailable and",
        report["counts"]["errors"],
        "errors.",
    )


if __name__ == "__main__":
    main()
