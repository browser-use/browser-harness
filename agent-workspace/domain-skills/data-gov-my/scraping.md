# data.gov.my via api.data.gov.my - Get This Week's Malaysian Pump Prices (RON95, BUDI 95, SKPS, RON97, Diesel) with the Week-on-Week Change, the MET Malaysia Weather Warnings in Force Now and a 7-Day Forecast for a Town (JSON API, no key)

Field-tested against api.data.gov.my, data.gov.my, developer.data.gov.my and storage.data.gov.my on 2026-11-25 (US Pacific afternoon; 2026-11-25 23:38 UTC to 2026-11-26 00:15 UTC, which was 07:38-08:15 on Thursday 26 November in Malaysia) using fresh Browser Use cloud browsers (logged out; one session 23:49-00:05 UTC for blocks 1 and 2, a new one 00:13-00:15 UTC for block 1's last run; both stopped and confirmed `stopped` afterwards) plus Python `urllib` and `curl` from a Linux machine. 27 browser page loads (block 1 opened the fuel price dataset page in its first and fourth runs; block 2 made 12 loads in each of its two runs; one load checked the FAQ markup; one more navigation timed out on the daemon side, and block 2 now retries a navigation once) and 48 in-page `fetch()` calls (block 1: 6 per run, four runs; block 2: 12 per run, two runs), 15 urllib calls (1 while exploring; block 3 ran twice: 3 robots.txt files, 3 API calls and the CSV each) and 100 curl calls (52 while exploring; 16 in each of block 4's three runs). 114 of all these calls went to api.data.gov.my, spaced at least 16 s apart per API except one deliberate burst: 6 calls to `/opendosm/` within 24 s, whose 5th and 6th got HTTP 429 (see Limits). Every other API call was HTTP 200 except the deliberate HTTP 301, 400 and 404 probes. No 403, no challenge, no key, no login. Of the timed API calls most took 0.6-4.9 s, but four took 9.7-17.3 s (the first warnings call 17.3 s, the 4th call of the burst 16.8 s); the blocks allow 60-90 s. Each block ran at least twice; the outputs shown come from the last run of each block, and the earlier runs differed only as noted under each output. An independent re-run of all four blocks, unchanged, in a separate cloud browser and from the same Linux machine (2026-11-26 00:17-00:27 UTC) printed the same data apart from the clock, call timings and cookie expiry. Later on 2026-11-26 block 4 got a `trap ... EXIT` that removes its two temporary files even when the script stops early; that version re-ran from the same Linux machine at 01:01-01:04 UTC with the same output apart from the clock, timings and cookie expiry. After review on 2026-11-26, block 1 URL-encodes the town name and prints one forecast per town id when a name matches several, block 3's docstring names the retried statuses, and block 4 adds `--retry-max-time 120`; block 1 re-ran in a new cloud browser (01:21:34-01:22:43 UTC, stopped and confirmed `stopped`), blocks 3 and 4 from the Linux machine at 01:15-01:19 UTC, with the same output apart from the clock, timings and cookie expiry. After review of the website sync on 2026-11-26, block 4 retries 16 s after a failed call (`--retry-delay 16`; 10 s could put a fifth call to one API inside a minute) and writes answers it discards to a temporary file instead of `/dev/null` (curl 8.5 cannot truncate `/dev/null` for a retry and exits 23); it re-ran from the same Linux machine at 02:47-02:50 UTC with the same output apart from the clock, the cookie expiry and the validity window of one MET Malaysia warning (10:00-14:00 by then).

robots.txt (checked 2026-11-25 23:39 UTC to 2026-11-26 00:15 UTC, curl, the cloud browser and `urllib.robotparser`): https://api.data.gov.my/robots.txt is HTTP 404 (an HTML "Not Found" page) and https://storage.data.gov.my/robots.txt is HTTP 404 (XML), so neither host has rules or named AI-agent groups; RFC 9309 section 2.3.1.3 says that for 400-499 answers "the crawler MAY access any resources on the server". https://data.gov.my/robots.txt and https://developer.data.gov.my/robots.txt are each `User-agent: *` / `Allow: /` plus `Host` and `Sitemap` lines, nothing else. No file names an AI agent, so GPTBot, ChatGPT-User, OAI-SearchBot, ClaudeBot, Claude-User, anthropic-ai, Google-Extended, PerplexityBot, CCBot and Bytespider fall under `*`, and every path this skill uses is allowed for all 11 agents (block 3). Terms: there is no terms-of-use page. https://data.gov.my/terms-of-use, `/terms`, `/disclaimer` and `/privacy-policy` are HTTP 404 (block 2), https://developer.data.gov.my/terms is HTTP 404, and neither sitemap (54 URLs on data.gov.my, 24 on developer.data.gov.my) lists a terms, privacy or disclaimer page; the data.gov.my footer links the source code repositories, the design file, "Open Data Guiding Principles" (a document on dasar.jdn.gov.my), FAQ, OpenDOSM and KKMNOW, and none of them is a terms page. The licence statements: the developer FAQ answers "Can I really use all the data here for free?" with "This data is made open under the Creative Commons Attribution 4.0 International License (CC BY 4.0). You can use the data available on our platform for free", the developer docs footer says "License: CC BY 4.0", the Weather API page says "All weather feeds are licensed under CC BY 4.0", and the fuel price dataset page says "This data is made open under the Creative Commons Attribution 4.0 International License (CC BY 4.0)". CC BY 4.0 allows commercial use and asks for credit. The only usage rule published is the rate limit (https://developer.data.gov.my/rate-limit): "Data Catalogue 4 requests per minute", the same for OpenDOSM, Weather, GTFS Static and GTFS Realtime, and "If the limit is exceeded, subsequent requests will fail and you will receive a 429 Too Many Requests error". No AI/ML, scraping, automated-access or non-commercial-only clause on any page read (block 2 found none of the words scrap, artificial intelligence, machine learning, non-commercial, robot or crawl on the rate-limit or dataset pages). Naming: no trademark statement was found. This skill calls the site "data.gov.my (Malaysia's official open data portal)" (the developer docs' own title is "Malaysia's Official Open API"), credits the source agency each dataset names (the fuel dataset page: "Data source(s) Ministry of Finance"; the Weather API page: "The data is provided by MET Malaysia (Malaysian Meteorological Department)"), uses no coat of arms or logo, and is not endorsed by data.gov.my, the Ministry of Finance or MET Malaysia. Slug `data-gov-my`, following `data-gov-sg`.

**Not for safety decisions.** Weather warnings change by the hour: between block 1's 07:50 and 07:55 MYT runs the 03:00-08:00 thunderstorm warning for Selangor, Putrajaya, Negeri Sembilan, Melaka and Johor left the feed, before it ran out, and an 08:00-12:00 one for four Johor districts took its place. The Weather API page points to MET Malaysia's official portal "For more comprehensive weather-related information"; use MET Malaysia's own channels for anything that matters.

## Quick summary

