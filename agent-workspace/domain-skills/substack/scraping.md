# Substack — Data Extraction

Field-tested against multiple Substack publications on 2026-04-27.
No authentication required for any approach documented here.
All endpoints work via `http_get` without a browser.

---

## TL;DR

Substack exposes a clean public REST API at `{publication}.substack.com/api/v1/`.
Every publication hosted on Substack (custom domain or `{name}.substack.com`)
responds to the same API paths. No API key, no login, no browser required.

**What you can do:**
- List all posts from any publication (`/api/v1/posts`)
- Fetch full post content by slug (`/api/v1/posts/{slug}`)
- Fetch post comments (`/api/v1/post/{post_id}/comments`)
- Read the RSS feed (`/feed`) for title/date/link/description metadata

**Limitations:**
- Paid-only post bodies return a truncated HTML preview for `body_html` (not the full article)
- No cross-publication search API accessible without a logged-in session
- Comment endpoint uses `post_id` (integer), not slug

---

## Approach 1 (Recommended): Publication Post List

`GET https://{subdomain}.substack.com/api/v1/posts?limit=N&offset=N`

Works for any Substack publication. Returns posts sorted newest-first.

```python
from helpers import http_get
import json

def substack_list_posts(publication_url, limit=20, offset=0):
    """List posts from a Substack publication.

    Args:
        publication_url: Base URL of the publication, e.g.
                         'https://www.slowboring.com' or
                         'https://simonwillison.substack.com'
        limit: Number of posts to return (max observed: 100)
        offset: Pagination offset

    Returns list of post dicts with keys: title, subtitle, slug,
    canonical_url, post_date, audience, wordcount, reactions, restacks.
    audience is 'everyone' (free) or 'only_paid' (paywalled).
    """
    url = f"{publication_url.rstrip('/')}/api/v1/posts?limit={limit}&offset={offset}"
    posts = json.loads(http_get(url))
    return [
        {
            "title":         p.get("title"),
            "subtitle":      p.get("subtitle"),
            "slug":          p.get("slug"),
            "url":           p.get("canonical_url"),
            "post_date":     p.get("post_date"),
            "audience":      p.get("audience"),   # 'everyone' or 'only_paid'
            "wordcount":     p.get("wordcount"),
            "reactions":     p.get("reactions"),  # e.g. {"❤": 221}
            "restacks":      p.get("restacks"),
            "cover_image":   p.get("cover_image"),
            "post_id":       p.get("id"),
        }
        for p in posts
    ]

posts = substack_list_posts("https://www.slowboring.com", limit=10)
# [
#   {
#     "title":     "What to make of the generic ballot",
#     "subtitle":  "Plus ties, Mamdani, the Obama legacy, and fundraising's diminishing returns",
#     "slug":      "what-to-make-of-the-generic-ballot",
#     "url":       "https://www.slowboring.com/p/what-to-make-of-the-generic-ballot",
#     "post_date": "2026-04-24T10:03:26.581Z",
#     "audience":  "everyone",
#     "wordcount": 4369,
#     "reactions": {"❤": 221},
#     "restacks":  10,
#     "post_id":   194950421,
#   },
#   ...
# ]

# Filter for free (non-paywalled) posts only
free_posts = [p for p in posts if p["audience"] == "everyone"]
```

### Pagination

```python
def substack_all_posts(publication_url, max_posts=200):
    """Fetch all posts from a publication via paginated API."""
    all_posts = []
    offset = 0
    batch_size = 50
    while len(all_posts) < max_posts:
        batch = substack_list_posts(publication_url, limit=batch_size, offset=offset)
        if not batch:
            break
        all_posts.extend(batch)
        if len(batch) < batch_size:
            break  # last page
        offset += batch_size
    return all_posts[:max_posts]
```

---

## Approach 2: Full Post Content by Slug

`GET https://{subdomain}.substack.com/api/v1/posts/{slug}`

Returns the full post including `body_html` for free posts. Paywalled posts
return a truncated HTML preview for `body_html` (not the full article).

