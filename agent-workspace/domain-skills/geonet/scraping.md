# GeoNet - List the Newest Quakes Possibly Felt in New Zealand at MMI 4+ (Up to 100, Within the Last Year; UTC Time, Magnitude, MMI, Locality, Link) and the Current Volcanic Alert Level for Every Monitored Volcano (REST GeoJSON, no key)

Field-tested against the GeoNet API (api.geonet.org.nz) and www.geonet.org.nz on 2026-11-24 (US Pacific afternoon; 23:31-23:42 UTC on 24 November, which was 12:31-12:42 on Wednesday 25 November in New Zealand, NZDT = UTC+13) using a fresh Browser Use cloud browser (logged out; one session, 23:33-23:38 UTC) plus Python `urllib` and `curl` from a Linux machine. 16 browser page loads (1 smoke test, 7 in each of block 2's two runs, 1 while reading the quake page's text) and 31 in-page `fetch()` calls (1 smoke test, 3 in each of block 1's three runs, 10 and 11 in block 2's two runs), 52 urllib calls (block 3's five commands ran four times, 12 calls each, as the last one is refused before any call, plus one default run of 4 calls) and 43 curl calls (27 while exploring, 8 in each of block 4's two runs), all serial and at least 1 s apart. Every call was HTTP 200 except the deliberate probes: HTTP 400 for `MMI=9`, a missing `MMI`, `Accept: ...;version=1`, an unknown volcano and `/quake/stats` with the geo+json `Accept` header. curl and urllib timed the API at 0.02-0.81 s; block 1 in the browser saw 0.06-0.38 s (polled every 0.2 s). No 429, no challenge, no key, no login, no cookie needed. Two exploring calls were a mistake: one FDSN query on service.geonet.org.nz and one WFS call on wfs.geonet.org.nz, sent in the same command that read those hosts' robots.txt files, which disallow those paths for every agent; their output is not used and no block calls those hosts. Block 1's output below is its third run (23:34:50 UTC; the first two listed the same 94 quakes and levels), block 2's its second (after the quake-page pattern was fixed and the `/quake/stats` probes added), block 3's its fourth (after its first command was shortened to `--days 30`, since block 1 already prints the whole year, and the deleted count was limited to the chosen days; the default run printed the same 94 quakes as block 1), block 4's its second (identical to the first). An independent verifier re-ran all four blocks verbatim at 23:42-23:46 UTC the same day (a separate cloud browser for blocks 1 and 2): the quakes, levels, robots lines, quotes and probes were the same; only the times and timings changed. After a code review on 2026-11-25, blocks 1 and 3 make one `/quake` call instead of stepping up to `MMI=5` and merging (see Gotchas) and mark a full list PARTIAL; block 1 re-ran at 01:00 UTC in a new cloud browser (stopped and confirmed `stopped`) and block 3's five commands at 00:59 UTC, and the outputs shown for them come from those runs.

robots.txt (checked 2026-11-24 UTC with curl, the cloud browser and blocks 3 and 4): https://api.geonet.org.nz/robots.txt is `User-agent: *` / `Disallow: /p/` / `Disallow: /news/` / `Disallow: /assets/` / `Disallow: /network/` with no named agent groups, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider may fetch `/quake?MMI=...`, `/quake/{publicID}`, `/quake/history/{publicID}`, `/quake/stats`, `/volcano/val`, `/volcano/quake/{volcanoID}` and `/intensity`, and may not fetch `/network/...` or `/news/...`, which this skill never calls (block 2 checks all 11 agents with Python's `urllib.robotparser`; block 3 checks the same 11 plus its own User-Agent before every API call and stops if the file ever disallows one). https://www.geonet.org.nz/robots.txt disallows `/p/ /news/ /assets/ /images/ /app /vabs/ /response/ /rss/ /feeds/ /mbl/` for `*`, with no named groups; `/earthquake/{publicID}`, `/volcano`, `/policy` and `/disclaimer` are allowed. Terms: the API page https://api.geonet.org.nz/ says "The GeoNet project makes all its data and images freely available. Please ensure you have read and understood our Data Policy and Disclaimer before using any of these services." and its footer "GeoNet content is copyright Earth Sciences New Zealand and is licensed under a Creative Commons Attribution 3.0 New Zealand License" (link: http://creativecommons.org/licenses/by/3.0/nz/). The data policy https://www.geonet.org.nz/policy: "All data and images are made available free of charge through the GeoNet programme to facilitate research into hazards and assessment of risk." and "Users are requested to acknowledge the GeoNet programme sponsors as the source of the data or images.", with the suggested text "We acknowledge the New Zealand GeoNet programme and its sponsors NHC, Earth Sciences NZ, LINZ, NEMA and MBIE for providing data/images used in this study." The disclaimer https://www.geonet.org.nz/disclaimer covers no warranty ("provided without warranties of any kind") and no liability, and ends "the information on this website is made freely available to the public and may be used subject to these terms." No AI/ML, scraping, crawling, robot, automated-access, non-commercial or rate-limit wording on the API page, the policy or the disclaimer (block 2 checks the quotes and scans for the words). Naming: this skill writes "GeoNet" in plain text, shows no GeoNet or NHC logo (the site shows them as images; the CC licence covers the content), is not affiliated with or endorsed by GeoNet, Earth Sciences New Zealand or NHC, and blocks 1, 3 and 4 (the ones that list quakes and alert levels) end with the CC BY 3.0 NZ credit, the policy's acknowledgement of the sponsors and what it changed.

## Quick summary

- **No scraping needed.** Open JSON (GeoJSON) API, no key, no login. Felt quakes: `GET https://api.geonet.org.nz/quake?MMI=4` with `Accept: application/vnd.geo+json;version=2` -> `features[]`, each with `properties.publicID`, `time` (UTC), `magnitude`, `mmi`, `depth`, `locality`, `quality`; the page for a quake is `https://www.geonet.org.nz/earthquake/{publicID}`. Alert levels: `GET /volcano/val` -> one feature per monitored volcano with `volcanoTitle`, `level`, `acc` (aviation colour code), `activity`, `hazards`. `Access-Control-Allow-Origin: *`, so `fetch()` works from any https page.
- **Answers (25 November 2026, 01:00 UTC):** the API's newest 100 quakes possibly felt at MMI 4+ reach back to 2026-06-10 06:02 UTC, so this is a PARTIAL year: 82 after dropping 18 deleted ones (66 at MMI 4, 11 at 5, 4 at 6, 1 at 7), newest **M4.5 MMI 4, 20 km north-east of Hanmer Springs, 2026-11-21 07:59 UTC** (2026p876575). The strongest shaking: **2026p553250, M5.9, MMI 7, 5 km south of Taumarunui, 2026-07-24 16:51 UTC**; the biggest magnitude: M6.3 (MMI 6) 45 km south-west of Milford Sound on 2026-07-16. **Volcanic Alert Levels:** **White Island 2** (Yellow, "Moderate to heightened volcanic unrest."), **Ruapehu 1** (Green, "Minor volcanic unrest."), the other 10 volcanoes **0**.
- **One call is not a year.** `/quake?MMI=n` returns "up to a maximum of 100 quakes" (API page) and has no date or page parameter. `MMI=4` hit the cap: its oldest quake was 2026-06-10, and 18 of its 100 were `quality: "deleted"`, so MMI 4+ quakes from before 2026-06-10 are not in the answer. Blocks 1 and 3 make one call, drop deleted ones, and mark a full list PARTIAL with the date it reaches back to. A higher `MMI` is a different question (stronger shaking) with its own newest 100: `MMI=5` gave 33, back to 2025-12-03.
- **The filter is shaking, not magnitude.** `MMI=4` means "may have caused shaking greater than or equal to the MMI value in the New Zealand region" (API page). The list ran from M2.6 (MMI 4, within 5 km of Mount Cook, depth 0 km) to M6.3.
- **Rate limits:** none published (the API page, the policy and the disclaimer have no rate-limit wording; block 2 scans for it) and no rate-limit headers. Answers carry `cache-control: max-age=10`. The blocks run serially at 1 call a second; blocks 1 and 3 retry once after 10 s on a 429, a 5xx or a network error, then stop.

## What works

### 1. Quakes possibly felt at MMI 4+ over the last year, and every volcano's alert level (browser)

`on_geonet_tab()` opens the logged-out www.geonet.org.nz volcano page. Its Content-Security-Policy allows `connect-src https://*.geonet.org.nz` and the API answers `Access-Control-Allow-Origin: *`, so in-page `fetch()` works. `call()` returns parsed JSON on HTTP 200, retries once after 10 s on a 429, a 5xx or a network error, and stops on anything else. 2 calls: `MMI=4` (full today, so PARTIAL) and `/volcano/val`. Change `MIN_MMI` for other levels.

