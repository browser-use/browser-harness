# Spotify — Data Extraction

Field-tested against open.spotify.com on 2026-04-18.
No authentication required for any approach documented here.

---

## Approach 1 (Fastest): oEmbed API — No Auth, No Browser

`https://open.spotify.com/oembed?url=<resource_url>`

Returns JSON in ~0.25s. Works for tracks, albums, playlists, and artists. Does **not** work for episodes/shows.

```python
from helpers import http_get
import json

def spotify_oembed(resource_type, resource_id):
    """Fetch oEmbed metadata for a Spotify resource.

    resource_type: 'track', 'album', 'playlist', or 'artist'
    resource_id:   Spotify ID (22-char alphanumeric)
    """
    resource_url = f"https://open.spotify.com/{resource_type}/{resource_id}"
    url = f"https://open.spotify.com/oembed?url={resource_url}"
    data = json.loads(http_get(url))
    return data

# Example: track
track = spotify_oembed("track", "4PTG3Z6ehGkBFwjybzWkR8")
# {
#   "title":           "Never Gonna Give You Up",
#   "thumbnail_url":   "https://image-cdn-ak.spotifycdn.com/image/ab67616100005174...",
#   "thumbnail_width": 320,
#   "thumbnail_height": 320,
#   "type":            "rich",
#   "html":            "<iframe ...src=\"https://open.spotify.com/embed/track/4PTG3Z6...\"...>",
#   "iframe_url":      "https://open.spotify.com/embed/track/4PTG3Z6ehGkBFwjybzWkR8?utm_source=oembed",
#   "width":           456,
#   "height":          152,
#   "version":         "1.0",
#   "provider_name":   "Spotify",
#   "provider_url":    "https://spotify.com"
# }

# Artist (height is 352 — taller widget)
artist = spotify_oembed("artist", "0gxyHStUsqpMadRV0Di1Qt")
# title="Rick Astley", thumbnail_url=<artist photo URL>

# Album
album = spotify_oembed("album", "4LH4d3cOWNNsVw41Gqt2kv")
# title="The Dark Side of the Moon", thumbnail_url=<album art URL>

# Playlist
pl = spotify_oembed("playlist", "37i9dQZF1DXcBWIGoYBM5M")
# title="Today's Top Hits", thumbnail_url=<playlist cover URL>
```

### Bulk fetching (ThreadPoolExecutor)

```python
from concurrent.futures import ThreadPoolExecutor
import json
from helpers import http_get

track_ids = [
    "4PTG3Z6ehGkBFwjybzWkR8",
    "7qiZfU4dY1lWllzX7mPBI3",
    "0VjIjW4GlUZAMYd2vXMi3b",
]

def fetch_oembed(tid):
    url = f"https://open.spotify.com/oembed?url=https://open.spotify.com/track/{tid}"
    try:
        return json.loads(http_get(url))
    except Exception as e:
        return {"error": str(e), "id": tid}

with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_oembed, track_ids))
# 5 tracks: ~1.3s total, ~0.26s per track
```

---

## Approach 2: Static HTML — Rich Metadata via http_get

Every open.spotify.com page (track, album, playlist, artist) serves full HTML with no JS requirement. The HTML contains JSON-LD and Open Graph tags that provide structured data.

### Track page — all extractable fields

