# SoundCloud — Data Extraction

Field-tested against soundcloud.com on 2026-04-18.
No authentication required for any approach documented here. All code uses `http_get` (pure HTTP, no browser).

---

## Approach 1 (Fastest): oEmbed API — No Auth, No Client ID

`https://soundcloud.com/oembed?url=<resource_url>&format=json`

Returns JSON in ~0.3s. Works for **tracks, playlists/sets, and user profiles**. No key required.

```python
from helpers import http_get
import json

def soundcloud_oembed(resource_url):
    """Fetch oEmbed metadata for any public SoundCloud URL.

    Works for:
      - https://soundcloud.com/{user}/{track-slug}
      - https://soundcloud.com/{user}/sets/{playlist-slug}
      - https://soundcloud.com/{user}
    """
    url = f"https://soundcloud.com/oembed?url={resource_url}&format=json"
    return json.loads(http_get(url))

# Track
track = soundcloud_oembed("https://soundcloud.com/forss/flickermood")
# {
#   "version": 1.0,
#   "type": "rich",
#   "provider_name": "SoundCloud",
#   "provider_url": "https://soundcloud.com",
#   "height": 400,
#   "width": "100%",
#   "title": "Flickermood by Forss",
#   "description": "From the Soulhack album...",
#   "thumbnail_url": "https://i1.sndcdn.com/artworks-000067273316-smsiqx-t500x500.jpg",
#   "html": "<iframe width=\"100%\" height=\"400\" scrolling=\"no\" frameborder=\"no\" src=\"https://w.soundcloud.com/player/?visual=true&url=...\">",
#   "author_name": "Forss",
#   "author_url": "https://soundcloud.com/forss"
# }

# Playlist/set
pl = soundcloud_oembed("https://soundcloud.com/forss/sets/soulhack")
# title="Soulhack by Forss", description="My 2003 debut album...", height=450

# User profile
user = soundcloud_oembed("https://soundcloud.com/forss")
# title="Forss", description="Artist & Founder SoundCloud", height=450
```

### oEmbed fields

| Field | Type | Notes |
|-------|------|-------|
| `title` | str | "{Track Title} by {Artist}" for tracks, "{Name}" for users |
| `author_name` | str | Artist/user display name |
| `author_url` | str | Profile URL |
| `thumbnail_url` | str | Artwork at 500×500px (t500x500) |
| `description` | str | Track/profile description (may contain HTML entities) |
| `html` | str | Embed iframe for the SoundCloud player widget |
| `height` | int | 400 for tracks, 450 for playlists and users |
| `width` | str | Always `"100%"` |

---

## Approach 2: Page Hydration (`__sc_hydration`) — Rich Metadata, No Client ID

Every SoundCloud page embeds a JSON array in a `<script>` tag as `window.__sc_hydration`. This contains full API-grade metadata with no key required.

```python
from helpers import http_get
import json, re

def extract_hydration(page_url):
    """Extract __sc_hydration JSON from any SoundCloud page."""
    html = http_get(page_url)
    match = re.search(r'window\.__sc_hydration\s*=\s*(\[.*?\]);\s*<', html, re.DOTALL)
    if not match:
        return []
    return json.loads(match.group(1))

def get_hydration_by_type(page_url, hydratable):
    """Get the 'data' dict for a specific hydratable type."""
    for obj in extract_hydration(page_url):
        if obj.get('hydratable') == hydratable:
            return obj.get('data')
    return None

# Track page — hydration key is 'sound'
track = get_hydration_by_type("https://soundcloud.com/forss/flickermood", "sound")
# track['id']             = 293
# track['title']          = "Flickermood"
# track['playback_count'] = 962685
# track['likes_count']    = 2592
# track['duration']       = 213886  (milliseconds)
# track['genre']          = "Electronic"
# track['created_at']     = "2007-09-22T14:45:46Z"
# track['artwork_url']    = "https://i1.sndcdn.com/artworks-000067273316-smsiqx-large.jpg"
# track['waveform_url']   = "https://wave.sndcdn.com/cWHNerOLlkUq_m.json"
# track['streamable']     = True
# track['downloadable']   = True
# track['license']        = "all-rights-reserved"
# track['tag_list']       = "downtempo"
# track['urn']            = "soundcloud:tracks:293"
# track['media']          = {'transcodings': [...]}  (HLS/progressive stream URLs — need auth)
# track['user']           = {full user object nested}

# User page — hydration key is 'user'
user = get_hydration_by_type("https://soundcloud.com/forss", "user")
# user['id']               = 183
# user['username']         = "Forss"
# user['full_name']        = "Eric Quidenus-Wahlforss"
# user['followers_count']  = 132203
# user['track_count']      = 26
# user['verified']         = True
# user['city']             = "Berlin"
# user['country_code']     = "DE"
# user['description']      = "Artist & Founder SoundCloud"
# user['creator_subscription'] = {'product': {'id': 'creator-pro-unlimited'}}
# user['badges']           = {'pro_unlimited': True, 'verified': True}

# Playlist/set page — hydration key is 'playlist'
playlist = get_hydration_by_type("https://soundcloud.com/forss/sets/soulhack", "playlist")
# playlist['id']           = 18
# playlist['title']        = "Soulhack"
# playlist['track_count']  = 11
# playlist['tracks']       = [full track objects list]
# playlist['is_album']     = True/False
# playlist['genre']        = "Electronic"
```

