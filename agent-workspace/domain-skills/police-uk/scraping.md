# data.police.uk (Police API) - Most Common Street-Level Crimes Within a Mile of a Point, Latest Month Published (official API)

Field-tested against data.police.uk on 2026-11-12 using a fresh Browser Use cloud browser (logged out) plus Python urllib and `curl` from a laptop. 7 browser page loads and 16 in-page `fetch()` calls, about 50 curl calls and 7 urllib calls, all serial at 0.5 s or more spacing: every call was HTTP 200 except the deliberate 400/404 probes below. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-12, curl and the cloud browser): https://data.police.uk/robots.txt is HTTP 200 `text/plain` with an empty body (0 bytes), the same for User-Agent `*`, GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, Claude-SearchBot, anthropic-ai, Google-Extended, PerplexityBot, Perplexity-User, CCBot, Bytespider, Applebot-Extended and Meta-ExternalAgent: no rules, no named AI-agent groups, so `/api/` is allowed for all of them. Terms: the docs say "The Police API no longer requires authentication." (https://data.police.uk/docs/authentication/) and "The current rate limit is 15 requests per second with a burst of 30." (https://data.police.uk/docs/api-call-limits/); the about page (https://data.police.uk/about/) gives the licence of the crime data as "Open Government Licence v3.0" and links https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/ . The OGL lets you "exploit the Information commercially and non-commercially"; you must "acknowledge the source of the Information" with the provider's attribution statement, or, if none is given (data.police.uk gives none), "Contains public sector information licensed under the Open Government Licence v3.0."; it does not cover "departmental or public sector organisation logos, crests and the Royal Arms", and grants no right to suggest "official status" or that the provider "endorse[s] you or your use". No AI/ML, scraping, automated-access or non-commercial clause. This skill names the source "data.police.uk (Police API)", uses no police crest or logo, and prints the OGL attribution line with every answer. The blocks do not fetch the OGL page (www.nationalarchives.gov.uk robots.txt carries `Content-Signal: ai-train=no, search=yes, ai-input=no`).

## Quick summary

- **No scraping.** `GET https://data.police.uk/api/crimes-street/all-crime?lat=51.50806&lng=-0.12806&date=2026-09` returns a JSON array of every crime and anti-social behaviour (ASB) incident within **1 mile** of the point that month (the radius is fixed). For Trafalgar Square in September 2026: 3,749 records = **3,353 crimes** + 396 ASB incidents. Top crime types: **other theft 823 (24.5%), theft from the person 662 (19.7%), violence and sexual offences 584 (17.4%)**, then shoplifting 540 (16.1%).
- **"Latest month published" = `/api/crime-last-updated`.** It returned `{"date":"2026-09-01"}` on 2026-11-12: data runs about 2 months behind, updated "once a month" (docs). The day is a placeholder. Pass `date=YYYY-MM` explicitly so the month you quote is the month you fetched; the no-`date` default gave the same 3,749 rows.
- **Drop `anti-social-behaviour` before ranking crimes.** `all-crime` includes ASB incidents (the docs call the category "All crime and ASB"), and ASB would rank 5th here.
- **Locations are approximate.** Each crime is snapped to the nearest point on a master list of anonymous map points (about page), so the 1-mile circle counts snap points inside it, and street names read like "On or near Nightclub". Moving the centre 7 m and 76 m changed the total (3,722 / 3,749 / 3,777 records for the three points) but not the order of the top 4.
- **Coverage:** England, Wales and Northern Ireland only, months 2023-10 .. 2026-09 (`/api/crimes-street-dates`, 36 months). A point outside coverage (Paris) or a future month (2026-10) returns HTTP 200 `[]`, not an error.
- **Errors are not JSON:** a bad month (2026-13) or a month before coverage (2023-09) is HTTP 404 with an empty `text/html` body; `lat=abc` is HTTP 400 empty; `locate-neighbourhood` outside coverage is HTTP 404 `Not Found` (`text/plain`). An unknown crime category is **not** an error: it silently returns all-crime.
- **Rate limit:** 15 requests/s, burst 30, HTTP 429 above that (docs); no rate-limit headers on responses. One area-month is one call (about 1.5 MB for central London), so pacing is easy; the blocks wait 0.5 s per call.

