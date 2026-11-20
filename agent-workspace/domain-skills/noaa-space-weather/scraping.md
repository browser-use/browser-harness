# NOAA Space Weather Prediction Center (SWPC) via services.swpc.noaa.gov - Check Current Space Weather: Geomagnetic (G), Solar Radiation (S) and Radio Blackout (R) Levels, Kp Index and 3-Day Forecast, Active Watches and Warnings (JSON files, no key)

Field-tested against services.swpc.noaa.gov on 2026-11-19 (US Pacific afternoon; 23:32-23:46 UTC) using a fresh Browser Use cloud browser (logged out; one session, 23:34-23:46 UTC) plus Python `urllib` and `curl` from a Linux machine. 19 browser page loads (one JSON file, then three robots.txt files and five SWPC and NWS pages twice each) and 22 in-page `fetch()` calls (blocks 1 and 2 each ran twice), 51 curl calls (38 to the data host, 13 to robots.txt and documentation pages) and 48 urllib calls (block 3 ran 4 times; 24 of the calls were robots.txt), all serial, at most one a second. Every data call was HTTP 200 except the deliberate HTTP 404 probe of a misspelled file name and the HTTP 304 answers to conditional GETs. The 5 timed curl calls took 0.04-0.07 s each (CloudFront cache hits). No 429, no challenge, no key, no login, no query parameters.

robots.txt (checked 2026-11-19, curl, the cloud browser and `urllib.robotparser`): https://services.swpc.noaa.gov/robots.txt answers HTTP 404 (an Apache "Not Found" page), so the data host has no rules and no named AI-agent groups; under RFC 9309 (section 2.3.1.3) an unavailable robots.txt (4xx) means a crawler "MAY access any resources", and Python's parser treats it as allow-all. https://www.swpc.noaa.gov/robots.txt redirects (HTTP 301) to https://www.spaceweather.gov/robots.txt: one `User-agent: *` group with 34 `Disallow` lines (Drupal defaults such as `/admin/`, `/user/login`, plus `/search/`) and no named AI-agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`. https://www.weather.gov/robots.txt answers HTTP 404. Every path this skill uses is allowed for all 11 agents (block 3). Terms: the SWPC Data Access page https://www.swpc.noaa.gov/content/data-access says "The SWPC Data Service offers text and image data for a variety of products" with base URL services.swpc.noaa.gov and "JSON: services.swpc.noaa.gov/json". The NWS disclaimer https://www.weather.gov/disclaimer (the "Disclaimer" link in the footer of the SWPC pages; seen on all 4 product and data pages this skill cites) says the information on NWS web pages is "in the public domain, unless specifically noted otherwise, and may be used without charge for any lawful purpose so long as you do not: 1) claim it is your own (e.g., by claiming copyright for NWS information -- see below), 2) use it in a manner that implies an endorsement or affiliation with NOAA/NWS, or 3) modify its content and then present it as official government material." Its "Public Notice of Appropriate Use" says NWS "may find it necessary to block IP addresses or query types" of a user "impacting our service delivery capability", and asks users to know the data refresh frequency, "Request only the data that you need" and "limit the number of retries to 1 minute intervals". No AI/ML, scraping, automated-access or non-commercial clause on either page. Naming: the disclaimer says "Use of the NWS name ("National Weather Service") and/or visual identifier are protected under trademark law", allows them "to identify unaltered NWS content or links to NWS web sites", and never "in a manner that implies an endorsement or affiliation with NOAA/NWS". So this skill says "NOAA Space Weather Prediction Center (SWPC)" in plain text with a source line, uses no NOAA or NWS logo, and is not affiliated with or endorsed by NOAA or NWS. Slug `noaa-space-weather`, because `noaa` is the tides skill.

**Planetary, not local.** Kp and the G, S and R levels describe the whole Earth. Only the night window is local (block 1), and whether you can see an aurora also depends on latitude, darkness and cloud: the SWPC aurora page says "The aurora is not visible during daylight hours". For safety-critical use (power grids, aviation, HF radio), use the official SWPC products and subscription services, not a copy.

## Quick summary

- **No scraping.** Plain JSON files, no key, no parameters: `GET https://services.swpc.noaa.gov/products/noaa-scales.json` -> `{"0": {"DateStamp": "2026-11-19", "TimeStamp": "23:33:00", "R": {"Scale": "0", "Text": "none", "MinorProb": null, "MajorProb": null}, "S": {"Scale": "0", ...}, "G": {"Scale": "0", "Text": "none"}}, "1": {...}, "2": {...}, "3": {...}, "-1": {...}}`. Kp: `/products/noaa-planetary-k-index.json` (7 days, final) and `/products/noaa-planetary-k-index-forecast.json` (observed, estimated, predicted). Messages: `/products/alerts.json`. Full 3-day Kp table: `/text/3-day-forecast.txt`. Aurora grid: `/json/ovation_aurora_latest.json` (923 KB, about 158 KB gzipped). `Access-Control-Allow-Origin: *`, `Cache-Control: max-age=60`.
- **Answer (run 2026-11-19, 23:36 UTC):** now **R0 S0 G0**; 24-hour observed maximum **R1, S0, G1** (Kp 5.00 in the 00-03 UTC slot of Nov 19); latest Kp **2.67** (estimated, 21-24 UTC); **0 watches or warnings in effect** (the newest message, K04W "EXTENDED WARNING: Geomagnetic K-index of 4 expected", expired at 09:00 UTC). Tonight in New York (23:00-11:00 UTC) the highest predicted Kp is **3.33**, below G1: no geomagnetic storm expected. Next 3 days: R1-R2 15%, R3 or greater 5%, S1 or greater 1% each day; highest expected Kp 3.67 (Nov 22, 12-15 UTC), "No G1 (Minor) or greater geomagnetic storms are expected."
- **G from Kp.** The SWPC Planetary K-index page: "Kp = 5 (G1) Kp = 6 (G2) Kp = 7 (G3) Kp = 8, 9- (G4) Kp = 9o (G5)". Kp arrives in thirds (the 7-day file held 0.33, 0.67, 1.0 ... 5.0, block 2); the table writes thirds as "9-" and "9o", so this skill reads 4.67 as 5- and 5.33 as 5+. Watches are issued for a predicted daily maximum of K = 5 or more; warnings when Kp 4 or more is expected; alerts when it is reached (same page).
- **No "active" flag.** `alerts.json` holds about 30 days of messages (75 on 2026-11-19, newest first). Read `Valid To:` / `Now Valid Until:` for warnings and the per-day levels of the newest watch (each says "THIS SUPERSEDES ANY/ALL PRIOR WATCHES IN EFFECT"). Block 1 does that.
- **The JSON Kp forecast stops early.** It ended at 00:00 UTC of day 3: 7 of the 24 slots in the 3-day text forecast, including that forecast's peak (3.67), were missing. Block 3 reads the text table.
- **Rate limit:** none published. The NWS asks to request only what you need, match the data's update cycle and retry at 1-minute intervals, and may block IP addresses that hurt service. Every file is served with `Cache-Control: max-age=60`, so polling faster than once a minute gets nothing new. Blocks 1 and 3 pause 1 s between calls, wait 60 s once on 429/5xx or a network error, and stop after that. Block 3 keeps a 60 s disk cache, revalidates with `If-None-Match` and asks for gzip.

## What works

### 1. Current R/S/G, latest Kp, watches and warnings in effect, "is a storm expected tonight?" (browser)

