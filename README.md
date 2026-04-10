# GitHub Pages Port Spike

This repo is a clean test bed for evaluating a move from a Python-backed site to a static site hosted on GitHub Pages.

## Initial conclusion

For a site that is mostly:

- text pages
- images
- sortable/filterable tables in the browser

GitHub Pages is a realistic target.

It is a good fit if the current Python layer is mainly serving rendered pages and static assets rather than doing request-time work.

## Not a fit if the live site depends on

- server-side Python rendering per request
- login or user-specific sessions
- admin dashboards
- database writes from the public site
- file uploads handled by your server
- private APIs that must stay hidden from the browser

## Practical migration shape

1. Export page content into Markdown, HTML, or structured data files.
2. Keep images as static assets.
3. Move table sorting/filtering to client-side JavaScript.
4. Use a static site generator only if it improves maintainability.
5. Deploy the built site to GitHub Pages with GitHub Actions.

## Repo layout

- `site/` contains the published static site for the spike
- `.github/workflows/deploy.yml` deploys `site/` to GitHub Pages
- `migration-checklist.md` captures what to inspect on the existing live site

## Next step

Audit the live Python site page by page and classify each feature as one of:

- pure static content
- static content with client-side enhancement
- dynamic/server-only feature

If most pages land in the first two buckets, the port is likely worth doing.
