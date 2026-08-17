# Wikipedia REST API (`en.wikipedia.org/api/rest_v1`)

Supplemental skill for the **Wikimedia REST API v1** — a clean JSON/HTML API
distinct from the older MediaWiki action API (`/w/api.php`).  Use this API
for page summaries, media lists, featured feeds, and random pages.  Use the
action API for full-text search (see gotchas below).

Base URL: `https://en.wikipedia.org/api/rest_v1/`

---

## Critical: User-Agent required

Wikipedia's CDN (Varnish) returns **403** for requests without a descriptive
User-Agent.  Always set one:

```python
WIKI_UA = "MyBot/1.0 (your-contact@example.com)"
```

Pass it as a header in every request.  The `http_get()` helper in
`helpers.py` sets `Mozilla/5.0` by default — override it for Wikipedia.

---

## 1. Page Summary (simplest, most useful)

Returns title, short description, first-paragraph extract, thumbnail, and
content URLs.  **Start here** for any "look up a Wikipedia article" task.

```python
import json
from helpers import http_get

def wiki_summary(title: str) -> dict:
    """Fetch summary for a Wikipedia page title.
    Title may use spaces or underscores — both work.
    Returns dict with: title, description, extract, extract_html, thumbnail,
    content_urls, type ('standard' | 'disambiguation' | 'no-extract').
    """
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
    raw = http_get(url, headers={"User-Agent": WIKI_UA})
    return json.loads(raw)

# Example
data = wiki_summary("Python_(programming_language)")
print(data["title"])        # Python (programming language)
print(data["description"])  # General-purpose programming language
print(data["extract"])      # Python is a high-level, general-purpose...
print(data["thumbnail"]["source"])  # https://upload.wikimedia.org/...
```

**Check `data["type"]` before trusting the extract:**
- `"standard"` — normal article with extract
- `"disambiguation"` — multiple meanings; extract is unreliable, pick a
  specific title instead (e.g. `"Python_(programming_language)"`)
- `"no-extract"` — article exists but has no lead section

---

## 2. Random Page Summary

Returns a 303 redirect to a random article summary.  `urllib` (used by
`http_get`) follows this automatically.

```python
def wiki_random() -> dict:
    raw = http_get(
        "https://en.wikipedia.org/api/rest_v1/page/random/summary",
        headers={"User-Agent": WIKI_UA},
    )
    return json.loads(raw)

article = wiki_random()
print(article["title"], "|", article["extract"][:120])
```

---

## 3. Page HTML (full article)

Returns the full article as Parsoid HTML.  Large pages can be >1 MB.

```python
def wiki_html(title: str) -> str:
    """Returns raw HTML string of the full article."""
    return http_get(
        f"https://en.wikipedia.org/api/rest_v1/page/html/{title}",
        headers={"User-Agent": WIKI_UA},
    )

html = wiki_html("Python_(programming_language)")
# Parse with BeautifulSoup or extract text sections as needed
```

Tip: For structured section extraction, prefer `page/mobile-html/{title}` —
it returns cleaner HTML designed for programmatic consumption.

---

## 4. Media List

Returns all images and media files used in an article.

```python
def wiki_media(title: str) -> list[dict]:
    """Returns list of media items: title, type, srcset, caption."""
    raw = http_get(
        f"https://en.wikipedia.org/api/rest_v1/page/media-list/{title}",
        headers={"User-Agent": WIKI_UA},
    )
    return json.loads(raw)["items"]

items = wiki_media("Python_(programming_language)")
for item in items:
    print(item["type"], item["title"])
    if "srcset" in item:
        print("  2x src:", item["srcset"][-1]["src"])
    if "caption" in item:
        print("  caption:", item["caption"].get("text", ""))
```

Each item has:
- `type` — `"image"` or `"video"` or `"audio"`
- `title` — File namespace title (e.g. `"File:Python-logo-notext.svg"`)
- `leadImage` — bool, true if it's the article's lead/thumbnail image
- `srcset` — list of `{src, scale}` dicts (scale = `"1x"`, `"2x"`)
- `caption` — optional `{html, text}` dict

---

## 5. Page Revision / Metadata

Returns edit history metadata for the current revision.

```python
def wiki_revision(title: str) -> dict:
    """Returns revision metadata: rev, timestamp, user_text, comment, tags."""
    raw = http_get(
        f"https://en.wikipedia.org/api/rest_v1/page/title/{title}",
        headers={"User-Agent": WIKI_UA},
    )
    items = json.loads(raw)["items"]
    return items[0] if items else {}

rev = wiki_revision("Python_(programming_language)")
print(rev["rev"], rev["timestamp"], rev["user_text"])
```

---

## 6. Featured Content Feed

Returns today's (or any past date's) featured article, most-read articles,
picture of the day, and on-this-day events.

