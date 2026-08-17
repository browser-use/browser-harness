# Anna's Archive — search via browser (WAF bypass)

## Why the browser at all

As of 2026-08, AA `/search` is behind DDoS-Guard on every mirror: `.gl`,
`.pk`, `.gd` return 403 to plain HTTP clients; `.li` serves a JS-fingerprint
interstitial (and for fresh browser profiles has redirected to an ad-parking
page — avoid `.li`). No member search API exists: the member key only works
for `dyn/api/fast_download.json` by md5; bulk search means the ES/MariaDB
dumps. So title→md5 resolution goes through a real browser; downloads then go
through the fast-download API outside the browser.

## What works

- **Mirror**: use `https://annas-archive.gl/search?q=<query>`. A real Chrome
  clears the DDoS-Guard challenge automatically in ~1-3s (no CAPTCHA, just JS
  fingerprinting). A throwaway `--user-data-dir` Chrome instance passes fine —
  no login or cookies needed for search.
- **Challenge detection**: `document.title` contains `DDoS-Guard` while the
  interstitial is up; poll until it clears, then extract. After the first
  clearance the cookie persists for the session and later searches don't
  re-challenge.
- **Result extraction**: every hit is an `<a href="/md5/<hex>">` wrapping the
  whole result card. Dedupe by md5 (each card can contain nested anchors).
  `a.innerText` carries title, publisher, authors and a meta line like
  `English [en], .pdf, 🚀/lgli/zlib, 12.3MB, 📘 Book (non-fiction)` — enough
  to pick an edition without opening the detail page.

```python
EXTRACT = """
(() => {
  const seen = new Set(); const res = [];
  for (const a of document.querySelectorAll('a[href^="/md5/"]')) {
    const md5 = a.getAttribute('href').split('/md5/')[1].split(/[/?]/)[0];
    if (seen.has(md5)) continue;
    seen.add(md5);
    const t = a.innerText.replace(/\\s+/g,' ').trim();
    if (t.length > 10) res.push({md5, text: t.slice(0,350)});
    if (res.length >= 6) break;
  }
  return JSON.stringify(res);
})()
"""
```

Sequential search cadence ~10-15s per query including challenge/nav waits is
sustained fine over 60+ queries in one tab.

## Traps

- **Fuzzy fallback**: when nothing matches, AA silently pads the page with
  unrelated "partial match" cards — the presence of hits does NOT mean the
  work exists. Judge every hit's text against the query; expect pure junk for
  rare scholarly titles.
- **Search drops diacritics/translator names**: query author-surname + short
  title; adding a translator often zeroes an otherwise-good match.
- **`.li` ad-parking redirect**: a fresh profile navigating to
  `annas-archive.li` can land on `ron.mamma.com` spam instead of AA.
- **Dead links**: `Invalid domain_index or path_index` from the fast-download
  API is permanent for that md5 — resolve an alternate md5/edition rather
  than retrying.