### All hydration keys on a typical page

| `hydratable` | Content |
|---|---|
| `sound` | Full track object (on track pages) |
| `playlist` | Full playlist + all tracks (on set pages) |
| `user` | Full user object (on any page with a profile) |
| `apiClient` | `{'id': '<client_id>', 'isExpiring': False}` — the client_id |
| `geoip` | Viewer country/city/coordinates |
| `features` | Feature flags dict |
| `anonymousId` | Session tracking ID (not useful) |

---

## Approach 3: API v2 — Full Query Power (Requires Client ID)

The `client_id` lives in every page's `__sc_hydration` under the `apiClient` key. It is **stable across all pages and sessions** — extract once and reuse.

```python
from helpers import http_get
import json, re

def get_client_id(page_url="https://soundcloud.com"):
    """Extract client_id from any SoundCloud page's __sc_hydration."""
    html = http_get(page_url)
    match = re.search(r'window\.__sc_hydration\s*=\s*(\[.*?\]);\s*<', html, re.DOTALL)
    if not match:
        raise ValueError("No hydration found")
    for obj in json.loads(match.group(1)):
        if obj.get('hydratable') == 'apiClient':
            return obj['data']['id']
    raise ValueError("apiClient not found in hydration")

CLIENT_ID = get_client_id()  # "efg2kjLJnAJpInbN6P3hsHzispI1SKQH" (example — extract fresh)

def sc_api(path, **params):
    """Call api-v2.soundcloud.com. Returns parsed JSON."""
    params['client_id'] = CLIENT_ID
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    return json.loads(http_get(f"https://api-v2.soundcloud.com/{path}?{qs}"))
```

### Resolve any URL to a resource

```python
# Resolve a permalink URL to get its resource with full metadata
track = sc_api("resolve", url="https://soundcloud.com/forss/flickermood")
# Returns: {'kind': 'track', 'id': 293, 'title': 'Flickermood', ...}

user = sc_api("resolve", url="https://soundcloud.com/forss")
# Returns: {'kind': 'user', 'id': 183, 'username': 'Forss', ...}
```

### Track lookup

```python
# Single track by numeric ID
track = sc_api("tracks/293")

# Bulk track lookup (comma-separated IDs — returns list)
tracks = sc_api("tracks", ids="293,290,48031525")
# Returns a JSON array directly (not wrapped in 'collection')
for t in tracks:
    print(t['id'], t['title'], t['playback_count'])
```

### Search

```python
# Tracks
results = sc_api("search/tracks", q="jazz", limit=20)
# results['collection']    = list of track objects
# results['total_results'] = 5293248
# results['next_href']     = pagination URL (see below)

# Users
results = sc_api("search/users", q="jazz", limit=10)

# Playlists/sets
results = sc_api("search/playlists", q="jazz", limit=10)

# Paginate with next_href
def paginate(first_response):
    """Yield all pages of a collection response."""
    yield from first_response.get('collection', [])
    next_href = first_response.get('next_href')
    while next_href:
        page = json.loads(http_get(f"{next_href}&client_id={CLIENT_ID}"))
        yield from page.get('collection', [])
        next_href = page.get('next_href')
```

### Trending charts

```python
# Trending tracks across all genres
trending = sc_api("charts", kind="trending",
                  genre="soundcloud:genres:all-music", limit=20)
for item in trending['collection']:
    t = item['track']
    print(f"{t['title']} — score={item['score']:.4f}")

# Genre options: soundcloud:genres:all-music, soundcloud:genres:electronic,
#                soundcloud:genres:hiphoprap, soundcloud:genres:ambient, etc.
```

### User resources

```python
user_id = 183  # numeric ID from resolve or hydration

# User's tracks
tracks = sc_api(f"users/{user_id}/tracks", limit=20)
# tracks['collection'] = list of track objects

# User's playlists
playlists = sc_api(f"users/{user_id}/playlists", limit=10)

# User's likes
likes = sc_api(f"users/{user_id}/likes", limit=10)

# Related tracks for a track
related = sc_api("tracks/293/related", limit=10)
# related['collection'] = list of track objects
```

### Waveform data

