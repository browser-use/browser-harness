# Federal Register - Documents an Agency Published This Week (official API)

Field-tested against www.federalregister.gov on 2026-11-08 (a Sunday) using a Browser Use cloud browser, logged out, plus plain HTTP (Python urllib, curl). About 25 browser API calls, 15 page loads and 15 plain HTTP calls, all serial: every answer was HTTP 200 or a documented 400, no 429, no challenge, no login or consent wall.

robots.txt (fetched 2026-11-08) has only a `User-agent: *` group, which disallows `/documents/current`, `/documents/email-a-friend`, `/articles/search`, `/documents/search`, `/public-inspection/search`, `/regulations/search`, `/my/` and `/auth/`; `/api/v1/` is not disallowed and there are no named AI-agent groups. Terms: there is no separate ToS (the old terms-of-service URL is a 404); the API page says "No API keys are needed; all you need is an HTTP client or browser", and its one usage restriction is "Republishers of Federal Register material are not permitted to use official NARA or OFR logos or seals." The site's access page (unblock.federalregister.gov) says "programmatic access to these sites is limited to access to our extensive developer APIs", so both blocks read data only from `/api/v1/`. About This Site: "Any person may reproduce or republish any material appearing in any regular or special edition of the Federal Register (1 CFR 2.6)."

## Quick summary

