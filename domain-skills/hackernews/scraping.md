# Hacker News — Data Extraction

`https://news.ycombinator.com` — YCombinator's link aggregator. Three access paths tested: `http_get` DOM scraping, Algolia search API, and the official HN Firebase API. All work without a browser.

## Do this first: pick your access path

| Goal | Best approach | Latency |
|------|--------------|---------|
| Current front page (30 stories, real-time) | `http_get` + regex | ~170ms |
| Historical / keyword search | Algolia search API | ~400ms |
| Full comment tree (nested) | Algolia items API | ~300ms |
| Specific item by ID | Firebase API | ~200ms |
| 500 ranked story IDs | Firebase topstories | ~200ms (+ ~190ms/item after) |

**Never use a browser for read-only HN tasks.** Everything is accessible over HTTP with no auth, no JS rendering needed.

---

## Path 1: http_get front page (fastest for real-time data)

The front page HTML is ~34KB. Story order matches Firebase `/topstories.json` exactly — confirmed identical on 2026-04-18.

```python
import re, html as htmllib

page = http_get("https://news.ycombinator.com")

# Extract all 30 story IDs (in rank order)
story_ids = re.findall(r'<tr class="athing submission" id="(\d+)">', page)

# Extract titles + URLs (same order as IDs)
titles_urls = re.findall(
    r'class="titleline"[^>]*><a href="([^"]*)"[^>]*>(.*?)</a>', page
)

# Extract scores keyed by story ID (job posts have no score row)
scores_by_id = {
    m.group(1): int(m.group(2))
    for m in re.finditer(
        r'<span class="score" id="score_(\d+)">(\d+) points</span>', page
    )
}

# Extract authors keyed by story ID (anchor on score span)
authors_by_id = {}
for m in re.finditer(
    r'<span class="score" id="score_(\d+)">\d+ points</span>'
    r'.*?class="hnuser">(.*?)</a>',
    page, re.DOTALL
):
    authors_by_id[m.group(1)] = m.group(2)

# Extract comment counts keyed by story ID
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
        'title': htmllib.unescape(raw_title),   # MUST unescape — titles contain &#x27; etc.
        'url': url,
        'score': scores_by_id.get(sid),          # None for job posts
        'author': authors_by_id.get(sid),
        'comments': comments_by_id.get(sid, 0),
    })
```

**Gotchas:**
- Titles contain HTML entities (`&#x27;` `&amp;` `&quot;` `&gt;`). Always call `html.unescape()`.
- `<tr class="athing submission" id="...">` — the class is `athing submission`, not just `athing`. The `athing comtr` class is for comment rows.
- Job/hiring posts (YC ads) appear in the list but have no score or author. `scores_by_id.get(sid)` returns `None` for them — check before comparing.
- `re.DOTALL` multi-line patterns can cross story boundaries. Use ID-anchored patterns (as above) instead of positional zip for score/author.
- The page only serves page 1 (30 items). Pages 2–4 exist at `?p=2` etc. but require a login cookie for page 3+.

---

## Path 2: Algolia search API (best for historical / keyword search)

No rate limiting observed. Returns up to 1000 hits per query (`hitsPerPage` max is capped at ~1000 per Algolia plan).

```python
import json

# Keyword search — sorted by relevance
data = json.loads(http_get(
    "https://hn.algolia.com/api/v1/search"
    "?query=llm&tags=story&hitsPerPage=20"
))

# Date-sorted (most recent first)
data = json.loads(http_get(
    "https://hn.algolia.com/api/v1/search_by_date"
    "?tags=story&hitsPerPage=20"
))

# Paginate: add &page=N (0-indexed), up to data['nbPages']-1
```

**Fields returned per story hit:**
```
objectID, title, url, author, points, num_comments,
created_at (ISO 8601), created_at_i (unix ts), story_id,
children (list of comment IDs — flat, not tree),
_tags, _highlightResult
```

**Fields returned per comment hit:**
```
objectID, comment_text, author, story_id, story_title, story_url,
parent_id, created_at, created_at_i, points
```
Note: comment hits use `comment_text`, NOT `text`. Story hits use `story_text` for self-post body.

### Tag filters

Tags are AND by default, OR with parentheses:

