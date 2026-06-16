# IMDb — Charts, Search, and "More Like This" Scraping

`https://www.imdb.com` — the Internet Movie Database. Field-tested on 2026-04-24 against `chart/top`, `chart/moviemeter`, `find/?s=tt&q=`, and `title/tt{id}/` pages.

IMDb's app shell is React with a shared design system (`ipc-*` classes). The same `li.ipc-metadata-list-summary-item` row primitive is reused across Top 250, MovieMeter, Search, and most other list pages — learn one selector set, scrape many pages.

The `tt`-prefixed title ID in the URL (`/title/tt0111161/`) is IMDb's stable primary key. Titles, prefixes, rankings, and CSS class hashes change between releases; `tt`-ids do not. Always dedupe by `tt`-id.

---

## Access path decision table

| Goal | Method | Page | Notes |
|------|--------|------|-------|
| Top 250 films (ranked) | browser | `/chart/top` | 250 rows, fully rendered server-side |
| MovieMeter (trending top 100) | browser | `/chart/moviemeter` | 100 rows, same row structure as Top 250 |
| Keyword/title search | browser | `/find/?s=tt&q=KEYWORD` | `s=tt` restricts to titles |
| "More Like This" recommendations | browser | `/title/tt{id}/` | Lazy-loaded, requires scroll |
| Title metadata (year, runtime, genres) | `http_get` + JSON-LD | `/title/tt{id}/` | The `<script type="application/ld+json">` block carries full Movie schema |

`http_get` works for title pages (the JSON-LD and OG meta-tag blocks are pre-rendered), but the chart, search, and "More Like This" panels are client-hydrated — use the browser for those.

---

## Path 1: Top 250 chart (`/chart/top`)

```python
import json
from helpers import goto, wait_for_load, wait, js

goto("https://www.imdb.com/chart/top/")
wait_for_load()
wait(2)  # let React finish hydration

rows = json.loads(js(r"""
(function () {
  var out = [];
  document.querySelectorAll('li.ipc-metadata-list-summary-item').forEach(function (li) {
    var a = li.querySelector('a.ipc-title-link-wrapper');
    var h = li.querySelector('a.ipc-title-link-wrapper h3.ipc-title__text');
    if (!a || !h) return;
    var raw = h.textContent.trim();                       // "1. The Shawshank Redemption"
    var m = raw.match(/^(\d+)\.\s*(.+)$/);
    var ttMatch = a.href.match(/\/title\/(tt\d+)\//);

    var meta = Array.from(li.querySelectorAll(
      '.cli-title-metadata-item, .sc-300a8231-6, span.cli-title-metadata-item'
    )).map(function (s) { return s.textContent.trim(); });

    var rating = li.querySelector('span.ipc-rating-star--rating');
    var votes  = li.querySelector('span.ipc-rating-star--voteCount');

    out.push({
      rank:      m ? parseInt(m[1], 10) : null,
      title:     m ? m[2] : raw,
      tt_id:     ttMatch ? ttMatch[1] : null,
      url:       a.href,
      year:      meta[0] || null,        // "1994"
      runtime:   meta[1] || null,        // "2h 22m"
      certificate: meta[2] || null,      // "R" / "PG-13"
      rating:    rating ? parseFloat(rating.textContent) : null,
      votes_raw: votes ? votes.textContent.trim() : null   // "(3.1M)"
    });
  });
  return JSON.stringify(out);
})()
"""))

print(len(rows), rows[0])
# 250 rows; rows[0]: {'rank': 1, 'title': 'The Shawshank Redemption',
#                    'tt_id': 'tt0111161', 'year': '1994', 'runtime': '2h 22m',
#                    'certificate': 'R', 'rating': 9.3, 'votes_raw': '(3.1M)'}
```

The title text is prefixed with the rank (e.g. `"1. The Shawshank Redemption"`) — strip it with a single regex rather than relying on a separate rank element.

### Parsing the abbreviated vote count

```python
def parse_votes(raw):
    """'(3.1M)' -> 3_100_000, '(850K)' -> 850_000, '(12,345)' -> 12345."""
    if not raw:
        return None
    s = raw.strip("() ").upper().replace(",", "")
    if s.endswith("M"): return int(float(s[:-1]) * 1_000_000)
    if s.endswith("K"): return int(float(s[:-1]) * 1_000)
    return int(s) if s.isdigit() else None
```

---

## Path 2: MovieMeter (`/chart/moviemeter`)

