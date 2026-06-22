# BundlePhobia — npm Package Size Analysis

`https://bundlephobia.com` — bundle size (minified + gzip), tree-shaking signals, and dependency breakdown for npm packages. Fully public JSON API, no auth required. Never use a browser — all data is available over HTTP.

Tested 2026-04-18 with `http_get`.

---

## Do this first: `http_get` the size API

**Fastest path: one call, fully parsed JSON.**

```python
import json

# Latest version
data = json.loads(http_get("https://bundlephobia.com/api/size?package=react"))
# Pinned version
data = json.loads(http_get("https://bundlephobia.com/api/size?package=react@18.2.0"))

# Key fields:
# data['size']            – minified size in bytes (NOT gzip)
# data['gzip']            – gzip size in bytes  ← the number shown on the site
# data['version']         – resolved version string
# data['hasSideEffects']  – False = safe to tree-shake (package.json sideEffects:false)
# data['hasJSModule']     – path string or False; truthy = has ESM entry point
# data['isModuleType']    – True if package.json type:"module"
# data['dependencyCount'] – number of bundled dependencies
# data['dependencySizes'] – list of {name, approximateSize} for each dep
# data['assets']          – list of {name, type, size, gzip} per bundle asset
# data['scoped']          – True for @scope/name packages
# data['description']     – npm package description
# data['repository']      – git repo URL
```

Measured latency for cached popular packages: **80–120ms**.

---

## Latency reference (measured)

| Endpoint | Latency |
|----------|---------|
| `/api/size` (cached popular package) | ~80–120ms |
| `/api/size` (uncached/first-build) | up to 30s or timeout |
| `/api/package-history` (react, 129 versions) | ~100ms |
| 5 packages parallel via ThreadPoolExecutor | ~300ms |

---

## Common workflows

### Single package — latest or pinned version

```python
import json

react = json.loads(http_get("https://bundlephobia.com/api/size?package=react"))
print(react['version'])        # '19.2.5'
print(react['gzip'])           # 2908  (bytes)
print(react['size'])           # 7593  (bytes, minified)
print(react['hasSideEffects']) # True
print(react['hasJSModule'])    # False  (no ESM entry)
print(react['dependencyCount'])# 0

# Pinned version
r18 = json.loads(http_get("https://bundlephobia.com/api/size?package=react@18.2.0"))
print(r18['gzip'], r18['size'])  # 2598  6542
```

### Scoped packages

Pass the `@scope/name` directly — no URL encoding needed.

```python
import json

babel = json.loads(http_get("https://bundlephobia.com/api/size?package=@babel/core"))
print(babel['version'])   # '7.29.0'
print(babel['gzip'])      # 292003
print(babel['scoped'])    # True
```

### Parallel fetch for multiple packages

```python
import json
from concurrent.futures import ThreadPoolExecutor

packages = ["react", "lodash", "axios", "vue", "express"]

def fetch_size(pkg):
    try:
        data = json.loads(http_get(f"https://bundlephobia.com/api/size?package={pkg}"))
        return {
            "name": pkg,
            "version": data["version"],
            "gzip_kb": round(data["gzip"] / 1024, 1),
            "size_kb": round(data["size"] / 1024, 1),
            "has_side_effects": data["hasSideEffects"],
            "has_esm": bool(data.get("hasJSModule")),
        }
    except Exception as e:
        return {"name": pkg, "error": str(e)}

with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_size, packages))

for r in results:
    if "error" not in r:
        print(f"{r['name']}@{r['version']}: {r['gzip_kb']}KB gzip, esm={r['has_esm']}, sideEffects={r['has_side_effects']}")
# react@19.2.5:   2.8KB gzip, esm=False, sideEffects=True
# lodash@4.18.1: 24.7KB gzip, esm=False, sideEffects=True
# axios@1.15.0:  14.1KB gzip, esm=False, sideEffects=False
# vue@3.5.32:    41.5KB gzip, esm=False, sideEffects=True
# express@5.2.1: 236.1KB gzip, esm=False, sideEffects=True
```

### Scan a package.json's dependencies

```python
import json
from concurrent.futures import ThreadPoolExecutor

package_json = json.loads(http_get("https://raw.githubusercontent.com/owner/repo/main/package.json"))
deps = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}

# Build pinned package strings
pinned = []
for name, version_range in deps.items():
    # Strip semver range prefixes (^, ~, >=, etc.)
    v = version_range.lstrip("^~>=<").split(" ")[0]
    pinned.append(f"{name}@{v}" if v and v[0].isdigit() else name)

def fetch_size(pkg_str):
    try:
        data = json.loads(http_get(f"https://bundlephobia.com/api/size?package={pkg_str}", timeout=15.0))
        return {"pkg": pkg_str, "gzip": data["gzip"], "size": data["size"],
                "version": data["version"], "hasSideEffects": data["hasSideEffects"]}
    except Exception as e:
        return {"pkg": pkg_str, "error": str(e)[:80]}

with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_size, pinned))

# Sort by gzip size descending
ok = [r for r in results if "error" not in r]
ok.sort(key=lambda x: x["gzip"], reverse=True)
for r in ok:
    print(f"{r['pkg']}: {r['gzip']/1024:.1f}KB gzip")
```

### Version history — all versions with cached size data