```python
from helpers import http_get
import json, re

def scrape_track(track_id):
    url = f"https://open.spotify.com/track/{track_id}"
    html = http_get(url)

    # ---- JSON-LD (most structured) ----
    ld_raw = re.search(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    ld = json.loads(ld_raw.group(1)) if ld_raw else {}

    # ---- Open Graph / music: meta tags ----
    metas = {}
    for m in re.finditer(r'<meta\s+(?:property|name)="([^"]+)"\s+content="([^"]*)"', html):
        key, val = m.group(1), m.group(2)
        if key not in metas:
            metas[key] = val

    musician_urls = re.findall(r'<meta\s+(?:property|name)="music:musician"\s+content="([^"]*)"', html)
    allowed_countries = re.findall(r'<meta\s+property="og:restrictions:country:allowed"\s+content="([^"]*)"', html)

    return {
        "title":          metas.get("og:title"),
        "artist":         metas.get("music:musician_description"),
        "artist_urls":    musician_urls,               # spotify artist page URLs
        "album_url":      metas.get("music:album"),    # spotify album page URL
        "track_number":   metas.get("music:album:track"),
        "duration_s":     int(metas.get("music:duration", 0)),
        "release_date":   metas.get("music:release_date"),  # YYYY-MM-DD
        "cover_art":      metas.get("og:image"),       # 640px JPG
        "audio_preview":  metas.get("og:audio"),       # 30s MP3 (may be None)
        "spotify_url":    metas.get("og:url"),
        "description":    metas.get("og:description"),
        "eligible_regions": allowed_countries,
        "ld_name":        ld.get("name"),
        "ld_date":        ld.get("datePublished"),
    }

# Tested on track/4PTG3Z6ehGkBFwjybzWkR8 (Never Gonna Give You Up):
# {
#   "title":         "Never Gonna Give You Up",
#   "artist":        "Rick Astley",
#   "artist_urls":   ["https://open.spotify.com/artist/0gxyHStUsqpMadRV0Di1Qt"],
#   "album_url":     "https://open.spotify.com/album/6eUW0wxWtzkFdaEFsTJto6",
#   "track_number":  "1",
#   "duration_s":    214,
#   "release_date":  "1987-11-12",
#   "cover_art":     "https://i.scdn.co/image/ab67616d0000b27315ebbedaacef61af244262a8",
#   "audio_preview": "https://p.scdn.co/mp3-preview/b4c682084c3fd05538726d0a126b7e14b6e92c83",
#   "spotify_url":   "https://open.spotify.com/track/4PTG3Z6ehGkBFwjybzWkR8",
#   "eligible_regions": [185 country codes],
# }
```

### Artist page — fields available

```python
def scrape_artist(artist_id):
    url = f"https://open.spotify.com/artist/{artist_id}"
    html = http_get(url)

    ld_raw = re.search(r'<script type="application/ld\+json"[^>]*>(.*?)</script>', html, re.DOTALL)
    ld = json.loads(ld_raw.group(1)) if ld_raw else {}

    metas = {}
    for m in re.finditer(r'<meta\s+(?:property|name)="([^"]+)"\s+content="([^"]*)"', html):
        if m.group(1) not in metas:
            metas[m.group(1)] = m.group(2)

    return {
        "name":              metas.get("og:title"),
        "monthly_listeners": metas.get("og:description"),  # "Artist · 6.7M monthly listeners."
        "image":             metas.get("og:image"),         # full-size artist photo
        "spotify_url":       metas.get("og:url"),
        "description":       ld.get("description"),
    }

# Tested on Rick Astley (artist/0gxyHStUsqpMadRV0Di1Qt):
# {
#   "name":              "Rick Astley",
#   "monthly_listeners": "Artist · 6.7M monthly listeners.",
#   "image":             "https://i.scdn.co/image/ab6761610000e5ebe834a63a0cfa3c0f57a9a434",
# }
```

---

## Approach 3: Embed Page — Structured JSON with Track Lists

`https://open.spotify.com/embed/{type}/{id}` returns a small Next.js SSR page. Its `__NEXT_DATA__` script tag contains a fully-parsed entity object. This is the only no-auth route that returns track listings for albums, playlists, and artists.

