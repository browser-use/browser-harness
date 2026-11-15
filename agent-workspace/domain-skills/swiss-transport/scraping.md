# Transport API (transport.opendata.ch) - Next Three Train Connections from Zurich HB to Bern with Platforms, Delays and Transfers (unofficial keyless API by Opendata.ch)

Field-tested against transport.opendata.ch on 2026-11-14 (23:30-23:36 UTC, which is 00:30-00:36 on Sunday 15 November in Switzerland) using a fresh Browser Use cloud browser (logged out) plus Python urllib and `curl` from a Linux server. 17 browser page loads and 39 in-page `fetch()` calls, about 48 curl calls and 3 urllib calls, all serial at 0.5 s or more spacing: every API call was HTTP 200 except the deliberate HTTP 400 probes below. No 429, no challenge, no key, no login. Python's default User-Agent also got HTTP 200.

robots.txt (checked 2026-11-14, curl and the cloud browser): https://transport.opendata.ch/robots.txt is HTTP 200 `text/plain` with `User-agent: *` / `Allow: /` and a sitemap line, and no other groups. The same bytes came back for User-Agent `*`, GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, Claude-SearchBot, anthropic-ai, Google-Extended, PerplexityBot, Perplexity-User, CCBot, Bytespider, Applebot-Extended and Meta-ExternalAgent: no named AI-agent groups, so `/v1/` is allowed for all of them. Terms: the home page (https://transport.opendata.ch/) calls it an "unofficial API" that "answers from the national timetable and its real-time data, published as open data on opentransportdata.swiss", "Powered by Opendata.ch". The licenses page (https://transport.opendata.ch/licenses.html): the software is "free software under the MIT License, © 2012–2026 Opendata.ch"; timetable, real time and operator names come from the Swiss national timetable under the "opentransportdata.swiss terms of use"; streets, addresses and places from OpenStreetMap under "ODbL 1.0, © OpenStreetMap contributors"; shared mobility from sharedmobility.ch, "Open use, must provide the source (BY)". The docs (https://transport.opendata.ch/docs.html): "There is no fixed limit per client", "please cache what you can", "An application that asks the same question every few seconds will be throttled", "CORS is enabled ... (avoid setting custom headers though)", and "If you show the data, please name its source: Timetable data: opentransportdata.swiss." The opentransportdata.swiss General Terms and Conditions of Use (https://opentransportdata.swiss/en/terms-of-use/): "The data obtained can be processed, analysed and published, including incorporating additional data", and "The URL opentransportdata.swiss must be cited as the source for raw data in publications and analyses"; registration and an access code apply to that platform's own service APIs, which this skill does not call. No AI/ML, scraping, automated-access or non-commercial clause on either site. (opentransportdata.swiss/robots.txt disallows `/harvest`, `/dataset?*` and similar for a list of named crawlers and nothing for `*`; this skill only reads its terms page, which is allowed.) This skill names the service "Transport API (transport.opendata.ch), unofficial, by Opendata.ch", cites opentransportdata.swiss as the data source in every answer and shows no logos. It is not an official railway API and is not affiliated with any train operator.

## Quick summary