## What works

### 1. Most common crimes within a mile of Trafalgar Square, latest month (browser)

`on_api_tab()` opens `/api/crime-last-updated` on data.police.uk once, so `fetch()` is same-origin. `get()` returns parsed JSON on 200, waits 10 s once on 429/5xx and otherwise raises, so an error never looks like "no crimes". The block refuses a latest month that is implausibly old or new, checks every record is from the month asked for and every category is a known one, then ranks crimes with ASB set aside.

```python
import json, time
from collections import Counter
from datetime import date

PLACE = "Trafalgar Square"
LAT, LNG = 51.50806, -0.12806  # Trafalgar Square, en.wikipedia.org/wiki/Trafalgar_Square (51.50805556, -0.12805556)
TOP = 10

SITE = "https://data.police.uk"
API = SITE + "/api"
PAUSE = 0.5  # docs: 15 requests/s, burst 30, HTTP 429 above that; one call at a time is far below it
ATTRIBUTION = "Contains public sector information licensed under the Open Government Licence v3.0."

def on_api_tab():
    """fetch() runs same-origin from a logged-out data.police.uk tab (the crime-last-updated JSON). Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(API + "/crime-last-updated")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"date"' not in body:
        raise RuntimeError(f"data.police.uk did not serve the API (at {js('location.href')}, body {body[:80]!r}): stop")

# js() gives up after a few seconds, and a 1-mile all-crime answer is about 1.5 MB, so start the fetch, then poll.
START_JS = """(() => { window.__pol = window.__pol || {}; const id = String(Math.random()).slice(2); window.__pol[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__pol[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__pol[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__pol[%s]; if (v) delete window.__pol[%s]; return v; })()"""

def get(path, timeout=90):
    """GET API+path from inside the tab -> parsed JSON. Errors are not JSON (400/404 empty HTML, 'Not Found' text).
    Waits 10 s once on 429/5xx, raises on anything else, so an error never looks like 'no crimes'."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(API + path)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{path}: no answer after {timeout}s")
            time.sleep(0.5)
        time.sleep(PAUSE)
        if r["status"] == 200 and "json" in (r["type"] or ""):
            return json.loads(r["text"])
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(10)
            continue
        raise RuntimeError(f"{path}: HTTP {r['status']} {r['type']!r} {' '.join(r['text'].split())[:120]!r}; stopping")

on_api_tab()

# 1. Latest published month. The day is a placeholder ("2026-09-01" means September 2026).
last = get("/crime-last-updated")
month = last["date"][:7]
y, m = map(int, month.split("-"))
today = date.today()
lag = (today.year - y) * 12 + today.month - m
print(f"crime-last-updated: {last['date']} -> latest month {month} ({lag} months before {today:%Y-%m})")
if lag < 1 or lag > 6:
    raise RuntimeError(f"latest month {month} is {lag} months from today: check the changelog before answering")

# 2. Which force covers the point (the 1-mile circle can cross force boundaries; Trafalgar Square is the Met).
hood = get(f"/locate-neighbourhood?q={LAT},{LNG}")
force = get(f"/forces/{hood['force']}")
print(f"point {LAT},{LNG} ({PLACE}): force {force['name']} ({hood['force']}), neighbourhood {hood['neighbourhood']}")

# 3. Category names for that month, then every crime within 1 mile of the point in that month.
names = {c["url"]: c["name"] for c in get(f"/crime-categories?date={month}")}
crimes = get(f"/crimes-street/all-crime?lat={LAT}&lng={LNG}&date={month}")
if not isinstance(crimes, list) or not crimes:
    raise RuntimeError(f"no crimes returned for {month} at {LAT},{LNG}: outside England, Wales and NI, or a future month")
months = Counter(c["month"] for c in crimes)
if set(months) != {month}:
    raise RuntimeError(f"asked for {month}, got months {dict(months)}")
unknown = {c["category"] for c in crimes} - set(names)
if unknown:
    raise RuntimeError(f"categories not in crime-categories?date={month}: {sorted(unknown)}")

by_cat = Counter(c["category"] for c in crimes)
asb = by_cat.pop("anti-social-behaviour", 0)  # all-crime includes ASB incidents, which are not crimes
n = sum(by_cat.values())
print(f"\nall-crime within 1 mile, {month}: {len(crimes):,} records = {n:,} crimes + {asb:,} anti-social behaviour incidents")
print(f"location_type: {dict(Counter(c['location_type'] for c in crimes))}   (BTP = British Transport Police)")
print(f"\ntop {TOP} crime types ({month}, 1 mile of {PLACE}):")
for i, (cat, k) in enumerate(by_cat.most_common(TOP), 1):
    print(f"  {i:2}. {names[cat]:<30} {k:5,}  {100 * k / n:4.1f}%   ({cat})")
print(f"  (anti-social behaviour, not a crime: {asb:,})")

streets = Counter(c["location"]["street"]["name"] for c in crimes if c["category"] != "anti-social-behaviour")
print("\nbusiest snap points (approximate, anonymised locations):")
for s, k in streets.most_common(5):
    print(f"  {k:4}  {s}")

top3 = ", ".join(f"{names[c].lower()} ({k:,})" for c, k in by_cat.most_common(3))
print(f"\nanswer: in {date(y, m, 1):%B %Y}, the latest month published, the most common street-level crimes within"
      f" a mile of {PLACE} were {top3}, out of {n:,} crimes.")
print(f"  Source: data.police.uk (Police API), /api/crimes-street/all-crime, {force['name']} data. {ATTRIBUTION}")
```

