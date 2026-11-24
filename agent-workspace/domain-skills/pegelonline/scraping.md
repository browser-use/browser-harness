# PEGELONLINE - Get the Current Rhine Water Level at Köln, or Any German Federal Waterway Gauge by River, With Its 24-Hour Trend and Its State Against Mean Low and Mean High Water (REST API JSON, no key)

Field-tested against the PEGELONLINE REST API (WSV / ITZBund) on 2026-11-23 (US Pacific afternoon; 23:32-23:46 UTC, already 24 November in German local time) using a fresh Browser Use cloud browser (logged out; one session, 23:34-23:43 UTC) plus Python `urllib` and `curl` from a Linux machine. 17 browser page loads (8 in each of block 2's two runs, 1 in block 1's first run; its second run reused the open guide page) and 32 in-page `fetch()` calls (block 1: 3 per run, block 2: 13 per run, both ran twice), 53 curl calls (29 while exploring the API and the docs, 12 in each of block 4's two runs) and 17 urllib calls (block 3 ran 7 times: empty cache, warm, after the cache expired, the Main at Würzburg, a misspelled gauge, plus two earlier runs before a file-name fix), all serial and at least 1 s apart. Every call was HTTP 200 except the deliberate probes below: HTTP 404 (robots.txt on both hosts, `KOELN`, `XYZ`), HTTP 304 (conditional GETs with `If-None-Match`) and one HTTP 301 (`www.` docs page to the bare host). curl timed 28 answers at 0.50-0.87 s. No 429, no challenge, no key, no login, no cookie needed (answers carry a load-balancer `Set-Cookie`; no block sends it back). Block 1's output below is its second run (23:43 UTC), block 2's its second (started 23:36:36 UTC, after one docs quote was re-cut to match the page's spacing), block 3's its third (empty cache) and fourth (warm), block 4's its second. An independent re-run (23:46-23:56 UTC, fresh cloud browser) reproduced every block one 15-minute step later; it corrected the cache-header gotcha, the Basel and gauge-zero notes, the current-value size, the cookie wording and one block 4 comment. After a code review, blocks 1 and 3 changed and re-ran on 2026-11-24 between 00:28 and 00:36 UTC (browser blocks in a new cloud browser); the outputs shown for them come from those runs. A website review made block 3 stop cleanly when stations.json has no current value for the gauge (tested by deleting it by hand: "KÖLN: no current measurement in stations.json (gauge not reporting): stop") and brought the quick summary in line with block 1's output; block 3's re-run at 01:46 UTC printed the same lines five 15-minute steps later (Köln still 345 cm, last 3 h +0 cm).

robots.txt (checked 2026-11-23, curl, the cloud browser and block 3): https://www.pegelonline.wsv.de/robots.txt and https://pegelonline.wsv.de/robots.txt both answer HTTP 404 with the site's HTML error page. RFC 9309 treats an unavailable (4xx) robots.txt as no restrictions, so every agent, including GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider, may fetch every path this skill uses (`/webservices/rest-api/v2/...` and the docs pages; block 3 checks these 11 agents plus its own User-Agent on every path before it calls it, and stops if the host ever publishes rules that disallow one). Terms: "Nutzungsbedingungen PEGELONLINE", https://pegelonline.wsv.de/gast/nutzungsbedingungen ("Stand: 21.05.2024"): "Informationen, Produkte oder Dienste, die Sie von dieser Website erhalten, dürfen übernommen werden. Dies geschieht auf der Grundlage der Lizenz DL-DE->Zero-2.0" and the data "dürfen für die kommerzielle und nicht kommerzielle Nutzung insbesondere ... in interne und externe Geschäftsprozesse, Produkte und Anwendungen in öffentlichen und nicht öffentlichen elektronischen Netzwerken eingebunden werden" (commercial and non-commercial use, including in applications). The licence text at govdata.de (Datenlizenz Deutschland - Zero - Version 2.0) says "Any use is permitted without restrictions or conditions."; no attribution is required. The webservices overview https://pegelonline.wsv.de/webservice/ueberblick: "Über die PEGELONLINE-Webservices können Drittanbieter kostenlos ihre Angebote mit Daten von PEGELONLINE erweitern." and "Die Wasserstraßen- und Schifffahrtsverwaltung des Bundes (WSV) stellt diese ungeprüften Rohdaten bereit." (unchecked raw data, no liability or warranty for correctness, accuracy, timeliness, reliability or completeness). The REST docs: "Es ist keine Authentifizierung oder Autorisierung erforderlich"; the FAQ: "Sie können die PEGELONLINE Webservices ohne Registrierung verwenden." No AI/ML, scraping, crawling, robot or non-commercial-only wording on the terms page (block 2 scans it; its two hits are the allowing phrase "kommerzielle und nicht kommerzielle Nutzung" and the phone service's "automatisierter Sprachansage"). www.govdata.de/robots.txt has `User-agent: *` / `Disallow: /`, so no block fetches the licence page; the quote above was read once while vetting. Naming: this skill writes "PEGELONLINE (WSV / ITZBund)" in plain text and shows no WSV or federal-eagle logo; it is not affiliated with or endorsed by the WSV, the GDWS or the ITZBund. Every block's output names the source and says what was computed.

## Quick summary

- **No scraping needed.** `GET https://www.pegelonline.wsv.de/webservices/rest-api/v2/stations.json?waters=RHEIN&timeseries=W&includeTimeseries=true&includeCurrentMeasurement=true&includeCharacteristicValues=true` -> every Rhine gauge with its water level (`W`) series, `currentMeasurement {"timestamp", "value", "stateMnwMhw", "stateNswHsw"}` and characteristic values (`MNW`, `MW`, `MHW`, `HSW`, ...) in one call (93 KB, 7 KB gzip). One gauge: `stations/K%C3%96LN/W/currentmeasurement.json` (118 bytes) and `stations/K%C3%96LN/W/measurements.json?start=P1D` (the last 24 h, 96 values). JSON, `Access-Control-Allow-Origin: *`, gzip, `ETag` on everything, no key.
- **Answers (block 1 as shown below, re-run 24 November 2026 00:32 UTC = 01:32 in Köln; the 23:43 UTC run on 23 November gave the same Köln level and trend):** **Köln (Rhine km 688): 345 cm** at 2026-11-24T01:15+01:00, **stateMnwMhw `normal`** (between mean low water MNW 114 cm and mean high water MHW 725 cm; 48 cm above the 2010-2020 mean MW 297 cm), `stateNswHsw` normal (485 cm below the highest navigable level HSW 830 cm). **24 h trend: falling, 368 -> 345 cm (-23 cm)**, steady in the last 3 h (-2 cm). 36 Rhine gauges answered, Konstanz (km 0.5) to Pannerdense Kop (km 867.3); Kaub 223 cm (+15 vs MW), Düsseldorf 301 cm, Duisburg-Ruhrort 457 cm, all `normal` where a state is known.
- **W is not depth.** `W` is cm above the gauge zero (Köln: 35.038 m above NHN, so the surface was 38.49 m above NHN). The help page: "Der Wasserstand am Pegel sagt somit weder etwas über die lokale Wassertiefe noch über den Höhenbezug zum umgebenden Terrain aus."
- **Shortnames need UTF-8 percent-encoding.** `KÖLN` -> `K%C3%96LN`; lower case works (`k%C3%B6ln`), `KOELN` is HTTP 404, and Python `urllib` raises `UnicodeEncodeError` on a raw `Ö`. Some names are mixed case with spaces (`Neuwied Stadt`, `Basel-Rheinhalle`). The `uuid` (Köln `a6ee8177-107b-47dd-bcfd-30960ccc6e9c`) never changes.
- **Rate limits: none published, no rate-limit headers.** Current values carry `Cache-Control: max-age=` 0-59 s (the docs: "zwischen 1 und 60 Sekunden"), series carry an `ETag` (HTTP 304 on repeat). Most inland gauges update every 15 minutes (help page: "Im Binnenbereich wird das Gros der Pegel alle 15 Minuten aktualisiert."), so poll a gauge at most every 15 minutes, use gzip (the Rhine list: 35,548 bytes plain, about 3.7 KB gzip) and conditional GETs, serial, 1 s apart.

## What works

### 1. River -> every gauge's current level and state; one gauge -> now, 24 h trend, mean-water bands (browser)

