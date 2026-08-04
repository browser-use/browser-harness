# Cover Art Archive — Scraping & Data Extraction

`https://coverartarchive.org` — album artwork database linked to MusicBrainz. **Never use the browser.** All data is reachable via HTTP. No API key required.

## Do this first

**Use subprocess curl (not `http_get`) to avoid SSL certificate errors on macOS Python 3.11.** The CAA API always redirects (`307`) to `archive.org` — pass `-L` to follow.

```python
import subprocess, json

def caa_get(url):
    """Fetch a CAA URL, following redirects. Returns parsed JSON or None (on 404)."""
    result = subprocess.run(
        ['curl', '-sL', url],
        capture_output=True, text=True, timeout=20
    )
    if not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

# Get all cover art for a release (MusicBrainz Release MBID)
data = caa_get('https://coverartarchive.org/release/76df3287-6cda-33eb-8e9a-044b5e15ffdd')
# Confirmed output (2026-04-18): {'images': [...6 items...], 'release': 'https://musicbrainz.org/...'}
```

You need the **Release MBID** (not Release Group MBID) for the most reliable results. Use the MusicBrainz API to look up MBIDs by artist/album name.

## Common workflows

### Get front cover art for a release

```python
import subprocess, json

def caa_get(url):
    result = subprocess.run(['curl', '-sL', url], capture_output=True, text=True, timeout=20)
    if not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None

# OK Computer (UK original pressing)
MBID = '76df3287-6cda-33eb-8e9a-044b5e15ffdd'
data = caa_get(f'https://coverartarchive.org/release/{MBID}')

if data is None:
    print('No cover art found for this release')
else:
    images = data['images']
    front = next((img for img in images if img.get('front')), None)
    if front:
        print('Full image:', front['image'])
        print('250px thumb:', front['thumbnails']['250'])
        print('500px thumb:', front['thumbnails']['500'])
        print('1200px thumb:', front['thumbnails']['1200'])
        print('Types:', front['types'])
        print('Approved:', front['approved'])
        print('Image ID:', front['id'])
# Confirmed output (2026-04-18):
# Full image:    http://coverartarchive.org/release/76df3287-.../829521842.jpg
# 250px thumb:   http://coverartarchive.org/release/76df3287-.../829521842-250.jpg
# 500px thumb:   http://coverartarchive.org/release/76df3287-.../829521842-500.jpg
# 1200px thumb:  http://coverartarchive.org/release/76df3287-.../829521842-1200.jpg
# Types: ['Front']
# Approved: True
# Image ID: 829521842
```

### Get all images with their types

```python
data = caa_get(f'https://coverartarchive.org/release/{MBID}')
if data:
    for img in data['images']:
        print(
            f"ID={img['id']}",
            f"front={img['front']}",
            f"back={img['back']}",
            f"types={img['types']}",
            f"approved={img['approved']}"
        )
# Confirmed output for OK Computer (UK):
# ID=829521842   front=True  back=False  types=['Front']           approved=True
# ID=24546038908 front=False back=False  types=['Front', 'Booklet'] approved=True
# ID=24546039829 front=False back=False  types=['Booklet']          approved=True
# ID=24546040945 front=False back=False  types=['Booklet']          approved=True
# ID=5769317885  front=False back=True   types=['Back']             approved=True
# ID=5769316809  front=False back=False  types=['Medium']           approved=True
```

Known image types: `Front`, `Back`, `Booklet`, `Medium`, `Tray`, `Spine`, `Obi`, `Sticker`, `Liner`, `Poster`, `Watermark`, `Raw/Unedited`, `Matrix/Runout`, `Top`, `Bottom`, `Other`.

### Release-group cover art (canonical front cover across all releases)

