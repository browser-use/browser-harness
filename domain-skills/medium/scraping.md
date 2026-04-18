# Medium — Data Extraction

`https://medium.com` — blogging platform. Three access paths tested and validated: the undocumented `?format=json` endpoint (fastest for article + publication data), the undocumented GraphQL API (best for targeted metric lookups), and RSS feeds (best for recent posts lists without auth). No browser needed for any read-only task.

## Do this first: pick your access path

| Goal | Best approach | Latency |
|------|--------------|---------|
| Article metadata + full body | `?format=json` on article URL | ~400ms |
| Article metrics only (claps, visibility) | GraphQL `post(id:)` | ~275ms |
| Author profile + follower count | GraphQL `user(username:)` | ~220ms |
| Recent posts for a user (up to 10) | `?format=json` on profile URL | ~240ms |
| Recent posts for a publication | `?format=json` on publication URL | ~300ms |
| Paginated post list (feed) | RSS feed | ~260ms |
| Full article body as HTML | RSS `content:encoded` field | ~260ms |
| Publication subscriber count | `?format=json` on publication URL | ~300ms |

**Never use a browser for read-only Medium tasks.** All article content, metadata, and metrics are available over HTTP. Browser is only needed for authenticated actions (clapping, posting, account management).

---

## The XSSI prefix

Every `?format=json` response starts with the anti-hijacking prefix `])}while(1);</x>` before the JSON. **Strip it before parsing.** The helper below handles this.

```python
import urllib.request, gzip, json, re

def medium_json(url):
    """Fetch any Medium URL with ?format=json and return parsed dict.
    Strips the XSSI prefix ])}while(1);</x> automatically.
    Works on: article URLs, user profile URLs, publication URLs.
    Does NOT work on: search pages, /latest, profile stream API.
    """
    sep = '&' if '?' in url else '?'
    req = urllib.request.Request(
        url + sep + 'format=json',
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json, */*",
            "Accept-Encoding": "gzip",
        }
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        text = raw.decode()
    # Strip everything before the first {
    return json.loads(re.sub(r'^[^\{]+', '', text))
```

---

## Path 1: `?format=json` — article metadata + body (fastest for articles)

Append `?format=json` to any article URL. Returns full metadata, virtuals (metrics), and the complete article body in a structured `bodyModel`. No auth required for public and subscriber-locked articles alike — the metadata and full body are always returned, but paywalled body content in a browser would be truncated.

```python
data = medium_json("https://medium.com/@karpathy/software-2-0-a64152b37c35")
payload = data['payload']
val     = payload['value']        # article fields
refs    = payload['references']   # User, Social, SocialStats dicts keyed by ID

# --- Article fields ---
title       = val['title']                              # "Software 2.0"
article_id  = val['id']                                 # "a64152b37c35"
creator_id  = val['creatorId']                          # "ac9d9a35533e"
slug        = val['uniqueSlug']                         # "software-2-0-a64152b37c35"
url         = val['canonicalUrl']                       # "https://medium.com/@karpathy/..."
first_pub   = val['firstPublishedAt']                   # unix ms: 1510438733751
last_pub    = val['latestPublishedAt']                  # unix ms: 1615659523264
visibility  = val['visibility']                         # 0=public, 2=subscriber-locked
is_locked   = val['isSubscriptionLocked']               # True if paywalled
locked_src  = val['lockedPostSource']                   # 0=free, 1=Medium Partner Program

# --- Metrics (in val['virtuals']) ---
virtuals    = val['virtuals']
clap_count  = virtuals['totalClapCount']                # 60865 (all claps, including multi-clap)
recommends  = virtuals['recommends']                    # 8846 (unique clappers)
read_time   = virtuals['readingTime']                   # 8.79811320754717 (minutes, float)
word_count  = virtuals['wordCount']                     # 2146

# --- Tags ---
tags = [t['slug'] for t in virtuals['tags']]
# ['machine-learning', 'artificial-intelligence', 'programming', 'software-development', 'future']

# --- Author (from references) ---
user = refs['User'][creator_id]
author_name = user['name']          # "Andrej Karpathy"
author_handle = user['username']    # "karpathy"
author_bio  = user['bio']           # "I like to train deep neural nets on large datasets."
author_twitter = user['twitterScreenName']  # "karpathy"

# --- Follower count (from SocialStats) ---
ss = refs['SocialStats'][creator_id]
follower_count  = ss['usersFollowedByCount']   # 60027
following_count = ss['usersFollowedCount']     # 183
```

