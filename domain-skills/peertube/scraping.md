# PeerTube — Scraping & Data Extraction

`https://sepiasearch.org` / `https://framatube.org` / `https://peertube.tv` — federated open-source video platform (ActivityPub). **Never use the browser.** All data is reachable via `http_get`. No API key required for read operations.

Federation model: thousands of independent instances run the same software and share/mirror content. SepiaSearch indexes the public federation; individual instances expose the same REST API.

## Do this first: pick your access path

| Goal | Endpoint |
|------|----------|
| Cross-instance search | `https://sepiasearch.org/api/v1/search/videos?search=…` |
| Instance trending/recent | `https://{instance}/api/v1/videos?sort=-trending` |
| Video detail + streaming URLs | `https://{instance}/api/v1/videos/{uuid}` |
| Channel search (federated) | `https://sepiasearch.org/api/v1/search/video-channels?search=…` |
| Channel's video list | `https://{instance}/api/v1/video-channels/{handle}/videos` |
| Comments on a video | `https://{instance}/api/v1/videos/{uuid}/comment-threads` |
| Captions/subtitles | `https://{instance}/api/v1/videos/{uuid}/captions` |
| Instance metadata | `https://{instance}/api/v1/config` |

Use **SepiaSearch** when you don't know which instance hosts the content. Use a **specific instance** when you want trending/recent videos from that community, or when you already have a UUID.

---

## SepiaSearch — cross-instance video search

```python
import json
from helpers import http_get

# Search across all federated instances
resp = json.loads(http_get(
    "https://sepiasearch.org/api/v1/search/videos"
    "?search=linux&count=20&start=0&sort=-views"
))
print("total:", resp["total"])   # up to 10000 capped

for v in resp["data"]:
    print(v["uuid"], v["name"][:60])
    print("  host:", v["account"]["host"])       # originating instance
    print("  views:", v["views"], "duration:", v["duration"])
    print("  url:", v["url"])                    # canonical watch URL
# Confirmed output (2026-04-18):
# da5463ca-... Installing Linux Doesn't Need to Change. The Experience Does.
#   host: spectra.video
#   views: 880 duration: 639
#   url: https://spectra.video/videos/watch/da5463ca-fbc7-4311-948a-356594d5c70a
```

### SepiaSearch video object fields

```python
{
    "id":          167978,                    # numeric ID on host instance
    "uuid":        "da5463ca-...",            # stable global identifier
    "shortUUID":   "abc123",                  # short alias for watch URLs
    "name":        "Installing Linux...",
    "duration":    639,                       # seconds
    "views":       880,
    "viewers":     0,                         # current live viewers
    "likes":       5,
    "dislikes":    0,
    "comments":    2,
    "publishedAt": "2024-12-15T10:00:00.000Z",
    "isLive":      False,
    "nsfw":        False,
    "thumbnailUrl": "https://spectra.video/lazy-static/thumbnails/da5463ca-....jpg",
    "embedUrl":    "https://spectra.video/videos/embed/da5463ca-...",
    "url":         "https://spectra.video/videos/watch/da5463ca-...",
    "isLocal":     False,                     # False = federated (lives on another instance)
    "tags":        ["linux", "open-source"],
    "category":    {"id": 15, "label": "Science & Technology"},
    "language":    {"id": "en", "label": "English"},
    "licence":     {"id": 1, "label": "Attribution"},
    "account": {
        "name":        "trafotin.com",
        "displayName": "Trafotin",
        "host":        "spectra.video",
        "url":         "https://spectra.video/accounts/trafotin.com",
    },
    "channel": {
        "name":        "trafotin",
        "displayName": "Trafotin",
        "host":        "spectra.video",
        "url":         "https://spectra.video/video-channels/trafotin",
    },
    # NOTE: streamingPlaylists and files are ABSENT in search results.
    # Fetch the detail endpoint on the host instance to get streaming URLs.
}
```

### SepiaSearch query parameters

