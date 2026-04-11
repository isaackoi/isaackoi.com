# Joomla Extraction Workspace

This repo is now structured around extracting and normalizing content from a Joomla backup before any final GitHub Pages template is adopted.

The Python-backed site is treated as non-authoritative. The backup database is the primary source of truth for structured content, and the backed-up Joomla filesystem is used for assets, media resolution, and template/rendering clues.

## Working layout

- `backups/raw/db/` holds original SQL dump files unchanged
- `backups/raw/joomla-site/` holds the original Joomla filesystem backup unchanged
- `content/` is the normalized extraction target
- `templates/reference-sites/` is where donor GitHub Pages sites should be staged later as references
- `templates/static-preview/` holds the source assets for the temporary preview builder
- `site/` is generated output and should be treated as disposable

## Extractor

The first-pass extractor lives at `scripts/extract_joomla.py`.

It currently:

- scans `backups/raw/db/` for `.sql` and `.sql.gz` dumps
- parses Joomla content, categories, users, menus, tags, and redirects when present
- writes normalized Markdown content files with YAML front matter into `content/articles/`
- writes machine-readable manifests and reports into `content/_meta/`
- resolves referenced assets against `backups/raw/joomla-site/`, including Akeeba `.jpa` archives without unpacking them first

The static preview builder lives at `scripts/build_static_site.py`.

It assembles the current normalized content into `site/` by:

- rendering published articles at their normalized legacy-style URLs
- generating section index pages from the extracted Joomla categories
- generating lightweight `/tags/*` pages from internal tag links
- emitting redirect pages for legacy Joomla `.html` SEF URLs
- copying extracted asset trees from `content/assets/source/` into the publish root

## Run it

```powershell
python scripts/extract_joomla.py
```

Optional overrides:

```powershell
python scripts/extract_joomla.py --db-root backups/raw/db --joomla-root backups/raw/joomla-site --content-root content
```

To also materialize resolved assets out of the Joomla backup or `.jpa` archive:

```powershell
python scripts/extract_joomla.py --extract-assets --assets-output-root content/assets/source
```

To unpack the full Joomla Akeeba archive into a derived workspace tree:

```powershell
python scripts/extract_joomla.py --extract-archive --archive-output-root backups/extracted/joomla-site
```

To assemble the current normalized content into the GitHub Pages output tree:

```powershell
python scripts/build_static_site.py
```

## Test it

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Notes

- Do not place a donor GitHub Pages site into `site/` yet.
- Stage any candidate donor site later under `templates/reference-sites/<site-name>/`.
- Template adoption should consume normalized content from `content/`, not raw Joomla schemas.
