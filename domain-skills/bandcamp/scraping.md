# Bandcamp — Data Extraction

Field-tested against bandcamp.com on 2026-04-18.
No authentication required for any approach documented here. All code uses `http_get` (pure HTTP, no browser) except the search approach.
Bandcamp has no official public API but embeds rich JSON in every page's HTML data attributes.

---

## Approach 1 (Fastest): `data-tralbum` — Album/Track Metadata + Full Track List

Every album and track page serves complete metadata in a `data-tralbum` attribute. No JS rendering needed.

```python
from helpers import http_get
import json, re
from html import unescape
import ssl, urllib.request, gzip

# http_get in helpers may fail with SSL on some systems; use this drop-in:
def _get(url):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    h = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip",
         "Accept": "text/html,application/xhtml+xml,*/*"}
    req = urllib.request.Request(url, headers=h)
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    with opener.open(req, timeout=20) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return data.decode("utf-8", errors="replace")

def bandcamp_album(album_url):
    """Extract full metadata from an album or track page URL."""
    page = _get(album_url)

    m = re.search(r'data-tralbum="([^"]+)"', page)
    if not m:
        raise ValueError("data-tralbum not found — page may have redirected to signup")
    tralbum = json.loads(unescape(m.group(1)))

    m2 = re.search(r'data-band="([^"]+)"', page)
    band = json.loads(unescape(m2.group(1))) if m2 else {}

    current = tralbum.get("current", {})
    art_id = tralbum.get("art_id")

    return {
        # --- Identity ---
        "item_type":    tralbum.get("item_type"),   # 'album' or 'track'
        "id":           current.get("id"),
        "url":          tralbum.get("url"),

        # --- Metadata ---
        "title":        current.get("title"),
        "artist":       tralbum.get("artist"),
        "about":        current.get("about"),       # description
        "credits":      current.get("credits"),
        "upc":          current.get("upc"),
        "release_date": current.get("release_date"),
        "publish_date": current.get("publish_date"),

        # --- Pricing ---
        "set_price":    current.get("set_price"),   # None if name-your-price
        "minimum_price": current.get("minimum_price"),
        "download_pref": current.get("download_pref"),
        # download_pref: 1=free, 2=name-your-price (FREE=1, PAID=2 are the constants)

        # --- Artwork ---
        # art_id for album cover: https://f4.bcbits.com/img/a{art_id}_{size}.jpg
        # sizes: _0 (~800px), _2 (original), _10 (700px), _16 (700px), _23 (300px)
        "art_id":       art_id,
        "cover_url":    f"https://f4.bcbits.com/img/a{art_id}_10.jpg" if art_id else None,

        # --- Tracks ---
        "tracks":       _parse_tracks(tralbum.get("trackinfo", [])),

        # --- Physical merch (vinyl, CD, cassette) ---
        "packages":     _parse_packages(tralbum.get("packages", [])),

        # --- Band info ---
        "band_id":      band.get("id"),
        "band_name":    band.get("name"),
        "band_url":     band.get("url"),
        "band_currency": band.get("currency"),
        "is_label":     band.get("is_label"),
    }

def _parse_tracks(trackinfo):
    out = []
    for t in trackinfo:
        stream = t.get("file") or {}
        out.append({
            "track_num":   t.get("track_num"),
            "title":       t.get("title"),
            "duration":    t.get("duration"),     # seconds (float), 0.0 if not streamable
            "artist":      t.get("artist"),        # set if different from album artist
            "has_lyrics":  t.get("has_lyrics"),
            "streaming":   t.get("streaming"),    # 1=can stream
            "is_downloadable": t.get("is_downloadable"),
            "has_free_download": t.get("has_free_download"),
            "play_count":  t.get("play_count"),
            "track_url":   t.get("title_link"),   # relative path, e.g. /track/song-name
            # Stream URL — valid for ~24h (ts param is expiry Unix timestamp)
            "stream_mp3":  stream.get("mp3-128"),
        })
    return out

def _parse_packages(packages):
    out = []
    for p in packages:
        out.append({
            "title":       p.get("title"),
            "price":       p.get("price"),         # float USD
            "type_name":   p.get("type_name"),     # e.g. "Vinyl LP"
            "edition_size": p.get("edition_size"),
            "quantity_available": p.get("quantity_available"),
            "quantity_sold": p.get("quantity_sold"),
            "url":         p.get("url"),
        })
    return out


# --- Example ---
album = bandcamp_album("https://djseinfeld.bandcamp.com/album/if-this-is-it")
# {
#   "item_type":    "album",
#   "id":           3797931520,
#   "url":          "https://djseinfeld.bandcamp.com/album/if-this-is-it",
#   "title":        "If This Is It",
#   "artist":       "DJ Seinfeld",
#   "about":        "With his highly accomplished third album...",
#   "upc":          "5054429206265",
#   "release_date": "05 Jun 2026 00:00:00 GMT",
#   "set_price":    9.0,
#   "minimum_price": 9.0,
#   "download_pref": 2,
#   "art_id":       3871310243,
#   "cover_url":    "https://f4.bcbits.com/img/a3871310243_10.jpg",
#   "tracks": [
#     {"track_num": 1, "title": "U Can't Come Home (feat. TS Graye)", "duration": 196.416,
#      "streaming": 1, "stream_mp3": "https://t4.bcbits.com/stream/..."},
#     {"track_num": 2, "title": "Quakin'", "duration": 0.0, "stream_mp3": None},
#     ...  # 12 total
#   ],
#   "packages": [
#     {"title": "DJ Seinfeld - 'If This Is It' Clear Vinyl [ZEN319]", "price": 30.0},
#     {"title": "DJ Seinfeld - 'If This Is It' Colour Vinyl [ZEN319N]", "price": 30.0},
#   ],
#   "band_id":      205707144,
#   "band_name":    "DJ Seinfeld",
#   "band_currency": "GBP",
#   "is_label":     False,
# }

# Same function works for individual track pages:
track = bandcamp_album("https://djseinfeld.bandcamp.com/track/u-cant-come-home-feat-ts-graye")
# track["item_type"] == "track"
# track["tracks"] has 1 entry
```

