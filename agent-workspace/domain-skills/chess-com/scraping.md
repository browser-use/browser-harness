# Chess.com - Player Profiles, Ratings and Monthly Game Archives (official PubAPI)

Field-tested against api.chess.com on 2026-11-01 using a Browser Use cloud browser, logged out. Every call is a same-origin `fetch()` from an api.chess.com tab. No CAPTCHA, 403 or 429 across about 40 calls.

robots.txt (fetched 2026-11-01): api.chess.com is `User-agent: *` / `Disallow: /`; this skill uses it only under the official-API exception, because Chess.com documents these `/pub/...` endpoints as its public Published-Data API (https://www.chess.com/news/view/published-data-api, a path www.chess.com's robots.txt allows) and says they "can be called, by any kind of client or browsers". www.chess.com disallows `/games/archive`, `/stats/`, `/game/` (plus their `/*/` forms) and `/download/pgn` for `User-agent: *`, so this skill never loads chess.com site pages.

## Quick summary

- **No scraping.** Three public JSON endpoints and one PGN endpoint cover the task. No key, no cookies, `access-control-allow-origin: *`:
  - `https://api.chess.com/pub/player/<user>` - profile: `player_id`, title, status, name, country, joined, last online, followers.
  - `https://api.chess.com/pub/player/<user>/stats` - ratings per game type (`chess_blitz`, `chess_bullet`, `chess_rapid`, `chess_daily`, `chess960_daily`) with current, best and W/L/D, plus `fide`, `tactics`, `puzzle_rush`.
  - `https://api.chess.com/pub/player/<user>/games/archives` - every month with games, as URLs, oldest first.
  - `https://api.chess.com/pub/player/<user>/games/<YYYY>/<MM>` (JSON, one object per game incl. its PGN) and `.../<YYYY>/<MM>/pgn` (one multi-game PGN file).
- **Serial calls only.** Chess.com's docs: "Your serial access rate is unlimited", but parallel requests may get "429 Too Many Requests", and abnormal activity can get a client blocked. The blocks wait for each response, pause 0.3 s, retry 429/5xx with backoff, and raise on anything else.
- **Archives can be big.** hikaru: 154 months; 2026/10 alone is 583 games, 2.4 MB of JSON or 1.8 MB of PGN. `get()` pulls large bodies out of the tab in 500 KB slices.
- Unknown users and malformed URLs return HTTP 404 with JSON `{"code":0,"message":...}`. Months with no games (future or before the account existed) return HTTP 200 `{"games":[]}`.

## What works

All blocks share the same helpers: `on_api_tab()` opens `https://api.chess.com/robots.txt` once (a tiny page on the API host, so `fetch()` is same-origin) and later blocks reuse it. `get(path)` fetches `https://api.chess.com/pub/<path>`, keeps the body in the page, and reads it back in 500 KB slices. It returns `(meta, text)`, with `text = None` on 404/410, retries 429/5xx (honoring a numeric `Retry-After`), and otherwise raises. A failed call never comes back as an empty result.

### 1. Profiles and ratings for a list of usernames (browser)

```python
import json, time, urllib.parse
from datetime import datetime, timezone

USERS = ["hikaru", "MagnusCarlsen", "erik", "zzqx-no-such-user-98712"]

API = "https://api.chess.com/pub/"
PAUSE = 0.3        # seconds between calls; the API asks for serial calls, never parallel
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab

def on_api_tab():
    """All calls run as same-origin fetch() in a logged-out api.chess.com tab; reuse it if already there."""
    try:
        if js("location.origin") == "https://api.chess.com":
            return
    except Exception:
        pass
    new_tab("https://api.chess.com/robots.txt")   # tiny page on the API host
    wait_for_load()

FETCH_JS = """(async () => {
  try {
    const r = await fetch(%s, {credentials: 'omit'});
    window.__cc = await r.text();
    return {status: r.status, url: r.url, len: window.__cc.length, type: r.headers.get('content-type'),
            disposition: r.headers.get('content-disposition'), retry_after: r.headers.get('retry-after')};
  } catch (e) { window.__cc = ''; return {status: 0, error: String(e)}; }
})()"""

def get(path, tries=4):
    """Serial GET of api.chess.com/pub/<path>. Returns (meta, text); text is None on 404/410.
    Retries 429/5xx with backoff, then raises: a failed call never looks like an empty result."""
    url = API + path
    for attempt in range(tries):
        meta = js(FETCH_JS % json.dumps(url))
        status = meta["status"]
        if status in (200, 404, 410):
            text = None
            if status == 200:
                text = "".join(js(f"window.__cc.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
            js("window.__cc = ''")
            time.sleep(PAUSE)
            return meta, text
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('error', '')}; stopping")
        ra = meta.get("retry_after") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def get_json(path):
    meta, text = get(path)
    return None if text is None else json.loads(text)

def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if isinstance(ts, int) else None

def player(username):
    u = urllib.parse.quote(username.strip().lower())   # usernames are case-insensitive; lowercase skips a 301
    prof = get_json(f"player/{u}")
    if prof is None:
        return None
    stats = get_json(f"player/{u}/stats") or {}
    ratings = {}
    for key, s in stats.items():
        if not (key.startswith("chess") and isinstance(s, dict)):
            continue
        last, best, rec = s.get("last", {}), s.get("best", {}), s.get("record", {})
        ratings[key] = {"rating": last.get("rating"), "rd": last.get("rd"), "as_of": iso(last.get("date")),
                        "best": best.get("rating"), "best_on": iso(best.get("date")), "best_game": best.get("game"),
                        "win": rec.get("win"), "loss": rec.get("loss"), "draw": rec.get("draw")}
    return {
        "username": prof.get("username"),
        "url": prof.get("url"),
        "player_id": prof.get("player_id"),
        "title": prof.get("title"),
        "status": prof.get("status"),
        "name": prof.get("name"),
        "country": (prof.get("country") or "").rsplit("/", 1)[-1] or None,
        "joined": iso(prof.get("joined")),
        "last_online": iso(prof.get("last_online")),
        "followers": prof.get("followers"),
        "fide": stats.get("fide"),
        "tactics_high": (stats.get("tactics", {}).get("highest") or {}).get("rating"),
        "puzzle_rush_best": (stats.get("puzzle_rush", {}).get("best") or {}).get("score"),
        "ratings": ratings,
    }

on_api_tab()
rows, missing = [], []
for name in USERS:
    row = player(name)
    (rows.append(row) if row else missing.append(name))
print(json.dumps({"requested": len(USERS), "found": len(rows), "missing": missing}))
for r in rows:
    print(r["username"], "|", r["title"], "|", r["status"], "|", r["country"], "| joined", r["joined"], "| followers", r["followers"],
          "| fide", r["fide"], "|", ", ".join(f"{k.removeprefix('chess_')}={v['rating']}" for k, v in r["ratings"].items()))
print(json.dumps(rows[0], indent=1, ensure_ascii=False))
```

Output observed on 2026-11-01:

```text
{"requested": 4, "found": 3, "missing": ["zzqx-no-such-user-98712"]}
hikaru | GM | premium | US | joined 2014-01-06T21:20Z | followers 1422496 | fide 2814 | daily=2239, chess960_daily=1231, rapid=2838, bullet=3393, blitz=3453
magnuscarlsen | GM | premium | NO | joined 2010-08-26T21:05Z | followers 327751 | fide 2882 | rapid=2941, bullet=3344, blitz=3404
erik | None | staff | US | joined 2007-05-07T16:50Z | followers 9325 | fide 1707 | daily=1493, chess960_daily=1440, rapid=1904, bullet=1713, blitz=1912
{
 "username": "hikaru",
 "url": "https://www.chess.com/member/Hikaru",
 "player_id": 15448422,
 "title": "GM",
 "status": "premium",
 "name": "Hikaru Nakamura",
 "country": "US",
 "joined": "2014-01-06T21:20Z",
 "last_online": "2026-11-01T17:33Z",
 "followers": 1422496,
 "fide": 2814,
 "tactics_high": 2730,
 "puzzle_rush_best": 123,
 "ratings": {
  "chess_daily": {
   "rating": 2239,
   "rd": 103,
   "as_of": "2026-02-08T15:03Z",
   "best": 2464,
   "best_on": "2014-04-10T13:32Z",
   "best_game": "https://www.chess.com/game/daily/84604826",
   "win": 73,
   "loss": 11,
   "draw": 4
  },
  "chess960_daily": {
   "rating": 1231,
   "rd": 230,
   "as_of": "2015-10-10T06:23Z",
   "best": 1489,
   "best_on": "2014-04-09T19:50Z",
   "best_game": "https://www.chess.com/game/daily/87191830",
   "win": 1,
   "loss": 2,
   "draw": 0
  },
  "chess_rapid": {
   "rating": 2838,
   "rd": 44,
   "as_of": "2026-08-15T12:18Z",
   "best": 2927,
   "best_on": "2022-02-26T19:08Z",
   "best_game": "https://www.chess.com/game/live/141332265952",
   "win": 205,
   "loss": 69,
   "draw": 220
  },
  "chess_bullet": {
   "rating": 3393,
   "rd": 26,
   "as_of": "2026-10-31T18:59Z",
   "best": 3570,
   "best_on": "2020-11-11T23:07Z",
   "best_game": "https://www.chess.com/game/live/5710095242",
   "win": 17232,
   "loss": 2539,
   "draw": 1186
  },
  "chess_blitz": {
   "rating": 3453,
   "rd": 33,
   "as_of": "2026-10-31T19:39Z",
   "best": 3503,
   "best_on": "2026-10-06T16:21Z",
   "best_game": "https://www.chess.com/game/live/184580310677",
   "win": 36083,
   "loss": 5550,
   "draw": 4382
  }
 }
}
```

### 2. Monthly archives: newest months as game rows with PGN (browser)

```python
import json, time, urllib.parse
from datetime import datetime, timezone

USER = "hikaru"
LAST_MONTHS = 2    # newest N monthly archives; hikaru's are about 2.4 MB of JSON each


API = "https://api.chess.com/pub/"
PAUSE = 0.3        # seconds between calls; the API asks for serial calls, never parallel
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab

def on_api_tab():
    """All calls run as same-origin fetch() in a logged-out api.chess.com tab; reuse it if already there."""
    try:
        if js("location.origin") == "https://api.chess.com":
            return
    except Exception:
        pass
    new_tab("https://api.chess.com/robots.txt")   # tiny page on the API host
    wait_for_load()

FETCH_JS = """(async () => {
  try {
    const r = await fetch(%s, {credentials: 'omit'});
    window.__cc = await r.text();
    return {status: r.status, url: r.url, len: window.__cc.length, type: r.headers.get('content-type'),
            disposition: r.headers.get('content-disposition'), retry_after: r.headers.get('retry-after')};
  } catch (e) { window.__cc = ''; return {status: 0, error: String(e)}; }
})()"""

def get(path, tries=4):
    """Serial GET of api.chess.com/pub/<path>. Returns (meta, text); text is None on 404/410.
    Retries 429/5xx with backoff, then raises: a failed call never looks like an empty result."""
    url = API + path
    for attempt in range(tries):
        meta = js(FETCH_JS % json.dumps(url))
        status = meta["status"]
        if status in (200, 404, 410):
            text = None
            if status == 200:
                text = "".join(js(f"window.__cc.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
            js("window.__cc = ''")
            time.sleep(PAUSE)
            return meta, text
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('error', '')}; stopping")
        ra = meta.get("retry_after") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def get_json(path):
    meta, text = get(path)
    return None if text is None else json.loads(text)

def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%MZ") if isinstance(ts, int) else None

DRAWS = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}

def game_row(g, me):
    white, black = g.get("white", {}), g.get("black", {})
    color = "white" if white.get("username", "").lower() == me else "black"
    mine, opp = (white, black) if color == "white" else (black, white)
    res = mine.get("result")
    eco = g.get("eco") or ""
    return {
        "url": g.get("url"),
        "end": iso(g.get("end_time")),
        "time_class": g.get("time_class"),
        "time_control": g.get("time_control"),
        "rules": g.get("rules"),
        "rated": g.get("rated"),
        "color": color,
        "rating": mine.get("rating"),
        "opponent": opp.get("username"),
        "opp_rating": opp.get("rating"),
        "outcome": "win" if res == "win" else "draw" if res in DRAWS else "loss",
        "result": res,
        "opp_result": opp.get("result"),
        "accuracy": (g.get("accuracies") or {}).get(color),
        "opening": eco.rsplit("/", 1)[-1] or None,
        "pgn": g.get("pgn"),
    }

def months(user):
    """Archive URLs (oldest first) as [(YYYY, MM)], or None for an unknown user."""
    data = get_json(f"player/{urllib.parse.quote(user)}/games/archives")
    if data is None:
        return None
    return [tuple(u.rstrip("/").split("/")[-2:]) for u in data["archives"]]

def month_games(user, yyyy, mm):
    data = get_json(f"player/{urllib.parse.quote(user)}/games/{yyyy}/{mm}")
    if data is None:
        raise RuntimeError(f"{user} {yyyy}/{mm}: 404 for a month listed in archives")
    return [game_row(g, user) for g in data["games"]]

on_api_tab()
me = USER.strip().lower()
ms = months(me)
if ms is None:
    raise SystemExit(f"no such player: {USER}")
print(f"{me}: {len(ms)} monthly archives, {'/'.join(ms[0])} .. {'/'.join(ms[-1])}")
rows = []
for yyyy, mm in ms[-LAST_MONTHS:]:
    got = month_games(me, yyyy, mm)
    print(f"{yyyy}/{mm}: {len(got)} games")
    rows += got
summary = {}
for r in rows:
    s = summary.setdefault(r["time_class"], {"games": 0, "win": 0, "draw": 0, "loss": 0})
    s["games"] += 1
    s[r["outcome"]] += 1
print(json.dumps(summary))
last = rows[-1]
print(json.dumps({k: v for k, v in last.items() if k != "pgn"}, ensure_ascii=False))
print(last["pgn"][:400])
```

Output observed on 2026-11-01:

```text
hikaru: 154 monthly archives, 2014/01 .. 2026/10
2026/09: 509 games
2026/10: 583 games
{"blitz": {"games": 549, "win": 473, "draw": 41, "loss": 35}, "bullet": {"games": 543, "win": 412, "draw": 45, "loss": 86}}
{"url": "https://www.chess.com/game/live/186299800014", "end": "2026-10-31T19:39Z", "time_class": "blitz", "time_control": "180", "rules": "chess", "rated": true, "color": "white", "rating": 3453, "opponent": "Sina-Movahed", "opp_rating": 3299, "outcome": "win", "result": "win", "opp_result": "timeout", "accuracy": 84.31, "opening": "Sicilian-Defense-Canal-Attack...10.h3-Bh5-11.g4-Bg6-12.Nh4"}
[Event "Live Chess"]
[Site "Chess.com"]
[Date "2026.10.31"]
[Round "-"]
[White "Hikaru"]
[Black "Sina-Movahed"]
[Result "1-0"]
[CurrentPosition "8/6p1/6Pb/kP5P/8/8/3p4/3K1B2 b - - 7 79"]
[Timezone "UTC"]
[ECO "B51"]
[ECOUrl "https://www.chess.com/openings/Sicilian-Defense-Canal-Attack...10.h3-Bh5-11.g4-Bg6-12.Nh4"]
[UTCDate "2026.10.31"]
[UTCTime "19:32:56"]
[WhiteElo "3453"]
[BlackElo "3299"]
[Ti
```

### 3. Download a month as one PGN file (browser)

Saves Chess.com's own multi-game PGN under `chess-com-pgn/` in the current directory, named as the API names it (`Content-Disposition`), after checking that its game count matches the JSON archive for the same month.

```python
import json, os, re, time, urllib.parse

JOBS = [("erik", "2009", "10"), ("Hikaru", "2026", "10"), ("erik", "2031", "01"), ("zzqx-no-such-user-98712", "2026", "10")]  # (user, YYYY, MM)
OUT_DIR = "chess-com-pgn"


API = "https://api.chess.com/pub/"
PAUSE = 0.3        # seconds between calls; the API asks for serial calls, never parallel
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab

def on_api_tab():
    """All calls run as same-origin fetch() in a logged-out api.chess.com tab; reuse it if already there."""
    try:
        if js("location.origin") == "https://api.chess.com":
            return
    except Exception:
        pass
    new_tab("https://api.chess.com/robots.txt")   # tiny page on the API host
    wait_for_load()

FETCH_JS = """(async () => {
  try {
    const r = await fetch(%s, {credentials: 'omit'});
    window.__cc = await r.text();
    return {status: r.status, url: r.url, len: window.__cc.length, type: r.headers.get('content-type'),
            disposition: r.headers.get('content-disposition'), retry_after: r.headers.get('retry-after')};
  } catch (e) { window.__cc = ''; return {status: 0, error: String(e)}; }
})()"""

def get(path, tries=4):
    """Serial GET of api.chess.com/pub/<path>. Returns (meta, text); text is None on 404/410.
    Retries 429/5xx with backoff, then raises: a failed call never looks like an empty result."""
    url = API + path
    for attempt in range(tries):
        meta = js(FETCH_JS % json.dumps(url))
        status = meta["status"]
        if status in (200, 404, 410):
            text = None
            if status == 200:
                text = "".join(js(f"window.__cc.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
            js("window.__cc = ''")
            time.sleep(PAUSE)
            return meta, text
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('error', '')}; stopping")
        ra = meta.get("retry_after") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def get_json(path):
    meta, text = get(path)
    return None if text is None else json.loads(text)

def month_pgn(user, yyyy, mm):
    """Multi-game PGN for one month. Returns (filename, text), or None on 404/410 (unknown user or bad URL)."""
    if not (len(yyyy) == 4 and len(mm) == 2 and (yyyy + mm).isdigit()):
        raise ValueError("use a 4-digit year and a 2-digit month, e.g. '2026', '01' ('1' is a 404)")
    u = urllib.parse.quote(user.strip().lower())
    meta, text = get(f"player/{u}/games/{yyyy}/{mm}/pgn")
    if text is None:
        return None
    m = re.search(r'filename="?([^";]+)', meta.get("disposition") or "")
    name = os.path.basename(m.group(1)) if m else f"ChessCom_{u}_{yyyy}{mm}.pgn"
    return name, text

on_api_tab()
os.makedirs(OUT_DIR, exist_ok=True)
for user, yyyy, mm in JOBS:
    got = month_pgn(user, yyyy, mm)
    if got is None:
        print(user, yyyy, mm, "-> 404/410, nothing saved")
        continue
    name, text = got
    n_pgn = len(re.findall(r'^\[Event "', text, re.M))
    n_json = len(get_json(f"player/{user.lower()}/games/{yyyy}/{mm}")["games"])   # cross-check against the JSON archive
    if n_pgn != n_json:
        raise RuntimeError(f"{user} {yyyy}/{mm}: PGN has {n_pgn} games, JSON has {n_json}; not saving")
    if n_pgn == 0:
        print(user, yyyy, mm, "-> HTTP 200 but no games that month, nothing saved")
        continue
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    dates = sorted(set(re.findall(r'^\[UTCDate "([\d.]+)"\]', text, re.M)))
    print(f"{user} {yyyy}/{mm}: {n_pgn} games (JSON agrees), {len(text):,} chars -> {path} | UTCDate {dates[0]} .. {dates[-1]}")
```

Output observed on 2026-11-01:

```text
erik 2009/10: 42 games (JSON agrees), 58,402 chars -> chess-com-pgn/ChessCom_erik_200910.pgn | UTCDate 2009.08.26 .. 2009.10.31
Hikaru 2026/10: 583 games (JSON agrees), 1,776,596 chars -> chess-com-pgn/ChessCom_hikaru_202610.pgn | UTCDate 2026.10.02 .. 2026.10.31
erik 2031 01 -> HTTP 200 but no games that month, nothing saved
zzqx-no-such-user-98712 2026 10 -> 404/410, nothing saved
```

The saved files open in any PGN tool. The first game in `ChessCom_erik_200910.pgn` starts:

```text
[Event "Hello!"]
[Site "Chess.com"]
[Date "2009.09.17"]
...
[TimeControl "1/259200"]
[Termination "erik won by checkmate"]
[StartTime "21:40:19"]
[EndDate "2009.10.31"]
[EndTime "17:53:17"]
[Link "https://www.chess.com/game/daily/28103371"]

1. Nf3 d6 2. Nc3 g6 3. e4 Bg7 ...
```

## Fields

Block 1 row:

| Key | Source | Notes |
|---|---|---|
| `username` | profile `username` | always lowercase; `url` keeps the display case (`/member/Hikaru`) |
| `player_id` | profile `player_id` | never changes for an account; use it to detect a renamed user |
| `title` | profile `title` | `GM`, `IM`, `WGM`, ... or `None` |
| `status` | profile `status` | `basic`, `premium`, `staff`, `mod`, `closed`, `closed:fair_play_violations` (docs) |
| `name` | profile `name` | optional, user-entered |
| `country` | last part of profile `country` (an API URL) | ISO-style code, e.g. `US`, `NO` |
| `joined`, `last_online` | profile `joined`, `last_online` | Unix seconds, shown as UTC ISO |
| `followers` | profile `followers` | int |
| `fide` | stats `fide` | int as stored on Chess.com; the docs do not say it is verified |
| `tactics_high`, `puzzle_rush_best` | stats `tactics.highest.rating`, `puzzle_rush.best.score` | absent for players who never did them |
| `ratings[<rules>_<time_class>]` | stats `chess_*` / `chess960_*` objects | `rating`/`rd`/`as_of` from `last` (`as_of` = last rated game end), `best`/`best_on`/`best_game` from `best`, `win`/`loss`/`draw` from `record` |

Block 2 row (one per game, from the monthly archive): `url` (www.chess.com game page), `end` (`end_time`), `time_class` (`daily`, `rapid`, `blitz`, `bullet`), `time_control` (PGN style: `180` for 3-minute blitz, `1/604800` for 7-day daily), `rules` (`chess`, `chess960`, ...), `rated`, `color`, `rating` and `opp_rating` (each player's rating after the game), `opponent`, `result` and `opp_result` (Chess.com result codes), `outcome` (`win` / `draw` / `loss`, derived), `accuracy` (only if the game was analyzed), `opening` (slug at the end of `eco`), `pgn`.

Result codes (docs "Game results codes"): `win`, `checkmated`, `agreed`, `repetition`, `timeout`, `resigned`, `stalemate`, `lose`, `insufficient`, `50move`, `abandoned`, `kingofthehill`, `threecheck`, `timevsinsufficient`, `bughousepartnerlose`. Block 2 counts `agreed`, `repetition`, `stalemate`, `insufficient`, `50move`, `timevsinsufficient` as draws.

Other raw game fields: `uuid`, `tcn` (compact move encoding), `fen` (final position), `initial_setup`, `start_time` (daily games only), `white/black.uuid`.

## Gotchas

- **Month = month the game ended.** The JSON archive is in end-time order. The PGN `[Date]`/`[UTCDate]` is the start date, so a month's PGN file can start weeks earlier: erik's 2009/10 file spans UTCDate 2009.08.26 to 2009.10.31 (daily games), and its game order differs from the JSON.
- **Two-digit months.** `/games/2009/1` is HTTP 404 `Data provider not found for key ...`; `/games/2009/01` works. Block 3 refuses `'1'`.
- **Empty months are not errors.** `/games/2031/01` and `/games/1999/01` both return HTTP 200 `{"games":[]}`. Use `/games/archives` to know which months exist.
- **Uppercase usernames redirect.** `/pub/player/Hikaru` 301-redirects to `/pub/player/hikaru`; the blocks lowercase first.
- **Game rows carry the display case** (`"username":"Hikaru"`), so compare usernames lowercased.
- **PGN content type** was `application/vnd.chess-pgn` today (the docs say `application/x-chess-pgn`), with `Content-Disposition: attachment; filename="ChessCom_<user>_<YYYYMM>.pgn"`.
- **Caching:** 200 responses had `Cache-Control: public, max-age=5` (archives were also seen at `max-age=60`), 404s `max-age=30`. The docs say data may be up to 12-24 h old and every response carries `ETag` and `Last-Modified` for conditional requests.
- **`rating` in a game row is the rating after that game**, not before it.
- **Parallel requests:** not tested on purpose. The docs warn they may get 429 and that suspicious traffic can be blocked; keep calls serial.
- **Browser User-Agent:** the docs ask apps to send a recognizable User-Agent with contact info so Chess.com can reach you before blocking. In-tab `fetch()` cannot set it; the browser's own UA goes out unchanged. Do not spoof it.
- **Closed accounts** (`status` `closed` or `closed:fair_play_violations`) were not hit today, so how their archives behave is untested.

## What does not work

- **Site pages for the same data:** www.chess.com `/games/archive`, `/stats/`, `/game/` and `/download/pgn` are disallowed by robots.txt. The `url` fields point at `/game/...` pages; this skill returns them as links and never loads them.
- **Plain HTTP (no browser):** not tested; the authoring machine's network could not open a connection to api.chess.com, so only the browser path above is verified.
