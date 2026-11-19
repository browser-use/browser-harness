# NYC Open Data (data.cityofnewyork.us) - Get a NYC Restaurant's Latest Health Inspection Score, Grade and Violations by Name or Address, or the Latest 311 Complaints for a ZIP Code (SODA API, no key)

Field-tested against data.cityofnewyork.us on 2026-11-18 (US Eastern evening; 23:27-23:37 UTC) using a fresh Browser Use cloud browser (logged out; one session, 23:30-23:34 UTC) plus Python `urllib` and `curl` from a Linux machine. 16 browser page loads (an API JSON page, robots.txt, the NYC Open Data FAQ, the NYC.gov Terms of Use, the Socrata app-token doc, the DOHMH restaurant grades page and the ABCEats FAQ; block 2 ran twice) and 34 in-page `fetch()` calls, plus 28 curl calls and 10 urllib calls (2 of them robots.txt) to data.cityofnewyork.us, all serial at 1 s or more spacing: every API call was HTTP 200 except the deliberate HTTP 400 and 404 probes below. Most answers took 0.1-4.5 s; counting the not-yet-inspected rows took 10.8 s, the 311 metadata (`/api/views/erm2-nwe9.json`) 9.6 s, an unknown dataset id 6.0 s and a 60,000-row answer 17.6 s. No 429, no challenge, no key, no login. After code review on 2026-11-19, blocks 1 and 3 were re-run at 00:16 UTC (block 1 in a new cloud browser, block 3 locally) with PARTIAL notes for answers that hit their `$limit`, A/B/C as the only letter grades, a closed 7-day window and a NaN-safe `Retry-After`: same output except the times. After a second review the same day, block 1 was re-run at 01:14 UTC in a new cloud browser with a full 7 x 24 h 311 window ending at the newest request (it started at midnight 6 days before, so about 6 days and a half): only the window line and its counts changed; block 1 shows that output.

robots.txt (checked 2026-11-18 in the cloud browser, block 2, and with Python, block 3): https://data.cityofnewyork.us/robots.txt has one `User-agent: *` group with `Crawl-delay: 1` and 54 `Disallow` lines: catalog search URLs with filters (`/browse?*&q=`, `/catalog/*?*&tags=` and the like), `*/alt$`, `*/edit$`, `/*/*/*/widget_preview`, `/OData.svc/`, `/api/odata/`, `/browse/embed`, `/login`, `/reset_password/`, `/tiles/`, `/views/INLINE/rows.json?*method=clustered2*` and `/api/collocate*`. No rule touches `/resource/`, and there are no groups for GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot or Bytespider, so the `*` rules apply to them: `/resource/43nn-pn8j.json` and `/resource/erm2-nwe9.json` are allowed for all 11 agents, OData for none (block 3). The blocks never use OData and wait 1 s between calls. Terms: the NYC Open Data FAQ (https://www.nyc.gov/opendata/get-started/FAQs) says "Are there restrictions on how I can use Open Data? Open Data belongs to all New Yorkers. There are no restrictions on the use of Open Data." The NYC.gov Terms of Use (https://www.nyc.gov/main/terms-of-use) say "You agree to access and use NYC.gov only for lawful purposes", ask you not to "disrupt NYC.gov or its servers or networks in any way", and say "Service marks and trademarks contained in or displayed on NYC.gov ... are the property of their respective owners (which may be the City)"; the footer of the FAQ page says "NYC is a trademark and service mark of the City of New York." The Socrata app-token doc (https://dev.socrata.com/docs/app-tokens.html; the portal runs on Socrata, and its answers carry `X-Socrata-Region`) says "requests that aren’t using an application token come from a shared pool via IP address", "IP addresses that make too many requests during a given period may be subject to throttling" and "If you are throttled for any reason, you will receive a status code 429 response". No AI/ML, scraping, automated-access or non-commercial clause on any of these pages (block 2). Naming: this skill says "NYC Open Data" in plain text, uses no NYC logo or City seal, and is not affiliated with or endorsed by the City of New York, DOHMH or 311.

**Read the grade with the inspection type.** The data is the City's record, not a verdict: show the inspection date and type with every score and grade, and link the dataset. A score of 0 from a non-graded inspection (Katz's on 2026-09-30) is not a fresh "A".

## Quick summary

- **No scraping.** `GET https://data.cityofnewyork.us/resource/43nn-pn8j.json?$where=upper(dba) like '%KATZ%S%DELI%'&$order=inspection_date DESC` (URL-encode it) returns DOHMH restaurant inspection rows; `GET https://data.cityofnewyork.us/resource/erm2-nwe9.json?$where=incident_zip='10001'&$order=created_date DESC&$limit=5` returns the newest 311 service requests for a ZIP. SoQL parameters: `$select`, `$where`, `$group`, `$order`, `$limit`, `$q`. JSON, or CSV with `.csv`. No key.
- **Answer (block 1, 23:32 UTC):** **Katz's Delicatessen, camis 40732665, 205 East Houston Street, Manhattan 10002.** Latest inspection **2026-09-30, "Inter-Agency Task Force / Initial Inspection", score 0, no violations, no grade.** Latest letter grade in the data: **A, 2025-02-25 (score 12).** Latest cycle inspection: **2026-07-13, score 20 (the B range), 7 violations, 3 critical (04H, 04K "Evidence of rats or live rats", 04N "Filth flies"), no grade recorded.** A second "KATZ'S DELICATESSEN" is camis 50062888 at 445 Gold Street, Brooklyn 11201. **ZIP 10001, 311:** newest request **2026-11-17 00:30 (NYC time), #71146891, DOT, Sidewalk Condition / Cellar Door Open/Unprotected**; in the 7 x 24 h to it (block 1 re-run at 01:14 UTC) the top types were Illegal Parking 53, Encampment 49, Noise - Residential 20.
- **One row per violation.** An inspection with 7 violations is 7 rows with the same date, type, score and grade; an inspection with none is 1 row with `action` "No violations were recorded at the time of this inspection." The blocks group rows by `(inspection_date, inspection_type)`: Katz's 20 rows are 8 inspections, two of them on 2026-07-13 (Cycle and Administrative Miscellaneous).
- **Latest is not graded.** `grade` was blank on 150,520 of 295,247 rows (23:28 UTC). DOHMH's ABCEats FAQ: "A" is 0 to 13 points, "B" 14 to 27, "C" 28 or more, and "Grade Pending" means "on both the initial inspection and reinspection, the restaurant received 14 or more points". The blocks print the latest inspection, the latest one with a grade, and the latest cycle inspection with its violations.
- **Every value is a string** (`"score":"20"`) and **missing columns are left out** of the row, not sent as null (`grade`, `score`, `violation_code`, `descriptor` all go missing). Use `.get()`.
- **Rate limit:** `Crawl-delay: 1`; without an app token requests share a per-IP pool and get HTTP 429 when throttled (Socrata doc, no number given). All blocks call 1 s apart, serial; blocks 1 and 3 wait `Retry-After` (seconds or an HTTP date; default 60 s) once on 429/5xx and stop when it asks for more than 120 s. No rate-limit headers were sent.