```python
# Returns images from one specific release chosen as canonical for the group.
# The 'release' field tells you which release was selected.
# Dark Side of the Moon release group
data = caa_get('https://coverartarchive.org/release-group/f5093c06-23e3-404f-aeaa-40f72885ee3a')
if data:
    print('Canonical release:', data['release'])
    front = next((i for i in data['images'] if i.get('front')), None)
    print('Front thumb 500:', front['thumbnails']['500'] if front else None)
# Confirmed output (2026-04-18):
# Canonical release: https://musicbrainz.org/release/956fbc58-362d-43b8-b880-3779e0508559
# Front thumb 500:   http://coverartarchive.org/release/956fbc58-.../34025419985-500.jpg
```

### Direct front/back shortcut URLs (redirect straight to image bytes)

```python
import subprocess

# These URLs redirect (307) to the actual JPEG — no JSON parsing needed.
MBID = '76df3287-6cda-33eb-8e9a-044b5e15ffdd'

# Download full-resolution front cover
result = subprocess.run(
    ['curl', '-sL', f'https://coverartarchive.org/release/{MBID}/front'],
    capture_output=True, timeout=30
)
jpeg_bytes = result.stdout  # raw JPEG bytes — 76KB for OK Computer front cover

# Thumbnail shortcuts: /front-250, /front-500, /front-1200, /back-250, /back-500, /back-1200
result = subprocess.run(
    ['curl', '-sL', f'https://coverartarchive.org/release/{MBID}/front-500'],
    capture_output=True, timeout=30
)
thumb_bytes = result.stdout

# Save to file
with open('/tmp/cover.jpg', 'wb') as f:
    f.write(result.stdout)
```

### Parallel fetch for multiple releases

```python
import subprocess, json
from concurrent.futures import ThreadPoolExecutor

def get_front_thumb(mbid, size=500):
    """Return (mbid, thumbnail_url_or_None)."""
    result = subprocess.run(
        ['curl', '-sL', f'https://coverartarchive.org/release/{mbid}'],
        capture_output=True, text=True, timeout=20
    )
    if not result.stdout.strip():
        return mbid, None
    try:
        data = json.loads(result.stdout)
        front = next((i for i in data['images'] if i.get('front')), None)
        return mbid, front['thumbnails'].get(str(size)) if front else None
    except Exception:
        return mbid, None

mbids = [
    '76df3287-6cda-33eb-8e9a-044b5e15ffdd',  # OK Computer (UK)
    '956fbc58-362d-43b8-b880-3779e0508559',  # Dark Side of the Moon
]
with ThreadPoolExecutor(max_workers=4) as ex:
    results = list(ex.map(get_front_thumb, mbids))

for mbid, url in results:
    print(mbid, url)
# Confirmed working (2026-04-18): both returned 500px thumbnail URLs
# max_workers=4 is safe; don't exceed 8 for continuous crawling
```

## URL reference

### API endpoints

| Endpoint | Method | Returns |
|---|---|---|
| `https://coverartarchive.org/release/{mbid}` | GET | JSON index of all images for a release |
| `https://coverartarchive.org/release-group/{mbid}` | GET | JSON index from the canonical release of a group |
| `https://coverartarchive.org/release/{mbid}/front` | GET | Redirects to full-res front cover JPEG |
| `https://coverartarchive.org/release/{mbid}/back` | GET | Redirects to full-res back cover JPEG |
| `https://coverartarchive.org/release/{mbid}/front-250` | GET | Redirects to 250px front thumbnail |
| `https://coverartarchive.org/release/{mbid}/front-500` | GET | Redirects to 500px front thumbnail |
| `https://coverartarchive.org/release/{mbid}/front-1200` | GET | Redirects to 1200px front thumbnail |
| `https://coverartarchive.org/release/{mbid}/{image_id}.jpg` | GET | Redirects to full-res specific image |
| `https://coverartarchive.org/release/{mbid}/{image_id}-250.jpg` | GET | Redirects to 250px thumbnail |
| `https://coverartarchive.org/release/{mbid}/{image_id}-500.jpg` | GET | Redirects to 500px thumbnail |
| `https://coverartarchive.org/release/{mbid}/{image_id}-1200.jpg` | GET | Redirects to 1200px thumbnail |

