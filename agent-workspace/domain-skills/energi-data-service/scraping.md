# Energi Data Service (Energinet) - Find the Cheapest Hours to Run an Appliance Tomorrow From Denmark's Day-Ahead Electricity Prices, DK1 and DK2 (API, no key)

Field-tested against api.energidataservice.dk on 2026-11-16 (US Pacific afternoon; 2026-11-16 23:48 to 2026-11-17 00:08 UTC, which is 00:48-01:08 on 17 November in Denmark) using a fresh Browser Use cloud browser (logged out) plus Python `urllib` and `curl` from a Linux machine. 15 browser page loads (an API metadata page, both robots files, the terms page and the API guide) and 25 in-page `fetch()` calls, 23 curl calls (2 of them robots.txt) and 5 urllib calls (4 of them robots.txt) to the Energi Data Service hosts, all serial. Every call was HTTP 200 except the deliberate HTTP 400 and 404 probes, the HTTP 404 robots files and 13 HTTP 429 answers from the DayAheadPrices rate limit (1 call per minute from one IP, see below); each retry after the wait the message named got HTTP 200 or the probe's expected error. No challenge, no key, no login.

robots.txt (checked 2026-11-16, curl, the cloud browser and `urllib.robotparser`): https://api.energidataservice.dk/robots.txt answers HTTP 404 `{ "statusCode": 404, "message": "Resource not found" }` and https://www.energidataservice.dk/robots.txt answers HTTP 404 with an empty body, so neither host has rules or named AI-agent groups. Under RFC 9309 (section 2.3.1.3) an unavailable robots.txt (4xx) means a crawler "MAY access any resources", and Python's parser treats it as allow-all for GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider (block 3 checks all 11 agents on `/dataset/DayAheadPrices` and `/meta/dataset/DayAheadPrices`). Terms: https://www.energidataservice.dk/terms-and-conditions says "Data published on Energi Data Service is subject to the conditions of Creative Commons CC-BY 4.0. Users may copy, change and distribute data freely, even for commercial purposes." and "Users must give appropriate credit and indicate if data has been changed. This must not be done in a way which suggests that Energinet endorses the use of data." It also says "Energinet stores the used IP address for 3 months from each API call", for "statistical analyses on the usage of the API solution". The API guide (https://www.energidataservice.dk/guides/api-guides) says the API "enables users free of charge to download data for further processing", applies rate limits per dataset, answers `HTTP 429 - "Rate limit is exceeded. Try again in X seconds"` over the limit, warns that "IP addresses may be blocked if behavior is observed that places unnecessary strain on the platform", and says "It is not meant as the source for all units for vendor applications. In this situation the vendor must download data and then be the source of all possible units for the application." No AI/ML, scraping, automated-access or non-commercial clause. Naming: "Energi Data Service (Energinet)" as plain text with the credit line below; no Energinet logo. This skill is not affiliated with or endorsed by Energinet.

**Attribution (CC BY 4.0):** the terms suggest "Source: Energinet (www.energidataservice.dk)." Add what you changed (for example "averaged over 8 15-minute slots") and do not suggest that Energinet endorses the result. Blocks 1 and 3 print such a line.

## Quick summary

- **No scraping.** `GET https://api.energidataservice.dk/dataset/DayAheadPrices?start=StartOfDay&end=StartOfDay&endOffset=P2D&filter={"PriceArea":["DK1","DK2"]}&sort=TimeUTC&limit=0` returns today's and (once published) tomorrow's day-ahead prices for both Danish price areas in one call. No key, `access-control-allow-origin: *`. Metadata: `GET /meta/dataset/DayAheadPrices`.
- **Answer (run 2026-11-17 00:01 UTC = 01:01 Danish time):** tomorrow, 18 November, was **not published yet** (0 of 96 slots), so block 1 fell back to the rest of 17 November. **Cheapest 2-hour window: 22:00-00:00 Danish time in both areas, DK1 mean 160.92 EUR/MWh (1.203 DKK/kWh), DK2 170.57 EUR/MWh (1.275 DKK/kWh)**, against day means of 209.17 and 225.69 EUR/MWh. Cheapest single slot: DK1 23:45 at 134.23 EUR/MWh, DK2 23:30 at 146.91. Dearest: DK1 09:15 at 264.22, DK2 08:45 at 276.08. 1 h and 3 h windows: block 3.
- **"Tomorrow" is a Danish date, and it does not exist before about 13:00 CET.** `StartOfDay` is Danish midnight. At 23:54 UTC on 16 November it was already 17 November in Denmark, so `start=StartOfDay&startOffset=P1D` asked for 18 November and got HTTP 200 with `"total":0`. The dataset note says to poll "every five minutes or so between 13:00 and 14:00 CET"; `lastDataUpdate` read `2026-11-16T13:07:28`. Count the slots (96, or 92/100 on daylight-saving days) before answering.
- **15-minute prices.** Since 2025-10-01 the dataset has 15-minute resolution (`"resolution": "15 minutes (PT15M)"`), so an hour is 4 rows and a 2-hour appliance run is 8 consecutive rows. The older hourly dataset `Elspotprices` stopped at 2025-09-30 and returns `total 0` for today, silently.
- **Rate limit: 1 call per minute from one IP on DayAheadPrices.** Each counted answer carries `remainingcalls: 0` and `totalcalls: 1`; a second, different DayAheadPrices URL within the minute got HTTP 429 `{"statusCode": 429, "message": "Rate limit is exceeded. Try again in 58 seconds."}`, and 400 answers count too. Repeating the exact same URL within the minute returned HTTP 200 without quota headers. The metadata endpoint showed `totalcalls: 5`. Fetch both areas and both days in one call, wait the seconds the 429 names, and cache.

