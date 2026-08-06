# NBA Stats — Scraping & Data Extraction

`https://stats.nba.com` — official NBA statistics API. **Never use `http_get` from helpers.py for this site.** The server uses Akamai bot protection that inspects TLS fingerprints; Python's `urllib` silently hangs (TCP connects, no response body). Use `requests` with the exact header set below — confirmed working 2026-04-18.

## Do this first

**Install `requests` if not present, then call with the required header bundle.**

```python
import requests, json

NBA_HEADERS = {
    "Host": "stats.nba.com",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Referer": "https://www.nba.com/",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache",
}

def nba_get(endpoint, params):
    url = f"https://stats.nba.com/stats/{endpoint}"
    r = requests.get(url, headers=NBA_HEADERS, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def rows_to_dicts(result_set):
    """Convert NBA API rowSet to list of dicts using headers as keys."""
    cols = result_set["headers"]
    return [dict(zip(cols, row)) for row in result_set["rowSet"]]

# Quick test: games on a specific date
data = nba_get("scoreboardv2", {"GameDate": "2025-01-15", "LeagueID": "00", "DayOffset": 0})
games = rows_to_dicts(data["resultSets"][0])
for g in games[:3]:
    print(g["GAME_ID"], g["GAMECODE"], g["GAME_STATUS_TEXT"])
# Confirmed output (2026-04-18):
# 0022400561 20250115/NYKPHI Final/OT
# 0022400562 20250115/BOSTOR Final
# 0022400563 20250115/ATLCHI Final
```

## Common workflows

### All player game logs for a season

```python
import requests, json

data = nba_get("playergamelogs", {
    "Season": "2024-25",
    "SeasonType": "Regular Season",
    "LeagueID": "00",
})
rs = data["resultSets"][0]  # name: "PlayerGameLogs"
logs = rows_to_dicts(rs)
print(f"Total game logs: {len(logs)}")  # 26306 for full 2024-25 Regular Season
# Key fields: PLAYER_ID, PLAYER_NAME, GAME_DATE, MATCHUP, WL, MIN, PTS, REB, AST,
#             FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, FTM, FTA, FT_PCT,
#             STL, BLK, TOV, PLUS_MINUS, GAME_ID, TEAM_ID, TEAM_ABBREVIATION

# Filter to one player by adding PlayerID param
lebron_logs = nba_get("playergamelogs", {
    "Season": "2024-25",
    "SeasonType": "Regular Season",
    "LeagueID": "00",
    "PlayerID": 2544,
})
logs = rows_to_dicts(lebron_logs["resultSets"][0])
print(f"LeBron games: {len(logs)}")  # 70
game = logs[0]
print(game["PLAYER_NAME"], game["GAME_DATE"][:10], game["MATCHUP"],
      f"PTS={game['PTS']} AST={game['AST']} REB={game['REB']}")
# Confirmed: LeBron James 2025-04-11 LAL vs. HOU PTS=14 AST=8 REB=4

# Filter by date range (MM/DD/YYYY format)
day_logs = nba_get("playergamelogs", {
    "Season": "2024-25",
    "SeasonType": "Regular Season",
    "LeagueID": "00",
    "DateFrom": "01/15/2025",
    "DateTo": "01/15/2025",
})
print(f"Game logs on 2025-01-15: {len(rows_to_dicts(day_logs['resultSets'][0]))}")
# Confirmed: 232
```

### Scoreboard — games on a date