### Redirect chain

Every CAA URL redirects — always pass `-L` to curl or use an HTTP client that follows redirects:

1. `coverartarchive.org/release/{mbid}` → `307` → `archive.org/download/mbid-{mbid}/index.json` → `200` (JSON)
2. `coverartarchive.org/release/{mbid}/front` → `307` → `archive.org/download/mbid-{mbid}/mbid-{mbid}-{id}.jpg` → `302` → CDN URL → `200` (JPEG)
3. Thumbnail URLs in the JSON response use `http://` not `https://`, but both work.

### JSON response structure

```python
{
    "images": [
        {
            "id": 829521842,          # numeric image ID
            "image": "http://coverartarchive.org/release/{mbid}/829521842.jpg",  # full-res
            "thumbnails": {
                "250":   "http://coverartarchive.org/release/{mbid}/829521842-250.jpg",
                "500":   "http://coverartarchive.org/release/{mbid}/829521842-500.jpg",
                "1200":  "http://coverartarchive.org/release/{mbid}/829521842-1200.jpg",
                "small": "...829521842-250.jpg",   # alias for 250
                "large": "...829521842-500.jpg",   # alias for 500
            },
            "types": ["Front"],       # list of type strings
            "front": True,            # bool — is this the designated front cover?
            "back": False,            # bool — is this the designated back cover?
            "approved": True,         # bool — approved by MusicBrainz editors
            "comment": "",            # optional editor comment
            "edit": 17462565          # MusicBrainz edit ID that added this image
        },
        # ... more images
    ],
    "release": "https://musicbrainz.org/release/{mbid}"  # canonical MB release URL
}
```

## Gotchas

- **`http_get` from helpers.py fails on macOS Python 3.11** — `urllib` SSL certificate verification fails (`CERTIFICATE_VERIFY_FAILED`) on this platform. Use `subprocess.run(['curl', '-sL', ...])` instead. Alternatively, patch SSL: `ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE`.

- **Always pass `-L` to curl** — CAA never returns data directly; it always redirects (`307`). Without `-L`, you get 87 bytes of plain text: `See: https://archive.org/download/mbid-.../index.json`.

- **404 means no cover art uploaded, not a bad MBID** — A valid MBID with no art returns HTTP 404 and `<p>No cover art found for release {mbid}</p>`. Many releases on MusicBrainz have no associated cover art.

- **Release MBID vs Release Group MBID are different** — The release-group endpoint (`/release-group/{mbid}`) accepts a different type of MBID and returns images from whichever release the CAA chose as canonical for that group. The canonical release is identified by the `release` field in the response. When you need a specific edition's artwork (e.g., the Japanese pressing vs the UK pressing), use the individual release MBID.

- **The `front` and `back` boolean fields are independent of the `types` list** — An image can have `front: True` and `types: ['Front', 'Booklet']`. The boolean flags indicate which image is the *designated* front/back for the `/front` and `/back` shortcuts. Use `img.get('front')` to find the one image that serves the `/front` shortcut.

- **`small` and `large` are aliases, not unique sizes** — `thumbnails['small']` == `thumbnails['250']`; `thumbnails['large']` == `thumbnails['500']`. Only `250`, `500`, and `1200` are actual distinct sizes.

- **Image URLs in the JSON use `http://` not `https://**` — The `image` and `thumbnails` fields return `http://coverartarchive.org/...` URLs. Substitute `https://` or use as-is; the server accepts both.

- **No rate limit headers are returned** — CAA does not send `X-Ratelimit-*` headers. In practice, rapid bursts of 8–10 requests complete without throttling. For bulk crawling of hundreds of releases, add `time.sleep(1)` between batches to be safe.

- **Not all image IDs have all thumbnail sizes** — If a very old or small image was uploaded before thumbnail generation was added, the `250` or `1200` key may be missing from `thumbnails`. Always use `.get('250')` rather than `['250']` and fall back to `image` (the full-res URL) if needed.