## What works

### 1. Cheapest window for one appliance, tomorrow or the rest of today (browser)

`on_eds_tab()` opens one logged-out API metadata page (`/meta/dataset/DayAheadPrices`), so `fetch()` runs on the API's own origin. `get()` returns parsed JSON on HTTP 200, waits the seconds a 429 names (once), waits 60 s once on 5xx or a network error, and raises on anything else. One DayAheadPrices call covers both areas and both days, with explicit Danish dates. The block answers for tomorrow when all its slots are there; otherwise it says so and plans over the slots of today that have not started. `cheapest_window()` never bridges a gap in the data. 2 `fetch()` calls.

```python
import json, math, time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

AREAS = ["DK1", "DK2"]  # DK1 is west of the Great Belt, DK2 east of it (dataset column description)
RUN_HOURS = 2.0         # how long the appliance runs; rounded up to whole 15-minute slots

SITE = "https://api.energidataservice.dk"
DK = ZoneInfo("Europe/Copenhagen")  # start/end are read as Danish local time; TimeDK is Danish local time
SLOT = timedelta(minutes=15)        # DayAheadPrices resolution since 2025-10-01 (meta: "15 minutes (PT15M)")

def on_eds_tab():
    """fetch() runs from a logged-out api.energidataservice.dk JSON page (the dataset's metadata). Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/meta/dataset/DayAheadPrices")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"DayAheadPrices"' not in body:
        raise RuntimeError(f"api.energidataservice.dk did not serve the DayAheadPrices metadata (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__e = window.__e || {}; const id = String(Math.random()).slice(2); window.__e[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__e[id] = {status: r.status, type: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__e[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__e[%s]; if (v) delete window.__e[%s]; return v; })()"""

def get(path, timeout=60):
    """GET SITE+path in the tab -> parsed JSON. DayAheadPrices allows 1 call per minute per IP (header totalcalls: 1),
    so on HTTP 429 it waits the "Try again in X seconds" the API names (+2 s), once, and stops if that is over 120 s;
    one 60 s wait on 5xx or a network error; raises on anything else (400 "Invalid json in filter", 404 "dataset not found ...", plain text)."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{path}: no answer after {timeout}s")
            time.sleep(0.2)
        if r["status"] == 200 and "json" in r["type"]:
            return json.loads(r["text"])
        if attempt == 0 and r["status"] == 429:
            msg = json.loads(r["text"]).get("message", "")  # "Rate limit is exceeded. Try again in 32 seconds."
            wait = int(msg.split("Try again in ")[1].split()[0]) if "Try again in " in msg else 60
            if wait > 120:
                raise RuntimeError(f"{path}: HTTP 429 asks to wait {wait}s (over 120 s): stopping")
            time.sleep(wait + 2)
            continue
        if attempt == 0 and r["status"] in (0, 500, 502, 503, 504):
            time.sleep(60)
            continue
        raise RuntimeError(f"{path}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")

def slots_in_day(d):
    """15-minute slots in a Danish calendar day: 96, or 92/100 on the daylight-saving switch days."""
    n = d + timedelta(days=1)
    a, b = (datetime(x.year, x.month, x.day, tzinfo=DK).astimezone(timezone.utc) for x in (d, n))
    return int((b - a) / SLOT)  # in UTC: subtracting two times that share one tzinfo ignores the DST change

def cheapest_window(rows, k):
    """rows sorted by time -> (mean EUR/MWh, mean DKK/MWh, first row, last row) of the cheapest k consecutive slots."""
    best = None
    for i in range(len(rows) - k + 1):
        w = rows[i:i + k]
        t = [datetime.fromisoformat(x["TimeUTC"]) for x in w]
        if any(b - a != SLOT for a, b in zip(t, t[1:])):
            continue  # a gap in the data: never bridge it
        eur = sum(x["DayAheadPriceEUR"] for x in w) / k
        if best is None or eur < best[0]:
            best = (eur, sum(x["DayAheadPriceDKK"] for x in w) / k, w[0], w[-1])
    return best

on_eds_tab()
now = datetime.now(timezone.utc)
today = now.astimezone(DK).date()
tomorrow = today + timedelta(days=1)
k = math.ceil(RUN_HOURS * 4)

meta = get("/meta/dataset/DayAheadPrices")
if meta.get("resolution") != "15 minutes (PT15M)":
    raise RuntimeError(f"resolution is now {meta.get('resolution')!r}, not 15 minutes: re-check the window maths")
time.sleep(1)
flt = json.dumps({"PriceArea": AREAS}, separators=(",", ":"))
q = f"/dataset/DayAheadPrices?start={today}&end={today + timedelta(days=2)}&filter={flt}&sort=TimeUTC&limit=0"
d = get(q)
recs = d["records"]
if d["total"] != len(recs):
    raise RuntimeError(f"total {d['total']} but {len(recs)} records returned: stop")

print(f"Now {now:%Y-%m-%d %H:%M} UTC = {now.astimezone(DK):%Y-%m-%d %H:%M} Danish time; "
      f"dataset lastDataUpdate {meta['lastDataUpdate']}, dataTo {meta['dataTo']}")
target, ahead_only = tomorrow, False
# distinct UTC slots, so a duplicated row cannot hide a missing one
counts = {(a, dd): len({x["TimeUTC"] for x in recs if x["PriceArea"] == a and x["TimeDK"][:10] == str(dd)})
          for a in AREAS for dd in (today, tomorrow)}
dupes = len(recs) - len({(x["PriceArea"], x["TimeUTC"]) for x in recs})
if dupes:
    raise RuntimeError(f"{dupes} duplicated (PriceArea, TimeUTC) rows in the answer: stop")
if any(counts[(a, tomorrow)] != slots_in_day(tomorrow) for a in AREAS):
    print(f"Tomorrow ({tomorrow}) is NOT published yet: {[counts[(a, tomorrow)] for a in AREAS]} of "
          f"{slots_in_day(tomorrow)} slots per area. The dataset note says to poll about every 5 minutes "
          "between 13:00 and 14:00 CET for tomorrow's prices.")
    target, ahead_only = today, True
    print(f"Falling back to the rest of today ({today}), slots that have not started yet.")
for a in AREAS:
    if counts[(a, target)] != slots_in_day(target):
        raise RuntimeError(f"{a} {target}: {counts[(a, target)]} of {slots_in_day(target)} slots: incomplete day, stop")

print(f"\nCheapest {k} consecutive 15-minute slots ({k / 4:g} h) on {target}, wholesale day-ahead price:")
for a in AREAS:
    rows = [x for x in recs if x["PriceArea"] == a and x["TimeDK"][:10] == str(target)]
    day_mean = sum(x["DayAheadPriceEUR"] for x in rows) / len(rows)
    if ahead_only:
        rows = [x for x in rows if datetime.fromisoformat(x["TimeUTC"]).replace(tzinfo=timezone.utc) >= now]
    best = cheapest_window(rows, k)
    if best is None:
        print(f"  {a}: no {k} consecutive slots left on {target} ({len(rows)} slots considered): wait for tomorrow's prices")
        continue
    eur, dkk, first, last = best
    end = (datetime.fromisoformat(last["TimeUTC"]).replace(tzinfo=timezone.utc) + SLOT).astimezone(DK)  # DST-safe
    lo = min(rows, key=lambda x: x["DayAheadPriceEUR"])
    hi = max(rows, key=lambda x: x["DayAheadPriceEUR"])
    print(f"  {a}: start {first['TimeDK'][11:16]}, end {end:%H:%M} Danish time; mean {eur:.2f} EUR/MWh = "
          f"{dkk / 1000:.3f} DKK/kWh (day mean {day_mean:.2f} EUR/MWh)")
    print(f"       cheapest slot {lo['TimeDK'][11:16]} {lo['DayAheadPriceEUR']:.2f}, dearest {hi['TimeDK'][11:16]} "
          f"{hi['DayAheadPriceEUR']:.2f} EUR/MWh; {len(rows)} slots considered")
print(f"\nSource: Energinet (www.energidataservice.dk), dataset DayAheadPrices, {SITE}{q}, "
      f"accessed {now:%d %B %Y %H:%M} UTC. Licence CC BY 4.0. Changes: averaged over {k} 15-minute slots; "
      "DKK/MWh divided by 1000 for DKK/kWh. Not endorsed by Energinet.")
```