`on_docs_tab()` opens the logged-out REST-API guide on pegelonline.wsv.de and `fetch()` calls the API on www.pegelonline.wsv.de cross-origin (it sends `Access-Control-Allow-Origin: *`). `get()` returns parsed JSON on HTTP 200, waits once on 429/5xx or a network error and otherwise raises. 3 `fetch()` calls: the river list, the gauge's current value, its last 24 h. Set `RIVER` and `GAUGE` to the shortnames the API uses (`/waters.json` lists rivers).

```python
import email.utils, json, time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

RIVER = "RHEIN"   # waters shortname, as in /waters.json (RHEIN, MAIN, ELBE, DONAU, MOSEL, ...)
GAUGE = "KÖLN"    # station shortname, as in the river list (case-insensitive, umlauts kept)
DOCS = "https://pegelonline.wsv.de/webservice/guideRestapi"
API = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"
STEADY_CM = 2     # this skill's own cut-off for "steady" over the last 3 h; not a WSV term
PAUSE = 1.0       # serial, 1 s apart

def on_docs_tab():
    """fetch() from the logged-out REST-API guide page (the API sends Access-Control-Allow-Origin: *)."""
    try:
        if js("location.href").startswith(DOCS) and "REST-API" in js("document.body.innerText"):
            return
    except Exception:
        pass
    new_tab(DOCS)
    wait_for_load()
    for _ in range(20):
        if "stations.json" in (js("document.body ? document.body.innerText : ''") or ""):
            return
        time.sleep(0.5)
    raise RuntimeError(f"PEGELONLINE guide page did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for the answer
START_JS = """(() => { window.__p = window.__p || {}; const id = String(Math.random()).slice(2); window.__p[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__p[id] = {status: r.status, type: r.headers.get('content-type') || '',
                                         retry: r.headers.get('retry-after'), text: await r.text()}; })
    .catch(e => { window.__p[id] = {status: 0, type: '', retry: null, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__p[%s]; if (v) delete window.__p[%s]; return v; })()"""

def retry_wait(value, default):
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def get(url):
    """-> parsed JSON on HTTP 200. Waits once on 429/5xx or a network error (Retry-After, else 30 s; over 120 s
    stops). Raises on anything else (404 {"status":404,"message":...} = unknown station or time series)."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer after 60s")
            time.sleep(0.2)
        time.sleep(PAUSE)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            wait = retry_wait(r["retry"], 30)
            if wait > 120:
                raise RuntimeError(f"{url}: server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] != 200 or "json" not in r["type"]:
        raise RuntimeError(f"{url}: HTTP {r['status']} {r['type']} {' '.join(r['text'].split())[:160]!r}; stopping")
    return json.loads(r["text"])

ts = lambda s: datetime.fromisoformat(s)          # every JSON timestamp carries its +01:00/+02:00 offset
utc = lambda s: f"{ts(s).astimezone(timezone.utc):%d %b %H:%M} UTC"
cvals = lambda t: {c["shortname"]: c for c in t.get("characteristicValues", [])}
num = lambda v: "-" if v is None else f"{v:g}"

on_docs_tab()
now = datetime.now(timezone.utc)
print(f"PEGELONLINE REST API, checked {now:%Y-%m-%d %H:%M} UTC")

# 1 call: every gauge on the river, its W series, the current value and the characteristic values (MNW, MW, MHW, HSW ...)
river = get(f"{API}/stations.json?waters={quote(RIVER)}&timeseries=W&includeTimeseries=true"
            f"&includeCurrentMeasurement=true&includeCharacteristicValues=true")
if not river:
    raise RuntimeError(f"no gauges for waters={RIVER!r}; see {API}/waters.json for shortnames: stop")
print(f"\n{RIVER}: {len(river)} gauges with a W (water level) series, upstream to downstream by river km")
print(f"  {'km':>7}  {'gauge':<20} {'W cm':>5}  {'measured (local)':<16} {'state':<8} {'vs MW':>6}  MNW/MW/MHW      HSW")
for s in sorted(river, key=lambda s: s.get("km", 0)):
    w = s["timeseries"][0]
    cm, cv = w.get("currentMeasurement") or {}, cvals(w)
    mw = cv.get("MW", {}).get("value")
    dev = f"{cm['value'] - mw:+g}" if mw is not None and "value" in cm else "-"
    band = "/".join(num(cv.get(k, {}).get("value")) for k in ("MNW", "MW", "MHW"))
    print(f"  {s.get('km', 0):>7g}  {s['shortname'][:20]:<20} {num(cm.get('value')):>5}  {cm.get('timestamp', '-')[:16].replace('T', ' '):<16} "
          f"{cm.get('stateMnwMhw', '-'):<8} {dev:>6}  {band:<15} {num(cv.get('HSW', {}).get('value'))}")

hit = [s for s in river if s["shortname"].casefold() == GAUGE.casefold()]
if len(hit) != 1:
    raise RuntimeError(f"{GAUGE!r} is not one gauge on {RIVER}; names: {', '.join(s['shortname'] for s in river)}: stop")
st = hit[0]
w = st["timeseries"][0]
cv = cvals(w)
path = f"{API}/stations/{quote(st['shortname'], safe='')}/W"   # KÖLN -> K%C3%96LN; the uuid works too

# 2 calls: the current value on its own, and the last 24 h (start=P1D, ISO 8601 period; 31 days at most)
cur = get(f"{path}/currentmeasurement.json")
series = get(f"{path}/measurements.json?start=P1D")
if not series:
    raise RuntimeError(f"{GAUGE}: no measurements in the last 24 h: stop")
first, last = series[0], series[-1]
expected = 24 * 60 // w["equidistance"]
gaps = sum(ts(b["timestamp"]) - ts(a["timestamp"]) != timedelta(minutes=w["equidistance"]) for a, b in zip(series, series[1:]))
complete = "no gaps" if not gaps else f"PARTIAL: {gaps} breaks in the {w['equidistance']}-min steps, read the trend with care"
lo, hi = min(series, key=lambda m: m["value"]), max(series, key=lambda m: m["value"])
back3 = [m for m in series if ts(m["timestamp"]) <= ts(last["timestamp"]) - timedelta(hours=3)]
d3 = last["value"] - back3[-1]["value"] if back3 else None
trend = "n/a" if d3 is None else "steady" if abs(d3) <= STEADY_CM else "rising" if d3 > 0 else "falling"
age_h = (now - ts(cur["timestamp"])).total_seconds() / 3600

print(f"\n{st['longname']} ({RIVER} km {st['km']:g}, {st['agency']}, uuid {st['uuid']})")
print(f"  now: W = {cur['value']:g} {w['unit']} at {cur['timestamp']} ({utc(cur['timestamp'])}; {age_h:.1f} h old)")
print(f"  state vs MNW/MHW: {cur['stateMnwMhw']}; vs HSW: {cur['stateNswHsw']}")
if age_h > 25 or cur["stateMnwMhw"] in ("out-dated", "commented"):
    print("  WARNING: value older than 25 h or gauge commented (fault); do not use it or the differences below as current")
for k in ("MNW", "MW", "MHW"):
    if k in cv:
        c = cv[k]
        print(f"    {k:<4} {c['value']:>6g} cm  {c['longname'].strip()} ({c.get('timespanStart', '')[:4]}-{c.get('timespanEnd', '')[:4]}); "
              f"now {cur['value'] - c['value']:+g} cm")
for k in ("HSW", "M_I", "M_II", "GlW"):
    if k in cv:
        print(f"    {k:<4} {cv[k]['value']:>6g} cm  {cv[k]['longname'].strip()}; now {cur['value'] - cv[k]['value']:+g} cm")
if "gaugeZero" in w:
    gz = w["gaugeZero"]
    print(f"  gauge zero {gz['value']:g} {gz['unit']} -> water surface {gz['value'] + cur['value'] / 100:.2f} {gz['unit']} "
          f"(W is height above gauge zero, not water depth)")
print(f"  last 24 h: {len(series)} values ({w['equidistance']}-min steps; {expected} expected, {complete}), "
      f"{first['timestamp'][5:16]} -> {last['timestamp'][5:16]} local")
print(f"    {first['value']:g} -> {last['value']:g} cm ({last['value'] - first['value']:+g} cm in 24 h); "
      f"low {lo['value']:g} at {lo['timestamp'][5:16]}, high {hi['value']:g} at {hi['timestamp'][5:16]}")
print(f"    last 3 h: {'n/a' if d3 is None else f'{d3:+g} cm'} -> {trend} (steady = within +-{STEADY_CM} cm, this skill's cut-off)")
if last["timestamp"] != cur["timestamp"]:
    print(f"    note: currentmeasurement ({cur['timestamp']}) and the series end ({last['timestamp']}) differ")
print("    hourly:", ", ".join(f"{m['timestamp'][11:16]} {m['value']:g}" for m in series if m["timestamp"][14:16] == "00"))
print(f"\nSource: PEGELONLINE (WSV / ITZBund) REST API, DL-DE->Zero-2.0, accessed {now:%d %B %Y %H:%M} UTC. "
      f"Unchecked raw data, no warranty. Trend and differences computed here.")
```

