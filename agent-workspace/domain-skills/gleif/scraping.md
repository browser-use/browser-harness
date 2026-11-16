# GLEIF - Find a Company's LEI by Legal Name, Check Its Status and List Its Direct Subsidiaries (LEI API, no key)

Field-tested against api.gleif.org on 2026-11-15 (US Pacific evening; 2026-11-16 04:35-04:40 UTC) using a fresh Browser Use cloud browser (logged out) plus Python `urllib` and `curl` from a Linux machine. 7 browser page loads (API JSON pages and both robots files) and 44 in-page `fetch()` calls, about 45 curl calls and 9 urllib calls to api.gleif.org and www.gleif.org, all serial at 1.1 s or more spacing: every call was HTTP 200 except the deliberate HTTP 400 and 404 probes below. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-15, curl and the cloud browser): https://api.gleif.org/robots.txt (last-modified 13 Nov 2026) is `User-agent: *` with an empty `Disallow:`, so everything is allowed. No named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*` and may fetch the `/api/v1/lei-records` paths used here (block 3 checks all 11 with `urllib.robotparser`). https://www.gleif.org/robots.txt disallows `/*?` and `/*x-external-links` for `*`; this skill never loads www.gleif.org pages with a query string (it only cites the terms pages). Terms: the LEI Data Terms of Use (https://www.gleif.org/en/meta/lei-data-terms-of-use/) say "The Access Service on the website http(s)://www.gleif.org is provided for free" and "The data available through the Access Service are provided under the CC0 licence". The same terms ask users to "refrain from trying to circumvent technical restrictions", call the GLEIF Trademark and Logo "a registered trademark" (contact GLEIF to use it), and forbid "creating, in whatever way, the impression that, data and/or services, except the original LEI and LE-RD downloaded by you through the Access Service, are provided or supported or authorized or granted or otherwise associated by or with GLEIF". The API quick-start (https://documenter.getpostman.com/view/7679680/SVYrrxuU; https://api.gleif.org/docs redirects there) says "There is no charge for the use of GLEIF's LEI data" and "Rate limiting is currently set at 60 requests, per minute, per user, for all users". GLEIF's AI Terms of Use (https://www.gleif.org/en/meta/ai-terms-of-use/) "govern the general use of AI and the AI-powered chatbot provided by" GLEIF; their "No AI/ML Training" clause is about "Chatbot outputs", not the API or LEI data. No AI/ML, scraping, automated-access or non-commercial clause covers the API. Naming: this skill writes "GLEIF" and "Global Legal Entity Identifier Foundation" as plain text and uses no GLEIF logo. This skill is not affiliated with or endorsed by GLEIF.

**Attribution:** CC0 needs none, but quote "GLEIF LEI data", the golden copy `meta.goldenCopy.publishDate` (2026-11-15T16:00:00Z here) and the LEI. Block 1 prints a source line.

## Quick summary

- **No scraping.** `GET https://api.gleif.org/api/v1/lei-records?filter[entity.legalName]=Apple Inc.&filter[entity.legalAddress.country]=US&page[size]=200` finds the LEI; `GET /api/v1/lei-records/<LEI>` is the record, `/<LEI>/direct-children` the subsidiaries, `/<LEI>/ultimate-parent` the top parent. JSON:API (`application/vnd.api+json`), no key.
- **Answer (golden copy 2026-11-15T16:00:00Z; run 2026-11-16 04:36 UTC):** Apple Inc. is **HWUPKR0MPOU8FGXBT394**, entity status **ACTIVE**, LEI registration **ISSUED** (FULLY_CORROBORATED, next renewal 2027-03-08), legal address Glendale, US-CA, registered as 806592 (formerly "Apple Computer, Inc."). It has **8 direct children**: APPLE OPERATIONS INTERNATIONAL LIMITED (IE), BRAEBURN CAPITAL, INC. (US), APPLE ENERGY LLC (US), APPLE CANADA INC. (CA), APPLE COMPUTER BRASIL LTDA. (BR), APPLE OPERATIONS MEXICO SA DE CV (MX), APPLE CHILE COMERCIAL LIMITADA (CL) and APPLE OPERATIONS INDIA PRIVATE LIMITED (IN); all ACTIVE and ISSUED. It is the top of its group: `/ultimate-parent` is HTTP 404 "Related resource not found" and the reporting exception gives reason `NATURAL_PERSONS`. 20 ultimate children in total.
- **`filter[entity.legalName]` matches words, not the whole name.** "Apple Inc." with country US returns 20 records (Apple Ford, Inc., APPLE QUEST, INC., Apple Hospitality REIT, Inc. ...); 24 without the country. Keep only the exact legal name; block 1 requires exactly one. `filter[fulltext]=Apple Inc` is worse: 50 hits, Saybrook Realty LLC and four "AM ... LLC" records first, Apple Inc. last (50th of 50).
- **Children are self-reported Level 2 data.** `direct-children` lists only entities with their own LEI that report this LEI as their direct accounting-consolidation parent (`IS_DIRECTLY_CONSOLIDATED_BY`), not every legal subsidiary. Say "8 direct children reported to GLEIF".
- **Silent failures:** country `USA` (alpha-3) is HTTP 200 with 0 results. Loud ones: a misspelt filter is HTTP 400 "Filter should contain only allowed values.", `page[size]=201` is HTTP 400 "The page.size must be between 1 and 200."
- **Rate limit:** 60 requests per minute per user (quick-start). No rate-limit headers in responses. Blocks pace 1.1 s per call, serial, and wait 60 s once on 429/500/502/503/504.

