# endoflife.date API (endoflife.date) - Check Whether a Software Version (Python, Node.js, Ubuntu, PostgreSQL...) Is Still Supported and When It Reaches End of Life (REST API, no key)

Field-tested against endoflife.date on 2026-11-18 (US Pacific afternoon; 23:47-23:56 UTC) using a fresh Browser Use cloud browser (logged out; one session, 23:49-23:54 UTC) plus Python `urllib` and `curl` from a Linux machine. 20 browser page loads (the Python product page, robots.txt 4 times, the API index 4 times, the OpenAPI spec twice (a page load downloads it, see Gotchas), the GitHub README 4 times and the LICENSE 5 times, 4 on github.com and 1 on raw.githubusercontent.com) and 71 in-page `fetch()` calls (blocks 1 and 2 ran 2 and 4 times while they were written), 57 curl calls and 21 urllib calls to endoflife.date (plus 2 curl calls for the README and LICENSE on raw.githubusercontent.com), all serial (1 s apart in the blocks below). Every call was HTTP 200 except the deliberate HTTP 404 (unknown product, release or category), HTTP 301 (alias) and HTTP 304 (conditional GET) probes below, and https://endoflife.date/terms and https://endoflife.date/credits, which do not exist (HTTP 404). Each call took about 0.07-0.33 s. No 429, no challenge, no key, no login. After code review on 2026-11-19, blocks 1, 3 and 4 were re-run at 00:05-00:17 UTC (block 1 in a new cloud browser, block 3 with an empty cache) after small fixes (hyphen-suffix versions, a label fallback, a `mktemp` file, a NaN-safe `Retry-After`): same output except the times and block 3's day counts, which moved by 1 day at midnight UTC. After a second review the same day, blocks 1 and 3 were re-run at 01:15 UTC (block 1 in a new cloud browser, block 3 with an empty cache) after a cycle with no end-of-life date that is neither `isEol` nor `isMaintained` became UNKNOWN instead of supported: same output except the times and block 3's day counts (1 day later); none of the cycles asked about is in that state. They show the re-run output.

robots.txt (checked 2026-11-18, curl, the cloud browser and `urllib.robotparser`): https://endoflife.date/robots.txt is three lines, `User-Agent: *`, `Allow: /` and a `Sitemap:` line, with no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*` and may fetch `/api/v1/` (block 3 checks all 11 agents). Terms: endoflife.date has no terms page (`/terms` is HTTP 404; the site's "Credits" link goes to the GitHub README). The OpenAPI spec (https://endoflife.date/docs/api/v1/openapi.yml, version 1.2.1) declares `license: name: MIT License` with a link to the repository LICENSE, which reads "Copyright 2020 endoflife.date contributors" and "Permission is hereby granted, free of charge ... to deal in the Software without restriction"; the README (https://github.com/endoflife-date/endoflife.date) says "Licensed under the MIT License." and "The API is currently in Beta, and breaking changes can happen." The spec asks clients to "follow the 301 redirects (products, categories or tags may occasionally be renamed)" and documents HTTP 429, whose response "may contain a `Retry-After` header", "to prevent abuse of the API and ensure fair usage for all users"; it gives no number. No AI/ML, scraping, crawling, automated-access, rate-limit number or non-commercial wording in the spec, the README or the LICENSE (block 2 checks the quotes; a word search of all three found none). The README also says product descriptions are adapted from English Wikipedia under CC BY-SA 3.0 and the site icon is CC-BY-SA-4.0; the API responses used here carry no descriptions, and this skill shows no icon or logo (`links.icon` points to Simple Icons brand logos: not used). Naming: the project writes its name "endoflife.date", lowercase, and so does this skill. It is a community project; this is its own API, and this skill is not affiliated with or endorsed by it.

**Community data, not a vendor statement.** endoflife.date collects dates from each vendor's published policy (the product's `links.releasePolicy`). Show the date with the product page link (`links.html`) and the access date, and check the vendor's policy before a decision that depends on one day.

## Quick summary

- **No scraping.** `GET https://endoflife.date/api/v1/products/python/releases/3.12` -> `{"schema_version": "1.2.1", "generated_at": ..., "result": {"name": "3.12", "isEol": false, "eolFrom": "2028-10-31", "isMaintained": true, "latest": {"name": "3.12.16", ...}}}`. `/products/<product>/` returns every cycle at once (newest first), `/products/<product>/releases/latest` the newest cycle, `/products` the 489 product names with aliases, `/categories/<c>` and `/tags/<t>` a product list. JSON, `Access-Control-Allow-Origin: *`, no key.
- **Answers (block 1, 23:51 UTC; block 4 at 23:56 agrees on Python 3.12 and Node.js 26):** **Python 3.12 is supported (security fixes only) until 2028-10-31**, latest 3.12.16; **Node.js latest is 26 (LTS) at 26.13.1 (2026-11-11), end of life 2029-04-30**; **Node.js 20 reached end of life on 2026-04-30** (the API still marks it maintained: "Commercial Support", no end date); **Ubuntu 20.04 reached end of life on 2025-05-31**, with Expanded Security Maintenance until 2030-04-23; **PostgreSQL 13 reached end of life on 2025-11-13** (`isMaintained` false).
- **Ask for the cycle, not the version.** The release name is the cycle (`3.12`, `20`, `22.04`, `13`): `releases/3.12.4` and `releases/v20` are HTTP 404. Blocks 1 and 3 fetch the product once and map a version to its cycle locally (longest cycle name followed by a dot or a hyphen, so `3.1` never takes `3.12.4`), then compare it with the cycle's `latest`.
- **404 is an HTML page.** An unknown product (`java`, `pyhton`), release or category answers HTTP 404 `text/html` "Page not Found | endoflife.date", not JSON (the spec says so). Check the status before parsing. Names: `/products` lists names, labels and aliases (`node` -> `nodejs`, `pg` -> `postgresql`, which the API also serves as HTTP 301); there is no product "java" (14 products carry the tag `java-distribution`).
- **"End of life" and "maintained" are different fields.** `isMaintained` is "any level of support, even extended support": 207 of 9,419 cycles are `isEol` true and `isMaintained` true (Node.js 20, Ubuntu 20.04, Amazon EKS 1.31). The blocks report the phase from the dates: active support (`eoasFrom`), end of life (`eolFrom`), extended support (`eoesFrom`), with each product's own phase names from `labels`.
- **Rate limit:** none published; the spec documents 429 with an optional `Retry-After`. All blocks send 1 request per second, serial, wait `Retry-After` (seconds or an HTTP date; default 60 s) once on 429/502/503/504 and stop when it asks for more than 120 s. Responses carry an `ETag` and `Cache-Control: public,max-age=0,must-revalidate`; block 3 keeps answers on disk for 6 h and then revalidates with `If-None-Match` (HTTP 304, no body).