- **No scraping.** `GET https://transport.opendata.ch/v1/connections?from=8503000&to=8507000&limit=3` returns the next connections with departure and arrival `platform`, `delay` (minutes), `duration`, `transfers`, `products` and the legs in `sections[]`. Station ids come from `GET /v1/locations?query=Zürich HB&type=station` (`8503000` Zürich HB, `8507000` Bern). No key; CORS is on.
- **Answer (00:33 Swiss time, Sunday 15 November 2026, a late-night run):** 1) **01:02 IC 8, platform 16 -> Bern 02:04 platform 9**, direct, 62 min, on time. 2) **02:02 IR N1, platform 31 -> Bern 03:04 platform 9**, direct, 62 min, on time. 3) **02:30 SN 11, platform 41/42 -> Olten 03:27, change (129 min wait), IR 35 05:36 -> Bern 06:21 platform 50**, 1 transfer, 3 h 51 min; no real-time for the second leg yet.
- **Daytime shape** (same query with `date=2026-11-16&time=08:00`, block 4): 08:02 IC 8 platform 31 -> 08:58 (56 min, direct); 08:06 IR 16 platform 15 -> 09:24 (direct); 08:08 IR 37 + IR 16 platform 16 -> 09:24 (1 transfer). `delay` is `null` that far ahead.
- **`delay`:** minutes; `0` = on time per the real-time feed; `null` = no real-time prognosis for that stop (future trains, or a later leg). Docs: delays are "at most about a minute behind the source".
- **"Next" is not always useful.** At night the third result was a 1-transfer trip with a 2-hour wait. Print `duration` and `transfers`, and use `page=1` or `time=` for more.
- **Rate limit:** none fixed; the API is shared, so cache. Real-time data changes every 30 s (docs), so block 3 caches each URL for 30 s. `limit` is 1-16, `page` 0-10: `limit=17` and `page=11` are HTTP 400 `{"errors": [...]}`, but `limit=0` silently returned 4 connections.

## What works

### 1. Next three connections with platforms, delays and transfers (browser)

`on_api_tab()` opens the API's home page once and runs `fetch()` from it (CORS is on, so any page would do; block 2 shows example.com). `get()` sends no custom headers, as the docs ask, returns parsed JSON on 200, waits 30 s once on 429/500/502/503/504 and otherwise raises. Stations are resolved to ids with `/locations` first, so a loose name cannot silently pick another stop.

