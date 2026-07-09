# Wikipedia — Scraping & Data Extraction

`https://en.wikipedia.org` — no browser needed. Two clean APIs cover every use case: the REST Content API (fast summaries) and the Action API (search, full text, metadata). Both are free, unauthenticated, and return JSON.

## Do this first

**Use the REST summary API for a single article — one call returns title, description, extract, thumbnail, and page URL.**

```python
import json
data = json.loads(http_get("https://en.wikipedia.org/api/rest_v1/page/summary/Python_(programming_language)"))
# Fields: type, title, displaytitle, namespace, wikibase_item, titles, pageid,
#         thumbnail, originalimage, lang, dir, revision, tid, timestamp,
#         description, description_source, content_urls, extract, extract_html
print(data['title'])        # "Python (programming language)"
print(data['description'])  # "General-purpose programming language"
print(data['extract'])      # plain-text intro paragraph(s)
print(data['thumbnail']['source'])   # thumbnail CDN URL
print(data['originalimage']['source'])  # full-res image URL
```

Use the **Action API** (`/w/api.php`) for search, full article text, sections, categories, and bulk access. The REST API is for single-page lookups; the Action API is for everything else.

**Never use a browser for Wikipedia.** Both APIs are fully server-rendered JSON, load in under 300ms, and have no bot protection.

---

## Common workflows

### Article summary (REST API)

```python
import json

# Fetch summary — title must be URL-encoded with underscores (not spaces)
data = json.loads(http_get(
    "https://en.wikipedia.org/api/rest_v1/page/summary/Machine_learning"
))
print(data['title'])          # "Machine learning"
print(data['description'])    # "Branch of artificial intelligence"
print(data['extract'][:300])  # intro text, plain text
print(data['pageid'])         # 233488
print(data['revision'])       # latest revision ID

# content_urls gives desktop + mobile page URLs
print(data['content_urls']['desktop']['page'])
# "https://en.wikipedia.org/wiki/Machine_learning"
```

Confirmed fields from test: `type, title, displaytitle, namespace, wikibase_item, titles, pageid, thumbnail, originalimage, lang, dir, revision, tid, timestamp, description, description_source, content_urls, extract, extract_html`.

### Random article

```python
import json

rand = json.loads(http_get("https://en.wikipedia.org/api/rest_v1/page/random/summary"))
print(rand['title'], rand['description'])
# Returns a random English Wikipedia article summary each call
```

### Keyword search (Action API)

```python
import json

results = json.loads(http_get(
    "https://en.wikipedia.org/w/api.php"
    "?action=query&list=search&srsearch=machine+learning&format=json&srlimit=10"
))
for r in results['query']['search']:
    print(r['title'], r['pageid'], r['wordcount'])
    # "Machine learning"  233488  ...
    # "Attention (machine learning)"  66001552  ...
    # "Neural network (machine learning)"  21523  ...

# Pagination
total = results['query']['searchinfo']['totalhits']
continue_token = results.get('continue', {}).get('sroffset')  # pass as &sroffset=N
```

Fields per result: `ns, title, pageid, size, wordcount, snippet (HTML), timestamp`.

### Autocomplete / title suggestions

```python
import json

data = json.loads(http_get(
    "https://en.wikipedia.org/w/api.php"
    "?action=opensearch&search=python&limit=10&format=json"
))
titles = data[1]       # list of matching article titles
urls   = data[3]       # corresponding page URLs
print(titles)
# ['Python', 'Python (programming language)', 'Pythonidae', ...]
```

`opensearch` returns a 4-element list: `[query, titles, descriptions, urls]`. Fast (~100ms), good for autocomplete.

### Full article text (intro or complete)

```python
import json

# Intro only (exintro=1)
data = json.loads(http_get(
    "https://en.wikipedia.org/w/api.php"
    "?action=query&titles=Python_(programming_language)"
    "&prop=extracts&explaintext=1&exintro=1&format=json"
))
page = next(iter(data['query']['pages'].values()))
print(page['extract'][:200])  # first intro paragraph(s)

# Full article text (no exintro)
data2 = json.loads(http_get(
    "https://en.wikipedia.org/w/api.php"
    "?action=query&titles=Python_(programming_language)"
    "&prop=extracts&explaintext=1&format=json"
))
page2 = next(iter(data2['query']['pages'].values()))
print(len(page2['extract']))   # ~39,000 chars for Python article
```

`explaintext=1` returns plain text (no wikitext or HTML). Without it you get HTML. Full text can be 20K–100K chars for large articles.

### Article sections

```python
import json

data = json.loads(http_get(
    "https://en.wikipedia.org/w/api.php"
    "?action=parse&page=Python_(programming_language)&prop=sections&format=json"
))
sections = data['parse']['sections']
# 28 sections for the Python article
for s in sections[:5]:
    print(s['number'], s['line'])
    # "1"  "History"
    # "2"  "Design philosophy and features"
    # "3"  "Syntax and semantics"
    # "3.1"  "Indentation"
```

