# Spotify — Web Player Internals (Pathfinder + REST)

The Web Player's private APIs. Replay its GraphQL (pathfinder) and REST calls with the session's own tokens — library extraction, search, lyrics, and playback control all become single HTTP calls instead of UI work.

Companion files: `playback.md` for UI automation, `scraping.md` for no-auth HTTP.

---

## Core pattern

Three endpoints cover everything in this file. They share the same Bearer+client-token auth pair.

| Purpose              | URL                                                                    |
|----------------------|------------------------------------------------------------------------|
| GraphQL (pathfinder) | `POST https://api-partner.spotify.com/pathfinder/v2/query`             |
| REST (spclient)      | `GET/POST https://spclient.wg.spotify.com/...`                         |
| Player commands      | `POST https://guc3-spclient.spotify.com/connect-state/v1/player/command/...` |

Do **not** use `api.spotify.com/v1` — it's IP-rate-limited and a single burst earns a ~22h ban. Stick to pathfinder/spclient/guc3 even when you have a valid token.

## Extracting both tokens

Pathfinder requires `Authorization: Bearer <user-token>` **and** `client-token: <client-token>`. Without `client-token` you get `403 Forbidden`. Intercept any pathfinder request to grab both:

```python
import time, json
from helpers import cdp, drain_events, js

cdp("Network.enable")
cdp("Network.setCacheDisabled", cacheDisabled=True)
js("window.location.href = 'https://open.spotify.com/collection/tracks'")
time.sleep(3)
js("""(() => {
  const sc = [...document.querySelectorAll('*')].filter(e => {
    const s = getComputedStyle(e);
    return s.overflowY === 'auto' && e.scrollHeight > e.clientHeight + 100;
  }).sort((a,b) => b.scrollHeight - a.scrollHeight)[0];
  if (sc) sc.scrollTop = 20000;
})()""")
time.sleep(3)

for e in drain_events():
    if e.get("method") == "Network.requestWillBeSent":
        req = e["params"]["request"]
        if "pathfinder" in req["url"] and "fetchLibraryTracks" in (req.get("postData") or ""):
            json.dump(req["headers"], open("/tmp/pf_headers.json", "w"))
            break
```

Save every header verbatim and reuse on replay. Tokens last ~1h — re-intercept on 401.

## Persisted-query hashes

Pathfinder uses persisted queries. The hash is `SHA256(query_text)` — public protocol info derived from the JS bundle, not user-specific. It rotates when Spotify ships a new bundle, so never hardcode it.

```python
import urllib.request, re, gzip
from helpers import http_get

def load_pathfinder_hashes():
    """Return {operationName: sha256Hash} for every op in the main Web Player bundle."""
    html = http_get("https://open.spotify.com/")
    bundles = re.findall(r'https://open\.spotifycdn\.com/cdn/build/web-player/[^"\'\s]+\.js', html)
    ops = {}
    for url in bundles:
        try:
            src = http_get(url, timeout=60)
        except Exception:
            continue
        for op, h in re.findall(r'\("(\w+)","(?:query|mutation|subscription)","([0-9a-f]{64})"', src):
            ops[op] = h
    return ops

OPS = load_pathfinder_hashes()   # ~100 ops from the main bundle
```

Cache the result; only re-run on `PersistedQueryNotFound`.

### Lazy-loaded route chunks hide more ops

The main bundle has ~100 ops. Route-specific ones (search, recent searches, some modal flows) live in lazy-loaded `xpui-routes-*.<hash>.js` chunks. `searchDesktop`, `browseAll`, and 11 search-type variants all live in `xpui-routes-search.<hash>.js`.

The chunk URLs baked into the main bundle's webpack manifest don't resolve via direct HTTPS. Trigger the route in the browser so its chunk loads, then read `performance`:

