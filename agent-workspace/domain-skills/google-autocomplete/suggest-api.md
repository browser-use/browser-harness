# Google Suggest — autocomplete API for keyword expansion

Field-tested 2026-07-24. This is the fastest way to get real (not invented) long-tail keyword variants for SEO/keyword-research tasks — no browser needed, plain `http_get`/`urllib`.

## Endpoint

```
https://suggestqueries.google.com/complete/search?client=firefox&hl=en&q=<url-encoded query>
```

`client=firefox` returns clean JSON (`["<query>", ["suggestion 1", "suggestion 2", ...]]`) with no JSONP wrapper to strip — simpler than `client=chrome` which wraps in extra metadata. Suggestions come back in Google's own ranked order (most-searched-adjacent first, roughly).

```python
import json, urllib.request, urllib.parse

def autocomplete(q, hl="en"):
    url = "https://suggestqueries.google.com/complete/search?client=firefox&hl=" + hl + "&q=" + urllib.parse.quote(q)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())[1]
```

No auth, no rate-limit hit even across dozens of sequential calls in one session (unlike `pytrends`/Google Trends, which 429s fast — see `google-trends/explore.md`). A `time.sleep(0.3)` between calls is plenty polite; not strictly required.

## Expansion technique

1. Seed term alone → gets the "canonical" top-10 completions.
2. Seed + single letter (`"schulte table a"`, `"schulte table b"`, ...) → cycles through a different top-10 for each letter, effectively unlocking Google's full completion list beyond the first 10 (Google caps each response at ~10 regardless of query).
3. Seed + modifier (`free`, `online`, `app`, `vs`, `how`, `best`) → surfaces intent-specific long tail (transactional vs informational vs comparison).
4. Empty result (`[]`) is itself a signal — the seed+modifier combo has essentially no real search volume/pattern (e.g. `"focus training how"` → `[]`, `"aim trainer cognitive"` → `[]`).

## No volume data

This endpoint returns *which strings people type*, not *how often*. It's a discovery tool, not a sizing tool — pair with Google Trends (relative-index comparison) and manual SERP checks (who ranks = competition signal) to get a fuller picture. See `google-trends/explore.md` for the comparison-chart trick.