```python
import requests, json

# v2: classic resultSets format
data = nba_get("scoreboardv2", {
    "GameDate": "2025-01-15",
    "LeagueID": "00",
    "DayOffset": 0,
})
# resultSets in v2:
#   GameHeader      — game metadata (status, teams, arena)
#   LineScore       — per-team quarter scores + box totals
#   TeamLeaders     — PTS/REB/AST leaders for each team
#   EastConfStandingsByDay, WestConfStandingsByDay — standings snapshot
#   SeriesStandings, LastMeeting, Available, TicketLinks

game_headers = rows_to_dicts(data["resultSets"][0])  # GameHeader
for g in game_headers[:2]:
    print(g["GAME_ID"], g["GAMECODE"], g["GAME_STATUS_TEXT"], "Arena:", g["ARENA_NAME"])
# Confirmed:
# 0022400561 20250115/NYKPHI Final/OT Arena: Wells Fargo Center
# 0022400562 20250115/BOSTOR Final Arena: Scotiabank Arena

line_scores = rows_to_dicts(data["resultSets"][1])  # LineScore
for ls in line_scores[:2]:
    print(ls["TEAM_ABBREVIATION"], ls["PTS_QTR1"], ls["PTS_QTR2"],
          ls["PTS_QTR3"], ls["PTS_QTR4"], "Total:", ls["PTS"])
# Confirmed: NYK 30 30 25 24 Total: 125

# v3: cleaner JSON structure (preferred for new code)
data3 = nba_get("scoreboardv3", {"GameDate": "2025-01-15", "LeagueID": "00"})
# Returns: {"meta": {...}, "scoreboard": {"gameDate", "games": [...]}}
for game in data3["scoreboard"]["games"][:2]:
    home = game["homeTeam"]    # teamCity, teamName, teamTricode, wins, losses, score
    away = game["awayTeam"]
    leaders = game["gameLeaders"]
    print(game["gameId"], f"{away['teamTricode']} @ {home['teamTricode']}",
          game["gameStatusText"])
    print(f"  Leaders — {leaders['awayLeaders']['name']}: {leaders['awayLeaders']['points']} pts")
```

### Live games (real-time, no auth)

```python
import requests, json

# Today's live scoreboard — updates in real time, no special headers needed
r = requests.get(
    "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json",
    timeout=15
)
sb = r.json()["scoreboard"]
print("Game date:", sb["gameDate"])
for g in sb["games"]:
    home = g["homeTeam"]
    away = g["awayTeam"]
    print(f"{away['teamTricode']} {away['score']} @ {home['teamTricode']} {home['score']}",
          f"Q{g['period']} {g['gameClock'] or g['gameStatusText']}")
# Confirmed (2026-04-18, live Playoffs game):
# HOU 7 @ LAL 14  Q1 7:43

# Live box score by game ID
game_id = "0042500171"
r2 = requests.get(
    f"https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{game_id}.json",
    timeout=15
)
game = r2.json()["game"]
home = game["homeTeam"]
for p in home["players"][:3]:
    s = p["statistics"]
    print(f"{p['name']:25} PTS={s['points']} REB={s['reboundsTotal']} AST={s['assists']} MIN={s['minutesCalculated']}")
# Confirmed: LeBron James  PTS=4 REB=2 AST=2 MIN=PT08M52.00S

# Live play-by-play
r3 = requests.get(
    f"https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{game_id}.json",
    timeout=15
)
actions = r3.json()["game"]["actions"]
for a in actions[-5:]:
    print(f"Q{a['period']} {a['clock']} {a['actionType']} — {a['description']}")
# action keys: actionNumber, clock, timeActual, period, actionType, subType,
#              personId, scoreHome, scoreAway, description, isFieldGoal, x, y
```

### Player profile and career stats

