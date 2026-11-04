# NBA.com - Player, team and leader stats from /stats pages

Field-tested against www.nba.com on 2026-11-04 using a Browser Use cloud browser, logged out. 25 page loads, no challenge, no 403.

robots.txt (read in the browser 2026-11-04, `User-Agent: *`) disallows `/api/*`, `/stats/events/` and `/search` among others; `/stats/leaders`, `/stats/players/*`, `/stats/teams/*` and `/stats/player/<id>` match no rule, so they are allowed, and the blocks only read the stats.nba.com JSON those pages load themselves (stats.nba.com/robots.txt redirects to www.nba.com/stats/robots.txt, a "Content Unavailable" page). The same file also has named groups for AI crawlers and agents (`GPTBot`, `ChatGPT-User`, `ClaudeBot`, `Claude-Web`, `anthropic-ai`, `PerplexityBot`, `Google-Extended` ...) with `Disallow: /` plus a few `Allow` lines (team game pages; for `GPTBot` and `Google-Extended` also `/standings`, `/schedule`, `/players`, `/stats/history` and three other `/stats/help|draft` pages), so `/stats/leaders`, `/stats/players/*`, `/stats/teams/*` and `/stats/player/<id>` are closed to anything that identifies as one of them. `OAI-SearchBot` gets `Allow: /`.

## Quick summary

- Every `/stats` page is a Next.js shell. `__NEXT_DATA__` holds only nav and ads. The table comes from one XHR to `https://stats.nba.com/stats/<endpoint>?...` after load.
- **Method:** open the page, watch the browser's network events (`drain_events()`), and read that XHR's body with `cdp("Network.getResponseBody", requestId=...)`. No extra request is sent; the page's own call is read.
- Page URL query params set the page's own filters and pass through to the XHR: `?Season=2025-26&SeasonType=Playoffs&PerMode=Totals&StatCategory=REB`. No params = current season, regular season, per game.
- One response holds the whole table, not one UI page: 582 players for 2025-26, 299 leaders for 2026-27 so far.
- JSON shape: `resultSets[]` (or one `resultSet` on `leagueLeaders`), each `{name, headers, rowSet}`. The helper zips them into row dicts keyed by set name.

| Page | XHR endpoint | Result set |
|---|---|---|
| `/stats/leaders` | `leagueLeaders` | `LeagueLeaders` |
| `/stats/players/traditional`, `/stats/players/advanced` (`MeasureType=Advanced`) | `leaguedashplayerstats` | `LeagueDashPlayerStats` |
| `/stats/teams/traditional`, `/stats/teams/advanced` | `leaguedashteamstats` | `LeagueDashTeamStats` |
| `/stats/player/<PLAYER_ID>` | `playerdashboardbyyearoveryearcombined` | `ByYear{Base,Advanced,Misc,Scoring,Usage}PlayerDashboard` |

## What works

All three blocks are self-contained and repeat the same helper. `nba_stats_page(path, params)` refuses paths outside `/stats/` or under a disallowed prefix, opens the page, waits for its stats.nba.com response(s) plus 2 s of quiet, raises on a failed XHR, an Akamai "Access Denied" page or a redirect, and returns `{url, api, parameters, tables}`. About 3 s between page loads.

### 1. League leaders (browser)