```python
# Story types
"tags=story"           # regular link/self posts
"tags=show_hn"         # Show HN
"tags=ask_hn"          # Ask HN
"tags=poll"            # polls
"tags=job"             # job posts

# Combined AND
"tags=story,front_page"          # currently on front page
"tags=story,author_pg"           # stories submitted by pg

# OR
"tags=(ask_hn,show_hn),story"    # Ask OR Show HN

# By story ID (gets story + all its comments)
"tags=story_47806725"
```

### Numeric filters

```python
# Date range (unix timestamps)
"numericFilters=created_at_i>1745000000"
"numericFilters=created_at_i>1700000000,created_at_i<1750000000"

# Point threshold
"numericFilters=points>100"
"numericFilters=points>500,points<1000"
```

### Full Algolia items API (nested comment tree)

```python
import json

thread = json.loads(http_get(
    "https://hn.algolia.com/api/v1/items/47806725"
))
# thread['children'] = list of top-level comment objects
# Each comment: author, text (HTML), created_at, children (nested replies)
# Recursively walk children for full thread

# Total comment count (recursive walk with stack):
stack = list(thread.get('children', []))
total = 0
while stack:
    node = stack.pop()
    total += 1
    stack.extend(node.get('children', []))
```

Confirmed: Algolia items returns 653 total comments for a 659-comment thread (some deleted). `text` field in items API is HTML with `<p>` tags and `<a>` links — may need to strip tags.

---

## Path 3: Official HN Firebase API

Clean JSON, no scraping. Use for fetching specific items or building live feeds.

```python
import json

# Ranked story ID lists (no metadata — just IDs)
top   = json.loads(http_get("https://hacker-news.firebaseio.com/v0/topstories.json"))  # 500 IDs
new   = json.loads(http_get("https://hacker-news.firebaseio.com/v0/newstories.json"))  # 500 IDs
best  = json.loads(http_get("https://hacker-news.firebaseio.com/v0/beststories.json")) # 200 IDs
ask   = json.loads(http_get("https://hacker-news.firebaseio.com/v0/askstories.json"))  # ~32 IDs
show  = json.loads(http_get("https://hacker-news.firebaseio.com/v0/showstories.json")) # ~119 IDs
jobs  = json.loads(http_get("https://hacker-news.firebaseio.com/v0/jobstories.json"))  # ~31 IDs

# Fetch a single item
item = json.loads(http_get(
    "https://hacker-news.firebaseio.com/v0/item/47806725.json"
))
# Fields: id, type, by, title, url, score, descendants (total comment count),
#         time (unix ts), kids (list of top-level comment IDs), text (self-post body)

# Fetch a user profile
user = json.loads(http_get(
    "https://hacker-news.firebaseio.com/v0/user/pg.json"
))
# Fields: id, karma, created (unix ts), about (HTML), submitted (list of item IDs)

# Highest current item ID (useful for polling new items)
maxid = json.loads(http_get("https://hacker-news.firebaseio.com/v0/maxitem.json"))
```

**Firebase vs Algolia tradeoff:**
- Firebase `topstories` gives you 500 IDs in one call but then requires one HTTP call per item (~190ms each). Fetching all 500 items sequentially would take ~100 seconds.
- Algolia returns full story data (title, points, author, comments) in one call for up to ~1000 results.
- For "top 30 stories with full metadata": use `http_get` front page scrape (170ms total). For "top 500 stories with full metadata": use Algolia with `tags=front_page` or loop pages.

---

## Comment thread HTML (item page)

For a large thread, the item page HTML (~1MB for 659 comments) loads ALL comments flat in a single request — no pagination, no JS required.

```python
import re, html as htmllib

page = http_get("https://news.ycombinator.com/item?id=47806725")

# Count all comment IDs
comment_ids = re.findall(r'<tr class="athing comtr" id="(\d+)">', page)
# len(comment_ids) matches total comment count

# Extract comment texts (careful: text spans multiple lines with <p> tags)
# Use Algolia items API instead for structured access
```

For structured comment access prefer Algolia items API — it returns a proper nested tree. The HTML item page is useful only when you need approximate comment count without an API call.

---

## Do NOT use a browser for HN

All data is in plain HTML or JSON APIs. `goto_url()` + `wait_for_load()` takes 3–8 seconds; `http_get` takes 170–400ms. The JS `querySelectorAll` approach works (tested, returns correct data) but is 20–50x slower with no benefit.