Output (re-run on 2026-11-24 after the code-review fixes, 00:32 UTC, in a new cloud browser; the 23:35 and 23:43 runs on 2026-11-23 printed the same Köln figures, one or four 15-minute steps earlier):

```text
PEGELONLINE REST API, checked 2026-11-24 00:32 UTC

RHEIN: 36 gauges with a W (water level) series, upstream to downstream by river km
       km  gauge                 W cm  measured (local) state     vs MW  MNW/MW/MHW      HSW
      0.5  KONSTANZ-RHEIN         265  2026-11-24 01:15 unknown       -  -/-/-           -
    164.3  Basel-Rheinhalle       630  2026-11-24 01:20 unknown       -  -/-/-           820
    186.2  RHEINWEILER            198  2026-11-24 01:30 normal      -22  192/220/564     -
    227.6  BREISACH               220  2026-11-24 01:15 unknown       -  -/-/-           -
    254.2  RUST                    80  2026-11-24 01:15 unknown       -  -/-/-           -
    270.6  OTTENHEIM              299  2026-11-24 01:15 unknown       -  -/-/-           -
    292.2  KEHL-KRONENHOF         281  2026-11-24 01:15 normal      +45  180/236/426     -
    336.2  IFFEZHEIM              319  2026-11-24 01:15 normal      +79  104/240/518     -
    340.2  PLITTERSDORF           480  2026-11-24 01:15 normal      +69  272/411/687     -
  362.327  MAXAU                  560  2026-11-24 01:15 normal      +64  353/496/785     750
   389.33  PHILIPPSBURG           446  2026-11-24 01:15 normal      +48  254/398/718     -
   400.61  SPEYER                 402  2026-11-24 01:15 normal      +41  214/361/699     730
  424.733  MANNHEIM               303  2026-11-24 01:15 normal      +10  132/293/644     760
   443.37  WORMS                  195  2026-11-24 01:15 normal       +0  46/195/529      650
  480.606  NIERSTEIN-OPPENHEIM    267  2026-11-24 01:15 normal       +8  112/259/554     -
      489  Bodenheim              336  2026-11-24 01:15 unknown       -  -/-/-           -
   498.27  MAINZ                  308  2026-11-24 01:30 normal      +20  159/288/547     630
   518.08  OESTRICH               200  2026-11-24 01:15 normal      +14  79/186/412      -
   528.36  BINGEN                 209  2026-11-24 01:15 normal      +14  84/195/436      490
   546.23  KAUB                   223  2026-11-24 01:30 normal      +15  65/208/544      640
   556.43  SANKT GOAR             335  2026-11-24 01:15 normal      +24  152/311/652     -
   570.45  BOPPARD                263  2026-11-24 01:15 normal      +24  77/239/573      -
   579.98  BRAUBACH               276  2026-11-24 01:15 unknown       -  -/-/-           -
   591.49  KOBLENZ                251  2026-11-24 01:30 normal      +37  60/214/588      650
   608.04  Neuwied Stadt          264  2026-11-24 01:30 unknown       -  -/-/-           -
   613.78  ANDERNACH              302  2026-11-24 01:30 normal      +44  71/258/672      760
   638.19  OBERWINTER             263  2026-11-24 01:15 normal      +45  50/218/597      680
    654.8  BONN                   333  2026-11-24 01:15 normal      +43  121/290/680     -
      688  KÖLN                   345  2026-11-24 01:15 normal      +48  114/297/725     830
    744.2  DÜSSELDORF             301  2026-11-24 01:30 normal      +44  70/257/684      880
    780.8  DUISBURG-RUHRORT       457  2026-11-24 01:15 normal      +63  201/394/835     1130
      814  WESEL                  414  2026-11-24 01:15 normal      +66  144/348/804     1060
    837.4  REES                   350  2026-11-24 01:15 normal      +57  91/293/747      -
    851.9  EMMERICH               287  2026-11-24 01:30 normal      +48  51/239/669      870
      862  LOBITH                 944  2026-11-24 01:20 unknown       -  -/-/-           -
    867.3  PANNERDENSE KOP        904  2026-11-24 01:20 unknown       -  -/-/-           -

KÖLN (RHEIN km 688, STANDORT KÖLN, uuid a6ee8177-107b-47dd-bcfd-30960ccc6e9c)
  now: W = 345 cm at 2026-11-24T01:15:00+01:00 (24 Nov 00:15 UTC; 0.3 h old)
  state vs MNW/MHW: normal; vs HSW: normal
    MNW     114 cm  Mittel der Niedrigwasserstände (2010-2020); now +231 cm
    MW      297 cm  Mittel der Tageswasserstände (2010-2020); now +48 cm
    MHW     725 cm  Mittel der Hochwasserstände (2010-2020); now -380 cm
    HSW     830 cm  höchster Schifffahrtswasserstand; now -485 cm
    M_I     620 cm  Marke_I; now -275 cm
    M_II    830 cm  Marke_II; now -485 cm
    GlW     139 cm  gleichwertiger Wasserstand; now +206 cm
  gauge zero 35.038 m. ü. NHN -> water surface 38.49 m. ü. NHN (W is height above gauge zero, not water depth)
  last 24 h: 96 values (15-min steps; 96 expected, no gaps), 11-23T01:45 -> 11-24T01:30 local
    368 -> 345 cm (-23 cm in 24 h); low 345 at 11-23T21:30, high 368 at 11-23T01:45
    last 3 h: -2 cm -> steady (steady = within +-2 cm, this skill's cut-off)
    note: currentmeasurement (2026-11-24T01:15:00+01:00) and the series end (2026-11-24T01:30:00+01:00) differ
    hourly: 02:00 368, 03:00 368, 04:00 368, 05:00 368, 06:00 367, 07:00 367, 08:00 366, 09:00 365, 10:00 364, 11:00 362, 12:00 361, 13:00 358, 14:00 356, 15:00 354, 16:00 352, 17:00 351, 18:00 349, 19:00 349, 20:00 348, 21:00 347, 22:00 346, 23:00 346, 00:00 345, 01:00 345

Source: PEGELONLINE (WSV / ITZBund) REST API, DL-DE->Zero-2.0, accessed 24 November 2026 00:32 UTC. Unchecked raw data, no warranty. Trend and differences computed here.
```

### 2. robots.txt, the terms and docs quotes, and what the API does with mistakes (browser)

8 page loads (2 robots.txt files, 5 docs and terms pages, back to the guide page) and 13 in-page `fetch()` calls in the same tab. `www.` docs URLs redirect to the bare host; the API answers on both.