Output (from the run on 2026-11-12 23:31 UTC):

```text
crime-last-updated: 2026-09-01 -> latest month 2026-09 (2 months before 2026-11)
point 51.50806,-0.12806 (Trafalgar Square): force Metropolitan Police Service (metropolitan), neighbourhood E05013806N

all-crime within 1 mile, 2026-09: 3,749 records = 3,353 crimes + 396 anti-social behaviour incidents
location_type: {'Force': 3749}   (BTP = British Transport Police)

top 10 crime types (2026-09, 1 mile of Trafalgar Square):
   1. Other theft                      823  24.5%   (other-theft)
   2. Theft from the person            662  19.7%   (theft-from-the-person)
   3. Violence and sexual offences     584  17.4%   (violent-crime)
   4. Shoplifting                      540  16.1%   (shoplifting)
   5. Public order                     195   5.8%   (public-order)
   6. Drugs                            162   4.8%   (drugs)
   7. Robbery                          119   3.5%   (robbery)
   8. Burglary                          86   2.6%   (burglary)
   9. Bicycle theft                     65   1.9%   (bicycle-theft)
  10. Vehicle crime                     64   1.9%   (vehicle-crime)
  (anti-social behaviour, not a crime: 396)

busiest snap points (approximate, anonymised locations):
   308  On or near Nightclub
   188  On or near Theatre/concert Hall
   178  On or near Further/higher Educational Building
    90  On or near Parking Area
    90  On or near Shopping Area

answer: in September 2026, the latest month published, the most common street-level crimes within a mile of Trafalgar Square were other theft (823), theft from the person (662), violence and sexual offences (584), out of 3,353 crimes.
  Source: data.police.uk (Police API), /api/crimes-street/all-crime, Metropolitan Police Service data. Contains public sector information licensed under the Open Government Licence v3.0.
```

### 2. Docs, robots.txt and error shapes (browser)

Reads the auth, call-limit, street-crime and about pages, then makes 11 calls from an API page: robots.txt, the list of available months and 9 edge cases.

