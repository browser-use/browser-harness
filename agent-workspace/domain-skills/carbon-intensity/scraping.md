# Carbon Intensity API - Greenest 2-Hour Window in the Next 24 Hours for a GB Postcode (official keyless API)

Field-tested against api.carbonintensity.org.uk on 2026-11-12 using a fresh Browser Use cloud browser (logged out) plus Python urllib and `curl` from a Linux server. 7 browser page loads and 26 in-page `fetch()` calls, about 60 curl calls (API, robots files, docs, terms) and 1 urllib call, all serial at 1 s or more spacing: every API call was HTTP 200 except the deliberate HTTP 400 probes below. No 429, no challenge, no key, no login.

robots.txt (checked 2026-11-12, curl and the cloud browser): https://api.carbonintensity.org.uk/robots.txt has no robots file: it answers HTTP 200 `application/json` `{"error": {"code": "400 Bad Request", "message": "Please enter a valid path e.g. /intensity/"}}`, the same for User-Agent `*`, GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, Claude-SearchBot, anthropic-ai, Google-Extended, PerplexityBot, Perplexity-User, CCBot, Bytespider, Applebot-Extended and Meta-ExternalAgent: no rules, no named AI-agent groups. The docs host https://carbon-intensity.github.io/robots.txt is HTTP 404 (no rules). carbonintensity.org.uk and www.carbonintensity.org.uk return HTTP 403 `application/xml` (S3 AccessDenied) for robots.txt; this skill does not use them. Terms: the "API Terms of Use" linked from the docs (https://github.com/carbon-intensity/terms, last commit 2024-10-01) license the API under CC BY 4.0, "for free", "anywhere in the world". Forbidden: "Sell, lease, or sublicense the Carbon Intensity API or access to it", any application "that substantially replaces the core user experience of [the owner's] websites, apps, or the Carbon Intensity API", implying endorsement, spam, malware, concealing your identity, and use "that undermines the stability of the host servers" (the owner "applies a rate limit and may block applications that make a large number of calls to the API"). No AI/ML, scraping, automated-access or non-commercial clause. §2 Trademark asks for "prior approval in writing ... before any use of [the owner's] logo or word mark", so this skill names only the API ("Carbon Intensity API", carbonintensity.org.uk), shows no logo and does not write the owner's name. This skill answers one household question from the public API and does not rebuild the API or its site.

**Attribution:** CC BY 4.0 requires credit, a licence link and a note of changes (§3(a)(1)); §3(a)(2) allows "providing a URI or hyperlink to a resource that includes the required information". Credit "Carbon Intensity API (https://api.carbonintensity.org.uk, docs https://carbon-intensity.github.io/api-definitions)", link https://creativecommons.org/licenses/by/4.0/ and say the 2-hour average is your calculation. The docs page carries the licensor's own credit, so the link covers it without writing the word mark. Blocks 1 and 3 print that line.

## Quick summary

- **No scraping.** `GET https://api.carbonintensity.org.uk/regional/intensity/<from>/fw24h/postcode/M1` returns 48 half-hour forecasts for the region that M1 belongs to: **North West England** (regionid 3, Electricity North West). Each slot is `{from, to, intensity: {forecast, index}, generationmix[]}` in gCO2/kWh.
- **Answer for M1 on 2026-11-12 23:32 UTC:** best 2-hour window **Fri 13 Nov 02:00-04:00 UK time (GMT)**, forecast average **21.5 gCO2/kWh** ('very low', wind about 44%). Starting at the next half hour (00:00) averaged 22.2; the worst window (07:00-09:00) averaged 53.2. When the spread is this small, any night slot is fine.
- **Outward code only.** `M1`, `SW1A`, `EH8`. `M1 1AE` is HTTP 400 "No postcode match can be found."; lower case `m1` works.
- **Great Britain only.** `BT1` (Belfast) is HTTP 400 on `/regional/postcode/`, and **HTTP 200 with body `null`** on the fw24h route. Check `data` is present, never just the status.
- **UTC, 30-minute slots.** Convert to `Europe/London` (GMT in winter, BST in summer). The first fw24h slot is the half hour already running; the blocks start at the next half hour and stop at now + 24 h.
- **Regional = forecast only.** National `/intensity` also has `actual` (estimated): 96 forecast, 100 actual for Great Britain at 23:00-23:30 UTC, against 22 in North West England.
- **Rate limit:** the terms say one applies but publish no number; no rate-limit headers. Blocks pace 1 s per call, serial, and wait 30 s once on 429/5xx.