Output (from the run on 2026-11-17, 00:01 UTC; the first run at 2026-11-16 23:51 UTC printed the same windows and prices, with 92 slots ahead instead of 91):

```text
Now 2026-11-17 00:01 UTC = 2026-11-17 01:01 Danish time; dataset lastDataUpdate 2026-11-16T13:07:28, dataTo 2026-11-17T23:45:00
Tomorrow (2026-11-18) is NOT published yet: [0, 0] of 96 slots per area. The dataset note says to poll about every 5 minutes between 13:00 and 14:00 CET for tomorrow's prices.
Falling back to the rest of today (2026-11-17), slots that have not started yet.

Cheapest 8 consecutive 15-minute slots (2 h) on 2026-11-17, wholesale day-ahead price:
  DK1: start 22:00, end 00:00 Danish time; mean 160.92 EUR/MWh = 1.203 DKK/kWh (day mean 209.17 EUR/MWh)
       cheapest slot 23:45 134.23, dearest 09:15 264.22 EUR/MWh; 91 slots considered
  DK2: start 22:00, end 00:00 Danish time; mean 170.57 EUR/MWh = 1.275 DKK/kWh (day mean 225.69 EUR/MWh)
       cheapest slot 23:30 146.91, dearest 08:45 276.08 EUR/MWh; 91 slots considered

Source: Energinet (www.energidataservice.dk), dataset DayAheadPrices, https://api.energidataservice.dk/dataset/DayAheadPrices?start=2026-11-17&end=2026-11-19&filter={"PriceArea":["DK1","DK2"]}&sort=TimeUTC&limit=0, accessed 17 November 2026 00:01 UTC. Licence CC BY 4.0. Changes: averaged over 8 15-minute slots; DKK/MWh divided by 1000 for DKK/kWh. Not endorsed by Energinet.
```

