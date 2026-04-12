from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "build_jekyll_site.py"
SPEC = importlib.util.spec_from_file_location("build_jekyll_site", MODULE_PATH)
assert SPEC and SPEC.loader
build_jekyll_site = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = build_jekyll_site
SPEC.loader.exec_module(build_jekyll_site)


class JekyllSiteBuildTests(unittest.TestCase):
    def test_render_category_page_truncates_large_card_sets(self) -> None:
        children = [
            {
                "title": f"Page {index}",
                "url": f"/section/page-{index}",
                "summary": f"Summary {index}",
                "kicker": "Page",
                "level": 3,
            }
            for index in range(build_jekyll_site.MAX_RENDERED_CATEGORY_CARDS + 5)
        ]

        rendered = build_jekyll_site.render_category_page(
            route="/example/large-section",
            title="Large Section",
            description="Many pages.",
            children=children,
            level_kicker="Subsection",
        )

        self.assertIn("Showing the first", rendered)
        self.assertIn(f"of {len(children)} pages in this section.", rendered)
        self.assertEqual(rendered.count('<article class="topic-card '), build_jekyll_site.MAX_RENDERED_CATEGORY_CARDS)

    def test_render_tag_page_truncates_large_card_sets(self) -> None:
        items = [
            {
                "title": f"Tagged {index}",
                "url": f"/tags/example/page-{index}",
                "category": "Example",
            }
            for index in range(build_jekyll_site.MAX_RENDERED_TAG_CARDS + 5)
        ]

        rendered = build_jekyll_site.render_tag_page(
            {"label": "Example", "count": len(items), "items": items}
        )

        self.assertIn("Showing the first", rendered)
        self.assertIn(f"of {len(items)} tagged pages.", rendered)
        self.assertEqual(rendered.count('<article class="topic-card '), build_jekyll_site.MAX_RENDERED_TAG_CARDS)

    def test_html_to_markdown_fragment_cleans_jce_caption_and_anchors(self) -> None:
        html = (
            '<div class="jce_caption" style="margin: 5px;"><a href="/example">'
            '<img src="images/example.jpg" alt="image_needed" /></a>'
            '<div style="clear: both;">Example caption</div></div>'
            '<p><strong>1993<a name="webner"></a></strong></p>'
            '<p><a name="solo"></a></p>'
        )

        markdown = build_jekyll_site.html_to_markdown_fragment(html)

        self.assertIn("![]({{ '/images/example.jpg' | relative_url }})", markdown)
        self.assertIn("*Example caption*", markdown)
        self.assertNotIn("jce_caption", markdown)
        self.assertIn('<a id="webner"></a>**1993**', markdown)
        self.assertIn('<a id="solo"></a>', markdown)

    def test_html_to_markdown_fragment_marks_data_tables_sortable(self) -> None:
        html = (
            "<table border=\"1\">"
            "<tr><td>Year</td><td>Pages</td></tr>"
            "<tr><td>1989</td><td>3</td></tr>"
            "</table>"
        )

        markdown = build_jekyll_site.html_to_markdown_fragment(html)

        self.assertIn('class="sortable"', markdown)
        self.assertIn('data-sortable="true"', markdown)

    def test_html_to_markdown_fragment_rootifies_local_asset_paths(self) -> None:
        html = (
            '<p><img src="images/example.jpg" alt="Example"></p>'
            '<p><a href="documents/example.pdf">PDF</a></p>'
            '<table><tr><td><img src="images/table.jpg" alt="Table"></td></tr></table>'
        )

        markdown = build_jekyll_site.html_to_markdown_fragment(html)

        self.assertIn("![Example]({{ '/images/example.jpg' | relative_url }})", markdown)
        self.assertIn("[PDF]({{ '/documents/example.pdf' | relative_url }})", markdown)
        self.assertIn('src="{{ \'/images/table.jpg\' | relative_url }}"', markdown)

    def test_html_to_markdown_fragment_absolutizes_schemeless_external_links(self) -> None:
        html = (
            '<p><a href="toolbar.google.com">Google Toolbar</a></p>'
            '<p><a href="www.cufos.org">CUFOS</a></p>'
        )

        markdown = build_jekyll_site.html_to_markdown_fragment(html)

        self.assertIn("[Google Toolbar](http://toolbar.google.com)", markdown)
        self.assertIn("[CUFOS](http://www.cufos.org)", markdown)

    def test_html_to_markdown_fragment_canonicalizes_legacy_relative_links(self) -> None:
        html = (
            '<p><a href="best-ufo-cases/13-the-top-100-ufo-cases.html">Top 100</a></p>'
            '<p><a href="Search.html?ordering=0&searchword=king">Search</a></p>'
        )

        markdown = build_jekyll_site.html_to_markdown_fragment(html)

        self.assertIn("[Top 100]({{ '/ufog/best-ufo-cases/13-the-top-100-ufo-cases' | relative_url }})", markdown)
        self.assertIn("[Search]({{ '/search/' | relative_url }}?q=king)", markdown)
        self.assertNotIn("Search.html", markdown)

    def test_book_metadata_extracts_isbn_cover(self) -> None:
        item = {
            "original_url": "/ufo-history/ufo-books/example-book",
            "body": (
                '<iframe src="//ws-na.amazon-adsystem.com/widgets/q?placement=067402401X&asins=0684166550"></iframe>'
                '<a href="http://www.amazon.com/dp/0684166550/?&tag=ufot-20">Amazon USA</a>'
            ),
        }

        book = build_jekyll_site.build_book_metadata(item)

        self.assertIsNotNone(book)
        assert book is not None
        self.assertEqual(book["identifiers"][:2], ["0684166550", "067402401X"])
        self.assertEqual(book["primary_isbn"], "0684166550")
        self.assertEqual(
            book["cover_image"],
            "https://covers.openlibrary.org/b/isbn/0684166550-L.jpg?default=false",
        )

    def test_book_metadata_prefers_local_cached_cover(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_root = Path(temp_dir)
            cache_root = content_root / "assets" / "source" / "book-covers"
            cache_root.mkdir(parents=True)
            (cache_root / "0684166550.jpg").write_bytes(b"cover")

            item = {
                "original_url": "/ufo-history/ufo-books/example-book",
                "body": '<a href="http://www.amazon.com/dp/0684166550/?&tag=ufot-20">Amazon USA</a>',
            }

            book = build_jekyll_site.build_book_metadata(item, content_root=content_root)

            self.assertIsNotNone(book)
            assert book is not None
            self.assertEqual(book["cover_image"], "/book-covers/0684166550.jpg")
            self.assertEqual(book["cover_source"], "local-cache")

    def test_book_metadata_uses_alternate_cached_identifier(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            content_root = Path(temp_dir)
            cache_root = content_root / "assets" / "source" / "book-covers"
            cache_root.mkdir(parents=True)
            (cache_root / "067402401X.jpg").write_bytes(b"cover")

            item = {
                "original_url": "/ufo-history/ufo-books/example-book",
                "body": '<a href="http://www.amazon.com/dp/0684166550/?&tag=ufot-20">Amazon USA</a>'
                        '<a href="http://www.amazon.com/dp/067402401X/?&tag=ufot-20">Amazon Alt</a>',
            }

            book = build_jekyll_site.build_book_metadata(item, content_root=content_root)

            self.assertIsNotNone(book)
            assert book is not None
            self.assertEqual(book["primary_isbn"], "0684166550")
            self.assertEqual(book["cover_image"], "/book-covers/067402401X.jpg")
            self.assertEqual(book["cover_source"], "local-cache")

    def test_book_metadata_falls_back_to_placeholder_for_asin_only_books(self) -> None:
        item = {
            "original_url": "/ufo-history/ufo-books/example-book",
            "body": '<a href="http://www.amazon.com/dp/B000S2L0EK/?&tag=ufot-20">Amazon USA</a>',
        }

        book = build_jekyll_site.build_book_metadata(item)

        self.assertIsNotNone(book)
        assert book is not None
        self.assertEqual(book["identifiers"], ["B000S2L0EK"])
        self.assertEqual(book["cover_image"], build_jekyll_site.BOOK_COVER_PLACEHOLDER_URL)
        self.assertEqual(book["cover_source"], "placeholder")

    def test_book_metadata_falls_back_to_placeholder_when_no_identifiers_found(self) -> None:
        item = {
            "original_url": "/ufo-history/ufo-books/example-book",
            "body": "<p>No Amazon identifiers here.</p>",
        }

        book = build_jekyll_site.build_book_metadata(item)

        self.assertIsNotNone(book)
        assert book is not None
        self.assertEqual(book["identifiers"], [])
        self.assertEqual(book["cover_image"], build_jekyll_site.BOOK_COVER_PLACEHOLDER_URL)
        self.assertEqual(book["cover_source"], "placeholder")

    def test_build_site_repairs_mojibake_and_uses_public_navigation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content_root = root / "content"
            meta_root = content_root / "_meta"
            assets_root = content_root / "assets" / "source" / "images"
            template_root = root / "templates" / "jekyll-phoenix-theme"
            output_root = root / "jekyll-site"
            meta_root.mkdir(parents=True)
            assets_root.mkdir(parents=True)
            (template_root / "_includes").mkdir(parents=True)
            (template_root / "_layouts").mkdir(parents=True)
            (template_root / "assets" / "css").mkdir(parents=True)
            (template_root / "assets" / "js").mkdir(parents=True)

            bad_title = "Valleeâ€™s Study"
            bad_summary = "A review of Hynek â€“ Strangeness and related material."
            bad_body = (
                '<iframe src="//ws-na.amazon-adsystem.com/widgets/q?placement=123456789X&asins=1234567890"></iframe>'
                '<p>Valleeâ€™s note includes Hynek â€“ terminology.</p>'
                '<a href="http://www.amazon.com/dp/1234567890/?&tag=ufot-20">Amazon USA</a>'
            )

            manifest = [
                {
                    "source_id": 1,
                    "title": "Homepage",
                    "summary": "Intro to the archive.",
                    "body": "<p>Welcome.</p>",
                    "status": "published",
                    "original_url": "/homepage",
                    "updated_at": "2024-01-01 09:00:00",
                    "asset_resolution": {"resolved": [], "missing": []},
                },
                {
                    "source_id": 2,
                    "title": bad_title,
                    "summary": bad_summary,
                    "body": bad_body,
                    "status": "published",
                    "original_url": "/ufo-history/ufo-books/vallee-study",
                    "updated_at": "2024-01-02 09:00:00",
                    "asset_resolution": {"resolved": ["images/cover.jpg"], "missing": []},
                },
                {
                    "source_id": 3,
                    "title": "Admin Search",
                    "summary": "Should not be exported",
                    "body": "<p>Admin only</p>",
                    "status": "published",
                    "original_url": "/other/admin/search-results",
                    "updated_at": "2024-01-03 09:00:00",
                    "asset_resolution": {"resolved": [], "missing": []},
                },
            ]
            categories = [
                {"id": 1, "title": "ROOT", "path": "", "extension": "system", "published": 1, "parent_id": 0},
                {"id": 61, "title": "Other", "path": "other", "extension": "com_content", "published": 1, "parent_id": 1},
                {"id": 57, "title": "UFO History", "path": "ufo-history", "extension": "com_content", "published": 1, "parent_id": 1},
                {"id": 36, "title": "UFO Books", "path": "ufo-history/ufo-books", "extension": "com_content", "published": 1, "parent_id": 57},
            ]
            tags = [
                {
                    "slug": "books",
                    "label": "Books",
                    "count": 1,
                    "items": [
                        {
                            "source_id": 2,
                            "title": "Vallee’s Study",
                            "url": "/ufo-history/ufo-books/vallee-study",
                            "category": "UFO Books",
                        }
                    ],
                }
            ]
            public_nav = [
                {"title": "Home", "route": "/homepage"},
                {"title": "UFO History", "route": "/ufo-history"},
                {"title": "UFO Books", "route": "/ufo-history/ufo-books"},
                {"title": "Tags", "route": "/tags"},
            ]

            (meta_root / "content-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (meta_root / "category-index.json").write_text(json.dumps(categories), encoding="utf-8")
            (meta_root / "tags-index.json").write_text(json.dumps(tags), encoding="utf-8")
            (meta_root / "homepage-intent.json").write_text("[]", encoding="utf-8")
            (meta_root / "public-nav.json").write_text(json.dumps(public_nav), encoding="utf-8")
            (assets_root / "cover.jpg").write_text("image", encoding="utf-8")

            (template_root / "_includes" / "head.html").write_text("<meta charset=\"utf-8\">", encoding="utf-8")
            (template_root / "_includes" / "header.html").write_text("<header>Header</header>", encoding="utf-8")
            (template_root / "_includes" / "sidebar.html").write_text("<aside>Sidebar</aside>", encoding="utf-8")
            (template_root / "_includes" / "footer.html").write_text("<footer>Footer</footer>", encoding="utf-8")
            (template_root / "_layouts" / "default.html").write_text("{{ content }}", encoding="utf-8")
            (template_root / "assets" / "css" / "main.css").write_text("body { color: black; }", encoding="utf-8")
            (template_root / "assets" / "js" / "page-enhancements.js").write_text("console.log('enhance');", encoding="utf-8")
            (template_root / "assets" / "js" / "theme-toggle.js").write_text("console.log('theme');", encoding="utf-8")
            (template_root / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
            (template_root / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")

            result = build_jekyll_site.build_site(
                content_root=content_root,
                output_root=output_root,
                template_root=template_root,
                site_url="https://isaackoi.github.io",
                site_baseurl="/isaackoi.com",
            )

            self.assertEqual(result["article_pages"], 2)
            self.assertEqual(result["category_pages"], 2)
            self.assertEqual(result["tag_pages"], 2)

            article_text = (output_root / "pages" / "ufo-history" / "ufo-books" / "vallee-study.md").read_text(encoding="utf-8")
            self.assertIn("Vallee’s Study", article_text)
            self.assertIn("Hynek – Strangeness", article_text)
            self.assertIn("Vallee’s note includes Hynek – terminology.", article_text)
            self.assertIn("https://covers.openlibrary.org/b/isbn/1234567890-L.jpg?default=false", article_text)
            self.assertIn('header: {"preview_image": "/images/cover.jpg"}', article_text)
            self.assertNotIn("<p>", article_text)
            self.assertNotIn("<iframe", article_text)
            self.assertFalse((output_root / "pages" / "other" / "admin" / "search-results.md").exists())

            home_text = (output_root / "index.html").read_text(encoding="utf-8")
            self.assertIn("UFO History", home_text)
            self.assertNotIn("Other", home_text)
            self.assertIn("Isaac Koi Archive", home_text)
            self.assertIn("{{ '/search' | relative_url }}", home_text)
            self.assertIn("Start with the Starter Pack", home_text)
            self.assertNotIn("/other/articles/coming-soon", home_text)
            self.assertNotIn("Jekyll archive prototype", home_text)
            self.assertNotIn("A Jekyll archive prototype for the extracted Isaac Koi website content.", home_text)

            category_text = (output_root / "pages" / "category-ufo-history__ufo-books.html").read_text(encoding="utf-8")
            self.assertIn("child_links_total: 1", category_text)
            self.assertIn("{{ '/ufo-history/ufo-books/vallee-study' | relative_url }}", category_text)
            self.assertIn("A large bibliography and notes branch covering books relevant to UFOs, SETI, skepticism, contact claims, and adjacent topics.", category_text)
            self.assertIn("Search books", category_text)
            search_page_text = (output_root / "pages" / "search.html").read_text(encoding="utf-8")
            self.assertIn('permalink: "/search/"', search_page_text)
            self.assertIn("data-archive-search", search_page_text)
            self.assertIn("{{ '/search-index.json' | relative_url }}", search_page_text)
            search_index = json.loads((output_root / "search-index.json").read_text(encoding="utf-8"))
            self.assertTrue(any(entry["url"] == "/ufo-history/ufo-books/vallee-study" for entry in search_index))
            self.assertTrue(any(entry["url"] == "/search/" or entry["url"] == "/" for entry in search_index))
            page_entry = next(entry for entry in search_index if entry["url"] == "/ufo-history/ufo-books/vallee-study")
            self.assertEqual(page_entry["title_text"], "Vallee’s Study")
            self.assertEqual(page_entry["section_text"], "UFO Books")
            self.assertIn("ufo history ufo books vallee study", page_entry["url_text"])
            self.assertIn("Books", page_entry["tags_text"])
            self.assertIn("Vallee", page_entry["body_text"])
            self.assertIn("hynek", page_entry["summary_text"].lower())
            nav_tree_text = (output_root / "navigation-tree.json").read_text(encoding="utf-8")
            self.assertIn('"url": "/ufo-history"', nav_tree_text)
            self.assertIn('"title_short": "Vallee\\u2019s Study"', nav_tree_text)
            self.assertTrue((output_root / ".github" / "workflows" / "pages.yml").exists())
            self.assertTrue((output_root / "README.md").exists())
            self.assertTrue((output_root / ".gitignore").exists())
            self.assertEqual((output_root / "CNAME").read_text(encoding="utf-8").strip(), "isaackoi.com")
            config_text = (output_root / "_config.yml").read_text(encoding="utf-8")
            self.assertIn('baseurl: "/isaackoi.com"', config_text)
            self.assertIn('url: "https://isaackoi.github.io"', config_text)
            robots_text = (output_root / "robots.txt").read_text(encoding="utf-8")
            self.assertIn("Sitemap: https://isaackoi.github.io/isaackoi.com/sitemap.xml", robots_text)
            self.assertIn("Host: isaackoi.com", robots_text)
            not_found_text = (output_root / "404.html").read_text(encoding="utf-8")
            self.assertIn("permalink: \"/404.html\"", not_found_text)
            self.assertIn("Page not found", not_found_text)
            self.assertIn("{{ '/' | relative_url }}", not_found_text)

            nav_data = json.loads((output_root / "_data" / "navigation.json").read_text(encoding="utf-8"))
            self.assertEqual([node["url"] for node in nav_data["sidebar_generated"]], ["/ufo-history"])
            self.assertEqual(nav_data["sidebar_generated"][0]["children"][0]["url"], "/ufo-history/ufo-books")
            self.assertEqual(nav_data["footer_primary"][1]["url"], "/search")

    def test_build_site_can_filter_by_route_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            content_root = root / "content"
            meta_root = content_root / "_meta"
            assets_root = content_root / "assets" / "source" / "images"
            template_root = root / "templates" / "jekyll-phoenix-theme"
            output_root = root / "jekyll-site"
            meta_root.mkdir(parents=True)
            assets_root.mkdir(parents=True)
            (template_root / "_includes").mkdir(parents=True)
            (template_root / "_layouts").mkdir(parents=True)
            (template_root / "assets" / "css").mkdir(parents=True)
            (template_root / "assets" / "js").mkdir(parents=True)

            manifest = [
                {
                    "source_id": 1,
                    "title": "Homepage",
                    "summary": "Intro to the archive.",
                    "body": "<p>Welcome.</p>",
                    "status": "published",
                    "original_url": "/homepage",
                    "updated_at": "2024-01-01 09:00:00",
                    "asset_resolution": {"resolved": [], "missing": []},
                },
                {
                    "source_id": 2,
                    "title": "Book One",
                    "summary": "Book summary.",
                    "body": "<p>Book body.</p>",
                    "status": "published",
                    "original_url": "/ufo-history/ufo-books/book-one",
                    "updated_at": "2024-01-02 09:00:00",
                    "asset_resolution": {"resolved": [], "missing": []},
                },
                {
                    "source_id": 3,
                    "title": "Timeline Entry",
                    "summary": "Timeline summary.",
                    "body": "<p>Timeline body.</p>",
                    "status": "published",
                    "original_url": "/ufo-history/ufo/19470000-example",
                    "updated_at": "2024-01-03 09:00:00",
                    "asset_resolution": {"resolved": [], "missing": []},
                },
            ]
            categories = [
                {"id": 1, "title": "ROOT", "path": "", "extension": "system", "published": 1, "parent_id": 0},
                {"id": 57, "title": "UFO History", "path": "ufo-history", "extension": "com_content", "published": 1, "parent_id": 1},
                {"id": 36, "title": "UFO Books", "path": "ufo-history/ufo-books", "extension": "com_content", "published": 1, "parent_id": 57},
                {"id": 37, "title": "UFO", "path": "ufo-history/ufo", "extension": "com_content", "published": 1, "parent_id": 57},
            ]
            tags = [
                {
                    "slug": "books",
                    "label": "Books",
                    "count": 1,
                    "items": [{"source_id": 2, "title": "Book One", "url": "/ufo-history/ufo-books/book-one", "category": "UFO Books"}],
                },
                {
                    "slug": "timeline",
                    "label": "Timeline",
                    "count": 1,
                    "items": [{"source_id": 3, "title": "Timeline Entry", "url": "/ufo-history/ufo/19470000-example", "category": "UFO"}],
                },
            ]
            public_nav = [
                {"title": "Home", "route": "/homepage"},
                {"title": "UFO History", "route": "/ufo-history"},
                {"title": "UFO Books", "route": "/ufo-history/ufo-books"},
                {"title": "UFO", "route": "/ufo-history/ufo"},
                {"title": "Tags", "route": "/tags"},
            ]

            (meta_root / "content-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (meta_root / "category-index.json").write_text(json.dumps(categories), encoding="utf-8")
            (meta_root / "tags-index.json").write_text(json.dumps(tags), encoding="utf-8")
            (meta_root / "homepage-intent.json").write_text("[]", encoding="utf-8")
            (meta_root / "public-nav.json").write_text(json.dumps(public_nav), encoding="utf-8")

            (template_root / "_includes" / "head.html").write_text("<meta charset=\"utf-8\">", encoding="utf-8")
            (template_root / "_includes" / "header.html").write_text("<header>Header</header>", encoding="utf-8")
            (template_root / "_includes" / "sidebar.html").write_text("<aside>Sidebar</aside>", encoding="utf-8")
            (template_root / "_includes" / "footer.html").write_text("<footer>Footer</footer>", encoding="utf-8")
            (template_root / "_layouts" / "default.html").write_text("{{ content }}", encoding="utf-8")
            (template_root / "assets" / "css" / "main.css").write_text("body { color: black; }", encoding="utf-8")
            (template_root / "assets" / "js" / "page-enhancements.js").write_text("console.log('enhance');", encoding="utf-8")
            (template_root / "assets" / "js" / "theme-toggle.js").write_text("console.log('theme');", encoding="utf-8")
            (template_root / "assets" / "js" / "table-sort.js").write_text("console.log('sort');", encoding="utf-8")
            (template_root / "favicon.svg").write_text("<svg></svg>", encoding="utf-8")
            (template_root / "Gemfile").write_text("source 'https://rubygems.org'\n", encoding="utf-8")

            result = build_jekyll_site.build_site(
                content_root=content_root,
                output_root=output_root,
                template_root=template_root,
                route_prefixes=["/ufo-history/ufo-books"],
            )

            self.assertEqual(result["article_pages"], 1)
            self.assertTrue((output_root / "pages" / "ufo-history" / "ufo-books" / "book-one.md").exists())
            self.assertFalse((output_root / "pages" / "ufo-history" / "ufo" / "19470000-example.md").exists())

            tag_index = (output_root / "pages" / "tags-index.html").read_text(encoding="utf-8")
            self.assertIn("Books", tag_index)
            self.assertNotIn("Timeline", tag_index)


if __name__ == "__main__":
    unittest.main()
