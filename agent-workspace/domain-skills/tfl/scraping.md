# TfL Unified API - Is a Tube Line Running Normally, and the Next Three Trains at a Station (Transport for London open data, official API)

Field-tested against api.tfl.gov.uk on 2026-11-12 (23:27-23:32 GMT, a Thursday) using a fresh Browser Use cloud browser (logged out) plus Python urllib and `curl` from a laptop. About 14 browser page loads and 30 in-page `fetch()` calls, about 14 curl calls and 3 urllib calls, all serial at 1 s or more spacing: every call was HTTP 200 except the deliberate 404 probes below and two Cloudflare 403s for Python's default User-Agent (see Gotchas). No 429, no challenge on api.tfl.gov.uk, no key, no login.

robots.txt (checked 2026-11-12, curl and the cloud browser): https://api.tfl.gov.uk/robots.txt answers HTTP 404 with a JSON `EntityNotFoundException` body, so there are no rules for the API host (RFC 9309 section 2.3.1.3: on a 400-499 robots.txt the crawler "MAY access any resources"). https://tfl.gov.uk/robots.txt (read in the cloud browser; curl got a Cloudflare 403 challenge) has `User-agent: AhrefsBot` / `Disallow: /` and one `User-agent: *` group with `Allow: /` that disallows `/plan-a-journey/results*`, `/search/`, `/traffic/status*?`, `/journeyplanner`, `/statusupdates`, `/disambiguation` and some driving and maintenance pages. https://api-portal.tfl.gov.uk/robots.txt answers HTTP 404 (HTML), so no rules there either. This skill reads only the API plus the licence page and the API portal home page, none of them disallowed. No named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall to `*` (allowed). Terms: the Transport Data Service licence (https://tfl.gov.uk/corporate/terms-and-conditions/transport-data-service) is "based on version 2.0 of the Open Government Licence"; you may "Exploit the Information commercially and non-commercially"; you must include "'Powered by TfL Open Data'" and "'Contains OS data © Crown copyright and database rights 2016' and Geomni UK Map data © and database rights [2019]", follow TfL's "design and branding guidelines", and "Limit traffic requests up to a maximum of 500 calls per minute per data feed". The automated-extraction ban ("trawling, data mining and screen scraping") applies only "in relation to the Oyster, Congestion Charging and Santander Cycles websites". No AI/ML or non-commercial-only clause (block 2 checks). The licence also forbids use "that suggests any official status or that TfL endorses You". This skill names TfL only to say where the data comes from, uses no roundel, logo or brand colours, and prints the attribution with every answer.

Powered by TfL Open Data. Contains OS data © Crown copyright and database rights 2016 and Geomni UK Map data © and database rights [2019].

## Quick summary

- **No scraping.** Two keyless GETs answer the question: `https://api.tfl.gov.uk/Line/victoria/Status` (`lineStatuses[].statusSeverity`, `statusSeverityDescription`, `reason`) and `https://api.tfl.gov.uk/Line/victoria/Arrivals/940GZZLUOXC` (predictions with `expectedArrival`, `timeToStation` in seconds, `platformName`, `towards`). At 23:44 GMT on 2026-11-12: Victoria **Good Service**; next three at Oxford Circus **23:46 northbound to Walthamstow Central, 23:48 southbound to Brixton, 23:52 southbound to Brixton**.
- **"Running normally" = every `lineStatuses[]` entry has `statusSeverity` 10 ("Good Service").** `/Line/Meta/Severity` lists 0-20 for tube (6 Severe Delays, 9 Minor Delays, 20 Service Closed, ...). A non-10 status carries a `reason` string; the same run showed Northern `6 Severe Delays` "due to an earlier points failure at Mornington Crescent".
- **Station id:** `/StopPoint/Search/oxford%20circus?modes=tube` returns one match, `940GZZLUOXC`. Most tube station ids are `940GZZLU...`, not all: `/Line/northern/StopPoints` has `940GZZBPSUST` (Battersea Power Station) and `940GZZNEUGST` (Nine Elms), so look the id up instead of building it.
- **Use the line-filtered arrivals route.** `/StopPoint/940GZZLUOXC/Arrivals` returns every line at the station (25 predictions at 23:27: Bakerloo, Central and Victoria); `/Line/victoria/Arrivals/940GZZLUOXC` returns only the Victoria ones (6).
- **Recompute the countdown from `expectedArrival`.** Responses are cached (`cache-control: public, must-revalidate, max-age=30, s-maxage=60`) and predictions were 55-106 s old when read (23:29, 23:35, 23:38, 23:44), so `timeToStation` runs fast. Blocks subtract the server's `Date` header from `expectedArrival` and drop trains whose time has passed.
- **"Next three" mixes directions.** Block 1 prints the next three per platform and the next three overall, each labelled northbound or southbound.
- **Errors are JSON:** an unknown line or stop is HTTP 404 `EntityNotFoundException` with a readable `message`; a station the line does not serve is HTTP 200 `[]` (empty lists outside service hours were not tested).
- **Rate limit:** licence cap 500 calls per minute per feed; no rate-limit headers seen. Blocks pace 1 s per call, serial.