```python
from helpers import http_get
import json, re

def scrape_embed(resource_type, resource_id):
    """
    resource_type: 'track', 'album', 'playlist', or 'artist'
    Returns the entity dict from __NEXT_DATA__.
    """
    url = f"https://open.spotify.com/embed/{resource_type}/{resource_id}"
    html = http_get(url)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    data = json.loads(m.group(1))
    return data['props']['pageProps']['state']['data']['entity']

# ---- TRACK ----
entity = scrape_embed("track", "4PTG3Z6ehGkBFwjybzWkR8")
# entity keys: type, name, uri, id, title, artists, releaseDate, duration,
#              isPlayable, isExplicit, audioPreview, hasVideo, visualIdentity
# {
#   "name":     "Never Gonna Give You Up",
#   "uri":      "spotify:track:4PTG3Z6ehGkBFwjybzWkR8",
#   "artists":  [{"name": "Rick Astley", "uri": "spotify:artist:0gxyHStUsqpMadRV0Di1Qt"}],
#   "duration": 213573,   # milliseconds
#   "releaseDate": {"isoString": "1987-11-12T00:00:00Z"},
#   "isPlayable": True,
#   "isExplicit": False,
#   "audioPreview": {"url": "https://p.scdn.co/mp3-preview/b4c682..."},
#   "visualIdentity": {
#     "image": [
#       {"url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d00001e02...", "maxWidth": 300, "maxHeight": 300},
#       {"url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d000048...", "maxWidth": 64,  "maxHeight": 64},
#       {"url": "https://image-cdn-fa.spotifycdn.com/image/ab67616d0000b27...", "maxWidth": 640, "maxHeight": 640},
#     ]
#   }
# }

# ---- ALBUM (includes full track list) ----
entity = scrape_embed("album", "6fu8fvc7O4p8Gb8KMTBTUW")
# entity.trackList — list of all album tracks, e.g. 12 items:
# [{
#   "uri":          "spotify:track:4e1zdmsDwNBNe9rk7HHC0i",
#   "title":        "Prelude for Piano No. 1 in E-Flat Major",
#   "subtitle":     "Eduard Abramyan,\u00a0Sona Shaboyan",
#   "duration":     107426,
#   "isPlayable":   True,
#   "audioPreview": {"url": "https://p.scdn.co/mp3-preview/d03c37..."},
#   "entityType":   "track"
# }, ...]

# ---- PLAYLIST (includes up to 50 tracks) ----
entity = scrape_embed("playlist", "37i9dQZF1DXcBWIGoYBM5M")
# entity.trackList — 50 items
# entity.subtitle  — "Spotify"
# entity.authors   — [{"name": "Spotify"}]

# ---- ARTIST (includes top 10 tracks) ----
entity = scrape_embed("artist", "0gxyHStUsqpMadRV0Di1Qt")
# entity.trackList — 10 top tracks, same shape as album trackList
# entity.subtitle  — "Top tracks"
```

### Bonus: Anonymous access token (embedded in every embed page)

The embed page SSR data includes a short-lived anonymous Spotify Web Player access token. The token is valid (~1 hour) but **anonymous tokens are severely rate-limited for api.spotify.com/v1 calls** (observed `Retry-After: 79561` seconds on the tracks endpoint after a few requests).

```python
def get_embed_token(resource_type="track", resource_id="4PTG3Z6ehGkBFwjybzWkR8"):
    """Extract the anonymous access token from an embed page."""
    url = f"https://open.spotify.com/embed/{resource_type}/{resource_id}"
    html = http_get(url)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    data = json.loads(m.group(1))
    session = data['props']['pageProps']['state']['settings']['session']
    return {
        "access_token":  session['accessToken'],
        "expires_ms":    session['accessTokenExpirationTimestampMs'],
        "is_anonymous":  session['isAnonymous'],          # always True
        "client_id":     data['props']['pageProps']['config']['clientId'],
    }

# Returned fields (verified 2026-04-18):
# access_token: "BQBfxv..." (a standard Spotify Bearer token, ~160 chars)
# expires_ms:   1776512455031 (~1 hour TTL)
# is_anonymous: True
# client_id:    "ab9ad0d96a624805a7d51e8868df1f97"

# WARNING: Do NOT use this token to hammer api.spotify.com/v1 — anonymous tokens
# share a global rate-limit bucket. One call can trigger a 22-hour ban window.
# Use the embed page __NEXT_DATA__ directly instead (Approach 3 above).
```

---

## What Requires a Browser

The following are **not accessible** via http_get and require the CDP browser:

- Lyrics (login-gated; JSON-LD confirms: `isAccessibleForFree: false`)
- Search (`/search?q=...`) — loads client-side only, no meaningful HTML on first response
- User library / listening history — requires OAuth
- Full audio playback — requires OAuth + Widevine DRM
- Podcast episodes — oEmbed returns 404; embed page `__NEXT_DATA__` lacks `state.data.entity`
- Track recommendations beyond the top-10 artist view
- Artist discography / full album list

If browser access is needed for search:

```python
goto("https://open.spotify.com/search")
wait_for_load()
wait(2)
# Type into the search box
js("document.querySelector('input[data-testid=\"search-input\"]').focus()")
type_text("never gonna give you up")
wait(1)
# Results appear in [data-testid="top-results-card"] or similar dynamic selectors
```

---

## URL Patterns

| Resource  | URL pattern                                    | ID format         |
|-----------|------------------------------------------------|-------------------|
| Track     | `https://open.spotify.com/track/{id}`          | 22-char alphanum  |
| Album     | `https://open.spotify.com/album/{id}`          | 22-char alphanum  |
| Artist    | `https://open.spotify.com/artist/{id}`         | 22-char alphanum  |
| Playlist  | `https://open.spotify.com/playlist/{id}`       | 22-char alphanum  |
| oEmbed    | `https://open.spotify.com/oembed?url={resource_url}` | any of above |
| Embed     | `https://open.spotify.com/embed/{type}/{id}`   | same ID           |

Extract Spotify ID from any URL:

```python
import re
def spotify_id(url):
    m = re.search(r'spotify\.com/(?:embed/)?(?:track|album|artist|playlist)/([A-Za-z0-9]{22})', url)
    return m.group(1) if m else None
```

---

## Gotchas

- **oEmbed 404 for valid IDs**: A 404 from oEmbed can mean the resource is region-locked or not available for embedding, not necessarily that the ID is wrong. Verified: track `3n3Ppam7vgaVa1iaRUIOKE` returns 404 on oEmbed despite existing on Spotify.
- **oEmbed 404 for artists**: Only works with valid, existing artist IDs. The artist ID `4gzpq5DumSF1a1LpGLBBl5` returns 404 — verify IDs from canonical Spotify URLs before using.
- **oEmbed does not support episodes**: `open.spotify.com/episode/{id}` always returns 404 from the oEmbed endpoint.
- **Embed page for episodes**: The embed page SSR for episodes does not include `state.data.entity` in the expected structure — parse defensively.
- **Anonymous token rate limiting**: The access token from embed pages is valid but severely rate-limited for `api.spotify.com/v1`. Observed `Retry-After: 79561` (~22 hours) after 2-3 rapid API calls. Use embed `__NEXT_DATA__` data instead of the API.
- **`get_access_token` endpoint blocked**: `https://open.spotify.com/get_access_token?reason=transport&productType=web_player` returns HTTP 403 from plain http_get regardless of headers. Token must be sourced from the embed page HTML.
- **`music:musician` meta tag dedup**: `re.findall` on `music:musician` returns all artist URLs. `dict(re.finditer(...))` would only keep the last one — always use `findall` for multi-value tags.
- **Cover art CDN differences**: oEmbed thumbnail uses `image-cdn-ak.spotifycdn.com`; track page `og:image` uses `i.scdn.co`. Both are publicly accessible. The embed `visualIdentity.image` array provides three sizes (64, 300, 640).
- **No `__NEXT_DATA__` on main open.spotify.com pages**: The SSR `__NEXT_DATA__` pattern only works on `open.spotify.com/embed/*`, not on main track/album/artist pages. Those pages use JSON-LD and Open Graph tags instead.
- **Track duration units differ**: `music:duration` meta tag is in **seconds** (integer). Embed `__NEXT_DATA__` `entity.duration` is in **milliseconds**.
- **Rate limits for http_get pages**: No rate limit observed on oEmbed or static HTML pages in testing (10 concurrent requests succeeded; ~0.25s avg per oEmbed call).