```python
import json, os, tempfile, time, urllib.parse

# www.nba.com/robots.txt, group "User-Agent: *" (read 2026-11-04): Disallow /api/*, /stats/events/, /search.
ROBOTS_DISALLOW = ("/api/", "/stats/events/", "/search")

def nba_stats_page(path, params=None, timeout=40):
    """Open a www.nba.com/stats page; return the stats.nba.com JSON that page loaded itself.
    No extra request: the body is read from the browser's network log (CDP Network.getResponseBody)."""
    if not path.startswith("/stats/") or path.startswith(ROBOTS_DISALLOW):
        raise ValueError(f"{path}: not a robots.txt-allowed /stats page")
    url = "https://www.nba.com" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    drain_events()  # forget network events from earlier pages
    try:
        goto_url(url)
    except TimeoutError:
        pass  # Page.navigate can exceed the 5 s daemon timeout on this ad-heavy site; the navigation still runs
    pending, got, last = {}, [], time.time()
    end = time.time() + timeout
    while time.time() < end:
        for e in drain_events():
            m, p = e.get("method"), e.get("params", {})
            if m == "Network.responseReceived" and p["response"]["url"].startswith("https://stats.nba.com/stats/"):
                pending[p["requestId"]] = (p["response"]["url"], p["response"]["status"])
            elif m in ("Network.loadingFinished", "Network.loadingFailed") and p.get("requestId") in pending:
                api, status = pending.pop(p["requestId"])
                if m == "Network.loadingFailed" or status != 200:
                    raise RuntimeError(f"{url}: the page's own stats request failed (HTTP {status}); stop, do not retry around it")
                got.append((api, json.loads(cdp("Network.getResponseBody", requestId=p["requestId"])["body"])))
                last = time.time()
        if got and not pending and time.time() - last > 2:
            break
        time.sleep(0.2)
    if "Access Denied" in (js("document.title") or ""):
        raise RuntimeError(f"Akamai 'Access Denied' on {url}: stop and tell the user; do not retry around it")
    if not got:
        raise RuntimeError(f"{url}: no stats.nba.com response within {timeout}s; layout changed?")
    if js("location.pathname") != path:
        raise RuntimeError(f"asked for {path}, landed on {js('location.href')}")
    tables = {}
    for _, d in got:
        for s in d.get("resultSets") or [d["resultSet"]]:  # leagueLeaders has one "resultSet"; the others a "resultSets" list
            tables[s["name"]] = [dict(zip(s["headers"], r)) for r in s["rowSet"]]
    return {"url": url, "api": [a for a, _ in got], "parameters": got[0][1].get("parameters"), "tables": tables}

tab = new_tab("about:blank")
out = {}
try:
    for i, (label, params) in enumerate([
        ("PTS, this season", {"StatCategory": "PTS"}),  # no Season: the page's default (current) season
        ("REB, 2025-26 playoffs", {"StatCategory": "REB", "Season": "2025-26", "SeasonType": "Playoffs"}),
        ("AST, 2025-26 totals", {"StatCategory": "AST", "Season": "2025-26", "PerMode": "Totals"}),
    ]):
        if i:
            time.sleep(3)
        page = nba_stats_page("/stats/leaders", params)
        rows = page["tables"]["LeagueLeaders"]
        out[label] = page
        q = page["parameters"]
        print(f'{label}: {q["Season"]} {q["SeasonType"]} {q["PerMode"]} {q["StatCategory"]} | rows {len(rows)}')
        stat = q["StatCategory"]
        for r in rows[:3]:
            print(f'   #{r["RANK"]} {r["PLAYER"]} ({r["TEAM"]}, id {r["PLAYER_ID"]}) GP {r["GP"]} {stat} {r[stat]}')
finally:
    cdp("Target.closeTarget", targetId=tab)
print("columns:", list(out["PTS, this season"]["tables"]["LeagueLeaders"][0]))
print("page's own request:", out["PTS, this season"]["api"][0])
path = os.path.join(tempfile.gettempdir(), "nba_leaders.json")
with open(path, "w") as f:
    json.dump(out, f)
print("saved", path)
```

Output from the test run (saved path shortened):

