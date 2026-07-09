# Discogs — Scraping & Data Extraction

`https://api.discogs.com` — 17 M+ releases, artists, labels, and marketplace listings. **Never use the browser for Discogs.** All catalog data is reachable via `http_get` with a custom `User-Agent` header. No API key required for read-only catalog access; authenticated users get 60 req/min vs 25 req/min unauthenticated.

## Do this first

**Search → fetch by ID is the fastest pipeline — two calls, pure JSON, no HTML.**

```python
import json
from helpers import http_get

UA = {"User-Agent": "MyApp/1.0 +https://myapp.example"}

# Step 1: find artist
results = json.loads(http_get(
    "https://api.discogs.com/database/search?q=radiohead&type=artist&per_page=5",
    headers=UA
))
# results['pagination']['items'] = 299 total matches
artist = results['results'][0]
# artist: {'id': 3840, 'type': 'artist', 'title': 'Radiohead',
#           'resource_url': 'https://api.discogs.com/artists/3840',
#           'uri': '/artist/3840-Radiohead'}

# Step 2: fetch full artist record
artist_data = json.loads(http_get(artist['resource_url'], headers=UA))
print(artist_data['name'])          # 'Radiohead'
print(artist_data['profile'][:80])  # bio text (Discogs markup, see Gotchas)
print([m['name'] for m in artist_data['members']])
# ['Thom Yorke', 'Jonny Greenwood', 'Phil Selway', 'Colin Greenwood', "Ed O'Brien"]
# Confirmed output (2026-04-18)
```

## Common workflows

### Search the catalog

```python
import json
from helpers import http_get

UA = {"User-Agent": "MyApp/1.0 +https://myapp.example"}

data = json.loads(http_get(
    "https://api.discogs.com/database/search"
    "?q=ok+computer+radiohead"
    "&type=master"        # master | release | artist | label
    "&per_page=5"
    "&page=1",
    headers=UA
))
print("Total hits:", data['pagination']['items'])   # e.g. 47 (int, not str)
print("Pages:", data['pagination']['pages'])        # e.g. 10

for r in data['results']:
    print(r['id'], r['title'], r.get('year'), r.get('country'))
    # master_id and master_url present for release/master results
    # resource_url points to the canonical API object
# Confirmed output (2026-04-18):
# 21491  Radiohead - OK Computer  1997  Worldwide
```

#### Search filter parameters

| Parameter | Values | Notes |
|---|---|---|
| `q` | query string | Searches title, artist, label, catno, barcode |
| `type` | `release`, `master`, `artist`, `label` | Omit to search all types |
| `genre` | `Rock`, `Electronic`, `Jazz`, etc. | Single value |
| `style` | `Alternative Rock`, `IDM`, etc. | Single value |
| `country` | `UK`, `US`, `Germany`, etc. | Release country |
| `year` | `1997` | 4-digit year string |
| `format` | `Vinyl`, `CD`, `Cassette`, etc. | Physical format |
| `sort` | `year`, `title`, `format`, `country` | Default: relevance |
| `sort_order` | `asc`, `desc` | |
| `per_page` | 1–100 | Default 50 |
| `page` | integer | 1-indexed |

### Artist detail

```python
import json
from helpers import http_get

UA = {"User-Agent": "MyApp/1.0 +https://myapp.example"}

artist = json.loads(http_get("https://api.discogs.com/artists/3840", headers=UA))

# Key fields:
artist['id']             # 3840
artist['name']           # 'Radiohead'
artist['profile']        # bio text with Discogs markup (strip [a=], [r=], [url=...] tags)
artist['urls']           # list of external URLs (website, Wikipedia, social)
artist['namevariations'] # ['Radio Head', 'Radioheads', 'レディオヘッド', ...]
artist['aliases']        # [{'id': 840842, 'name': 'On A Friday', 'resource_url': ...}, ...]
artist['members']        # [{'id': 4854, 'name': 'Thom Yorke', 'active': True}, ...]
artist['releases_url']   # 'https://api.discogs.com/artists/3840/releases'
artist['images']         # list of {'type': 'primary'|'secondary', 'uri': ..., 'uri150': ..., 'width': ..., 'height': ...}
artist['data_quality']   # 'Needs Vote' | 'Correct' | 'Complete and Correct' etc.
```

### Artist releases (paginated)

```python
import json
from helpers import http_get

UA = {"User-Agent": "MyApp/1.0 +https://myapp.example"}

page = json.loads(http_get(
    "https://api.discogs.com/artists/3840/releases?per_page=50&page=1",
    headers=UA
))
print(page['pagination']['items'])   # 3207 total releases for Radiohead
print(page['pagination']['pages'])   # 65 pages at per_page=50

for rel in page['releases']:
    print(rel['id'], rel['year'], rel['type'], rel['role'], rel['title'])
    # type: 'release' | 'master'
    # role: 'Main' | 'Appearance' | 'TrackAppearance' | 'UnofficialRelease'
    # resource_url: direct link to fetch full release/master record
# Confirmed: id=12888486, year=1992, type='release', role='Main', title='Radiohead'
```

