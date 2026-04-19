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

Save every header verbatim and reuse on replay.

## Keeping tokens fresh

Bearer tokens last ~1h. Beyond that you get `HTTP 401` on every call until you refresh. Two paths, pick based on whether the browser stays open:

### Fast path: piggyback on the Web Player's own refresh (~2ms reads)

Install a one-shot `fetch` interceptor that caches every outgoing pathfinder/spclient call's headers. The Web Player makes these requests constantly (library navigation, metadata, connect-state heartbeats), so the cache stays <60s stale without any effort. Skip the re-intercept dance entirely.

```python
INTERCEPTOR = r"""
(() => {
  if (window.__authCache) return;
  window.__authCache = null;
  const origFetch = window.fetch;
  window.fetch = async function(input, init) {
    const url = typeof input === 'string' ? input : input.url;
    if (/pathfinder|spclient\.wg|connect-state/.test(url) && init?.headers) {
      const h = init.headers instanceof Headers ? Object.fromEntries(init.headers) : {...init.headers};
      if (h.authorization || h.Authorization) {
        window.__authCache = {captured_at: Date.now(), headers: h};
      }
    }
    return origFetch.apply(this, arguments);
  };
})();
"""

# Install once per harness session — survives navigations
cdp("Page.enable")
cdp("Page.addScriptToEvaluateOnNewDocument", source=INTERCEPTOR)
js(INTERCEPTOR)   # also inject into current page

# Every subsequent read is ~2ms and always fresh
def get_headers():
    c = json.loads(js("JSON.stringify(window.__authCache)") or "null")
    if not c:                       # cold start — wait for Web Player's first call
        time.sleep(2)
        c = json.loads(js("JSON.stringify(window.__authCache)") or "null")
    return {k: v for k, v in c["headers"].items()
            if k.lower() not in ("host", "content-length")}
```

**Measured:** full "read cache + call `/presence-view/v1/buddylist`" cycle is ~400ms, dominated by network. The token read itself is <2ms. Compared to the subprocess-based path (below), this is ~30× faster and eliminates 401 handling entirely as long as the browser tab is alive.

### Fallback: subprocess-based re-intercept

Use when the browser isn't attached (cron jobs, CI) or the interceptor cache is somehow dead. Slower (~10-15s per refresh) because it spawns a fresh `browser-harness` subprocess that navigates, forces a request, and drains CDP events.

```python
REINTERCEPT = r"""
import time, json
cdp("Network.enable")
cdp("Network.setCacheDisabled", cacheDisabled=True)
js("window.location.href = 'https://open.spotify.com/collection/tracks'")
time.sleep(3)
js('''(() => {
  const sc = [...document.querySelectorAll('*')].filter(e => {
    const s = getComputedStyle(e);
    return s.overflowY === 'auto' && e.scrollHeight > e.clientHeight + 100;
  }).sort((a,b) => b.scrollHeight - a.scrollHeight)[0];
  if (sc) sc.scrollTop += 20000;
})()''')
time.sleep(3)
for e in drain_events():
    if e.get("method") == "Network.requestWillBeSent":
        req = e["params"]["request"]
        if "pathfinder" in req["url"] and "fetchLibraryTracks" in (req.get("postData") or ""):
            json.dump(req["headers"], open("/tmp/pf_headers.json", "w"))
            print("ok")
            break
else:
    print("MISS")
"""

def reintercept():
    r = subprocess.run(["browser-harness"], input=REINTERCEPT,
                        capture_output=True, text=True, timeout=45)
    return "ok" in r.stdout

def call_with_retry(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except urllib.error.HTTPError as e:
        if e.code != 401: raise
        if not reintercept(): raise
        return fn(*args, **kwargs)   # retry once
```

### Choosing between them

| Scenario                                        | Use                |
|-------------------------------------------------|--------------------|
| Browser attached, interactive or long-running   | Fast path          |
| Unattended cron job, Chrome closes between runs | Fallback only      |
| CI / server deploy without ever touching a GUI  | Neither — you need full TOTP refresh (below) |

### Downsides of the fast path (know before you ship it)

- **Dies with the tab.** Closing Chrome kills `window.__authCache`. Fallback is required for scripts that survive browser quits.
- **Doesn't refresh on idle tabs off `open.spotify.com`.** The Web Player has to keep issuing requests for the cache to stay fresh. Browse to `google.com` and the cache ages out.
- **Monkey-patches `window.fetch`.** No current detection, but not tamper-proof if Spotify ever adds feature-checks.
- **Cache-empty cold start.** First read after a page load can be null for ~2s until the Web Player's first natural request lands. The `get_headers()` helper above sleeps once to cover this.

### Full token refresh without a browser

Out of scope for this doc — included here for honesty about the gap. The Web Player refreshes its own tokens by POSTing to `https://open.spotify.com/api/token` with a **TOTP-signed** payload derived from a secret embedded in the main JS bundle. Replicating it is a separate RE task: extract the TOTP secret, implement the signing, match the exact request shape. Until that's done, every long-running tool needs either a live browser (fast path) or a one-shot human re-auth (fallback).

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