`on_swpc_tab()` opens one logged-out services.swpc.noaa.gov JSON file so `fetch()` runs same-origin (the host also allows any origin). `get()` returns parsed JSON and the `Last-Modified` time on HTTP 200, waits 60 s once on 429/500/502/503/504 or a network error and otherwise raises. 3 `fetch()` calls. Set `TZ` and `NIGHT` for the place you care about.

```python
import json, re, time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

# Where "tonight" is. Kp is planetary (one number for the whole Earth); only the night window is local.
TZ = "America/New_York"
NIGHT = (18, 6)   # local hours: tonight runs 18:00 -> 06:00

SITE = "https://services.swpc.noaa.gov"
SCALES = SITE + "/products/noaa-scales.json"
KP_FC = SITE + "/products/noaa-planetary-k-index-forecast.json"
ALERTS = SITE + "/products/alerts.json"
PAUSE = 1.0   # 3 small files per run; the files are cached 60 s (Cache-Control: max-age=60), so never poll faster
UTC = timezone.utc

def on_swpc_tab():
    """fetch() from a logged-out services.swpc.noaa.gov JSON page (the host also sends Access-Control-Allow-Origin: *)."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(SCALES)
    wait_for_load()
    if js("location.origin") != SITE or '"DateStamp"' not in (js("document.body ? document.body.innerText : ''") or ""):
        raise RuntimeError(f"services.swpc.noaa.gov did not serve noaa-scales.json (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def fetch(url):
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(PAUSE)
    return r

def get(url):
    """-> (parsed JSON, Last-Modified as datetime or None). Waits 60 s once on 429/5xx or a network error (the NWS
    guidance: 'limit the number of retries to 1 minute intervals'); raises on anything else."""
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            time.sleep(60)
            continue
        break
    if r["status"] != 200 or "json" not in r["headers"].get("content-type", ""):
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:150]!r}; stopping")
    lm = r["headers"].get("last-modified")
    return json.loads(r["text"]), (parsedate_to_datetime(lm) if lm else None)

def g_level(kp):
    """NOAA G scale from Kp (SWPC Planetary K-index page: Kp = 5 (G1), 6 (G2), 7 (G3), 8 and 9- (G4), 9o (G5)).
    Kp comes in thirds (4.67 = 5-, 5.33 = 5+); 9- in G4 means the whole number counts, so 4.67 is below G1."""
    return max(0, min(5, int(kp + 1e-6) - 4))

MON = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}

def swpc_time(s):
    """'2026 Nov 19 0900 UTC' -> aware datetime; '2400' is midnight next day."""
    y, mo, d, hm = s.split()[:4]
    base = datetime(int(y), MON[mo], int(d), tzinfo=UTC)
    return base + timedelta(hours=int(hm[:2]), minutes=int(hm[2:]))

def parse_alert(a):
    """One alerts.json item -> dict(kind, head, issued, until, days). Messages mix \\r\\n and \\n line breaks."""
    lines = [l.strip() for l in a["message"].replace("\r\n", "\n").split("\n")]
    head = next((l for l in lines if re.match(r"(EXTENDED |CONTINUED )?(WARNING|WATCH|ALERT|SUMMARY)|CANCEL", l)), lines[0])
    issued = datetime.fromisoformat(a["issue_datetime"][:19]).replace(tzinfo=UTC)  # 'YYYY-MM-DD HH:MM:SS.fff', UTC
    until, days = None, {}
    for l in lines:
        m = re.match(r"(Now Valid Until|Valid To|Valid Until): (\d{4} \w{3} \d{1,2} \d{4}) UTC", l)
        if m:
            until = swpc_time(m.group(2))
    # Watches list a level per day without a year: 'Nov 16:  None (Below G1)   Nov 17:  G1 (Minor)'
    if head.startswith("WATCH"):
        txt = " ".join(lines)
        for mo, d, lvl in re.findall(r"\b(\w{3}) (\d{1,2}):\s+(G\d|None)", txt):
            if mo in MON:
                y = issued.year + (1 if MON[mo] < issued.month else 0)  # a Dec watch can name Jan days
                days[datetime(y, MON[mo], int(d), tzinfo=UTC)] = lvl
    kind = "watch" if days else ("warning" if until else ("cancel" if head.startswith("CANCEL") else "alert"))
    return {"id": a["product_id"], "kind": kind, "head": " ".join(head.split()), "issued": issued, "until": until, "days": days}

on_swpc_tab()
now = datetime.now(UTC)
scales, lm_s = get(SCALES)
kpf, lm_k = get(KP_FC)
alerts, lm_a = get(ALERTS)

if set(scales) != {"-1", "0", "1", "2", "3"}:
    raise RuntimeError(f"noaa-scales.json keys changed: {sorted(scales)}: stop")
cur = scales["0"]
stamp = datetime.fromisoformat(f"{cur['DateStamp']}T{cur['TimeStamp']}").replace(tzinfo=UTC)
age = (now - stamp).total_seconds() / 60
print(f"NOAA Space Weather Prediction Center (SWPC), checked {now:%Y-%m-%d %H:%M} UTC")
lvl = lambda x: f"{x['Scale']} ({x['Text']})" if x["Scale"] is not None else "-"
y = scales["-1"]
for label, d in ((f"now ({stamp:%H:%M} UTC, {age:.0f} min old):", cur),
                 (f"24-hour observed max (since {y['DateStamp']} {y['TimeStamp'][:5]}):", y)):
    print(f"{label:<47} R{lvl(d['R'])}  S{lvl(d['S'])}  G{lvl(d['G'])}")
if age > 30:
    print(f"  stale: the 'now' entry is {age:.0f} min old; check the Last-Modified times below")
print("forecast             R1-R2  R3+   S1+   G (max predicted)")
for k in ("1", "2", "3"):
    d = scales[k]
    print(f"  {d['DateStamp']}          {d['R']['MinorProb']:>3}%  {d['R']['MajorProb']:>3}%  {d['S']['Prob']:>3}%   G{d['G']['Scale']}")

rows = [dict(r, t=datetime.fromisoformat(r["time_tag"]).replace(tzinfo=UTC)) for r in kpf]
seen = [r for r in rows if r["observed"] in ("observed", "estimated") and r["t"] <= now]  # "estimated" can include later slots of today
last = seen[-1]
day = [r for r in seen if r["t"] > now - timedelta(hours=24)]
top = max(day, key=lambda r: r["kp"])
print(f"latest Kp: {last['kp']:.2f} ({last['observed']}, {last['t']:%m-%d %H:%M}-{last['t'] + timedelta(hours=3):%H:%M} UTC); "
      f"max of last 24 h: {top['kp']:.2f} at {top['t']:%m-%d %H:%M} UTC = G{g_level(top['kp'])}")

# Tonight, local: the 18:00 -> 06:00 window that is running now or comes next.
tz = ZoneInfo(TZ)
loc = now.astimezone(tz)
start = loc.replace(hour=NIGHT[0], minute=0, second=0, microsecond=0)
if loc.hour < NIGHT[1]:
    start -= timedelta(days=1)
end = start + timedelta(hours=24 - NIGHT[0] + NIGHT[1])
slots = [r for r in rows if r["t"] < end and r["t"] + timedelta(hours=3) > start]
pred_end = rows[-1]["t"] + timedelta(hours=3)
peak = max(slots, key=lambda r: r["kp"]) if slots else None

parsed = [parse_alert(a) for a in alerts]
watches = sorted((p for p in parsed if p["kind"] == "watch"), key=lambda p: p["issued"])
# each watch says 'THIS SUPERSEDES ANY/ALL PRIOR WATCHES IN EFFECT', so only the newest one counts
active = [p for p in parsed if p["kind"] == "warning" and p["until"] > now] + \
         [p for p in watches[-1:] if any(d.date() >= now.date() and v != "None" for d, v in p["days"].items())]
for p in sorted(active, key=lambda p: p["issued"]):
    extra = f"until {p['until']:%m-%d %H:%M} UTC" if p["until"] else \
        "; ".join(f"{d:%b %d} {v}" for d, v in sorted(p["days"].items()) if d.date() >= now.date())
    print(f"IN EFFECT  {p['id']}  issued {p['issued']:%m-%d %H:%M} UTC  {p['head']}  ({extra})")
recent = parsed[:3]  # alerts.json is newest first
print(f"watches/warnings in effect now: {len(active)} (of {len(alerts)} messages in alerts.json, "
      f"{alerts[-1]['issue_datetime'][:10]} .. {alerts[0]['issue_datetime'][:10]})")
for p in recent:
    print(f"  latest: {p['id']} {p['kind']:<7} issued {p['issued']:%m-%d %H:%M} UTC  {p['head'][:70]}"
          + (f"  (valid until {p['until']:%m-%d %H:%M} UTC, {'in effect' if p['until'] > now else 'expired'})" if p["until"] else ""))
print(f"tonight in {TZ}: {start:%a %m-%d %H:%M} -> {end:%a %m-%d %H:%M} local "
      f"({start.astimezone(UTC):%m-%d %H:%M} -> {end.astimezone(UTC):%m-%d %H:%M} UTC), {len(slots)} three-hour Kp slots")
for r in slots:
    print(f"  {r['t']:%m-%d %H:%M} UTC ({r['t'].astimezone(tz):%H:%M} local)  Kp {r['kp']:.2f}  {r['observed']}")
if pred_end < end:
    print(f"  the JSON forecast stops at {pred_end:%m-%d %H:%M} UTC: the rest of tonight is not covered (see /text/3-day-forecast.txt)")
# a G1+ watch day (UTC) that tonight touches, or a K-index 5+ warning still valid when tonight starts
nights = {start.astimezone(UTC).date(), end.astimezone(UTC).date()}
storm = [p for p in active if (p["kind"] == "watch" and any(d.date() in nights and v != "None" for d, v in p["days"].items()))
         or (p["kind"] == "warning" and re.search(r"K-index of [5-9]", p["head"]) and p["until"] > start)]
if peak is None:
    print("verdict: no Kp slots cover tonight yet")
else:
    g = g_level(peak["kp"])
    # a NO needs Kp slots up to the end of tonight; below G1 in a shorter forecast is not a NO
    word = "YES" if g or storm else "NO" if pred_end >= end else f"NOT KNOWN YET (below G1 up to {pred_end:%m-%d %H:%M} UTC, where the JSON forecast stops)"
    print(f"verdict: geomagnetic storm (G1 or more) expected tonight: {word}: max Kp {peak['kp']:.2f} "
          f"({peak['observed']}, {peak['t']:%H:%M} UTC) = {'G' + str(g) if g else 'below G1'}; "
          f"G1+ watches or K5+ warnings in effect: {len(storm)}")
hms = lambda t: f"{t:%H:%M:%S}" if t else "unavailable"  # get() returns None when a file has no Last-Modified
print(f"\nfiles last modified (UTC): scales {hms(lm_s)}, Kp forecast {hms(lm_k)}, alerts {hms(lm_a)}")
print(f"Source: NOAA Space Weather Prediction Center (SWPC), {SITE}/products/, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the run on 2026-11-19, 23:36 UTC; re-run 2026-11-20 00:52 UTC in a new cloud browser after the Last-Modified fallback was added, and 02:02 UTC after the latest-Kp row skipped not-yet-started `estimated` slots and a short forecast stopped giving NO: same lines, live values moved with the clock):

```text
NOAA Space Weather Prediction Center (SWPC), checked 2026-11-19 23:36 UTC
now (23:33 UTC, 3 min old):                     R0 (none)  S0 (none)  G0 (none)
24-hour observed max (since 2026-11-18 23:33):  R1 (minor)  S0 (none)  G1 (minor)
forecast             R1-R2  R3+   S1+   G (max predicted)
  2026-11-19           15%    5%    1%   G0
  2026-11-20           15%    5%    1%   G0
  2026-11-21           15%    5%    1%   G0