## What works

### 1. Product and version as a person types them -> support phase, end-of-life date and latest patch (browser)

`on_eol_tab()` opens the logged-out API index, so `fetch()` is same-origin (the API also allows any origin). `get()` returns parsed JSON on HTTP 200, `None` on 404, waits once on 429/502/503/504 and otherwise raises; `fetch()` follows the 301 of an alias by itself. `resolve()` matches the typed name against each product's name, label and aliases from `/products`; with no match it prints close names and tags. `status()` works from the dates for today, not from the `is*` flags (see Gotchas); a cycle with no end-of-life date that is neither `isEol` nor `isMaintained` is UNKNOWN, not supported (block 3 does the same). 6 `fetch()` calls for the 7 questions.

```python
import difflib, json, re, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ASK = [("Python", "3.12.4"), ("Node.js", "v20.11.1"), ("ubuntu", "20.04"), ("PostgreSQL", "13.4"),
       ("node", "latest"), ("Java", "21"), ("pyhton", "3.12")]  # (product as a person types it, version or "latest")

SITE = "https://endoflife.date"
API = SITE + "/api/v1"
PAUSE = 1.0  # no published limit (the spec only documents 429 + Retry-After "to prevent abuse"): 1 request per second

def on_eol_tab():
    """fetch() from a logged-out endoflife.date page (the API also sends Access-Control-Allow-Origin: *)."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(API + "/")
    wait_for_load()
    if js("location.origin") != SITE or '"schema_version"' not in (js("document.body ? document.body.innerText : ''") or ""):
        raise RuntimeError(f"endoflife.date did not serve its API index (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__u[id] = {status: r.status, type: r.headers.get('content-type') || '',
      retry: r.headers.get('retry-after'), url: r.url, redirected: r.redirected, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, type: '', retry: null, url: '', redirected: false, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def retry_after(v):
    """Retry-After in seconds: a number or an HTTP date; 60 when absent or unreadable; at least 1. Over 120 s: stop."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        try:
            s = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            s = 60
    if s != s:  # 'nan'
        s = 60
    if s > 120:
        raise RuntimeError(f"server asks to wait {s:.0f} s (over 120 s): stopping")
    return max(s, 1)

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
    """-> parsed JSON, or None on 404 (whose body is an HTML page, not JSON). fetch() follows the 301s of renamed
    products and aliases itself. Waits Retry-After once on 429/502/503/504 or a network error; raises on anything else."""
    for attempt in range(2):
        r = fetch(API + path)
        if r["status"] in (0, 429, 502, 503, 504) and attempt == 0:
            time.sleep(retry_after(r["retry"]))
            continue
        break
    if r["status"] == 404:
        return None
    if r["status"] != 200 or "json" not in r["type"]:
        raise RuntimeError(f"{path}: HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:150]!r}; stopping")
    d = json.loads(r["text"])
    d["_url"] = r["url"]
    return d

def resolve(name, products):
    """What a person types -> product records whose name, alias or label matches (case and punctuation ignored)."""
    k = re.sub(r"[^a-z0-9]", "", name.lower())
    hits = [p for p in products if k in [re.sub(r"[^a-z0-9]", "", x.lower()) for x in [p["name"], p["label"], *p["aliases"]]]]
    if not hits:  # substring of a name or label, e.g. "Java" -> the four JDK builds
        hits = [p for p in products if len(k) > 2 and k in re.sub(r"[^a-z0-9]", "", (p["name"] + " " + p["label"]).lower())]
    return hits

def cycle(version, releases):
    """'v20.11.1' -> the release cycle '20'; '3.12.4' -> '3.12'; '22.04.3' -> '22.04'. Longest cycle name equal to the
    version or followed by a dot or a hyphen ('1.31-eks-70' -> '1.31'), so '3.1' never takes '3.12.4'."""
    v = version.lower().lstrip("v")
    found = [r for r in releases if v == r["name"].lower() or v.startswith((r["name"].lower() + ".", r["name"].lower() + "-"))]
    return max(found, key=lambda r: len(r["name"]), default=None)

def nums(s):
    return tuple(int(x) for x in re.findall(r"\d+", s or ""))

def status(r, labels, today):
    """Support phase for today, from the dates (the is* flags are as of the API's generated_at)."""
    eol, eoas, eoes = r.get("eolFrom"), r.get("eoasFrom"), r.get("eoesFrom")
    past_eol = today >= eol if eol else r["isEol"]
    if not eol and not r["isEol"] and not r["isMaintained"]:  # no date and the flags disagree: do not call it supported
        return "UNKNOWN", "no end-of-life date; isEol is false but isMaintained is false: check the product's own page"
    if not past_eol:
        if eoas and today < eoas:
            return "SUPPORTED", f"{labels.get('eoas') or 'active support'} until {eoas}, then {labels['eol']} until {eol or 'a date not known'}"
        return "SUPPORTED", f"{labels['eol']} until {eol or 'a date not known'}" + (f" ({labels.get('eoas')} ended {eoas})" if eoas else "")
    when = f"since {eol}" if eol else "(date not known)"
    if eoes and today < eoes:
        return "EOL", f"end of life {when}; {labels.get('eoes') or 'extended support'} only, until {eoes}"
    if r["isMaintained"]:
        return "EOL", f"end of life {when}; the API still marks it maintained ({labels.get('eoes') or 'extended support'}, end date not known)"
    return "EOL", f"end of life {when}; isMaintained is false (no support phase left)"

on_eol_tab()
now = datetime.now(timezone.utc)
today = now.strftime("%Y-%m-%d")
products = get("/products")["result"]
print(f"endoflife.date API, {len(products)} products, checked {now:%Y-%m-%d %H:%M} UTC")
for name, version in ASK:
    hits = resolve(name, products)
    if len(hits) != 1:
        close = difflib.get_close_matches(name.lower(), [p["name"] for p in products], n=3, cutoff=0.6)
        k = re.sub(r"[^a-z0-9]", "", name.lower())
        tags = sorted({t for p in products for t in p["tags"] if k in t.replace("-", "")})
        print(f"\n{name} {version}: {len(hits)} products match; " + (
            "pick one: " + ", ".join(f"{p['name']} ({p['label']})" for p in hits) if hits else
            f"close names: {', '.join(close) or 'none'}; tags: " + (", ".join(
                f"{t} ({sum(t in p['tags'] for p in products)} products)" for t in tags) or "none")))
        continue
    d = get(f"/products/{hits[0]['name']}/")
    if d is None:
        print(f"\n{name}: /products/{hits[0]['name']}/ is HTTP 404 now: re-read /products")
        continue
    p = d["result"]
    rel = p["releases"][0] if version == "latest" else cycle(version, p["releases"])  # releases are newest first
    print(f"\n{name} {version} -> {p['label']} ({p['name']}), page {p['links']['html']}, product data modified {d['last_modified'][:10]}")
    if rel is None:
        print(f"  no release cycle matches {version!r}; cycles: {', '.join(r['name'] for r in p['releases'][:12])} ...")
        continue
    verdict, detail = status(rel, p["labels"], today)
    print(f"  cycle {rel['label']} (released {rel['releaseDate']}): {verdict}, {detail}")
    lt = rel.get("latest") or {}
    if lt:
        behind = version != "latest" and len(nums(version)) > len(nums(rel["name"])) and nums(version) < nums(lt["name"])
        print(f"  latest in this cycle: {lt['name']} ({lt.get('date')})" + (f"; {version} is older, update" if behind else ""))
    if version != "latest" and p["releases"][0] is not rel:
        print(f"  newest cycle: {p['releases'][0]['label']}, end of life {p['releases'][0]['eolFrom'] or 'not known'}")

print(f"\nSource: endoflife.date (https://endoflife.date), community-maintained, via {API}, accessed {now:%d %B %Y %H:%M} UTC. "
      "Check the vendor's own policy link before acting on a date.")
```