```python
import json, re, time

API = "https://www.pegelonline.wsv.de/webservices/rest-api/v2"
SITE = "https://pegelonline.wsv.de"

START_JS = """(() => { window.__p = window.__p || {}; const id = String(Math.random()).slice(2); window.__p[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__p[id] = {status: r.status, type: r.headers.get('content-type') || '', text: await r.text()}; })
    .catch(e => { window.__p[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__p[%s]; if (v) delete window.__p[%s]; return v; })()"""

def raw(url):
    """One in-page GET, no retries: inspection only. 1 s after each call."""
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1)
    return r

def page(url, wait_for=None):
    """Load a page, wait for a phrase, return (HTTP status, final URL, whitespace-collapsed text)."""
    goto_url(url)
    wait_for_load()
    for _ in range(20):
        txt = js("document.body ? document.body.innerText : (document.documentElement.textContent || '')") or ""
        if not wait_for or wait_for in txt:
            break
        time.sleep(0.5)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("location.href"), " ".join(txt.split())

for host in ("www.pegelonline.wsv.de", "pegelonline.wsv.de"):
    st, final, txt = page(f"https://{host}/robots.txt")
    agents = sorted(set(re.findall(r"(?i)user-agent:\s*(\S+)", txt)))
    print(f"robots.txt {host:<23} HTTP {st}: user-agent groups {agents or 'none'}; {txt[:60]!r}")

checks = [
    ("/gast/nutzungsbedingungen", [
        "Stand: 21.05.2024",
        "Informationen, Produkte oder Dienste, die Sie von dieser Website erhalten, dürfen übernommen werden. Dies geschieht auf der Grundlage der Lizenz DL-DE->Zero-2.0",
        "kommerzielle und nicht kommerzielle Nutzung",
        "in interne und externe Geschäftsprozesse, Produkte und Anwendungen in öffentlichen und nicht öffentlichen elektronischen Netzwerken eingebunden werden",
        "keine Haftung und Gewährleistung für die inhaltliche Richtigkeit"]),
    ("/webservice/ueberblick", [
        "Über die PEGELONLINE-Webservices können Drittanbieter kostenlos ihre Angebote mit Daten von PEGELONLINE erweitern.",
        "Die Wasserstraßen- und Schifffahrtsverwaltung des Bundes (WSV) stellt diese ungeprüften Rohdaten bereit.",
        "Die Schnittstelle befindet sich derzeit in der Beta-Phase und kann sich noch inkompatibel ändern."]),
    ("/webservice/dokuRestapi", [
        "Es ist keine Authentifizierung oder Autorisierung erforderlich, um die PEGELONLINE REST-API zu nutzen.",
        "Es können Daten für die letzten 31 Tage bezogen werden.",
        "Alle Zeitangaben erfolgen in lokaler gesetzlicher Zeit (MEZ/MESZ mit Sommerzeitumstellung)",
        "Aktueller Wasserstand veraltet (älter als 25 Stunden)",
        "Dieser Zeitraum ist relativ kurz und liegt zwischen 1 und 60 Sekunden.",
        "Alle HTTP-Antworten der PEGELONLINE REST-API werden mit einem Etag HTTP-Header ausgestattet."]),
    ("/gast/hilfe", [
        "Der Wasserstand am Pegel sagt somit weder etwas über die lokale Wassertiefe noch über den Höhenbezug zum umgebenden Terrain aus.",
        "Im Binnenbereich wird das Gros der Pegel alle 15 Minuten aktualisiert.",
        "Bei Erreichen dieser Marken (Hochwasser) treten unterschiedliche Beschränkungen (z.B. Sperrungen) für die Schifffahrt im jeweiligen Gewässerabschnitt in Kraft"]),
    ("/webservice/faq", ["Sie können die PEGELONLINE Webservices ohne Registrierung verwenden."]),
]
words = r"\bKI\b|künstlich|\bAI\b|maschinell|scrap|crawl|robot|automatisiert\w*|nicht kommerziell\w*|nichtkommerziell\w*"
for path, needles in checks:
    st, final, txt = page("https://www.pegelonline.wsv.de" + path, needles[0][:25])
    print(f"\n{path} -> HTTP {st} {final}")
    for needle in needles:
        print(f"  {'found' if ' '.join(needle.split()) in txt else 'MISSING'}: {needle[:95]!r}")
    if path == "/gast/nutzungsbedingungen":
        for m in re.finditer(words, txt, re.I):
            print(f"  word {m[0]!r} in: ...{txt[max(0, m.start() - 40):m.end() + 25]}...")
        print(f"  words /{words}/: {len(re.findall(words, txt, re.I))} hit(s)")
print()

def brief(r):
    out = f"HTTP {r['status']} {r['type'].split(';')[0] or '-'} {len(r['text']):,} chars"
    if "json" not in r["type"]:
        return out + f" {' '.join(r['text'].split())[:60]!r}"
    d = json.loads(r["text"])
    if isinstance(d, list) and d and "timestamp" in d[0]:
        return out + f" {len(d)} values, {d[0]['timestamp']} .. {d[-1]['timestamp']}"
    if isinstance(d, list):
        return out + f" {len(d)} stations: {[s['shortname'] for s in d][:4]}"
    return out + " " + json.dumps(d, ensure_ascii=False)[:110]

page(SITE + "/webservice/guideRestapi", "stations.json")  # fetch() from the logged-out guide page
for label, url in (
    ("Köln, upper case, encoded       ", f"{API}/stations/K%C3%96LN/W/currentmeasurement.json"),
    ("köln, lower case                ", f"{API}/stations/k%C3%B6ln/W/currentmeasurement.json"),
    ("Köln by uuid                    ", f"{API}/stations/a6ee8177-107b-47dd-bcfd-30960ccc6e9c/W/currentmeasurement.json"),
    ("KOELN (oe instead of Ö)         ", f"{API}/stations/KOELN/W/currentmeasurement.json"),
    ("unknown station XYZ             ", f"{API}/stations/XYZ.json"),
    ("Neuwied Stadt (space, mixed)    ", f"{API}/stations/Neuwied%20Stadt/W/currentmeasurement.json"),
    ("Köln Q (discharge), m3/s        ", f"{API}/stations/K%C3%96LN/Q/currentmeasurement.json"),
    ("Köln start=P40D (over 31 days)  ", f"{API}/stations/K%C3%96LN/W/measurements.json?start=P40D"),
    ("fuzzyId=köln                    ", f"{API}/stations.json?fuzzyId=k%C3%B6ln"),
    ("fuzzyId=koeln                   ", f"{API}/stations.json?fuzzyId=koeln"),
    ("waters=rhein (lower case)       ", f"{API}/stations.json?waters=rhein"),
    ("waters=RHINE (English)          ", f"{API}/stations.json?waters=RHINE"),
    ("Rhine km 688 +-20 km            ", f"{API}/stations.json?waters=RHEIN&km=688&radius=20"),
):
    print(f"{label} {brief(raw(url))}")
print("\nSource: PEGELONLINE (WSV / ITZBund), DL-DE->Zero-2.0; answers shortened to the fields shown.")
```

Output (from the second run, started 2026-11-23 23:36:36 UTC; the first run, started 23:36:01, printed the same apart from one docs quote that it searched with different spacing and reported MISSING):