```python
import json, time

SITE = "https://data.police.uk"
API = SITE + "/api"
LAT, LNG = 51.50806, -0.12806  # Trafalgar Square

# The docs pages, as a logged-out browser sees them: authentication, call limits, licence, 1-mile radius.
new_tab(SITE + "/docs/authentication/")
wait_for_load()
if js("location.origin") != SITE:
    raise RuntimeError(f"data.police.uk did not serve its docs (at {js('location.href')}): stop")
for page, needles in (("/docs/authentication/", ["The Police API no longer requires authentication."]),
                      ("/docs/api-call-limits/", ["The current rate limit is 15 requests per second with a burst of 30.",
                                                  "HTTP 429 (Too Many Requests)"]),
                      ("/docs/method/crime-street/", ["within a 1 mile radius of a single point",
                                                      "The latest month will be shown by default"]),
                      ("/about/", ["Open Government Licence v3.0", "Geographic Coverage: England, Wales, Northern Ireland"])):
    goto_url(SITE + page)
    wait_for_load()
    text = " ".join((js("document.body.innerText") or "").split())
    for s in needles:
        if s not in text:
            raise RuntimeError(f"{page} no longer says {s!r}: re-read it before relying on this skill")
        i = text.find(s)
        print(f"{page}: ...{text[i:i + 110]}...")
    time.sleep(1)

# Same-origin probes from an API page, same tab. No retries: this block only inspects answers.
goto_url(API + "/crime-last-updated")
wait_for_load()
START_JS = """(() => { window.__pol = window.__pol || {}; const id = String(Math.random()).slice(2); window.__pol[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__pol[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__pol[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__pol[%s]; if (v) delete window.__pol[%s]; return v; })()"""

def raw(url, timeout=90):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{url}: no answer after {timeout}s")
        time.sleep(0.5)
    time.sleep(0.5)
    return r["status"], r["type"] or "", r["text"]

s, t, body = raw(SITE + "/robots.txt")
print(f"\nrobots.txt: HTTP {s} {t} {len(body)} bytes {body!r}")

s, t, body = raw(API + "/crimes-street-dates")
d = json.loads(body)
print(f"crimes-street-dates: HTTP {s}, {len(d)} months, {d[-1]['date']} .. {d[0]['date']}\n")

pt = f"lat={LAT}&lng={LNG}"
for label, path in (("no date (latest)",  f"/crimes-street/all-crime?{pt}"),
                    ("next month",        f"/crimes-street/all-crime?{pt}&date=2026-10"),
                    ("before coverage",   f"/crimes-street/all-crime?{pt}&date=2023-09"),
                    ("bad month",         f"/crimes-street/all-crime?{pt}&date=2026-13"),
                    ("bad lat",           f"/crimes-street/all-crime?lat=abc&lng={LNG}"),
                    ("Paris",             "/crimes-street/all-crime?lat=48.8566&lng=2.3522&date=2026-09"),
                    ("unknown category",  f"/crimes-street/not-a-category?{pt}&date=2026-09"),
                    ("one category",      f"/crimes-street/burglary?{pt}&date=2026-09"),
                    ("locate in Paris",   "/locate-neighbourhood?q=48.8566,2.3522")):
    s, t, body = raw(API + path)
    if s == 200 and "json" in t and body.startswith("["):
        rows = json.loads(body)
        cats = sorted({r["category"] for r in rows})
        months = sorted({r["month"] for r in rows})
        print(f"{label:17} HTTP {s} {len(rows):5} rows, months {months}, {len(cats)} categories {cats[:3]}")
    else:
        print(f"{label:17} HTTP {s} {t!r} {' '.join(body.split())[:60]!r}")
```

Output (from the run on 2026-11-12 23:32 UTC):

```text
/docs/authentication/: ...The Police API no longer requires authentication. Responses If a request succeeds, the API will return a 200 s...
/docs/api-call-limits/: ...The current rate limit is 15 requests per second with a burst of 30. So, on average you must make fewer than 1...
/docs/api-call-limits/: ...HTTP 429 (Too Many Requests) response code. Cookies...
/docs/method/crime-street/: ...within a 1 mile radius of a single point, or within a custom area. The street-level crimes returned in the API...
/docs/method/crime-street/: ...The latest month will be shown by default Custom area poly The lat/lng pairs which define the boundary of the ...
/about/: ...Open Government Licence v3.0 Language: en-GB Data Download The latest complete copy of all the data described ...
/about/: ...Geographic Coverage: England, Wales, Northern Ireland Publisher: Single Online Home National Digital Team lice...

robots.txt: HTTP 200 text/plain 0 bytes ''
crimes-street-dates: HTTP 200, 36 months, 2023-10 .. 2026-09

no date (latest)  HTTP 200  3749 rows, months ['2026-09'], 14 categories ['anti-social-behaviour', 'bicycle-theft', 'burglary']
next month        HTTP 200     0 rows, months [], 0 categories []
before coverage   HTTP 404 'text/html; charset=utf-8' ''
bad month         HTTP 404 'text/html; charset=utf-8' ''
bad lat           HTTP 400 'text/html; charset=utf-8' ''
Paris             HTTP 200     0 rows, months [], 0 categories []
unknown category  HTTP 200  3749 rows, months ['2026-09'], 14 categories ['anti-social-behaviour', 'bicycle-theft', 'burglary']
one category      HTTP 200    86 rows, months ['2026-09'], 1 categories ['burglary']
locate in Paris   HTTP 404 'text/plain' 'Not Found'
```