```
PTS, this season: 2026-27 Regular Season PerGame PTS | rows 299
   #1 Luka Dončić (LAL, id 1629029) GP 7 PTS 38.3
   #2 Stephen Curry (GSW, id 201939) GP 6 PTS 30.0
   #3 Tyrese Maxey (PHI, id 1630178) GP 8 PTS 29.1
REB, 2025-26 playoffs: 2025-26 Playoffs PerGame REB | rows 155
   #1 Nikola Jokić (DEN, id 203999) GP 6 REB 13.2
   #2 Victor Wembanyama (SAS, id 1641705) GP 22 REB 10.9
   #3 Jayson Tatum (BOS, id 1628369) GP 6 REB 10.7
AST, 2025-26 totals: 2025-26 Regular Season Totals AST | rows 582
   #1 Nikola Jokić (DEN, id 203999) GP 65 AST 697
   #2 Cade Cunningham (DET, id 1630595) GP 64 AST 634
   #3 Jalen Johnson (ATL, id 1630552) GP 72 AST 566
columns: ['PLAYER_ID', 'RANK', 'PLAYER', 'TEAM_ID', 'TEAM', 'GP', 'MIN', 'FGM', 'FGA', 'FG_PCT', 'FG3M', 'FG3A', 'FG3_PCT', 'FTM', 'FTA', 'FT_PCT', 'OREB', 'DREB', 'REB', 'AST', 'STL', 'BLK', 'TOV', 'PTS', 'EFF']
page's own request: https://stats.nba.com/stats/leagueLeaders?LeagueID=00&PerMode=PerGame&Scope=S&Season=2026-27&SeasonType=Regular+Season&StatCategory=PTS
saved <tempdir>/nba_leaders.json
```

### 2. Full player and team tables (browser)

`/stats/players/<tab>` and `/stats/teams/<tab>` take the same params. Sort and filter in Python; the response already has every row.

```python
import json, os, tempfile, time, urllib.parse

# www.nba.com/robots.txt, group "User-Agent: *" (read 2026-11-04): Disallow /api/*, /stats/events/, /search.
ROBOTS_DISALLOW = ("/api/", "/stats/events/", "/search")

def nba_stats_page(path, params=None, timeout=40):
    """Open a www.nba.com/stats page; return the stats.nba.com JSON that page loaded itself.
    No extra request: the body is read from the browser's network log (CDP Network.getResponseBody)."""
    if not path.startswith("/stats/") or path.startswith(ROBOTS_DISALLOW):
        raise ValueError(f"{path}: not a robots.txt-allowed /stats page")
    url = "https://www.nba.com" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    drain_events()  # forget network events from earlier pages
    try:
        goto_url(url)
    except TimeoutError:
        pass  # Page.navigate can exceed the 5 s daemon timeout on this ad-heavy site; the navigation still runs
    pending, got, last = {}, [], time.time()
    end = time.time() + timeout
    while time.time() < end:
        for e in drain_events():
            m, p = e.get("method"), e.get("params", {})
            if m == "Network.responseReceived" and p["response"]["url"].startswith("https://stats.nba.com/stats/"):
                pending[p["requestId"]] = (p["response"]["url"], p["response"]["status"])
            elif m in ("Network.loadingFinished", "Network.loadingFailed") and p.get("requestId") in pending:
                api, status = pending.pop(p["requestId"])
                if m == "Network.loadingFailed" or status != 200:
                    raise RuntimeError(f"{url}: the page's own stats request failed (HTTP {status}); stop, do not retry around it")
                got.append((api, json.loads(cdp("Network.getResponseBody", requestId=p["requestId"])["body"])))
                last = time.time()
        if got and not pending and time.time() - last > 2:
            break
        time.sleep(0.2)
    if "Access Denied" in (js("document.title") or ""):
        raise RuntimeError(f"Akamai 'Access Denied' on {url}: stop and tell the user; do not retry around it")
    if not got:
        raise RuntimeError(f"{url}: no stats.nba.com response within {timeout}s; layout changed?")
    if js("location.pathname") != path:
        raise RuntimeError(f"asked for {path}, landed on {js('location.href')}")
    tables = {}
    for _, d in got:
        for s in d.get("resultSets") or [d["resultSet"]]:  # leagueLeaders has one "resultSet"; the others a "resultSets" list
            tables[s["name"]] = [dict(zip(s["headers"], r)) for r in s["rowSet"]]
    return {"url": url, "api": [a for a, _ in got], "parameters": got[0][1].get("parameters"), "tables": tables}

tab = new_tab("about:blank")
try:
    players = nba_stats_page("/stats/players/traditional", {"Season": "2025-26", "PerMode": "Totals"})
    time.sleep(3)
    teams = nba_stats_page("/stats/teams/advanced", {"Season": "2025-26"})
finally:
    cdp("Target.closeTarget", targetId=tab)

for page in (players, teams):
    (name, rows), = page["tables"].items()
    print(page["url"].split(".com")[1], "->", name, len(rows), "rows,", len(rows[0]), "columns")
p = players["tables"]["LeagueDashPlayerStats"]
print("top PTS (totals):", [(r["PLAYER_NAME"], r["TEAM_ABBREVIATION"], r["PTS"]) for r in sorted(p, key=lambda r: -r["PTS"])[:3]])
jokic = next(r for r in p if r["PLAYER_NAME"] == "Nikola Jokić")
print("Jokic:", {k: jokic[k] for k in ("PLAYER_ID", "GP", "MIN", "PTS", "REB", "AST", "PLUS_MINUS", "DD2", "TD3", "PTS_RANK")})
t = teams["tables"]["LeagueDashTeamStats"]
print("best NET_RATING:", [(r["TEAM_NAME"], r["W"], r["L"], r["NET_RATING"]) for r in sorted(t, key=lambda r: -r["NET_RATING"])[:3]])
try:
    nba_stats_page("/stats/events/", {"GameID": "0022500001"})  # robots.txt-disallowed: refused before any request
except ValueError as e:
    print("refused:", e)
path = os.path.join(tempfile.gettempdir(), "nba_dash_2025-26.json")
with open(path, "w") as f:
    json.dump({"players": players, "teams": teams}, f)
print("saved", path)
```