Structurally identical to Top 250 — same `li.ipc-metadata-list-summary-item` rows, same `h3.ipc-title__text` prefix, same rating/votes spans. The chart returns 100 trending titles updated weekly.

```python
goto("https://www.imdb.com/chart/moviemeter/")
wait_for_load()
wait(2)

# Reuse the Path 1 JS block verbatim — it works unchanged.
rows = json.loads(js(TOP_CHART_JS))   # returns 100 rows
```

Because the row primitive is shared, any function you write for `/chart/top` works on `/chart/moviemeter`, `/chart/toptv`, `/chart/bottom`, and the box-office charts. The difference is only the row count and the semantic meaning of the rank.

---

## Path 3: Title search (`/find/?s=tt&q=KEYWORD`)

The `s=tt` param restricts results to titles (other values: `nm` people, `co` companies, `kw` keywords). IMDb has two result-item classes — older pages ship `li.find-title-result`, newer variants use the shared `li.ipc-metadata-list-summary-item`. Query with both, dedupe by `tt`-id.

```python
import urllib.parse
from helpers import goto, wait_for_load, wait, js

def imdb_search(keyword, limit=25):
    q = urllib.parse.quote(keyword)
    goto(f"https://www.imdb.com/find/?s=tt&q={q}")
    wait_for_load()
    wait(1.5)

    results = json.loads(js(r"""
    (function () {
      var seen = new Set();
      var out = [];
      var rows = document.querySelectorAll(
        'li.find-title-result, li.ipc-metadata-list-summary-item'
      );
      rows.forEach(function (li) {
        var a = li.querySelector('a[href*="/title/tt"]');
        if (!a) return;
        var ttM = a.href.match(/\/title\/(tt\d+)\//);
        if (!ttM || seen.has(ttM[1])) return;
        seen.add(ttM[1]);

        var tEl = li.querySelector(
          '.ipc-metadata-list-summary-item__t, .ipc-title__text, a.ipc-metadata-list-summary-item__t'
        );
        var meta = Array.from(li.querySelectorAll(
          '.ipc-metadata-list-summary-item__li, .ipc-inline-list__item'
        )).map(function (s) { return s.textContent.trim(); }).filter(Boolean);

        out.push({
          tt_id: ttM[1],
          title: (tEl ? tEl.textContent.trim() : a.textContent.trim()),
          url:   a.href.split('?')[0],
          meta:  meta                        // e.g. ['1994', 'Feature', 'Tim Robbins']
        });
      });
      return JSON.stringify(out);
    })()
    """))

    return results[:limit]

hits = imdb_search("shawshank")
# [{'tt_id': 'tt0111161', 'title': 'The Shawshank Redemption',
#   'url': 'https://www.imdb.com/title/tt0111161/',
#   'meta': ['1994', 'Feature', 'Tim Robbins, Morgan Freeman']}, ...]
```

The `meta` list's content varies by title type (feature / short / TV episode / video game) — don't assume a fixed positional schema.

---

## Path 4: "More Like This" recommendations (`/title/tt{id}/`)

The "More Like This" panel sits below the fold on the title page and mounts via IntersectionObserver. It is **not present** in the initial DOM — you must scroll down to trigger hydration. Two `scroll(dy=3000)` calls with a short `wait()` between them is the verified recipe.

The panel's heading text ("More Like This") is stable; its container class hash is not. Find the heading by regex, then walk up to its section and scrape every `a[href*="/title/tt"]` inside. Dedupe by `tt`-id — each card has the title link twice (poster + text).

