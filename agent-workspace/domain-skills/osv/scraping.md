# OSV.dev - Check a Pinned Dependency Version for Known Vulnerabilities, With CVE Aliases, Severity and Fixed Versions (API, no key)

Field-tested against api.osv.dev on 2026-11-15 (US Pacific evening; 2026-11-16 04:49-04:59 UTC) using a fresh Browser Use cloud browser (logged out) plus Python `urllib` and `curl` from a Linux machine. 5 browser page loads (an API JSON page, both robots files and the osv.dev home page) and 30 in-page `fetch()` calls, 39 curl calls and 78 urllib calls to api.osv.dev, all serial at 0.5 s or more spacing: every call was HTTP 200 except the deliberate HTTP 400, 404 and 405 probes below. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-15, curl and the cloud browser): https://api.osv.dev/robots.txt does not exist (HTTP 404, `{"code":404,"message":"The current request is not defined by this API."}`), which means no rules; block 3 checks all 11 agents with `urllib.robotparser` (`allow_all=True`). https://osv.dev/robots.txt is one line, `Sitemap: https://osv.dev/sitemap_index.xml`, with no `User-agent` group. No named AI-agent groups on either host, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider may fetch the `/v1/query`, `/v1/querybatch` and `/v1/vulns/<id>` paths used here. Terms: osv.dev has no terms-of-use page; the home page has 69 links and none to terms, privacy, licence or policy (cloud browser, 2026-11-15). The FAQ (https://google.github.io/osv.dev/faq/) says the API is for "Open source consumers: By querying OSV.dev's API and using our tooling to find known vulnerabilities in their dependencies", and "Is the API rate limited? No. Currently there is not a limit on the API." No AI/ML, scraping, automated-access or non-commercial clause on the FAQ, API or data pages. Licence is per source, from the data page (https://google.github.io/osv.dev/data/): GitHub Advisory Database, PyPI Advisory Database, Go Vulnerability Database and OSS-Fuzz are CC-BY 4.0, Rust Advisory Database CC0 1.0, Ubuntu and Alpine CC-BY-SA 4.0, and "Chainguard / Wolfi (CC-BY-NC-ND 4.0 / Chainguard License for Commercial Scanners)". This skill therefore never queries the Chainguard or Wolfi ecosystems, drops any `CGA-` record, and credits each record's source database. Naming: "OSV.dev" as plain text, no logos. This skill is not affiliated with or endorsed by OSV.dev, Google or any of the source databases.

**Attribution:** credit each record's source with its licence, for example "GitHub Advisory Database (CC-BY 4.0) via OSV.dev", plus the record ID and access date. The source is the ID prefix (`GHSA-`, `PYSEC-`, `GO-`, `RUSTSEC-`) and the exact file is `affected[].database_specific.source`. Blocks 1 and 3 print a source line.

## Quick summary

- **No scraping.** `POST https://api.osv.dev/v1/query` with `{"package":{"name":"jinja2","ecosystem":"PyPI"},"version":"2.11.2"}` returns every matching record in full. `POST /v1/querybatch` takes many pins and returns only IDs; `GET /v1/vulns/<id>` returns one record (any alias works as the id). JSON, no key.
- **Answer, jinja2 2.11.2 on PyPI (run 2026-11-16 04:56 UTC):** **10 records = 5 vulnerabilities**, because each one is listed twice (GitHub `GHSA-` and PyPI `PYSEC-`): CVE-2020-28493 (ReDoS, fixed 2.11.3), CVE-2024-22195 and CVE-2024-34064 (xmlattr HTML attribute injection, fixed 3.1.3 and 3.1.4), CVE-2024-56326 (sandbox breakout, fixed 3.1.5) and **CVE-2025-27516 / GHSA-cpwx-vrp4-4pq7** (sandbox breakout through the `attr` filter, fixed 3.1.6). All 5 are MODERATE in GitHub's label. Upgrade to **3.1.6**; a re-query of 3.1.6 returns 0 records.
- **Answer, lodash 4.17.15 on npm:** **5 GHSA records**, 3 HIGH: CVE-2020-8203 prototype pollution (fixed 4.17.19), CVE-2021-23337 **command injection** (fixed 4.17.21), CVE-2026-4800 code injection via `_.template` (fixed 4.18.0); 2 MODERATE: CVE-2020-28500 ReDoS (fixed 4.17.21), CVE-2025-13465 **prototype pollution** in `_.unset`/`_.omit` (fixed 4.17.23). The highest fix, 4.18.0, is **not clean**: it matches GHSA-f23m-r3pf-42rh / CVE-2026-2950 (introduced in 4.17.23, fixed in 4.18.1). Upgrade to **4.18.1**; a re-query returns 0 records.
- **Records are not vulnerabilities.** Merge records that list each other in `aliases` before counting. Read the fixed version only from the `affected[]` entry for your exact package: one lodash record also covers lodash-es, lodash.set, lodash-rails and others, with different fixes.
- **Silent failures:** a misspelled package (`jinja22`) or a version OSV has no record for is HTTP 200 with `{}`, the same answer as a clean version. A lower-case ecosystem (`pypi`) is a loud HTTP 400 `invalid ecosystem`.
- **Rate limit:** none ("Currently there is not a limit on the API", FAQ). Responses are capped at 32 MiB on HTTP/1.1 and uncapped on HTTP/2 (FAQ). Python `urllib` is HTTP/1.1; curl used HTTP/2. Blocks stay serial, pause 0.5 to 1 s, and wait 60 s once on 429/500/502/503/504.

## What works

### 1. Is this pinned version vulnerable, and what version fixes everything? (browser)