Output from the test run (saved path shortened):

```
/stats/players/traditional?Season=2025-26&PerMode=Totals -> LeagueDashPlayerStats 582 rows, 69 columns
/stats/teams/advanced?Season=2025-26 -> LeagueDashTeamStats 30 rows, 46 columns
top PTS (totals): [('Luka Dončić', 'LAL', 2143), ('Shai Gilgeous-Alexander', 'OKC', 2117), ('Jaylen Brown', 'BOS', 2038)]
Jokic: {'PLAYER_ID': 203999, 'GP': 65, 'MIN': 2264.855, 'PTS': 1799, 'REB': 836, 'AST': 697, 'PLUS_MINUS': 555, 'DD2': 55, 'TD3': 34, 'PTS_RANK': 10}
best NET_RATING: [('Oklahoma City Thunder', 64, 18, 11.1), ('Detroit Pistons', 60, 22, 8.4), ('San Antonio Spurs', 62, 20, 8.4)]
refused: /stats/events/: not a robots.txt-allowed /stats page
saved <tempdir>/nba_dash_2025-26.json
```

### 3. One player, season by season (browser)

`PLAYER_ID` comes from block 1 or 2. The page loads all seasons in one call, newest first.

```python
import json, os, tempfile, time, urllib.parse

# www.nba.com/robots.txt, group "User-Agent: *" (read 2026-11-04): Disallow /api/*, /stats/events/, /search.
ROBOTS_DISALLOW = ("/api/", "/stats/events/", "/search")

def nba_stats_page(path, params=None, timeout=40):
    """Open a www.nba.com/stats page; return the stats.nba.com JSON that page loaded itself.
    No extra request: the body is read from the browser's network log (CDP Network.getResponseBody)."""
    if not path.startswith("/stats/") or path.startswith(ROBOTS_DISALLOW):
        raise ValueError(f"{path}: not a robots.txt-allowed /stats page")
    url = "https://www.nba.com" + path + ("?" + urllib.parse.urlencode(params) if params else "")
    drain_events()  # forget network events from earlier pages
    try:
        goto_url(url)
    except TimeoutError:
        pass  # Page.navigate can exceed the 5 s daemon timeout on this ad-heavy site; the navigation still runs
    pending, got, last = {}, [], time.time()
    end = time.time() + timeout
    while time.time() < end:
        for e in drain_events():
            m, p = e.get("method"), e.get("params", {})
            if m == "Network.responseReceived" and p["response"]["url"].startswith("https://stats.nba.com/stats/"):
                pending[p["requestId"]] = (p["response"]["url"], p["response"]["status"])
            elif m in ("Network.loadingFinished", "Network.loadingFailed") and p.get("requestId") in pending:
                api, status = pending.pop(p["requestId"])
                if m == "Network.loadingFailed" or status != 200:
                    raise RuntimeError(f"{url}: the page's own stats request failed (HTTP {status}); stop, do not retry around it")
                got.append((api, json.loads(cdp("Network.getResponseBody", requestId=p["requestId"])["body"])))
                last = time.time()
        if got and not pending and time.time() - last > 2:
            break
        time.sleep(0.2)
    if "Access Denied" in (js("document.title") or ""):
        raise RuntimeError(f"Akamai 'Access Denied' on {url}: stop and tell the user; do not retry around it")
    if not got:
        raise RuntimeError(f"{url}: no stats.nba.com response within {timeout}s; layout changed?")
    if js("location.pathname") != path:
        raise RuntimeError(f"asked for {path}, landed on {js('location.href')}")
    tables = {}
    for _, d in got:
        for s in d.get("resultSets") or [d["resultSet"]]:  # leagueLeaders has one "resultSet"; the others a "resultSets" list
            tables[s["name"]] = [dict(zip(s["headers"], r)) for r in s["rowSet"]]
    return {"url": url, "api": [a for a, _ in got], "parameters": got[0][1].get("parameters"), "tables": tables}

tab = new_tab("about:blank")
careers = {}
try:
    for i, pid in enumerate([2544, 1641705]):  # LeBron James, Victor Wembanyama (PLAYER_ID from the leaders or players tables)
        if i:
            time.sleep(3)
        page = nba_stats_page(f"/stats/player/{pid}")
        careers[pid] = page
        name = js("document.title").split(" | ")[0].lstrip("\U0001F434 ")  # strip the harness tab marker if present
        base = page["tables"]["ByYearBasePlayerDashboard"]
        print(pid, name, "| sets:", list(page["tables"]), "| seasons:", len(base))
        for r in base[:4]:
            print(f'   {r["GROUP_VALUE"]} {r["TEAM_ABBREVIATION"]:>3} GP {r["GP"]:>2} MIN {r["MIN"]} PTS {r["PTS"]} REB {r["REB"]} AST {r["AST"]} last game {r["MAX_GAME_DATE"][:10]}')
        adv = page["tables"]["ByYearAdvancedPlayerDashboard"][0]
        print(f'   advanced {adv["GROUP_VALUE"]}: TS% {adv["TS_PCT"]} USG% {adv["USG_PCT"]} NET_RATING {adv["NET_RATING"]} PIE {adv["PIE"]}')
finally:
    cdp("Target.closeTarget", targetId=tab)
print("request params:", {k: v for k, v in careers[2544]["parameters"].items() if v not in (None, "", 0, "N")})
path = os.path.join(tempfile.gettempdir(), "nba_careers.json")
with open(path, "w") as f:
    json.dump(careers, f)
print("saved", path)
```

