# Genius — Data Extraction

Field-tested against genius.com on 2026-04-18.
No authentication required for any approach documented here.

---

## Anti-Bot: http_get Fails, Custom UA Required

`http_get` uses `User-Agent: Mozilla/5.0` (bare string). Genius returns HTTP 403 for that UA on both HTML pages and internal API endpoints. Adding any OS token (e.g. `(Macintosh; Intel Mac OS X 10_15_7)`) immediately lifts the block — no cookies, no session, no JavaScript required.

```python
from helpers import http_get

def genius_get(url, extra_headers=None):
    """Drop-in replacement for http_get on genius.com endpoints."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip",
    }
    if extra_headers:
        headers.update(extra_headers)
    return http_get(url, headers=headers)
```

Use `genius_get` everywhere in this document instead of bare `http_get`.

---

## Approach 1 (Fastest): Internal JSON API — No Auth, No Browser

Genius's own website calls `genius.com/api/*` (not `api.genius.com`) from
its server-side rendering layer. These endpoints are public and require only
a browser-like User-Agent. They return rich structured JSON in ~0.13s.

### Song metadata

```python
import json
from helpers import http_get

def genius_get(url, extra_headers=None):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip",
    }
    if extra_headers:
        headers.update(extra_headers)
    return http_get(url, headers=headers)

def genius_song(song_id):
    """Fetch full song metadata by Genius song ID."""
    data = json.loads(genius_get(f"https://genius.com/api/songs/{song_id}"))
    return data["response"]["song"]

song = genius_song(1063)
# All fields available in one call (no auth):
# song["title"]                          → "Bohemian Rhapsody"
# song["full_title"]                     → "Bohemian Rhapsody by Queen"
# song["artist_names"]                   → "Queen"
# song["primary_artist"]["name"]         → "Queen"
# song["primary_artist"]["id"]           → 563
# song["primary_artist"]["url"]          → "https://genius.com/artists/Queen"
# song["release_date"]                   → "1975-10-31"
# song["release_date_for_display"]       → "October 31, 1975"
# song["release_date_components"]        → {"year": 1975, "month": 10, "day": 31}
# song["stats"]["pageviews"]             → 11067562
# song["stats"]["contributors"]          → 516
# song["stats"]["accepted_annotations"]  → 20
# song["pyongs_count"]                   → 703
# song["annotation_count"]              → 33
# song["comment_count"]                 → 253
# song["album"]["name"]                 → "Studio Collection"   (varies by region)
# song["albums"][0]["name"]             → "A Night at the Opera"  (first = original)
# song["url"]                           → "https://genius.com/Queen-bohemian-rhapsody-lyrics"
# song["path"]                          → "/Queen-bohemian-rhapsody-lyrics"
# song["song_art_image_url"]            → "https://images.genius.com/718de9d..."
# song["explicit"]                      → False
# song["language"]                      → "en"
# song["lyrics_state"]                  → "complete"
# song["lyrics_verified"]              → False
# song["spotify_uuid"]                  → "7tFiyTwD0nx5a1eklYtX2J"
# song["youtube_url"]                   → "https://www.youtube.com/watch?v=fJ9rUzIMcZQ"
# song["writer_artists"]                → [{"name": "Freddie Mercury", ...}]
# song["producer_artists"]              → [{"name": "Roy Thomas Baker"}, {"name": "Queen"}]
# song["featured_artists"]             → []

# Primary album (first in list = original release):
primary_album = song["albums"][0]["name"]   # "A Night at the Opera"
```

### Search

```python
def genius_search(query, per_page=5):
    """Search Genius. Returns sections: top_hit, song, lyric, artist, album, video, article, user."""
    url = f"https://genius.com/api/search/multi?per_page={per_page}&q={urllib.parse.quote(query)}"
    data = json.loads(genius_get(url))
    return data["response"]["sections"]

import urllib.parse
sections = genius_search("Bohemian Rhapsody Queen", per_page=5)
# sections is a list of dicts with keys: "type", "hits"
# Each hit has: "type", "result"
# For type="song", result has: id, full_title, url, primary_artist, stats, ...

for section in sections:
    if section["type"] == "song":
        for hit in section["hits"]:
            r = hit["result"]
            print(r["full_title"], r["url"], r["id"])
        # Bohemian Rhapsody by Queen  https://genius.com/Queen-bohemian-rhapsody-lyrics  1063
        break

# Simpler search (song section only):
def genius_search_songs(query, per_page=5):
    sections = genius_search(query, per_page)
    for s in sections:
        if s["type"] == "song":
            return [h["result"] for h in s["hits"]]
    return []
```

