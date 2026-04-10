# Migration Checklist

Use this checklist against the live Python site before committing to a full port.

## Content

- Count the number of text pages.
- Count image assets and total size.
- Identify pages with tables, filters, or search.
- Identify shared navigation, headers, footers, and sidebars.

## Dynamic behavior

- Check whether pages are generated from a database.
- Check whether URLs depend on query parameters or server routing rules.
- Check whether any page content changes by user, session, or login state.
- Check whether there are forms, uploads, comments, or contact flows.
- Check whether the site uses server-side search.

## Security and infrastructure

- Check whether the Python app is currently exposing outdated dependencies.
- Check whether the site relies on custom headers, auth middleware, or rate limiting.
- Check whether secrets are embedded into templates or frontend code.

## Migration decision rule

The port is usually a strong candidate if:

- almost all pages can be prebuilt
- tables can be sorted or filtered in the browser
- forms can be replaced with a third-party endpoint or removed
- no sensitive logic needs to run on the server

## Possible target stack

- Plain HTML, CSS, JS if the site is small and stable
- Jekyll if you want tight GitHub Pages alignment
- Eleventy or Astro if you want a nicer authoring workflow and build via Actions