Output (from the re-run on 2026-11-19, 01:15 UTC):

```text
endoflife.date API, 489 products, checked 2026-11-19 01:15 UTC

Python 3.12.4 -> Python (python), page https://endoflife.date/python, product data modified 2026-11-16
  cycle 3.12 (released 2023-10-02): SUPPORTED, Security Support until 2028-10-31 (Active Support ended 2025-04-02)
  latest in this cycle: 3.12.16 (2026-10-25); 3.12.4 is older, update
  newest cycle: 3.15, end of life 2031-10-31

Node.js v20.11.1 -> Node.js (nodejs), page https://endoflife.date/nodejs, product data modified 2026-11-12
  cycle 20 (LTS) (released 2023-04-18): EOL, end of life since 2026-04-30; the API still marks it maintained (Commercial Support, end date not known)
  latest in this cycle: 20.20.2 (2026-03-24); v20.11.1 is older, update
  newest cycle: 26 (LTS), end of life 2029-04-30

ubuntu 20.04 -> Ubuntu (ubuntu), page https://endoflife.date/ubuntu, product data modified 2026-11-07
  cycle 20.04 'Focal Fossa' (LTS) (released 2020-04-23): EOL, end of life since 2025-05-31; Expanded Security Maintenance only, until 2030-04-23
  latest in this cycle: 20.04.6 (2023-03-23)
  newest cycle: 26.10 'Stonking Stingray', end of life 2027-07-01

PostgreSQL 13.4 -> PostgreSQL (postgresql), page https://endoflife.date/postgresql, product data modified 2026-11-12
  cycle 13 (released 2020-09-24): EOL, end of life since 2025-11-13; isMaintained is false (no support phase left)
  latest in this cycle: 13.23 (2025-11-10); 13.4 is older, update
  newest cycle: 18, end of life 2030-11-14

node latest -> Node.js (nodejs), page https://endoflife.date/nodejs, product data modified 2026-11-12
  cycle 26 (LTS) (released 2026-05-05): SUPPORTED, Active Support until 2027-10-27, then Security Support until 2029-04-30
  latest in this cycle: 26.13.1 (2026-11-11)

Java 21: 0 products match; close names: none; tags: java-distribution (14 products), java-runtime (59 products), javascript-runtime (34 products)

pyhton 3.12: 0 products match; close names: python, photon, iphone; tags: none

Source: endoflife.date (https://endoflife.date), community-maintained, via https://endoflife.date/api/v1, accessed 19 November 2026 01:15 UTC. Check the vendor's own policy link before acting on a date.
```