---

## Approach 2: Artist Page — Band Info + Discography Listing

```python
def bandcamp_artist(artist_url):
    """
    Fetch artist/band info and album listing from the artist or /music page.
    artist_url examples:
      'https://djseinfeld.bandcamp.com/'
      'https://djseinfeld.bandcamp.com/music'
    """
    page = _get(artist_url)

    # Band metadata
    m = re.search(r'data-band="([^"]+)"', page)
    band = json.loads(unescape(m.group(1))) if m else {}

    # Meta tags
    metas = {}
    for mm in re.finditer(r'<meta[^>]+(?:property|name)="([^"]+)"[^>]+content="([^"]*)"', page):
        metas[mm.group(1)] = mm.group(2)

    # Album/track grid items on the /music page
    items = []
    for li in re.finditer(
        r'<li[^>]+class="music-grid-item[^"]*"[^>]*>(.*?)</li>', page, re.DOTALL
    ):
        li_html = li.group(1)
        href_m = re.search(r'href="([^"]+)"', li_html)
        title_m = re.search(r'class="title"[^>]*>\s*(.*?)\s*</p>', li_html, re.DOTALL)
        img_m = re.search(r'<img src="([^"]+)"', li_html)
        title_raw = title_m.group(1) if title_m else ""
        # Strip HTML from title (some have <br><span> for VA releases)
        title_clean = re.sub(r"<[^>]+>", "", title_raw).strip()
        items.append({
            "path":  href_m.group(1) if href_m else None,
            "title": title_clean,
            "art":   img_m.group(1) if img_m else None,
        })

    # Shows / upcoming events from data-blob
    blob_m = re.search(r'data-blob="([^"]+)"', page)
    shows = []
    if blob_m:
        blob = json.loads(unescape(blob_m.group(1)))
        for s in blob.get("shows_list", []):
            shows.append({
                "venue": s.get("venue"),
                "loc":   s.get("loc"),
                "date":  s.get("date"),
                "url":   s.get("uri"),
            })

    return {
        "name":        band.get("name") or metas.get("og:title"),
        "id":          band.get("id"),
        "url":         band.get("url") or metas.get("og:url"),
        "description": metas.get("og:description"),
        "image":       metas.get("og:image"),      # band photo/logo
        "currency":    band.get("currency"),
        "genre_id":    band.get("genre_id"),
        "is_label":    band.get("is_label"),
        "has_merch":   band.get("merch_enabled"),
        "discography": items,   # all public releases visible on /music
        "shows":       shows,
    }


# --- Example ---
artist = bandcamp_artist("https://djseinfeld.bandcamp.com/music")
# {
#   "name":   "DJ Seinfeld",
#   "id":     205707144,
#   "url":    "https://djseinfeld.bandcamp.com",
#   "description": "DJ Seinfeld\nRimbaudian\nBirds Of Sweden",
#   "image":  "https://f4.bcbits.com/img/0042812762_23.jpg",
#   "currency": "GBP",
#   "is_label": False,
#   "discography": [
#     {"path": "/album/if-this-is-it", "title": "If This Is It",
#      "art": "https://f4.bcbits.com/img/a3871310243_2.jpg"},
#     {"path": "/album/of-joy",        "title": "Of Joy", ...},
#     ...  # 16 items
#   ],
#   "shows": [
#     {"venue": "Fabric", "loc": "London, UK", "date": "2026-05-10", "url": "..."},
#     ...  # 13 upcoming
#   ]
# }
```

