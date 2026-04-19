# Spotify — Web Player Playback

Field-tested against open.spotify.com on 2026-04-19. Requires the user to be logged in to the Web Player.

---

## Trap: coordinate clicks don't trigger playback

`click(x, y)` on a play button or a track row is the obvious move, but Spotify's React handlers **do not fire** on `Input.dispatchMouseEvent`. The row visibly highlights and the tooltip appears, but the player state does not change.

Drive playback through the DOM instead:

```python
js("""document.querySelector('button[aria-label="Play BKJB by Nation"]').click()""")
```

This is one of the cases in the SKILL.md "if compositor clicks are the wrong tool" bucket. Use coordinate clicks only for things that aren't reactive buttons (e.g. scrubber position on the progress bar).

## Stable selector: `aria-label="Play <Track> by <Artist>"`

Every in-page play button — top result, song rows, artist/album tiles — exposes the same aria-label shape:

- Song row:       `Play <Track> by <Artist>`
- Album/playlist: `Play <Album name>` / `Play <Playlist name>`
- Top Result:     aria-label is just `Play` — use `[data-testid="top-result-card"] button[aria-label="Play"]` to scope.

These survive React re-renders and are exact-match unique, so `querySelector` via aria-label is more reliable than DOM position.

## Search URL pattern

```
https://open.spotify.com/search/<url-encoded query>
```

Loads full search results SSR-free (client-side render). No need to click into the search box and type — navigate directly, then `wait_for_load()` + a short `wait(2)` for React to hydrate.

```python
from urllib.parse import quote
new_tab(f"https://open.spotify.com/search/{quote('bkjb nation')}")
wait_for_load(); wait(2)
js('document.querySelector(\'button[aria-label="Play BKJB by Nation"]\').click()')
```

## Player state selectors

Read current playback state without screenshots:

| What                 | Selector                                                 | Value        |
|----------------------|----------------------------------------------------------|--------------|
| Current track title  | `[data-testid="context-item-link"]`                      | `innerText`  |
| Current artist       | `[data-testid="context-item-info-artist"]`               | `innerText`  |
| Play/pause state     | `[data-testid="control-button-playpause"]`               | aria-label is `"Play"` (paused) or `"Pause"` (playing) |
| Now-playing widget   | `[data-testid="now-playing-widget"]`                     | presence check |
| Top result card      | `[data-testid="top-result-card"]`                        | scope container |

```python
state = js("""(() => ({
  title:   document.querySelector('[data-testid="context-item-link"]')?.innerText,
  artist:  document.querySelector('[data-testid="context-item-info-artist"]')?.innerText,
  state:   document.querySelector('[data-testid="control-button-playpause"]')?.getAttribute('aria-label'),
}))()""")
# {'title': 'BKJB', 'artist': 'Nation', 'state': 'Pause'}  # state='Pause' means currently playing
```

Invert the `state` field when reading — the button shows the *action available*, not the current state.

## Deep links that skip search entirely

If you already have a Spotify ID, prefer a direct URL over search → click:

```
https://open.spotify.com/track/<id>     # opens the track page, then click the big Play
https://open.spotify.com/album/<id>
https://open.spotify.com/playlist/<id>
```

On the track/album page the main play button is `button[data-testid="play-button"]` (also has aria-label `Play` / `Pause`).

Spotify IDs can be looked up via the oEmbed / embed approaches in `scraping.md` without needing a browser.

## Traps