- **No scraping.** Three GET endpoints, no key: `GET https://api.data.gov.my/data-catalogue/?id=fuelprice&sort=-date&limit=4` (the newest two dates, each as a `series_type` `"level"` row and a `"change_weekly"` row; prices in RM per litre), `GET /weather/warning/` (the warnings in the feed now, a handful of rows) and `GET /weather/forecast/?ifilter=Kuala%20Lumpur@location__location_name&contains=Tn@location__location_id&sort=date` (7 days for one town). Write the trailing slash: without it `/data-catalogue?id=...` answered HTTP 301 to the slashed URL (blocks 2 and 4). Filters are `<value>@<column>`, nested columns use a double underscore. `Access-Control-Allow-Origin: *`, so `fetch()` works from any page.
- **Answer (block 1, 2026-11-26 08:13 MYT):** pump prices in effect from **Thursday 26 November 2026**, RM per litre (Ministry of Finance): **RON95 3.47** (general market, **-0.25** on 19 November's 3.72), **RON95 under BUDI 95 1.99** (+0.00), RON95 under SKPS 2.05 (+0.00), **RON97 3.75** (-0.25 from 4.00), **diesel 4.47** in Peninsular Malaysia and 4.47 in East Malaysia (both -0.25 from 4.72). Over eight weeks RON95 fell from 4.67 (8 October) to 3.47 (block 3). **MET Malaysia warnings in force (4 of 5 rows):** a first-category strong winds and rough seas warning (23-28 November) and a second one for 05:00-10:00, a thunderstorms warning for Johor (Kluang, Mersing, Kota Tinggi, Kulai) 08:00-12:00, and a continuous rain alert for Kelantan and Terengganu until 27 November 23:59; the fifth row is "No Advisory" (no tropical cyclone). **Kuala Lumpur (town Tn079), 7 days:** 24-32/33 C; thunderstorms Thursday afternoon and night and Friday, no rain Saturday, morning rain Sunday to Wednesday.
- **"Week-on-week" is the API's own `change_weekly` row.** It is the difference to the previous price set; block 1 checks that it equals the difference of the two `level` rows and prints how many days apart they are (7 here). Prices take effect on Thursdays; 5 level rows since March 2021 fall on other days, the newest three (2024-06-10, 2025-09-30, 2026-07-01) on the dates of the subsidy changes the dataset page's caveats list (block 3). The coming Thursday's row can exist before that Thursday: the CSV already held the 2026-11-26 row at its `Last-Modified` of 25 November 10:31 UTC (18:31 MYT), so block 1 compares `date` with today in Malaysia and prints "ANNOUNCED, not yet in effect" for a future date.
- **Weather values are Malay only** ("the above field values are currently only available in Bahasa Melayu"). Block 1 translates them with the Weather API page's 13-value table and marks anything else with `*`; the 440 locations' rows for 26 November also used 6 values the table lacks, such as `Ribut petir di kebanyakan tempat` and `Hujan menyeluruh` (see Gotchas).
- **Limits: 4 requests per minute for each API** (Data Catalogue, Weather, OpenDOSM...). A burst of 6 `/opendosm/` calls got HTTP 429 on the 5th, 20 s after the first: `{"detail":"Request was throttled. Expected available in 37 seconds."}` with `Retry-After: 37`. Block 1 made 1 Data Catalogue and 4 Weather calls inside 60 s with no 429, which fits per-API counting. No rate-limit headers on a 200. Every block spaces calls to the same API 16 s apart and waits once on 429 (Retry-After or the body's "available in N seconds"; over 120 s it stops), HTTP 500, 502, 503, 504 or a network error (10 s), then stops; block 2 only inspects answers and never retries; block 4's curl `--retry 1 --retry-delay 16` retries once, 16 s later (curl's man page says it "complies with the Retry-After: response header", which wins when sent), and `--retry-max-time 120` drops that retry when Retry-After asks for longer. Blocks 1 and 3 also keep the 16 s spacing on a retry: the 10 s wait counts from the failed call, and the spacing then adds the rest.

## What works

### 1. This week's pump prices and change, the warnings in force, a 7-day forecast for towns (browser)

`on_dgm_tab()` opens the logged-out fuel price dataset page on data.gov.my (the page the credit line names); the API is CORS-open, so `fetch()` from there needs no credentials. `get()` returns parsed JSON on HTTP 200, spaces calls to the same API 16 s apart, waits once on 429, 500, 502, 503, 504 or a network error and otherwise raises with the API's `status_code` and `details`. 6 calls (1 Data Catalogue, 5 Weather; about 70 s). A town is matched by exact name in any case (URL-encoded, so `&`, `#` or non-ASCII text stays in the value); a name that matches several town ids gets one forecast per id; a near miss costs one more Weather call and prints the closest MET Malaysia town names instead of guessing.

```python
import difflib, json, re, time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

# Towns as a person types them: any case. A near miss prints the closest MET Malaysia town names instead of guessing.
TOWNS = ["Kuala Lumpur", "kota kinabalu", "Johor Baru"]

SITE = "https://data.gov.my"
API = "https://api.data.gov.my"     # every path needs the trailing slash (/weather/warning/); without it: HTTP 301
GAP = 16.0                          # "4 requests per minute" for each API (developer.data.gov.my/rate-limit): 16 s apart per API
MYT = timezone(timedelta(hours=8))  # API times have no zone; they are Malaysia time (UTC+8)
UTC = timezone.utc

# English for the forecast values, copied from the Weather API page's table (the API answers in Malay only).
EN = {"berjerebu": "Hazy", "tiada hujan": "No rain", "hujan": "Rain", "hujan di beberapa tempat": "Scattered rain",
      "hujan di satu dua tempat": "Isolated rain", "hujan di satu dua tempat di kawasan pantai": "Isolated rain over coastal areas",
      "hujan di satu dua tempat di kawasan pedalaman": "Isolated rain over inland areas", "ribut petir": "Thunderstorms",
      "ribut petir di beberapa tempat": "Scattered thunderstorms",
      "ribut petir di beberapa tempat di kawasan pedalaman": "Scattered thunderstorms over inland areas",
      "ribut petir di satu dua tempat": "Isolated thunderstorms",
      "ribut petir di satu dua tempat di kawasan pantai": "Isolated thunderstorms over coastal areas",
      "ribut petir di satu dua tempat di kawasan pedalaman": "Isolated thunderstorms over inland areas"}
WHEN = {"pagi": "morning", "malam": "night", "petang": "afternoon", "pagi dan petang": "morning and afternoon",
        "pagi dan malam": "morning and night", "petang dan malam": "afternoon and night", "sepanjang hari": "throughout the day"}

def on_dgm_tab():
    """The logged-out fuel price dataset page on data.gov.my (the page the credit line links to). The API sends
    Access-Control-Allow-Origin: *, so fetch() from here needs no credentials."""
    try:
        if js("location.href").startswith(SITE + "/data-catalogue/fuelprice"):
            return
    except Exception:
        pass
    new_tab(SITE + "/data-catalogue/fuelprice")
    wait_for_load()
    if not js("location.href").startswith(SITE) or "Price of Petroleum" not in (js("document.body ? document.body.innerText : ''") or ""):
        raise RuntimeError(f"data.gov.my did not serve the fuel price page (at {js('location.href')}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, {credentials: 'omit', cache: 'no-store'})
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

last, calls = {}, []
def fetch(url):
    """One in-page GET, at least GAP s after the previous call to the same API (data-catalogue, weather, opendosm...)."""
    bucket = url.split("/")[3]
    wait = last.get(bucket, 0) + GAP - time.time()
    if wait > 0:
        time.sleep(wait)
    last[bucket] = time.time()
    rid = json.dumps(js(START_JS % json.dumps(url)))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{url}: no answer after 90s")
        time.sleep(0.2)
    calls.append((bucket, r["status"], round(time.time() - t0, 1)))
    return r

def get(path, **params):
    """GET API + path (trailing slash included) -> parsed JSON. Waits once on 429 (the body says "Expected available in
    N seconds"; a cross-origin fetch() cannot read Retry-After), 500, 502, 503, 504 or a network error (10 s); over 120 s it stops.
    Raises on anything else with the API's status_code and details."""
    q = "&".join(f"{k}={v}" for k, v in params.items())   # values below are already URL-safe; @ and , may stay raw
    url = f"{API}{path}?{q}"
    for attempt in range(2):
        r = fetch(url)
        if r["status"] in (0, 429, 500, 502, 503, 504) and attempt == 0:
            m = re.search(r"available in (\d+) seconds", r["text"])
            wait = int(m[1]) + 1 if m else 10
            if wait > 120:
                raise RuntimeError(f"{url}: server asks to wait {wait} s: stopping")
            time.sleep(wait)
            continue
        break
    if r["status"] != 200 or "json" not in r["headers"].get("content-type", ""):
        raise RuntimeError(f"{url}: HTTP {r['status']} {' '.join(r['text'].split())[:160]!r}; stopping")
    return json.loads(r["text"])

def myt(s):
    return datetime.fromisoformat(s).replace(tzinfo=MYT) if s else None

starred = []
def en(v):
    """Malay forecast value -> English from the docs' table (case-insensitive: the API sends "Tiada Hujan", the table
    "Tiada hujan"); values the table lacks keep their Malay text and a *."""
    if (v or "").lower() in EN:
        return EN[v.lower()]
    starred.append(v)
    return f"{v}*"

on_dgm_tab()
now = datetime.now(UTC)
print(f"data.gov.my (Malaysia's official open data portal), checked {now:%Y-%m-%d %H:%M} UTC = {now.astimezone(MYT):%Y-%m-%d %H:%M} MYT")

# 1. Pump prices: the newest 4 rows sorted by date, newest first = the latest two weeks, each as a "level" and a "change_weekly" row
fuel = get("/data-catalogue/", id="fuelprice", sort="-date", limit=4, meta="true")
meta, rows = fuel["meta"], fuel["data"]
lv = sorted((r for r in rows if r["series_type"] == "level"), key=lambda r: r["date"], reverse=True)
ch = [r for r in rows if r["series_type"] == "change_weekly" and r["date"] == lv[0]["date"]]
if len(lv) != 2 or len(ch) != 1:
    raise RuntimeError(f"expected 2 level rows and this week's change_weekly row, got {[(r['date'], r['series_type']) for r in rows]}: stop")
cur, prev, chg = lv[0], lv[1], ch[0]
d_cur, d_prev = datetime.fromisoformat(cur["date"]), datetime.fromisoformat(prev["date"])
# The coming Thursday's row can be there the evening before (the CSV with the 2026-11-26 row was modified 18:31 MYT on the 25th)
state = "in effect from" if d_cur.date() <= now.astimezone(MYT).date() else "ANNOUNCED, not yet in effect; from"
print(f"\nPump prices {state} {d_cur:%A %d %B %Y}, RM per litre (Ministry of Finance; catalogue {meta['catalogue_id']}, "
      f"data as of {meta['data_as_of']}, next update {meta['next_update']} MYT)")
print(f"  previous price set: {d_prev:%A %d %B %Y} ({(d_cur - d_prev).days} days earlier)")
# Names as the dataset page words them: RON95 "for the general market", BUDI 95 for eligible individuals (up to 300 litres
# a month), SKPS (Subsidised Petrol Control System) for eligible commercial vehicles.
LABELS = [("ron95", "RON95, general market"), ("ron95_budi95", "RON95, BUDI 95 subsidy"), ("ron95_skps", "RON95, SKPS subsidy"),
          ("ron97", "RON97"), ("diesel", "Diesel, Peninsular"), ("diesel_eastmsia", "Diesel, East Malaysia")]
bad = []
for k, name in LABELS:
    a, b, c = cur[k], prev[k], chg[k]
    diff = None if a is None or b is None else round(a - b, 2)
    if c is not None and diff is not None and round(c, 2) != diff:
        bad.append(k)
    print(f"  {name:<27} {a:>5.2f}  {round(c, 2):+.2f} on {d_prev:%d %b} ({b:.2f})")
print(f"  check: change_weekly {'equals' if not bad else 'DIFFERS from'} the difference of the two level rows"
      f"{'' if not bad else ' for ' + str(bad)} (rounded to the sen; the raw values carry float noise, e.g. {chg['ron95']!r})")
extra = {k: cur[k] for k in cur if k not in dict(LABELS) and k not in ("date", "series_type")}
print(f"  also in the answer, not defined on the dataset page: {extra}")

# 2. MET Malaysia warnings: the whole current list (a handful of rows), active = valid_from <= now <= valid_to in MYT
warn = get("/weather/warning/")
nowm = now.astimezone(MYT)
active = [w for w in warn if w["valid_from"] and myt(w["valid_from"]) <= nowm <= myt(w["valid_to"])]
other = [w for w in warn if w not in active]
print(f"\nMET Malaysia warnings: {len(warn)} in the feed, {len(active)} active at {nowm:%d %b %H:%M} MYT")
for w in sorted(active, key=lambda w: w["valid_to"]):
    print(f"  ACTIVE {w['warning_issue']['title_en']}: {w['heading_en']}, issued {w['warning_issue']['issued'][5:16].replace('T', ' ')}, "
          f"valid {w['valid_from'][5:16].replace('T', ' ')} to {w['valid_to'][5:16].replace('T', ' ')} MYT")
    print(f"         {w['text_en'][:230]}{'...' if len(w['text_en']) > 230 else ''}")
for w in other:
    if not w["valid_from"]:
        state, span = "no validity period", ""
    else:
        state = "starts later" if myt(w["valid_from"]) > nowm else "expired"
        span = f", valid {w['valid_from'][5:16].replace('T', ' ')} to {w['valid_to'][5:16].replace('T', ' ')} MYT"
    print(f"  {state}: {w['warning_issue']['title_en']}{span}: {w['text_en'][:110]}")

# 3. 7-day forecast for each town: exact name, any case (ifilter), Town ids only (Tn...), sorted by date
def forecast(town):
    rows = get("/weather/forecast/", ifilter=quote(town, safe="") + "@location__location_name",
               contains="Tn@location__location_id", sort="date")
    if rows:
        return rows
    names = sorted({r["location"]["location_name"] for r in get("/weather/forecast/", contains="Tn@location__location_id",
                                                                 date_start=f"{nowm:%Y-%m-%d}@date", date_end=f"{nowm:%Y-%m-%d}@date")})
    near = difflib.get_close_matches(town.title(), names, n=3, cutoff=0.6)
    print(f"\n{town!r}: no MET Malaysia town of that name ({len(names)} towns); closest: {near}")
    return []

for town in TOWNS:
    by_id = {}
    for r in forecast(town):
        by_id.setdefault(r["location"]["location_id"], []).append(r)
    if len(by_id) > 1:
        print(f"\n{town!r} names {len(by_id)} MET Malaysia towns {sorted(by_id)}: one forecast each")
    for lid, rows in by_id.items():
        loc = rows[0]["location"]
        print(f"\n7-day forecast, {loc['location_name']} ({lid}), MET Malaysia:"
              + ("" if len(rows) == 7 else f" {len(rows)} days, not 7"))
        for r in rows:
            print(f"  {datetime.fromisoformat(r['date']):%a %d %b}  {r['min_temp']}-{r['max_temp']} C  {en(r['summary_forecast'])}"
                  f" ({WHEN.get((r['summary_when'] or '').lower(), r['summary_when'])}); morning {en(r['morning_forecast'])}, "
                  f"afternoon {en(r['afternoon_forecast'])}, night {en(r['night_forecast'])}")
        hits = [w["warning_issue"]["title_en"] for w in active if loc["location_name"].lower() in (w["text_en"] or "").lower()]
        print(f"  active warnings naming {loc['location_name']}: {hits or 'none'}")

if starred:
    print(f"\n* not in the Weather API page's value table, Malay kept as sent: {sorted(set(starred))}")
print(f"{len(calls)} API calls {[(b, s) for b, s, _ in calls]}, slowest {max(t for *_, t in calls)} s")
print(f"Source: fuel prices, Ministry of Finance; weather, MET Malaysia (Malaysian Meteorological Department); via data.gov.my "
      f"({API}), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/), accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (fourth run, 2026-11-26 00:13 UTC = 08:13 MYT, in a new cloud browser, after the not-yet-in-effect check was added; the 23:50, 23:55 and 00:04 UTC runs printed the same prices and forecasts. The first two labelled the RON95 rows "unsubsidised", "subsidised" and "fleet subsidy" before the labels were changed to the dataset page's wording; at 07:50 MYT the feed held the earlier 03:00-08:00 thunderstorm warning (for Selangor, Putrajaya, Negeri Sembilan, Melaka and Johor) instead of the 08:00-12:00 one, and at 07:55 MYT it held the 08:00-12:00 one not yet in force (printed as "not active"); the 00:04 UTC run printed what is shown here apart from the clock and the slowest call):

```text
data.gov.my (Malaysia's official open data portal), checked 2026-11-26 00:13 UTC = 2026-11-26 08:13 MYT

Pump prices in effect from Thursday 26 November 2026, RM per litre (Ministry of Finance; catalogue fuelprice, data as of 2026-11-26 00:01, next update 2026-12-02 23:59 MYT)
  previous price set: Thursday 19 November 2026 (7 days earlier)
  RON95, general market        3.47  -0.25 on 19 Nov (3.72)
  RON95, BUDI 95 subsidy       1.99  +0.00 on 19 Nov (1.99)
  RON95, SKPS subsidy          2.05  +0.00 on 19 Nov (2.05)
  RON97                        3.75  -0.25 on 19 Nov (4.00)
  Diesel, Peninsular           4.47  -0.25 on 19 Nov (4.72)
  Diesel, East Malaysia        4.47  -0.25 on 19 Nov (4.72)
  check: change_weekly equals the difference of the two level rows (rounded to the sen; the raw values carry float noise, e.g. -0.25)
  also in the answer, not defined on the dataset page: {'diesel_budi': 2.1, 'diesel_skds': 2.15}

MET Malaysia warnings: 5 in the feed, 4 active at 26 Nov 08:13 MYT
  ACTIVE Strong Winds and Rough Seas Warning: FIRST CATEGORY WARNING ON STRONG WINDS AND ROUGH SEAS, issued 11-26 05:00, valid 11-26 05:00 to 11-26 10:00 MYT
         SECTION A: FOR MALAYSIAN WATERS [WITHIN 24 NAUTICAL MILES] 1) THUNDERSTORMS WARNING Thunderstorms, heavy rain and strong winds are expected over the waters of Perak • Selangor • N. Sembilan • Melaka • Johor • Pahang • Terengganu •...
  ACTIVE Thunderstorms Warning: THUNDERSTORMS WARNING, issued 11-26 08:00, valid 11-26 08:00 to 11-26 12:00 MYT
         Thunderstorms, heavy rain and strong winds are expected over the state of Johor (Kluang, Mersing, Kota Tinggi and Kulai) until 12:00 PM; Thursday, 26 November 2026.
  ACTIVE Continuous Rain Warning: CONTINUOUS RAIN WARNING (ALERT), issued 11-24 14:00, valid 11-24 00:00 to 11-27 23:59 MYT
         Continuous rain is expected to occur over the states of Kelantan (Pasir Puteh, Bachok, Kota Bharu, Tumpat, Pasir Mas, Machang and Tanah Merah) • Terengganu until Friday, 27 November 2026.
  ACTIVE Strong Winds and Rough Seas Warning: FIRST CATEGORY WARNING ON STRONG WINDS AND ROUGH SEAS, issued 11-26 05:00, valid 11-23 00:00 to 11-28 23:59 MYT
         SECTION A: FOR MALAYSIAN WATERS [WITHIN 24 NAUTICAL MILES] 1) THUNDERSTORMS WARNING Thunderstorms, heavy rain and strong winds are expected over the waters of Perak • Selangor • N. Sembilan • Melaka • Johor • Pahang • Terengganu •...
  no validity period: No Advisory: No Tropical Cyclone system is observed under MMD monitoring region (Latitude: 0-20 North & Longitude: 95-130 E

7-day forecast, Kuala Lumpur (Tn079), MET Malaysia:
  Thu 26 Nov  24-32 C  Thunderstorms (afternoon and night); morning No rain, afternoon Thunderstorms, night Rain
  Fri 27 Nov  24-33 C  Thunderstorms (throughout the day); morning Rain, afternoon Thunderstorms, night Rain
  Sat 28 Nov  24-33 C  No rain (throughout the day); morning No rain, afternoon No rain, night No rain
  Sun 29 Nov  24-33 C  Rain (morning); morning Rain, afternoon No rain, night No rain
  Mon 30 Nov  24-33 C  Rain (morning); morning Rain, afternoon No rain, night No rain
  Tue 01 Dec  24-33 C  Rain (morning); morning Rain, afternoon No rain, night No rain
  Wed 02 Dec  24-33 C  Rain (morning); morning Rain, afternoon No rain, night No rain
  active warnings naming Kuala Lumpur: none

7-day forecast, Kota Kinabalu (Tn196), MET Malaysia:
  Thu 26 Nov  24-32 C  Thunderstorms (throughout the day); morning Rain, afternoon Thunderstorms, night Rain
  Fri 27 Nov  24-32 C  Thunderstorms (throughout the day); morning Rain, afternoon Thunderstorms, night Thunderstorms
  Sat 28 Nov  24-32 C  Thunderstorms (throughout the day); morning Rain, afternoon Thunderstorms, night Rain
  Sun 29 Nov  24-32 C  Rain (throughout the day); morning Rain, afternoon Rain, night Rain
  Mon 30 Nov  24-32 C  Rain (afternoon and night); morning No rain, afternoon Rain, night Rain
  Tue 01 Dec  24-32 C  Thunderstorms (afternoon); morning No rain, afternoon Thunderstorms, night No rain
  Wed 02 Dec  24-32 C  Thunderstorms (afternoon and night); morning No rain, afternoon Thunderstorms, night Rain
  active warnings naming Kota Kinabalu: none

'Johor Baru': no MET Malaysia town of that name (200 towns); closest: ['Johor Bahru', 'Kota Bharu']
6 API calls [('data-catalogue', 200), ('weather', 200), ('weather', 200), ('weather', 200), ('weather', 200), ('weather', 200)], slowest 1.7 s
Source: fuel prices, Ministry of Finance; weather, MET Malaysia (Malaysian Meteorological Department); via data.gov.my (https://api.data.gov.my), CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/), accessed 26 November 2026 00:13 UTC.
```

### 2. robots.txt, the licence and rate-limit pages, the dataset page, missing terms pages, CORS, what the API does with mistakes (browser)

12 page loads and 12 in-page `fetch()` calls from data.gov.my (cross-origin: response type `cors` means the browser let the page read the answer). The FAQ answers sit in closed `<details>` elements, so the FAQ is read with `textContent`; the other pages use the visible `innerText`.

```python
import json, time

SITE, DEV, API = "https://data.gov.my", "https://developer.data.gov.my", "https://api.data.gov.my"
GAP = 16.0   # 4 requests per minute for each API

START_JS = """(() => { window.__u = window.__u || {}; const id = String(Math.random()).slice(2); window.__u[id] = null;
  fetch(%s, %s)
    .then(async r => { const h = {}; r.headers.forEach((v, k) => { h[k] = v; });
      window.__u[id] = {status: r.status, type: r.type, url: r.url, headers: h, text: await r.text()}; })
    .catch(e => { window.__u[id] = {status: 0, type: 'error', url: '', headers: {}, text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__u[%s]; if (v) delete window.__u[%s]; return v; })()"""

last = {}
def raw(url, redirect="follow"):
    """One in-page GET -> {status, type, url, headers, text}, GAP s apart per API. No retries: this block only inspects answers."""
    bucket = url.split("/")[3].split("?")[0]
    wait = last.get(bucket, 0) + GAP - time.time()
    if wait > 0:
        time.sleep(wait)
    last[bucket] = time.time()
    opts = {"credentials": "omit", "cache": "no-store", "redirect": redirect}
    rid = json.dumps(js(START_JS % (json.dumps(url), json.dumps(opts))))
    t0 = time.time()
    while (r := js(POLL_JS % (rid, rid))) is None:
        if time.time() - t0 > 90:
            raise RuntimeError(f"{url}: no answer after 90s")
        time.sleep(0.2)
    return r

def page(url, prop="innerText"):
    """Load a page -> (HTTP status, content type, final URL, text). innerText is the visible text; the FAQ answers sit in
    closed accordions, so the FAQ is read with textContent."""
    for attempt in range(2):   # a navigation can time out on the daemon side; try once more
        try:
            goto_url(url)
            break
        except Exception as e:
            if attempt:
                raise
            print(f"  ({url}: {type(e).__name__}, retrying once)")
            time.sleep(3)
    wait_for_load()
    time.sleep(2)
    st = js("(performance.getEntriesByType('navigation')[0] || {}).responseStatus")
    return st, js("document.contentType"), js("location.href"), js(f"(document.body || document.documentElement).{prop} || ''") or ""

def needles(url, items, prop="innerText"):
    st, ct, href, txt = page(url, prop)
    flat = " ".join(txt.split())
    print(f"\n{href} HTTP {st}")
    for n in items:
        print(f"  {'found' if n in flat else 'MISSING'}: {n[:100]!r}")
    return flat

# robots.txt: a 404 on the API host (no rules), Allow: / for * on the two web hosts, no named agent anywhere
for url in (API + "/robots.txt", SITE + "/robots.txt", DEV + "/robots.txt"):
    st, ct, href, txt = page(url)
    lines = [l.strip() for l in txt.splitlines() if l.strip() and not l.startswith("#")]
    if st == 200 and ct.startswith("text/plain"):
        print(f"{url.split('//')[1]:<30} HTTP {st} {ct}: {lines}")
    else:
        print(f"{url.split('//')[1]:<30} HTTP {st} {ct}: {' '.join(txt.split())[:80]!r}")

# Licence, rate limit and the Weather API source on the developer docs; the dataset page names the agency
needles(DEV + "/faq", ["This data is made open under the Creative Commons Attribution 4.0 International License (CC BY 4.0)",
                       "You can use the data available on our platform for free", "License: CC BY 4.0"], "textContent")
flat = needles(DEV + "/rate-limit", ["Data Catalogue 4 requests per minute", "OpenDOSM 4 requests per minute",
                                     "Weather 4 requests per minute", "429 Too Many Requests"])
needles(DEV + "/realtime-api/weather", ["The data is provided by MET Malaysia (Malaysian Meteorological Department)",
                                        "All weather feeds are licensed under CC BY 4.0", "The 7-day general forecast data is updated daily",
                                        "The warning data (including earthquake data) is updated when required",
                                        "the above field values are currently only available in Bahasa Melayu"])
low = needles(SITE + "/data-catalogue/fuelprice", ["Data source(s) Ministry of Finance", "This data is made open under the Creative Commons Attribution 4.0",
                                                    "maximum of 300 litres per month", "Subsidised Petrol Control System (SKPS)",
                                                    "https://storage.data.gov.my/commodities/fuelprice.csv"]).lower()
print(f"  words diesel_budi / diesel_skds on the dataset page: {[w for w in ('diesel_budi', 'diesel_skds') if w in low] or 'none'}")
for path in ("/terms-of-use", "/terms", "/disclaimer", "/privacy-policy"):
    st, ct, href, txt = page(SITE + path)
    print(f"{SITE + path:<36} HTTP {st}")
bad = [w for w in ("scrap", "artificial intelligence", "machine learning", "non-commercial", "noncommercial", "robot", "crawl")
       if w in (flat + " " + low)]
print(f"words scrap/AI/ML/non-commercial/robot/crawl on the rate-limit and dataset pages: {bad or 'none'}")

page(SITE + "/data-catalogue/fuelprice")   # back on data.gov.my: every call below is cross-origin
print(f"\ncalls from {js('location.origin')} (cross-origin), {GAP:.0f} s apart per API:")

def brief(r):
    t = " ".join(r["text"].split())
    # type "cors" = the browser let this page read a cross-origin answer; "opaqueredirect" = a 3xx not followed
    return f"HTTP {r['status']} {r['type']:<14} {r['headers'].get('content-type', '-'):<17} {len(r['text']):>5} chars: {t[:116]}"

for label, url, how in (
    ("fuel, newest 2 (sort=-date)          ", API + "/data-catalogue/?id=fuelprice&sort=-date&limit=2&include=date,series_type,ron95", "follow"),
    ("warnings, title only                 ", API + "/weather/warning/?include=warning_issue,valid_to", "follow"),
    ("no trailing slash (redirect manual)  ", API + "/data-catalogue?id=fuelprice&limit=1", "manual"),
    ("forecast: filter 'kuala lumpur' (case)", API + "/weather/forecast/?filter=kuala%20lumpur@location__location_name", "follow"),
    ("no trailing slash, followed          ", API + "/data-catalogue?id=fuelprice&limit=1&include=date", "follow"),
    ("forecast: bad column location__name  ", API + "/weather/forecast/?contains=Ipoh@location__name", "follow"),
    ("fuel, no sort, limit=1               ", API + "/data-catalogue/?id=fuelprice&limit=1&include=date,series_type,ron95", "follow"),
    ("forecast: icontains, all location ids", API + "/weather/forecast/?icontains=kuala%20lumpur@location__location_name&include=location,date&sort=date&limit=4", "follow"),
    ("no id                                ", API + "/data-catalogue/", "follow"),
    ("earthquakes, newest 1                ", API + "/weather/warning/earthquake/?sort=-utcdatetime&limit=1&include=localdatetime,location_original,magdefault,n_distancemas", "follow"),
    ("unknown id                           ", API + "/data-catalogue/?id=fuelprices&limit=1", "follow"),
    ("OpenDOSM CPI, newest 2               ", API + "/opendosm/?id=cpi_headline&sort=-date&limit=2", "follow"),
):
    print(f"{label} {brief(raw(url, how))}")
print(f"Source: data.gov.my (Malaysia's official open data portal), {API}; fuel prices: Ministry of Finance; weather: MET Malaysia; CC BY 4.0.")
```

Output (second run, 2026-11-25 23:56 UTC; the first run, at 23:52, read the FAQ with `innerText` and printed `MISSING` for the two FAQ sentences, which sit in a closed `<details>`, and printed a meaningless `ACAO=None` column, as a page cannot read that header):

```text
api.data.gov.my/robots.txt     HTTP 404 text/html: 'Not Found The requested resource was not found on this server.'
data.gov.my/robots.txt         HTTP 200 text/plain: ['User-agent: *', 'Allow: /', 'Host: https://data.gov.my', 'Sitemap: https://data.gov.my/sitemap.xml']
developer.data.gov.my/robots.txt HTTP 200 text/plain: ['User-agent: *', 'Allow: /', 'Host: https://developer.data.gov.my', 'Sitemap: https://developer.data.gov.my/sitemap.xml']

https://developer.data.gov.my/faq HTTP 200
  found: 'This data is made open under the Creative Commons Attribution 4.0 International License (CC BY 4.0)'
  found: 'You can use the data available on our platform for free'
  found: 'License: CC BY 4.0'

https://developer.data.gov.my/rate-limit HTTP 200
  found: 'Data Catalogue 4 requests per minute'
  found: 'OpenDOSM 4 requests per minute'
  found: 'Weather 4 requests per minute'
  found: '429 Too Many Requests'

https://developer.data.gov.my/realtime-api/weather HTTP 200
  found: 'The data is provided by MET Malaysia (Malaysian Meteorological Department)'
  found: 'All weather feeds are licensed under CC BY 4.0'
  found: 'The 7-day general forecast data is updated daily'
  found: 'The warning data (including earthquake data) is updated when required'
  found: 'the above field values are currently only available in Bahasa Melayu'

https://data.gov.my/data-catalogue/fuelprice HTTP 200
  found: 'Data source(s) Ministry of Finance'
  found: 'This data is made open under the Creative Commons Attribution 4.0'
  found: 'maximum of 300 litres per month'
  found: 'Subsidised Petrol Control System (SKPS)'
  found: 'https://storage.data.gov.my/commodities/fuelprice.csv'
  words diesel_budi / diesel_skds on the dataset page: ['diesel_budi', 'diesel_skds']
https://data.gov.my/terms-of-use     HTTP 404
https://data.gov.my/terms            HTTP 404
https://data.gov.my/disclaimer       HTTP 404
https://data.gov.my/privacy-policy   HTTP 404
words scrap/AI/ML/non-commercial/robot/crawl on the rate-limit and dataset pages: none

calls from https://data.gov.my (cross-origin), 16 s apart per API:
fuel, newest 2 (sort=-date)           HTTP 200 cors           application/json    135 chars: [{"series_type": "level", "ron95": 3.47, "date": "2026-11-26"}, {"series_type": "change_weekly", "ron95": -0.25, "da
warnings, title only                  HTTP 200 cors           application/json    801 chars: [{"warning_issue":{"issued":"2026-11-26T05:00:00","title_bm":"Amaran Angin Kencang dan Laut Bergelora","title_en":"S
no trailing slash (redirect manual)   HTTP 0 opaqueredirect -                     0 chars:
forecast: filter 'kuala lumpur' (case) HTTP 200 cors           application/json      2 chars: []
no trailing slash, followed           HTTP 200 cors           application/json     24 chars: [{"date": "2017-03-30"}]
forecast: bad column location__name   HTTP 400 cors           application/json    106 chars: {"status_code": 400, "details": ["`The column used in `Ipoh@location__name` is an invalid column value."]}
fuel, no sort, limit=1                HTTP 200 cors           application/json     63 chars: [{"series_type": "level", "ron95": 2.13, "date": "2017-03-30"}]
forecast: icontains, all location ids HTTP 200 cors           application/json    356 chars: [{"location":{"location_id":"Ds058","location_name":"Kuala Lumpur"},"date":"2026-11-26"},{"location":{"location_id":
no id                                 HTTP 400 cors           application/json     70 chars: {"status_code": 400, "details": ["Query parameter 'id' is required."]}
earthquakes, newest 1                 HTTP 200 cors           application/json    152 chars: [{"localdatetime":"2026-11-25T20:08:09","location_original":"Minahassa Peninsula, Sulawesi","n_distancemas":"744km S
unknown id                            HTTP 404 cors           application/json     94 chars: {"status_code": 404, "details": ["The data catalogue (fuelprices) requested does not exist."]}
OpenDOSM CPI, newest 2                HTTP 200 cors           application/json    121 chars: [{"date": "2026-10-01", "index": 137.7, "division": "overall"}, {"date": "2026-10-01", "index": 161.5, "division": "
Source: data.gov.my (Malaysia's official open data portal), https://api.data.gov.my; fuel prices: Ministry of Finance; weather: MET Malaysia; CC BY 4.0.
```

### 3. Same API with Python urllib: robots check for every agent, eight weeks of prices, the full history CSV, warnings in force, every town's forecast in one call (no browser)

Sends a descriptive User-Agent (Python's default one also got HTTP 200). One `/weather/forecast/` call with `contains=Tn@location__location_id` returns all 201 town ids for 7 days (1,407 rows), so several towns cost one call; the full fuel history comes from the CSV the dataset page links on storage.data.gov.my, which is not one of the rate-limited APIs.

```python
import csv, email.utils, io, json, sys, time, urllib.error, urllib.request, urllib.robotparser
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

API = "https://api.data.gov.my"
CSV_URL = "https://storage.data.gov.my/commodities/fuelprice.csv"   # the full dataset, linked from the dataset page
UA = "data-gov-my-skill-example/1.0 (+https://github.com/browser-use/browser-harness)"
AGENTS = ["*", "GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-User", "anthropic-ai",
          "Google-Extended", "PerplexityBot", "CCBot", "Bytespider"]
GAP = 16.0          # 4 requests per minute for each API (developer.data.gov.my/rate-limit)
WEEKS = 8
TOWNS = ["Serdang", "Georgetown", "Kuching"]
MYT, UTC = timezone(timedelta(hours=8)), timezone.utc
last, calls = {}, []

def retry_wait(value, body, default=10):
    """Retry-After (seconds or an HTTP date), else the body's "Expected available in N seconds", else default."""
    v = (value or "").strip()
    if v.isdigit():
        return int(v)
    try:
        return max(0, int((email.utils.parsedate_to_datetime(v) - datetime.now(UTC)).total_seconds()) + 1)
    except (TypeError, ValueError):
        pass
    try:
        return int(json.loads(body)["detail"].split("available in ")[1].split()[0]) + 1
    except (ValueError, KeyError, IndexError, TypeError):
        return default

def get(path, **params):
    """GET API + path + ?params -> parsed JSON. GAP s apart per API. Waits once on 429, 500, 502, 503, 504 or a network error
    (Retry-After, else 10 s; over 120 s exits). Exits on any other non-200 with the API's status_code and details."""
    url = API + path + "?" + "&".join(f"{k}={quote(str(v), safe='@,:-')}" for k, v in params.items())
    bucket = path.strip("/").split("/")[0]
    for attempt in range(2):
        wait = last.get(bucket, 0) + GAP - time.time()
        if wait > 0:
            time.sleep(wait)
        last[bucket] = time.time()
        t0 = time.time()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
                calls.append((bucket, r.status, round(time.time() - t0, 1)))
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            calls.append((bucket, e.code, round(time.time() - t0, 1)))
            if e.code in (429, 500, 502, 503, 504) and attempt == 0:
                wait = retry_wait(e.headers.get("Retry-After"), body)
                if wait > 120:
                    sys.exit(f"{url}: server asks to wait {wait} s: stopping")
                print(f"  HTTP {e.code}, waiting {wait} s once")
                time.sleep(wait)
                continue
            sys.exit(f"{url}: HTTP {e.code} {body[:200]}")
        except (urllib.error.URLError, TimeoutError) as e:
            calls.append((bucket, 0, round(time.time() - t0, 1)))
            if attempt == 0:
                time.sleep(10)
                continue
            sys.exit(f"{url}: {e}")

now = datetime.now(UTC)
print(f"data.gov.my (Malaysia's official open data portal), urllib, checked {now:%Y-%m-%d %H:%M} UTC = {now.astimezone(MYT):%H:%M} MYT")

# 1. robots.txt: the API host has none (HTTP 404 = no rules under RFC 9309); check every path this block uses for 11 agents
paths = ["/data-catalogue/?id=fuelprice", "/weather/forecast/", "/weather/warning/"]
for host in ("https://api.data.gov.my", "https://data.gov.my", "https://storage.data.gov.my"):
    try:
        with urllib.request.urlopen(urllib.request.Request(host + "/robots.txt", headers={"User-Agent": UA}), timeout=30) as r:
            code, lines = r.status, r.read().decode("utf-8", "replace").splitlines()
    except urllib.error.HTTPError as e:
        code, lines = e.code, []
    if code != 200 and not (400 <= code < 500 and code != 429):
        sys.exit(f"{host}/robots.txt HTTP {code}: rules unknown, stop")
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(lines)
    check = paths if host == API else (["/data-catalogue/fuelprice"] if host.endswith("//data.gov.my") else ["/commodities/fuelprice.csv"])
    ok = all(rp.can_fetch(a, host + p) for a in AGENTS for p in check)
    named = [l for l in lines if l.lower().startswith("user-agent") and l.split(":", 1)[1].strip() != "*"]
    print(f"  {host}/robots.txt HTTP {code}: {len(AGENTS)} agents x {len(check)} paths {'allowed' if ok else 'NOT all allowed'}; named groups {named or 'none'}")
    if not ok:
        sys.exit("robots.txt disallows a path: stop")

# 2. The last WEEKS price sets (level rows only), newest first, plus the meta block; flag changes that were not 7 days apart
f = get("/data-catalogue/", id="fuelprice", filter="level@series_type", sort="-date", limit=WEEKS, meta="true")
rows = f["data"]
print(f"\nfuelprice, {len(rows)} newest level rows (meta: data as of {f['meta']['data_as_of']}, source {f['meta']['data_source']}, "
      f"{f['meta']['update_frequency']}, next update {f['meta']['next_update']} MYT)")
def f2(v, w):
    return f"{v:>{w}.2f}" if v is not None else f"{'-':>{w}}"
print(f"  {'effective':<11} {'RON95':>6} {'BUDI95':>6} {'SKPS':>5} {'RON97':>6} {'diesel':>6} {'east':>5}  days since previous")
for r, older in zip(rows, rows[1:] + [None]):
    gap = (datetime.fromisoformat(r["date"]) - datetime.fromisoformat(older["date"])).days if older else None
    print(f"  {r['date']:<11} {f2(r['ron95'], 6)} {f2(r['ron95_budi95'], 6)} {f2(r['ron95_skps'], 5)} {f2(r['ron97'], 6)} "
          f"{f2(r['diesel'], 6)} {f2(r['diesel_eastmsia'], 5)}  {gap if gap is not None else '-'}")
d = round(rows[0]["ron95"] - rows[-1]["ron95"], 2)
print(f"  RON95 general market: {rows[-1]['ron95']:.2f} on {rows[-1]['date']} -> {rows[0]['ron95']:.2f} on {rows[0]['date']} ({d:+.2f})")

# 3. The full history from the CSV the dataset page links (one download, no API call): when did BUDI 95 first appear?
with urllib.request.urlopen(urllib.request.Request(CSV_URL, headers={"User-Agent": UA}), timeout=60) as r:
    lm, body = r.headers.get("Last-Modified"), r.read().decode("utf-8")
hist = [x for x in csv.DictReader(io.StringIO(body)) if x["series_type"] == "level"]
first_budi = min(x["date"] for x in hist if x["ron95_budi95"])
newest = max(hist, key=lambda x: x["date"])
mid = [x["date"] for x in hist if datetime.fromisoformat(x["date"]).weekday() != 3 and x["date"] >= "2021-03-03"]
print(f"\n{CSV_URL}: {len(body):,} bytes, Last-Modified {lm}, {len(hist)} level rows {min(x['date'] for x in hist)}..{newest['date']}")
print(f"  newest row RON95 {newest['ron95']} (API said {rows[0]['ron95']}: {'same' if float(newest['ron95']) == rows[0]['ron95'] else 'DIFFERENT'}); "
      f"first BUDI 95 price {first_budi}; level rows since 2021-03-03 not on a Thursday: {len(mid)} (newest {mid[-3:] if mid else []})")

# 4. Warnings in force now, and the 7-day forecast for towns (one call for all 200-odd towns, then pick)
warn = get("/weather/warning/")
nowm = now.astimezone(MYT)
act = [w for w in warn if w["valid_from"] and datetime.fromisoformat(w["valid_from"]).replace(tzinfo=MYT) <= nowm
       <= datetime.fromisoformat(w["valid_to"]).replace(tzinfo=MYT)]
print(f"\nMET Malaysia warnings in force at {nowm:%d %b %H:%M} MYT: {len(act)} of {len(warn)}: "
      f"{sorted({w['warning_issue']['title_en'] for w in act})}")
fc = get("/weather/forecast/", contains="Tn@location__location_id", sort="date")
by = {}
for r in fc:
    by.setdefault(r["location"]["location_name"].lower(), {}).setdefault(r["location"]["location_id"], []).append(r)
print(f"forecast: {len(fc)} rows, {sum(len(v) for v in by.values())} town ids, {len(by)} town names, "
      f"dates {fc[0]['date']}..{fc[-1]['date']}")
for t in TOWNS:
    ids = by.get(t.lower())
    if not ids:
        print(f"  {t}: no such MET Malaysia town")
        continue
    for lid, rs in ids.items():
        rain = sum(1 for r in rs if "hujan" in r["summary_forecast"].lower() and "tiada" not in r["summary_forecast"].lower())
        storm = sum(1 for r in rs if "ribut petir" in r["summary_forecast"].lower())
        print(f"  {t} ({lid}): min {min(r['min_temp'] for r in rs)} C, max {max(r['max_temp'] for r in rs)} C over {len(rs)} days; "
              f"thunderstorm days {storm}, rain days {rain}, dry days {len(rs) - storm - rain}; "
              f"today {rs[0]['summary_forecast']!r} ({rs[0]['summary_when']})")

print(f"\n{len(calls)} API calls {[(b, s) for b, s, _ in calls]}, slowest {max(t for *_, t in calls)} s; 1 CSV download")
print(f"Source: Ministry of Finance (fuel) and MET Malaysia (weather) via data.gov.my, CC BY 4.0, accessed {now:%d %B %Y %H:%M} UTC.")
```

Output (second run, 2026-11-26 00:05 UTC = 08:05 MYT; the 23:59 UTC run printed the same prices, history and forecasts, with 3 of 5 warnings in force because the 08:00 Johor thunderstorm warning had not started):

```text
data.gov.my (Malaysia's official open data portal), urllib, checked 2026-11-26 00:05 UTC = 08:05 MYT
  https://api.data.gov.my/robots.txt HTTP 404: 11 agents x 3 paths allowed; named groups none
  https://data.gov.my/robots.txt HTTP 200: 11 agents x 1 paths allowed; named groups none
  https://storage.data.gov.my/robots.txt HTTP 404: 11 agents x 1 paths allowed; named groups none

fuelprice, 8 newest level rows (meta: data as of 2026-11-26 00:01, source ['MOF'], WEEKLY, next update 2026-12-02 23:59 MYT)
  effective    RON95 BUDI95  SKPS  RON97 diesel  east  days since previous
  2026-11-26    3.47   1.99  2.05   3.75   4.47  4.47  7
  2026-11-19    3.72   1.99  2.05   4.00   4.72  4.72  7
  2026-11-12    3.87   1.99  2.05   4.20   4.87  4.87  7
  2026-11-05    4.27   1.99  2.05   4.70   5.12  5.12  7
  2026-10-29    4.42   1.99  2.05   4.90   5.27  5.27  7
  2026-10-22    4.32   1.99  2.05   4.80   5.07  5.07  7
  2026-10-15    4.62   1.99  2.05   5.10   5.17  5.17  7
  2026-10-08    4.67   1.99  2.05   5.15   5.27  5.27  -
  RON95 general market: 4.67 on 2026-10-08 -> 3.47 on 2026-11-26 (-1.20)

https://storage.data.gov.my/commodities/fuelprice.csv: 56,216 bytes, Last-Modified Wed, 25 Nov 2026 10:31:07 GMT, 489 level rows 2017-03-30..2026-11-26
  newest row RON95 3.47 (API said 3.47: same); first BUDI 95 price 2025-09-30; level rows since 2021-03-03 not on a Thursday: 5 (newest ['2024-06-10', '2025-09-30', '2026-07-01'])

MET Malaysia warnings in force at 26 Nov 08:05 MYT: 4 of 5: ['Continuous Rain Warning', 'Strong Winds and Rough Seas Warning', 'Thunderstorms Warning']
forecast: 1407 rows, 201 town ids, 200 town names, dates 2026-11-26..2026-12-02
  Serdang (Tn023): min 24 C, max 32 C over 7 days; thunderstorm days 5, rain days 2, dry days 0; today 'Ribut petir' (Petang dan Malam)
  Serdang (Tn164): min 24 C, max 33 C over 7 days; thunderstorm days 2, rain days 4, dry days 1; today 'Ribut petir' (Petang dan Malam)
  Georgetown (Tn013): min 24 C, max 32 C over 7 days; thunderstorm days 5, rain days 2, dry days 0; today 'Ribut petir' (Petang dan Malam)
  Kuching (Tn187): min 24 C, max 34 C over 7 days; thunderstorm days 7, rain days 0, dry days 0; today 'Ribut petir' (Petang dan Malam)

3 API calls [('data-catalogue', 200), ('weather', 200), ('weather', 200)], slowest 9.7 s; 1 CSV download
Source: Ministry of Finance (fuel) and MET Malaysia (weather) via data.gov.my, CC BY 4.0, accessed 26 November 2026 00:05 UTC.
```

### 4. curl: prices, warnings, a town forecast, the 301, headers, mistakes, OpenDOSM, the CSV with ETag, robots

```bash
A=https://api.data.gov.my
UA='data-gov-my-skill-example/1.0 (+https://github.com/browser-use/browser-harness)'
# --retry 1 retries once on a timeout or HTTP 408, 429, 500, 502, 503 or 504 (curl's man page: it "complies with the Retry-After: response header");
# --retry-max-time 120 skips the retry when Retry-After would wait past 120 s
# 4 requests per minute per API: every call below sleeps 16 s before the next call to the same API, and a retry waits 16 s too.
C=(curl -sS --max-time 90 --retry 1 --retry-delay 16 --retry-max-time 120 -A "$UA")
T=$(mktemp); trap 'rm -f "$T" "$T.h" "$T.n"' EXIT   # $T.n takes answers we discard: on a retry curl 8.5 truncates its output file and fails on /dev/null (exit 23)
# 1. this week's pump prices: the newest 4 rows = level + change_weekly for the newest two dates (trailing slash required)
"${C[@]}" --fail "$A/data-catalogue/?id=fuelprice&sort=-date&limit=4&meta=true" | python3 -c 'import json, sys
d = json.load(sys.stdin); m = d["meta"]; rows = d["data"]
print("meta:", {k: m[k] for k in ("data_as_of", "last_updated", "next_update", "data_source", "update_frequency")})
for r in sorted(rows, key=lambda r: (r["date"], r["series_type"]), reverse=True):
    st = r["series_type"]; fmt = "{:.2f}" if st == "level" else "{:+.2f}"
    print(" ", r["date"], st.ljust(13), " ".join(k + " " + fmt.format(round(r[k], 2))
          for k in ("ron95", "ron95_budi95", "ron95_skps", "ron97", "diesel", "diesel_eastmsia")))'
sleep 16
# 2. warnings (weather API): times are Malaysia time with no zone; keep the ones in force now
"${C[@]}" --fail "$A/weather/warning/" | python3 -c 'import json, sys
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None).isoformat(timespec="seconds")
for w in json.load(sys.stdin):
    on = bool(w["valid_from"]) and w["valid_from"] <= now <= w["valid_to"]
    print("  IN FORCE" if on else "  other   ", w["warning_issue"]["title_en"], "|", w["valid_from"], "->", w["valid_to"], "|", (w["text_en"] or "")[:80])'
sleep 16
# 3. 7-day forecast for one town: exact name in any case (ifilter) + Town ids only (contains=Tn), oldest date first
"${C[@]}" --fail "$A/weather/forecast/?ifilter=kuala%20lumpur@location__location_name&contains=Tn@location__location_id&sort=date" | python3 -c 'import json, sys
for r in json.load(sys.stdin):
    print(" ", r["location"]["location_id"], r["location"]["location_name"], r["date"], r["min_temp"], "-", r["max_temp"], "C |", r["summary_forecast"], "/", r["summary_when"])'
sleep 16
# 4. without the trailing slash: a 301 to the slashed URL (curl -L would follow it, at the cost of one more request)
"${C[@]}" -o "$T.n" -w '  no slash: HTTP %{http_code} -> %{redirect_url}\n' "$A/data-catalogue?id=fuelprice&limit=1"
sleep 16
# 5. headers on a 200: no rate-limit, ETag or Last-Modified headers; Cloudflare sets a __cf_bm cookie (not needed)
"${C[@]}" -D - -o "$T.n" "$A/data-catalogue/?id=fuelprice&limit=1&include=date" | tr -d '\r' \
  | grep -iE '^(HTTP/|(content-type|cache-control|etag|last-modified|retry-after|x-ratelimit[a-z-]*|ratelimit[a-z-]*|allow|server):)'
sleep 16
"${C[@]}" -D - -o "$T.n" "$A/data-catalogue/?id=fuelprice&limit=1&include=date" -H 'Origin: https://example.org' 2>/dev/null | tr -d '\r' | grep -iE '^(access-control-allow-origin|set-cookie):' | sed -E 's/(__cf_bm=)[^;]*/\1<value>/'
sleep 16
# 6. mistakes: JSON {"status_code", "details"}
for u in "data-catalogue/" "data-catalogue/?id=fuelprices" "data-catalogue/?id=fuelprice&filter=Level@series_type&limit=1"; do
  curl -sS --max-time 60 -A "$UA" -o "$T" -w "  %{http_code} " "$A/$u"; echo "$(head -c 130 "$T")  <- $u"; sleep 16
done
"${C[@]}" -o "$T" -w "  %{http_code} " "$A/weather/forecast/?contains=Ipoh@location__name"; echo "$(head -c 130 "$T")  <- weather/forecast/?contains=Ipoh@location__name"
sleep 16
# 7. OpenDOSM API (same query syntax): headline consumer price index, newest month
"${C[@]}" --fail "$A/opendosm/?id=cpi_headline&filter=overall@division&sort=-date&limit=2"; echo
# 8. the full fuel history as CSV from storage.data.gov.my (no API call; ETag for a conditional re-download)
"${C[@]}" --fail -D "$T.h" -o "$T" https://storage.data.gov.my/commodities/fuelprice.csv
E=$(tr -d '\r' < "$T.h" | awk -F': ' 'tolower($1)=="etag"{print $2}')
echo "  CSV: $(wc -l < "$T") lines, $(head -1 "$T")"; grep -E '^(level|change_weekly),2026-11-26' "$T" | sed 's/^/  /'
"${C[@]}" -o "$T.n" -H "If-None-Match: $E" -w '  CSV again with If-None-Match: HTTP %{http_code}\n' https://storage.data.gov.my/commodities/fuelprice.csv
# 9. robots.txt: none on the API host or storage (404), Allow: / on data.gov.my
for h in api.data.gov.my data.gov.my storage.data.gov.my; do
  "${C[@]}" -o "$T" -w "  $h/robots.txt: HTTP %{http_code} %{content_type}" "https://$h/robots.txt"; echo " | $(grep -iE '^(user-agent|allow|disallow)' "$T" | tr '\n' ' ')"
done
echo "Source: Ministry of Finance (fuel), MET Malaysia (weather), OpenDOSM (CPI), via data.gov.my, CC BY 4.0, accessed $(date -u '+%d %B %Y %H:%M') UTC."
```

Output (third run, 2026-11-26 00:10-00:13 UTC; the 00:00 and 00:06 UTC runs printed the same data apart from the clock and the cookie expiry, and their source line said "DOSM (CPI)" before it was changed to "OpenDOSM (CPI)"; the comment on line 3 was reworded after this run):

```text
meta: {'data_as_of': '2026-11-26 00:01', 'last_updated': '2026-11-25 23:59', 'next_update': '2026-12-02 23:59', 'data_source': ['MOF'], 'update_frequency': 'WEEKLY'}
  2026-11-26 level         ron95 3.47 ron95_budi95 1.99 ron95_skps 2.05 ron97 3.75 diesel 4.47 diesel_eastmsia 4.47
  2026-11-26 change_weekly ron95 -0.25 ron95_budi95 +0.00 ron95_skps +0.00 ron97 -0.25 diesel -0.25 diesel_eastmsia -0.25
  2026-11-19 level         ron95 3.72 ron95_budi95 1.99 ron95_skps 2.05 ron97 4.00 diesel 4.72 diesel_eastmsia 4.72
  2026-11-19 change_weekly ron95 -0.15 ron95_budi95 +0.00 ron95_skps +0.00 ron97 -0.20 diesel -0.15 diesel_eastmsia -0.15
  IN FORCE Strong Winds and Rough Seas Warning | 2026-11-23T00:00:00 -> 2026-11-28T23:59:59 | SECTION A: FOR MALAYSIAN WATERS [WITHIN 24 NAUTICAL MILES] 1) THUNDERSTORMS WARN
  IN FORCE Strong Winds and Rough Seas Warning | 2026-11-26T05:00:00 -> 2026-11-26T10:00:00 | SECTION A: FOR MALAYSIAN WATERS [WITHIN 24 NAUTICAL MILES] 1) THUNDERSTORMS WARN
  IN FORCE Thunderstorms Warning | 2026-11-26T08:00:00 -> 2026-11-26T12:00:00 | Thunderstorms, heavy rain and strong winds are expected over the state of Johor
  other    No Advisory | None -> None | No Tropical Cyclone system is observed under MMD monitoring region (Latitude: 0-
  IN FORCE Continuous Rain Warning | 2026-11-24T00:00:00 -> 2026-11-27T23:59:59 | Continuous rain is expected to occur over the states of Kelantan (Pasir Puteh, B
  Tn079 Kuala Lumpur 2026-11-26 24 - 32 C | Ribut petir / Petang dan Malam
  Tn079 Kuala Lumpur 2026-11-27 24 - 33 C | Ribut petir / Sepanjang Hari
  Tn079 Kuala Lumpur 2026-11-28 24 - 33 C | Tiada Hujan / Sepanjang Hari
  Tn079 Kuala Lumpur 2026-11-29 24 - 33 C | Hujan / Pagi
  Tn079 Kuala Lumpur 2026-11-30 24 - 33 C | Hujan / Pagi
  Tn079 Kuala Lumpur 2026-12-01 24 - 33 C | Hujan / Pagi
  Tn079 Kuala Lumpur 2026-12-02 24 - 33 C | Hujan / Pagi
  no slash: HTTP 301 -> https://api.data.gov.my/data-catalogue/?id=fuelprice&limit=1
HTTP/2 200
content-type: application/json
server: cloudflare
allow: GET, HEAD, OPTIONS
cache-control: private
access-control-allow-origin: *
set-cookie: __cf_bm=<value>; HttpOnly; SameSite=None; Partitioned; Secure; Path=/; Domain=api.data.gov.my; Expires=Thu, 26 Nov 2026 00:41:43 GMT
  400 {"status_code": 400, "details": ["Query parameter 'id' is required."]}  <- data-catalogue/
  404 {"status_code": 404, "details": ["The data catalogue (fuelprices) requested does not exist."]}  <- data-catalogue/?id=fuelprices
  200 []  <- data-catalogue/?id=fuelprice&filter=Level@series_type&limit=1
  400 {"status_code": 400, "details": ["`The column used in `Ipoh@location__name` is an invalid column value."]}  <- weather/forecast/?contains=Ipoh@location__name
[{"date": "2026-10-01", "index": 137.7, "division": "overall"}, {"date": "2026-09-01", "index": 137.6, "division": "overall"}]
  CSV: 978 lines, series_type,date,ron95,ron97,diesel,diesel_eastmsia,ron95_budi95,ron95_skps,diesel_skds,diesel_budi
  level,2026-11-26,3.47,3.75,4.47,4.47,1.99,2.05,2.15,2.1
  change_weekly,2026-11-26,-0.25,-0.25,-0.25,-0.25,0.0,0.0,0.0,0.0
  CSV again with If-None-Match: HTTP 304
  api.data.gov.my/robots.txt: HTTP 404 text/html; charset=utf-8 |
  data.gov.my/robots.txt: HTTP 200 text/plain; charset=utf-8 | User-agent: * Allow: /
  storage.data.gov.my/robots.txt: HTTP 404 application/xml |
Source: Ministry of Finance (fuel), MET Malaysia (weather), OpenDOSM (CPI), via data.gov.my, CC BY 4.0, accessed 26 November 2026 00:13 UTC.
```

## Fields

| Endpoint / field | Value | Notes |
|---|---|---|
| `/data-catalogue/?id=fuelprice` | `[{date, series_type, ron95, ron97, diesel, diesel_eastmsia, ron95_budi95, ron95_skps, diesel_budi, diesel_skds}]` | without `sort` the oldest row comes first (2017-03-30); `meta=true` wraps it as `{"meta": {catalogue_id, data_as_of, last_updated, next_update, data_source: ["MOF"], update_frequency: "WEEKLY", total, ...}, "data": [...]}` (times Malaysia time, no zone) |
| `series_type` | `"level"` or `"change_weekly"` | the dataset page: "Price in RM (level), or weekly change in RM (change_weekly)"; two rows per date, in no fixed order (the first answer listed 2026-11-26 level first and 2026-11-19 change first) |
| `date` | `"2026-11-26"` | "The date of effect of the price"; since 3 March 2021 Thursdays except 5 level dates: 2021-07-28, 2022-09-14 and the subsidy changes 2024-06-10, 2025-09-30 and 2026-07-01 |
| `ron95` | `3.47` | "Price per litre of RON95 petrol, in RM": the general-market price |
| `ron95_budi95` | `1.99` | "under BUDI 95 subsidy"; the dataset page: RM1.99 "(up to a maximum of 300 litres per month) for eligibles individuals"; null before 2025-09-30 |
| `ron95_skps` | `2.05` | "under the Subsidised Petrol Control System (SKPS)", for eligible commercial vehicles; null before 2025-09-30 |
| `ron97`, `diesel`, `diesel_eastmsia` | `3.75`, `4.47`, `4.47` | `diesel` is Peninsular Malaysia, `diesel_eastmsia` "Sarawak, Sabah, W.P. Labuan" |
| `diesel_budi`, `diesel_skds` | `2.1`, `2.15` | in the API and the CSV but not in the dataset page's variable definitions; this skill prints them and does not interpret them. In the CSV `diesel_skds` has values from 2024-06-10 and `diesel_budi` from 2026-07-01, the date after which, the caveats say, "East Malaysia moved to the BUDI Diesel scheme" |
| `/weather/warning/` | `[{warning_issue{issued, title_bm, title_en}, valid_from, valid_to, heading_en, text_en, instruction_en, heading_bm, text_bm, instruction_bm}]` | times Malaysia time with no zone; 5 rows on 26 November; a `"No Advisory"` row (tropical cyclones) has `valid_from`/`valid_to` null; `instruction_*` can be null; texts are long (marine ones over 1,000 characters) |
| `/weather/forecast/` | `[{location{location_id, location_name}, date, morning_forecast, afternoon_forecast, night_forecast, summary_forecast, summary_when, min_temp, max_temp}]` | 440 locations x 7 days = 3,080 rows (904 KB) with no filter; ids `St` state (16), `Rc` recreation centre (37), `Ds` district (168), `Tn` town (201), `Dv` division (18); temperatures integer deg C |
| `/weather/warning/earthquake/` | `[{utcdatetime, localdatetime, lat, lon, depth, location, location_original, n_distancemas, magdefault, ...}]` | sort with `-utcdatetime` |
| `/opendosm/?id=` | rows of the OpenDOSM catalogue | `cpi_headline`: `{date, index, division}`; same query syntax and limit |
| errors | `{"status_code": 400, "details": ["..."]}` | not the `{status, errors}` the Response Format page shows; 400 missing `id` or bad column, 404 unknown `id`; 429 is `{"detail": "Request was throttled. Expected available in 37 seconds."}` plus `Retry-After` |
| response headers | `content-type: application/json`, `cache-control: private`, `allow: GET, HEAD, OPTIONS`, `server: cloudflare`, a `__cf_bm` cookie | no `ETag`, `Last-Modified` or rate-limit headers; `Access-Control-Allow-Origin: *` when an `Origin` is sent |
| storage CSV | `series_type,date,ron95,ron97,diesel,diesel_eastmsia,ron95_budi95,ron95_skps,diesel_skds,diesel_budi` | 978 lines, 56,216 bytes; `ETag` and `Last-Modified` (`If-None-Match` gave HTTP 304) |

## Gotchas

- **Trailing slash.** `/data-catalogue?id=...` is HTTP 301 to `/data-catalogue/?id=...`; a client that follows it spends a second request, which may count against the 4 a minute. Always write the slash, also on `/weather/warning/` and `/weather/forecast/` (both are HTTP 301 without it too). The docs' own examples (`curl --location 'https://api.data.gov.my/weather/forecast?limit=3'`, the dataset page's `https://api.data.gov.my/data-catalogue?id=fuelprice&limit=3`) leave it out and rely on following the redirect.
- **Sort, or you get 2017.** Without `sort=-date`, `limit=1` returns the first row of the dataset (`2017-03-30`, RON95 2.13). Then pick rows by `series_type`, not by position: the two rows of one date come in either order.
- **Float noise in changes.** `change_weekly` for 2026-11-19 RON95 is `-0.1499999999999999`; round to 2 decimals before printing or comparing.
- **Filters are case-sensitive, values and all.** `filter=Level@series_type` returns `[]`, as does `filter=kuala lumpur@location__location_name`; use the exact case or `ifilter`/`icontains`. A wrong column name is HTTP 400 "is an invalid column value".
- **One name, several places.** `contains=Kuala Lumpur@location__location_name` returns 21 rows: district `Ds058`, state `St009` "WP Kuala Lumpur" and town `Tn079`, whose texts differ (`Ribut petir di kebanyakan tempat` for the district, `Ribut petir` for the town on 26 November). Add `contains=Tn@location__location_id` for towns. Two towns are both called Serdang (`Tn023`, `Tn164`) with different forecasts, and names follow MET Malaysia: `Georgetown`, `Johor Bahru`.
- **Malay values, not all documented, case varies.** The API sends `Tiada Hujan`; the docs' table says `Tiada hujan`. The 440 locations' rows for 26 November (one call while exploring) also used `Ribut petir di kebanyakan tempat`, `Hujan menyeluruh`, `Hujan di kebanyakan tempat`, `Ribut petir menyeluruh`, `Hujan di beberapa tempat di kawasan pantai` and `Hujan di beberapa tempat di kawasan pedalaman`, which the table lacks; keep them in Malay rather than guess.
- **Times have no zone; they are Malaysia time.** At 23:40 UTC on 25 November the feed already held warnings `issued` `2026-11-26T05:00:00`, so these cannot be UTC; compare `valid_from`/`valid_to` with the time in UTC+8, as blocks 1, 3 and 4 do. Rows can leave the feed before `valid_to`: by 07:55 MYT the 03:00-08:00 thunderstorm warning had been replaced by an 08:00-12:00 one (block 1, runs 1 and 2).
- **"Active" needs your own check.** The feed mixes warnings in force, warnings that start later and the "No Advisory" row with null times. Warnings name states and districts, not towns; block 1's "naming Kuala Lumpur" check is a plain text search and found none, though the Selangor and Putrajaya warnings were nearby.
- **Slow answers.** Most calls take about 1 s, but the warnings call once took 17.3 s; allow 60 s or more before giving up, and do not retry early (a retry is another request against the limit).
- **CORS.** Cross-origin `fetch()` works (`Access-Control-Allow-Origin: *`); block 1 reads a 429's wait from the body text, which a page can always read, rather than from `Retry-After`.
- **Errors differ from the docs.** The Response Format page shows `{status, errors}`; the API sends `{"status_code", "details"}`, and a 429 sends `{"detail": ...}`.
- **Credit and no logo.** Credit the agency and the licence each time ("Source: Ministry of Finance via data.gov.my, CC BY 4.0"; "MET Malaysia via data.gov.my"), use no coat of arms or logo, and do not suggest an endorsement.
- **Tab marker.** The harness sets the tab title to a horse emoji; the blocks check `location.href` and the page text, not the title.

## What does not work

- **Paths without the trailing slash**: HTTP 301 (blocks 2 and 4).
- **More than 4 calls a minute to one API**: HTTP 429 with `Retry-After` (seen once, on purpose, while exploring).
- **A missing or unknown `id`, a wrong column**: HTTP 400 / 404 with `{"status_code", "details"}`.
- **Terms pages**: `/terms-of-use`, `/terms`, `/disclaimer`, `/privacy-policy` on data.gov.my are HTTP 404; the licence statements above are all there is.
- **English forecast text**: the API has none; only the docs' table.
- **Conditional GETs on the API**: no `ETag` or `Last-Modified` (the storage CSV has both).
- **Not tested:** GTFS Static and GTFS Realtime, `range`, `exclude`, `timestamp_end`, paging past large `limit` values, a 5xx (never seen), and how long a 429 lasts beyond the 37 s it announced.