`on_api_tab()` opens one logged-out api.osv.dev JSON page, so `fetch()` is same-origin. `call()` posts JSON, waits 60 s once on 429/500/502/503/504 and otherwise raises. `query()` refuses Chainguard/Wolfi, follows `next_page_token` and drops `CGA-` records. The block merges alias records, reads the fix from the exact package's `affected[]` entry, then re-queries the candidate upgrade until OSV returns nothing.

```python
import json, re, time, textwrap
from datetime import datetime, timezone

PINS = [("PyPI", "jinja2", "2.11.2"), ("npm", "lodash", "4.17.15")]  # (ecosystem, package, pinned version)

API = "https://api.osv.dev"
PAUSE = 1.0  # the FAQ says "Currently there is not a limit on the API"; stay serial anyway
# Chainguard / Wolfi data is CC-BY-NC-ND 4.0 (data sources page): never query it, drop any of its records.
SKIP_ECOSYSTEMS = ("Chainguard", "Wolfi")
SKIP_PREFIXES = ("CGA-",)
# Record ID prefix -> (source database, licence), from https://google.github.io/osv.dev/data/
SOURCES = {"GHSA-": ("GitHub Advisory Database", "CC-BY 4.0"), "PYSEC-": ("PyPI Advisory Database", "CC-BY 4.0"),
           "GO-": ("Go Vulnerability Database", "CC-BY 4.0"), "RUSTSEC-": ("Rust Advisory Database", "CC0 1.0")}

def on_api_tab():
    """fetch() runs same-origin from a logged-out api.osv.dev tab (a /v1/vulns JSON page). Reuse it."""
    try:
        if js("location.origin") == API:
            return
    except Exception:
        pass
    new_tab(API + "/v1/vulns/GHSA-cpwx-vrp4-4pq7")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != API or '"id":"GHSA-cpwx-vrp4-4pq7"' not in body:
        raise RuntimeError(f"api.osv.dev did not serve a record (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__o = window.__o || {}; const id = String(Math.random()).slice(2); window.__o[id] = null;
  const body = %s; fetch(%s, body === null ? {credentials: 'omit'} :
      {method: 'POST', credentials: 'omit', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})
    .then(async r => { window.__o[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__o[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__o[%s]; if (v) delete window.__o[%s]; return v; })()"""

def call(path, body=None, timeout=60):
    """POST body (or GET when None) from inside the tab -> parsed JSON. Waits 60 s once on 429/500/502/503/504 or a
    network error, raises on anything else (400 = {"code": 3, "message": "invalid ecosystem"} and similar)."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % (json.dumps(body), json.dumps(API + path))))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{path}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(60)
            continue
        if r["status"] != 200 or "json" not in (r["type"] or ""):
            raise RuntimeError(f"{path} {json.dumps(body)}: HTTP {r['status']} {r['text'][:200]!r}; stopping")
        return json.loads(r["text"])

def query(eco, name, version):
    """Every OSV record for one package version, following next_page_token if the API pages."""
    if eco.split(":")[0] in SKIP_ECOSYSTEMS:
        raise RuntimeError(f"{eco} records are CC-BY-NC-ND 4.0: this skill does not query them")
    body, out = {"package": {"name": name, "ecosystem": eco}, "version": version}, []
    while True:
        d = call("/v1/query", body)
        out += d.get("vulns", [])
        if not d.get("next_page_token"):
            return [v for v in out if not v["id"].startswith(SKIP_PREFIXES)]
        body["page_token"] = d["next_page_token"]

def norm(eco, name):
    return re.sub(r"[-_.]+", "-", name.lower()) if eco == "PyPI" else name  # PyPI names are case/punctuation-insensitive

def vkey(v):
    """Numeric sort key for plain dotted versions (4.17.21 > 4.17.19); the re-query below is the final check.
    Pre-releases and other suffixes (3.1.6rc1, 1.0.0-beta) order differently per ecosystem: stop instead of guessing."""
    if not re.fullmatch(r"\d+(\.\d+)*", v):
        raise RuntimeError(f"version {v!r} is not plain dotted numbers: compare it with the ecosystem's own rules")
    return tuple(int(x) for x in v.split("."))

def fixes_for(v, eco, name, version):
    """Fixed versions above the pin from the affected[] entries for exactly this package (a record often also lists
    sibling packages such as lodash-es with a different fix); None if the entry has no 'fixed' event."""
    mine = [a for a in v.get("affected", []) if a.get("package", {}).get("ecosystem") == eco
            and norm(eco, a["package"].get("name", "")) == norm(eco, name)]
    if not mine:
        raise RuntimeError(f"{v['id']} came back for {name} but lists no affected entry for it: stop")
    fixed = sorted({e["fixed"] for a in mine for r in a.get("ranges", []) if r["type"] != "GIT"  # GIT = commit hashes
                    for e in r["events"] if "fixed" in e}, key=vkey)
    above = [f for f in fixed if vkey(f) > vkey(version)]
    return above[0] if above else None, mine

def groups(vulns):
    """Merge records that are aliases of each other (GHSA-x and PYSEC-y for the same CVE) into one issue."""
    ids = {v["id"] for v in vulns}
    parent = {i: i for i in ids}
    def find(i):
        while parent[i] != i:
            i = parent[i]
        return i
    for v in vulns:
        for a in v.get("aliases", []):
            if a in ids:
                parent[find(a)] = find(v["id"])
    out = {}
    for v in vulns:
        out.setdefault(find(v["id"]), []).append(v)
    return list(out.values())

on_api_tab()
now = datetime.now(timezone.utc)
used = set()
for eco, name, version in PINS:
    vulns = query(eco, name, version)
    issues = groups(vulns)
    print(f"{name} {version} ({eco}): {len(vulns)} OSV records = {len(issues)} distinct vulnerabilities")
    targets, nofix = [], []
    for g in sorted(issues, key=lambda g: min(v.get("published", "") for v in g)):
        g.sort(key=lambda v: (not v["id"].startswith("GHSA-"), v["id"]))  # GitHub records carry the severity label
        main = g[0]
        cves = sorted({a for v in g for a in [v["id"], *v.get("aliases", [])] if a.startswith("CVE-")})
        fix, _ = fixes_for(main, eco, name, version)
        for v in g[1:]:  # every alias record must agree on the fix for this package
            f2, _ = fixes_for(v, eco, name, version)
            if f2 != fix:
                print(f"  note: {v['id']} gives fixed {f2}, {main['id']} gives {fix}")
        (targets if fix else nofix).append(fix or main["id"])
        label = main.get("database_specific", {}).get("severity") or "-"
        vec = " ".join(s["score"] for s in main.get("severity", []) if s["type"].startswith("CVSS_V3")) or \
              " ".join(s["score"] for s in main.get("severity", [])) or "no CVSS vector"
        for v in g:
            used.add(next((p for p in SOURCES if v["id"].startswith(p)), "other"))
        print(f"  {', '.join(cves) or 'no CVE'} | {' = '.join(v['id'] for v in g)} | {label} | fixed in {fix or 'NO FIX LISTED'}")
        print(textwrap.fill(f"{main.get('summary') or main['details'][:120]} ({vec}; published {main['published'][:10]})",
                            110, initial_indent="      ", subsequent_indent="      "))
    if nofix:
        print(f"  no fixed version listed for {nofix}: upgrading does not clear those")
    elif targets:
        # The highest fix is only a candidate: a later version can carry a newer record (lodash 4.17.23 introduced
        # CVE-2026-2950). Re-query the candidate and hop to the next fix until OSV returns nothing.
        up = max(targets, key=vkey)
        for hop in range(5):
            left = query(eco, name, up)
            if not left:
                print(f"  upgrade to {name} {up} or later: re-query of {up} returns 0 records")
                break
            nxt = [fixes_for(v, eco, name, up)[0] for v in left]
            print(f"  {up} still matches {[v['id'] + ' (' + ', '.join(a for a in v.get('aliases', []) if a.startswith('CVE-')) + ')' for v in left]}"
                  f", fixed in {nxt}")
            if None in nxt:
                print(f"  no fixed version for {name} {up} yet: stop at {up} and track those records")
                break
            up = max(nxt, key=vkey)
        else:
            raise RuntimeError(f"{name}: still vulnerable after 5 upgrade hops: check by hand")
    print()

credits = [f"{SOURCES[p][0]} ({SOURCES[p][1]})" for p in SOURCES if p in used]
if "other" in used:
    credits.append("other sources: check each record's licence on https://google.github.io/osv.dev/data/")
print(f"Source: OSV.dev API (https://api.osv.dev/v1/query), accessed {now:%d %B %Y %H:%M} UTC; records from "
      f"{'; '.join(credits)}. Chainguard/Wolfi records skipped (CC-BY-NC-ND 4.0).")
```