```python
js("window.location.href = 'https://open.spotify.com/search/anything'")
time.sleep(3)
chunk_js = js("""(async () => {
  const urls = [...new Set(performance.getEntriesByType('resource')
    .map(e => e.name)
    .filter(u => /xpui-routes-[^/]*\\.[a-f0-9]+\\.js$/.test(u)))];
  const out = {};
  for (const url of urls) {
    try { out[url] = await (await fetch(url)).text(); } catch(e) {}
  }
  return out;
})()""")
for src in chunk_js.values():
    for op, h in re.findall(r'\\("(\\w+)","(?:query|mutation|subscription)","([0-9a-f]{64})"', src):
        OPS[op] = h
```

## Shared `pathfinder()` helper

Every subsequent example uses this — load headers once, call ops by name.

```python
import json, urllib.request
headers = json.load(open("/tmp/pf_headers.json"))
headers = {k: v for k, v in headers.items() if k.lower() not in ("host", "content-length")}

def pathfinder(op, variables, version="v2"):
    body = json.dumps({
        "variables": variables,
        "operationName": op,
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": OPS[op]}},
    }).encode()
    req = urllib.request.Request(
        f"https://api-partner.spotify.com/pathfinder/{version}/query",
        data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())
```

## Library extraction

### Liked Songs — `fetchLibraryTracks` (paginated)

```python
from concurrent.futures import ThreadPoolExecutor

first = pathfinder("fetchLibraryTracks", {"offset": 0, "limit": 1})
total = first["data"]["me"]["library"]["tracks"]["totalCount"]

with ThreadPoolExecutor(max_workers=10) as ex:
    pages = list(ex.map(
        lambda o: pathfinder("fetchLibraryTracks", {"offset": o, "limit": 50}),
        range(0, total, 50)))

tracks = [
    {
        "uri":     it["track"]["_uri"],
        "name":    it["track"]["data"]["name"],
        "artists": [(a["uri"].split(":")[-1], a["profile"]["name"])
                    for a in it["track"]["data"]["artists"]["items"]],
        "addedAt": it["addedAt"]["isoString"],
    }
    for p in pages for it in p["data"]["me"]["library"]["tracks"]["items"]
]
# Seconds instead of minutes, regardless of library size.
```

Response shape:
```
data.me.library.tracks.totalCount   # int
data.me.library.tracks.items[]      # UserLibraryTrackResponse
  .addedAt.isoString
  .track._uri                       # "spotify:track:<id>"
  .track.data.{name, artists, albumOfTrack}
```

### Everything else — `libraryV3`

Saved albums, followed artists, playlists, folders — one op, swap `filters`:

```python
def lib_page(filters, order="Recents", offset=0, limit=50, text=""):
    return pathfinder("libraryV3", {
        "filters": filters, "order": order, "textFilter": text,
        "offset": offset, "limit": limit,
    })

albums    = lib_page(["Albums"])     # item.__typename = AlbumResponseWrapper
artists   = lib_page(["Artists"])    # ArtistResponseWrapper
playlists = lib_page(["Playlists"])  # PlaylistResponseWrapper
```

No `totalCount`; walk until the returned page is shorter than `limit`. Valid `order` values come back in the response itself under `availableSortOrders` — typically `"Recents"`, `"Recently Added"`, `"Alphabetical"`, `"Creator"`.

### Probing unknown operations

Invalid values come back as structured responses with `__typename: "Library*Error"` and a plain-text `message`. Probe, read the error, iterate — much faster than reading the minified bundle:

```python
r = pathfinder("libraryV3", {"filters": ["Albums"], "order": "RECENTLY_ADDED", "offset": 0, "limit": 5, "textFilter": ""})
# data.me.libraryV3 = {
#   "__typename": "LibraryInvalidSortOrderIdError",
#   "message": "RECENTLY_ADDED is not a valid sort order",
#   "invalidSortOrderId": "RECENTLY_ADDED"
# }
```

## Search — `searchDesktop`

Closes `scraping.md`'s "search is not accessible via http_get" gap. Lives in the lazy route chunk (extract hashes with the chunk trick above).

```python
def search(term, limit=10):
    r = pathfinder("searchDesktop", {
        "searchTerm": term, "offset": 0, "limit": limit, "numberOfTopResults": 5,
        "includeAudiobooks": False, "includeArtistHasConcertsField": False,
        "includePreReleases": False, "includeLocalConcertsField": False,
    })
    return r["data"]["searchV2"]

# Returns all sections in one call (~1s):
# { topResultsV2, tracksV2, albumsV2, artists, playlists,
#   podcasts, episodes, genres, users, chipOrder }
```