latest Kp: 2.67 (estimated, 11-19 21:00-00:00 UTC); max of last 24 h: 5.00 at 11-19 00:00 UTC = G1
watches/warnings in effect now: 0 (of 75 messages in alerts.json, 2026-10-21 .. 2026-11-19)
  latest: K04W warning issued 11-19 01:18 UTC  EXTENDED WARNING: Geomagnetic K-index of 4 expected  (valid until 11-19 09:00 UTC, expired)
  latest: K05A alert   issued 11-19 01:08 UTC  ALERT: Geomagnetic K-index of 5
  latest: K05W warning issued 11-19 01:00 UTC  WARNING: Geomagnetic K-index of 5 expected  (valid until 11-19 03:00 UTC, expired)
tonight in America/New_York: Thu 11-19 18:00 -> Fri 11-20 06:00 local (11-19 23:00 -> 11-20 11:00 UTC), 5 three-hour Kp slots
  11-19 21:00 UTC (16:00 local)  Kp 2.67  estimated
  11-20 00:00 UTC (19:00 local)  Kp 3.00  predicted
  11-20 03:00 UTC (22:00 local)  Kp 3.33  predicted
  11-20 06:00 UTC (01:00 local)  Kp 2.67  predicted
  11-20 09:00 UTC (04:00 local)  Kp 2.33  predicted
verdict: geomagnetic storm (G1 or more) expected tonight: NO: max Kp 3.33 (predicted, 03:00 UTC) = below G1; G1+ watches or K5+ warnings in effect: 0

files last modified (UTC): scales 23:34:00, Kp forecast 23:35:21, alerts 23:35:21
Source: NOAA Space Weather Prediction Center (SWPC), https://services.swpc.noaa.gov/products/, accessed 19 November 2026 23:36 UTC.
```

### 2. robots.txt, the terms and product pages, and what the files really contain (browser)

9 page loads and 8 in-page `fetch()` calls in the same tab. The product pages keep their "Details" text in hidden tabs, so the block reads `textContent`; `innerText` reported 4 of the needles below as missing on the first run.

```python
import json, re, time

SITE = "https://services.swpc.noaa.gov"

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