### 2. robots.txt, the license and spec quotes, and what the API does with mistakes (browser)

3 page loads, 1 return to the API index and 15 in-page `fetch()` calls in the same tab. The spec is served as `application/x-yaml`, which a page load downloads instead of showing, so the block reads it with `fetch()`.

```python
import json, time

SITE = "https://endoflife.date"
API = SITE + "/api/v1"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', headers: %s})
    .then(async r => { window.__u[id] = {status: r.status, type: r.headers.get('content-type') || '', etag: r.headers.get('etag'),
      url: r.url, redirected: r.redirected, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, type: '', etag: null, url: '', redirected: false, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(path, headers=None):
    """One in-page GET of API + path (or a full URL) -> status, type, final URL and body. No retries: inspection only."""
    url = path if path.startswith("https://") else API + path
    rid = json.dumps(js(START_JS % (json.dumps(url), json.dumps(headers or {}))))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1.0)
    return r

def brief(r):
    out = f"HTTP {r['status']} {r['type'].split(';')[0] or '-'}"
    if r["redirected"]:
        out += f" after a redirect to {r['url'].replace(API, '')}"
    if "json" not in r["type"]:
        t = r["text"]
        return out + (f" {t[t.find('<title>') + 7:t.find('</title>')]!r}" if "<title>" in t else f" {t[:50]!r}")
    res = json.loads(r["text"]).get("result")
    if isinstance(res, list):
        return out + f" {len(res)} items, first {res[0]['name'] if res else None!r}"
    keep = ("name", "label", "isEol", "eolFrom", "isMaintained") if "releases" not in res else ("name", "label", "category")
    return out + " " + json.dumps({k: res.get(k) for k in keep})

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or ""

try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(API + "/")
    wait_for_load()

st, txt = page(SITE + "/robots.txt")
print(f"robots.txt HTTP {st}: {[l.strip() for l in txt.splitlines() if l.strip()]}")
st, txt = page("https://github.com/endoflife-date/endoflife.date/blob/master/README.md")
flat = " ".join(txt.split())
for needle in ("The API is currently in Beta, and breaking changes can happen.", "Licensed under the MIT License."):
    print(f"README HTTP {st}: {'found' if needle in flat else 'MISSING'}: {needle!r}")
st, txt = page("https://raw.githubusercontent.com/endoflife-date/endoflife.date/master/LICENSE")  # plain text
flat = " ".join(txt.split())
for needle in ("Copyright 2020 endoflife.date contributors", "Permission is hereby granted, free of charge",
               "to deal in the Software without restriction"):
    print(f"LICENSE HTTP {st}: {'found' if needle in flat else 'MISSING'}: {needle!r}")
page(API + "/")  # back to an endoflife.date page for same-origin fetch()
# the spec is served as application/x-yaml, which a page load downloads instead of showing: fetch() it
r = raw(SITE + "/docs/api/v1/openapi.yml")
flat = " ".join(r["text"].split())
for needle in ("name: MIT License", "follow the 301 redirects (products, categories or tags may occasionally be renamed)",
               "the body of the response is not JSON, but our HTML error page",
               "The response may contain a `Retry-After` header indicating when the client can retry the request.",
               "This is to prevent abuse of the API and ensure fair usage for all users.",
               "Our API is hosted on [Netlify]", "Whether this release cycle still have some level of support."):
    print(f"openapi.yml HTTP {r['status']} {r['type']}: {'found' if needle in flat else 'MISSING'}: {needle!r}")
print()

for label, path in (
    ("one release cycle         ", "/products/python/releases/3.12"),
    ("latest cycle              ", "/products/nodejs/releases/latest"),
    ("upper-case product        ", "/products/PYTHON/releases/3.12"),
    ("alias node (301)          ", "/products/node/releases/latest"),
    ("alias pg (301)            ", "/products/pg/"),
    ("patch version as a cycle  ", "/products/python/releases/3.12.4"),
    ("'v' prefix                ", "/products/nodejs/releases/v20"),
    ("unknown product java      ", "/products/java/"),
    ("typo pyhton               ", "/products/pyhton/"),
    ("tag java-distribution     ", "/tags/java-distribution/"),
    ("category lang             ", "/categories/lang/"),
    ("unknown category          ", "/categories/languages/"),
):
    print(f"{label} {brief(raw(path))}")

r = raw("/products/python/")
print(f"\nproduct python: HTTP {r['status']}, {len(r['text']):,} bytes, ETag {r['etag']}")
r2 = raw("/products/python/", {"If-None-Match": r["etag"]})
print(f"same URL with If-None-Match: HTTP {r2['status']}, {len(r2['text'])} bytes")
```