### Detect paywall

```python
# Paywalled (Medium Partner Program): isSubscriptionLocked=True, visibility=2, lockedPostSource=1
# Free: isSubscriptionLocked=False, visibility=0, lockedPostSource=0
is_paywalled = val['isSubscriptionLocked']   # True / False
```

Confirmed on real TDS articles: paywalled articles return `isSubscriptionLocked=True`, `visibility=2`, `lockedPostSource=1`. Free articles: all three are `False`/`0`.

### Article body

The full body is in `val['content']['bodyModel']['paragraphs']` — a list of dicts:

```python
paragraphs = val['content']['bodyModel']['paragraphs']

# Paragraph types (confirmed for this article):
# type=1  -> body text (P)
# type=3  -> heading (H1/H2)
# type=4  -> image (text is empty; metadata has image ID)

# Reconstruct plain text:
text_paras = [p['text'] for p in paragraphs if p.get('text')]
full_text   = '\n\n'.join(text_paras)
```

---

## Path 2: GraphQL API — targeted metric lookups

`POST https://medium.com/_/graphql` with a JSON body. No auth, no CSRF token required.
Returns HTTP 200 with JSON even for unauthenticated queries. Invalid fields return HTTP 400 — do not assume a field exists without testing first.

```python
import json, urllib.request, gzip

def gql(query):
    body = json.dumps({"query": query}).encode()
    req  = urllib.request.Request(
        "https://medium.com/_/graphql",
        data=body,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            raw = gzip.decompress(raw)
        return json.loads(raw.decode())
```

### Fetch article metrics (fastest)

```python
result = gql("""
{
  post(id: "a64152b37c35") {
    title
    id
    firstPublishedAt
    latestPublishedAt
    visibility
    uniqueSlug
    canonicalUrl
    mediumUrl
    isLocked
    clapCount
    readingTime
    wordCount
  }
}
""")
post = result['data']['post']
# post['visibility']  -> "PUBLIC" | "LOCKED"  (string, not numeric)
# post['isLocked']    -> False | True
# post['clapCount']   -> 60865  (same as totalClapCount in format=json)
# post['readingTime'] -> 8.79811320754717  (minutes)
# post['wordCount']   -> 2146
```

**Confirmed working `post()` fields:** `title`, `id`, `createdAt`, `updatedAt`, `firstPublishedAt`, `latestPublishedAt`, `visibility`, `uniqueSlug`, `canonicalUrl`, `mediumUrl`, `isLocked`, `clapCount`, `readingTime`, `wordCount`

**Nested object that works:** `topics { name slug }`, `creator { name username }`, `collection { name id slug description domain creator { name username } }`

**Fields that return HTTP 400 (not available):** `tags`, `author`, `recommends`, `content`, `publication`, `responses`, `sequence`

### Fetch author profile

```python
result = gql("""
{
  user(username: "karpathy") {
    name
    username
    id
    bio
    imageId
    twitterScreenName
    mediumMemberAt
    socialStats {
      followerCount
      followingCount
    }
  }
}
""")
user = result['data']['user']
# user['name']                       -> "Andrej Karpathy"
# user['id']                         -> "ac9d9a35533e"
# user['bio']                        -> "I like to train deep neural nets on large datasets."
# user['twitterScreenName']          -> "karpathy"
# user['socialStats']['followerCount'] -> 60028
# user['mediumMemberAt']             -> 0 (not a member); nonzero = unix ms join date
```

**Confirmed working `user()` fields:** `name`, `username`, `id`, `bio`, `imageId`, `twitterScreenName`, `mediumMemberAt`, `socialStats { followerCount followingCount }`

**Fields that return HTTP 400:** `followerCount` (top-level), `followingCount` (top-level), `postCount`

### Fetch collection (publication) by ID

The GraphQL `collection()` query only accepts `id`, not `slug`. Get the ID from `?format=json` on the publication page.

