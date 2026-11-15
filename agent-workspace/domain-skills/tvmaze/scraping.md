# TVmaze - Show Search, Episode Lists, TV and Streaming Schedule, Cast (official API + site)

Field-tested against api.tvmaze.com and www.tvmaze.com on 2026-11-05 using a Browser Use cloud browser, logged out. Blocks 1-4 call the official TVmaze API (https://www.tvmaze.com/api) with `fetch()` from a www.tvmaze.com tab; block 5 reads the public site. About 110 API calls and 25 page loads: every answer was HTTP 200 or a documented 404/422, no 429, no challenge, no login or consent wall.

robots.txt (fetched 2026-11-05): www.tvmaze.com has `User-agent: *` disallowing only `/stats`, `/offer`, `/users/*/*/followed` and `/users/*/*/watched`, with no named AI-agent groups; api.tvmaze.com/robots.txt is HTTP 404 (no rules). This skill opens `/robots.txt`, `/search`, `/shows/<id>/<slug>/episodes` and `/shows/<id>/<slug>/cast` on www and calls the documented API endpoints.

## Quick summary

- **Use the API.** Public, keyless, CORS enabled on every endpoint (docs). Twelve endpoints cover the task:
  - `/search/shows?q=` (fuzzy, best first, max 10), `/singlesearch/shows?q=` (one show or 404), `/lookup/shows?imdb=|thetvdb=`.
  - `/shows/<id>?embed[]=seasons&embed[]=nextepisode&embed[]=previousepisode`, `/shows/<id>/episodes[?specials=1]`, `/shows/<id>/episodebynumber?season=&number=`.
  - `/schedule?country=<ISO2>&date=<YYYY-MM-DD>` (broadcast/cable) and `/schedule/web?date=[&country=]` (streaming).
  - `/shows/<id>/cast`, `/episodes/<id>/guestcast`, `/search/people?q=`, `/people/<id>/castcredits?embed=show`.
- **Rate limit** (docs): "at least 20 calls every 10 seconds per IP address", HTTP 429 above that. The blocks run one call at a time with 0.6 s between calls, back off 10 s once on a 429 (the docs say to retry after a small pause), then stop.
- **Caching** (docs): API output is cached 60 minutes (`cache-control: public, max-age=3600` observed), so site edits take up to an hour to show.
- **License** (docs): API data is CC BY-SA; credit TVmaze with a link back.
- **User-Agent:** the docs recommend (do not require) a descriptive User-Agent. The blocks keep the browser's own; do not change it.
- **The site works too** (block 5): search, episode guide and cast pages are server-rendered HTML and match the API.

## What works

Blocks 1-4 share the same helpers: `on_tvmaze_tab()` opens `https://www.tvmaze.com/robots.txt` once (a tiny allowed page) and later blocks reuse any www.tvmaze.com tab. `api(path, params)` runs one `fetch()` in that tab, polls for the answer (episode lists reach 725 KB, schedules 515 KB), reads big bodies back in 500,000-character slices, and returns parsed JSON. It raises `NotFound` on 404, backs off once then exits on 429, retries 5xx and network errors twice, and raises on anything else (422 included), so a failure never looks like an empty result.

### 1. Find a show: fuzzy search, single best match, IMDb / TheTVDB id (browser, official API)

```python
import json, time, urllib.parse

QUERIES = ["the office", "breking bad", "zzqx no such show 98712"]   # fuzzy search, typo, no match
SINGLE = ["breaking bad", "top gear"]                                 # best single match (or 404)
LOOKUPS = [{"imdb": "tt0386676"}, {"thetvdb": "81189"}]               # by IMDb / TheTVDB id

API = "https://api.tvmaze.com"
PACE = 0.6             # seconds between calls; docs: "at least 20 calls every 10 seconds per IP address"
CHUNK = 500_000        # characters per js() read when pulling a big body out of the tab

class NotFound(Exception):
    """TVmaze answered 404: no such show/episode/person, or singlesearch/lookup found nothing."""

def on_tvmaze_tab():
    """API calls run as fetch() from a logged-out www.tvmaze.com tab (the docs: every endpoint is CORS enabled)."""
    try:
        if js("location.origin") == "https://www.tvmaze.com":
            return
    except Exception:
        pass
    new_tab("https://www.tvmaze.com/robots.txt")   # tiny allowed page on the site
    wait_for_load()

START_JS = """(() => { window.__tm = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__tm = {status: r.status, len: t.length, body: t}; })
    .catch(e => { window.__tm = {status: 0, len: 0, body: '', err: String(e)}; });
  return 1; })()"""

def api(path, params=None, tries=3):
    """Serial GET of api.tvmaze.com<path>. Parsed JSON; NotFound on 404; one 10 s back-off on 429, then stops;
    retries 5xx/network errors with backoff, then raises (so a failure never looks like an empty result)."""
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    for attempt in range(tries):
        js(START_JS % json.dumps(url))
        t0 = time.time()
        while not (meta := js("window.__tm && {status: window.__tm.status, len: window.__tm.len, err: window.__tm.err}")):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__tm.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__tm = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            return json.loads(body)
        if status == 404:
            raise NotFound(f"{url}: {body[:120]}")
        if status == 429:
            if attempt == 0:
                time.sleep(10)   # docs: back off a few seconds and retry; once only
                continue
            raise SystemExit(f"HTTP 429 twice on {url}: stop and slow down, do not work around it")
        if (status >= 500 or status == 0) and attempt < tries - 1:
            time.sleep(5 * 2 ** attempt)
            continue
        raise RuntimeError(f"{url}: HTTP {status}: {meta.get('err') or body[:200]}")

def channel(show):
    """Broadcast network or streaming web channel, with country when known."""
    ch = show.get("network") or show.get("webChannel") or {}
    country = (ch.get("country") or {}).get("code")
    return f"{ch.get('name', '?')}{' ' + country if country else ''}"

def show_row(s):
    return {
        "id": s["id"], "name": s["name"], "channel": channel(s), "type": s["type"], "language": s["language"],
        "status": s["status"], "premiered": s["premiered"], "ended": s["ended"],
        "rating": s["rating"]["average"], "imdb": s["externals"].get("imdb"), "url": s["url"],
    }

on_tvmaze_tab()
for q in QUERIES:
    hits = api("/search/shows", {"q": q})                    # list of {score, show}; at most 10, best first
    print(f"{q!r}: {len(hits)} hits")
    for h in hits[:5]:
        r = show_row(h["show"])
        print(f"  {h['score']:.3f}  #{r['id']:<6} {r['name']:<28} {r['channel']:<16} {r['premiered']} -> {r['ended'] or r['status']}  rating {r['rating']}")
for q in SINGLE:
    try:
        r = show_row(api("/singlesearch/shows", {"q": q}))
        print(f"singlesearch {q!r}: #{r['id']} {r['name']} ({r['channel']}, {r['premiered']})")
    except NotFound:
        print(f"singlesearch {q!r}: no match")
for ids in LOOKUPS:
    try:
        r = show_row(api("/lookup/shows", ids))
        print(f"lookup {ids}: #{r['id']} {r['name']} ({r['channel']})")
    except NotFound:
        print(f"lookup {ids}: no match")
print(json.dumps(show_row(api("/search/shows", {"q": QUERIES[0]})[0]["show"]), indent=1))
```

Output observed on 2026-11-05:

```text
'the office': 10 hits
  1.185  #526    The Office                   NBC US           2005-03-24 -> 2013-05-16  rating 8.5
  1.183  #1292   The Office                   BBC Two GB       2001-07-09 -> 2003-12-27  rating 7.8
  1.169  #69044  The Office                   Prime Video      2024-10-18 -> 2024-10-18  rating 4.9
  1.169  #57704  The Office                   JioHotstar IN    2019-06-28 -> 2019-09-15  rating None
  1.150  #57168  The Office                   CBS US           1995-03-11 -> 1995-04-15  rating None
'breking bad': 9 hits
  0.556  #169    Breaking Bad                 AMC US           2008-01-20 -> 2019-10-11  rating 9.2
  0.527  #27845  Breaking Bad: Original Minisodes AMC US           2009-02-17 -> 2011-07-11  rating 7
  0.460  #6101   Breaking Band                AXS TV US        2016-01-24 -> 2016-02-28  rating None
  0.409  #37136  Breaking the Band            REELZ US         2018-06-10 -> Running  rating None
  0.356  #39967  Bradley Walsh & Son: Breaking Dad ITV1 GB          2019-01-02 -> Running  rating 5.2
'zzqx no such show 98712': 0 hits
singlesearch 'breaking bad': #169 Breaking Bad (AMC US, 2008-01-20)
singlesearch 'top gear': #522 Top Gear (BBC One GB, 2002-10-20)
lookup {'imdb': 'tt0386676'}: #526 The Office (NBC US)
lookup {'thetvdb': '81189'}: #169 Breaking Bad (AMC US)
{
 "id": 526,
 "name": "The Office",
 "channel": "NBC US",
 "type": "Scripted",
 "language": "English",
 "status": "Ended",
 "premiered": "2005-03-24",
 "ended": "2013-05-16",
 "rating": 8.5,
 "imdb": "tt0386676",
 "url": "https://www.tvmaze.com/shows/526/the-office"
}
```

### 2. Episode list: seasons, regular episodes, specials, previous and next episode (browser, official API)

```python
import json, time, urllib.parse
from datetime import datetime, timezone

SHOWS = [526, 169, 83]          # TVmaze show ids (block 1): The Office (US), Breaking Bad, The Simpsons
BY_NUMBER = (526, 2, 1)         # show id, season, episode -> one episode

API = "https://api.tvmaze.com"
PACE = 0.6             # seconds between calls; docs: "at least 20 calls every 10 seconds per IP address"
CHUNK = 500_000        # characters per js() read when pulling a big body out of the tab

class NotFound(Exception):
    """TVmaze answered 404: no such show/episode/person, or singlesearch/lookup found nothing."""

def on_tvmaze_tab():
    """API calls run as fetch() from a logged-out www.tvmaze.com tab (the docs: every endpoint is CORS enabled)."""
    try:
        if js("location.origin") == "https://www.tvmaze.com":
            return
    except Exception:
        pass
    new_tab("https://www.tvmaze.com/robots.txt")   # tiny allowed page on the site
    wait_for_load()

START_JS = """(() => { window.__tm = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__tm = {status: r.status, len: t.length, body: t}; })
    .catch(e => { window.__tm = {status: 0, len: 0, body: '', err: String(e)}; });
  return 1; })()"""

def api(path, params=None, tries=3):
    """Serial GET of api.tvmaze.com<path>. Parsed JSON; NotFound on 404; one 10 s back-off on 429, then stops;
    retries 5xx/network errors with backoff, then raises (so a failure never looks like an empty result)."""
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    for attempt in range(tries):
        js(START_JS % json.dumps(url))
        t0 = time.time()
        while not (meta := js("window.__tm && {status: window.__tm.status, len: window.__tm.len, err: window.__tm.err}")):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__tm.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__tm = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            return json.loads(body)
        if status == 404:
            raise NotFound(f"{url}: {body[:120]}")
        if status == 429:
            if attempt == 0:
                time.sleep(10)   # docs: back off a few seconds and retry; once only
                continue
            raise SystemExit(f"HTTP 429 twice on {url}: stop and slow down, do not work around it")
        if (status >= 500 or status == 0) and attempt < tries - 1:
            time.sleep(5 * 2 ** attempt)
            continue
        raise RuntimeError(f"{url}: HTTP {status}: {meta.get('err') or body[:200]}")

def ep_row(e):
    return {
        "id": e["id"], "season": e["season"], "number": e["number"], "type": e["type"], "name": e["name"],
        "airdate": e["airdate"], "airstamp": e["airstamp"], "runtime": e["runtime"],
        "rating": e["rating"]["average"], "url": e["url"],
    }

on_tvmaze_tab()
now = datetime.now(timezone.utc)
for sid in SHOWS:
    show = api(f"/shows/{sid}", {"embed[]": ["seasons", "nextepisode", "previousepisode"]})
    seasons = show["_embedded"]["seasons"]
    eps = [ep_row(e) for e in api(f"/shows/{sid}/episodes", {"specials": 1})]   # specials=1 adds specials
    regular = [e for e in eps if e["type"] == "regular"]
    aired = [e for e in regular if e["airstamp"] and datetime.fromisoformat(e["airstamp"]) <= now]
    print(f"\n#{sid} {show['name']} ({show['status']}): {len(seasons)} seasons, {len(regular)} regular episodes "
          f"({len(aired)} aired), {len(eps) - len(regular)} specials")
    for s in seasons[:3] + (["..."] if len(seasons) > 4 else []) + seasons[-1:] * (len(seasons) > 3):
        if s == "...":
            print("   ...")
            continue
        n = sum(1 for e in regular if e["season"] == s["number"])
        print(f"   S{s['number']:<4} {n:>3} eps (episodeOrder {s['episodeOrder']})  {s['premiereDate']} -> {s['endDate']}")
    for e in regular[:2] + regular[-1:]:
        print(f"   {e['season']}x{e['number']:<3} {e['airdate']}  {e['name']}  rating {e['rating']}")
    for e in [e for e in eps if e["type"] != "regular"][:2]:
        print(f"   special ({e['type']}) S{e['season']} {e['airdate']}  {e['name']}")
    for key in ("previousepisode", "nextepisode"):
        e = show["_embedded"].get(key)   # absent when there is none (ended show, or nothing scheduled)
        code = e and (f"{e['season']}x{e['number']}" if e["number"] is not None else f"S{e['season']} special")
        print(f"   {key}: " + (f"{code} {e['name']} airstamp {e['airstamp']}" if e else "none"))

sid, season, number = BY_NUMBER
e = ep_row(api(f"/shows/{sid}/episodebynumber", {"season": season, "number": number}))
print("\nepisodebynumber:", json.dumps(e, indent=1))
try:
    api(f"/shows/{sid}/episodebynumber", {"season": season, "number": 99})
except NotFound as err:
    print("episodebynumber 2x99:", err)
```

Output observed on 2026-11-05:

```text

#526 The Office (Ended): 9 seasons, 202 regular episodes (202 aired), 1 specials
   S1      6 eps (episodeOrder 6)  2005-03-24 -> 2005-04-26
   S2     22 eps (episodeOrder 22)  2005-09-20 -> 2006-05-11
   S3     25 eps (episodeOrder 25)  2006-09-21 -> 2007-05-17
   ...
   S9     25 eps (episodeOrder 27)  2012-09-20 -> 2013-05-16
   1x1   2005-03-24  Pilot  rating 7.6
   1x2   2005-03-29  Diversity Day  rating 8.1
   9x25  2013-05-16  Finale (2)  rating 9
   special (insignificant_special) S9 2013-05-16  Retrospective
   previousepisode: 9x25 Finale (2) airstamp 2013-05-17T01:30:00+00:00
   nextepisode: none

#169 Breaking Bad (Ended): 5 seasons, 62 regular episodes (62 aired), 1 specials
   S1      7 eps (episodeOrder 7)  2008-01-20 -> 2008-03-09
   S2     13 eps (episodeOrder 13)  2009-03-08 -> 2009-05-31
   S3     13 eps (episodeOrder 13)  2010-03-21 -> 2010-06-13
   ...
   S5     16 eps (episodeOrder 16)  2012-07-15 -> 2019-10-11
   1x1   2008-01-20  Pilot  rating 8.3
   1x2   2008-01-27  Cat's in the Bag...  rating 7.9
   5x16  2013-09-29  Felina  rating 8
   special (significant_special) S5 2019-10-11  El Camino: A Breaking Bad Movie
   previousepisode: S5 special El Camino: A Breaking Bad Movie airstamp 2019-10-12T02:00:00+00:00
   nextepisode: none

#83 The Simpsons (Running): 38 seasons, 809 regular episodes (806 aired), 3 specials
   S1     13 eps (episodeOrder 13)  1989-12-17 -> 1990-05-13
   S2     22 eps (episodeOrder 22)  1990-10-11 -> 1991-07-11
   S3     24 eps (episodeOrder 24)  1991-09-19 -> 1992-08-27
   ...
   S38     8 eps (episodeOrder None)  2026-09-27 -> 2026-11-22
   1x1   1989-12-17  Simpsons Roasting on an Open Fire  rating 7.9
   1x2   1990-01-14  Bart the Genius  rating 7.5
   38x8   2026-11-22  Curb Your Expectations  rating None
   special (insignificant_special) S21 2010-01-10  The Simpsons 20th Anniversary Special - In 3-D! on Ice!
   special (insignificant_special) S24 2012-10-19  Stand Up to Cancer
   previousepisode: 38x5 Testing 1-2-3 airstamp 2026-11-02T01:00:00+00:00
   nextepisode: 38x6 The Kosmic Kruiser airstamp 2026-11-09T01:30:00+00:00

episodebynumber: {
 "id": 47646,
 "season": 2,
 "number": 1,
 "type": "regular",
 "name": "The Dundies",
 "airdate": "2005-09-20",
 "airstamp": "2005-09-21T01:00:00+00:00",
 "runtime": 30,
 "rating": 8.1,
 "url": "https://www.tvmaze.com/episodes/47646/the-office-2x01-the-dundies"
}
episodebynumber 2x99: https://api.tvmaze.com/shows/526/episodebynumber?season=2&number=99: {"name":"Not Found","message":"Unknown episode","code":0,"status":404}
```

### 3. Schedule: what airs on TV in one country, and what drops on streaming, for one day (browser, official API)

```python
import json, time, urllib.parse
from collections import Counter, defaultdict
from datetime import date

DATE = date.today().isoformat()   # YYYY-MM-DD; other formats are HTTP 422
COUNTRY = "US"                    # ISO 3166-1 alpha-2; the United Kingdom is GB (UK is HTTP 422)
PRIME = ("20:00", "23:00")        # local primetime window for the broadcast listing

API = "https://api.tvmaze.com"
PACE = 0.6             # seconds between calls; docs: "at least 20 calls every 10 seconds per IP address"
CHUNK = 500_000        # characters per js() read when pulling a big body out of the tab

class NotFound(Exception):
    """TVmaze answered 404: no such show/episode/person, or singlesearch/lookup found nothing."""

def on_tvmaze_tab():
    """API calls run as fetch() from a logged-out www.tvmaze.com tab (the docs: every endpoint is CORS enabled)."""
    try:
        if js("location.origin") == "https://www.tvmaze.com":
            return
    except Exception:
        pass
    new_tab("https://www.tvmaze.com/robots.txt")   # tiny allowed page on the site
    wait_for_load()

START_JS = """(() => { window.__tm = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__tm = {status: r.status, len: t.length, body: t}; })
    .catch(e => { window.__tm = {status: 0, len: 0, body: '', err: String(e)}; });
  return 1; })()"""

def api(path, params=None, tries=3):
    """Serial GET of api.tvmaze.com<path>. Parsed JSON; NotFound on 404; one 10 s back-off on 429, then stops;
    retries 5xx/network errors with backoff, then raises (so a failure never looks like an empty result)."""
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    for attempt in range(tries):
        js(START_JS % json.dumps(url))
        t0 = time.time()
        while not (meta := js("window.__tm && {status: window.__tm.status, len: window.__tm.len, err: window.__tm.err}")):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__tm.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__tm = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            return json.loads(body)
        if status == 404:
            raise NotFound(f"{url}: {body[:120]}")
        if status == 429:
            if attempt == 0:
                time.sleep(10)   # docs: back off a few seconds and retry; once only
                continue
            raise SystemExit(f"HTTP 429 twice on {url}: stop and slow down, do not work around it")
        if (status >= 500 or status == 0) and attempt < tries - 1:
            time.sleep(5 * 2 ** attempt)
            continue
        raise RuntimeError(f"{url}: HTTP {status}: {meta.get('err') or body[:200]}")

def channel(show, web=False):
    """Channel name; a show can have both a network and a webChannel, so say which one wins."""
    ch = (show.get("webChannel") or show.get("network")) if web else (show.get("network") or show.get("webChannel"))
    return (ch or {}).get("name", "?")

def code(e):
    return f"{e['season']}x{e['number']}" if e["number"] is not None else f"S{e['season']} special"

on_tvmaze_tab()

# 1. Broadcast/cable schedule for one country and day. The show is under e["show"].
tv = api("/schedule", {"country": COUNTRY, "date": DATE})
print(f"/schedule {COUNTRY} {DATE}: {len(tv)} episodes on {len({channel(e['show']) for e in tv})} channels")
by_ch = defaultdict(list)
for e in tv:
    if PRIME[0] <= e["airtime"] < PRIME[1]:     # airtime is local to the channel's country, airstamp is UTC
        by_ch[channel(e["show"])].append(f"{e['airtime']} {e['show']['name']} {code(e)}")
for ch in sorted(by_ch)[:8]:
    print(f"  {ch:<10} " + " | ".join(by_ch[ch]))
late = [e for e in tv if e["airdate"] != DATE]   # after-midnight airings belong to the previous broadcast day
print(f"  {len(late)} rows carry airdate != {DATE}, e.g.",
      json.dumps({k: late[0][k] for k in ("airdate", "airtime", "airstamp", "runtime", "url")} | {"show": late[0]["show"]["name"]}) if late else "none")

# 2. Streaming schedule. The show is under e["_embedded"]["show"].
#    No country = local + global web channels; country=XX = only that country's local channels; country="" = only global ones.
for label, params in [("all", {"date": DATE}), (COUNTRY + " local", {"date": DATE, "country": COUNTRY}),
                      ("global", {"date": DATE, "country": ""})]:
    web = api("/schedule/web", params)
    top = Counter(channel(e["_embedded"]["show"], web=True) for e in web).most_common(5)
    print(f"/schedule/web {label}: {len(web)} episodes; top channels {top}")
    if label == "global":
        for e in [e for e in web if channel(e["_embedded"]["show"], web=True) == "Netflix"][:4]:
            print(f"  Netflix  {e['_embedded']['show']['name']} {code(e)} {e['name']!r} airstamp {e['airstamp']}")

try:
    api("/schedule", {"country": "UK", "date": DATE})
except RuntimeError as err:
    print("country=UK:", err)
```

Output observed on 2026-11-05:

```text
/schedule US 2026-11-05: 80 episodes on 26 channels
  A&E        21:00 After the First 48 13x3 | 22:00 Killer Investigations 2x3
  ABC        20:00 9-1-1 10x4 | 21:00 9-1-1: Nashville 2x4 | 22:00 Grey's Anatomy 23x4
  AMC        21:00 TNA iMPACT! 2026x45
  BYUtv      20:30 Studio C 23x3
  Bravo      20:00 The Real Housewives of Orange County 20x18 | 21:15 Southern Charm S12 special | 21:45 Watch What Happens Live 23x180
  CBS        20:00 Georgie & Mandy's First Marriage 3x5 | 20:31 Eternally Yours 1x5 | 21:00 Elsbeth 4x4 | 22:00 Cupertino 1x5
  FOX        20:00 Hell's Kitchen 25x7 | 21:02 Special Forces: World's Toughest Test 5x7
  HBO        21:00 War 1x6
  2 rows carry airdate != 2026-11-05, e.g. {"airdate": "2026-11-04", "airtime": "00:35", "airstamp": "2026-11-05T05:35:00+00:00", "runtime": 60, "url": "https://www.tvmaze.com/episodes/3798341/late-night-with-seth-meyers-2026-11-04-john-malkovich-gabby-windey", "show": "Late Night with Seth Meyers"}
/schedule/web all: 253 episodes; top channels [('Tencent QQ', 78), ('iQIYI', 78), ('Mango TV', 13), ('Youku', 10), ('YouTube', 7)]
/schedule/web US local: 13 episodes; top channels [('ABC News Live', 4), ('Peacock', 2), ('NBC.com', 2), ('Hulu', 2), ('CBS News', 1)]
/schedule/web global: 106 episodes; top channels [('iQIYI', 78), ('YouTube', 7), ('Netflix', 6), ('HBO Max', 3), ('Prime Video', 2)]
  Netflix  Black Doves 2x1 'Black Door' airstamp 2026-11-05T12:00:00+00:00
  Netflix  Black Doves 2x2 'Put Your Head on my Shoulder' airstamp 2026-11-05T12:00:00+00:00
  Netflix  Black Doves 2x3 'P Is for Poison' airstamp 2026-11-05T12:00:00+00:00
  Netflix  Black Doves 2x4 'The Opportunity to Become Savage' airstamp 2026-11-05T12:00:00+00:00
country=UK: https://api.tvmaze.com/schedule?country=UK&date=2026-11-05: HTTP 422: {"name":"Unprocessable entity","message":"Not a valid ISO country code","code":0,"status":422}
```

### 4. Cast: main cast, voice cast, one episode's guest cast, one person's credits (browser, official API)

```python
import json, time, urllib.parse
from collections import Counter

SHOW = 526          # The Office (US); show ids come from block 1
VOICE_SHOW = 83     # The Simpsons: a voice cast
EPISODE = 47640     # The Office 1x01 "Pilot" (episode ids come from block 2)
PERSON_QUERY = "rainn wilson"
TOP = 10

API = "https://api.tvmaze.com"
PACE = 0.6             # seconds between calls; docs: "at least 20 calls every 10 seconds per IP address"
CHUNK = 500_000        # characters per js() read when pulling a big body out of the tab

class NotFound(Exception):
    """TVmaze answered 404: no such show/episode/person, or singlesearch/lookup found nothing."""

def on_tvmaze_tab():
    """API calls run as fetch() from a logged-out www.tvmaze.com tab (the docs: every endpoint is CORS enabled)."""
    try:
        if js("location.origin") == "https://www.tvmaze.com":
            return
    except Exception:
        pass
    new_tab("https://www.tvmaze.com/robots.txt")   # tiny allowed page on the site
    wait_for_load()

START_JS = """(() => { window.__tm = null;
  fetch(%s, {credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__tm = {status: r.status, len: t.length, body: t}; })
    .catch(e => { window.__tm = {status: 0, len: 0, body: '', err: String(e)}; });
  return 1; })()"""

def api(path, params=None, tries=3):
    """Serial GET of api.tvmaze.com<path>. Parsed JSON; NotFound on 404; one 10 s back-off on 429, then stops;
    retries 5xx/network errors with backoff, then raises (so a failure never looks like an empty result)."""
    url = API + path + ("?" + urllib.parse.urlencode(params, doseq=True) if params else "")
    for attempt in range(tries):
        js(START_JS % json.dumps(url))
        t0 = time.time()
        while not (meta := js("window.__tm && {status: window.__tm.status, len: window.__tm.len, err: window.__tm.err}")):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__tm.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__tm = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            return json.loads(body)
        if status == 404:
            raise NotFound(f"{url}: {body[:120]}")
        if status == 429:
            if attempt == 0:
                time.sleep(10)   # docs: back off a few seconds and retry; once only
                continue
            raise SystemExit(f"HTTP 429 twice on {url}: stop and slow down, do not work around it")
        if (status >= 500 or status == 0) and attempt < tries - 1:
            time.sleep(5 * 2 ** attempt)
            continue
        raise RuntimeError(f"{url}: HTTP {status}: {meta.get('err') or body[:200]}")

def cast_row(c):
    p, ch = c["person"], c["character"]
    return {"person": p["name"], "person_id": p["id"], "character": ch["name"], "character_id": ch["id"],
            "self": c["self"], "voice": c["voice"], "country": (p.get("country") or {}).get("code"),
            "birthday": p["birthday"], "person_url": p["url"]}

on_tvmaze_tab()

# 1. Main cast, ordered by the character's number of appearances (docs).
cast = [cast_row(c) for c in api(f"/shows/{SHOW}/cast")]
print(f"show {SHOW} main cast: {len(cast)}")
for r in cast[:TOP]:
    print(f"  {r['person']:<22} as {r['character']}")
print(json.dumps(cast[0], indent=1))

# 2. Animated show: voice=True rows, and one person can play many characters.
vc = [cast_row(c) for c in api(f"/shows/{VOICE_SHOW}/cast")]
per_person = Counter(r["person"] for r in vc)
print(f"\nshow {VOICE_SHOW} cast rows: {len(vc)} ({sum(r['voice'] for r in vc)} voice, {sum(r['self'] for r in vc)} self), "
      f"{len(per_person)} people; most characters: {per_person.most_common(3)}")

# 3. Guest cast of one episode (main cast who appear can be listed here too).
guests = [cast_row(c) for c in api(f"/episodes/{EPISODE}/guestcast")]
print(f"\nepisode {EPISODE} guest cast: {len(guests)}: " + ", ".join(f"{g['person']} ({g['character']})" for g in guests[:6]))

# 4. A person's show credits: people search, then /people/<id>/castcredits with the show embedded.
hits = api("/search/people", {"q": PERSON_QUERY})
pid, name = hits[0]["person"]["id"], hits[0]["person"]["name"]
credits = api(f"/people/{pid}/castcredits", {"embed": "show"})
print(f"\n{name} (#{pid}, score {hits[0]['score']:.2f}): {len(credits)} show credits")
for c in credits[:6]:
    s = c["_embedded"]["show"]
    print(f"  {s['name']:<32} {s['premiered']}  as {c['_links']['character']['name']}{'  (self)' if c['self'] else ''}{'  (voice)' if c['voice'] else ''}")
```

Output observed on 2026-11-05:

```text
show 526 main cast: 25
  Rainn Wilson           as Dwight Kurt Schrute
  John Krasinski         as Jim Halpert
  Leslie David Baker     as Stanley Hudson
  Phyllis Smith          as Phyllis Lapin-Vance
  Jenna Fischer          as Pam Beesly
  Brian Baumgartner      as Kevin Malone
  Angela Kinsey          as Angela Martin
  Oscar Nuñez            as Oscar Martinez
  Kate Flannery          as Meredith Palmer
  Creed Bratton          as Creed Bratton
{
 "person": "Rainn Wilson",
 "person_id": 19396,
 "character": "Dwight Kurt Schrute",
 "character_id": 85556,
 "self": false,
 "voice": false,
 "country": "US",
 "birthday": "1966-01-20",
 "person_url": "https://www.tvmaze.com/people/19396/rainn-wilson"
}

show 83 cast rows: 1420 (1419 voice, 1 self), 6 people; most characters: [('Dan Castellaneta', 455), ('Hank Azaria', 422), ('Harry Shearer', 353)]

episode 47640 guest cast: 11: Melora Hardin (Jan Levinson), David Denman (Roy Anderson), Leslie David Baker (Stanley Hudson), Phyllis Smith (Phyllis Lapin-Vance), Brian Baumgartner (Kevin Malone), Angela Kinsey (Angela Martin)

Rainn Wilson (#19396, score 1.00): 8 show credits
  The Office                       2005-03-24  as Dwight Kurt Schrute
  Backstrom                        2015-01-22  as Det. Lt. Everett Backstrom
  Independent Spirit Awards        1986-03-22  as Host  (self)
  Star Trek: Short Treks           2018-10-04  as Harry Mudd
  Utopia                           2020-09-25  as Dr. Michael Stearns
  We Are the Champions             2020-11-17  as Narrator  (self)  (voice)
```

### 5. Same data from the site: search results, episode guide, cast page (browser, HTML)

```python
import json, time, urllib.parse

QUERY = "the office"
SHOW_URL = "https://www.tvmaze.com/shows/526/the-office"   # canonical show URL (API field `url`)

def open_page(url):
    """Logged-out page load on www.tvmaze.com; stops if the page is not what was asked for."""
    if not js("location.origin") == "https://www.tvmaze.com":
        new_tab(url)
    else:
        goto_url(url)
    wait_for_load()
    title = js("document.title")
    if not js("location.href").startswith("https://www.tvmaze.com/") or "TVmaze" not in title:
        raise SystemExit(f"unexpected page at {js('location.href')}: {title!r}; stop (challenge or block)")
    time.sleep(1)   # one page at a time

SEARCH_JS = """[...document.querySelectorAll('a[href^="/shows/"]')].filter(a => a.innerText.trim())
  .map(a => ({name: a.innerText.trim(), href: a.href,
              line: (a.closest('.cell, article, div').parentElement.innerText || '').split('\\n').map(s => s.trim()).filter(Boolean).slice(0, 3)}))"""

EPISODES_JS = """[...document.querySelectorAll('section.season')].map(sec => {
  const h = sec.previousElementSibling;
  return {season: h ? h.innerText.trim() : null,
          rows: [...sec.querySelectorAll('article.episode-row')].map(r => {
            const c = r.querySelectorAll(':scope > div');
            const a = r.querySelector('a[href^="/episodes/"]');
            return {number: c[0].innerText.trim(), date: c[1].innerText.trim(), name: a ? a.innerText.trim() : c[2].innerText.trim(),
                    score: (c[3] && c[3].querySelector('a span') || {}).innerText || null, href: a && a.href};
          })};
})"""

CAST_JS = """[...document.querySelectorAll('h2 a[href^="/people/"]')].map(a => {
  const cell = a.closest('.cell');
  const ch = cell.querySelector('a[href^="/characters/"]');
  return {person: a.innerText.trim(), character: ch ? ch.innerText.trim() : cell.innerText.split('\\n').slice(1).join(' ').trim(), person_url: a.href};
})"""

open_page("https://www.tvmaze.com/search?" + urllib.parse.urlencode({"q": QUERY}))
hits = js(SEARCH_JS)
print(f"site search {QUERY!r}: {len(hits)} shows on page 1")
for h in hits[:4]:
    print("  ", h["href"], "|", " / ".join(h["line"]))

open_page(SHOW_URL + "/episodes")
seasons = js(EPISODES_JS)
print(f"\nepisode guide: {len(seasons)} sections, {sum(len(s['rows']) for s in seasons)} rows")
for s in seasons[-2:]:   # page lists the newest season first; the last section is Specials when there are any
    print(f"  {s['season']}: {len(s['rows'])} rows; first {json.dumps(s['rows'][-1] if s['season'] != 'Specials' else s['rows'][0])}")

open_page(SHOW_URL + "/cast")
cast = js(CAST_JS)
print(f"\ncast page: {len(cast)} people")
for c in cast[:5]:
    print(f"  {c['person']:<20} as {c['character']}")
```

Output observed on 2026-11-05:

```text
site search 'the office': 10 shows on page 1
   https://www.tvmaze.com/shows/526/the-office | The Office (NBC , 2005 - 2013) / Previous episode: Finale (2) / Starring: Rainn Wilson John Krasinski Leslie David Baker
   https://www.tvmaze.com/shows/1292/the-office | The Office (BBC Two , 2001 - 2003) / Previous episode: Christmas Special: Part 2 / Starring: Ricky Gervais Martin Freeman Mackenzie Crook
   https://www.tvmaze.com/shows/69044/the-office | The Office (Prime Video, 2024 - 2024) / Previous episode: The Sales Report / Starring: Felicity Ward Edith Poor Steen Raskopoulos
   https://www.tvmaze.com/shows/57704/the-office | The Office (JioHotstar , 2019 - 2019) / Previous episode: Founder's Day / Starring: Mukul Chadda Gopal Dutt Sayandeep Sengupta

episode guide: 10 sections, 203 rows
  Season 1: 6 rows; first {"number": "1", "date": "Mar 24, 2005", "name": "Pilot", "score": "7.6", "href": "https://www.tvmaze.com/episodes/47640/the-office-1x01-pilot"}
  Specials: 1 rows; first {"number": "S", "date": "May 16, 2013", "name": "Retrospective", "score": "6", "href": "https://www.tvmaze.com/episodes/47839/the-office-s09-special-retrospective"}

cast page: 25 people
  Rainn Wilson         as Dwight Kurt Schrute
  John Krasinski       as Jim Halpert
  Leslie David Baker   as Stanley Hudson
  Phyllis Smith        as Phyllis Lapin-Vance
  Jenna Fischer        as Pam Beesly
```

## URL patterns (all observed)

| URL | What it is |
|---|---|
| `api.tvmaze.com/search/shows?q=<q>` | up to 10 `{score, show}`, best first; `page=` is ignored |
| `api.tvmaze.com/singlesearch/shows?q=<q>[&embed=episodes]` | one show, or 404 with body `null` |
| `api.tvmaze.com/lookup/shows?imdb=<tt id>` / `?thetvdb=<id>` | one show by external id |
| `api.tvmaze.com/shows/<id>?embed[]=seasons&embed[]=nextepisode&embed[]=previousepisode` | show plus embeds under `_embedded`; `embed[]=episodes`, `embed[]=cast` also work |
| `api.tvmaze.com/shows/<id>/episodes[?specials=1]` | all episodes in airing order; specials only with `specials=1` |
| `api.tvmaze.com/shows/<id>/seasons` | seasons with `episodeOrder`, `premiereDate`, `endDate` |
| `api.tvmaze.com/shows/<id>/episodebynumber?season=<s>&number=<n>` | one episode, or 404 `Unknown episode` |
| `api.tvmaze.com/schedule?country=<ISO2>&date=<YYYY-MM-DD>` | broadcast/cable day; defaults US and today |
| `api.tvmaze.com/schedule/web?date=<d>[&country=<ISO2>]` | streaming day; no country = all, `country=XX` = local, `country=` = global only |
| `api.tvmaze.com/shows/<id>/cast` | main cast, ordered by appearances |
| `api.tvmaze.com/episodes/<id>/guestcast` | guest cast of one episode |
| `api.tvmaze.com/search/people?q=<q>` / `people/<id>/castcredits?embed=show` | person search, show credits |
| `www.tvmaze.com/search?q=<q>[&page=N]` | site search, 10 shows per page, paginated |
| `www.tvmaze.com/shows/<id>/<slug>/episodes` / `/cast` | episode guide (newest season first, Specials last) / cast |

## Fields

| Object | Keys this task needs |
|---|---|
| Show | `id`, `name`, `type`, `language`, `genres`, `status` (`Running`, `Ended`, `In Development`, ...), `premiered`, `ended`, `runtime`, `schedule.time` / `.days`, `rating.average`, `network` or `webChannel` (`name`, `country.code`, `country.timezone`), `externals.imdb` / `.thetvdb` / `.tvrage`, `image.medium` / `.original`, `summary` (HTML), `url`, `_links.previousepisode` / `.nextepisode` |
| Episode | `id`, `season`, `number` (`null` for specials), `type` (`regular`, `significant_special`, `insignificant_special`), `name`, `airdate`, `airtime` (local), `airstamp` (UTC ISO), `runtime`, `rating.average`, `summary` (HTML or `null`), `url` |
| Season | `id`, `number`, `name`, `episodeOrder` (can be `null`), `premiereDate`, `endDate`, `network`, `webChannel` |
| Cast item | `person` (`id`, `name`, `country`, `birthday`, `deathday`, `gender`, `url`), `character` (`id`, `name`, `url`), `self`, `voice` |
| Cast credit | `self`, `voice`, `_links.show`, `_links.character.name`, `_embedded.show` with `embed=show` |
| Schedule row | an Episode plus the show: `show` on `/schedule`, `_embedded.show` on `/schedule/web` |

## Gotchas

- **API search stops at 10.** `q=the` and `q=the&page=2` returned the same 10 ids. For more matches use a more specific query, `/lookup/shows` by IMDb/TheTVDB id, or the site's paginated `/search?q=...&page=N` (block 5).
- **Same-name shows.** `the office` returned five shows named The Office (NBC, BBC Two, Prime Video, JioHotstar, CBS). `singlesearch` picks one, and the docs say it is undefined which one wins when names are identical (`top gear` gave BBC One #522). Pick by `network`/`webChannel`, `premiered` or external id.
- **`ended` and season `endDate` count specials.** Breaking Bad shows `ended` 2019-10-11 and season 5 `endDate` 2019-10-11 (El Camino, a `significant_special`); the last regular episode, Felina 5x16, aired 2013-09-29. `previousepisode` can be a special with `number: null`.
- **Episode lists include announced future episodes.** The Simpsons: 809 regular rows, 806 aired, 38x8 dated 2026-11-22. Filter on `airstamp` (block 2).
- **`episodeOrder` is not the row count.** The Office season 9 says 27 with 25 regular rows; the current Simpsons season has `null`.
- **Schedule show key differs:** `e["show"]` on `/schedule`, `e["_embedded"]["show"]` on `/schedule/web`.
- **Schedule day = broadcast day.** `/schedule?country=US&date=2026-11-05` held 2 rows dated 2026-11-04 (Late Night with Seth Meyers, airtime 00:35, airstamp 2026-11-05T05:35Z). `airtime` is local to the channel's country, `airstamp` is UTC; streaming rows can have `airtime: ""`.
- **Country codes and dates are strict:** `country=UK` is HTTP 422 `Not a valid ISO country code` (use `GB`); a date like `11/05/2026` is HTTP 422 `Not a valid ISO date`.
- **Netflix is a global web channel:** it is missing from `/schedule/web?country=US` (13 rows) and present with no country (253 rows) or `country=` (106 rows). A show can have both `network` and `webChannel`; block 3 prefers `webChannel` for streaming rows.
- **The site's /schedule page is a primetime grid** (20:00-22:30 columns for the chosen country); `/schedule` in the API is the whole day (80 US rows).
- **Cast is main cast only;** guests are per episode, and main cast can show up there too (Leslie David Baker and Phyllis Smith are in the Pilot's guest cast). Animated shows list every character: The Simpsons has 1,420 cast rows from 6 people (Dan Castellaneta 455), `voice: true`.
- **Ratings:** the API gives `rating.average` only; vote counts appear only on the site (episode guide rating dropdown, e.g. `(16 votes)`).
- **Summaries are HTML** (`<p>...</p>`) or `null`.
- **404 bodies differ:** a singlesearch no-match is a 404 with body `null`; other misses are JSON `{"name":"Not Found","message":"Unknown episode",...}`.
- **CORS:** a cross-origin `fetch()` exposes only `cache-control`, `content-type` and sometimes `last-modified`; no rate-limit headers are readable, so pace yourself. Open api.tvmaze.com/robots.txt as a page; a cross-origin `fetch()` of it failed with `TypeError: Failed to fetch`.
- On a repeated 429 or a challenge page, stop. Do not retry with a different user agent, session or IP.

## What does not work

- **More than 10 API search results:** no paging parameter (see Gotchas).
- **Follow, watched, voting and user lists:** need an account (`js-needlogin` on the site) and `/users/*/*/followed` and `/users/*/*/watched` are disallowed by robots.txt; not attempted.
- **`/stats` and `/offer`:** disallowed by robots.txt; not used.
- **Calling faster than the documented limit:** 429; not attempted beyond the paced calls above.