### 2. robots.txt, terms, and query mistakes (browser)

5 page loads and 8 in-page `fetch()` calls in the same tab, plus one retry per HTTP 429 (5 in the run below; run within a minute of block 1, the first probe gets a 429 too). `raw()` does not retry anything but a 429, and reports when it waited. The probes show which mistakes are silent.

```python
import json, time

SITE = "https://api.energidataservice.dk"
PAUSE = 2  # between calls; a 429 names its own wait, which raw() honours once

START_JS = """(() => { window.__e = window.__e || {}; const id = String(Math.random()).slice(2); window.__e[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__e[id] = {status: r.status, type: r.headers.get('content-type') || '',
      quota: [r.headers.get('remainingcalls'), r.headers.get('totalcalls')], text: await r.text()}; })
    .catch(e => { window.__e[id] = {status: 0, type: '', quota: [null, null], text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__e[%s]; if (v) delete window.__e[%s]; return v; })()"""

def raw(path):
    """One in-page GET -> status, content type, quota headers, body. On HTTP 429 it waits the seconds the message
    names (+2, at most 120 s) and asks once more, and reports that it did."""
    note = ""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > 60:
                raise RuntimeError(f"{path}: no answer after 60s")
            time.sleep(0.2)
        time.sleep(PAUSE)
        if r["status"] == 429 and attempt == 0:
            wait = int(json.loads(r["text"])["message"].split("Try again in ")[1].split()[0])
            if wait > 120:
                raise RuntimeError(f"{path}: HTTP 429 asks to wait {wait}s (over 120 s): stopping")
            note = f"[429 'Try again in {wait} seconds', waited] "
            time.sleep(wait + 2)
            continue
        break
    r["note"] = note
    return r

def brief(r):
    q = r["quota"]
    out = r["note"] + f"HTTP {r['status']}" + (f" (remainingcalls {q[0]}/totalcalls {q[1]})" if q[0] is not None else "")
    if "json" not in r["type"]:
        return out + f" {r['type'].split(';')[0] or 'no type'} {' '.join(r['text'].split())[:90]!r}"
    d = json.loads(r["text"])
    if "records" in d:
        days = sorted({x.get("TimeDK", "")[:10] for x in d["records"]})
        areas = sorted({x.get("PriceArea", "") for x in d["records"]})
        return out + f" total {d['total']}, areas {areas}, days {days}"
    return out + " " + json.dumps(d)[:140]

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, " ".join((js("document.body ? document.body.innerText : ''") or "").split())

try:
    here = js("location.origin")
except Exception:
    here = None
if here != SITE:  # never navigate a tab from another task: open our own
    new_tab("about:blank")

for url in ("https://api.energidataservice.dk/robots.txt", "https://www.energidataservice.dk/robots.txt"):
    st, txt = page(url)
    print(f"{url} HTTP {st}: {txt[:90]!r}")

st, txt = page("https://www.energidataservice.dk/terms-and-conditions")
for s in ("subject to the conditions of Creative Commons CC-BY 4.0",
          "Users may copy, change and distribute data freely, even for commercial purposes.",
          "Users must give appropriate credit and indicate if data has been changed.",
          "Source: Energinet (www.energidataservice.dk).",
          "Energinet stores the used IP address for 3 months from each API call."):
    print(f"terms HTTP {st} {'has' if s in txt else 'LACKS'}: {s!r}")
st, txt = page("https://www.energidataservice.dk/guides/api-guides")
for s in ("enables users free of charge to download data",
          "It is not meant as the source for all units for vendor applications.",
          "dataset‑specific (differentiated) rate limits",
          'HTTP 429 - "Rate limit is exceeded. Try again in X seconds"',
          "IP addresses may be blocked"):
    print(f"API guide HTTP {st} {'has' if s in txt else 'LACKS'}: {s!r}")

page(SITE + "/meta/dataset/DayAheadPrices")  # back to an API JSON page for fetch()
print()
F = '&filter={"PriceArea":["%s"]}'
for label, path in (
    ("tomorrow, start=StartOfDay&startOffset=P1D", "/dataset/DayAheadPrices?start=StartOfDay&startOffset=P1D" + F % "DK1"),
    ("today, start=StartOfDay&end=...P1D       ", "/dataset/DayAheadPrices?start=StartOfDay&end=StartOfDay&endOffset=P1D" + F % "DK1" + "&limit=0"),
    ("lowercase area dk1                       ", "/dataset/DayAheadPrices?start=StartOfDay" + F % "dk1"),
    ("unknown area DK3                         ", "/dataset/DayAheadPrices?start=StartOfDay" + F % "DK3"),
    ("filter that is not JSON                  ", "/dataset/DayAheadPrices?start=StartOfDay&filter=PriceArea:DK1"),
    ("sort by a column that does not exist     ", "/dataset/DayAheadPrices?start=StartOfDay&sort=Price"),
    ("misspelled dataset DayAheadPrice         ", "/dataset/DayAheadPrice?start=StartOfDay"),
    ("old hourly dataset Elspotprices, today   ", "/dataset/Elspotprices?start=StartOfDay" + F % "DK1"),
):
    print(f"{label} {brief(raw(path))}")
```

