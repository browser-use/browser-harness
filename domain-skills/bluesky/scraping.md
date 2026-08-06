# Bluesky / AT Protocol — Scraping & Data Extraction

`https://public.api.bsky.app` — fully public REST API, no auth required. Never use a browser for read-only Bluesky tasks.

## Do this first

**Use `http_get` against the AppView API — no auth, no JS rendering, pure JSON.**

Two hosts are in play:

| Host | Use for |
|------|---------|
| `public.api.bsky.app` | Profile, feed, graph (follows/followers/likes/reposts), trending, thread |
| `api.bsky.app` | `searchPosts`, `searchActors` (public.api returns 403 for search) |

All endpoints are XRPC: `GET /xrpc/<nsid>?param=value`.

```python
import json
data = json.loads(http_get("https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor=bsky.app"))
# Key fields: did, handle, displayName, description, followersCount, followsCount,
#             postsCount, avatar, banner, createdAt, indexedAt, pinnedPost
```

---

## Common workflows

### Profile — single actor

```python
import json

# Accept handle OR DID interchangeably
profile = json.loads(http_get(
    "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor=bsky.app"
))
print(profile['did'], profile['handle'], profile['displayName'])
print(profile['followersCount'], profile['postsCount'])
# did:plc:z72i7hdynmk6r22z27h6tvur  bsky.app  Bluesky
# 32902601  742
```

### Resolve handle → DID

```python
import json

r = json.loads(http_get(
    "https://public.api.bsky.app/xrpc/com.atproto.identity.resolveHandle?handle=bsky.app"
))
did = r['did']   # 'did:plc:z72i7hdynmk6r22z27h6tvur'
```

### Batch profiles (up to 25 actors per call)

```python
import json
from urllib.parse import quote

dids = [
    "did:plc:z72i7hdynmk6r22z27h6tvur",
    "did:plc:ry3hbexak5ytsum7aazhpkbv",
]
qs = "&".join(f"actors={quote(d)}" for d in dids)
resp = json.loads(http_get(
    f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfiles?{qs}"
))
for p in resp['profiles']:
    print(p['handle'], p['followersCount'])
```

### Author feed (posts by a user)

```python
import json
from urllib.parse import quote

feed = json.loads(http_get(
    "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
    "?actor=bsky.app&limit=100"
    # filter options: posts_no_replies (default) | posts_with_replies |
    #                 posts_and_author_threads | posts_with_media
))
for item in feed['feed']:
    post = item['post']
    rec  = post['record']
    print(post['uri'], rec['text'][:60])
    print(f"  likes={post['likeCount']} reposts={post['repostCount']} replies={post['replyCount']}")
    # item['reply'] is present if this post IS a reply (contains root + parent refs)

cursor = feed.get('cursor')  # ISO timestamp; pass as &cursor= for next page
```

### Post thread (replies tree)

```python
import json
from urllib.parse import quote

uri = "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.post/3mjprnr5ptk2m"
thread = json.loads(http_get(
    f"https://public.api.bsky.app/xrpc/app.bsky.feed.getPostThread"
    f"?uri={quote(uri)}&depth=6"
))
root = thread['thread']          # keys: post, replies, threadContext, $type
top_replies = root['replies']    # list of thread nodes, each with nested replies
```

### Search posts

```python
import json

# Use api.bsky.app (NOT public.api.bsky.app) for search — public returns 403
results = json.loads(http_get(
    "https://api.bsky.app/xrpc/app.bsky.feed.searchPosts"
    "?q=machine+learning&limit=25&sort=top"
    # sort: top (engagement) | latest (default)
    # lang=en  filters by language tag
    # since=2026-04-01T00:00:00Z  and  until=2026-04-10T00:00:00Z  for date range
))
for p in results['posts']:
    print(p['uri'], p['record']['text'][:80])

cursor = results.get('cursor')  # numeric offset string e.g. "25"; pass as &cursor= for next page
# No hitsTotal field — cursor is None when results are exhausted
```

### Search actors

```python
import json

actors = json.loads(http_get(
    "https://api.bsky.app/xrpc/app.bsky.actor.searchActors?q=climate+scientist&limit=25"
))
for a in actors['actors']:
    print(a['handle'], a['displayName'], a.get('description', '')[:60])
cursor = actors.get('cursor')  # numeric offset
```