```python
import json, time
from datetime import datetime, timedelta, timezone

API = "https://api.geonet.org.nz"
ACCEPT = "application/vnd.geo+json;version=2"   # the version the API docs give for /quake and /volcano/val
PAUSE = 1.0     # serial, 1 call a second (GeoNet publishes no rate limit)
MIN_MMI = 4     # 4..8; /quake?MMI=n returns quakes with MMI >= n

def on_geonet_tab():
    """www.geonet.org.nz pages allow connect-src https://*.geonet.org.nz and the API sends
    Access-Control-Allow-Origin: *, so in-page fetch() works from the logged-out volcano page."""
    try:
        if js("location.origin") == "https://www.geonet.org.nz":
            return
    except Exception:
        pass
    new_tab("https://www.geonet.org.nz/volcano")
    wait_for_load()
    if js("location.origin") != "https://www.geonet.org.nz":
        raise RuntimeError(f"www.geonet.org.nz did not load (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  fetch(%s, {headers: {Accept: %s}, credentials: 'omit', cache: 'no-store'})
    .then(async r => { window.__g[id] = {status: r.status, text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

calls = []
def call(path):
    """GET -> parsed JSON. 5xx, 429 or network error: one retry after 10 s. Anything else that is not 200 stops."""
    url = API + path
    for attempt in range(2):
        rid = json.dumps(js(START_JS % (json.dumps(url), json.dumps(ACCEPT))))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer after 60s")
            time.sleep(0.2)
        calls.append((path, r["status"], round(time.time() - t0, 2)))
        time.sleep(PAUSE)
        if attempt == 0 and r["status"] in (0, 429, 500, 502, 503, 504):
            time.sleep(10)
            continue
        break
    if r["status"] != 200:
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")
    return json.loads(r["text"])

on_geonet_tab()
now = datetime.now(timezone.utc)
print(f"GeoNet API, checked {now:%Y-%m-%d %H:%M} UTC")

# /quake?MMI=n gives at most 100 quakes, newest first, deleted ones included, with no date or page parameter.
# One call. A full list (100) is the newest 100 only, so it is marked PARTIAL with the date it reaches back to.
feats = call(f"/quake?MMI={MIN_MMI}")["features"]
quakes = [f["properties"] for f in feats]
oldest = min((q["time"] for q in quakes), default=None)
year_ago = now - timedelta(days=365)
partial = len(feats) == 100
if partial:
    print(f"  MMI>={MIN_MMI}: 100 quakes = the API's cap. PARTIAL: they reach back only to {oldest[:16]} UTC, not the "
          f"whole 365 days since {year_ago:%Y-%m-%d}; older MMI {MIN_MMI}+ quakes are not in this answer")
else:
    print(f"  MMI>={MIN_MMI}: {len(feats)} quakes (under the cap: the whole 365 days since {year_ago:%Y-%m-%d})")

rows = sorted(quakes, key=lambda q: q["time"], reverse=True)
deleted = [q for q in rows if q["quality"] == "deleted"]
rows = [q for q in rows if q["quality"] != "deleted"]
span = f"since {oldest[:10]} (PARTIAL year)" if partial else "in the last 365 days"
print(f"\n{len(rows)} quakes possibly felt at MMI {MIN_MMI}+ {span} (dropped {len(deleted)} marked quality=deleted), newest first:")
print(f"  {'time (UTC)':<17} {'mag':>4} {'MMI':>3} {'depth':>6}  {'quality':<11} {'locality':<38} link")
for q in rows:
    t = datetime.fromisoformat(q["time"].replace("Z", "+00:00"))
    print(f"  {t:%Y-%m-%d %H:%M} {q['magnitude']:>4.1f} {q['mmi']:>3} {q['depth']:>4.0f}km  {q['quality']:<11} "
          f"{q['locality']:<38} https://www.geonet.org.nz/earthquake/{q['publicID']}")

if rows:   # MMI=8 had no quake this year: an empty list is HTTP 200
    top = max(rows, key=lambda q: (q["mmi"], q["magnitude"]))
    print(f"\nStrongest shaking in this list: {top['publicID']} M{top['magnitude']:.1f} MMI {top['mmi']} {top['locality']} "
          f"({top['time'][:16]} UTC)")
else:
    print(f"\nNo quake at MMI {MIN_MMI}+ in the answer")

val = call("/volcano/val")["features"]
val.sort(key=lambda f: (-f["properties"]["level"], f["properties"]["volcanoTitle"]))
print(f"\nVolcanic Alert Levels, {len(val)} monitored volcanoes (highest first):")
print(f"  {'level':>5}  {'aviation':<8} {'volcano':<28} activity")
for f in val:
    p = f["properties"]
    print(f"  {p['level']:>5}  {p['acc']:<8} {p['volcanoTitle']:<28} {p['activity']} Hazards: {p['hazards']}")

print(f"\n{len(calls)} API calls: " + ", ".join(f"{p} {s} {t}s" for p, s, t in calls))
print("Data: GeoNet (https://www.geonet.org.nz), CC BY 3.0 NZ (https://creativecommons.org/licenses/by/3.0/nz/). "
      "We acknowledge the New Zealand GeoNet programme and its sponsors NHC, Earth Sciences NZ, LINZ, NEMA and MBIE "
      "for providing the data. Changed: deleted quakes dropped, magnitudes rounded, sorted.")
```

Output (re-run on 2026-11-25 after the code-review fixes, 01:00 UTC, in a new cloud browser; the three runs on 2026-11-24 at 23:34 UTC, which also asked `MMI=5` and merged it in, listed the same 82 quakes from 2026-06-10 on, plus 12 older MMI 5+ ones, and the same levels):

