# Lemmy — Data Extraction

`https://lemmy.world` / `https://lemmy.ml` — federated Reddit alternative (ActivityPub). Full REST API, no auth, no JS rendering needed. **Never use a browser for read-only Lemmy tasks.**

Base API path: `https://{instance}/api/v3/`

## Do this first: pick your access path

| Goal | Endpoint | Latency |
|------|----------|---------|
| Hot/trending posts (global or per community) | `post/list` | ~300ms |
| Keyword search across posts/communities/users | `search` | ~400ms |
| Community metadata + subscriber counts | `community` | ~200ms |
| Comments on a post | `comment/list` | ~300ms |
| User profile + their posts/comments | `user` | ~300ms |
| All federated instances (10 000+) | `federated_instances` | ~400ms |

---

## Posts

### Global hot feed

```python
import json

data = json.loads(http_get(
    "https://lemmy.world/api/v3/post/list?sort=Hot&limit=50"
))
# data keys: posts (list of PostView objects)

for pv in data['posts']:
    p   = pv['post']       # core post fields
    c   = pv['community']  # which community it lives in
    cr  = pv['creator']    # author
    cnt = pv['counts']     # engagement metrics
    print(p['id'], p['name'][:80])
    print("  community:", c['actor_id'])   # e.g. https://lemmy.world/c/technology
    print("  score:", cnt['score'], "comments:", cnt['comments'])
    print("  ap_id:", p['ap_id'])          # canonical ActivityPub URL
```

### PostView field reference

```python
# pv['post'] — core post
{
    'id':          45779800,
    'name':        'Post title here',
    'url':         'https://...',          # linked URL (absent for text posts)
    'body':        'Self-post text ...',   # absent for link posts
    'ap_id':       'https://lemmy.world/post/45779800',  # canonical AP URL
    'published':   '2026-04-18T23:31:42.738137Z',
    'creator_id':  12345,
    'community_id': 678,
    'nsfw':        False,
    'locked':      False,
    'local':       True,   # False = post originated on another instance
    'embed_title': '...',  # OG title of linked URL
    'thumbnail_url': 'https://...',
}

# pv['counts']
{
    'score':       101,     # upvotes - downvotes
    'upvotes':     108,
    'downvotes':   7,
    'comments':    9,
    'newest_comment_time': '2026-04-18T23:55:00Z',
}

# pv['creator']
{
    'id':       12345,
    'name':     'Sunflier',
    'actor_id': 'https://lemmy.world/u/Sunflier',  # home instance URL
    'local':    True,   # False = user registered on another instance
    'bot_account': False,
}

# pv['community']
{
    'id':        2478,
    'name':      'technology',
    'title':     'Technology',
    'actor_id':  'https://lemmy.world/c/technology',
    'local':     True,
    'instance_id': 1,
}
```

### Sort options

Valid values for `sort=` on `post/list` and `search`:
```
Hot  Active  Scaled  Controversial  New  Old
TopHour  TopSixHour  TopTwelveHour  TopDay  TopWeek
TopMonth  TopYear  TopAll  MostComments  NewComments
```

### Pagination

```python
import json

# page is 1-indexed; limit max is 50 (returns error above 50)
def iter_posts(sort="Hot", limit=50, max_pages=10):
    for page in range(1, max_pages + 1):
        data = json.loads(http_get(
            f"https://lemmy.world/api/v3/post/list"
            f"?sort={sort}&limit={limit}&page={page}"
        ))
        posts = data.get('posts', [])
        if not posts:
            break
        yield from posts

all_posts = list(iter_posts(sort="TopWeek", max_pages=5))
```

### Posts by community

```python
import json

# By community name (local community on this instance)
data = json.loads(http_get(
    "https://lemmy.world/api/v3/post/list"
    "?community_name=technology&sort=Hot&limit=50"
))

# By community_id (faster if you already have the ID)
data = json.loads(http_get(
    "https://lemmy.world/api/v3/post/list"
    "?community_id=2478&sort=Hot&limit=50"
))
```

---

## Communities