## What works

### 1. LEI by legal name, status, top parent and direct children (browser)

`on_api_tab()` opens one logged-out api.gleif.org JSON page, so `fetch()` is same-origin. `get()` returns parsed JSON on HTTP 200, returns `None` only for the JSON 404 "Related resource not found" when asked (no parent), waits 60 s once on 429/500/502/503/504 and otherwise raises. `get_all()` follows `links.next` and checks the count against `meta.pagination.total`. The block keeps only exact legal-name matches, requires one, reads the record, checks the top parent, then lists the direct children and cross-checks them against the relationship records.

```python
import json, time, unicodedata, urllib.parse
from datetime import datetime, timezone

NAME = "Apple Inc."   # the registered legal name, as precisely as you know it
COUNTRY = "US"        # ISO 3166-1 alpha-2 of the LEGAL address (not HQ); None to search all countries

SITE = "https://api.gleif.org"
API = SITE + "/api/v1"
PAUSE = 1.1  # the API quick-start: "Rate limiting is currently set at 60 requests, per minute, per user". Stay serial.

def on_api_tab():
    """fetch() runs same-origin from a logged-out api.gleif.org JSON page. Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(API + "/lei-records?page%5Bsize%5D=1")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"goldenCopy"' not in body:
        raise RuntimeError(f"api.gleif.org did not serve JSON (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/vnd.api+json'}})
    .then(async r => { window.__g[id] = {status: r.status, ctype: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, ctype: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def get(url, ok404=False, timeout=60):
    """GET url from inside the tab -> parsed JSON. Waits 60 s once on 429/500/502/503/504 or a network error.
    ok404=True returns None for the JSON 404 'Related resource not found' (no such parent); every other
    non-200 raises (400 = bad filter or page size, with a reason; an unknown LEI is a 404 HTML page)."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(60)
            continue
        if ok404 and r["status"] == 404 and "json" in r["ctype"] and "Related resource not found" in r["text"]:
            return None
        if r["status"] != 200 or "json" not in r["ctype"]:
            raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
        return json.loads(r["text"])

def get_all(path, params=None, size=200):
    """Every record of a list endpoint, following links.next; checks the count against meta.pagination.total
    and that the golden copy did not change between pages."""
    url = API + path + "?" + urllib.parse.urlencode({**(params or {}), "page[size]": size})
    out, total, pub = [], None, None
    while url:
        d = get(url)
        pg = d["meta"].get("pagination", {})
        total = pg.get("total", 0) if total is None else total
        pub = pub or d["meta"]["goldenCopy"]["publishDate"]
        if d["meta"]["goldenCopy"]["publishDate"] != pub:
            raise RuntimeError(f"golden copy changed mid-paging ({pub} -> {d['meta']['goldenCopy']['publishDate']}): re-run")
        out += d["data"]
        url = d.get("links", {}).get("next")
    if len(out) != total:
        raise RuntimeError(f"{path}: got {len(out)} records, meta says {total}: stop")
    return out, pub

def norm(s):
    """Compare names the way a person would: case, accents and spacing ignored, punctuation kept."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return " ".join(s.casefold().split())

def row(r):
    a = r["attributes"]
    e, g = a["entity"], a["registration"]
    return f"{r['id']}  {e['legalName']['name']} ({e['legalAddress']['country']}), entity {e['status']}, LEI {g['status']}"

on_api_tab()
now = datetime.now(timezone.utc)

# 1. Find the LEI. filter[entity.legalName] matches words, not the whole name ("Apple Inc." also returns
#    "Apple Hospitality REIT, Inc."), so keep only exact legal-name matches and require exactly one.
params = {"filter[entity.legalName]": NAME}
if COUNTRY:
    params["filter[entity.legalAddress.country]"] = COUNTRY
hits, pub = get_all("/lei-records", params)
exact = [r for r in hits if norm(r["attributes"]["entity"]["legalName"]["name"]) == norm(NAME)]
print(f"GLEIF golden copy {pub}; legal name {NAME!r}{', legal address ' + COUNTRY if COUNTRY else ''}: "
      f"{len(hits)} word matches, {len(exact)} exact")
if len(exact) != 1:
    raise RuntimeError(f"expected exactly one exact legal-name match, got {[row(r) for r in exact]}: add COUNTRY or check otherNames")
lei = exact[0]["id"]

# 2. Entity and registration status, from the record itself.
rec = get(f"{API}/lei-records/{lei}")
a = rec["data"]["attributes"]
e, g = a["entity"], a["registration"]
if a["lei"] != lei:
    raise RuntimeError(f"record {a['lei']} is not {lei}: stop")
print(f"\n{lei}  {e['legalName']['name']}")
print(f"  entity status {e['status']} (category {e['category']}, legal form {e['legalForm']['id']}, jurisdiction {e['jurisdiction']}, "
      f"registered as {e['registeredAs']} at {e['registeredAt']['id']})")
print(f"  LEI registration {g['status']}, {g['corroborationLevel']}; first registered {g['initialRegistrationDate'][:10]}, "
      f"last update {g['lastUpdateDate'][:10]}, next renewal {g['nextRenewalDate'][:10]}")
print(f"  legal address {', '.join(e['legalAddress']['addressLines'])}, {e['legalAddress']['city']} {e['legalAddress']['region']}; "
      f"HQ {', '.join(e['headquartersAddress']['addressLines'])}, {e['headquartersAddress']['city']}")
if e["otherNames"]:
    print("  other names: " + "; ".join(f"{n['name']} ({n['type']})" for n in e["otherNames"]))
if g["status"] != "ISSUED" or e["status"] != "ACTIVE":
    print(f"  WARNING: not an active, issued LEI (entity {e['status']}, registration {g['status']})")

# 3. Is it the top of its group? The parent calls are 404 "Related resource not found" when no parent is
#    reported; the reporting-exception endpoint then says why.
up = get(f"{API}/lei-records/{lei}/ultimate-parent", ok404=True)
if up is None:
    ex = get(f"{API}/lei-records/{lei}/ultimate-parent-reporting-exception", ok404=True)
    why = ex["data"]["attributes"]["reason"] if ex and ex.get("data") else "no exception filed"
    print(f"  ultimate parent: none reported (404); reporting exception: {why}")
else:
    print(f"  ultimate parent: {row(up['data'])}")

# 4. Direct children (entities that report this LEI as their direct accounting-consolidation parent),
#    cross-checked against the relationship records.
kids, _ = get_all(f"/lei-records/{lei}/direct-children")
rels, _ = get_all(f"/lei-records/{lei}/direct-child-relationships")
rel_by_child = {x["attributes"]["relationship"]["startNode"]["id"]: x["attributes"] for x in rels}
if sorted(rel_by_child) != sorted(k["id"] for k in kids):
    raise RuntimeError(f"direct-children ({len(kids)}) and direct-child-relationships ({len(rels)}) disagree: stop")
if any(x["relationship"]["endNode"]["id"] != lei for x in rel_by_child.values()):
    raise RuntimeError("a relationship record does not point at this LEI: stop")
print(f"\n{len(kids)} direct children:")
for k in sorted(kids, key=lambda k: k["attributes"]["entity"]["legalName"]["name"].casefold()):
    rr = rel_by_child[k["id"]]
    since = next((p["startDate"][:10] for p in rr["relationship"]["periods"] if p["type"] == "RELATIONSHIP_PERIOD"), "?")
    print(f"  {row(k)}; {rr['relationship']['type']} {rr['relationship']['status']} since {since}")

print(f"\nSource: GLEIF LEI data (golden copy {pub}), {API}/lei-records/{lei}, "
      f"accessed {now:%d %B %Y %H:%M} UTC. CC0. Level 2 parent/child data is reported by the entities themselves.")
```