- **Use the API, never the HTML search.** `GET /api/v1/documents.json?conditions[agencies][]=<slug>&conditions[publication_date][gte]=<monday>&conditions[publication_date][lte]=<sunday>&order=newest` lists the week's documents as JSON. `/documents/search` is disallowed in robots.txt.
- **Agency slugs** come from `GET /api/v1/agencies` (473 agencies on 2026-11-08: `slug`, `name`, `short_name`, `parent_id`, `child_slugs`). Names read "Agriculture Department", not "Department of Agriculture". A wrong slug is HTTP 400 `{"errors":{"agencies":"invalid value"}}`, not an empty list.
- **Set an end date.** On Sunday 2026-11-08 the API already listed Monday 2026-11-09's issue: EPA `gte=2026-11-02` alone gave 18 documents, with `lte=2026-11-08` 16.
- **A parent department includes its sub-agencies.** Each document lists every agency on it (`agriculture-department` plus `animal-and-plant-health-inspection-service`), so both slugs match it.
- **Pick fields** with repeated `fields[]=` (56 names in the spec's `DocumentField` enum): `comments_close_on`, `effective_on`, `docket_ids`, `regulation_id_numbers`, `action`, `html_url`, `pdf_url` and more.
- **Paging:** `per_page` (default 20; spec says 1000 max), follow `next_page_url` (it carries a `search_after_cursor`). The docs: "you can only paginate through the first 2000 results. If you wish to download more results, use the date range filters." One agency-week is far below that (EPA 16, USDA 18, all agencies 466 for 2026-11-02..08).
- **Browser or plain HTTP, API only.** Block 1 opens the tab on an API URL, so `fetch()` is same-origin and no HTML page is loaded. The API also answers plain HTTP (block 2). HTML pages over plain HTTP are redirected to `unblock.federalregister.gov` ("Request Access", a CAPTCHA): the site limits programmatic access to the API. Do not script HTML pages.

## What works

### 1. One agency's documents this week, by name or short name (browser, official API)

Self-contained. Resolves `AGENCY` against the agency list, takes this week's Monday to Sunday in Eastern time, and follows `next_page_url` to the end. `fetch_json()` returns parsed JSON on 200, waits 30 s on 429/5xx and otherwise raises, so a failure never looks like "no documents".

```python
import collections, datetime, json, os, tempfile, time, urllib.parse, zoneinfo

AGENCY = "EPA"  # agency name, short name or slug, e.g. "Environmental Protection Agency", "EPA", "environmental-protection-agency"

SITE = "https://www.federalregister.gov"
API = SITE + "/api/v1/"
FIELDS = ["document_number", "publication_date", "type", "title", "action", "agencies", "html_url", "pdf_url",
          "comments_close_on", "effective_on", "docket_ids", "regulation_id_numbers", "significant"]

def on_site():
    """A logged-out tab on www.federalregister.gov, so fetch() to /api/v1/ is same-origin. It opens a small API URL, not an HTML page:
    the site limits programmatic access to its API."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(API + "documents.json?per_page=1&fields[]=document_number")
    wait_for_load()
    time.sleep(2)
    if js("location.origin") != SITE:
        raise RuntimeError(f"tab landed on {js('location.href')} (access check?): stop and tell the user; do not retry around it")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__fr = window.__fr || {}; const id = String(Math.random()).slice(2); window.__fr[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__fr[id] = {status: r.status, url: r.url, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__fr[id] = {status: 0, url: '', type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__fr[%s]; if (v) delete window.__fr[%s]; return v; })()"""

def fetch_json(url, tries=3, timeout=60):
    """GET url from inside the tab -> parsed JSON. 400 carries {"errors": {...}}. Waits 30 s on 429/5xx, raises on anything else,
    and on an HTML answer (the site's "Request Access" check), so a failure never looks like "no documents"."""
    for attempt in range(tries):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.5)
        time.sleep(1)  # serial, about one call per second
        if r["status"] == 200 and "json" in (r["type"] or ""):
            return json.loads(r["text"])
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt < tries - 1:
            time.sleep(30)
            continue
        raise RuntimeError(f"{url}: HTTP {r['status']} {r['type']} at {r['url']}: {r['text'][:200]!r}; stopping")

def find_agency(q, agencies):
    """Exact slug or name, then short name, then a unique substring of the name. Raises with candidates otherwise:
    short names repeat (DOE = Energy Department and its EERE office, FS = Fiscal Service and Forest Service)."""
    ql = q.strip().lower()
    for a in agencies:
        if ql in (a["slug"], a["name"].lower()):
            return a
    hits = [a for a in agencies if (a.get("short_name") or "").lower() == ql] or [a for a in agencies if ql in a["name"].lower()]
    if len(hits) == 1:
        return hits[0]
    raise ValueError(f"{q!r}: {len(hits)} matches: {[(a['slug'], a['name']) for a in hits[:10]]}")

def documents(slug, since, until=None):
    """Every document the agency (or any of its sub-agencies) published on or after `since`, newest first, following next_page_url."""
    params = [("conditions[agencies][]", slug), ("conditions[publication_date][gte]", since), ("order", "newest"), ("per_page", 100)]
    if until:
        params.append(("conditions[publication_date][lte]", until))
    params += [("fields[]", f) for f in FIELDS]
    url = API + "documents.json?" + urllib.parse.urlencode(params)
    rows, first = [], None
    while url:
        d = fetch_json(url)
        first = first or d
        if d["count"] > 2000:
            raise RuntimeError(f"{d['count']} documents: the API pages through the first 2000 only, and its docs say to use the date range filters for more")
        rows += d.get("results", [])  # a 0-count answer has no "results" key
        url = d.get("next_page_url")
    if len(rows) != first["count"]:
        raise RuntimeError(f"got {len(rows)} rows, count says {first['count']}: paging changed; stopping")
    return first["description"], rows

on_site()
agencies = fetch_json(API + "agencies")
ag = find_agency(AGENCY, agencies)
today = datetime.datetime.now(zoneinfo.ZoneInfo("America/New_York")).date()  # the Federal Register publishes on Eastern time
monday = today - datetime.timedelta(days=today.weekday())
sunday = monday + datetime.timedelta(days=6)  # without an end date the next issue shows up too: it is listed before its publication date
desc, docs = documents(ag["slug"], monday.isoformat(), sunday.isoformat())
print(f"{len(agencies)} agencies listed; {AGENCY!r} -> {ag['slug']} ({ag['name']}, short name {ag.get('short_name')}, {len(ag['child_slugs'])} sub-agencies)")
print(f"today {today} (ET), week {monday}..{sunday}: {desc}")
print(f"{len(docs)} documents | by type {dict(collections.Counter(d['type'] for d in docs))}")
print("by day:", dict(collections.Counter(d["publication_date"] for d in docs)))
for d in docs:
    extra = " | ".join(x for x in (d["comments_close_on"] and f"comments close {d['comments_close_on']}",
                                    d["effective_on"] and f"effective {d['effective_on']}",
                                    d["significant"] and "significant") if x)
    print(f"\n{d['publication_date']} {d['type']:<13} {d['document_number']}  {d['title'][:100].rstrip()}")
    print(f"   {(d['action'] or '-')[:60]} | dockets {d['docket_ids'][:2]} | RIN {d['regulation_id_numbers'][:1]}" + (f" | {extra}" if extra else ""))
    print("  ", d["html_url"])
fd, out = tempfile.mkstemp(prefix=f"federal_register_{ag['slug']}_{monday}_", suffix=".json")  # a new file each run
with os.fdopen(fd, "w") as f:
    json.dump(docs, f)
print("\nsaved:", os.path.basename(out), "in tempfile.gettempdir()")
```

Output (from the run on 2026-11-08):

```text
473 agencies listed; 'EPA' -> environmental-protection-agency (Environmental Protection Agency, short name EPA, 0 sub-agencies)
today 2026-11-08 (ET), week 2026-11-02..2026-11-08: Documents published from 11/02/2026 to 11/08/2026 and from Environmental Protection Agency
16 documents | by type {'Notice': 6, 'Rule': 5, 'Proposed Rule': 5}
by day: {'2026-11-06': 2, '2026-11-05': 10, '2026-11-03': 2, '2026-11-02': 2}

2026-11-06 Notice        2026-22684  Environmental Impact Statements; Notice of Availability
   - | dockets ['FRL OPRM-FAD-247'] | RIN []
   https://www.federalregister.gov/documents/2026/11/06/2026-22684/environmental-impact-statements-notice-of-availability

2026-11-06 Rule          2026-22671  Air Plan Approval; California; Revised Format for Materials Incorporated by Reference
   Final rule; administrative change. | dockets ['EPA-R09-OAR-2024-0527', 'FRL-13582-01-R9'] | RIN [] | effective 2026-11-06
   https://www.federalregister.gov/documents/2026/11/06/2026-22671/air-plan-approval-california-revised-format-for-materials-incorporated-by-reference

2026-11-05 Rule          2026-22647  Air Plan Revisions; Arizona; Maricopa County Air Quality Department; New Source Review; Emission Red
   Final rule. | dockets ['EPA-R09-OAR-2026-1684', 'FRL-13268-02-R9'] | RIN [] | effective 2026-12-07
   https://www.federalregister.gov/documents/2026/11/05/2026-22647/air-plan-revisions-arizona-maricopa-county-air-quality-department-new-source-review-emission

2026-11-05 Proposed Rule 2026-22592  Air Plan Approval; District of Columbia; Enhanced Vehicle Emission Inspection and Maintenance (I/M)
   Proposed rule. | dockets ['EPA-R03-OAR-2026-1024', 'FRL-12072-01-R3'] | RIN [] | comments close 2026-12-07
   https://www.federalregister.gov/documents/2026/11/05/2026-22592/air-plan-approval-district-of-columbia-enhanced-vehicle-emission-inspection-and-maintenance-im

2026-11-05 Proposed Rule 2026-22588  Air Quality Implementation Plans; California; San Joaquin Valley; 2015 8-Hour Ozone Nonattainment Ar
   Proposed rule. | dockets ['EPA-R09-OAR-2026-8252', 'FRL-13635-01-R9'] | RIN [] | comments close 2026-12-07
   https://www.federalregister.gov/documents/2026/11/05/2026-22588/air-quality-implementation-plans-california-san-joaquin-valley-2015-8-hour-ozone-nonattainment-area

2026-11-05 Proposed Rule 2026-22585  Approval and Promulgation of State Plans for Designated Facilities and Pollutants; Arizona; Control
   Proposed rule. | dockets ['EPA-R09-OAR-2026-5710', 'FRL-13516-01-R9'] | RIN [] | comments close 2026-12-07
   https://www.federalregister.gov/documents/2026/11/05/2026-22585/approval-and-promulgation-of-state-plans-for-designated-facilities-and-pollutants-arizona-control-of

2026-11-05 Rule          2026-22584  Approval and Promulgation of State Plans for Designated Facilities and Pollutants; West Virginia; Co
   Final rule. | dockets ['EPA-R03-OAR-2023-0230', 'FRL-9329-03-R3'] | RIN [] | effective 2026-12-07
   https://www.federalregister.gov/documents/2026/11/05/2026-22584/approval-and-promulgation-of-state-plans-for-designated-facilities-and-pollutants-west-virginia

2026-11-05 Proposed Rule 2026-22583  Approval and Promulgation of Delegation of Authority for Designated Facilities and Pollutants; Alleg
   Proposed rule. | dockets ['EPA-R03-OAR-2026-5021', 'FRL-13501-01-R3'] | RIN [] | comments close 2026-12-07
   https://www.federalregister.gov/documents/2026/11/05/2026-22583/approval-and-promulgation-of-delegation-of-authority-for-designated-facilities-and-pollutants

2026-11-05 Rule          2026-22576  Significant New Use Rules on Certain Chemical Substances (25-3.5e)
   Final rule. | dockets ['EPA-HQ-OPPT-2025-2169', 'FRL-13126-03-OCSPP'] | RIN ['2070-AB27'] | effective 2027-01-04
   https://www.federalregister.gov/documents/2026/11/05/2026-22576/significant-new-use-rules-on-certain-chemical-substances-25-35e

2026-11-05 Notice        2026-22548  Proposed Consent Decree
   Notice of proposed consent decree; request for public commen | dockets ['EPA-HQ-OGC-2026-9242', 'FRL-13676-01-OGC'] | RIN [] | comments close 2026-12-07
   https://www.federalregister.gov/documents/2026/11/05/2026-22548/proposed-consent-decree

2026-11-05 Notice        2026-22547  Public Meeting of the Clean Air Scientific Advisory Committee (CASAC) on Lead
   Notice. | dockets ['FRL- 13687-01-AO'] | RIN []
   https://www.federalregister.gov/documents/2026/11/05/2026-22547/public-meeting-of-the-clean-air-scientific-advisory-committee-casac-on-lead

2026-11-05 Notice        2026-22546  Cross-Media Electronic Reporting: Announcement of Determination To Approve Authorized Program Revisi
   Notice. | dockets ['FRL-13494-01-OFA'] | RIN []
   https://www.federalregister.gov/documents/2026/11/05/2026-22546/cross-media-electronic-reporting-announcement-of-determination-to-approve-authorized-program

2026-11-03 Rule          2026-22404  National Emission Standards for Hazardous Air Pollutants: Lime Manufacturing Plants Technology Revie
   Correcting amendment. | dockets ['EPA-HQ-OAR-2026-7525', 'FRL-5948.4-01-OAR'] | RIN [] | effective 2026-11-03
   https://www.federalregister.gov/documents/2026/11/03/2026-22404/national-emission-standards-for-hazardous-air-pollutants-lime-manufacturing-plants-technology-review

2026-11-03 Notice        2026-22392  Avanti Corporation; Access to Confidential Business Information
   Notice. | dockets ['EPA-HQ-OPPT-2003-0004', 'FRL-13681-01-OCSPP'] | RIN []
   https://www.federalregister.gov/documents/2026/11/03/2026-22392/avanti-corporation-access-to-confidential-business-information

2026-11-02 Proposed Rule 2026-22295  Significant New Use Rules on Certain Chemical Substances (26-7)
   Proposed rule. | dockets ['EPA-HQ-OPPT-2026-5974', 'FRL-13610-01-OCSPP'] | RIN ['2070-AB27'] | comments close 2026-12-02
   https://www.federalregister.gov/documents/2026/11/02/2026-22295/significant-new-use-rules-on-certain-chemical-substances-26-7

2026-11-02 Notice        2026-22291  Certain New Chemicals or Significant New Uses; Statements of Findings-July 2026
   Notice. | dockets ['EPA-HQ-OPPT-2026-1849', 'FRL-13203-07-OCSPP'] | RIN []
   https://www.federalregister.gov/documents/2026/11/02/2026-22291/certain-new-chemicals-or-significant-new-uses-statements-of-findings-july-2026

saved: federal_register_environmental-protection-agency_2026-11-02_r6qb0qti.json in tempfile.gettempdir()
```

### 2. A department with sub-agencies: breakdown, comment deadlines, next issue (plain HTTP, no browser)

Python standard library only, truthful User-Agent, 4 calls at 1 s spacing.

```python
import collections, datetime, json, time, urllib.error, urllib.parse, urllib.request, zoneinfo

AGENCY = "agriculture-department"  # a parent department: its sub-agencies' documents are included
UA = {"User-Agent": "browser-harness-skill/1.0 (Python urllib)"}
API = "https://www.federalregister.gov/api/v1/"

def call(path, params=()):
    """GET -> parsed JSON. 400 = bad parameter ({"errors": {...}}), raised as ValueError. Waits 30 s on 429/5xx, then stops.
    An HTML answer means the site's access check (unblock.federalregister.gov): stop, do not work around it."""
    url = API + path + ("?" + urllib.parse.urlencode(list(params)) if params else "")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                status, body, ctype, final = r.status, r.read(), r.headers.get("content-type", ""), r.url
        except urllib.error.HTTPError as e:
            status, body, ctype, final = e.code, e.read(), e.headers.get("content-type", ""), url
        time.sleep(1)  # serial, about one call per second
        if status == 200 and "json" in ctype:
            return json.loads(body)
        if status == 400:
            raise ValueError(f"HTTP 400 {body[:200].decode()}")
        if status not in (429, 500, 502, 503, 504) or attempt == 2:
            raise RuntimeError(f"{url}: HTTP {status} {ctype} at {final}; stopping")
        time.sleep(30)

def week_docs(slug, since, until, fields):
    params = [("conditions[agencies][]", slug), ("conditions[publication_date][gte]", since),
              ("conditions[publication_date][lte]", until), ("order", "newest"), ("per_page", 1000)] + [("fields[]", f) for f in fields]
    d = call("documents.json", params)
    if d["count"] > 1000:
        raise RuntimeError(f"{d['count']} documents: page with next_page_url or split the dates")
    return d.get("results", [])

ag = call("agencies/" + AGENCY)
today = datetime.datetime.now(zoneinfo.ZoneInfo("America/New_York")).date()
monday = today - datetime.timedelta(days=today.weekday())
docs = week_docs(AGENCY, monday.isoformat(), (monday + datetime.timedelta(days=6)).isoformat(),
                 ["document_number", "publication_date", "type", "title", "agencies", "comments_close_on", "html_url"])
print(f"{ag['name']}: {len(ag['child_slugs'])} sub-agencies | week {monday}..{monday + datetime.timedelta(days=6)}: {len(docs)} documents")
by_sub = collections.Counter(" + ".join(a["name"] for a in d["agencies"] if a.get("slug") != AGENCY) or ag["name"] + " (itself)"
                             for d in docs)  # a document can list several sub-agencies
print("by sub-agency:", by_sub.most_common())
print("by type:", dict(collections.Counter(d["type"] for d in docs)))
open_comments = sorted((d["comments_close_on"], d["document_number"], d["title"]) for d in docs if d["comments_close_on"])
print(f"\n{len(open_comments)} with a comment deadline:")
for close, num, title in open_comments:
    print(f"  closes {close}  {num}  {title[:90].rstrip()}")

# The next issue is already listed before its date: documents dated after today
nxt = week_docs(AGENCY, (today + datetime.timedelta(days=1)).isoformat(), (today + datetime.timedelta(days=7)).isoformat(),
                ["document_number", "publication_date", "type", "title"])
print(f"\nalready listed with a later date: {len(nxt)}", [(d["publication_date"], d["type"], d["title"][:60]) for d in nxt[:3]])

# A wrong slug is a 400, not an empty list
try:
    call("documents.json", [("conditions[agencies][]", "usda"), ("conditions[publication_date][gte]", monday.isoformat())])
except ValueError as e:
    print("\nslug 'usda':", e)
```

Output (from the run on 2026-11-08):

```text
Agriculture Department: 36 sub-agencies | week 2026-11-02..2026-11-08: 18 documents
by sub-agency: [('Agriculture Department (itself)', 6), ('Food and Nutrition Administration', 5), ('Foreign Agricultural Service', 3), ('Agricultural Marketing Service', 2), ('Animal and Plant Health Inspection Service', 1), ('Forest Service', 1)]
by type: {'Notice': 16, 'Rule': 2}

6 with a comment deadline:
  closes 2027-01-04  2026-22309  Notice of Request for Revision to and Extension of Approval of an Information Collection;
  closes 2027-01-04  2026-22438  Notice of Request for an Extension of a Currently Approved Information Collection
  closes 2027-01-04  2026-22442  Notice of Request for an Extension of a Currently Approved Information Collection
  closes 2027-01-04  2026-22445  Notice of Request for Approval of an Existing Collection for Borlaug Fellowship Program OM
  closes 2027-01-04  2026-22467  Assessment Exemption for Organic Commodities Under Federal Marketing Orders; Notice of Req
  closes 2027-01-05  2026-22679  Special Supplemental Nutrition Program for Women, Infants, and Children (WIC): Online Orde

already listed with a later date: 3 [('2026-11-09', 'Proposed Rule', 'Pecans Grown in the States of Alabama, Arkansas, Arizona, Ca'), ('2026-11-09', 'Notice', 'Pioneer Hi-Bred International, Inc.: Availability of a Petit'), ('2026-11-09', 'Rule', 'Single Family Housing Guaranteed Loan Program-Limited Party ')]

slug 'usda': HTTP 400 {"errors":{"agencies":"invalid value"}}
```

## URL patterns (all observed)

| URL | What |
|---|---|
| `/api/v1/documents.json?conditions[agencies][]=<slug>&conditions[publication_date][gte]=YYYY-MM-DD&conditions[publication_date][lte]=YYYY-MM-DD&order=newest&per_page=N&fields[]=...` | the week's documents; repeat `conditions[agencies][]` for several agencies (OR: with `gte=2026-11-02` only, EPA 18 + APHIS 2 = 20) |
| `/api/v1/documents/facets/type?conditions[...]` | counts by type: `{"NOTICE":{"count":6,"name":"Notice"},"PRORULE":{...},"RULE":{...}}` (EPA, 2026-11-02..08) |
| `/api/v1/agencies`, `/api/v1/agencies/<slug>` | agency list / one agency (`child_slugs`, `parent_id`, `url`) |
| `/api/v1/documentation.json` | the OpenAPI spec behind the interactive docs page (parameter and field enums, agency slug enum) |
| `/documents/YYYY/MM/DD/<document_number>/<title-slug>` | `html_url`, the document page for people: link to it, do not script it (read the document's fields from the API) |

## Fields

| Field | Notes |
|---|---|
| `document_number` | `2026-22788`; the stable ID |
| `publication_date` | `YYYY-MM-DD`; issues are weekdays only (EPA had none on 2026-11-04) |
| `type` | `Rule`, `Proposed Rule`, `Notice` seen; filter codes `RULE`, `PRORULE`, `NOTICE`, `PRESDOCU` in `conditions[type][]` |
| `action` | free text, e.g. `Final rule.`, `Correcting amendment.`; can be `null` |
| `agencies[]` | `{name, slug, id, url, json_url, parent_id, raw_name}`; parent and sub-agency both listed |
| `comments_close_on`, `effective_on` | `YYYY-MM-DD` or `null` |
| `docket_ids[]`, `regulation_id_numbers[]` | `EPA-HQ-OAR-2002-0037`, RIN `2060-AR73`; docket strings are as printed (`FRL- 13687-01-AO`) |
| `html_url`, `pdf_url` | document page; PDF on www.govinfo.gov (`/content/pkg/FR-2026-11-02/pdf/2026-22309.pdf`) |
| `count`, `total_pages`, `next_page_url`, `description` | top level; `results` is absent when `count` is 0 |

## Gotchas

- **Next issue leaks into "this week".** Documents for the next publication date are listed before that date (Monday 2026-11-09 documents on Sunday 2026-11-08). Always pass `conditions[publication_date][lte]`.
- **Short names repeat.** `DOE` = Energy Department and Energy Efficiency and Renewable Energy Office, `DOL`, `FS` (Fiscal Service, Forest Service): 10 repeated short names; 53 of 473 agencies have no short name. Block 1 refuses an ambiguous match.
- **`count` tops out at 10000.** `gte=2026-01-01` said 10000 while Oct 1 - Nov 8 alone was 2577. Narrow dates before trusting a count.
- **Loose date parsing:** `gte=11/02/2026` returned the same 18 as `2026-11-02`. Send ISO dates anyway.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; block 1 reads only the origin.

## What does not work

- **`/documents/search` (and `/articles/search`, `/documents/current`)**: disallowed in robots.txt. Not used.
- **HTML pages for data**: over plain HTTP they redirect to `unblock.federalregister.gov` "Request Access" (a CAPTCHA), which says programmatic access is limited to the API. Do not solve it or work around it; use the API.
- **Not tested:** public inspection endpoints, `per_page` above 1000 with more than 1000 results, rate limits (none documented, none hit).