```text
GeoNet API, checked 2026-11-25 01:00 UTC
  MMI>=4: 100 quakes = the API's cap. PARTIAL: they reach back only to 2026-06-10T06:02 UTC, not the whole 365 days since 2025-11-25; older MMI 4+ quakes are not in this answer

82 quakes possibly felt at MMI 4+ since 2026-06-10 (PARTIAL year) (dropped 18 marked quality=deleted), newest first:
  time (UTC)         mag MMI  depth  quality     locality                               link
  2026-11-21 07:59  4.5   4    5km  best        20 km north-east of Hanmer Springs     https://www.geonet.org.nz/earthquake/2026p876575
  2026-11-17 10:30  5.4   6    5km  best        15 km south-east of Arthur's Pass      https://www.geonet.org.nz/earthquake/2026p866048
  2026-11-16 12:58  3.6   4    4km  best        10 km north-west of Taupo              https://www.geonet.org.nz/earthquake/2026p863622
  2026-11-14 17:51  4.2   4   20km  best        20 km west of Waipukurau               https://www.geonet.org.nz/earthquake/2026p858767
  2026-11-03 23:10  4.1   4   60km  best        20 km south of St Arnaud               https://www.geonet.org.nz/earthquake/2026p829637
  2026-11-02 23:35  4.2   4   40km  best        25 km north-east of Taihape            https://www.geonet.org.nz/earthquake/2026p826979
  2026-11-01 13:47  3.2   4   21km  best        5 km north of Upper Hutt               https://www.geonet.org.nz/earthquake/2026p823174
  2026-10-26 06:24  4.5   5   31km  best        20 km south-west of Blenheim           https://www.geonet.org.nz/earthquake/2026p806127
  2026-10-26 02:33  4.0   4   12km  best        30 km south of Whanganui               https://www.geonet.org.nz/earthquake/2026p805693
  2026-10-25 22:52  3.2   4   15km  best        15 km south-east of Seddon             https://www.geonet.org.nz/earthquake/2026p805279
  2026-10-25 18:23  3.4   4   27km  best        10 km east of Blenheim                 https://www.geonet.org.nz/earthquake/2026p804773
  2026-10-19 21:34  3.1   4   17km  best        5 km north-west of Masterton           https://www.geonet.org.nz/earthquake/2026p788916
  2026-10-19 17:27  4.0   4   15km  best        15 km east of Pongaroa                 https://www.geonet.org.nz/earthquake/2026p788453
  2026-10-19 08:56  3.6   4   17km  best        20 km east of Pongaroa                 https://www.geonet.org.nz/earthquake/2026p787494
  2026-10-18 22:54  3.7   4   26km  best        5 km south of Napier                   https://www.geonet.org.nz/earthquake/2026p786364
  2026-10-16 05:53  3.6   5    9km  best        5 km west of Hanmer Springs            https://www.geonet.org.nz/earthquake/2026p779041
  2026-10-16 04:00  4.0   5    7km  best        5 km west of Hanmer Springs            https://www.geonet.org.nz/earthquake/2026p778829
  2026-10-15 05:25  5.6   4  267km  best        30 km north-east of Taumarunui         https://www.geonet.org.nz/earthquake/2026p776286
  2026-10-12 06:52  3.8   4   26km  best        10 km east of Eketahuna                https://www.geonet.org.nz/earthquake/2026p768341
  2026-10-11 00:40  4.3   4   38km  best        40 km north-west of Te Araroa          https://www.geonet.org.nz/earthquake/2026p764940
  2026-10-08 13:53  4.1   5    7km  best        10 km south of Taumarunui              https://www.geonet.org.nz/earthquake/2026p758320
  2026-10-06 22:08  3.1   4   17km  best        5 km east of Porangahau                https://www.geonet.org.nz/earthquake/2026p753844
  2026-10-06 22:03  3.2   4   13km  best        5 km east of Porangahau                https://www.geonet.org.nz/earthquake/2026p753834
  2026-10-06 22:02  3.4   4   16km  best        10 km east of Porangahau               https://www.geonet.org.nz/earthquake/2026p753832
  2026-10-02 13:57  5.2   6   14km  best        20 km north of Stratford               https://www.geonet.org.nz/earthquake/2026p742111
  2026-09-27 10:32  4.1   4   32km  best        20 km south-west of Dannevirke         https://www.geonet.org.nz/earthquake/2026p728213
  2026-09-25 16:07  2.9   4   14km  best        5 km south-east of Tokomaru Bay        https://www.geonet.org.nz/earthquake/2026p723438
  2026-09-25 07:30  4.8   4   94km  best        50 km north-west of Te Anau            https://www.geonet.org.nz/earthquake/2026p722468
  2026-09-24 19:46  3.3   4   10km  best        15 km south-east of Seddon             https://www.geonet.org.nz/earthquake/2026p721145
  2026-09-24 09:49  3.9   4   38km  best        5 km south of Hastings                 https://www.geonet.org.nz/earthquake/2026p720025
  2026-09-21 09:23  4.1   5   17km  best        5 km west of Masterton                 https://www.geonet.org.nz/earthquake/2026p711868
  2026-09-11 04:25  3.9   5    7km  best        10 km south of Taumarunui              https://www.geonet.org.nz/earthquake/2026p684281
  2026-09-10 13:09  4.5   4    5km  best        35 km north-east of Milford Sound      https://www.geonet.org.nz/earthquake/2026p682563
  2026-09-05 18:46  4.2   4    8km  best        15 km north of Opunake                 https://www.geonet.org.nz/earthquake/2026p669681
  2026-09-04 18:34  4.9   5   26km  best        30 km north-west of Paraparaumu        https://www.geonet.org.nz/earthquake/2026p666955
  2026-09-04 05:03  4.6   4    5km  best        35 km north-east of Milford Sound      https://www.geonet.org.nz/earthquake/2026p665433
  2026-09-02 07:39  4.6   4    5km  best        40 km north-east of Milford Sound      https://www.geonet.org.nz/earthquake/2026p660321
  2026-09-02 07:12  4.8   4    5km  best        35 km north-east of Milford Sound      https://www.geonet.org.nz/earthquake/2026p660272
  2026-09-02 06:57  5.6   5    5km  best        35 km north-east of Milford Sound      https://www.geonet.org.nz/earthquake/2026p660242
  2026-09-02 06:13  5.3   4    5km  best        40 km north-east of Milford Sound      https://www.geonet.org.nz/earthquake/2026p660160
  2026-08-28 05:08  4.3   4   39km  best        10 km north of Ruatoria                https://www.geonet.org.nz/earthquake/2026p646525
  2026-08-27 12:32  3.1   4   16km  best        5 km south-east of Tokomaru Bay        https://www.geonet.org.nz/earthquake/2026p644655
  2026-08-25 12:26  4.7   4    5km  best        25 km north of Milford Sound           https://www.geonet.org.nz/earthquake/2026p639238
  2026-08-19 04:41  3.1   4   10km  best        10 km south-east of Seddon             https://www.geonet.org.nz/earthquake/2026p622150
  2026-08-17 09:19  3.5   4   10km  best        20 km north-west of Taihape            https://www.geonet.org.nz/earthquake/2026p617265
  2026-08-13 00:31  3.1   4    7km  best        5 km west of Masterton                 https://www.geonet.org.nz/earthquake/2026p605464
  2026-08-11 06:25  4.1   4    5km  best        15 km north-west of Whakatane          https://www.geonet.org.nz/earthquake/2026p600722
  2026-08-10 07:17  4.7   4   12km  best        45 km north of Te Kaha                 https://www.geonet.org.nz/earthquake/2026p598118
  2026-08-08 15:06  4.2   4   43km  best        40 km north of Te Anau                 https://www.geonet.org.nz/earthquake/2026p593592
  2026-08-06 21:17  4.1   5   26km  best        5 km north-west of Tokomaru Bay        https://www.geonet.org.nz/earthquake/2026p588884
  2026-08-02 08:35  5.7   6   39km  best        10 km south-west of Te Araroa          https://www.geonet.org.nz/earthquake/2026p576643
  2026-08-01 03:23  5.2   4  102km  best        35 km north-west of Te Anau            https://www.geonet.org.nz/earthquake/2026p573355
  2026-07-31 11:09  4.6   4   38km  best        30 km west of Porirua                  https://www.geonet.org.nz/earthquake/2026p571526
  2026-07-27 21:24  4.1   4   31km  best        30 km north-east of Napier             https://www.geonet.org.nz/earthquake/2026p561870
  2026-07-27 20:26  4.0   4   46km  best        30 km north-west of Te Anau            https://www.geonet.org.nz/earthquake/2026p561761
  2026-07-24 18:35  2.9   4    9km  best        5 km south of Taumarunui               https://www.geonet.org.nz/earthquake/2026p553444
  2026-07-24 17:21  3.7   4    7km  best        15 km south-west of Taumarunui         https://www.geonet.org.nz/earthquake/2026p553306
  2026-07-24 17:04  3.4   4    7km  best        10 km south of Taumarunui              https://www.geonet.org.nz/earthquake/2026p553275
  2026-07-24 16:51  5.9   7    9km  best        5 km south of Taumarunui               https://www.geonet.org.nz/earthquake/2026p553250
  2026-07-21 18:48  3.0   4   10km  best        Within 5 km of Taihape                 https://www.geonet.org.nz/earthquake/2026p545360
  2026-07-21 11:28  4.5   4   42km  best        45 km north of Te Anau                 https://www.geonet.org.nz/earthquake/2026p544535
  2026-07-19 14:08  4.9   4   49km  best        45 km north of Te Anau                 https://www.geonet.org.nz/earthquake/2026p539429
  2026-07-17 22:04  3.8   4   27km  best        20 km east of Matawai                  https://www.geonet.org.nz/earthquake/2026p534917
  2026-07-17 02:26  4.7   4   42km  best        45 km north of Te Anau                 https://www.geonet.org.nz/earthquake/2026p532707
  2026-07-16 09:31  4.3   4   41km  best        45 km north of Te Anau                 https://www.geonet.org.nz/earthquake/2026p530802
  2026-07-16 09:14  6.3   6   50km  best        45 km south-west of Milford Sound      https://www.geonet.org.nz/earthquake/2026p530771
  2026-07-15 12:16  3.4   4   16km  best        5 km south-west of Porangahau          https://www.geonet.org.nz/earthquake/2026p528408
  2026-07-15 11:55  3.8   4   18km  best        30 km south-east of Martinborough      https://www.geonet.org.nz/earthquake/2026p528370
  2026-07-12 16:31  4.7   5   24km  best        25 km south-west of Kaikoura           https://www.geonet.org.nz/earthquake/2026p520779
  2026-07-12 13:04  3.8   4   22km  best        5 km south of Napier                   https://www.geonet.org.nz/earthquake/2026p520391
  2026-07-08 06:56  4.1   5    8km  best        10 km north-west of Pongaroa           https://www.geonet.org.nz/earthquake/2026p508890
  2026-07-07 20:33  5.4   4  104km  best        70 km north of Te Kaha                 https://www.geonet.org.nz/earthquake/2026p507720
  2026-07-06 16:31  3.8   4   40km  best        5 km north-east of Picton              https://www.geonet.org.nz/earthquake/2026p504563
  2026-06-29 11:21  2.9   4    4km  best        Within 5 km of Arthur's Pass           https://www.geonet.org.nz/earthquake/2026p485063
  2026-06-28 11:04  4.7   4   54km  best        65 km west of Levin                    https://www.geonet.org.nz/earthquake/2026p482327
  2026-06-23 14:53  2.6   4    0km  best        Within 5 km of Mount Cook              https://www.geonet.org.nz/earthquake/2026p469245
  2026-06-20 16:06  4.1   4   24km  best        40 km north-east of Te Kaha            https://www.geonet.org.nz/earthquake/2026p461272
  2026-06-18 12:12  3.0   4   15km  best        5 km south-west of Porangahau          https://www.geonet.org.nz/earthquake/2026p455428
  2026-06-17 11:41  3.8   4   19km  best        20 km east of Castlepoint              https://www.geonet.org.nz/earthquake/2026p452668
  2026-06-16 14:33  4.0   4   46km  best        30 km west of Porirua                  https://www.geonet.org.nz/earthquake/2026p450287
  2026-06-16 11:42  3.7   4   16km  best        20 km north-east of Pongaroa           https://www.geonet.org.nz/earthquake/2026p449966
  2026-06-12 01:54  4.4   4   45km  best        25 km north-west of Blenheim           https://www.geonet.org.nz/earthquake/2026p438052

Strongest shaking in this list: 2026p553250 M5.9 MMI 7 5 km south of Taumarunui (2026-07-24T16:51 UTC)

Volcanic Alert Levels, 12 monitored volcanoes (highest first):
  level  aviation volcano                      activity
      2  Yellow   White Island                 Moderate to heightened volcanic unrest. Hazards: Volcanic unrest hazards, potential for eruption hazards.
      1  Green    Ruapehu                      Minor volcanic unrest. Hazards: Volcanic unrest hazards.
      0  Green    Auckland Volcanic Field      No volcanic unrest. Hazards: Volcanic environment hazards.
      0  Green    Mayor Island                 No volcanic unrest. Hazards: Volcanic environment hazards.
      0  Green    Ngauruhoe                    No volcanic unrest. Hazards: Volcanic environment hazards.
      0  Green    Northland                    No volcanic unrest. Hazards: Volcanic environment hazards.
      0  Green    Okataina                     No volcanic unrest. Hazards: Volcanic environment hazards.
      0  Green    Rangitāhua/Kermadec Islands  No volcanic unrest. Hazards: Volcanic environment hazards.
      0  Green    Rotorua                      No volcanic unrest. Hazards: Volcanic environment hazards.
      0  Green    Taranaki Maunga              No volcanic unrest. Hazards: Volcanic environment hazards.
      0  Green    Taupo                        No volcanic unrest. Hazards: Volcanic environment hazards.
      0  Green    Tongariro                    No volcanic unrest. Hazards: Volcanic environment hazards.

2 API calls: /quake?MMI=4 200 1.3s, /volcano/val 200 0.33s
Data: GeoNet (https://www.geonet.org.nz), CC BY 3.0 NZ (https://creativecommons.org/licenses/by/3.0/nz/). We acknowledge the New Zealand GeoNet programme and its sponsors NHC, Earth Sciences NZ, LINZ, NEMA and MBIE for providing the data. Changed: deleted quakes dropped, magnitudes rounded, sorted.
```