def raw(path):
    """One in-page GET of SITE + path -> {status, headers, text}. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(SITE + path)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{path}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1.0)
    return r

def page(url):
    goto_url(url)
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    # textContent, not innerText: the SWPC product pages keep their Details text in hidden tabs
    return st, js("location.href"), js("(document.body || document.documentElement).textContent || ''") or ""

for url in (SITE + "/robots.txt", "https://www.swpc.noaa.gov/robots.txt", "https://www.weather.gov/robots.txt"):
    st, href, txt = page(url)
    groups = [l.strip() for l in txt.splitlines() if l.lower().startswith("user-agent")]
    print(f"{url.split('//')[1]:<35} HTTP {st} -> {href.split('//')[1]}: "
          + (f"user-agent lines {groups}, {sum(l.lower().startswith('disallow') for l in txt.splitlines())} Disallow lines, "
             f"'/products/' disallowed: {any(l.split(':', 1)[1].strip() in ('/', '/products/') for l in txt.splitlines() if l.lower().startswith('disallow'))}"
             if groups else f"no robots rules ({' '.join(txt.split())[:40]!r})"))
for url, needles in (
    ("https://www.weather.gov/disclaimer", ["are in the public domain, unless specifically noted otherwise, and may be used without charge for any lawful purpose",
                                            "use it in a manner that implies an endorsement or affiliation with NOAA/NWS",
                                            "protected under trademark law", "we may find it necessary to block IP addresses or query types",
                                            "Request only the data that you need", "limit the number of retries to 1 minute intervals"]),
    ("https://www.swpc.noaa.gov/content/data-access", ["The SWPC Data Service offers text and image data", "services.swpc.noaa.gov/json"]),
    ("https://www.swpc.noaa.gov/products/planetary-k-index", ["Kp = 5 (G1)", "Kp = 8, 9- (G4)", "Kp = 9o (G5)", "This chart updates every minute",
                                                              "K-index Watches are issued when the highest predicted NOAA estimated Kp-indices for a day are K = 5, 6, 7, or >= 8",
                                                              "K-index Warnings are issued when NOAA estimated Kp-indices of 4, 5, 6, and 7 or greater are expected"]),
    ("https://www.swpc.noaa.gov/products/alerts-watches-and-warnings", ["The current Alerts, Watches and Warnings data is available directly from this JSON file"]),
    ("https://www.swpc.noaa.gov/products/aurora-30-minute-forecast", ["provides a 30 to 90 minute forecast of the location and intensity of the aurora",
                                                                       "The aurora is not visible during daylight hours"]),
):
    st, href, txt = page(url)
    flat = " ".join(txt.split())
    for n in needles:
        print(f"{href.split('//')[1][:48]:<48} HTTP {st}: {'found' if n in flat else 'MISSING'}: {n[:64]!r}")
page(SITE + "/products/noaa-scales.json")  # back on the data host for same-origin fetch()
print()

def brief(r):
    h = r["headers"]
    return f"HTTP {r['status']} {h.get('content-type', '?')}, {len(r['text'])} chars, cache-control {h.get('cache-control')}"

for label, path in (("scales                  ", "/products/noaa-scales.json"),
                    ("scales ?days=7 (ignored)", "/products/noaa-scales.json?days=7"),
                    ("typo noaa-scale.json    ", "/products/noaa-scale.json"),
                    ("/products/ directory    ", "/products/"),
                    ("7-day Kp                ", "/products/noaa-planetary-k-index.json")):
    r = raw(path)
    print(f"{label} {brief(r)}")
    if path.startswith("/products/noaa-scales.json") and r["status"] == 200:
        print(f"   key order {list(json.loads(r['text']))}, 'now' = {json.loads(r['text'])['0']['DateStamp']} {json.loads(r['text'])['0']['TimeStamp']}")
    if "k-index.json" in path:
        k = json.loads(r["text"])
        print(f"   {len(k)} rows {k[0]['time_tag']} .. {k[-1]['time_tag']}, fields {sorted(k[0])}, Kp values seen {sorted({x['Kp'] for x in k})}")

# The JSON Kp forecast versus the 3-day text forecast it comes from
fc = json.loads(raw("/products/noaa-planetary-k-index-forecast.json")["text"])
kinds = {}
for x in fc:
    kinds.setdefault(x["observed"], []).append(x["time_tag"])
print("Kp forecast JSON:", {k: f"{len(v)} rows {v[0][5:16]}..{v[-1][5:16]}" for k, v in kinds.items()},
      "| noaa_scale set on", [(x["time_tag"][5:16], x["kp"], x["noaa_scale"]) for x in fc if x["noaa_scale"]])
txt = raw("/text/3-day-forecast.txt")["text"]
issued = re.search(r":Issued: (.+)", txt).group(1)
days = re.search(r"NOAA Kp index breakdown (.+)", txt).group(1)
grid = re.findall(r"^(\d\d-\d\dUT)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", txt, re.M)
print(f"3-day text forecast issued {issued}, {days}: {len(grid)} slots x 3 days; day 3 slots {[g[3] for g in grid]}")
print("  ", re.search(r"The greatest expected 3 hr Kp for .+?\)\.", " ".join(txt.split())).group(0))
print("   radio/solar lines:", [" ".join(l.split()) for l in txt.splitlines() if l.startswith(("R1-R2", "R3 or greater", "S1 or greater"))])

# A past watch, read the way block 1 reads it (alerts.json keeps about 30 days)
al = json.loads(raw("/products/alerts.json")["text"])
w = next(a for a in al if re.search(r"^WATCH:", a["message"], re.M))
body = [l for l in w["message"].replace("\r\n", "\n").split("\n") if l.strip()]
print(f"\nnewest watch {w['product_id']} issued {w['issue_datetime']} UTC:")
for l in body[3:7]:
    print("   ", " ".join(l.split()))
print("line breaks in alerts.json messages: \\r\\n", sum(a["message"].count("\r\n") for a in al),
      "| bare \\n", sum(a["message"].count("\n") - a["message"].count("\r\n") for a in al))
```

Output (from the re-run on 2026-11-19, 23:37 UTC):

```text
services.swpc.noaa.gov/robots.txt   HTTP 404 -> services.swpc.noaa.gov/robots.txt: no robots rules ('Not Found The requested URL was not foun')
www.swpc.noaa.gov/robots.txt        HTTP 200 -> www.spaceweather.gov/robots.txt: user-agent lines ['User-agent: *'], 34 Disallow lines, '/products/' disallowed: False
www.weather.gov/robots.txt          HTTP 404 -> www.weather.gov/robots.txt: no robots rules ('var domains = { weather: "https://www.we')
www.weather.gov/disclaimer                       HTTP 200: found: 'are in the public domain, unless specifically noted otherwise, a'
www.weather.gov/disclaimer                       HTTP 200: found: 'use it in a manner that implies an endorsement or affiliation wi'
www.weather.gov/disclaimer                       HTTP 200: found: 'protected under trademark law'
www.weather.gov/disclaimer                       HTTP 200: found: 'we may find it necessary to block IP addresses or query types'
www.weather.gov/disclaimer                       HTTP 200: found: 'Request only the data that you need'
www.weather.gov/disclaimer                       HTTP 200: found: 'limit the number of retries to 1 minute intervals'
www.spaceweather.gov/content/data-access         HTTP 200: found: 'The SWPC Data Service offers text and image data'
www.spaceweather.gov/content/data-access         HTTP 200: found: 'services.swpc.noaa.gov/json'
www.spaceweather.gov/products/planetary-k-index  HTTP 200: found: 'Kp = 5 (G1)'
www.spaceweather.gov/products/planetary-k-index  HTTP 200: found: 'Kp = 8, 9- (G4)'
www.spaceweather.gov/products/planetary-k-index  HTTP 200: found: 'Kp = 9o (G5)'
www.spaceweather.gov/products/planetary-k-index  HTTP 200: found: 'This chart updates every minute'
www.spaceweather.gov/products/planetary-k-index  HTTP 200: found: 'K-index Watches are issued when the highest predicted NOAA estim'
www.spaceweather.gov/products/planetary-k-index  HTTP 200: found: 'K-index Warnings are issued when NOAA estimated Kp-indices of 4,'
www.spaceweather.gov/products/alerts-watches-and HTTP 200: found: 'The current Alerts, Watches and Warnings data is available direc'
www.spaceweather.gov/products/aurora-30-minute-f HTTP 200: found: 'provides a 30 to 90 minute forecast of the location and intensit'
www.spaceweather.gov/products/aurora-30-minute-f HTTP 200: found: 'The aurora is not visible during daylight hours'

scales                   HTTP 200 application/json, 1101 chars, cache-control max-age=60
   key order ['0', '1', '2', '3', '-1'], 'now' = 2026-11-19 23:35:00
scales ?days=7 (ignored) HTTP 200 application/json, 1101 chars, cache-control max-age=60
   key order ['0', '1', '2', '3', '-1'], 'now' = 2026-11-19 23:35:00
typo noaa-scale.json     HTTP 404 text/html; charset=iso-8859-1, 196 chars, cache-control None
/products/ directory     HTTP 200 text/html;charset=UTF-8, 1983 chars, cache-control max-age=60
7-day Kp                 HTTP 200 application/json, 4860 chars, cache-control max-age=60
   63 rows 2026-11-12T00:00:00 .. 2026-11-19T18:00:00, fields ['Kp', 'a_running', 'station_count', 'time_tag'], Kp values seen [0.33, 0.67, 1.0, 1.33, 1.67, 2.0, 2.33, 2.67, 3.0, 3.33, 5.0]
Kp forecast JSON: {'observed': '63 rows 11-12T00:00..11-19T18:00', 'estimated': '1 rows 11-19T21:00..11-19T21:00', 'predicted': '17 rows 11-20T00:00..11-22T00:00'} | noaa_scale set on [('11-19T00:00', 5.0, 'G1')]
3-day text forecast issued 2026 Nov 19 2200 UTC, Nov 20-Nov 22 2026: 8 slots x 3 days; day 3 slots ['2.33', '2.00', '2.00', '2.67', '3.67', '2.67', '2.67', '3.00']
   The greatest expected 3 hr Kp for Nov 20-Nov 22 2026 is 3.67 (below NOAA Scale levels).
   radio/solar lines: ['S1 or greater 1% 1% 1%', 'R1-R2 15% 15% 15%', 'R3 or greater 5% 5% 5%']

newest watch A20F issued 2026-11-15 13:34:32.160 UTC:
    WATCH: Geomagnetic Storm Category G1 Predicted
    Highest Storm Level Predicted by Day:
    Nov 16: None (Below G1) Nov 17: G1 (Minor) Nov 18: G1 (Minor)
    THIS SUPERSEDES ANY/ALL PRIOR WATCHES IN EFFECT
line breaks in alerts.json messages: \r\n 686 | bare \n 341
```

### 3. Same data with Python urllib: robots check for every agent, 7-day Kp, the full 3-day forecast, aurora at three places, 60 s cache (no browser)

Sends a descriptive User-Agent (curl's default User-Agent also got HTTP 200). The aurora grid is the only large file: fetch it only when someone asks about the aurora, then look up every place from one copy. Run with an empty cache; it sleeps 61 s near the end to show a revalidation.

```python
import gzip, hashlib, json, os, re, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timedelta, timezone

SITE = "https://services.swpc.noaa.gov"
UA = "swpc-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
CACHE_DIR = "~/.cache/swpc-skill"
CACHE = os.path.expanduser(CACHE_DIR)
FRESH = 60    # every file here is served with Cache-Control: max-age=60; inside that, do not ask again
PAUSE = 1.0   # serial, at most one request a second
PLACES = {"Fairbanks, Alaska": (64.84, -147.72), "Tromso, Norway": (69.65, 18.96), "Minneapolis, Minnesota": (44.98, -93.27)}
UTC = timezone.utc
stats = {"net200": 0, "net304": 0, "cache": 0, "bytes": 0, "same": 0}

def get(path, want="json"):
    """SITE + path -> parsed JSON (or text). Reuses the disk copy for 60 s, then revalidates with If-None-Match /
    If-Modified-Since (HTTP 304 = no body); asks for gzip. Waits 60 s once on 429/5xx or a network error (NWS: 'limit the number of
    retries to 1 minute intervals'); exits on anything else."""
    url = SITE + path
    f = os.path.join(CACHE, hashlib.sha256(url.encode()).hexdigest())
    meta = {}
    try:
        meta = json.load(open(f + ".meta"))
        if time.time() - os.path.getmtime(f + ".meta") < FRESH:
            stats["cache"] += 1
            body = open(f, "rb").read()
            return json.loads(body) if want == "json" else body.decode()
    except (OSError, ValueError):
        meta = {}
    hdr = {"User-Agent": UA, "Accept-Encoding": "gzip"}  # the 923 KB aurora grid came as about 158 KB gzipped
    if meta.get("etag"):
        hdr["If-None-Match"] = meta["etag"]
    if meta.get("last_modified"):
        hdr["If-Modified-Since"] = meta["last_modified"]
    for attempt in range(2):
        time.sleep(PAUSE)
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=60) as r:
                body = r.read()
                stats["bytes"] += len(body)  # bytes on the wire
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                old = meta.get("sha")
                meta = {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified"),
                        "sha": hashlib.sha256(body).hexdigest()}
            stats["net200"] += 1
            stats["same"] += meta["sha"] == old  # SWPC rewrites some files every minute with the same bytes
            os.makedirs(CACHE, exist_ok=True)
            open(f, "wb").write(body)
            break
        except urllib.error.HTTPError as e:
            if e.code == 304:
                stats["net304"] += 1
                body = open(f, "rb").read()
                break
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"HTTP {e.code} {url}: {' '.join(e.read().decode(errors='replace').split())[:150]}")
        except OSError as e:  # DNS, refused connection, timeout, reset
            if attempt == 0:
                time.sleep(60)
                continue
            sys.exit(f"{url}: {e}")
    json.dump(meta, open(f + ".meta", "w"))  # rewriting it restarts the 60 s window
    return json.loads(body) if want == "json" else body.decode()