```python
import json, time
from datetime import datetime, timezone
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

FROM, TO, N = "Zürich HB", "Bern", 3  # exact station names as /locations spells them (block 2: "Zurich" is not one)

SITE = "https://transport.opendata.ch"
PAUSE = 1.0  # docs: "no fixed limit per client", but an app asking the same question every few seconds "will be throttled"

def on_api_tab():
    """Open the API's own home page once and fetch() from it. CORS is on ("from any website"), so any page works;
    this one keeps the calls same-origin. Reuse the tab."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/")
    wait_for_load()
    if js("location.origin") != SITE:
        raise RuntimeError(f"transport.opendata.ch did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it. No custom headers (docs: "avoid setting custom headers").
START_JS = """(() => { window.__tch = window.__tch || {}; const id = String(Math.random()).slice(2); window.__tch[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__tch[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__tch[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__tch[%s]; if (v) delete window.__tch[%s]; return v; })()"""

def get(path, params, timeout=60):
    """GET SITE+path?params from inside the tab -> parsed JSON. HTTP 400 is {"errors": [...]} and raises.
    Waits 30 s once on 429/500/502/503/504 or a network error, then raises."""
    url = SITE + path + "?" + urlencode(params)
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{path}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(30)
            continue
        if r["status"] != 200 or "json" not in (r["type"] or ""):
            raise RuntimeError(f"{path}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")
        return json.loads(r["text"])
    raise RuntimeError(f"{path}: still failing after one retry: stop")

def t(s):
    """'2026-11-15T01:02:00+0100' -> aware datetime; None stays None."""
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z") if s else None

def hm(s):
    return t(s).strftime("%H:%M") if s else "--:--"

def mins(duration):
    """'00d01:02:00' -> 62."""
    d, rest = duration.split("d")
    h, m, _ = rest.split(":")
    return int(d) * 1440 + int(h) * 60 + int(m)

def delay_txt(stop):
    """delay is minutes; None = no real-time prognosis for this stop (e.g. a train days ahead)."""
    d = stop.get("delay")
    return "no real-time" if d is None else "on time" if d == 0 else f"+{d} min"

def platform_txt(stop):
    """Planned platform, plus the real-time one when prognosis.platform differs (a platform change)."""
    p, new = stop.get("platform") or "?", (stop.get("prognosis") or {}).get("platform")
    return f"pl {p}" if not new or new == p else f"pl {new} (changed from {p})"

def station(name):
    """Resolve a name to one station id with /locations; a hit must match the name exactly, else stop."""
    hits = get("/v1/locations", {"query": name, "type": "station"})["stations"]
    exact = [h for h in hits if h["name"] == name]
    if not exact:
        raise RuntimeError(f"no station named exactly {name!r}; candidates {[(h['name'], h['id']) for h in hits[:5]]}: "
                           "pick one and set FROM/TO to its name")
    return exact[0]

on_api_tab()
now = datetime.now(timezone.utc)
a, b = station(FROM), station(TO)
print(f"now {now.astimezone(ZoneInfo('Europe/Zurich')):%Y-%m-%d %H:%M %Z} (Swiss time), {a['name']} ({a['id']}) -> {b['name']} ({b['id']})")

data = get("/v1/connections", {"from": a["id"], "to": b["id"], "limit": N})
conns = data["connections"]
if not conns:
    raise RuntimeError(f"no connections returned (stations {data['stations']}): stop")
if data["from"]["id"] != a["id"] or data["to"]["id"] != b["id"]:
    raise RuntimeError(f"API planned {data['from']['name']} -> {data['to']['name']}, not what was asked: stop")

for i, c in enumerate(conns[:N], 1):
    dep, arr = c["from"], c["to"]
    if t(dep["departure"]) < now.replace(second=0, microsecond=0):
        print(f"NOTE: connection {i} departs {hm(dep['departure'])}, before now")
    print(f"\n{i}. {hm(dep['departure'])} {platform_txt(dep)}, {delay_txt(dep)}  ->  {hm(arr['arrival'])} {platform_txt(arr)}, {delay_txt(arr)}"
          f"  | {mins(c['duration'])} min, {c['transfers']} transfer(s), {' + '.join(c['products'])}")
    prev = None
    for s in c["sections"]:
        d, r, j = s["departure"], s["arrival"], s["journey"]
        if prev is not None:
            wait = (t(d["departure"]) - t(prev["arrival"])).total_seconds() / 60
            print(f"     change at {d['station']['name']}: {prev.get('platform') or '?'} -> {d.get('platform') or '?'}, {wait:.0f} min")
        if j:
            print(f"     {j['category']} {j['number']} to {j['to']} ({j['operator']}): {d['station']['name']} {hm(d['departure'])} {platform_txt(d)}"
                  f" -> {r['station']['name']} {hm(r['arrival'])} {platform_txt(r)}, {delay_txt(r)}")
        else:  # walk section: journey null, walk {"duration": seconds}
            print(f"     walk {d['station']['name']} -> {r['station']['name']}, {((s.get('walk') or {}).get('duration') or 0) / 60:.0f} min")
        prev = r

print(f"\nSource: Transport API (transport.opendata.ch), unofficial, by Opendata.ch. Timetable data: opentransportdata.swiss.")
```

Output (from the run on 2026-11-14, 23:33 UTC):

```text
now 2026-11-15 00:33 CET (Swiss time), Zürich HB (8503000) -> Bern (8507000)

1. 01:02 pl 16, on time  ->  02:04 pl 9, on time  | 62 min, 0 transfer(s), IC 8
     IC 8 to Bern (SBB): Zürich HB 01:02 pl 16 -> Bern 02:04 pl 9, on time

2. 02:02 pl 31, on time  ->  03:04 pl 9, on time  | 62 min, 0 transfer(s), IR N1
     IR N1 to Bern (SBB): Zürich HB 02:02 pl 31 -> Bern 03:04 pl 9, on time

3. 02:30 pl 41/42, on time  ->  06:21 pl 50, no real-time  | 231 min, 1 transfer(s), SN11 + IR 35
     SN 11 to Olten (SBB): Zürich HB 02:30 pl 41/42 -> Olten 03:27 pl 8, on time
     change at Olten: 8 -> 8, 129 min
     IR 35 to Bern (SBB): Olten 05:36 pl 8 -> Bern 06:21 pl 50, no real-time

Source: Transport API (transport.opendata.ch), unofficial, by Opendata.ch. Timetable data: opentransportdata.swiss.
```