```python
def wiki_featured(year: int, month: int, day: int) -> dict:
    """
    Returns dict with keys:
      tfa        — today's featured article (summary-shaped)
      mostread   — {date, articles: [summary + views + rank]}
      image      — picture of the day {title, thumbnail, description}
      onthisday  — list of {year, text, pages: [...]}
    """
    url = f"https://en.wikipedia.org/api/rest_v1/feed/featured/{year}/{month:02d}/{day:02d}"
    raw = http_get(url, headers={"User-Agent": WIKI_UA})
    return json.loads(raw)

feed = wiki_featured(2024, 1, 15)
print("Featured:", feed["tfa"]["title"])
print("Top article:", feed["mostread"]["articles"][0]["title"])
print("On this day:", feed["onthisday"][0]["year"], feed["onthisday"][0]["text"][:80])
```

---

## 7. On This Day

Returns historical events, births, or deaths for a given month/day.

```python
def wiki_onthisday(month: int, day: int, kind: str = "events") -> list[dict]:
    """
    kind options: events | births | deaths | holidays | selected
    Each item: {year, text, pages: [summary-shaped articles]}
    """
    url = f"https://en.wikipedia.org/api/rest_v1/feed/onthisday/{kind}/{month:02d}/{day:02d}"
    raw = http_get(url, headers={"User-Agent": WIKI_UA})
    return json.loads(raw)[kind]

events = wiki_onthisday(1, 15, "births")
for e in events[:5]:
    print(e["year"], e["text"])
```

---

## 8. Bulk: Multiple Summaries

`http_get` is synchronous — for fetching many pages, use a thread pool:

```python
from concurrent.futures import ThreadPoolExecutor
import json
from helpers import http_get

def fetch_summary(title):
    try:
        raw = http_get(
            f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}",
            headers={"User-Agent": WIKI_UA},
        )
        return json.loads(raw)
    except Exception as e:
        return {"title": title, "error": str(e)}

titles = ["Python_(programming_language)", "Rust_(programming_language)", "Go_(programming_language)"]
with ThreadPoolExecutor(max_workers=5) as pool:
    results = list(pool.map(fetch_summary, titles))

for r in results:
    print(r["title"], "|", r.get("description", r.get("error")))
```

---

## Gotchas

### Title encoding
- Spaces and underscores are **equivalent** in titles — both work in the URL.
- URL-encode special characters: `%27` for apostrophe, `%28`/`%29` for
  parentheses (though most HTTP clients do this automatically).
- Always use the **canonical title** from `data["titles"]["canonical"]` when
  chaining calls (e.g., using a summary result to build the next URL).

### Disambiguation pages
- `data["type"] == "disambiguation"` means the title is ambiguous.
- The extract will be a short list of meanings, not a real article lead.
- Append `_(topic)` to the title (e.g., `"Python_(programming_language)"`) to
  reach the specific article.

### Redirects (303)
- `page/random/summary` returns HTTP 303 → a specific article URL.
- `urllib.request.urlopen` (used by `http_get`) **follows redirects
  automatically** — no special handling needed.

### `related` endpoint: not available
- `page/related/{title}` returns **404** ("route not found") as of 2024.
- Use the MediaWiki action API for related-article discovery instead (see
  "Search" below).

### `mobile-sections` endpoint: not available
- `/page/mobile-sections/{title}` is **no longer served** by the REST v1
  gateway — returns 403/404.
- Use `/page/mobile-html/{title}` for a structured HTML alternative, or
  `/page/summary/{title}` for the lead section.

### Full-text search: use the action API
The REST v1 API has **no search endpoint**.  For search, use:

```python
def wiki_search(query: str, limit: int = 5) -> list[dict]:
    """Uses MediaWiki action API — separate from REST v1."""
    import urllib.parse
    params = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srlimit": limit,
        "format": "json",
    })
    raw = http_get(
        f"https://en.wikipedia.org/w/api.php?{params}",
        headers={"User-Agent": WIKI_UA},
    )
    return json.loads(raw)["query"]["search"]

results = wiki_search("python programming language")
for r in results:
    print(r["title"], "|", r["snippet"][:80])
# → Python (programming language) | Python is a high-level...
```

### Rate limits and caching
- Wikipedia REST responses are heavily cached (CDN).  Repeated identical
  requests are essentially free.
- For novel requests, stay under ~50 req/s per the Wikimedia policy.
- `featured` feed is cached per-day; re-requesting the same date is instant.

### 404 for missing pages
- Non-existent titles return `{"status": 404, "type": "Internal error"}`.
- Check `"status" in data` or wrap in try/except before accessing `data["title"]`.

```python
data = wiki_summary("ZZZNOTAPAGE12345")
if data.get("status") == 404:
    print("Page not found")
else:
    print(data["title"])
```