```python
from helpers import goto, wait_for_load, wait, scroll, js
import json, re

def more_like_this(tt_id, limit=12):
    goto(f"https://www.imdb.com/title/{tt_id}/")
    wait_for_load()
    wait(2)

    # Force lazy-load: two big scrolls beat the IntersectionObserver threshold.
    # Positive dy scrolls DOWN in CDP's mouseWheel convention.
    scroll(500, 500, dy=3000); wait(1.0)
    scroll(500, 500, dy=3000); wait(1.2)

    recs = json.loads(js(r"""
    (function () {
      // Find the "More Like This" heading by regex (class hash is unstable).
      var heading = Array.from(document.querySelectorAll(
        'h3, h2, [data-testid*="more"], span.ipc-title__text'
      )).find(function (el) { return /more like this/i.test(el.textContent); });
      if (!heading) return '[]';

      // Walk up to the enclosing section.
      var section = heading.closest('section, [data-testid*="MoreLikeThis"], div');
      for (var i = 0; i < 5 && section && section.querySelectorAll('a[href*="/title/tt"]').length < 2; i++) {
        section = section.parentElement;
      }
      if (!section) return '[]';

      var seen = new Set();
      var out  = [];
      section.querySelectorAll('a[href*="/title/tt"]').forEach(function (a) {
        var m = a.href.match(/\/title\/(tt\d+)\//);
        if (!m || seen.has(m[1]) || m[1] === arguments[0]) return;
        seen.add(m[1]);

        // The card root usually sits a few levels up from the link.
        var card = a.closest(
          '[data-testid*="MoreLikeThis"], .ipc-poster-card, .ipc-sub-grid-item, li'
        ) || a.parentElement;

        var titleEl = card ? card.querySelector(
          '.ipc-title__text, [data-testid*="title"], span'
        ) : null;
        var rating  = card ? card.querySelector('span.ipc-rating-star--rating') : null;

        var txt = (titleEl ? titleEl.textContent : a.textContent).trim();
        // Some titles are prefixed with a rank number on chart-embedded cards.
        txt = txt.replace(/^\d+\.\s*/, '');
        if (!txt) return;

        out.push({
          tt_id:  m[1],
          title:  txt,
          url:    a.href.split('?')[0],
          rating: rating ? parseFloat(rating.textContent) : null
        });
      });
      return JSON.stringify(out);
    })()
    """))

    # Drop the source title itself if it slipped through.
    recs = [r for r in recs if r["tt_id"] != tt_id]
    return recs[:limit]

recs = more_like_this("tt0111161")   # Shawshank -> ~12 recommendations
# [{'tt_id': 'tt0068646', 'title': 'The Godfather', 'rating': 9.2, ...}, ...]
```

---

## Gotchas

**`li.ipc-metadata-list-summary-item` is IMDb's universal list row.** It's reused on chart pages, search results, company credits, and people filmographies. Before writing a bespoke selector for a new IMDb list page, try this one first — it probably works.

**Title text includes the rank prefix on chart pages.** `h3.ipc-title__text` contains `"1. The Shawshank Redemption"`, not `"The Shawshank Redemption"`. Strip with `/^(\d+)\.\s*(.+)$/` — don't assume the rank lives in a separate element.

**Votes are abbreviated and parenthesised.** `span.ipc-rating-star--voteCount` returns `(3.1M)`, `(850K)`, `(12,345)`. Trim the parens, uppercase, and dispatch on trailing `M`/`K` — see `parse_votes` above.

**CSS class hashes churn.** Selectors like `.sc-300a8231-6` (a styled-components hash) WILL break — use them only as a last-resort fallback alongside the stable `ipc-*` names.

**"More Like This" requires scroll to mount.** It is mounted via IntersectionObserver and will not appear in the initial DOM. Two `scroll(500, 500, dy=3000)` calls with a `wait()` after each is the verified minimum. Positive `dy` is scroll-down in CDP's mouseWheel convention (matches the reddit/facebook domain-skills).

**Heading text is the stable anchor, not the container class.** IMDb rewrites its layout containers frequently; the strings "More Like This", "Top Cast", and "User reviews" are kept stable for SEO. Always locate panels by heading-regex and walk up to find the section root.

**Each recommendation card has the title link twice** — once wrapping the poster, once wrapping the text label. Always dedupe by the `tt`-id parsed out of `href`, not by element count.

**Search result classes come in two flavours.** Older result pages use `li.find-title-result`; newer ones use the shared `li.ipc-metadata-list-summary-item`. Query both in one `querySelectorAll` call.

**`s=tt` restricts to titles only.** Drop the param (or use `s=all`) and the result set mixes in people (`nm*`), companies (`co*`), keywords, and user lists. The `tt`-id dedupe still works, but the result shape changes.

**`http_get` works on title pages.** If you only need year, runtime, directors, cast, and the aggregate rating, a plain `http_get(f"https://www.imdb.com/title/{tt_id}/")` gives you the `<script type="application/ld+json">` Movie block in one request — no browser needed. Use the browser only for the chart, search, and "More Like This" panels.

---

## Why this skill exists

Built 2026-04-24 for the LOMA3 "Web Data in Empirical Research" Module III demo, which replicates Fig 4B of Foerderer (2023) — using IMDb's Top 250 as a ground-truth ranked list against which a naïve keyword-search scraper's recall is measured. The four paths above are exactly what that demo exercises live in class.