### 2. robots.txt, the API's rules and error shapes (browser)

Reads robots.txt, six rules from the docs page and two lines of the opentransportdata.swiss terms, then makes 9 same-origin calls (mostly deliberate edge cases) and two cross-origin calls from example.com.

```python
import json, time

SITE = "https://transport.opendata.ch"

# robots.txt, as the browser sees it. Reuse block 1's tab if it is open.
try:
    on_site = js("location.origin") == SITE
except Exception:
    on_site = False
(goto_url if on_site else new_tab)(SITE + "/robots.txt")
wait_for_load()
print(f"robots.txt: {' '.join((js('document.body.innerText') or '').split())!r}\n")

# The API's own rules, from the docs page.
goto_url(SITE + "/docs.html")
wait_for_load()
text = " ".join((js("document.body.innerText") or "").split())
for q in ("There is no fixed limit per client", "please cache what you can", "An application that asks the same question",
          "Cross Origin Resource Sharing (CORS) is enabled", "If several connections depart at the same time", "If you show the data, please name its source"):
    i = text.find(q)
    if i < 0:
        raise RuntimeError(f"docs page changed, {q!r} not found: re-read {SITE}/docs.html before relying on this skill")
    print(f"docs: {text[i:text.find('. ', i + len(q) - 1) + 1]}")  # '. ' so 'transport.opendata.ch' does not end it

# The data terms the licenses page points to (opentransportdata.swiss General Terms and Conditions of Use).
goto_url("https://opentransportdata.swiss/en/terms-of-use/")
wait_for_load()
time.sleep(2)
terms = " ".join((js("document.body.innerText") or "").split())
for q in ("The data obtained can be processed, analysed and published", "must be cited as the source"):
    i = terms.find(q)
    if i < 0:
        raise RuntimeError(f"terms page changed, {q!r} not found: re-read it before relying on this skill")
    j = terms.rfind(". ", 0, i) + 1
    print(f"opentransportdata.swiss terms: {terms[j:terms.find('. ', i) + 1].strip()}")

START_JS = """(() => { window.__tch = window.__tch || {}; const id = String(Math.random()).slice(2); window.__tch[id] = null;
  fetch(%s, {credentials: 'omit', headers: %s})
    .then(async r => { window.__tch[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__tch[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__tch[%s]; if (v) delete window.__tch[%s]; return v; })()"""

def raw(url, headers=None, timeout=60):
    rid = json.dumps(js(START_JS % (json.dumps(url), json.dumps(headers or {}))))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{url}: no answer after {timeout}s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r["status"], r["type"], " ".join(r["text"].split())

goto_url(SITE + "/")
wait_for_load()
if js("location.origin") != SITE:
    raise RuntimeError(f"not on {SITE} (at {js('location.href')}): stop")
print()
for path in ("/v1/locations?query=Zurich&type=station",                    # no umlaut
             "/v1/connections?from=Zurich&to=Bern&limit=1",                # loose name, resolved by the API
             "/v1/connections?from=Xyzzyqq&to=Bern&limit=1",               # unknown station
             "/v1/connections?from=8503000&to=8507000&limit=17",           # over the documented 1 - 16
             "/v1/connections?from=8503000&to=8507000&limit=0",            # zero
             "/v1/connections?from=8503000&to=8507000&page=11",            # over 0 - 10
             "/v1/connections?from=8503000&to=8507000&limit=2&date=2026-11-16&time=8am",  # bad time
             "/v1/stationboard?station=Xyzzyqq&limit=3"):                  # unknown stationboard
    s, ct, body = raw(SITE + path)
    if s == 200 and body.startswith("{"):
        d = json.loads(body)
        if "connections" in d:
            body = (f"{len(d['connections'])} connection(s), from={d['from'] and d['from']['name']!r}, "
                    f"departures {[c['from']['departure'][5:16] for c in d['connections']][:4]}")
        elif "stations" in d:
            body = f"stations {[(x['id'], x['name']) for x in d['stations'][:3]]}"
    print(f"{path}: HTTP {s} {body[:150]}")

# Stationboard: the next trains leaving Zurich HB.
s, _, body = raw(SITE + "/v1/stationboard?id=8503000&limit=5&transportations[]=train")
for j in json.loads(body)["stationboard"]:
    st = j["stop"]
    print(f"  board: {st['departure'][11:16]} {j['category']} {j['number']} to {j['to']}, pl {st['platform']}, delay {st['delay']}, "
          f"prognosis.departure {((st['prognosis'] or {}).get('departure') or '')[11:19]}")

# The same call from another site's page: CORS is on, and a custom header still passes the preflight.
print()
goto_url("https://example.com/")
wait_for_load()
for h in (None, {"X-Example": "1"}):
    s, ct, body = raw(SITE + "/v1/locations?query=Bern&type=station", h)
    print(f"from {js('location.origin')} headers={h}: HTTP {s} {ct}, {body[:60]}")
```