## What works

### 1. Restaurant name -> latest inspection, latest grade, latest cycle violations; ZIP -> newest 311 requests (browser)

`on_site_tab()` opens one logged-out `/resource/` JSON answer so `fetch()` is same-origin (the API also sends `Access-Control-Allow-Origin: *`). `soql()` returns the JSON rows on HTTP 200, waits once on 429/500/502/503/504 and otherwise raises with the server's `errorCode`. `find()` matches every name word in order inside `upper(dba)`; with more than one CAMIS it shows all and reports the most recently inspected. 8 `fetch()` calls.

```python
import json, re, time, urllib.parse
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

RESTAURANTS = [("Katz's Deli", "10002"), ("Katz's Deli", None), ("Peter Luger", None)]  # (name words, ZIP or None)
ZIP_311 = "10001"
SHOW_311 = 5

SITE = "https://data.cityofnewyork.us"
INSPECTIONS = SITE + "/resource/43nn-pn8j.json"  # DOHMH New York City Restaurant Inspection Results
REQUESTS_311 = SITE + "/resource/erm2-nwe9.json"  # 311 Service Requests from 2020 to Present
PAUSE = 1.0  # robots.txt 'Crawl-delay: 1' for '*'
GRADES = {"A": "Grade A", "B": "Grade B", "C": "Grade C", "N": "Not Yet Graded", "Z": "Grade Pending",
          "P": "Grade Pending issued on re-opening following an initial inspection that resulted in a closure"}

def on_site_tab():
    """fetch() runs from a logged-out data.cityofnewyork.us /resource/ page (the API also sends CORS '*')."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(INSPECTIONS + "?$limit=1&$select=camis")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"camis"' not in body:
        raise RuntimeError(f"data.cityofnewyork.us did not serve the SODA API (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
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
    """One in-page GET -> {status, headers, text}."""
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{url}: no answer after 90s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def soql(resource, **params):
    """SoQL GET -> list of row dicts (every value a string; absent columns left out). Waits Retry-After once on
    429/500/502/503/504 or a network error; raises on any other status with the server's errorCode and message."""
    url = resource + "?" + urllib.parse.urlencode({"$" + k: v for k, v in params.items()})
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(retry_after(r["headers"].get("retry-after")))
            continue
        break
    if r["status"] != 200:
        try:
            e = json.loads(r["text"])
            msg = f"{e.get('errorCode') or e.get('code')}: {e.get('message', '')[:160]}"
        except ValueError:
            msg = " ".join(r["text"].split())[:200]
        raise RuntimeError(f"HTTP {r['status']} {url}: {msg}")
    rows = json.loads(r["text"])
    if not isinstance(rows, list):
        raise RuntimeError(f"{url}: expected a JSON array, got {r['text'][:200]!r}")
    return rows

def lit(s):
    """A SoQL string literal: single quotes doubled."""
    return "'" + s.replace("'", "''") + "'"

def find(name, zipcode=None):
    """Name words -> restaurants (one per CAMIS), most recently inspected first. dba is stored in upper case, so
    every word is matched in order inside upper(dba): "Katz's Deli" -> upper(dba) like '%KATZ%S%DELI%'."""
    words = re.findall(r"[A-Z0-9]+", name.upper())
    where = f"upper(dba) like {lit('%' + '%'.join(words) + '%')}"
    if zipcode:
        where += f" AND zipcode={lit(zipcode)}"
    cols = "camis,dba,building,street,zipcode,boro,cuisine_description"
    return soql(INSPECTIONS, select=cols + ",max(inspection_date) as last", where=where, group=cols,
                order="last DESC", limit=20)

def inspections(camis):
    """All rows for one CAMIS -> inspections, newest first. The data has one row per violation, so rows are grouped by
    (inspection_date, inspection_type); the 1900-01-01 placeholder (not yet inspected) is dropped."""
    rows = soql(INSPECTIONS, where=f"camis={lit(camis)}", order="inspection_date DESC, violation_code", limit=1000)
    out = OrderedDict()
    for r in rows:
        day = r.get("inspection_date", "")[:10]
        if day == "1900-01-01":
            continue
        i = out.setdefault((day, r.get("inspection_type", "?")), dict(
            date=day, type=r.get("inspection_type", "?"), action=r.get("action", ""), score=r.get("score"),
            grade=r.get("grade"), grade_date=r.get("grade_date", "")[:10], violations=[]))
        if r.get("violation_code"):
            i["violations"].append((r["violation_code"], r.get("critical_flag", ""), r.get("violation_description", "")))
    return rows, list(out.values())

def band(score):
    """The DOHMH point cut-offs: A 0-13, B 14-27, C 28 or more."""
    s = int(score)
    return "A range (0-13)" if s <= 13 else "B range (14-27)" if s <= 27 else "C range (28+)"

def describe(i):
    s = f"{i['date']} {i['type']}: "
    s += f"score {i['score']}" if i["score"] is not None else "no score"
    s += f", grade {i['grade']} ({GRADES.get(i['grade'], '?')}, grade date {i['grade_date'] or '-'})" if i["grade"] else ", no grade"
    crit = sum(1 for v in i["violations"] if v[1] == "Critical")
    s += f", {len(i['violations'])} violations ({crit} critical)" if i["violations"] else f", {i['action'][:60]}"
    return s

on_site_tab()
now = datetime.now(timezone.utc)
print(f"NYC Open Data (data.cityofnewyork.us), queried {now:%Y-%m-%d %H:%M} UTC")
for name, z in RESTAURANTS:
    print(f"\n=== {name!r}" + (f" in ZIP {z}" if z else ""))
    found = find(name, z)
    if not found:
        print("  no restaurant matches: try fewer or other words")
        continue
    for f in found:
        print(f"  camis {f['camis']} {f['dba']}, {f.get('building', '')} {f.get('street', '')}, {f.get('boro', '')} "
              f"{f.get('zipcode', '')}; {f.get('cuisine_description', '-')}; last inspected {f['last'][:10]}")
    pick = found[0]
    if len(found) > 1:
        more = " or more" if len(found) == 20 else ""  # find() asks for at most 20
        print(f"  {len(found)}{more} matches: showing the most recently inspected (add a ZIP to choose)")
    rows, insp = inspections(pick["camis"])
    print(f"  {pick['dba']} (camis {pick['camis']}): {len(rows)} rows, {len(insp)} inspections in the data"
          + (" (PARTIAL: hit the 1,000-row $limit, page with $offset for older rows)" if len(rows) == 1000 else ""))
    if not insp:
        print("  not yet inspected")
        continue
    print(f"  latest inspection:       {describe(insp[0])}")
    graded = next((i for i in insp if i["grade"] in ("A", "B", "C")), None)  # N, Z, P are not letter grades
    print(f"  latest graded:           {describe(graded) if graded else 'no A, B or C in the data'}")
    cycle = next((i for i in insp if i["type"].startswith("Cycle Inspection") and i["score"] is not None), None)
    if cycle:
        print(f"  latest cycle inspection: {describe(cycle)}; score is in the {band(cycle['score'])}")
        for code, flag, desc in cycle["violations"]:
            print(f"    {code:<6} {flag:<12} {desc[:100]}" + ("..." if len(desc) > 100 else ""))

print(f"\n=== latest 311 service requests for ZIP {ZIP_311}")
reqs = soql(REQUESTS_311, select="unique_key,created_date,status,agency,complaint_type,descriptor,street_name",
            where=f"incident_zip={lit(ZIP_311)}", order="created_date DESC, unique_key DESC", limit=SHOW_311)
for q in reqs:
    print(f"  {q['created_date'][:16].replace('T', ' ')}  #{q['unique_key']} {q['agency']:<6} {q['complaint_type']}"
          f" / {q.get('descriptor', '-')} ({q.get('street_name', 'no street')}; {q.get('status', '?')})")
if reqs:
    newest = datetime.fromisoformat(reqs[0]["created_date"][:19])
    since = newest - timedelta(days=7)  # a full 7 x 24 h window ending at the newest request
    top = soql(REQUESTS_311, select="complaint_type,count(*) as n", group="complaint_type", order="n DESC", limit=5,
               where=f"incident_zip={lit(ZIP_311)} AND created_date > {lit(since.strftime('%Y-%m-%dT%H:%M:%S'))}"
                     f" AND created_date <= {lit(reqs[0]['created_date'][:19])}")
    print(f"  top complaint types, {since:%Y-%m-%d %H:%M} to {newest:%Y-%m-%d %H:%M} (7 x 24 h to the newest request, NYC local time):")
    print("    " + "; ".join(f"{t['complaint_type']} {t['n']}" for t in top))

print(f"\nSource: NYC Open Data, datasets 43nn-pn8j (DOHMH) and erm2-nwe9 (311), {SITE}, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the re-run on 2026-11-19, 01:14 UTC):

```text
NYC Open Data (data.cityofnewyork.us), queried 2026-11-19 01:14 UTC

