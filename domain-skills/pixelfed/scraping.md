# Pixelfed — Data Extraction

`https://pixelfed.social` — federated photo-sharing platform (Instagram alternative). Implements a **Mastodon-compatible API**, but with critical divergences: almost every Mastodon API endpoint requires user-level OAuth auth, even the public timeline. The fastest unauthenticated path is the ActivityPub/Atom layer. **Never use a browser for public read-only tasks.**

Base API path: `https://pixelfed.social/api/v1/`  
ActivityPub base: `https://pixelfed.social/users/{username}`  
Post URL pattern: `https://pixelfed.social/p/{username}/{snowflake_id}`  
Media CDN: `https://pxscdn.com/` (separate from `pixelfed.social/storage/`)

---

## Access matrix — what needs auth

| Endpoint | Auth needed? |
|----------|-------------|
| `GET /api/v1/instance` | No |
| `GET /api/v1/accounts/lookup?acct={username}` | No |
| `GET /api/v1/custom_emojis` | No |
| `GET /.well-known/webfinger?resource=acct:{user}@{instance}` | No |
| `GET /users/{username}` (AP actor) | No |
| `GET /users/{username}.atom` (Atom feed, last 10 posts) | No |
| `GET /p/{username}/{id}` (AP Note, full attachments) | No |
| `GET /api/v1/timelines/public` | **Yes** |
| `GET /api/v1/timelines/tag/{tag}` | **Yes** |
| `GET /api/v1/trends` | **Yes** |
| `GET /api/v1/accounts/{id}` | **Yes** |
| `GET /api/v1/accounts/{id}/statuses` | **Yes** |
| `GET /api/v2/search` | **Yes** |
| All other Mastodon-compat endpoints | **Yes** |

---

## Unauthenticated: fastest path to posts

### Account profile + last 10 posts

```python
import json, xml.etree.ElementTree as ET

# Step 1: get account metadata (id, follower count, bio, avatar)
acct = json.loads(http_get(
    "https://pixelfed.social/api/v1/accounts/lookup?acct=dansup"
))
print(acct['id'], acct['username'], acct['followers_count'], acct['statuses_count'])
# => '2'  'dansup'  87953  382

# Step 2: get last 10 posts via Atom feed
atom_xml = http_get("https://pixelfed.social/users/dansup.atom")
root = ET.fromstring(atom_xml)
ns  = {'atom': 'http://www.w3.org/2005/Atom',
       'media': 'http://search.yahoo.com/mrss/'}

posts = []
for entry in root.findall('atom:entry', ns):
    post_url = entry.find('atom:id', ns).text    # e.g. https://pixelfed.social/p/dansup/948948726609726866
    title    = entry.find('atom:title', ns).text  # caption / first line of text
    updated  = entry.find('atom:updated', ns).text
    media_el = entry.find('media:content', ns)
    media    = media_el.attrib if media_el is not None else {}
    posts.append({'url': post_url, 'title': title, 'updated': updated, 'first_media': media})
    print(post_url)
    print('  caption:', title[:80])
    print('  media:', media.get('url', '')[:60], '|', media.get('type'))
```

Note: Atom feed always returns exactly the last 10 posts — no pagination param works.

### Individual post — full attachment list + alt text