## What works

### 1. Victoria line status and the next three trains at Oxford Circus (browser)

`on_api_tab()` opens the Victoria line status JSON on api.tfl.gov.uk once, so `fetch()` is same-origin. `get()` returns parsed JSON on 200, waits 30 s once on 429/5xx and otherwise raises, so an error never looks like an answer. The block resolves the station id, reads the status, refuses stale predictions and works out minutes from the server clock.

```python
import json, time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

LINE, STATION = "victoria", "Oxford Circus"  # line id as the API spells it; station name to look up

SITE = "https://api.tfl.gov.uk"
PAUSE = 1.0  # TfL licence: "maximum of 500 calls per minute per data feed"; keep calls serial
LONDON = ZoneInfo("Europe/London")

def on_api_tab():
    """fetch() runs same-origin from a logged-out api.tfl.gov.uk tab (the line's own status JSON). Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(f"{SITE}/Line/{LINE}/Status")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"lineStatuses"' not in body:
        raise RuntimeError(f"api.tfl.gov.uk did not serve the line status JSON (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__tfl = window.__tfl || {}; const id = String(Math.random()).slice(2); window.__tfl[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__tfl[id] = {status: r.status, type: r.headers.get('content-type'), date: r.headers.get('date'), text: await r.text()}; })
    .catch(e => { window.__tfl[id] = {status: 0, type: '', date: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__tfl[%s]; if (v) delete window.__tfl[%s]; return v; })()"""

def get(path, timeout=30):
    """GET SITE+path from inside the tab -> parsed JSON. Errors are JSON ApiError {"httpStatusCode":404,"message":...}.
    Waits 30 s once on 429/5xx, raises on anything else, so an error never looks like an answer."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{path}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] == 200 and "json" in (r["type"] or ""):
            get.date = r["date"]  # server clock (HTTP Date header); used as "now" so a skewed local clock does not matter
            return json.loads(r["text"])
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(30)
            continue
        raise RuntimeError(f"{path}: HTTP {r['status']} {' '.join(r['text'].split())[:200]!r}; stopping")

def ts(s):
    """TfL times are UTC ISO strings with up to 7 fractional digits ('2026-11-12T23:27:28.3735786Z')."""
    s = s.rstrip("Z")
    if "." in s:
        head, frac = s.split(".")
        s = head + "." + frac[:6]
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)

on_api_tab()

# 1. Station id: search, keep the tube match whose name starts with the station name (940GZZLUOXC for Oxford Circus).
hits = get("/StopPoint/Search/" + STATION.replace(" ", "%20") + "?modes=tube")["matches"]
hits = [m for m in hits if m["name"].lower().startswith(STATION.lower())]
if len(hits) != 1:
    raise RuntimeError(f"expected one tube station for {STATION!r}, got {[m['name'] for m in hits]}")
naptan = hits[0]["id"]
print(f"station: {hits[0]['name']} -> {naptan}")

# 2. Line status. Severity 10 = "Good Service" (/Line/Meta/Severity); anything else comes with a reason.
line = get(f"/Line/{LINE}/Status")
if len(line) != 1 or line[0]["id"] != LINE:
    raise RuntimeError(f"asked {LINE}, got {[l['id'] for l in line]}")
line = line[0]
statuses = line["lineStatuses"]
if not statuses:
    raise RuntimeError("no lineStatuses in the answer: stop")
normal = all(s["statusSeverity"] == 10 for s in statuses)
print(f"\n{line['name']} line: " + "; ".join(f"{s['statusSeverityDescription']} (severity {s['statusSeverity']})" for s in statuses))
for s in statuses:
    if s.get("reason"):
        print("  reason:", " ".join(s["reason"].split()))

# 3. Arrivals for this line at this station. One call; the server caches 30 s (cache-control max-age=30).
preds = get(f"/Line/{LINE}/Arrivals/{naptan}")
now = parsedate_to_datetime(get.date) if get.date else datetime.now(timezone.utc)
skew = (datetime.now(timezone.utc) - now).total_seconds()
if abs(skew) > 5:
    print(f"  note: local clock is {skew:+.0f} s off the server; using the server's Date header")
bad = [p for p in preds if p["lineId"] != LINE or p["naptanId"] != naptan]
if bad:
    raise RuntimeError(f"{len(bad)} predictions for another line or stop: stop")
if preds:
    age = (now - max(ts(p["timestamp"]) for p in preds)).total_seconds()
    print(f"\n{len(preds)} predictions, newest computed {age:.0f} s ago")
    if age > 120:
        raise RuntimeError(f"predictions are {age:.0f} s old; the feed is stale, do not quote them")

# timeToStation is seconds at prediction time; recompute from expectedArrival so a cached answer does not run fast.
best = {}
for p in preds:
    secs = (ts(p["expectedArrival"]) - now).total_seconds()
    if secs < 0:  # expected time has passed: the train is in the platform or gone
        continue
    key = (p["vehicleId"], p["platformName"])  # one train can appear twice; keep its earliest row per platform
    if key not in best or secs < best[key][0]:
        best[key] = (secs, p)
trains = sorted(best.values(), key=lambda t: t[0])

print(f"\nnow {now.astimezone(LONDON):%H:%M:%S %Z}")
by_platform = {}
for secs, p in trains:
    by_platform.setdefault(p["platformName"], []).append((secs, p))
if not by_platform:
    print("no Victoria line trains predicted at this station: check the line status and that the line serves it")
for plat in sorted(by_platform):
    print(f"{plat}:")
    for secs, p in by_platform[plat][:3]:
        when = ts(p["expectedArrival"]).astimezone(LONDON)
        mins = "due" if secs < 30 else f"{round(secs / 60)} min"
        print(f"  {when:%H:%M}  {mins:>6}  to {p['towards'] or p['destinationName']}  ({p['currentLocation']}, train {p['vehicleId']})")

nxt = trains[:3]
print(f"\nanswer: {line['name']} line {'running normally' if normal else 'NOT running normally'} "
      f"({', '.join(s['statusSeverityDescription'] for s in statuses)}).")
print("  next three at " + hits[0]["name"].replace(" Underground Station", "") + ": "
      + "; ".join(f"{ts(p['expectedArrival']).astimezone(LONDON):%H:%M} {p['platformName'].split(' ')[0].lower()} to {p['towards'] or p['destinationName']}" for _, p in nxt))
print("  Powered by TfL Open Data")
```