## What works

### 1. Best 2-hour window in the next 24 hours for M1 (browser)

`on_api_tab()` opens `/intensity` on api.carbonintensity.org.uk once, so `fetch()` is same-origin. `get()` returns the response's `data` on HTTP 200, waits 30 s once on 429/5xx and otherwise raises, including on the silent `null`/`{}` bodies, so an error never looks like a forecast. The block checks the region, the slot chain and the time window, then slides a 4-slot window over the forecast.

```python
import json, time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

OUTCODE = "M1"  # outward code only (M1, SW1A, EH8); "M1 1AE" is rejected
HOURS = 2       # how long the appliance runs; the window is HOURS x 2 half-hour slots

SITE = "https://api.carbonintensity.org.uk"
LOCAL = ZoneInfo("Europe/London")  # the API speaks UTC; GB clocks are GMT in winter, BST in summer
PAUSE = 1.0  # terms: a rate limit applies (no number published); keep calls serial

def on_api_tab():
    """fetch() runs same-origin from a logged-out api.carbonintensity.org.uk tab (/intensity, plain JSON). Reuse it."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SITE + "/intensity")
    wait_for_load()
    body = js("document.body ? document.body.innerText : ''") or ""
    if js("location.origin") != SITE or '"intensity"' not in body:
        raise RuntimeError(f"api.carbonintensity.org.uk did not serve /intensity (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__ci = window.__ci || {}; const id = String(Math.random()).slice(2); window.__ci[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/json'}})
    .then(async r => { window.__ci[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__ci[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__ci[%s]; if (v) delete window.__ci[%s]; return v; })()"""

def get(path, timeout=30):
    """GET SITE+path from inside the tab -> the response's "data". Errors are {"error": {"code": "400 Bad Request", ...}}.
    An unknown outcode on the fw24h route is HTTP 200 with body null, a far-future date is HTTP 200 {}: both raise here.
    Waits 30 s once on 429/5xx, raises on anything else, so an error never looks like a forecast."""
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
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
        d = json.loads(r["text"])
        if not isinstance(d, dict) or "error" in d or not d.get("data"):
            raise RuntimeError(f"{path}: no data ({' '.join(r['text'].split())[:160]!r}); "
                               "Great Britain outward codes only (no Northern Ireland BT, no full postcode)")
        return d["data"]

def t(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)

def hm(dt):
    return dt.astimezone(LOCAL).strftime("%a %H:%M")

on_api_tab()

# 1. Which region the outcode maps to, and its current half hour.
cur = get(f"/regional/postcode/{OUTCODE}")[0]
c = cur["data"][0]
mix = {m["fuel"]: m["perc"] for m in c["generationmix"]}
print(f"{OUTCODE} -> region {cur['regionid']} {cur['shortname']} ({cur['dnoregion']})")
print(f"  latest slot {c['from']}..{c['to']} UTC: forecast {c['intensity']['forecast']} gCO2/kWh '{c['intensity']['index']}', "
      f"wind {mix.get('wind', 0)}%, nuclear {mix.get('nuclear', 0)}%, gas {mix.get('gas', 0)}%")

# 2. The next 24 hours, half hour by half hour.
now = datetime.now(timezone.utc)
reg = get(f"/regional/intensity/{now:%Y-%m-%dT%H:%MZ}/fw24h/postcode/{OUTCODE}")
if reg["regionid"] != cur["regionid"]:
    raise RuntimeError(f"fw24h region {reg['regionid']} differs from postcode lookup {cur['regionid']}: stop")
slots = [(t(s["from"]), t(s["to"]), s["intensity"]["forecast"], s["intensity"]["index"],
          {m["fuel"]: m["perc"] for m in s["generationmix"]}) for s in reg["data"]]
for a, b in zip(slots, slots[1:]):
    if a[1] != b[0] or b[1] - b[0] != timedelta(minutes=30):
        raise RuntimeError(f"gap or odd slot between {a[0]} and {b[0]}: stop")

# The first slot is the one already running; start at the next half hour and stay inside now + 24 h.
start = now.replace(second=0, microsecond=0)
if start.minute % 30:
    start += timedelta(minutes=30 - start.minute % 30)
usable = [s for s in slots if s[0] >= start and s[1] <= now + timedelta(hours=24)]
n = HOURS * 2
if len(usable) < n:
    raise RuntimeError(f"only {len(usable)} future slots: stop")
print(f"\nnow {now:%Y-%m-%d %H:%M} UTC ({hm(now)} UK); {len(reg['data'])} slots returned "
      f"{reg['data'][0]['from']}..{reg['data'][-1]['to']}, {len(usable)} usable from {start:%H:%M} UTC")

wins = [(sum(s[2] for s in usable[i:i + n]) / n, i) for i in range(len(usable) - n + 1)]
best_avg, bi = min(wins)
worst_avg, wi = max(wins)
now_avg = wins[0][0]
best = usable[bi:bi + n]
lo = min(usable, key=lambda s: s[2])
hi = max(usable, key=lambda s: s[2])
print(f"slot range: {lo[2]} ({hm(lo[0])}) .. {hi[2]} ({hm(hi[0])}) gCO2/kWh")
print(f"\nbest {HOURS} h window: {hm(best[0][0])} - {hm(best[-1][1])} UK time "
      f"({best[0][0]:%Y-%m-%d %H:%M}..{best[-1][1]:%H:%M} UTC), average {best_avg:.1f} gCO2/kWh")
for s in best:
    print(f"  {s[0]:%H:%M}-{s[1]:%H:%M} UTC  {s[2]:>3} '{s[3]}'  wind {s[4].get('wind', 0)}%  gas {s[4].get('gas', 0)}%")
ties = [i for a, i in wins if a == best_avg]
if len(ties) > 1:
    print(f"  ({len(ties)} windows tie at {best_avg:.1f}; earliest shown)")
print(f"starting at the next half hour instead ({hm(usable[0][0])}): {now_avg:.1f}; "
      f"worst window ({hm(usable[wi][0])}): {worst_avg:.1f} gCO2/kWh")

print(f"\nanswer: run the dishwasher {hm(best[0][0])} - {hm(best[-1][1])} (UK time), "
      f"forecast average {best_avg:.0f} gCO2/kWh in {reg['shortname']} ({OUTCODE}).")
print("  Source: Carbon Intensity API (https://api.carbonintensity.org.uk, docs https://carbon-intensity.github.io/api-definitions),")
print("  regional forecast, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); the 2-hour average is our calculation.")
```