Output (from the run on 2026-11-14, 23:35 UTC):

```text
robots.txt: 'User-agent: * Allow: / Sitemap: https://transport.opendata.ch/sitemap.xml'

docs: There is no fixed limit per client.
docs: please cache what you can: the timetable changes twice a week, real-time data every 30 seconds.
docs: An application that asks the same question every few seconds will be throttled.
docs: Cross Origin Resource Sharing (CORS) is enabled, so you can easily use the API on transport.opendata.ch from any website (avoid setting custom headers though).
docs: If several connections depart at the same time they are counted as 1.
docs: If you show the data, please name its source: Timetable data: opentransportdata.swiss.
opentransportdata.swiss terms: The data obtained can be processed, analysed and published, including incorporating additional data.
opentransportdata.swiss terms: Citing sources The URL opentransportdata.swiss must be cited as the source for raw data in publications and analyses that make use of ODMCH data.

/v1/locations?query=Zurich&type=station: HTTP 200 stations [('8503000', 'Zürich HB'), ('8530813', 'Zürich, Kreuzplatz'), ('8530812', 'Zürich, Hegibachplatz')]
/v1/connections?from=Zurich&to=Bern&limit=1: HTTP 200 1 connection(s), from='Zürich HB', departures ['11-15T01:02']
/v1/connections?from=Xyzzyqq&to=Bern&limit=1: HTTP 200 0 connection(s), from=None, departures []
/v1/connections?from=8503000&to=8507000&limit=17: HTTP 400 {"errors":["Maximal value of argument `limit` is 16."]}
/v1/connections?from=8503000&to=8507000&limit=0: HTTP 200 4 connection(s), from='Zürich HB', departures ['11-15T01:02', '11-15T02:02', '11-15T02:30', '11-15T03:35']
/v1/connections?from=8503000&to=8507000&page=11: HTTP 400 {"errors":["Maximal value of argument `page` is 10."]}
/v1/connections?from=8503000&to=8507000&limit=2&date=2026-11-16&time=8am: HTTP 200 2 connection(s), from='Zürich HB', departures ['11-16T05:08', '11-16T05:19']
/v1/stationboard?station=Xyzzyqq&limit=3: HTTP 200 {"station":null,"stationboard":[]}
  board: 00:35 RE N7 to Luzern, pl 6, delay 0, prognosis.departure 00:35:00
  board: 00:35 RE 48 to Schaffhausen, pl 34, delay 0, prognosis.departure 00:35:00
  board: 00:39 S 5 to Zug, pl 41/42, delay 0, prognosis.departure 00:39:00
  board: 00:57 SN 5 to Knonau, pl 41/42, delay 0, prognosis.departure 00:57:00
  board: 00:57 SN 7 to Stäfa, pl 43/44, delay 0, prognosis.departure 00:57:00

from https://example.com headers=None: HTTP 200 application/json, {"stations":[{"id":"8507000","name":"Bern","score":null,"coo
from https://example.com headers={'X-Example': '1'}: HTTP 200 application/json, {"stations":[{"id":"8507000","name":"Bern","score":null,"coo
```