```python
import requests, json

# Player info (bio + current season headline stats)
data = nba_get("commonplayerinfo", {"PlayerID": 2544, "LeagueID": "00"})
info = rows_to_dicts(data["resultSets"][0])[0]
print(info["DISPLAY_FIRST_LAST"], info["POSITION"], info["HEIGHT"],
      info["TEAM_NAME"], f"#{info['JERSEY']}")
headline = rows_to_dicts(data["resultSets"][1])[0]
print(f"Season avg: {headline['PTS']} pts / {headline['REB']} reb / {headline['AST']} ast")
# Confirmed: LeBron James Forward 6-9 Lakers #23
# Season avg: 20.9 pts / 6.1 reb / 7.2 ast

# Career stats (multiple result sets)
data = nba_get("playercareerstats", {"PlayerID": 2544, "PerMode": "PerGame"})
# resultSets:
#   SeasonTotalsRegularSeason   — per season per-game averages
#   CareerTotalsRegularSeason   — career totals
#   SeasonTotalsPostSeason, CareerTotalsPostSeason
#   SeasonTotalsAllStarSeason, CareerTotalsAllStarSeason
#   SeasonHighs, CareerHighs    — single-game bests by stat category
rs_by_name = {rs["name"]: rs for rs in data["resultSets"]}

seasons = rows_to_dicts(rs_by_name["SeasonTotalsRegularSeason"])
print(f"Regular seasons: {len(seasons)}")
latest = seasons[-1]
print(f"{latest['SEASON_ID']} {latest['TEAM_ABBREVIATION']}: {latest['PTS']} ppg")
# Confirmed: 23 regular seasons, most recent: 2024-25 LAL: 23.7 ppg
```

### Player list

```python
import requests, json

# Current-season active players only
data = nba_get("commonallplayers", {
    "Season": "2024-25",
    "IsOnlyCurrentSeason": 1,
    "LeagueID": "00",
})
players = rows_to_dicts(data["resultSets"][0])
print(f"Active players: {len(players)}")  # 139 in 2024-25
# Fields: PERSON_ID, DISPLAY_FIRST_LAST, ROSTERSTATUS, FROM_YEAR, TO_YEAR,
#         PLAYER_SLUG, TEAM_ID, TEAM_CITY, TEAM_NAME, TEAM_ABBREVIATION

# All-time players
data_all = nba_get("commonallplayers", {
    "Season": "2024-25",
    "IsOnlyCurrentSeason": 0,
    "LeagueID": "00",
})
print(f"All-time players: {len(rows_to_dicts(data_all['resultSets'][0]))}")  # 5126
```

### League leaders

```python
import requests, json

# Note: leagueleaders returns "resultSet" (singular), not "resultSets"
data = nba_get("leagueleaders", {
    "LeagueID": "00",
    "PerMode": "PerGame",
    "Scope": "S",
    "Season": "2024-25",
    "SeasonType": "Regular Season",
    "StatCategory": "PTS",   # PTS, REB, AST, STL, BLK, FGM, FGA, FTM, ...
})
# DIFFERENT SHAPE: data["resultSet"] not data["resultSets"]
leaders = rows_to_dicts(data["resultSet"])  # singular key!
for p in leaders[:3]:
    print(f"#{p['RANK']} {p['PLAYER']} ({p['TEAM']}) {p['PTS']} ppg in {p['GP']} games")
# Confirmed (2024-25):
# #1 Shai Gilgeous-Alexander (OKC) 32.7 ppg in 76 games
# #2 Giannis Antetokounmpo (MIL) 30.4 ppg in 67 games
# #3 Nikola Jokić (DEN) 29.6 ppg in 70 games
```

### Team game logs and standings

```python
import requests, json

# Team game logs
data = nba_get("teamgamelogs", {
    "Season": "2024-25",
    "SeasonType": "Regular Season",
    "LeagueID": "00",
    "TeamID": 1610612738,   # Boston Celtics
})
logs = rows_to_dicts(data["resultSets"][0])
print(f"Celtics games: {len(logs)}")  # 82 for full season
# Fields: TEAM_ABBREVIATION, GAME_DATE, MATCHUP, WL, W, L, W_PCT, MIN,
#         PTS, REB, AST, FGM, FGA, FG_PCT, FG3M, FG3A, FG3_PCT, ...

# League standings
data = nba_get("leaguestandingsv3", {
    "LeagueID": "00",
    "Season": "2024-25",
    "SeasonType": "Regular Season",
})
standings = rows_to_dicts(data["resultSets"][0])
east = [t for t in standings if t["Conference"] == "East"]
west = [t for t in standings if t["Conference"] == "West"]
print("East leader:", east[0]["TeamCity"], east[0]["TeamName"],
      east[0]["W"], "-", east[0]["L"])
# Confirmed: Cleveland Cavaliers 34-5

# Team info
data = nba_get("teaminfocommon", {
    "TeamID": 1610612738,
    "Season": "2024-25",
    "LeagueID": "00",
    "SeasonType": "Regular Season",
})
info = rows_to_dicts(data["resultSets"][0])[0]
print(info["TEAM_CITY"], info["TEAM_NAME"], info["TEAM_CONFERENCE"])
```

