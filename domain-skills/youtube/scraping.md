# YouTube — Data Extraction

Field-tested against youtube.com on 2026-04-21.
No authentication required for any approach documented here.

---

## Approach 1 (Fastest): oEmbed API — No Auth, No Browser

`https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={VIDEO_ID}&format=json`

Returns JSON in ~0.3s. Works for any public video. Does **not** require login.

```python
from helpers import http_get
import json

def youtube_oembed(video_id):
    """Fetch oEmbed metadata for a YouTube video.

    Returns title, author, thumbnail URL, and embed iframe HTML.
    """
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    return json.loads(http_get(url))

data = youtube_oembed("dQw4w9WgXcQ")
# {
#   "title":            "Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)",
#   "author_name":      "Rick Astley",
#   "author_url":       "https://www.youtube.com/@RickAstleyYT",
#   "type":             "video",
#   "thumbnail_url":    "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
#   "thumbnail_width":  480,
#   "thumbnail_height": 360,
#   "width":            200,
#   "height":           113,
#   "version":          "1.0",
#   "provider_name":    "YouTube",
#   "html":             '<iframe width="200" height="113" src="https://www.youtube.com/embed/dQw4w9WgXcQ?feature=oembed" ...>'
# }
```

### Bulk oEmbed (ThreadPoolExecutor)

```python
from concurrent.futures import ThreadPoolExecutor
import json
from helpers import http_get

video_ids = ["dQw4w9WgXcQ", "jNQXAC9IVRw", "9bZkp7q19f0"]

def fetch_oembed(vid):
    url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json"
    try:
        return json.loads(http_get(url))
    except Exception as e:
        return {"error": str(e), "id": vid}

with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_oembed, video_ids))
# 3 videos: ~4.1s total (YouTube oEmbed is slower than Spotify's; don't use >5 workers)
```

---

## Approach 2: Watch Page — Full Metadata via ytInitialPlayerResponse

Every `youtube.com/watch?v={ID}` page embeds two JSON blobs in the HTML:

- `ytInitialPlayerResponse` — video details, microformat, caption track list
- `ytInitialData` — comments section structure, related videos

### Extract all video metadata

```python
from helpers import http_get
import json, re

def scrape_video(video_id):
    html = http_get(f"https://www.youtube.com/watch?v={video_id}")

    # ---- ytInitialPlayerResponse ----
    m = re.search(r'var ytInitialPlayerResponse = (\{.*?\});(?:var|</script>)', html, re.DOTALL)
    if not m:
        raise ValueError(f"ytInitialPlayerResponse not found for video {video_id} — video may be private, deleted, or region-blocked")
    pr = json.loads(m.group(1))

    # Check playability before parsing
    status = pr.get("playabilityStatus", {}).get("status")
    if status == "LOGIN_REQUIRED":
        raise ValueError(f"Video {video_id} is age-restricted or login-gated (playabilityStatus: LOGIN_REQUIRED)")
    if status == "ERROR":
        reason = pr.get("playabilityStatus", {}).get("reason", "unknown")
        raise ValueError(f"Video {video_id} is unavailable: {reason}")

    vd  = pr["videoDetails"]
    mf  = pr["microformat"]["playerMicroformatRenderer"]
    caps = pr.get("captions", {}) \
             .get("playerCaptionsTracklistRenderer", {}) \
             .get("captionTracks", [])

    return {
        # Core
        "video_id":      vd["videoId"],
        "title":         vd["title"],
        "author":        vd["author"],
        "channel_id":    vd["channelId"],
        "description":   vd["shortDescription"],
        "duration_s":    int(vd["lengthSeconds"]),
        "view_count":    int(vd["viewCount"]),
        "keywords":      vd.get("keywords", []),
        "is_live":       vd.get("isLiveContent", False),
        "is_private":    vd.get("isPrivate", False),
        # Microformat (richer publishing data)
        "publish_date":  mf.get("publishDate"),   # ISO 8601, e.g. "2009-10-25T00:57:33-07:00"
        "upload_date":   mf.get("uploadDate"),
        "category":      mf.get("category"),       # e.g. "Music", "Gaming", "Education"
        "like_count":    int(mf.get("likeCount", 0)),
        "is_family_safe": mf.get("isFamilySafe"),
        "is_unlisted":   mf.get("isUnlisted"),
        "available_countries": mf.get("availableCountries", []),  # list of ISO 3166-1 alpha-2 codes
        "channel_name":  mf.get("ownerChannelName"),
        "channel_url":   mf.get("ownerProfileUrl"),
        "embed_url":     mf.get("embed", {}).get("iframeUrl"),
        # Thumbnails (all publicly accessible, no auth)
        "thumbnail_hq":  f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",    # 480×360, always exists
        "thumbnail_max": f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg", # 1280×720, may 404
        # Caption tracks — baseUrl is included for reference but returns empty in practice;
        # use the Show Transcript UI flow in the browser instead (see playback.md)
        "caption_tracks": [
            {
                "lang":     t.get("languageCode"),
                "name":     t.get("name", {}).get("simpleText"),
                "kind":     t.get("kind", "manual"),  # "manual" or "asr" (auto-generated)
                "base_url": t.get("baseUrl"),
            }
            for t in caps
        ],
    }

video = scrape_video("dQw4w9WgXcQ")
# {
#   "video_id":     "dQw4w9WgXcQ",
#   "title":        "Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)",
#   "author":       "Rick Astley",
#   "channel_id":   "UCuAXFkgsw1L7xaCfnd5JJOw",
#   "duration_s":   213,
#   "view_count":   1764468859,
#   "publish_date": "2009-10-24T23:57:33-07:00",
#   "category":     "Music",
#   "like_count":   16942558,
#   "caption_tracks": [
#     {"lang": "en",    "name": "English",                "kind": "manual"},
#     {"lang": "en",    "name": "English (auto-generated)", "kind": "asr"},
#     {"lang": "de-DE", "name": "German (Germany)",        "kind": "manual"},
#     ...
#   ],
# }
```