```python
import json

# Single community by name
data = json.loads(http_get(
    "https://lemmy.world/api/v3/community?name=technology"
))
cv = data['community_view']
c  = cv['community']
cnt = cv['counts']

print(c['actor_id'])              # https://lemmy.world/c/technology
print(cnt['subscribers'])         # total across federation
print(cnt['subscribers_local'])   # only on this instance
print(cnt['users_active_week'])   # weekly active users
print(cnt['posts'], cnt['comments'])
```

### Community counts field reference

```python
{
    'community_id':          2478,
    'subscribers':           145000,
    'subscribers_local':     12000,
    'posts':                 88000,
    'comments':              430000,
    'users_active_day':      120,
    'users_active_week':     680,
    'users_active_month':    2100,
    'users_active_half_year': 5400,
}
```

---

## Search

```python
import json

# Posts
results = json.loads(http_get(
    "https://lemmy.world/api/v3/search"
    "?q=linux&type_=Posts&sort=TopWeek&limit=50&page=1"
))
# results keys: type_, posts, comments, communities, users
for pv in results['posts']:
    print(pv['post']['ap_id'], pv['post']['name'][:60])

# Communities
results = json.loads(http_get(
    "https://lemmy.world/api/v3/search"
    "?q=linux&type_=Communities&limit=20"
))
for cv in results['communities']:
    print(cv['community']['actor_id'], cv['counts']['subscribers'])

# Users
results = json.loads(http_get(
    "https://lemmy.world/api/v3/search"
    "?q=linux&type_=Users&limit=20"
))
for uv in results['users']:
    print(uv['person']['actor_id'], uv['counts']['post_count'])
```

Valid `type_` values: `Posts`, `Comments`, `Communities`, `Users`, `All`

---

## Comments

```python
import json

# All comments on a post — flat list with ltree path for threading
data = json.loads(http_get(
    "https://lemmy.world/api/v3/comment/list"
    "?post_id=45779800&sort=Hot&limit=50"
))
for cv in data['comments']:
    c   = cv['comment']
    cnt = cv['counts']
    cr  = cv['creator']
    print(c['id'], c['path'])            # e.g. "0.23292774.23301445" — ltree
    print("  content:", c['content'][:80])
    print("  score:", cnt['score'], "children:", cnt['child_count'])
    print("  author:", cr['actor_id'])   # home-instance URL
```

### Comment field reference

```python
# cv['comment']
{
    'id':          23292774,
    'post_id':     45779800,
    'creator_id':  99,
    'content':     'Comment text (markdown)',
    'path':        '0.23292774',          # ltree; parent is last segment before this id
    'ap_id':       'https://lemmy.world/comment/23292774',
    'published':   '2026-04-18T23:40:00Z',
    'local':       True,
    'removed':     False,
    'deleted':     False,
    'distinguished': False,
}

# cv['counts']
{
    'comment_id':  23292774,
    'score':       30,
    'upvotes':     32,
    'downvotes':   2,
    'child_count': 1,    # direct children only
}
```

### Reconstruct comment tree from path

```python
# path is a dot-separated ltree: "0.parent_id.child_id.grandchild_id"
# The last segment is the comment's own ID; second-to-last is its parent.
def parent_id(cv):
    parts = cv['comment']['path'].split('.')
    return int(parts[-2]) if len(parts) >= 3 else None   # None = top-level (parent is "0")

# Build a parent→children mapping
from collections import defaultdict
children = defaultdict(list)
by_id = {}
for cv in data['comments']:
    by_id[cv['comment']['id']] = cv
    pid = parent_id(cv)
    children[pid].append(cv['comment']['id'])
# children[None] = top-level comment IDs
```

---

## Users

```python
import json

# User profile + recent posts + comments
data = json.loads(http_get(
    "https://lemmy.world/api/v3/user?username=Sunflier&limit=20"
))
pv  = data['person_view']
p   = pv['person']
cnt = pv['counts']

print(p['actor_id'])           # https://lemmy.world/u/Sunflier
print(p['local'])              # False = registered on another instance
print(cnt['post_count'], cnt['comment_count'])

for post_view in data['posts']:        # their recent posts
    print(post_view['post']['name'])
for comment_view in data['comments']:  # their recent comments
    print(comment_view['comment']['content'][:60])

# Paginate their history
data_p2 = json.loads(http_get(
    "https://lemmy.world/api/v3/user?username=Sunflier&limit=20&page=2"
))
```