### Artist songs (paginated)

```python
def genius_artist_songs(artist_id, per_page=20, sort="popularity"):
    """Fetch paginated list of songs for an artist. sort: 'popularity' or 'title'."""
    page = 1
    while True:
        url = (f"https://genius.com/api/artists/{artist_id}/songs"
               f"?per_page={per_page}&page={page}&sort={sort}")
        data = json.loads(genius_get(url))["response"]
        songs = data["songs"]
        if not songs:
            break
        yield from songs
        if data["next_page"] is None:
            break
        page = data["next_page"]

# Example: get top 5 Queen songs by popularity
for song in list(genius_artist_songs(563, per_page=5))[:5]:
    print(f"{song['full_title']} — {song['stats']['pageviews']:,} views")
# Bohemian Rhapsody by Queen — 11,067,663 views
# Don't Stop Me Now by Queen — 2,453,240 views
# Under Pressure by Queen & David Bowie — 1,972,606 views
# Somebody to Love by Queen — 1,241,740 views
# Killer Queen by Queen — 1,146,813 views
```

---

## Approach 2: Lyrics from HTML — Regex on data-lyrics-container

The lyrics live in `<div data-lyrics-container="true">` elements on the song's
lyrics page. There are usually 3–5 such divs (the song is split across sections).
Each div can contain nested child divs for annotation highlights — including a
`data-exclude-from-selection="true"` header div that must be stripped first.

```python
import re, json
from helpers import http_get

def genius_get(url, extra_headers=None):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip",
    }
    if extra_headers:
        headers.update(extra_headers)
    return http_get(url, headers=headers)

def _remove_excluded_divs(html):
    """Strip all <div data-exclude-from-selection="true"> subtrees (contributor headers)."""
    while True:
        idx = html.find('data-exclude-from-selection="true"')
        if idx == -1:
            break
        tag_start = html.rfind("<div", 0, idx)
        depth, pos = 0, tag_start
        while pos < len(html):
            if html[pos:pos+4] == "<div":
                depth += 1; pos += 4
            elif html[pos:pos+6] == "</div>":
                depth -= 1; pos += 6
                if depth == 0:
                    html = html[:tag_start] + html[pos:]
                    break
            else:
                pos += 1
        else:
            break
    return html

def _extract_div_content(html, marker):
    """Extract all <div> subtrees that contain the given attribute marker."""
    parts = []
    start = 0
    while True:
        idx = html.find(marker, start)
        if idx == -1:
            break
        tag_start = html.rfind("<div", 0, idx)
        depth, pos = 0, tag_start
        while pos < len(html):
            if html[pos:pos+4] == "<div":
                depth += 1; pos += 4
            elif html[pos:pos+6] == "</div>":
                depth -= 1; pos += 6
                if depth == 0:
                    parts.append(html[tag_start:pos])
                    break
            else:
                pos += 1
        start = idx + 1
    return parts

def _html_to_text(html_str):
    """Convert lyrics HTML to plain text, preserving line breaks."""
    text = re.sub(r"<br\s*/?>", "\n", html_str)
    text = re.sub(r"<[^>]+>", "", text)
    text = (text
            .replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
            .replace("&#39;", "'").replace("&quot;", '"').replace("&#x27;", "'")
            .replace("&#x2F;", "/").replace("&nbsp;", " "))
    # Collapse multiple blank lines to one
    lines = [l.strip() for l in text.split("\n")]
    result, prev_blank = [], False
    for line in lines:
        if not line:
            if not prev_blank:
                result.append("")
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False
    return "\n".join(result).strip()

def genius_lyrics(url):
    """
    Scrape lyrics from a Genius song URL.

    url: the canonical lyrics URL, e.g. 'https://genius.com/Queen-bohemian-rhapsody-lyrics'
    Returns: plain-text lyrics string with section headers like [Verse 1], [Chorus].
    """
    html = genius_get(url)
    cleaned = _remove_excluded_divs(html)
    containers = _extract_div_content(cleaned, 'data-lyrics-container="true"')
    parts = []
    for c in containers:
        text = _html_to_text(c).strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)

lyrics = genius_lyrics("https://genius.com/Queen-bohemian-rhapsody-lyrics")
# Returns 2076 chars, 62 lines, structured as:
# [Intro]
# Is this the real life? Is this just fantasy?
# Caught in a landslide, no escape from reality
# ...
# [Verse 1]
# Mama, just killed a man
# ...
# [Outro]
# Nothing really matters to me
# Any way the wind blows
```