=== "Katz's Deli" in ZIP 10002
  camis 40732665 KATZ'S DELICATESSEN, 205 EAST HOUSTON STREET, Manhattan 10002; Sandwiches; last inspected 2026-09-30
  KATZ'S DELICATESSEN (camis 40732665): 20 rows, 8 inspections in the data
  latest inspection:       2026-09-30 Inter-Agency Task Force / Initial Inspection: score 0, no grade, No violations were recorded at the time of this inspection.
  latest graded:           2025-02-25 Cycle Inspection / Initial Inspection: score 12, grade A (Grade A, grade date 2025-02-25), 2 violations (1 critical)
  latest cycle inspection: 2026-07-13 Cycle Inspection / Initial Inspection: score 20, no grade, 7 violations (3 critical); score is in the B range (14-27)
    04H    Critical     Raw, cooked or prepared food is adulterated, contaminated, cross-contaminated, or not discarded in a...
    04K    Critical     Evidence of rats or live rats in establishment's food or non-food areas.
    04N    Critical     Filth flies or food/refuse/sewage associated with (FRSA) flies or other nuisance pests in establishm...
    08A    Not Critical Establishment is not free of harborage or conditions conducive to rodents, insects or other pests.
    10B    Not Critical Anti-siphonage or back-flow prevention device not provided where required; equipment or floor not pr...
    10F    Not Critical Non-food contact surface or equipment made of unacceptable material, not kept clean, or not properly...
    28-05  Not Critical Food adulterated or misbranded. Adulterated or misbranded food possessed, being manufactured, produc...

=== "Katz's Deli"
  camis 40732665 KATZ'S DELICATESSEN, 205 EAST HOUSTON STREET, Manhattan 10002; Sandwiches; last inspected 2026-09-30
  camis 50062888 KATZ'S DELICATESSEN, 445 GOLD STREET, Brooklyn 11201; American; last inspected 2025-06-11
  2 matches: showing the most recently inspected (add a ZIP to choose)
  KATZ'S DELICATESSEN (camis 40732665): 20 rows, 8 inspections in the data
  latest inspection:       2026-09-30 Inter-Agency Task Force / Initial Inspection: score 0, no grade, No violations were recorded at the time of this inspection.
  latest graded:           2025-02-25 Cycle Inspection / Initial Inspection: score 12, grade A (Grade A, grade date 2025-02-25), 2 violations (1 critical)
  latest cycle inspection: 2026-07-13 Cycle Inspection / Initial Inspection: score 20, no grade, 7 violations (3 critical); score is in the B range (14-27)
    04H    Critical     Raw, cooked or prepared food is adulterated, contaminated, cross-contaminated, or not discarded in a...
    04K    Critical     Evidence of rats or live rats in establishment's food or non-food areas.
    04N    Critical     Filth flies or food/refuse/sewage associated with (FRSA) flies or other nuisance pests in establishm...
    08A    Not Critical Establishment is not free of harborage or conditions conducive to rodents, insects or other pests.
    10B    Not Critical Anti-siphonage or back-flow prevention device not provided where required; equipment or floor not pr...
    10F    Not Critical Non-food contact surface or equipment made of unacceptable material, not kept clean, or not properly...
    28-05  Not Critical Food adulterated or misbranded. Adulterated or misbranded food possessed, being manufactured, produc...

=== 'Peter Luger'
  camis 40364335 PETER LUGER STEAKHOUSE, 178 BROADWAY, Brooklyn 11211; Steakhouse; last inspected 2026-04-06
  PETER LUGER STEAKHOUSE (camis 40364335): 4 rows, 2 inspections in the data
  latest inspection:       2026-04-06 Cycle Inspection / Initial Inspection: score 13, grade A (Grade A, grade date 2026-04-06), 2 violations (2 critical)
  latest graded:           2026-04-06 Cycle Inspection / Initial Inspection: score 13, grade A (Grade A, grade date 2026-04-06), 2 violations (2 critical)
  latest cycle inspection: 2026-04-06 Cycle Inspection / Initial Inspection: score 13, grade A (Grade A, grade date 2026-04-06), 2 violations (2 critical); score is in the A range (0-13)
    02G    Critical     Cold TCS food item held above 41 °F; smoked or processed fish held above 38 °F; intact raw eggs held...
    06D    Critical     Food contact surface not properly washed, rinsed and sanitized after each use and following any acti...