Output (from the run on 2026-11-16, 04:56 UTC):

```text
jinja2 2.11.2 (PyPI): 10 OSV records = 5 distinct vulnerabilities
  CVE-2020-28493 | GHSA-g3rq-g295-4j3m = PYSEC-2021-66 | MODERATE | fixed in 2.11.3
      Regular Expression Denial of Service (ReDoS) in Jinja2 (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L;
      published 2021-03-19)
  CVE-2024-22195 | GHSA-h5c8-rqwp-cp95 = PYSEC-2026-1473 | MODERATE | fixed in 3.1.3
      Jinja vulnerable to HTML attribute injection when passing user input as keys to xmlattr filter
      (CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N; published 2024-01-11)
  CVE-2024-34064 | GHSA-h75v-3vvj-5mfj = PYSEC-2026-1474 | MODERATE | fixed in 3.1.4
      Jinja vulnerable to HTML attribute injection when passing user input as keys to xmlattr filter
      (CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N; published 2024-05-06)
  CVE-2024-56326 | GHSA-q2x7-8rv6-6q7h = PYSEC-2026-1475 | MODERATE | fixed in 3.1.5
      Jinja has a sandbox breakout through indirect reference to format method
      (CVSS:3.1/AV:L/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:H; published 2024-12-23)
  CVE-2025-27516 | GHSA-cpwx-vrp4-4pq7 = PYSEC-2026-1471 | MODERATE | fixed in 3.1.6
      Jinja2 vulnerable to sandbox breakout through attr filter selecting format method
      (CVSS:4.0/AV:L/AC:L/AT:P/PR:L/UI:P/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N; published 2025-03-05)
  upgrade to jinja2 3.1.6 or later: re-query of 3.1.6 returns 0 records

lodash 4.17.15 (npm): 5 OSV records = 5 distinct vulnerabilities
  CVE-2020-8203 | GHSA-p6mc-m468-83gw | HIGH | fixed in 4.17.19
      Prototype Pollution in lodash (CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:H/A:H; published 2020-07-15)
  CVE-2021-23337 | GHSA-35jh-r3h4-6jhm | HIGH | fixed in 4.17.21
      Command Injection in lodash (CVSS:3.1/AV:N/AC:L/PR:H/UI:N/S:U/C:H/I:H/A:H; published 2021-05-06)
  CVE-2020-28500 | GHSA-29mw-wpgm-hmr9 | MODERATE | fixed in 4.17.21
      Regular Expression Denial of Service (ReDoS) in lodash (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L;
      published 2022-01-06)
  CVE-2025-13465 | GHSA-xxjr-mmjv-4gpg | MODERATE | fixed in 4.17.23
      Lodash has Prototype Pollution Vulnerability in `_.unset`, `_.omit`, and `_.pullAt` functions
      (CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:L/A:L; published 2026-01-21)
  CVE-2026-4800 | GHSA-r5fr-rjxr-66jc | HIGH | fixed in 4.18.0
      lodash vulnerable to Code Injection via `_.template` imports key names
      (CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:H/A:H; published 2026-04-01)
  4.18.0 still matches ['GHSA-f23m-r3pf-42rh (CVE-2026-2950)'], fixed in ['4.18.1']
  upgrade to lodash 4.18.1 or later: re-query of 4.18.1 returns 0 records

Source: OSV.dev API (https://api.osv.dev/v1/query), accessed 16 November 2026 04:56 UTC; records from GitHub Advisory Database (CC-BY 4.0); PyPI Advisory Database (CC-BY 4.0). Chainguard/Wolfi records skipped (CC-BY-NC-ND 4.0).
```

