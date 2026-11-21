# crates.io - Look Up a Rust Crate's Latest Stable Version, Downloads, Repository and Most-Downloaded Dependents, or Search Crates by Downloads (JSON API and sparse index, no key)

Field-tested against crates.io on 2026-11-20 (US Pacific afternoon; 23:27-23:37 UTC) using a fresh Browser Use cloud browser (logged out; one session, 23:30-23:37 UTC) plus Python `urllib` and `curl` from a Linux machine. 19 browser page loads (the Data Access Policy 5 times, the usage policy, robots.txt, https://index.crates.io/robots.txt, the tokio crate page and the serde index file 2 times each, the publishing rate-limits page 3 times, the serde dependents page once) and 69 in-page `fetch()` calls (block 1 ran 3 times, block 2 twice), 69 curl calls and 62 urllib calls to crates.io, index.crates.io and static.crates.io, all serial and at least 1 s apart (block 3's index calls 0.2 s apart). Every call was HTTP 200 except the deliberate probes below: HTTP 403 (no User-Agent, or curl's default one), HTTP 404 (unknown crate, an index path spelled with `-` or upper case, robots.txt on index.crates.io and static.crates.io), HTTP 400 (`per_page=101`, a repeated `sort`), HTTP 304 (conditional GETs on the index) and a browser `fetch()` of index.crates.io that CORS blocked. curl timed answers at 0.16-0.59 s. No 429, no challenge, no key, no login. Block 1's output below is its third run, block 2's its second, block 3's its second (empty cache both times), block 4's its second (after a quoting fix). An independent verifier re-ran all four blocks verbatim at 23:40-23:45 UTC in a separate cloud browser and from the same machine: every block ran, and the only differences were the timestamps, dependent counts (serde 142,761 -> 142,769) and today's partial download totals.

robots.txt (checked 2026-11-20, curl, the cloud browser and `urllib.robotparser`): https://crates.io/robots.txt is `# allow crawling everything by default`, `User-agent: *`, `Disallow:` (empty), with no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*` and may fetch `/api/v1/`. https://index.crates.io/robots.txt and https://static.crates.io/robots.txt answer HTTP 404 (an S3 `NoSuchKey` XML page): no rules, so everything is allowed (block 3 checks all 11 agents on all 3 hosts). Terms: the Data Access Policy https://crates.io/data-access says to try the sources "in the order below": the sparse index ("No rate limits are required to use data from the sparse crate index."), crate files and RSS on static.crates.io ("No rate limits apply to static.crates.io at present."), the database dumps ("updated every 24 hours"), and last the API, which "you are welcome to use ... provided you abide by the following limits: A maximum of 1 request per second, and A `user-agent` header that identifies your application. We strongly suggest providing a way for us to contact you". The usage policy https://crates.io/policies forbids "excessive automated bulk activity, to place undue burden on our servers through automated means" and impersonation "including through false association with crates.io". The "Rate Limits" page https://crates.io/docs/rate-limits is titled "Publishing Rate Limits" and covers only publishing. No AI/ML, scraping, crawling or non-commercial wording on any of these pages (block 2 checks the quotes). Licence: the pages state none for registry metadata (the usage policy's own text is under CC BY 4.0); each crate's code has its own licence (`license` field), which this skill reports but does not download. Naming: the site writes its name "crates.io", lowercase, and so does this skill; it shows no Rust or Cargo logo. The Rust Foundation trademark policy (https://rustfoundation.org/policy/rust-trademark-policy/) says "the Rust and Cargo word marks can be used with minimal restriction to refer to the Rust programming language and the Cargo package manager" and that they "cannot be used in ways that appear (to a casual observer) official, affiliated, or endorsed by the Rust Project or Rust Foundation". This skill is not affiliated with or endorsed by crates.io, the Rust Project or the Rust Foundation.

## Quick summary

- **No scraping.** `GET https://crates.io/api/v1/crates/tokio?include=downloads,default_version` -> `{"crate": {"name": "tokio", "default_version": "1.54.1", "downloads": 1223086474, "recent_downloads": 322790561, "repository": "https://github.com/tokio-rs/tokio", ...}}` (3.6 KB; serde's is 2.7 KB). `/crates/<name>/versions?sort=semver&per_page=20` lists versions highest first, `/crates/<name>/reverse_dependencies?per_page=50` the dependents, most-downloaded first, `/crates?q=<words>&sort=downloads&per_page=<n>` searches. Version lists also come from the sparse index, `GET https://index.crates.io/to/ki/tokio`: one JSON line per published version. JSON, `Access-Control-Allow-Origin: *` on the API, no key. The crates.io web app reads the same API (block 2 lists the calls the tokio page makes).
- **Answers (block 1, 23:35 UTC; block 3 at 23:36 agrees):** **tokio 1.54.1** (2026-10-21, MIT), 1,223,086,474 downloads, 322,790,561 in the last 90 days, repository https://github.com/tokio-rs/tokio, 83,814 dependents; the most-downloaded with a normal dependency are **hyper, h2, tokio-util, tokio-rustls, reqwest**. **serde 1.0.229** (2026-07-18), 1,750,809,565 downloads, 142,761 dependents. **rustls 0.23.46** is the latest stable, but the highest version is **0.24.0-dev.3** (a pre-release). Search "http client" by downloads: **hyper, rustls, h2, reqwest, tower** (17,768 matches).
- **Ask for the small record.** `/crates/<name>` without `include` is the full record with every version: serde 440,993 bytes. `include=downloads,default_version` is 2,684 bytes but leaves `max_stable_version` null (deprecated in the OpenAPI description) and `max_version` "0.0.0". Take the latest stable from `/versions?sort=semver` (block 1) or the index (block 3), skipping pre-releases and yanked versions.
- **"Depends on it" includes dev-dependencies.** `reverse_dependencies` mixes `kind` `normal`, `dev` and `build`, and `optional` ones: of serde_json's 50 most-downloaded dependents only 9 have a normal dependency (the first 5 of them optional). The blocks keep `kind == "normal"` and mark optional ones. Join `dependencies[].version_id` to `versions[].id` for the dependent's name; the two lists are not in the same order.
- **Rate limit: 1 request per second to the API with an identifying User-Agent** (Data Access Policy); no User-Agent or curl's default one is HTTP 403. The sparse index and static.crates.io have none ("No rate limits are required", "at present"). Blocks 1 and 3 wait 1.1 s after each API call, serial, wait once on 429/5xx (`Retry-After`, else 30 s) and stop above 120 s; block 4 sleeps 1 s between calls. For many crates, use the index or the daily database dump https://static.crates.io/db-dump.tar.gz, not the API.

## What works

### 1. Crate names as a person types them -> latest stable version, downloads, repository, top dependents; and a keyword search by downloads (browser)

`on_crates_tab()` opens the logged-out Data Access Policy page (a JavaScript app, so it waits for the text) and `fetch()` runs same-origin. The browser sends its own User-Agent, as the crates.io web app does; for scripted use, send your own (blocks 3 and 4). `get()` returns parsed JSON on HTTP 200, `None` on 404 (a JSON `errors` body), waits once on 429/5xx and otherwise raises. 3 `fetch()` calls per crate (record, versions, dependents), 2 for an unknown name, 1 for the search: 15 in all.

```python
import json, re, time, urllib.parse
from datetime import datetime, timezone

CRATES = ["serde", "tokio", "rustls", "Serde-JSON", "serde-jason"]  # names as a person types them
SEARCH = ("http client", 5)  # (keyword, how many), sorted by all-time downloads
TOP = 5  # most-downloaded crates that depend on it (normal dependencies only)

SITE = "https://crates.io"
API = SITE + "/api/v1"
PAUSE = 1.1  # Data Access Policy: "A maximum of 1 request per second"

def on_crates_tab():
    """fetch() from a logged-out crates.io page (same origin; the API also sends Access-Control-Allow-Origin: *)."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/data-access")
    wait_for_load()
    for _ in range(20):  # the page is a JavaScript app: wait for the policy text
        if "Data Access Policy" in (js("document.body ? document.body.innerText : ''") or ""):
            return
        time.sleep(0.5)
    raise RuntimeError(f"crates.io did not render its Data Access Policy page (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__c = window.__c || {}; const id = String(Math.random()).slice(2); window.__c[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__c[id] = {status: r.status, type: r.headers.get('content-type') || '',
      retry: r.headers.get('retry-after'), text: await r.text()}; })
    .catch(e => { window.__c[id] = {status: 0, type: '', retry: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__c[%s]; if (v) delete window.__c[%s]; return v; })()"""

def fetch(url):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def get(path):
    """-> parsed JSON, or None on 404 (a JSON {"errors": ...} body). Waits once on 429/5xx or a network error
    (Retry-After seconds, else 30 s; over 120 s stops). Raises on anything else, e.g. 400 or 403."""
    for attempt in range(2):
        r = fetch(API + path)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            wait = float(r["retry"]) if (r["retry"] or "").isdigit() else 30
            if wait > 120:
                raise RuntimeError(f"{path}: server asks to wait {wait:.0f} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] == 404:
        return None
    if r["status"] != 200 or "json" not in r["type"]:
        raise RuntimeError(f"{path}: HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:200]!r}; stopping")
    return json.loads(r["text"])

def stable(num):
    """SemVer: a pre-release has '-' before any '+build' part ('0.24.0-dev.3'); '1.0.0+abc' is stable."""
    return "-" not in num.split("+")[0]

def versions(name):
    """-> (highest non-yanked stable version, highest version overall), semver order, up to 3 pages of 20."""
    q, top = f"/crates/{name}/versions?sort=semver&per_page=20", None
    for _ in range(3):
        d = get(q)
        top = top or (d["versions"] or [None])[0]
        for v in d["versions"]:
            if stable(v["num"]) and not v["yanked"]:
                return v, top
        if not d["meta"].get("next_page"):
            break
        q = f"/crates/{name}/versions" + d["meta"]["next_page"]
    return None, top

on_crates_tab()
now = datetime.now(timezone.utc)
print(f"crates.io API, checked {now:%Y-%m-%d %H:%M} UTC")
for typed in CRATES:
    d = get(f"/crates/{urllib.parse.quote(typed)}?include=downloads,default_version")  # 2.7-3.6 KB, not 441-456 KB (serde, tokio)
    if d is None:
        s = get(f"/crates?q={urllib.parse.quote(typed)}&per_page=3")  # relevance order
        print(f"\n{typed}: no such crate (HTTP 404); search suggests: "
              + (", ".join(c["name"] for c in s["crates"]) or "nothing"))
        continue
    c = d["crate"]
    v, newest = versions(c["name"])
    rd = get(f"/crates/{c['name']}/reverse_dependencies?per_page=50")  # dependents, most-downloaded first (~100 KB)
    names = {x["id"]: x["crate"] for x in rd["versions"]}  # dependencies[].version_id -> dependent crate
    normal = [(names[x["version_id"]], x["downloads"], x["optional"]) for x in rd["dependencies"] if x["kind"] == "normal"]
    print(f"\n{typed} -> {c['name']}: {' '.join((c['description'] or '').split())}")
    print(f"  latest stable {v['num'] if v else 'none'}" + (f" (published {v['created_at'][:10]}, {v['license']})" if v else "")
          + (f"; highest overall {newest['num']}" + ("" if stable(newest["num"]) else " (pre-release)")
             if newest and (not v or newest["num"] != v["num"]) else "")
          + f"; default_version {c['default_version']}")
    print(f"  downloads {c['downloads']:,} all time, {c['recent_downloads']:,} in the last 90 days")
    print(f"  repository {c['repository'] or 'not set'}; page {SITE}/crates/{c['name']}")
    print(f"  {rd['meta']['total']:,} dependents; most-downloaded with a normal dependency "
          f"({len(normal)} of the top {len(rd['dependencies'])}):")
    for n, dl, opt in normal[:TOP]:
        print(f"    {n:<20} {dl:>15,} downloads" + ("  (optional)" if opt else ""))

q, n = SEARCH
s = get(f"/crates?q={urllib.parse.quote(q)}&sort=downloads&per_page={n}")
print(f"\nsearch {q!r}, sorted by all-time downloads: {s['meta']['total']:,} matches")
for c in s["crates"]:
    print(f"  {c['name']:<10} {c['downloads']:>15,} all time {c['recent_downloads']:>13,} last 90 d  "
          f"default {c['default_version']:<9} {c['repository'] or '-'}")
print(f"\nSource: crates.io (https://crates.io) public API, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the third run on 2026-11-20, 23:35 UTC; the runs at 23:30 and 23:31 gave the same numbers, with 142,759 serde dependents):

```text
crates.io API, checked 2026-11-20 23:35 UTC

serde -> serde: A generic serialization/deserialization framework
  latest stable 1.0.229 (published 2026-07-18, MIT OR Apache-2.0); default_version 1.0.229
  downloads 1,750,809,565 all time, 451,883,541 in the last 90 days
  repository https://github.com/serde-rs/serde; page https://crates.io/crates/serde
  142,761 dependents; most-downloaded with a normal dependency (32 of the top 50):
    hashbrown              3,186,298,437 downloads  (optional)
    rand                   2,244,029,666 downloads  (optional)
    rand_chacha            1,713,010,452 downloads  (optional)
    smallvec               1,500,697,911 downloads  (optional)
    bytes                  1,311,161,545 downloads  (optional)

tokio -> tokio: An event-driven, non-blocking I/O platform for writing asynchronous I/O backed applications.
  latest stable 1.54.1 (published 2026-10-21, MIT); default_version 1.54.1
  downloads 1,223,086,474 all time, 322,790,561 in the last 90 days
  repository https://github.com/tokio-rs/tokio; page https://crates.io/crates/tokio
  83,814 dependents; most-downloaded with a normal dependency (29 of the top 50):
    hyper                  1,157,491,530 downloads
    h2                     1,000,465,140 downloads
    tokio-util               978,763,777 downloads
    tokio-rustls             968,949,022 downloads
    reqwest                  939,269,748 downloads

rustls -> rustls: Rustls is a modern TLS library written in Rust.
  latest stable 0.23.46 (published 2026-10-14, Apache-2.0 OR ISC OR MIT); highest overall 0.24.0-dev.3 (pre-release); default_version 0.23.46
  downloads 1,150,882,937 all time, 298,480,817 in the last 90 days
  repository https://github.com/rustls/rustls; page https://crates.io/crates/rustls
  6,220 dependents; most-downloaded with a normal dependency (40 of the top 50):
    tokio-rustls             968,949,022 downloads
    reqwest                  939,269,748 downloads  (optional)
    hyper-rustls             828,709,871 downloads
    quinn-proto              446,411,586 downloads  (optional)
    quinn                    436,240,972 downloads  (optional)

Serde-JSON -> serde_json: A JSON serialization file format
  latest stable 1.0.154 (published 2026-10-11, MIT OR Apache-2.0); default_version 1.0.154
  downloads 1,658,067,727 all time, 454,939,590 in the last 90 days
  repository https://github.com/serde-rs/json; page https://crates.io/crates/serde_json
  123,864 dependents; most-downloaded with a normal dependency (9 of the top 50):
    reqwest                  939,269,748 downloads  (optional)
    icu_provider             795,743,164 downloads  (optional)
    tracing-subscriber       767,626,746 downloads  (optional)
    siphasher                718,815,438 downloads  (optional)
    wasm-bindgen             677,856,943 downloads  (optional)

serde-jason: no such crate (HTTP 404); search suggests: nothing

search 'http client', sorted by all-time downloads: 17,768 matches
  hyper        1,157,491,530 all time   299,909,528 last 90 d  default 1.12.0    https://github.com/hyperium/hyper
  rustls       1,150,882,937 all time   298,480,817 last 90 d  default 0.23.46   https://github.com/rustls/rustls
  h2           1,000,465,140 all time   238,750,484 last 90 d  default 0.4.20    https://github.com/hyperium/h2
  reqwest        939,269,748 all time   279,147,920 last 90 d  default 0.13.5    https://github.com/seanmonstar/reqwest
  tower          865,220,051 all time   255,319,587 last 90 d  default 0.5.3     https://github.com/tower-rs/tower

Source: crates.io (https://crates.io) public API, accessed 20 November 2026 23:35 UTC.
```

### 2. robots.txt, the policy quotes, what the web app calls, and what the API does with mistakes (browser)

8 page loads and 13 in-page `fetch()` calls in the same tab. The last `fetch()` shows that a crates.io page cannot read index.crates.io (no `Access-Control-Allow-Origin` header); a page load of the index file works because it is plain text.

```python
import json, time

SITE = "https://crates.io"
API = SITE + "/api/v1"

START_JS = """(() => { window.__c = window.__c || {}; const id = String(Math.random()).slice(2); window.__c[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__c[id] = {status: r.status, type: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__c[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__c[%s]; if (v) delete window.__c[%s]; return v; })()"""

def raw(path):
    """One in-page GET of API + path (or a full URL). No retries: inspection only. 1.1 s after each call."""
    url = path if path.startswith("https://") else API + path
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1.1)
    return r

def page(url, wait_for=None):
    """Page load; crates.io pages are a JavaScript app, so wait until `wait_for` shows up in the text."""
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    for _ in range(20):
        txt = js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or ""
        if not wait_for or wait_for in txt:
            break
        time.sleep(0.5)
    return st, " ".join(txt.split())

st, txt = page(SITE + "/robots.txt")
print(f"robots.txt HTTP {st}: {txt!r}")
st, txt = page("https://index.crates.io/robots.txt")
print(f"index.crates.io/robots.txt HTTP {st}: {txt[:60]!r}")

st, txt = page(SITE + "/data-access", "Questions")
for needle in ("Please try them in the order below.",
               "No rate limits are required to use data from the sparse crate index.",
               "No rate limits apply to static.crates.io at present.",
               "They are updated every 24 hours.",
               "A maximum of 1 request per second, and",
               "header that identifies your application.",
               "We strongly suggest providing a way for us to contact you"):
    print(f"data-access HTTP {st}: {'found' if needle in txt else 'MISSING'}: {needle!r}")
st, txt = page(SITE + "/policies", "Package Ownership")
for needle in ("is using our servers for any form of excessive automated bulk activity, to place undue burden on our servers through automated means",
               "impersonates any person or entity, including through false association with crates.io"):
    print(f"policies HTTP {st}: {'found' if needle in txt else 'MISSING'}: {needle!r}")
st, txt = page(SITE + "/docs/rate-limits", "Please plan")
print(f"docs/rate-limits HTTP {st}: {'found' if 'Publishing Rate Limits' in txt else 'MISSING'}: 'Publishing Rate Limits' "
      f"(mentions downloads or API reads: {'yes' if ' API ' in txt or 'download' in txt.lower() else 'no'})")

# the crates.io web app reads the same API: list the /api/v1 calls one crate page made
st, txt = page(SITE + "/crates/tokio", "Install")
calls = js("performance.getEntriesByType('resource').map(e => e.name).filter(n => n.includes('/api/v1/'))")
print(f"\n/crates/tokio page HTTP {st}: its own API calls: {[c.replace(SITE, '') for c in calls]}")
print()

def brief(r):
    out = f"HTTP {r['status']} {r['type'].split(';')[0] or '-'} {len(r['text']):,} bytes"
    if "json" not in r["type"]:
        return out + f" {' '.join(r['text'].split())[:70]!r}"
    d = json.loads(r["text"])
    if "errors" in d:
        return out + " " + json.dumps(d["errors"])[:90]
    c = d.get("crate")
    if c:
        return out + " " + json.dumps({k: c.get(k) for k in ("name", "default_version", "max_stable_version", "recent_downloads")})
    if "crates" in d:
        return out + f" total {d['meta']['total']:,}, first {[x['name'] for x in d['crates']]}"
    if "versions" in d:
        return out + f" {[(v['num'], v['yanked']) for v in d['versions']]}"
    return out

for label, path in (
    ("crate, include=downloads,default_version", "/crates/serde?include=downloads,default_version"),
    ("crate, no include (full, every version) ", "/crates/serde"),
    ("crate, include= (empty)                 ", "/crates/serde?include="),
    ("upper case Serde                        ", "/crates/Serde?include=downloads,default_version"),
    ("hyphen serde-json                       ", "/crates/serde-json?include=downloads,default_version"),
    ("unknown crate                           ", "/crates/serde-jason"),
    ("versions sort=semver (rustls)           ", "/crates/rustls/versions?sort=semver&per_page=3"),
    ("versions sort=date (rustls)             ", "/crates/rustls/versions?sort=date&per_page=3"),
    ("reverse_dependencies per_page=101       ", "/crates/serde/reverse_dependencies?per_page=101"),
    ("search q, sort=downloads                ", "/crates?q=http%20client&sort=downloads&per_page=3"),
    ("search q, relevance (default with q)    ", "/crates?q=http%20client&per_page=3"),
    ("search sort=bogus                       ", "/crates?q=http%20client&sort=bogus&per_page=3"),
):
    print(f"{label} {brief(raw(path))}")

print()
r = raw("https://index.crates.io/se/rd/serde")  # different origin, no Access-Control-Allow-Origin header
print(f"fetch() of index.crates.io from a crates.io page: status {r['status']} {r['text'][:60]!r}")
st, txt = page("https://index.crates.io/se/rd/serde")  # a page load of the same file works (text/plain)
lines = js("document.body.innerText.trim().split('\\n')")
last = json.loads(lines[-1])
print(f"index.crates.io/se/rd/serde page load HTTP {st}: {len(lines)} lines, last line vers {last['vers']!r}, "
      f"yanked {last['yanked']}, keys {sorted(last)}")
page(SITE + "/data-access", "Questions")  # back to a crates.io page
```

Output (from the second run on 2026-11-20, 23:36 UTC):

```text
robots.txt HTTP 200: '# allow crawling everything by default User-agent: * Disallow:'
index.crates.io/robots.txt HTTP 404: 'This XML file does not appear to have any style information '
data-access HTTP 200: found: 'Please try them in the order below.'
data-access HTTP 200: found: 'No rate limits are required to use data from the sparse crate index.'
data-access HTTP 200: found: 'No rate limits apply to static.crates.io at present.'
data-access HTTP 200: found: 'They are updated every 24 hours.'
data-access HTTP 200: found: 'A maximum of 1 request per second, and'
data-access HTTP 200: found: 'header that identifies your application.'
data-access HTTP 200: found: 'We strongly suggest providing a way for us to contact you'
policies HTTP 200: found: 'is using our servers for any form of excessive automated bulk activity, to place undue burden on our servers through automated means'
policies HTTP 200: found: 'impersonates any person or entity, including through false association with crates.io'
docs/rate-limits HTTP 200: found: 'Publishing Rate Limits' (mentions downloads or API reads: no)

/crates/tokio page HTTP 200: its own API calls: ['/api/v1/site_metadata', '/api/v1/crates/tokio?include=keywords%2Ccategories%2Cdownloads%2Cdefault_version', '/api/v1/crates/tokio/owners', '/api/v1/crates/tokio/downloads?include=versions']

crate, include=downloads,default_version HTTP 200 application/json 2,684 bytes {"name": "serde", "default_version": "1.0.229", "max_stable_version": null, "recent_downloads": 451883541}
crate, no include (full, every version)  HTTP 200 application/json 440,993 bytes {"name": "serde", "default_version": "1.0.229", "max_stable_version": "1.0.229", "recent_downloads": 451883541}
crate, include= (empty)                  HTTP 200 application/json 952 bytes {"name": "serde", "default_version": "1.0.229", "max_stable_version": null, "recent_downloads": null}
upper case Serde                         HTTP 200 application/json 2,684 bytes {"name": "serde", "default_version": "1.0.229", "max_stable_version": null, "recent_downloads": 451883541}
hyphen serde-json                        HTTP 200 application/json 2,764 bytes {"name": "serde_json", "default_version": "1.0.154", "max_stable_version": null, "recent_downloads": 454939590}
unknown crate                            HTTP 404 application/json 60 bytes [{"detail": "crate `serde-jason` does not exist"}]
versions sort=semver (rustls)            HTTP 200 application/json 5,357 bytes [('0.24.0-dev.3', False), ('0.24.0-dev.2', False), ('0.24.0-dev.1', False)]
versions sort=date (rustls)              HTTP 200 application/json 5,732 bytes [('0.24.0-dev.3', False), ('0.23.46', False), ('0.24.0-dev.2', False)]
reverse_dependencies per_page=101        HTTP 400 application/json 60 bytes [{"detail": "cannot request more than 100 items"}]
search q, sort=downloads                 HTTP 200 application/json 2,780 bytes total 17,768, first ['hyper', 'rustls', 'h2']
search q, relevance (default with q)     HTTP 200 application/json 3,058 bytes total 17,768, first ['cdk-http-client', 'http-client', 'http-client-gpui-unofficial']
search sort=bogus                        HTTP 200 application/json 3,316 bytes total 17,768, first ['AthenaEngine', 'BREP_app', 'BREP_mcp']

fetch() of index.crates.io from a crates.io page: status 0 'TypeError: Failed to fetch'
index.crates.io/se/rd/serde page load HTTP 200: 316 lines, last line vers '1.0.229', yanked False, keys ['cksum', 'deps', 'features', 'name', 'pubtime', 'rust_version', 'vers', 'yanked']
```

### 3. A Cargo.toml dependency list with Python urllib: robots check for every agent, latest stable from the sparse index (ETag cache), downloads from the API, last 7 days (no browser)

The index gives every version with `yanked` and `pubtime`, so the latest stable, the newest pre-release and what a caret requirement (`"1.38"` means `^1.38`) resolves to are computed locally. The API adds downloads and the repository (1 call per crate, 1.1 s apart). `/crates/<name>/downloads` gives 90 days of daily counts: per version for the top versions (5 for serde), plus `meta.extra_downloads` for all the others. Run with an empty cache; the last pass shows every index file coming back as HTTP 304.

```python
import collections, hashlib, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from datetime import datetime, timedelta, timezone

DEPS = {"serde": "1.0.200", "tokio": "1.38", "rustls": "0.23.12", "reqwest": "0.11.27", "clap": "4.5.4",
        "serde-json": "1.0.120", "libc": "0.2.155", "rand": "0.8.5"}  # [dependencies] from a Cargo.toml
DOWNLOADS_FOR = ["tokio", "reqwest"]  # also show the last 7 complete days of downloads for these

UA = "crates-io-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"  # identify yourself (policy)
API = "https://crates.io/api/v1"
INDEX = "https://index.crates.io"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/crates-io-skill"
CACHE = os.path.expanduser(CACHE_DIR)
API_PAUSE = 1.1    # Data Access Policy: at most 1 request per second to the API
INDEX_PAUSE = 0.2  # "No rate limits are required" for the sparse index; still serial and gentle
calls = collections.Counter()

def http(url, headers=None, pause=API_PAUSE):
    """GET -> (status, headers, body bytes). 304 and 404 are returned, not raised. Waits once on 429/5xx or a
    network error (Retry-After seconds, else 30 s; over 120 s exits); exits on any other error."""
    for attempt in range(2):
        time.sleep(pause)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})}),
                                        timeout=30) as r:
                return r.status, r.headers, r.read()
        except urllib.error.HTTPError as e:
            if e.code in (304, 404):
                return e.code, e.headers, e.read()
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                ra = e.headers.get("Retry-After") or ""
                wait = int(ra) if ra.isdigit() else 30
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                time.sleep(wait)
                continue
            sys.exit(f"HTTP {e.code} {url}: {' '.join(e.read().decode(errors='replace').split())[:200]}")
        except OSError as e:
            if attempt == 0:
                time.sleep(30)
                continue
            sys.exit(f"{url}: {e}")

