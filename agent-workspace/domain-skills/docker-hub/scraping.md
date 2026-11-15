# Docker Hub - Repo Pulls and Stars, Tag List with Digests and Sizes (official Hub API v2)

Field-tested against hub.docker.com on 2026-11-03 using a Browser Use cloud browser, logged out. Every call is a same-origin `fetch()` from a hub.docker.com tab. No CAPTCHA, challenge or 429 across about 100 calls; the only refusals were the HTTP 403s of the logged-out paging cap (see Gotchas).

robots.txt (fetched 2026-11-03 in the browser): hub.docker.com is `User-agent: *` / `Disallow:` (empty, everything allowed); the blocks only call the official Docker Hub API (https://docs.docker.com/reference/api/hub/latest/) under `/v2/namespaces/`.

## Quick summary

- **No scraping.** Four documented JSON endpoints cover the task. No key, no cookies, public repos only:
  - `/v2/namespaces/<ns>/repositories/<repo>` - one repo: `pull_count`, `star_count`, `last_updated`, `date_registered`, description, categories, `storage_size`.
  - `/v2/namespaces/<ns>/repositories/<repo>/tags?page_size=100&page=<n>` - tags with the tag digest, `full_size`, and one entry per platform (`images[]`) with its own digest and size.
  - `/v2/namespaces/<ns>/repositories/<repo>/tags/<tag>` - one tag, same shape.
  - `/v2/namespaces/<ns>/repositories?page_size=100&ordering=pull_count` - public repos in a namespace with pulls and stars (first 100 logged out).
- **Official images live in namespace `library`** (`nginx` = `library/nginx`).
- **Logged-out paging is capped.** A page whose first row is past row 1,000 (tags) or row 100 (namespace repo list) returns HTTP 403 `pagination offset too large for anonymous requests; sign in to page further`. nginx has 1,381 tags; logged out you get the first 1,000. grafana has 195 repos; you get 100. The blocks stop there and say so. Do not reshape queries or page sizes to reach the rest.
- **`page_size` max is 100**; 101 or 1000 are silently cut to 100.
- **Rate limit:** responses carried `X-RateLimit-Limit: 180` (per minute, per the docs) and `X-RateLimit-Remaining`. The blocks run one call at a time, pause 0.5 s (120/min), sleep until `X-RateLimit-Reset` when fewer than 5 calls remain, retry 429/5xx with backoff, and raise on anything else. A failed call never comes back as an empty result.

## What works

All blocks share the same helpers: `on_api_tab()` opens `https://hub.docker.com/robots.txt` once (a tiny same-origin page, so `fetch()` needs no CORS) and later blocks reuse it. `get(path)` starts a `fetch()` of `https://hub.docker.com/v2/namespaces/<path>` in that tab, polls for the answer, and reads big bodies back in 500 KB slices. It returns parsed JSON, `None` on 404, raises `AnonymousCap` on the logged-out paging limit, and raises on anything else after retries.

### 1. Pulls and stars for a list of repos (browser)

```python
import json, time, urllib.parse

REPOS = ["nginx", "library/python", "grafana/grafana", "zzqx-no-such-user-98712/nothing"]

API = "https://hub.docker.com/v2/namespaces/"
PACE = 0.5         # seconds between calls (120/min); the API reports a limit of 180/min
MAX_WAIT = 120     # longest wait this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab

class AnonymousCap(Exception):
    """HTTP 403 'pagination offset too large for anonymous requests': logged-out paging ends here."""

def on_api_tab():
    """All calls run as same-origin fetch() in a logged-out hub.docker.com tab; reuse it if already there."""
    try:
        if js("location.href") == "https://hub.docker.com/robots.txt":
            return
    except Exception:
        pass
    new_tab("https://hub.docker.com/robots.txt")   # tiny page on the API host
    wait_for_load()

START_JS = """(() => { window.__dh = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__dh = {status: r.status, len: t.length, body: t,
      ra: r.headers.get('retry-after'), rem: r.headers.get('x-ratelimit-remaining'), reset: r.headers.get('x-ratelimit-reset')}; })
    .catch(e => { window.__dh = {status: 0, len: 0, err: String(e), body: ''}; });
  return 1; })()"""
META_JS = "window.__dh && {status: window.__dh.status, len: window.__dh.len, ra: window.__dh.ra, rem: window.__dh.rem, reset: window.__dh.reset, err: window.__dh.err}"

def get(path, tries=4):
    """Serial GET of hub.docker.com/v2/namespaces/<path>. Parsed JSON, None on 404, AnonymousCap on the
    logged-out paging limit. Retries 429/5xx with backoff, then raises: a failure never looks like an empty result."""
    url = API + path
    for attempt in range(tries):
        js(START_JS % json.dumps(url))   # fetch runs in the page; poll so slow answers do not hit js()'s timeout
        t0 = time.time()
        while not (meta := js(META_JS)):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__dh.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__dh = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            rem, reset = meta.get("rem") or "", meta.get("reset") or ""
            if rem.isdigit() and int(rem) < 5 and reset.isdigit():
                wait = int(reset) - time.time() + 1
                if wait > MAX_WAIT:
                    raise RuntimeError(f"rate limit resets in {wait:.0f} s (> {MAX_WAIT} s); stopping")
                time.sleep(max(0, wait))
            return json.loads(body)
        if status == 404:
            return None
        if status == 403 and "anonymous" in body:
            raise AnonymousCap(body[:200])
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('err') or body[:200]!r}; stopping")
        ra = meta.get("ra") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def split(repo):
    """'nginx' -> ('library', 'nginx'); 'grafana/grafana' -> ('grafana', 'grafana')."""
    ns, _, name = repo.strip().lower().rpartition("/")
    return ns or "library", name

def repo_path(ns, name):
    return f"{urllib.parse.quote(ns)}/repositories/{urllib.parse.quote(name)}"

def hub_url(ns, name):
    return f"https://hub.docker.com/_/{name}" if ns == "library" else f"https://hub.docker.com/r/{ns}/{name}"

on_api_tab()
rows = []
for repo in REPOS:
    ns, name = split(repo)
    d = get(repo_path(ns, name))
    if d is None:
        print(f"{repo}: not found (HTTP 404)")
        continue
    rows.append({
        "repo": f"{ns}/{name}", "url": hub_url(ns, name),
        "pulls": d["pull_count"], "stars": d["star_count"],
        "last_updated": d.get("last_updated"), "registered": d.get("date_registered"),
        "description": d.get("description"), "status": d.get("status_description"),
        "categories": [c["name"] for c in d.get("categories") or []],
        "storage_bytes": d.get("storage_size"), "content_types": d.get("content_types"),
    })
for r in rows:
    print(f"{r['repo']:<18} pulls {r['pulls']:>15,}  stars {r['stars']:>6,}  updated {(r['last_updated'] or '')[:10]}  {r['url']}")
print(json.dumps(rows[0], indent=1))
```

Output observed on 2026-11-03:

```text
zzqx-no-such-user-98712/nothing: not found (HTTP 404)
library/nginx      pulls  13,549,006,554  stars 21,416  updated 2026-11-03  https://hub.docker.com/_/nginx
library/python     pulls   9,546,144,727  stars 10,543  updated 2026-11-02  https://hub.docker.com/_/python
grafana/grafana    pulls   5,377,272,183  stars  3,593  updated 2026-10-27  https://hub.docker.com/r/grafana/grafana
{
 "repo": "library/nginx",
 "url": "https://hub.docker.com/_/nginx",
 "pulls": 13549006554,
 "stars": 21416,
 "last_updated": "2026-11-03T04:52:35.923567Z",
 "registered": "2014-06-05T19:14:45Z",
 "description": "Official build of Nginx.",
 "status": "active",
 "categories": [
  "Web servers"
 ],
 "storage_bytes": 258964254730,
 "content_types": [
  "unrecognized",
  "image"
 ]
}
```

### 2. All tags of a repo with digests and sizes (browser)

One row per tag: the tag digest (what `docker pull <repo>@sha256:...` pins) plus one entry per platform with that platform's manifest digest and compressed size. Stops at the logged-out 1,000-row cap and reports it.

```python
import json, time, urllib.parse

REPOS = ["hello-world", "nginx"]
PAGE_SIZE = 100    # server maximum; larger values are silently cut to 100

API = "https://hub.docker.com/v2/namespaces/"
PACE = 0.5         # seconds between calls (120/min); the API reports a limit of 180/min
MAX_WAIT = 120     # longest wait this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab

class AnonymousCap(Exception):
    """HTTP 403 'pagination offset too large for anonymous requests': logged-out paging ends here."""

def on_api_tab():
    """All calls run as same-origin fetch() in a logged-out hub.docker.com tab; reuse it if already there."""
    try:
        if js("location.href") == "https://hub.docker.com/robots.txt":
            return
    except Exception:
        pass
    new_tab("https://hub.docker.com/robots.txt")   # tiny page on the API host
    wait_for_load()

START_JS = """(() => { window.__dh = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__dh = {status: r.status, len: t.length, body: t,
      ra: r.headers.get('retry-after'), rem: r.headers.get('x-ratelimit-remaining'), reset: r.headers.get('x-ratelimit-reset')}; })
    .catch(e => { window.__dh = {status: 0, len: 0, err: String(e), body: ''}; });
  return 1; })()"""
META_JS = "window.__dh && {status: window.__dh.status, len: window.__dh.len, ra: window.__dh.ra, rem: window.__dh.rem, reset: window.__dh.reset, err: window.__dh.err}"

def get(path, tries=4):
    """Serial GET of hub.docker.com/v2/namespaces/<path>. Parsed JSON, None on 404, AnonymousCap on the
    logged-out paging limit. Retries 429/5xx with backoff, then raises: a failure never looks like an empty result."""
    url = API + path
    for attempt in range(tries):
        js(START_JS % json.dumps(url))   # fetch runs in the page; poll so slow answers do not hit js()'s timeout
        t0 = time.time()
        while not (meta := js(META_JS)):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__dh.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__dh = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            rem, reset = meta.get("rem") or "", meta.get("reset") or ""
            if rem.isdigit() and int(rem) < 5 and reset.isdigit():
                wait = int(reset) - time.time() + 1
                if wait > MAX_WAIT:
                    raise RuntimeError(f"rate limit resets in {wait:.0f} s (> {MAX_WAIT} s); stopping")
                time.sleep(max(0, wait))
            return json.loads(body)
        if status == 404:
            return None
        if status == 403 and "anonymous" in body:
            raise AnonymousCap(body[:200])
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('err') or body[:200]!r}; stopping")
        ra = meta.get("ra") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def split(repo):
    """'nginx' -> ('library', 'nginx'); 'grafana/grafana' -> ('grafana', 'grafana')."""
    ns, _, name = repo.strip().lower().rpartition("/")
    return ns or "library", name

def repo_path(ns, name):
    return f"{urllib.parse.quote(ns)}/repositories/{urllib.parse.quote(name)}"

def tag_row(t):
    """Flatten one tag. 'unknown/unknown' images are build attestations, not runnable platforms: counted, not listed."""
    imgs = t.get("images") or []
    plats = [im for im in imgs if im.get("os") != "unknown"]
    return {
        "tag": t["name"], "digest": t.get("digest"), "media_type": t.get("media_type"),
        "full_size": t.get("full_size"), "last_updated": t.get("last_updated"),
        "last_pushed": t.get("tag_last_pushed"), "last_pulled": t.get("tag_last_pulled"), "tag_status": t.get("tag_status"),
        "platforms": [{"platform": "/".join(x for x in (im.get("os"), im.get("architecture"), im.get("variant")) if x),
                       "digest": im.get("digest"), "size": im.get("size"), "last_pushed": im.get("last_pushed")} for im in plats],
        "attestations": len(imgs) - len(plats),
    }

def list_tags(repo):
    """Returns (rows, total, status); status = complete | truncated_anonymous_cap | not_found."""
    ns, name = split(repo)
    rows, seen, total, page = [], set(), None, 1
    while True:
        try:
            d = get(f"{repo_path(ns, name)}/tags?page_size={PAGE_SIZE}&page={page}")
        except AnonymousCap:
            return rows, total, "truncated_anonymous_cap"
        if d is None:
            return rows, total, "not_found"
        total = d["count"]
        for t in d["results"]:
            if t["name"] not in seen:   # order can shift between pages if a tag is pushed mid-run
                seen.add(t["name"])
                rows.append(tag_row(t))
        if not d.get("next"):
            return rows, total, "complete"
        page += 1

def human(n):
    """Bytes in decimal units (1 MB = 10^6 bytes)."""
    if not isinstance(n, int):
        return "-"
    for unit in ("B", "KB", "MB"):
        if n < 1000:
            return f"{n:,.0f} {unit}" if unit == "B" else f"{n:,.1f} {unit}"
        n /= 1000
    return f"{n:,.1f} GB"

on_api_tab()
tags = {}
for repo in REPOS:
    rows, total, status = list_tags(repo)
    tags[repo] = rows
    print(f"{repo}: {len(rows)} of {total} tags, {status}")
    for r in rows[:4]:
        print(f"   {r['tag']:<22} {r['digest']}  {human(r['full_size']):>9}  {len(r['platforms'])} platforms  updated {(r['last_updated'] or '')[:10]}")
r = next(x for x in tags["nginx"] if x["tag"] == "latest")
print("nginx:latest platforms:")
for p in r["platforms"]:
    print(f"   {p['platform']:<16} {p['digest']}  {human(p['size']):>9}")
print("attestation manifests:", r["attestations"])
```

Output observed on 2026-11-03:

```text
hello-world: 10 of 10 tags, complete
   latest                 sha256:c567b231f65614688711a75f31518a064258a51d442117a3e771a3a8fdba78ef     2.4 KB  11 platforms  updated 2026-10-27
   nanoserver-ltsc2025    sha256:e78dec6982395f4f83172fd5473e2f0a3cb00e2f2bfd2c2b8854c2e4ff1aa625   200.0 MB  1 platforms  updated 2026-10-27
   nanoserver-ltsc2022    sha256:8bd18cd3ea467af8a6cc13bb24c6a14ca0df30e04246574607b65bbaa0085770   125.9 MB  1 platforms  updated 2026-10-27
   nanoserver             sha256:4a9014d1ca19c8494fa7e505c165735b3a2dff69723283bca4827d912c9be8f1   200.0 MB  2 platforms  updated 2026-10-27
nginx: 1000 of 1381 tags, truncated_anonymous_cap
   latest                 sha256:5ab5b0b01097420873a3f3330f44248e34a3c2a3e8d5ee30658aeae8cb7435da    63.9 MB  8 platforms  updated 2026-10-30
   trixie-perl            sha256:3921681524c54b4cbbeed5837fd1b844efc827a2cf4989ad5edc69ce3f264596    76.1 MB  8 platforms  updated 2026-11-03
   stable-trixie-perl     sha256:eda5a512e96bef6b359d3edaabe2d31300d1566f8f9e2a6335ce44974185ebc3    75.8 MB  8 platforms  updated 2026-11-03
   stable-perl            sha256:eda5a512e96bef6b359d3edaabe2d31300d1566f8f9e2a6335ce44974185ebc3    75.8 MB  8 platforms  updated 2026-11-03
nginx:latest platforms:
   linux/amd64      sha256:8e0328743c8e52ead9fac9c198d0893d63cd38e41b1d9ea629e092a8ac229a93    63.9 MB
   linux/ppc64le    sha256:95585e33abbbff85858c7a593970dc30fad5a4f617dfbb469da07e03156257e0    68.2 MB
   linux/386        sha256:e9063f3d18e2741f5a1e6f0deb475a36df1f88bb23d3123b85b0b1e485ee73ad    64.4 MB
   linux/s390x      sha256:a5ed35eb3f3a22fe6f40999c40dde01fe76bc831305ec88a8701ad2344d1dac2    61.6 MB
   linux/arm/v7     sha256:f4d5905d8df10683a428863fe066e3b4b25f227977891b0ea3eeb834e17f56ed    53.2 MB
   linux/arm64/v8   sha256:2e2921b6d12e0fbc8fb4374cb945d2bcac0f5cd304bb6c55d2f957c34cc0e720    62.2 MB
   linux/arm/v5     sha256:17a7aefb10a7b333913d311e8268e38f710f3faf78d0969c9c7848ffc8f824bc    54.9 MB
   linux/riscv64    sha256:22b23e530247ce19c5c6328e0e04d834263ef087b02792d666c922874db098a8    58.7 MB
attestation manifests: 8
```

### 3. One tag: digest to pin, per-platform digests and sizes (browser)

```python
import json, time, urllib.parse

REPO = "nginx"
TAGS = ["latest", "alpine", "1.31.8", "zzqx-no-such-tag"]

API = "https://hub.docker.com/v2/namespaces/"
PACE = 0.5         # seconds between calls (120/min); the API reports a limit of 180/min
MAX_WAIT = 120     # longest wait this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab

class AnonymousCap(Exception):
    """HTTP 403 'pagination offset too large for anonymous requests': logged-out paging ends here."""

def on_api_tab():
    """All calls run as same-origin fetch() in a logged-out hub.docker.com tab; reuse it if already there."""
    try:
        if js("location.href") == "https://hub.docker.com/robots.txt":
            return
    except Exception:
        pass
    new_tab("https://hub.docker.com/robots.txt")   # tiny page on the API host
    wait_for_load()

START_JS = """(() => { window.__dh = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__dh = {status: r.status, len: t.length, body: t,
      ra: r.headers.get('retry-after'), rem: r.headers.get('x-ratelimit-remaining'), reset: r.headers.get('x-ratelimit-reset')}; })
    .catch(e => { window.__dh = {status: 0, len: 0, err: String(e), body: ''}; });
  return 1; })()"""
META_JS = "window.__dh && {status: window.__dh.status, len: window.__dh.len, ra: window.__dh.ra, rem: window.__dh.rem, reset: window.__dh.reset, err: window.__dh.err}"

def get(path, tries=4):
    """Serial GET of hub.docker.com/v2/namespaces/<path>. Parsed JSON, None on 404, AnonymousCap on the
    logged-out paging limit. Retries 429/5xx with backoff, then raises: a failure never looks like an empty result."""
    url = API + path
    for attempt in range(tries):
        js(START_JS % json.dumps(url))   # fetch runs in the page; poll so slow answers do not hit js()'s timeout
        t0 = time.time()
        while not (meta := js(META_JS)):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__dh.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__dh = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            rem, reset = meta.get("rem") or "", meta.get("reset") or ""
            if rem.isdigit() and int(rem) < 5 and reset.isdigit():
                wait = int(reset) - time.time() + 1
                if wait > MAX_WAIT:
                    raise RuntimeError(f"rate limit resets in {wait:.0f} s (> {MAX_WAIT} s); stopping")
                time.sleep(max(0, wait))
            return json.loads(body)
        if status == 404:
            return None
        if status == 403 and "anonymous" in body:
            raise AnonymousCap(body[:200])
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('err') or body[:200]!r}; stopping")
        ra = meta.get("ra") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def split(repo):
    """'nginx' -> ('library', 'nginx'); 'grafana/grafana' -> ('grafana', 'grafana')."""
    ns, _, name = repo.strip().lower().rpartition("/")
    return ns or "library", name

def repo_path(ns, name):
    return f"{urllib.parse.quote(ns)}/repositories/{urllib.parse.quote(name)}"

on_api_tab()
ns, name = split(REPO)
ref = name if ns == "library" else f"{ns}/{name}"
for tag in TAGS:
    t = get(f"{repo_path(ns, name)}/tags/{urllib.parse.quote(tag)}")
    if t is None:
        print(f"{ref}:{tag}: not found (HTTP 404)")
        continue
    plats = [im for im in t.get("images") or [] if im.get("os") != "unknown"]
    print(f"{ref}:{tag}  pin as {ref}@{t['digest']}")
    print(f"   {t['media_type']}, pushed {t['tag_last_pushed'][:16]}, full_size {t['full_size']:,} B, {len(plats)} platforms")
    for im in plats[:3]:
        plat = "/".join(x for x in (im["os"], im["architecture"], im.get("variant")) if x)
        print(f"   {plat:<16} {im['digest']}  {im['size']:,} B")
```

Output observed on 2026-11-03:

```text
nginx:latest  pin as nginx@sha256:5ab5b0b01097420873a3f3330f44248e34a3c2a3e8d5ee30658aeae8cb7435da
   application/vnd.oci.image.index.v1+json, pushed 2026-10-30T22:51, full_size 63,911,306 B, 8 platforms
   linux/amd64      sha256:8e0328743c8e52ead9fac9c198d0893d63cd38e41b1d9ea629e092a8ac229a93  63,911,306 B
   linux/ppc64le    sha256:95585e33abbbff85858c7a593970dc30fad5a4f617dfbb469da07e03156257e0  68,241,179 B
   linux/386        sha256:e9063f3d18e2741f5a1e6f0deb475a36df1f88bb23d3123b85b0b1e485ee73ad  64,446,937 B
nginx:alpine  pin as nginx@sha256:785835ea65db4bba6f021acc0f3be91b0fef76a53fe41f8588c6698d2aed0606
   application/vnd.oci.image.index.v1+json, pushed 2026-10-28T22:51, full_size 26,329,254 B, 8 platforms
   linux/amd64      sha256:2db7d28517d1fba17c2da3210395f7be11a11b419246ad0da2edf782af72f367  26,329,254 B
   linux/ppc64le    sha256:70a21d46f8df2d17241a6671cf55f6b6796b45f9297fc92bd630b3b7534a3bcd  26,699,231 B
   linux/386        sha256:155035959fcc4f1ff1409803cc9e1b61ca0953ca60729229eb05891f17954b46  25,661,268 B
nginx:1.31.8  pin as nginx@sha256:5ab5b0b01097420873a3f3330f44248e34a3c2a3e8d5ee30658aeae8cb7435da
   application/vnd.oci.image.index.v1+json, pushed 2026-10-30T22:51, full_size 63,911,306 B, 8 platforms
   linux/amd64      sha256:8e0328743c8e52ead9fac9c198d0893d63cd38e41b1d9ea629e092a8ac229a93  63,911,306 B
   linux/ppc64le    sha256:95585e33abbbff85858c7a593970dc30fad5a4f617dfbb469da07e03156257e0  68,241,179 B
   linux/386        sha256:e9063f3d18e2741f5a1e6f0deb475a36df1f88bb23d3123b85b0b1e485ee73ad  64,446,937 B
nginx:zzqx-no-such-tag: not found (HTTP 404)
```

### 4. Most-pulled repos in a namespace (browser)

Logged out, the namespace list stops after its first 100 rows, so this asks the server to sort by pulls and reads one page. The direction of `ordering` is checked, because today it is the reverse of the spec (see Gotchas).

```python
import json, time, urllib.parse

NAMESPACE = "grafana"
TOP = 10

API = "https://hub.docker.com/v2/namespaces/"
PACE = 0.5         # seconds between calls (120/min); the API reports a limit of 180/min
MAX_WAIT = 120     # longest wait this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab

class AnonymousCap(Exception):
    """HTTP 403 'pagination offset too large for anonymous requests': logged-out paging ends here."""

def on_api_tab():
    """All calls run as same-origin fetch() in a logged-out hub.docker.com tab; reuse it if already there."""
    try:
        if js("location.href") == "https://hub.docker.com/robots.txt":
            return
    except Exception:
        pass
    new_tab("https://hub.docker.com/robots.txt")   # tiny page on the API host
    wait_for_load()

START_JS = """(() => { window.__dh = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__dh = {status: r.status, len: t.length, body: t,
      ra: r.headers.get('retry-after'), rem: r.headers.get('x-ratelimit-remaining'), reset: r.headers.get('x-ratelimit-reset')}; })
    .catch(e => { window.__dh = {status: 0, len: 0, err: String(e), body: ''}; });
  return 1; })()"""
META_JS = "window.__dh && {status: window.__dh.status, len: window.__dh.len, ra: window.__dh.ra, rem: window.__dh.rem, reset: window.__dh.reset, err: window.__dh.err}"

def get(path, tries=4):
    """Serial GET of hub.docker.com/v2/namespaces/<path>. Parsed JSON, None on 404, AnonymousCap on the
    logged-out paging limit. Retries 429/5xx with backoff, then raises: a failure never looks like an empty result."""
    url = API + path
    for attempt in range(tries):
        js(START_JS % json.dumps(url))   # fetch runs in the page; poll so slow answers do not hit js()'s timeout
        t0 = time.time()
        while not (meta := js(META_JS)):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__dh.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__dh = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            rem, reset = meta.get("rem") or "", meta.get("reset") or ""
            if rem.isdigit() and int(rem) < 5 and reset.isdigit():
                wait = int(reset) - time.time() + 1
                if wait > MAX_WAIT:
                    raise RuntimeError(f"rate limit resets in {wait:.0f} s (> {MAX_WAIT} s); stopping")
                time.sleep(max(0, wait))
            return json.loads(body)
        if status == 404:
            return None
        if status == 403 and "anonymous" in body:
            raise AnonymousCap(body[:200])
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('err') or body[:200]!r}; stopping")
        ra = meta.get("ra") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def top_by_pulls(ns):
    """One page of 100 repos sorted by pulls, most first. Today 'ordering=pull_count' returns the most-pulled
    first, the reverse of the spec; if that ever flips, ask once for '-pull_count'. Returns (repos, total) or None."""
    for order in ("pull_count", "-pull_count"):
        d = get(f"{urllib.parse.quote(ns)}/repositories?page_size=100&page=1&ordering={order}")
        if d is None:
            return None
        pulls = [r["pull_count"] for r in d["results"]]
        if pulls == sorted(pulls, reverse=True):
            return d["results"], d["count"]
    raise RuntimeError("neither ordering returned repos most-pulled first; stopping")

on_api_tab()
found = top_by_pulls(NAMESPACE)
if found is None:
    raise SystemExit(f"{NAMESPACE}: namespace not found (HTTP 404)")
repos, total = found
print(f"{NAMESPACE}: {total} public repos; top {min(TOP, len(repos))} by pulls")
for r in repos[:TOP]:
    print(f"   {r['name']:<28} pulls {r['pull_count']:>15,}  stars {r['star_count']:>5,}  updated {(r.get('last_updated') or '')[:10]}")
```

Output observed on 2026-11-03:

```text
grafana: 195 public repos; top 10 by pulls
   grafana                      pulls   5,377,272,183  stars 3,593  updated 2026-10-27
   loki                         pulls   4,818,541,514  stars   336  updated 2026-11-03
   promtail                     pulls   2,979,830,170  stars   217  updated 2026-05-13
   synthetic-monitoring-agent   pulls   1,061,637,999  stars     8  updated 2026-11-02
   grafana-image-renderer       pulls     900,975,364  stars    35  updated 2026-10-28
   alloy                        pulls     487,253,828  stars    29  updated 2026-10-28
   agent                        pulls     473,586,340  stars    26  updated 2026-03-25
   fluent-bit-plugin-loki       pulls     448,649,104  stars    10  updated 2026-10-20
   mimir                        pulls     386,831,365  stars    24  updated 2026-11-03
   loki-canary                  pulls     158,728,075  stars     4  updated 2026-11-03
```

## Fields

Repo (`/v2/namespaces/<ns>/repositories/<repo>`):

| Key | Notes |
|---|---|
| `pull_count` | int, all-time pulls |
| `star_count` | int |
| `last_updated` | last push to any tag (UTC ISO) |
| `last_modified` | last change to repo metadata (description etc.), not a push |
| `date_registered` | repo creation |
| `description`, `full_description` | short text and the full README Markdown |
| `status_description` | `active` for live repos |
| `categories` | list of `{name, slug}`; empty for many repos |
| `storage_size` | bytes stored for the repo (grafana/grafana: 31,243,536,648,882) |
| `media_types`, `content_types` | manifest media types seen, and `image` / other artifact kinds |

Tag (`.../tags` rows and `.../tags/<tag>`):

| Key | Notes |
|---|---|
| `name` | tag |
| `digest` | digest of what the tag points to: an image index for multi-platform tags; use it in `repo@sha256:...` |
| `media_type` | e.g. `application/vnd.oci.image.index.v1+json` |
| `full_size` | compressed bytes of one image (on nginx:latest it equals the linux/amd64 entry), not the sum of all platforms |
| `last_updated`, `tag_last_pushed`, `tag_last_pulled` | UTC ISO |
| `tag_status` | `active` / `inactive`; per the docs, whether the tag was pushed or pulled in the past month |
| `images[]` | one per manifest: `os`, `architecture`, `variant`, `digest` (platform manifest digest), `size` (compressed bytes), `status`, `last_pushed`, `last_pulled` |

## Gotchas

- **Anonymous caps: 1,000 tags, 100 namespace repos.** Tags at `page_size` 10/25/50/100: page 100/40/20/10 answered 200, the next page 403 with `{"message":"pagination offset too large for anonymous requests; sign in to page further"}`. The grafana repo list at `page_size` 10/50/100 stopped after page 10/2/1 the same way. The `count` field still reports the full total (nginx: 1,381 tags, grafana: 195 repos). Block 2 returns what it got with status `truncated_anonymous_cap`. Logged-in access is out of scope for this skill.
- **`unknown/unknown` images are attestations.** nginx:latest lists 16 `images`: 8 real platforms plus 8 entries with `os`/`architecture` `unknown` (about 2.8 MB each). Docker's docs say attestation manifests get platform `unknown/unknown` so runtimes never run them (https://docs.docker.com/build/metadata/attestations/attestation-storage/). Blocks 2 and 3 count them but do not list them as platforms.
- **Tag digest vs platform digest.** The tag `digest` is the multi-platform index; each `images[].digest` is one platform's manifest. Pin with the tag digest unless you need one platform.
- **Tag order is not a contract.** Rows come roughly newest first, but page 1 at `page_size=100` began with `latest` while three pages at `page_size=10` did not; the same request twice gave the same order. Keep one `page_size` for a whole run and dedupe by tag name (block 2 does).
- **`ordering` on the namespace list is inverted vs the spec.** `ordering=pull_count` returned the most-pulled repos first (library: nginx; grafana: grafana), `ordering=-pull_count` the least (grafana: repos with 0 pulls first); `-last_updated` on library returned the oldest first. Block 4 checks the direction of what came back instead of trusting the name.
- **`page_size` is capped at 100** with no error; `next` links then carry `page_size=100`.
- **Missing things are 404s:** an unknown repo returns `{"message":"object not found","errinfo":{}}`; an unknown tag returns `httperror 404: tag '<tag>' not found`.
- **Legacy paths** `/v2/repositories/<ns>/<repo>/` and `/v2/repositories/<ns>/<repo>/tags` answered with the same data, but the current spec documents the `/v2/namespaces/...` form; the blocks use that.
- **Rate-limit headers:** the answers checked (200 and 404) carried `X-RateLimit-Limit: 180`, `X-RateLimit-Remaining` and `X-RateLimit-Reset` (unix seconds). The docs say a 429 comes with `Retry-After` in seconds and that these limits are separate from image pull limits. Do not cycle IPs or sessions to get past either.
- **Plain HTTP works too:** `curl https://hub.docker.com/v2/namespaces/library/repositories/hello-world` answered 200 from the authoring machine, so the same paths work without a browser.

## What does not work

- **More than 1,000 tags or 100 namespace repos logged out:** blocked by the anonymous caps above. Do not reshape queries (other `ordering` values, other page sizes) to reach the rest.
- **Private repos:** need a Docker account and token; not covered.
- **Layer lists:** the spec's `image` schema has a `layers` array, but tag-list answers today had no `layers` key.
- **Pull counts per tag or over time:** the API gives one all-time `pull_count` per repo only.
