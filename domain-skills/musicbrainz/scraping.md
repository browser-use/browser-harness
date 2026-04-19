# MusicBrainz — Data Extraction

`https://musicbrainz.org` — open music encyclopedia with a fully free JSON API.
No auth required for reads. No browser needed for any documented workflow.

Field-tested against musicbrainz.org on 2026-04-18.

---

## Do this first

**The MusicBrainz Web Service API (ws/2) returns clean JSON for all entity types — no browser needed.**

```python
from helpers import http_get
import json

# REQUIRED: every request must include this header or you get HTTP 403
UA = {"User-Agent": "browser-harness/1.0 (your@email.com)"}

data = json.loads(http_get("https://musicbrainz.org/ws/2/artist/?query=queen&fmt=json&limit=5", headers=UA))
for a in data['artists']:
    print(a['id'], a['name'], a.get('type'), a.get('country'), a['score'])
# 0383dadf-2a4e-4d10-a46a-e9e041da8eb3  Queen  Group  GB  100
# 79239441-bfd5-4981-a70c-55c3f15c1287  Madonna  Person  US  73
```

`User-Agent` is **mandatory** — omitting it returns HTTP 403 immediately. Format: `AppName/Version (contact@email.com)`.

---

## Entity types

| Entity | Endpoint | Key fields |
|---|---|---|
| `artist` | `/ws/2/artist/` | name, sort-name, type (Group/Person/Orchestra/Choir), country, life-span, tags, rating |
| `release-group` | `/ws/2/release-group/` | title, primary-type (Album/Single/EP/Other), first-release-date |
| `release` | `/ws/2/release/` | title, date, country, status (Official/Bootleg/Promotional), barcode, label-info, media |
| `recording` | `/ws/2/recording/` | title, length (milliseconds), artist-credit, releases |
| `label` | `/ws/2/label/` | name, type, country, area |
| `work` | `/ws/2/work/` | title, type (Song/Aria/Soundtrack/etc.), relations |

All entities share the same MBID (MusicBrainz ID) format: UUID v4, e.g. `0383dadf-2a4e-4d10-a46a-e9e041da8eb3`.

---

## Common workflows

### Artist search

```python
from helpers import http_get
import json

UA = {"User-Agent": "browser-harness/1.0 (your@email.com)"}

resp = json.loads(http_get(
    "https://musicbrainz.org/ws/2/artist/?query=queen&fmt=json&limit=5",
    headers=UA
))
# resp keys: count (total matches), offset, artists (list)
for a in resp['artists']:
    print(a['id'])           # MBID: 0383dadf-2a4e-4d10-a46a-e9e041da8eb3
    print(a['name'])         # Queen
    print(a['sort-name'])    # Queen  (differs for persons: "Bowie, David")
    print(a.get('type'))     # Group / Person / Orchestra / Choir
    print(a.get('country'))  # GB
    print(a.get('life-span'))# {'begin': '1970-06-27', 'end': None, 'ended': True}
    print(a.get('disambiguation', ''))  # e.g. "English singer-songwriter"
    print(a['score'])        # relevance 0-100
```

### Artist by MBID (with related data via `inc=`)

```python
# inc= parameters stack with + between them
resp = json.loads(http_get(
    "https://musicbrainz.org/ws/2/artist/0383dadf-2a4e-4d10-a46a-e9e041da8eb3"
    "?inc=releases+tags+ratings+release-groups&fmt=json",
    headers=UA
))
print(resp['name'])      # Queen
print(resp['type'])      # Group
print(resp['country'])   # GB
print(resp['life-span']) # {'begin': '1970-06-27', 'end': None, 'ended': True}

# Tags (community-voted genre labels, sorted by count)
tags = sorted(resp.get('tags', []), key=lambda x: x['count'], reverse=True)
print([t['name'] for t in tags[:5]])
# ['rock', 'glam rock', 'hard rock', 'art rock', 'british']

# Rating (community score, 0-5)
print(resp.get('rating'))  # {'votes-count': 43, 'value': 4.7}

# Direct releases (up to 25 per request — use browse for full list)
for r in resp.get('releases', []):
    print(r['id'], r['title'], r.get('date'))

# Release groups (albums, singles, EPs — deduplicated by edition)
for rg in resp.get('release-groups', []):
    print(rg['id'], rg['title'], rg.get('primary-type'), rg.get('first-release-date'))
# 6b47c9a0  A Night at the Opera  Album  1975-11-21
# 002ed683  Sheer Heart Attack    Album  1974-11-01
```

