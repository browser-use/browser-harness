# KMB (Kowloon Motor Bus) via DATA.GOV.HK - Find a Stop on a KMB Route by Name and List the Next 3 Bus Arrivals in Hong Kong Time With Remarks (REST JSON, no key)

Field-tested against data.etabus.gov.hk (the ETA API) and data.gov.hk on 2026-11-24 (US Pacific afternoon; 00:01-00:20 UTC on 25 November, which was 08:01-08:20 on Wednesday 25 November in Hong Kong, HKT = UTC+8) using a fresh Browser Use cloud browser (logged out; one session, 00:04:50-00:20:09 UTC) plus Python `urllib` and `curl` from a Linux machine. 29 browser page loads (1 smoke test, 1 in a first draft of block 1, 7 while probing the firewall, 1 in block 1's first run, 6, 6 and 7 in block 2's three runs) and 117 in-page `fetch()` calls (3 in the first draft of block 1, 2 while probing, 41 in each of block 1's two runs, 10 in each of block 2's three runs), 69 urllib calls (block 3: 43 in its first run, which fell back to one `/stop/{id}` call per stop; 26 in its second run of six commands), and 82 curl calls (67 while exploring the API, the spec and the data dictionary, 15 in block 4's two runs), all serial and at least 1 s apart, except the firewall probes while exploring (20 list and ETA calls 2-3 s apart). Every per-route, per-stop and ETA call was HTTP 200; the deliberate probes gave HTTP 422 (wrong direction word, missing path part, robots.txt on the API host) and HTTP 404 (data.gov.hk/robots.txt). The three list endpoints (`/route`, `/stop`, `/route-stop`) are different: 13 of the curl calls and some of the browser calls to them got **HTTP 403 "The request is blocked."** from the Azure Front Door firewall, sometimes and not always (see Gotchas). curl timed ETA and per-route answers at 0.27-1.80 s and the 1 MB stop list at 1.74 s. No 429, no challenge, no key, no login, no cookie. Before the change at the end of this paragraph, the last runs were block 1's second (00:14 UTC), block 3's second (00:16 UTC) and, for block 4, a verifier's run at 00:30 UTC; block 2's output below is its third run (00:19 UTC). Earlier runs gave the same stops and the same probe answers, and ETAs that moved with the clock. An independent verifier re-ran all four blocks at 00:23-00:32 UTC in a separate cloud browser, re-checked the facts below against the live API, spec, data dictionary, dataset and terms pages, and added a per-stop fallback to block 4 after its `/stop` download got HTTP 403 twice. On 2026-11-25, blocks 1, 3 and 4 were changed to drop arrival rows whose time has already passed before taking the next N; they re-ran on 2026-11-25 at 01:01-01:02 UTC (block 1 in a new cloud browser, stopped and confirmed `stopped`), and the outputs shown for blocks 1, 3 and 4 come from those runs.

robots.txt (checked 2026-11-25 00:01-00:20 UTC with curl, the cloud browser and blocks 3 and 4): https://data.etabus.gov.hk/robots.txt answers HTTP 422 `application/json` `{"code":422,"message":"Invalid/Missing parameter(s)."}` (the API's own error for an unknown path), and https://data.gov.hk/robots.txt answers HTTP 404 with the site's "Page Not Found" HTML page. Neither host has a robots.txt file, so there are no rules for `*` or for any named agent (GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot, Bytespider); RFC 9309 (section 2.3.1.3) says a 4xx robots.txt means "the crawler MAY access any resources on the server". Every path this skill uses (`/v1/transport/kmb/route/...`, `/route-stop/...`, `/stop`, `/stop/{id}`, `/eta/...`, the dataset and terms pages) is allowed. Blocks 3 and 4 read robots.txt before any API call and stop if it ever returns rules that disallow a path. Terms: https://data.gov.hk/en/terms-and-conditions ("Version 1.2 (last updated on 26 May 2025)"): "You are allowed to browse, download, distribute, reproduce, hyperlink to, and print the Data for both commercial and non-commercial purposes on a free-of-charge basis on condition that" you comply with the Terms of Use, "identify clearly the source of the Data and acknowledge the Government and the Relevant Organisations’ ownership of the intellectual property rights in the Data", "indemnify the Government and the Relevant Organisations" against claims arising from your use, and "give proper attribution to the Government, the Relevant Organisations and DATA.GOV.HK". Links do not mean "that the Government agrees with, approves, recommends or endorses" a third-party site. The dataset page https://data.gov.hk/en-data/dataset/hk-td-tis_21-etakmb names the "Owner of Raw Dataset : Kowloon Motor Bus Company (1933) Limited (KMB) and Long Win Bus Company Limited (LWB)" and says "The Transport Department disseminates the KMB/LWB ETA from raw data provided by KMB/LWB". No AI/ML, scraping, crawling, robot, automated-access or rate-limit wording on the terms page, the dataset page, the API specification (v1.05, 23 Oct 2024) or the data dictionary (v1.02, 10 May 2021); the only "non-commercial" is the grant above (block 2 checks the quotes and scans for the words). Naming: this skill writes "KMB" and "Kowloon Motor Bus" in plain text as the data owner and "DATA.GOV.HK" as the source, uses no KMB, LWB or HKSAR Government logo, and is not affiliated with or endorsed by any of them. Blocks 1, 3 and 4 print a source and ownership line.

## Quick summary

- **No scraping needed.** Open JSON API under `https://data.etabus.gov.hk/v1/transport/kmb`, no key, no login. Find the stop: `GET /route-stop/1A/outbound/1` -> stop ids in order (`seq`, `stop`); names come from `GET /stop/{stop_id}` (one stop) or `GET /stop` (all 6,744 stops, 1 MB). Arrivals: `GET /eta/{stop_id}/1A/1` -> up to 3 rows per direction with `eta` (ISO time with `+08:00`), `eta_seq`, `dir`, `seq`, `dest_en`, `rmk_en`. Route ends: `GET /route/1A/outbound/1`. `Access-Control-Allow-Origin: *`, so `fetch()` works from any https page. Routes, stops and directions are case-sensitive.
- **Answers (25 November 2026, 08:14-08:16 HKT):** route **1A** runs **SAU MAU PING (CENTRAL) -> STAR FERRY** (outbound, 35 stops) and back (inbound, 34 stops). **HIU LAI COURT (曉麗苑)** is outbound stop 6 (`41E81A921D79F375`) and inbound stop 29 (`C3201264CC8E5C5D`). Towards Star Ferry at 08:16 HKT: **08:22, "Scheduled Bus"** (one row only); towards Sau Mau Ping: **08:29 and 08:37, no remark** (two rows). A minute earlier (08:15:54) the outbound row had `eta: null` with no remark, and at 08:01 it had 08:12 "Scheduled Bus": the answer changes minute to minute.
- **Match the row, not just the stop.** One `/eta` answer can hold both directions (the Sau Mau Ping terminus `A3ADFCDF8487ADB9` gave `O` seq 1 and `I` seq 34) and `/stop-eta` lists the same bus once per service type (13X at Hiu Lai Court came back three times, as service types 1, 2 and 5, with the same times). Keep `dir` = your bound and `seq` = the stop's place on the route, then drop duplicates.
- **Rate limits:** none published (the terms, the dataset page, the spec and the data dictionary have no number). Responses carry no rate-limit headers, only `cache-control: max-age=300;` and an `x-cache` value (`TCP_REMOTE_HIT`, `TCP_HIT` or `TCP_MISS` seen). ETA data is "updated every 1 minute"; other data "updated daily" (dataset page), at "05:00 daily" (spec). The list endpoints sit behind a firewall that answered 403 to repeated downloads (10 of 12 `/route` calls 2-3 s apart), so download `/stop` once a day and cache it (block 3 does), or use the per-stop endpoint (block 1 does; blocks 3 and 4 fall back to it on a 403). The blocks run serially at 1 call a second.

## What works

### 1. Next 3 arrivals at a named stop on a route (browser)

`on_dataset_tab()` opens the logged-out DATA.GOV.HK dataset page; the API answers `Access-Control-Allow-Origin: *` and the page sets no `connect-src`, so `fetch()` from it works. Browser fetches of the list endpoints `/route` and `/stop` failed with "Failed to fetch" in some runs (the firewall's 403 page carries no CORS header), so this block uses only per-route and per-stop endpoints: 2 `/route` calls, 2 `/route-stop` calls, one `/stop/{id}` per stop until the name matches exactly (35 here), and one `/eta` per match. The run below made 41 calls in about 85 s. Edit `ROUTE`, `STOP` and `SERVICE_TYPE` to ask about another stop.

```python
import json, re, time
from datetime import datetime, timedelta, timezone

ROUTE = "1A"              # KMB/LWB route number as printed on the bus; the API is case-sensitive (upper case)
STOP = "Hiu Lai Court"    # stop name, English or Chinese; exact name first, then "contains"
SERVICE_TYPE = "1"        # 1 = the normal service; specials have 2, 3, ... (see /route in block 3)
N = 3                     # next arrivals per matching stop
API = "https://data.etabus.gov.hk/v1/transport/kmb"
PAGE = "https://data.gov.hk/en-data/dataset/hk-td-tis_21-etakmb"
HKT = timezone(timedelta(hours=8))   # Hong Kong: UTC+8 all year (no daylight saving); the API sends +08:00
PAUSE = 1.0                          # serial, 1 call a second (no rate limit is published)

def on_dataset_tab():
    """fetch() from the logged-out DATA.GOV.HK dataset page. The API answers Access-Control-Allow-Origin: *
    and the page sets no connect-src, so any https page would work; this one keeps the tab on the source."""
    try:
        if js("location.href").startswith(PAGE):
            return
    except Exception:
        pass
    new_tab(PAGE)
    wait_for_load()
    if not js("location.href").startswith(PAGE):
        raise RuntimeError(f"DATA.GOV.HK dataset page did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it
START_JS = """(() => { window.__k = window.__k || {}; const id = String(Math.random()).slice(2); window.__k[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { window.__k[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__k[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__k[%s]; if (v) delete window.__k[%s]; return v; })()"""

calls = []
def call(path):
    """GET -> parsed JSON. 5xx or 429: one retry after 10 s. 'Failed to fetch' (status 0) is what the browser
    shows for the firewall's 403 on the list endpoints (/route, /stop, /route-stop), so it stops at once.
    422 (bad parameter) or anything else that is not HTTP 200 stops."""
    url = API + path
    for attempt in range(2):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer after 60s")
            time.sleep(0.2)
        calls.append((path.split("/")[1], r["status"], round(time.time() - t0, 2)))
        time.sleep(PAUSE)
        if attempt == 0 and r["status"] in (429, 500, 502, 503, 504):
            time.sleep(10)
            continue
        break
    if r["status"] == 0:
        raise RuntimeError(f"{url}: fetch failed ({r['text']}); list endpoints answer 403 to browsers: stop")
    if r["status"] != 200:
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")
    return json.loads(r["text"])

def norm(s):
    return re.sub(r"\s+", " ", s).strip().upper()   # stop names come in upper case, some with double spaces

def hkt(iso):
    return datetime.fromisoformat(iso).astimezone(HKT)

on_dataset_tab()
route = ROUTE.strip().upper()
q = norm(STOP)
print(f"KMB ETA API, checked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC ({datetime.now(HKT):%a %d %b %H:%M} HKT)")

names = {}
def stop_name(sid):
    if sid not in names:
        names[sid] = call(f"/stop/{sid}")["data"]
    return names[sid]

found = []                                        # (bound letter, seq, stop id, route info)
for bound in ("outbound", "inbound"):
    info = call(f"/route/{route}/{bound}/{SERVICE_TYPE}")["data"]
    if not info:                                  # {} = no such route/direction (circular routes have no inbound)
        print(f"route {route} {bound} type {SERVICE_TYPE}: not in the API")
        continue
    stops = sorted(call(f"/route-stop/{route}/{bound}/{SERVICE_TYPE}")["data"], key=lambda s: int(s["seq"]))
    exact, part = [], []
    for s in stops:                               # one /stop/{id} call per stop, until the first exact match
        st = stop_name(s["stop"])
        if q in (norm(st["name_en"]), st["name_tc"]):
            exact.append((int(s["seq"]), s["stop"]))
            break
        if q in norm(st["name_en"]) or q in st["name_tc"]:
            part.append((int(s["seq"]), s["stop"]))
    hits = exact or part
    found += [(info["bound"], seq, sid, info) for seq, sid in hits]
    print(f"route {route} {bound} ({info['bound']}) type {SERVICE_TYPE}: {info['orig_en']} -> {info['dest_en']}, "
          f"{len(stops)} stops, {'exact' if exact else 'contains'} match for {STOP!r}: "
          + (", ".join(f"stop {seq} {names[sid]['name_en']}" for seq, sid in hits) or "none"))

for bound, seq, sid, info in found:
    d = call(f"/eta/{sid}/{route}/{SERVICE_TYPE}")
    now = hkt(d["generated_timestamp"])
    uniq = {}
    for e in d["data"]:
        if e["dir"] == bound and e["seq"] == seq:   # other directions can come back,
            uniq.setdefault((e["eta"], e["rmk_en"]), e)   # and the same bus once per service type
    past = [e for e in uniq.values() if e["eta"] and hkt(e["eta"]) < now]   # cached rows can be behind the clock
    rows = sorted((e for e in uniq.values() if e not in past), key=lambda e: (e["eta"] is None, e["eta"] or ""))[:N]
    s = names[sid]
    print(f"\n{route} to {info['dest_en']} ({bound}), stop {seq}: {s['name_en']} {s['name_tc']} ({sid}, "
          f"{float(s['lat']):.5f}, {float(s['long']):.5f}); generated {now:%H:%M:%S} HKT")
    if len(rows) < N:
        print(f"  only {len(rows)} of {N} asked for: the answer holds at most 3 rows per direction"
              + (f", and {len(past)} already past were dropped" if past else ""))
    for e in rows:
        if e["eta"] is None:
            print(f"  {e['eta_seq']}. no time       remark: {e['rmk_en'] or '(none)'} / {e['rmk_tc'] or '-'}")
            continue
        t = hkt(e["eta"])
        when = f"in {int((t - now).total_seconds() // 60)} min"
        print(f"  {e['eta_seq']}. {t:%H:%M:%S} HKT  {when:<10} remark: {e['rmk_en'] or '(none)'}")
if not found:
    print(f"\nno stop matching {STOP!r} on route {route} (service type {SERVICE_TYPE})")

by = {}
for p, s, t in calls:
    by.setdefault(p, []).append((s, t))
print(f"\n{len(calls)} API calls: " + ", ".join(f"{p} x{len(v)} HTTP {sorted({s for s, _ in v})} "
      f"{min(t for _, t in v):.2f}-{max(t for _, t in v):.2f}s" for p, v in by.items()))
print("Source: DATA.GOV.HK, Real time Arrival Data of Kowloon Motor Bus and Long Win Bus Services (Transport "
      "Department). Data owners: The Kowloon Motor Bus Company (1933) Limited and Long Win Bus Company Limited; "
      "intellectual property rights belong to the HKSAR Government and these data owners. Changed: stop picked, "
      "times shown in HKT with minutes to go.")
```

Output (re-run on 2026-11-25, 01:01-01:02 UTC = 09:01-09:02 HKT, in a new cloud browser; the same two stops and 41 calls as the 00:08 and 00:14 UTC runs, with ETAs that moved with the clock):

```text
KMB ETA API, checked 2026-11-25 01:01 UTC (Wed 25 Nov 09:01 HKT)
route 1A outbound (O) type 1: SAU MAU PING (CENTRAL) -> STAR FERRY, 35 stops, exact match for 'Hiu Lai Court': stop 6 HIU LAI COURT
route 1A inbound (I) type 1: STAR FERRY -> SAU MAU PING (CENTRAL), 34 stops, exact match for 'Hiu Lai Court': stop 29 HIU LAI COURT

1A to STAR FERRY (O), stop 6: HIU LAI COURT 曉麗苑 (41E81A921D79F375, 22.31871, 114.22984); generated 09:02:54 HKT
  1. 09:09:26 HKT  in 6 min   remark: Scheduled Bus
  2. 09:18:26 HKT  in 15 min  remark: Scheduled Bus
  3. 09:26:26 HKT  in 23 min  remark: Scheduled Bus

1A to SAU MAU PING (CENTRAL) (I), stop 29: HIU LAI COURT 曉麗苑 (C3201264CC8E5C5D, 22.31908, 114.22935); generated 09:02:56 HKT
  1. 09:27:24 HKT  in 24 min  remark: (none)
  2. 09:43:28 HKT  in 40 min  remark: (none)
  3. 09:53:10 HKT  in 50 min  remark: (none)

41 API calls: route x2 HTTP [200] 1.11-1.11s, route-stop x2 HTTP [200] 1.11-1.11s, stop x35 HTTP [200] 0.32-1.90s, eta x2 HTTP [200] 1.11-1.11s
Source: DATA.GOV.HK, Real time Arrival Data of Kowloon Motor Bus and Long Win Bus Services (Transport Department). Data owners: The Kowloon Motor Bus Company (1933) Limited and Long Win Bus Company Limited; intellectual property rights belong to the HKSAR Government and these data owners. Changed: stop picked, times shown in HKT with minutes to go.
```

### 2. robots.txt, the terms and dataset quotes, and what the API does with mistakes (browser)

7 page loads and 10 in-page `fetch()` calls in the same tab. robots.txt is loaded as a page on both hosts. The quotes are matched on the flattened page text. The probes run from the dataset page.

```python
import json, time

API = "https://data.etabus.gov.hk/v1/transport/kmb"
TERMS = "https://data.gov.hk/en/terms-and-conditions"
PAGE = "https://data.gov.hk/en-data/dataset/hk-td-tis_21-etakmb"

START_JS = """(() => { window.__k = window.__k || {}; const id = String(Math.random()).slice(2); window.__k[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { window.__k[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__k[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__k[%s]; if (v) delete window.__k[%s]; return v; })()"""

def raw(url):
    """One in-page GET -> {status, text}. No retries: this block only inspects answers."""
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1.0)
    return r

def page(url, wait_for=None):
    """Load a page -> (HTTP status, content type, flattened text); waits up to 20 s for a phrase."""
    goto_url(url)
    wait_for_load()
    t0 = time.time()
    while True:
        txt = " ".join((js("(document.body || document.documentElement).innerText || ''") or "").split())
        if not wait_for or wait_for in txt or time.time() - t0 > 20:
            break
        time.sleep(0.5)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    time.sleep(1.0)
    return st, js("document.contentType"), txt

# 1) robots.txt on the API host and on DATA.GOV.HK: both 4xx, so there are no rules (RFC 9309, 2.3.1.3)
for host in ("data.etabus.gov.hk", "data.gov.hk"):
    st, ct, txt = page(f"https://{host}/robots.txt")
    rules = st == 200 and ct.startswith("text/plain")
    print(f"{host}/robots.txt: HTTP {st} {ct}; {'RULES PRESENT, check them' if rules else 'no robots rules'}; "
          f"text starts {txt[:56]!r}")

# 2) the terms and the dataset page, as a reader sees them
for url, needles in (
    (TERMS, ["You are allowed to browse, download, distribute, reproduce, hyperlink to, and print the Data for both "
             "commercial and non-commercial purposes on a free-of-charge basis on condition that",
             "you shall identify clearly the source of the Data and acknowledge the Government and the Relevant "
             "Organisations’ ownership of the intellectual property rights in the Data",
             "you shall indemnify the Government and the Relevant Organisations",
             "you shall also give proper attribution to the Government, the Relevant Organisations and DATA.GOV.HK",
             "does not give rise to any statement, representation or warranty, express or implied, that the "
             "Government agrees with, approves, recommends or endorses",
             "Version 1.2 (last updated on 26 May 2025)"]),
    (PAGE, ["Owner of Raw Dataset : Kowloon Motor Bus Company (1933) Limited (KMB) and Long Win Bus Company Limited (LWB)",
            "The Transport Department disseminates the KMB/LWB ETA from raw data provided by KMB/LWB",
            "Estimated Time of Arrival (ETA) data updated every 1 minute. Other data updated daily.",
            "https://data.etabus.gov.hk/datagovhk/kmb_eta_data_dictionary.pdf"]),
):
    st, ct, txt = page(url, wait_for=needles[0][:40])
    short = url.split("//")[1][:44]
    print(f"\n{short} HTTP {st}")
    for n in needles:
        print(f"  {'found' if n in txt else 'MISSING'}: {n[:96]!r}")
    low = txt.lower()
    for w in ("scrap", "crawl", "robot", "artificial intelligence", "machine learning", "automat",
              "rate limit", "non-commercial"):
        hits = [low[max(0, i - 30):i + 30] for i in range(len(low)) if low.startswith(w, i)]
        print(f"  word {w!r}: {len(hits)}" + (f" -> {hits[0]!r}" if hits else ""))

# 3) what the API does with mistakes (fetch from the dataset page; the API sends CORS *)
print()
for label, path in (
    ("route 1A outbound type 1        ", "/route/1A/outbound/1"),
    ("lower-case route 1a             ", "/route/1a/outbound/1"),
    ("direction 'O' in the path       ", "/route/1A/O/1"),
    ("service type 2 (1A has none)    ", "/route/1A/outbound/2"),
    ("missing direction               ", "/route/1A"),
    ("unknown stop id                 ", "/eta/0000000000000000/1A/1"),
    ("lower-case stop id              ", "/eta/41e81a921d79f375/1A/1"),
    ("stop not on route 999           ", "/eta/41E81A921D79F375/999/1"),
    ("stop list /stop (1 MB)          ", "/stop"),
    ("route list /route               ", "/route"),
):
    r = raw(API + path)
    print(f"{label} HTTP {r['status']}: {' '.join(r['text'].split())[:100]}")

# 4) a list endpoint as a page load shows why fetch() can fail: the firewall's 403 page has no CORS header
for p in ("/route", "/stop"):
    st, ct, txt = page(API + p)
    print(f"{'' if p == '/stop' else chr(10)}page load {API}{p}: HTTP {st} {ct}: {txt[:40]!r}")
st, ct, txt = page(API + "/stop/41E81A921D79F375")
print(f"page load {API}/stop/41E81A921D79F375: HTTP {st}: {txt[:90]}")
```

Output (third run, 2026-11-25 00:19 UTC). In the two runs before it, the `/stop` fetch came back HTTP 200 with the stop list while `/route` failed the same way, and the page load of `/stop` was HTTP 200 too; in a first draft of block 1 (00:05 UTC) `/route` was HTTP 200 and `/stop` failed twice. A verifier's run at 00:25 UTC in another cloud browser got the `/stop` fetch HTTP 200, the `/route` fetch "Failed to fetch", the `/route` page load HTTP 200 and the `/stop` page load HTTP 403:

```text
data.etabus.gov.hk/robots.txt: HTTP 422 application/json; no robots rules; text starts '{"code":422,"message":"Invalid/Missing parameter(s)."}'
data.gov.hk/robots.txt: HTTP 404 text/html; no robots rules; text starts 'Page Not Found Sorry, the page you are looking for does '

data.gov.hk/en/terms-and-conditions HTTP 200
  found: 'You are allowed to browse, download, distribute, reproduce, hyperlink to, and print the Data for'
  found: 'you shall identify clearly the source of the Data and acknowledge the Government and the Relevan'
  found: 'you shall indemnify the Government and the Relevant Organisations'
  found: 'you shall also give proper attribution to the Government, the Relevant Organisations and DATA.GO'
  found: 'does not give rise to any statement, representation or warranty, express or implied, that the Go'
  found: 'Version 1.2 (last updated on 26 May 2025)'
  word 'scrap': 0
  word 'crawl': 0
  word 'robot': 0
  word 'artificial intelligence': 0
  word 'machine learning': 0
  word 'automat': 0
  word 'rate limit': 0
  word 'non-commercial': 1 -> ' data for both commercial and non-commercial purposes on a f'

data.gov.hk/en-data/dataset/hk-td-tis_21-eta HTTP 200
  found: 'Owner of Raw Dataset : Kowloon Motor Bus Company (1933) Limited (KMB) and Long Win Bus Company L'
  found: 'The Transport Department disseminates the KMB/LWB ETA from raw data provided by KMB/LWB'
  found: 'Estimated Time of Arrival (ETA) data updated every 1 minute. Other data updated daily.'
  found: 'https://data.etabus.gov.hk/datagovhk/kmb_eta_data_dictionary.pdf'
  word 'scrap': 0
  word 'crawl': 0
  word 'robot': 0
  word 'artificial intelligence': 0
  word 'machine learning': 0
  word 'automat': 0
  word 'rate limit': 0
  word 'non-commercial': 0

route 1A outbound type 1         HTTP 200: {"type":"Route","version":"1.0","generated_timestamp":"2026-11-25T08:19:37+08:00","data":{"route":"1
lower-case route 1a              HTTP 200: {"type":"Route","version":"1.0","generated_timestamp":"2026-11-25T08:19:39+08:00","data":{}}
direction 'O' in the path        HTTP 422: {"code":422,"message":"Invalid direction."}
service type 2 (1A has none)     HTTP 200: {"type":"Route","version":"1.0","generated_timestamp":"2026-11-25T08:19:43+08:00","data":{}}
missing direction                HTTP 422: {"code":422,"message":"Invalid/Missing parameter(s)."}
unknown stop id                  HTTP 200: {"type":"ETA","version":"1.0","generated_timestamp":"2026-11-25T08:19:47+08:00","data":[]}
lower-case stop id               HTTP 200: {"type":"ETA","version":"1.0","generated_timestamp":"2026-11-25T08:19:49+08:00","data":[]}
stop not on route 999            HTTP 200: {"type":"ETA","version":"1.0","generated_timestamp":"2026-11-25T08:19:51+08:00","data":[]}
stop list /stop (1 MB)           HTTP 0: TypeError: Failed to fetch
route list /route                HTTP 0: TypeError: Failed to fetch

page load https://data.etabus.gov.hk/v1/transport/kmb/route: HTTP 403 text/html: 'The request is blocked. 20261125T001954Z'
page load https://data.etabus.gov.hk/v1/transport/kmb/stop: HTTP 200 application/json: '{"type":"StopList","version":"1.0","gene'
page load https://data.etabus.gov.hk/v1/transport/kmb/stop/41E81A921D79F375: HTTP 200: {"type":"Stop","version":"1.0","generated_timestamp":"2026-11-25T08:20:00+08:00","data":{"
```

### 3. The same with Python urllib, as a command-line tool: robots check, cached stop list, next arrivals (no browser)

Standard library only. It runs with `python3 -I`. Save it as `kmb.py`. It reads robots.txt, then the stop list once per data day (stored in `~/.cache/kmb-eta/stop-YYYY-MM-DD.json`, or in `$KMB_CACHE`; the day turns at 05:00 HKT, when the spec says the list is refreshed). If the firewall answers 403 to the list, it falls back to one `/stop/{id}` call per stop and stops scanning a direction at the first exact match. Then 1 `/route` and 1 `/route-stop` call per direction and 1 `/eta` call per matching stop. Exit code 2 = no such route or stop. On a 429 or 5xx it retries once after 10 s.

```python
"""Next KMB / Long Win bus arrivals at a stop, by route number and stop name (DATA.GOV.HK ETA API,
Python standard library only).

  python3 kmb.py 1A "Hiu Lai Court"            # both directions, next 3 arrivals each
  python3 kmb.py 1A "star ferry" --bound I     # "contains" match, inbound only
  python3 kmb.py 1A 曉麗苑 -n 2                 # Chinese stop names work too
"""
import argparse, gzip, json, os, re, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timedelta, timezone

HOST = "https://data.etabus.gov.hk"
API = HOST + "/v1/transport/kmb"
HKT = timezone(timedelta(hours=8))          # Hong Kong, UTC+8 all year; the API sends +08:00
UA = "kmb-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider", "kmb-skill-example"]   # last = this UA
CACHE = os.path.expanduser(os.environ.get("KMB_CACHE", "~/.cache/kmb-eta"))
CREDIT = ("Source: DATA.GOV.HK, Real time Arrival Data of Kowloon Motor Bus and Long Win Bus Services (Transport "
          "Department). Data owners: The Kowloon Motor Bus Company (1933) Limited and Long Win Bus Company Limited; "
          "intellectual property rights belong to the HKSAR Government and these data owners.")
calls, _last, RP = [], [0.0], None

def http(url):
    """-> (status, text). Serial, at least 1 s apart; asks for gzip and unzips it (urllib does not)."""
    time.sleep(max(0.0, _last[0] + 1.0 - time.time()))
    t0 = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status, enc, body = r.status, r.headers.get("Content-Encoding"), r.read()
    except urllib.error.HTTPError as e:
        status, enc, body = e.code, e.headers.get("Content-Encoding"), e.read()
    except (urllib.error.URLError, TimeoutError) as e:
        status, enc, body = 0, None, str(e).encode()
    _last[0] = time.time()
    size = len(body)
    if enc == "gzip":
        body = gzip.decompress(body)
    p = url[len(API):]
    calls.append(("robots.txt" if not url.startswith(API) else "stop list" if p == "/stop" else p.split("/")[1],
                  status, round(time.time() - t0, 2), size))
    return status, body.decode("utf-8", errors="replace")

def call(path, ok403=False):
    """-> parsed JSON, or None for a 403 when ok403 (the firewall blocks repeated list downloads).
    Checks robots.txt first. 429/5xx/network error: one retry after 10 s. 422 = bad parameter: stop."""
    url = API + path
    if RP and not all(RP.can_fetch(a, url) for a in AGENTS):
        sys.exit(f"robots.txt disallows {path}: stop")
    for attempt in range(2):
        s, text = http(url)
        if attempt == 0 and s in (0, 429, 500, 502, 503, 504):
            time.sleep(10)
            continue
        break
    if s == 403 and ok403:
        return None
    if s != 200:
        sys.exit(f"{url}: HTTP {s} {' '.join(text.split())[:160]!r}")
    return json.loads(text)

def robots_load():
    """data.etabus.gov.hk/robots.txt answers HTTP 422 JSON today: a 4xx other than 429 = no rules.
    429, 5xx or no answer = rules unknown, so stop."""
    global RP
    s, text = http(HOST + "/robots.txt")
    if 400 <= s < 500 and s != 429:
        print(f"robots.txt: HTTP {s}, no rules")
        return
    if s != 200:
        sys.exit(f"robots.txt: HTTP {s}; rules unknown, try later")
    RP = urllib.robotparser.RobotFileParser()
    RP.parse(text.splitlines())
    print(f"robots.txt: HTTP 200; every API path is checked for all {len(AGENTS)} agents")

def norm(s):
    return re.sub(r"\s+", " ", s).strip().upper()

def stop_names():
    """The 6,744-stop list (1 MB), once per data day: the API refreshes it at 05:00 HKT, and the firewall
    answers 403 to repeated downloads. -> {stop_id: stop} or None if the list is blocked right now."""
    day = (datetime.now(HKT) - timedelta(hours=5)).strftime("%Y-%m-%d")
    path = os.path.join(CACHE, f"stop-{day}.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    d = call("/stop", ok403=True)
    if d is None:
        return None
    names = {s["stop"]: s for s in d["data"]}
    os.makedirs(CACHE, exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(names, f, ensure_ascii=False)
    os.replace(path + ".tmp", path)
    return names

ap = argparse.ArgumentParser()
ap.add_argument("route", help="route number, e.g. 1A, 74B, N293 (upper-cased for you)")
ap.add_argument("stop", help="stop name in English or Chinese; exact name wins, else 'contains'")
ap.add_argument("-n", type=int, default=3, help="arrivals per stop (the API gives at most 3)")
ap.add_argument("--bound", choices=["O", "I"], help="O = outbound, I = inbound; default both")
ap.add_argument("--service-type", default="1", help="1 = normal service (default); specials are 2, 3, ...")
args = ap.parse_args()
if not 1 <= args.n <= 3:
    ap.error("-n must be 1, 2 or 3")
route, q = args.route.strip().upper(), norm(args.stop)

print(f"KMB ETA, checked {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC ({datetime.now(HKT):%a %H:%M} HKT)")
robots_load()
names = stop_names()
print(f"stop names: {'list of ' + str(len(names)) + ' stops (cached per day)' if names else '/stop blocked (403), one /stop/{id} call per stop'}")

def name(sid):
    if names is not None and sid in names:
        return names[sid]
    cache = name.__dict__.setdefault("c", {})
    if sid not in cache:
        cache[sid] = call(f"/stop/{sid}")["data"]
    return cache[sid]

found = []
for b in [x for x in ("O", "I") if args.bound in (None, x)]:
    bound = {"O": "outbound", "I": "inbound"}[b]
    info = call(f"/route/{route}/{bound}/{args.service_type}")["data"]
    if not info:
        print(f"{route} {bound} service type {args.service_type}: not in the API")
        continue
    stops = sorted(call(f"/route-stop/{route}/{bound}/{args.service_type}")["data"], key=lambda s: int(s["seq"]))
    exact, part = [], []
    for s in stops:
        st = name(s["stop"])
        if q in (norm(st["name_en"]), st["name_tc"]):
            exact.append((int(s["seq"]), s["stop"]))
            if names is None:
                break                                  # stop paying /stop/{id} calls once found
        elif q in norm(st["name_en"]) or q in st["name_tc"]:
            part.append((int(s["seq"]), s["stop"]))
    hits = exact or part
    print(f"{route} {bound}: {info['orig_en']} -> {info['dest_en']}, {len(stops)} stops; "
          + (", ".join(f"stop {seq} {name(sid)['name_en']}" for seq, sid in hits) or f"no stop matching {args.stop!r}"))
    found += [(b, seq, sid, info) for seq, sid in hits]

if not found:
    print(CREDIT)
    sys.exit(2)
for b, seq, sid, info in found:
    d = call(f"/eta/{sid}/{route}/{args.service_type}")
    now = datetime.fromisoformat(d["generated_timestamp"])
    uniq = {}
    for e in d["data"]:
        if e["dir"] == b and e["seq"] == seq:          # the answer can hold the other direction too
            uniq.setdefault((e["eta"], e["rmk_en"]), e)  # and the same bus once per service type
    past = [e for e in uniq.values() if e["eta"] and datetime.fromisoformat(e["eta"]) < now]   # stale cached rows
    rows = sorted((e for e in uniq.values() if e not in past), key=lambda e: (e["eta"] is None, e["eta"] or ""))[:args.n]
    s = name(sid)
    print(f"\n{route} -> {info['dest_en']} at stop {seq} {s['name_en']} / {s['name_tc']} ({sid})")
    if len(rows) < args.n:
        print(f"  only {len(rows)} of {args.n}: the answer holds at most 3 rows per direction"
              + (f", {len(past)} already past dropped" if past else ""))
    for e in rows:
        rmk = e["rmk_en"] or "-"
        if e["eta"] is None:
            print(f"  {e['eta_seq']}  no time   remark: {rmk}")
            continue
        t = datetime.fromisoformat(e["eta"]).astimezone(HKT)
        print(f"  {e['eta_seq']}  {t:%H:%M} HKT  {'in ' + str(int((t - now).total_seconds() // 60)) + ' min':<16} remark: {rmk}")

by = {}
for p, st, t, z in calls:
    by.setdefault(p, []).append(st)
print(f"\n{len(calls)} calls: " + ", ".join(f"{p} x{len(v)} {sorted(set(v))}" for p, v in by.items()))
print(CREDIT + " Times converted to HKT and stop matched by this script.")
```

Output (six commands, re-run on 2026-11-25, 01:01-01:02 UTC = 09:01-09:02 HKT, empty cache; the first command downloaded and cached the stop list, the others read the cache, and in the first and third the outbound answer still held a row whose time had passed, which is now dropped). The first run of the first command, on 2026-11-25 at 00:13 UTC, got HTTP 403 on `/stop`, fell back to 35 `/stop/{id}` calls and found the same two stops (43 calls in all):

```text
$ python3 -I kmb.py 1A "Hiu Lai Court"
KMB ETA, checked 2026-11-25 01:01 UTC (Wed 09:01 HKT)
robots.txt: HTTP 422, no rules
stop names: list of 6744 stops (cached per day)
1A outbound: SAU MAU PING (CENTRAL) -> STAR FERRY, 35 stops; stop 6 HIU LAI COURT
1A inbound: STAR FERRY -> SAU MAU PING (CENTRAL), 34 stops; stop 29 HIU LAI COURT

1A -> STAR FERRY at stop 6 HIU LAI COURT / 曉麗苑 (41E81A921D79F375)
  only 2 of 3: the answer holds at most 3 rows per direction, 1 already past dropped
  2  09:09 HKT  in 7 min         remark: Scheduled Bus
  3  09:18 HKT  in 16 min        remark: Scheduled Bus

1A -> SAU MAU PING (CENTRAL) at stop 29 HIU LAI COURT / 曉麗苑 (C3201264CC8E5C5D)
  1  09:27 HKT  in 25 min        remark: -
  2  09:43 HKT  in 41 min        remark: -
  3  09:52 HKT  in 51 min        remark: -

8 calls: robots.txt x1 [422], stop list x1 [200], route x2 [200], route-stop x2 [200], eta x2 [200]
Source: DATA.GOV.HK, Real time Arrival Data of Kowloon Motor Bus and Long Win Bus Services (Transport Department). Data owners: The Kowloon Motor Bus Company (1933) Limited and Long Win Bus Company Limited; intellectual property rights belong to the HKSAR Government and these data owners. Times converted to HKT and stop matched by this script.

$ python3 -I kmb.py 1A "star ferry" --bound I
KMB ETA, checked 2026-11-25 01:01 UTC (Wed 09:01 HKT)
robots.txt: HTTP 422, no rules
stop names: list of 6744 stops (cached per day)
1A inbound: STAR FERRY -> SAU MAU PING (CENTRAL), 34 stops; stop 1 STAR FERRY, HARBOUR CITY

1A -> SAU MAU PING (CENTRAL) at stop 1 STAR FERRY, HARBOUR CITY / 尖沙咀碼頭,海港城 (8D804CFD9C7B9042)
  1  09:12 HKT  in 10 min        remark: Scheduled Bus
  2  09:24 HKT  in 22 min        remark: Scheduled Bus
  3  09:36 HKT  in 34 min        remark: Scheduled Bus

4 calls: robots.txt x1 [422], route x1 [200], route-stop x1 [200], eta x1 [200]
Source: DATA.GOV.HK, Real time Arrival Data of Kowloon Motor Bus and Long Win Bus Services (Transport Department). Data owners: The Kowloon Motor Bus Company (1933) Limited and Long Win Bus Company Limited; intellectual property rights belong to the HKSAR Government and these data owners. Times converted to HKT and stop matched by this script.

$ python3 -I kmb.py 1A 曉麗苑 -n 2
KMB ETA, checked 2026-11-25 01:02 UTC (Wed 09:02 HKT)
robots.txt: HTTP 422, no rules
stop names: list of 6744 stops (cached per day)
1A outbound: SAU MAU PING (CENTRAL) -> STAR FERRY, 35 stops; stop 6 HIU LAI COURT
1A inbound: STAR FERRY -> SAU MAU PING (CENTRAL), 34 stops; stop 29 HIU LAI COURT

1A -> STAR FERRY at stop 6 HIU LAI COURT / 曉麗苑 (41E81A921D79F375)
  2  09:09 HKT  in 7 min         remark: Scheduled Bus
  3  09:18 HKT  in 16 min        remark: Scheduled Bus

1A -> SAU MAU PING (CENTRAL) at stop 29 HIU LAI COURT / 曉麗苑 (C3201264CC8E5C5D)
  1  09:27 HKT  in 25 min        remark: -
  2  09:43 HKT  in 41 min        remark: -

7 calls: robots.txt x1 [422], route x2 [200], route-stop x2 [200], eta x2 [200]
Source: DATA.GOV.HK, Real time Arrival Data of Kowloon Motor Bus and Long Win Bus Services (Transport Department). Data owners: The Kowloon Motor Bus Company (1933) Limited and Long Win Bus Company Limited; intellectual property rights belong to the HKSAR Government and these data owners. Times converted to HKT and stop matched by this script.

$ python3 -I kmb.py N293 "Hiu Lai Court" --bound O
KMB ETA, checked 2026-11-25 01:02 UTC (Wed 09:02 HKT)
robots.txt: HTTP 422, no rules
stop names: list of 6744 stops (cached per day)
N293 outbound: SHEUNG TAK -> MONG KOK (PARK AVENUE), 41 stops; stop 22 HIU LAI COURT

N293 -> MONG KOK (PARK AVENUE) at stop 22 HIU LAI COURT / 曉麗苑 (41E81A921D79F375)
  only 1 of 3: the answer holds at most 3 rows per direction
  1  no time   remark: -

4 calls: robots.txt x1 [422], route x1 [200], route-stop x1 [200], eta x1 [200]
Source: DATA.GOV.HK, Real time Arrival Data of Kowloon Motor Bus and Long Win Bus Services (Transport Department). Data owners: The Kowloon Motor Bus Company (1933) Limited and Long Win Bus Company Limited; intellectual property rights belong to the HKSAR Government and these data owners. Times converted to HKT and stop matched by this script.

$ python3 -I kmb.py zz9 "Hiu Lai Court"
KMB ETA, checked 2026-11-25 01:02 UTC (Wed 09:02 HKT)
robots.txt: HTTP 422, no rules
stop names: list of 6744 stops (cached per day)
ZZ9 outbound service type 1: not in the API
ZZ9 inbound service type 1: not in the API
Source: DATA.GOV.HK, Real time Arrival Data of Kowloon Motor Bus and Long Win Bus Services (Transport Department). Data owners: The Kowloon Motor Bus Company (1933) Limited and Long Win Bus Company Limited; intellectual property rights belong to the HKSAR Government and these data owners.

$ python3 -I kmb.py 1A "Hiu Lai Court" -n 5
usage: kmb.py [-h] [-n N] [--bound {O,I}] [--service-type SERVICE_TYPE]
              route stop
kmb.py: error: -n must be 1, 2 or 3
```

### 4. curl: route ends, stop names, next arrivals, headers, mistakes

```bash
#!/usr/bin/env bash
# KMB ETA API with curl: robots, route 1A both ways, stop names, next 3 arrivals at one stop, headers, mistakes.
set -euo pipefail
K=https://data.etabus.gov.hk/v1/transport/kmb
C=(curl -sS --max-time 30 --compressed -A 'kmb-skill-example/1.0 (+https://github.com/browser-use/browser-harness)')
ROUTE=1A; STOP='HIU LAI COURT'
T=$(mktemp -d)
# 0. robots.txt first: a 4xx other than 429 = no rules; 200 = check the paths below
code=$("${C[@]}" -o "$T/robots" -w '%{http_code}' https://data.etabus.gov.hk/robots.txt)
echo "robots.txt HTTP $code: $(head -c 80 "$T/robots")"
python3 -c 'import sys, urllib.robotparser
code, text = int(sys.argv[1]), open(sys.argv[2]).read()
if code != 200 and not (400 <= code < 500 and code != 429): sys.exit("robots.txt rules unknown: stop")
rp = urllib.robotparser.RobotFileParser(); rp.parse(text.splitlines() if code == 200 else [])
paths = ("/route/1A/outbound/1", "/route-stop/1A/outbound/1", "/stop", "/eta/41E81A921D79F375/1A/1")
if not all(rp.can_fetch(a, "https://data.etabus.gov.hk/v1/transport/kmb" + p) for a in ("*", "kmb-skill-example") for p in paths): sys.exit("robots.txt disallows a path: stop")
print("robots: paths allowed")' "$code" "$T/robots"
sleep 1
# 1. the route both ways (paths say outbound/inbound, answers say O/I)
for b in outbound inbound; do
  "${C[@]}" --fail "$K/route/$ROUTE/$b/1" | python3 -c 'import json, sys
d = json.load(sys.stdin)["data"]; print(sys.argv[1], "->", d["bound"], "|", d["orig_en"], "->", d["dest_en"], "|", d["orig_tc"], "->", d["dest_tc"])' "$b"
  sleep 1
done
# 2. stop names: the 1 MB list once, then the route's stops; if the firewall answers 403 to the list
#    (it does to repeated downloads), one /stop/{id} call per stop of the route instead
code=$("${C[@]}" -o "$T/stops" -w '%{http_code}' "$K/stop")
echo "stop list HTTP $code, $(wc -c < "$T/stops") bytes"
sleep 1
"${C[@]}" --fail "$K/route-stop/$ROUTE/outbound/1" -o "$T/rs"
if [ "$code" != 200 ]; then
  echo "stop list blocked (HTTP $code): one /stop/{id} call per stop of the route instead"
  mkdir "$T/s"
  for sid in $(python3 -c 'import json, sys; print(*[s["stop"] for s in json.load(open(sys.argv[1]))["data"]])' "$T/rs"); do
    sleep 1; "${C[@]}" --fail "$K/stop/$sid" -o "$T/s/$sid"
  done
  python3 -c 'import json, os, sys
d = sys.argv[1]; json.dump({"data": [json.load(open(os.path.join(d, f)))["data"] for f in os.listdir(d)]}, open(sys.argv[2], "w"))' "$T/s" "$T/stops"
fi
python3 -c 'import json, sys
names = {s["stop"]: s for s in json.load(open(sys.argv[1]))["data"]}
rs = json.load(open(sys.argv[2]))["data"]
print(len(rs), "stops outbound; seq is a string here:", repr(rs[0]["seq"]))
for s in rs:
    if s["seq"] in ("1", "5", "6", "7", str(len(rs))):
        n = names[s["stop"]]; print(" ", s["seq"], s["stop"], n["name_en"], n["name_tc"], n["lat"], n["long"])
hit = [s for s in rs if names[s["stop"]]["name_en"] == sys.argv[3]][0]
open(sys.argv[4], "w").write(hit["stop"] + " " + hit["seq"] + "\n")' "$T/stops" "$T/rs" "$STOP" "$T/hit"
read -r SID SEQ < "$T/hit"
sleep 1
# 3. next arrivals at that stop: keep dir O and this seq, drop times already past; +08:00 (HKT); eta can be null
"${C[@]}" --fail "$K/eta/$SID/$ROUTE/1" | python3 -c 'import json, sys
from datetime import datetime as T
d = json.load(sys.stdin); seq = int(sys.argv[1]); now = T.fromisoformat(d["generated_timestamp"])
print("generated", d["generated_timestamp"], "|", len(d["data"]), "rows, dirs", sorted({e["dir"] for e in d["data"]}))
for e in [e for e in d["data"] if e["dir"] == "O" and e["seq"] == seq and not (e["eta"] and T.fromisoformat(e["eta"]) < now)][:3]:
    print(" ", e["eta_seq"], e["eta"], "|", e["dest_en"], "|", repr(e["rmk_en"]), "|", e["data_timestamp"])' "$SEQ"
sleep 1
# 4. response headers: 300 s cache, CORS open, no rate-limit headers
"${C[@]}" -D - -o /dev/null "$K/eta/$SID/$ROUTE/1" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|content-encoding|cache-control|access-control-allow-origin|retry-after|x-cache|x-ratelimit[a-z-]*|ratelimit[a-z-]*):)'
sleep 1
# 5. mistakes: a wrong direction word is HTTP 422; a wrong case or unknown id is HTTP 200 with empty data
for p in "route/$ROUTE/O/1" "route/1a/outbound/1" "eta/0000000000000000/$ROUTE/1"; do
  "${C[@]}" -o "$T/m" -w "$p: HTTP %{http_code} " "$K/$p"; head -c 110 "$T/m"; echo; sleep 1
done
rm -rf "$T"
echo "Source: DATA.GOV.HK, Real time Arrival Data of Kowloon Motor Bus and Long Win Bus Services (Transport Department); data owners The Kowloon Motor Bus Company (1933) Limited and Long Win Bus Company Limited. Accessed $(date -u '+%d %B %Y %H:%M') UTC."
```

Output (re-run on 2026-11-25, 01:02 UTC; the stop list came back HTTP 200, and the outbound answer's first row, `eta_seq` 1, had passed, so rows 2 and 3 are shown). The verifier's run at 00:30 UTC and the author's at 00:18 UTC printed the same stops and probe lines. An earlier version of the script exited when the list was blocked; the verifier's two runs of it at 00:27 and 00:29 UTC both got HTTP 403 on `/stop`, so the fallback was added and tested with the list forced to fail:

```text
robots.txt HTTP 422: {"code":422,"message":"Invalid/Missing parameter(s)."}
robots: paths allowed
outbound -> O | SAU MAU PING (CENTRAL) -> STAR FERRY | 中秀茂坪 -> 尖沙咀碼頭
inbound -> I | STAR FERRY -> SAU MAU PING (CENTRAL) | 尖沙咀碼頭 -> 中秀茂坪
stop list HTTP 200, 1048321 bytes
35 stops outbound; seq is a string here: '1'
  1 A3ADFCDF8487ADB9 SAU MAU PING (CENTRAL) 中秀茂坪 22.318856 114.231353
  5 D95CAEA4D5C491E2 HIU YAN ESTATE 曉茵邨 22.316484 114.231751
  6 41E81A921D79F375 HIU LAI COURT 曉麗苑 22.318714 114.229840
  7 04B6438688E12AC0 CHEUNG WO COURT 祥和苑 22.319803 114.227405
  35 DCFF4041D0C0ACF8 STAR FERRY, HARBOUR CITY 尖沙咀碼頭,海港城 22.293816 114.168797
generated 2026-11-25T09:02:32+08:00 | 3 rows, dirs ['O']
  2 2026-11-25T09:09:26+08:00 | STAR FERRY | 'Scheduled Bus' | 2026-11-25T09:02:16+08:00
  3 2026-11-25T09:18:26+08:00 | STAR FERRY | 'Scheduled Bus' | 2026-11-25T09:02:16+08:00
HTTP/2 200
content-type: application/json; charset=utf-8
access-control-allow-origin: *
cache-control: max-age=300;
x-cache: TCP_HIT
route/1A/O/1: HTTP 422 {"code":422,"message":"Invalid direction."}
route/1a/outbound/1: HTTP 200 {"type":"Route","version":"1.0","generated_timestamp":"2026-11-25T09:02:36+08:00","data":{}}
eta/0000000000000000/1A/1: HTTP 200 {"type":"ETA","version":"1.0","generated_timestamp":"2026-11-25T09:02:38+08:00","data":[]}
Source: DATA.GOV.HK, Real time Arrival Data of Kowloon Motor Bus and Long Win Bus Services (Transport Department); data owners The Kowloon Motor Bus Company (1933) Limited and Long Win Bus Company Limited. Accessed 25 November 2026 01:02 UTC.
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| `/route/{route}/{outbound\|inbound}/{service_type}` -> `data` | `route` (`1A`), `bound` (`O` / `I`), `service_type` (`"1"`), `orig_en`, `orig_tc`, `orig_sc`, `dest_en`, `dest_tc`, `dest_sc` | `data` is `{}` for an unknown route, a lower-case route or a missing service type. The spec's samples also show `co` and `data_timestamp`; the live answers did not have them |
| `/route` (list) | 1,570 rows for 770 route numbers on 2026-11-25; service types `1` (1,281 rows), `2` (183), `3` (75), `4` (19), `5` (6), `6` (3), `9` (2), `7` (1) | 223 route-and-direction pairs have more than one service type. Circular routes (`5D` to `HUNG HOM (CIRCULAR)`) have only `O` |
| `/route-stop/{route}/{bound}/{service_type}` -> `data[]` | `route`, `bound` (`O` / `I`), `service_type`, `seq` (`"1"`, a string), `stop` (16-character id) | no names; join with `/stop` |
| `/stop/{stop_id}` and `/stop` | `stop`, `name_en` (`HIU LAI COURT`), `name_tc` (`曉麗苑`), `name_sc`, `lat`, `long` (strings, WGS84) | 6,744 stops; 1,688 English names are shared by more than one stop (`TUEN MUN ROAD BBI` 25 times), so match on the route's own stop list. The list is 1,048,321 bytes of JSON (193,745 and 193,749 bytes brotli in two downloads; the envelope timestamp changes) |
| `/eta/{stop_id}/{route}/{service_type}` -> `data[]` | `co` (`KMB`), `route`, `dir` (`O` / `I`), `service_type` (a number here), `seq` (a number here), `dest_en`, `eta_seq` (1-3), `eta` (`2026-11-25T08:22:17+08:00` or `null`), `rmk_en`, `rmk_tc`, `rmk_sc`, `data_timestamp` | "up to 3 ETA data may be returned for each direction" (spec). `generated_timestamp` on the envelope is "the initial generated time of the response before it is cached" (data dictionary) |
| `/stop-eta/{stop_id}`, `/route-eta/{route}/{service_type}` | same rows for every route at one stop, or every stop of one route | Hiu Lai Court: 23 rows for 8 routes at 08:01 HKT; route 1A: 189 rows at 08:01 HKT, 154 at 08:16 |
| errors | HTTP 422 `{"code":422,"message":"Invalid direction."}` or `"Invalid/Missing parameter(s)."` | HTTP 403 from the firewall is an HTML page: "Service unavailable The request is blocked." plus a reference id |

## Gotchas

- **Paths say `outbound`/`inbound`, answers say `O`/`I`.** `/route/1A/O/1` is HTTP 422 "Invalid direction.". Use the words in the path and compare `dir` / `bound` with the letters.
- **Case matters and mistakes are silent.** "Please note that URL and parameters in API requests are case-sensitive" (spec). `/route/1a/outbound/1`, a lower-case stop id, an unknown stop id or a stop that route 999 does not serve all answer HTTP 200 with empty `data` (`{}` or `[]`), not an error. Upper-case the route and check for empty data, as the blocks do.
- **`eta` can be `null`.** Seen live on 2026-11-25 08:01-08:20 HKT: night route N293 at Hiu Lai Court (`null`, empty remark; all 85 N293 rows and all 103 N216 rows were `null`), 601P ("The final bus has departed from this stop"), and 1A outbound: `/route-eta/1A/1` at 08:16:05 HKT had `null` with an empty remark for outbound stops 1-15, while block 1 at 08:15:54 and block 3 in the same minute saw `null` and then 08:22 at stop 6. The spec's sample has `null` with "This route only operates on Sundays and Public Holidays". Print the remark when there is no time.
- **Remarks.** Live values were `""` (most rows), "Scheduled Bus" (`原定班次`) and "The final bus has departed from this stop" (`最後班次已過`), each also in Simplified Chinese. The spec's samples show `""`, "Scheduled Bus" and "This route only operates on Sundays and Public Holidays", but neither the spec nor the data dictionary lists the possible values; show them as given.
- **ETAs can already be past.** At 08:01:46 HKT a 13X row said 08:00:42, and at 09:01 HKT the 1A answer for Hiu Lai Court still held a row for 09:00. Blocks 1, 3 and 4 drop rows whose `eta` is before `generated_timestamp` before taking the next N, and blocks 1 and 3 say when fewer than N are left (the answer holds at most 3 per direction).
- **Same bus, several service types.** "the returned ETA information is also included in other service types of the same route number if they share the same bus stop" (spec). `/stop-eta` therefore lists such a bus once per service type, and `/eta/{stop}/13X/1`, `/2` and `/5` each returned the same three times. Drop duplicates on (`eta`, `rmk_en`) and ask one service type.
- **Seq types differ.** `seq` is the string `"6"` in `/route-stop` and the number `6` in `/eta`; `service_type` likewise. Convert before comparing.
- **The list endpoints can be blocked.** `/route`, `/stop` and `/route-stop` (all routes) answered HTTP 403 "The request is blocked." (Azure Front Door) to some calls and HTTP 200 to others, from both the cloud browser and the Linux machine. With curl: 8 `/route` calls 2 s apart with Chrome's User-Agent gave 2 x 200 and 6 x 403, then 4 calls with curl's own User-Agent gave 4 x 403; 4 minutes later `/stop` was HTTP 200 again. Per-route, per-stop and ETA calls were never blocked. Cache the lists for the day; do not retry them in a loop.
- **Stop names are not unique and not tidy.** Some have double spaces (`KOWLOON BAY  STATION`) and the same stop has different names in each direction (outbound `STAR FERRY, HARBOUR CITY` is `DCFF4041D0C0ACF8`, inbound `8D804CFD9C7B9042`). Normalise spaces and case, try the exact name first, then "contains". Block 1 stops at the first exact match in each direction (each name costs a `/stop/{id}` call); block 3 does the same when the list is blocked, but with the cached list it keeps every exact match, so a route that serves the same stop twice in one direction lists both.
- **Hong Kong time.** Times carry `+08:00`; Hong Kong has no daylight saving. `generated_timestamp` is the API's clock; compute "minutes to go" from it rather than from your own clock.
- **Credit and no logo.** Name DATA.GOV.HK as the source, acknowledge that the HKSAR Government and KMB/LWB own the rights in the data, give attribution to the Government, the data owners and DATA.GOV.HK, and use no KMB, LWB or Government logo or wording that suggests endorsement.
- **Tab marker.** The harness sets the tab title to a horse emoji. Blocks 1 and 2 check `location.href` and the page text, not the title.

## What does not work

- **Stop names in `/route-stop`**: there are none; join with `/stop/{id}` or the `/stop` list.
- **A search by stop name on the API**: there is none; match names yourself.
- **Reliable browser downloads of the list endpoints**: see the 403 gotcha.
- **Not tested:** a 429 (never seen; no limit is published), Long Win routes (the data dictionary says `co` "will always be "KMB" which includes bus route services of KMB and LWB"), service types above 1 end to end, `/route-stop` for all routes as a list, Citybus or other operators (other APIs), and an evening or overnight run.
