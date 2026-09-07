# Dropbox — downloading files from a shared folder link

Verified 2026-08-10 on a `/scl/fo/<id>/h?rlkey=<key>` share (logged-in session).

## The working recipe

1. **Route downloads somewhere readable first** — macOS blocks agents from
   `~/Downloads` (TCC). CDP fixes it:
   `cdp("Browser.setDownloadBehavior", behavior="allow", downloadPath=<your dir>)`
   Persists for the session.
2. **Deep-link each file's preview page**:
   `https://www.dropbox.com/scl/fo/<id>/h/<subpath>/<file>?rlkey=<key>&dl=0`
   The `<subpath>` must be the FULL path inside the share — check the share's
   root listing first (folders may nest, e.g. everything under `all_ast/`).
   A wrong path silently falls back to the share ROOT (no error page) — and a
   Download click there requests a whole-folder zip. Verify you're on a file
   preview before clicking.
3. **Click the download button by text**: it's locale-dependent
   (`Baixar` in pt-BR) — match `/baixar|download/i` over `button,a`.
4. **Poll the download dir for the exact filename** (~5–25 s for small files).

## What does NOT work

- `curl`/`http_get` on `?dl=1` for folder-scoped file URLs → returns the HTML
  preview page, even with cookies. Only real per-file share links support
  direct `dl=1` fetch.
- In-page `fetch(url, {credentials:"include"})` of `dl=1` → same HTML; the
  content URL is minted by Dropbox JS only on the button click.
- The page HTML contains no `dropboxusercontent` links to scrape.

## Trap: filename conventions vary per folder

In the swisseph share, asteroid files ≥ 100000 drop the `e`:
`se90377s.se1` but `s136199s.se1`. If a deep link "times out", screenshot the
parent folder and check the real names — the click probably landed on the
root's folder-download button.