### Browse releases by artist (full list)

```python
# Browse API: uses 'artist' param (not 'query') — response key is 'release-count' not 'count'
resp = json.loads(http_get(
    "https://musicbrainz.org/ws/2/release/"
    "?artist=0383dadf-2a4e-4d10-a46a-e9e041da8eb3&fmt=json&limit=25&offset=0",
    headers=UA
))
print(resp['release-count'])   # 1635 — total releases for this artist
for r in resp['releases']:
    print(r['id'], r['title'], r.get('date'), r.get('country'), r.get('status'))
    # Also has: cover-art-archive.artwork (bool), cover-art-archive.front (bool)
    caa = r.get('cover-art-archive', {})
    print(caa.get('artwork'), caa.get('front'), caa.get('count'))

# Paginate: increment offset by limit
```

### Release search and lookup

```python
# Search by title
resp = json.loads(http_get(
    "https://musicbrainz.org/ws/2/release/?query=dark+side+of+the+moon&fmt=json&limit=5",
    headers=UA
))
# resp keys: count, offset, releases

# Full release with track list, artists, and labels
release = json.loads(http_get(
    "https://musicbrainz.org/ws/2/release/b84ee12a-09ef-421b-82de-0441a926375b"
    "?inc=artists+recordings+labels+release-groups&fmt=json",
    headers=UA
))
print(release['title'])   # The Dark Side of the Moon
print(release['date'])    # 1973-03-24
print(release['status'])  # Official
print(release['country']) # GB

# Release group (the "album concept", deduplicates editions)
rg = release.get('release-group', {})
print(rg['title'], rg.get('primary-type'), rg['id'])
# The Dark Side of the Moon  Album  f5093c06-23e3-404f-aeaa-40f72885ee3a

# Artist credit
for ac in release.get('artist-credit', []):
    if isinstance(ac, dict) and 'artist' in ac:
        print(ac['artist']['name'], ac['artist']['id'])
        # Pink Floyd  83d91898-7763-47d7-b03b-b92132375c47

# Labels
for li in release.get('label-info', []):
    label = li.get('label', {})
    print(label.get('name'), li.get('catalog-number'))
    # Harvest  SHVL 804

# Track list (from media[].tracks[])
for disc in release.get('media', []):
    for track in disc.get('tracks', []):
        dur_s = track['length'] // 1000 if track.get('length') else None
        rec = track.get('recording', {})
        print(track['number'], track['title'], dur_s, rec.get('id'))
        # A1  Speak to Me  68s  bef3fddb-5aca-49f5-b2fd-d56a23268d63
        # A2  Breathe      168s ecbc7c9b-e79d-4ec8-ac77-44e4a7f7f1b8
```

### Recording (track) search

```python
# Use Lucene field syntax to filter by artist
resp = json.loads(http_get(
    "https://musicbrainz.org/ws/2/recording/"
    "?query=bohemian+rhapsody+AND+artist:queen&fmt=json&limit=5",
    headers=UA
))
print(resp['count'])  # 419
for r in resp['recordings']:
    dur_s = r['length'] // 1000 if r.get('length') else None
    artists = [ac['artist']['name'] for ac in r.get('artist-credit', []) if isinstance(ac, dict)]
    releases = r.get('releases', [])
    print(r['id'], r['title'], dur_s, artists, releases[0]['title'] if releases else None)
# a4803b45  Bohemian Rhapsody  130s  ['Queen']  Rhapsody in Red
# 40212eb6  Bohemian Rhapsody  338s  ['Queen']  1986-07: Wembley Stadium
```

### Release-group search (deduplicated albums)