| Parameter | Values | Notes |
|-----------|--------|-------|
| `search` | string | Required |
| `count` | 1–100 | Default 15 |
| `start` | integer | Offset for pagination |
| `sort` | `-views`, `-publishedAt`, `-createdAt`, `-likes` | `-trending` not supported on SepiaSearch (400 error) |
| `durationMin` | seconds | Filter: minimum duration |
| `durationMax` | seconds | Filter: maximum duration |
| `languageOneOf` | `en`, `fr`, … | Filter by language code |
| `categoryOneOf` | integer | Category ID (15=Science & Technology, etc.) |
| `isLive` | `true`/`false` | Filter live streams |
| `nsfw` | `false` | Exclude NSFW |

### SepiaSearch pagination

```python
import json
from helpers import http_get

def sepia_search(query, max_results=100, sort="-views"):
    videos = []
    start = 0
    count = min(100, max_results)
    while len(videos) < max_results:
        resp = json.loads(http_get(
            f"https://sepiasearch.org/api/v1/search/videos"
            f"?search={query}&count={count}&start={start}&sort={sort}"
        ))
        batch = resp.get("data", [])
        if not batch:
            break
        videos.extend(batch)
        start += len(batch)
        if start >= resp["total"]:
            break
    return videos[:max_results]

results = sepia_search("open source", max_results=200)
```

### SepiaSearch channel search

```python
import json
from helpers import http_get

resp = json.loads(http_get(
    "https://sepiasearch.org/api/v1/search/video-channels"
    "?search=linux&count=20"
))
for ch in resp["data"]:
    print(ch["name"], "@", ch["host"])
    print("  followers:", ch["followersCount"], "videos:", ch["videosCount"])
# Confirmed output (2026-04-18):
# linux @ diode.zone
#   followers: 6 videos: 1
```

---

## Instance API — trending / recent videos

```python
import json
from helpers import http_get

# Trending on framatube.org (20k+ videos)
resp = json.loads(http_get(
    "https://framatube.org/api/v1/videos?count=20&sort=-trending"
))
print("total:", resp["total"])   # 20156 (2026-04-18)
for v in resp["data"]:
    print(v["uuid"], v["views"], v["name"][:50])
```

Valid `sort` values for instance `/api/v1/videos`:
```
-trending  -hot  -views  -likes  -publishedAt  -createdAt
```

### Pagination on instance

```python
import json
from helpers import http_get

def iter_instance_videos(instance, sort="-publishedAt", max_videos=500):
    start = 0
    count = 100
    while start < max_videos:
        resp = json.loads(http_get(
            f"https://{instance}/api/v1/videos"
            f"?count={count}&start={start}&sort={sort}"
        ))
        batch = resp.get("data", [])
        if not batch:
            break
        yield from batch
        start += len(batch)
        if start >= resp["total"]:
            break

for v in iter_instance_videos("diode.zone", sort="-views", max_videos=200):
    print(v["uuid"], v["name"][:50])
```

### Known active public instances

```python
INSTANCES = [
    "framatube.org",      # 20k+ videos, Framasoft
    "diode.zone",         # 8.8k videos, tech focus
    "tilvids.com",        # 3.3k videos, educational
    "video.blender.org",  # 1.2k videos, Blender Foundation official
    "peertube.tv",        # 16.8k videos, general
]
```

---

## Video detail — streaming URLs

The list and search endpoints omit `streamingPlaylists` and `files`. Fetch the detail endpoint using the UUID and the video's **host instance**.

```python
import json
from helpers import http_get

uuid = "9c9de5e8-0a1e-484a-b099-e80766180a6d"
v = json.loads(http_get(f"https://framatube.org/api/v1/videos/{uuid}"))

# HLS master playlist (always present on modern instances, type=1)
for sp in v.get("streamingPlaylists", []):
    hls_master = sp["playlistUrl"]
    # e.g. https://framatube.org/static/streaming-playlists/hls/{uuid}/{id}-master.m3u8

    # Per-resolution files within the HLS playlist
    for f in sp.get("files", []):
        print(f["resolution"]["label"], f["fps"], f["size"])
        print("  HLS segment file:", f["fileUrl"])
        print("  Direct download:", f["fileDownloadUrl"])
        print("  Torrent URL:", f["torrentUrl"])
        print("  Magnet URI:", f["magnetUri"][:80])

# Legacy WebTorrent / direct MP4 (top-level v["files"], older instances only)
for f in v.get("files", []):
    print(f["resolution"]["label"], f.get("fileUrl", "")[:80])
# Confirmed output for 9c9de5e8 on framatube.org (2026-04-18):
# 1080p 24 16815344
#   HLS segment file: https://framatube.org/static/streaming-playlists/hls/9c9de5e8-.../9c9de5e8-...-1080-fragmented.mp4
#   Direct download: https://framatube.org/download/streaming-playlists/hls/videos/9c9de5e8-...-1080-fragmented.mp4
#   Torrent URL: https://framatube.org/lazy-static/torrents/...-1080-hls.torrent
#   Magnet URI: magnet:?xs=https%3A%2F%2Fframatube.org%2Flazy-static%2Ftorrents%2F...
# (also 720p, 480p, 360p, 240p)
```