---

## Approach 3: Search Results — No Auth

`youtube.com/results?search_query={QUERY}` is server-side rendered. The `ytInitialData` blob contains up to ~20 video results.

```python
from helpers import http_get
import json, re
from urllib.parse import quote_plus

def youtube_search(query, max_results=20):
    """Search YouTube videos without a browser or API key."""
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    html = http_get(url)

    m = re.search(r'var ytInitialData = (\{.*?\});</script>', html, re.DOTALL)
    data = json.loads(m.group(1))

    # Walk the nested structure to find videoRenderer items
    section_contents = (
        data.get("contents", {})
            .get("twoColumnSearchResultsRenderer", {})
            .get("primaryContents", {})
            .get("sectionListRenderer", {})
            .get("contents", [])
    )

    results = []
    for section in section_contents:
        for item in section.get("itemSectionRenderer", {}).get("contents", []):
            vr = item.get("videoRenderer", {})
            if not vr:
                continue
            snippet = vr.get("detailedMetadataSnippets", [])
            desc = (
                "".join(r.get("text", "") for r in snippet[0]["snippetText"]["runs"])
                if snippet else None
            )
            results.append({
                "video_id":   vr["videoId"],
                "url":        f"https://www.youtube.com/watch?v={vr['videoId']}",
                "title":      vr.get("title", {}).get("runs", [{}])[0].get("text"),
                "channel":    vr.get("ownerText", {}).get("runs", [{}])[0].get("text"),
                "channel_url": (
                    "https://www.youtube.com"
                    + vr.get("ownerText", {}).get("runs", [{}])[0]
                                              .get("navigationEndpoint", {})
                                              .get("browseEndpoint", {})
                                              .get("canonicalBaseUrl", "")
                ),
                "duration":   vr.get("lengthText", {}).get("simpleText"),  # e.g. "3:32"
                "views":      vr.get("viewCountText", {}).get("simpleText"),  # e.g. "1,764,468,859 views"
                "published":  vr.get("publishedTimeText", {}).get("simpleText"),  # e.g. "7 years ago"
                "description_snippet": desc,
                "thumbnail":  f"https://i.ytimg.com/vi/{vr['videoId']}/hqdefault.jpg",
            })
            if len(results) >= max_results:
                return results  # exit both loops immediately
    return results

results = youtube_search("python tutorial", max_results=5)
# Returns up to ~14-20 results (YouTube serves fewer than 20 on first page)
# [
#   {
#     "video_id":  "K5KVEU3aaeQ",
#     "title":     "Python Full Course for Beginners",
#     "channel":   "Programming with Mosh",
#     "duration":  "2:02:21",
#     "views":     "6,056,121 views",
#     "published": "1 year ago",
#   }, ...
# ]
```

---

## Approach 4: Channel Metadata — No Auth

Channel pages (`youtube.com/@handle` or `youtube.com/channel/{CHANNEL_ID}`) embed metadata in `ytInitialData`.