### 2. robots.txt, the terms quotes, the web pages against the API, and what the API does with mistakes (browser)

7 page loads and 11 in-page `fetch()` calls in the same tab. robots.txt is read as page text and checked with `urllib.robotparser` for all 11 agents on the used paths and the two disallowed ones. Then it reads the quake's own page and the volcano page and compares them with the API.

```python
import json, re, time, urllib.robotparser

API = "https://api.geonet.org.nz"
ACCEPT = "application/vnd.geo+json;version=2"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]

START_JS = """(() => { window.__g = window.__g || {}; const id = String(Math.random()).slice(2); window.__g[id] = null;
  const a = %s;
  fetch(a.url, {headers: a.headers, credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__g[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__g[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__g[%s]; if (v) delete window.__g[%s]; return v; })()"""

def raw(url, accept=ACCEPT):
    """One in-page GET -> {status, headers, text}. No retries: this block only inspects answers."""
    h = {"Accept": accept} if accept else {}
    rid = json.dumps(js(START_JS % json.dumps({"url": url, "headers": h})))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 60:
            raise RuntimeError(f"{url}: no answer after 60s")
        time.sleep(0.2)
    time.sleep(1.0)
    return r

def page(url, wait_for=None):
    """Load a page and return (HTTP status, content type, final URL, flattened text); waits up to 15 s for a phrase."""
    goto_url(url)
    wait_for_load()
    t0 = time.time()
    while True:
        txt = " ".join((js("(document.body || document.documentElement).innerText || ''") or "").split())
        if not wait_for or wait_for in txt or time.time() - t0 > 15:
            break
        time.sleep(0.5)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.contentType"), js("location.href"), txt

# 1) robots.txt on both hosts, checked for every agent on the paths the skill uses and the ones it must not
for host, used, avoid in (
    ("api.geonet.org.nz", ["/quake?MMI=4", "/quake/2026p866048", "/quake/history/2026p866048", "/volcano/val",
                           "/volcano/quake/ruapehu", "/intensity?type=measured", "/"], ["/network/sensors", "/news/geonet"]),
    ("www.geonet.org.nz", ["/earthquake/2026p866048", "/volcano", "/policy", "/disclaimer"], []),
):
    goto_url(f"https://{host}/robots.txt")
    wait_for_load()
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    txt = js("document.body.innerText") or ""
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(txt.splitlines())
    named = [l for l in txt.splitlines() if l.lower().startswith("user-agent") and l.split(":", 1)[1].strip() != "*"]
    bad = [(a, p) for a in AGENTS for p in used if not rp.can_fetch(a, f"https://{host}{p}")]
    print(f"{host}/robots.txt HTTP {st}: {' / '.join(l.strip() for l in txt.splitlines() if l.strip())!r}")
    print(f"  named agent groups: {named or 'none'}; used paths disallowed for the {len(AGENTS)} agents: {bad or 'none'}")
    for p in avoid:
        no = [a for a in AGENTS if not rp.can_fetch(a, f"https://{host}{p}")]
        print(f"  {p}: disallowed for {len(no)} of {len(AGENTS)} agents (the skill does not call it)")

# 2) the API page, the data policy and the disclaimer, as a reader sees them
for url, needles in (
    ("https://api.geonet.org.nz/", [
        "The GeoNet project makes all its data and images freely available.",
        "Please ensure you have read and understood our Data Policy and Disclaimer before using any of these services.",
        "API queries may be versioned via the Accept header.",
        "If you don't specify an Accept header with a version then your request will be routed to the current highest API version of the query.",
        "Returns quakes possibly felt in the New Zealand region during the last 365 days up to a maximum of 100 quakes.",
        "GeoNet content is copyright Earth Sciences New Zealand and is licensed under a Creative Commons Attribution 3.0 New Zealand License"]),
    ("https://www.geonet.org.nz/policy", [
        "All data and images are made available free of charge through the GeoNet programme to facilitate research into hazards and assessment of risk.",
        "Users are requested to acknowledge the GeoNet programme sponsors as the source of the data or images.",
        "We acknowledge the New Zealand GeoNet programme and its sponsors NHC, Earth Sciences NZ, LINZ, NEMA and MBIE for providing data/images used in this study."]),
    ("https://www.geonet.org.nz/disclaimer", [
        "Use of this website and the information on it will be deemed to be acceptance of these terms.",
        "provided without warranties of any kind",
        "the information on this website is made freely available to the public and may be used subject to these terms."]),
):
    st, ct, href, txt = page(url, wait_for=needles[0][:40])
    short = href.split("//")[1][:30]
    print(f"\n{short} HTTP {st}")
    for n in needles:
        print(f"  {'found' if n in txt else 'MISSING'}: {n[:96]!r}")
    lic = js("[...document.querySelectorAll('a[href*=\"creativecommons\"]')].map(a => a.href)")
    words = [w for w in ("scrap", "crawl", "artificial intelligence", "machine learning", "non-commercial",
                         "noncommercial", "rate limit", "robot", "automated") if w in txt.lower()]
    print(f"  licence links: {sorted(set(lic)) or 'none'}; words scrap/crawl/AI/ML/non-commercial/rate limit/robot/automated: {words or 'none'}")

# 3) the quake's own web page against the API record (www.geonet.org.nz/earthquake/{publicID})
q = json.loads(raw(f"{API}/quake/2026p866048")["text"])["features"][0]["properties"]
st, ct, href, txt = page("https://www.geonet.org.nz/earthquake/2026p866048", wait_for="Search Magnitude")
m = re.search(r"Magnitude (\d+\.\d) (\w+ \w+ \d+, \d{4} - [\d:]+ [AP]M), (.+?) Shaking (\w+) Depth (\d+) km Quality (\w+) ", txt)
print(f"\nAPI  /quake/2026p866048: M{q['magnitude']:.1f} MMI {q['mmi']} {q['time']} {q['locality']!r} depth {q['depth']} quality {q['quality']}")
print(f"page {href.split('//')[1]} HTTP {st}: " + (f"M{m.group(1)} at {m.group(2)} (NZ time), {m.group(3)!r}, shaking {m.group(4)!r}, "
      f"depth {m.group(5)} km, quality {m.group(6)!r}" if m else f"pattern not found; text starts {txt[:120]!r}"))

# 4) the volcano page against /volcano/val: same levels, some names differ
val = [f["properties"] for f in json.loads(raw(f"{API}/volcano/val")["text"])["features"]]
st, ct, href, txt = page("https://www.geonet.org.nz/volcano", wait_for="Monitored volcanoes")
n_page = len(re.findall(r"\d Alert level ", txt))
print(f"\n{href.split('//')[1]} HTTP {st}: {n_page} volcanoes listed; /volcano/val has {len(val)}")
same = 0
for p in val:
    if f"{p['level']} Alert level {p['volcanoTitle']} " in txt:
        same += 1
        continue
    alt = re.search(rf"{p['level']} Alert level (\S*{re.escape(p['volcanoTitle'])}.*?) (?:Cone|Caldera|Vent)\b", txt)
    print(f"  {p['volcanoID']:<22} API {p['volcanoTitle']!r} level {p['level']}; page: "
          + (f"{alt.group(1)!r} level {p['level']}" if alt else "not found with this level"))
print(f"  the other {same} show the same name and level on the page")

# 5) what the API does with mistakes and defaults
def brief(r, n=100):
    return f"HTTP {r['status']} {r['headers'].get('content-type', '?')}: {' '.join(r['text'].split())[:n]}"
print()
for label, url, acc in (
    ("MMI=9 (allowed -1..8)          ", f"{API}/quake?MMI=9", ACCEPT),
    ("no MMI                         ", f"{API}/quake", ACCEPT),
    ("MMI=8 (none this year)         ", f"{API}/quake?MMI=8", ACCEPT),
    ("unknown publicID 2099p000000   ", f"{API}/quake/2099p000000", ACCEPT),
    ("/quake/stats, geo+json Accept  ", f"{API}/quake/stats", ACCEPT),
    ("/quake/stats, its own Accept   ", f"{API}/quake/stats", "application/json;version=2"),
    ("Accept version=1               ", f"{API}/quake?MMI=4", "application/vnd.geo+json;version=1"),
    ("unknown volcano                ", f"{API}/volcano/quake/notavolcano", ACCEPT),
):
    print(f"{label} {brief(raw(url, acc))}")
r = raw(f"{API}/quake?MMI=4", None)
d = json.loads(r["text"])["features"]
print(f"no Accept header               HTTP {r['status']} {r['headers'].get('content-type')}: {len(d)} quakes, "
      f"{sum(f['properties']['quality'] == 'deleted' for f in d)} of them quality=deleted")
print(f"headers visible to fetch(): {sorted(r['headers'])}")
```