Output (from the run on 2026-11-16, 04:36 UTC):

```text
GLEIF golden copy 2026-11-15T16:00:00Z; legal name 'Apple Inc.', legal address US: 20 word matches, 1 exact

HWUPKR0MPOU8FGXBT394  Apple Inc.
  entity status ACTIVE (category GENERAL, legal form H1UM, jurisdiction US-CA, registered as 806592 at RA000598)
  LEI registration ISSUED, FULLY_CORROBORATED; first registered 2012-06-06, last update 2026-03-03, next renewal 2027-03-08
  legal address C/O C T Corporation System, 330 N. Brand Blvd, Suite 700, Glendale US-CA; HQ One Apple Park Way, Cupertino
  other names: Apple Computer, Inc. (PREVIOUS_LEGAL_NAME)
  ultimate parent: none reported (404); reporting exception: NATURAL_PERSONS

8 direct children:
  5493004SYPRAVRVNK561  APPLE CANADA INC. (CA), entity ACTIVE, LEI ISSUED; IS_DIRECTLY_CONSOLIDATED_BY ACTIVE since 2023-05-08
  5493004QI6E3PJNCEB09  APPLE CHILE COMERCIAL LIMITADA (CL), entity ACTIVE, LEI ISSUED; IS_DIRECTLY_CONSOLIDATED_BY ACTIVE since 2013-09-11
  549300UJWEUFNYXPJ620  APPLE COMPUTER BRASIL LTDA. (BR), entity ACTIVE, LEI ISSUED; IS_DIRECTLY_CONSOLIDATED_BY ACTIVE since 2022-06-08
  549300YX4S1LLSMK2627  APPLE ENERGY LLC (US), entity ACTIVE, LEI ISSUED; IS_DIRECTLY_CONSOLIDATED_BY ACTIVE since 2018-04-10
  2549008YU9EOMHFUA249  APPLE OPERATIONS INDIA PRIVATE LIMITED (IN), entity ACTIVE, LEI ISSUED; IS_DIRECTLY_CONSOLIDATED_BY ACTIVE since 2023-05-17
  549300G81RQKP7XW2N18  APPLE OPERATIONS INTERNATIONAL LIMITED (IE), entity ACTIVE, LEI ISSUED; IS_DIRECTLY_CONSOLIDATED_BY ACTIVE since 2017-12-13
  549300MF6CNUB2URPE58  APPLE OPERATIONS MEXICO SA DE CV (MX), entity ACTIVE, LEI ISSUED; IS_DIRECTLY_CONSOLIDATED_BY ACTIVE since 2013-10-31
  5493006LHHR4CLPX4Q79  BRAEBURN CAPITAL, INC. (US), entity ACTIVE, LEI ISSUED; IS_DIRECTLY_CONSOLIDATED_BY ACTIVE since 2005-10-03

Source: GLEIF LEI data (golden copy 2026-11-15T16:00:00Z), https://api.gleif.org/api/v1/lei-records/HWUPKR0MPOU8FGXBT394, accessed 16 November 2026 04:36 UTC. CC0. Level 2 parent/child data is reported by the entities themselves.
```

