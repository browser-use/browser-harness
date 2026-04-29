# The Guardian — Scraping & Data Extraction

`https://content.guardianapis.com` — 3 M+ articles from 1821 to present. **Never use the browser for The Guardian.** All content is reachable via `http_get` using the free Content API. The `test` key works immediately with no registration; a registered free key raises daily quota limits.

## Do this first

**Search + per-article body fetch is the standard pipeline — one search call for IDs, one call per article for full text.**

```python
import json
from helpers import http_get

# Step 1: search → get article IDs and metadata
search = json.loads(http_get(
    "https://content.guardianapis.com/search"
    "?q=climate+change"
    "&api-key=test"
    "&order-by=newest"
    "&page-size=10"
    "&show-fields=headline,byline,trailText,wordcount,thumbnail"
    "&show-tags=keyword,contributor"
))
resp = search['response']
print(f"Total: {resp['total']}, pages: {resp['pages']}")  # e.g. Total: 129557, pages: 12956
for art in resp['results']:
    print(art['id'], art['webPublicationDate'][:10])
    print("  ", art.get('fields', {}).get('headline', art['webTitle'])[:80])
    print("  byline:", art.get('fields', {}).get('byline', ''))
    print("  tags:", [t['id'] for t in art.get('tags', [])])
# Confirmed output (2026-04-18):
# Total: 129557, pages: 12956
# environment/2026/mar/02/uk-slashes-climate-aid-developing-countries 2026-03-02
#    UK slashes climate aid programmes for developing countries
#    byline: Fiona Harvey Environment editor

# Step 2: fetch full body for a specific article
article_id = "environment/2026/mar/02/uk-slashes-climate-aid-developing-countries"
article = json.loads(http_get(
    f"https://content.guardianapis.com/{article_id}"
    "?api-key=test"
    "&show-fields=headline,byline,bodyText,body,wordcount,firstPublicationDate,thumbnail"
    "&show-tags=all"
))
content = article['response']['content']
fields  = content.get('fields', {})
print(content['id'])
print("wordcount:", fields.get('wordcount'))      # '1223' — string, not int
print("byline:", fields.get('byline'))
print("bodyText:", fields.get('bodyText', '')[:200])  # plain text, no HTML
# body field is the same content wrapped in HTML tags
```

## Common workflows

### Search with filtering

```python
import json
from helpers import http_get

# Date range + section + order
data = json.loads(http_get(
    "https://content.guardianapis.com/search"
    "?api-key=test"
    "&q=artificial+intelligence"
    "&section=technology"            # one section; comma-separate for multiple
    "&from-date=2025-01-01"          # YYYY-MM-DD
    "&to-date=2025-12-31"
    "&order-by=newest"               # newest | oldest | relevance (default)
    "&page-size=50"                  # max 200 per request
    "&show-fields=headline,byline,wordcount,trailText,thumbnail,bodyText"
))
resp = data['response']
print(f"Total: {resp['total']}, currentPage: {resp['currentPage']}, pages: {resp['pages']}")
# Confirmed output (2026-04-18):
# startIndex=1, pageSize=50, currentPage=1, pages=X, orderBy='newest'
```

#### Tag filtering (AND / OR)

```python
# AND: both tags must match — comma-separated
data = json.loads(http_get(
    "https://content.guardianapis.com/search"
    "?api-key=test"
    "&tag=technology/technology,profile/alex-hern"   # articles tagged BOTH
    "&page-size=5&show-fields=headline"
))

# OR: either tag — pipe-separated
data = json.loads(http_get(
    "https://content.guardianapis.com/search"
    "?api-key=test"
    "&tag=technology/technology|environment/environment"  # articles tagged EITHER
    "&page-size=5"
))
```

### Pagination

```python
import json
from helpers import http_get

PAGE_SIZE = 200   # max allowed per call

def search_all_pages(query, max_pages=10):
    results = []
    for page in range(1, max_pages + 1):
        data = json.loads(http_get(
            f"https://content.guardianapis.com/search"
            f"?q={query}&api-key=test"
            f"&page={page}&page-size={PAGE_SIZE}"
            f"&order-by=newest"
            f"&show-fields=headline,byline,wordcount"
        ))
        resp = data['response']
        results.extend(resp['results'])
        if page >= resp['pages']:   # resp['pages'] is int
            break
    return results

# Confirmed: page=200 works; page=99999 returns HTTP 400 Bad Request
# page-size max is 200; page-size=201 returns HTTP 400 Bad Request
```

### Bulk body fetch (concurrent)