Output (second run, 2026-11-24 23:36:38 UTC; the first run, before the quake-page pattern was fixed and with one `/quake/stats` probe instead of two, printed the same robots, terms, volcano and error lines):

```text
api.geonet.org.nz/robots.txt HTTP 200: 'User-agent: * / Disallow: /p/ / Disallow: /news/ / Disallow: /assets/ / Disallow: /network/'
  named agent groups: none; used paths disallowed for the 11 agents: none
  /network/sensors: disallowed for 11 of 11 agents (the skill does not call it)
  /news/geonet: disallowed for 11 of 11 agents (the skill does not call it)
www.geonet.org.nz/robots.txt HTTP 200: 'User-agent: * / Disallow: /p/ / Disallow: /news/ / Disallow: /assets/ / Disallow: /images/ / Disallow: /app / Disallow: /news/ / Disallow: /vabs/ / Disallow: /response/ / Disallow: /rss/ / Disallow: /feeds/ / Disallow: /mbl/ / Sitemap: https://www.geonet.org.nz/sitemap.xml'
  named agent groups: none; used paths disallowed for the 11 agents: none

api.geonet.org.nz/ HTTP 200
  found: 'The GeoNet project makes all its data and images freely available.'
  found: 'Please ensure you have read and understood our Data Policy and Disclaimer before using any of th'
  found: 'API queries may be versioned via the Accept header.'
  found: "If you don't specify an Accept header with a version then your request will be routed to the cur"
  found: 'Returns quakes possibly felt in the New Zealand region during the last 365 days up to a maximum '
  found: 'GeoNet content is copyright Earth Sciences New Zealand and is licensed under a Creative Commons '
  licence links: ['http://creativecommons.org/licenses/by/3.0/nz/']; words scrap/crawl/AI/ML/non-commercial/rate limit/robot/automated: none

www.geonet.org.nz/policy HTTP 200
  found: 'All data and images are made available free of charge through the GeoNet programme to facilitate'
  found: 'Users are requested to acknowledge the GeoNet programme sponsors as the source of the data or im'
  found: 'We acknowledge the New Zealand GeoNet programme and its sponsors NHC, Earth Sciences NZ, LINZ, N'
  licence links: ['https://creativecommons.org/licenses/by/3.0/nz/']; words scrap/crawl/AI/ML/non-commercial/rate limit/robot/automated: none

www.geonet.org.nz/disclaimer HTTP 200
  found: 'Use of this website and the information on it will be deemed to be acceptance of these terms.'
  found: 'provided without warranties of any kind'
  found: 'the information on this website is made freely available to the public and may be used subject t'
  licence links: ['https://creativecommons.org/licenses/by/3.0/nz/']; words scrap/crawl/AI/ML/non-commercial/rate limit/robot/automated: none

API  /quake/2026p866048: M5.4 MMI 6 2026-11-17T10:30:48.727Z "15 km south-east of Arthur's Pass" depth 5 quality best
page www.geonet.org.nz/earthquake/2026p866048 HTTP 200: M5.4 at Tuesday November 17, 2026 - 11:30 PM (NZ time), "15 km south-east of Arthur's Pass", shaking 'Strong', depth 5 km, quality 'Best'

www.geonet.org.nz/volcano HTTP 200: 12 volcanoes listed; /volcano/val has 12
  whiteisland            API 'White Island' level 2; page: 'Whakaari/White Island' level 2
  the other 11 show the same name and level on the page

MMI=9 (allowed -1..8)           HTTP 400 text/plain; charset=utf-8: bad request: invalid MMI: 9
no MMI                          HTTP 400 text/plain; charset=utf-8: bad request: missing required query parameter: MMI
MMI=8 (none this year)          HTTP 200 application/vnd.geo+json;version=2: {"type":"FeatureCollection","features":[]}
unknown publicID 2099p000000    HTTP 200 application/vnd.geo+json;version=2: {"type":"FeatureCollection","features":[]}
/quake/stats, geo+json Accept   HTTP 400 text/plain; charset=utf-8: bad request: invalid publicID: stats
/quake/stats, its own Accept    HTTP 200 application/json;version=2: {"magnitudeCount":{"days365":{ "6" : 2, "5" : 79, "2" : 8257, "3" : 1858, "0" : 1233, "-1" : 20, "1"
Accept version=1                HTTP 400 text/plain; charset=utf-8: bad request: missing required query parameters: regionID, regionIntensity, number, quality
unknown volcano                 HTTP 400 text/plain; charset=utf-8: bad request: invalid volcanoID notavolcano
no Accept header               HTTP 200 application/vnd.geo+json;version=2: 100 quakes, 18 of them quality=deleted
headers visible to fetch(): ['cache-control', 'content-length', 'content-type']
```

### 3. The same with Python urllib, as a command-line tool: robots check for every agent, felt quakes, alert levels, one quake's history (no browser)

Standard library only. It runs with `python3 -I`. Save it as `geonet.py`. A list run makes 1 robots.txt call, 1 `/quake?MMI=n` call (marked PARTIAL when it returns the full 100 and the oldest is newer than `--days` allows), and 1 `/volcano/val` call. `--quake` reads `/quake/{publicID}` and `/quake/history/{publicID}`. urllib does not ask for gzip, so the answers come uncompressed (27.6 KB for `MMI=4`).