Output (from the run on 2026-11-16, 23:54-00:00 UTC):

```text
https://api.energidataservice.dk/robots.txt HTTP 404: '{ "statusCode": 404, "message": "Resource not found" }'
https://www.energidataservice.dk/robots.txt HTTP 404: 'This www.energidataservice.dk page can’t be found No webpage was found for the web address'
terms HTTP 200 has: 'subject to the conditions of Creative Commons CC-BY 4.0'
terms HTTP 200 has: 'Users may copy, change and distribute data freely, even for commercial purposes.'
terms HTTP 200 has: 'Users must give appropriate credit and indicate if data has been changed.'
terms HTTP 200 has: 'Source: Energinet (www.energidataservice.dk).'
terms HTTP 200 has: 'Energinet stores the used IP address for 3 months from each API call.'
API guide HTTP 200 has: 'enables users free of charge to download data'
API guide HTTP 200 has: 'It is not meant as the source for all units for vendor applications.'
API guide HTTP 200 has: 'dataset‑specific (differentiated) rate limits'
API guide HTTP 200 has: 'HTTP 429 - "Rate limit is exceeded. Try again in X seconds"'
API guide HTTP 200 has: 'IP addresses may be blocked'

tomorrow, start=StartOfDay&startOffset=P1D HTTP 200 (remainingcalls 0/totalcalls 1) total 0, areas [], days []
today, start=StartOfDay&end=...P1D        [429 'Try again in 58 seconds', waited] HTTP 200 (remainingcalls 0/totalcalls 1) total 96, areas ['DK1'], days ['2026-11-17']
lowercase area dk1                        [429 'Try again in 58 seconds', waited] HTTP 200 (remainingcalls 0/totalcalls 1) total 96, areas ['DK1'], days ['2026-11-17']
unknown area DK3                          [429 'Try again in 58 seconds', waited] HTTP 200 (remainingcalls 0/totalcalls 1) total 0, areas [], days []
filter that is not JSON                   [429 'Try again in 58 seconds', waited] HTTP 400 (remainingcalls 0/totalcalls 1) text/plain 'Invalid json in filter'
sort by a column that does not exist      [429 'Try again in 58 seconds', waited] HTTP 400 (remainingcalls 0/totalcalls 1) text/plain 'Invalid key in sort expression: [Price]'
misspelled dataset DayAheadPrice          HTTP 404 (remainingcalls 2/totalcalls 3) text/plain 'dataset not found DayAheadPrice'
old hourly dataset Elspotprices, today    HTTP 200 (remainingcalls 0/totalcalls 1) total 0, areas [], days []
```

The first run of this block (2026-11-16, 23:53 UTC) paused a fixed 12 s between calls and did not retry: 4 of the 6 DayAheadPrices probes after the first got HTTP 429 ("Try again in 48 seconds", then 36, 23, 11), which is how the 1-call-per-minute limit showed up.

### 3. Same plan for 1, 2 and 3 hours with Python urllib, robots check for every agent, disk cache (no browser)

This block sends a descriptive User-Agent; Python's default `urllib` User-Agent was not tried for API calls (the robots fetch inside `rp.read()` uses it). It asks with the documented dynamic timestamps (`start=StartOfDay&end=StartOfDay&endOffset=P2D`), caches each complete Danish day as a JSON file, and asks the API again at most every 5 minutes while tomorrow is missing, which is the polling interval the dataset note gives. Run with an empty cache.

