from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_wayback_external_link_rewrites.py"
SPEC = importlib.util.spec_from_file_location("build_wayback_external_link_rewrites", MODULE_PATH)
assert SPEC and SPEC.loader
build_wayback_external_link_rewrites = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_wayback_external_link_rewrites
SPEC.loader.exec_module(build_wayback_external_link_rewrites)


class BuildWaybackExternalLinkRewritesTests(unittest.TestCase):
    def test_fetch_wayback_rows_with_retries_retries_transient_failure(self) -> None:
        calls = {"count": 0}
        original_fetch = build_wayback_external_link_rewrites.fetch_wayback_rows
        original_sleep = build_wayback_external_link_rewrites.time.sleep
        try:
            def flaky_fetch(url: str, timeout: int) -> list[list[str]]:
                calls["count"] += 1
                if calls["count"] == 1:
                    raise TimeoutError("transient")
                return [["20090102120000", "http://example.com/page.html", "200", "text/html"]]

            build_wayback_external_link_rewrites.fetch_wayback_rows = flaky_fetch
            build_wayback_external_link_rewrites.time.sleep = lambda seconds: None
            rows = build_wayback_external_link_rewrites.fetch_wayback_rows_with_retries(
                "http://example.com/page.html",
                timeout=5,
                retries=2,
                sleep_seconds=0.1,
            )
        finally:
            build_wayback_external_link_rewrites.fetch_wayback_rows = original_fetch
            build_wayback_external_link_rewrites.time.sleep = original_sleep

        self.assertEqual(calls["count"], 2)
        self.assertEqual(rows[0][0], "20090102120000")

    def test_choose_capture_prefers_nearest_in_window(self) -> None:
        chosen, preferred_window = build_wayback_external_link_rewrites.choose_capture(
            [
                ["20070101221051", "http://www.daviddarling.info:80/encyclopedia/C/CUFOS.html", "200", "text/html"],
                ["20090102120000", "http://www.daviddarling.info:80/encyclopedia/C/CUFOS.html", "200", "text/html"],
                ["20110501120000", "http://www.daviddarling.info:80/encyclopedia/C/CUFOS.html", "200", "text/html"],
            ],
            preferred_timestamp="20100101",
            from_year=2008,
            to_year=2012,
        )
        self.assertTrue(preferred_window)
        self.assertEqual(chosen["timestamp"], "20090102120000")

    def test_choose_capture_falls_back_to_nearest_overall(self) -> None:
        chosen, preferred_window = build_wayback_external_link_rewrites.choose_capture(
            [
                ["20060102120000", "http://example.com/page.html", "200", "text/html"],
                ["20190102120000", "http://example.com/page.html", "200", "text/html"],
            ],
            preferred_timestamp="20100101",
            from_year=2008,
            to_year=2012,
        )
        self.assertFalse(preferred_window)
        self.assertEqual(chosen["timestamp"], "20060102120000")

    def test_build_rewrites_uses_cdx_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_path = root / "dead-links-report.json"
            output_path = root / "external-link-rewrites.json"
            report = {
                "external": {
                    "dead": [
                        {
                            "url": "http://www.daviddarling.info/encyclopedia/C/CUFOS.html",
                            "host": "www.daviddarling.info",
                            "occurrences": 3,
                        }
                    ]
                }
            }
            report_path.write_text(json.dumps(report), encoding="utf-8")

            original_fetch = build_wayback_external_link_rewrites.fetch_wayback_rows
            try:
                build_wayback_external_link_rewrites.fetch_wayback_rows = lambda url, timeout: [
                    ["20070101221051", "http://www.daviddarling.info:80/encyclopedia/C/CUFOS.html", "200", "text/html"]
                ]
                summary = build_wayback_external_link_rewrites.build_rewrites(
                    dead_report_path=report_path,
                    output_path=output_path,
                    hosts={"www.daviddarling.info"},
                    preferred_timestamp="20100101",
                    from_year=2008,
                    to_year=2012,
                    timeout=5,
                    retries=0,
                    sleep_seconds=0,
                )
            finally:
                build_wayback_external_link_rewrites.fetch_wayback_rows = original_fetch

            rows = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["stats"]["rewritten_urls"], 1)
            self.assertEqual(summary["stats"]["preferred_window_urls"], 0)
            self.assertEqual(rows[0]["replacement_url"], "https://web.archive.org/web/20070101221051/http://www.daviddarling.info:80/encyclopedia/C/CUFOS.html")

    def test_build_rewrites_preserves_manual_non_wayback_rows_for_same_host(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            report_path = root / "dead-links-report.json"
            output_path = root / "external-link-rewrites.json"
            report = {
                "external": {
                    "dead": [
                        {
                            "url": "http://www.daviddarling.info/encyclopedia/C/CUFOS.html",
                            "host": "www.daviddarling.info",
                            "occurrences": 3,
                        }
                    ]
                }
            }
            report_path.write_text(json.dumps(report), encoding="utf-8")
            output_path.write_text(
                json.dumps(
                    [
                        {
                            "original_url": "http://www.daviddarling.info/encyclopedia/D/DrakeE.html",
                            "replacement_url": "https://www.daviddarling.info/encyclopedia/D/DrakeEq.html",
                            "host": "www.daviddarling.info",
                            "occurrences": 1,
                            "snapshot_timestamp": "",
                            "preferred_window": False,
                            "source": "manual_live",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            original_fetch = build_wayback_external_link_rewrites.fetch_wayback_rows
            try:
                build_wayback_external_link_rewrites.fetch_wayback_rows = lambda url, timeout: [
                    ["20070101221051", "http://www.daviddarling.info:80/encyclopedia/C/CUFOS.html", "200", "text/html"]
                ]
                build_wayback_external_link_rewrites.build_rewrites(
                    dead_report_path=report_path,
                    output_path=output_path,
                    hosts={"www.daviddarling.info"},
                    preferred_timestamp="20100101",
                    from_year=2008,
                    to_year=2012,
                    timeout=5,
                    retries=0,
                    sleep_seconds=0,
                )
            finally:
                build_wayback_external_link_rewrites.fetch_wayback_rows = original_fetch

            rows = json.loads(output_path.read_text(encoding="utf-8"))
            original_urls = {row["original_url"] for row in rows}
            self.assertIn("http://www.daviddarling.info/encyclopedia/D/DrakeE.html", original_urls)
            self.assertIn("http://www.daviddarling.info/encyclopedia/C/CUFOS.html", original_urls)


if __name__ == "__main__":
    unittest.main()
