from __future__ import annotations

import importlib.util
import json
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "extract_joomla.py"
SPEC = importlib.util.spec_from_file_location("extract_joomla", MODULE_PATH)
assert SPEC and SPEC.loader
extract_joomla = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = extract_joomla
SPEC.loader.exec_module(extract_joomla)


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "joomla_sample.sql"


def build_jpa_entity(path: str, data: bytes, compression_type: int) -> bytes:
    path_bytes = path.encode("utf-8")
    if compression_type == 0:
        payload = data
    elif compression_type == 1:
        compressor = zlib.compressobj(level=6, wbits=-zlib.MAX_WBITS)
        payload = compressor.compress(data) + compressor.flush()
    else:
        raise ValueError("Unsupported compression type for test fixture")

    block_length = 21 + len(path_bytes)
    header = b"".join(
        [
            b"JPF",
            struct.pack("<H", block_length),
            struct.pack("<H", len(path_bytes)),
            path_bytes,
            bytes([1, compression_type]),
            struct.pack("<I", len(payload)),
            struct.pack("<I", len(data)),
            struct.pack("<I", 0),
        ]
    )
    return header + payload


def write_sample_jpa(path: Path) -> None:
    members = [
        ("images/hello.jpg", b"hello-image", 0),
        ("images/intro.jpg", b"intro-image", 0),
        ("docs/spec.pdf", b"%PDF-1.4 sample", 1),
    ]
    payload = b"".join(build_jpa_entity(member_path, data, compression) for member_path, data, compression in members)
    header = b"".join(
        [
            b"JPA",
            struct.pack("<H", 19),
            bytes([1, 2]),
            struct.pack("<I", len(members)),
            struct.pack("<I", sum(len(data) for _, data, _ in members)),
            struct.pack("<I", len(payload)),
        ]
    )
    path.write_bytes(header + payload)


