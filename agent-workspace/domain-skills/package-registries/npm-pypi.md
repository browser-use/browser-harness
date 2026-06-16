# npm & PyPI — Package Registry Data Extraction

`https://registry.npmjs.org` · `https://api.npmjs.org` · `https://pypi.org` · `https://pypistats.org`

Both registries expose full JSON APIs with no auth required. Never use a browser — every data point is available over HTTP.

Tested 2026-04-18 with `uv run python` + `http_get`.

---

## Latency reference (measured)

| Endpoint | Latency |
|----------|---------|
| PyPI package JSON | ~80ms |
| npm downloads point | ~110ms |
| npm registry full doc (react = 6.3MB) | ~280ms |
| npm registry search | ~330ms |
| pypistats.org recent | ~480ms |

---

## npm Registry

### Package metadata

Two endpoints — pick based on what you need:

**Full registry document** — includes all version history, time map, author, bugs, homepage, keywords, README (when present). Large for popular packages (react = 6.3MB).

```python
import json
data = json.loads(http_get("https://registry.npmjs.org/react"))

# Top-level keys: _id, name, dist-tags, versions, time, bugs, author,
#                 license, homepage, keywords, repository, description,
#                 contributors, maintainers, readme, readmeFilename, users
print(data['name'])                          # 'react'
print(data['dist-tags']['latest'])           # '19.2.5'
print(data['time']['created'])               # '2011-10-26T17:46:21.942Z'
print(data['time']['modified'])              # '2026-04-18T00:57:09.913Z'

latest = data['dist-tags']['latest']
v = data['versions'][latest]
# Version object keys: name, version, description, license, keywords,
#   homepage, bugs, repository, engines, exports, main, scripts,
#   dependencies, devDependencies, peerDependencies, dist, maintainers,
#   _npmUser, _nodeVersion, _npmVersion
print(v['description'])                      # 'React is a JavaScript library...'
print(v['license'])                          # 'MIT'
print(list(v.get('dependencies', {}).keys())) # [] (react 19 has no runtime deps)
print(v.get('homepage'))                     # 'https://react.dev/'
print(len(data['versions']))                 # 2785 — all published versions
```

**Single version endpoint** — 1–2KB instead of megabytes. Use when you only need one version's data.

```python
import json
# Fetch a specific version
v = json.loads(http_get("https://registry.npmjs.org/react/19.2.5"))
print(v['name'], v['version'], v['description'])

# Fetch latest directly (no need to resolve dist-tags first)
v = json.loads(http_get("https://registry.npmjs.org/react/latest"))
print(v['version'])   # '19.2.5'
```

**Abbreviated document** — skips time map and (in theory) README; versions dict still present. Use `Accept` header.

```python
import json, urllib.request, gzip

req = urllib.request.Request(
    "https://registry.npmjs.org/react",
    headers={
        "Accept": "application/vnd.npm.install-v1+json",
        "Accept-Encoding": "gzip"
    }
)
with urllib.request.urlopen(req, timeout=20) as r:
    raw = r.read()
    if r.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
data = json.loads(raw)
# Keys: name, dist-tags, versions, modified (no time map, no readme)
print(data['dist-tags']['latest'])           # '4.18.1' (for lodash)
```

Note: abbreviated is still large (react: 2.7MB) — use single-version endpoint when possible.

### Scoped packages

Scoped packages (`@scope/name`) work with a direct path — no encoding needed:

```python
import json
data = json.loads(http_get("https://registry.npmjs.org/@playwright/test"))
print(data['name'])                          # '@playwright/test'
print(data['dist-tags']['latest'])           # '1.59.1'
print(len(data['versions']))                 # 3148
```

If constructing URLs dynamically, either form works:
```python
# Direct path (preferred)
url = f"https://registry.npmjs.org/{pkg}"          # '@playwright/test'
# URL-encoded slash
url = f"https://registry.npmjs.org/{pkg.replace('/', '%2F')}"
```

### Download statistics

The npm downloads API is separate from the registry and very fast (~110ms).

**Point query** — single number for a period:

```python
import json

# Supported periods: last-day, last-week, last-month, last-year
# Also accepts ISO date ranges: YYYY-MM-DD:YYYY-MM-DD

stats = json.loads(http_get("https://api.npmjs.org/downloads/point/last-week/react"))
print(stats['downloads'])   # 123302510
print(stats['start'])       # '2026-04-11'
print(stats['end'])         # '2026-04-17'
print(stats['package'])     # 'react'

# Confirmed values (2026-04-18):
# last-day:   19,411,762
# last-week: 123,302,510
# last-month: 502,719,511
# last-year: 3,000,644,845
```

**Bulk point query** — up to ~128 packages in one call, comma-separated:

```python
import json

bulk = json.loads(http_get(
    "https://api.npmjs.org/downloads/point/last-week/"
    "react,vue,angular,webpack,typescript,eslint,jest,prettier,rollup,babel"
))
# Returns dict keyed by package name
for pkg, info in bulk.items():
    print(f"{pkg}: {info['downloads']:,}")
# react: 123,302,510
# vue: 11,042,359
# angular: 524,366
# webpack: 44,425,549
# typescript: 180,054,359
# eslint: 126,113,686
# jest: 43,394,412
# prettier: 87,551,734
# rollup: 103,431,439
# babel: 139,207
```

**Range query** — downloads per day over a period:

```python
import json

resp = json.loads(http_get(
    "https://api.npmjs.org/downloads/range/2025-01-01:2025-01-07/react"
))
# resp['downloads'] is a list of {downloads, day} objects
for entry in resp['downloads']:
    print(entry['day'], entry['downloads'])
# 2025-01-01  1336801
# 2025-01-02  3288088
# 2025-01-03  3381680
# ...
```

### Search

```python
import json

# Fields: text, size (max ~250), from (offset), quality, popularity, maintenance weights
data = json.loads(http_get(
    "https://registry.npmjs.org/-/v1/search?text=browser+automation&size=5"
))
print(data['total'])   # total results matching the query

for obj in data['objects']:
    p = obj['package']
    s = obj['score']
    # p keys: name, version, description, keywords, date, links, publisher, maintainers
    # s keys: final, detail.quality, detail.popularity, detail.maintenance
    print(
        p['name'],
        p['version'],
        f"{s['final']:.2f}",
        p.get('description', '')[:60]
    )
# agent-browser 0.26.0 462.28 Browser automation CLI for AI agents
# nightmare     3.0.2  306.64 A high-level browser automation library.
```

Score breakdown (all three are 0–1 floats):
- `quality` — code quality signals (tests, lint, TypeScript types)
- `popularity` — download counts normalized
- `maintenance` — release frequency, open issues

`final` is a weighted combination and can exceed 1.0 for extremely popular packages.

### Error handling

```python
import json, urllib.error

try:
    data = json.loads(http_get("https://registry.npmjs.org/nonexistent-pkg-xyz"))
except urllib.error.HTTPError as e:
    # 404 for missing packages
    print(e.code)                            # 404
    print(json.loads(e.read()))             # {'error': 'Not found'}
```

---

## PyPI

### Package metadata

```python
import json

# Latest version metadata
data = json.loads(http_get("https://pypi.org/pypi/requests/json"))
info = data['info']

# info keys (selected):
print(info['name'])             # 'requests'
print(info['version'])          # '2.33.1'
print(info['summary'])          # 'Python HTTP for Humans.'
print(info['license'])          # 'Apache-2.0'
print(info['author'])           # None (sometimes empty — check author_email)
print(info['author_email'])     # '"Kenneth Reitz" <me@kennethreitz.org>'
print(info['requires_python'])  # '>=3.10'
print(info['home_page'])        # None (may be empty — check project_urls)
print(info['project_urls'])
# {'Documentation': 'https://requests.readthedocs.io',
#  'Source': 'https://github.com/psf/requests'}

requires = info.get('requires_dist') or []
print(requires[:5])
# ['charset_normalizer<4,>=2', 'idna<4,>=2.5', 'urllib3<3,>=1.26',
#  'certifi>=2023.5.7', 'PySocks!=1.5.7,>=1.5.6; extra == "socks"']

print(info.get('classifiers', [])[:3])
# ['Development Status :: 5 - Production/Stable',
#  'Intended Audience :: Developers',
#  'License :: OSI Approved :: Apache Software License']

# data['urls'] — list of dist files for the latest version
for f in data['urls']:
    # keys: filename, packagetype, python_version, size, digests, url,
    #       upload_time, requires_python, yanked, yanked_reason
    print(f['packagetype'], f['python_version'], f['filename'], f['size'])
# bdist_wheel  py3     requests-2.33.1-py3-none-any.whl  64947
# sdist        source  requests-2.33.1.tar.gz           134120
```