### 2. robots.txt, query mistakes and record lookups (browser)

3 page loads and 16 in-page `fetch()` calls in the same tab.

```python
import json, time
from collections import Counter

API = "https://api.osv.dev"

START_JS = """(() => { window.__o = window.__o || {}; const id = String(Math.random()).slice(2); window.__o[id] = null;
  const [method, body] = %s; fetch(%s, {method, credentials: 'omit',
      ...(body === null ? {} : {headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)})})
    .then(async r => { const t = await r.text(); window.__o[id] = {status: r.status, bytes: new TextEncoder().encode(t).length, text: t.slice(0, 400000)}; })
    .catch(e => { window.__o[id] = {status: 0, bytes: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__o[%s]; if (v) delete window.__o[%s]; return v; })()"""

def raw(path, body=None, method=None):
    """One in-page request -> status, size and body. No retries: this block only inspects answers."""
    method = method or ("GET" if body is None else "POST")
    rid = json.dumps(js(START_JS % (json.dumps([method, body]), json.dumps(API + path))))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r

def brief(r):
    out = f"HTTP {r['status']} {r['bytes']:,} B"
    try:
        d = json.loads(r["text"])
    except ValueError:
        return out + f" {r['text'][:80]!r}"
    if "message" in d:
        return out + f" {d}"
    if "results" in d:
        return out + " " + str([len(x.get("vulns", [])) for x in d["results"]]) + " ids per query, keys of first id: " + \
            str(sorted(d["results"][0]["vulns"][0]))
    if "vulns" in d:
        pre = Counter(v["id"].split("-")[0] for v in d["vulns"])
        return out + f" {len(d['vulns'])} records {dict(pre)}" + (", has next_page_token" if d.get("next_page_token") else "")
    if "id" in d:
        return out + f" {d['id']} aliases {d.get('aliases')}, {len(d.get('related', []))} related"
    return out + f" {d}"

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.body ? document.body.innerText : ''")

try:
    on_api = js("location.origin") == API
except Exception:
    on_api = False
if not on_api:
    new_tab(API + "/v1/vulns/GHSA-cpwx-vrp4-4pq7")
    wait_for_load()

for url in ("https://api.osv.dev/robots.txt", "https://osv.dev/robots.txt"):
    st, txt = page(url)
    print(f"{url} HTTP {st}: {txt.strip()[:120]}")
page(API + "/v1/vulns/GHSA-cpwx-vrp4-4pq7")  # back to an api.osv.dev JSON page for same-origin fetch()
print()

J = {"name": "jinja2", "ecosystem": "PyPI"}
for label, path, body, method in (
    ("jinja2 2.11.2 PyPI               ", "/v1/query", {"package": J, "version": "2.11.2"}, None),
    ("name Jinja2 (capital J)          ", "/v1/query", {"package": {**J, "name": "Jinja2"}, "version": "2.11.2"}, None),
    ("ecosystem pypi (lower case)      ", "/v1/query", {"package": {**J, "ecosystem": "pypi"}, "version": "2.11.2"}, None),
    ("version v2.11.2                  ", "/v1/query", {"package": J, "version": "v2.11.2"}, None),
    ("misspelled package jinja22       ", "/v1/query", {"package": {**J, "name": "jinja22"}, "version": "2.11.2"}, None),
    ("fixed version 3.1.6              ", "/v1/query", {"package": J, "version": "3.1.6"}, None),
    ("no version (every jinja2 record) ", "/v1/query", {"package": J}, None),
    ("no ecosystem (all ecosystems)    ", "/v1/query", {"package": {"name": "jinja2"}, "version": "2.11.2"}, None),
    ("purl pkg:pypi/jinja2@2.11.2      ", "/v1/query", {"package": {"purl": "pkg:pypi/jinja2@2.11.2"}}, None),
    ("version only, no package         ", "/v1/query", {"version": "2.11.2"}, None),
    ("bad page_token                   ", "/v1/query", {"package": J, "version": "2.11.2", "page_token": "x"}, None),
    ("querybatch jinja2 + lodash       ", "/v1/querybatch", {"queries": [{"package": J, "version": "2.11.2"},
        {"package": {"name": "lodash", "ecosystem": "npm"}, "version": "4.17.15"}]}, None),
    ("GET /v1/vulns/GHSA-cpwx-vrp4-4pq7", "/v1/vulns/GHSA-cpwx-vrp4-4pq7", None, None),
    ("GET /v1/vulns/CVE-2025-27516     ", "/v1/vulns/CVE-2025-27516", None, None),
    ("GET /v1/vulns/GHSA-zzzz-zzzz-zzzz", "/v1/vulns/GHSA-zzzz-zzzz-zzzz", None, None),
    ("GET /v1/query (wrong method)     ", "/v1/query", None, "GET"),
):
    r = raw(path, body, method)
    print(f"{label} {brief(r)}")
    if label.startswith("no ecosystem") and r["status"] == 200:
        d = json.loads(r["text"])
        eco = Counter(a["package"]["ecosystem"].split(":")[0] for v in d["vulns"] for a in v["affected"] if a.get("package"))
        print(f"{'':35}  affected ecosystems: {dict(eco)}")
```