Output from the test run (saved path shortened):

```
2544 LeBron James | sets: ['ByYearBasePlayerDashboard', 'ByYearAdvancedPlayerDashboard', 'ByYearMiscPlayerDashboard', 'ByYearScoringPlayerDashboard', 'ByYearUsagePlayerDashboard'] | seasons: 24
   2026-27 PHI GP  6 MIN 33.1 PTS 16.2 REB 7.0 AST 7.3 last game 2026-11-02
   2025-26 LAL GP 60 MIN 33.2 PTS 20.9 REB 6.1 AST 7.2 last game 2026-04-12
   2024-25 LAL GP 70 MIN 34.9 PTS 24.4 REB 7.8 AST 8.2 last game 2025-04-11
   2023-24 LAL GP 71 MIN 35.3 PTS 25.7 REB 7.3 AST 8.3 last game 2024-04-14
   advanced 2026-27: TS% 0.512 USG% 0.235 NET_RATING 5.7 PIE 0.137
1641705 Victor Wembanyama | sets: ['ByYearBasePlayerDashboard', 'ByYearAdvancedPlayerDashboard', 'ByYearMiscPlayerDashboard', 'ByYearScoringPlayerDashboard', 'ByYearUsagePlayerDashboard'] | seasons: 4
   2026-27 SAS GP  7 MIN 31.2 PTS 25.7 REB 10.7 AST 3.3 last game 2026-11-02
   2025-26 SAS GP 64 MIN 29.2 PTS 25.0 REB 11.5 AST 3.1 last game 2026-04-10
   2024-25 SAS GP 46 MIN 33.2 PTS 24.3 REB 11.0 AST 3.7 last game 2025-02-12
   2023-24 SAS GP 71 MIN 29.7 PTS 21.4 REB 10.6 AST 3.9 last game 2024-04-12
   advanced 2026-27: TS% 0.544 USG% 0.344 NET_RATING 19.5 PIE 0.189
request params: {'PerMode': 'PerGame', 'LeagueID': '00', 'Season': '2026-27', 'SeasonType': 'Regular Season', 'PlayerID': 2544}
saved <tempdir>/nba_careers.json
```