def g_level(kp):
    """SWPC Planetary K-index page: Kp = 5 (G1), 6 (G2), 7 (G3), 8 and 9- (G4), 9o (G5)."""
    return max(0, min(5, int(kp + 1e-6) - 4))

# robots.txt: services.swpc.noaa.gov and www.weather.gov answer 404 (RobotFileParser.read() treats a 4xx other than
# 401/403 as allow-all, RFC 9309 section 2.3.1.3); www.swpc.noaa.gov redirects to www.spaceweather.gov (one '*' group).
for host, paths in ((SITE, ["/products/noaa-scales.json", "/products/alerts.json", "/text/3-day-forecast.txt",
                            "/json/ovation_aurora_latest.json"]),
                    ("https://www.spaceweather.gov", ["/products/planetary-k-index", "/content/data-access"]),
                    ("https://www.weather.gov", ["/disclaimer"])):
    rp = urllib.robotparser.RobotFileParser(host + "/robots.txt")
    try:
        with urllib.request.urlopen(urllib.request.Request(rp.url, headers={"User-Agent": UA}), timeout=30) as r:
            print(f"{host}/robots.txt: HTTP {r.status}")
    except urllib.error.HTTPError as e:
        print(f"{host}/robots.txt: HTTP {e.code}")
    rp.read()
    time.sleep(PAUSE)
    for p in paths:
        ok = all(rp.can_fetch(a, host + p) for a in AGENTS)
        print(f"  robots {p:<34} {'allowed' if ok else 'DISALLOWED'} for all {len(AGENTS)} agents")
        if not ok:
            sys.exit("robots.txt now disallows a path this skill uses: stop")