Output (from the run on 2026-11-16, 04:54 UTC):

```text
https://api.osv.dev/robots.txt HTTP 404: {"code":404,"message":"The current request is not defined by this API."}
https://osv.dev/robots.txt HTTP 200: Sitemap: https://osv.dev/sitemap_index.xml

jinja2 2.11.2 PyPI                HTTP 200 26,849 B 10 records {'GHSA': 5, 'PYSEC': 5}
name Jinja2 (capital J)           HTTP 200 26,849 B 10 records {'GHSA': 5, 'PYSEC': 5}
ecosystem pypi (lower case)       HTTP 400 40 B {'code': 3, 'message': 'invalid ecosystem'}
version v2.11.2                   HTTP 200 26,849 B 10 records {'GHSA': 5, 'PYSEC': 5}
misspelled package jinja22        HTTP 200 2 B {}
fixed version 3.1.6               HTTP 200 2 B {}
no version (every jinja2 record)  HTTP 200 51,473 B 20 records {'GHSA': 10, 'PYSEC': 10}
no ecosystem (all ecosystems)     HTTP 200 106,528 B 35 records {'DEBIAN': 7, 'DLA': 4, 'ECHO': 3, 'GHSA': 5, 'PYSEC': 5, 'RHLW': 1, 'UBUNTU': 6, 'USN': 4}
                                     affected ecosystems: {'Debian': 25, 'Echo': 3, 'PyPI': 10, 'Red Hat Lightwell': 1, 'Ubuntu': 54}
purl pkg:pypi/jinja2@2.11.2       HTTP 200 26,849 B 10 records {'GHSA': 5, 'PYSEC': 5}
version only, no package          HTTP 400 36 B {'code': 3, 'message': 'invalid query'}
bad page_token                    HTTP 400 37 B {'code': 3, 'message': 'invalid cursor'}
querybatch jinja2 + lodash        HTTP 200 1,065 B [10, 5] ids per query, keys of first id: ['id', 'modified']
GET /v1/vulns/GHSA-cpwx-vrp4-4pq7 HTTP 200 2,635 B GHSA-cpwx-vrp4-4pq7 aliases ['CVE-2025-27516', 'PYSEC-2026-1471'], 0 related
GET /v1/vulns/CVE-2025-27516      HTTP 200 2,940 B CVE-2025-27516 aliases ['GHSA-cpwx-vrp4-4pq7', 'PYSEC-2026-1471'], 8 related
GET /v1/vulns/GHSA-zzzz-zzzz-zzzz HTTP 404 46 B {'code': 5, 'message': 'Vulnerability not found'}
GET /v1/query (wrong method)      HTTP 405 133 B {'code': 405, 'message': 'The current request is matched to the defined url template "/v1/query" but its http method is not allowed'}
```

### 3. Many pins in one querybatch call, robots check for every agent (no browser)

Python's `urllib` speaks HTTP/1.1, so it is fine for `querybatch` (IDs only) and single records, but use curl or an HTTP/2 client for queries that may pass 32 MiB.