---

## Approach 3: Discover API — Browse by Genre/Tag (POST)

`POST https://bandcamp.com/api/hub/2/dig_deeper` — internal discovery endpoint, no auth required.
Returns 20 items per page with streaming preview URLs.

```python
import json, ssl, urllib.request, gzip

def _post_json(url, payload):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    h = {
        "User-Agent":   "Mozilla/5.0",
        "Content-Type": "application/json",
        "Accept":       "application/json",
        "Accept-Encoding": "gzip",
        "Referer":      "https://bandcamp.com/discover",
        "Origin":       "https://bandcamp.com",
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
    with opener.open(req, timeout=20) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        return json.loads(data.decode())

def bandcamp_discover(tags=None, genre_id=None, sort="pop",
                      format_type="all", page=1):
    """
    Discover releases by tag or genre.

    tags:       list of tag slugs, e.g. ['ambient'], ['jazz', 'vinyl']
                Pass [] to browse by genre_id only.
    genre_id:   int from discover page genres (10=electronic, 23=rock, 18=metal,
                2=alternative, 14=hip-hop-rap, 11=experimental, 20=punk,
                12=folk, 19=pop, 3=ambient). Use 0 for all.
    sort:       'pop' (popular), 'new' (newest), 'top' (top sellers)
    format_type: 'all', 'digital', 'vinyl', 'cd', 'cassette'
    page:       1-based page number (20 items per page)
    """
    filters = {
        "format":   format_type,
        "location": 0,
        "sort":     sort,
        "tags":     tags or [],
    }
    if genre_id is not None:
        filters["genre_id"] = genre_id

    result = _post_json(
        "https://bandcamp.com/api/hub/2/dig_deeper",
        {"filters": filters, "page": page}
    )
    if "error" in result:
        raise ValueError(result.get("error_message", result))

    items = []
    for item in result.get("items", []):
        items.append({
            "title":         item.get("title"),
            "artist":        item.get("artist"),
            "band_name":     item.get("band_name"),
            "band_url":      item.get("band_url"),
            "album_url":     item.get("tralbum_url"),
            "genre":         item.get("genre"),
            "art_id":        item.get("art_id"),
            "cover_url":     f"https://f4.bcbits.com/img/a{item['art_id']}_10.jpg"
                             if item.get("art_id") else None,
            "item_type":     "album" if item.get("tralbum_type") == "a" else "track",
            "tralbum_id":    item.get("tralbum_id"),
            "is_preorder":   item.get("is_preorder"),
            # Preview audio URL for featured track (valid ~24h)
            "preview_mp3":   (item.get("audio_url") or {}).get("mp3-128"),
            "featured_track": item.get("featured_track_title"),
            # Packages price (first physical package if any)
            "packages":      item.get("packages", []),
        })

    return {
        "items":          items,
        "more_available": result.get("more_available", False),
        "page":           page,
        "spec":           result.get("discover_spec", {}),
    }


# --- Examples ---

# Browse ambient tag, sorted by popularity
ambient = bandcamp_discover(tags=["ambient"], sort="pop")
# ambient["items"][0]:
# {
#   "title":    "GEO - C06; 夢裡花開 (The Flower Blooms in a Dream)",
#   "artist":   "虛擬夢想廣場",
#   "band_name": "Geometric Lullaby",
#   "band_url":  "https://geometriclullaby.bandcamp.com",
#   "album_url": "https://geometriclullaby.bandcamp.com/album/geo-c06-...",
#   "genre":     "electronic",
#   "cover_url": "https://f4.bcbits.com/img/a4150883668_10.jpg",
#   "item_type": "album",
#   "preview_mp3": "https://t4.bcbits.com/stream/...",
# }
# ambient["more_available"] == True

# Browse newest jazz vinyl
jazz_vinyl = bandcamp_discover(tags=["jazz"], format_type="vinyl", sort="new")

# Browse by genre ID (all electronic, all formats)
electronic = bandcamp_discover(genre_id=10, sort="top", page=2)

# Paginate all pages
def discover_all_pages(tags, sort="pop", max_pages=5):
    for page in range(1, max_pages + 1):
        result = bandcamp_discover(tags=tags, sort=sort, page=page)
        yield from result["items"]
        if not result["more_available"]:
            break
```