### Box score details

```python
import requests, json

game_id = "0022400561"  # from scoreboardv2 GAME_ID field

# Summary (officials, attendance, inactive players)
data = nba_get("boxscoresummaryv2", {"GameID": game_id})
summary = rows_to_dicts(data["resultSets"][0])[0]  # GameSummary
game_info = rows_to_dicts(data["resultSets"][4])[0]  # GameInfo
print(f"Attendance: {game_info['ATTENDANCE']}, Duration: {game_info['GAME_TIME']}")
# Confirmed: Attendance: 20088, Duration: 2:34

# Traditional box score v3 (cleaner nested JSON, different shape)
data = nba_get("boxscoretraditionalv3", {
    "GameID": game_id,
    "StartPeriod": 0, "EndPeriod": 10,
    "StartRange": 0, "EndRange": 28800, "RangeType": 0,
})
# Shape: data["boxScoreTraditional"]["homeTeam"]["players"][n]["statistics"]
# No resultSets — direct JSON object
box = data["boxScoreTraditional"]
for team_key in ("homeTeam", "awayTeam"):
    team = box[team_key]
    print(f"\n{team['teamTricode']}:")
    for p in team["players"][:3]:
        s = p["statistics"]
        print(f"  {p['nameI']:15} {s['points']}pts {s['minutes']}")
```

## URL and parameter reference

### stats.nba.com endpoints

```
/stats/scoreboardv2          — games by date (resultSets format)
/stats/scoreboardv3          — games by date (nested JSON format)
/stats/playergamelogs        — all player game-by-game logs for a season
/stats/teamgamelogs          — team game-by-game logs
/stats/leagueleaders         — season stat leaders (resultSet singular!)
/stats/leaguestandingsv3     — full league standings
/stats/commonallplayers      — player roster (current or all-time)
/stats/commonplayerinfo      — player bio + headline stats
/stats/playercareerstats     — per-season and career totals
/stats/teaminfocommon        — team info + season ranks
/stats/boxscoresummaryv2     — game summary, attendance, officials
/stats/boxscoretraditionalv3 — full player box scores (nested JSON)
```

### cdn.nba.com live endpoints (no special headers needed)

```
https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json
https://cdn.nba.com/static/json/liveData/boxscore/boxscore_{GAME_ID}.json
https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_{GAME_ID}.json
```

### Common parameters

| Parameter | Values | Notes |
|---|---|---|
| `Season` | `2024-25` | Format: `YYYY-YY` (last two digits of end year) |
| `SeasonType` | `Regular Season`, `Playoffs`, `Pre Season` | Exact string with spaces |
| `LeagueID` | `00` | Always `00` for NBA; `20` for WNBA |
| `GameDate` | `2025-01-15` | YYYY-MM-DD for scoreboardv2/v3 |
| `DateFrom`, `DateTo` | `01/15/2025` | MM/DD/YYYY for game log filters |
| `PerMode` | `PerGame`, `Totals`, `Per100Possessions` | For career stats and leaders |
| `PlayerID` | `2544` | Integer player ID from commonallplayers |
| `TeamID` | `1610612738` | Integer team ID (always 10-digit starting with 161...) |
| `GameID` | `0022400561` | 10-digit string from scoreboard |

### Response shapes

Two shapes exist — check which one the endpoint returns:

**Multiple result sets** (most endpoints):
```python
data["resultSets"]   # list of {name, headers, rowSet}
rs = data["resultSets"][0]
rows = [dict(zip(rs["headers"], row)) for row in rs["rowSet"]]
```

