# Internet Archive / Wayback Machine — Scraping & Data Extraction

`https://archive.org` / `https://web.archive.org` — all public data, no auth required. Every workflow here is pure `http_get` — no browser needed.

## Do this first

**Use the CDX API for anything Wayback-related — it is the reliable workhorse. The Wayback Availability API (`/wayback/available`) is known to return empty `archived_snapshots` even for well-archived URLs and should not be used as a primary mechanism.**

```python
import json

# Find snapshots of any URL — primary entry point for Wayback data
r = http_get(
    "https://web.archive.org/cdx/search/cdx"
    "?url=iana.org&output=json&limit=5"
    "&fl=timestamp,original,statuscode,mimetype,length",
    timeout=40.0
)
rows = json.loads(r)
headers = rows[0]   # ['timestamp', 'original', 'statuscode', 'mimetype', 'length']
for row in rows[1:]:
    ts, orig, status, mime, length = row
    snap_url = f"https://web.archive.org/web/{ts}/{orig}"
    print(f"{ts}  {status}  {snap_url}")
```

For item metadata (books, video, audio, software), go straight to:

```python
data = json.loads(http_get("https://archive.org/metadata/{identifier}", timeout=30.0))
```

## Common workflows

### Find the nearest archived snapshot to a target date

```python
import json

# CDX sort=closest returns the single snapshot nearest to the given timestamp
r = http_get(
    "https://web.archive.org/cdx/search/cdx"
    "?url=iana.org&output=json&limit=1"
    "&fl=timestamp,original,statuscode"
    "&closest=20230601120000&sort=closest",
    timeout=60.0   # CDX can be slow — always use timeout >= 40s
)
rows = json.loads(r)
# rows[0] = header, rows[1] = closest snapshot
ts, orig, status = rows[1]
snap_url = f"https://web.archive.org/web/{ts}/{orig}"
# Result: ts='20230601114925', orig='https://www.iana.org/', status='200'
# snap_url: https://web.archive.org/web/20230601114925/https://www.iana.org/
```

Timestamp format is always 14-digit `YYYYMMDDHHMMSS`. Pass any prefix — `20230601` (day), `202306` (month), `2023` (year) — and CDX will match.

### List all monthly snapshots for a URL (collapsed)

```python
import json

r = http_get(
    "https://web.archive.org/cdx/search/cdx"
    "?url=iana.org&output=json"
    "&collapse=timestamp:6"   # :6 = dedupe by YYYYMM (one per month)
    "&from=20230101&to=20231231"
    "&fl=timestamp,original",
    timeout=60.0
)
rows = json.loads(r)
# rows[0] = header ['timestamp', 'original']
# rows[1:] = one row per month:
# ['20230101103807', 'https://www.iana.org/']
# ['20230201144829', 'https://www.iana.org/']
# ...12 rows for 2023

for ts, orig in rows[1:]:
    print(f"{ts[:4]}-{ts[4:6]}  https://web.archive.org/web/{ts}/{orig}")
```

`collapse=timestamp:N` deduplicates by the first N digits of the timestamp:
- `:4` = one per year, `:6` = one per month, `:8` = one per day

### List snapshots for an entire domain (all pages)

```python
import json

# matchType=domain captures all URLs under that domain
r = http_get(
    "https://web.archive.org/cdx/search/cdx"
    "?url=iana.org&matchType=domain&output=json"
    "&limit=10&fl=timestamp,original,statuscode"
    "&collapse=timestamp:8",  # one capture per URL per day
    timeout=60.0
)
rows = json.loads(r)
for row in rows[1:]:
    print(row)
# ['19971210061738', 'http://www.iana.org:80/', '200']
# ['19980211065537', 'http://www.iana.org:80/', '200']
# ...
```

`matchType` options: `exact` (default), `prefix` (URL + subpaths), `host` (all subdomains), `domain` (host + all subdomains).

### Filter snapshots by prefix path

