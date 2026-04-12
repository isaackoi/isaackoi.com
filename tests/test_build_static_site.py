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
    def test_known_bad_link_normalization_and_body_sanitization(self) -> None:
        self.assertEqual(
            build_static_site.normalize_html_url("documents/chronology/example.pdf"),
            "/documents/chronology/example.pdf",
        )
        self.assertEqual(
            build_static_site.normalize_html_url("wiki/Arthur_Tedder,_1st_Baron_Tedder"),
            "https://en.wikipedia.org/wiki/Arthur_Tedder,_1st_Baron_Tedder",
        )
        self.assertEqual(build_static_site.normalize_html_url("undefined/"), "/")
        self.assertEqual(
            build_static_site.normalize_html_url(
                'As far as I can tell, "Beings" ... http:/www.imdb.com/title/tt0824290/ ...'
            ),
            "https://www.imdb.com/title/tt0824290/",
        )

        rockefeller_body = build_static_site.sanitize_article_body(
            '<p><a href="v">Pascagoula Mississippi Case</a></p>',
            "/ufog/best-ufo-cases/11-consensus-lists-the-rockefeller-briefing-document",
        )
        self.assertIn('href="/ufo-history/ufo/19731011-pascagoula-abduction"', rockefeller_body)

        video_body = build_static_site.sanitize_article_body(
            '<p><a href="/ufog/alien-photos/koi-alien-photo-34">a dummy in a well-known display at the UFO museum in Roswell</a></p>',
            "/ufog/ufo-videos/koi-ufo-video-070",
        )
        self.assertNotIn('href="/ufog/alien-photos/koi-alien-photo-34"', video_body)
        self.assertIn("a dummy in a well-known display at the UFO museum in Roswell", video_body)

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
                    "body": (
                        '<p>See <a href="/tags/seti">SETI</a>.</p>'
                        '<p><a href="toolbar.google.com">Google Toolbar</a></p>'
                        '<p><a href="www.cufos.org">CUFOS</a></p>'
                        '<p><a href="Search.html?ordering=0&searchword=king">Search</a></p>'
                        '<p><a href="http://www.project1947.com/shg/condon/contents.html">Condon</a></p>'
                        '<p><a href="http://www.cia.gov/csi/studies/97unclass/ufo.html#ft7">CIA</a></p>'
                        '<p><a href="best-ufo-cases/13-the-top-100-ufo-cases.html%20\'">Top 100</a></p>'
                        '<table class="sortable"><tr><th>Name</th></tr><tr><td>Hello</td></tr></table>'
                    ),
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
                    "body": '<p><a href="/tags/1947">1947</a></p><p><a href="vhttp://example.com/credits">Credits</a></p>',
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
                    "parent_id": 1,
                },
                {
                    "id": 56,
                    "title": "UFO",
                    "path": "ufog",
                    "extension": "com_content",
                    "published": 1,
                    "parent_id": 1,
                },
                {
                    "id": 47,
                    "title": "UFO",
                    "path": "ufog/ufoc",
                    "extension": "com_content",
                    "published": 1,
                    "parent_id": 56,
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
                {
                    "sefurl": "ufog.html",
                    "target_path": "/ufog",
                    "origurl": "index.php?option=com_content&id=56&view=category",
                    "route_type": "com_content_category",
                    "enabled": 1,
                },
                {
                    "sefurl": "ufoc.html",
                    "target_path": "/ufoc",
                    "origurl": "index.php?option=com_content&id=47&view=category",
                    "route_type": "com_content_category",
                    "enabled": 1,
                },
            ]
            redirects = [
                {
                    "source": "/old-page.html",
                    "destination": "/news/hello-world",
                }
            ]
            external_link_rewrites = [
                {
                    "original_url": "http://www.project1947.com/shg/condon/contents.html",
                    "replacement_url": "https://web.archive.org/web/20100101000000/http://www.project1947.com/shg/condon/contents.html",
                    "host": "www.project1947.com",
                    "occurrences": 1,
                    "snapshot_timestamp": "20100101000000",
                    "preferred_window": True,
                    "source": "wayback",
                }
            ]

            (meta_root / "content-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (meta_root / "extraction-report.json").write_text(json.dumps(report), encoding="utf-8")
            (meta_root / "category-index.json").write_text(json.dumps(categories), encoding="utf-8")
            (meta_root / "legacy-routes.json").write_text(json.dumps(legacy_routes), encoding="utf-8")
            (meta_root / "redirects.json").write_text(json.dumps(redirects), encoding="utf-8")
            (meta_root / "external-link-rewrites.json").write_text(json.dumps(external_link_rewrites), encoding="utf-8")
            (assets_root / "hello.jpg").write_text("asset", encoding="utf-8")
            (template_root / "css" / "site.css").write_text("body { color: black; }", encoding="utf-8")
            (template_root / "js" / "table-sort.js").write_text("console.log('sort');", encoding="utf-8")
            (template_root / "js" / "archive-search.js").write_text("console.log('search');", encoding="utf-8")

            result = build_static_site.build_site(
                content_root=content_root,
                output_root=output_root,
                template_root=root / "templates" / "static-preview",
            )

            self.assertEqual(result["article_pages"], 2)
            self.assertEqual(result["category_pages"], 3)
            self.assertEqual(result["tag_pages"], 2)
            self.assertEqual(result["redirect_pages"], 6)
            self.assertTrue((output_root / ".nojekyll").exists())
            self.assertTrue((output_root / "index.html").exists())
            self.assertTrue((output_root / "news" / "hello-world" / "index.html").exists())
            self.assertTrue((output_root / "news" / "index.html").exists())
            self.assertTrue((output_root / "ufog" / "index.html").exists())
            self.assertTrue((output_root / "ufog" / "ufoc" / "index.html").exists())
            self.assertTrue((output_root / "tags" / "seti" / "index.html").exists())
            self.assertTrue((output_root / "sitemap" / "index.html").exists())
            self.assertTrue((output_root / "images" / "hello.jpg").exists())
            self.assertTrue((output_root / "assets" / "css" / "site.css").exists())
            self.assertTrue((output_root / "assets" / "js" / "table-sort.js").exists())
            self.assertTrue((output_root / "assets" / "js" / "archive-search.js").exists())
            self.assertTrue((output_root / "hello-world.html").exists())
            self.assertTrue((output_root / "updates.html").exists())
            self.assertTrue((output_root / "ufog.html").exists())
            self.assertTrue((output_root / "ufoc.html").exists())
            self.assertTrue((output_root / "tags" / "seti.html").exists())
            self.assertTrue((output_root / "old-page.html").exists())
            self.assertTrue((output_root / "search" / "index.html").exists())
            self.assertTrue((output_root / "search-index.json").exists())

            article_html = (output_root / "news" / "hello-world" / "index.html").read_text(encoding="utf-8")
            self.assertIn('data-sortable', article_html)
            self.assertIn("Source ID 1", article_html)
            self.assertIn("More In Updates", article_html)
            self.assertIn('href="/search/"', article_html)
            self.assertIn('href="http://toolbar.google.com"', article_html)
            self.assertIn('href="http://www.cufos.org"', article_html)
            self.assertIn('href="/search/?q=king"', article_html)
            self.assertIn('href="https://web.archive.org/web/20100101000000/http://www.project1947.com/shg/condon/contents.html"', article_html)
            self.assertIn('href="http://www.cia.gov/csi/studies/97unclass/ufo.html#ft7"', article_html)
            self.assertNotIn('href="/shg/condon/contents"', article_html)
            self.assertIn('href="/ufog/best-ufo-cases/13-the-top-100-ufo-cases"', article_html)

            second_article_html = (output_root / "news" / "second-page" / "index.html").read_text(encoding="utf-8")
            self.assertIn('href="http://example.com/credits"', second_article_html)

            ufog_html = (output_root / "ufog" / "index.html").read_text(encoding="utf-8")
            self.assertIn("child sections", ufog_html)
            self.assertIn('href="/ufog/ufoc"', ufog_html)

            search_html = (output_root / "search" / "index.html").read_text(encoding="utf-8")
            self.assertIn("<!doctype html>", search_html)
            self.assertIn("Search the archive", search_html)
            self.assertIn('data-search-source="/search-index.json"', search_html)
            self.assertIn('data-archive-search-results', search_html)
            self.assertIn('/assets/js/archive-search.js', search_html)

            search_index = json.loads((output_root / "search-index.json").read_text(encoding="utf-8"))
            self.assertTrue(any(row["url"] == "/news/hello-world" for row in search_index if row["kind"] == "page"))
            self.assertTrue(any(row["url"] == "/tags/seti" for row in search_index if row["kind"] == "tag"))

            redirect_html = (output_root / "hello-world.html").read_text(encoding="utf-8")
            self.assertIn("/news/hello-world", redirect_html)
            ufoc_redirect_html = (output_root / "ufoc.html").read_text(encoding="utf-8")
            self.assertIn("/ufog/ufoc", ufoc_redirect_html)


if __name__ == "__main__":
    unittest.main()