### 2. robots.txt, search mistakes, parents and children (browser)

3 page loads and 19 in-page `fetch()` calls in the same tab.

```python
import json, time, urllib.parse

SITE = "https://api.gleif.org"
API = SITE + "/api/v1"
APPLE, AOI = "HWUPKR0MPOU8FGXBT394", "549300G81RQKP7XW2N18"  # Apple Inc., Apple Operations International Limited

START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/vnd.api+json'}})
    .then(async r => { window.__g[id] = {status: r.status, ctype: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, ctype: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def raw(path):
    """One in-page GET -> status, content type, body. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(API + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.3)
    time.sleep(1.1)  # 60 requests per minute per user
    return r

def q(**f):
    return "/lei-records?" + urllib.parse.urlencode({**{f"filter[{k.replace('__', '.')}]": v for k, v in f.items() if k != "size"},
                                                     "page[size]": f.get("size", 3)})

def brief(r):
    out = f"HTTP {r['status']}"
    if "json" not in r["ctype"]:
        return out + f" {r['ctype'].split(';')[0]} ({len(r['text']):,} chars, title {r['text'].split('<title>')[1].split('<')[0] if '<title>' in r['text'] else '-'})"
    d = json.loads(r["text"])
    if "errors" in d:
        return out + " " + "; ".join(e.get("detail") or e.get("title") for e in d["errors"])
    if isinstance(d["data"], list):
        names = [x["attributes"]["entity"]["legalName"]["name"] for x in d["data"][:3]] if d["data"] and d["data"][0]["type"] == "lei-records" else []
        return out + f" total {d['meta'].get('pagination', {}).get('total', len(d['data']))}, first {names}"
    a = d["data"]["attributes"]
    if d["data"]["type"] == "reporting-exceptions":
        return out + f" exception {a['category']} reason {a['reason']}"
    return out + f" {d['data']['id']} {a['entity']['legalName']['name']}"

try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
if not on_site:
    new_tab(API + "/lei-records?page%5Bsize%5D=1")
    wait_for_load()

# robots.txt of both hosts (the API host is the only one used).
for host in ("https://api.gleif.org", "https://www.gleif.org"):
    goto_url(host + "/robots.txt")
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    print(f"{host}/robots.txt HTTP {st}:")
    print("\n".join("  " + l for l in js("document.body.innerText").strip().splitlines() if l.strip()))
goto_url(API + "/lei-records?page%5Bsize%5D=1")  # back to an API JSON page for same-origin fetch()
wait_for_load()
print()

for label, path in (
    ("legalName 'Apple Inc.', country US     ", q(entity__legalName="Apple Inc.", entity__legalAddress__country="US")),
    ("legalName 'Apple Inc.', any country    ", q(entity__legalName="Apple Inc.")),
    ("legalName 'apple inc' (case, no dot)   ", q(entity__legalName="apple inc")),
    ("fulltext 'Apple Inc', country US       ", q(fulltext="Apple Inc", entity__legalAddress__country="US")),
    ("legalName + registration.status ISSUED ", q(entity__legalName="Apple Inc.", registration__status="ISSUED")),
    ("country 'USA' (alpha-3)                ", q(entity__legalName="Apple Inc.", entity__legalAddress__country="USA")),
    ("typo filter[entity.legalNam]           ", q(entity__legalNam="Apple Inc.")),
    ("page[size]=201                         ", q(entity__legalName="Apple Inc.", size=201)),
    ("filter[lei]=two LEIs                   ", q(lei=f"{APPLE},{AOI}")),
    ("filter[ownedBy]=Apple                  ", q(ownedBy=APPLE)),
    ("Apple /direct-children                 ", f"/lei-records/{APPLE}/direct-children"),
    ("Apple /ultimate-children               ", f"/lei-records/{APPLE}/ultimate-children"),
    ("Apple /ultimate-parent                 ", f"/lei-records/{APPLE}/ultimate-parent"),
    ("Apple /direct-parent                   ", f"/lei-records/{APPLE}/direct-parent"),
    ("Apple /direct-parent-reporting-excep.  ", f"/lei-records/{APPLE}/direct-parent-reporting-exception"),
    ("AOI (IE) /direct-parent                ", f"/lei-records/{AOI}/direct-parent"),
    ("AOI (IE) /ultimate-parent              ", f"/lei-records/{AOI}/ultimate-parent"),
    ("lower-case LEI                         ", f"/lei-records/{APPLE.lower()}"),
    ("unknown LEI (last char changed)        ", f"/lei-records/{APPLE[:-1]}X"),
):
    print(f"{label} {brief(raw(path))}")
```