now = datetime.now(UTC)
print(f"\nNOAA Space Weather Prediction Center (SWPC), checked {now:%Y-%m-%d %H:%M} UTC")

# 1. Last 7 days: highest 3-hour Kp per UTC day
kp = get("/products/noaa-planetary-k-index.json")
days = {}
for r in kp:
    d = r["time_tag"][:10]
    days[d] = max(days.get(d, (0, "")), (r["Kp"], r["time_tag"][11:16]))
print("observed Kp, highest 3-hour value per UTC day:")
for d, (v, t) in days.items():
    print(f"  {d}  Kp {v:.2f} at {t} UTC  {'G' + str(g_level(v)) if g_level(v) else 'below G1'}"
          + ("  (day not over)" if d == f"{now:%Y-%m-%d}" else ""))
last = kp[-1]
print(f"  newest final value: {last['time_tag'][5:16]} UTC Kp {last['Kp']:.2f} from {last['station_count']} stations")

# 2. The full 3-day Kp forecast lives in the text product; the JSON forecast stops early (see Gotchas)
txt = get("/text/3-day-forecast.txt", want="text")
issued = re.search(r":Issued: (.+)", txt).group(1)
cols = re.search(r"^\s+(\w{3} \d+)\s+(\w{3} \d+)\s+(\w{3} \d+)\s*$", txt[txt.index("Kp index breakdown"):], re.M).groups()
grid = re.findall(r"^(\d\d)-(\d\d)UT\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", txt, re.M)
if len(grid) != 8:
    sys.exit(f"3-day forecast table changed ({len(grid)} rows): stop")
# the columns are the 3 days after the issue date; a late-Dec forecast names Jan days of the next year
issued_day = datetime.strptime(" ".join(issued.split()[:3]), "%Y %b %d").replace(tzinfo=UTC)  # "2026 Nov 19 2200 UTC"
fc = get("/products/noaa-planetary-k-index-forecast.json")
in_json = {r["time_tag"][:13] for r in fc if r["observed"] == "predicted"}
print(f"\n3-day Kp forecast (text product issued {issued}), highest slot per UTC day:")
missing = 0
for i, c in enumerate(cols):
    day = datetime.strptime(f"{c} {issued_day.year}", "%b %d %Y").replace(tzinfo=UTC)
    if day < issued_day - timedelta(days=1):  # Jan columns of a forecast issued in late Dec
        day = day.replace(year=day.year + 1)
    vals = [(float(g[2 + i]), f"{g[0]}-{g[1]}") for g in grid]
    v, h = max(vals)
    missing += sum(f"{day:%Y-%m-%d}T{g[0]}" not in in_json for g in grid)
    print(f"  {day:%Y-%m-%d}  max Kp {v:.2f} ({h} UTC)  {'G' + str(g_level(v)) if g_level(v) else 'below G1'}"
          f"   slots {' '.join(f'{x:.2f}' for x, _ in vals)}")
print(f"  {missing} of 24 forecast slots are not in noaa-planetary-k-index-forecast.json ({len(in_json)} predicted rows there)")
print("  " + re.search(r"The greatest expected 3 hr Kp for .+?\)\.", " ".join(txt.split())).group(0))
print("  " + re.search(r"A\. NOAA Geomagnetic.+?Rationale: (.+?)(?= B\. )", " ".join(txt.split())).group(1))

# 3. Aurora: one 923 KB grid; fetch it only when someone asks about the aurora, and look up every place in one pass
aur = get("/json/ovation_aurora_latest.json")
cell = {(lon, lat): v for lon, lat, v in aur["coordinates"]}
print(f"\nOVATION aurora grid: observation {aur['Observation Time']}, forecast for {aur['Forecast Time']}, "
      f"{len(cell)} cells ({aur['Data Format']}), max value {max(cell.values())}")
for name, (lat, lon) in PLACES.items():
    key = (round(lon) % 360, round(lat))
    print(f"  {name:<24} lat {lat:6.2f} lon {lon:8.2f} -> cell {key}: aurora value {cell[key]}")

# 4. Ask again: inside 60 s every answer comes from disk; after that a revalidation costs a 304 and no body
n = dict(stats)
for p in ("/products/noaa-planetary-k-index.json", "/text/3-day-forecast.txt", "/json/ovation_aurora_latest.json"):
    get(p, want="text" if p.endswith(".txt") else "json")
print(f"\nrepeat within 60 s: {stats['net200'] - n['net200']} downloads, {stats['net304'] - n['net304']} 304s, "
      f"{stats['cache'] - n['cache']} disk hits")
time.sleep(FRESH + 1)
n = dict(stats)
get("/json/ovation_aurora_latest.json")
get("/text/3-day-forecast.txt", want="text")
print(f"repeat after 61 s: {stats['net200'] - n['net200']} downloads ({stats['bytes'] - n['bytes']:,} bytes; "
      f"{stats['same'] - n['same']} byte-identical to the copy on disk), {stats['net304'] - n['net304']} answered 304 (no body)")