```python
import json, math, os, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

AREAS = ["DK1", "DK2"]
HOURS = [1, 2, 3]  # appliance run times to plan for: washing machine, dishwasher, EV top-up...

API = "https://api.energidataservice.dk"
UA = "energi-data-service-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/energi-data-service-skill"
CACHE = os.path.expanduser(CACHE_DIR)
POLL = 300  # the dataset note: poll "every five minutes or so between 13:00 and 14:00 CET"
DK = ZoneInfo("Europe/Copenhagen")
SLOT = timedelta(minutes=15)
calls = 0

def get(path):
    """GET API+path -> parsed JSON. DayAheadPrices answers 1 call per minute per IP; on 429 waits the seconds the
    message names (+2), once, unless that is over 120 s. Exits on anything else (400/404 are plain text)."""
    global calls
    for attempt in range(2):
        calls += 1
        try:
            req = urllib.request.Request(API + path, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")
            if e.code == 429 and attempt == 0 and "Try again in " in body:
                wait = int(body.split("Try again in ")[1].split()[0])
                if wait > 120:
                    sys.exit(f"HTTP 429 {path}: asks to wait {wait}s (over 120 s): stopping")
                time.sleep(wait + 2)
                continue
            sys.exit(f"HTTP {e.code} {path}: {body[:200]}")
        except OSError as e:
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{path}: {e}")

def slots_in_day(d):
    n = d + timedelta(days=1)
    a, b = (datetime(x.year, x.month, x.day, tzinfo=DK).astimezone(timezone.utc) for x in (d, n))
    return int((b - a) / SLOT)  # 96, or 92/100 on daylight-saving days

def load(day):
    try:
        return json.load(open(os.path.join(CACHE, f"{day}.json")))
    except (OSError, ValueError):
        return None

def prices(day, now):
    """{area: [rows sorted by time]} for one Danish day, or None if it is not published. A complete day is cached
    on disk; one API call covers today and tomorrow, and it is repeated at most every POLL seconds."""
    if (c := load(day)) is not None:
        return c
    stamp = os.path.join(CACHE, "last_call")
    if os.path.exists(stamp) and now.timestamp() - os.path.getmtime(stamp) < POLL:
        return None  # asked less than POLL s ago and the day was not complete then
    flt = json.dumps({"PriceArea": AREAS}, separators=(",", ":"))
    d = get("/dataset/DayAheadPrices?start=StartOfDay&end=StartOfDay&endOffset=P2D"
            f"&filter={urllib.parse.quote(flt)}&sort=TimeUTC&limit=0")
    os.makedirs(CACHE, exist_ok=True)
    open(stamp, "w").close()
    by = {}
    for x in d["records"]:
        by.setdefault(x["TimeDK"][:10], {}).setdefault(x["PriceArea"], []).append(x)
    for dd, areas in by.items():
        n = slots_in_day(datetime.fromisoformat(dd).date())
        # complete = every area has n rows on n distinct UTC slots (a duplicate cannot hide a missing slot)
        if sorted(areas) == sorted(AREAS) and all(len(v) == n == len({x["TimeUTC"] for x in v}) for v in areas.values()):
            json.dump(areas, open(os.path.join(CACHE, f"{dd}.json"), "w"))
    return load(day)

def cheapest(rows, k):
    best = None
    for i in range(len(rows) - k + 1):
        w = rows[i:i + k]
        if any(datetime.fromisoformat(b["TimeUTC"]) - datetime.fromisoformat(a["TimeUTC"]) != SLOT
               for a, b in zip(w, w[1:])):
            continue
        eur = sum(x["DayAheadPriceEUR"] for x in w) / k
        if best is None or eur < best[0]:
            t0, t1 = (datetime.fromisoformat(x["TimeUTC"]).replace(tzinfo=timezone.utc) for x in (w[0], w[-1]))
            best = (eur, t0.astimezone(DK).strftime("%H:%M"), (t1 + SLOT).astimezone(DK).strftime("%H:%M"))  # DST-safe
    return best

# robots.txt: both hosts answer 404. RobotFileParser.read() treats a 4xx other than 401/403 as "allow all"
# (RFC 9309, section 2.3.1.3: an unavailable robots.txt means the crawler MAY access any resources).
for host in ("https://api.energidataservice.dk", "https://www.energidataservice.dk"):
    try:
        urllib.request.urlopen(urllib.request.Request(host + "/robots.txt", headers={"User-Agent": UA}), timeout=30)
        sys.exit(f"{host}/robots.txt now exists: read it before going on")
    except urllib.error.HTTPError as e:
        print(f"{host}/robots.txt: HTTP {e.code}")
    rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
    rp.read()
    for p in ("/dataset/DayAheadPrices", "/meta/dataset/DayAheadPrices") if "api." in host else ("/terms-and-conditions",):
        ok = all(rp.can_fetch(a, host + p) for a in AGENTS)
        print(f"  robots {p:<30} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
        if not ok:
            sys.exit("robots.txt now disallows a path this skill uses: stop")

for run in (1, 2):
    n0, now = calls, datetime.now(timezone.utc)
    today = now.astimezone(DK).date()
    tomorrow = today + timedelta(days=1)
    p, day, rest = prices(tomorrow, now), tomorrow, False
    if p is None:
        p, day, rest = prices(today, now), today, True
    if p is None:
        sys.exit("neither today nor tomorrow is complete in the API: stop")
    print(f"\nrun {run}, {now:%H:%M:%S} UTC ({now.astimezone(DK):%H:%M} Danish time): "
          + (f"tomorrow ({tomorrow}) not published yet, rest of {today}" if rest else f"tomorrow, {tomorrow}"))
    for a in AREAS:
        rows = p[a]
        if rest:
            rows = [x for x in rows if datetime.fromisoformat(x["TimeUTC"]).replace(tzinfo=timezone.utc) >= now]
        out = []
        for h in HOURS:
            best = cheapest(rows, math.ceil(h * 4))
            out.append(f"{h} h {best[1]}-{best[2]} {best[0]:.2f}" if best else f"{h} h: not enough consecutive slots left")
        print(f"  {a} cheapest window, mean EUR/MWh: " + "; ".join(out))
    print(f"  network calls this run: {calls - n0} (cache {CACHE_DIR})")

print("\nSource: Energinet (www.energidataservice.dk), dataset DayAheadPrices, CC BY 4.0. Changes: 15-minute prices "
      "averaged over each window. Not endorsed by Energinet.")
```

Output (from the run on 2026-11-17, 00:02 UTC):