### Specific version

```python
import json

# Fetch a pinned version (not just latest)
data = json.loads(http_get("https://pypi.org/pypi/requests/2.32.3/json"))
print(data['info']['version'])   # '2.32.3'
# Same structure as the latest endpoint
```

### Version history and yanked releases

```python
import json

data = json.loads(http_get("https://pypi.org/pypi/requests/json"))

# data['releases'] is a dict: version_string -> list of file objects
versions = list(data['releases'].keys())
print("Total versions:", len(versions))   # 159
# Versions are insertion-ordered (chronological, oldest first)
# dict key order is stable

# Find yanked versions
yanked = [
    (ver, files[0]['yanked_reason'])
    for ver, files in data['releases'].items()
    if files and files[0].get('yanked')
]
print(yanked[:2])
# [('2.32.0', 'Yanked due to conflicts with CVE-2024-35195 mitigation'),
#  ('2.32.1', 'Yanked due to conflicts with CVE-2024-35195 mitigation ')]

# info.yanked is True only if the LATEST version is yanked
print(data['info']['yanked'])            # False
print(data['info']['yanked_reason'])     # None
```

### Download statistics (pypistats.org)

PyPI does not expose download counts in its own JSON API. Use pypistats.org.

```python
import json

# Recent (last day/week/month) — fastest, single call
stats = json.loads(http_get("https://pypistats.org/api/packages/requests/recent"))
d = stats['data']
print(d['last_day'])    # 52969887
print(d['last_week'])   # 356556988
print(d['last_month'])  # 1385411770

# Historical daily totals (overall, going back ~6 months)
overall = json.loads(http_get("https://pypistats.org/api/packages/requests/overall"))
# overall['data'] is list of {category, date, downloads}
# category is 'with_mirrors' or 'without_mirrors'
for row in overall['data'][:3]:
    print(row['date'], row['category'], row['downloads'])
# 2025-10-19  with_mirrors     21916634
# 2025-10-19  without_mirrors  21882953

# Without mirrors (pip installs only, more accurate for real usage):
clean = json.loads(http_get(
    "https://pypistats.org/api/packages/requests/overall?mirrors=false"
))

# By Python major version
by_python = json.loads(http_get(
    "https://pypistats.org/api/packages/requests/python_major"
))
# data rows: {category: '3', date: '...', downloads: N}

# By OS
by_sys = json.loads(http_get(
    "https://pypistats.org/api/packages/requests/system"
))
# data rows: {category: 'Darwin'|'Linux'|'Windows'|'other'|'null', date, downloads}

# By Python minor version
by_minor = json.loads(http_get(
    "https://pypistats.org/api/packages/requests/python_minor"
))
```

### Parallel fetch for multiple packages

```python
import json
from concurrent.futures import ThreadPoolExecutor

packages = ['numpy', 'pandas', 'scikit-learn', 'torch', 'tensorflow']

def get_pypi_info(pkg):
    d = json.loads(http_get(f"https://pypi.org/pypi/{pkg}/json"))
    return {
        'name': pkg,
        'version': d['info']['version'],
        'summary': d['info']['summary'],
        'requires_python': d['info']['requires_python'],
    }

with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(get_pypi_info, packages))

for r in results:
    print(r['name'], r['version'], r['summary'][:50])
# numpy        2.4.4  Fundamental package for array computing in Python
# pandas       3.0.2  Powerful data structures for data analysis, time s
# scikit-learn 1.8.0  A set of python modules for machine learning and d
# torch        2.11.0 Tensors and Dynamic neural networks in Python with
# tensorflow   2.21.0 TensorFlow is an open source machine learning fram
```

### Error handling

```python
import json, urllib.error

try:
    data = json.loads(http_get("https://pypi.org/pypi/nonexistent-xyz-abc/json"))
except urllib.error.HTTPError as e:
    print(e.code)   # 404
    # Body is HTML, not JSON — don't try to parse it
```

