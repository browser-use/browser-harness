# Mastodon — Scraping & Data Extraction

`https://mastodon.social` / `https://fosstodon.org` — decentralized social network (ActivityPub).
Most read endpoints work without auth. No browser needed for any data task covered here.

## Do this first

**Use the REST API — it returns clean JSON, no browser, no auth for most endpoints.**

```python
import json
from helpers import http_get

# Public trending posts (no auth, works on mastodon.social)
toots = json.loads(http_get("https://mastodon.social/api/v1/trends/statuses?limit=5"))

# Account lookup by username
acct = json.loads(http_get("https://mastodon.social/api/v1/accounts/lookup?acct=Mastodon"))
print(acct['id'], acct['followers_count'])   # 13179  869022

# Hashtag timeline
posts = json.loads(http_get("https://mastodon.social/api/v1/timelines/tag/python?limit=10"))
```

**Important instance note:** `mastodon.social` has disabled its public live-feed timeline
(`/timelines/public`) — it returns HTTP 422 with `"This method requires an authenticated user"`.
Use `fosstodon.org` for unauthenticated public/local timelines, or use the hashtag timeline on
either instance (hashtag feeds are always public).

## What works without auth

| Endpoint | mastodon.social | fosstodon.org |
|---|---|---|
| `GET /api/v1/timelines/public` | **NO** (422) | YES |
| `GET /api/v1/timelines/public?local=true` | **NO** (422) | YES |
| `GET /api/v1/timelines/tag/{hashtag}` | YES | YES |
| `GET /api/v1/trends/statuses` | YES | YES |
| `GET /api/v1/trends/tags` | YES | YES |
| `GET /api/v1/trends/links` | YES | YES |
| `GET /api/v1/accounts/lookup` | YES | YES |
| `GET /api/v1/accounts/{id}/statuses` | YES | YES |
| `GET /api/v1/statuses/{id}` | YES | YES |
| `GET /api/v1/statuses/{id}/context` | YES | YES |
| `GET /api/v2/search` (accounts + hashtags) | YES | YES |
| `GET /api/v2/search` (statuses) | **NO** (empty) | NO |
| `GET /api/v1/instance` | YES | YES |
| `GET /api/v2/instance` | YES | YES |
| `GET /api/v1/instance/peers` | YES | YES |
| `GET /api/v1/directory` | YES | YES |

## Common workflows

### Trending posts

```python
import json, re
from helpers import http_get

def strip_html(html):
    text = re.sub(r'<[^>]+>', '', html)
    for ent, ch in [('&amp;','&'),('&lt;','<'),('&gt;','>'),('&quot;','"'),('&#39;',"'"),('&nbsp;',' ')]:
        text = text.replace(ent, ch)
    return text.strip()

toots = json.loads(http_get("https://mastodon.social/api/v1/trends/statuses?limit=5"))
for t in toots:
    print(t['id'], t['created_at'])
    print(t['account']['acct'], t['account']['followers_count'])
    print("favs:", t['favourites_count'], "reblogs:", t['reblogs_count'])
    print(strip_html(t['content'])[:200])
    print()
```

### Trending hashtags

```python
import json
from helpers import http_get

tags = json.loads(http_get("https://mastodon.social/api/v1/trends/tags?limit=10"))
for tag in tags:
    day0 = tag['history'][0]   # most recent day
    print(f"#{tag['name']}: {day0['uses']} uses by {day0['accounts']} accounts today")
# history is a list of dicts: {day (unix timestamp str), uses (str), accounts (str)}
# day[0] = most recent, day[1] = yesterday, etc. Values are strings — cast with int()
```

### Hashtag timeline (confirmed on both instances)

```python
import json
from helpers import http_get

posts = json.loads(http_get("https://mastodon.social/api/v1/timelines/tag/python?limit=10"))
for p in posts:
    # Skip reblogs if you want only originals
    if p['reblog']:
        continue
    print(p['id'], p['account']['acct'])
    print(strip_html(p['content'])[:200])
```

### Public / local timeline (use fosstodon.org)

```python
import json
from helpers import http_get

# Federated (all instances)
federated = json.loads(http_get("https://fosstodon.org/api/v1/timelines/public?limit=20"))

# Local only (fosstodon.org users)
local = json.loads(http_get("https://fosstodon.org/api/v1/timelines/public?local=true&limit=20"))
```

### Account lookup and their posts

```python
import json
from helpers import http_get

# Lookup by username (cross-instance: use full acct@domain)
acct = json.loads(http_get("https://mastodon.social/api/v1/accounts/lookup?acct=Mastodon"))
# acct@domain format for remote users: ?acct=fosstodon@fosstodon.org
uid = acct['id']  # '13179'

# Fetch their posts
posts = json.loads(http_get(
    f"https://mastodon.social/api/v1/accounts/{uid}/statuses?limit=10&exclude_reblogs=true"
))
# Optional params: exclude_reblogs=true, exclude_replies=true, only_media=true, pinned=true
```