## Playlist mutations

Creating playlists uses a REST endpoint; adding/removing/moving tracks uses pathfinder. All share the same auth pair.

### Create a playlist

```python
def create_playlist(name):
    url = "https://spclient.wg.spotify.com/playlist/v2/playlist"
    body = json.dumps({
        "ops": [{"kind": "UPDATE_LIST_ATTRIBUTES",
                 "updateListAttributes": {"newAttributes": {"values": {"name": name}}}}]
    }).encode()
    req = urllib.request.Request(url, data=body, headers=send_headers, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())   # {"uri": "spotify:playlist:<id>", "revision": "..."}
```

New playlists don't automatically appear in the user's sidebar. To show it, add it to the rootlist:

```python
def add_to_rootlist(username, playlist_uri):
    url = f"https://spclient.wg.spotify.com/playlist/v2/user/{username}/rootlist/changes"
    body = json.dumps({"deltas": [{
        "ops": [{"kind": "ADD", "add": {
            "items": [{"uri": playlist_uri, "attributes": {"timestamp": str(int(time.time()*1000))}}],
            "addFirst": True}}],
        "info": {"source": {"client": "WEBPLAYER"}},
    }]}).encode()
    urllib.request.urlopen(urllib.request.Request(url, data=body, headers=send_headers, method="POST"))
```

The `username` is available from any captured user-scoped endpoint (e.g. `/collection/v2/contains` bodies include `"username": "<id>"`).

### Add / remove / move tracks

Three pathfinder ops, all sharing one hash, differing by operation name:

```python
def add_tracks(playlist_uri, track_uris):
    # Cap batches at 25 — larger calls return 200 OK but silently add nothing.
    for i in range(0, len(track_uris), 25):
        pathfinder("addToPlaylist", {
            "playlistUri": playlist_uri,
            "playlistItemUris": track_uris[i:i+25],
            "newPosition": {"moveType": "BOTTOM_OF_PLAYLIST"},
        })

def remove_tracks(playlist_uri, uids):
    # `uids` are per-playlist-item identifiers from fetchPlaylistContents, NOT track URIs.
    pathfinder("removeFromPlaylist", {"playlistUri": playlist_uri, "uids": uids})

def move_tracks(playlist_uri, uids, new_position):
    pathfinder("moveItemsInPlaylist", {
        "playlistUri": playlist_uri, "uids": uids, "newPosition": new_position,
    })
```

**`uid` vs `uri`.** Playlist items have both: the `uri` is the track's global URI; the `uid` is a per-slot identifier unique to *this* playlist's instance of that track. `removeFromPlaylist` and `moveItemsInPlaylist` operate on `uid` (so you can have duplicates and delete one specific copy). Read them out of `fetchPlaylistContents`:

```python
r = pathfinder("fetchPlaylistContents", {
    "uri": playlist_uri, "offset": 0, "limit": 100,
    "includeEpisodeContentRatingsV2": False,
})
for item in r["data"]["playlistV2"]["content"]["items"]:
    uid = item["uid"]
    track = item["itemV2"]["data"]
    # {uri, name, artists, ...}
```

### Trap: silent 25-track cap on `addToPlaylist`

Calling `addToPlaylist` with >25 URIs in `playlistItemUris` returns `200` with `{"data": {"addItemsToPlaylist": {"__typename": "AddItemsToPlaylistPayload"}}}` — looks successful, adds nothing. Always batch to 25 max. The response is the same whether zero or all tracks landed; verify with `fetchPlaylistContents.totalCount` if it matters.

### Using error-driven probing to find variable shapes

`addToPlaylist`'s error messages directly name the variables you're missing (`VALIDATION_INVALID_TYPE_VARIABLE` → `$playlistItemUris: [String!]!` → `$newPosition: PlaylistItemPositionInput!`). See "Probing unknown operations" above — same technique works here.

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
| Add / remove / move playlist items  | `addToPlaylist` / `removeFromPlaylist` / `moveItemsInPlaylist` |
| Create playlist (REST)              | `POST spclient.wg.spotify.com/playlist/v2/playlist` |

## Gotchas

- **Persisted-query hashes rotate.** Use `load_pathfinder_hashes()`; re-run on `PersistedQueryNotFound`.
- **`client-token` is required.** Missing it is the #1 cause of 403. Curl/Python won't auto-add it.
- **Tokens expire ~1h.** Use the fetch-interceptor fast path above; fall back to subprocess re-intercept when the browser isn't attached.
- **`api.spotify.com/v1` is poisoned.** Even a valid Bearer hits `429` almost immediately there; use pathfinder/spclient/guc3 only.
- **Parallelism ceiling is ~10 workers.** Connections start dropping around 20+.
- **Never commit captured headers.** They carry user identity (Bearer + client-token). `/tmp` only.