def index_path(name):
    """Cargo sparse index layout: 1/{n}, 2/{n}, 3/{first letter}/{n}, else {first two}/{next two}/{n}, lower case."""
    n = name.lower()
    return {1: f"1/{n}", 2: f"2/{n}", 3: f"3/{n[0]}/{n}"}.get(len(n), f"{n[:2]}/{n[2:4]}/{n}")

def index_versions(name):
    """-> (canonical name, [one dict per published version]) from index.crates.io, or (name, None) if unknown.
    The index file is named by the crate's real name, so try '-' <-> '_' too (the API treats them as equal).
    Disk cache with the ETag: the server says Cache-Control max-age=600, and a 304 costs no body."""
    for n in dict.fromkeys([name, name.replace("-", "_"), name.replace("_", "-")]):
        url = f"{INDEX}/{index_path(n)}"
        f = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ".json")
        try:
            cached = json.load(open(f))
        except (OSError, ValueError):
            cached = None
        st, h, body = http(url, {"If-None-Match": cached["etag"]} if cached else None, pause=INDEX_PAUSE)
        calls[f"index {st}"] += 1
        if st == 304:
            return n, cached["lines"]
        if st == 200:
            lines = [json.loads(l) for l in body.decode().splitlines() if l.strip()]
            os.makedirs(CACHE, exist_ok=True)
            json.dump({"etag": h.get("ETag"), "lines": lines}, open(f, "w"))
            return n, lines
    return name, None