### Trending topics

```python
import json

trends = json.loads(http_get(
    "https://public.api.bsky.app/xrpc/app.bsky.unspecced.getTrendingTopics"
))
# Two lists:
for t in trends['topics']:    # real-time trending
    print(t['topic'], t['link'])   # link is a relative /profile/... path

for s in trends['suggested']:  # curated category feeds
    print(s['topic'], s['link'])
```

### Follows and followers

```python
import json
from urllib.parse import quote

# Follows (who this actor follows) — max 100 per page
follows = json.loads(http_get(
    "https://public.api.bsky.app/xrpc/app.bsky.graph.getFollows?actor=bsky.app&limit=100"
))
for f in follows['follows']:
    print(f['did'], f['handle'])
cursor = follows.get('cursor')   # opaque string; URL-encode before passing

# Followers (who follows this actor) — max 100 per page
followers = json.loads(http_get(
    "https://public.api.bsky.app/xrpc/app.bsky.graph.getFollowers?actor=bsky.app&limit=100"
))
cursor = followers.get('cursor')
```

### Likes and reposts on a post

```python
import json
from urllib.parse import quote

uri = "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.post/3mjprnr5ptk2m"

likes = json.loads(http_get(
    f"https://public.api.bsky.app/xrpc/app.bsky.feed.getLikes?uri={quote(uri)}&limit=100"
))
for like in likes['likes']:
    print(like['actor']['handle'], like['createdAt'])
# cursor: ISO timestamp

reposts = json.loads(http_get(
    f"https://public.api.bsky.app/xrpc/app.bsky.feed.getRepostedBy?uri={quote(uri)}&limit=100"
))
```

### Custom / curated feed

```python
import json
from urllib.parse import quote

# Feed generator AT URI from trending link or known feeds
feed_uri = "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.generator/whats-hot"
feed = json.loads(http_get(
    f"https://public.api.bsky.app/xrpc/app.bsky.feed.getFeed?feed={quote(feed_uri)}&limit=30"
))
cursor = feed.get('cursor')  # base64-encoded opaque token
```

### Parallel fetching

```python
import json
from concurrent.futures import ThreadPoolExecutor

handles = ["bsky.app", "jay.bsky.team", "pfrazee.com"]

def fetch_profile(handle):
    return json.loads(http_get(
        f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={handle}"
    ))

with ThreadPoolExecutor(max_workers=5) as ex:
    profiles = list(ex.map(fetch_profile, handles))
# 3 profiles in ~0.23s vs ~0.7s sequential
```

### Cursor pagination (generic pattern)

```python
import json
from urllib.parse import quote

def paginate(base_url, result_key, max_pages=10):
    cursor = None
    for _ in range(max_pages):
        url = base_url + (f"&cursor={quote(str(cursor))}" if cursor else "")
        data = json.loads(http_get(url))
        items = data.get(result_key, [])
        yield from items
        cursor = data.get('cursor')
        if not cursor or not items:
            break

posts = list(paginate(
    "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=bsky.app&limit=100",
    "feed"
))
```

---

## Data model reference

### AT URI anatomy

```
at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.post/3mjprnr5ptk2m
    └─ authority (DID) ──────────────┘  └─ NSID (collection) ──┘  └─ rkey ┘
```

Convert to web URL:
```python
uri = "at://did:plc:z72i7hdynmk6r22z27h6tvur/app.bsky.feed.post/3mjprnr5ptk2m"
_, _, did, collection, rkey = uri.split("/")
web_url = f"https://bsky.app/profile/{did}/post/{rkey}"
```

### Post record (`record` field)

```python
{
    "$type": "app.bsky.feed.post",
    "text": "The full plain text of the post",
    "createdAt": "2026-04-17T20:36:31.198Z",
    "langs": ["en"],
    # If reply:
    "reply": {
        "root":   {"uri": "at://...", "cid": "bafy..."},
        "parent": {"uri": "at://...", "cid": "bafy..."}
    },
    # If facets (links, mentions, hashtags):
    "facets": [ ... ]  # see below
}
```

### Facets (rich text annotations)

Facets annotate byte ranges of `text`. All indices are **UTF-8 byte offsets**, not character positions.