Output (from the run on 2026-11-18, 23:54 UTC):

```text
robots.txt HTTP 200: ['User-Agent: *', 'Allow: /', 'Sitemap: https://endoflife.date/sitemap.xml']
README HTTP 200: found: 'The API is currently in Beta, and breaking changes can happen.'
README HTTP 200: found: 'Licensed under the MIT License.'
LICENSE HTTP 200: found: 'Copyright 2020 endoflife.date contributors'
LICENSE HTTP 200: found: 'Permission is hereby granted, free of charge'
LICENSE HTTP 200: found: 'to deal in the Software without restriction'
openapi.yml HTTP 200 application/x-yaml: found: 'name: MIT License'
openapi.yml HTTP 200 application/x-yaml: found: 'follow the 301 redirects (products, categories or tags may occasionally be renamed)'
openapi.yml HTTP 200 application/x-yaml: found: 'the body of the response is not JSON, but our HTML error page'
openapi.yml HTTP 200 application/x-yaml: found: 'The response may contain a `Retry-After` header indicating when the client can retry the request.'
openapi.yml HTTP 200 application/x-yaml: found: 'This is to prevent abuse of the API and ensure fair usage for all users.'
openapi.yml HTTP 200 application/x-yaml: found: 'Our API is hosted on [Netlify]'
openapi.yml HTTP 200 application/x-yaml: found: 'Whether this release cycle still have some level of support.'

one release cycle          HTTP 200 application/json {"name": "3.12", "label": "3.12", "isEol": false, "eolFrom": "2028-10-31", "isMaintained": true}
latest cycle               HTTP 200 application/json {"name": "26", "label": "26 (LTS)", "isEol": false, "eolFrom": "2029-04-30", "isMaintained": true}
upper-case product         HTTP 200 application/json {"name": "3.12", "label": "3.12", "isEol": false, "eolFrom": "2028-10-31", "isMaintained": true}
alias node (301)           HTTP 200 application/json after a redirect to /products/nodejs/releases/latest {"name": "26", "label": "26 (LTS)", "isEol": false, "eolFrom": "2029-04-30", "isMaintained": true}
alias pg (301)             HTTP 200 application/json after a redirect to /products/postgresql/ {"name": "postgresql", "label": "PostgreSQL", "category": "database"}
patch version as a cycle   HTTP 404 text/html 'Page not Found | endoflife.date'
'v' prefix                 HTTP 404 text/html 'Page not Found | endoflife.date'
unknown product java       HTTP 404 text/html 'Page not Found | endoflife.date'
typo pyhton                HTTP 404 text/html 'Page not Found | endoflife.date'
tag java-distribution      HTTP 200 application/json 14 items, first 'alibaba-dragonwell'
category lang              HTTP 200 application/json 34 items, first 'alibaba-dragonwell'
unknown category           HTTP 404 text/html 'Page not Found | endoflife.date'

product python: HTTP 200, 11,718 bytes, ETag W/"46573980c3c2eb6161f353ddf75568e1-ssl"
same URL with If-None-Match: HTTP 304, 0 bytes
```

### 3. A whole stack with Python urllib: robots check for every agent, end-of-life flags, disk cache with ETag revalidation (no browser)