Output (from the run on 2026-11-12, 23:44 GMT):

```text
station: Oxford Circus Underground Station -> 940GZZLUOXC

Victoria line: Good Service (severity 10)

6 predictions, newest computed 106 s ago

now 23:44:33 GMT
Northbound - Platform 6:
  23:46   1 min  to Walthamstow Central  (Approaching Green Park, train 271)
  23:53   9 min  to Walthamstow Central  (Approaching Stockwell, train 214)
Southbound - Platform 5:
  23:48   3 min  to Brixton  (Between Kings Cross St. Pancras and Euston, train 212)
  23:52   8 min  to Brixton  (Departed Finsbury Park, train 272)
  23:58  14 min  to Brixton  (At Tottenham Hale, train 205)

answer: Victoria line running normally (Good Service).
  next three at Oxford Circus: 23:46 northbound to Walthamstow Central; 23:48 southbound to Brixton; 23:52 southbound to Brixton
  Powered by TfL Open Data
```

### 2. Licence terms, robots.txt, severity codes and error shapes (browser)

Reads five clauses from the licence page and the key note on the API portal, then makes 8 small calls from an api.tfl.gov.uk page: robots.txt, the severity list, the all-lines status and four deliberate misses.

```python
import json, time

SITE = "https://api.tfl.gov.uk"
TERMS = "https://tfl.gov.uk/corporate/terms-and-conditions/transport-data-service"
PORTAL = "https://api-portal.tfl.gov.uk/"

def page_text(url, must, timeout=30):
    """Load url and wait until `must` is in the text. tfl.gov.uk shows a Cloudflare check
    ("Just a moment...") for about 5 s in a fresh browser, then the page."""
    goto_url(url)
    wait_for_load()
    t0 = time.time()
    while True:
        t = " ".join((js("document.body ? document.body.innerText : ''") or "").split())
        if must in t:
            return t
        if time.time() - t0 > timeout:
            if "Verification required" in t or "Just a moment" in (js("document.title") or ""):
                raise RuntimeError(f"{url}: Cloudflare check did not clear in {timeout}s; read it later, do not guess the terms")
            raise RuntimeError(f"{must!r} not on {url}: the page changed, re-read it before relying on this skill")
        time.sleep(1)

def quote(text, start, n=300):
    i = text.find(start)
    if i < 0:
        raise RuntimeError(f"{start!r} not found: the page changed, re-read it before relying on this skill")
    return text[i:i + n]

# Licence terms, as the page shows them.
new_tab("about:blank")
t = page_text(TERMS, "You are free to:")
for s, n in (("You are free to:", 240), ("Acknowledge TfL as the source", 260), ("Limit traffic requests", 200),
             ("Use any automated system", 220), ("This Licence does not grant You any right to use the Information in a way", 160)):
    print(f"terms: {quote(t, s, n).rstrip()}\n")
for word in ("artificial intelligence", "machine learning", " AI ", "non-commercial use only"):
    print(f"terms mention {word.strip()!r}: {word.lower() in t.lower()}")

# The API portal on keys.
t = page_text(PORTAL, "Unified API")
i = t.lower().find("recommended")
print("\nportal:", t[max(0, i - 200):i + 200] if i >= 0 else "no 'recommended' on the home page")

# Same-origin probes from an api.tfl.gov.uk page. No retries: this block only inspects answers.
goto_url(SITE + "/Line/Meta/Severity")
wait_for_load()
if js("location.origin") != SITE:
    raise RuntimeError(f"not on {SITE} (at {js('location.href')}): stop")

START_JS = """(() => { window.__tfl = window.__tfl || {}; const id = String(Math.random()).slice(2); window.__tfl[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__tfl[id] = {status: r.status, type: r.headers.get('content-type'), cache: r.headers.get('cache-control'), text: await r.text()}; })
    .catch(e => { window.__tfl[id] = {status: 0, type: '', cache: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__tfl[%s]; if (v) delete window.__tfl[%s]; return v; })()"""

def raw(path, timeout=30):
    rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{path}: no answer after {timeout}s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r

r = raw("/robots.txt")
print(f"\napi robots.txt: HTTP {r['status']} {r['type']} {json.loads(r['text'])['message']!r}")

sev = json.loads(raw("/Line/Meta/Severity")["text"])
print("tube severities:", ", ".join(f"{x['severityLevel']} {x['description']}" for x in sev if x["modeName"] == "tube"))

r = raw("/Line/Mode/tube/Status")
print(f"\n/Line/Mode/tube/Status: HTTP {r['status']} cache-control {r['cache']!r}")
for l in json.loads(r["text"]):
    for s in l["lineStatuses"]:
        why = " ".join((s.get("reason") or "").split())
        print(f"  {l['id']:<16} {s['statusSeverity']:>2} {s['statusSeverityDescription']:<14} {why[:110]}".rstrip())

for path in ("/Line/victoriaa/Status",          # typo in the line id
             "/StopPoint/940GZZLUXXX/Arrivals",  # unknown stop
             "/StopPoint/Search/zzqqxx",         # no match
             "/Line/victoria/Arrivals/940GZZLUBST"):  # a station the Victoria line does not serve (Baker Street)
    r = raw(path)
    d = json.loads(r["text"])
    body = (f"{d['exceptionType']}: {d['message']}" if isinstance(d, dict) and "httpStatusCode" in d
            else json.dumps({k: v for k, v in d.items() if k != "$type"}) if isinstance(d, dict) else r["text"])
    print(f"{path}: HTTP {r['status']} {body}")
```