### StreamingPlaylist file fields reference

```python
{
    "id":          1337952,
    "resolution":  {"id": 1080, "label": "1080p"},
    "width":       1920,
    "height":      1080,
    "fps":         24,
    "size":        16815344,                  # bytes
    "hasAudio":    True,
    "hasVideo":    True,
    "fileUrl":     "https://…/9c9de5e8-…-1080-fragmented.mp4",   # direct stream
    "fileDownloadUrl": "https://…/download/…/9c9de5e8-…-1080-fragmented.mp4",
    "torrentUrl":  "https://…/lazy-static/torrents/…-1080-hls.torrent",
    "torrentDownloadUrl": "https://…/…",
    "magnetUri":   "magnet:?xs=…&xt=urn:btih:…&dn=…&tr=…&ws=…",
    "metadataUrl": "https://…",
    "storage":     1,
}
```

### Tracker and redundancy

```python
v["trackerUrls"]           # list: HTTP announce + WebSocket announce
v["streamingPlaylists"][0]["redundancies"]  # list of {baseUrl} for CDN mirrors
# e.g. 14 redundancy mirrors for the framatube "What is PeerTube?" video
```

---

## Comments

```python
import json
from helpers import http_get

uuid = "9c9de5e8-0a1e-484a-b099-e80766180a6d"
resp = json.loads(http_get(
    f"https://framatube.org/api/v1/videos/{uuid}/comment-threads"
    "?count=25&start=0"
))
print("total threads:", resp["total"])

for thread in resp["data"]:
    c = thread
    print(c["id"], c["createdAt"][:10])
    print("  text (HTML):", c["text"][:100])
    print("  replies:", c["totalReplies"])
    print("  author:", c["account"]["name"] if c.get("account") else "[deleted]")

# Fetch replies to a specific thread
thread_id = resp["data"][0]["threadId"]
replies = json.loads(http_get(
    f"https://framatube.org/api/v1/videos/{uuid}/comment-threads/{thread_id}"
))
# replies["detail"]["children"] — nested reply tree
```

---

## Captions / subtitles

```python
import json
from helpers import http_get

uuid = "9c9de5e8-0a1e-484a-b099-e80766180a6d"
resp = json.loads(http_get(
    f"https://framatube.org/api/v1/videos/{uuid}/captions"
))
print("caption count:", resp["total"])  # e.g. 34 languages for the "What is PeerTube?" video

for cap in resp["data"]:
    print(cap["language"]["id"], cap["language"]["label"])
    print("  VTT URL:", cap["fileUrl"])
    # e.g. https://framatube.org/lazy-static/video-captions/…-en.vtt

# Download a caption file
vtt = http_get(resp["data"][0]["fileUrl"])
```

---

## Channels

```python
import json
from helpers import http_get

# Channel videos (by handle@instance or just handle on local instance)
resp = json.loads(http_get(
    "https://framatube.org/api/v1/video-channels"
    "?count=20&sort=-createdAt"
))
for ch in resp["data"]:
    print(ch["name"], "@", ch["host"])
    print("  followers:", ch["followersCount"])
    print("  url:", ch["url"])

# Videos belonging to a specific channel
ch_handle = "framasoft_channel@framatube.org"   # or just "framasoft_channel" on local instance
videos = json.loads(http_get(
    f"https://framatube.org/api/v1/video-channels/{ch_handle}/videos"
    "?count=20&sort=-views"
))
```