Output (from the run on 2026-11-16, 04:37 UTC):

```text
https://api.gleif.org/robots.txt HTTP 200:
  User-agent: *
  Disallow:
https://www.gleif.org/robots.txt HTTP 200:
  User-agent: *
  Disallow: /*?
  Disallow: /*x-external-links
  Sitemap: http://gleif.org/meta/sitemap/xml

legalName 'Apple Inc.', country US      HTTP 200 total 20, first ['Apple Inc.', 'Apple Ford, Inc.', 'APPLE QUEST, INC.']
legalName 'Apple Inc.', any country     HTTP 200 total 24, first ['Apple Inc.', 'Apple Ford, Inc.', 'APPLE MANAGEMENT INC.']
legalName 'apple inc' (case, no dot)    HTTP 200 total 24, first ['Apple Inc.', 'Apple Ford, Inc.', 'APPLE MANAGEMENT INC.']
fulltext 'Apple Inc', country US        HTTP 200 total 50, first ['Saybrook Realty LLC', 'AM NYCF, LLC', 'AM SUBF, LLC']
legalName + registration.status ISSUED  HTTP 200 total 6, first ['Apple Inc.', 'APPLE MANAGEMENT INC.', 'APPLE CANADA INC.']
country 'USA' (alpha-3)                 HTTP 200 total 0, first []
typo filter[entity.legalNam]            HTTP 400 Filter should contain only allowed values.
page[size]=201                          HTTP 400 The page.size must be between 1 and 200.
filter[lei]=two LEIs                    HTTP 200 total 2, first ['APPLE OPERATIONS INTERNATIONAL LIMITED', 'Apple Inc.']
filter[ownedBy]=Apple                   HTTP 200 total 20, first ['APPLE TEKNOLOJİ VE SATIŞ LİMİTED ŞİRKETİ', 'APPLE OPERATIONS INDIA PRIVATE LIMITED', 'APPLE CHILE COMERCIAL LIMITADA']
Apple /direct-children                  HTTP 200 total 8, first ['APPLE OPERATIONS INDIA PRIVATE LIMITED', 'APPLE CHILE COMERCIAL LIMITADA', 'APPLE ENERGY LLC']
Apple /ultimate-children                HTTP 200 total 20, first ['Apple Technology Services India Private Limited', 'APPLE OPERATIONS INDIA PRIVATE LIMITED', '蘋果電腦貿易（上海）有限公司']
Apple /ultimate-parent                  HTTP 404 Related resource not found
Apple /direct-parent                    HTTP 404 Related resource not found
Apple /direct-parent-reporting-excep.   HTTP 200 exception DIRECT_ACCOUNTING_CONSOLIDATION_PARENT reason NATURAL_PERSONS
AOI (IE) /direct-parent                 HTTP 200 HWUPKR0MPOU8FGXBT394 Apple Inc.
AOI (IE) /ultimate-parent               HTTP 200 HWUPKR0MPOU8FGXBT394 Apple Inc.
lower-case LEI                          HTTP 200 HWUPKR0MPOU8FGXBT394 Apple Inc.
unknown LEI (last char changed)         HTTP 404 Resource lei-records with id HWUPKR0MPOU8FGXBT39X does not exist.
```

### 3. Same answer with Python urllib, robots check for every agent, links.next paging (no browser)

Python's default `urllib` User-Agent also got HTTP 200; this block sends a descriptive one.