---

## Parallel fetch patterns

### Mixed registry + stats in one shot

```python
import json
from concurrent.futures import ThreadPoolExecutor

def npm_info(pkg):
    # Use single-version endpoint (1-2KB) not full registry doc (MB)
    v = json.loads(http_get(f"https://registry.npmjs.org/{pkg}/latest"))
    s = json.loads(http_get(f"https://api.npmjs.org/downloads/point/last-month/{pkg}"))
    return {'name': pkg, 'version': v['version'], 'downloads': s['downloads']}

pkgs = ['react', 'vue', 'svelte', 'solid-js', 'preact']
with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(npm_info, pkgs))
for r in results:
    print(r['name'], r['version'], f"{r['downloads']:,}")
```

### npm bulk downloads (most efficient for many packages)

```python
import json

# Up to ~128 packages in one HTTP call
pkgs = ['react', 'vue', 'angular', 'svelte']
bulk = json.loads(http_get(
    f"https://api.npmjs.org/downloads/point/last-week/{','.join(pkgs)}"
))
# Returns: {pkg_name: {'downloads': N, 'start': '...', 'end': '...', 'package': '...'}, ...}
sorted_pkgs = sorted(bulk.items(), key=lambda x: x[1]['downloads'], reverse=True)
for name, info in sorted_pkgs:
    print(f"{name}: {info['downloads']:,}")
```

---

## Rate limits

No rate limits encountered across rapid bursts of 10 sequential calls per endpoint (2026-04-18 testing):

| API | Observed limit |
|-----|----------------|
| npm registry (`registry.npmjs.org`) | None observed |
| npm downloads (`api.npmjs.org`) | None observed |
| npm search | None observed |
| PyPI JSON (`pypi.org`) | None observed |
| pypistats.org | None observed |

npm's official documentation mentions soft rate limits at very high volumes, but normal task-level usage (dozens of calls) is unaffected. If building a large scraper, add a short sleep between batches as a precaution.

---

## Gotchas

- **Full npm registry doc is huge** — `registry.npmjs.org/react` is 6.3MB (2785 versions). When you only need the latest version metadata, fetch `registry.npmjs.org/react/latest` (~1.8KB) instead. Similarly for any specific version.

- **npm `versions` dict keys are ordered oldest-first** — The last key is NOT necessarily the latest release; it may be a canary/experimental build. Always use `dist-tags.latest` to identify the stable latest version.

- **PyPI `author` field is often `None`** — Many packages set `author_email` instead (often in `"Name" <email>` format). Fall back: `info['author'] or info['author_email']`.

- **PyPI `home_page` is frequently empty** — Check `info['project_urls']` for `Homepage`, `Source`, `Documentation` links instead.

- **PyPI `requires_dist` can be `None`** — Not an empty list — `None`. Always guard: `info.get('requires_dist') or []`.

- **PyPI XML-RPC API is dead** — `https://pypi.org/pypi` (XML-RPC) returns a fault for most methods including `package_releases`. Use JSON API only.

- **pypistats.org `total` field is `None`** — The `total` key in response JSON is null; compute sums from `data` list yourself.

- **pypistats.org data goes back ~6 months** — The `overall` endpoint returns daily rows for roughly the past 180 days, not full history.

- **PyPI yanked versions** — `data['releases'][ver][0]['yanked']` is `True` for yanked versions. `data['info']['yanked']` is only `True` if the latest version itself is yanked. Both `yanked` and `yanked_reason` fields exist on each file object.

- **npm scoped packages** — Both `registry.npmjs.org/@scope/name` (direct path) and `registry.npmjs.org/@scope%2Fname` (URL-encoded) work. Use the direct path form.

- **npm downloads bulk response is a dict** — When you request multiple packages, the response is `{pkg_name: {...}}`, not a list. Single-package response is a flat object with `downloads`, `start`, `end`, `package` directly.

- **`http_get` handles gzip transparently** — The helper already decompresses gzip responses. No manual decompression needed.

- **Never use a browser for either registry** — All data is JSON over HTTP. `http_get` calls take 80–480ms; a browser navigation would take 3–8 seconds with no benefit.