```python
# Use release-group endpoint to avoid getting every regional edition
resp = json.loads(http_get(
    "https://musicbrainz.org/ws/2/release-group/"
    "?query=release-group:\"A+Night+at+the+Opera\"+AND+artist:queen&fmt=json&limit=5",
    headers=UA
))
# resp keys: count, release-groups
for rg in resp.get('release-groups', []):
    print(rg['id'], rg['title'], rg.get('primary-type'), rg.get('first-release-date'), rg['score'])
# 6b47c9a0  A Night at the Opera  Album  1975-11-21  100

# Browse release-groups for an artist
resp = json.loads(http_get(
    "https://musicbrainz.org/ws/2/release-group/"
    "?artist=0383dadf-2a4e-4d10-a46a-e9e041da8eb3&fmt=json&limit=25",
    headers=UA
))
print(resp['release-group-count'])  # 412
for rg in resp.get('release-groups', []):
    print(rg['title'], rg.get('primary-type'), rg.get('first-release-date'))
```

### Label and work lookups

```python
# Label search
resp = json.loads(http_get(
    "https://musicbrainz.org/ws/2/label/?query=EMI&fmt=json&limit=3",
    headers=UA
))
for l in resp['labels']:
    print(l['id'], l['name'], l.get('type'), l.get('country'), l['score'])
# c029628b  EMI  Original Production  GB  100

# Work (song composition — author-level, not performance-level)
resp = json.loads(http_get(
    "https://musicbrainz.org/ws/2/work/?query=bohemian+rhapsody&fmt=json&limit=3",
    headers=UA
))
for w in resp['works']:
    print(w['id'], w['title'], w.get('type'), w['score'])
# 41c94a08  Bohemian Rhapsody  Song  100
```

### Cover Art Archive

```python
# Get cover art for a release MBID
# 404 if no artwork has been uploaded for that release
def get_cover_art(release_mbid, size="500"):
    """
    size: '250', '500', '1200', or 'full' (original file)
    Returns the front cover URL, or None if no artwork exists.
    """
    try:
        resp = json.loads(http_get(
            f"https://coverartarchive.org/release/{release_mbid}",
            headers=UA
        ))
    except Exception:
        return None   # 404 = no art uploaded

    images = resp.get('images', [])
    # Prefer an image flagged as front=True
    front = next((img for img in images if img.get('front')), None)
    img = front or (images[0] if images else None)
    if not img:
        return None

    if size == 'full':
        return img['image']
    return img['thumbnails'].get(size) or img['thumbnails'].get('large')

# Thumbnail sizes confirmed: '250', '500', '1200', 'small' (=250), 'large' (=500)

url = get_cover_art("b84ee12a-09ef-421b-82de-0441a926375b")
# http://coverartarchive.org/release/b84ee12a.../1611507818-500.jpg

# Full images response structure
resp = json.loads(http_get(
    "https://coverartarchive.org/release/b84ee12a-09ef-421b-82de-0441a926375b",
    headers=UA
))
for img in resp['images']:
    print(img.get('types'))   # ['Front'], ['Back'], ['Liner'], ['Poster'], ['Medium'], ['Sticker'], ['Other']
    print(img.get('front'))   # True only for front=True flagged images (not all 'Front' types)
    print(img.get('approved'))# True/False
    print(img['image'])       # full resolution URL
    print(img['thumbnails'])  # {'small': '...-250.jpg', 'large': '...-500.jpg', '250': ..., '500': ..., '1200': ...}
```

### Lucene query syntax for search

All search endpoints support Lucene field queries:

```python
# Field search: artist:, type:, country:, tag:, release:, date:
resp = json.loads(http_get(
    "https://musicbrainz.org/ws/2/artist/"
    "?query=artist:queen+AND+type:group+AND+country:GB&fmt=json&limit=5",
    headers=UA
))
# count: 23 (exact matches only)

# Phrase search with quotes
resp = json.loads(http_get(
    "https://musicbrainz.org/ws/2/release/"
    '?query=release:"A+Night+at+the+Opera"+AND+artist:queen&fmt=json&limit=5',
    headers=UA
))
```

Common Lucene field names per entity:
- artist: `artist:`, `type:`, `country:`, `tag:`, `begin:`, `end:`
- release: `release:`, `artist:`, `date:`, `country:`, `status:`, `label:`, `barcode:`
- recording: `recording:`, `artist:`, `release:`, `dur:` (milliseconds), `tnum:` (track number)
- release-group: `release-group:`, `artist:`, `primarytype:`, `secondarytype:`

### Parallel fetching