### 3. Same answer with Python urllib (no browser), with a 30 s cache

```python
import json, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime

FROM, TO, N = "Zürich HB", "Bern", 3
API = "https://transport.opendata.ch/v1"
UA = {"User-Agent": "swiss-transport-example/1.0"}
TTL = 30  # docs: real-time data changes "every 30 seconds"; asking the same question every few seconds gets throttled
_cache = {}

def get(path, **params):
    """GET -> parsed JSON, cached for TTL seconds per URL. Waits 30 s once on HTTP 429/500/502/503/504 or a network
    error; HTTP 400 {"errors": [...]} exits."""
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    hit = _cache.get(url)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                data = json.loads(r.read())
                _cache[url] = (time.time(), data)
                time.sleep(1)
                return data
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(30)
                continue
            sys.exit(f"{path}: HTTP {e.code} {e.read().decode()[:160]}")
        except OSError as e:  # URLError (DNS, refused connection), timeouts, resets
            if attempt == 0:
                time.sleep(30)
                continue
            sys.exit(f"{path}: {e}")
    sys.exit(f"{path}: still failing after one retry")

def hm(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z").strftime("%H:%M") if s else "--:--"

def delay(stop):
    d = stop.get("delay")
    return "no real-time" if d is None else "on time" if d == 0 else f"+{d} min"

def next_connections(a, b, n=N):
    data = get("/connections", **{"from": a, "to": b, "limit": n})
    if not data["connections"] or not data["from"] or not data["to"]:
        sys.exit(f"no connections for {a!r} -> {b!r}: stations {data['stations']}")
    return data

data = next_connections(FROM, TO)
print(f"{data['from']['name']} ({data['from']['id']}) -> {data['to']['name']} ({data['to']['id']})")
for c in data["connections"][:N]:
    d, a = c["from"], c["to"]
    changes = [s["departure"]["station"]["name"] for s in c["sections"][1:] if s["journey"]]
    print(f"{hm(d['departure'])} pl {d['platform'] or '?':<6} {delay(d):<12} -> {hm(a['arrival'])} pl {a['platform'] or '?':<4} {delay(a):<12} "
          f"{c['duration'][3:8]} h, {c['transfers']} transfer(s){' at ' + ', '.join(changes) if changes else ''}  {' + '.join(c['products'])}")

t0 = time.time()
again = next_connections(FROM, TO)  # same question within TTL: served from the cache, no request
print(f"second ask: {time.time() - t0:.3f} s, same object: {again is data}")
print("Source: Transport API (transport.opendata.ch), unofficial, by Opendata.ch. Timetable data: opentransportdata.swiss.")
```

Output (from the run on 2026-11-14, 23:36 UTC):

```text
Zürich HB (8503000) -> Bern (8507000)
01:02 pl 16     on time      -> 02:04 pl 9    on time      01:02 h, 0 transfer(s)  IC 8
02:02 pl 31     on time      -> 03:04 pl 9    on time      01:02 h, 0 transfer(s)  IR N1
02:30 pl 41/42  on time      -> 06:21 pl 50   no real-time 03:51 h, 1 transfer(s) at Olten  SN11 + IR 35
second ask: 0.000 s, same object: True
Source: Transport API (transport.opendata.ch), unofficial, by Opendata.ch. Timetable data: opentransportdata.swiss.
```

### 4. curl