class JoomlaExtractionTests(unittest.TestCase):
    def test_decode_sql_string_repairs_mojibake_and_doubled_quotes(self) -> None:
        repaired = extract_joomla.decode_sql_string("It''s FranÃ§ais")
        self.assertEqual(repaired, "It's Français")

    def test_normalize_body_html_expands_articles_strips_scripts_and_rewrites_links(self) -> None:
        article_by_id = {
            1329: {
                "introtext": '<p>Please use the comments section below to share references.</p><script>alert(1)</script>',
                "fulltext": "",
            }
        }
        link_lookup = {
            "best-ufo-cases.html": "/ufog/best-ufo-cases",
            "best-ufo-cases/1-introduction.html": "/ufog/best-ufo-cases/1-introduction",
            "starter-pack/2-preliminary-points.html": "/ufog/starter-pack/2-preliminary-points",
        }
        body = (
            '<p><a href="best-ufo-cases.html">Best UFO Cases</a></p>'
            '<p><st1:date year="1972" day="12" month="3">12 March 1972</st1:date></p>'
            '<p><a href="starter-pack/2-preliminary-points.html#section%202.4">Starter Pack</a></p>'
            '<p><a href="tags/seti.html">SETI</a></p>'
            '<p><span id="google-navclient-highlight" style="background-color: #50ccc5; color: white;">part</span>ially done</p>'
            '{article 1329}{text}{/article}'
        )

        normalized = extract_joomla.normalize_body_html(body, article_by_id, link_lookup)

        self.assertIn('href="/ufog/best-ufo-cases"', normalized)
        self.assertIn('href="/ufog/starter-pack/2-preliminary-points#section%202.4"', normalized)
        self.assertIn('href="/tags/seti"', normalized)
        self.assertIn("12 March 1972", normalized)
        self.assertNotIn("<st1:date", normalized)
        self.assertIn("Please use the comments section below to share references.", normalized)
        self.assertNotIn("<script", normalized)
        self.assertNotIn("google-navclient-highlight", normalized)
        self.assertIn("partially done", normalized)
        self.assertNotIn("{article 1329}", normalized)

    def test_normalize_body_html_handles_legacy_aliases_and_bare_external_links(self) -> None:
        link_lookup = {
            "best-ufo-cases/27-quantitative-criteria-kois-ices-ratings.html":
                "/ufog/best-ufo-cases/27-quantitative-criteria-kois-ices-ratings",
            "ufo-books/redfern-nicholas-on-the-trail-of-the-saucer-spies.html":
                "/ufo-history/ufo-books/redfern-nicholas-on-the-trail-of-the-saucer-spies",
            "ufo-personalities/friend-robert-j.html":
                "/ufo-history/ufo-personalities/friend-robert-j",
            "ufo-personalities/wilson-k.html":
                "/ufo-history/ufo-personalities/wilson-k",
            "ufo-personalities/wilkins-harold.html":
                "/ufo-history/ufo-personalities/wilkins-harold",
            "ufo/19910000-roper-abduction-polls.html":
                "/ufo-history/ufo/19910000-roper-abduction-polls",
        }
        body = (
            '<p><a href="best-ufo-cases/27-quantitative-criteria-kois-card-ratings.html#impact">ICES</a></p>'
            '<p><a href="UFO-Books/redfern-nicholas-on-the-trail-of-the-saucer-spiesq.html">Book</a></p>'
            '<p><a href="ufo-personalities/friend-robert-f.html">Friend</a></p>'
            '<p><a href="UFO-Personalities/wilson-katharina.html">Wilson</a></p>'
            '<p><a href="UFO-Personalities/wilkins-harold-t.html">Wilkins</a></p>'
            '<p><a href="UFO-History-Guides/polls.html">Poll</a></p>'
            '<p><a href="sitemap.html">Sitemap</a></p>'
            '<p><a href="shadowboxent.brinkster.net/HoaxResearchCenter/IrishTriangleUFO.html">External</a></p>'
        )

        normalized = extract_joomla.normalize_body_html(body, {}, link_lookup)

        self.assertIn(
            'href="/ufog/best-ufo-cases/27-quantitative-criteria-kois-ices-ratings#impact"',
            normalized,
        )
        self.assertIn(
            'href="/ufo-history/ufo-books/redfern-nicholas-on-the-trail-of-the-saucer-spies"',
            normalized,
        )
        self.assertIn('href="/ufo-history/ufo-personalities/friend-robert-j"', normalized)
        self.assertIn('href="/ufo-history/ufo-personalities/wilson-k"', normalized)
        self.assertIn('href="/ufo-history/ufo-personalities/wilkins-harold"', normalized)
        self.assertIn('href="/ufo-history/ufo/19910000-roper-abduction-polls"', normalized)
        self.assertIn('href="/sitemap"', normalized)
        self.assertIn(
            'href="http://shadowboxent.brinkster.net/HoaxResearchCenter/IrishTriangleUFO.html"',
            normalized,
        )

    def test_build_asset_lookup_reads_jpa_archive_and_member_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            joomla_root = Path(temp_dir) / "joomla-site"
            joomla_root.mkdir()
            archive_path = joomla_root / "sample.jpa"
            write_sample_jpa(archive_path)

            asset_lookup = extract_joomla.build_asset_lookup(joomla_root)
            resolution = extract_joomla.resolve_assets(
                ["images/hello.jpg", "docs/spec.pdf", "images/missing.jpg"],
                asset_lookup,
            )

            self.assertEqual(asset_lookup.asset_source["mode"], "jpa-archive")
            self.assertEqual(asset_lookup.asset_source["archive_indexed_entries"], 3)
            self.assertEqual(sorted(resolution["resolved"]), ["docs/spec.pdf", "images/hello.jpg"])
            self.assertEqual(resolution["missing"], ["images/missing.jpg"])
            payload = extract_joomla.read_jpa_member(asset_lookup.archive_index, "docs/spec.pdf")
            self.assertEqual(payload, b"%PDF-1.4 sample")

    def test_run_extraction_can_export_assets_from_jpa_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_root = root / "db"
            joomla_root = root / "joomla-site"
            assets_root = root / "exported-assets"
            db_root.mkdir()
            joomla_root.mkdir()
            (db_root / "backup.sql").write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            write_sample_jpa(joomla_root / "sample.jpa")

            result = extract_joomla.run_extraction(
                db_root=db_root,
                joomla_root=joomla_root,
                export_assets_root=assets_root,
            )

            self.assertEqual(result.report["asset_export"]["exported"], 3)
            self.assertEqual(result.report["asset_export"]["missing"], 0)
            self.assertEqual((assets_root / "images" / "hello.jpg").read_bytes(), b"hello-image")
            self.assertEqual((assets_root / "docs" / "spec.pdf").read_bytes(), b"%PDF-1.4 sample")

    def test_run_extraction_can_unpack_full_jpa_archive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_root = root / "db"
            joomla_root = root / "joomla-site"
            archive_root = root / "archive-extracted"
            db_root.mkdir()
            joomla_root.mkdir()
            (db_root / "backup.sql").write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            write_sample_jpa(joomla_root / "sample.jpa")

            result = extract_joomla.run_extraction(
                db_root=db_root,
                joomla_root=joomla_root,
                extract_archive_root=archive_root,
            )

            self.assertEqual(result.report["archive_export"]["files"], 3)
            self.assertTrue((archive_root / "images" / "hello.jpg").exists())
            self.assertTrue((archive_root / "images" / "intro.jpg").exists())
            self.assertTrue((archive_root / "docs" / "spec.pdf").exists())

    def test_run_extraction_normalizes_records_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_root = root / "db"
            joomla_root = root / "joomla-site"
            db_root.mkdir()
            (db_root / "backup.sql").write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            (joomla_root / "images").mkdir(parents=True)
            (joomla_root / "docs").mkdir(parents=True)
            (joomla_root / "images" / "hello.jpg").write_text("", encoding="utf-8")
            (joomla_root / "images" / "intro.jpg").write_text("", encoding="utf-8")
            (joomla_root / "docs" / "spec.pdf").write_text("", encoding="utf-8")

            result = extract_joomla.run_extraction(db_root=db_root, joomla_root=joomla_root)

            self.assertEqual(len(result.items), 2)
            self.assertEqual(len(result.redirects), 1)

            first = result.items[0]
            second = result.items[1]

            self.assertEqual(first["source_id"], 1)
            self.assertEqual(first["slug"], "hello-world")
            self.assertEqual(first["original_url"], "/news")
            self.assertEqual(first["legacy_route_guess"], "menu")
            self.assertEqual(first["category"], "Updates")
            self.assertEqual(first["author"], "Site Admin")
            self.assertEqual(first["tags"], ["featured", "migration"])
            self.assertIn("images/hello.jpg", first["asset_refs"])
            self.assertIn("docs/spec.pdf", first["asset_refs"])
            self.assertIn('href="/tags/seti"', first["body"])
            self.assertIn("images/full.jpg", first["asset_resolution"]["missing"])
            self.assertEqual(second["original_url"], "/blog/orphan-page")
            self.assertEqual(second["status"], "unpublished")

    def test_write_outputs_creates_manifest_report_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            db_root = root / "db"
            joomla_root = root / "joomla-site"
            content_root = root / "content"
            db_root.mkdir()
            (db_root / "backup.sql").write_text(FIXTURE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
            (joomla_root / "images").mkdir(parents=True)
            (joomla_root / "docs").mkdir(parents=True)
            (joomla_root / "images" / "hello.jpg").write_text("", encoding="utf-8")
            (joomla_root / "images" / "intro.jpg").write_text("", encoding="utf-8")
            (joomla_root / "docs" / "spec.pdf").write_text("", encoding="utf-8")

            result = extract_joomla.run_extraction(db_root=db_root, joomla_root=joomla_root)
            extract_joomla.write_outputs(content_root=content_root, result=result)

            article_path = content_root / "articles" / "1-hello-world.md"
            manifest_path = content_root / "_meta" / "content-manifest.json"
            report_path = content_root / "_meta" / "extraction-report.json"
            redirects_path = content_root / "_meta" / "redirects.json"
            menu_index_path = content_root / "_meta" / "menu-index.json"
            category_index_path = content_root / "_meta" / "category-index.json"
            legacy_routes_path = content_root / "_meta" / "legacy-routes.json"
            unresolved_links_path = content_root / "_meta" / "unresolved-relative-links.json"
            template_inventory_path = content_root / "_meta" / "template-inventory.json"

            self.assertTrue(article_path.exists())
            self.assertTrue(manifest_path.exists())
            self.assertTrue(report_path.exists())
            self.assertTrue(redirects_path.exists())
            self.assertTrue(menu_index_path.exists())
            self.assertTrue(category_index_path.exists())
            self.assertTrue(legacy_routes_path.exists())
            self.assertTrue(unresolved_links_path.exists())
            self.assertTrue(template_inventory_path.exists())

            article_text = article_path.read_text(encoding="utf-8")
            self.assertIn("source_id: 1", article_text)
            self.assertIn('original_url: "/news"', article_text)
            self.assertIn("<p>Intro", article_text)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            report = json.loads(report_path.read_text(encoding="utf-8"))
            redirects = json.loads(redirects_path.read_text(encoding="utf-8"))
            menu_index = json.loads(menu_index_path.read_text(encoding="utf-8"))
            category_index = json.loads(category_index_path.read_text(encoding="utf-8"))
            legacy_routes = json.loads(legacy_routes_path.read_text(encoding="utf-8"))

            self.assertEqual(len(manifest), 2)
            self.assertEqual(report["normalized_counts"]["content_items"], 2)
            self.assertEqual(report["content_audit"]["unresolved_relative_link_targets"], 0)
            self.assertEqual(redirects[0]["source"], "/old-page")
            self.assertEqual(menu_index[0]["path"], "news")
            self.assertEqual(category_index[0]["alias"], "blog")
            self.assertEqual(legacy_routes[0]["target_path"], "/tags/seti")


if __name__ == "__main__":
    unittest.main()
