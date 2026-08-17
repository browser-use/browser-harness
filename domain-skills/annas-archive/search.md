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
- **Result extraction (live DOM)**: target the *title* anchor
  `a.js-vim-focus[href^="/md5/"]` and take `a.closest('div.pt-3')` as the
  card — its innerText carries file path, title, authors, publisher and a
  meta line like `English [en] · PDF · 12.3MB · 📘 Book (non-fiction)`,
  enough to pick an edition without opening the detail page.

```python
EXTRACT = """
(() => {
  const seen = new Set(); const res = [];
  for (const a of document.querySelectorAll('a.js-vim-focus[href^="/md5/"]')) {
    const md5 = a.getAttribute('href').split('/md5/')[1].split(/[/?]/)[0];
    if (seen.has(md5)) continue;
    seen.add(md5);
    const card = a.closest('div.pt-3') || a.parentElement;
    res.push({md5, text: card.innerText.replace(/\\s+/g,' ').trim().slice(0,400)});
    if (res.length >= 8) break;
  }
  return JSON.stringify({res, none: document.body.innerText.includes('No files found')});
})()
"""
```

- **Static-HTML parsing** (if you fetch the page body some other way): result
  cards may sit inside HTML comments (lazy-render trick) — strip
  `<!--`/`-->` first, then split on `<div class="flex pt-3 pb-3 border-b`.
  Each card's *first* md5 anchor is an **empty cover-image link**; the title
  is in a later anchor. Don't dedupe-by-first-anchor or you keep the textless
  cover link.

Sequential navigation cadence ~10-15s per query including challenge/nav waits
is sustained fine over 100+ queries in one tab.

## Traps

- **Cookie snapshots go stale fast.** Exporting the `__ddg*`/`aa_ddg_check`
  cookies for plain-HTTP reuse works for ~40-60 requests, then DDoS-Guard
  starts 302-loops and connection resets (`__ddg8_`/`__ddg10_` rotate
  per-request in the browser; a static copy ages out). Parallel workers make
  it die faster. `fetch()` from inside the page gets challenged the same way
  at speed — it receives the interstitial HTML but *cannot solve it* (only
  navigation can). For bulk work, paced real navigation is the only route
  that survives.
- **Recent-downloads marquee poisons naive extraction.** The page top has a
  `.js-recent-downloads-scroll` strip full of `/md5/` links to random books.
  A generic `a[href^="/md5/"]` sweep on the live DOM returns those first.
  Use `a.js-vim-focus` (result-title anchors only).
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