```python
# Waveform URL comes from track['waveform_url']
waveform_url = "https://wave.sndcdn.com/cWHNerOLlkUq_m.json"
waveform = json.loads(http_get(waveform_url))
# {
#   'width': 1800,   # number of sample points
#   'height': 140,   # max amplitude value
#   'samples': [11, 86, 91, 80, ...]  # 1800 amplitude values
# }
```

---

## Full track fields from `__sc_hydration` / API v2

```
id               int     Numeric track ID (e.g. 293)
urn              str     "soundcloud:tracks:293"
title            str     Track title
description      str     May contain HTML entities/tags
genre            str     Genre string
tag_list         str     Space-separated tags
created_at       str     ISO 8601 UTC
last_modified    str     ISO 8601 UTC
release_date     str     ISO 8601 UTC (original release)
display_date     str     ISO 8601 UTC (shown to users)
duration         int     Milliseconds
full_duration    int     Milliseconds (untruncated)
playback_count   int
likes_count      int
reposts_count    int
comment_count    int
download_count   int
artwork_url      str     e.g. .../artworks-...-large.jpg (replace 'large' with 't500x500' for 500px)
waveform_url     str     https://wave.sndcdn.com/....json
permalink        str     Slug (e.g. "flickermood")
permalink_url    str     Full canonical URL
streamable       bool
downloadable     bool
license          str     e.g. "all-rights-reserved", "cc-by"
sharing          str     "public" or "private"
state            str     "finished" | "processing" | "failed"
monetization_model str   "AD_SUPPORTED" | "SUB_HIGH_TIER" | "NOT_APPLICABLE"
embeddable_by    str     "all" | "me" | "none"
user             dict    Nested user object (id, username, avatar_url, verified, ...)
user_id          int     Owner numeric ID
publisher_metadata dict  {artist, publisher, isrc, contains_music, ...}
media            dict    {'transcodings': [...]}  — stream URLs (require OAuth, not usable without login)
label_name       str     Record label
purchase_url     str     External buy link
station_urn      str     "soundcloud:system-playlists:track-stations:{id}"
```

---

## Gotchas

**client_id is required for api-v2.soundcloud.com** — requests without it return HTTP 401. Always extract from `__sc_hydration['apiClient']['id']`.

**client_id source: hydration, not JS bundles** — the JS bundles on `a-v2.sndcdn.com` do NOT contain the `client_id` pattern. The only reliable source is the `apiClient` object in the page hydration. It is stable across all pages (same value from homepage, track pages, user pages) and does not appear to rotate on short timescales.

**Artwork URL sizes** — hydration/API returns `...-large.jpg` (100×100). Replace the size suffix to get larger images:
- `-large.jpg` → 100×100
- `-t300x300.jpg` → 300×300
- `-t500x500.jpg` → 500×500 (oEmbed returns this size)

**Regex must use `re.DOTALL`** — the `__sc_hydration` JSON spans multiple lines. Without `re.DOTALL`, the `.` in the regex won't match newlines.

**Stream URLs (media.transcodings) are gated** — the HLS/progressive audio stream URLs in `track['media']['transcodings']` require an OAuth token even to fetch a stream manifest. They cannot be played without a logged-in session.

**Bulk track lookup returns a list, not collection** — `GET /tracks?ids=...` returns a JSON array directly. Do NOT look for `.get('collection')`.

**Search `total_results` can be huge** — results like 5M+ are normal for broad queries. Use `next_href` for pagination; do not calculate offsets manually.

**oEmbed description contains HTML** — SoundCloud descriptions may include `&nbsp;` and anchor tags. Decode with `html.unescape()` if you need plain text.

**HTTP 400 on some endpoints** — `/tracks/{id}/comments` returns 400 without OAuth headers. Timed comments are not accessible without login.

**No browser required** — all documented approaches work with plain `http_get`. SoundCloud does not require JavaScript rendering for metadata extraction.

**Rate limits** — 20 rapid sequential API v2 requests completed without errors in testing. SoundCloud does not publish official rate limits; stay under ~50 req/s for sustained scraping. oEmbed is more lenient than api-v2.

---

## Quick Reference

| Goal | Approach | Auth |
|------|----------|------|
| Track title/author/thumbnail from URL | oEmbed | None |
| Full track metadata + play counts | `__sc_hydration` `sound` key | None |
| Full user profile + stats | `__sc_hydration` `user` key | None |
| Full playlist with all tracks | `__sc_hydration` `playlist` key | None |
| Search tracks/users/playlists | API v2 `/search/*` | client_id |
| Trending charts | API v2 `/charts` | client_id |
| Bulk track lookup by IDs | API v2 `/tracks?ids=` | client_id |
| User's track list | API v2 `/users/{id}/tracks` | client_id |
| Resolve permalink to resource | API v2 `/resolve?url=` | client_id |
| Waveform amplitude data | Direct fetch of `waveform_url` | None |
| Audio stream playback | OAuth login required | Login |