Output (from the run on 2026-11-12, 23:45 GMT):

```text
terms: You are free to: Copy, publish, distribute and transmit the Information Adapt the Information and Exploit the Information commercially and non-commercially for example, by combining it with other Information, or by including it in Your own

terms: Acknowledge TfL as the source of the Information by including the following attribution statement ‘Powered by TfL Open Data’ Acknowledge that this Information contains Ordnance Survey derived data by including the following attribution statement: ‘Contains OS

terms: Limit traffic requests up to a maximum of 500 calls per minute per data feed. TfL reserves the right to throttle or limit access to feeds when it is believed the overall service is being degraded by e

terms: Use any automated system, software or process to extract content and/or data, including trawling, data mining and screen scraping in relation to the Oyster, Congestion Charging and Santander Cycles websites, except where

terms: This Licence does not grant You any right to use the Information in a way that suggests any official status or that TfL endorses You or Your use of the Informat

terms mention 'artificial intelligence': False
terms mention 'machine learning': False
terms mention 'AI': False
terms mention 'non-commercial use only': False

portal: Home APIs FAQ Sign in Register To use the Unified API, it is recommended to register for an account. During registration, you should receive a confirmation email containing a link to activate your account. If you have not received the email, please check your s

api robots.txt: HTTP 404 application/json; charset=utf-8 'Resource not found: http://api:8001/robots.txt'
tube severities: 0 Special Service, 1 Closed, 2 Suspended, 3 Part Suspended, 4 Planned Closure, 5 Part Closure, 6 Severe Delays, 7 Reduced Service, 8 Bus Service, 9 Minor Delays, 10 Good Service, 11 Part Closed, 12 Exit Only, 13 No Step Free Access, 14 Change of frequency, 15 Diverted, 16 Not Running, 17 Issues Reported, 18 No Issues, 19 Information, 20 Service Closed

/Line/Mode/tube/Status: HTTP 200 cache-control 'public, must-revalidate, max-age=30, s-maxage=60'
  bakerloo          9 Minor Delays   Bakerloo Line: Minor delays between Queen's park and Harrow & Wealdstone due to an earlier signal fault at Sou
  central          10 Good Service
  circle            9 Minor Delays   Circle Line: Minor delays due to train cancellations.
  district          9 Minor Delays   District Line: Minor delays due to an earlier faulty train at Whitechapel and train cancellations.
  hammersmith-city 10 Good Service
  jubilee           9 Minor Delays   Jubilee Line: Minor delays due to train cancellations.
  metropolitan     10 Good Service
  northern          6 Severe Delays  Northern Line: Severe delays due to an earlier points failure at Mornington Crescent. Tickets are being accept
  piccadilly       10 Good Service
  victoria         10 Good Service
  waterloo-city    10 Good Service
/Line/victoriaa/Status: HTTP 404 EntityNotFoundException: The following line id is not recognised: victoriaa
/StopPoint/940GZZLUXXX/Arrivals: HTTP 404 EntityNotFoundException: The following stop point is not recognised: 940GZZLUXXX
/StopPoint/Search/zzqqxx: HTTP 200 {"query": "zzqqxx", "total": 0, "matches": []}
/Line/victoria/Arrivals/940GZZLUBST: HTTP 200 []
```