```python
"""Quakes possibly felt in New Zealand at a given MMI and up, and the current Volcanic Alert Levels
(GeoNet API, Python standard library only).

  python3 geonet.py                 # MMI 4+ over the last 365 days, plus every volcano's alert level
  python3 geonet.py --mmi 6         # stronger shaking only
  python3 geonet.py --quake 2026p866048   # one quake and how its magnitude was revised
"""
import argparse, json, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timedelta, timezone

HOST = "https://api.geonet.org.nz"
ACCEPT = "application/vnd.geo+json;version=2"
UA = "geonet-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider", "geonet-skill-example"]  # last = this script's UA
CREDIT = ("Data: GeoNet (https://www.geonet.org.nz), CC BY 3.0 NZ (https://creativecommons.org/licenses/by/3.0/nz/). "
          "We acknowledge the New Zealand GeoNet programme and its sponsors NHC, Earth Sciences NZ, LINZ, NEMA and MBIE "
          "for providing the data.")
calls = []
_last = [0.0]
RP = None   # parsed robots.txt; call() checks every request URL against it

def http(url, accept=ACCEPT):
    """-> (status, text). Serial, at least 1 s apart."""
    time.sleep(max(0.0, _last[0] + 1.0 - time.time()))
    req = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": UA})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status, body = r.status, r.read()
    except urllib.error.HTTPError as e:
        status, body = e.code, e.read()
    except (urllib.error.URLError, TimeoutError) as e:
        status, body = 0, str(e).encode()
    _last[0] = time.time()
    calls.append((url[len(HOST):], status, round(time.time() - t0, 2), len(body)))
    return status, body.decode("utf-8", errors="replace")

def robots_load():
    """api.geonet.org.nz/robots.txt disallows /p/ /news/ /assets/ /network/ for '*' today. A 4xx other than 429 =
    no rules; 429, 5xx or no answer = rules unknown, so stop."""
    global RP
    s, text = http(HOST + "/robots.txt", "text/plain")
    if 400 <= s < 500 and s != 429:
        print(f"robots.txt api.geonet.org.nz: HTTP {s}, no rules")
        return
    if s != 200:
        sys.exit(f"robots.txt: HTTP {s}; rules unknown, try later")
    RP = urllib.robotparser.RobotFileParser()
    RP.parse(text.splitlines())
    print(f"robots.txt api.geonet.org.nz: HTTP 200; each API URL is checked for all {len(AGENTS)} agents before its call")

def call(path):
    """-> parsed JSON. Checks robots.txt first. 429, 5xx or network error: one retry after 10 s.
    HTTP 400 is GeoNet's plain-text 'bad request: ...'; it and any other non-200 stop."""
    url = HOST + path
    bad = [a for a in AGENTS if RP and not RP.can_fetch(a, url)]
    if bad:
        sys.exit(f"robots.txt disallows {path} for {bad}: stop")
    for attempt in range(2):
        s, text = http(url)
        if attempt == 0 and s in (0, 429, 500, 502, 503, 504):
            time.sleep(10)
            continue
        break
    if s != 200:
        sys.exit(f"{url}: HTTP {s} {' '.join(text.split())[:200]!r}")
    return json.loads(text)

def utc(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))

def link(pid):
    return f"https://www.geonet.org.nz/earthquake/{pid}"

ap = argparse.ArgumentParser()
ap.add_argument("--mmi", type=int, default=4, help="lowest MMI to list, -1..8 (default 4)")
ap.add_argument("--days", type=int, default=365, help="only quakes from the last N days (the API keeps 365)")
ap.add_argument("--quake", help="one publicID instead of the lists, e.g. 2026p866048")
ap.add_argument("--no-volcanoes", action="store_true")
args = ap.parse_args()
if not -1 <= args.mmi <= 8:
    ap.error("--mmi must be -1..8 (the API answers HTTP 400 'invalid MMI' otherwise)")
if not 1 <= args.days <= 365:
    ap.error("--days must be 1..365")

now = datetime.now(timezone.utc)
print(f"GeoNet API, checked {now:%Y-%m-%d %H:%M} UTC")
robots_load()

if args.quake:
    feats = call(f"/quake/{args.quake}")["features"]
    if not feats:                                # an unknown publicID is HTTP 200 with no features
        sys.exit(f"no quake {args.quake!r} (HTTP 200, empty FeatureCollection)")
    q = feats[0]["properties"]
    lon, lat = feats[0]["geometry"]["coordinates"]
    print(f"{q['publicID']}: {q['time']} M{q['magnitude']:.2f} MMI {q['mmi']} depth {q['depth']:.1f} km "
          f"{q['locality']} ({lat:.3f}, {lon:.3f}) quality {q['quality']}\n  {link(q['publicID'])}")
    hist = sorted((f["properties"] for f in call(f"/quake/history/{args.quake}")["features"]),
                  key=lambda p: p["modificationTime"])
    if hist:
        mags = [p["magnitude"] for p in hist]
        print(f"  history: {len(hist)} versions from {hist[0]['modificationTime'][:19]} to {hist[-1]['modificationTime'][:19]} UTC; "
              f"magnitude {mags[0]:.2f} first, {min(mags):.2f}-{max(mags):.2f} range, {mags[-1]:.2f} last; "
              f"qualities {sorted({p['quality'] for p in hist})}")
    else:
        print("  history: none (not all quakes have a location history)")
else:
    feats = call(f"/quake?MMI={args.mmi}")["features"]   # at most 100, newest first; no date or page parameter
    quakes = [f["properties"] for f in feats]
    oldest = min((q["time"] for q in quakes), default=None)
    since = now - timedelta(days=args.days)
    inside = [q for q in quakes if utc(q["time"]) >= since]
    rows = sorted((q for q in inside if q["quality"] != "deleted"), key=lambda q: q["time"], reverse=True)
    n_del = len(inside) - len(rows)
    partial = len(feats) == 100 and utc(oldest) > since
    print(f"MMI {args.mmi}+ since {since:%Y-%m-%d %H:%M} UTC: {len(rows)} quakes ({n_del} quality=deleted dropped)"
          + ("  PARTIAL" if partial else ""))
    print(f"  /quake?MMI={args.mmi}: {len(feats)} returned, oldest {oldest[:16] if oldest else '-'}"
          + ("  <- 100 cap" if len(feats) == 100 else ""))
    if partial:
        print(f"  PARTIAL: the 100 cap ends at {oldest[:16]} UTC; MMI {args.mmi}+ quakes from before then are not in "
              f"this answer (a --days that ends after that date gives a complete list)")
    print(f"  {'time (UTC)':<16}  {'mag':>4} {'MMI':>3}  {'locality':<38} link")
    for q in rows:
        print(f"  {utc(q['time']):%Y-%m-%d %H:%M}  {q['magnitude']:>4.1f} {q['mmi']:>3}  {q['locality']:<38} {link(q['publicID'])}")

    if not args.no_volcanoes:
        val = sorted((f["properties"] for f in call("/volcano/val")["features"]),
                     key=lambda p: (-p["level"], p["volcanoTitle"]))
        print(f"Volcanic Alert Level, {len(val)} volcanoes: " +
              "; ".join(f"{p['volcanoTitle']} {p['level']} ({p['acc']})" for p in val))

print(f"{len(calls)} calls: " + ", ".join(f"{p} {s} {t}s {z / 1024:.1f} KB" for p, s, t, z in calls))
print(CREDIT + (" Changed: fields picked, magnitudes rounded." if args.quake else
                " Changed: list filtered, magnitudes rounded, sorted by this script."))
```

Output (five commands, re-run on 2026-11-25 after the code-review fixes, 00:59 UTC; the 23:41 UTC run on 2026-11-24 listed the same quakes and levels with one more call, `/quake?MMI=5`, in the `--days 30` run; the default run, 365 days, now prints 82 quakes and PARTIAL):