Sends a descriptive User-Agent (curl's default User-Agent also got HTTP 200). One `/products/<product>/` call per product, cached as one JSON file per URL with its ETag. Run with an empty cache; the last lines age one entry past the TTL to show the HTTP 304 path.

```python
import hashlib, json, os, re, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

STACK = [("python", "3.11.9"), ("nodejs", "18.20.4"), ("ubuntu", "22.04.4"), ("postgresql", "16.3"),
         ("redis", "7.2.5"), ("django", "4.2.14"), ("nginx", "1.26.1"), ("kubernetes", "1.30.2")]
WARN_DAYS = 365  # flag cycles that reach end of life within this many days

API = "https://endoflife.date/api/v1"
UA = "endoflife-date-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/endoflife-date-skill"
CACHE = os.path.expanduser(CACHE_DIR)
TTL = 6 * 3600   # serve from disk without asking for 6 h, then revalidate with the ETag (a 304 costs no body)
PAUSE = 1.0      # no published limit; 1 request per second
calls = {"200": 0, "304": 0, "cache": 0}

def retry_after(v):
    """Retry-After in seconds: a number or an HTTP date; 60 when absent or unreadable; at least 1. Over 120 s: exit."""
    try:
        s = float(v)
    except (TypeError, ValueError):
        try:
            s = (parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()
        except (TypeError, ValueError):
            s = 60
    if s != s:  # 'nan'
        s = 60
    if s > 120:
        sys.exit(f"server asks to wait {s:.0f} s (over 120 s): stopping")
    return max(s, 1)

def get(path):
    """-> parsed JSON, or None on 404 (an HTML page, not JSON). urllib follows the 301s of renamed products and aliases.
    Disk cache: fresh for TTL, then revalidated with If-None-Match. Once waits Retry-After (default 60 s) on
    429/502/503/504 or a network error; exits on anything else."""
    url = API + path
    f = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ".json")
    cached = None
    try:
        cached = json.load(open(f))
        if time.time() - os.path.getmtime(f) < TTL:
            calls["cache"] += 1
            return cached["body"]
    except (OSError, ValueError):
        pass
    headers = {"User-Agent": UA}
    if cached and cached.get("etag"):
        headers["If-None-Match"] = cached["etag"]
    for attempt in range(2):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
                ctype, etag, raw = r.headers.get("Content-Type", ""), r.headers.get("ETag"), r.read()
            break
        except urllib.error.HTTPError as e:
            if e.code == 304 and cached:
                calls["304"] += 1
                os.utime(f)
                return cached["body"]
            if e.code == 404:
                return None
            if e.code in (429, 502, 503, 504) and attempt == 0:
                time.sleep(retry_after(e.headers.get("Retry-After")))
                continue
            sys.exit(f"HTTP {e.code} {url}: {' '.join(e.read().decode(errors='replace').split())[:200]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url}: {e}")
    if "json" not in ctype:
        sys.exit(f"{url}: {ctype!r} is not JSON: stopping")
    calls["200"] += 1
    body = json.loads(raw)
    os.makedirs(CACHE, exist_ok=True)
    json.dump({"etag": etag, "body": body}, open(f, "w"))
    return body

def cycle(version, releases):
    """'18.20.4' -> cycle '18', '22.04.4' -> '22.04', '1.30.2' -> '1.30'; the longest cycle name followed by a dot or '-'."""
    v = version.lower().lstrip("v")
    found = [r for r in releases if v == r["name"].lower() or v.startswith((r["name"].lower() + ".", r["name"].lower() + "-"))]
    return max(found, key=lambda r: len(r["name"]), default=None)

def nums(s):
    return tuple(int(x) for x in re.findall(r"\d+", s or ""))

# robots.txt is 'User-Agent: * / Allow: /' (no named AI-agent groups): check every agent on the API paths used.
rp = urllib.robotparser.RobotFileParser("https://endoflife.date/robots.txt")
with urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30) as r:
    rp.parse(r.read().decode().splitlines())
    print(f"robots.txt HTTP {r.status}")
for p in ("/api/v1/products/python/", "/api/v1/products/nodejs/releases/latest"):
    ok = all(rp.can_fetch(a, "https://endoflife.date" + p) for a in AGENTS)
    print(f"  robots {p:<40} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
    if not ok:
        sys.exit("robots.txt now disallows a path this skill uses: stop")

now = datetime.now(timezone.utc)
today = now.date()
print(f"\nStack check against endoflife.date, {now:%Y-%m-%d %H:%M} UTC (flag: end of life within {WARN_DAYS} days)")
for product, version in STACK:
    d = get(f"/products/{product}/")
    if d is None:
        print(f"  {product:<11}{version:<9} unknown product (HTTP 404): look the name up in {API}/products")
        continue
    p = d["result"]
    r = cycle(version, p["releases"])
    if r is None:
        print(f"  {product:<11}{version:<9} no cycle matches; cycles: {', '.join(x['name'] for x in p['releases'][:8])}")
        continue
    eol = r["eolFrom"]
    left = (datetime.strptime(eol, "%Y-%m-%d").date() - today).days if eol else None
    state = ("EOL" if (left is not None and left <= 0) or (left is None and r["isEol"]) else
             "UNKNOWN" if left is None and not r["isMaintained"] else  # no date, not EOL, not maintained: flags disagree
             "EOL SOON" if left is not None and left <= WARN_DAYS else "ok")
    extra = ""
    if state != "ok" and r.get("eoesFrom") and r["eoesFrom"] > str(today):
        extra = f", then {p['labels'].get('eoes') or 'extended support'} until {r['eoesFrom']}"
    elif state == "EOL" and r["isMaintained"]:
        extra = f", API still says maintained ({p['labels'].get('eoes') or 'extended support'}, no end date)"
    lt = (r.get("latest") or {}).get("name")
    patch = f"; latest {lt}" + (" (update)" if lt and nums(version) < nums(lt) else "") if lt else ""
    print(f"  {product:<11}{version:<9} cycle {r['name']:<6} {state:<9} eol {eol or 'not known'}"
          + (f" ({left:+d} days)" if left is not None else "") + extra + patch)

first = dict(calls)
for product, _ in STACK[:3]:  # repeated lookups come from the disk cache
    get(f"/products/{product}/")
f = os.path.join(CACHE, hashlib.sha256(f"{API}/products/python/".encode()).hexdigest() + ".json")
os.utime(f, (time.time() - TTL - 1,) * 2)  # age one entry past the TTL: the next lookup revalidates with its ETag
get("/products/python/")
print(f"\nfirst pass: {first['200']} HTTP 200 downloads, {first['304']} 304s, {first['cache']} cache hits; "
      f"then 3 repeats -> {calls['cache']} cache hits, 1 aged entry -> {calls['304']} HTTP 304 (cache {CACHE_DIR})")
print("Source: endoflife.date (https://endoflife.date), community-maintained data; confirm with each vendor's policy.")
```

Output (from the re-run on 2026-11-19, 01:15 UTC, empty cache):

```text
robots.txt HTTP 200
  robots /api/v1/products/python/                 allowed for all 11 agents
  robots /api/v1/products/nodejs/releases/latest  allowed for all 11 agents

Stack check against endoflife.date, 2026-11-19 01:15 UTC (flag: end of life within 365 days)
  python     3.11.9    cycle 3.11   EOL SOON  eol 2027-10-31 (+346 days); latest 3.11.18 (update)
  nodejs     18.20.4   cycle 18     EOL       eol 2025-04-30 (-568 days), API still says maintained (Commercial Support, no end date); latest 18.20.8 (update)
  ubuntu     22.04.4   cycle 22.04  EOL SOON  eol 2027-06-01 (+194 days), then Expanded Security Maintenance until 2032-04-21; latest 22.04.5 (update)
  postgresql 16.3      cycle 16     ok        eol 2028-11-09 (+721 days); latest 16.16 (update)
  redis      7.2.5     cycle 7.2    ok        eol 2029-12-01 (+1108 days); latest 7.2.17 (update)
  django     4.2.14    cycle 4.2    EOL       eol 2026-04-07 (-226 days); latest 4.2.30 (update)
  nginx      1.26.1    cycle 1.26   EOL       eol 2025-04-23 (-575 days); latest 1.26.3 (update)
  kubernetes 1.30.2    cycle 1.30   EOL       eol 2025-07-15 (-492 days); latest 1.30.14 (update)

first pass: 8 HTTP 200 downloads, 0 304s, 0 cache hits; then 3 repeats -> 3 cache hits, 1 aged entry -> 1 HTTP 304 (cache ~/.cache/endoflife-date-skill)
Source: endoflife.date (https://endoflife.date), community-maintained data; confirm with each vendor's policy.
```

### 4. curl, headers and mistakes

```bash
B=https://endoflife.date/api/v1
UA='endoflife-date-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# one release cycle: is it end of life, and when? (the cycle name, never a patch version)
curl -sS --fail -A "$UA" "$B/products/python/releases/3.12" \
  | python3 -c 'import sys, json
r = json.load(sys.stdin)["result"]
print("python", r["name"], "| isEol", r["isEol"], "| eolFrom", r["eolFrom"], "| isMaintained", r["isMaintained"], "| latest", r["latest"]["name"], r["latest"]["date"])'
sleep 1
# the newest cycle; -L follows the 301 of an alias (node -> nodejs)
curl -sS --fail -L -A "$UA" "$B/products/node/releases/latest" \
  | python3 -c 'import sys, json
r = json.load(sys.stdin)["result"]
print("node latest ->", r["label"], "| LTS", r["isLts"], "| latest", r["latest"]["name"], r["latest"]["date"], "| eolFrom", r["eolFrom"])'
sleep 1
# the alias without -L: a 301 with a text/plain body
curl -sS -A "$UA" -o /dev/null -w 'node (no -L) -> HTTP %{http_code} %{content_type} Location %{redirect_url}\n' "$B/products/node/"
sleep 1
# headers: JSON, CORS open, revalidate every time, an ETag
curl -sS -A "$UA" -D - -o /dev/null "$B/products/python/" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|access-control-allow-origin|cache-control|etag|retry-after|x-ratelimit-limit|server):)'
sleep 1
# conditional GET: the same ETag gives HTTP 304 and no body
E=$(curl -sS -A "$UA" -D - -o /dev/null "$B/products/python/" | tr -d '\r' | sed -n 's/^etag: //Ip')
sleep 1
curl -sS -A "$UA" -H "If-None-Match: $E" -o /dev/null -w 'If-None-Match -> HTTP %{http_code}, %{size_download} bytes\n' "$B/products/python/"
sleep 1
# mistakes: an unknown product or a patch version is HTTP 404 with an HTML page, so --fail and a JSON parse both stop
T=$(mktemp)
for p in products/java/ products/python/releases/3.12.4; do
  curl -sS -A "$UA" -o "$T" -w "$p -> HTTP %{http_code} %{content_type} " "$B/$p"
  grep -o '<title>[^<]*</title>' "$T"; sleep 1
done
rm -f "$T"
```

Output (from the run on 2026-11-18, 23:56 UTC):

```text
python 3.12 | isEol False | eolFrom 2028-10-31 | isMaintained True | latest 3.12.16 2026-10-25
node latest -> 26 (LTS) | LTS True | latest 26.13.1 2026-11-11 | eolFrom 2029-04-30
node (no -L) -> HTTP 301 text/plain Location https://endoflife.date/api/v1/products/nodejs/
HTTP/2 200 
access-control-allow-origin: *
cache-control: public,max-age=0,must-revalidate
content-type: application/json
etag: "46573980c3c2eb6161f353ddf75568e1-ssl"
server: Netlify
If-None-Match -> HTTP 304, 0 bytes
products/java/ -> HTTP 404 text/html; charset=utf-8 <title>Page not Found | endoflife.date</title>
products/python/releases/3.12.4 -> HTTP 404 text/html; charset=utf-8 <title>Page not Found | endoflife.date</title>
```

## Fields (`/api/v1/products/<product>/` and `/releases/<cycle>`, schema 1.2.1)

| Field | Value | Notes |
|---|---|---|
| `generated_at` | ISO time | the same `2026-11-18T09:37:30+00:00` on every response of the day: the build time of the static files, not the request time |
| `last_modified` | ISO time | product endpoint only; Python `2026-11-16T22:35:06+00:00` matches its page's "Last updated on 16 November 2026" |
| `result.name`, `label`, `aliases`, `category`, `tags` | `nodejs`, `Node.js`, `["node"]`, `framework`, ... | `category` is one of 9 (`server-app` 176 products, `framework` 74, `os` 68, `app` 62, `lang` 34, `database` 27, `service` 25, `device` 21, `standard` 2) |
| `labels.eoas`, `eol`, `eoes` | phase names | Node.js: "Active Support", "Security Support", "Commercial Support"; Ubuntu: "Hardware & Maintenance", "Maintenance & Security Support", "Expanded Security Maintenance"; PostgreSQL has only `eol` "Support Status" |
| `links.html`, `links.releasePolicy` | URLs | the endoflife.date page and the vendor's policy; cite both. `links.icon` is a Simple Icons brand logo |
| `versionCommand` | text or null | how to read the installed version, e.g. `python --version`, `cat /etc/os-release` |
| `releases[]` | newest first | `[0]` is the same cycle as `/releases/latest` |
| `releases[].name`, `codename`, `label` | `22.04`, `Jammy Jellyfish`, `22.04 'Jammy Jellyfish' (LTS)` | `name` is the path segment for `/releases/<name>` |
| `releaseDate` | date | never null in the 9,419 cycles |
| `isLts`, `ltsFrom` | bool, date or null | |
| `isEoas`, `eoasFrom` | bool, date or null | absent when the product has no active-support phase (PostgreSQL) |
| `isEol`, `eolFrom` | bool, date or null | `eolFrom` null in 1,288 cycles (553 of them `isEol` true, e.g. Android 4.x) |
| `isEoes`, `eoesFrom` | bool or null, date or null | extended support; present in 1,126 cycles |
| `isDiscontinued`, `discontinuedFrom` | bool, date or null | hardware; present in 273 cycles |
| `isMaintained` | bool | any support left, extended included |
| `latest.name`, `latest.date`, `latest.link` | newest patch | `latest` null in 2,423 cycles |
| `custom` | object or null | per product, e.g. Python `{"pep": "PEP-0693"}` |
| response headers | `Content-Type: application/json`, `Access-Control-Allow-Origin: *`, `Cache-Control: public,max-age=0,must-revalidate`, `ETag`, `Server: Netlify` | no rate-limit headers seen. The browser saw a weak ETag (`W/"..."`), curl a strong one; both revalidated to 304 |

Counts are from one `GET /api/v1/products/full` (3.06 MB, all 489 products with every cycle) on 2026-11-18 23:48 UTC; the spec says "Preferably, use the /products endpoint to get a summary of the products and reduce the amount of data transferred", so the blocks use `/products` plus one call per product.

## Gotchas

- **The flags are as of the build, the dates are not.** `isEol`, `isEoas` and `isMaintained` come with `generated_at`, which the spec calls "The time this response was generated" but which stayed `2026-11-18T09:37:30+00:00` on every response from 2026-11-18 23:47 to 2026-11-19 00:02 UTC, so it is a build time (the README lists Jekyll, "a static site generator", and Netlify, which the `Server` header names). So a cycle whose `eolFrom` passes after a build would read `isEol` false until the next one (inferred from `generated_at`; not observed). Blocks 1 and 3 compare `eolFrom` with today and fall back to `isEol` only when the date is null. On 2026-11-18 no cycle disagreed. The blocks count the `eolFrom` day itself as end of life; the spec does not say.
- **"Supported" needs a definition.** Python 3.12 is past active support (`eoasFrom` 2025-04-02) and gets security fixes only until 2028-10-31. Node.js 20 is past `eolFrom` but `isMaintained` true (paid "Commercial Support", `eoesFrom` null). Ubuntu 20.04 is past `eolFrom` but has Expanded Security Maintenance until 2030-04-23. Report the phase and its product-specific label, as the blocks do, not a single yes/no.
- **Cycle names differ per product** (`3.12`, `20`, `22.04`, `1.30`, `7.2`), and `latest.name` need not be a plain version (Amazon EKS 1.31: `1.31-eks-70`). Map a version to its cycle by the longest cycle name followed by a dot or a hyphen (`1.31-eks-70` -> `1.31`). A leading `v` (`v20.11.1`) is not part of any cycle name; the blocks drop it.
- **Unknown names fail as HTML 404**, with no suggestion. Resolve names first from `/products` (names, labels and the 214 products with aliases). "Java" is not a product: the JDK builds are separate products (`oracle-jdk`, `eclipse-temurin`, `amazon-corretto`, `openjdk-builds-from-oracle` and 10 more; tag `java-distribution`, 14 products).
- **Aliases and renamed products answer HTTP 301** with a `text/plain` body "Redirecting to /api/v1/products/nodejs/". `fetch()` (block 2) and urllib (`/products/node/releases/latest` -> `/products/nodejs/releases/latest`, HTTP 200) follow it; curl needs `-L` (block 4). The spec asks clients to follow 301s.
- **Case does not matter in the path** (`/products/PYTHON/releases/3.12` and `/releases/LATEST` were HTTP 200), and the trailing slash is optional.
- **The spec downloads.** https://endoflife.date/docs/api/v1/openapi.yml is `application/x-yaml`, so a browser page load saves it instead of rendering it; read it with `fetch()` or curl. The human docs at https://endoflife.date/docs/api/v1/ are Swagger UI loading that file.
- **Beta.** The README calls the API "Beta, and breaking changes can happen", while the spec promises backward compatibility within `/api/v1` if clients follow 301s and accept new fields and enum values. Read fields by name and ignore unknown ones.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **Patch versions or a `v` prefix in the path** (`/releases/3.12.4`, `/releases/v20`, `/releases/22.04.3`): HTTP 404 HTML. Fetch the product and map locally (blocks 1 and 3).
- **`/products/<product>/releases/<cycle>/latest`**: HTTP 404; `latest` is only a cycle alias directly under `/releases/`.
- **A terms or credits page on the site**: `/terms` and `/credits` are HTTP 404; the license and credits are in the GitHub repository.
- **Not tested:** the 429 response (never provoked; the spec gives no limit and no fixed wait), `/identifiers/<type>` lookups by purl or CPE, and `/products/full` inside the blocks (fetched once for the counts above).