```python
from helpers import http_get
import json, re

def scrape_channel(handle_or_id):
    """
    handle_or_id: "@RickAstleyYT"           (handle, with @)
                  "UCuAXFkgsw1L7xaCfnd5JJOw" (channel ID)
    """
    if handle_or_id.startswith("UC"):
        url = f"https://www.youtube.com/channel/{handle_or_id}"
    else:
        url = f"https://www.youtube.com/{handle_or_id}"

    html = http_get(url)
    m = re.search(r'var ytInitialData = (\{.*?\});</script>', html, re.DOTALL)
    data = json.loads(m.group(1))

    # Canonical metadata (always present)
    cmd = data.get("metadata", {}).get("channelMetadataRenderer", {})

    # Subscriber count + handle from pageHeaderViewModel
    ph = (
        data.get("header", {})
            .get("pageHeaderRenderer", {})
            .get("content", {})
            .get("pageHeaderViewModel", {})
    )
    meta_parts = [
        part.get("text", {}).get("content", "")
        for row in ph.get("metadata", {})
                     .get("contentMetadataViewModel", {})
                     .get("metadataRows", [])
        for part in row.get("metadataParts", [])
    ]
    # meta_parts is typically: ["@handle", "4.48m subscribers", "N videos"]

    # Avatar (take the largest source)
    avatar_sources = (
        ph.get("image", {})
          .get("decoratedAvatarViewModel", {})
          .get("avatar", {})
          .get("avatarViewModel", {})
          .get("image", {})
          .get("sources", [])
    )
    avatar_url = avatar_sources[-1]["url"] if avatar_sources else None

    # Channel banner
    banner_sources = (
        ph.get("banner", {})
          .get("imageBannerViewModel", {})
          .get("image", {})
          .get("sources", [])
    )
    banner_url = banner_sources[-1]["url"] if banner_sources else None

    return {
        "channel_id":  cmd.get("externalId"),
        "title":       cmd.get("title"),
        "description": cmd.get("description"),
        "channel_url": cmd.get("channelUrl"),
        "keywords":    cmd.get("keywords", ""),
        "handle":      meta_parts[0] if len(meta_parts) > 0 else None,
        "subscribers": meta_parts[1] if len(meta_parts) > 1 else None,  # e.g. "4.48m subscribers"
        "avatar_url":  avatar_url,
        "banner_url":  banner_url,
    }

channel = scrape_channel("@RickAstleyYT")
# {
#   "channel_id":  "UCuAXFkgsw1L7xaCfnd5JJOw",
#   "title":       "Rick Astley",
#   "description": "2026 UK & Ireland Reflection Tour...",
#   "channel_url": "https://www.youtube.com/channel/UCuAXFkgsw1L7xaCfnd5JJOw",
#   "handle":      "@RickAstleyYT",
#   "subscribers": "4.48m subscribers",
#   "avatar_url":  "https://yt3.googleusercontent.com/...",
#   "banner_url":  "https://yt3.googleusercontent.com/...",
# }
```

---

## Thumbnail URLs — All Sizes

All thumbnail sizes are publicly accessible without auth. Construct directly from `video_id`:

```python
def thumbnail_urls(video_id):
    base = f"https://i.ytimg.com/vi/{video_id}"
    return {
        "default":  f"{base}/default.jpg",      # 120×90,  always exists
        "medium":   f"{base}/mqdefault.jpg",     # 320×180, always exists
        "high":     f"{base}/hqdefault.jpg",     # 480×360, always exists
        "standard": f"{base}/sddefault.jpg",     # 640×480, always exists
        "maxres":   f"{base}/maxresdefault.jpg", # 1280×720, may 404 on older/low-res videos
    }
```

---

## Extract Video ID from Any URL

```python
import re

def extract_video_id(url):
    """Extract YouTube video ID (11-char) from any YouTube URL format."""
    m = re.search(r'(?:v=|/v/|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})', url)
    return m.group(1) if m else None

extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")  # "dQw4w9WgXcQ"
extract_video_id("https://youtu.be/dQw4w9WgXcQ")                  # "dQw4w9WgXcQ"
extract_video_id("https://www.youtube.com/shorts/dQw4w9WgXcQ")    # "dQw4w9WgXcQ"
extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ")     # "dQw4w9WgXcQ"
```

---

## What Requires a Browser

The following are **not accessible** via `http_get` and require the CDP browser (see `playback.md`):

