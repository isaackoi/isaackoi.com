from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "recover_wayback_assets.py"
SPEC = importlib.util.spec_from_file_location("recover_wayback_assets", MODULE_PATH)
assert SPEC and SPEC.loader
recover_wayback_assets = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = recover_wayback_assets
SPEC.loader.exec_module(recover_wayback_assets)


class RecoverWaybackAssetsTests(unittest.TestCase):
    def test_normalize_asset_url_handles_internal_and_external_refs(self) -> None:
        self.assertEqual(
            recover_wayback_assets.normalize_asset_url(
                "images/stories/ufo_videos/video076_10.JPG",
                "https://www.isaackoi.com",
            ),
            "https://www.isaackoi.com/images/stories/ufo_videos/video076_10.JPG",
        )
        self.assertEqual(
            recover_wayback_assets.normalize_asset_url(
                "www.cassiopaea.org/cass/Varo-Jessup.PdF",
                "https://www.isaackoi.com",
            ),
            "http://www.cassiopaea.org/cass/Varo-Jessup.PdF",
        )

    def test_output_paths_match_expected_storage_layout(self) -> None:
        internal = recover_wayback_assets.internal_output_path(
            "images/stories/ufo_videos/video076_10.JPG",
            Path("backups/extracted/joomla-site"),
        )
        self.assertEqual(
            internal.as_posix(),
            "backups/extracted/joomla-site/images/stories/ufo_videos/video076_10.JPG",
        )

        external = recover_wayback_assets.external_output_path(
            "http://www.cassiopaea.org/cass/Varo-Jessup.PdF",
            Path("backups/extracted/external-assets"),
        )
        self.assertEqual(
            external.as_posix(),
            "backups/extracted/external-assets/www.cassiopaea.org/cass/Varo-Jessup.PdF",
        )

    def test_choose_capture_prefers_latest_timestamp(self) -> None:
        capture = recover_wayback_assets.choose_capture(
            [
                ["20150722070453", "http://example.com/a.jpg", "200", "image/jpeg"],
                ["20160722070453", "http://example.com/a.jpg", "200", "image/jpeg"],
            ]
        )
        self.assertEqual(capture["timestamp"], "20160722070453")


if __name__ == "__main__":
    unittest.main()