```python
# TDS Archive id: 7f60cf5620c9  (from medium.com/towards-data-science?format=json)
result = gql("""
{
  collection(id: "7f60cf5620c9") {
    name
    id
    slug
    description
    domain
    creator { name username }
  }
}
""")
coll = result['data']['collection']
# coll['name'] -> "TDS Archive"
# coll['slug'] -> "data-science"
```

---

## Path 3: RSS feeds (best for recent posts list + article bodies)

Works with plain `http_get`. Returns up to 10 most recent posts. Full article HTML is in `content:encoded`. No clap count or visibility info in RSS.

```python
import re
from helpers import http_get

def parse_rss_items(rss_xml):
    """Extract items from Medium RSS feed. Returns list of dicts."""
    def cdata(tag, text):
        m = re.search(rf'<{tag}[^>]*><!\[CDATA\[(.*?)\]\]></{tag}>', text, re.DOTALL)
        return m.group(1).strip() if m else None

    items = []
    for raw in re.findall(r'<item>(.*?)</item>', rss_xml, re.DOTALL):
        # link is plain text (not CDATA)
        link_m = re.search(r'<link>(.*?)</link>', raw, re.DOTALL)
        items.append({
            'title':    cdata('title', raw),
            'link':     link_m.group(1).strip() if link_m else None,
            'pubDate':  cdata('pubDate', raw),
            'creator':  cdata('dc:creator', raw),
            'tags':     re.findall(r'<category><!\[CDATA\[(.*?)\]\]></category>', raw),
            'body_html': cdata('content:encoded', raw),   # full article HTML
        })
    return items

# User feed (up to 10 latest posts)
rss = http_get("https://medium.com/feed/@karpathy")
posts = parse_rss_items(rss)
# posts[0]['title']    -> "Software 2.0"
# posts[0]['pubDate']  -> "Sat, 11 Nov 2017 22:18:53 GMT"
# posts[0]['creator']  -> "Andrej Karpathy"
# posts[0]['tags']     -> ['programming', 'software-development', 'artificial-intelligence', 'future', 'machine-learning']
# posts[0]['link']     -> "https://karpathy.medium.com/software-2-0-a64152b37c35?source=rss-..."
# posts[0]['body_html'] -> full article body as HTML string (~15KB for this article)

# Publication feed (up to 10 latest posts)
rss_pub = http_get("https://medium.com/feed/towards-data-science")
pub_posts = parse_rss_items(rss_pub)
```

**RSS limitations:**
- RSS does not include clap count, view count, or paywall status.
- `body_html` contains the full article body as HTML, including `<p>`, `<strong>`, `<a>`, `<img>` tags.
- Pagination is not supported — RSS always returns the 10 most recent posts.

---

## Path 4: `?format=json` on user profile — recent posts with metrics

Better than RSS when you need clap counts alongside post list. Returns up to `limit` posts (default 10) plus full author metadata.

```python
data = medium_json("https://medium.com/@karpathy?limit=10")
payload = data['payload']

user = payload['user']
# user['name']     -> "Andrej Karpathy"
# user['username'] -> "karpathy"
# user['bio']      -> "I like to train deep neural nets on large datasets."

refs = payload['references']
ss   = refs['SocialStats'][user['userId']]
# ss['usersFollowedByCount'] -> 60028 (followers)
# ss['usersFollowedCount']   -> 183   (following)

posts = refs.get('Post', {})  # dict keyed by post ID
for pid, p in posts.items():
    v = p['virtuals']
    print(p['title'], v['totalClapCount'], round(v['readingTime'], 1))

# Paginate: use paging['next'] from payload
paging = payload['paging']
next_params = paging['next']
# next_params = {'limit': 10, 'to': '1495652975362', 'source': 'overview', 'page': 2, 'ignoredIds': []}
# Append as query params to the same profile URL to get next page
next_url = (
    f"https://medium.com/@{user['username']}"
    f"?limit={next_params['limit']}&to={next_params['to']}"
    f"&source={next_params['source']}&page={next_params['page']}"
)
data2 = medium_json(next_url)
# Note: karpathy has only 8 total posts — pagination returns same refs on page 2
```

---

## Path 5: `?format=json` on publication page

Returns publication metadata and recent posts with metrics.

