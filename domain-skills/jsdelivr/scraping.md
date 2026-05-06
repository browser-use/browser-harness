# jsDelivr — Data Extraction

`data.jsdelivr.com` (stats/metadata API) + `cdn.jsdelivr.net` (file serving). No auth, no browser, pure `http_get`. All endpoints return JSON. API is fully public.

## Do this first

**Use `http_get` directly — no browser needed for any jsDelivr task.** The data API serves CORS-open JSON. The CDN serves raw files. Both work without cookies or tokens.

```python
import json
data = json.loads(http_get("https://data.jsdelivr.com/v1/packages/npm/react"))
# data keys: type, name, tags, versions
# tags keys: latest, beta, canary, next, etc.
# versions: list of dicts with .version and .links
latest = data['tags']['latest']   # e.g. "19.2.5"
```

| Goal | Endpoint | Latency (measured) |
|------|----------|-------------------|
| Package tags + version list | `v1/packages/npm/{pkg}` | ~200ms |
| Resolve semver/tag to exact version | `v1/package/resolve/npm/{pkg}@{range}` | ~230ms |
| Download stats (hits + bandwidth) | `v1/stats/packages/npm/{pkg}?period=month` | ~60–280ms |
| Stats by version | `v1/stats/packages/npm/{pkg}/versions?period=month` | ~250ms |
| Stats by file | `v1/stats/packages/npm/{pkg}@{ver}/files?period=month` | ~250ms |
| Top packages across CDN | `v1/stats/packages?period=month&limit=N` | ~3–8s |
| List all files in a version | `v1/package/npm/{pkg}@{ver}/flat` | ~100ms |
| Fetch actual file | `cdn.jsdelivr.net/npm/{pkg}@{ver}/{file}` | ~80–400ms |
| package.json metadata | `cdn.jsdelivr.net/npm/{pkg}@{ver}/package.json` | ~80ms |
| ESM-bundled module | `cdn.jsdelivr.net/npm/{pkg}@{ver}/+esm` | ~70ms |

---

## Common workflows

### Package metadata and latest version

```python
import json

data = json.loads(http_get("https://data.jsdelivr.com/v1/packages/npm/react"))
print(data['tags']['latest'])     # "19.2.5"
print(data['tags'].get('beta'))   # "19.0.0-beta-..."
print(len(data['versions']))      # total version count

# Resolve semver range or tag to exact version
resolved = json.loads(http_get(
    "https://data.jsdelivr.com/v1/package/resolve/npm/react@^18"
))
print(resolved['version'])   # "18.3.1"

# Also works with: @latest, @17, @^17, @~16.0
```

### Download statistics

```python
import json

stats = json.loads(http_get(
    "https://data.jsdelivr.com/v1/stats/packages/npm/react?period=month"
))
# stats keys: hits, bandwidth, links
# hits keys: rank, typeRank, total, dates, prev
# bandwidth keys: rank, typeRank, total, dates, prev

print(stats['hits']['total'])           # e.g. 283,243,887
print(stats['hits']['rank'])            # CDN-wide rank (all types)
print(stats['hits']['typeRank'])        # rank among npm packages only
print(stats['bandwidth']['total'])      # bytes served this period

# dates dict: {"2026-03-19": 9144085, ...}  — one entry per day
daily = stats['hits']['dates']
```

**Valid `period` values** (confirmed): `day` (1 date), `week` (7 dates), `month` (30 dates), `year` (365 dates).

### Stats broken down by version

```python
import json

versions = json.loads(http_get(
    "https://data.jsdelivr.com/v1/stats/packages/npm/react/versions?period=month"
))
# returns list sorted by hits desc
for v in versions[:5]:
    print(v['version'], v['hits']['total'])
# "18.3.1"  89898312
# "18.2.0"  84329445
# "16.14.0" 32173878
```

### Stats broken down by file (within a version)

```python
import json

files = json.loads(http_get(
    "https://data.jsdelivr.com/v1/stats/packages/npm/react@18.2.0/files?period=month"
))
for f in files[:3]:
    print(f['name'], f['hits']['total'])
# "/+esm"                    43924116
# "/umd/react.production.min.js" 38476714
```

### Top packages globally

```python
import json

top = json.loads(http_get(
    "https://data.jsdelivr.com/v1/stats/packages?period=month&limit=10"
))
# Each item: type, name, hits, bandwidth, prev, links
for pkg in top:
    print(pkg['type'], pkg['name'], pkg['hits'])
# Includes both npm and gh (GitHub) packages mixed together

# Filter to npm only:
top_npm = json.loads(http_get(
    "https://data.jsdelivr.com/v1/stats/packages?period=month&limit=10&type=npm"
))
```

Warning: this endpoint is slow (3–8s). Always specify `limit` to cap results.

### List all files in a version

```python
import json

# Flat list (simpler for iteration)
listing = json.loads(http_get(
    "https://data.jsdelivr.com/v1/package/npm/react@18.2.0/flat"
))
print(listing['default'])          # "/index.min.js"  — CDN default entrypoint
for f in listing['files']:
    print(f['name'], f['size'])    # name, hash, time, size
# e.g. "/cjs/react.development.js"  87574

# Tree listing (nested dirs)
tree = json.loads(http_get(
    "https://data.jsdelivr.com/v1/package/npm/react@18.2.0"
))
# tree['files'] = list of {type: "directory"|"file", name, files?, hash?, size?}
```