```python
# Three feature $types:
# app.bsky.richtext.facet#link     — hyperlink
# app.bsky.richtext.facet#mention  — @mention (includes resolved DID)
# app.bsky.richtext.facet#tag      — #hashtag

for facet in post['record'].get('facets', []):
    start = facet['index']['byteStart']
    end   = facet['index']['byteEnd']
    text_bytes = post['record']['text'].encode('utf-8')
    slice_text = text_bytes[start:end].decode('utf-8')   # e.g. "@bsky.app" or "#AI"

    for feature in facet['features']:
        ftype = feature['$type']
        if ftype == 'app.bsky.richtext.facet#link':
            print("link →", feature['uri'])
        elif ftype == 'app.bsky.richtext.facet#mention':
            print("mention →", slice_text, "DID:", feature['did'])
        elif ftype == 'app.bsky.richtext.facet#tag':
            print("hashtag →", feature['tag'])
```

### Embed types (on the `post.embed` view field)

| `$type` | Description |
|---------|-------------|
| `app.bsky.embed.images#view` | Image post — `embed['images']` list with `thumb`, `fullsize`, `alt`, `aspectRatio` |
| `app.bsky.embed.external#view` | Link card — `embed['external']` with `uri`, `title`, `description`, `thumb` |
| `app.bsky.embed.record#view` | Quote post — `embed['record']` contains the quoted post |
| `app.bsky.embed.video#view` | Video post |

### CDN image URLs

```
https://cdn.bsky.app/img/{type}/plain/{did}/{cid}

Types: avatar  banner  feed_thumbnail  feed_fullsize
```

Avatar and banner CIDs come from the profile. Post image CIDs come from `post.embed.images[].thumb/fullsize` (already fully formed URLs).

---

## Gotchas

- **Search endpoint split**: `searchPosts` and `searchActors` return HTTP 403 from `public.api.bsky.app`. Use `api.bsky.app` instead. All other read endpoints work on `public.api.bsky.app`.

- **Cursor formats differ by endpoint** — treat them as opaque strings; always URL-encode before appending:
  - `getAuthorFeed`, `getLikes`, `getRepostedBy`: ISO timestamp (`2026-04-16T23:47:25.966Z`)
  - `getFollows`, `getFollowers`: opaque base36 or UUID string
  - `searchPosts`, `searchActors`: numeric offset string (`"25"`, `"50"`)
  - `getFeed`: base64-encoded opaque token
  - When cursor is absent or `None`, results are exhausted.

- **Facet indices are UTF-8 byte offsets, not codepoint indices** — emoji and non-ASCII characters widen the byte span. Always slice on `.encode('utf-8')[start:end].decode('utf-8')`, never on `text[start:end]`.

- **Mention facets include the resolved DID** — `feature['did']` gives you the DID of the mentioned user without a separate resolve call.

- **DID vs handle** — DIDs (`did:plc:...`) are stable permanent identifiers; handles (`user.bsky.social`) can change. Use DIDs for storage and joins. All profile/feed endpoints accept either.

- **AT URI is not a web URL** — The `uri` field on every post is an AT URI (`at://did/.../rkey`). Construct the bsky.app web URL manually: `https://bsky.app/profile/{did}/post/{rkey}`.

- **`getFollows` on bsky.app returns only 5 results** — bsky.app follows only 5 accounts; limit=100 still returns 5. This is correct data, not a bug.

- **`searchPosts` has no `hitsTotal`** — The response contains `posts` and `cursor` only; there is no total count. Paginate until `cursor` is absent.

- **No rate limit headers exposed** — The public API does not return `X-RateLimit-*` headers. Burst of 20 sequential calls completes without errors. Use `ThreadPoolExecutor` with `max_workers≤5` for parallel safety.

- **`item['reply']` vs `record['reply']`** — In a feed response, `item['reply']` (top-level) contains hydrated `root`/`parent` post objects. `item['post']['record']['reply']` contains only `{uri, cid}` refs. Use the former for display context, the latter for thread structure.

- **`getPostThread` depth** — Default depth is 6 levels of replies. Each reply node has a `replies` list with nested thread nodes. Nodes at the depth limit have `$type: app.bsky.feed.defs#threadViewPost` with an empty `replies` array.

- **`getTrendingTopics` links are relative** — `topic['link']` is `/profile/trending.bsky.app/feed/688534877`, not a full URL. Prepend `https://bsky.app` to build the feed URL, or extract the feed AT URI from the path.