Account fields:
- `id`, `acct` (username or username@domain), `display_name`, `username`
- `followers_count`, `following_count`, `statuses_count`
- `note` (bio — HTML, strip it), `fields` (profile metadata — also HTML)
- `created_at`, `last_status_at`, `bot`, `group`, `locked`
- `avatar`, `header` (image URLs)

### Single status + thread context

```python
import json
from helpers import http_get

status = json.loads(http_get("https://mastodon.social/api/v1/statuses/116402716327956884"))
print(status['reblogs_count'], status['favourites_count'], status['replies_count'])

# Get full thread (ancestors + descendants)
ctx = json.loads(http_get("https://mastodon.social/api/v1/statuses/116402716327956884/context"))
print(len(ctx['ancestors']), "parents,", len(ctx['descendants']), "replies")
```

### Search (accounts and hashtags — no auth required; statuses require auth)

```python
import json
from helpers import http_get

results = json.loads(http_get(
    "https://mastodon.social/api/v2/search?q=python&type=accounts&limit=5"
))
for a in results['accounts']:
    print(a['acct'], a['followers_count'])

# Hashtag search
results = json.loads(http_get(
    "https://mastodon.social/api/v2/search?q=python&type=hashtags&limit=5"
))
for h in results['hashtags']:
    print(h['name'], h['url'])

# type=statuses returns empty list without auth — don't bother without a token
```

### Instance metadata

```python
import json
from helpers import http_get

# v1 — stats, rules, version
info = json.loads(http_get("https://mastodon.social/api/v1/instance"))
print(info['stats'])      # {'user_count': 3237063, 'status_count': 171295328, 'domain_count': 114640}
print(info['version'])    # '4.6.0-nightly.2026-04-17'
print(info['rules'])      # list of {id, text}

# v2 — monthly active users, character limit, config
info2 = json.loads(http_get("https://mastodon.social/api/v2/instance"))
print(info2['usage']['users']['active_month'])   # 286734
print(info2['configuration']['statuses']['max_characters'])  # 500

# Federated instance list (warning: huge — 114,230 entries on mastodon.social)
peers = json.loads(http_get("https://mastodon.social/api/v1/instance/peers"))
print(len(peers))  # 114230

# Public account directory
directory = json.loads(http_get("https://mastodon.social/api/v1/directory?limit=10&order=active"))
# order=active (recently posted) or order=new (recently joined)
```

### Pagination (Link header, not offset)

Mastodon uses cursor-based pagination via the `Link` response header — there is no `page=` or
`offset=` parameter. The response contains `rel="next"` (older) and `rel="prev"` (newer) URLs.

```python
import json, re, gzip, urllib.request
from helpers import http_get

def http_get_with_link(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        link = r.headers.get("Link", "")
        return json.loads(data.decode()), link

def parse_link(link_header):
    next_m = re.search(r'<([^>]+)>; rel="next"', link_header)
    prev_m = re.search(r'<([^>]+)>; rel="prev"', link_header)
    return next_m.group(1) if next_m else None, prev_m.group(1) if prev_m else None

# Crawl older posts page by page
url = "https://fosstodon.org/api/v1/timelines/public?local=true&limit=20"
all_posts = []
for _ in range(3):   # 3 pages = 60 posts
    data, link = http_get_with_link(url)
    all_posts.extend(data)
    next_url, _ = parse_link(link)
    if not next_url:
        break
    url = next_url
print(f"Collected {len(all_posts)} posts")

# Or manually: append max_id=<oldest_id_seen> to get posts older than that
oldest_id = data[-1]['id']
older = json.loads(http_get(
    f"https://fosstodon.org/api/v1/timelines/public?local=true&limit=20&max_id={oldest_id}"
))
# For newer posts (since last check), use min_id=<newest_id_seen>
```

### Parallel account fetching

```python
import json
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

def fetch_account(acct_name):
    try:
        data = json.loads(http_get(f"https://mastodon.social/api/v1/accounts/lookup?acct={acct_name}"))
        return {"acct": data['acct'], "followers": data['followers_count'], "id": data['id']}
    except Exception as e:
        return {"acct": acct_name, "error": str(e)}

accounts = ["Mastodon", "fosstodon@fosstodon.org", "kuketzblog@social.tchncs.de"]
with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_account, accounts))
# Verified: 3 concurrent calls complete without rate limiting
```

## Status (toot) fields

Every status object returned by all list and single-fetch endpoints:

| Field | Type | Notes |
|---|---|---|
| `id` | string | Snowflake ID (numeric string); sortable as integer — larger = newer |
| `created_at` | string | ISO 8601 UTC, e.g. `"2026-04-19T00:26:54.248Z"` |
| `content` | string | **HTML** — always strip tags before displaying (see `strip_html` above) |
| `reblog` | object or null | If non-null, this is a boost; the original toot is in `reblog` |
| `reblogs_count` | int | Number of boosts |
| `favourites_count` | int | Number of favourites (likes) |
| `replies_count` | int | Number of replies |
| `sensitive` | bool | True = media is hidden behind a click-through |
| `spoiler_text` | string | Content warning text (empty string `""` when none) |
| `visibility` | string | `"public"`, `"unlisted"`, `"private"`, `"direct"` |
| `language` | string | BCP 47 code, e.g. `"en"`, or null |
| `url` | string | Canonical URL of the toot, e.g. `"https://mastodon.social/@Mastodon/116402..."` |
| `uri` | string | ActivityPub URI |
| `account` | object | Author — see account fields above |
| `media_attachments` | list | Images/video — each has `type`, `url`, `preview_url`, `description` |
| `tags` | list | `[{name, url}]` — hashtags in the toot |
| `mentions` | list | `[{id, username, acct, url}]` — @-mentioned users |
| `card` | object or null | Link preview card with `url`, `title`, `description`, `image` |
| `poll` | object or null | Poll with `options`, `votes_count`, `expires_at` |
| `in_reply_to_id` | string or null | ID of parent toot if this is a reply |
| `edited_at` | string or null | ISO 8601 if toot was edited |

## Rate limits

- **300 requests per 5 minutes** per IP without authentication
- Header: `X-RateLimit-Limit: 300`, `X-RateLimit-Remaining: N`, `X-RateLimit-Reset: <ISO timestamp>`
- Reset is a rolling 5-minute window aligned to clock minutes (confirmed from response headers)
- With auth (user token): higher limits, but documented per-endpoint in Mastodon docs
- The `/api/v1/instance/peers` response is ~1.6 MB — counts as 1 request but is slow

## Gotchas

- **mastodon.social disabled public timeline** — `/api/v1/timelines/public` returns HTTP 422
  `"This method requires an authenticated user"`. This is an instance policy, not an API design.
  Check `GET /api/v2/instance` → `configuration.timelines_access.live_feeds` to see a server's
  policy before calling. Use `fosstodon.org` or any instance that hasn't restricted it. Hashtag
  and trending endpoints are always public.

- **Content is HTML, not plain text** — `content` always comes back as `<p>text with <a href>links</a></p>`.
  Strip with `re.sub(r'<[^>]+>', '', html)`, then decode HTML entities. Whitespace collapses
  across paragraph boundaries — add a space or newline between `</p><p>` segments if needed.

- **Reblog vs original** — When `status['reblog']` is not null, the top-level `content` is `''`
  (empty string). The actual content, author, and counts are in `status['reblog']`. Always check:
  ```python
  actual = s['reblog'] if s['reblog'] else s
  text = strip_html(actual['content'])
  author = actual['account']['acct']
  ```

- **Snowflake IDs are strings** — `id` is a numeric string like `"116428532236221371"`. Compare
  and sort as integers: `int(s['id'])`. Larger integer = more recent.

- **Pagination is cursor-based, not offset** — There is no `page=N` or `offset=N` param.
  Use `max_id=<id>` to get posts older than that ID, `min_id=<id>` for posts newer. The `Link`
  header in each response gives you pre-built next/prev URLs. Do not parse and reconstruct manually
  — just follow the `rel="next"` URL verbatim.

- **IDs are not globally unique across instances** — A status ID from fosstodon.org is not
  valid on mastodon.social. Always query the instance that hosts the content.

- **`spoiler_text` is `""` not null when absent** — Check `s['spoiler_text'] != ''`, not
  `s['spoiler_text'] is not None`. Same for `edited_at` — it is `null` when unedited, but
  `spoiler_text` is always a string.

- **`sensitive=True` doesn't always mean NSFW** — Any media can be marked sensitive by the
  author (e.g. for flashing images, food photos on #MH-related accounts). The `spoiler_text`
  field is the actual content warning text; `sensitive=True` just hides media behind a click.

- **Account `note` and `fields` are also HTML** — The bio (`note`) and profile metadata (`fields`
  values) are HTML, not plain text. Strip them the same way as toot content.

- **Search statuses require auth** — `GET /api/v2/search?type=statuses` returns 0 results without
  a user token. Account and hashtag search work fine unauthenticated.

- **Cross-instance account lookup** — Use full `acct@domain` format to look up remote users:
  `?acct=fosstodon@fosstodon.org`. Single username resolves to local users only.

- **`/api/v1/instance/peers` is huge** — Returns all 114k+ federated instance hostnames as a
  flat JSON array (~1.6 MB). Only fetch when you specifically need federation data.

- **Trending history values are strings** — `tag['history'][0]['uses']` and `['accounts']` are
  strings (`"9"`, `"540"`), not integers. Cast with `int()` before sorting or comparing.
  `history[0]` is the most recent day; `history[0]['day']` is a Unix timestamp string.