def key(v):
    """SemVer order: 1.2.3 > 1.2.3-rc.1; numeric parts of a pre-release compare as numbers. Drops '+build'."""
    core, _, pre = v.split("+")[0].partition("-")
    nums = tuple(int(x) for x in core.split("."))
    parts = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split(".")) if pre else ()
    return nums, (0,) if pre else (1,), parts

def caret_upper(req):
    """Cargo's default requirement '1.38' means ^1.38: >= 1.38.0, < next left-most non-zero part."""
    p = [int(x) for x in req.split(".")] + [0, 0]
    if p[0] > 0:
        return (p[0] + 1, 0, 0)
    if p[1] > 0:
        return (0, p[1] + 1, 0)
    return (0, 0, p[2] + 1)

# 1) robots.txt for every host used and every agent (index/static answer 404 for robots.txt: no rules).
for host, path in (("https://crates.io", "/api/v1/crates/serde"), (INDEX, "/se/rd/serde"),
                   ("https://static.crates.io", "/rss/crates/serde.xml")):
    st, _, body = http(host + "/robots.txt")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(body.decode(errors="replace").splitlines() if st == 200 else [])  # 404: allow all (RFC 9309)
    ok = all(rp.can_fetch(a, host + path) for a in AGENTS)
    print(f"robots {host:<26} HTTP {st}: {path:<22} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
    if not ok:
        sys.exit("robots.txt now disallows a path this skill uses: stop")

# 2) Every dependency: latest stable from the sparse index, then downloads and repository from the API.
now = datetime.now(timezone.utc)
print(f"\nCargo.toml check against crates.io, {now:%Y-%m-%d %H:%M} UTC")
for typed, req in DEPS.items():
    name, vers = index_versions(typed)
    if vers is None:
        print(f"  {typed:<11} {req:<9} not in the index (HTTP 404 for every spelling tried)")
        continue
    live = [v for v in vers if not v["yanked"]]
    stable = [v for v in live if "-" not in v["vers"].split("+")[0]]
    top = max(stable, key=lambda v: key(v["vers"]), default=None)
    up = caret_upper(req)
    in_range = [v for v in stable if key(req + ".0" * (2 - req.count(".")))[0] <= key(v["vers"])[0] < up]
    best = max(in_range, key=lambda v: key(v["vers"]), default=None)
    pre = max((v for v in live if v not in stable), key=lambda v: key(v["vers"]), default=None)
    pinned = next((v for v in vers if v["vers"] == req), None)
    d = json.loads(http(f"{API}/crates/{urllib.parse.quote(name)}?include=downloads,default_version")[2])["crate"]
    calls["api"] += 1
    note = ("the range allows the latest" if best and top and best["vers"] == top["vers"] else
            f"NEW MAJOR {top['vers']} (outside ^{req})" if top else "no stable release")
    print(f"  {typed:<11} {req:<9} -> {name}: ^{req} resolves to {best['vers'] if best else '-'}; latest stable "
          f"{top['vers'] if top else '-'} ({(top or {}).get('pubtime', '')[:10] or 'date not in index'}); {note}"
          + (f"; newer pre-release {pre['vers']}" if pre and top and key(pre["vers"]) > key(top["vers"]) else "")
          + ("; THIS EXACT VERSION IS YANKED" if pinned and pinned["yanked"] else ""))
    print(f"  {'':<21} {d['downloads']:,} downloads all time, {d['recent_downloads']:,} in 90 days; "
          f"{len(vers)} versions ({len(vers) - len(live)} yanked); repo {d['repository'] or 'not set'}")

# 3) Daily downloads: the last 7 complete UTC days (the newest date in the answer is today, still counting).
today = now.date()
for name in DOWNLOADS_FOR:
    d = json.loads(http(f"{API}/crates/{name}/downloads")[2])
    calls["api"] += 1
    by = collections.Counter()
    for x in d["version_downloads"] + d["meta"]["extra_downloads"]:  # top versions per day + all others per day
        by[x["date"]] += x["downloads"]
    days = [str(today - timedelta(days=i)) for i in range(7, 0, -1)]
    print(f"\n{name}: {sum(by[x] for x in days):,} downloads {days[0]}..{days[-1]} (7 complete days); "
          f"{len(by)} days returned, {sum(by.values()):,} in total; today so far {by[str(today)]:,}")

# 4) Run the index part again: every file comes back as HTTP 304 with no body.
before = dict(calls)
for typed in DEPS:
    index_versions(typed)
print(f"\ncalls: first pass {before}; second index pass {dict(calls - collections.Counter(before))} (cache {CACHE_DIR})")
print("Source: crates.io (https://crates.io) sparse index and public API.")
```

Output (from the second run on 2026-11-20, 23:36 UTC, empty cache):

```text
robots https://crates.io          HTTP 200: /api/v1/crates/serde   allowed for all 11 agents
robots https://index.crates.io    HTTP 404: /se/rd/serde           allowed for all 11 agents
robots https://static.crates.io   HTTP 404: /rss/crates/serde.xml  allowed for all 11 agents

Cargo.toml check against crates.io, 2026-11-20 23:36 UTC
  serde       1.0.200   -> serde: ^1.0.200 resolves to 1.0.229; latest stable 1.0.229 (2026-07-18); the range allows the latest
                        1,750,809,565 downloads all time, 451,883,541 in 90 days; 316 versions (3 yanked); repo https://github.com/serde-rs/serde
  tokio       1.38      -> tokio: ^1.38 resolves to 1.54.1; latest stable 1.54.1 (2026-10-21); the range allows the latest
                        1,223,086,474 downloads all time, 322,790,561 in 90 days; 201 versions (6 yanked); repo https://github.com/tokio-rs/tokio
  rustls      0.23.12   -> rustls: ^0.23.12 resolves to 0.23.46; latest stable 0.23.46 (2026-10-14); the range allows the latest; newer pre-release 0.24.0-dev.3
                        1,150,882,937 downloads all time, 298,480,817 in 90 days; 119 versions (4 yanked); repo https://github.com/rustls/rustls
  reqwest     0.11.27   -> reqwest: ^0.11.27 resolves to 0.11.27; latest stable 0.13.5 (2026-09-08); NEW MAJOR 0.13.5 (outside ^0.11.27)
                        939,269,748 downloads all time, 279,147,920 in 90 days; 126 versions (0 yanked); repo https://github.com/seanmonstar/reqwest
  clap        4.5.4     -> clap: ^4.5.4 resolves to 4.6.9; latest stable 4.6.9 (2026-11-20); the range allows the latest
                        1,366,141,170 downloads all time, 300,095,836 in 90 days; 464 versions (92 yanked); repo https://github.com/clap-rs/clap
  serde-json  1.0.120   -> serde_json: ^1.0.120 resolves to 1.0.154; latest stable 1.0.154 (2026-10-11); the range allows the latest
                        1,658,067,727 downloads all time, 454,939,590 in 90 days; 186 versions (2 yanked); repo https://github.com/serde-rs/json
  libc        0.2.155   -> libc: ^0.2.155 resolves to 0.2.191; latest stable 0.2.191 (2026-10-16); the range allows the latest; newer pre-release 1.0.0-alpha.5
                        2,027,083,847 downloads all time, 509,815,396 in 90 days; 209 versions (9 yanked); repo https://github.com/rust-lang/libc
  rand        0.8.5     -> rand: ^0.8.5 resolves to 0.8.8; latest stable 0.10.4 (2026-11-15); NEW MAJOR 0.10.4 (outside ^0.8.5)
                        2,244,029,666 downloads all time, 671,456,246 in 90 days; 95 versions (2 yanked); repo https://github.com/rust-random/rand

tokio: 33,864,329 downloads 2026-11-13..2026-11-19 (7 complete days); 90 days returned, 323,946,779 in total; today so far 4,878,247

reqwest: 29,256,591 downloads 2026-11-13..2026-11-19 (7 complete days); 90 days returned, 280,148,872 in total; today so far 4,123,671

calls: first pass {'index 200': 8, 'api': 10, 'index 404': 1}; second index pass {'index 404': 1, 'index 304': 8} (cache ~/.cache/crates-io-skill)
Source: crates.io (https://crates.io) sparse index and public API.
```

### 4. curl, headers and mistakes

```bash
B=https://crates.io/api/v1
UA='crates-io-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# search by keyword, sorted by all-time downloads (sort=recent-downloads for the last 90 days)
curl -sS --fail -A "$UA" "$B/crates?q=async%20runtime&sort=downloads&per_page=3" \
  | python3 -c 'import sys, json
d = json.load(sys.stdin)
print("matches", d["meta"]["total"])
for c in d["crates"]: print(c["name"], c["default_version"], "| all time", c["downloads"], "| 90 days", c["recent_downloads"], "|", c["repository"])'
sleep 1
# one crate, small: include=downloads,default_version (3.6 KB; without include it is the full 456 KB record)
curl -sS --fail -A "$UA" "$B/crates/tokio?include=downloads,default_version" \
  | python3 -c 'import sys, json
c = json.load(sys.stdin)["crate"]
print(c["name"], "default", c["default_version"], "| downloads", c["downloads"], "| 90 days", c["recent_downloads"], "|", c["repository"])'
sleep 1
# who depends on it: most-downloaded dependents first, at most 100 per page
curl -sS --fail -A "$UA" "$B/crates/tokio/reverse_dependencies?per_page=5" \
  | python3 -c 'import sys, json
d = json.load(sys.stdin); n = {v["id"]: v["crate"] for v in d["versions"]}
print("dependents", d["meta"]["total"], [(n[x["version_id"]], x["kind"], x["optional"]) for x in d["dependencies"]])'
sleep 1
# version list from the sparse index (no rate limit): one JSON line per published version, newest last
curl -sS --fail -A "$UA" "https://index.crates.io/to/ki/tokio" \
  | python3 -c 'import sys, json
L = [json.loads(l) for l in sys.stdin]
print("index lines", len(L), "| last", L[-1]["vers"], L[-1].get("pubtime"), "| yanked", sum(v["yanked"] for v in L))'
sleep 1
# index file conditional GET: same ETag -> 304, no body
E=$(curl -sS -A "$UA" -D - -o /dev/null https://index.crates.io/to/ki/tokio | tr -d '\r' | sed -n 's/^etag: //Ip')
sleep 1
curl -sS -A "$UA" -H "If-None-Match: $E" -o /dev/null -w 'index If-None-Match -> HTTP %{http_code}, %{size_download} bytes\n' https://index.crates.io/to/ki/tokio
sleep 1
# API headers: JSON, CORS open, no rate-limit or ETag headers
curl -sS -A "$UA" -D - -o /dev/null "$B/crates/tokio?include=downloads" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|access-control-allow-origin|cache-control|etag|retry-after|x-ratelimit-[a-z]+|server|via):)'
sleep 1
# mistakes: curl's default User-Agent is refused, an unknown crate is a JSON 404, per_page over 100 is a 400
T=$(mktemp)
curl -sS -o "$T" -w 'default curl UA -> HTTP %{http_code} %{content_type} %{size_download} bytes ' "$B/crates/tokio"; head -c 120 "$T"; echo; sleep 1
curl -sS -H 'User-Agent:' -o "$T" -w 'no User-Agent -> HTTP %{http_code} ' "$B/crates/tokio"; head -c 120 "$T"; echo; sleep 1
curl -sS -A "$UA" -o "$T" -w 'unknown crate -> HTTP %{http_code} ' "$B/crates/tokyo-runtime"; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -o "$T" -w 'per_page=101 -> HTTP %{http_code} ' "$B/crates/tokio/reverse_dependencies?per_page=101"; cat "$T"; echo; sleep 1
curl -sS -A "$UA" -o "$T" -w 'index, upper case -> HTTP %{http_code}\n' "https://index.crates.io/To/ki/Tokio"
rm -f "$T"
```

Output (from the second run on 2026-11-20, 23:34 UTC):

```text
matches 16320
mio 1.2.5 | all time 1296930397 | 90 days 338427375 | https://github.com/tokio-rs/mio
tokio 1.54.1 | all time 1223086474 | 90 days 322790561 | https://github.com/tokio-rs/tokio
rustls 0.23.46 | all time 1150882937 | 90 days 298480817 | https://github.com/rustls/rustls
tokio default 1.54.1 | downloads 1223086474 | 90 days 322790561 | https://github.com/tokio-rs/tokio
dependents 83814 [('futures-util', 'dev', False), ('hyper', 'normal', False), ('tokio-macros', 'dev', False), ('h2', 'normal', False), ('tokio-util', 'normal', False)]
index lines 201 | last 1.54.1 2026-10-21T21:05:43Z | yanked 6
index If-None-Match -> HTTP 304, 0 bytes
HTTP/2 200 
access-control-allow-origin: *
content-type: application/json
server: Heroku
via: 1.1 heroku-router, 1.1 varnish
default curl UA -> HTTP 403 text/html; charset=utf-8 0 bytes 
no User-Agent -> HTTP 403 {"errors":[{"detail":"We require that all requests include a `User-Agent` header.  To allow us to determine the impact y
unknown crate -> HTTP 404 {"errors":[{"detail":"crate `tokyo-runtime` does not exist"}]}
per_page=101 -> HTTP 400 {"errors":[{"detail":"cannot request more than 100 items"}]}
index, upper case -> HTTP 404
```

## Fields

| Field | Value | Notes |
|---|---|---|
| `crate.name` | `serde_json` | canonical name; the API accepts any case and `-` for `_` (`Serde`, `serde-json`), the index does not |
| `crate.default_version` | `1.54.1` | "This version will be displayed by default on the crate's page" (OpenAPI); equal to the latest non-yanked stable for all 11 crates checked on 2026-11-20 (serde, tokio, rustls, serde_json, hyper, h2, reqwest, tower, clap, libc, rand), but not defined as such |
| `crate.max_stable_version`, `max_version`, `newest_version` | versions | deprecated; filled only in the full record (no `include`), else `null` / `"0.0.0"` |
| `crate.downloads` | integer | all time, all versions |
| `crate.recent_downloads` | integer or null | "in the last 90 days"; `null` unless `include` has `downloads` (or no `include`). serde: 451,883,541, while the 90 daily totals from `/downloads` (2026-08-23 to 2026-11-20, today partial) add up to 453,484,733 |
| `crate.repository`, `homepage`, `documentation` | URL or null | from the publisher's Cargo.toml (`repository` "should be a URL to the source repository", Cargo manifest reference); treat as the publisher's claim |
| `crate.num_versions`, `created_at`, `updated_at` | | serde: 316 versions, created 2014-12-05 |
| `versions[].num`, `yanked`, `license`, `created_at`, `downloads`, `crate_size`, `published_by.login` | | `/versions` and `include=default_version` |
| `versions[].features`, index `features`, `deps` | | the index line also has `cksum`, `rust_version` (MSRV) and `pubtime` |
| `reverse_dependencies`: `dependencies[].kind`, `optional`, `req`, `downloads`, `version_id` | `normal` / `dev` / `build` | `downloads` is the dependent crate's all-time total; `meta.total` counts dependent crates (one version each) |
| `/crates` search: `crates[]`, `meta.total`, `meta.next_page` | | `next_page` is a `?...&seek=` string for the next page; `exact_match` true when the name equals `q` |
| `/downloads`: `version_downloads[].version`, `date`, `downloads`; `meta.extra_downloads[]` | | 90 dates; the last one is today (UTC) and still counting |
| API headers | `Content-Type: application/json`, `Access-Control-Allow-Origin: *`, `Server: Heroku`, `Via: 1.1 heroku-router, 1.1 varnish` | no `ETag`, `Cache-Control` or rate-limit headers seen |
| index headers | `Content-Type: text/plain`, `Cache-Control: public,max-age=600`, `ETag`, `Last-Modified`, `Server: AmazonS3` | no `Access-Control-Allow-Origin`; If-None-Match gives HTTP 304 |

## Gotchas

- **Pre-releases sort first.** `sort=semver` puts rustls `0.24.0-dev.3`, `-dev.2`, `-dev.1`, `-dev.0` before `0.23.46`; `sort=date` puts the newest upload first. "Latest stable" = the highest version with no `-` before any `+build` part and `yanked` false. libc's index also has `1.0.0-alpha.5` above `0.2.191`.
- **Yanked versions stay listed.** clap has 92 yanked of 464 versions in the index. Skip `yanked` when picking a latest version, and flag a pinned version that is yanked (block 3).
- **Index paths are lower case and use the real name.** `index.crates.io/se/rd/serde_json` is HTTP 200, `/se/rd/serde-json` and `/To/ki/Tokio` are HTTP 404. Layout: 1-letter names `1/<n>`, 2-letter `2/<n>`, 3-letter `3/<first letter>/<n>`, else `<first two>/<next two>/<n>` (`3/s/syn`, `2/cc`, `to/ki/tokio`). The API resolves `Serde` and `serde-json` to the canonical name; use that name for the index.
- **The index is not readable from a crates.io page.** It sends no CORS header, so a browser `fetch()` fails with `TypeError: Failed to fetch`; use a page load (plain text, block 2), urllib or curl.
- **Keyword search is broad.** `q=http client` matches 17,768 crates; sorted by downloads, rustls ("a modern TLS library", no keywords) is second. The default order with `q` (relevance) puts name matches first (`cdk-http-client`, `http-client`). Check each result's description. A typo has no suggestions: `q=serde-jason` returns 0 results.
- **An unknown `sort` is ignored.** `sort=bogus` is HTTP 200 in name order (`AthenaEngine`, `BREP_app`, ...), so a misspelled `recent-downloads` silently gives the wrong list. A repeated `sort` is HTTP 400 "sort: unsupported value". Valid: `alphabetical`, `relevance`, `downloads`, `recent-downloads`, `recent-updates`, `new`.
- **User-Agent is checked.** No User-Agent: HTTP 403 JSON "We require that all requests include a `User-Agent` header. ... we ask that your user agent actually identify your bot, and not just report the HTTP client library you're using." curl's default (`curl/<version>`): HTTP 403 with an empty `text/html` body. `Python-urllib/3.12` and `Mozilla/5.0` were HTTP 200, but the policy asks for one that names your application.
- **`per_page` tops out at 100** (HTTP 400 "cannot request more than 100 items"). Page on with `meta.next_page` (a `seek` key) or `page=`. serde's dependents are 142,761, so read only the first page or two.
- **Counts move.** serde's dependents went from 142,759 to 142,761 between 23:30 and 23:35 UTC; date every number.
- **Tab marker.** The harness may set the tab title to a horse emoji; the blocks check `location.origin` and the page text, not the title.

## What does not work

- **`max_stable_version` from the small record**: `null` with any `include`; only the 441 KB full record fills it.
- **Browser `fetch()` of index.crates.io from crates.io**: blocked by CORS.
- **The "Rate Limits" page for read limits**: it covers publishing only; the read limit is on the Data Access Policy page.
- **Not tested:** the 429 response (never provoked), the database dump (not downloaded), `/crates/<name>/owners`, the legacy Git index on GitHub, and the RSS feeds inside the blocks (https://static.crates.io/rss/crates/serde.xml was fetched once while exploring: HTTP 200 `text/xml`, RSS 2.0, one `<item>` per release with `<crates:version>`; `rss/updates.xml` was not fetched).
