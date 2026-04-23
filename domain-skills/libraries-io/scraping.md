# Libraries.io — Scraping & Data Extraction

`https://libraries.io` — open-source package dependency tracking across 31 package managers. **Use `http_get` / pure HTTP for everything — no browser required.** Most endpoints return JSON without an API key; search requires a free key.

## Do this first

**Use the REST API — one call, JSON response, no browser.**

```python
import json
data = json.loads(http_get("https://libraries.io/api/pypi/requests"))
# Key fields: name, platform, description, rank, stars, forks,
#             latest_release_number, latest_stable_release_number,
#             latest_release_published_at, dependents_count,
#             dependent_repos_count, contributions_count,
#             licenses, normalized_licenses, repository_url,
#             package_manager_url, homepage, keywords, language, versions[]
```

API key is **optional** for project info and dependency lookups. Get a free key at `https://libraries.io/account` to unlock search and raise rate limits.

## Common workflows

### Project metadata (no key required)

```python
import json

data = json.loads(http_get("https://libraries.io/api/pypi/requests"))
print(data['name'], data['latest_release_number'], data['rank'])
print("Stars:", data['stars'], "Forks:", data['forks'])
print("Dependents:", data['dependents_count'], "Dependent repos:", data['dependent_repos_count'])
print("License:", data['licenses'])
print("Repo:", data['repository_url'])
# Confirmed output (2026-04-18):
# requests 2.33.1 32
# Stars: 53897 Forks: 9840
# Dependents: 108138 Dependent repos: 55851
# License: Apache-2.0
# Repo: https://github.com/psf/requests
```

Works for any supported platform — replace `pypi` with `npm`, `cargo`, `rubygems`, `maven`, `nuget`, etc.

```python
import json

express = json.loads(http_get("https://libraries.io/api/npm/express"))
serde   = json.loads(http_get("https://libraries.io/api/cargo/serde"))
rails   = json.loads(http_get("https://libraries.io/api/rubygems/rails"))
```

### Version list

The `versions` array in every project response lists all published versions:

```python
import json

data  = json.loads(http_get("https://libraries.io/api/pypi/requests"))
versions = data['versions']   # list of dicts
for v in versions[-3:]:       # last 3 (oldest first in array)
    print(v['number'], v['published_at'])
# Example: 2.33.0  2026-02-12T...  |  2.33.1  2026-03-30T...
# Each version: {number, published_at, spdx_expression, original_license,
#                researched_at, repository_sources[]}
```

### Dependencies for a specific version (no key required)

```python
import json

url  = "https://libraries.io/api/pypi/requests/2.31.0/dependencies"
data = json.loads(http_get(url))
# Response adds two extra keys on top of normal project fields:
#   dependencies_for_version: "2.31.0"
#   dependencies: list of dependency dicts
for dep in data['dependencies']:
    if not dep['optional']:
        print(dep['name'], dep['requirements'], dep['kind'])
# Confirmed output (2026-04-18):
# charset-normalizer  <4,>=2        runtime
# idna                <4,>=2.5      runtime
# urllib3             <3,>=1.21.1   runtime
# certifi             >=2017.4.17   runtime
# (PySocks and cryptography are optional extras)

# Each dependency dict:
# {project_name, name, platform, requirements, latest_stable, latest,
#  deprecated, outdated, filepath, kind, optional, normalized_licenses[]}
```

### Search packages (API key required)

```python
import json, os

key = os.environ.get('LIBRARIES_IO_API_KEY', '')
url = f"https://libraries.io/api/search?q=http+client&platforms=Pypi&per_page=10&api_key={key}"
results = json.loads(http_get(url))  # list of project dicts, same shape as project endpoint
for r in results:
    print(r['name'], r['rank'], r['dependents_count'])
```

Search parameters:

| Parameter | Values | Notes |
|---|---|---|
| `q` | any string | URL-encode spaces as `+` |
| `platforms` | `Pypi`, `NPM`, `Cargo`, `Rubygems`, `Maven`, `NuGet`, etc. | Case-sensitive. Omit for all platforms |
| `languages` | `Python`, `JavaScript`, `Rust`, `Ruby`, etc. | Optional filter |
| `licenses` | `MIT`, `Apache-2.0`, `GPL-3.0`, etc. | Optional filter |
| `keywords` | comma-separated | Optional filter |
| `sort` | `rank`, `stars`, `dependents_count`, `dependent_repos_count`, `latest_release_published_at`, `contributions_count`, `created_at` | Default: `rank` |
| `per_page` | 1–100 (default 30) | |
| `page` | integer | 1-indexed |

### All platforms and counts (no key required)

```python
import json

platforms = json.loads(http_get("https://libraries.io/api/platforms"))
# Returns list of 31 platform dicts
for p in platforms:
    print(f"{p['name']}: {p['project_count']:,} projects")
# Confirmed output (2026-04-18):
# NPM: 5,610,617 projects
# Pypi: 815,927 projects
# Maven: 801,455 projects
# Go: 746,949 projects
# NuGet: 637,571 projects
# Packagist: 489,543 projects
# Cargo: 268,817 projects
# Rubygems: 196,782 projects
# CocoaPods: 104,659 projects
# Pub: 80,565 projects
# ... (31 total)

# Each platform dict: {name, project_count, homepage, color,
#                      default_language, package_manager_url}
```