Output (from the run on 2026-11-12, 23:32 UTC):

```text
M1 -> region 3 North West England (Electricity North West)
  latest slot 2026-11-12T23:00Z..2026-11-12T23:30Z UTC: forecast 22 gCO2/kWh 'very low', wind 45.7%, nuclear 39.9%, gas 5.6%

now 2026-11-12 23:32 UTC (Thu 23:32 UK); 48 slots returned 2026-11-12T23:30Z..2026-11-13T23:30Z, 47 usable from 00:00 UTC
slot range: 21 (Fri 00:00) .. 54 (Fri 08:30) gCO2/kWh

best 2 h window: Fri 02:00 - Fri 04:00 UK time (2026-11-13 02:00..04:00 UTC), average 21.5 gCO2/kWh
  02:00-02:30 UTC   22 'very low'  wind 43.6%  gas 5.6%
  02:30-03:00 UTC   21 'very low'  wind 43.9%  gas 5.3%
  03:00-03:30 UTC   21 'very low'  wind 43.9%  gas 5.3%
  03:30-04:00 UTC   22 'very low'  wind 43.9%  gas 5.5%
  (2 windows tie at 21.5; earliest shown)
starting at the next half hour instead (Fri 00:00): 22.2; worst window (Fri 07:00): 53.2 gCO2/kWh

answer: run the dishwasher Fri 02:00 - Fri 04:00 (UK time), forecast average 22 gCO2/kWh in North West England (M1).
  Source: Carbon Intensity API (https://api.carbonintensity.org.uk, docs https://carbon-intensity.github.io/api-definitions),
  regional forecast, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); the 2-hour average is our calculation.
```

### 2. Docs, robots.txt and error shapes (browser)

Reads three lines and the terms and licence links from the docs page, then makes 8 small calls from an api.carbonintensity.org.uk page: robots.txt, lower case, and six deliberate errors. It does not open the terms on github.com (github.com/robots.txt has `User-agent: Bytespider` / `Disallow: /`); read them yourself at the link.