### 3. Same answer with Python urllib (no browser)

Python's default User-Agent gets a Cloudflare 403; the block sends its own.

```python
import json, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

LINE, NAPTAN = "victoria", "940GZZLUOXC"  # Oxford Circus (from /StopPoint/Search/oxford%20circus?modes=tube)
API = "https://api.tfl.gov.uk"
LONDON = ZoneInfo("Europe/London")
UA = {"User-Agent": "tube-status-example/1.0"}  # Python's default "Python-urllib/3.12" gets Cloudflare 403 "error code: 1010"

def get(path):
    """GET -> (status, Date header, body). No key: app_key is optional (the portal 'recommended' registering)."""
    try:
        with urllib.request.urlopen(urllib.request.Request(API + path, headers=UA), timeout=30) as r:
            return r.status, r.headers.get("Date"), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Date"), e.read().decode()

def ts(s):
    s = s.rstrip("Z")
    if "." in s:
        head, frac = s.split(".")
        s = head + "." + frac[:6]  # TfL sends up to 7 fractional digits
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)

s, _, body = get(f"/Line/{LINE}/Status")
if s != 200:
    sys.exit(f"status: HTTP {s} {body[:200]}")
statuses = json.loads(body)[0]["lineStatuses"]
normal = bool(statuses) and all(x["statusSeverity"] == 10 for x in statuses)
print("Victoria:", ", ".join(x["statusSeverityDescription"] for x in statuses), "->", "normal" if normal else "NOT normal")
for x in statuses:
    if x.get("reason"):
        print("  reason:", " ".join(x["reason"].split()))

time.sleep(1)
s, date, body = get(f"/Line/{LINE}/Arrivals/{NAPTAN}")
if s != 200:
    sys.exit(f"arrivals: HTTP {s} {body[:200]}")
now = parsedate_to_datetime(date)  # server clock
trains = {}
for p in json.loads(body):
    if p["lineId"] != LINE or p["naptanId"] != NAPTAN:
        sys.exit("prediction for another line or stop: stop")
    secs = (ts(p["expectedArrival"]) - now).total_seconds()
    key = (p["vehicleId"], p["platformName"])  # one row per train per platform, its earliest
    if secs >= 0 and (key not in trains or secs < trains[key][0]):
        trains[key] = (secs, p)
nxt = sorted(trains.values(), key=lambda t: t[0])[:3]
if not nxt:
    sys.exit("no Victoria line trains predicted at Oxford Circus: check the line status")
print(f"now {now.astimezone(LONDON):%H:%M:%S %Z}, next three at Oxford Circus:")
for secs, p in nxt:
    print(f"  {ts(p['expectedArrival']).astimezone(LONDON):%H:%M}  {round(secs / 60):>2} min  {p['platformName']:<24} to {p['towards'] or p['destinationName']}")
print("Powered by TfL Open Data")
```