Type-specific variants in the same chunk, cheaper when you want one category: `searchTracks`, `searchAlbums`, `searchArtists`, `searchPlaylists`, `searchPodcasts`, `searchEpisodes`, `searchAudiobooks`, `searchGenres`, `searchUsers`.

`searchSuggestions` is autocomplete only — returns `SearchAutoCompleteEntity` strings plus a handful of typed hits. Not a full search.

## Lyrics — `color-lyrics` (REST)

Not pathfinder. Regular REST on `spclient.wg.spotify.com`, same auth pair.

```python
def get_lyrics(track_id):
    url = f"https://spclient.wg.spotify.com/color-lyrics/v2/track/{track_id}?format=json&market=from_token"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None      # no lyrics for this track
        raise
```

Response: `{lyrics: {syncType, lines: [{startTimeMs, words, syllables, endTimeMs, transliteratedWords}]}, colors, hasVocalRemoval}`. `syncType` is `LINE_SYNCED`, `SYLLABLE_SYNCED` (word-level), or `UNSYNCED`. The `/image/<cover-art-url>` segment the Web Player uses is optional.

## Playback control — `connect-state`

```
POST https://guc3-spclient.spotify.com/connect-state/v1/player/command/from/<device-id>/to/<device-id>
```

`<device-id>` is a 40-char hex string from any live request URL (e.g. the `track-playback/v1/devices/<id>/state` puts you see while something is playing). Returns `HTTP 200` with `{"ack_id": "..."}`.

**Play a context** (track/album/playlist/collection). `skip_to.track_uri` optionally jumps to a specific track inside a playlist:
```json
{"command": {
  "context": {"uri": "spotify:track:4PTG3Z6ehGkBFwjybzWkR8", "url": "context://spotify:track:4PTG3Z6ehGkBFwjybzWkR8", "metadata": {}},
  "play_origin": {"feature_identifier": "harness"},
  "options": {"license": "tft", "skip_to": {}, "player_options_override": {}},
  "logging_params": {"command_id": "<uuid>"},
  "endpoint": "play"
}}
```

**Queue a track:**
```json
{"command": {
  "track": {"uri": "spotify:track:4PTG3Z6ehGkBFwjybzWkR8", "metadata": {"is_queued": "true"}, "provider": "queue"},
  "endpoint": "add_to_queue",
  "logging_params": {"command_id": "<uuid>"}
}}
```

## Operation reference

Everything not covered above follows the same `pathfinder(op, vars)` shape:

| Action                              | `operationName`            |
|-------------------------------------|----------------------------|
| Saved tracks (Liked Songs)          | `fetchLibraryTracks`       |
| Saved albums / artists / playlists  | `libraryV3`                |
| Full playlist contents              | `fetchPlaylist`            |
| Album page                          | `getAlbum` / `queryAlbumTracks` |
| Artist overview                     | `queryArtistOverview` / `queryArtistDiscographyAlbums` |
| Is-saved check, N URIs              | `areEntitiesInLibrary`     |
| Batch curation ("saved" heart state)| `isCurated`                |
| Search (all categories)             | `searchDesktop` (route chunk) |
| Autocomplete / recent searches      | `searchSuggestions`, `recentSearches` |

## Gotchas

- **Persisted-query hashes rotate.** Use `load_pathfinder_hashes()`; re-run on `PersistedQueryNotFound`.
- **`client-token` is required.** Missing it is the #1 cause of 403. Curl/Python won't auto-add it.
- **Tokens expire ~1h.** Re-intercept on 401.
- **`api.spotify.com/v1` is poisoned.** Even a valid Bearer hits `429` almost immediately there; use pathfinder/spclient/guc3 only.
- **Parallelism ceiling is ~10 workers.** Connections start dropping around 20+.
- **Never commit captured headers.** They carry user identity (Bearer + client-token). `/tmp` only.