- **Trending / Explore** (`/feed/trending`) — `ytInitialData` loads but video items are empty without cookies
- **Playlist contents** — `ytInitialData` returns only microformat; full video list requires session cookies
- **Comments** — loaded lazily via XHR, not present in initial HTML
- **Shorts feed** — requires JS hydration
- **Channel Videos tab** — video list requires cookies for consistent results
- **Caption text content** — `captionTracks[].baseUrl` URLs return empty bytes regardless of session state; use the browser's Show Transcript UI flow instead (see `playback.md`)
- **Age-restricted videos** — oEmbed returns HTTP 401; `scrape_video()` raises `ValueError("LOGIN_REQUIRED")`

### Watch-page DOM hydration — the wait you need

When you do fall through to the browser for watch-page DOM (e.g. because you need a
rendered UI state, not just metadata), `wait_for_load()` is **not** enough. The `load`
event fires before YouTube's Polymer components hydrate — `h1.ytd-watch-metadata yt-formatted-string`,
`ytd-video-owner-renderer #channel-name a`, and `ytd-watch-info-text` all return `null` for
~2s after load. Add a `wait(3)` after `wait_for_load()` before querying any watch-page
selector.

Field-tested 2026-04-24 on Brave; same behavior observed on ungoogled-chromium. Prefer
the `http_get` + `ytInitialPlayerResponse` path above — the browser path exists for flows
that need live UI state, not for reading metadata.

---

## URL Patterns

| Resource       | URL pattern                                                        |
|----------------|--------------------------------------------------------------------|
| Video          | `https://www.youtube.com/watch?v={VIDEO_ID}`                       |
| Short URL      | `https://youtu.be/{VIDEO_ID}`                                      |
| Shorts         | `https://www.youtube.com/shorts/{VIDEO_ID}`                        |
| Channel handle | `https://www.youtube.com/@{HANDLE}`                                |
| Channel ID     | `https://www.youtube.com/channel/{CHANNEL_ID}`                     |
| Playlist       | `https://www.youtube.com/playlist?list={PLAYLIST_ID}`              |
| Search         | `https://www.youtube.com/results?search_query={QUERY}`             |
| oEmbed         | `https://www.youtube.com/oembed?url={VIDEO_URL}&format=json`       |
| Thumbnail (HQ) | `https://i.ytimg.com/vi/{VIDEO_ID}/hqdefault.jpg`                  |

---

## Gotchas

- **`ytInitialPlayerResponse` regex must use non-greedy match with lookahead** — `(\{.*?\});(?:var|</script>)` with `re.DOTALL` is reliable. Do not use `\{.*\}` (greedy) — it consumes the entire rest of the page.
- **`viewCount` and `lengthSeconds` are strings, not ints** — `vd["viewCount"]` returns `"1764468859"`. Always cast with `int()`.
- **`likeCount` lives in `microformat`, not `videoDetails`** — `videoDetails` does not expose like count. `microformat.playerMicroformatRenderer.likeCount` is a string integer.
- **`availableCountries` is a list of ISO 3166-1 alpha-2 codes** — 249 entries for globally available videos. An empty list means region data is unavailable, not that the video is globally blocked.
- **oEmbed thumbnail is always `hqdefault` (480×360)** — if you need 1280×720, construct the `maxresdefault.jpg` URL directly, but check for 404 on older videos.
- **Search returns ~14–20 results** — YouTube does not guarantee 20 results. Always iterate `itemSectionRenderer.contents` rather than assuming a fixed count.
- **Channel subscriber count is a rounded string** — `"4.48m subscribers"`, not an integer. Parse with regex if sorting: `re.search(r'([\d.]+)\s*([km]?)', text, re.I)`.
- **`meta_parts` order is `[handle, subscribers, video_count]`** — the third element is not always present. Index defensively.
- **Caption `baseUrl` is not fetchable** — `captionTracks[].baseUrl` contains `expire=` and `signature=` params but returns empty bytes in all tested conditions (plain `http_get`, XHR from within the page, and `fetch()` with cookies). Use the Show Transcript UI in the browser for caption text (see `playback.md`).
- **Age-restricted videos** — `scrape_video()` raises `ValueError` with a `LOGIN_REQUIRED` message. `oEmbed` returns HTTP 401 (raises `urllib.error.HTTPError`). Neither approach can access age-restricted content without login.
- **Private / deleted videos** — oEmbed returns HTTP 404 (raises `urllib.error.HTTPError`). Wrap in `try/except`.
- **`ytInitialData` blob terminator is `;</script>`** — using `re.DOTALL` with `(\{.*?\});</script>` is safe; the blob does not contain `;</script>` internally.