```text
robots.txt www.pegelonline.wsv.de  HTTP 404: user-agent groups none; 'Hilfe Links Impressum Nutzungsbedingungen Datenschutzhinweis'
robots.txt pegelonline.wsv.de      HTTP 404: user-agent groups none; 'Hilfe Links Impressum Nutzungsbedingungen Datenschutzhinweis'

/gast/nutzungsbedingungen -> HTTP 200 https://pegelonline.wsv.de/gast/nutzungsbedingungen
  found: 'Stand: 21.05.2024'
  found: 'Informationen, Produkte oder Dienste, die Sie von dieser Website erhalten, dürfen übernommen we'
  found: 'kommerzielle und nicht kommerzielle Nutzung'
  found: 'in interne und externe Geschäftsprozesse, Produkte und Anwendungen in öffentlichen und nicht öf'
  found: 'keine Haftung und Gewährleistung für die inhaltliche Richtigkeit'
  word 'nicht kommerzielle' in: ...tadaten dürfen für die kommerzielle und nicht kommerzielle Nutzung insbesondere ver...
  word 'automatisierter' in: ... Speicherwerte und Durchfahrtshöhen per automatisierter Sprachansage abgefragt w...
  words /\bKI\b|künstlich|\bAI\b|maschinell|scrap|crawl|robot|automatisiert\w*|nicht kommerziell\w*|nichtkommerziell\w*/: 2 hit(s)

/webservice/ueberblick -> HTTP 200 https://pegelonline.wsv.de/webservice/ueberblick
  found: 'Über die PEGELONLINE-Webservices können Drittanbieter kostenlos ihre Angebote mit Daten von PEG'
  found: 'Die Wasserstraßen- und Schifffahrtsverwaltung des Bundes (WSV) stellt diese ungeprüften Rohdate'
  found: 'Die Schnittstelle befindet sich derzeit in der Beta-Phase und kann sich noch inkompatibel änder'

/webservice/dokuRestapi -> HTTP 200 https://pegelonline.wsv.de/webservice/dokuRestapi
  found: 'Es ist keine Authentifizierung oder Autorisierung erforderlich, um die PEGELONLINE REST-API zu '
  found: 'Es können Daten für die letzten 31 Tage bezogen werden.'
  found: 'Alle Zeitangaben erfolgen in lokaler gesetzlicher Zeit (MEZ/MESZ mit Sommerzeitumstellung)'
  found: 'Aktueller Wasserstand veraltet (älter als 25 Stunden)'
  found: 'Dieser Zeitraum ist relativ kurz und liegt zwischen 1 und 60 Sekunden.'
  found: 'Alle HTTP-Antworten der PEGELONLINE REST-API werden mit einem Etag HTTP-Header ausgestattet.'

/gast/hilfe -> HTTP 200 https://pegelonline.wsv.de/gast/hilfe
  found: 'Der Wasserstand am Pegel sagt somit weder etwas über die lokale Wassertiefe noch über den Höhen'
  found: 'Im Binnenbereich wird das Gros der Pegel alle 15 Minuten aktualisiert.'
  found: 'Bei Erreichen dieser Marken (Hochwasser) treten unterschiedliche Beschränkungen (z.B. Sperrunge'

/webservice/faq -> HTTP 200 https://pegelonline.wsv.de/webservice/faq
  found: 'Sie können die PEGELONLINE Webservices ohne Registrierung verwenden.'

Köln, upper case, encoded        HTTP 200 application/json 118 chars {"timestamp": "2026-11-24T00:30:00+01:00", "value": 345.0, "stateMnwMhw": "normal", "stateNswHsw": "normal"}
köln, lower case                 HTTP 200 application/json 118 chars {"timestamp": "2026-11-24T00:30:00+01:00", "value": 345.0, "stateMnwMhw": "normal", "stateNswHsw": "normal"}
Köln by uuid                     HTTP 200 application/json 118 chars {"timestamp": "2026-11-24T00:30:00+01:00", "value": 345.0, "stateMnwMhw": "normal", "stateNswHsw": "normal"}
KOELN (oe instead of Ö)          HTTP 404 application/json 62 chars {"status": 404, "message": "Current measurement does not exist."}
unknown station XYZ              HTTP 404 application/json 50 chars {"status": 404, "message": "Station does not exist."}
Neuwied Stadt (space, mixed)     HTTP 200 application/json 120 chars {"timestamp": "2026-11-24T00:30:00+01:00", "value": 266.0, "stateMnwMhw": "unknown", "stateNswHsw": "unknown"}
Köln Q (discharge), m3/s         HTTP 200 application/json 65 chars {"timestamp": "2026-11-24T00:00:00+01:00", "value": 2210.0}
Köln start=P40D (over 31 days)   HTTP 200 application/json 225,884 chars 3074 values, 2026-10-23T01:15:00+02:00 .. 2026-11-24T00:30:00+01:00
fuzzyId=köln                     HTTP 200 application/json 362 chars 1 stations: ['KÖLN']
fuzzyId=koeln                    HTTP 200 application/json 2 chars 0 stations: []
waters=rhein (lower case)        HTTP 200 application/json 13,571 chars 36 stations: ['KONSTANZ-RHEIN', 'Basel-Rheinhalle', 'RHEINWEILER', 'BREISACH']
waters=RHINE (English)           HTTP 200 application/json 2 chars 0 stations: []
Rhine km 688 +-20 km             HTTP 200 application/json 362 chars 1 stations: ['KÖLN']

Source: PEGELONLINE (WSV / ITZBund), DL-DE->Zero-2.0; answers shortened to the fields shown.
```

### 3. One gauge with Python urllib: robots check for every agent, a 24-hour CSV, trend and state (cache by max-age and ETag, no browser)

`python3 block3.py [RIVER GAUGE]` (default `RHEIN KÖLN`). 3 calls with an empty cache: robots.txt, the river list (to find the gauge and its MNW/MW/MHW/HSW) and the 24 h series. A warm run reuses the river list while its `max-age` lasts and sends `If-None-Match` for the series. Writes `pegelonline-<gauge>-24h.csv` (local time with offset, UTC, cm; three columns on every row, the source line goes to the terminal).