**Performance:** Lyrics page is ~1.2 MB. One `genius_get` call takes ~0.18s.
No rate limiting observed across 10 rapid sequential requests.

---

## Approach 3: Combined Workflow — Metadata + Lyrics

The fastest complete extraction pattern: one API call for all metadata,
one HTML call for lyrics. Song ID can be derived several ways.

```python
import json, re, urllib.parse
from helpers import http_get

def genius_get(url, extra_headers=None):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip",
    }
    if extra_headers:
        headers.update(extra_headers)
    return http_get(url, headers=headers)

def genius_song_id_from_url(lyrics_url):
    """
    Extract Genius song ID from a lyrics page URL without fetching it.
    Returns None if not determinable — fall back to fetching the page.
    """
    # Not possible from the slug alone; must fetch the page or use search.
    # From the HTML: <meta content="genius://songs/{id}" name="twitter:app:url:iphone">
    html = genius_get(lyrics_url)
    m = re.search(r'content="genius://songs/(\d+)"', html)
    return int(m.group(1)) if m else None

def genius_full(query):
    """
    Search for a song, return metadata + lyrics in two HTTP calls.
    """
    # Call 1: search for song
    sections = json.loads(
        genius_get(f"https://genius.com/api/search/multi?per_page=3&q={urllib.parse.quote(query)}")
    )["response"]["sections"]
    song_result = None
    for s in sections:
        if s["type"] == "song" and s["hits"]:
            song_result = s["hits"][0]["result"]
            break
    if not song_result:
        return None

    song_id = song_result["id"]
    lyrics_url = song_result["url"]

    # Call 2: full metadata from internal API
    meta = json.loads(genius_get(f"https://genius.com/api/songs/{song_id}"))["response"]["song"]

    # Call 3: lyrics from HTML
    lyrics = genius_lyrics(lyrics_url)   # uses the function from Approach 2

    return {
        "id":           meta["id"],
        "title":        meta["title"],
        "artist":       meta["primary_artist"]["name"],
        "artist_id":    meta["primary_artist"]["id"],
        "album":        meta["albums"][0]["name"] if meta.get("albums") else None,
        "release_date": meta["release_date"],           # "1975-10-31"
        "pageviews":    meta["stats"]["pageviews"],      # 11067562
        "contributors": meta["stats"]["contributors"],   # 516
        "writers":      [a["name"] for a in meta["writer_artists"]],
        "producers":    [a["name"] for a in meta["producer_artists"]],
        "spotify_uuid": meta["spotify_uuid"],
        "youtube_url":  meta["youtube_url"],
        "song_art_url": meta["song_art_image_url"],
        "lyrics_url":   meta["url"],
        "lyrics":       lyrics,
    }

result = genius_full("Queen Bohemian Rhapsody")
# {
#   "id":           1063,
#   "title":        "Bohemian Rhapsody",
#   "artist":       "Queen",
#   "artist_id":    563,
#   "album":        "A Night at the Opera",
#   "release_date": "1975-10-31",
#   "pageviews":    11067562,
#   "contributors": 516,
#   "writers":      ["Freddie Mercury"],
#   "producers":    ["Roy Thomas Baker", "Queen"],
#   "spotify_uuid": "7tFiyTwD0nx5a1eklYtX2J",
#   "youtube_url":  "https://www.youtube.com/watch?v=fJ9rUzIMcZQ",
#   "song_art_url": "https://images.genius.com/718de9d1fbcaae9f3c9b1bf483bfa8f1.1000x1000x1.png",
#   "lyrics_url":   "https://genius.com/Queen-bohemian-rhapsody-lyrics",
#   "lyrics":       "[Intro]\nIs this the real life?..."
# }
```

---

## URL and ID Patterns

| Resource    | URL pattern                                   | Notes                            |
|-------------|-----------------------------------------------|----------------------------------|
| Song page   | `genius.com/{Artist}-{song-slug}-lyrics`      | Slug is lowercased, hyphenated   |
| Artist page | `genius.com/artists/{Artist}`                 | Title-cased artist name          |
| Album page  | `genius.com/albums/{Artist}/{album-slug}`     |                                  |
| Song API    | `genius.com/api/songs/{id}`                   | Internal; no auth required       |
| Artist API  | `genius.com/api/artists/{id}`                 | Internal; no auth required       |
| Artist songs| `genius.com/api/artists/{id}/songs?...`       | per_page, page, sort params      |
| Search API  | `genius.com/api/search/multi?per_page=N&q=...`| Internal; multi-section results  |

**Extracting song ID from a known lyrics URL:**