```text
$ python3 -I geonet.py --days 30
GeoNet API, checked 2026-11-25 00:59 UTC
robots.txt api.geonet.org.nz: HTTP 200; each API URL is checked for all 12 agents before its call
MMI 4+ since 2026-10-26 00:59 UTC: 9 quakes (1 quality=deleted dropped)
  /quake?MMI=4: 100 returned, oldest 2026-06-10T06:02  <- 100 cap
  time (UTC)         mag MMI  locality                               link
  2026-11-21 07:59   4.5   4  20 km north-east of Hanmer Springs     https://www.geonet.org.nz/earthquake/2026p876575
  2026-11-17 10:30   5.4   6  15 km south-east of Arthur's Pass      https://www.geonet.org.nz/earthquake/2026p866048
  2026-11-16 12:58   3.6   4  10 km north-west of Taupo              https://www.geonet.org.nz/earthquake/2026p863622
  2026-11-14 17:51   4.2   4  20 km west of Waipukurau               https://www.geonet.org.nz/earthquake/2026p858767
  2026-11-03 23:10   4.1   4  20 km south of St Arnaud               https://www.geonet.org.nz/earthquake/2026p829637
  2026-11-02 23:35   4.2   4  25 km north-east of Taihape            https://www.geonet.org.nz/earthquake/2026p826979
  2026-11-01 13:47   3.2   4  5 km north of Upper Hutt               https://www.geonet.org.nz/earthquake/2026p823174
  2026-10-26 06:24   4.5   5  20 km south-west of Blenheim           https://www.geonet.org.nz/earthquake/2026p806127
  2026-10-26 02:33   4.0   4  30 km south of Whanganui               https://www.geonet.org.nz/earthquake/2026p805693
Volcanic Alert Level, 12 volcanoes: White Island 2 (Yellow); Ruapehu 1 (Green); Auckland Volcanic Field 0 (Green); Mayor Island 0 (Green); Ngauruhoe 0 (Green); Northland 0 (Green); Okataina 0 (Green); Rangitāhua/Kermadec Islands 0 (Green); Rotorua 0 (Green); Taranaki Maunga 0 (Green); Taupo 0 (Green); Tongariro 0 (Green)
3 calls: /robots.txt 200 0.21s 0.1 KB, /quake?MMI=4 200 0.37s 27.6 KB, /volcano/val 200 0.16s 3.0 KB
Data: GeoNet (https://www.geonet.org.nz), CC BY 3.0 NZ (https://creativecommons.org/licenses/by/3.0/nz/). We acknowledge the New Zealand GeoNet programme and its sponsors NHC, Earth Sciences NZ, LINZ, NEMA and MBIE for providing the data. Changed: list filtered, magnitudes rounded, sorted by this script.

$ python3 -I geonet.py --mmi 6 --days 180
GeoNet API, checked 2026-11-25 01:00 UTC
robots.txt api.geonet.org.nz: HTTP 200; each API URL is checked for all 12 agents before its call
MMI 6+ since 2026-05-29 01:00 UTC: 6 quakes (0 quality=deleted dropped)
  /quake?MMI=6: 8 returned, oldest 2025-12-25T18:16
  time (UTC)         mag MMI  locality                               link
  2026-11-17 10:30   5.4   6  15 km south-east of Arthur's Pass      https://www.geonet.org.nz/earthquake/2026p866048
  2026-10-02 13:57   5.2   6  20 km north of Stratford               https://www.geonet.org.nz/earthquake/2026p742111
  2026-08-02 08:35   5.7   6  10 km south-west of Te Araroa          https://www.geonet.org.nz/earthquake/2026p576643
  2026-07-24 16:51   5.9   7  5 km south of Taumarunui               https://www.geonet.org.nz/earthquake/2026p553250
  2026-07-16 09:14   6.3   6  45 km south-west of Milford Sound      https://www.geonet.org.nz/earthquake/2026p530771
  2026-05-29 22:56   4.7   6  10 km east of Seddon                   https://www.geonet.org.nz/earthquake/2026p402583
Volcanic Alert Level, 12 volcanoes: White Island 2 (Yellow); Ruapehu 1 (Green); Auckland Volcanic Field 0 (Green); Mayor Island 0 (Green); Ngauruhoe 0 (Green); Northland 0 (Green); Okataina 0 (Green); Rangitāhua/Kermadec Islands 0 (Green); Rotorua 0 (Green); Taranaki Maunga 0 (Green); Taupo 0 (Green); Tongariro 0 (Green)
3 calls: /robots.txt 200 0.22s 0.1 KB, /quake?MMI=6 200 0.23s 2.3 KB, /volcano/val 200 0.24s 3.0 KB
Data: GeoNet (https://www.geonet.org.nz), CC BY 3.0 NZ (https://creativecommons.org/licenses/by/3.0/nz/). We acknowledge the New Zealand GeoNet programme and its sponsors NHC, Earth Sciences NZ, LINZ, NEMA and MBIE for providing the data. Changed: list filtered, magnitudes rounded, sorted by this script.

$ python3 -I geonet.py --quake 2026p866048
GeoNet API, checked 2026-11-25 01:00 UTC
robots.txt api.geonet.org.nz: HTTP 200; each API URL is checked for all 12 agents before its call
2026p866048: 2026-11-17T10:30:48.727Z M5.44 MMI 6 depth 5.0 km 15 km south-east of Arthur's Pass (-43.015, 171.776) quality best
  https://www.geonet.org.nz/earthquake/2026p866048
  history: 114 versions from 2026-11-17T10:31:44 to 2026-11-18T10:47:42 UTC; magnitude 5.12 first, 5.12-5.66 range, 5.44 last; qualities ['automatic', 'best']
3 calls: /robots.txt 200 0.11s 0.1 KB, /quake/2026p866048 200 0.18s 0.3 KB, /quake/history/2026p866048 200 0.19s 38.2 KB
Data: GeoNet (https://www.geonet.org.nz), CC BY 3.0 NZ (https://creativecommons.org/licenses/by/3.0/nz/). We acknowledge the New Zealand GeoNet programme and its sponsors NHC, Earth Sciences NZ, LINZ, NEMA and MBIE for providing the data. Changed: fields picked, magnitudes rounded.

$ python3 -I geonet.py --quake 2099p000000
GeoNet API, checked 2026-11-25 01:00 UTC
robots.txt api.geonet.org.nz: HTTP 200; each API URL is checked for all 12 agents before its call
no quake '2099p000000' (HTTP 200, empty FeatureCollection)

$ python3 -I geonet.py --mmi 9
usage: geonet.py [-h] [--mmi MMI] [--days DAYS] [--quake QUAKE]
                 [--no-volcanoes]
geonet.py: error: --mmi must be -1..8 (the API answers HTTP 400 'invalid MMI' otherwise)
```

### 4. curl: robots, felt quakes, alert levels, headers, `/quake/stats`, mistakes

```bash
#!/usr/bin/env bash
# GeoNet API with curl: robots check, MMI 4+ quakes, volcano alert levels, headers, mistakes.
set -euo pipefail
A='Accept: application/vnd.geo+json;version=2'
C=(curl -sS --max-time 30 --compressed -H "$A")
G=https://api.geonet.org.nz
T=$(mktemp)
# 0. robots.txt first: a 4xx other than 429 = no rules; stop if it disallows the paths below
code=$(curl -sS --max-time 30 -o "$T" -w '%{http_code}' $G/robots.txt)
echo "robots.txt HTTP $code: $(tr '\n' ' ' < "$T")"
python3 -c 'import sys, urllib.robotparser
code, text = int(sys.argv[1]), open(sys.argv[2]).read()
if code != 200 and not (400 <= code < 500 and code != 429): sys.exit("robots.txt rules unknown: stop")
rp = urllib.robotparser.RobotFileParser(); rp.parse(text.splitlines() if code == 200 else [])
paths = ("/quake?MMI=4", "/volcano/val", "/quake/stats")
if not all(rp.can_fetch(a, "https://api.geonet.org.nz" + p) for a in ("*", "curl") for p in paths): sys.exit("robots.txt disallows a path: stop")
print("robots: paths allowed; /network/sensors allowed:", rp.can_fetch("*", "https://api.geonet.org.nz/network/sensors"))' "$code" "$T"
sleep 1
# 1. quakes possibly felt at MMI 4+ (newest 100 at most, deleted ones included): the 8 newest that are not deleted
"${C[@]}" --fail "$G/quake?MMI=4" | python3 -c 'import json, sys
f = [x["properties"] for x in json.load(sys.stdin)["features"]]
ok = [p for p in f if p["quality"] != "deleted"]
print(len(f), "returned,", len(f) - len(ok), "deleted, oldest", min(p["time"] for p in f))
for p in ok[:8]:
    print(p["time"][:16].replace("T", " "), "M%.1f" % p["magnitude"], "MMI", p["mmi"], "|", p["locality"], "| https://www.geonet.org.nz/earthquake/" + p["publicID"])'
sleep 1
# 2. Volcanic Alert Level for every monitored volcano, highest first
"${C[@]}" --fail "$G/volcano/val" | python3 -c 'import json, sys
for p in sorted((x["properties"] for x in json.load(sys.stdin)["features"]), key=lambda p: -p["level"]):
    print("level", p["level"], p["acc"], "|", p["volcanoTitle"], "|", p["activity"])'
sleep 1
# 3. response headers: 10 s public cache, CORS open, no rate-limit headers
"${C[@]}" -D - -o /dev/null "$G/volcano/val" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|content-encoding|cache-control|access-control-allow-origin|vary|retry-after|x-ratelimit[a-z-]*|ratelimit[a-z-]*):)'
sleep 1
# 4. /quake/stats wants its own Accept header; with the geo+json one it is read as a publicID
curl -sS --max-time 30 -o "$T" -w 'stats, geo+json Accept: HTTP %{http_code} ' -H "$A" "$G/quake/stats"; cat "$T"; echo; sleep 1
curl -sS --max-time 30 --compressed -H 'Accept: application/json;version=2' "$G/quake/stats" | python3 -c 'import json, sys
d = json.load(sys.stdin)["magnitudeCount"]
print("stats, json Accept: quakes by magnitude, last 365 days:", {k: d["days365"][k] for k in sorted(d["days365"], key=int)})'
sleep 1
# 5. mistakes: MMI out of range is HTTP 400 plain text; an unknown publicID is HTTP 200 with no features
for q in "quake?MMI=9" "quake/2099p000000"; do
  "${C[@]}" -o "$T" -w "$q: HTTP %{http_code} " "$G/$q"; head -c 100 "$T"; echo; sleep 1
done
rm -f "$T"
echo "Data: GeoNet (https://www.geonet.org.nz), CC BY 3.0 NZ (https://creativecommons.org/licenses/by/3.0/nz/). We acknowledge the New Zealand GeoNet programme and its sponsors NHC, Earth Sciences NZ, LINZ, NEMA and MBIE for providing the data. Accessed $(date -u '+%d %B %Y %H:%M') UTC. Changed: fields picked, magnitudes rounded."
```

Output (second run, 2026-11-24 23:38:46 UTC; identical to the 23:38:23 UTC run):