```text
https://api.energidataservice.dk/robots.txt: HTTP 404
  robots /dataset/DayAheadPrices        allowed for all 11 agents
  robots /meta/dataset/DayAheadPrices   allowed for all 11 agents
https://www.energidataservice.dk/robots.txt: HTTP 404
  robots /terms-and-conditions          allowed for all 11 agents

run 1, 00:02:23 UTC (01:02 Danish time): tomorrow (2026-11-18) not published yet, rest of 2026-11-17
  DK1 cheapest window, mean EUR/MWh: 1 h 23:00-00:00 150.55; 2 h 22:00-00:00 160.92; 3 h 21:00-00:00 167.97
  DK2 cheapest window, mean EUR/MWh: 1 h 23:00-00:00 156.40; 2 h 22:00-00:00 170.57; 3 h 21:00-00:00 177.97
  network calls this run: 1 (cache ~/.cache/energi-data-service-skill)

run 2, 00:02:23 UTC (01:02 Danish time): tomorrow (2026-11-18) not published yet, rest of 2026-11-17
  DK1 cheapest window, mean EUR/MWh: 1 h 23:00-00:00 150.55; 2 h 22:00-00:00 160.92; 3 h 21:00-00:00 167.97
  DK2 cheapest window, mean EUR/MWh: 1 h 23:00-00:00 156.40; 2 h 22:00-00:00 170.57; 3 h 21:00-00:00 177.97
  network calls this run: 0 (cache ~/.cache/energi-data-service-skill)

Source: Energinet (www.energidataservice.dk), dataset DayAheadPrices, CC BY 4.0. Changes: 15-minute prices averaged over each window. Not endorsed by Energinet.
```

### 4. curl, headers and the rate limit

```bash
A=https://api.energidataservice.dk
# DayAheadPrices answers 1 distinct call per minute per IP: start this at least 60 s after any other call to it
F='filter=%7B%22PriceArea%22:%5B%22DK1%22%5D%7D'   # filter={"PriceArea":["DK1"]}, URL-encoded
# the 3 cheapest DK1 slots from the start of today (Danish time) to 2 days later
curl -sS --fail "$A/dataset/DayAheadPrices?start=StartOfDay&end=StartOfDay%2BP2D&$F&sort=DayAheadPriceDKK%20ASC&limit=3" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); [print(r["TimeDK"], r["PriceArea"], r["DayAheadPriceEUR"], "EUR/MWh", round(r["DayAheadPriceDKK"]/1000, 3), "DKK/kWh") for r in d["records"]]'
# the same URL again at once: answered (cache-control max-age=60), no quota headers
curl -sS -D - -o /dev/null "$A/dataset/DayAheadPrices?start=StartOfDay&end=StartOfDay%2BP2D&$F&sort=DayAheadPriceDKK%20ASC&limit=3" \
  | tr -d '\r' | grep -iE '^(HTTP/|(cache-control|access-control-allow-origin|remainingcalls|totalcalls|x-cache-status):)' | tr '\n' ' '; echo
# a different DayAheadPrices URL within the same minute: 429, with the wait in the message
curl -sS -w ' <- HTTP %{http_code}\n' "$A/dataset/DayAheadPrices?start=StartOfDay&$F&limit=1"
# metadata is a separate quota: what is published and when it last changed
curl -sS --fail "$A/meta/dataset/DayAheadPrices" \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print({k: d[k] for k in ("resolution", "updateFrequency", "dataFrom", "dataTo", "lastDataUpdate")})'
```

Output (from the run on 2026-11-17, 00:04 UTC):

```text
2026-11-17T23:45:00 DK1 134.229996 EUR/MWh 1.003 DKK/kWh
2026-11-17T23:30:00 DK1 144.259995 EUR/MWh 1.078 DKK/kWh
2026-11-17T22:45:00 DK1 159.770004 EUR/MWh 1.194 DKK/kWh
HTTP/2 200  cache-control: public, must-revalidate, max-age=59 access-control-allow-origin: * x-cache-status: MISS 
{ "statusCode": 429, "message": "Rate limit is exceeded. Try again in 59 seconds." } <- HTTP 429
{'resolution': '15 minutes (PT15M)', 'updateFrequency': 'P1D', 'dataFrom': '2025-10-01T00:00:00', 'dataTo': '2026-11-17T23:45:00', 'lastDataUpdate': '2026-11-16T13:07:28'}
```

A first run of this block started about 40 s after block 3's call: its first curl got HTTP 429 and `--fail` left the Python one-liner nothing to parse. The `end=StartOfDay%2BP2D` form in this block is not in the API guide; it returned the same 17 November rows as the documented `end=StartOfDay&endOffset=P2D` (block 2 checks `endOffset`), but blocks 1 and 3 use explicit dates and `endOffset`.

## Fields (DayAheadPrices and its metadata)