Output (from the run on 2026-11-12, 23:45 GMT):

```text
Victoria: Good Service -> normal
now 23:45:06 GMT, next three at Oxford Circus:
  23:45   0 min  Northbound - Platform 6  to Walthamstow Central
  23:48   3 min  Southbound - Platform 5  to Brixton
  23:52   7 min  Southbound - Platform 5  to Brixton
Powered by TfL Open Data
```

### 4. curl

```bash
A=https://api.tfl.gov.uk   # no key needed; add ?app_key=... only if you registered one
curl -sS --fail "$A/Line/victoria/Status" | python3 -c '
import json, sys
s = json.load(sys.stdin)[0]["lineStatuses"]
print("victoria:", [(x["statusSeverity"], x["statusSeverityDescription"]) for x in s])
'
sleep 1
curl -sS --fail "$A/Line/victoria/Arrivals/940GZZLUOXC" | python3 -c '
import json, sys
d = sorted(json.load(sys.stdin), key=lambda p: p["timeToStation"])
for p in d[:3]:
    print(p["timeToStation"], "s", p["platformName"], "->", p["towards"], p["expectedArrival"])
'
sleep 1
curl -sS -o /dev/null -w 'unknown line: HTTP %{http_code} %{content_type}\n' "$A/Line/victoriaa/Status"
```

Output (from the run on 2026-11-12, 23:31 GMT):

```text
victoria: [(10, 'Good Service')]
218 s Northbound - Platform 6 -> Walthamstow Central 2026-11-12T23:34:30Z
218 s Southbound - Platform 5 -> Brixton 2026-11-12T23:34:30Z
518 s Southbound - Platform 5 -> Brixton 2026-11-12T23:39:30Z
unknown line: HTTP 404 application/json; charset=utf-8
```

`timeToStation` here is the raw cached value; use block 1 or 3 when the minutes matter.

## Fields