```python
# The slug alone cannot be decoded to an ID. Must fetch HTML or search.
# From lyrics page HTML (fastest — one line):
song_id = re.search(r'content="genius://songs/(\d+)"', html).group(1)

# Or from __PRELOADED_STATE__ (same page, equally reliable):
song_id = re.search(r'\\"song\\":\s*(\d+)', html).group(1)

# Or from search API (no HTML required):
sections = json.loads(genius_get(f"https://genius.com/api/search/multi?per_page=1&q={query}"))
# then walk sections for type="song"
```

---

## What Requires a Browser

The following are **not available** via `genius_get` / HTTP:

- **Search results page** (`/search?q=...`): renders client-side only. The
  returned HTML contains no song results matching the query. Use the internal
  search API (`/api/search/multi`) instead — it works without a browser.

- **Public API** (`api.genius.com`): returns HTTP 401 without a Bearer token
  even with a browser-like User-Agent. Must register at genius.com/developers
  to obtain a client access token. The internal site API (`genius.com/api/*`)
  is the no-auth alternative and returns equivalent data.

- **Annotations content**: annotation HTML is embedded in `__PRELOADED_STATE__`
  but the JSON is multi-escaped (six levels of backslash nesting) and cannot
  be reliably parsed with plain string operations. Annotation IDs are
  available but their body text is not easily extractable.

- **Login-gated features**: user library, personalization, editor tools.

---

## Public API (api.genius.com) — Requires Bearer Token

If you have a token (free registration at genius.com/developers):

```python
def genius_api(path, token):
    """Call the official public API. path example: '/songs/1063'"""
    import json
    from helpers import http_get
    url = f"https://api.genius.com{path}"
    return json.loads(http_get(url, headers={"Authorization": f"Bearer {token}"}))

# Returns same structure as the internal /api/* endpoints.
# Endpoints: /songs/{id}, /artists/{id}, /artists/{id}/songs, /search?q=...
# Without a token: HTTP 401 with body:
# {"meta": {"status": 401, "message": "This call requires an access_token..."}}
```

---

## Gotchas

- **`http_get` returns 403**: The default `User-Agent: Mozilla/5.0` (bare) is
  blocked. Add any OS string — `(Macintosh; Intel Mac OS X 10_15_7)` is
  sufficient. Use the `genius_get` wrapper from this document.

- **`data-lyrics-container` split across 3–5 divs**: Don't look for a single
  lyrics block. Use `_extract_div_content` on all occurrences, then join.
  Empty containers (`<div ...></div>`, 87 bytes) appear between sections —
  the `if text:` guard skips them cleanly.

- **`data-exclude-from-selection` header in first container**: The first
  lyrics container includes a contributor credit header div. It must be
  stripped before text extraction or the output will begin with
  `"516 ContributorsTranslations..."` instead of `"[Intro]"`.

- **`album` field vs `albums[0]`**: `song["album"]` is the "primary" album
  used by Genius's album link (often a compilation or reissue). `song["albums"][0]`
  is the first album in the full list and is typically the original release.
  Verified: for Bohemian Rhapsody, `album.name` = "Studio Collection" but
  `albums[0].name` = "A Night at the Opera".

- **`__PRELOADED_STATE__` is not parseable**: The state is embedded as
  `JSON.parse('...')` where the inner JSON is escaped six levels deep
  (`\\\\\"` for a literal quote inside HTML content). Standard string
  replacement fails due to `\\'` and `\$` sequences. Don't try to parse it —
  use the `/api/songs/{id}` endpoint instead.

- **No `__NEXT_DATA__`**: Genius does not use Next.js. There is no
  `<script id="__NEXT_DATA__">` on any page.

- **No JSON-LD**: Genius does not emit `<script type="application/ld+json">`.
  Open Graph tags are present but minimal (only `og:title`, `og:image`,
  `og:description`, `og:url`, `og:type`). Use the API for structured data.

- **Search page is client-side only**: `GET /search?q=...` returns an HTML
  shell with ~5 unrelated song links (trending, not query-matched). The actual
  search results are fetched client-side by JavaScript. Use `/api/search/multi`
  instead — it works without a browser and returns properly filtered results.

- **Rate limiting**: No rate limiting observed across 10 rapid sequential
  requests to `/api/songs/{id}` (avg 0.13s/request). Song lyrics pages
  average 0.18s. No Retry-After headers observed.

- **Cloudflare**: Present (confirmed by `<meta itemprop="cf-country">` and
  `cf-cache-status` tags), but in pass-through mode — no JS challenge, no
  CAPTCHA. A browser-like User-Agent is all that's needed.