| Call | JSON path | Notes |
|---|---|---|
| `/dataset/DayAheadPrices?...` | `total`, `filters`, `sort`, `limit`, `dataset`, `records[]` | `total` is the number of rows returned (3 with `limit=3`, 192 for two areas over one day with `limit=0`). `limit=0` returns all rows; "If neither "start" nor "limit" is provided a default value of 100 is used" (API guide) |
| `records[].TimeUTC`, `records[].TimeDK` | `"2026-11-17T22:45:00"`, `"2026-11-17T23:45:00"` | the "from" time of each 15-minute slot, in UTC and in Danish local time; no zone suffix on either |
| `records[].PriceArea` | `"DK1"` | DK1 is west of the Great Belt, DK2 east of it. The metadata lists DK1, DK2, DE, NO2, SE3, SE4. The filter matched lowercase `dk1` (96 rows) |
| `records[].DayAheadPriceEUR` | `134.229996` | EUR per MWh |
| `records[].DayAheadPriceDKK` | `1003.449758` | DKK per MWh, "calculated based on the Day-Ahead Price (EUR) and the Euro exchange rate from Danmarks Nationalbank. It may therefore deviate from Danish Day-Ahead prices seen elsewhere." Divide by 1000 for DKK/kWh |
| `/meta/dataset/DayAheadPrices` | `resolution`, `updateFrequency`, `dataFrom`, `dataTo`, `lastDataUpdate`, `columns[]`, `comment` | `"15 minutes (PT15M)"`, `"P1D"`, `"2025-10-01T00:00:00"`, `"2026-11-17T23:45:00"` (the last published slot, Danish time), `"2026-11-16T13:07:28"`; `comment` holds the 13:00-14:00 CET polling note |
| response headers | `remainingcalls`, `totalcalls`, `cache-control`, `access-control-allow-origin` | `0`, `1` on DayAheadPrices (`3`/`5` and `2`/`3` were seen on metadata and on an unknown dataset); `public, must-revalidate, max-age=60`; `*`. The API also sets `INGRESSCOOKIE` and a 30-day `anon-id` cookie; the blocks send no cookies |

## Gotchas

- **Check that tomorrow is complete.** A day that is not published yet is HTTP 200 with `total 0`, and a half-loaded day would be HTTP 200 with too few rows. Block 1 compares the count per area with the number of 15-minute slots in that Danish day (96; 92 on the March switch and 100 on the October switch). Compute that in UTC: subtracting two `datetime`s that share one `ZoneInfo` ignores the clock change.
- **US evening is already tomorrow in Denmark.** At Danish midnight (23:00 UTC in winter, 22:00 UTC in summer) `StartOfDay` moves to the next Danish day. A user in the US asking on the evening of 16 November for "tomorrow" may mean 17 November, which Denmark already calls today. Say which Danish date the answer is for.
- **Windows stop at midnight.** Blocks 1 and 3 search one Danish day. On 17 November the cheapest windows ended at 00:00, so a cheaper run across midnight may exist once 18 November is published; join the two days' rows (the gap check in `cheapest_window()` still applies) to search across it.
- **1 call per minute per dataset, from one IP.** `totalcalls: 1` on DayAheadPrices; a 400 (`Invalid json in filter`) still used the minute. The 429 message names the wait (58 s right after a call). The same URL repeated within the minute came back HTTP 200 with no quota headers. The API guide says the limits "may be adjusted over time" and that IPs can be blocked for "unnecessary strain": ask once for both areas and days, and cache.
- **Silent filters.** An unknown area (`DK3`) is HTTP 200 with `total 0`. `dk1` matched DK1. A filter that is not JSON is a plain-text HTTP 400 `Invalid json in filter`; an unknown sort column is HTTP 400 `Invalid key in sort expression: [Price]`; a misspelled dataset is HTTP 404 `dataset not found DayAheadPrice`. Check `total` and the areas you got back.
- **Wholesale price only.** DayAheadPrices is the day-ahead market price. Subscriptions, tariffs and fees are in a separate dataset, `DatahubPricelist` ("prices for the electrical power retail market in Denmark per supplier per charge type (subscriptions, tariffs, and fees)", with hourly `Price1`-`Price24` columns), so the cheapest day-ahead window is not necessarily the cheapest window on a household bill. This skill does not add tariffs.
- **The DKK column is derived.** It is the EUR price converted at Danmarks Nationalbank's rate, and the metadata warns it may differ from Danish prices shown elsewhere. Rank by EUR or DKK, but say which.
- **Elspotprices is the old dataset.** Its metadata says "This dataset is no longer updated. For data after 2025-09-30 see Day-Ahead Prices", and it returns `total 0` for today without an error. Old code and tutorials that use `Elspotprices` and `HourDK` silently return nothing.
- **Your IP is stored.** The terms say Energinet keeps the calling IP address for 3 months from each API call. For an app with many users, the API guide asks the vendor to download the data and serve it, not to send each user to the API.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the JSON, never the title.

## What does not work

- **Tomorrow before the daily publication**: on 2026-11-17 at 01:01 Danish time, 18 November had 0 rows. Wait for the 13:00-14:00 CET window the dataset note names.
- **Fast polling or many small calls**: more than one distinct DayAheadPrices call per minute from one IP gets HTTP 429.
- **Not tested:** a full "tomorrow" answer after publication (this run fell in the gap before it), daylight-saving days (the 92/100 slot count is computed, not observed), combining tariffs from `DatahubPricelist`, the CSV/XLSX download URLs, and areas other than DK1 and DK2.