```python
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "browser-harness/1.0 (your@email.com)"}

def fetch_artist(mbid):
    resp = json.loads(http_get(
        f"https://musicbrainz.org/ws/2/artist/{mbid}?inc=tags&fmt=json",
        headers=UA
    ))
    tags = [t['name'] for t in sorted(resp.get('tags', []), key=lambda x: x['count'], reverse=True)[:3]]
    return {"name": resp['name'], "type": resp.get('type'), "tags": tags}

mbids = [
    "0383dadf-2a4e-4d10-a46a-e9e041da8eb3",  # Queen
    "83d91898-7763-47d7-b03b-b92132375c47",  # Pink Floyd
    "678d88b2-87b0-403b-b63d-5da7465aecc3",  # Led Zeppelin
]

with ThreadPoolExecutor(max_workers=3) as ex:
    results = list(ex.map(fetch_artist, mbids))
# 3 artists fetched in ~0.79s total
```

Tested: 5-6 rapid sequential requests all succeed. Parallel requests at 3x concurrency succeed. Real 429s (rate-limit blocks) are only hit at very high burst rates; if you do get a 429, add `time.sleep(1)` between requests.

### Pagination

```python
import time

UA = {"User-Agent": "browser-harness/1.0 (your@email.com)"}

def browse_all_releases(artist_mbid, page_size=25):
    """Fetch all releases for an artist across multiple pages."""
    offset = 0
    total = None
    releases = []
    while total is None or offset < total:
        resp = json.loads(http_get(
            f"https://musicbrainz.org/ws/2/release/"
            f"?artist={artist_mbid}&fmt=json&limit={page_size}&offset={offset}",
            headers=UA
        ))
        total = resp['release-count']
        batch = resp['releases']
        releases.extend(batch)
        offset += len(batch)
        if offset < total:
            time.sleep(1)  # stay within 1 req/s for sequential pagination
    return releases

# Queen has 1635 releases — use release-groups (412) to get deduplicated albums
```

---

## `inc=` parameter reference

Stack multiple `inc=` values with `+` between them.

**Artist lookup** (`/ws/2/artist/{mbid}`):
- `releases` — list of releases (max ~25)
- `release-groups` — list of release groups (max ~25)
- `recordings` — list of recordings (max ~25)
- `works` — list of works
- `tags` — community genre tags (name + vote count)
- `ratings` — community rating (value 0-5, votes-count)
- `aliases` — alternative names and transliterations
- `annotation` — free-text editorial note
- `artist-rels`, `release-rels`, `recording-rels`, `work-rels` — relationship data

**Release lookup** (`/ws/2/release/{mbid}`):
- `artists` — full artist-credit objects
- `recordings` — track list with recording links (populates `media[].tracks[].recording`)
- `labels` — label-info with catalog numbers
- `release-groups` — the release group this belongs to
- `artist-credits` — expanded artist credit with joinphrase
- `media` — disc/format info (always included in lookup, not needed in `inc=`)

---

## Response shapes cheat sheet

```
# MBID format: standard UUID v4
"0383dadf-2a4e-4d10-a46a-e9e041da8eb3"

# Search response (artist/recording/release/release-group/label/work)
{
  "count": 1612,          # total matches
  "offset": 0,
  "<entity-plural>": [...] # e.g. "artists", "releases", "recordings", "release-groups"
}

# Browse response (using ?artist=MBID or ?label=MBID style)
{
  "release-count": 1635,  # note: key name changes per entity
  "release-offset": 0,    # e.g. "release-group-count", "recording-count"
  "releases": [...]
}

# Recording length is always milliseconds
recording['length'] // 1000  # => seconds

# Artist life-span
life_span = artist['life-span']
# {'begin': '1970-06-27', 'end': None, 'ended': True}
# 'ended': True with 'end': None means end date unknown but band is inactive

# Artist credit joinphrase (for multi-artist tracks)
# [{"name": "Simon", "artist": {...}, "joinphrase": " & "}, {"name": "Garfunkel", ...}]
```

---

## URL patterns

