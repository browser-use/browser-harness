# Reddit — Scraping & Data Extraction

`https://www.reddit.com` — JSON API only. Append `.json` to any Reddit URL to get structured data. No auth required for public subreddits. **`User-Agent: browser-harness/1.0` is mandatory** — `Mozilla/5.0` gets 403.

## Do this first

**Append `.json` to any public Reddit URL. Set `User-Agent: browser-harness/1.0`.**

```python
import json

headers = {"User-Agent": "browser-harness/1.0"}  # CRITICAL — Mozilla/5.0 returns 403

data = json.loads(http_get("https://www.reddit.com/r/programming/hot.json?limit=25", headers=headers))
posts = data['data']['children']
for p in posts:
    d = p['data']
    print(d['title'], d['score'], d['url'])
```

**Never use a browser for Reddit read-only tasks.** The `.json` API is identical in content to the web UI, returns in ~200ms, and requires no JS rendering.

---

## Common workflows

### Subreddit listings

```python
import json

headers = {"User-Agent": "browser-harness/1.0"}

# Listing types: hot, new, top, controversial, rising
# hot — current trending
hot = json.loads(http_get("https://www.reddit.com/r/python/hot.json?limit=25", headers=headers))

# top — with time filter: hour, day, week, month, year, all
top_week = json.loads(http_get("https://www.reddit.com/r/python/top.json?limit=25&t=week", headers=headers))

# new — chronological
new = json.loads(http_get("https://www.reddit.com/r/python/new.json?limit=25", headers=headers))

# controversial — with time filter
contr = json.loads(http_get("https://www.reddit.com/r/programming/controversial.json?limit=10&t=week", headers=headers))

posts = hot['data']['children']
for p in posts:
    d = p['data']
    print(d['title'][:60], '|', d['score'], 'pts |', d['url'][:50])
```

Key post fields: `id, title, selftext, score, upvote_ratio, url, permalink, author, subreddit, num_comments, created_utc, is_self, flair_text, thumbnail, preview, link_flair_text`.

### Post comments

```python
import json

headers = {"User-Agent": "browser-harness/1.0"}

# Method 1: from post object (post_id is the 'id' field, e.g. '1abc123')
post_id = "1abc123"
subreddit = "python"
thread = json.loads(http_get(
    f"https://www.reddit.com/r/{subreddit}/comments/{post_id}.json",
    headers=headers
))

post     = thread[0]['data']['children'][0]['data']   # post metadata
comments = thread[1]['data']['children']               # top-level comments

print("Title:", post['title'])
print("Selftext:", post['selftext'][:200])

for c in comments:
    if c['kind'] == 't1':   # t1=comment, t3=post, more=load-more placeholder
        d = c['data']
        print(d['author'], d['score'], d['body'][:100])
        # d['replies'] is nested dict of child comments (same structure)

# Method 2: without subreddit (works for any post ID)
thread2 = json.loads(http_get(
    f"https://www.reddit.com/comments/{post_id}.json",
    headers=headers
))
```

Comment fields: `id, author, body, score, created_utc, replies, depth, is_submitter, stickied, distinguished, permalink`.

`replies` is either a dict (same `data.children` structure) or an empty string `""` for leaf comments — check `isinstance(d['replies'], dict)` before recursing.

### Nested comment tree (recursive)

```python
import json

headers = {"User-Agent": "browser-harness/1.0"}

def extract_comments(node, depth=0):
    if node['kind'] != 't1':
        return []
    d = node['data']
    result = [{'depth': depth, 'author': d['author'], 'score': d['score'], 'body': d['body']}]
    if isinstance(d.get('replies'), dict):
        for child in d['replies']['data']['children']:
            result.extend(extract_comments(child, depth + 1))
    return result

thread = json.loads(http_get(
    "https://www.reddit.com/r/python/comments/POSTID.json?limit=500",
    headers=headers
))
all_comments = []
for node in thread[1]['data']['children']:
    all_comments.extend(extract_comments(node))
```

### Subreddit search

```python
import json

headers = {"User-Agent": "browser-harness/1.0"}

# Search within a subreddit
results = json.loads(http_get(
    "https://www.reddit.com/r/python/search.json"
    "?q=asyncio&sort=top&t=month&limit=10",
    headers=headers
))
for p in results['data']['children']:
    d = p['data']
    print(d['title'][:60], d['score'])

# Site-wide search
all_results = json.loads(http_get(
    "https://www.reddit.com/search.json"
    "?q=site:python.org&sort=relevance&limit=10",
    headers=headers
))
```

Sort options: `relevance, hot, top, new, comments`. Time filter `t=`: `hour, day, week, month, year, all`.

### Pagination (after/before tokens)

