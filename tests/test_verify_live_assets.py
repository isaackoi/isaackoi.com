from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "verify_live_assets.py"
SPEC = importlib.util.spec_from_file_location("verify_live_assets", MODULE_PATH)
assert SPEC and SPEC.loader
verify_live_assets = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verify_live_assets
SPEC.loader.exec_module(verify_live_assets)


class VerifyLiveAssetsTests(unittest.TestCase):
    def test_build_live_page_lookup_prefers_article_html_routes(self) -> None:
        items = [
            {
                "source_id": 1413,
                "original_url": "/ufog/alien-photos/koi-alien-photo-57",
            }
        ]
        categories = []
        legacy_routes = [
            {
                "sefurl": "alien-photos/koi-alien-photo-57.html",
                "target_path": "/alien-photos/koi-alien-photo-57",
                "origurl": "index.php?option=com_content&catid=25&id=1413&view=article",
                "route_type": "com_content_article",
            },
            {
                "sefurl": "alien-photos/koi-alien-photo-57/atom.html",
                "target_path": "/alien-photos/koi-alien-photo-57/atom",
                "origurl": "index.php?option=com_content&format=feed&id=1413&type=atom&view=article",
                "route_type": "com_content_article",
            },
        ]

        lookup = verify_live_assets.build_live_page_lookup(
            items,
            categories,
            legacy_routes,
            "https://www.isaackoi.com",
        )

        self.assertEqual(
            lookup[1413][0],
            "https://www.isaackoi.com/alien-photos/koi-alien-photo-57.html",
        )

    def test_normalize_asset_reference_handles_internal_and_external_paths(self) -> None:
        self.assertEqual(
            verify_live_assets.normalize_asset_reference(
                "images/stories/ufo_videos/video076_10.JPG",
                "https://www.isaackoi.com",
            ),
            "https://www.isaackoi.com/images/stories/ufo_videos/video076_10.JPG",
        )
        self.assertEqual(
            verify_live_assets.normalize_asset_reference(
                "www.cassiopaea.org/cass/Varo-Jessup.PdF",
                "https://www.isaackoi.com",
            ),
            "http://www.cassiopaea.org/cass/Varo-Jessup.PdF",
        )


if __name__ == "__main__":
    unittest.main()