**Single result set** (`leagueleaders`):
```python
data["resultSet"]    # single {name, headers, rowSet} — note: singular key
rows = [dict(zip(data["resultSet"]["headers"], row)) for row in data["resultSet"]["rowSet"]]
```

**Nested JSON** (v3 endpoints: `scoreboardv3`, `boxscoretraditionalv3`):
```python
data["scoreboard"]["games"]          # scoreboardv3
data["boxScoreTraditional"]["homeTeam"]["players"]   # boxscoretraditionalv3
data["meta"]["request"]              # original internal request URL
```

**CDN live data** (`cdn.nba.com`):
```python
data["scoreboard"]["games"]          # todaysScoreboard
data["game"]["homeTeam"]["players"]  # boxscore, play-by-play
data["game"]["actions"]              # playbyplay
```

## Gotchas

- **`http_get` from helpers.py will silently hang.** The site uses Akamai bot protection that checks TLS fingerprints. Python's `urllib` connects (TCP/TLS handshake succeeds) but receives no response body — it appears as a 30-second timeout. Only `requests` (which uses a more browser-like TLS fingerprint) works.

- **`Referer: https://www.nba.com/` is required.** Without it, the connection drops immediately (`RemoteDisconnected`). The Referer must contain an nba.com domain — `https://stats.nba.com/` also works. Any non-nba.com Referer fails.

- **`Accept-Language` is also required.** Omitting it causes a timeout even when all other headers are present. The minimum working set is: `User-Agent` + `Accept-Language` + `Referer`.

- **`leagueleaders` returns `resultSet` (singular), not `resultSets` (plural).** This is the only standard stats endpoint with this shape. Using `data["resultSets"]` raises `KeyError`.

- **v3 endpoints return nested JSON, not `resultSets` at all.** `scoreboardv3` and `boxscoretraditionalv3` use `data["meta"]` + `data["scoreboard"]` / `data["boxScoreTraditional"]`. There are no headers/rowSet arrays to unpack.

- **Game IDs are 10-character strings, not integers.** `"0022400561"` — the leading zeros are significant. Always treat as string. The format is `SSYYYYNNNNN` where SS=season prefix (00=preseason, 00=regular for NBA), YYYY=season year, NNNNN=game sequence. For Playoffs: `004YYYYNNNNN`.

- **Season format is `YYYY-YY`, not `YYYY-YYYY`.** Use `"2024-25"` not `"2024-2025"`.

- **`SeasonType` requires exact strings with spaces.** `"Regular Season"` (capital R, capital S, space between). `"Regular+Season"` URL-encoding works in query params but pass as the plain string to `requests` `params=` dict — it handles encoding.

- **Date format differs by endpoint.** `scoreboardv2`/`v3` use `GameDate=2025-01-15` (ISO). Game log filters `DateFrom`/`DateTo` use `01/15/2025` (US format, MM/DD/YYYY).

- **`MIN` field in game logs is a float, not a string.** `48.4` means 48 minutes 24 seconds. The string form `MIN_SEC` is also available: `"48:24"`.

- **Missing required params return HTTP 500 with empty body.** There is no structured error JSON — `r.text` is empty. Always check `r.raise_for_status()` or `r.status_code`.

- **No pagination needed for game logs.** `playergamelogs` returns all rows for the season in one call (26 000+ rows for a full regular season). The full response is ~8 MB. There is no `retmax` or cursor param.

- **CDN live endpoints need no special headers.** `cdn.nba.com/static/json/liveData/...` endpoints are open CORS and work with plain `requests.get(url)`. They update in near-real-time during games.

- **Rate limits are lenient.** 15+ sequential requests/second succeed without throttling or 429 errors. No API key required. Practical limit is unknown but standard scraping pace (1-5 req/s) is safe.

- **`nba_api` PyPI package is a reliable thin wrapper.** `pip install nba_api` provides typed endpoint classes. It uses the same header set shown above. Use it for production code; the raw approach above is for quick scripts or when `nba_api` is unavailable.