```python
import json

history = json.loads(http_get("https://bundlephobia.com/api/package-history?package=react"))
# Returns a dict: version_string -> size_data_object (or empty dict {})
# Only versions that have been previously built have data; the rest are empty {}

versions_with_data = {k: v for k, v in history.items() if v}
print(f"Total versions: {len(history)}, with size data: {len(versions_with_data)}")
# Total versions: 129, with size data: 32

# Most recently cached version with size data:
for version, data in list(versions_with_data.items())[-3:]:
    print(f"  {version}: gzip={data['gzip']} size={data['size']}")
# 18.2.0: gzip=2598 size=6542
# 19.2.4: gzip=2908 size=7593
# 19.2.5: gzip=2908 size=7593
```

### Error handling

```python
import json, urllib.error

def safe_fetch(pkg):
    try:
        data = json.loads(http_get(
            f"https://bundlephobia.com/api/size?package={pkg}",
            timeout=15.0
        ))
        return data
    except urllib.error.HTTPError as e:
        err = json.loads(e.read())["error"]
        return {"error_code": err["code"], "pkg": pkg}
    except Exception as e:
        # Timeout or connection error — package may be uncached and slow to build
        return {"error_code": "Timeout", "pkg": pkg}

# Known error codes (HTTP 404):
# PackageNotFoundError      – package does not exist on npm
# PackageVersionMismatchError – version does not exist; response includes valid versions list
# Known error codes (HTTP 403):
# UnsupportedPackageError   – @types/* and similar non-runtime-code packages

result = safe_fetch("@types/node")
print(result)
# {'error_code': 'UnsupportedPackageError', 'pkg': '@types/node'}

result = safe_fetch("react@999.999.999")
print(result["error_code"])  # 'PackageVersionMismatchError'
```

---

## Response shape reference

```
/api/size response
├── name              str    package name
├── version           str    resolved version
├── description       str    npm description
├── repository        str    git URL
├── scoped            bool   True for @scope/name
├── size              int    minified bytes (no compression)
├── gzip              int    gzip bytes ← use this for "bundle size"
├── hasSideEffects    bool   False = package.json sets sideEffects:false → tree-shakeable
├── hasJSModule       str|False  ESM entry point path, or False if CJS-only
├── hasJSNext         str|False  "jsnext:main" field (older ESM signal, usually False)
├── isModuleType      bool   True if package.json type:"module"
├── dependencyCount   int    number of dependencies bundled in
├── dependencySizes   list[{name, approximateSize}]
└── assets            list[{name, type, size, gzip}]  per-output-file breakdown
```

---

## Rate limits

Headers on every response:
- `X-RateLimit-Limit: 60`
- `X-RateLimit-Remaining: N`
- `X-RateLimit-Reset: <epoch-ms>`

**60 requests per window** (the reset timestamp indicates the next window boundary). The window appears to be per-minute or per-session — `Remaining` was not always present on cached (Cloudflare HIT) responses, suggesting Cloudflare may serve cached results without decrementing the counter.

At 5 workers parallel, 5 cached packages complete in ~300ms — well within any practical rate budget. Add `time.sleep(1)` between large batches if scanning 50+ packages.

---

## Gotchas

- **Build-on-demand latency** — Uncached packages (first query for that version) are built in real time. This can take 10–30+ seconds and sometimes returns HTTP 502/520 (Cloudflare upstream error). Popular packages (react, lodash, axios) are always cached and return in under 200ms. Retry once after a 2-second delay if you get 502/520.

- **Nonexistent packages time out, not 404** — `PackageNotFoundError` takes ~28 seconds to return because bundlephobia must first verify the package is absent from npm. Always set `timeout=15.0` and treat timeout as a likely "not found or uncached" signal.

- **`@types/*` packages return 403, not 404** — Type-only packages raise `UnsupportedPackageError` (HTTP 403) almost instantly. No bundle size exists for them.

- **`gzip` is the canonical size** — The site UI shows the gzip size. `size` is the raw minified size before compression — always larger. Use `data['gzip']` to match what users see on the website.

- **`hasJSModule` is a path string, not a boolean** — It's either `False` or a non-empty string like `"./index.mjs"`. Use `bool(data.get('hasJSModule'))` for a boolean check.

- **`package-history` returns empty dicts for most versions** — Versions that have never been queried on bundlephobia have `{}` as their value. Only filter for `v for v in history.values() if v` to get real data.

- **`PackageVersionMismatchError` includes valid versions** — The `message` field contains an HTML-formatted list of valid versions. Useful for discovery but requires HTML stripping to read cleanly.

- **Scoped packages work without encoding** — `@babel/core` works fine directly in the query string. URL-encoding the `@` and `/` also works but is not required.

- **Bulk endpoint does not exist** — There is no `bulk-sizes` or `scan` API endpoint. Use `ThreadPoolExecutor` with the single-package `/api/size` endpoint for multi-package queries.

- **`X-RateLimit-Remaining` may be absent** — Cloudflare-cached responses sometimes omit this header. Don't rely on it for precise counting; use the Limit header and track your own request count.

- **`size` ≠ `assets[0].size` for multi-asset packages** — Some packages produce multiple output files; `size` and `gzip` reflect the main/primary asset. Check `assets` for the full breakdown.