```text
robots.txt HTTP 200: User-agent: * Disallow: /p/ Disallow: /news/ Disallow: /assets/ Disallow: /network/
robots: paths allowed; /network/sensors allowed: False
100 returned, 18 deleted, oldest 2026-06-10T06:02:12.739Z
2026-11-21 07:59 M4.5 MMI 4 | 20 km north-east of Hanmer Springs | https://www.geonet.org.nz/earthquake/2026p876575
2026-11-17 10:30 M5.4 MMI 6 | 15 km south-east of Arthur's Pass | https://www.geonet.org.nz/earthquake/2026p866048
2026-11-16 12:58 M3.6 MMI 4 | 10 km north-west of Taupo | https://www.geonet.org.nz/earthquake/2026p863622
2026-11-14 17:51 M4.2 MMI 4 | 20 km west of Waipukurau | https://www.geonet.org.nz/earthquake/2026p858767
2026-11-03 23:10 M4.1 MMI 4 | 20 km south of St Arnaud | https://www.geonet.org.nz/earthquake/2026p829637
2026-11-02 23:35 M4.2 MMI 4 | 25 km north-east of Taihape | https://www.geonet.org.nz/earthquake/2026p826979
2026-11-01 13:47 M3.2 MMI 4 | 5 km north of Upper Hutt | https://www.geonet.org.nz/earthquake/2026p823174
2026-10-26 06:24 M4.5 MMI 5 | 20 km south-west of Blenheim | https://www.geonet.org.nz/earthquake/2026p806127
level 2 Yellow | White Island | Moderate to heightened volcanic unrest.
level 1 Green | Ruapehu | Minor volcanic unrest.
level 0 Green | Taupo | No volcanic unrest.
level 0 Green | Tongariro | No volcanic unrest.
level 0 Green | Auckland Volcanic Field | No volcanic unrest.
level 0 Green | Mayor Island | No volcanic unrest.
level 0 Green | Ngauruhoe | No volcanic unrest.
level 0 Green | Northland | No volcanic unrest.
level 0 Green | Okataina | No volcanic unrest.
level 0 Green | Rotorua | No volcanic unrest.
level 0 Green | Taranaki Maunga | No volcanic unrest.
level 0 Green | Rangitāhua/Kermadec Islands | No volcanic unrest.
HTTP/2 200
content-type: application/vnd.geo+json;version=2
access-control-allow-origin: *
cache-control: max-age=10
content-encoding: gzip
vary: Accept, Accept-Encoding
stats, geo+json Accept: HTTP 400 bad request: invalid publicID: stats
stats, json Accept: quakes by magnitude, last 365 days: {'-1': 20, '0': 1233, '1': 10178, '2': 8257, '3': 1858, '4': 582, '5': 79, '6': 2}
quake?MMI=9: HTTP 400 bad request: invalid MMI: 9
quake/2099p000000: HTTP 200 {"type":"FeatureCollection","features":[]}
Data: GeoNet (https://www.geonet.org.nz), CC BY 3.0 NZ (https://creativecommons.org/licenses/by/3.0/nz/). We acknowledge the New Zealand GeoNet programme and its sponsors NHC, Earth Sciences NZ, LINZ, NEMA and MBIE for providing the data. Accessed 24 November 2026 23:38 UTC. Changed: fields picked, magnitudes rounded.
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| `/quake?MMI=n` `features[].properties` | `publicID` (`2026p866048`), `time` (`2026-11-17T10:30:48.727Z`), `depth` (km), `magnitude` (`5.444425927675574`), `mmi` (`6`), `locality` (`15 km south-east of Arthur's Pass`), `quality` (`best`, `preliminary`, `automatic`, `deleted`) | `n` is -1..8; -1 "is used for quakes that are to small to calculate a stable MMI value for" (API page, spelling as there). Newest first, at most 100. `geometry.coordinates` is `[longitude, latitude]` |
| `/quake/{publicID}` | one feature, same properties | unknown ID: HTTP 200 with `"features":[]` |
| `/quake/history/{publicID}` | one feature per revision, plus `modificationTime` | 114 revisions for 2026p866048 (111 `automatic`, 3 `best`): magnitude 5.12 first, 5.12-5.66 range, 5.44 last. "Not all quakes have a location history" (API page) |
| `/volcano/val` `features[].properties` | `volcanoID` (`whiteisland`), `volcanoTitle` (`White Island`), `level` (0-5), `acc` (`Green`, `Yellow`, ...), `activity`, `hazards` | 12 volcanoes on 2026-11-24. The volcano page: "The NZ Volcanic Alert Level system is based on 6 levels" |
| `/volcano/quake/{volcanoID}` | quakes near one volcano in the past 60 days, adds `intensity`, `regionIntensity`, `status` | 67 for `ruapehu` on 2026-11-24 (explored with curl, not used by the blocks) |
| `/quake/stats` | `magnitudeCount.days7/days28/days365` (counts keyed by whole magnitude), `rate.perDay` | needs `Accept: application/json;version=2`. 365 days: 22,209 quakes, 582 in the `4` bucket, 79 in `5`, 2 in `6` |
| `/intensity?type=measured` | GeoJSON points with `mmi` for the last 60 minutes | 327 points at 23:31 UTC (explored with curl, not used by the blocks) |
| response headers | `content-type: application/vnd.geo+json;version=2`, `cache-control: max-age=10`, `access-control-allow-origin: *`, `vary: Accept, Accept-Encoding`, gzip when asked | no rate-limit headers. A browser `fetch()` sees `cache-control`, `content-length`, `content-type` |
| errors | HTTP 400 `text/plain`: `bad request: invalid MMI: 9`, `bad request: missing required query parameter: MMI`, `bad request: invalid volcanoID notavolcano` | not JSON |

## Gotchas

- **100 quakes at most, no dates.** `/quake?MMI=4` returned exactly 100, back only to 2026-06-10 06:02 UTC. Report such a list as partial and say where it ends (blocks 1 and 3 do); do not split or repeat queries to get past the cap. The other GeoNet hosts that take dates cannot fill the gap within robots.txt: service.geonet.org.nz (FDSN) and quakesearch.geonet.org.nz have `Disallow: /`, and wfs.geonet.org.nz disallows `/geonet/ows`.
- **Deleted quakes take slots.** 18 of the 100 `MMI=4` features had `quality: "deleted"` (5 of 33 for `MMI=5`). Drop them; they still count toward the 100.
- **`mmi` is lower case.** The API page writes `MMI` for `/quake/{publicID}` and `/quake/history`, but every answer on 2026-11-24 had `mmi`.
- **Round the magnitude.** `magnitude` has up to 16 digits (`5.444425927675574`); the quake's web page shows `5.4`. The web page shows NZ local time (`Tuesday November 17, 2026 - 11:30 PM` for `2026-11-17T10:30:48.727Z`, NZDT = UTC+13) and the word `Strong` for MMI 6.
- **Numbers change after the first report.** 2026p866048 has 114 revisions in `/quake/history`; 111 of them said "20 km south-east of Arthur's Pass", the magnitude moved between 5.12 and 5.66, and the current version says "15 km south-east" and 5.44. The list endpoint gives the current version.
- **The `Accept` header picks the version.** Without one, "your request will be routed to the current highest API version" (API page); it was version 2 today. `version=1` on `/quake` is HTTP 400 `missing required query parameters: regionID, regionIntensity, number, quality`. `/quake/stats` is HTTP 400 `invalid publicID: stats` with the geo+json header and HTTP 200 with its own `application/json;version=2`.
- **Unknown IDs are not errors.** `/quake/2099p000000` is HTTP 200 with an empty `features` list; `MMI=8` was the same (no MMI 8 quake in the year). Bad parameters are HTTP 400 plain text, not JSON.
- **One name differs from the website.** The API's `White Island` is `Whakaari/White Island` on https://www.geonet.org.nz/volcano; the other 11 names are the same, and the levels matched for all 12 (block 2). The page puts a type tag (`Cone`, `Caldera`, `Vent`, `Volcanic Field`) after each name, so its text reads `Northland Volcanic Field` although the name is `Northland`.
- **Stay off `/network/` and `/news/`.** Both are in the API docs and both are disallowed for every agent in api.geonet.org.nz/robots.txt. Block 3 refuses any path robots.txt disallows.
- **Caching.** `cache-control: max-age=10`; polling more often than every 10 s returns the same answer.
- **Credit and no logo.** Credit GeoNet with the CC BY 3.0 NZ link and the policy's sponsor acknowledgement, say what you changed, use no GeoNet or NHC logo, and do not suggest GeoNet endorses your app.
- **Tab marker.** The harness sets the tab title to a horse emoji. The blocks check `location.origin` and the page text, not the title.

## What does not work

- **A date range or more than 100 quakes from `/quake`**: there is no parameter for either.
- **FDSN, WFS and quake search hosts**: robots.txt disallows them (see Gotchas); this skill does not use them.
- **`/quake/stats` with the geo+json `Accept` header**: HTTP 400; use `application/json;version=2`.
- **Not tested:** a 429 (never provoked; no limit is published), `/intensity?type=reported`, `/intensity/strong/processed/{publicID}`, the CAP feed, `preliminary` and `automatic` quakes in the list (all 82 were `best` today), and a day with a volcano at level 3 or higher.