=== latest 311 service requests for ZIP 10001
  2026-11-17 00:30  #71146891 DOT    Sidewalk Condition / Cellar Door Open/Unprotected (WEST 26 STREET; In Progress)
  2026-11-17 00:23  #71143659 TLC    Taxi Compliment / Driver Compliment (MADISON SQUARE GARDEN; In Progress)
  2026-11-16 23:03  #71152197 DOT    Street Condition / Plate Condition - Noisy (AVENUE OF THE AMERICAS; In Progress)
  2026-11-16 22:57  #71150415 DOT    Street Condition / Plate Condition - Noisy (6 AVENUE; In Progress)
  2026-11-16 22:28  #71141788 DOHMH  Food Establishment / Food Contaminated (BROADWAY; In Progress)
  top complaint types, 2026-11-10 00:30 to 2026-11-17 00:30 (7 x 24 h to the newest request, NYC local time):
    Illegal Parking 53; Encampment 49; Noise - Residential 20; Water Maintenance 17; Noise 16

Source: NYC Open Data, datasets 43nn-pn8j (DOHMH) and erm2-nwe9 (311), https://data.cityofnewyork.us, accessed 19 November 2026 01:14 UTC.
```

### 2. robots.txt, the terms pages, the grade cut-offs and query mistakes (browser)

5 page loads, 1 return to the API page and 13 in-page `fetch()` calls in the same tab. The FAQ answers sit in collapsed accordions, so the checks read `textContent` (the first run used `innerText` and reported the "no restrictions" sentence MISSING).

```python
import json, time