```python
from helpers import http_get
import json, re

def substack_get_post(publication_url, slug):
    """Fetch full content of a single Substack post by slug.

    Returns title, body as plain text, body_html, author, date,
    and metadata. body_html is a truncated preview for paywalled posts.
    """
    url = f"{publication_url.rstrip('/')}/api/v1/posts/{slug}"
    post = json.loads(http_get(url))

    body_html = post.get("body_html")
    body_text = None
    if body_html:
        # Strip HTML tags for plain text
        body_text = re.sub(r'<[^>]+>', ' ', body_html)
        body_text = re.sub(r'\s+', ' ', body_text).strip()

    return {
        "title":         post.get("title"),
        "subtitle":      post.get("subtitle"),
        "slug":          post.get("slug"),
        "url":           post.get("canonical_url"),
        "post_date":     post.get("post_date"),
        "audience":      post.get("audience"),
        "wordcount":     post.get("wordcount"),
        "reactions":     post.get("reactions"),
        "restacks":      post.get("restacks"),
        "body_html":     body_html,   # full article if free; truncated preview if paywalled
        "body_text":     body_text,   # full plain text if free; truncated if paywalled
        "truncated_preview": post.get("truncated_body_text"),  # always present
        "post_id":       post.get("id"),
        "publication_id": post.get("publication_id"),
    }

post = substack_get_post(
    "https://www.slowboring.com",
    "what-to-make-of-the-generic-ballot"
)
# Free post (audience == "everyone"):
# {
#   "title":    "What to make of the generic ballot",
#   "audience": "everyone",
#   "wordcount": 4369,
#   "body_html": "<p>I suppose this isn't a huge surprise...</p>...",  # ~40KB full article
#   "body_text": "I suppose this isn't a huge surprise ...",           # ~25KB plain text
#   "post_id":  194950421,
# }

# Paywalled post (audience == "only_paid"):
# post["body_html"]        -> truncated HTML preview (a few hundred bytes, not the full article)
# post["body_text"]        -> truncated plain text (stripped from truncated HTML)
# post["truncated_preview"] -> short plaintext excerpt (separate, always present)
# Use audience == "everyone" as the reliable signal for full content availability.
```

---

## Approach 3: Post Comments

`GET https://{subdomain}.substack.com/api/v1/post/{post_id}/comments?limit=N`

Note: uses **integer `post_id`**, not slug. Get `post_id` from the post list
or post detail responses.

```python
from helpers import http_get
import json

def substack_get_comments(publication_url, post_id, limit=50):
    """Fetch top-level comments for a Substack post.

    Args:
        publication_url: Base URL of the publication
        post_id: Integer post ID (from post list or post detail)
        limit: Max comments to return

    Returns list of comment dicts.
    """
    url = f"{publication_url.rstrip('/')}/api/v1/post/{post_id}/comments?limit={limit}"
    data = json.loads(http_get(url))
    comments = data.get("comments", [])
    return [
        {
            "comment_id":     c.get("id"),
            "author":         c.get("name"),
            "author_handle":  c.get("handle"),
            "body":           c.get("body"),
            "date":           c.get("date"),
            "reaction_count": c.get("reaction_count"),  # e.g. {"❤": 99}
            "children_count": c.get("children_count"),  # reply count
            "restacks":       c.get("restacks"),
        }
        for c in comments
        if not c.get("deleted")
    ]

comments = substack_get_comments("https://www.slowboring.com", 194950421, limit=10)
# [
#   {
#     "comment_id":     248392394,
#     "author":         "John from FL",
#     "body":           "Sam asks: \"don't they kind of have a point...\"",
#     "date":           "2026-04-24T10:20:21.997Z",
#     "reaction_count": {"❤": 99},
#     "children_count": 3,
#   },
#   ...
# ]
```

---

## Approach 4: RSS Feed (Lightweight Metadata)

`GET https://{subdomain}.substack.com/feed`

