# Hacker News — Data Extraction

`https://news.ycombinator.com` — YCombinator's link aggregator. Three access paths: `http_get` DOM scraping, Algolia search API, and the official HN Firebase API. All work without a browser, no auth required.

## Do this first: pick your access path

| Goal | Best approach | Latency (measured) |
|------|--------------|---------|
| Current front page (30 stories, real-time) | `http_get` + regex | ~170ms |
| Historical / keyword search | Algolia search API | ~370ms |
| Full nested comment tree | Algolia items API | ~1000ms |
| Specific item by ID | Firebase API | ~170ms |
| 500 ranked story IDs | Firebase topstories | ~200ms |
| Parallel bulk item fetch | Firebase + ThreadPoolExecutor | ~210ms for 5 items |

**Never use a browser for read-only HN tasks.** Everything is accessible over HTTP with no auth, no JS rendering needed.

---

## Path 1: Algolia search API (best for search and filtering)

No auth, no rate limiting observed. Two endpoints: `search` (relevance-ranked) and `search_by_date` (newest first).

```python
import json

# Keyword search — sorted by relevance
data = json.loads(http_get(
    "https://hn.algolia.com/api/v1/search"
    "?query=llm&tags=story&hitsPerPage=20"
))
# data keys: hits, nbHits, nbPages, page, hitsPerPage, query, processingTimeMS

# Date-sorted (most recent first) — query='' returns all
data = json.loads(http_get(
    "https://hn.algolia.com/api/v1/search_by_date"
    "?tags=story&hitsPerPage=20"
))

# Paginate: add &page=N (0-indexed). Max page index = data['nbPages']-1
# hitsPerPage max = 1000. Pages beyond nbPages return 0 hits.
```

**Fields per story hit** (from `search` / `search_by_date`):
```
objectID       – string ID ("44567857")
story_id       – int version of the same ID
title          – story title
url            – linked URL (absent for self-posts)
author         – submitter username
points         – upvote count (int)
num_comments   – total comment count including replies (int)
children       – list of TOP-LEVEL comment IDs only (ints) — NOT all comment IDs
created_at     – ISO 8601 string ("2025-07-15T04:35:35Z")
created_at_i   – unix timestamp (int)
updated_at     – last index update timestamp
story_text     – self-post body (HTML), only present for Ask HN / self-posts
_tags          – ["story", "author_username", "story_44567857"]
```

**Fields per comment hit** (when `tags=comment`):
```
objectID, author, comment_text,  ← "comment_text" NOT "text"
story_id, story_title, story_url,
parent_id, created_at, created_at_i,
points  ← usually None for comments
```

### Tag filters

Tags are AND by default, OR with parentheses:

```python
# Story types
"tags=story"                    # regular link/self posts
"tags=show_hn"                  # Show HN
"tags=ask_hn"                   # Ask HN
"tags=poll"                     # polls
"tags=job"                      # job posts
"tags=comment"                  # comments only

# Combined AND
"tags=story,front_page"         # currently on front page (~75 items)
"tags=story,author_pg"          # stories submitted by user 'pg'

# OR
"tags=(ask_hn,show_hn)"         # Ask OR Show HN (no story tag needed)

# All items in a thread (story + all its comments)
"tags=story_44567857"
```

### Numeric filters

```python
# Date range (unix timestamps)
"numericFilters=created_at_i>1745000000"
"numericFilters=created_at_i>1700000000,created_at_i<1750000000"

# Point threshold
"numericFilters=points>500"
"numericFilters=points>100,points<500"
```

Combine tags and numericFilters freely:
```python
data = json.loads(http_get(
    "https://hn.algolia.com/api/v1/search"
    "?query=rust&tags=story"
    "&numericFilters=points>100"
    "&hitsPerPage=20&page=0"
))
```

---

## Path 2: Algolia items API (full nested comment tree)

Returns the story with its full comment tree, recursively nested. ~1000ms for a large thread.

```python
import json

thread = json.loads(http_get(
    "https://hn.algolia.com/api/v1/items/44567857"
))
# thread keys: id, type, author, title, url, text, points, parent_id,
#              story_id, created_at, created_at_i, options, children

# children = list of TOP-LEVEL comment objects (each with their own children)
# comment object keys: same as thread keys — author, text (HTML), created_at, children

# Walk all comments recursively:
stack = list(thread.get('children', []))
total = 0
while stack:
    node = stack.pop()
    total += 1
    stack.extend(node.get('children', []))
# total = all comments (deleted items are omitted, so count may be < descendants)
```

**Items API comment `text` field is HTML** — contains `<p>` tags, `<a>` links, HTML entities (`&#x27;` `&gt;` `&#x2F;`). Strip tags if you need plain text.

---

## Path 3: http_get front page (fastest for real-time)

The front page HTML is ~34KB. Matches Firebase `/topstories.json` rank order exactly.

```python
import re, html as htmllib

page = http_get("https://news.ycombinator.com")

story_ids = re.findall(r'<tr class="athing submission" id="(\d+)">', page)

titles_urls = re.findall(
    r'class="titleline"[^>]*><a href="([^"]*)"[^>]*>(.*?)</a>', page
)

scores_by_id = {
    m.group(1): int(m.group(2))
    for m in re.finditer(
        r'<span class="score" id="score_(\d+)">(\d+) points</span>', page
    )
}

comments_by_id = {
    m.group(1): int(m.group(2))
    for m in re.finditer(
        r'href="item\?id=(\d+)">(\d+)&nbsp;comments</a>', page
    )
}

stories = []
for i, sid in enumerate(story_ids):
    url, raw_title = titles_urls[i] if i < len(titles_urls) else ('', '')
    stories.append({
        'rank': i + 1,
        'id': sid,
        'title': htmllib.unescape(raw_title),
        'url': url,
        'score': scores_by_id.get(sid),       # None for job posts
        'comments': comments_by_id.get(sid, 0),
    })
```