| Field | Where | Notes |
|---|---|---|
| `id`, `name` | `/Line/<id>/Status` | `victoria`, `Victoria`; ids are lower case with hyphens (`hammersmith-city`, `waterloo-city`) |
| `lineStatuses[].statusSeverity` | status | integer; 10 = Good Service; full list at `/Line/Meta/Severity` |
| `lineStatuses[].statusSeverityDescription` | status | `Good Service`, `Minor Delays`, `Severe Delays`, ... |
| `lineStatuses[].reason` | status | present when the status is not 10, e.g. "Northern Line: Severe delays due to an earlier points failure at Mornington Crescent. ..." |
| `lineStatuses[].validityPeriods[]` | status | empty for Victoria (Good Service); each disrupted line had one entry, e.g. Northern `{"fromDate": "2026-11-12T17:33:12Z", "toDate": "2026-11-13T01:29:00Z", "isNow": true}` |
| `matches[].id`, `matches[].name` | `/StopPoint/Search/<q>` | `940GZZLUOXC`, `Oxford Circus Underground Station`; `?modes=tube` narrows it |
| `expectedArrival` | arrivals | UTC ISO time; the field to trust |
| `timeToStation` | arrivals | seconds from the prediction's `timestamp`, not from now |
| `timestamp` | arrivals | when TfL computed the prediction, UTC, up to 7 fractional digits (`2026-11-12T23:27:28.3735786Z`) |
| `platformName` | arrivals | `Northbound - Platform 6`, `Southbound - Platform 5` at Oxford Circus |
| `towards`, `destinationName` | arrivals | `Walthamstow Central` / `Walthamstow Central Underground Station` |
| `currentLocation` | arrivals | free text: `At Pimlico`, `Between Warren Street and Oxford Circus` |
| `vehicleId`, `lineId`, `naptanId`, `direction` | arrivals | `direction` is `inbound`/`outbound`; use `platformName` for north/south |

## Gotchas

- **Cached predictions.** `cache-control: max-age=30, s-maxage=60`; the newest prediction was 55 s old at 23:29, 61 s at 23:35, 64 s at 23:38 and 106 s at 23:44. Count down from `expectedArrival` against the response `Date`, and refuse predictions older than 2 minutes (block 1).
- **A train in the platform is "due".** Block 1 prints `due` under 30 s and drops a train once `expectedArrival` has passed; between calls the first train can disappear.
- **Python's default User-Agent is blocked.** `Python-urllib/3.12` got HTTP 403 `error code: 1010` (Cloudflare) from api.tfl.gov.uk; curl's default, an empty one and `my-app/1.0` got 200. Send any descriptive User-Agent.
- **tfl.gov.uk sits behind a Cloudflare challenge** for curl (HTTP 403). A fresh cloud browser shows "Just a moment..." / "Verification required" for about 5 s, then the page, so a fixed 3 s wait can read the challenge; block 2 polls for the text it needs. api.tfl.gov.uk did not challenge.
- **Empty is not an error.** `/Line/victoria/Arrivals/940GZZLUBST` (Baker Street, not on the Victoria line) is HTTP 200 `[]`, not an error. Check the station is on the line before saying "no trains".
- **Keys.** The API portal says "To use the Unified API, it is recommended to register for an account"; every call here was keyless. With a key, add `?app_key=<key>` (the query parameter named in https://api.tfl.gov.uk/swagger/docs/v1 `securityDefinitions`); never print it. A wrong key is not ignored: `?app_key=invalid000` got HTTP 429 with the plain-text body `Invalid app_key is provided.`, so a 429 can mean a bad key, not a rate limit.
- **CORS is open** (`access-control-allow-origin: *`), so `fetch()` works from any tab; the blocks use an api.tfl.gov.uk tab anyway.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks check `location.origin` and page text, not the title.

## What does not work

- **Scraping tfl.gov.uk status pages:** `/statusupdates` is disallowed for `*` in robots.txt, and curl got a Cloudflare 403 on tfl.gov.uk. The API gives the status as JSON.
- **The Oyster, Congestion Charging and Santander Cycles websites:** the licence bans automated extraction from them. Not used.
- **TfL logos, the roundel or line colours as branding:** the licence keeps TfL's trademarks and points to its branding guidelines. This skill uses the name only to cite the source.
- **Not tested:** Night Tube and "Service Closed" behaviour (the run was at 23:29 on a Thursday, inside service hours), planned-works `validityPeriods`, `/Line/<id>/Timetable`, crowding, bus and rail modes, keyed requests, rate-limit behaviour (never provoked).