### Parallel fetch for multiple packages

```python
import json
from concurrent.futures import ThreadPoolExecutor

def fetch_pkg(platform_name):
    platform, name = platform_name
    return json.loads(http_get(f"https://libraries.io/api/{platform}/{name}"))

pkgs = [("pypi", "requests"), ("pypi", "httpx"), ("pypi", "aiohttp")]
with ThreadPoolExecutor(max_workers=3) as ex:
    results = list(ex.map(fetch_pkg, pkgs))
for r in results:
    print(r['name'], r['rank'], r['dependents_count'])
# CAUTION: unauthenticated limit is 10 req/hour — parallel fetches burn it fast
# Add api_key param when doing bulk work
```

### Rate limit check before bulk work

```python
import json, urllib.request

req = urllib.request.Request("https://libraries.io/api/pypi/requests",
                             headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=20) as r:
    remaining = r.headers.get("X-RateLimit-Remaining")
    limit      = r.headers.get("X-RateLimit-Limit")
    reset_secs = r.headers.get("X-RateLimit-Reset")   # seconds until reset
    print(f"Rate limit: {remaining}/{limit} remaining, resets in {reset_secs}s")
    data = json.loads(r.read().decode())
```

## URL reference

### Endpoints (all base URL: `https://libraries.io/api`)

| Endpoint | Auth | Notes |
|---|---|---|
| `GET /platforms` | No | 31 platforms with project counts |
| `GET /{platform}/{name}` | No | Full project metadata + all versions |
| `GET /{platform}/{name}/{version}/dependencies` | No | Project metadata + `dependencies[]` for one version |
| `GET /{platform}/{name}/dependents` | No | Returns `{"message":"Disabled for performance reasons"}` |
| `GET /search?q=...&api_key=KEY` | **Yes** | Full-text search across packages |

### Platform identifiers (case-sensitive in URLs)

```
Pypi  NPM  Maven  Go  NuGet  Packagist  Cargo  Rubygems  CocoaPods  Pub
Bower  Clojars  CPAN  CRAN  Hackage  Hex  Homebrew  Julia  Meteor
Nimble  Puppet  PyPI  Racket  SwiftPM  Wordpress
```

### Rate limits

| Mode | Limit | Window |
|---|---|---|
| Unauthenticated | 10 req | per hour (per IP) |
| API key (free tier) | 60 req | per minute |

Rate limit headers on every response:
- `X-RateLimit-Limit` — total allowed
- `X-RateLimit-Remaining` — calls left
- `X-RateLimit-Reset` — seconds until window resets
- `Retry-After` — same as Reset, seconds to wait after 429

## Gotchas

- **10 req/hour unauthenticated is very low.** Even basic exploration burns through it quickly. Get a free API key at `https://libraries.io/account` — the free tier allows 60 req/min. Pass as `?api_key=KEY` query param.

- **Invalid API key returns HTTP 403 `Forbidden` (plain text), not JSON.** Wrap calls in try/except and check `Content-Type` before parsing:
  ```python
  try:
      data = json.loads(http_get(url))
  except Exception as e:
      print("API error (bad key or rate limited):", e)
  ```

- **Search endpoint always requires API key.** `GET /api/search` without a key returns `HTTP 403 {"error":"Error 403, you don't have permissions for this operation."}` — no anonymous fallback.

- **Dependents endpoint is disabled.** `GET /api/{platform}/{name}/dependents` returns `HTTP 200 {"message":"Disabled for performance reasons"}` for all packages. Use `dependents_count` and `dependent_repos_count` fields from the project endpoint instead.

- **`versions[]` array is sorted oldest-first.** `data['versions'][0]` is the first published version; `data['versions'][-1]` is the most recent. `latest_release_number` is more reliable than indexing `versions[-1]`.

- **Platform names are case-sensitive in URLs.** Use `pypi` (lowercase) in the URL path: `https://libraries.io/api/pypi/requests`. The `platforms` endpoint returns names like `"Pypi"` and `"NPM"` but the URL path must be lowercase (`pypi`, `npm`).

- **`latest_stable_release_number` can differ from `latest_release_number`.** Pre-releases (alpha, beta, rc) increment `latest_release_number` but not `latest_stable_release_number`. Use `latest_stable_release_number` for production dependency checks.

- **`rank` is Libraries.io's composite score** — lower number = more popular. `requests` ranks 32 on Pypi (2026-04-18). It combines dependents count, stars, and other signals; it is not a simple sort position.

- **`http_get` from helpers.py uses urllib and may hit SSL cert errors** on some systems. Use `requests` library directly if you see `[SSL: CERTIFICATE_VERIFY_FAILED]`:
  ```python
  import requests, json
  data = requests.get("https://libraries.io/api/pypi/requests", timeout=20).json()
  ```

- **`X-RateLimit-Reset` is seconds-until-reset, not a Unix timestamp.** When rate limited (HTTP 429), `Retry-After` also gives seconds to wait — typically 3,300–3,600 seconds (close to 1 hour).

- **Dependencies `kind` field distinguishes runtime vs extras.** Runtime dependencies have `kind: "runtime"`. Optional extras have `kind` set to the extra name string (e.g., `"extra == 'socks'"`). Filter with `dep['optional'] == False` to get only required dependencies.