---

## Approach 4: Text Search

`https://bandcamp.com/search?q=<query>&item_type=<type>&page=<n>`

Returns HTML with structured result items. 18–20 results per page. No JS required.

```python
import re
from html import unescape as hu

def bandcamp_search(query, item_type="a", page=1):
    """
    Search Bandcamp.
    item_type: 'a' = albums, 't' = tracks, 'b' = bands/artists
    Returns list of result dicts.
    """
    url = f"https://bandcamp.com/search?q={query.replace(' ', '+')}&item_type={item_type}&page={page}"
    html = _get(url)

    results = []
    for li in re.finditer(
        r'<li[^>]+class="searchresult[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL
    ):
        item = li.group(1)

        # URL: strip tracking params
        url_m = re.search(r'class="artcont"[^>]*href="([^"?]+)', item)
        img_m = re.search(r'<img src="([^"]+)"', item)
        title_m = re.search(r'class="heading".*?<a[^>]*>([^<]+)', item, re.DOTALL)
        sub_m = re.search(r'class="subhead"[^>]*>(.*?)</div>', item, re.DOTALL)
        released_m = re.search(r'class="released"[^>]*>([^<]+)', item)
        length_m = re.search(r'class="length"[^>]*>([^<]+)', item)
        # Tags are in the text content of .tags div
        tags_m = re.search(r'class="tags[^"]*"[^>]*>(.*?)</div>', item, re.DOTALL)
        tags = re.findall(r"[\w][\w\s\-\']+", re.sub(r"tags:", "", tags_m.group(1))) \
               if tags_m else []

        results.append({
            "url":      url_m.group(1) if url_m else None,
            "thumb":    img_m.group(1) if img_m else None,
            "title":    title_m.group(1).strip() if title_m else None,
            "subhead":  re.sub(r"<[^>]+>", "", sub_m.group(1)).strip() if sub_m else None,
            "released": released_m.group(1).strip() if released_m else None,
            "length":   length_m.group(1).strip() if length_m else None,
            "tags":     [t.strip() for t in tags if t.strip()],
        })
    return results


# --- Examples ---

# Album search
albums = bandcamp_search("ambient soundscapes", item_type="a")
# [
#   {"url": "https://..../album/...", "title": "...", "subhead": "by Artist Name",
#    "released": "released March 4, 2023", "length": "12 tracks, 47 minutes",
#    "tags": ["ambient", "drone", "England"]},
#   ...
# ]

# Track search
tracks = bandcamp_search("lo-fi jazz", item_type="t", page=2)

# Artist/band search
bands = bandcamp_search("mogwai", item_type="b")
# bands[0]["url"] → https://mogwaiband.bandcamp.com  (no tracking params)
```