```python
import json

# Fetch a single post as an ActivityPub Note (public, no auth)
post = json.loads(http_get(
    "https://pixelfed.social/p/dansup/948948726609726866",
    headers={"Accept": "application/activity+json"}
))

# Core fields
print('id:          ', post['id'])          # https://pixelfed.social/p/dansup/948948726609726866
print('type:        ', post['type'])        # "Note"
print('published:   ', post['published'])   # "2026-04-12T14:23:27+00:00"
print('content:     ', post['content'][:120])  # HTML — hashtags are <a> links
print('sensitive:   ', post['sensitive'])
print('commentsEnabled:', post.get('commentsEnabled'))  # Pixelfed-only field

# Hashtags (Pixelfed-specific: always lowercase href, mixed-case name)
for tag in post.get('tag', []):
    print('hashtag:', tag['name'], '->', tag['href'])
    # => '#DogsOfPixelFed' -> 'https://pixelfed.social/discover/tags/dogsofpixelfed'

# Attachments — photos or video, up to 20 per album
for att in post.get('attachment', []):
    print('type:     ', att['type'])           # "Document"
    print('mediaType:', att['mediaType'])       # "image/jpeg" | "image/png" | "video/mp4" | "image/webp" | "image/gif" | "image/heic"
    print('url:      ', att['url'])             # direct CDN URL (pxscdn.com for pixelfed.social)
    print('width/height:', att['width'], 'x', att['height'])
    print('alt text: ', att.get('name'))        # per-image alt text (often set, can be None)
    print('blurhash: ', att.get('blurhash'))    # always present
    print('focalPoint:', att.get('focalPoint')) # [x, y] in [-1,1]; [0,0] = center
    print()
```

### Batch: all recent posts from a user

```python
import json, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

def get_posts_for_user(username):
    """Returns last 10 posts with full AP data. No auth needed."""
    # Step 1: atom feed for URLs
    atom_xml = http_get(f"https://pixelfed.social/users/{username}.atom")
    root = ET.fromstring(atom_xml)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    urls = [e.find('atom:id', ns).text
            for e in root.findall('atom:entry', ns)]

    # Step 2: parallel AP fetch for full data
    def fetch_ap(url):
        try:
            return json.loads(http_get(url, headers={"Accept": "application/activity+json"}))
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=5) as ex:
        posts = list(ex.map(fetch_ap, urls))
    return [p for p in posts if p]

posts = get_posts_for_user("dansup")
for p in posts:
    n_media = len(p.get('attachment', []))
    hashtags = [t['name'] for t in p.get('tag', []) if t['type'] == 'Hashtag']
    print(p['id'], f'({n_media} media, {len(hashtags)} tags)')
```

---

## Instance metadata

```python
import json

info = json.loads(http_get("https://pixelfed.social/api/v1/instance"))
print(info['uri'])                   # "pixelfed.social"
print(info['version'])               # "3.5.3 (compatible; Pixelfed 0.12.7)"
print(info['stats']['user_count'])   # 552315
print(info['stats']['status_count']) # 15921797
print(info['stats']['domain_count']) # 38758 federated instances
print(info['registrations'])         # False — pixelfed.social is invite-only
```

---

## Account lookup

```python
import json

# By username (works for any public account on this instance)
acct = json.loads(http_get(
    "https://pixelfed.social/api/v1/accounts/lookup?acct=dansup"
))

# Key fields
print(acct['id'])               # "2"  — snowflake string ID
print(acct['username'])         # "dansup"
print(acct['acct'])             # "dansup" (local) or "user@other.instance" (remote)
print(acct['display_name'])     # "dansup"
print(acct['followers_count'])  # 87953
print(acct['following_count'])  # 213
print(acct['statuses_count'])   # 382
print(acct['discoverable'])     # True
print(acct['locked'])           # False — open follow
print(acct['note'])             # HTML bio
print(acct['url'])              # "https://pixelfed.social/dansup"
print(acct['avatar'])           # direct URL
print(acct['created_at'])       # "2018-06-01T05:01:59.000000Z"
```

---

## Federated account lookup via Webfinger

```python
import json

# Find any fediverse account's canonical ActivityPub URL
wf = json.loads(http_get(
    "https://pixelfed.social/.well-known/webfinger"
    "?resource=acct:dansup@pixelfed.social"
))
# wf['subject']  = "acct:dansup@pixelfed.social"
# wf['aliases']  = ["https://pixelfed.social/dansup", "https://pixelfed.social/users/dansup"]
# wf['links']    = list of rel/type/href dicts

ap_url   = next(l['href'] for l in wf['links'] if l.get('type') == 'application/activity+json')
atom_url = next(l['href'] for l in wf['links'] if 'atom' in l.get('type',''))
print('AP actor:', ap_url)    # https://pixelfed.social/users/dansup
print('Atom feed:', atom_url) # https://pixelfed.social/users/dansup.atom
```

