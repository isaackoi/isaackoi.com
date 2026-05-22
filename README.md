# Isaac Koi Archive

This Jekyll site is the generated public-repo source for the Isaac Koi archive.

Key paths:

- `pages/` holds the route-based Markdown source pages
- `images/`, `documents/`, `book-covers/`, and `assets/` hold site assets
- `_layouts/`, `_includes/`, and `assets/` hold the Phoenix-derived theme
- `navigation-tree.json` holds the client-side sidebar navigation tree

Local development:

```powershell
bundle install
bundle exec jekyll serve
```

Production deploys should use the GitHub Actions workflow in `.github/workflows/pages.yml`.