Each section has: `toclevel, level, line, number, index, fromtitle, byteoffset, anchor`.

### Article images

```python
import json

# pageimages — returns the lead/representative image
data = json.loads(http_get(
    "https://en.wikipedia.org/w/api.php"
    "?action=query&titles=Python_(programming_language)"
    "&prop=pageimages&piprop=original&format=json"
))
page = next(iter(data['query']['pages'].values()))
print(page['original']['source'])   # full-res CDN URL
# "https://upload.wikimedia.org/wikipedia/commons/c/c3/Python-logo-notext.svg"
print(page['original']['width'], page['original']['height'])

# REST API also gives thumbnail + originalimage in summary call (see above)
```

### Categories and links

```python
import json

# Categories
data = json.loads(http_get(
    "https://en.wikipedia.org/w/api.php"
    "?action=query&titles=Python_(programming_language)"
    "&prop=categories&cllimit=20&format=json"
))
page = next(iter(data['query']['pages'].values()))
cats = [c['title'].removeprefix('Category:') for c in page.get('categories', [])]

# Wiki-links (outgoing)
data2 = json.loads(http_get(
    "https://en.wikipedia.org/w/api.php"
    "?action=query&titles=Python_(programming_language)"
    "&prop=links&pllimit=50&format=json"
))
page2 = next(iter(data2['query']['pages'].values()))
links = [l['title'] for l in page2.get('links', [])]
```

### Parallel fetch of multiple articles

```python
import json
from concurrent.futures import ThreadPoolExecutor

def fetch_summary(title):
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"
    return json.loads(http_get(url))

titles = ["Python_(programming_language)", "Rust_(programming_language)", "Go_(programming_language)"]
with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_summary, titles))
# No auth, no rate limit in practice for moderate concurrency
```

### Multi-title batch via Action API

```python
import json

# Up to 50 titles in one call using | separator
data = json.loads(http_get(
    "https://en.wikipedia.org/w/api.php"
    "?action=query&titles=Python_(programming_language)|Rust_(programming_language)|Go_(programming_language)"
    "&prop=extracts&explaintext=1&exintro=1&format=json"
))
for pageid, page in data['query']['pages'].items():
    print(page['title'], len(page.get('extract', '')), 'chars')
```

Batch up to 50 titles per request with `|` separator. Returned as a dict keyed by `pageid` (negative IDs like `-1` mean page not found).

---

## Gotchas

- **Title format**: REST API and Action API both need underscores (not spaces) in the URL path. `Python_(programming_language)` not `Python (programming language)`. URL-encoded spaces (`%20`) also work in Action API `titles=` param.

- **Multiple pages dict**: Action API returns `data['query']['pages']` as a dict keyed by pageid string — not a list. Always use `next(iter(data['query']['pages'].values()))` for single-page queries, or iterate `.items()` for batches.

- **Missing page returns pageid=-1**: If a title is not found, the page dict has `"pageid": -1` and a `"missing": ""` key. Check before accessing `extract`.
  ```python
  page = next(iter(data['query']['pages'].values()))
  if page.get('missing') is not None:
      print("Article not found")
  ```

- **`exintro=1` only returns first section**: For disambiguation pages or articles with very short intros, the extract can be a single sentence. Use without `exintro` and split on `\n\n` for full text.

- **REST summary 404**: Non-existent articles return HTTP 404. Wrap in try/except:
  ```python
  try:
      data = json.loads(http_get("https://en.wikipedia.org/api/rest_v1/page/summary/Nonexistent_Page"))
  except Exception as e:
      print("Not found:", e)  # "HTTP Error 404: Not Found"
  ```

- **REST vs Action API extract difference**: Both return the same intro text for `exintro=1`. REST is simpler (one call, consistent schema). Action API is better for batching and additional props in the same request.

- **`prop=sections` only works with `action=parse`, not `action=query`**: `action=query&prop=sections` silently returns zero sections. Use `action=parse&prop=sections` for section lists.

- **No auth, no rate limit (in practice)**: Wikipedia explicitly allows automated access. The Wikimedia API has a soft limit of 200 req/s for unauthenticated bots — far above what single-task scripts will hit. No `User-Agent` override needed; default `Mozilla/5.0` from `http_get` works fine.

- **Wikimedia CDN image URLs are stable**: `upload.wikimedia.org` URLs in `thumbnail.source` and `originalimage.source` are permanent CDN links — safe to store and reuse.

- **`content_urls` gives both desktop and mobile URLs**: `data['content_urls']['desktop']['page']` and `data['content_urls']['mobile']['page']` — use desktop for standard Wikipedia links.
