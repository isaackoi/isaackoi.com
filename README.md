# Joomla Extraction Workspace

This repo is now structured around extracting and normalizing content from a Joomla backup before any final GitHub Pages template is adopted.

The Python-backed site is treated as non-authoritative. The backup database is the primary source of truth for structured content, and the backed-up Joomla filesystem is used for assets, media resolution, and template/rendering clues.

## Working layout

- `backups/raw/db/` holds original SQL dump files unchanged
- `backups/raw/joomla-site/` holds the original Joomla filesystem backup unchanged
- `content/` is the normalized extraction target
- `templates/reference-sites/` is where donor GitHub Pages sites should be staged later as references
- `templates/static-preview/` holds the source assets for the temporary preview builder
- `templates/jekyll-phoenix-theme/` holds the Phoenix-derived Jekyll theme source
- `site/` is generated output and should be treated as disposable
- `jekyll-site/` is the generated full Jekyll source tree
- `jekyll-site-preview/` is an optional filtered Jekyll preview tree for faster local iteration

## Extractor

The first-pass extractor lives at `scripts/extract_joomla.py`.

It currently:

- scans `backups/raw/db/` for `.sql` and `.sql.gz` dumps
- parses Joomla content, categories, users, menus, tags, and redirects when present
- writes normalized Markdown content files with YAML front matter into `content/articles/`
- writes machine-readable manifests and reports into `content/_meta/`
- derives article tags from `/tags/*` links in article bodies and writes `tags-index.json`
- filters Joomla menu rows down to a public navigation dataset in `public-nav.json`
- captures homepage/featured intent into `homepage-intent.json`
- extracts per-page Open Graph metadata into `social-metadata.json`
- audits unresolved asset references into `missing-assets.json`
- writes a secondary Joomla feature inventory into `secondary-content-inventory.json`
- resolves referenced assets against `backups/raw/joomla-site/`, including Akeeba `.jpa` archives without unpacking them first

The static preview builder lives at `scripts/build_static_site.py`.

It assembles the current normalized content into `site/` by:

- rendering published articles at their normalized legacy-style URLs
- generating section index pages from the extracted Joomla categories
- generating lightweight `/tags/*` pages from internal tag links
- emitting redirect pages for legacy Joomla `.html` SEF URLs
- copying extracted asset trees from `content/assets/source/` into the publish root

The Jekyll source builder lives at `scripts/build_jekyll_site.py`.

It assembles a Markdown-first Jekyll site by:

- converting article prose into route-based Markdown files under `jekyll-site/pages/`
- preserving complex sortable tables as raw HTML blocks inside the Markdown source
- deriving optional book-cover metadata from legacy Amazon identifiers on book pages
- generating homepage, section, tag, and sitemap pages
- emitting `navigation-tree.json` so the full sidebar tree is hydrated client-side instead of being rendered into every page at build time
- copying the Phoenix-derived theme assets and extracted site assets into the Jekyll tree
- supporting filtered preview builds with `--route-prefix` and `--limit-items`

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

To assemble the full Jekyll source tree:

```powershell
python scripts/build_jekyll_site.py
```

To stage a clean standalone public-repo tree from that generated Jekyll source:

```powershell
python scripts/export_public_repo.py
```

That exports `jekyll-site/` into `jekyll-public-repo/` while stripping local build residue such as `vendor/`, `.bundle/`, `_site/`, and cache directories.

To build a faster local Jekyll preview for a specific branch of the site:

```powershell
python scripts/build_jekyll_site.py --route-prefix /ufo-history/ufo-books --limit-items 40 --output-root jekyll-site-preview
cd jekyll-site-preview
bundle install
bundle exec jekyll build --profile
```

That preview path is the recommended local workflow on Windows. It keeps the theme and content loop fast while the full site remains too large for comfortable full-corpus local builds.

To wrap generation plus local Jekyll build into one command:

```powershell
python scripts/run_jekyll_preview.py --route-prefix /ufo-history/ufo-books --limit-items 40
```

To cache book covers locally for later Jekyll builds:

```powershell
python scripts/cache_book_covers.py --route-prefix /ufo-history/ufo-books --limit-items 40
```

To run a local Jekyll server for that same filtered preview:

```powershell
python scripts/run_jekyll_preview.py --route-prefix /ufo-history/ufo-books --limit-items 40 --serve
```

To verify missing extracted assets against the live legacy site and write a verification artifact:

```powershell
python scripts/verify_live_assets.py
```

## Test it

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## Notes

- Do not place a donor GitHub Pages site into `site/` yet.
- Stage any candidate donor site later under `templates/reference-sites/<site-name>/`.
- Template adoption should consume normalized content from `content/`, not raw Joomla schemas.