### Release detail

```python
import json
from helpers import http_get

UA = {"User-Agent": "MyApp/1.0 +https://myapp.example"}

rel = json.loads(http_get("https://api.discogs.com/releases/4950798", headers=UA))

# Core metadata
rel['id']                  # 4950798
rel['title']               # 'OK Computer'
rel['year']                # 1997
rel['country']             # 'Worldwide'
rel['released']            # '1997-06-16' (ISO date, may have -00 for missing day)
rel['released_formatted']  # 'Jun 1997'
rel['genres']              # ['Electronic', 'Rock']
rel['styles']              # ['Alternative Rock']
rel['notes']               # freeform text notes about the pressing
rel['master_id']           # 21491  — links to canonical master
rel['master_url']          # 'https://api.discogs.com/masters/21491'

# Labels, formats, artists
rel['labels']    # [{'name': 'Parlophone', 'catno': '7243 8 55229 1 8', 'id': 2294, ...}]
rel['formats']   # [{'name': 'Vinyl', 'qty': '2', 'descriptions': ['LP', 'Album'], 'text': 'Gatefold'}]
rel['artists']   # [{'name': 'Radiohead', 'id': 3840, 'anv': '', 'join': '', 'role': '', ...}]

# Tracklist — filter out headings (type_ == 'heading'), keep tracks
tracks = [t for t in rel['tracklist'] if t['type_'] == 'track']
for t in tracks:
    print(t['position'], t['title'], t['duration'])
    # 'A1'  'Airbag'  '' (duration empty when not catalogued)
    # type_ 'heading' entries are side/disc dividers, not tracks

# Market data
rel['num_for_sale']    # 35
rel['lowest_price']    # 170.0  (USD)
rel['community']['have']              # 261292
rel['community']['want']              # 212743
rel['community']['rating']['average'] # 4.7
rel['community']['rating']['count']   # 1205

# Identifiers (barcodes, matrix, label codes)
for ident in rel['identifiers']:
    print(ident['type'], ident['value'])
    # 'Barcode'  '724385522918'
    # 'Matrix / Runout'  'NODATA 01ↆ2A-1-1-...'
    # 'Label Code'  'lc 0299'
# Confirmed output (2026-04-18)
```

### Master release

A **master** is the canonical grouping of all pressings/editions of an album. Use it to get metadata once, then enumerate versions.

```python
import json
from helpers import http_get

UA = {"User-Agent": "MyApp/1.0 +https://myapp.example"}

master = json.loads(http_get("https://api.discogs.com/masters/21491", headers=UA))

master['id']                   # 21491
master['title']                # 'OK Computer'
master['year']                 # 1997
master['genres']               # ['Electronic', 'Rock']
master['styles']               # ['Alternative Rock']
master['artists']              # same structure as release artists list
master['main_release']         # 4950798  — canonical "best" pressing ID
master['main_release_url']     # direct URL to fetch it
master['most_recent_release']  # 36339292 — latest pressing
master['versions_url']         # 'https://api.discogs.com/masters/21491/versions'
master['num_for_sale']         # 1625
master['lowest_price']         # 0.58

# Enumerate all pressings of an album
versions = json.loads(http_get(
    "https://api.discogs.com/masters/21491/versions?per_page=50&page=1",
    headers=UA
))
print(versions['pagination']['items'])   # 245 pressings of OK Computer
for v in versions['versions']:
    print(v['id'], v['released'], v['country'], v['label'], v['catno'], v['major_formats'])
    # 15338048  '1997'  'Europe'  'Parlophone'  'CDNODATA 02'  ['CD']
```

### Label detail and releases

```python
import json
from helpers import http_get

UA = {"User-Agent": "MyApp/1.0 +https://myapp.example"}

label = json.loads(http_get("https://api.discogs.com/labels/2294", headers=UA))
label['id']            # 2294
label['name']          # 'Parlophone'
label['profile']       # label history text (Discogs markup)
label['urls']          # list of external links
label['parent_label']  # {'id': 563997, 'name': 'Parlophone Records Ltd.', ...}
label['sublabels']     # list of sub-imprints

# Label releases (paginated)
releases = json.loads(http_get(
    "https://api.discogs.com/labels/2294/releases?per_page=50&page=1",
    headers=UA
))
print(releases['pagination']['items'])   # 71695 releases on Parlophone
for r in releases['releases']:
    print(r['id'], r['year'], r['artist'], r['title'], r['catno'], r['format'])
```

### Pagination pattern

All list endpoints share the same pagination envelope:

```python
import json
from helpers import http_get

UA = {"User-Agent": "MyApp/1.0 +https://myapp.example"}

def paginate(base_url, per_page=100):
    """Yield every item across all pages."""
    page = 1
    while True:
        sep = '&' if '?' in base_url else '?'
        data = json.loads(http_get(
            f"{base_url}{sep}per_page={per_page}&page={page}",
            headers=UA
        ))
        pag = data['pagination']
        # Determine list key — one of: results, releases, versions
        items_key = next(k for k in data if k != 'pagination')
        yield from data[items_key]
        if page >= pag['pages']:
            break
        page += 1

# Example: all releases on Parlophone
for rel in paginate("https://api.discogs.com/labels/2294/releases"):
    print(rel['id'], rel['title'])
```

## URL and ID reference

### Endpoint map

```
https://api.discogs.com/database/search          # search catalog
https://api.discogs.com/artists/{id}             # artist detail
https://api.discogs.com/artists/{id}/releases    # artist's releases (paginated)
https://api.discogs.com/releases/{id}            # specific pressing detail
https://api.discogs.com/masters/{id}             # canonical album grouping
https://api.discogs.com/masters/{id}/versions    # all pressings of a master
https://api.discogs.com/labels/{id}              # label detail
https://api.discogs.com/labels/{id}/releases     # releases on a label (paginated)
```

### Discogs web URL construction

```python
artist_id  = 3840
release_id = 4950798
master_id  = 21491
label_id   = 2294

# These come from the API as 'uri' fields:
artist_url  = f"https://www.discogs.com/artist/{artist_id}-Radiohead"
release_url = f"https://www.discogs.com/release/{release_id}"
master_url  = f"https://www.discogs.com/master/{master_id}"
label_url   = f"https://www.discogs.com/label/{label_id}"
```

### Rate limit headers

```
x-discogs-ratelimit:           25   (requests per minute, unauthenticated)
x-discogs-ratelimit-remaining: 22   (remaining in current window)
x-discogs-ratelimit-used:       3   (used so far)
```

Authenticated with OAuth token: 60 req/min. Insert `time.sleep(1.1)` between sequential calls when hitting limits, or use `ThreadPoolExecutor` with 20-request bursts then check remaining.

## Gotchas

- **User-Agent is required — but any value works.** Requests without `User-Agent` still succeed but get the 25 req/min cap with no way to raise it. The Discogs policy asks for `AppName/Version +contactURL`. The `helpers.http_get` default (`Mozilla/5.0`) satisfies the header requirement; confirmed 25 req/min (2026-04-18).

- **Rate limit is 25 req/min unauthenticated, 60 req/min authenticated.** The limit resets on a rolling per-minute window, not on the :00 second boundary. Check `x-discogs-ratelimit-remaining` and sleep when it hits 0.

- **`pagination['items']` is an int, not a string.** Unlike PubMed's E-utilities, Discogs returns item counts as integers. No casting needed.

- **`per_page` max is 100.** Requests for more are silently capped at 100. For bulk collection use the paginator pattern above.

- **Tracklist contains headings, not just tracks.** Entries with `type_ == 'heading'` are side/disc/section dividers (e.g. `"Eeny"`, `"Side A"`). Always filter `type_ == 'track'` before processing. `duration` is frequently an empty string `""` when not catalogued.

- **Release `released` date uses `-00` for unknown day/month.** `"1997-06-00"` means June 1997, day unknown. `"1997-00-00"` means year only. Parse with `split('-')` and check for zeros rather than using `datetime.fromisoformat()`.

- **Profile/bio text uses Discogs markup, not HTML.** The `profile` field contains inline references like `[a=Talking Heads]` (artist link), `[r=767600]` (release link), `[l=EMI]` (label link), `[url=http://...]{text}[/url]` (hyperlink), and `[b]bold[/b]`. Strip with a regex or parse as structured text.

- **Artist `releases_url` returns all credit types, not just main artist.** Set `role` filter if needed — but the API does not expose a `role` query param on artist releases. Filter client-side: `[r for r in releases if r['role'] == 'Main']`.

- **Search requires authentication for some advanced filters.** The `q=` parameter works unauthenticated. Genre, style, country, and year filters work unauthenticated too (confirmed 2026-04-18). If a filtered search returns 0 results unexpectedly, try removing filters and narrowing via client-side post-processing.

- **`master_id` is `null` for releases that have no master.** Singles, promos, and DJ-only releases often lack a canonical master grouping. Guard: `if rel.get('master_id')`.

- **Image URLs require no auth but may return 401 in browser.** The `i.discogs.com` CDN tokens are pre-signed per request. Use the `uri150` (150×150 thumbnail) field for fast previews; `uri` for full size. Download with `http_get` using the same User-Agent header.

- **`anv` field on artist credits means "Artist Name Variation".** When a release credits an artist under a different name than their canonical name, `anv` contains the credited name. If `anv` is `""`, use `name` as the credited name.