```python
import json, time
from datetime import datetime, timezone

SITE = "https://api.carbonintensity.org.uk"
DOCS = "https://carbon-intensity.github.io/api-definitions/"

# The API docs, as the page shows them: outward code rule, licence, terms link.
new_tab(DOCS)
wait_for_load()
text = " ".join((js("document.body.innerText") or "").split())
if "Carbon Intensity API" not in text:
    raise RuntimeError(f"the docs page did not load (at {js('location.href')}): stop")
for q in ("Base URL:", "Do not include full postcode", "The maximum date range is limited to"):
    i = text.find(q)
    if i < 0:
        raise RuntimeError(f"docs changed, {q!r} not found: re-read {DOCS} before relying on this skill")
    print(f"docs: {text[i:i + 150].split(' Email:')[0].rstrip()}\n")
links = js("""[...document.querySelectorAll('a')].filter(a => /terms|creativecommons/i.test(a.href)).map(a => a.textContent.trim() + ' -> ' + a.href)""")
print(f"docs links: {sorted(set(links))}\n")

# Same-origin probes from an api.carbonintensity.org.uk page, same tab. No retries: this block only inspects answers.
goto_url(SITE + "/intensity")
wait_for_load()
if js("location.origin") != SITE:
    raise RuntimeError(f"not on {SITE} (at {js('location.href')}): stop")

START_JS = """(() => { window.__ci = window.__ci || {}; const id = String(Math.random()).slice(2); window.__ci[id] = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { window.__ci[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__ci[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__ci[%s]; if (v) delete window.__ci[%s]; return v; })()"""

def raw(path, timeout=30):
    rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > timeout:
            raise RuntimeError(f"{path}: no answer after {timeout}s")
        time.sleep(0.3)
    time.sleep(1.0)
    return r["status"], r["type"], " ".join(r["text"].split())

now = f"{datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ}"
for path in ("/robots.txt",                                   # no robots file: a JSON error with HTTP 200
             "/regional/postcode/m1",                         # lower case is fine
             "/regional/postcode/M1%201AE",                   # full postcode
             "/regional/postcode/BT1",                        # Belfast: Northern Ireland is not on the GB grid
             "/regional/postcode/M",                          # too short
             f"/regional/intensity/{now}/fw24h/postcode/BT1",  # same outcode on the forecast route
             "/regional/intensity/2026-13-01T00:00Z/fw24h/postcode/M1",
             "/regional/intensity/2027-06-01T00:00Z/fw24h/postcode/M1"):  # beyond the forecast horizon
    s, ct, body = raw(path)
    print(f"{path}: HTTP {s} {ct} {body[:110]}")
```

Output (from the run on 2026-11-12, 23:45 UTC):

```text
docs: Base URL: api.carbonintensity.org.uk Further Information Methodology: National Forecast and Regional Forecast Terms: API Terms of Use

docs: Do not include full postcode, outward postcode only. Example responses { "data":[ { "regionid": 3, "dnoregion": "Electricity North West", "shortname":

docs: The maximum date range is limited to 14 days. All times provided in UTC (+00:00). Parameters Parameter In Type Required Description from path string t

docs links: ['API Terms of Use -> https://github.com/carbon-intensity/terms', 'CC BY 4.0 -> https://creativecommons.org/licenses/by/4.0/']

/robots.txt: HTTP 200 application/json { "error": { "code": "400 Bad Request", "message": "Please enter a valid path e.g. /intensity/" } }
/regional/postcode/m1: HTTP 200 application/json {"data":[{"regionid":3,"dnoregion":"Electricity North West","shortname":"North West England","postcode":"M1","
/regional/postcode/M1%201AE: HTTP 400 application/json { "error": { "code": "400 Bad Request", "message": "No postcode match can be found." } }
/regional/postcode/BT1: HTTP 400 application/json { "error": { "code": "400 Bad Request", "message": "No postcode match can be found." } }
/regional/postcode/M: HTTP 400 application/json { "error": { "code": "400 Bad Request", "message": "Please enter a valid outward postcode i.e. EH8, TF8, TN23,
/regional/intensity/2026-11-12T23:45Z/fw24h/postcode/BT1: HTTP 200 application/json null
/regional/intensity/2026-13-01T00:00Z/fw24h/postcode/M1: HTTP 400 application/json { "error": { "code": "400 Bad Request", "message": "Please enter a valid datetime in ISO8601 format YYYY-MM-DD
/regional/intensity/2027-06-01T00:00Z/fw24h/postcode/M1: HTTP 200 application/json {}
```