### 3. Same answer with Python urllib, plus outcomes (no browser)

Python's default User-Agent got HTTP 200. Also checks that `crime-last-updated` and the newest entry of `crimes-street-dates` agree, so a half-finished monthly update is caught.

```python
import json, sys, time, urllib.error, urllib.request
from collections import Counter

LAT, LNG = 51.50806, -0.12806  # Trafalgar Square (en.wikipedia.org/wiki/Trafalgar_Square)
API = "https://data.police.uk/api"

def get(path):
    """GET -> parsed JSON. Python's default User-Agent got HTTP 200. Errors are empty HTML (400/404), not JSON."""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(API + path, timeout=90) as r:
                body = r.read()
            time.sleep(0.5)  # docs: 15 requests/s, burst 30
            return json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(10)
                continue
            sys.exit(f"{path}: HTTP {e.code} {e.headers.get('content-type')!r}")

month = get("/crime-last-updated")["date"][:7]
newest = get("/crimes-street-dates")[0]["date"]  # newest first
if newest != month:
    sys.exit(f"crime-last-updated says {month}, crimes-street-dates starts at {newest}: data mid-update, retry later")

crimes = get(f"/crimes-street/all-crime?lat={LAT}&lng={LNG}&date={month}")
if not crimes or {c["month"] for c in crimes} != {month}:
    sys.exit(f"unexpected answer for {month}: {len(crimes)} rows, months {sorted({c['month'] for c in crimes})}")
names = {c["url"]: c["name"] for c in get(f"/crime-categories?date={month}")}
cats = Counter(c["category"] for c in crimes if c["category"] != "anti-social-behaviour")
n = sum(cats.values())
print(f"{month}: {len(crimes):,} records within 1 mile, {n:,} crimes excluding anti-social behaviour")
for cat, k in cats.most_common(5):
    print(f"  {names[cat]:<30} {k:5,}  {100 * k / n:4.1f}%")

outcomes = Counter((c["outcome_status"] or {}).get("category", "no outcome yet") for c in crimes
                   if c["category"] != "anti-social-behaviour")
print("latest outcomes:", ", ".join(f"{o} {k:,}" for o, k in outcomes.most_common(3)))
print("Contains public sector information licensed under the Open Government Licence v3.0.")
```

Output (from the run on 2026-11-12 23:33 UTC):

```text
2026-09: 3,749 records within 1 mile, 3,353 crimes excluding anti-social behaviour
  Other theft                      823  24.5%
  Theft from the person            662  19.7%
  Violence and sexual offences     584  17.4%
  Shoplifting                      540  16.1%
  Public order                     195   5.8%
latest outcomes: Investigation complete; no suspect identified 1,683, Under investigation 1,224, Unable to prosecute suspect 242
Contains public sector information licensed under the Open Government Licence v3.0.
```

### 4. curl

```bash
A=https://data.police.uk/api
M=$(curl -sS --fail "$A/crime-last-updated" | python3 -c 'import json,sys; print(json.load(sys.stdin)["date"][:7])')
echo "latest month: $M"
sleep 1
curl -sS --fail "$A/crimes-street/all-crime?lat=51.50806&lng=-0.12806&date=$M" | python3 -c '
import json, sys
from collections import Counter
rows = json.load(sys.stdin)
c = Counter(r["category"] for r in rows if r["category"] != "anti-social-behaviour")
print(sum(c.values()), "crimes;", c.most_common(3))
'
sleep 1
curl -sS -o /dev/null -w 'next month (2026-10): HTTP %{http_code}, %{size_download} bytes\n' "$A/crimes-street/all-crime?lat=51.50806&lng=-0.12806&date=2026-10"
```