```python
import json
from helpers import http_get
from concurrent.futures import ThreadPoolExecutor

def fetch_article(article_id):
    data = json.loads(http_get(
        f"https://content.guardianapis.com/{article_id}"
        "?api-key=test"
        "&show-fields=headline,byline,bodyText,wordcount,firstPublicationDate"
        "&show-tags=keyword,contributor"
    ))
    c = data['response']['content']
    return {
        'id':       c['id'],
        'headline': c.get('fields', {}).get('headline', c['webTitle']),
        'byline':   c.get('fields', {}).get('byline', ''),
        'wordcount': int(c.get('fields', {}).get('wordcount', 0) or 0),
        'bodyText': c.get('fields', {}).get('bodyText', ''),   # plain text, ready for NLP
        'tags':     [t['id'] for t in c.get('tags', [])],
        'url':      c['webUrl'],
    }

article_ids = [
    "environment/2026/mar/02/uk-slashes-climate-aid-developing-countries",
    "us-news/2026/jan/29/donald-trump-perverse-policy-on-climate-change",
]
with ThreadPoolExecutor(max_workers=5) as ex:
    articles = list(ex.map(fetch_article, article_ids))
# Confirmed: concurrent requests work fine with `test` key; no rate limit errors observed
```

### Browse by section

```python
import json
from helpers import http_get

# GET /section-id — same params as /search
data = json.loads(http_get(
    "https://content.guardianapis.com/technology"
    "?api-key=test"
    "&page-size=10"
    "&order-by=newest"
    "&show-fields=headline,byline"
))
resp = data['response']
# resp has extra keys: 'section' (metadata) vs search's generic response
print(resp['section']['webTitle'])   # 'Technology'
print(f"Total articles: {resp['total']}")
for art in resp['results']:
    print(art['webPublicationDate'][:10], art.get('fields', {}).get('headline', art['webTitle']))
# Confirmed: 80 sections total (2026-04-18)
```

### Browse by contributor / tag page

```python
import json
from helpers import http_get

# GET /profile/{contributor-slug}
data = json.loads(http_get(
    "https://content.guardianapis.com/profile/alex-hern"
    "?api-key=test&page-size=5&order-by=newest&show-fields=headline"
))
resp = data['response']
tag = resp['tag']   # contributor metadata
print(tag['webTitle'], tag.get('bio', '')[:80])
# 'Alex Hern  <p>Alex Hern is the Guardian's former UK technology editor</p>'
for art in resp['results']:
    print(art['webPublicationDate'][:10], art.get('fields', {}).get('headline', art['webTitle']))
```

### List all sections

```python
import json
from helpers import http_get

data = json.loads(http_get("https://content.guardianapis.com/sections?api-key=test"))
sections = data['response']['results']   # list of 80 sections
for s in sections:
    print(s['id'], s['webTitle'])
# e.g.: technology Technology, environment Environment, sport Sport, ...
# Each section dict: id, webTitle, webUrl, apiUrl, editions (list)
```

### Tag search and lookup

```python
import json
from helpers import http_get

# Find tags matching a query
data = json.loads(http_get(
    "https://content.guardianapis.com/tags"
    "?q=climate+change&api-key=test&page-size=10"
))
for t in data['response']['results']:
    print(t['id'], t['type'], t.get('sectionId', ''))
# Tag types: keyword, contributor, series, tone, type, blog, paid-content
# Filter by type: &type=contributor  (35899), keyword (25895), series (7381), tone (41)

# Contributor tag has extra fields:
# bio, bylineImageUrl, bylineLargeImageUrl, firstName, lastName
```

## URL and parameter reference

### Endpoints

```
https://content.guardianapis.com/search          # full-text search
https://content.guardianapis.com/{article-id}    # single article
https://content.guardianapis.com/{section-id}    # browse section (same params as search)
https://content.guardianapis.com/profile/{slug}  # browse contributor
https://content.guardianapis.com/sections        # list all 80 sections
https://content.guardianapis.com/tags            # tag search/lookup
```

### Search / browse parameters

| Parameter | Values | Notes |
|---|---|---|
| `api-key` | `test` or registered key | Required on every call; `test` returns `userTier: developer` |
| `q` | query string | Full-text search; supports `AND`, `OR`, `NOT`, phrase `"..."` |
| `section` | section id | e.g. `technology`, `environment`, `sport` |
| `tag` | tag id(s) | Comma = AND, pipe = OR: `tag=a,b` vs `tag=a\|b` |
| `from-date` | `YYYY-MM-DD` | Inclusive lower bound on publication date |
| `to-date` | `YYYY-MM-DD` | Inclusive upper bound |
| `order-by` | `newest`, `oldest`, `relevance` | Default: `relevance` |
| `page` | integer | 1-indexed; HTTP 400 if beyond total pages |
| `page-size` | 1–200 | Default 10; HTTP 400 above 200 |
| `show-fields` | comma-separated field names or `all` | Adds a `fields` object to each result |
| `show-tags` | `keyword`, `contributor`, `series`, `tone`, `type`, `all` | Adds a `tags` list |
| `show-elements` | `image`, `video`, `audio`, `all` | Adds an `elements` list |
| `show-references` | `all` | Adds a `references` list |
| `type` | (tags endpoint) `contributor`, `keyword`, `series`, `tone`, `type`, `blog` | Filter tag search by type |

### `show-fields` values