---

## ActivityPub actor profile (unauthenticated)

```python
import json

actor = json.loads(http_get(
    "https://pixelfed.social/users/dansup",
    headers={"Accept": "application/activity+json"}
))
# actor keys: @context, id, type, following, followers, inbox, outbox,
#             preferredUsername, name, summary, url, published, publicKey,
#             icon, endpoints, manuallyApprovesFollowers, indexable
print(actor['type'])               # "Person"
print(actor['preferredUsername'])  # "dansup"
print(actor['followers'])          # "https://pixelfed.social/users/dansup/followers"
print(actor['outbox'])             # "https://pixelfed.social/users/dansup/outbox"
print(actor['icon']['url'])        # avatar URL

# Follower/following counts (summary only — paging not supported on pixelfed.social)
fol = json.loads(http_get(actor['followers'], headers={"Accept": "application/activity+json"}))
print(fol['totalItems'])  # 87953
```

---

## With user OAuth — full Mastodon-compat API

Pixelfed requires full 3-legged OAuth. Client credentials tokens do NOT work for user APIs.

### App registration (one-time)

```python
import json

app = json.loads(http_get.__func__(  # use requests or urllib.request directly
    "POST", "https://pixelfed.social/api/v1/apps",
    data={"client_name": "my-scraper",
          "redirect_uris": "urn:ietf:wg:oauth:2.0:oob",
          "scopes": "read"}
))
CLIENT_ID     = app['client_id']
CLIENT_SECRET = app['client_secret']
```

Or use curl:
```bash
curl -s -X POST https://pixelfed.social/api/v1/apps \
  -d "client_name=my-scraper&redirect_uris=urn:ietf:wg:oauth:2.0:oob&scopes=read"
# => {"id":"...","client_id":"...","client_secret":"..."}
```

Then direct the user to:
```
https://pixelfed.social/oauth/authorize?client_id=CLIENT_ID&redirect_uri=urn:ietf:wg:oauth:2.0:oob&response_type=code&scope=read
```

Exchange the code:
```python
import json

token_resp = json.loads(...)  # POST /oauth/token with grant_type=authorization_code
ACCESS_TOKEN = token_resp['access_token']
```

### Using the token

```python
import json

headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}

# Public timeline (media-only by default on Pixelfed; includes text posts too)
posts = json.loads(http_get(
    "https://pixelfed.social/api/v1/timelines/public?limit=20",
    headers=headers
))

# Hashtag timeline
posts = json.loads(http_get(
    "https://pixelfed.social/api/v1/timelines/tag/photography?limit=20",
    headers=headers
))

# Account posts by numeric ID
statuses = json.loads(http_get(
    "https://pixelfed.social/api/v1/accounts/2/statuses?limit=20",
    headers=headers
))

# Pagination (cursor-based using max_id)
next_page = json.loads(http_get(
    f"https://pixelfed.social/api/v1/accounts/2/statuses?limit=20&max_id={statuses[-1]['id']}",
    headers=headers
))
```

### Mastodon-compat status fields when using the API (with auth)

```python
# Each status object:
{
    'id':                  '948948726609726866',  # snowflake string
    'created_at':          '2026-04-12T14:23:27.000000Z',
    'content':             '<p>Caption text with <a ...>#hashtags</a></p>',  # HTML
    'visibility':          'public',   # 'public' | 'unlisted' | 'private' | 'direct'
    'sensitive':           False,
    'spoiler_text':        '',         # always empty — Pixelfed has no content warnings
    'language':            None,       # always None on pixelfed.social
    'poll':                None,       # always None — Pixelfed has no polls
    'card':                None,       # always None — no link preview cards
    'in_reply_to_id':      None,       # set if it's a comment
    'reblog':              None,       # repost object or None
    'replies_count':       4,
    'reblogs_count':       12,
    'favourites_count':    89,
    'uri':                 'https://pixelfed.social/p/dansup/948948726609726866',
    'url':                 'https://pixelfed.social/p/dansup/948948726609726866',
    'account':             {...},      # account object
    'tags':                [{'name': 'dogsofpixelfed', 'url': '...'}],
    'emojis':              [],
    'media_attachments':   [...]       # see below
}

# media_attachments item (Mastodon-compat shape, auth path):
{
    'id':          '12345',
    'type':        'image',       # 'image' | 'video' | 'gifv'
    'url':         'https://pxscdn.com/...',
    'preview_url': 'https://pxscdn.com/...',   # smaller preview
    'remote_url':  None,
    'description': 'Alt text string',   # same as AP attachment['name']
    'blurhash':    'UXN]tl...',
    'meta': {
        'original': {'width': 1013, 'height': 1350, 'size': '1013x1350', 'aspect': 0.75},
        'small':    {'width': 400, 'height': 533, ...},
        'focus':    {'x': 0.0, 'y': 0.0}   # focalPoint
    }
}
```