```python
import csv, email.utils, gzip, hashlib, json, os, re, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

RIVER, GAUGE = (sys.argv[1], sys.argv[2]) if len(sys.argv) == 3 else ("RHEIN", "KÖLN")
UA = "pegelonline-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
HOST = "www.pegelonline.wsv.de"
API = f"https://{HOST}/webservices/rest-api/v2"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider", "pegelonline-skill-example"]  # last = this script's UA
CACHE_DIR = "~/.cache/pegelonline-skill"
CACHE = os.path.expanduser(CACHE_DIR)
SLUG = re.sub(r"[^a-z0-9]+", "-", GAUGE.lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))).strip("-")
OUT = f"pegelonline-{SLUG}-24h.csv"  # in the current directory
STEADY_CM = 2   # this skill's own cut-off for "steady" over the last 3 h
PAUSE = 1.0     # serial, 1 s apart
calls = []

def retry_wait(value, default):
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(timezone.utc)).total_seconds()) + 1)
    except (TypeError, ValueError):
        return default

def http(url, headers=None, ok=(200,)):
    """GET with gzip -> (status, headers, body). Statuses in `ok` (and 304) are returned. Waits once on 429/5xx or a
    network error (Retry-After, else 30 s; over 120 s exits); exits on anything else."""
    for attempt in range(2):
        time.sleep(PAUSE)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip", **(headers or {})})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
                calls.append(r.status)
                return r.status, r.headers, gzip.decompress(body) if r.headers.get("Content-Encoding") == "gzip" else body
        except urllib.error.HTTPError as e:
            calls.append(e.code)
            if e.code == 304 or e.code in ok:
                return e.code, e.headers, b""
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                wait = retry_wait(e.headers.get("Retry-After"), 30)
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                time.sleep(wait)
                continue
            sys.exit(f"HTTP {e.code} {url}: {' '.join(e.read().decode(errors='replace').split())[:160]}")
        except OSError as e:
            if attempt == 0:
                time.sleep(30)
                continue
            sys.exit(f"{url}: {e}")

def cached(url):
    """-> (data, how). Reuses a copy while Cache-Control max-age (1-60 s per the docs) lasts; else If-None-Match
    with the stored ETag (HTTP 304 = unchanged); else downloads."""
    f = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest() + ".json")
    try:
        with open(f) as fh:
            old = json.load(fh)
    except (OSError, ValueError):
        old = None
    if old and time.time() < old["until"]:
        return old["data"], "cache (fresh)"
    st, h, body = http(url, {"If-None-Match": old["etag"]} if old and old.get("etag") else None)
    m = re.search(r"max-age=(\d+)", h.get("Cache-Control") or "")
    until = time.time() + int(m[1]) if m else 0
    data = old["data"] if st == 304 else json.loads(body)
    os.makedirs(CACHE, exist_ok=True)
    with open(f, "w") as fh:
        json.dump({"etag": h.get("ETag") or (old or {}).get("etag"), "until": until, "data": data}, fh)
    return data, "HTTP 304" if st == 304 else f"HTTP {st}, {len(body):,} bytes unzipped"

# robots.txt groups and RFC 9309 matching (longest pattern wins, Allow on a tie); a 4xx robots.txt means no rules
def robots_groups(text):
    groups, agents, in_rules = {}, [], False
    for line in text.splitlines():
        k, _, v = line.split("#")[0].partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            agents, in_rules = (agents if not in_rules else []) + [v.lower()], False
            for a in agents:
                groups.setdefault(a, [])
        elif k in ("allow", "disallow") and agents:
            in_rules = True
            for a in agents:
                if v:
                    groups[a].append((k == "allow", v))
    return groups

def allowed(groups, agent, path):
    rules = groups.get(agent.lower(), groups.get("*", []))
    hits = [(len(p), ok) for ok, p in rules
            if re.match(re.escape(p.rstrip("$")).replace(r"\*", ".*") + ("$" if p.endswith("$") else ""), path)]
    return max(hits, default=(0, True))[1]

ts = datetime.fromisoformat   # every JSON timestamp carries its +01:00/+02:00 offset
now = datetime.now(timezone.utc)
river_url = (f"{API}/stations.json?waters={quote(RIVER)}&timeseries=W&includeTimeseries=true"
             f"&includeCurrentMeasurement=true&includeCharacteristicValues=true")

# 1) robots.txt for the API host, for every agent; the gauge's own path is checked in 3) once its exact shortname is known
paths = ["/webservices/rest-api/v2/stations.json"]
st, _, body = http(f"https://{HOST}/robots.txt", ok=(200, 404))
groups = robots_groups(body.decode(errors="replace")) if st == 200 else {}
bad = [(a, p) for a in AGENTS for p in paths if st == 200 and not allowed(groups, a, p)]
print(f"robots.txt {HOST}: HTTP {st}" + (" (no rules: RFC 9309 treats 4xx as allow-all)" if 400 <= st < 500 else "")
      + f"; stations.json x {len(AGENTS)} agents: {len(paths) * len(AGENTS) - len(bad)} allowed; the gauge's path is checked before its call")
if bad or st >= 500:
    sys.exit("robots.txt disallows (or could not be read for) a path this skill uses: stop")

# 2) the river's gauges with current W and characteristic values (one call)
river, how_r = cached(river_url)
hit = [s for s in river if s["shortname"].casefold() == GAUGE.casefold()]
if len(hit) != 1:
    sys.exit(f"{GAUGE!r} is not one gauge on {RIVER!r} ({len(river)} gauges): {', '.join(s['shortname'] for s in river) or 'none; see /waters.json'}")
s = hit[0]
w = s["timeseries"][0]
cur = w.get("currentMeasurement")   # missing when the gauge sends no value
if not cur:
    sys.exit(f"{s['shortname']}: no current measurement in stations.json (gauge not reporting): stop")
cv = {c["shortname"]: c["value"] for c in w.get("characteristicValues", [])}
age_h = (now - ts(cur["timestamp"])).total_seconds() / 3600
print(f"\n{s['longname']} ({RIVER} km {s['km']:g}) [{how_r}; {len(river)} gauges on {RIVER}]")
print(f"  W {cur['value']:g} {w['unit']} at {cur['timestamp']} ({age_h:.1f} h old); stateMnwMhw {cur['stateMnwMhw']}, "
      f"stateNswHsw {cur['stateNswHsw']}")
print("  " + ", ".join(f"{k} {cv[k]:g} ({cur['value'] - cv[k]:+g})" for k in ("MNW", "MW", "MHW", "HSW") if k in cv))
if age_h > 25 or cur["stateMnwMhw"] in ("out-dated", "commented"):
    print("  WARNING: value older than 25 h or gauge commented (fault); do not use it as current")

# 3) the last 24 h (15-minute steps on most inland gauges); ETag lets a repeat run get HTTP 304
mpath = f"/webservices/rest-api/v2/stations/{quote(s['shortname'], safe='')}/W/measurements.json"
if any(not allowed(groups, a, mpath) for a in AGENTS):
    sys.exit(f"robots.txt disallows {mpath}: stop")
series, how_m = cached(f"https://{HOST}{mpath}?start=P1D")
if not series:
    sys.exit(f"{GAUGE}: no measurements in the last 24 h: stop")
gaps = sum(ts(b["timestamp"]) - ts(a["timestamp"]) != timedelta(minutes=w["equidistance"]) for a, b in zip(series, series[1:]))
complete = "no gaps" if not gaps else f"PARTIAL: {gaps} breaks in the {w['equidistance']}-min steps"
last = series[-1]
back3 = [m for m in series if ts(m["timestamp"]) <= ts(last["timestamp"]) - timedelta(hours=3)]
d3 = last["value"] - back3[-1]["value"] if back3 else None
trend = "n/a" if d3 is None else "steady" if abs(d3) <= STEADY_CM else "rising" if d3 > 0 else "falling"
vals = [m["value"] for m in series]
with open(OUT, "w", newline="") as fh:
    out = csv.writer(fh)
    out.writerow(["timestamp_local", "timestamp_utc", "w_cm"])
    for m in series:
        out.writerow([m["timestamp"], ts(m["timestamp"]).astimezone(timezone.utc).isoformat(), m["value"]])
print(f"  24 h [{how_m}]: {len(series)} values ({complete}) {series[0]['timestamp']} .. {last['timestamp']} -> {OUT}")
print(f"  {series[0]['value']:g} -> {last['value']:g} cm ({last['value'] - series[0]['value']:+g}); min {min(vals):g}, max {max(vals):g}; "
      f"last 3 h {'n/a' if d3 is None else f'{d3:+g}'} cm -> {trend}")
print(f"\ncalls this run: {len(calls)} ({', '.join(map(str, calls))}); cache {CACHE_DIR}")
print("Source: PEGELONLINE (WSV / ITZBund) REST API, DL-DE->Zero-2.0. Unchecked raw data, no warranty; trend computed here.")
```

Output (re-run on 2026-11-24 after the code-review fixes, 00:33:38 UTC, empty cache; the 23:37 UTC run on 2026-11-23 printed the same figures four 15-minute steps earlier):

```text
robots.txt www.pegelonline.wsv.de: HTTP 404 (no rules: RFC 9309 treats 4xx as allow-all); stations.json x 12 agents: 12 allowed; the gauge's path is checked before its call

KÖLN (RHEIN km 688) [HTTP 200, 92,979 bytes unzipped; 36 gauges on RHEIN]
  W 345 cm at 2026-11-24T01:30:00+01:00 (0.1 h old); stateMnwMhw normal, stateNswHsw normal
  MNW 114 (+231), MW 297 (+48), MHW 725 (-380), HSW 830 (-485)
  24 h [HTTP 200, 7,106 bytes unzipped]: 96 values (no gaps) 2026-11-23T01:45:00+01:00 .. 2026-11-24T01:30:00+01:00 -> pegelonline-koeln-24h.csv
  368 -> 345 cm (-23); min 345, max 368; last 3 h -2 cm -> steady

calls this run: 3 (404, 200, 200); cache ~/.cache/pegelonline-skill
Source: PEGELONLINE (WSV / ITZBund) REST API, DL-DE->Zero-2.0. Unchecked raw data, no warranty; trend computed here.
```

5 seconds later: 2 calls instead of 3 (river list still fresh, series HTTP 304). 73 s later, after the list's `max-age` had passed, a gauge on the Rhine had reported in between, so the list came back HTTP 200 and the series HTTP 304 (3 calls: 404, 200, 304). On 2026-11-23 at 23:39 UTC, with no new value in between, the same wait gave HTTP 304 for both.

```text
robots.txt www.pegelonline.wsv.de: HTTP 404 (no rules: RFC 9309 treats 4xx as allow-all); stations.json x 12 agents: 12 allowed; the gauge's path is checked before its call

KÖLN (RHEIN km 688) [cache (fresh); 36 gauges on RHEIN]
  W 345 cm at 2026-11-24T01:30:00+01:00 (0.1 h old); stateMnwMhw normal, stateNswHsw normal
  MNW 114 (+231), MW 297 (+48), MHW 725 (-380), HSW 830 (-485)
  24 h [HTTP 304]: 96 values (no gaps) 2026-11-23T01:45:00+01:00 .. 2026-11-24T01:30:00+01:00 -> pegelonline-koeln-24h.csv
  368 -> 345 cm (-23); min 345, max 368; last 3 h -2 cm -> steady

calls this run: 2 (404, 304); cache ~/.cache/pegelonline-skill
Source: PEGELONLINE (WSV / ITZBund) REST API, DL-DE->Zero-2.0. Unchecked raw data, no warranty; trend computed here.
```

Another river (`python3 block3.py MAIN WÜRZBURG`, 00:35 UTC) and a misspelled gauge (`RHEIN KOELN`, which stops and lists the names):

