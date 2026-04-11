from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_static_site.py"
SPEC = importlib.util.spec_from_file_location("build_static_site", MODULE_PATH)
assert SPEC and SPEC.loader
build_static_site = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_static_site
SPEC.loader.exec_module(build_static_site)


class StaticSiteBuildTests(unittest.TestCase):
    def test_build_site_writes_articles_indexes_tags_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content_root = root / "content"
            meta_root = content_root / "_meta"
            assets_root = content_root / "assets" / "source" / "images"
            template_root = root / "templates" / "static-preview" / "assets"
            output_root = root / "site"
            meta_root.mkdir(parents=True)
            assets_root.mkdir(parents=True)
            (template_root / "css").mkdir(parents=True)
            (template_root / "js").mkdir(parents=True)

            manifest = [
                {
                    "source_id": 1,
                    "title": "Hello World",
                    "summary": "Short intro",
                    "body": '<p>See <a href="/tags/seti">SETI</a>.</p><table class="sortable"><tr><th>Name</th></tr><tr><td>Hello</td></tr></table>',
                    "status": "published",
                    "category": "Updates",
                    "asset_resolution": {"missing": []},
                    "original_url": "/news/hello-world",
                    "updated_at": "2024-01-02 08:00:00",
                    "author": "Site Admin",
                },
                {
                    "source_id": 2,
                    "title": "Second Page",
                    "summary": "Another intro",
                    "body": '<p><a href="/tags/1947">1947</a></p>',
                    "status": "published",
                    "category": "Updates",
                    "asset_resolution": {"missing": ["images/missing.jpg"]},
                    "original_url": "/news/second-page",
                    "updated_at": "2024-01-03 08:00:00",
                    "author": None,
                },
            ]
            report = {
                "normalized_counts": {"content_items": 2},
                "asset_counts": {"resolved": 1, "missing": 1},
                "template_inventory": {"template_count": 1},
            }
            categories = [
                {
                    "id": 3,
                    "title": "Updates",
                    "path": "news",
                    "extension": "com_content",
                    "published": 1,
                }
            ]
            legacy_routes = [
                {
                    "sefurl": "hello-world.html",
                    "target_path": "/hello-world",
                    "origurl": "index.php?option=com_content&view=article&id=1:hello-world&catid=3",
                    "route_type": "com_content_article",
                    "enabled": 1,
                },
                {
                    "sefurl": "updates.html",
                    "target_path": "/updates",
                    "origurl": "index.php?option=com_content&view=category&id=3",
                    "route_type": "com_content_category",
                    "enabled": 1,
                },
                {
                    "sefurl": "tags/seti.html",
                    "target_path": "/tags/seti",
                    "origurl": "index.php?option=com_tags&id=100&view=tag",
                    "route_type": "com_tags",
                    "enabled": 1,
                },
            ]
            redirects = [
                {
                    "source": "/old-page.html",
                    "destination": "/news/hello-world",
                }
            ]

            (meta_root / "content-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (meta_root / "extraction-report.json").write_text(json.dumps(report), encoding="utf-8")
            (meta_root / "category-index.json").write_text(json.dumps(categories), encoding="utf-8")
            (meta_root / "legacy-routes.json").write_text(json.dumps(legacy_routes), encoding="utf-8")
            (meta_root / "redirects.json").write_text(json.dumps(redirects), encoding="utf-8")
            (assets_root / "hello.jpg").write_text("asset", encoding="utf-8")
            (template_root / "css" / "site.css").write_text("body { color: black; }", encoding="utf-8")
            (template_root / "js" / "table-sort.js").write_text("console.log('sort');", encoding="utf-8")

            result = build_static_site.build_site(
                content_root=content_root,
                output_root=output_root,
                template_root=root / "templates" / "static-preview",
            )

            self.assertEqual(result["article_pages"], 2)
            self.assertEqual(result["category_pages"], 1)
            self.assertEqual(result["tag_pages"], 2)
            self.assertEqual(result["redirect_pages"], 4)
            self.assertTrue((output_root / ".nojekyll").exists())
            self.assertTrue((output_root / "index.html").exists())
            self.assertTrue((output_root / "news" / "hello-world" / "index.html").exists())
            self.assertTrue((output_root / "news" / "index.html").exists())
            self.assertTrue((output_root / "tags" / "seti" / "index.html").exists())
            self.assertTrue((output_root / "sitemap" / "index.html").exists())
            self.assertTrue((output_root / "images" / "hello.jpg").exists())
            self.assertTrue((output_root / "assets" / "css" / "site.css").exists())
            self.assertTrue((output_root / "assets" / "js" / "table-sort.js").exists())
            self.assertTrue((output_root / "hello-world.html").exists())
            self.assertTrue((output_root / "updates.html").exists())
            self.assertTrue((output_root / "tags" / "seti.html").exists())
            self.assertTrue((output_root / "old-page.html").exists())

            article_html = (output_root / "news" / "hello-world" / "index.html").read_text(encoding="utf-8")
            self.assertIn('data-sortable', article_html)
            self.assertIn("Source ID 1", article_html)
            self.assertIn("More In Updates", article_html)

            redirect_html = (output_root / "hello-world.html").read_text(encoding="utf-8")
            self.assertIn("/news/hello-world", redirect_html)


if __name__ == "__main__":
    unittest.main()