## Fields

| Field | Notes |
|---|---|
| `parameters` | the filters the page actually sent (`Season`, `SeasonType`, `PerMode`, `MeasureType`...). Check it: it is the source of truth for what the rows mean |
| `LeagueLeaders` | 25 columns: `PLAYER_ID, RANK, PLAYER, TEAM_ID, TEAM, GP, MIN, FGM ... PTS, EFF`. Sorted by `RANK` for `StatCategory` |
| `LeagueDashPlayerStats` | 69 columns on `traditional`: box score plus `AGE`, `W`, `L`, `PLUS_MINUS`, `DD2`, `TD3`, `NBA_FANTASY_PTS` and a `*_RANK` for each stat |
| `LeagueDashTeamStats` | 46 columns on `advanced`: `OFF_RATING`, `DEF_RATING`, `NET_RATING`, `PACE`, `TS_PCT`, `PIE` and ranks |
| `ByYear*PlayerDashboard` | one row per season, `GROUP_VALUE` = season, `MAX_GAME_DATE` = last game played |
| percentages | fractions (`0.497`), not percent |
| `MIN` | per game on `PerGame`; total minutes as a decimal on `Totals` (`2264.855`) |
| ids | `PLAYER_ID` (2544 = LeBron James), `TEAM_ID` (1610612747 = Lakers); team logos load from `cdn.nba.com/logos/nba/<TEAM_ID>/` |

## Gotchas

- The network buffer holds 500 events and an NBA page fires many ad requests. The helper drains every 0.2 s; do not sleep between `goto_url` and the drain loop.
- `Network.getResponseBody` only works while the tab is open. Read the body before navigating again.
- Seasons with a mid-season trade on `/stats/player/<id>`: not checked; expect more than one row per season.
- Other tabs (`/misc`, `/scoring`, `/usage`, `/defense`...) should follow the same pattern with another `MeasureType`; only `traditional` and `advanced` were tested.
- The blocks open one tab and close it in `finally`.

## What does not work

- Plain HTTP (`curl`) to `https://www.nba.com/robots.txt`: HTTP 403 Akamai "Access Denied" (2026-11-04). Not worked around; use the browser.
- `/stats/events/` (play-by-play video events), `/api/*` and `/search`: disallowed by robots.txt. Not used; the helper refuses them before any request.
- `__NEXT_DATA__` on `/stats` pages: no table data, only layout.