```python
import json

headers = {"User-Agent": "browser-harness/1.0"}

all_posts = []
after = None
for _ in range(3):   # fetch 3 pages = 75 posts max
    url = "https://www.reddit.com/r/python/hot.json?limit=25"
    if after:
        url += f"&after={after}"
    data = json.loads(http_get(url, headers=headers))
    posts = data['data']['children']
    if not posts:
        break
    all_posts.extend(posts)
    after = data['data']['after']   # None when no more pages
    if not after:
        break
```

`after` is a fullname like `t3_1snwubm`. `before` token also exists for reverse pagination. Max `limit` is 100 per request.

### Subreddit metadata

```python
import json

headers = {"User-Agent": "browser-harness/1.0"}

sub = json.loads(http_get("https://www.reddit.com/r/python/about.json", headers=headers))
d = sub['data']
print(d['display_name'])        # "Python"
print(d['subscribers'])         # 1470616
print(d['active_user_count'])   # currently online
print(d['public_description'])  # sidebar text
print(d['created_utc'])         # unix timestamp of creation
print(d['over18'])              # NSFW flag
```

### User profile

```python
import json

headers = {"User-Agent": "browser-harness/1.0"}

user = json.loads(http_get("https://www.reddit.com/user/spez/about.json", headers=headers))
d = user['data']
print(d['name'])           # "spez"
print(d['link_karma'])     # 182287
print(d['comment_karma'])
print(d['created_utc'])
print(d['is_gold'])
print(d['verified'])

# User post history
posts = json.loads(http_get("https://www.reddit.com/user/spez/submitted.json?limit=10", headers=headers))
# User comment history
comments = json.loads(http_get("https://www.reddit.com/user/spez/comments.json?limit=10", headers=headers))
```

### Rate limit monitoring

```python
import urllib.request

req = urllib.request.Request(
    "https://www.reddit.com/r/python/hot.json?limit=1",
    headers={"User-Agent": "browser-harness/1.0"}
)
with urllib.request.urlopen(req) as resp:
    used      = resp.headers.get('x-ratelimit-used')       # e.g. "3"
    remaining = resp.headers.get('x-ratelimit-remaining')  # e.g. "97.0"
    reset_in  = resp.headers.get('x-ratelimit-reset')      # seconds until reset
    print(f"Used: {used}, Remaining: {remaining}, Reset in: {reset_in}s")
```

Unauthenticated limit: **100 requests per 10-minute window** per IP. Headers are on every response.

---

## Gotchas

- **`User-Agent: browser-harness/1.0` is required** — `Mozilla/5.0` (the default in `http_get`) returns HTTP 403. Any non-browser-looking UA string works; `browser-harness/1.0` confirmed returning 200 with rate limit headers. Always pass `headers={"User-Agent": "browser-harness/1.0"}` explicitly.

- **`http_get` default UA is `Mozilla/5.0`** — which is blocked. You must pass the custom headers dict on every call.

- **`kind` field distinguishes content types**: `t1`=comment, `t2`=account, `t3`=post/link, `t4`=message, `t5`=subreddit, `t6`=award. Always check `kind == 't1'` before reading comment fields; `kind == 'more'` means a "load more" placeholder.

- **`replies` is `""` for leaf comments** — not `None`, not `[]`. Use `isinstance(d['replies'], dict)` before accessing `d['replies']['data']['children']`.

- **Private subreddits return 403** — no special handling; just raises `HTTPError`. Quarantined subreddits return 403 without opt-in cookie.

- **Deleted/removed content**: Deleted posts have `author == '[deleted]'` and `selftext == '[deleted]'` or `'[removed]'`. Moderator-removed posts show `selftext == '[removed]'` but keep the title.

- **`created_utc` is a float** — convert with `datetime.utcfromtimestamp(d['created_utc'])`.

- **Max 1000 posts per listing** — Reddit caps pagination at 1000 items regardless of `after` token chaining. To get more historical data, use Pushshift (third-party, not official) or the search API with date filters.

- **`score` is approximate for recent posts** — Reddit fuzzes vote counts on hot posts to prevent vote manipulation. Expect ±5-10% variance on posts < 24 hours old.

- **`.json` suffix also works on post URLs** — `https://www.reddit.com/r/python/comments/abc123/title_here.json` returns the same thread data as the `/comments/` endpoint.

- **100 req/10min unauthenticated limit** — confirmed via response headers (`x-ratelimit-used`, `x-ratelimit-remaining`, `x-ratelimit-reset`). Authenticated OAuth apps get 1000 req/10min. For bulk scraping without OAuth, add `time.sleep(0.1)` between calls to stay safely under.

- **Subreddit names are case-insensitive in URLs** — `r/Python` and `r/python` both work.