```python
import json

# All archived pages under /domains/ path
r = http_get(
    "https://web.archive.org/cdx/search/cdx"
    "?url=iana.org/domains/&matchType=prefix&output=json"
    "&limit=5&fl=timestamp,original,statuscode",
    timeout=40.0
)
rows = json.loads(r)
for row in rows[1:]:
    print(row)
# ['20080509121811', 'http://www.iana.org/domains/', '200']
# ['20080704174537', 'http://iana.org/domains/', '200']
```

### Paginate CDX results with resumeKey

```python
import json
from urllib.parse import quote

def cdx_all_snapshots(url, fl="timestamp,original,statuscode", page_size=500):
    """Iterate all CDX records for a URL, yielding rows (excluding header)."""
    base = (
        f"https://web.archive.org/cdx/search/cdx"
        f"?url={quote(url, safe='')}&output=json"
        f"&fl={fl}&limit={page_size}&showResumeKey=true"
    )
    resume_key = None
    while True:
        endpoint = base if resume_key is None else f"{base}&resumeKey={quote(resume_key)}"
        rows = json.loads(http_get(endpoint, timeout=60.0))
        # rows structure with showResumeKey=true:
        # [header, row1, row2, ..., [], [resume_key_string]]
        # The second-to-last row is [] (separator), last row is [resume_key]
        has_resume = len(rows) >= 2 and rows[-1] != [] and rows[-2] == []
        data_rows = rows[1:-2] if has_resume else rows[1:]
        for row in data_rows:
            yield row
        if not has_resume:
            break
        resume_key = rows[-1][0]

for row in cdx_all_snapshots("iana.org", fl="timestamp,original"):
    ts, orig = row
    # process...
```

### Retrieve the actual archived page

```python
# Direct snapshot URL: /web/{14-digit-timestamp}/{original-url}
snap_url = "https://web.archive.org/web/19971210061738/http://www.iana.org:80/"
content = http_get(snap_url, timeout=30.0)
# Returns the archived HTML with Wayback toolbar injected at top
# The toolbar is inside <!-- BEGIN WAYBACK TOOLBAR INSERT --> comments

# The calendar view URL pattern (for browser navigation, not http_get):
# https://web.archive.org/web/20230101000000*/python.org
# The * tells Wayback to show the calendar — returns HTML, not raw page
```

### Item metadata (books, video, audio, software, collections)

```python
import json
from urllib.parse import quote

identifier = "HardWonWisdomTrailer"
data = json.loads(http_get(f"https://archive.org/metadata/{identifier}", timeout=30.0))

# Top-level keys:
# alternate_locations, created, d1, d2, dir, files, files_count,
# is_collection, item_last_updated, item_size, metadata, server, uniq, workable_servers

meta = data['metadata']
# Common metadata fields (not all present on every item):
print(meta.get('identifier'))   # 'HardWonWisdomTrailer'
print(meta.get('title'))        # 'Hard Won Wisdom Trailer'
print(meta.get('mediatype'))    # 'movies' | 'texts' | 'audio' | 'software' | 'collection'
print(meta.get('creator'))      # 'jakemauz'
print(meta.get('date'))         # '2017-02-18'
print(meta.get('description'))  # HTML string — strip tags if needed
print(meta.get('subject'))      # str OR list of str depending on item
print(meta.get('publicdate'))   # '2017-02-18 11:51:16'
print(meta.get('collection'))   # parent collection identifier

files = data['files']
# Each file entry:
# name, source ('original'|'derivative'|'metadata'), format, size (bytes as str),
# md5, sha1, crc32, mtime
# For video/audio: length (seconds as str), height, width
# For derivative: original (name of source file)

# Find the primary original file
orig_files = [f for f in files if f.get('source') == 'original']
# orig_files[0]: {'name': 'Hard-won wisdom trailer.mp4', 'source': 'original',
#  'format': 'MPEG4', 'size': '7532153', 'length': '94.13',
#  'height': '360', 'width': '640', 'md5': 'aaeebe0481...', ...}

# Build download URL — two equivalent forms:
server = data['server']      # 'ia601405.us.archive.org'
dir_path = data['dir']       # '/2/items/HardWonWisdomTrailer'
fname = orig_files[0]['name']
from urllib.parse import quote as urlquote
# Form 1: direct storage server (fastest)
url1 = f"https://{server}{dir_path}/{urlquote(fname)}"
# Form 2: standard redirect URL (always works, resolved by CDN)
url2 = f"https://archive.org/download/{identifier}/{urlquote(fname)}"
# Both confirmed status 200, Content-Type: video/mp4
```