```python
import json, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser

API = "https://api.gleif.org/api/v1"
UA = "gleif-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
NAME, COUNTRY = "Apple Inc.", "US"

def get(path, params=None, ok404=False):
    """-> parsed JSON (None for a 404 'Related resource not found' when ok404). One 60 s wait on 429/500/502/503/504
    or a network error; exits on anything else. Accept: application/vnd.api+json makes 404s JSON instead of HTML."""
    url = path if path.startswith("http") else API + path + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(2):
        time.sleep(1.1)  # 60 requests per minute per user
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.api+json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if ok404 and e.code == 404 and "Related resource not found" in body:
                return None
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"HTTP {e.code} {url}: {' '.join(body.split())[:200]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url}: {e}")

def pages(path, params, size):
    """Yield (records, meta) page by page via links.next; checks the total at the end."""
    url, seen = API + path + "?" + urllib.parse.urlencode({**params, "page[size]": size}), 0
    while url:
        d = get(url)
        seen += len(d["data"])
        yield d["data"], d["meta"]
        url = d.get("links", {}).get("next")
    if seen != d["meta"]["pagination"]["total"]:
        sys.exit(f"paged {seen} records, meta says {d['meta']['pagination']['total']}")

# robots.txt: every agent group must allow the paths used here.
rp = urllib.robotparser.RobotFileParser()
with urllib.request.urlopen(urllib.request.Request("https://api.gleif.org/robots.txt", headers={"User-Agent": UA}), timeout=30) as r:
    rp.parse(r.read().decode().splitlines())
paths = ["/api/v1/lei-records?filter%5Bentity.legalName%5D=x", "/api/v1/lei-records/HWUPKR0MPOU8FGXBT394",
         "/api/v1/lei-records/HWUPKR0MPOU8FGXBT394/direct-children", "/api/v1/lei-records/HWUPKR0MPOU8FGXBT394/ultimate-parent"]
for p in paths:
    ok = {a: rp.can_fetch(a, "https://api.gleif.org" + p) for a in AGENTS}
    print(f"robots {p[:58]:<58} {'allowed' if all(ok.values()) else ok} for all {len(AGENTS)} agents")
if not all(rp.can_fetch(a, "https://api.gleif.org" + p) for a in AGENTS for p in paths):
    sys.exit("robots.txt now disallows a path this skill uses: stop")

# The answer: exact legal-name match, status, top of group, direct children.
d = get("/lei-records", {"filter[entity.legalName]": NAME, "filter[entity.legalAddress.country]": COUNTRY, "page[size]": 200})
exact = [r for r in d["data"] if " ".join(r["attributes"]["entity"]["legalName"]["name"].casefold().split()) == NAME.casefold()]
if d["meta"]["pagination"]["total"] > 200 or len(exact) != 1:
    sys.exit(f"{d['meta']['pagination']['total']} matches, {len(exact)} exact: page through or narrow the search")
lei = exact[0]["id"]
a = exact[0]["attributes"]
top = get(f"/lei-records/{lei}/ultimate-parent", ok404=True)
kids = get(f"/lei-records/{lei}/direct-children", {"page[size]": 200})
if kids["meta"]["pagination"]["total"] != len(kids["data"]):
    sys.exit("more than 200 direct children: page through them")
print(f"\ngolden copy {d['meta']['goldenCopy']['publishDate']}: {NAME} -> {lei}, entity {a['entity']['status']}, "
      f"LEI {a['registration']['status']}, next renewal {a['registration']['nextRenewalDate'][:10]}, "
      f"ultimate parent {'none (top of group)' if top is None else top['data']['id']}")
print(f"{len(kids['data'])} direct children: " + "; ".join(
    f"{k['attributes']['entity']['legalName']['name']} ({k['attributes']['entity']['legalAddress']['country']})" for k in kids["data"]))

# Paging: all 20 reported ultimate children, 5 per page via links.next, counted by legal-address country.
by_country, n = {}, 0
for recs, meta in pages(f"/lei-records/{lei}/ultimate-children", {}, 5):
    n += 1
    for r in recs:
        c = r["attributes"]["entity"]["legalAddress"]["country"]
        by_country[c] = by_country.get(c, 0) + 1
print(f"\nultimate children: {sum(by_country.values())} in {n} pages of 5 (meta total {meta['pagination']['total']}); "
      f"by legal-address country: {dict(sorted(by_country.items(), key=lambda x: (-x[1], x[0])))}")
```

Output (from the run on 2026-11-16, 04:39 UTC):

```text
robots /api/v1/lei-records?filter%5Bentity.legalName%5D=x         allowed for all 11 agents
robots /api/v1/lei-records/HWUPKR0MPOU8FGXBT394                   allowed for all 11 agents
robots /api/v1/lei-records/HWUPKR0MPOU8FGXBT394/direct-children   allowed for all 11 agents
robots /api/v1/lei-records/HWUPKR0MPOU8FGXBT394/ultimate-parent   allowed for all 11 agents

golden copy 2026-11-15T16:00:00Z: Apple Inc. -> HWUPKR0MPOU8FGXBT394, entity ACTIVE, LEI ISSUED, next renewal 2027-03-08, ultimate parent none (top of group)
8 direct children: APPLE OPERATIONS INDIA PRIVATE LIMITED (IN); APPLE CHILE COMERCIAL LIMITADA (CL); APPLE ENERGY LLC (US); BRAEBURN CAPITAL, INC. (US); APPLE OPERATIONS INTERNATIONAL LIMITED (IE); APPLE COMPUTER BRASIL LTDA. (BR); APPLE OPERATIONS MEXICO SA DE CV (MX); APPLE CANADA INC. (CA)

ultimate children: 20 in 4 pages of 5 (meta total 20); by legal-address country: {'IE': 3, 'IN': 3, 'US': 2, 'AU': 1, 'BR': 1, 'CA': 1, 'CL': 1, 'CN': 1, 'GB': 1, 'JP': 1, 'KR': 1, 'MX': 1, 'NZ': 1, 'SG': 1, 'TR': 1}
```