Page 2–4 at `?p=2` etc., but page 3+ requires a login cookie.

---

## Path 4: Official HN Firebase API

Clean JSON, no scraping. Use for fetching specific items or live feeds.

```python
import json

# Ranked ID lists (IDs only — no metadata)
top   = json.loads(http_get("https://hacker-news.firebaseio.com/v0/topstories.json"))   # 500 IDs
new   = json.loads(http_get("https://hacker-news.firebaseio.com/v0/newstories.json"))   # 500 IDs
best  = json.loads(http_get("https://hacker-news.firebaseio.com/v0/beststories.json"))  # 200 IDs
ask   = json.loads(http_get("https://hacker-news.firebaseio.com/v0/askstories.json"))   # ~31 IDs
show  = json.loads(http_get("https://hacker-news.firebaseio.com/v0/showstories.json"))  # ~131 IDs
jobs  = json.loads(http_get("https://hacker-news.firebaseio.com/v0/jobstories.json"))   # ~31 IDs

# Single item — story fields
item = json.loads(http_get(
    "https://hacker-news.firebaseio.com/v0/item/44567857.json"
))
# Story keys: id, type, by, title, url, score, descendants, time, kids, text
# Comment keys: id, type, by, text, time, parent, kids

# User profile
user = json.loads(http_get(
    "https://hacker-news.firebaseio.com/v0/user/pg.json"
))
# Keys: id, karma, created (unix ts), about (HTML), submitted (list of item IDs)

# Highest current item ID (for polling new items)
maxid = json.loads(http_get("https://hacker-news.firebaseio.com/v0/maxitem.json"))

# Recently changed items and profiles
updates = json.loads(http_get("https://hacker-news.firebaseio.com/v0/updates.json"))
# keys: items (list of IDs), profiles (list of usernames)
```

### Parallel fetch of multiple Firebase items

Firebase has no rate limit concern at small scale. 5 items in ~210ms parallel vs ~850ms sequential:

```python
import json
from concurrent.futures import ThreadPoolExecutor

top_ids = json.loads(http_get("https://hacker-news.firebaseio.com/v0/topstories.json"))[:30]

def fetch_item(iid):
    return json.loads(http_get(
        f"https://hacker-news.firebaseio.com/v0/item/{iid}.json"
    ))

with ThreadPoolExecutor(max_workers=10) as ex:
    items = list(ex.map(fetch_item, top_ids))
# ~600ms for 30 items parallel vs ~5100ms sequential
```

---

## Gotchas

### Field naming differs across APIs

This is the #1 source of bugs. The three APIs use **different names** for the same data:

| Field | Algolia search hit | Algolia items API | Firebase item |
|-------|--------------------|-------------------|---------------|
| Vote score | `points` | `points` | `score` |
| Total comments | `num_comments` | *(absent)* | `descendants` |
| Submitter | `author` | `author` | `by` |
| Child comment IDs | `children` (int list) | `children` (object list) | `kids` (int list) |

- Algolia `search` hit `children` = flat list of **top-level comment IDs only** (ints). A story with 1628 `num_comments` has 137 entries in `children`.
- Algolia `items` API `children` = list of **full nested comment objects** (dicts with their own `children`).
- Firebase `kids` = list of **top-level comment IDs** (ints), same as Algolia search `children`.

### Comment text field name

- Algolia `search` endpoint with `tags=comment`: field is `comment_text`
- Algolia `items` API nested comment objects: field is `text` (HTML)
- Firebase comment item: field is `text` (HTML with entities)

### HTML entities in text fields

Algolia `items` API comment `text` and Firebase `text` both contain raw HTML: `<p>` tags, `<a>` links, and HTML entities (`&#x27;` = `'`, `&#x2F;` = `/`, `&gt;` = `>`). Algolia `search` hit titles and `story_text` also contain entities. Always unescape before displaying.

### Algolia `search` hit has no `num_comments` on items API

If you fetch `items/ID`, the returned object has no `num_comments` field. Use `descendants` from Firebase or count by walking `children` recursively.

### Deleted and dead items return null

Firebase returns `null` (Python `None`) for deleted or dead items. Check before accessing fields:
```python
item = json.loads(http_get(f"https://hacker-news.firebaseio.com/v0/item/{iid}.json"))
if item is None:
    continue  # deleted/dead
```

### Algolia page cap

Algolia caps at 1000 pages max. Requesting `page=1000` returns `nbPages: 0, hits: []`. Max retrievable results per query = `hitsPerPage * min(nbPages, 1000)` — effectively 1,000,000 items but Algolia won't return more than 1000 pages regardless.

### Job posts have no score or author on the front page

Front-page HTML scrape: job/hiring posts appear in `story_ids` but have no `<span class="score">` row. `scores_by_id.get(sid)` returns `None` — don't compare directly to integers.

### Title HTML entities on front page

Front-page titles contain HTML entities (`&#x27;` `&amp;` `&quot;`). Always call `html.unescape()` on raw title strings from regex.

### Firebase vs Algolia for bulk data

- Firebase `topstories` gives 500 IDs in one call, then one HTTP call per item (~170ms each) — too slow sequentially for large sets.
- Algolia `search?tags=front_page` returns full story metadata for all ~75 current front-page stories in one call.
- For top-30 with metadata: front-page HTML scrape is fastest (170ms total). For top-500 with metadata: Algolia pagination (multiple calls of 1000 hits each).

### `athing` vs `athing comtr` CSS classes

Front-page scrape: `<tr class="athing submission" id="...">` are story rows. `<tr class="athing comtr" id="...">` are comment rows (on item pages). Both match `athing` — use the full class string.