```python
import json, re, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timezone

API = "https://api.osv.dev"
UA = "osv-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
SKIP_ECOSYSTEMS = ("Chainguard", "Wolfi")  # CC-BY-NC-ND 4.0
SOURCES = {"GHSA-": "GitHub Advisory Database (CC-BY 4.0)", "PYSEC-": "PyPI Advisory Database (CC-BY 4.0)",
           "GO-": "Go Vulnerability Database (CC-BY 4.0)", "RUSTSEC-": "Rust Advisory Database (CC0 1.0)"}
PINS = [("PyPI", "jinja2", "2.11.2"), ("PyPI", "requests", "2.19.0"), ("PyPI", "flask", "3.1.2"),
        ("PyPI", "jinja2", "3.1.6"), ("npm", "lodash", "4.17.15"), ("Go", "golang.org/x/text", "0.3.0"),
        ("crates.io", "smallvec", "1.6.0"), ("Wolfi", "py3-jinja2", "3.1.4")]

def call(path, body=None):
    """POST JSON (or GET) -> parsed JSON. One 60 s wait on HTTP 429/500/502/503/504 or a network error; exits on
    anything else (400 carries {"code": 3, "message": ...}). urllib speaks HTTP/1.1, where responses are capped at
    32 MiB (FAQ); querybatch answers are ids only, so they stay small."""
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(API + path, data=data, headers={"User-Agent": UA, "Content-Type": "application/json"})
    for attempt in range(2):
        time.sleep(0.5)  # no published limit; stay serial
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"HTTP {e.code} {path} {data!r}: {e.read().decode()[:200]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{path}: {e}")

# robots.txt: api.osv.dev answers 404, which robotparser (like the robots standard) treats as "no rules".
rp = urllib.robotparser.RobotFileParser(API + "/robots.txt")
rp.read()
for p in ("/v1/query", "/v1/querybatch", "/v1/vulns/GHSA-cpwx-vrp4-4pq7"):
    ok = all(rp.can_fetch(a, API + p) for a in AGENTS)
    print(f"robots {p:<32} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents (allow_all={rp.allow_all})")
    if not ok:
        sys.exit("robots.txt now disallows a path this skill uses: stop")

now = datetime.now(timezone.utc)
# 1 querybatch call for every pin -> record ids; then one GET per distinct id for aliases, severity and fixes.
pins = [p for p in PINS if p[0].split(":")[0] not in SKIP_ECOSYSTEMS]
for p in PINS:
    if p not in pins:
        print(f"skipped {p[0]} {p[1]} {p[2]}: Chainguard/Wolfi data is CC-BY-NC-ND 4.0, not queried")
res = call("/v1/querybatch", {"queries": [{"package": {"name": n, "ecosystem": e}, "version": v} for e, n, v in pins]})["results"]
if len(res) != len(pins):
    sys.exit(f"querybatch returned {len(res)} results for {len(pins)} queries: stop")
ids = sorted({x["id"] for r in res for x in r.get("vulns", []) if not x["id"].startswith("CGA-")})
if any(r.get("next_page_token") for r in res):
    sys.exit("a batch result is paged: re-run that pin with /v1/query and its page_token")
print(f"\nquerybatch: {len(pins)} pins -> {sum(len(r.get('vulns', [])) for r in res)} record ids, {len(ids)} distinct; fetching each")
recs = {i: call(f"/v1/vulns/{i}") for i in ids}

def vkey(v):
    """Plain dotted versions only; anything else (3.1.6rc1, 1.0.0-beta) is listed apart, never ordered."""
    return tuple(int(x) for x in v.split(".")) if re.fullmatch(r"\d+(\.\d+)*", v) else None

def merge(ids_):
    """Alias groups: records that list each other (GHSA-x / PYSEC-y / GO-z for one CVE) count once."""
    out = []
    for i in ids_:
        g = {i, *recs[i].get("aliases", [])} & set(ids_)
        hit = [o for o in out if o & g]
        for o in hit:
            out.remove(o)
            g |= o
        out.append(g)
    return out

used = set()
print()
for (eco, name, version), r in zip(pins, res):
    mine = [x["id"] for x in r.get("vulns", []) if x["id"] in recs]
    grp = merge(mine)
    cves = sorted({a for i in mine for a in [i, *recs[i].get("aliases", [])] if a.startswith("CVE-")})
    sev = {}
    for g in grp:
        lab = next((recs[i]["database_specific"].get("severity") for i in sorted(g)
                    if i.startswith("GHSA-") and recs[i].get("database_specific", {}).get("severity")), "no label")
        sev[lab] = sev.get(lab, 0) + 1
    fixed = set()
    for i in mine:
        for a in recs[i].get("affected", []):  # affected[].package is optional in the OSV schema
            pk = a.get("package", {})
            if pk.get("ecosystem") == eco and pk.get("name", "").lower() == name.lower():
                fixed |= {e["fixed"] for rg in a.get("ranges", []) if rg["type"] != "GIT"  # GIT ranges hold commit hashes
                          for e in rg["events"] if "fixed" in e}
    used |= {p for i in mine for p in SOURCES if i.startswith(p)}
    print(f"{eco:<9} {name} {version}: {len(mine)} records, {len(grp)} distinct, severity {sev or '-'}")
    if mine:
        odd = sorted(f for f in fixed if vkey(f) is None or vkey(version) is None)
        above = sorted((f for f in fixed if f not in odd and vkey(f) > vkey(version)), key=vkey)
        print(f"          {', '.join(cves) or 'no CVE alias'}; fixed versions above the pin: {above}"
              + (f"; not ordered (pre-release or suffix): {odd}" if odd else ""))
        print(f"          records: {', '.join(mine)}")

print(f"\nrecords via OSV.dev API, accessed {now:%d %B %Y %H:%M} UTC, credited to: " + "; ".join(SOURCES[p] for p in SOURCES if p in used))
```

Output (from the run on 2026-11-16, 05:19 UTC):

```text
robots /v1/query                        allowed for all 11 agents (allow_all=True)
robots /v1/querybatch                   allowed for all 11 agents (allow_all=True)
robots /v1/vulns/GHSA-cpwx-vrp4-4pq7    allowed for all 11 agents (allow_all=True)
skipped Wolfi py3-jinja2 3.1.4: Chainguard/Wolfi data is CC-BY-NC-ND 4.0, not queried

querybatch: 7 pins -> 37 record ids, 37 distinct; fetching each

PyPI      jinja2 2.11.2: 10 records, 5 distinct, severity {'MODERATE': 5}
          CVE-2020-28493, CVE-2024-22195, CVE-2024-34064, CVE-2024-56326, CVE-2025-27516; fixed versions above the pin: ['2.11.3', '3.1.3', '3.1.4', '3.1.5', '3.1.6']
          records: GHSA-cpwx-vrp4-4pq7, GHSA-g3rq-g295-4j3m, GHSA-h5c8-rqwp-cp95, GHSA-h75v-3vvj-5mfj, GHSA-q2x7-8rv6-6q7h, PYSEC-2021-66, PYSEC-2026-1471, PYSEC-2026-1473, PYSEC-2026-1474, PYSEC-2026-1475
PyPI      requests 2.19.0: 10 records, 5 distinct, severity {'HIGH': 1, 'MODERATE': 4}
          CVE-2018-18074, CVE-2023-32681, CVE-2024-35195, CVE-2024-47081, CVE-2026-25645; fixed versions above the pin: ['2.20.0', '2.31.0', '2.32.0', '2.32.4', '2.33.0']
          records: GHSA-9hjg-9r4m-mvj7, GHSA-9wx4-h78v-vm56, GHSA-gc5v-m9x4-r6x2, GHSA-j8r2-6x86-q33q, GHSA-x84v-xcm2-53pg, PYSEC-2018-28, PYSEC-2023-74, PYSEC-2026-1872, PYSEC-2026-1873, PYSEC-2026-2275
PyPI      flask 3.1.2: 2 records, 1 distinct, severity {'LOW': 1}
          CVE-2026-27205; fixed versions above the pin: ['3.1.3']
          records: GHSA-68rp-wp8r-4726, PYSEC-2026-2151
PyPI      jinja2 3.1.6: 0 records, 0 distinct, severity -
npm       lodash 4.17.15: 5 records, 5 distinct, severity {'MODERATE': 2, 'HIGH': 3}
          CVE-2020-28500, CVE-2020-8203, CVE-2021-23337, CVE-2025-13465, CVE-2026-4800; fixed versions above the pin: ['4.17.19', '4.17.21', '4.17.23', '4.18.0']
          records: GHSA-29mw-wpgm-hmr9, GHSA-35jh-r3h4-6jhm, GHSA-p6mc-m468-83gw, GHSA-r5fr-rjxr-66jc, GHSA-xxjr-mmjv-4gpg
Go        golang.org/x/text 0.3.0: 8 records, 5 distinct, severity {'MODERATE': 1, 'HIGH': 2, 'no label': 2}
          CVE-2020-14040, CVE-2021-38561, CVE-2022-32149, CVE-2026-56851, CVE-2026-56852; fixed versions above the pin: ['0.3.3', '0.3.7', '0.3.8', '0.39.0', '0.41.0']
          records: GHSA-5rcv-m4m3-hfh7, GHSA-69ch-w2m2-3vjp, GHSA-ppp9-7jff-5vj2, GO-2020-0015, GO-2021-0113, GO-2022-1059, GO-2026-5970, GO-2026-6629
crates.io smallvec 1.6.0: 2 records, 1 distinct, severity {'CRITICAL': 1}
          CVE-2021-25900; fixed versions above the pin: ['1.6.1']
          records: GHSA-43w2-9j62-hq99, RUSTSEC-2021-0003

records via OSV.dev API, accessed 16 November 2026 05:19 UTC, credited to: GitHub Advisory Database (CC-BY 4.0); PyPI Advisory Database (CC-BY 4.0); Go Vulnerability Database (CC-BY 4.0); Rust Advisory Database (CC0 1.0)
```