### Fetch files from CDN

```python
# Specific version + file
content = http_get("https://cdn.jsdelivr.net/npm/react@18.2.0/umd/react.production.min.js")

# package.json for metadata (description, keywords, deps, license)
meta = json.loads(http_get("https://cdn.jsdelivr.net/npm/lodash@latest/package.json"))
print(meta['version'], meta['description'], meta['license'])

# ESM bundle (auto-generated by jsDelivr)
esm = http_get("https://cdn.jsdelivr.net/npm/react@18.2.0/+esm")

# GitHub repository files
bootstrap_js = http_get(
    "https://cdn.jsdelivr.net/gh/twbs/bootstrap@v5.3.2/dist/js/bootstrap.min.js"
)

# Tag/range in CDN URL — resolved server-side
http_get("https://cdn.jsdelivr.net/npm/react@latest/package.json")   # resolves to latest
http_get("https://cdn.jsdelivr.net/npm/react@18/package.json")       # resolves to 18.x
```

### Parallel fetch multiple packages

```python
import json
from concurrent.futures import ThreadPoolExecutor

pkgs = ['react', 'lodash', 'vue', 'axios', 'jquery']

def fetch_stats(name):
    data = json.loads(http_get(
        f"https://data.jsdelivr.com/v1/stats/packages/npm/{name}?period=month"
    ))
    return name, data['hits']['total'], data['hits']['rank']

with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_stats, pkgs))
# 5 packages in ~280ms parallel vs ~1400ms sequential
for name, total, rank in sorted(results, key=lambda x: x[1], reverse=True):
    print(f"#{rank:4d}  {total:>15,}  {name}")
```

### GitHub packages

```python
import json

# GitHub package (gh type): owner/repo
data = json.loads(http_get("https://data.jsdelivr.com/v1/packages/gh/twbs/bootstrap"))
# Same shape: tags (often empty {}), versions list

stats = json.loads(http_get(
    "https://data.jsdelivr.com/v1/stats/packages/gh/twbs/bootstrap?period=month"
))
print(stats['hits']['total'])

# CDN URL for GitHub:
http_get("https://cdn.jsdelivr.net/gh/twbs/bootstrap@v5.3.2/dist/css/bootstrap.min.css")
```

---

## Gotchas

- **v1/package (deprecated) vs v1/packages (current)** — The old endpoint `GET /v1/package/npm/{pkg}` still works but returns a flatter shape (`{tags, versions: ["1.0.0", ...]}` as plain strings). The new `GET /v1/packages/npm/{pkg}` returns versions as objects with `links`. Both exist. The `Link: rel="deprecation"` header flags the old one. Use `/v1/packages/` for new code.

- **`/v1/package/resolve/npm/{pkg}@{range}` is the correct resolve endpoint** — `GET /v1/package/npm/react/resolved` returns HTTP 400. The working form is `/v1/package/resolve/npm/{pkg}@{tag_or_range}`. Range syntax: `@latest`, `@18`, `@^17`, `@~16.0`.

- **`/flat` for files, not `/files`** — File listing lives at `/v1/package/npm/{pkg}@{ver}/flat`. The path `/v1/packages/npm/{pkg}@{ver}/files` returns HTTP 400. `/flat` returns `{default, files: [{name, hash, time, size}]}`. Without `/flat`, you get a directory tree instead.

- **No rate limit headers** — Responses include no `X-RateLimit-*` headers. No published rate limit. 10+ rapid sequential requests returned no errors. CDN responses are cached (Cloudflare + Fastly, `Cache-Control: public, max-age=300`). Burst-friendly for scraping.

- **Top packages endpoint is slow** — `GET /v1/stats/packages?period=month` can take 3–8s. Always add `&limit=N` (max observed working: 100). Filter by type with `&type=npm` or `&type=gh` to cut response size and time.

- **`hits` vs `bandwidth` are separate rank trees** — A package can rank #117 by hits but #432 by bandwidth. Check both if you care about either metric. `prev` gives last-period totals for delta comparison.

- **404 returns JSON, not HTML** — `{"status": 404, "message": "Couldn't fetch versions for {pkg}."}`. The body is gzip-encoded even on 404. Catch `urllib.error.HTTPError` and decompress the body manually if needed.

- **File `time` field is synthetic** — Files in npm packages served by jsDelivr show `"time": "1985-10-26T08:15:00.000Z"` (the Back to the Future timestamp). This is a known quirk of how npm stores file mtimes. Do not use it for anything real.

- **`@latest` in CDN URL resolves server-side** — `cdn.jsdelivr.net/npm/react@latest/package.json` works and resolves to the current latest tag. Same for named tags (`@beta`, `@next`) and major version shorthand (`@18`). The data API does not support this shorthand natively — use `/v1/package/resolve/npm/{pkg}@{range}` instead.

- **ESM endpoint `/+esm` is auto-bundled** — `cdn.jsdelivr.net/npm/{pkg}@{ver}/+esm` returns an ESM module auto-generated by jsDelivr using Rollup + Terser. The comment at top explicitly warns against SRI hashes for this file since the content can change even for the same version. Use it for `<script type="module">` snippets, not for integrity-sensitive fetches.