### 4. curl

```bash
A=https://api.gleif.org/api/v1
H='Accept: application/vnd.api+json'
# the answer: LEI by exact legal name (the filter matches words, so keep the exact name), then direct children
curl -sS --fail -G -H "$H" "$A/lei-records" --data-urlencode 'filter[entity.legalName]=Apple Inc.' \
  --data-urlencode 'filter[entity.legalAddress.country]=US' -d 'page[size]=200' \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); x=[r for r in d["data"] if r["attributes"]["entity"]["legalName"]["name"]=="Apple Inc."]; a=x[0]["attributes"]; print(d["meta"]["pagination"]["total"], "matches,", len(x), "exact:", x[0]["id"], a["entity"]["status"], a["registration"]["status"])'
sleep 1.1
curl -sS --fail -H "$H" "$A/lei-records/HWUPKR0MPOU8FGXBT394/direct-children?page%5Bsize%5D=200" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["meta"]["pagination"]["total"], "direct children"); [print(" ", r["id"], r["attributes"]["entity"]["legalName"]["name"]) for r in d["data"]]'
sleep 1.1
# top of the group: 404 with a JSON reason
curl -sS -H "$H" -w ' <- HTTP %{http_code}\n' "$A/lei-records/HWUPKR0MPOU8FGXBT394/ultimate-parent"
sleep 1.1
# without the Accept header an unknown LEI is an HTML 404 page; with it, JSON
curl -sS -o /dev/null -w 'unknown LEI, no Accept: HTTP %{http_code} %{content_type}\n' "$A/lei-records/HWUPKR0MPOU8FGXBT39X"
sleep 1.1
curl -sS -H "$H" -w ' <- HTTP %{http_code}\n' "$A/lei-records/HWUPKR0MPOU8FGXBT39X"
sleep 1.1
# headers: no rate-limit headers; CORS open when an Origin is sent
curl -sS -D - -o /dev/null -H "$H" -H 'Origin: https://example.com' "$A/lei-records/HWUPKR0MPOU8FGXBT394" \
  | tr -d '\r' | grep -iE '^(content-type|cache-control|access-control-allow-origin|x-ratelimit|retry-after|x-robots-tag):'
```

Output (from the run on 2026-11-16, 04:39 UTC):

```text
20 matches, 1 exact: HWUPKR0MPOU8FGXBT394 ACTIVE ISSUED
8 direct children
  2549008YU9EOMHFUA249 APPLE OPERATIONS INDIA PRIVATE LIMITED
  5493004QI6E3PJNCEB09 APPLE CHILE COMERCIAL LIMITADA
  549300YX4S1LLSMK2627 APPLE ENERGY LLC
  5493006LHHR4CLPX4Q79 BRAEBURN CAPITAL, INC.
  549300G81RQKP7XW2N18 APPLE OPERATIONS INTERNATIONAL LIMITED
  549300UJWEUFNYXPJ620 APPLE COMPUTER BRASIL LTDA.
  549300MF6CNUB2URPE58 APPLE OPERATIONS MEXICO SA DE CV
  5493004SYPRAVRVNK561 APPLE CANADA INC.
{"errors":[{"status":"404","title":"Resource not found","detail":"Related resource not found"}]} <- HTTP 404
unknown LEI, no Accept: HTTP 404 text/html; charset=UTF-8
{"errors":[{"status":"404","title":"Not Found","detail":"Resource lei-records with id HWUPKR0MPOU8FGXBT39X does not exist."}]} <- HTTP 404
content-type: application/vnd.api+json
cache-control: private, must-revalidate
access-control-allow-origin: *
x-robots-tag: all
```

## Fields (lei-records JSON)