### 4. curl

```bash
Q=https://api.osv.dev/v1/query
# the answer: every record for jinja2 2.11.2, with aliases, GitHub severity label and the fixed version for jinja2
curl -sS --fail "$Q" -H 'Content-Type: application/json' -d '{"package":{"name":"jinja2","ecosystem":"PyPI"},"version":"2.11.2"}' \
  | python3 -c 'import json,sys
for v in json.load(sys.stdin).get("vulns", []):
    fx = [e["fixed"] for a in v.get("affected", []) if a.get("package", {}).get("name") == "jinja2" for r in a.get("ranges", []) if r["type"] != "GIT" for e in r["events"] if "fixed" in e]
    print(v["id"], ",".join(v.get("aliases", [])), v.get("database_specific", {}).get("severity", "-"), "fixed", ",".join(fx))'
sleep 1
# protocol and headers: HTTP/2 by default (no 32 MiB cap), no rate-limit headers, CORS only when an Origin is sent
curl -sS -D - -o /dev/null "$Q" -H 'Origin: https://example.com' -d '{"package":{"name":"lodash","ecosystem":"npm"},"version":"4.17.15"}' \
  | tr -d '\r' | grep -iE '^(HTTP/|content-type|content-length|access-control-allow-origin|x-ratelimit|retry-after)'
sleep 1
# one record by id (any alias works as the id)
curl -sS --fail https://api.osv.dev/v1/vulns/CVE-2026-2950 | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["id"], d["aliases"], d.get("summary") or d["details"][:80])'
sleep 1
# mistakes: lower-case ecosystem is a loud 400; a misspelled package is a silent HTTP 200 with {}
curl -sS -w ' <- HTTP %{http_code}\n' "$Q" -d '{"package":{"name":"jinja2","ecosystem":"pypi"},"version":"2.11.2"}'
sleep 1
curl -sS -w ' <- HTTP %{http_code}\n' "$Q" -d '{"package":{"name":"jinja22","ecosystem":"PyPI"},"version":"2.11.2"}'
```

Output (from the run on 2026-11-16, 04:57 UTC):

```text
GHSA-cpwx-vrp4-4pq7 CVE-2025-27516,PYSEC-2026-1471 MODERATE fixed 3.1.6
GHSA-g3rq-g295-4j3m CVE-2020-28493,PYSEC-2021-66,SNYK-PYTHON-JINJA2-1012994 MODERATE fixed 2.11.3
GHSA-h5c8-rqwp-cp95 CVE-2024-22195,PYSEC-2026-1473 MODERATE fixed 3.1.3
GHSA-h75v-3vvj-5mfj CVE-2024-34064,PYSEC-2026-1474 MODERATE fixed 3.1.4
GHSA-q2x7-8rv6-6q7h CVE-2024-56326,PYSEC-2026-1475 MODERATE fixed 3.1.5
PYSEC-2021-66 CVE-2020-28493,GHSA-g3rq-g295-4j3m,SNYK-PYTHON-JINJA2-1012994 - fixed 2.11.3
PYSEC-2026-1471 CVE-2025-27516,GHSA-cpwx-vrp4-4pq7 - fixed 3.1.6
PYSEC-2026-1473 CVE-2024-22195,GHSA-h5c8-rqwp-cp95 - fixed 3.1.3
PYSEC-2026-1474 CVE-2024-34064,GHSA-h75v-3vvj-5mfj - fixed 3.1.4
PYSEC-2026-1475 CVE-2024-56326,GHSA-q2x7-8rv6-6q7h - fixed 3.1.5
HTTP/2 200 
content-type: application/json
content-length: 27426
access-control-allow-origin: https://example.com
CVE-2026-2950 ['GHSA-f23m-r3pf-42rh'] lodash vulnerable to Prototype Pollution via array path bypass in `_.unset` and `_.omit`
{"code":3,"message":"invalid ecosystem"} <- HTTP 400
{} <- HTTP 200
```

## Fields (OSV record JSON)