Output (from the run on 2026-11-12 23:33 UTC):

```text
latest month: 2026-09
3353 crimes; [('other-theft', 823), ('theft-from-the-person', 662), ('violent-crime', 584)]
next month (2026-10): HTTP 200, 2 bytes
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `date` | `/api/crime-last-updated` | `2026-09-01`: month of the latest crime data; the day "is irrelevant" (docs) |
| `category` | crime | slug (`other-theft`, `violent-crime`, `anti-social-behaviour`, ...); names from `/api/crime-categories?date=YYYY-MM` (`violent-crime` = "Violence and sexual offences") |
| `month` | crime | `YYYY-MM`; check it equals the month you asked for |
| `location.latitude`, `location.longitude` | crime | strings, the anonymised snap point, not the place of the crime |
| `location.street.name` | crime | `On or near <street or place type>`, an approximation (docs) |
| `location_type` | crime | `Force` or `BTP` (British Transport Police); all 3,749 were `Force` here |
| `outcome_status` | crime | `{category, date}` of the latest outcome ("Under investigation" included); `null` for all 396 ASB rows here. "Neither the British Transport Police nor the Police Service of Northern Ireland provide outcome data" (about page) |
| `id`, `persistent_id` | crime | `id` is API-only and "not guaranteed to always stay the same" (docs); `persistent_id` is a 64-character hash for all 3,353 crimes, empty for all 396 ASB rows |
| `force`, `neighbourhood` | `/api/locate-neighbourhood?q=lat,lng` | `metropolitan`, `E05013806N` for Trafalgar Square; `/api/forces/<id>` gives the name |
| `date`, `stop-and-search[]` | `/api/crimes-street-dates` | available months, newest first, with the forces that have stop-and-search data |

## Gotchas

- **All crime includes ASB.** `crime-categories?date=2026-09` names `all-crime` "All crime", but the rows include `anti-social-behaviour` (396 here). Say whether your count includes it.
- **Future months and empty areas return `[]` with HTTP 200.** `date=2026-10` on 2026-11-12 was `[]`; so was Paris. Read the month from `crime-last-updated`, and treat `[]` for a covered point and a published month as suspicious.
- **Unknown category = all-crime.** `/api/crimes-street/not-a-category?...` returned the same 3,749 rows as `all-crime`. Check the slug against `crime-categories` first.
- **Snap points, not addresses.** "If the nearest map point is more than 20km away, the co-ordinates are zeroed out" (about page); crimes with no location are not in `crimes-street` at all (`/api/crimes-no-location?category=all-crime&force=metropolitan&date=2026-09` is separate; it returned `[]`).
- **Scotland:** "since only the British Transport Police provide data for Scotland, crime levels may appear much lower than they really are" (docs). The Edinburgh centre point returned `[]` for 2026-09.
- **The data changes.** Forces upload "a snapshot in time"; crimes can later be reclassified or moved (about page). Quote the month and the fetch date.
- **Big answers.** 1.5 MB and 1.4 to 7 s for one central-London month (2023-10 was 2.6 MB). The browser blocks poll the fetch instead of waiting inside one `js()` call. Areas with more than 10,000 crimes return HTTP 503 for custom `poly` areas (docs); the 1-mile point query here was far below that.
- **CORS is open** (`access-control-allow-origin: *`); the blocks use a data.police.uk tab anyway.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks check `location.origin` and page text, not the title.

## What does not work

- **Changing the radius:** the point query is always 1 mile. For another shape use `poly=` (lat,lng pairs joined by `:`; GET over 4,094 characters is HTTP 400, use POST); not tested.
- **Months before 2023-10:** HTTP 404 on the API. The archive (`https://data.police.uk/data/archive/[year]-[month].zip`, about page) holds the bulk CSVs; not tested.
- **Police crests or logos:** not licensed under the OGL; not used.
- **Not tested:** www.police.uk (the public crime map), `crimes-at-location`, `outcomes-at-location`, stop-and-search methods, neighbourhood team and events methods, rate-limit behaviour (never provoked).