---

## Artwork URL Reference

```
Base CDN: https://f4.bcbits.com/img/

Album/track cover (from art_id in data-tralbum):
  https://f4.bcbits.com/img/a{art_id}_{size}.jpg
  sizes: _0 (~800px), _2 (original/full), _10 (700px), _16 (700px), _23 (300px)

Band/artist photo (from og:image or data-band):
  https://f4.bcbits.com/img/0{padded_id}_{size}.jpg
  (padded_id = image_id zero-padded to 10 digits)
  Same size suffixes apply.

Search result thumbnails:
  https://f4.bcbits.com/img/a{art_id}_7.jpg  (_7 = small square, ~150px)
```

```python
def bandcamp_cover(art_id, size=10):
    """Get album cover URL. size: 0=~800px, 2=original, 10=700px, 16=700px, 23=300px"""
    return f"https://f4.bcbits.com/img/a{art_id}_{size}.jpg"
```

---

## Streaming Audio URLs

Preview stream URLs embedded in `data-tralbum` are real `audio/mpeg` files, accessible without auth.

- Format: `mp3-128` (128kbps MP3)
- TTL: **~24 hours** — the `ts` URL param is a Unix expiry timestamp
- Not all tracks are streamable — check `track["streaming"] == 1` and `track["stream_mp3"] is not None`
- For a 12-track album, typically 4–6 tracks have preview streams; the rest are preview-blocked

```python
# Verify a stream URL is still valid before use
import time, urllib.parse

def stream_expires_in(stream_url):
    """Returns seconds until the stream token expires (negative = already expired)."""
    qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(stream_url).query))
    ts = int(qs.get("ts", 0))
    return ts - int(time.time())
```

---

## Gotchas

**Artist home page redirects to signup** — `https://mogwaiband.bandcamp.com/` may serve a login/signup page (HTML title: "Signup | Bandcamp") instead of the artist page. This happens when Bandcamp geo-redirects or detects bot-like requests. Workarounds:
- Fetch `/{artist}.bandcamp.com/music` directly instead of the root URL.
- Add `Accept-Language: en-US,en;q=0.9` header.
- If the redirect persists, use the browser via `goto()` instead of `http_get`.

**data-tralbum is on album/track pages only** — the artist home page (`/music`) does NOT have a full `data-tralbum`; it only has `{"url": "..."}`. Fetch individual album URLs from `discography` items to get track data.

**Album URL 404** — Bandcamp subdomain URLs like `https://mogwaiband.bandcamp.com/album/as-the-love-continues` can return 404 if the album was removed or the slug changed. Use links scraped from `/music` or search results.

**Not all tracks are streamable** — `track["duration"] == 0.0` and `track["stream_mp3"] is None` means Bandcamp has blocked streaming for that track (artist/label choice). This is normal; only some tracks per album have preview streams.

**Stream URLs expire in ~24h** — The `ts` URL parameter is a Unix timestamp. URLs fetched from a page are valid for ~24 hours. Re-fetch the album page to get fresh tokens.

**dig_deeper requires `page` key** — Omitting `page` returns `{"error": "missing key page"}`. The `cursor` parameter (seen in some docs) is not accepted; only integer `page` works.

**dig_deeper `sort` key required** — Using `sort_agg` instead of `sort` returns an error. The correct filter key is `sort` with values `'pop'`, `'new'`, or `'top'`.

**Prices in packages are in artist's local currency** — `band["currency"]` tells you the currency. The `packages[].price` float is in that currency, not always USD.

**`data-tralbum` art_id vs artist image_id** — Album cover uses `a{art_id}` prefix. Band logo/photo uses zero-padded 10-digit `image_id` without the `a` prefix. Don't mix them.

**Search tags are plaintext, not JSON** — Tags in search results are in the text of the `.tags` div, not a structured attribute. Parse with regex from the div content.

**Search returns 18–20 results max per page** — There is no `total_results` count. Paginate by incrementing `page` until you get fewer results than expected.

**No official public API** — All approaches here use undocumented internal endpoints. The dig_deeper endpoint and page data attributes have been stable for years but can change without notice.