```python
data = medium_json("https://medium.com/towards-data-science")
payload = data['payload']

coll = payload['collection']
# coll['name']            -> "TDS Archive"
# coll['slug']            -> "data-science"
# coll['description']     -> full description string
# coll['subscriberCount'] -> 828527
# coll['metadata']['followerCount'] -> 828527
# coll['tags']            -> ['DATA SCIENCE', 'MACHINE LEARNING', ...]

posts = payload['references'].get('Post', {})
for pid, p in posts.items():
    v = p['virtuals']
    print(p['title'], v['totalClapCount'], p['isSubscriptionLocked'])
# Also includes: p['visibility'] (0=free, 2=paywalled)

# Paginate (same pattern as user profile)
paging = payload['paging']
# paging['next'] = {'to': '1738573325936', 'page': 3}
```

---

## Retrieving the article ID from a URL

The `id` is the last 12 hex chars of a Medium article URL slug:

```python
import re

url = "https://medium.com/@karpathy/software-2-0-a64152b37c35"
article_id = re.search(r'-([a-f0-9]{12})$', url.rstrip('/').split('?')[0])
if article_id:
    article_id = article_id.group(1)   # "a64152b37c35"
```

This ID is the same across all URL forms (`medium.com/@user/slug`, `user.medium.com/slug`, `medium.com/publication/slug`).

---

## Gotchas

- **HTTP 403 on plain `http_get`** — The default `http_get` helper sends `User-Agent: Mozilla/5.0` which Medium accepts for most endpoints, but article HTML pages (without `?format=json`) return 403. Always use `?format=json` for article and profile pages.

- **`?format=json` works; profile stream API does not** — `https://medium.com/_/api/users/{id}/profile/stream` returns HTTP 403 for unauthenticated requests. Use `?format=json` on the profile URL instead.

- **`?format=json` on search pages returns 403 or broken JSON** — `medium.com/search?q=...&format=json` and `medium.com/search/posts?q=...&format=json` both fail. Search is not available without auth.

- **GraphQL `collection()` requires ID, not slug** — `collection(slug: "towards-data-science")` returns HTTP 400. You must use the numeric ID (e.g. `"7f60cf5620c9"`). Get it from `?format=json` on the publication page: `payload['collection']['id']`.

- **GraphQL `tags` field on `post()` returns HTTP 400** — Use `topics { name slug }` instead. Topics are a subset of tags but work without auth.

- **GraphQL visibility is a string, not a number** — `post().visibility` returns `"PUBLIC"` or `"LOCKED"` (string). The `?format=json` `value.visibility` field uses integers: `0`=public, `2`=locked. Both agree on the lock status.

- **`totalClapCount` vs `recommends`** — `totalClapCount` (60865) counts all claps (Medium allows up to 50 claps per reader). `recommends` (8846) counts unique clappers. The GraphQL `clapCount` field equals `totalClapCount`, not `recommends`.

- **RSS returns at most 10 items, no clap counts** — RSS is best for getting recent article links + full HTML body. Use `?format=json` profile if you need metrics.

- **RSS link contains tracking params** — `posts[0]['link']` includes `?source=rss-{userId}------2`. Strip with `.split('?')[0]` if you need a clean URL.

- **`content:encoded` in RSS is full HTML, not plaintext** — Strip HTML tags if you want plaintext: `re.sub(r'<[^>]+>', '', body_html)`.

- **Medium subdomains** — Some users have custom subdomains (`karpathy.medium.com`). Both `medium.com/@karpathy/...` and `karpathy.medium.com/...` resolve to the same article; `?format=json` works on both.

- **towardsdatascience.com is no longer Medium** — TDS moved to its own WordPress site. `towardsdatascience.com/article-slug?format=json` returns full WordPress HTML, not Medium JSON. Use `medium.com/towards-data-science` for the archived Medium publication.

- **No public search API** — Medium has no Algolia equivalent. Finding articles by keyword requires either a browser, or fetching a user/publication feed and filtering locally.

- **Timestamps are unix milliseconds** — `firstPublishedAt`, `createdAt`, `latestPublishedAt` are all in milliseconds. Convert: `datetime.fromtimestamp(val['firstPublishedAt'] / 1000, tz=timezone.utc)`.