---

## Federated instances

```python
import json

data = json.loads(http_get("https://lemmy.world/api/v3/federated_instances"))
fi = data['federated_instances']
# fi keys: linked, allowed, blocked

print(f"linked instances: {len(fi['linked'])}")   # ~10 735

# Each instance entry
for inst in fi['linked'][:5]:
    print(inst['domain'], inst['software'], inst['version'])
    # software: 'lemmy', 'kbin', 'mbin', 'mastodon', etc.
    # domain: 'lemmy.ml', 'sh.itjust.works', 'kbin.social', ...
```

### Parallel bulk collection across instances

```python
import json
from concurrent.futures import ThreadPoolExecutor

instances = ['lemmy.world', 'lemmy.ml', 'sh.itjust.works', 'beehaw.org']

def fetch_hot(instance):
    try:
        data = json.loads(http_get(
            f"https://{instance}/api/v3/post/list?sort=Hot&limit=20"
        ))
        return [(pv['post']['ap_id'], pv['post']['name'], pv['counts']['score'])
                for pv in data.get('posts', [])]
    except Exception:
        return []

with ThreadPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(fetch_hot, instances))
```

---

## Gotchas

### Hard limit of 50 on post/list
`limit > 50` returns `{"error": "couldnt_get_posts"}` — not a soft cap. Use `page=` to iterate: `page=1`, `page=2`, etc. (1-indexed). Same cap applies to `search`.

### Federated community naming: `name@instance`
When querying via `community?name=` or `post/list?community_name=` you must use `name@instance` for remote communities:
```python
# Local (on lemmy.world):
"?community_name=technology"
# Remote (on lemmy.ml):
"?community_name=technology@lemmy.ml"
"?name=technology@lemmy.ml"
```
`community['local']` is `False` and `community['actor_id']` points to the home instance (`https://lemmy.ml/c/technology`).

### `ap_id` vs local `id` — use `ap_id` for stable cross-instance keys
Numeric `id` (e.g. `45779800`) is local to the queried instance. The same post on another instance may have a completely different numeric ID. Use `ap_id` (a full URL) as the canonical unique identifier for posts, comments, and users:
```python
# Post: https://lemmy.world/post/45779800
# Comment: https://lemmy.ca/comment/23292774
# User: https://lemmy.ca/u/ech
```

### `local: False` means content originated elsewhere
Both posts and users have a `local` boolean. `local: False` means the post/user lives on another Fediverse instance — the queried instance is caching it. The authoritative copy is at the URL in `ap_id`.

### Comment `path` is ltree, not parent_id
`comment['path']` is `"0.grandparent_id.parent_id.comment_id"`. There is no dedicated `parent_id` field. Parse the second-to-last segment for the parent ID (the root sentinel is `"0"`).

### `child_count` in counts is direct children only
`counts['child_count']` counts direct replies, not the full subtree depth. To get the full thread, paginate `comment/list` and reconstruct from `path`.

### Removed/deleted posts still appear
`post['removed']` or `post['deleted']` may be `True`. These posts show up in list results with an empty `name` and no `url`. Filter them:
```python
posts = [pv for pv in data['posts'] if not pv['post']['removed'] and not pv['post']['deleted']]
```

### No next-page cursor — use `page=`
Unlike AT Protocol/Bluesky there is no cursor token. Pagination is strictly `page=N` (1-indexed). An empty `posts: []` signals exhaustion.

### Instance availability varies
Not all federated instances expose the same API version or stay online. Wrap cross-instance fetches in try/except. `fi['blocked']` lists instances this node has defederated from — those will likely fail.

### `subscribers` vs `subscribers_local`
`counts['subscribers']` is total federation-wide; `counts['subscribers_local']` is only users on the queried instance. For "community size" comparisons use `subscribers`.