print(f"totals: {stats['net200']} downloads ({stats['bytes']:,} bytes), {stats['net304']} 304s, {stats['cache']} disk hits, cache {CACHE_DIR}")
print(f"Source: NOAA Space Weather Prediction Center (SWPC), {SITE}, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (from the run on 2026-11-19, 23:43 UTC, empty cache; re-run 2026-11-20 01:58 UTC, empty cache, after the forecast dates moved to the issue date's year: same 3 dates, live values moved):

```text
https://services.swpc.noaa.gov/robots.txt: HTTP 404
  robots /products/noaa-scales.json         allowed for all 11 agents
  robots /products/alerts.json              allowed for all 11 agents
  robots /text/3-day-forecast.txt           allowed for all 11 agents
  robots /json/ovation_aurora_latest.json   allowed for all 11 agents
https://www.spaceweather.gov/robots.txt: HTTP 200
  robots /products/planetary-k-index        allowed for all 11 agents
  robots /content/data-access               allowed for all 11 agents
https://www.weather.gov/robots.txt: HTTP 404
  robots /disclaimer                        allowed for all 11 agents

NOAA Space Weather Prediction Center (SWPC), checked 2026-11-19 23:43 UTC
observed Kp, highest 3-hour value per UTC day:
  2026-11-12  Kp 1.67 at 21:00 UTC  below G1
  2026-11-13  Kp 1.33 at 06:00 UTC  below G1
  2026-11-14  Kp 1.67 at 12:00 UTC  below G1
  2026-11-15  Kp 2.00 at 00:00 UTC  below G1
  2026-11-16  Kp 1.33 at 12:00 UTC  below G1
  2026-11-17  Kp 3.00 at 21:00 UTC  below G1
  2026-11-18  Kp 3.33 at 03:00 UTC  below G1
  2026-11-19  Kp 5.00 at 00:00 UTC  G1  (day not over)
  newest final value: 11-19T18:00 UTC Kp 3.00 from 8 stations

3-day Kp forecast (text product issued 2026 Nov 19 2200 UTC), highest slot per UTC day:
  2026-11-20  max Kp 3.33 (03-06 UTC)  below G1   slots 3.00 3.33 2.67 2.33 1.67 2.67 2.67 3.00
  2026-11-21  max Kp 2.67 (03-06 UTC)  below G1   slots 2.33 2.67 2.00 2.00 1.33 2.00 2.00 2.33
  2026-11-22  max Kp 3.67 (12-15 UTC)  below G1   slots 2.33 2.00 2.00 2.67 3.67 2.67 2.67 3.00
  7 of 24 forecast slots are not in noaa-planetary-k-index-forecast.json (17 predicted rows there)
  The greatest expected 3 hr Kp for Nov 20-Nov 22 2026 is 3.67 (below NOAA Scale levels).
  No G1 (Minor) or greater geomagnetic storms are expected. No significant transient or recurrent solar wind features are forecast.

OVATION aurora grid: observation 2026-11-19T23:37:00Z, forecast for 2026-11-20T00:40:00Z, 65160 cells ([Longitude, Latitude, Aurora]), max value 25
  Fairbanks, Alaska        lat  64.84 lon  -147.72 -> cell (212, 65): aurora value 1
  Tromso, Norway           lat  69.65 lon    18.96 -> cell (19, 70): aurora value 16
  Minneapolis, Minnesota   lat  44.98 lon   -93.27 -> cell (267, 45): aurora value 0

repeat within 60 s: 0 downloads, 0 304s, 3 disk hits
repeat after 61 s: 2 downloads (158,372 bytes; 2 byte-identical to the copy on disk), 0 answered 304 (no body)
totals: 6 downloads (317,656 bytes), 0 304s, 3 disk hits, cache ~/.cache/swpc-skill
Source: NOAA Space Weather Prediction Center (SWPC), https://services.swpc.noaa.gov, accessed 19 November 2026 23:43 UTC.
```

The two files re-downloaded after 61 s were byte-identical to the cached copies: SWPC rewrites them about once a minute, which changes `ETag` and `Last-Modified`, so `If-None-Match` only returns 304 when the file was not touched (it did for the aurora grid in block 4 and in one earlier run of this block). gzip is what reliably saves bandwidth.

### 4. curl one-liners, headers, conditional GET and mistakes

```bash
B=https://services.swpc.noaa.gov
# --retry 1 retries once on a timeout or HTTP 408, 429, 500, 502, 503 or 504 (curl's "transient error" rule), 60 s later (NWS: retries at 1 minute intervals); --max-time stops a stalled call
C="curl -sS --max-time 60 --retry 1 --retry-delay 60"
# current R/S/G and the 24-hour maximum ("0" = now, "-1" = the 24-hour observed maximum)
$C --fail "$B/products/noaa-scales.json" | python3 -c 'import json, sys
s = json.load(sys.stdin)
for k in ("0", "-1"):
    d = s[k]; print(k, d["DateStamp"], d["TimeStamp"], *(x + str(d[x]["Scale"]) for x in "RSG"))'
sleep 1
# latest observed/estimated Kp and the highest predicted Kp in the JSON forecast
$C --fail "$B/products/noaa-planetary-k-index-forecast.json" | python3 -c 'import json, sys
from datetime import datetime, timezone
f = json.load(sys.stdin); t = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
now = [r for r in f if r["observed"] != "predicted" and r["time_tag"] <= t][-1]; p = max((r for r in f if r["observed"] == "predicted"), key=lambda r: r["kp"])
print("latest", now["time_tag"], now["kp"], now["observed"], "| max predicted", p["time_tag"], p["kp"])'
sleep 1
# newest 3 messages: product_id, issue time, headline (messages mix \r\n and \n)
$C --fail "$B/products/alerts.json" | python3 -c 'import json, re, sys
for a in json.load(sys.stdin)[:3]:
    m = re.search(r"^((EXTENDED |CONTINUED )?(WARNING|WATCH|ALERT|SUMMARY).*)$", a["message"].replace("\r\n", "\n"), re.M)
    print(a["product_id"], a["issue_datetime"][:16], m.group(1).strip() if m else "?")'
sleep 1
# the plain-text 3-day forecast: Kp table for all three days, plus the R and S probabilities
$C --fail "$B/text/3-day-forecast.txt" | sed -n -e '/^:Issued/p' -e '/greatest expected/,/G1)\.\|levels)\./p' -e '/^S1 or greater/p' -e '/^R1-R2/p' -e '/^R3 or greater/p'
sleep 1
H=$(mktemp)
# headers: JSON, 60 s cache, CORS open, ETag for conditional GET
$C -D - -o /dev/null "$B/json/ovation_aurora_latest.json" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|content-length|cache-control|access-control-allow-origin|etag|retry-after):)' | tee "$H"
sleep 1
E=$(grep -i '^etag:' "$H" | cut -d' ' -f2-)
$C -o /dev/null -w 'If-None-Match: HTTP %{http_code}, %{size_download} bytes\n' -H "If-None-Match: $E" "$B/json/ovation_aurora_latest.json"
sleep 1
$C -o /dev/null -w 'gzip: HTTP %{http_code}, %{size_download} bytes on the wire\n' -H 'Accept-Encoding: gzip' "$B/json/ovation_aurora_latest.json"
sleep 1
# a typo is an HTML 404, a query string is ignored
$C -o /dev/null -w 'noaa-scale.json (typo): HTTP %{http_code} %{content_type}\n' "$B/products/noaa-scale.json"
sleep 1
$C -o /dev/null -w 'noaa-scales.json?days=7: HTTP %{http_code} %{content_type}, %{size_download} bytes\n' "$B/products/noaa-scales.json?days=7"
rm -f "$H"
echo "Source: NOAA Space Weather Prediction Center (SWPC), $B, accessed $(date -u '+%d %B %Y %H:%M') UTC."
```

Output (from the re-run on 2026-11-19, 23:45 UTC; re-run 2026-11-20 02:02 UTC after the latest-Kp row skipped not-yet-started slots: same lines, live values moved):

```text
0 2026-11-19 23:43:00 R0 S0 G0
-1 2026-11-18 23:43:00 R1 S0 G1
latest 2026-11-19T21:00:00 2.67 estimated | max predicted 2026-11-20T03:00:00 3.33
K04W 2026-11-19 01:18 EXTENDED WARNING: Geomagnetic K-index of 4 expected
K05A 2026-11-19 01:08 ALERT: Geomagnetic K-index of 5
K05W 2026-11-19 01:00 WARNING: Geomagnetic K-index of 5 expected
:Issued: 2026 Nov 19 2200 UTC
The greatest expected 3 hr Kp for Nov 20-Nov 22 2026 is 3.67 (below NOAA
Scale levels).
S1 or greater    1%      1%      1%
R1-R2           15%           15%           15%
R3 or greater    5%            5%            5%
HTTP/2 200 
content-type: application/json
content-length: 922701
etag: "e144d-660a9b5d6ea33"
cache-control: max-age=60
access-control-allow-origin: *
If-None-Match: HTTP 304, 0 bytes
gzip: HTTP 200, 157652 bytes on the wire
noaa-scale.json (typo): HTTP 404 text/html; charset=iso-8859-1
noaa-scales.json?days=7: HTTP 200 application/json, 1101 bytes
Source: NOAA Space Weather Prediction Center (SWPC), https://services.swpc.noaa.gov, accessed 19 November 2026 23:45 UTC.
```

## Fields

| File / field | Value | Notes |
|---|---|---|
| `/products/noaa-scales.json` | object with string keys `"0"`, `"1"`, `"2"`, `"3"`, `"-1"` (in that order) | `"0"` = now (`DateStamp` + `TimeStamp`, UTC, a few minutes old); `"-1"` = 24-hour observed maximum (its stamp is the start of the window, `2026-11-18 23:33`; R1 and G1 matched the text forecast's "over the past 24 hours" lines); `"1"`-`"3"` = forecast, dated today, tomorrow and the day after (2026-11-19 to 2026-11-21) |
| `R.Scale`, `S.Scale`, `G.Scale` | strings `"0"`-`"5"`, `Text` `"none"`, `"minor"`... | `null` on forecast days for R and S (only probabilities); G has a forecast level |
| `R.MinorProb`, `R.MajorProb`, `S.Prob` | strings, percent (`"15"`, `"5"`, `"1"`) | matched the 3-day text forecast's "R1-R2 15%", "R3 or greater 5%" and "S1 or greater 1%" (all days were equal, so which text day matches which key was not checked) |
| `/products/noaa-planetary-k-index.json` | list of `{time_tag, Kp, a_running, station_count}` | 63 rows = 7 days of 3-hour slots plus today so far; `time_tag` is the slot start, UTC, no zone suffix; `Kp` floats in thirds (0.33, 0.67, 1.0...) |
| `/products/noaa-planetary-k-index-forecast.json` | list of `{time_tag, kp, observed, noaa_scale}` | 81 rows: 63 `observed`, 1 `estimated` (the running slot), 17 `predicted` (to day 3 00:00 UTC only) at 2026-11-19 23:36 UTC; at 2026-11-20 02:01 UTC all 8 slots of the new UTC day were `estimated`, 7 of them not yet started; `noaa_scale` was `"G1"` on 1 observed row (Kp 5.00) and `null` on all others, predicted ones included |
| `/products/alerts.json` | list of `{product_id, issue_datetime, message}`, newest first | about 30 days; `issue_datetime` `"2026-11-19 01:18:16.670"` is UTC without a zone; `message` is text with 686 `\r\n` and 341 bare `\n` breaks; ids seen: K04W/K05W/K06W (warnings), K04A/K05A/K06A (alerts), A20F (G1 watch), EF3A (electron flux), TIIA/TIVA (radio emission) |
| `/text/3-day-forecast.txt` | plain text, `:Issued: 2026 Nov 19 2200 UTC` | Kp table "NOAA Kp index breakdown" for 3 UTC days x 8 slots, S1+ and R1-R2/R3+ probabilities, a rationale per section |
| `/json/ovation_aurora_latest.json` | `{"Observation Time", "Forecast Time", "Data Format": "[Longitude, Latitude, Aurora]", "coordinates": [[lon, lat, value], ...]}` | 65,160 cells, lon 0-359, lat -90-90, 1-degree grid; values 0-25 at the time; about 923 KB (922,701 to 922,802 bytes in the 2026-11-19 runs), about 158 KB with `Accept-Encoding: gzip` |
| response headers | `content-type: application/json`, `cache-control: max-age=60`, `access-control-allow-origin: *`, `etag`, `last-modified` | served through CloudFront (`x-cache: Hit from cloudfront`); no rate-limit headers seen |

## Gotchas

- **The JSON Kp forecast is shorter than the forecast.** On 2026-11-19 the 22:00 UTC text forecast covered Nov 20-22 (24 slots); `noaa-planetary-k-index-forecast.json` carried 17 predicted rows ending at 2026-11-22 00:00 UTC, so the 3-day peak (3.67 at 12-15 UTC on Nov 22) was only in the text product. For "the next 3 days" read `/text/3-day-forecast.txt`; for "tonight" the JSON covered about 2 days ahead.
- **`noaa-scales.json` keys are strings, and `"-1"` comes last.** Look up `s["0"]`, never `s[0]` or by position. The values are strings too (`"0"`, `"15"`), and `null` where a field does not apply.
- **Day `"1"` is today, not tomorrow.** Its `DateStamp` was 2026-11-19 at 23:36 UTC, while the text forecast issued at 22:00 UTC already covered Nov 20-22. Print the `DateStamp` with every forecast line.
- **Kp to G.** Use whole Kp values per the SWPC table; 9- (8.67) is listed under G4, so this skill reads 5- (4.67) as below G1. Where `noaa_scale` is set it is SWPC's own label; it was `null` on every predicted row.
- **No "in effect" field.** Messages stay in `alerts.json` after they expire (K04W expired at 09:00 UTC and was still first at 23:45 UTC). Warnings carry `Valid To:` or, for an extension, `Now Valid Until:`; alerts (`...A` ids) report a threshold reached and have no end; watches list levels by day without a year (block 1 adds it, also across New Year). No cancellation message was in the 30 days on file; block 1 classes a headline starting with "CANCEL" as kind `cancel`, does not count it as in effect, and does not remove the warning it refers to, so read such a message yourself.
- **`estimated` is not "already happened".** Just after 00:00 UTC on 2026-11-20 every slot of that UTC day, 00:00 to 21:00, was labelled `estimated`, so the last non-`predicted` row was 21:00, a slot 19 hours away. For the latest Kp take the newest row whose `time_tag` is not in the future (blocks 1 and 4 do).
- **Times are UTC without a zone suffix** in `time_tag`, `issue_datetime` and `DateStamp`/`TimeStamp`; the aurora file uses `Z`. Attach UTC before comparing with local time.
- **Files are rewritten about every minute.** `Last-Modified` and `ETag` changed between two requests 70 s apart even when the bytes were the same (`/text/3-day-forecast.txt`: 23:38:56, then 23:40:05, 1,962 bytes both times), so conditional GETs often return a full 200. Cache for 60 s, ask for gzip, and poll no faster than the data changes (Kp comes in 3-hour slots; check the `:Issued:` line of the text forecast before re-reading it).
- **Mistakes are HTML.** A misspelled file name is an Apache HTML 404 (`text/html; charset=iso-8859-1`), and `/products/` and `/json/` are HTML directory listings. Check the status and `content-type` before `json.loads`.
- **Aurora grid.** Longitudes run 0-359 (west longitudes + 360) and latitudes are whole degrees; round your location to the nearest cell. The SWPC aurora page calls it "a short-term forecast" that "provides a 30 to 90 minute forecast" (OVATION stands for "Oval Variation, Assessment, Tracking, Intensity, and Online Nowcasting"), so it says nothing about later tonight; use the Kp forecast for that.
- **Credit and no logo.** Show "Source: NOAA Space Weather Prediction Center (SWPC)" with the file URL and the time, do not change the text of official messages and present it as official, and use no NOAA or NWS logo. The disclaimer adds that works "consisting predominantly" of NWS material must carry a notice that it "is not subject to copyright protection" (17 U.S.C. 403).
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.origin` and the page text, not the title.

## What does not work

- **Query parameters**: `noaa-scales.json?days=7` returned the same 1,101 bytes. There is no server-side filtering or history window; each file is fixed.
- **Day 3 from the JSON forecast**: 7 of 24 slots were missing (see Gotchas). Use the text product.
- **`innerText` on SWPC product pages**: the watch, warning and update-cadence sentences are in hidden tabs; use `textContent`.
- **Not tested:** a 429 or an IP block (never provoked), a cancelled warning or watch, the S and R forecast keys during an actual storm, the other `/json/`, `/text/`, `/images/` and `/netcdf/` products, the archive pages and the SWPC email subscription service.