```text
robots.txt www.pegelonline.wsv.de: HTTP 404 (no rules: RFC 9309 treats 4xx as allow-all); stations.json x 12 agents: 12 allowed; the gauge's path is checked before its call

WÜRZBURG (MAIN km 251.97) [HTTP 200, 38,146 bytes unzipped; 13 gauges on MAIN]
  W 229 cm at 2026-11-24T01:30:00+01:00 (0.1 h old); stateMnwMhw normal, stateNswHsw normal
  MNW 140 (+89), MW 174 (+55), MHW 515 (-286), HSW 340 (-111)
  24 h [HTTP 200, 7,106 bytes unzipped]: 96 values (no gaps) 2026-11-23T01:45:00+01:00 .. 2026-11-24T01:30:00+01:00 -> pegelonline-wuerzburg-24h.csv
  226 -> 229 cm (+3); min 223, max 233; last 3 h +4 cm -> rising

calls this run: 3 (404, 200, 200); cache ~/.cache/pegelonline-skill
Source: PEGELONLINE (WSV / ITZBund) REST API, DL-DE->Zero-2.0. Unchecked raw data, no warranty; trend computed here.
robots.txt www.pegelonline.wsv.de: HTTP 404 (no rules: RFC 9309 treats 4xx as allow-all); stations.json x 12 agents: 12 allowed; the gauge's path is checked before its call
'KOELN' is not one gauge on 'RHEIN' (36 gauges): KONSTANZ-RHEIN, Basel-Rheinhalle, RHEINWEILER, BREISACH, RUST, OTTENHEIM, KEHL-KRONENHOF, IFFEZHEIM, PLITTERSDORF, MAXAU, PHILIPPSBURG, SPEYER, MANNHEIM, WORMS, NIERSTEIN-OPPENHEIM, Bodenheim, MAINZ, OESTRICH, BINGEN, KAUB, SANKT GOAR, BOPPARD, BRAUBACH, KOBLENZ, Neuwied Stadt, ANDERNACH, OBERWINTER, BONN, KÖLN, DÜSSELDORF, DUISBURG-RUHRORT, WESEL, REES, EMMERICH, LOBITH, PANNERDENSE KOP
```

### 4. curl, headers and mistakes

```bash
A=https://www.pegelonline.wsv.de/webservices/rest-api/v2
UA='pegelonline-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# Köln now: W in cm above gauge zero, local time with offset, state vs MNW/MHW and vs HSW
curl -sS --fail -A "$UA" "$A/stations/K%C3%96LN/W/currentmeasurement.json?prettyprint=false"; echo
sleep 1
# the whole Rhine list in one call; six gauges shown (km, name, cm, time, state)
curl -sS --fail --compressed -A "$UA" "$A/stations.json?waters=RHEIN&timeseries=W&includeTimeseries=true&includeCurrentMeasurement=true&prettyprint=false" \
  | python3 -c 'import sys, json
d = json.load(sys.stdin); print(len(d), "Rhine gauges")
for s in d:
    if s["shortname"] in ("KAUB", "KOBLENZ", "BONN", "KÖLN", "DÜSSELDORF", "DUISBURG-RUHRORT"):
        c = s["timeseries"][0]["currentMeasurement"]; print(" ", s["km"], s["shortname"], c["value"], "cm", c["timestamp"], c["stateMnwMhw"])'
sleep 1
# last 2 hours as CSV (semicolon, local time without offset)
curl -sS --fail -A "$UA" "$A/stations/K%C3%96LN/W/measurements.csv?start=PT2H"
sleep 1
# headers of the 24 h series: no max-age (series only carry no-transform), an ETag, CORS open
H=$(mktemp)
curl -sS --compressed -A "$UA" -D "$H" -o /dev/null "$A/stations/K%C3%96LN/W/measurements.json?start=P1D"
tr -d '\r' < "$H" | grep -iE '^(HTTP/|(content-type|cache-control|expires|etag|access-control-allow-origin|retry-after|x-ratelimit-[a-z]+):)'
E=$(tr -d '\r' < "$H" | sed -n 's/^etag: //Ip')
sleep 1
curl -sS --compressed -A "$UA" -H "If-None-Match: $E" -o /dev/null -w 'same 24 h with If-None-Match -> HTTP %{http_code}, %{size_download} bytes\n' "$A/stations/K%C3%96LN/W/measurements.json?start=P1D"
sleep 1
curl -sS -A "$UA" -o /dev/null -w 'Rhine list without gzip -> %{size_download} bytes; ' "$A/stations.json?waters=RHEIN&includeTimeseries=true&includeCurrentMeasurement=true"; sleep 1
curl -sS --compressed -A "$UA" -o /dev/null -w 'with gzip -> %{size_download} bytes, %{time_total} s\n' "$A/stations.json?waters=RHEIN&includeTimeseries=true&includeCurrentMeasurement=true"
sleep 1
# mistakes
curl -sS -A "$UA" -w ' <- KOELN, HTTP %{http_code}\n' "$A/stations/KOELN/W/currentmeasurement.json"; sleep 1
curl -sS -A "$UA" -w ' <- XYZ, HTTP %{http_code}\n' "$A/stations/XYZ.json"; sleep 1
curl -sS -A "$UA" "$A/stations/K%C3%96LN/W/measurements.json?start=P40D&prettyprint=false" \
  | python3 -c 'import sys, json; d = json.load(sys.stdin); print("start=P40D ->", len(d), "values from", d[0]["timestamp"])'; sleep 1
curl -sS -A "$UA" -o /dev/null -w 'robots.txt www -> HTTP %{http_code} %{content_type}\n' https://www.pegelonline.wsv.de/robots.txt; sleep 1
curl -sS -A "$UA" -o /dev/null -w 'robots.txt apex -> HTTP %{http_code} %{content_type}\n' https://pegelonline.wsv.de/robots.txt
echo "Source: PEGELONLINE (WSV / ITZBund), DL-DE->Zero-2.0, accessed $(date -u '+%d %B %Y %H:%M') UTC; unchecked raw data; lists cut to the gauges shown."
rm -f "$H"
```

Output (second run, 2026-11-23 23:45 UTC, after a comment-only edit; the first run at 23:40 printed the same apart from the moving window: its CSV ended at 00:30, its ETag differed and `start=P40D` gave 3,074 values):

```text
{"timestamp":"2026-11-24T00:30:00+01:00","value":345.0,"stateMnwMhw":"normal","stateNswHsw":"normal"}
36 Rhine gauges
  546.23 KAUB 222.0 cm 2026-11-24T00:30:00+01:00 normal
  591.49 KOBLENZ 251.0 cm 2026-11-24T00:30:00+01:00 normal
  654.8 BONN 333.0 cm 2026-11-24T00:30:00+01:00 normal
  688.0 KÖLN 345.0 cm 2026-11-24T00:30:00+01:00 normal
  744.2 DÜSSELDORF 303.0 cm 2026-11-24T00:30:00+01:00 normal
  780.8 DUISBURG-RUHRORT 458.0 cm 2026-11-24T00:30:00+01:00 normal
timestamp;value
2026-11-23 23:00;346
2026-11-23 23:15;348
2026-11-23 23:30;345
2026-11-23 23:45;345
2026-11-24 00:00;345
2026-11-24 00:15;346
2026-11-24 00:30;345
2026-11-24 00:45;345
HTTP/1.1 200 200
Access-Control-Allow-Origin: *
Cache-Control: no-transform
Content-Type: application/json;charset=UTF-8
ETag: "06a4f012301f64ecd8596b3188391fb55"
same 24 h with If-None-Match -> HTTP 304, 0 bytes
Rhine list without gzip -> 35548 bytes; with gzip -> 3724 bytes, 0.710550 s
{"status":404,"message":"Current measurement does not exist."} <- KOELN, HTTP 404
{"status":404,"message":"Station does not exist."} <- XYZ, HTTP 404
start=P40D -> 3075 values from 2026-10-23T01:15:00+02:00
robots.txt www -> HTTP 404 text/html;charset=UTF-8
robots.txt apex -> HTTP 404 text/html;charset=UTF-8
Source: PEGELONLINE (WSV / ITZBund), DL-DE->Zero-2.0, accessed 23 November 2026 23:46 UTC; unchecked raw data; lists cut to the gauges shown.
```

## Fields