### 3. Same answer with Python urllib (no browser)

Python's default User-Agent got HTTP 200.

```python
import json, sys, time, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

OUTCODE, HOURS = "M1", 2  # outward code only; appliance run length in hours
API = "https://api.carbonintensity.org.uk"
UK = ZoneInfo("Europe/London")

def get(path):
    """GET -> the response's "data". Python's default User-Agent got HTTP 200. Unknown outcode on fw24h: HTTP 200 null."""
    try:
        with urllib.request.urlopen(urllib.request.Request(API + path, headers={"Accept": "application/json"}), timeout=30) as r:
            d = json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"{path}: HTTP {e.code} {e.read().decode()[:160]}")  # e.g. 400 "No postcode match can be found."
    time.sleep(1)  # a rate limit applies (terms); stay serial
    if not isinstance(d, dict) or not d.get("data"):
        sys.exit(f"{path}: no data ({json.dumps(d)[:120]}); GB outward codes only")
    return d["data"]

t = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
now = datetime.now(timezone.utc)
reg = get(f"/regional/intensity/{now:%Y-%m-%dT%H:%MZ}/fw24h/postcode/{OUTCODE}")
start = now.replace(second=0, microsecond=0)
start += timedelta(minutes=(30 - start.minute % 30) % 30)  # next half hour; the first slot is already running
slots = [(t(s["from"]), t(s["to"]), s["intensity"]["forecast"]) for s in reg["data"]]
slots = [s for s in slots if s[0] >= start and s[1] <= now + timedelta(hours=24)]
n = HOURS * 2
if len(slots) < n or any(b[0] != a[1] for a, b in zip(slots, slots[1:])):
    sys.exit(f"{len(slots)} slots or a gap in the forecast: stop")
avg, i = min((sum(s[2] for s in slots[j:j + n]) / n, j) for j in range(len(slots) - n + 1))
a, b = slots[i][0].astimezone(UK), slots[i + n - 1][1].astimezone(UK)
print(f"{reg['shortname']} ({OUTCODE}), {len(slots)} half hours from {start:%H:%M} UTC")
print(f"best {HOURS} h: {a:%a %d %b %H:%M}-{b:%H:%M} {b:%Z}, average {avg:.1f} gCO2/kWh "
      f"(slots {[s[2] for s in slots[i:i + n]]})")
print("Source: Carbon Intensity API (api.carbonintensity.org.uk), CC BY 4.0; the average is calculated.")
```

Output (from the run on 2026-11-12, 23:34 UTC):

```text
North West England (M1), 47 half hours from 00:00 UTC
best 2 h: Fri 13 Nov 02:00-04:00 GMT, average 21.5 gCO2/kWh (slots [22, 21, 21, 22])
Source: Carbon Intensity API (api.carbonintensity.org.uk), CC BY 4.0; the average is calculated.
```

### 4. curl

```bash
B=https://api.carbonintensity.org.uk
curl -sS --fail -H 'Accept: application/json' "$B/regional/postcode/M1" | python3 -c '
import json, sys
r = json.load(sys.stdin)["data"][0]; s = r["data"][0]
wind = next(m["perc"] for m in s["generationmix"] if m["fuel"] == "wind")
print(r["shortname"], s["from"], "->", s["to"], "UTC:", s["intensity"]["forecast"], "gCO2/kWh", repr(s["intensity"]["index"]), "wind", wind, "%")
'
sleep 1
curl -sS --fail "$B/intensity"; echo    # Great Britain as a whole: forecast and estimated actual
sleep 1
curl -sS -o /dev/null -w 'full postcode (M1 1AE): HTTP %{http_code} %{content_type}\n' "$B/regional/postcode/M1%201AE"
```

Output (from the run on 2026-11-12, 23:34 UTC):