SITE = "https://data.cityofnewyork.us"
R = SITE + "/resource/43nn-pn8j.json"
S = SITE + "/resource/erm2-nwe9.json"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__u[id] = {status: r.status, text: await r.text(),
      h: ['content-type', 'access-control-allow-origin', 'x-soda2-types', 'last-modified', 'retry-after']
         .map(k => k + '=' + (r.headers.get(k) || '-')).join(' | ')}; })
    .catch(e => { window.__u[id] = {status: 0, text: String(e), h: ''}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(url):
    """One in-page GET -> status, body, a few headers. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{url}: no answer after 90s")
        time.sleep(0.2)
    r["secs"] = time.time() - t0
    time.sleep(1.0)  # robots.txt Crawl-delay: 1
    return r

def brief(r):
    try:
        b = json.loads(r["text"])
    except ValueError:
        return f"HTTP {r['status']} not JSON: {' '.join(r['text'].split())[:90]!r}"
    if isinstance(b, list):
        return f"HTTP {r['status']} {len(b)} rows, first {json.dumps(b[0])[:110] if b else '-'}"
    return f"HTTP {r['status']} {b.get('errorCode') or b.get('code')}: {' '.join(str(b.get('message')).split())[:90]!r}"

def page(url):
    goto_url(url)
    wait_for_load()
    time.sleep(2)  # the ABCEats FAQ renders client-side
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    # textContent, not innerText: the FAQ answers sit in collapsed accordions, which innerText leaves out
    return st, js("document.body ? document.body.textContent : (document.documentElement.textContent || '')") or ""

st, txt = page(SITE + "/robots.txt")  # plain text: textContent keeps its line breaks
lines = [l.strip() for l in txt.splitlines() if l.strip()]
print(f"robots.txt HTTP {st}: {len(lines)} lines; user-agent lines {[l for l in lines if l.lower().startswith('user-agent')]}; "
      f"{[l for l in lines if l.lower().startswith('crawl-delay')]}")
dis = [l.split(':', 1)[1].strip() for l in lines if l.lower().startswith('disallow')]
print(f"  {len(dis)} Disallow lines; not about browse/catalog/facet/page filters: {[d for d in dis if not any(x in d for x in ('browse', 'catalog', 'facet', '/page/'))]}")
print(f"  any rule starting /resource: {[d for d in dis if d.startswith('/resource')]}")

for url, needles in (
    ("https://www.nyc.gov/opendata/get-started/FAQs",
     ["There are no restrictions on the use of Open Data", "NYC is a trademark and service mark of the City of New York"]),
    ("https://www.nyc.gov/main/terms-of-use",
     ["only for lawful purposes", "disrupt NYC.gov or its servers or networks in any way", "Service marks and trademarks contained in or displayed on NYC.gov"]),
    ("https://dev.socrata.com/docs/app-tokens.html",
     ["requests that aren’t using an application token come from a shared pool via IP address",
      "IP addresses that make too many requests during a given period may be subject to throttling",
      "you will receive a status code 429 response"]),
    ("https://a816-health.nyc.gov/ABCEatsRestaurants/#!/faq",
     ['"A" grade: 0 to 13 points', '"B" grade: 14 to 27 points', '"C" grade: 28 or more points',
      "on both the initial inspection and reinspection, the restaurant received 14 or more points"]),
):
    st, txt = page(url)
    flat = " ".join(txt.split())
    words = [w for w in ("artificial intelligence", "machine learning", "scrap", "crawl", "automated", "robot", "non-commercial", "noncommercial")
             if w in flat.lower()]
    print(f"\n{url}\n  HTTP {st}; AI/scraping/automated/commercial words present: {words}")
    for n in needles:
        print(f"  {'found' if n in flat else 'MISSING'} {n!r}")

page(R + "?$limit=1&$select=camis")  # back to an API page
print()
for label, url in (
    ("name, dba stored upper case     ", R + "?$select=camis,dba&$where=dba like '%25katz%25'"),
    ("same, upper(dba)                ", R + "?$select=camis,dba&$where=upper(dba) like '%25KATZ%25DELI%25'&$limit=2"),
    ("apostrophe doubled ''           ", R + "?$select=camis,zipcode&$where=dba='KATZ''S DELICATESSEN'&$limit=2"),
    ("apostrophe not escaped          ", R + "?$where=dba='KATZ'S DELICATESSEN'"),
    ("simple filter ?camis=           ", R + "?camis=40732665&$select=inspection_date,score,grade&$order=inspection_date DESC&$limit=3"),
    ("$q full text (rows, not places) ", R + "?$q=katz&$select=camis,dba,violation_code&$limit=3"),
    ("no $limit                       ", R + "?$select=camis"),
    ("unknown column                  ", R + "?$where=restaurant_name='X'"),
    ("not-yet-inspected placeholder   ", R + "?$select=camis,dba,inspection_date&$where=camis='50118533'"),
    ("311 incident_zip as a number    ", S + "?$where=incident_zip=10001&$limit=1"),
    ("311 newest in 10001             ", S + "?$select=created_date,complaint_type&$where=incident_zip='10001'&$order=created_date DESC&$limit=1"),
    ("unknown dataset id              ", SITE + "/resource/xxxx-xxxx.json"),
):
    r = raw(url)
    print(f"{label} {brief(r)} ({r['secs']:.1f} s)")
r = raw(R + "?camis=40732665&$select=camis,score&$limit=1")
print(f"\nheaders: {r['h']}")
```

Output (from the run on 2026-11-18, 23:33 UTC):

```text
robots.txt HTTP 200: 57 lines; user-agent lines ['User-agent: *']; ['Crawl-delay: 1']
  54 Disallow lines; not about browse/catalog/facet/page filters: ['*/alt$', '*/alt?', '*/edit$', '/*/*/*/widget_preview', '/OData.svc/', '/api/odata/', '/login', '/reset_password/', '/tiles/', '/views/INLINE/rows.json?*method=clustered2*', '/api/collocate*']
  any rule starting /resource: []

https://www.nyc.gov/opendata/get-started/FAQs
  HTTP 200; AI/scraping/automated/commercial words present: []
  found 'There are no restrictions on the use of Open Data'
  found 'NYC is a trademark and service mark of the City of New York'

https://www.nyc.gov/main/terms-of-use
  HTTP 200; AI/scraping/automated/commercial words present: []
  found 'only for lawful purposes'
  found 'disrupt NYC.gov or its servers or networks in any way'
  found 'Service marks and trademarks contained in or displayed on NYC.gov'

https://dev.socrata.com/docs/app-tokens.html
  HTTP 200; AI/scraping/automated/commercial words present: []
  found 'requests that aren’t using an application token come from a shared pool via IP address'
  found 'IP addresses that make too many requests during a given period may be subject to throttling'
  found 'you will receive a status code 429 response'

https://a816-health.nyc.gov/ABCEatsRestaurants/#!/faq
  HTTP 200; AI/scraping/automated/commercial words present: []
  found '"A" grade: 0 to 13 points'
  found '"B" grade: 14 to 27 points'
  found '"C" grade: 28 or more points'
  found 'on both the initial inspection and reinspection, the restaurant received 14 or more points'

name, dba stored upper case      HTTP 200 0 rows, first - (0.1 s)
same, upper(dba)                 HTTP 200 2 rows, first {"camis": "40732665", "dba": "KATZ'S DELICATESSEN"} (0.1 s)
apostrophe doubled ''            HTTP 200 2 rows, first {"camis": "40732665", "zipcode": "10002"} (0.1 s)
apostrophe not escaped           HTTP 400 query.compiler.malformed: 'Could not parse SoQL query "select * where dba=\'KATZ\'S DELICATESSEN\'" at line 1 character ' (0.3 s)
simple filter ?camis=            HTTP 200 3 rows, first {"inspection_date": "2026-09-30T00:00:00.000", "score": "0"} (0.1 s)
$q full text (rows, not places)  HTTP 200 3 rows, first {"camis": "40732665", "dba": "KATZ'S DELICATESSEN", "violation_code": "04K"} (0.1 s)
no $limit                        HTTP 200 1000 rows, first {"camis": "50116199"} (0.1 s)
unknown column                   HTTP 400 query.soql.no-such-column: 'Query coordinator error: query.soql.no-such-column; No such column: restaurant_name; posit' (0.3 s)
not-yet-inspected placeholder    HTTP 200 1 rows, first {"camis": "50118533", "dba": "JEFFREY KATZ", "inspection_date": "1900-01-01T00:00:00.000"} (0.1 s)
311 incident_zip as a number     HTTP 400 query.soql.type-mismatch: 'Query coordinator error: query.soql.type-mismatch; Type mismatch for op$=, is number; posi' (0.3 s)
311 newest in 10001              HTTP 200 1 rows, first {"created_date": "2026-11-17T00:30:36.000", "complaint_type": "Sidewalk Condition"} (0.1 s)
unknown dataset id               HTTP 404 dataset.missing: 'Not found' (0.3 s)

headers: content-type=application/json;charset=utf-8 | access-control-allow-origin=* | x-soda2-types=["text","number"] | last-modified=Wed, 18 Nov 2026 23:15:47 GMT | retry-after=-
```

### 3. By address with Python urllib, 311 for two ZIPs, robots check for every agent (no browser)

Sends a descriptive User-Agent (curl's default also got HTTP 200). The robots check is an RFC 9309 parser: Python's `urllib.robotparser` ends the `*` group at the blank line after `Crawl-delay: 1`, drops all 54 `Disallow` lines and so calls `/OData.svc/` allowed. The address match puts each word in order inside `upper(street)`, so "E Houston St" finds "EAST HOUSTON STREET"; the building number and ZIP must match exactly. 1 robots.txt call and 4 API calls.

```python
import json, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

ADDRESSES = [("205 E Houston St", "10002"), ("178 Broadway", "11211")]  # (building + street, ZIP)
ZIPS_311 = ["10001", "11211"]

SITE = "https://data.cityofnewyork.us"
INSPECTIONS = SITE + "/resource/43nn-pn8j.json"
REQUESTS_311 = SITE + "/resource/erm2-nwe9.json"
UA = "nyc-open-data-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
calls = 0

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

def rules_for(txt, agent):
    """RFC 9309 groups: every group naming the agent (merged), else every '*' group (merged). -> [(allow, path)].
    Blank lines do not end a group (Python's urllib.robotparser ends it there and loses every Disallow on this site)."""
    groups, cur, in_ua = [], None, False
    for raw in txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            if not in_ua:
                cur = ([], [])
                groups.append(cur)
            cur[0].append(v.lower())
            in_ua = True
        elif k in ("allow", "disallow") and cur is not None:
            in_ua = False
            if v:
                cur[1].append((k == "allow", v))
        else:
            in_ua = False
    named = [g for g in groups if agent.lower() in g[0]] if agent != "*" else []
    return [r for g in (named or [g for g in groups if "*" in g[0]]) for r in g[1]]

def allowed(rules, path):
    """Longest matching rule wins, Allow wins a tie; '*' and '$' as in RFC 9309."""
    best = (-1, True)
    for ok, pat in rules:
        rx = "".join(".*" if c == "*" else ("$" if c == "$" and i == len(pat) - 1 else re.escape(c)) for i, c in enumerate(pat))
        if re.match(rx, path) and (len(pat) > best[0] or (len(pat) == best[0] and ok)):
            best = (len(pat), ok)
    return best[1]

# robots.txt: one '*' group with Crawl-delay 1; /resource/ must stay allowed for every agent, OData is disallowed.
with urllib.request.urlopen(urllib.request.Request(SITE + "/robots.txt", headers={"User-Agent": UA}), timeout=30) as r:
    robots = r.read().decode("utf-8", "replace")
    print(f"robots.txt HTTP {r.status}, {len(robots.splitlines())} lines")
for path in ("/resource/43nn-pn8j.json", "/resource/erm2-nwe9.json", "/OData.svc/", "/api/odata/v4/43nn-pn8j"):
    ok = [a for a in AGENTS if allowed(rules_for(robots, a), path)]
    print(f"  robots {path:<26} allowed for {len(ok)}/{len(AGENTS)} agents")
    if path.startswith("/resource/") and len(ok) != len(AGENTS):
        sys.exit("robots.txt now disallows a path this skill uses: stop")
py = urllib.robotparser.RobotFileParser()
py.parse(robots.splitlines())
print(f"  (urllib.robotparser says /OData.svc/ is {'allowed' if py.can_fetch('*', SITE + '/OData.svc/') else 'disallowed'}: "
      f"it ends the '*' group at the blank line after Crawl-delay)")
delay = [l.split(":", 1)[1].strip() for l in robots.splitlines() if l.lower().startswith("crawl-delay")]
PAUSE = max(1.0, float(delay[0]) if delay else 1.0)
print(f"  Crawl-delay {delay} -> {PAUSE:.0f} s between calls")

def soql(resource, **params):
    """SoQL GET -> list of row dicts (strings only; absent columns left out). Once waits Retry-After (default 60 s)
    on 429/500/502/503/504 or a network error; exits on anything else with the server's errorCode and message."""
    global calls
    url = resource + "?" + urllib.parse.urlencode({"$" + k: v for k, v in params.items()})
    for attempt in range(2):
        time.sleep(PAUSE)
        calls += 1
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=90) as r:
                rows = json.loads(r.read())
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(retry_after(e.headers.get("Retry-After")))
                continue
            body = e.read().decode(errors="replace")
            try:
                j = json.loads(body)
                body = f"{j.get('errorCode') or j.get('code')}: {j.get('message', '')[:160]}"
            except ValueError:
                pass
            sys.exit(f"HTTP {e.code} {url}: {' '.join(body.split())[:240]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url}: {e}")
    if not isinstance(rows, list):
        sys.exit(f"{url}: expected a JSON array")
    return rows

def lit(s):
    return "'" + s.replace("'", "''") + "'"

def like(words):
    """'205 E Houston St' words -> '%E%HOUSTON%ST%': each word in order, so 'E' matches 'EAST', 'ST' matches 'STREET'."""
    return lit("%" + "%".join(re.findall(r"[A-Z0-9]+", words.upper())) + "%")

def by_address(address, zipcode):
    building, _, street = address.strip().partition(" ")
    where = f"building={lit(building)} AND upper(street) like {like(street)} AND zipcode={lit(zipcode)}"
    rows = soql(INSPECTIONS, where=where, order="inspection_date DESC, violation_code", limit=5000)
    places = OrderedDict()
    for r in rows:
        places.setdefault(r["camis"], []).append(r)
    return places

def summary(rows):
    """One restaurant's rows (one per violation) -> (latest inspection, latest A/B/C-graded inspection) as dicts."""
    insp = OrderedDict()
    for r in rows:
        day = r.get("inspection_date", "")[:10]
        if day == "1900-01-01":
            continue
        i = insp.setdefault((day, r.get("inspection_type")), dict(date=day, type=r.get("inspection_type", "?"),
                            score=r.get("score"), grade=r.get("grade"), v=[]))
        if r.get("violation_code"):
            i["v"].append((r["violation_code"], r.get("critical_flag", "")))
    items = list(insp.values())
    return (items[0] if items else None), next((i for i in items if i.get("grade") in ("A", "B", "C")), None)

now = datetime.now(timezone.utc)
print(f"\nNYC Open Data restaurant inspections by address, queried {now:%Y-%m-%d %H:%M} UTC")
for address, z in ADDRESSES:
    places = by_address(address, z)
    print(f"  {address}, {z}: {len(places)} restaurant(s)"
          + (" (PARTIAL: hit the 5,000-row $limit, page with $offset)" if sum(map(len, places.values())) == 5000 else ""))
    for camis, rows in places.items():
        last, graded = summary(rows)
        r0 = rows[0]
        print(f"    {r0['dba']} (camis {camis}, {r0['building']} {r0['street']}, {r0.get('boro', '')}), {len(rows)} rows")
        if last:
            crit = sum(1 for c, f in last["v"] if f == "Critical")
            print(f"      latest: {last['date']} {last['type']}, score {last['score'] if last['score'] is not None else '-'}, "
                  f"grade {last['grade'] or '-'}, violations {[c for c, f in last['v']]} ({crit} critical)")
        if graded:
            print(f"      latest grade: {graded['grade']} on {graded['date']} (score {graded['score']})")

print(f"\nNYC Open Data 311 service requests by ZIP")
for z in ZIPS_311:
    reqs = soql(REQUESTS_311, select="unique_key,created_date,status,agency,complaint_type,descriptor",
                where=f"incident_zip={lit(z)}", order="created_date DESC, unique_key DESC", limit=200)
    if not reqs:
        print(f"  {z}: no requests")
        continue
    print(f"  {z}: newest 200 span {reqs[-1]['created_date'][:16]} to {reqs[0]['created_date'][:16]} (local time); "
          f"top types {Counter(q['complaint_type'] for q in reqs).most_common(3)}")
    for q in reqs[:3]:
        print(f"    {q['created_date'][:16].replace('T', ' ')} #{q['unique_key']} {q['agency']} {q['complaint_type']} / "
              f"{q.get('descriptor', '-')} [{q.get('status', '?')}]")

print(f"\n{calls} API calls. Source: NYC Open Data (43nn-pn8j, erm2-nwe9), accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the run on 2026-11-18, 23:36 UTC):

```text
robots.txt HTTP 200, 64 lines
  robots /resource/43nn-pn8j.json   allowed for 11/11 agents
  robots /resource/erm2-nwe9.json   allowed for 11/11 agents
  robots /OData.svc/                allowed for 0/11 agents
  robots /api/odata/v4/43nn-pn8j    allowed for 0/11 agents
  (urllib.robotparser says /OData.svc/ is allowed: it ends the '*' group at the blank line after Crawl-delay)
  Crawl-delay ['1'] -> 1 s between calls

NYC Open Data restaurant inspections by address, queried 2026-11-18 23:36 UTC
  205 E Houston St, 10002: 1 restaurant(s)
    KATZ'S DELICATESSEN (camis 40732665, 205 EAST HOUSTON STREET, Manhattan), 20 rows
      latest: 2026-09-30 Inter-Agency Task Force / Initial Inspection, score 0, grade -, violations [] (0 critical)
      latest grade: A on 2025-02-25 (score 12)
  178 Broadway, 11211: 1 restaurant(s)
    PETER LUGER STEAKHOUSE (camis 40364335, 178 BROADWAY, Brooklyn), 4 rows
      latest: 2026-04-06 Cycle Inspection / Initial Inspection, score 13, grade A, violations ['02G', '06D'] (2 critical)
      latest grade: A on 2026-04-06 (score 13)

NYC Open Data 311 service requests by ZIP
  10001: newest 200 span 2026-11-12T10:07 to 2026-11-17T00:30 (local time); top types [('Illegal Parking', 44), ('Encampment', 18), ('Noise - Residential', 13)]
    2026-11-17 00:30 #71146891 DOT Sidewalk Condition / Cellar Door Open/Unprotected [In Progress]
    2026-11-17 00:23 #71143659 TLC Taxi Compliment / Driver Compliment [In Progress]
    2026-11-16 23:03 #71152197 DOT Street Condition / Plate Condition - Noisy [In Progress]
  11211: newest 200 span 2026-11-15T02:10 to 2026-11-16T22:33 (local time); top types [('HEAT/HOT WATER', 39), ('Illegal Parking', 22), ('Noise - Street/Sidewalk', 18)]
    2026-11-16 22:33 #71141767 NYPD Illegal Parking / Commercial Overnight Parking [Closed]
    2026-11-16 22:28 #71147339 HPD HEAT/HOT WATER / ENTIRE BUILDING [Open]
    2026-11-16 22:19 #71144061 HPD HEAT/HOT WATER / ENTIRE BUILDING [Open]

4 API calls. Source: NYC Open Data (43nn-pn8j, erm2-nwe9), accessed 18 November 2026 23:36 UTC.
```

### 4. curl, headers and mistakes

```bash
B=https://data.cityofnewyork.us/resource
UA='nyc-open-data-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# restaurant by CAMIS: one row per violation; date, type, score, grade, violation code
curl -sS --fail -A "$UA" -G "$B/43nn-pn8j.json" --data-urlencode 'camis=40732665' \
  --data-urlencode '$select=inspection_date,inspection_type,score,grade,violation_code' \
  --data-urlencode '$order=inspection_date DESC, violation_code' --data-urlencode '$limit=4' \
  | python3 -c 'import json, sys
for r in json.load(sys.stdin): print(r["inspection_date"][:10], r["inspection_type"], "| score", r.get("score", "-"), "| grade", r.get("grade", "-"), "|", r.get("violation_code", "-"))'
sleep 1
# CSV of the same query (the same /resource/ path, .csv instead of .json)
curl -sS --fail -A "$UA" -G "$B/43nn-pn8j.csv" --data-urlencode 'camis=40732665' \
  --data-urlencode '$select=inspection_date,score,grade' --data-urlencode '$order=inspection_date DESC' --data-urlencode '$limit=2'
sleep 1
# latest 311 request for a ZIP (incident_zip is text: quote it)
curl -sS --fail -A "$UA" -G "$B/erm2-nwe9.json" --data-urlencode "\$where=incident_zip='10001'" \
  --data-urlencode '$select=unique_key,created_date,agency,complaint_type,descriptor,status' \
  --data-urlencode '$order=created_date DESC' --data-urlencode '$limit=1'; echo
sleep 1
# headers: types, last change, CORS; no rate-limit headers
curl -sS -A "$UA" -D - -o /dev/null -G "$B/43nn-pn8j.json" --data-urlencode 'camis=40732665' --data-urlencode '$limit=1' | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|access-control-allow-origin|x-soda2-types|last-modified|retry-after|x-ratelimit-[a-z]+):)'
sleep 1
# mistakes: unquoted ZIP is a type error, an unescaped apostrophe is a parse error
curl -sS -A "$UA" -w ' <- HTTP %{http_code}\n' -G "$B/erm2-nwe9.json" --data-urlencode '$where=incident_zip=10001' | grep -o '"errorCode":"[^"]*"\| <- HTTP [0-9]*' | tr '\n' ' '; echo
sleep 1
curl -sS -A "$UA" -w ' <- HTTP %{http_code}\n' -G "$B/43nn-pn8j.json" --data-urlencode "\$where=dba='KATZ'S DELICATESSEN'" | grep -o '"code" : "[^"]*"\| <- HTTP [0-9]*' | tr '\n' ' '; echo
```

Output (from the run on 2026-11-18, 23:37 UTC):

```text
2026-09-30 Inter-Agency Task Force / Initial Inspection | score 0 | grade - | -
2026-07-13 Cycle Inspection / Initial Inspection | score 20 | grade - | 04H
2026-07-13 Cycle Inspection / Initial Inspection | score 20 | grade - | 04K
2026-07-13 Cycle Inspection / Initial Inspection | score 20 | grade - | 04N
"inspection_date","score","grade"
"2026-09-30T00:00:00.000","0",
"2026-07-13T00:00:00.000","20",
[{"unique_key":"71146891","created_date":"2026-11-17T00:30:36.000","agency":"DOT","complaint_type":"Sidewalk Condition","descriptor":"Cellar Door Open/Unprotected","status":"In Progress"}]

HTTP/1.1 200 OK
Content-Type: application/json;charset=utf-8
Access-Control-Allow-Origin: *
X-SODA2-Types: ["text","text","text","text","text","text","text","text","floating_timestamp","text","text","text","text","number","text","floating_timestamp","floating_timestamp","text","number","number","text","text","text","text","text","text","point"]
Last-Modified: Wed, 18 Nov 2026 23:15:47 GMT
"errorCode":"query.soql.type-mismatch"  <- HTTP 400 
"code" : "query.compiler.malformed"  <- HTTP 400 
```

## Fields

Restaurant inspections, `43nn-pn8j` ("DOHMH New York City Restaurant Inspection Results"; descriptions from the dataset's column metadata at `/api/views/43nn-pn8j.json`):

| Field | Example | Notes |
|---|---|---|
| `camis` | `"40732665"` | "unique identifier for the entity (restaurant)", "static per restaurant permit". Use it once you have picked a place |
| `dba` | `"KATZ'S DELICATESSEN"` | business name, upper case; `like` is case-sensitive, so match `upper(dba)` with upper-case words |
| `building`, `street`, `zipcode`, `boro` | `"205"`, `"EAST HOUSTON STREET"`, `"10002"`, `"Manhattan"` | street spelling varies by record ("EAST HOUSTON STREET", "W 10TH ST") |
| `cuisine_description`, `phone` | `"Sandwiches"` | "provided by restaurant owner/manager" (cuisine is an "Optional field") |
| `inspection_date` | `"2026-09-30T00:00:00.000"` | `1900-01-01` = "not yet had an inspection" (4,073 rows) |
| `inspection_type` | `"Cycle Inspection / Initial Inspection"` | program / type; 36 values in a curl probe at 23:28 UTC (blank on the 1900-01-01 rows), e.g. Cycle, Pre-permit, Administrative Miscellaneous, Inter-Agency Task Force, Smoke-Free Air Act |
| `action` | `"Violations were cited in the following area(s)."` | or "No violations were recorded at the time of this inspection.", closures and re-openings |
| `violation_code`, `violation_description`, `critical_flag` | `"04K"`, `"Evidence of rats..."`, `"Critical"` | one row per violation; `critical_flag` "Critical", "Not Critical" or "Not Applicable" |
| `score` | `"20"` | text in JSON (a number in `X-SODA2-Types`); "Scores are updated based on adjudication results" |
| `grade`, `grade_date` | `"A"`, `"2025-02-25T00:00:00.000"` | A, B, C, N = Not Yet Graded, Z = Grade Pending, P = Grade Pending issued on re-opening after a closure; often absent |
| `record_date` | `"2026-11-18T06:00:29.000"` | "the date when the extract was run" |
| `latitude`, `longitude`, `bin`, `bbl`, `nta`, `community_board`, `council_district`, `census_tract` | | location codes |

311 requests, `erm2-nwe9` ("311 Service Requests from 2020 to Present"): `unique_key`, `created_date`, `closed_date`, `agency`, `agency_name`, `complaint_type` ("Problem"), `descriptor`, `descriptor_2`, `incident_zip` (text), `incident_address`, `street_name`, `status`, `resolution_description`, `resolution_action_updated_date`, `borough`, `latitude`, `longitude` and 27 more (44 in all, plus 4 computed region columns). The description: "This dataset is updated daily" and "the data does not reveal any personally identifying information about the customer who made the request". Data for 2010-2019 is in a separate dataset (`76ig-c548`).

Response headers: `Content-Type: application/json;charset=utf-8`, `Access-Control-Allow-Origin: *`, `X-SODA2-Fields`, `X-SODA2-Types` (`floating_timestamp`, `number`, `text`, `point`), `Last-Modified` (restaurant data: Wed, 18 Nov 2026 23:15:47 GMT at 23:37 UTC). No `Retry-After` or rate-limit headers on any answer seen.

## Gotchas

- **Group before you count.** One row per violation, so "20 rows" for Katz's is 8 inspections. Two inspection types can share a date (2026-07-13: Cycle with 7 violations and score 20, Administrative Miscellaneous with no score), so group by date and type, not date alone.
- **The newest inspection may carry no grade or a meaningless 0.** Katz's latest was an Inter-Agency Task Force inspection with score 0 and no grade; its last letter grade in the data is from 2025-02-25. Do not call a 0 from such an inspection an "A". An initial cycle inspection with 14 points or more carries no letter grade (Katz's, 2026-07-13: score 20, B range): of the 97,068 "Cycle Inspection / Initial Inspection" rows scoring 14 or more, 94,749 have `grade` absent and 2,319 have N (Not Yet Graded), none A, B or C (23:43 UTC).
- **Names repeat and vary.** "Katz's Deli" matched two CAMIS numbers (205 East Houston Street, Manhattan, and 445 Gold Street, Brooklyn); "KATZ" alone also matched "JEFFREY KATZ" with the 1900-01-01 placeholder. Show the address and ask, or filter by ZIP (block 1). Split words on punctuation so `KATZ'S` is matched by `%KATZ%S%`.
- **Quote SoQL strings and double the apostrophes.** `dba='KATZ''S DELICATESSEN'` works; `'KATZ'S...'` is HTTP 400 `query.compiler.malformed`. `incident_zip` is text: `incident_zip=10001` without quotes is HTTP 400 `query.soql.type-mismatch`.
- **`like` is case-sensitive.** `dba like '%katz%'` is HTTP 200 with 0 rows; use `upper(dba)`.
- **Address words over-match.** `%E%HOUSTON%ST%` also fits "WEST HOUSTON STREET" (W-E-S-T); block 3 pins the building number and ZIP so the match stays one place.
- **Only active restaurants, about 3 years.** The dataset description: "every sustained or not yet adjudicated violation citation from every full or special program inspection conducted up to three years prior to the most recent inspection for restaurants and college cafeterias in an active status". A closed restaurant disappears. 31,555 CAMIS numbers and 295,247 rows at 23:28 UTC.
- **311 is a day behind.** At 23:32 UTC on 2026-11-18 the newest 10001 request was created 2026-11-17 00:30; the data said `Last-Modified: Wed, 18 Nov 2026 03:30:11 GMT`. "Latest" means the latest in the daily load. Store the access time with every answer.
- **Timestamps have no time zone.** `created_date` and `inspection_date` are `floating_timestamp`: "no timezone value, encoded as ISO8601 Times with no timezone offset" (Socrata doc). 311 times read as NYC local time; compare them as text in `$where` (`created_date >= '2026-11-11T00:00:00'`).
- **`$limit` defaults to 1,000, silently.** A query without `$limit` returned exactly 1,000 rows; `$limit=60000` returned 60,000 (1.3 MB; 17.6 s, 5.7 s on a re-run at 23:42 UTC). Page with `$offset` and a unique `$order` for more.
- **Some queries are slow.** The first grouped `upper(dba) like '%KATZ%'` query took 3.7 s, `$q=katz` (text search across columns, not just `dba`: `$q=HOUSTON` matched on `street`; it returns rows, one per violation) took up to 4.5 s, and counting the 1900-01-01 rows took 10.8 s; repeats were faster (0.1-0.6 s). Keep `$select` small and filter by `camis` once you have it.
- **Privacy.** 311 rows carry an `incident_address` with a house number. The blocks print the street only.
- **Python's robots parser is wrong here** (blank line after `Crawl-delay`, see block 3). Use an RFC 9309 parser.
- **Tab marker.** The harness sets the tab title to a horse emoji; block 1 checks `location.origin` and the JSON, not the title.

## What does not work

- **OData** (`/OData.svc/`, `/api/odata/`): robots.txt disallows both for every agent. Use `/resource/<id>.json`.
- **curl on the DOHMH page** https://www.nyc.gov/site/doh/services/restaurant-grades.page: HTTP 403 from this machine; the cloud browser got HTTP 200. The skill does not need it; the grade cut-offs come from the ABCEats FAQ (block 2).
- **Unknown dataset id or column:** HTTP 404 `dataset.missing`; HTTP 400 `query.soql.no-such-column`.
- **Not tested:** an app token (`X-App-Token`; optional, not used), the over-limit response (no 429 was provoked; the Socrata doc gives no number), `$offset` paging past 60,000 rows, and other datasets on the portal.