| Field | Example | Notes |
|---|---|---|
| `id` | `GHSA-cpwx-vrp4-4pq7`, `PYSEC-2026-1471`, `GO-2022-1059`, `RUSTSEC-2021-0003` | the prefix names the source database and so the licence; `CGA-` is Chainguard (CC-BY-NC-ND 4.0), skipped |
| `aliases` | `["CVE-2025-27516", "PYSEC-2026-1471"]` | CVE IDs and the other databases' IDs for the same issue; also `SNYK-PYTHON-JINJA2-1012994` |
| `related` | 8 entries on `CVE-2025-27516` | distro advisories (ALSA, SUSE) that are not aliases |
| `summary`, `details` | "Jinja2 vulnerable to sandbox breakout through attr filter selecting format method" | `summary` is missing on some records (PYSEC-2021-66); fall back to `details` |
| `database_specific.severity` | `MODERATE`, `HIGH`, `LOW`, `CRITICAL` | GitHub's label, on `GHSA-` records only; `PYSEC-` and `GO-` records have none (all 5 `GO-` records for golang.org/x/text 0.3.0) |
| `severity[]` | `{"type": "CVSS_V3", "score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:L"}` | a CVSS vector, not a number; some records carry `CVSS_V4` instead (GHSA-cpwx-vrp4-4pq7) |
| `affected[].package` | `{"name": "jinja2", "ecosystem": "PyPI", "purl": "pkg:pypi/jinja2"}` | one record can list several packages and ecosystems (npm lodash, lodash-es, RubyGems lodash-rails) |
| `affected[].ranges[]` | `{"type": "ECOSYSTEM", "events": [{"introduced": "0"}, {"fixed": "3.1.6"}]}` | `SEMVER` for npm, `ECOSYSTEM` for PyPI, `GIT` holds commit hashes; `last_affected` instead of `fixed` means no fix listed |
| `affected[].versions` | 51 versions for jinja2 | enumerated affected versions, present for non-SemVer ecosystems (PyPI, RubyGems), absent for npm |
| `affected[].database_specific.source` | `https://github.com/github/advisory-database/blob/main/advisories/github-reviewed/2025/03/...json` | the upstream file to credit and to report data errors to (the FAQ says fix data "at the source") |
| `published`, `modified` | `2025-03-05T20:40:14Z`, `2026-09-10T03:49:48.526758681Z` | `modified` is updated any time the `aliases` field changes (FAQ) |

## Gotchas

- **Count vulnerabilities, not records.** jinja2 2.11.2 returns 10 records for 5 issues; golang.org/x/text 0.3.0 returns 8 for 5 (GHSA plus GO). Blocks 1 and 3 merge alias groups.
- **Use the fix for your package only.** GHSA-p6mc-m468-83gw (CVE-2020-8203) is fixed in lodash 4.17.19 but lodash-es 4.17.20, and lists lodash.set with only `last_affected` 4.3.2. Filter `affected[]` on ecosystem and name.
- **The highest fixed version is a candidate, not an answer.** lodash 4.18.0 fixes all 5 records of 4.17.15 but has its own (CVE-2026-2950, introduced in 4.17.23). Re-query the target, as block 1 does.
- **`GIT` ranges hold commit hashes.** requests 2.19.0's PYSEC-2018-28 and PYSEC-2023-74 list `GIT` fixes `c45d7c49ea75133e52ab22a8e9e13173938e36ff` and `74ea7cf7a6a27a4eeb2ae24e162bcc942a6706d5`; skip `GIT` ranges when you want a version.
- **Empty means "no record", not "clean package".** `jinja22` (a typo) and a real clean version both return HTTP 200 `{}`. Check the package name against the registry yourself; OSV cannot tell the two apart.
- **Always pass the ecosystem.** Without it, `jinja2` 2.11.2 returned 35 records across Debian, Ubuntu, Echo and Red Hat Lightwell as well as PyPI; Ubuntu data is CC-BY-SA 4.0. Ecosystem names are case-sensitive (`PyPI`, `npm`, `Go`, `crates.io`); PyPI package names are not (`Jinja2` works). `v2.11.2` returned the same 10 records as `2.11.2`.
- **Chainguard and Wolfi are off-limits.** The osv.dev home page counted 1,304,837 Chainguard and 332,037 Wolfi records on 2026-11-15, all CC-BY-NC-ND 4.0. Two exploratory calls for `py3-jinja2` in those ecosystems returned `CGA-` records; the blocks refuse those ecosystems before any request.
- **`querybatch` returns IDs only** (`id`, `modified`). Fetch each record with `GET /v1/vulns/<id>`: block 3 makes 1 batch call and 37 GETs for 7 pins.
- **Withdrawn records** are left out of `POST` query answers but still served by `GET /v1/vulns/<id>`, marked with a `withdrawn` field (FAQ). Check that field when you look a record up by ID.
- **CORS** is reflected only when the request sends an `Origin` header (`access-control-allow-origin: https://example.com` in block 4; none without `Origin`). The browser blocks avoid the question by fetching from an api.osv.dev page.
- **Wrong method:** `GET /v1/query` and `HEAD /v1/vulns/<id>` are HTTP 405. Query endpoints are `POST` only.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **Chainguard / Wolfi data** (ecosystems `Chainguard`, `Wolfi`, IDs `CGA-`): CC-BY-NC-ND 4.0. Not used.
- **osv.dev web pages** for data: the API returns the same records as JSON. The website was loaded only to look for terms links.
- **Paging:** `next_page_token` was never returned in these runs (django 1.2 on PyPI gave 93 records in one page). The blocks follow it or stop if it appears; a bad `page_token` is HTTP 400 `invalid cursor`.
- **Not tested:** rate-limit behaviour (never provoked), the `commit` query, the `/v1experimental/` endpoints, the GCS data dumps, and answers above 32 MiB.