```text
North West England 2026-11-12T23:00Z -> 2026-11-12T23:30Z UTC: 22 gCO2/kWh 'very low' wind 45.7 %
{ 
  "data":[{ 
    "from": "2026-11-12T23:00Z",
    "to": "2026-11-12T23:30Z",
    "intensity": {
      "forecast": 96,
      "actual": 100,
      "index": "moderate"
    }
  }]
}
full postcode (M1 1AE): HTTP 400 application/json
```

## Fields

| Field | Where | Notes |
|---|---|---|
| `regionid`, `shortname`, `dnoregion` | regional | `3`, `North West England`, `Electricity North West` for M1; `13`, `London`, `UKPN London` for SW1A |
| `postcode` | regional | the outward code, upper-cased (`m1` -> `M1`) |
| `from`, `to` | every slot | `YYYY-MM-DDThh:mmZ`, UTC, 30 minutes apart |
| `intensity.forecast` | every slot | gCO2/kWh, integer |
| `intensity.actual` | national `/intensity` only | estimated; `null` for future slots; absent on regional slots |
| `intensity.index` | every slot | `very low`, `low`, `moderate`, `high`, `very high` (docs) |
| `generationmix[]` | regional slots, `/generation` | `{fuel, perc}` for biomass, coal, imports, gas, nuclear, other, hydro, solar, wind; percent of generation |
| response shape | | `/regional/postcode/<oc>`: `data` is a list `[ {region..., data: [slot]} ]`; `/regional/intensity/.../fw24h/postcode/<oc>`: `data` is one object `{region..., data: [48 slots]}` (the docs example shows a list) |

## Gotchas

- **Silent empty answers.** On `/regional/intensity/<from>/fw24h/postcode/<oc>`, an unknown or non-GB outcode (`BT1`, `ZZ99`, `M1 1AE`) is HTTP 200 with body `null`; a `from` beyond the forecast (`2027-06-01T00:00Z`) is HTTP 200 `{}`. Only a malformed date is HTTP 400.
- **`from` picks the slot that contains it, with a boundary quirk.** `from=23:28Z` and `23:28` (no Z) gave 48 slots 23:00..23:00 next day; `from=23:30Z` (exact boundary) gave 49 slots 23:00..23:30; `from=23:31Z` gave 48 slots 23:30..23:30. A bare date `2026-11-12` gave 49 slots from 2026-11-11T23:30Z. Filter by slot times yourself (block 1) instead of trusting the count.
- **The "current" slot lags.** At 23:29 UTC `/regional/postcode/M1` still returned 22:30-23:00; at 23:32 it returned 23:00-23:30. Read `from`/`to`, never assume it is now.
- **fw48h exists** (`/regional/intensity/<from>/fw48h/postcode/<oc>`, 96 slots). The docs say `/intensity/<from>/<to>` "is limited to 14 days", but on 2026-11-12 a 30-day national range (`2026-10-01T00:00Z/2026-10-31T00:00Z`) still returned HTTP 200 with 1441 slots: the cap is not enforced, so keep ranges to 14 days yourself and do not rely on it to bound a response.
- **It is a forecast.** Regional values are forecasts for the whole region, not for the postcode or your supplier's tariff. The docs say the API "provides an indicative trend". Re-run before starting the appliance; the forecast updates.
- **Rank by the number, not the label.** `index` is a 5-step label; adjacent windows often share it ('very low' all night here), so compare `forecast` in gCO2/kWh.
- **CORS is open** (`access-control-allow-origin: *`), responses come through CloudFront (`x-cache`), no cache-control on the probed fw24h response.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; the blocks check `location.origin` and page text, not the title.

## What does not work

- **carbonintensity.org.uk / www.carbonintensity.org.uk:** their robots.txt is HTTP 403 S3 AccessDenied on 2026-11-12 (curl in this run; a cloud browser in the batch's terms check), so there are no readable rules for them; the home pages themselves answer HTTP 200 `text/html`. Not used; the API and its docs carry everything this task needs.
- **Full postcodes and Northern Ireland:** see Quick summary. The API covers Great Britain's grid only.
- **Reading the terms from github.com at run time:** github.com/robots.txt disallows Bytespider entirely, so no block opens it. The terms were read once for this skill (link above).
- **Not tested:** `/regional/regionid/<id>` routes, `/intensity/stats`, `/intensity/factors`, `/generation/<from>/pt24h`, outcodes that straddle two regions, BST-period behaviour (the run was in GMT, where UK time = UTC), rate-limit behaviour (never provoked).