| Field | Value (Köln, 23 Nov 2026) | Notes |
|---|---|---|
| station `uuid`, `number` | `a6ee8177-107b-47dd-bcfd-30960ccc6e9c`, `2730010` | the uuid is "Eindeutige unveränderliche ID" (docs); works in every path in place of the shortname |
| `shortname`, `longname` | `KÖLN` | up to 40 / 255 characters; mostly upper case German with umlauts, some mixed case with spaces |
| `km`, `agency`, `longitude`, `latitude` | `688.0`, `STANDORT KÖLN`, `6.9633`, `50.936949` | river kilometre; WGS84 |
| `water.shortname` | `RHEIN` | the `waters=` value; German names (`RHINE` returns `[]`) |
| `timeseries[].shortname`, `.unit`, `.equidistance` | `W`, `cm`, `15` | W water level, Q discharge (m³/s; Köln's latest `Q` was stamped 00:00 while `W` was at 00:30), WT water temperature, DFH bridge clearance, LT, O2, PH; `equidistance` = minutes between values |
| `currentMeasurement.timestamp`, `.value` | `2026-11-24T00:30:00+01:00`, `345.0` | local legal time with offset (+01:00 winter, +02:00 summer) |
| `currentMeasurement.stateMnwMhw` | `normal` | `low` (W <= MNW), `normal`, `high` (W >= MHW), `unknown` (no MNW/MHW), `commented` (fault, see the series' `comment`), `out-dated` (older than 25 h); only on `W` |
| `currentMeasurement.stateNswHsw` | `normal` | the same against the highest navigable level HSW (no `low`) |
| `gaugeZero.value`, `.unit`, `.validFrom` | `35.038`, `m. ü. NHN`, `2019-11-01` | surface height = gauge zero + W/100; missing on 3 of the 36 Rhine gauges (KONSTANZ-RHEIN and the two Dutch gauges); Basel-Rheinhalle gives `mü.M.` |
| `characteristicValues[]` (`includeCharacteristicValues=true`) | `MNW 114`, `MW 297`, `MHW 725` (2010-11-01 to 2020-10-31), `HSW 830`, `M_I 620`, `M_II 830`, `GlW 139`, `TuGLW 250`, `HHW 1069` (1926), `NNW 69` (2018-10-23) | cm; `timespanStart/End`, `validFrom` or `occurrences` give the period; HSW and Marke I/II are shipping limits (help page: at these marks restrictions such as closures apply) |
| measurement `timestamp`, `value` | ISO with offset, number | `measurements.json?start=P1D` (ISO 8601 period or timestamp, optional `end`); `.csv` gives `timestamp;value` in local time without offset; `.png` a chart |
| error body | `{"status":404,"message":"Station does not exist."}` | JSON, also for unknown series ("Current measurement does not exist.") |
| headers | `Content-Type: application/json;charset=UTF-8`, `ETag`, `Access-Control-Allow-Origin: *`, `Cache-Control: max-age=N, must-revalidate, ...` on lists and current values (N counts down to a shared `Expires`, seen 0-59), `Cache-Control: no-transform` on series | no `Retry-After` or `X-RateLimit-*` seen |

## Gotchas

- **Encode shortnames as UTF-8.** `K%C3%96LN` and `k%C3%B6ln` work (matching is case-insensitive); `KOELN` (oe for Ö) gets HTTP 404 "Current measurement does not exist." (or "Station does not exist." on the station resource), `fuzzyId=koeln` returns `[]` while `fuzzyId=k%C3%B6ln` finds KÖLN. curl sends a raw `Ö` as UTF-8 and works; Python `urllib` raises `UnicodeEncodeError: 'ascii' codec can't encode character '\xd6'`. Use `urllib.parse.quote(name, safe='')`, or the uuid.
- **Names are not uniformly upper case.** The Rhine list has `Basel-Rheinhalle`, `Bodenheim` and `Neuwied Stadt` (space -> `%20`) among upper-case names. Match case-insensitively against the river list, as blocks 1 and 3 do.
- **W is height above gauge zero, not depth.** Gauge zeros differ along the river (Köln 35.038 m, Kaub 67.669 m above NHN), so W values from different gauges are not comparable with each other; compare each gauge with its own MNW/MW/MHW. The fairway depth needs `GlW` and `TuGLW`, which only some gauges have (17 of the 36 Rhine gauges).
- **Times are local, with an offset that changes.** JSON timestamps end in `+01:00` or `+02:00`; the 31-day Köln series switched at `2026-10-25T02:45:00+02:00 -> 2026-10-25T02:00:00+01:00`, so the local clock times 02:00-02:45 appear twice. Parse with `datetime.fromisoformat` and compare as aware datetimes. The CSV has no offset ("2026-11-24 00:30") and is ambiguous on that night.
- **The API answers in local time; your clock may be on the next day.** At 23:35 UTC on 23 November the newest Köln value was 2026-11-24T00:30+01:00. Block 1 prints both.
- **31 days of history, silently capped.** The docs: "Es können Daten für die letzten 31 Tage bezogen werden." `start=P40D` returned HTTP 200 with 3,074 values from 2026-10-23T01:15+02:00 (32 days), not an error. Older water levels and discharges ("in der Regel" since 1 January 2000, per the help page) are a download on the website, not this API.
- **`unknown` is not "fine".** 10 of the 36 Rhine gauges (Konstanz-Rhein, Basel-Rheinhalle, Breisach, Rust, Ottenheim, Bodenheim, Braubach, Neuwied Stadt, Lobith, Pannerdense Kop) report `stateMnwMhw` `unknown` because they have no MNW/MHW. `commented` means a fault; `out-dated` means older than 25 h. Block 3 warns on both.
- **Foreign gauges have other references.** Basel-Rheinhalle (BUNDESAMT FÜR UMWELT CH) has 5-minute values (`equidistance` 5), a gauge zero in `mü.M.` instead of m. ü. NHN, and only GlW, M_I, M_II and HSW; Lobith (943-944 cm) and Pannerdense Kop (903-904 cm), both RIJKSWATERSTAAT, have no `gaugeZero` and no characteristic values in the answer. Do not compare them with German gauges.
- **`timeseries=W` filters gauges.** On the Main, the plain list has 16 stations but `timeseries=W` 13: `HANAU BRÜCKE DFH` and `AUHEIM BRÜCKE DFH` only measure bridge clearance (`DFH`), `KLEINOSTHEIM_WUK` only oxygen and water temperature (`O2`, `WT`). Without the filter, pick the `W` series by `shortname`, not by position.
- **Characteristic values are reference statistics, not live records.** Köln lists `NNW` 69 cm (lowest known daily mean, 2018-10-23), but the 31-day series held 808 quarter-hour values below 69 cm, lowest 56 cm at 2026-11-09T01:45+01:00. Quarter-hour values are not daily means, and the data are unchecked raw data; say so when you quote a "record".
- **Unchecked raw data.** The WSV publishes "ungeprüfte Rohdaten" with no warranty; spikes and gaps can occur. The 24 h Köln series had all 96 expected values; blocks 1 and 3 check that every step is `equidistance` minutes and print PARTIAL otherwise. The count alone can read 95 without a gap: `start=P1D` slides with the clock, so the oldest value can drop out before the newest one is published (2026-11-24 00:30 UTC run).
- **`max-age` is a countdown, and series have none.** Lists and current values get `max-age` = seconds left until a shared `Expires` time, the same on both hosts (six alternating calls to www. and the bare host at 23:51:49-23:51:57 UTC gave 31, 30, 28, 26, 25, 23, all with `Expires` 23:52:21), so a call just before that time sees `max-age=0`. Series (`measurements.json`) have only `Cache-Control: no-transform` and an `ETag`. Use `If-None-Match`; it returned HTTP 304 with 0 bytes.
- **HyDAS is Beta.** The overview says of the HyDAS API: "Die Schnittstelle befindet sich derzeit in der Beta-Phase und kann sich noch inkompatibel ändern." This skill uses the REST API v2 only; the SOAP service is no longer developed.
- **The Rhine list's `km` is a float with up to 3 decimals** (`362.327`); `km=688&radius=20` on `waters=RHEIN` returned only KÖLN (Bonn is 33 km upstream).
- **Tab marker.** The harness may set the tab title to a horse emoji; the blocks check the URL and the page text, not the title.

## What does not work

- **Shortnames with umlauts written out** (`KOELN`, `DUESSELDORF`): HTTP 404; English river names (`waters=RHINE`): empty list.
- **More than 31 days from the REST API**: capped without an error (see Gotchas).
- **Water depth or fairway depth as a field**: not in the API; W is height above gauge zero.
- **Forecasts on most gauges**: water-level forecasts (`WV`, `includeForecastTimeseries=true&hasTimeseries=WV`) exist only at some stations; not tested here.
- **Not tested:** the 429 response (never provoked), forecast series, `Terminwerte`, the Elbe-Oder fairway depths, the HyDAS API, WMS/WFS/SOS, the EDIS MQTT streams, `measurements.png`, `limit`/`offset` paging and the SOAP service.