---

## Gotchas

### Nearly every API endpoint requires user auth
Unlike Mastodon, Pixelfed (0.12.x) requires a real user OAuth token for essentially all data endpoints — including the public timeline, hashtag timelines, trends, and account statuses. The instance redirects unauthenticated API requests to `/login` (HTML) or returns `{"error":"Unauthenticated."}`.

### Client credentials tokens are rejected
`POST /oauth/token` with `grant_type=client_credentials` succeeds and returns a JWT, but that token is rejected with `Unauthenticated.` on all user-facing API endpoints. Only 3-legged OAuth (authorization_code flow) produces a working token.

### The public API surface without auth is tiny
Only four endpoints work without auth: `/api/v1/instance`, `/api/v1/accounts/lookup`, `/api/v1/custom_emojis`, and `/.well-known/webfinger`. Everything else needs a token.

### ActivityPub and Atom are the only unauthenticated post sources
Use `/users/{username}.atom` for a quick list of the last 10 post URLs + first image. Use `Accept: application/activity+json` on individual post URLs (`/p/{username}/{id}`) for full album data. The outbox endpoint (`/users/{username}/outbox`) only returns `{"type":"OrderedCollection","totalItems":N}` — paging it returns the same empty summary.

### Atom feed has no pagination
`/users/{username}.atom?page=2` ignores the param and always returns the same last 10 entries. To get older posts you need user-authenticated API access.

### Posts are photo-only (almost)
Pixelfed enforces at least one media attachment on most post types. The `media_attachments` array is never empty on a real Pixelfed post. `spoiler_text`, `poll`, and `card` are always null/empty — these Mastodon features don't exist in Pixelfed.

### Hashtag href normalization
In ActivityPub `tag` objects, `name` preserves original casing (`'#DogsOfPixelFed'`) but `href` is always lowercased (`'.../discover/tags/dogsofpixelfed'`). Don't compare them directly.

### Media CDN vs instance storage
Profile avatars and headers are served from `pixelfed.social/storage/...`. Post media is on `pxscdn.com/...`. Both URLs are direct (no auth, no token needed) and link to permanent media files.

### Album limit is 20
Config exposes `album_limit: 20` — a single post can have up to 20 attachments. The AP `attachment` array reflects this (tested: 1–3 attachments confirmed; 20 is the ceiling).

### `id` is a snowflake string, not an integer
All IDs (account, post, attachment) are 64-bit snowflake integers returned as JSON strings. Don't cast to `int` for sorting — string lexicographic order works correctly for snowflakes of the same bit-width.

### No `/api/v1/directory` or `/api/v1/statuses/{id}` without auth
Neither endpoint exists or is accessible unauthenticated. Use AP (`/p/{user}/{id}` with `Accept: application/activity+json`) for individual post lookup.

### `/api/v2/discover/posts/trending` returns 404
This endpoint is documented in some Pixelfed sources but is not deployed on pixelfed.social. Use `/api/v1/trends` (auth required) instead.

### SPA pages are Vue apps — no SSR data
Pages like `/discover/tags/photography` render via Vue.js after login. The HTML returned to unauthenticated clients is a blank shell with config JSON only (`window.App = {...}`). No post data is embedded.
