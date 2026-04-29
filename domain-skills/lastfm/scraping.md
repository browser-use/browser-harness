# Last.fm — Scraping & Data Extraction

`https://ws.audioscrobbler.com/2.0/` — music metadata, scrobble history, user listening stats, charts, tags. **Never scrape the HTML site.** All data is available via the REST API as JSON. A free API key is required (register at https://www.last.fm/api/account/create — takes < 2 minutes). `api_key=test` returns HTTP 403; there is no keyless mode.

## Do this first

**Artist info + top tracks is the fastest lookup for most music tasks — two calls, pure JSON.**

```python
import json
from helpers import http_get

API_KEY = "YOUR_API_KEY"   # get free at last.fm/api/account/create
BASE    = "https://ws.audioscrobbler.com/2.0/"

# Artist info: listeners, playcount, bio, similar artists, tags
artist = json.loads(http_get(
    f"{BASE}?method=artist.getinfo&artist=Radiohead"
    f"&autocorrect=1&api_key={API_KEY}&format=json"
))['artist']
print(artist['name'])                              # 'Radiohead'
print(artist['stats']['listeners'])               # '8222008'
print(artist['stats']['playcount'])               # '1370054940'
print(artist['mbid'])                             # 'a74b1b7f-71a5-4011-9441-d0b5e4122711'
bio = artist['bio']['summary']                    # HTML snippet, ~300 chars
tags = [t['name'] for t in artist['tags']['tag']] # ['rock', 'alternative', ...]
similar = [a['name'] for a in artist['similar']['artist']]  # ['Thom Yorke', ...]
# Confirmed output (2026-04-18):
# Radiohead | listeners: 8222008 | playcount: 1370054940

# Top tracks for the artist
toptracks = json.loads(http_get(
    f"{BASE}?method=artist.gettoptracks&artist=Radiohead"
    f"&limit=10&page=1&api_key={API_KEY}&format=json"
))['toptracks']
attr = toptracks['@attr']   # {'artist':'Radiohead','page':'1','perPage':'10','totalPages':'...','total':'459094'}
for t in toptracks['track']:
    print(t['@attr']['rank'], t['name'], t['playcount'], t['listeners'])
# 1 Creep 59938570 4065525
# 2 No Surprises 54713807 3352961
# 3 Karma Police ...
```

## Common workflows

### Artist search

```python
import json
from helpers import http_get

data = json.loads(http_get(
    f"{BASE}?method=artist.search&artist=radiohead"
    f"&limit=5&page=1&api_key={API_KEY}&format=json"
))['results']
print("total results:", data['opensearch:totalResults'])  # '9055' — string, not int
print("page size:",     data['opensearch:itemsPerPage'])  # '30' default (override with limit=)
for a in data['artistmatches']['artist']:
    print(a['name'], '| listeners:', a['listeners'], '| mbid:', a['mbid'])
# Confirmed (2026-04-18):
# Radiohead | listeners: 8222008 | mbid: a74b1b7f-71a5-4011-9441-d0b5e4122711
```

### Album info + tracklist

```python
import json
from helpers import http_get

album = json.loads(http_get(
    f"{BASE}?method=album.getinfo&artist=Radiohead&album=OK+Computer"
    f"&api_key={API_KEY}&format=json"
))['album']
print(album['artist'], '-', album['name'])     # 'Radiohead - OK Computer'
print('playcount:', album['playcount'])        # '253180391'
print('mbid:', album['mbid'])                  # '0b6b4ba0-...'
tags = [t['name'] for t in album['tags']['tag']]
tracks = [(t['@attr']['rank'], t['name'], t['duration'])
          for t in album['tracks']['track']]
# duration is seconds as int (e.g. 314)
# Confirmed: 12 tracks returned for OK Computer
```

### Track info, tags, wiki

```python
import json
from helpers import http_get

track = json.loads(http_get(
    f"{BASE}?method=track.getinfo&artist=Radiohead&track=Creep"
    f"&autocorrect=1&api_key={API_KEY}&format=json"
))['track']
print(track['name'])                           # 'Creep'
print(track['duration'])                       # '235000' — milliseconds as string
print(track['listeners'])                      # '4065525'
print(track['playcount'])                      # '59938570'
print(track['album']['title'])                 # 'Pablo Honey'
tags = [t['name'] for t in track['toptags']['tag']]
wiki_summary = track['wiki']['summary']        # HTML with <a> link at end
wiki_full    = track['wiki']['content']
# Confirmed (2026-04-18): all fields present for major tracks
```

### Similar artists / similar tracks

```python
import json
from helpers import http_get

# Similar artists with match score (0-1)
similar = json.loads(http_get(
    f"{BASE}?method=artist.getsimilar&artist=Radiohead&limit=10"
    f"&api_key={API_KEY}&format=json"
))['similarartists']['artist']
for a in similar:
    print(a['name'], '| match:', a['match'])
# Thom Yorke | match: 1
# Atoms for Peace | match: 0.595170

# Similar tracks
similar_tracks = json.loads(http_get(
    f"{BASE}?method=track.getsimilar&artist=Radiohead&track=Creep&limit=5"
    f"&api_key={API_KEY}&format=json"
))['similartracks']['track']
for t in similar_tracks:
    print(t['name'], '-', t['artist']['name'], '| match:', t['match'])
# No Surprises - Radiohead | match: 1.0
# Where Is My Mind? - Pixies | match: 0.505988
```

### Tag exploration

```python
import json
from helpers import http_get

# Tag metadata
tag = json.loads(http_get(
    f"{BASE}?method=tag.getinfo&tag=indie&api_key={API_KEY}&format=json"
))['tag']
print(tag['name'])          # 'indie'
print(tag['reach'])         # '260522' — unique listeners who used this tag
print(tag['total'])         # '2065714' — total tag applications

# Top tracks for a tag
toptracks = json.loads(http_get(
    f"{BASE}?method=tag.gettoptracks&tag=indie&api_key={API_KEY}&format=json"
))['tracks']['track']
for t in toptracks[:3]:
    print(t['@attr']['rank'], t['name'], '-', t['artist']['name'])
# 1 Sweater Weather - The Neighbourhood

# Top artists for a tag
topartists = json.loads(http_get(
    f"{BASE}?method=tag.gettopartists&tag=indie&api_key={API_KEY}&format=json"
))['topartists']['artist']
```

### Global charts (no user required)

```python
import json
from helpers import http_get

# Weekly global top artists
artists = json.loads(http_get(
    f"{BASE}?method=chart.gettopartists&page=1&limit=10"
    f"&api_key={API_KEY}&format=json"
))['artists']
print(artists['@attr'])   # {'page':'1','perPage':'50','totalPages':'200','total':'10000'}
for a in artists['artist'][:3]:
    print(a['name'], a['playcount'], a['listeners'])

# Weekly global top tracks
tracks = json.loads(http_get(
    f"{BASE}?method=chart.gettoptracks&api_key={API_KEY}&format=json"
))['tracks']['track']
for t in tracks[:3]:
    print(t['name'], '-', t['artist']['name'])
# Confirmed (2026-04-18): Kanye West #1 artist; PinkPantheress #1 track
```

### Geographic charts

```python
import json
from helpers import http_get

# Top artists by country (ISO 3166-1 alpha-2 or full name both work)
topartists = json.loads(http_get(
    f"{BASE}?method=geo.gettopartists&country=spain"
    f"&api_key={API_KEY}&format=json"
))['topartists']['artist']
for a in topartists[:3]:
    print(a['name'], a['listeners'])
# Bad Bunny ... (confirmed 2026-04-18)

# Top tracks by country
toptracks = json.loads(http_get(
    f"{BASE}?method=geo.gettoptracks&country=germany"
    f"&api_key={API_KEY}&format=json"
))['toptracks']['track']
```

### User data (public profiles, no auth required)

```python
import json
from helpers import http_get

USERNAME = "rj"  # any public Last.fm username

# User profile
user = json.loads(http_get(
    f"{BASE}?method=user.getinfo&user={USERNAME}"
    f"&api_key={API_KEY}&format=json"
))['user']
print(user['name'])           # 'RJ'
print(user['playcount'])      # '150615'
print(user['artist_count'])   # '12753'
print(user['track_count'])    # '57122'
print(user['album_count'])    # '26671'
print(user['country'])        # 'United Kingdom'
registered = user['registered']['unixtime']  # unix timestamp as string

# Recent scrobbles — returns up to 200 per page
recent = json.loads(http_get(
    f"{BASE}?method=user.getrecenttracks&user={USERNAME}"
    f"&limit=10&api_key={API_KEY}&format=json"
))['recenttracks']
attr = recent['@attr']  # {'user':'RJ','totalPages':'75308','page':'1','perPage':'10','total':'150615'}
for t in recent['track']:
    name   = t['name']
    artist = t['artist']['#text']         # note: '#text' key, not 'name'
    album  = t['album']['#text']
    # If now playing, t has @attr={'nowplaying':'true'} and NO 'date' key
    if '@attr' in t and t['@attr'].get('nowplaying') == 'true':
        ts = None
    else:
        ts = t['date']['uts']             # unix timestamp string; '#text' has human date

# Time-range filter (unix timestamps)
ranged = json.loads(http_get(
    f"{BASE}?method=user.getrecenttracks&user={USERNAME}"
    f"&from=1704067200&to=1704153600"     # Jan 1-2 2024
    f"&limit=50&api_key={API_KEY}&format=json"
))['recenttracks']
# Confirmed: returns 15 tracks for rj in that window

# Top artists/tracks/albums with time period
for period in ['7day', '1month', '3month', '6month', '12month', 'overall']:
    top = json.loads(http_get(
        f"{BASE}?method=user.gettopartists&user={USERNAME}"
        f"&period={period}&limit=5&api_key={API_KEY}&format=json"
    ))['topartists']
    print(period, ':', top['@attr']['total'], 'unique artists')
# overall: 12753 | 7day: low numbers | etc.

# Loved tracks
loved = json.loads(http_get(
    f"{BASE}?method=user.getlovedtracks&user={USERNAME}"
    f"&limit=10&api_key={API_KEY}&format=json"
))['lovedtracks']['track']
for t in loved:
    print(t['name'], '-', t['artist']['name'], t['date']['#text'])

# Weekly artist chart (most recent week)
weekly = json.loads(http_get(
    f"{BASE}?method=user.getweeklyartistchart&user={USERNAME}"
    f"&api_key={API_KEY}&format=json"
))['weeklyartistchart']['artist']
for a in weekly[:5]:
    print(a['name'], a['playcount'])

# List available weekly chart windows (all-time)
charts = json.loads(http_get(
    f"{BASE}?method=user.getweeklychartlist&user={USERNAME}"
    f"&api_key={API_KEY}&format=json"
))['weeklychartlist']['chart']
# Each: {'from': '1108296000', 'to': '1108900800'} — unix timestamps
# Use from/to with user.getweeklyartistchart or user.getweeklytrackchart for historical data
```

### Pagination pattern (all list endpoints)

```python
import json
from helpers import http_get

# All paginated responses follow the same @attr pattern
page, per_page = 1, 50
while True:
    data = json.loads(http_get(
        f"{BASE}?method=artist.gettoptracks&artist=Radiohead"
        f"&limit={per_page}&page={page}&api_key={API_KEY}&format=json"
    ))['toptracks']
    attr = data['@attr']
    tracks = data['track']
    # Process tracks...
    for t in tracks:
        print(t['@attr']['rank'], t['name'])
    if int(attr['page']) >= int(attr['totalPages']):
        break
    page += 1
# Radiohead: 459094 total tracks, 91819 pages at 5/page
```

### Bulk parallel fetches

```python
import json
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

artists = ['Radiohead', 'Portishead', 'Massive Attack', 'Björk', 'PJ Harvey']

def fetch_artist(name):
    return json.loads(http_get(
        f"{BASE}?method=artist.getinfo&artist={name}"
        f"&autocorrect=1&api_key={API_KEY}&format=json"
    ))['artist']

with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_artist, artists))

for a in results:
    print(a['name'], a['stats']['listeners'])
```

## URL and parameter reference

### API base

```
https://ws.audioscrobbler.com/2.0/
```

Always append `&format=json` — default response is XML.

### Core methods

| Method | Required params | Returns |
|---|---|---|
| `artist.getinfo` | `artist` or `mbid` | bio, stats, similar, tags |
| `artist.gettoptracks` | `artist` | ranked tracks with playcount |
| `artist.gettopalbums` | `artist` | ranked albums with playcount |
| `artist.getsimilar` | `artist` | similar artists with match score |
| `artist.gettoptags` | `artist` | tags with count |
| `artist.search` | `artist` | fuzzy search results |
| `album.getinfo` | `artist` + `album` or `mbid` | tracklist, tags, playcount |
| `album.search` | `album` | fuzzy search results |
| `track.getinfo` | `artist` + `track` or `mbid` | duration, album, tags, wiki |
| `track.getsimilar` | `artist` + `track` | similar tracks with match score |
| `track.search` | `track` (+ optional `artist`) | fuzzy search results |
| `tag.getinfo` | `tag` | reach, total, wiki |
| `tag.gettoptracks` | `tag` | top tracks for tag |
| `tag.gettopartists` | `tag` | top artists for tag |
| `tag.gettopalbums` | `tag` | top albums for tag |
| `chart.gettopartists` | — | global weekly top artists |
| `chart.gettoptracks` | — | global weekly top tracks |
| `geo.gettopartists` | `country` | top artists by country |
| `geo.gettoptracks` | `country` | top tracks by country |
| `user.getinfo` | `user` | profile stats |
| `user.getrecenttracks` | `user` | scrobble history |
| `user.gettopartists` | `user`, `period` | listening stats |
| `user.gettoptracks` | `user`, `period` | listening stats |
| `user.gettopalbums` | `user`, `period` | listening stats |
| `user.getlovedtracks` | `user` | loved/hearted tracks |
| `user.getweeklyartistchart` | `user` | weekly scrobble breakdown |
| `user.getweeklychartlist` | `user` | available historical weeks |

### Common parameters

| Parameter | Effect |
|---|---|
| `api_key` | Required on every request |
| `format=json` | JSON response (default is XML) |
| `autocorrect=1` | Correct misspellings (`radiohed` → `Radiohead`) |
| `limit` | Results per page (default 30–50, max 1000) |
| `page` | Page number, 1-indexed |
| `period` | `7day`, `1month`, `3month`, `6month`, `12month`, `overall` — for user.get* methods |
| `from` / `to` | Unix timestamps — for `user.getrecenttracks` time filtering |
| `mbid` | MusicBrainz ID — alternative to `artist`/`track`/`album` name |

### MBID lookup (canonical identifier)

```python
# Artists, tracks, and albums all carry mbid in every response.
# Use mbid for unambiguous lookups (bypasses name matching/autocorrect):
data = json.loads(http_get(
    f"{BASE}?method=artist.getinfo"
    f"&mbid=a74b1b7f-71a5-4011-9441-d0b5e4122711"
    f"&api_key={API_KEY}&format=json"
))['artist']
# Confirmed: returns Radiohead (2026-04-18)
```

### URL construction

```python
artist_name  = "Radiohead"
track_name   = "Creep"
album_name   = "OK Computer"
username     = "rj"

artist_url = f"https://www.last.fm/music/{artist_name.replace(' ', '+')}"
track_url  = f"https://www.last.fm/music/{artist_name.replace(' ', '+')}/_/{track_name.replace(' ', '+')}"
album_url  = f"https://www.last.fm/music/{artist_name.replace(' ', '+')}/{album_name.replace(' ', '+')}"
user_url   = f"https://www.last.fm/user/{username}"
tag_url    = f"https://www.last.fm/tag/{tag_name.replace(' ', '+')}"
```

## Gotchas

- **API key is mandatory — no free tier without one.** `api_key=test` returns HTTP 403. Register at https://www.last.fm/api/account/create; the key is issued immediately at no cost.

- **All numeric fields are strings.** `listeners`, `playcount`, `total`, `totalPages`, `page`, `opensearch:totalResults` — all returned as strings. Cast with `int()` before arithmetic.

- **Track `duration` is milliseconds as a string.** `track['duration']` returns `'235000'`, not seconds. Divide by 1000 for seconds. Album tracklist `duration` is seconds as an int (inconsistent).

- **`recenttracks` artist field uses `#text` not `name`.** Every other endpoint uses `artist['name']`. In `user.getrecenttracks`, artist is `{'mbid': '...', '#text': 'Eagles'}` — use `t['artist']['#text']`.

- **Now-playing track has no `date` key.** If a user is scrobbling now, the first track in `recenttracks` has `@attr: {'nowplaying': 'true'}` and the `date` field is absent. Guard with `if '@attr' in t`.

- **Artist images are a generic placeholder.** Last.fm removed artist images in 2020 (rights issues). Every artist returns the same gray silhouette PNG: `2a96cbd8b46e442fc41c2b86b821562f.png`. Album art images ARE real and unique per album.

- **`opensearch:totalResults` is a string, not int.** Same pattern as all numeric fields — cast before use.

- **Default format is XML, not JSON.** Omitting `&format=json` returns an XML document wrapped in `<lfm status="ok">`. Always append `format=json`.

- **`autocorrect=1` silently corrects spelling.** The corrected name appears in the response `name` field. If you need to know whether a correction occurred, compare your input to `response['artist']['name']`.

- **Error responses use `error` (int) + `message` (string).** Always check for the `error` key:
  ```python
  data = json.loads(http_get(f"{BASE}?method=artist.getinfo&artist=XYZ&api_key={API_KEY}&format=json"))
  if 'error' in data:
      print(data['error'], data['message'])
      # 6 'The artist you supplied could not be found'
  ```
  Common error codes: 6 = not found, 10 = invalid API key, 8 = operation failed, 29 = rate limit.

- **Rate limits are lenient but unspecified.** 15 rapid sequential requests all return 200 in testing. The API TOS says 5 req/s; in practice burst is higher. For bulk work, stay under 5 req/s or use `ThreadPoolExecutor(max_workers=5)` which naturally paces to ~5 concurrent.

- **`user.getrecenttracks` paginates via `page=` + `from`/`to`.** Use `from`/`to` (unix timestamps) for time-range extraction. The `total` in `@attr` counts only scrobbles in the requested window, not all-time.

- **`mbid` may be empty string for some entities.** Many artists, tracks, and albums in the Last.fm database are not yet matched to MusicBrainz. Always check `if a['mbid']` before using it as an identifier.

- **`similar.artist` in `artist.getinfo` is limited to 5 entries.** Use `artist.getsimilar` with `limit=` for more; it supports up to 100 and includes the `match` score.

- **HTML scraping the website is unreliable.** `https://www.last.fm/music/Radiohead` returns a 502 or React-rendered SPA content that requires JS execution. The REST API covers all the same data. Never fall back to HTML scraping.