---

## Instance metadata

```python
import json
from helpers import http_get

info = json.loads(http_get("https://framatube.org/api/v1/config"))
print(info["instance"]["name"])          # "Framatube"
print(info["instance"]["shortDescription"])
print(info["serverVersion"])             # "8.1.5"
print(info["signup"]["allowed"])         # False
print(info["search"]["remoteUri"]["users"])     # True = logged-in users can search federation
print(info["search"]["remoteUri"]["anonymous"]) # False = anon users cannot
```

---

## Parallel collection across instances

```python
import json
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

INSTANCES = ["framatube.org", "diode.zone", "tilvids.com", "video.blender.org"]

def fetch_top(instance, n=20):
    try:
        resp = json.loads(http_get(
            f"https://{instance}/api/v1/videos?count={n}&sort=-views"
        ))
        return [(v["uuid"], v["name"], v["views"], instance)
                for v in resp.get("data", [])]
    except Exception:
        return []

with ThreadPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(fetch_top, INSTANCES))

all_videos = [v for batch in results for v in batch]
all_videos.sort(key=lambda x: x[2], reverse=True)
```

---

## URL construction reference

```python
uuid = "9c9de5e8-0a1e-484a-b099-e80766180a6d"
instance = "framatube.org"

watch_url     = f"https://{instance}/videos/watch/{uuid}"
embed_url     = f"https://{instance}/videos/embed/{uuid}"
api_detail    = f"https://{instance}/api/v1/videos/{uuid}"
thumbnail     = f"https://{instance}/lazy-static/thumbnails/{uuid}.jpg"
api_comments  = f"https://{instance}/api/v1/videos/{uuid}/comment-threads"
api_captions  = f"https://{instance}/api/v1/videos/{uuid}/captions"
```

---

## Gotchas

**`streamingPlaylists` and `files` are empty in list/search responses.** Both fields are `null`/absent on the list endpoint (`/api/v1/videos`) and SepiaSearch results. Always fetch `/api/v1/videos/{uuid}` on the video's host instance to get actual streaming URLs.

**Always use the host instance for detail fetches.** The UUID in SepiaSearch points to a video hosted on `v["account"]["host"]`. Fetching the UUID from a different instance will return a 404 or a federated copy that may lack streaming data. Use `v["url"]` to extract the canonical host.

```python
from urllib.parse import urlparse
host = urlparse(v["url"]).netloc   # "spectra.video"
detail = json.loads(http_get(f"https://{host}/api/v1/videos/{v['uuid']}"))
```

**`sort=-trending` is rejected by SepiaSearch (HTTP 400).** Valid SepiaSearch sorts: `-views`, `-publishedAt`, `-createdAt`, `-likes`. The `-trending` sort works only on instance endpoints.

**`isLocal: False` in list results means the video is federated.** The queried instance caches it. The authoritative copy and streaming files live at the host instance (see `account.host`).

**Direct MP4 `files` (WebTorrent) vs HLS `streamingPlaylists`.** Modern PeerTube instances (v5+) transcode into HLS only; `v["files"]` at the top level is empty. Older instances may have both. Always check `streamingPlaylists[0]["files"]` first; fall back to `v["files"]` for older instances.

**`magnetUri` in `streamingPlaylists[].files[]` points to HLS-fragmented MP4 segments**, not a complete MP4. Use `fileDownloadUrl` for a direct HTTP download of the full file.

**SepiaSearch caps total at 10000** regardless of the actual federated count. Use `start` to page up to that cap; beyond it you won't get more results from a single query. Narrow with `languageOneOf`, `categoryOneOf`, or `durationMin`/`durationMax` to dig into deeper slices.

**Comment text is HTML**, not plain text. Strip tags or parse with an HTML library before processing.

**Instance availability varies.** Wrap any cross-instance fetch in `try/except`. Some instances defederate, rate-limit, or go offline without warning. Check `/api/v1/config` first if you need to verify an instance is reachable.

**`count` max per request is 100** on most instance endpoints. SepiaSearch also caps at 100 per call. Page with `start`.