### Search items (books, audio, video, software)

```python
import json

# advancedsearch.php is the correct API — /search returns HTML
r = http_get(
    "https://archive.org/advancedsearch.php"
    "?q=artificial+intelligence+AND+mediatype:texts"
    "&fl[]=identifier&fl[]=title&fl[]=creator&fl[]=date&fl[]=downloads"
    "&rows=5&sort[]=downloads+desc&output=json",
    timeout=30.0
)
data = json.loads(r)
# data['responseHeader']['status'] = 0 (success)
# data['responseHeader']['QTime'] = query time ms
# data['response']['numFound'] = 25911 (total matches)
# data['response']['start'] = 0 (offset)
# data['response']['docs'] = list of item dicts

resp = data['response']
print(f"Total: {resp['numFound']}, showing: {len(resp['docs'])}")
for doc in resp['docs']:
    print(f"  {doc['identifier']}  {doc.get('title', '')[:50]}")
    # doc fields are only present if they have values — always use .get()
```

Pagination: use `start=` offset (not `page=`). Max `rows=` is not documented but 100 works reliably.

### Search with all supported parameters

```python
import json

r = http_get(
    "https://archive.org/advancedsearch.php"
    "?q=machine+learning+AND+mediatype:texts"  # Lucene query syntax
    "&fl[]=identifier&fl[]=title&fl[]=date&fl[]=year"
    "&fl[]=creator&fl[]=subject&fl[]=description&fl[]=downloads"
    "&rows=3"
    "&start=0"               # pagination offset
    "&sort[]=date+desc"      # sort field + direction
    "&output=json",
    timeout=30.0
)
data = json.loads(r)
# Confirmed fields in fl[]:
# identifier, title, date, year, creator, subject, description,
# downloads, mediatype, collection, language, avg_rating, num_reviews

# mediatype values: texts, audio, movies, software, image, etree, data, collection, account
# Sort fields: date, downloads, avg_rating, num_reviews, publicdate, addeddate
```

## API reference

| Endpoint | What it returns | Auth |
|---|---|---|
| `web.archive.org/cdx/search/cdx?url=...&output=json` | Snapshot index: all captures of a URL | None |
| `archive.org/wayback/available?url=...` | Nearest snapshot (DEGRADED — see gotchas) | None |
| `archive.org/metadata/{identifier}` | Item metadata + files list | None |
| `archive.org/advancedsearch.php?q=...&output=json` | Full-text + metadata search | None |
| `archive.org/download/{identifier}/{filename}` | Direct file download | None |
| `web.archive.org/web/{timestamp}/{url}` | Archived page HTML | None |

## CDX field reference

The CDX API returns a JSON array of arrays. The first row is always the header when `output=json`.

| Field | Description | Example |
|---|---|---|
| `urlkey` | SURT-format URL (reversed domain, path in parens) | `org,iana)/` |
| `timestamp` | Capture time, 14-digit `YYYYMMDDHHMMSS` | `19971210061738` |
| `original` | Original crawled URL (exact, including port) | `http://www.iana.org:80/` |
| `mimetype` | Content-Type of the archived response | `text/html` |
| `statuscode` | HTTP status at crawl time | `200` |
| `digest` | SHA-1 of response body, base32-encoded | `I4YBMQ6PHPWE2TD6TIXNWHZB6MXRNTSR` |
| `length` | Content length in bytes (as string) | `1418` |

Default `fl=` when omitted: `urlkey,timestamp,original,mimetype,statuscode,digest,length` (all 7 fields in that order).