| Resource | URL |
|---|---|
| Artist search | `https://musicbrainz.org/ws/2/artist/?query={q}&fmt=json&limit=5` |
| Artist by MBID | `https://musicbrainz.org/ws/2/artist/{mbid}?inc=tags+ratings&fmt=json` |
| Browse releases by artist | `https://musicbrainz.org/ws/2/release/?artist={mbid}&fmt=json&limit=25&offset=0` |
| Release search | `https://musicbrainz.org/ws/2/release/?query={q}&fmt=json&limit=5` |
| Release by MBID | `https://musicbrainz.org/ws/2/release/{mbid}?inc=artists+recordings+labels&fmt=json` |
| Release-group browse | `https://musicbrainz.org/ws/2/release-group/?artist={mbid}&fmt=json&limit=25` |
| Recording search | `https://musicbrainz.org/ws/2/recording/?query={q}&fmt=json&limit=5` |
| Label search | `https://musicbrainz.org/ws/2/label/?query={q}&fmt=json&limit=5` |
| Work search | `https://musicbrainz.org/ws/2/work/?query={q}&fmt=json&limit=5` |
| Cover art | `https://coverartarchive.org/release/{release-mbid}` |

MusicBrainz entity browser URL (human-readable): `https://musicbrainz.org/artist/{mbid}` (replace `artist` with `release`, `recording`, etc.)

---

## Gotchas

- **`User-Agent` is mandatory** — without it you get HTTP 403 instantly. The header must include contact info, e.g. `browser-harness/1.0 (you@example.com)`. The default `http_get` UA (`Mozilla/5.0`) also gets 403.

- **Browse vs search response keys differ** — Search responses use `count` and `offset`; Browse responses (with `?artist=MBID`) use `release-count` / `release-offset` (or `release-group-count` etc.). Accessing `data['count']` on a browse response throws `KeyError`.

- **`releases` include in artist lookup caps at ~25** — Use the browse endpoint (`?artist=MBID`) with pagination for complete lists. Queen has 1,635 releases total; the `inc=releases` on the artist endpoint only returns ~25.

- **Use release-groups to avoid edition explosion** — A popular album can have hundreds of release entries (every country's pressing, every remaster, every format). Use `/ws/2/release-group/` to get one entry per "album concept". Queen's "A Night at the Opera" has 75+ release entries but 1 release-group.

- **Recording length is milliseconds** — `recording['length']` is in milliseconds, not seconds. Divide by 1000.

- **Sort-name differs from display name for persons** — Artists have both `name` (display: "David Bowie") and `sort-name` (alphabetical: "Bowie, David"). Groups usually have identical values.

- **Disambiguation in parentheses** — When multiple entities share a name, MusicBrainz adds a `disambiguation` field to distinguish them (e.g. `"English singer-songwriter"` vs a different David Bowie). Always check `a.get('disambiguation', '')` when resolving artist identity.

- **Score 100 does not mean unique** — Search returns `score: 100` for multiple results when several equally match the query. "dark side of the moon" returns 6 results all scored 100 — they're different regional pressings. Filter by `date`, `country`, or `status` to narrow down.

- **Recording search: plain query matches titles AND artists broadly** — `?query=bohemian+rhapsody+queen` matches *cover versions* first because "queen" appears in the artist or title of other recordings. Use `AND artist:queen` Lucene syntax to restrict to Queen performances.

- **Cover Art Archive returns 404 for releases with no uploaded art** — Check `release['cover-art-archive']['artwork']` (boolean) from any release browse/search response before hitting the CAA endpoint. Saves an extra HTTP round-trip.

- **Cover art `front=True` flag vs `types=['Front']`** — A release can have multiple images typed as 'Front' but only one (or none) flagged `front: true`. Always filter on `img.get('front') == True` for the canonical cover, not on `img.get('types') == ['Front']`.

- **CAA thumbnail key names** — Both string keys `'small'` (250px) and `'large'` (500px) exist as aliases alongside numeric string keys `'250'`, `'500'`, `'1200'`. Access as `img['thumbnails']['500']` or `img['thumbnails']['large']` — both work.

- **Rate limit: 1 req/s unauthenticated** — In practice, bursts of 5-6 sequential requests succeed without throttling. True 429s appear at higher rates. For sequential pagination loops, add `time.sleep(1)` between pages. For parallel fetching, limit concurrency to 3-5 workers.

- **`fmt=json` required** — Omitting it returns XML instead of JSON. Always append `&fmt=json` to every request.