| Field | Content |
|---|---|
| `headline` | Article title string |
| `byline` | Author name(s) as plain string (may be empty for letters/wire) |
| `standfirst` | HTML subheadline / intro |
| `trailText` | HTML teaser text |
| `body` | Full HTML body |
| `bodyText` | Full body as plain text (no tags — best for NLP) |
| `wordcount` | String, not int — cast with `int(...)` |
| `firstPublicationDate` | ISO-8601 datetime string |
| `lastModified` | ISO-8601 datetime string |
| `thumbnail` | URL of lead image (500px wide) |
| `shortUrl` | Short URL e.g. `https://www.theguardian.com/p/x4z65n` |
| `lang` | ISO language code, e.g. `en` |
| `charCount` | Character count of body as string |
| `newspaperEditionDate`, `newspaperPageNumber` | Print edition metadata |
| `productionOffice` | `UK`, `US`, `AUS` etc |

### Response shape — search/browse

```python
{
    "response": {
        "status":      "ok",
        "userTier":    "developer",   # always 'developer' for test key
        "total":       129557,        # int — total matching articles across all pages
        "startIndex":  1,             # 1-indexed offset of first result on this page
        "pageSize":    10,
        "currentPage": 1,
        "pages":       12956,         # int — total number of pages
        "orderBy":     "relevance",
        "results": [{
            "id":                 "environment/2026/mar/02/...",   # use as article path
            "type":               "article",   # also: interactive, gallery, video, ...
            "sectionId":          "environment",
            "sectionName":        "Environment",
            "webPublicationDate": "2026-03-02T16:37:46Z",
            "webTitle":           "UK slashes climate aid...",
            "webUrl":             "https://www.theguardian.com/environment/...",
            "apiUrl":             "https://content.guardianapis.com/environment/...",
            "pillarId":           "pillar/news",
            "pillarName":         "News",
            "isHosted":           False,
            "fields":  {...},   # only if show-fields used
            "tags":    [...],   # only if show-tags used
            "elements":[...],   # only if show-elements used
        }]
    }
}
```

### Response shape — single article

```python
{
    "response": {
        "status":    "ok",
        "userTier":  "developer",
        "total":     1,
        "content": {
            "id":                 "environment/2026/mar/02/...",
            "type":               "article",
            "sectionId":          "environment",
            "webPublicationDate": "2026-03-02T16:37:46Z",
            "webTitle":           "...",
            "webUrl":             "https://www.theguardian.com/...",
            "apiUrl":             "https://content.guardianapis.com/...",
            "pillarId":           "pillar/news",
            "fields":  {...},
            "tags":    [...],
            "elements":[...],
        }
    }
}
```

### Article `id` as path

The article `id` field (e.g. `environment/2026/mar/02/uk-slashes-climate-aid`) serves as both the path segment for the single-article API call and as the canonical unique key. Store it; never fabricate paths.

## Gotchas

- **`wordcount` is a string, not int.** `fields['wordcount']` returns `'1223'`, not `1223`. Cast with `int(fields.get('wordcount', 0) or 0)` — some articles omit it.

- **`byline` is absent for many articles.** Wire copy, letters, and interactive pieces often have no `byline` field even when `show-fields=byline` is requested. Always use `.get('byline', '')`.

- **`body` contains HTML; `bodyText` is plain.** Both fields carry the same content. Use `bodyText` for NLP/extraction; use `body` only when you need to parse HTML structure (e.g. links, figures). The HTML uses `<aside>` for related-article embeds and `<figure>` for images.

- **`test` key is rate-limited but generously.** The `test` key returns `userTier: developer` and handles concurrent requests without throttling in practice. For production bulk scraping, register at https://bonobo.capi.gutools.io/ for a free key with higher daily quotas.

- **`page-size` max is 200.** Passing `page-size=201` or higher returns HTTP 400. Passing a `page` beyond `resp['pages']` also returns HTTP 400 — check the `pages` field before iterating.

- **Article `id` is the canonical path, not the URL slug alone.** The `id` includes section prefix: `technology/2026/apr/13/dont-make-marshal-fochs-mistake-on-ai`. Pass the entire `id` as the URL path when fetching a single article.

- **Missing API key returns HTTP 401, not a JSON error.** Both missing and invalid keys return `HTTP Error 401: Unauthorized` from `urllib`. Catch `urllib.error.HTTPError` and check `e.code`.

- **`tag` AND/OR syntax is positional.** Comma = AND (all tags must match), pipe character `|` = OR (any tag matches). Mixing both in one `tag=` param is not supported.

- **Section browse vs search.** `GET /technology` (section browse) and `GET /search?section=technology` return the same articles but the section browse response includes a `section` metadata object at the top level; the search response does not. Both paginate identically.

- **Content type is not always `article`.** The `type` field includes `interactive`, `gallery`, `video`, `liveblog`. The `show-fields=body` field may be empty for interactives. Filter with `&type=article` if needed (undocumented but works as a search param).

- **Archive content goes to 1821.** `order-by=oldest` returns genuine 19th-century archive items. Date fields are populated correctly but `bodyText` may be minimal for very old digitised content.

- **SSL certificate errors on macOS Python 3.11.** The system Python on macOS may fail with `CERTIFICATE_VERIFY_FAILED`. Fix: run `pip install certifi` and add an SSL context, or use `uv run` which bundles a correct cert store.