Returns an RSS 2.0 feed. Useful when you only need title/date/link/description
without hitting the JSON API. Works as a quick check without parsing JSON.

```python
from helpers import http_get
import re

def substack_rss(publication_url, max_items=20):
    """Fetch recent post metadata via RSS feed.

    Lighter than the JSON API — only returns title, link, pubDate,
    and description (short excerpt). Does not include body_html or wordcount.
    """
    rss = http_get(f"{publication_url.rstrip('/')}/feed")
    items = re.findall(
        r'<item>(.*?)</item>',
        rss,
        re.DOTALL
    )[:max_items]

    results = []
    for item in items:
        title = re.search(r'<title><!\[CDATA\[(.*?)\]\]></title>', item)
        link  = re.search(r'<link>(https?://[^<]+)</link>', item)
        date  = re.search(r'<pubDate>(.*?)</pubDate>', item)
        desc  = re.search(r'<description><!\[CDATA\[(.*?)\]\]></description>', item, re.DOTALL)
        results.append({
            "title":       title.group(1) if title else None,
            "link":        link.group(1) if link else None,
            "pub_date":    date.group(1) if date else None,
            "description": desc.group(1).strip() if desc else None,
        })
    return results

feed = substack_rss("https://www.slowboring.com", max_items=5)
# [
#   {
#     "title":    "Sunday Mailbag + Thread",
#     "link":     "https://www.slowboring.com/p/sunday-mailbag-thread-48b",
#     "pub_date": "Sun, 26 Apr 2026 17:02:04 GMT",
#     "description": "Ask your questions below.",
#   },
#   ...
# ]
```

---

## Publication URL Formats

Substack publications use one of two URL formats:

```python
# Format 1: native subdomain (older or simpler publications)
"https://simonwillison.substack.com"

# Format 2: custom domain (larger publications, purchased domain)
"https://www.slowboring.com"         # Matthew Yglesias — Slow Boring
"https://unchartedterritories.tomaspueyo.com"   # Tomas Pueyo

# Both formats use identical API paths:
# {base_url}/api/v1/posts
# {base_url}/api/v1/posts/{slug}
# {base_url}/api/v1/post/{post_id}/comments
# {base_url}/feed
```

If you only know a publication's Substack handle (e.g., `matthewyglesias`),
the canonical subdomain URL is `https://matthewyglesias.substack.com`. Custom
domain URLs are listed on the publication's about page or in the RSS feed's
`<link>` element.

---

## Gotchas

- **Paywalled post `body_html` is a truncated preview, not `null`** — the API
  returns a short HTML excerpt (typically a few hundred to a few KB). It is
  never `null`. The reliable way to detect full content availability is
  `audience == "everyone"`. For paywalled posts, compare `len(body_html)` to
  `wordcount * ~7` (average bytes per word) — a large gap means truncation.
  `truncated_body_text` (plaintext) is always present regardless of audience.
- **Comments endpoint uses integer `post_id`, not slug** — `/api/v1/post/{id}/comments`
  is correct. `/api/v1/posts/{slug}/comments` returns 404.
- **`reactions` field is a dict with emoji keys**, e.g. `{"❤": 221}` — not a
  plain integer. Sum the values for total reaction count:
  `total = sum(post["reactions"].values())`.
- **`limit` on post list is not strictly capped** — values up to at least 100
  work; beyond that behavior is untested.
- **Custom domains and `{name}.substack.com` are interchangeable** — use
  whichever you have. The `x-sub` response header always reflects the internal
  publication handle.
- **`audience` values**: only `"everyone"` and `"only_paid"` observed. A third
  value `"founding"` exists in Substack's data model but is rare.
- **No unauthenticated cross-publication search** — `substack.com/api/v1/search`
  returns HTML (a React page), not JSON. To find publications, use external
  search engines (`site:substack.com {query}`) or the RSS discovery approach.
- **Podcast posts** have `type == "podcast"` and `podcast_url` set; their
  `body_html` may be a show-notes HTML block. Check `type` to distinguish
  newsletter posts from podcast episodes.