```bash
B=https://transport.opendata.ch/v1
UA='swiss-transport-example/1.0'
R='--max-time 60 --retry 1 --retry-delay 30'  # one retry after 30 s on a timeout or HTTP 408/429/500/502/503/504
# Next 3 from Zurich HB (8503000) to Bern (8507000); -G --data-urlencode handles the umlaut and spaces.
curl -sS --fail $R -A "$UA" -G "$B/connections" --data-urlencode 'from=Zürich HB' --data-urlencode 'to=Bern' -d limit=3 | python3 -c '
import json, sys
for c in json.load(sys.stdin)["connections"]:
    d, a = c["from"], c["to"]
    print(d["departure"][11:16], "pl", d["platform"], "delay", d["delay"], "->", a["arrival"][11:16], "pl", a["platform"],
          "delay", a["delay"], "|", c["duration"][3:8], "|", c["transfers"], "transfer(s) |", " + ".join(c["products"]))
'
sleep 1
# A fixed departure time (Monday 08:00): planned data only, so delay is null.
curl -sS --fail $R -A "$UA" -G "$B/connections" -d from=8503000 -d to=8507000 -d limit=3 -d date=2026-11-16 -d time=08:00 \
  -d 'fields[]=connections/from/departure' -d 'fields[]=connections/from/platform' -d 'fields[]=connections/from/delay' \
  -d 'fields[]=connections/to/arrival' -d 'fields[]=connections/transfers' -d 'fields[]=connections/products'; echo
sleep 1
curl -sS $R -A "$UA" -w ' HTTP %{http_code}\n' "$B/connections?from=8503000&to=8507000&limit=17"
```

Output (from the run on 2026-11-14, 23:35 UTC):

```text
01:02 pl 16 delay 0 -> 02:04 pl 9 delay 0 | 01:02 | 0 transfer(s) | IC 8
02:02 pl 31 delay 0 -> 03:04 pl 9 delay 0 | 01:02 | 0 transfer(s) | IR N1
02:30 pl 41/42 delay 0 -> 06:21 pl 50 delay None | 03:51 | 1 transfer(s) | SN11 + IR 35
{"connections":[{"from":{"departure":"2026-11-16T08:02:00+0100","delay":null,"platform":"31"},"to":{"arrival":"2026-11-16T08:58:00+0100"},"transfers":0,"products":["IC 8"]},{"from":{"departure":"2026-11-16T08:06:00+0100","delay":null,"platform":"15"},"to":{"arrival":"2026-11-16T09:24:00+0100"},"transfers":0,"products":["IR 16"]},{"from":{"departure":"2026-11-16T08:08:00+0100","delay":null,"platform":"16"},"to":{"arrival":"2026-11-16T09:24:00+0100"},"transfers":1,"products":["IR 37","IR 16"]}]}
{"errors":["Maximal value of argument `limit` is 16."]} HTTP 400
```

## Fields