- **Row-hover tooltip ≠ play triggered.** If a screenshot shows the "Play X by Y" tooltip appearing over a row, that only means the hover fired. Verify with the `control-button-playpause` aria-label, not the tooltip.
- **First track title may lag.** Immediately after clicking, `context-item-link` can still show the *previous* track for ~500ms. Sleep 1-2 seconds before reading, or poll until the title changes.
- **Coordinate click on the play-button area sometimes works on the top-result card but not on song rows.** Don't rely on it — use the DOM click path everywhere for consistency.
- **Autoplay policies.** If the tab has never had user interaction, Chrome may block audio autoplay. The UI will show "Pause" (meaning it thinks it's playing) but no audio comes out. A real `click()` (dispatched via the DOM) counts as a user gesture for this purpose; navigating with `new_tab` + DOM click has been reliable.

---

## Fast path: hijack the Web Player's internal GraphQL (pathfinder)

Scrolling a virtualized list to extract a user's library is slow (minutes for a multi-thousand-song library) and misses tracks due to virtualization gaps. The Web Player itself paginates via `api-partner.spotify.com/pathfinder/v2/query` — hijack its auth headers and replay the persisted query in parallel. Measured in seconds regardless of library size, with 100% coverage.

### Why not `api.spotify.com/v1`?

The classic Web API at `api.spotify.com/v1/*` is IP-rate-limited aggressively — even with a valid user Bearer token, expect `429 API rate limit exceeded` within a handful of calls (scraping.md documents `Retry-After` of 22 hours on anonymous tokens). Pathfinder has separate, much looser limits because the Web Player hammers it on every page load.

### Extracting both tokens

Pathfinder requires two headers that are easy to miss: `Authorization: Bearer <user-token>` **and** `client-token: <client-token>`. Without `client-token` you get `403 Forbidden`. Intercept any pathfinder request to grab both:

```python
import time, json
from helpers import cdp, drain_events, js

cdp("Network.enable")
cdp("Network.setCacheDisabled", cacheDisabled=True)
# Force a fresh pathfinder call — navigate to a virtualized page, then scroll
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

Save every header — `Authorization`, `client-token`, `app-platform`, `spotify-app-version`, `accept`, `content-type`, etc. — and reuse them verbatim on your replay requests. Both tokens last ~1 hour; re-intercept when you start getting 401s.

### Getting the persisted-query hash (don't hardcode it)

Persisted-query hashes rotate when Spotify ships a new bundle. Look them up at runtime from the public Web Player JS — no auth, no browser needed. Every operation the Web Player can make is registered as `new X.l("<opName>","query"|"mutation","<sha256>",null)` in the main bundle.

```python
import urllib.request, re, gzip
from helpers import http_get

def load_pathfinder_hashes():
    """Return {operationName: sha256Hash} for every pathfinder op the Web Player knows."""
    html = http_get("https://open.spotify.com/")
    bundles = re.findall(r'https://open\.spotifycdn\.com/cdn/build/web-player/[^"\'\s]+\.js', html)
    ops = {}
    for url in bundles:
        try:
            js = http_get(url, timeout=60)
        except Exception:
            continue
        for op, h in re.findall(r'\("(\w+)","(?:query|mutation|subscription)","([0-9a-f]{64})"', js):
            ops[op] = h
    return ops

OPS = load_pathfinder_hashes()
# {'fetchLibraryTracks': '087278b2...', 'fetchPlaylist': '32b05e92...',
#  'getAlbum': 'b9bfabef...', 'queryArtistOverview': '7f86ff63...',
#  'isCurated': 'e4ed1f91...', 'areEntitiesInLibrary': '13433799...',  ...}
# ~100 operations total; one HTTP round-trip per bundle (typically 3 bundles).
```

Cache the result — the hashes only change on bundle rollouts, so re-parsing on every call is wasteful. Invalidate when you see `PersistedQueryNotFound`.

### Replaying `fetchLibraryTracks` (Liked Songs in parallel)

```python
import json, urllib.request
from concurrent.futures import ThreadPoolExecutor

headers = json.load(open("/tmp/pf_headers.json"))
headers = {k: v for k, v in headers.items() if k.lower() not in ("host", "content-length")}

HASH = OPS["fetchLibraryTracks"]   # from load_pathfinder_hashes()

def fetch_page(offset, limit=50):
    body = json.dumps({
        "variables": {"offset": offset, "limit": limit},
        "operationName": "fetchLibraryTracks",
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": HASH}},
    }).encode()
    req = urllib.request.Request(
        "https://api-partner.spotify.com/pathfinder/v2/query",
        data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

# Hit the endpoint once to get totalCount, then fan out
first = fetch_page(0, 1)
total = first["data"]["me"]["library"]["tracks"]["totalCount"]
offsets = list(range(0, total, 50))

with ThreadPoolExecutor(max_workers=10) as ex:
    pages = list(ex.map(fetch_page, offsets))

tracks = []
for page in pages:
    for item in page["data"]["me"]["library"]["tracks"]["items"]:
        t = item["track"]["data"]
        tracks.append({
            "uri":     item["track"]["_uri"],
            "name":    t["name"],
            "artists": [(a["uri"].split(":")[-1], a["profile"]["name"])
                        for a in t["artists"]["items"]],
            "addedAt": item["addedAt"]["isoString"],
        })
# Order-of-magnitude: seconds instead of minutes, regardless of library size.
```

### Response shape (fetchLibraryTracks)

```
data.me.library.tracks.totalCount      # int
data.me.library.tracks.pagingInfo      # {limit, offset}
data.me.library.tracks.items[]         # UserLibraryTrackResponse
  .addedAt.isoString                   # when liked
  .track._uri                          # "spotify:track:<id>"
  .track.data.name                     # track title
  .track.data.artists.items[]          # list of {uri, profile.name}
  .track.data.albumOfTrack             # album metadata
```

### Non-track library: `libraryV3`

Tracks use `fetchLibraryTracks` (above). **Every other library type** — saved albums, followed artists, playlists, folders — goes through one unified op, `libraryV3`. Swap the `filters` variable to pivot between them.

```python
HASH = OPS["libraryV3"]

def lib_page(filters, order="Recents", offset=0, limit=50, text=""):
    body = json.dumps({
        "variables": {"filters": filters, "order": order, "textFilter": text, "offset": offset, "limit": limit},
        "operationName": "libraryV3",
        "extensions": {"persistedQuery": {"version": 1, "sha256Hash": HASH}},
    }).encode()
    req = urllib.request.Request("https://api-partner.spotify.com/pathfinder/v2/query",
                                  data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

albums    = lib_page(["Albums"])     # AlbumResponseWrapper
artists   = lib_page(["Artists"])    # ArtistResponseWrapper
playlists = lib_page(["Playlists"])  # PlaylistResponseWrapper
# No totalCount in the response — walk until the returned page is shorter than `limit`.
```

Valid `order` values come back in the response itself under `availableSortOrders`: `"Recents"`, `"Recently Added"`, `"Alphabetical"`, `"Creator"`.

Response shape:
```
data.me.libraryV3.__typename = "LibraryPage"
data.me.libraryV3.availableSortOrders[]  # [{id, name}] — self-documenting
data.me.libraryV3.items[]                # one per saved item
  .addedAt.isoString
  .item.__typename                       # AlbumResponseWrapper | ArtistResponseWrapper | PlaylistResponseWrapper
  .item._uri                             # "spotify:album:..." etc.
  .item.data                             # typed payload (Album|Artist|Playlist)
```

### Probing an unknown operation

When you don't know what variables an op takes, pathfinder hands you the answer for free: invalid values come back as structured GraphQL responses with `__typename: "Library*Error"` (or similar) and a plain-text `message`. Probe, read the error, iterate.

```python
r = lib_page(["Albums"], order="RECENTLY_ADDED")
# -> data.me.libraryV3 = {
#      "__typename": "LibraryInvalidSortOrderIdError",
#      "message": "RECENTLY_ADDED is not a valid sort order",
#      "invalidSortOrderId": "RECENTLY_ADDED"
#    }
```

Much faster than reading the minified bundle. Works for any pathfinder op that returns union types.

### Other pathfinder operations worth knowing

Watch the Network tab while doing each action; each persisted-query hash comes out of `load_pathfinder_hashes()` — no need to scrape request bodies.

| Action                              | `operationName`            |
|-------------------------------------|----------------------------|
| Saved tracks (Liked Songs)          | `fetchLibraryTracks`       |
| Saved albums / followed artists / playlists | `libraryV3` (see above) |
| Full playlist contents              | `fetchPlaylist`            |
| Album page                          | `getAlbum` / `queryAlbumTracks` |
| Artist overview                     | `queryArtistOverview` / `queryArtistDiscographyAlbums` |
| Is-saved check, N URIs              | `areEntitiesInLibrary`     |
| Batch curation flags                | `isCurated` (for "saved" heart state) |

### Gotchas

- **Persisted-query hashes rotate.** Never hardcode them. Bundle rollouts invalidate cached hashes; use `load_pathfinder_hashes()` above and re-run it when you see `PersistedQueryNotFound`.
- **`client-token` is required.** 403 without it. Easy to miss because every browser tool auto-includes it; curl / Python do not.
- **Tokens expire ~1h.** Plan for re-interception, or run the extraction → API batch in one session.
- **Don't cross-use with `/v1`.** The same Bearer token is treated as rate-limit-poisoned on `api.spotify.com/v1` even if it works on pathfinder. Pick a lane.
- **Parallelism ceiling is ~10 workers.** Spotify starts dropping connections around 20+ concurrent. 10 is a good default for `ThreadPoolExecutor`.
- **Do not commit captured headers.** They contain user identity (Bearer + client-token). `/tmp` staging is fine; a repo file is not.
