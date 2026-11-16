# NPPES NPI Registry (CMS) - Verify a US Clinician or Hospital by NPI: Name, Primary Taxonomy, Practice Address and State Licence Number (Read API v2.1, no key)

Field-tested against npiregistry.cms.hhs.gov on 2026-11-15 (US Pacific; the logged run was 04:49-04:58 UTC on 2026-11-16) using a fresh Browser Use cloud browser (logged out) plus Python `urllib` and `curl` from a Linux machine. 7 browser page loads (API JSON pages and robots.txt) and 42 in-page `fetch()` calls (block 1 was run 3 times, once with an individual's NPI to test the Type 1 path; block 2 twice), 49 curl calls and 3 urllib calls to npiregistry.cms.hhs.gov (plus 4 curl calls to www.cms.gov for its robots.txt and the check-digit PDF), all serial at 1.5 s or more spacing: every call to npiregistry.cms.hhs.gov was HTTP 200, including the deliberate mistakes, which this API answers with HTTP 200 and an `Errors` list. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-15, curl, the cloud browser and `urllib.robotparser`): https://npiregistry.cms.hhs.gov/robots.txt is not a robots file. curl gets HTTP 200 `text/html`, the 406-byte shell of the site's web app (`<app-root></app-root>`), and the cloud browser lands on https://npiregistry.cms.hhs.gov/search. There are 0 directives and 0 named groups, so nothing restricts `*` or GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot or Bytespider; Python's parser allows all 11 agents for `/api/` (block 3 checks it and stops if directives ever appear). https://www.cms.gov/robots.txt (cited pages only) has one group, `User-agent: *`, that disallows `/*?`, `/node/`, `/media/` and admin paths, not the two CMS pages cited here. Terms (checked 2026-11-15 in a Browser Use cloud browser): the API page https://npiregistry.cms.hhs.gov/api-page says "Application Programming Interface (API) | Read-Only", "API Versions 1.0 and 2.0 are NOW retired" and "An API query will return a maximum of 200 results per request. The Skip field in the API will let you skip up to 1000 records." The search page https://npiregistry.cms.hhs.gov/search says "Effective 6/25/2024: To ensure the best experience, NPPES has limited the amount of NPI Registry queries that can be completed per hour" (no number is given) and "Bulk NPI Registry queries must use the DDS file." It also calls the Registry "a free directory of all active National Provider Identifier (NPI) records" and says "CMS provides this service based on federal law (45 CFR Part 162)". CMS's NPI Data Dissemination page (https://www.cms.gov/medicare/regulations-guidance/administrative-simplification/data-dissemination): "In September 2007, CMS began disclosing NPPES health care provider data that are disclosable under the Freedom of Information Act (FOIA) to the public", the Registry is "a query-only database which is updated daily" and "There is no charge to view the data." None of the three pages has an AI/ML, scraping, automated-access or non-commercial clause. Naming: this skill writes "NPPES NPI Registry (CMS)" as plain text, uses no CMS or HHS logo, and is not affiliated with or endorsed by CMS or HHS.

**An NPI is not a licence check.** Both the API page and the search page say: "Please Note: Issuance of an NPI does not ensure or validate that the Health Care Provider is Licensed or Credentialed." The `license` field is what the provider reported: the dissemination page says the data are "as reported to NPPES by you, or by someone acting on your behalf, or by an organization provider's Authorized Official." Block 1 prints the CMS notice with a source line. Quote it whenever you report a licence number.

**Personal data, one-off use.** Type 1 (NPI-1) records are individual clinicians, with name, credential, practice and mailing address. CMS publishes them because they are "FOIA-disclosable and are required to be disclosed under the FOIA" and "There is no way to 'opt out' or 'suppress' the NPPES record data for health care providers with active NPIs." Use this skill to check a specific provider for a specific reason; do not use it to build lists of people. For bulk data, CMS points to the monthly NPPES Downloadable File (the "DDS file") linked from the dissemination page. The examples here print no individual's name.

## Quick summary

- **No scraping.** `GET https://npiregistry.cms.hhs.gov/api/?version=2.1&number=1134262819` returns the record as JSON. `&organization_name=massachusetts general hospital&state=MA&enumeration_type=NPI-2&limit=200` lists an organization's NPIs. No key. `version=2.1` is required: without it, or with 1.0 or 2.0, the answer is HTTP 200 `{"Errors":[{"description":"Unsupported Version",...}]}`.
- **Answer (run 2026-11-16, 04:54 UTC):** NPI **1134262819** is **MASSACHUSETTS GENERAL HOSPITAL**, organization (Type 2), status A (active), primary taxonomy **282N00000X General Acute Care Hospital**, **state licence 99562 (MA)**, practice address **55 FRUIT ST, YAWKEY CENTER-8TH FLOOR, BOSTON, MA 02114-2621**, enumerated 2007-02-14, last updated 2020-08-22. The legal name has **35 organizational NPIs in MA** (34 with that exact legal name plus THE GENERAL HOSPITAL CORPORATION, which lists it as an other name); **18** of them have primary taxonomy General Acute Care Hospital, 13 with a licence number listed.
- **Mistakes are HTTP 200.** A missing version, `state` alone, `enumeration_type` alone and a 9-digit number each return an `Errors` list; check for it on every answer. A well-formed but unknown number, including a typo with a wrong check digit (1134262818), is `{"result_count":0,"results":[]}`. Blocks 1 and 3 test the NPI check digit (Luhn, CMS's published method) before calling.
- **`result_count` is the size of this answer, not a total.** 200 means "200 or more". `limit` above 200 is silently cut to 200, `limit=0` gives the default 10. Result order changed between two identical `skip=1000` requests, so paging with `skip` can repeat or miss records. Treat a 200-record answer as partial; for one provider query by NPI number, and for complete lists use the DDS file ("Bulk NPI Registry queries must use the DDS file").
- **Rate limit:** an hourly limit since 6/25/2024, value not published; bulk use "must use the DDS file". All blocks pace 2 s per call, serial, and wait 60 s once on 429/5xx.

## What works

### 1. Check one NPI, then list the organization's NPIs (browser)

`on_npi_tab()` opens one logged-out npiregistry.cms.hhs.gov API JSON page, so `fetch()` is same-origin (the API sends no `access-control-allow-origin` header, so a fetch from another site's page would be blocked). `get()` returns parsed JSON on HTTP 200, raises on an `Errors` answer, waits 60 s once on 429/500/502/503/504 and otherwise raises. `check_digit_ok()` implements the check digit from CMS's "Requirements for National Provider Identifier (NPI) and NPI Check Digit" (https://www.cms.gov/Regulations-and-Guidance/Administrative-Simplification/NationalProvIdentStand/Downloads/NPIcheckdigit.pdf): "the Luhn formula for computing the modulus 10 'double-add-double' check digit", calculated "as if the prefix [80840] is present", and tests it on the document's worked example (1234567893). The practice address is picked by `address_purpose`, not by position. 2 `fetch()` calls. With an individual's NPI the same code prints first, middle and last name plus credential (run with one from block 2's cardiology search; output not reproduced here).

```python
import collections, json, re, time, urllib.parse
from datetime import datetime, timezone

NUMBER = "1134262819"                           # the NPI to verify (10 digits); an NPI-1 (clinician) number works too
ORG, STATE = "massachusetts general hospital", "MA"  # list every organizational NPI under this name in this state

SITE = "https://npiregistry.cms.hhs.gov"
API = SITE + "/api/?version=2.1&"  # 1.0, 2.0 and a URL without version= answer "Unsupported Version"
PAUSE = 2.0  # NPPES limits queries per hour (value not published) and says bulk must use the DDS file: one-off lookups only

def on_npi_tab():
    """fetch() runs same-origin from a logged-out npiregistry.cms.hhs.gov JSON page (the API sends no CORS header)."""
    try:
        if js("location.origin") == SITE and js("document.contentType") == "application/json":
            return
    except Exception:
        pass
    new_tab(API + "number=" + NUMBER)
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"result_count"' not in body:
        raise RuntimeError(f"npiregistry.cms.hhs.gov did not serve API JSON (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/json'}})
    .then(async r => { window.__u[id] = {status: r.status, type: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def get(**params):
    """GET the API from inside the tab -> parsed JSON. Waits 60 s once on 429/500/502/503/504 or a network error.
    Bad queries are HTTP 200 with an "Errors" list instead of results, so that raises too."""
    url = API + urllib.parse.urlencode(params)
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer after 60s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(60)
            continue
        if r["status"] != 200 or "json" not in r["type"]:
            raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")
        d = json.loads(r["text"])
        if "Errors" in d:
            raise RuntimeError(f"{url}: API error {[(e['field'], e['description']) for e in d['Errors']]}; fix the query")
        return d

def check_digit_ok(npi):
    """CMS 'Requirements for NPI and NPI Check Digit' (2004): 9 digits + a Luhn check digit computed as if the
    card-issuer prefix 80840 were present."""
    if not re.fullmatch(r"\d{10}", npi):
        return False
    total = 0
    for i, ch in enumerate(reversed("80840" + npi[:9])):
        d = int(ch) * (2 if i % 2 == 0 else 1)
        total += d - 9 if d > 9 else d
    return (10 - total % 10) % 10 == int(npi[9])

def name_of(r):
    b = r["basic"]
    if r["enumeration_type"] == "NPI-2":
        return b["organization_name"]
    return " ".join(x for x in (b.get("first_name"), b.get("middle_name"), b.get("last_name")) if x) + \
        (f", {b['credential']}" if b.get("credential") else "")

def primary_taxonomy(r):
    p = [t for t in r["taxonomies"] if t.get("primary")]
    if len(p) != 1:
        raise RuntimeError(f"NPI {r['number']}: {len(p)} primary taxonomies: stop")
    return p[0]

def address(r, purpose):
    """addresses holds one LOCATION (primary practice) and one MAILING entry. The API page says the practice address
    comes first; for 1134262819 MAILING came first, so select by address_purpose, never by position."""
    a = [x for x in r["addresses"] if x["address_purpose"] == purpose]
    if len(a) != 1:
        raise RuntimeError(f"NPI {r['number']}: {len(a)} {purpose} addresses: stop")
    a = a[0]
    z = a.get("postal_code", "")
    z = f"{z[:5]}-{z[5:]}" if len(z) == 9 else z
    return ", ".join(x for x in (a["address_1"], a.get("address_2"), a["city"], f"{a['state']} {z}") if x)

if not check_digit_ok("1234567893"):  # the worked example in the CMS document
    raise RuntimeError("check digit code is wrong")
on_npi_tab()
now = datetime.now(timezone.utc)

# 1. Check one NPI number: local check digit first (a typo is otherwise just "0 results"), then the record.
if not check_digit_ok(NUMBER):
    raise RuntimeError(f"{NUMBER} is not a valid NPI (10 digits with a Luhn check digit): check the number")
d = get(number=NUMBER)
if d["result_count"] != 1 or d["results"][0]["number"] != NUMBER:
    raise RuntimeError(f"NPI {NUMBER}: {d['result_count']} records; the Registry lists only active NPIs: stop")
r = d["results"][0]
b, t = r["basic"], primary_taxonomy(r)
kind = {"NPI-1": "individual (Type 1)", "NPI-2": "organization (Type 2)"}[r["enumeration_type"]]
print(f"NPI {NUMBER} (check digit ok): {name_of(r)}, {kind}, status {b['status']} (A = active)")
print(f"  primary taxonomy: {t['code']} {t['desc']}")
print(f"  state licence: {t['license'] + ' (' + t['state'] + ')' if t.get('license') else 'not reported'}")
print(f"  practice address: {address(r, 'LOCATION')}")
print(f"  mailing address:  {address(r, 'MAILING')}")
print(f"  enumerated {b['enumeration_date']}, record last updated {b['last_updated']}; "
      f"{len(r['taxonomies'])} taxonomy, {len(r['practiceLocations'])} other practice locations, {len(r['other_names'])} other names")

# 2. Every organizational NPI under the name in the state (one request; 200 is the per-request maximum).
d = get(organization_name=ORG, state=STATE, enumeration_type="NPI-2", limit=200)
rows = d["results"]
if d["result_count"] != len(rows) or len(rows) == 200:
    raise RuntimeError(f"{len(rows)} records: 200 is the per-request cap, so this list is partial; "
                       "complete lists come from the NPPES DDS file, not more API queries")
if len({x["number"] for x in rows}) != len(rows):
    raise RuntimeError("duplicate NPIs in one answer: stop")
exact = [x for x in rows if x["basic"]["organization_name"].upper() == ORG.upper()]
by_tax = collections.Counter(primary_taxonomy(x)["desc"] for x in exact)
print(f"\norganization_name={ORG!r} state={STATE} NPI-2: {len(rows)} records, {len(exact)} with that exact legal name "
      f"(the rest matched an other name: {sorted({x['basic']['organization_name'] for x in rows} - {ORG.upper()})})")
print("  primary taxonomy of the exact-name NPIs:", ", ".join(f"{k} {v}" for k, v in by_tax.most_common()))
hosp = sorted((x for x in exact if primary_taxonomy(x)["code"] == "282N00000X"), key=lambda x: x["number"])
print(f"  {len(hosp)} with primary taxonomy 282N00000X General Acute Care Hospital (NPI, licence, practice city):")
for x in hosp:
    tx = primary_taxonomy(x)
    city = [a["city"] for a in x["addresses"] if a["address_purpose"] == "LOCATION"][0]
    print(f"    {x['number']}  {(tx['license'] + ' ' + tx['state']) if tx.get('license') else '(no licence listed)':<20} {city}")
if name_of(r).upper() == ORG.upper() and NUMBER not in {x["number"] for x in exact}:
    raise RuntimeError(f"{NUMBER} is named {ORG!r} but missing from the name search: stop")

print(f"\nSource: NPPES NPI Registry (CMS), API version 2.1, {SITE}/api/?version=2.1&number={NUMBER}, "
      f"accessed {now:%d %B %Y %H:%M} UTC. Data as reported to NPPES by the provider.")
print("CMS: \"Issuance of an NPI does not ensure or validate that the Health Care Provider is Licensed or Credentialed.\"")
```

Output (from the run on 2026-11-16, 04:54 UTC):

```text
NPI 1134262819 (check digit ok): MASSACHUSETTS GENERAL HOSPITAL, organization (Type 2), status A (A = active)
  primary taxonomy: 282N00000X General Acute Care Hospital
  state licence: 99562 (MA)
  practice address: 55 FRUIT ST, YAWKEY CENTER-8TH FLOOR, BOSTON, MA 02114-2621
  mailing address:  55 FRUIT ST, YAWKEY CENTER-8TH FLOOR, BOSTON, MA 02114-2621
  enumerated 2007-02-14, record last updated 2020-08-22; 1 taxonomy, 0 other practice locations, 0 other names

organization_name='massachusetts general hospital' state=MA NPI-2: 35 records, 34 with that exact legal name (the rest matched an other name: ['THE GENERAL HOSPITAL CORPORATION'])
  primary taxonomy of the exact-name NPIs: General Acute Care Hospital 18, Clinic/Center, Medical Specialty 2, Nurse Practitioner, Adult Health 2, General Acute Care Hospital, Critical Access 2, General Acute Care Hospital, Children 2, Psychiatry & Neurology, Neurology 1, Long Term Care Hospital 1, Rehabilitation Unit 1, Social Worker, Clinical 1, Clinic/Center, Radiology, Mammography 1, Anesthesiology 1, Registered Nurse, Reproductive Endocrinology/Infertility 1, Psychiatric Hospital 1
  18 with primary taxonomy 282N00000X General Acute Care Hospital (NPI, licence, practice city):
    1023300472  18686 MA             BOSTON
    1083740914  (no licence listed)  NORTH ANDOVER
    1114196961  (no licence listed)  BOSTON
    1134262819  99562 MA             BOSTON
    1154468510  205807 MA            BOSTON
    1184613721  79142 MA             BOSTON
    1205181021  9704 MA              SOUTH BOSTON
    1225232366  042697983 MA         BOSTON
    1366561391  16398 MA             BOSTON
    1417075193  16634 MA             SOMERVILLE
    1558506147  (no licence listed)  BOSTON
    1578842498  196727 MA            BOSTON
    1720455603  10168 MA             LEXINGTON
    1740573229  18408 MA             ARLINGTON
    1790812105  (no licence listed)  BROCKTON
    1942337126  (no licence listed)  RANDOLPH
    1962750919  202329 MA            BOSTON
    1992926992  213663 MA            BOSTON

Source: NPPES NPI Registry (CMS), API version 2.1, https://npiregistry.cms.hhs.gov/api/?version=2.1&number=1134262819, accessed 16 November 2026 04:54 UTC. Data as reported to NPPES by the provider.
CMS: "Issuance of an NPI does not ensure or validate that the Health Care Provider is Licensed or Credentialed."
```

### 2. robots.txt, query mistakes and how the search fields match (browser)

1 page load plus 1 navigation back to JSON and 18 in-page `fetch()` calls in the same tab. Taxonomy probes print only the counts of primary taxonomies, no names.

```python
import collections, json, time, urllib.parse

SITE = "https://npiregistry.cms.hhs.gov"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__u[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(query, version="2.1"):
    """One in-page GET of /api/ -> (status, parsed JSON). No retries: this block only inspects answers."""
    url = SITE + "/api/?" + urllib.parse.urlencode(({"version": version} if version else {}) | query)
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.3)
    time.sleep(2.0)
    return r["status"], json.loads(r["text"])

def brief(status, d, top=False):
    if "Errors" in d:
        return f"HTTP {status} Errors {[(e['number'], e['description']) for e in d['Errors']]}"
    out = f"HTTP {status} result_count {d['result_count']}"
    if top and d["results"]:
        c = collections.Counter(next(t["desc"] for t in x["taxonomies"] if t["primary"]) for x in d["results"])
        out += f", primary taxonomy {c.most_common(2)}"
    elif d["results"]:
        out += f", first {[x['number'] for x in d['results'][:3]]}"
    return out

# robots.txt: the cloud browser is sent to the search page; there are no robots directives.
new_tab(SITE + "/robots.txt")
wait_for_load()
time.sleep(3)
print(f"robots.txt -> {js('location.href')} ({js('document.contentType')}), page text starts: "
      f"{' | '.join((js('document.body.innerText') or '').split(chr(10))[1:3])!r}")
goto_url(SITE + "/api/?version=2.1&number=1134262819")  # back to a JSON page for same-origin fetch()
wait_for_load()
print()

N, MGH = {"number": "1134262819"}, {"state": "MA", "enumeration_type": "NPI-2"}
BOS = {"city": "boston", "state": "MA", "limit": 200}
for label, q, v, top in (
    ("no version=                             ", N, None, False),
    ("version=2.0                             ", N, "2.0", False),
    ("state=MA alone                          ", {"state": "MA"}, "2.1", False),
    ("enumeration_type=NPI-2 alone            ", {"enumeration_type": "NPI-2"}, "2.1", False),
    ("9-digit number                          ", {"number": "113426281"}, "2.1", False),
    ("wrong check digit 1134262818            ", {"number": "1134262818"}, "2.1", False),
    ("right number, wrong state               ", N | {"state": "CA"}, "2.1", False),
    ("org name 'massachusetts general'       ", {"organization_name": "massachusetts general"} | MGH, "2.1", False),
    ("org name 'massachusetts gen*'          ", {"organization_name": "massachusetts gen*", "limit": 200} | MGH, "2.1", False),
    ("org name 'm*'                          ", {"organization_name": "m*"} | MGH, "2.1", False),
    ("taxonomy 'hospital', Boston, NPI-2      ", {"taxonomy_description": "hospital", "enumeration_type": "NPI-2"} | BOS, "2.1", True),
    ("taxonomy 'general acute care hospital'  ", {"taxonomy_description": "general acute care hospital"} | BOS, "2.1", True),
    ("taxonomy 'cardiology', Boston           ", {"taxonomy_description": "cardiology"} | BOS, "2.1", True),
    ("taxonomy 'cardiovascular disease'       ", {"taxonomy_description": "cardiovascular disease"} | BOS, "2.1", True),
    ("limit=201                               ", {"taxonomy_description": "general acute care hospital", "state": "CA", "limit": 201}, "2.1", False),
    ("limit=0                                 ", {"taxonomy_description": "general acute care hospital", "state": "CA", "limit": 0}, "2.1", False),
    ("skip=1000 limit=5, first request        ", {"taxonomy_description": "general acute care hospital", "state": "CA", "limit": 5, "skip": 1000}, "2.1", False),
    ("skip=1000 limit=5, same request again   ", {"taxonomy_description": "general acute care hospital", "state": "CA", "limit": 5, "skip": 1000}, "2.1", False),
):
    print(label, brief(*raw(q, v), top=top))
```

Output (from the run on 2026-11-16, 04:56 UTC):

```text
robots.txt -> https://npiregistry.cms.hhs.gov/search (text/html), page text starts: 'NPPES NPI Registry | NPPES'

no version=                              HTTP 200 Errors [('17', 'Unsupported Version')]
version=2.0                              HTTP 200 Errors [('17', 'Unsupported Version')]
state=MA alone                           HTTP 200 Errors [('07', 'Field state requires additional search criteria')]
enumeration_type=NPI-2 alone             HTTP 200 Errors [('09', 'Enumeration_type requires additional search criteria')]
9-digit number                           HTTP 200 Errors [('06', 'NPI must be 10 digits')]
wrong check digit 1134262818             HTTP 200 result_count 0
right number, wrong state                HTTP 200 result_count 0
org name 'massachusetts general'        HTTP 200 result_count 0
org name 'massachusetts gen*'           HTTP 200 result_count 50, first ['1245473859', '1508390014', '1942118161']
org name 'm*'                           HTTP 200 Errors [('03', 'Wildcards require at least two leading characters')]
taxonomy 'hospital', Boston, NPI-2       HTTP 200 result_count 13, primary taxonomy [('Hospitalist', 6), ('Internal Medicine', 4)]
taxonomy 'general acute care hospital'   HTTP 200 result_count 200, primary taxonomy [('General Acute Care Hospital', 144), ('General Acute Care Hospital, Children', 21)]
taxonomy 'cardiology', Boston            HTTP 200 result_count 6, primary taxonomy [('Pharmacist, Cardiology', 6)]
taxonomy 'cardiovascular disease'        HTTP 200 result_count 200, primary taxonomy [('Internal Medicine, Cardiovascular Disease', 156), ('Internal Medicine', 15)]
limit=201                                HTTP 200 result_count 200, first ['1174939284', '1013306307', '1215186267']
limit=0                                  HTTP 200 result_count 10, first ['1174939284', '1013306307', '1215186267']
skip=1000 limit=5, first request         HTTP 200 result_count 5, first ['1801792437', '1649177114', '1538065057']
skip=1000 limit=5, same request again    HTTP 200 result_count 5, first ['1013813518', '1649177114', '1538065057']
```

### 3. Same lookup with Python urllib, robots check for every agent (no browser)

Sends a descriptive User-Agent. 3 calls (robots.txt and 2 API calls); the wrong check digit is caught locally and never sent.

```python
import json, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser

SITE = "https://npiregistry.cms.hhs.gov"
UA = "npi-registry-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]

def fetch(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read().decode()

def api(**params):
    """-> parsed JSON. One 60 s wait on HTTP 429/500/502/503/504 or a network error; exits on anything else,
    including the HTTP 200 answers that carry an "Errors" list instead of results."""
    url = f"{SITE}/api/?" + urllib.parse.urlencode({"version": "2.1"} | params)
    for attempt in range(2):
        time.sleep(2.0)  # hourly query limit, value not published: stay serial and slow
        try:
            status, ctype, body = fetch(url)
            d = json.loads(body)
            if "Errors" in d:
                sys.exit(f"{url}: API error {[(e['field'], e['description']) for e in d['Errors']]}")
            return d
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"HTTP {e.code} {url}: {e.read().decode()[:200]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url}: {e}")

def check_digit_ok(npi):
    """Luhn over '80840' + the first 9 digits (CMS, Requirements for NPI and NPI Check Digit, 2004)."""
    if len(npi) != 10 or not npi.isdigit():
        return False
    s = sum((d - 9 if d > 9 else d) for d in (int(c) * (2 - i % 2) for i, c in enumerate(reversed("80840" + npi[:9]))))
    return (10 - s % 10) % 10 == int(npi[9])

# robots.txt: the server answers with the web app's HTML, so there are no directives at all.
status, ctype, body = fetch(SITE + "/robots.txt")
directives = [l for l in body.splitlines() if l.split(":")[0].strip().lower() in ("user-agent", "allow", "disallow", "crawl-delay")]
print(f"robots.txt HTTP {status} {ctype}, {len(body)} bytes, <app-root> in body: {'<app-root>' in body}, directive lines: {len(directives)}")
rp = urllib.robotparser.RobotFileParser()
rp.parse(body.splitlines())
blocked = 0
for p in ("/api/?version=2.1&number=1134262819", "/api-page", "/search"):
    ok = [a for a in AGENTS if rp.can_fetch(a, SITE + p)]
    print(f"  {p:<38} allowed for {len(ok)}/{len(AGENTS)} agents")
    blocked += len(AGENTS) - len(ok)
if directives or blocked:
    sys.exit("robots.txt now has rules: re-check them before using the API")

for npi in ("1134262819", "1134262818"):
    print(f"\n{npi}: check digit {'ok' if check_digit_ok(npi) else 'WRONG (a typo; the API would just return 0 results)'}")
    if not check_digit_ok(npi):
        continue
    d = api(number=npi)
    if d["result_count"] != 1:
        sys.exit(f"{npi}: {d['result_count']} records")
    r = d["results"][0]
    t = [x for x in r["taxonomies"] if x["primary"]]
    loc = [a for a in r["addresses"] if a["address_purpose"] == "LOCATION"]
    if len(t) != 1 or len(loc) != 1:
        sys.exit(f"{npi}: {len(t)} primary taxonomies, {len(loc)} practice addresses")
    t, loc = t[0], loc[0]
    print(f"  {r['basic'].get('organization_name') or 'individual (NPI-1)'} | {r['enumeration_type']} | status {r['basic']['status']}"
          f" | {t['code']} {t['desc']} | licence {t.get('license') or '-'} {t.get('state') or ''}"
          f" | {loc['address_1']}, {loc['city']}, {loc['state']} {loc['postal_code'][:5]}")
    print(f"  addresses in the order served: {[a['address_purpose'] for a in r['addresses']]}")

# result_count is the size of this answer, not a total: 200 means "at least 200".
d = api(taxonomy_description="general acute care hospital", city="boston", state="MA", limit=200)
print(f"\nGeneral Acute Care Hospital taxonomy in Boston MA: result_count {d['result_count']}, "
      f"{len(d['results'])} records in the answer -> {'capped: partial, complete lists need the DDS file' if len(d['results']) == 200 else 'complete'}")
```

Output (from the run on 2026-11-16, 04:56 UTC):

```text
robots.txt HTTP 200 text/html, 406 bytes, <app-root> in body: True, directive lines: 0
  /api/?version=2.1&number=1134262819    allowed for 11/11 agents
  /api-page                              allowed for 11/11 agents
  /search                                allowed for 11/11 agents

1134262819: check digit ok
  MASSACHUSETTS GENERAL HOSPITAL | NPI-2 | status A | 282N00000X General Acute Care Hospital | licence 99562 MA | 55 FRUIT ST, BOSTON, MA 02114
  addresses in the order served: ['MAILING', 'LOCATION']

1134262818: check digit WRONG (a typo; the API would just return 0 results)

General Acute Care Hospital taxonomy in Boston MA: result_count 200, 200 records in the answer -> capped: partial, complete lists need the DDS file
```

### 4. curl, headers and mistakes

```bash
A='https://npiregistry.cms.hhs.gov/api/'
# one NPI: name, type, primary taxonomy with licence, practice address (picked by address_purpose)
curl -sS --fail -G "$A" -d version=2.1 -d number=1134262819 \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); r=d["results"][0]; t=[x for x in r["taxonomies"] if x["primary"]][0]; a=[x for x in r["addresses"] if x["address_purpose"]=="LOCATION"][0]; print(d["result_count"], r["number"], r["basic"]["organization_name"], r["enumeration_type"], "|", t["desc"], t["license"], t["state"], "|", a["address_1"], a["city"], a["state"])'
sleep 2
# headers: JSON, no caching, no CORS header (browser code must run on an npiregistry.cms.hhs.gov page)
curl -sS -G -D - -o /dev/null "$A" -d version=2.1 -d number=1134262819 \
  | tr -d '\r' | grep -iE '^(HTTP/|(content-type|cache-control|access-control-allow-origin|x-cache):)'
sleep 2
# all organizational NPIs under one legal name in one state (35 here, so one request is complete)
curl -sS --fail -G "$A" -d version=2.1 --data-urlencode 'organization_name=massachusetts general hospital' \
  -d state=MA -d enumeration_type=NPI-2 -d limit=200 | python3 -c 'import json,sys; print("result_count", json.load(sys.stdin)["result_count"])'
sleep 2
# mistakes are HTTP 200 too: an Errors list, or zero results
curl -sS -G -w ' <- HTTP %{http_code}\n' "$A" -d number=1134262819
sleep 2
curl -sS -G -w ' <- HTTP %{http_code}\n' "$A" -d version=2.1 -d number=1134262818
```

Output (from the run on 2026-11-16, 04:57 UTC):

```text
1 1134262819 MASSACHUSETTS GENERAL HOSPITAL NPI-2 | General Acute Care Hospital 99562 MA | 55 FRUIT ST BOSTON MA
HTTP/2 200 
content-type: application/json
cache-control: no-cache, no-store, must-revalidate
x-cache: Miss from cloudfront
result_count 35
{"Errors":[{"description":"Unsupported Version","field":"version","number":"17"}]} <- HTTP 200
{"result_count":0,"results":[]} <- HTTP 200
```

## Fields (api/?version=2.1)

| JSON path | Notes |
|---|---|
| `result_count`, `results[]` | `result_count` is the number of records in this answer (at most 200), not the total match count; a mistake returns `Errors[]` (`number`, `field`, `description`) instead, still HTTP 200 |
| `number`, `enumeration_type` | the 10-digit NPI; `NPI-1` individual (Type 1), `NPI-2` organization (Type 2) |
| `basic.organization_name`, `basic.organizational_subpart` | Type 2 legal name; subpart `YES`/`NO` (THE GENERAL HOSPITAL CORPORATION 1902991573 is a subpart) |
| `basic.first_name`, `middle_name`, `last_name`, `credential`, `sole_proprietor`, `sex`, `certification_date` | Type 1 only |
| `basic.status`, `enumeration_date`, `last_updated` | `A` = active; the Registry lists active NPIs; dates `YYYY-MM-DD`. `created_epoch`, `last_updated_epoch` are milliseconds as strings |
| `taxonomies[]`: `code`, `desc`, `primary`, `license`, `state`, `taxonomy_group` | up to 15 (API page); exactly one has `primary: true`. `license` + `state` is the state licence the provider reported for that taxonomy, or `null` (5 of MGH's 18 acute-care NPIs have none) |
| `addresses[]`: `address_purpose`, `address_1`, `address_2`, `city`, `state`, `postal_code`, `telephone_number`, `fax_number`, `country_code`, `address_type` | one `LOCATION` (primary practice) and one `MAILING`; pick by `address_purpose`. `postal_code` is 5 or 9 digits without a hyphen (021142621) |
| `practiceLocations[]`, `other_names[]`, `identifiers[]`, `endpoints[]` | other practice addresses; other organization names (`code`, `organization_name`, `type`, e.g. "Other Name"); other payer identifiers (up to 50); electronic endpoints |
| response headers | `content-type: application/json`, `cache-control: no-cache, no-store, must-revalidate`, served through CloudFront; no `access-control-allow-origin` |

## Gotchas

- **Check for `Errors` on every answer.** HTTP status is 200 for an unsupported version (error 17), `state` alone (07), `enumeration_type` alone (09), a number that is not 10 digits (06) and a one-character wildcard (03). `curl --fail` does not catch them.
- **Zero results is not proof the NPI does not exist.** A typo, a deactivated NPI (the search page calls the Registry a directory of "all active" NPI records; not tested) and an extra criterion that does not match (`number=1134262819&state=CA`) all give `result_count` 0. Check the check digit first (block 1), then query by number alone.
- **The address order in the docs is wrong for some records.** The API page says "The first address in the array will always be the Primary Practice Location and the second address in the array will always be the Mailing Address." For 1134262819 the order served was `['MAILING', 'LOCATION']` (block 3). Select by `address_purpose`.
- **One organization, many NPIs.** Massachusetts General Hospital has 35 organizational NPIs in MA, 18 with the General Acute Care Hospital taxonomy at several addresses, each with its own licence number or none. The Registry does not say which one a payer or claim uses; verify the specific NPI you were given.
- **Name search is whole-name or trailing wildcard.** `organization_name=massachusetts general` returned 0; `massachusetts gen*` with `state=MA` returned 50 organizational records; `m*` is error 03. The API page: "All types of Organization Names (LBN, DBA, Former LBN, Other Name) associated with an NPI are examined", so results can carry a different legal name (THE GENERAL HOSPITAL CORPORATION). Case does not matter (`MASSACHUSETTS GENERAL HOSPITAL` and `state=ma` gave the same 35).
- **`taxonomy_description` does not search inside the description.** Observed, not documented: `hospital` in Boston (NPI-2) matched 13 organizations, every one with a Hospitalist taxonomy and none with a hospital primary taxonomy; `cardiology` matched only "Pharmacist, Cardiology" (6), while `cardiovascular disease` hit the 200 cap. It matches any of a provider's taxonomies, not only the primary one. Use the wording of the taxonomy (`general acute care hospital`, `cardiovascular disease`).
- **Do not page through big result sets.** `limit` is cut to 200 without an error, `result_count` shows only what came back, and two identical `skip=1000` requests returned records in a different order (block 2). Report a 200-record answer as partial. For lists or more than a few lookups, CMS says to use the downloadable file.
- **Licence numbers are self-reported and state-specific.** Values under one organization name include `9704` and `042697983`, and one MGH Type 2 record (1710268362, primary taxonomy Nurse Practitioner, Adult Health) lists `RN2258297`. Treat it as the number the provider gave NPPES, check it with the state board that issued it, and quote the CMS notice.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **`/api/` without `version=2.1`**, `version=1.0`, `version=2.0`: HTTP 200 with error 17 "Unsupported Version" (the API page: the old links "will no longer work").
- **The search page as a data source**: https://npiregistry.cms.hhs.gov/search is a JavaScript app (curl gets a 406-byte shell); use the API. The search page "limits searches to the first 2100 results".
- **Bulk extraction**: the search page says "Bulk NPI Registry queries must use the DDS file" (the NPPES Downloadable File, monthly full and weekly incremental, linked from the CMS dissemination page). Not used here.
- **Not tested:** rate-limit behaviour (never provoked), the `address_purpose`, `postal_code` wildcard, `first_name`/`last_name` alias and `name_purpose` filters, and deactivated NPIs.