From the docs page (https://transport.opendata.ch/docs.html) and the responses in this run.

| Field | Where | Notes |
|---|---|---|
| `from`, `to`, `stations.from[]`, `stations.to[]` | `/connections` top level | the resolved stations; `null` and `[]` when a name matches nothing |
| `from.departure`, `to.arrival` | connection | planned time, ISO 8601 with offset: `2026-11-15T01:02:00+0100` (Swiss local time) |
| `departureTimestamp`, `arrivalTimestamp` | checkpoints | Unix seconds of the planned time |
| `platform` | checkpoints | planned platform, a string: `16`, `41/42` |
| `delay` | checkpoints | minutes (the docs give no unit; on 2026-11-14 23:41 UTC `/stationboard` had SN 9 planned 01:01, `prognosis.departure` 01:02, `delay` 1); `null` "if no prognosis is available" |
| `prognosis.departure`, `prognosis.arrival`, `prognosis.platform` | checkpoints | real-time estimates; `prognosis.platform` was `null` in every call here (docs: "The estimated arrival/departure platform") |
| `duration` | connection | `00d01:02:00` = 0 days, 1 h 02 min |
| `transfers` | connection | number of changes (present in responses, not in the docs table) |
| `products` | connection | `["IC 8"]`, `["SN11", "IR 35"]` |
| `sections[]` | connection | legs: `journey` (`category`, `number`, `name`, `operator`, `to`, `passList`) or `walk` (`{"duration": seconds}`, `journey` null), plus `departure` and `arrival` checkpoints |
| `stationboard[]` | `/stationboard` | `category`, `number`, `name`, `operator`, `to`, and `stop` with `departure`, `platform`, `delay`, `prognosis` |
| `capacity1st`, `capacity2nd` | connection, prognosis | load estimate; `null` in every call here |

## Gotchas

- **Night results.** At 00:33 the third "next" connection left at 02:30 and reached Bern at 06:21 after a 129-minute wait in Olten. The API returns "the connections that are best in arrival time and in the number of changes" (docs), not the fastest; show `duration` and `transfers` with each one.
- **`delay` null is not "on time".** `0` means the real-time feed says on time; `null` means no prognosis (the IR 35 leg at 05:36 and every train on Monday 08:00 had `null`). Say "no real-time" rather than "on time".
- **Platforms are strings.** `41/42` and `43/44` (Zürich HB S-Bahn platforms) do not parse as numbers.
- **Product label spacing differs.** `products` says `SN11` while the leg's `category` + `number` says `SN 11`; `IC 8` has a space in both.
- **Bad dates and times are not errors.** `time=8am` was ignored (the answer started at 05:08 on 16 November, the same as with no `time` at all); `date=16.11.2026` was read as 2026-11-16. Use `YYYY-MM-DD` and `hh:mm` and check the first returned departure.
- **Unknown stations are HTTP 200.** `from=Xyzzyqq` gives `{"connections":[],"from":null,"to":null,...}`; `/stationboard?station=Xyzzyqq` gives `{"station":null,"stationboard":[]}`. Check for empty results.
- **Loose names resolve.** `from=Zurich` planned from Zürich HB, and `/locations?query=Zurich` returned Zürich HB first, then tram stops. Resolve once with `/locations?type=station` and use the id.
- **`limit` edges.** `limit=0` returned 4 connections, not an error; `limit=17` and `page=11` are HTTP 400. Connections departing at the same time count as 1 (docs).
- **Stationboard `prognosis.arrival` at the origin.** Departures from Zürich HB carried a `prognosis.arrival` of `00:31:15` for trains leaving at 00:32 and 00:35, about the time of the request. Use `stop.departure` and `stop.delay`.
- **Custom headers.** The docs say to avoid them; in this run a fetch from example.com with `X-Example: 1` still passed the preflight (`access-control-allow-headers` echoed it). The blocks send none.
- **`operator` is the train company.** Legs show `operator: "SBB"` (the operator name from the timetable data); the API itself is unofficial and run by Opendata.ch.
- **Plain http is served too.** `http://transport.opendata.ch/v1/...` answered HTTP 200 without a redirect; use https.
- **Backend changed on 5 October 2026.** The docs' History: the API now answers from "its own copy of the timetable and its own journey planner. The parameters and the answers of /v1 stay as they were." The docs' Source section and the licenses page name that planner: MOTIS, "Journey planner behind /connections". Older write-ups that mention search.ch as the backend are out of date.
- **No cache headers.** Responses carry `cache-control: no-cache` and no rate-limit headers, so cache on the client (block 3).
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks check `location.origin` and the JSON, not the title.

## What does not work

- **Over-range parameters:** `limit` above 16 or `page` above 10: HTTP 400 `{"errors":["Maximal value of argument ..."]}`.
- **Not tested:** `via[]`, `isArrivalTime=1`, `transportations[]` on `/connections`, `sharedMobility=1`, addresses and coordinates as `from`/`to`, `/locations?x=&y=`, a real platform change, a non-zero delay on `/connections` (every connection in these runs had `delay` 0 or `null`; non-zero values were seen only on `/stationboard`, see Fields), throttling behaviour (never provoked).