| Field | JSON path (under `data.attributes` unless noted) | Notes |
|---|---|---|
| LEI | `lei` (also `data.id`) | 20 characters. Lookup is case-insensitive (lower-case LEI is HTTP 200). `filter[lei]=A,B` fetches several at once |
| legal name | `entity.legalName.name` | the search filter `filter[entity.legalName]` matches words (operators MATCH, NOT_MATCH per `/api/v1/fields`); compare the exact name yourself |
| previous names | `entity.otherNames[]` (`type` `PREVIOUS_LEGAL_NAME`, ...) | Apple: "Apple Computer, Inc." |
| entity status | `entity.status` | `ACTIVE`, `INACTIVE` or `NULL` (`/api/v1/fields`). Whether the legal entity still exists |
| registration status | `registration.status` | `ISSUED`, `LAPSED`, `ANNULLED`, `PENDING_TRANSFER`, `PENDING_ARCHIVAL`, `DUPLICATE`, `RETIRED`, `MERGED`. Whether the LEI is kept up to date; filter with `filter[registration.status]=ISSUED` |
| corroboration | `registration.corroborationLevel` | `ENTITY_SUPPLIED_ONLY`, `PARTIALLY_CORROBORATED`, `FULLY_CORROBORATED` |
| dates | `registration.initialRegistrationDate`, `.lastUpdateDate`, `.nextRenewalDate`, `entity.creationDate` | ISO 8601 UTC |
| addresses | `entity.legalAddress`, `entity.headquartersAddress` | `country` is ISO alpha-2 (`US`); `filter[entity.legalAddress.country]` uses the legal address, not HQ |
| register id | `entity.registeredAt.id`, `entity.registeredAs`, `entity.jurisdiction` | registration authority code (RA000598), company number (806592), US-CA |
| codes | `bic[]`, `entity.legalForm.id`, `entity.category` | Apple: BIC APLEUS66XXX, legal form H1UM, category GENERAL |
| relationships | `data.relationships.<name>.links` | `direct-children`, `ultimate-children`, `direct-parent`, `ultimate-parent`, `isins`, `managing-lou`, `lei-issuer`, `field-modifications`; when no parent is reported the parent link is a `reporting-exception` URL instead |
| relationship record | `/direct-child-relationships` -> `relationship.startNode.id` (child), `.endNode.id` (parent), `.type`, `.status`, `.periods[]` | `IS_DIRECTLY_CONSOLIDATED_BY`, `ACTIVE`; relationship registration `PUBLISHED`; all 8 of Apple's are `ENTITY_SUPPLIED_ONLY` |
| paging | `meta.pagination.total`, `.lastPage`; `links.next` | default 15 per page, `page[size]` 1 to 200, `page[number]` |
| data version | `meta.goldenCopy.publishDate` | on every response |

## Gotchas

- **Exact name, then exactly one.** The legal-name filter is a word match and is case-insensitive (`apple inc` and `Apple Inc.` both gave 24). Compare the normalised exact name and add the legal-address country when several countries share it. If the exact name gives 0, check `entity.otherNames` (a renamed company's old name is there) or the fuzzy endpoint `/api/v1/fuzzycompletions?field=entity.legalName&q=...`, whose quick-start disclaimer says it "does not guarantee that the LEI belongs to the legal entity you are searching for".
- **Do not use `filter[fulltext]` for names.** It searches every field including addresses; `Apple Inc` + US gave Saybrook Realty LLC first and Apple Inc. 50th of 50.
- **Two statuses.** `entity.status` (does the company exist) and `registration.status` (is the LEI renewed). 17 of the 20 US word matches for "Apple Inc." are ACTIVE entities with LAPSED LEIs. Report both.
- **404 means two different things.** `/<LEI>/ultimate-parent` and `/<LEI>/direct-parent` are HTTP 404 `{"errors":[{"detail":"Related resource not found"}]}` when no parent is reported (Apple). An unknown LEI is also HTTP 404, "Resource lei-records with id ... does not exist." Block 1 treats only the first as "no parent". The `...-parent-reporting-exception` endpoint gives the filed reason (Apple: `NATURAL_PERSONS`).
- **Send `Accept: application/vnd.api+json`.** Without it, curl got an HTML "Not Found" page (`text/html`) for an unknown LEI; with it, the JSON error above.
- **Direct vs ultimate.** `direct-children` is 8 for Apple; `ultimate-children` and `filter[ownedBy]=<LEI>` are both 20 (they add indirect children such as APPLE (UK) LIMITED and Apple Japan合同会社). Use `direct-children` for "direct subsidiaries".
- **Self-reported, LEI holders only.** Level 2 data describes relationships "where these have been reported by the Legal Entities themselves" (quick-start). A subsidiary without an LEI, or one that did not report its parent, is missing. The GLEIF terms say "WE CANNOT AND DO NOT REPRESENT OR WARRANT THAT SUCH INFORMATION IS ACCURATE, CORRECT, UP-TO-DATE".
- **Golden copy timing.** GLEIF's golden copy page (https://www.gleif.org/en/lei-data/gleif-golden-copy) says it "makes available three sets of updated Golden Copy Files daily (02:00 UTC, 10:00 UTC, 18:00 UTC)". At 04:36 UTC on 16 November the API still reported `publishDate` 2026-11-15T16:00:00Z. Quote `publishDate`, not the clock. Block 1 stops if it changes mid-paging.
- **Default page size is 15.** Lists longer than that page; always pass `page[size]` (max 200) and follow `links.next`.
- **CORS:** `access-control-allow-origin: *` is sent only when the request has an `Origin` header; the browser blocks run same-origin anyway.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **www.gleif.org URLs with a query string**: robots.txt disallows `/*?`. Not used; the LEI search website is not needed when the API answers.
- **`page[size]` above 200**: HTTP 400.
- **Alpha-3 country codes** (`USA`): silent zero results.
- **Not tested:** rate-limit behaviour (never provoked), the golden copy file downloads, `fuzzycompletions`, ISIN and BIC lookups, and the vLEI services.