## Rate limits

No auth, no API key. In practice:
- CDX API: **intermittently slow** — individual queries time out at 20s and succeed at 40–60s. Always use `timeout=40.0` minimum. 3 rapid sequential CDX calls in ~10s completed; 10 rapid calls produced 3 timeouts.
- Metadata API: Fast and reliable — 5 sequential calls completed in 3.0s with no errors.
- Search API: Fast — typically responds in 30–65ms (`QTime` in response header).
- No documented per-second or per-day limits. Archive.org's policy is to be respectful: add `time.sleep(1)` between CDX calls in loops.

## Gotchas

- **CDX times out — always set `timeout=40.0` or higher.** The default 20s is often too short for CDX. Metadata and search APIs are fine at 20–30s. CDX slowness is backend-side and unpredictable; add retry logic for production use.

- **Wayback Availability API is unreliable.** `GET /wayback/available?url=iana.org` returns `{"url": "iana.org", "archived_snapshots": {}}` even for URLs confirmed archived via CDX. Tested 2026-04-18 across many URLs and timestamp combinations — consistently empty. Use `CDX ?sort=closest&limit=1` instead (confirmed working).

- **CDX first row is always the header when `output=json`.** `rows[0]` is `['timestamp', 'original', ...]`, not a data row. Always slice `rows[1:]` for data. When `showResumeKey=true`, the last two rows are `[]` (separator) and `['<resume_key_string>']`.

- **CDX `fl=` must match exactly what you iterate.** If you request `&fl=timestamp,original` you get 2-element rows; forgetting a field breaks destructuring. When in doubt, omit `fl=` entirely and get all 7 fields.

- **`output=json` is required — there is no default JSON mode.** Omitting `output=json` returns space-separated text. `output=text` also works and is slightly faster for simple queries.

- **`timestamp` is a string, not an integer.** Even in JSON, CDX returns all fields as strings: `'1418'` not `1418`, `'200'` not `200`. Cast explicitly: `int(row[4])`, `int(row[6])`.

- **The `original` field preserves port numbers.** Old crawls captured `http://www.iana.org:80/` — the `:80` is part of the URL. When building a playback URL, use `original` verbatim: `f"https://web.archive.org/web/{ts}/{orig}"` works correctly with the port included.

- **Metadata `{}` means the item doesn't exist or is private.** `http_get("https://archive.org/metadata/nonexistent")` returns `'{}'` (2-byte response) with HTTP 200. Always check `if not data` or `if not data.get('metadata')` before accessing fields.

- **Metadata `subject` can be a string or a list.** When a single subject tag is set, the API returns `"subject": "short film"`. When multiple, it returns `"subject": ["short film", "spoken word"]`. Normalize with: `subjects = [meta['subject']] if isinstance(meta.get('subject'), str) else meta.get('subject', [])`.

- **File `size` and `length` are strings, not numbers.** `files[0]['size']` is `'7532153'` (bytes). `files[0]['length']` is `'94.13'` (seconds for video/audio). Cast with `int()` and `float()` respectively.

- **Use `archive.org/download/` not the raw storage server URL for reliability.** The raw URL (`ia601405.us.archive.org/2/items/...`) is faster but server-specific. `archive.org/download/{id}/{file}` redirects to the correct storage node and remains stable as items migrate.

- **`/search?output=json` returns HTML, not JSON.** The `/search` endpoint is a React SPA — it ignores `output=json`. Always use `advancedsearch.php` for programmatic access.

- **`collapse=timestamp:6` gives one row per month, but it keeps the FIRST capture of that month.** If you want the last, you'd need to reverse and re-collapse, or fetch all and filter client-side. The `collapse` parameter de-duplicates by truncating the timestamp to N digits and keeping the first matching row.

- **CDX `from=` / `to=` accept partial timestamps.** `from=20230101` means `20230101000000`. `to=20231231` means `20231231000000` (exclusive). To include all of 2023, use `to=20240101`.
