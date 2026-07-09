# ESPN / ESPN API — Scraping & Data Extraction

`site.web.api.espn.com`, `site.api.espn.com`, `sports.core.api.espn.com` — unofficial JSON API covering all major US sports. **Never use the browser for ESPN data.** All endpoints are `http_get`-accessible with no API key, no login, and no rate limiting observed.

## Do this first

**Scoreboard → Summary is the fastest pipeline for game data — two calls, full box scores and play-by-play.**

```python
import json
from helpers import http_get

# Step 1: today's NFL games
scoreboard = json.loads(http_get(
    "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
))
for event in scoreboard['events']:
    comp = event['competitions'][0]
    home, away = comp['competitors'][0], comp['competitors'][1]
    status = comp['status']['type']
    print(
        event['shortName'],              # e.g. "SEA @ NE"
        f"{away['score']}-{home['score']}",
        status['state'],                 # 'pre' | 'in' | 'post'
        status['detail'],                # e.g. "Final", "11:42 - 1st Quarter"
    )
# Confirmed output (2026-04-18):
# SEA VS NE 29-13 post Final

# Step 2: full game detail (box score + drives + scoring plays)
game_id = scoreboard['events'][0]['id']  # e.g. '401671881'
summary = json.loads(http_get(
    f"https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"
))
# Available top-level keys:
# boxscore, drives, leaders, scoringPlays, odds, againstTheSpread,
# header, injuries, broadcasts, winprobability, news, videos, standings
```

## Common workflows

### Scoreboard — current games or historical date

```python
import json
from helpers import http_get

# Today (default)
data = json.loads(http_get(
    "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
))

# Specific date
data = json.loads(http_get(
    "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    "?dates=20250112"   # YYYYMMDD
))

# Specific week and season type
data = json.loads(http_get(
    "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    "?seasontype=3&week=5&dates=2025"   # seasontype 3 = postseason, week 5 = Super Bowl
))

events = data['events']
season = data['season']   # {'type': 2, 'year': 2025}
week   = data['week']     # {'number': 18}

for event in events:
    comp = event['competitions'][0]
    competitors = comp['competitors']   # list of 2; index 0=home, 1=away per NFL convention
    for c in competitors:
        print(
            c['homeAway'],                          # 'home' | 'away'
            c['team']['displayName'],               # 'Seattle Seahawks'
            c['team']['abbreviation'],              # 'SEA'
            c['score'],                             # '29' (string)
            c.get('winner', False),                 # True if this team won
        )
    # Venue
    venue = comp.get('venue', {})
    print(venue.get('fullName'), venue.get('address', {}).get('city'))
    # Broadcasts
    print([b.get('media', {}).get('shortName') for b in comp.get('broadcasts', [])])
# Confirmed output (2026-04-18, postseason wk 5):
# away Seattle Seahawks SEA 29 True
# home New England Patriots NE 13 False
# Levi's Stadium Santa Clara
```

#### Season type codes

| `seasontype` | Meaning |
|---|---|
| `1` | Preseason |
| `2` | Regular season (default) |
| `3` | Postseason / playoffs |

### Game summary — box score, drives, scoring plays

```python
import json
from helpers import http_get

summary = json.loads(http_get(
    "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=401671881"
))

# Team stats (passing yards, first downs, etc.)
for team_stats in summary['boxscore']['teams']:
    name = team_stats['team']['displayName']
    stats = {s['name']: s['displayValue'] for s in team_stats['statistics']}
    print(name, '| 1st downs:', stats.get('firstDowns'), '| Total yards:', stats.get('totalYards'))

# Player stats by group (passing, rushing, receiving, ...)
for team_players in summary['boxscore']['players']:
    team_name = team_players['team']['displayName']
    for group in team_players['statistics']:
        labels = group['labels']    # e.g. ['C/ATT', 'YDS', 'AVG', 'TD', 'INT', ...]
        for entry in group['athletes']:
            athlete_name = entry['athlete']['displayName']
            stats = dict(zip(labels, entry['stats']))
            print(team_name, group['name'], athlete_name, stats)
# Confirmed (DEN @ BUF 2025-01-12):
# Denver Broncos passing Bo Nix {'C/ATT': '13/22', 'YDS': '144', 'AVG': '6.5', 'TD': '1', 'INT': '0', ...}
# Denver Broncos rushing Bo Nix {'CAR': '4', 'YDS': '43', ...}
# Denver Broncos receiving Courtland Sutton {'REC': '5', 'YDS': '75', ...}

# Scoring plays
for play in summary['scoringPlays']:
    print(
        f"Q{play['period']['number']} {play['clock']['displayValue']}",
        play['type']['text'],          # 'Passing Touchdown'
        play['text'],                  # 'Troy Franklin 43 Yd pass from Bo Nix...'
        f"{play['awayScore']}-{play['homeScore']}",
    )

# Drive log
for drive in summary['drives']['previous']:
    print(drive['description'], '|', drive['yards'], 'yds | scored:', drive['isScore'])

# Odds / spread (available pre-game; empty list post-game)
for line in summary.get('odds', []):
    print(line.get('details'), 'O/U:', line.get('overUnder'))
```

### Teams — all 32 NFL teams

```python
import json
from helpers import http_get

data = json.loads(http_get(
    "https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/teams"
))
teams = data['sports'][0]['leagues'][0]['teams']
for wrapper in teams:
    t = wrapper['team']
    print(
        t['id'],               # '22'  (use for team-specific endpoints)
        t['abbreviation'],     # 'ARI'
        t['displayName'],      # 'Arizona Cardinals'
        t['location'],         # 'Arizona'
        t['nickname'],         # 'Cardinals'
        f"#{t['color']}",      # primary hex color
        t['logos'][0]['href'], # PNG logo URL
    )
# Confirmed: 32 teams returned (2026-04-18)
# 22 ARI Arizona Cardinals Arizona Cardinals #a40227
# logo: https://a.espncdn.com/i/teamlogos/nfl/500/ari.png
```

### Single team detail + season record

```python
import json
from helpers import http_get

TEAM_ID = 12   # Kansas City Chiefs
data = json.loads(http_get(
    f"https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/teams/{TEAM_ID}"
))
team = data['team']
print(team['displayName'], team['standingSummary'])  # 'Kansas City Chiefs'

for record in team['record']['items']:
    stats = {s['name']: s['value'] for s in record['stats']}
    print(
        record['type'],          # 'total' | 'home' | 'road'
        f"W{int(stats.get('wins',0))} L{int(stats.get('losses',0))}",
    )
# Confirmed (2026-04-18):
# Kansas City Chiefs
# total W6 L11
# home W5 L4
# road W1 L7
```

### Team roster

```python
import json
from helpers import http_get

TEAM_ID = 12   # Kansas City Chiefs
data = json.loads(http_get(
    f"https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/teams/{TEAM_ID}/roster"
))
for group in data['athletes']:                   # grouped by position: offense/defense/special
    pos_group = group['position']
    for player in group['items']:
        print(
            player['id'],
            player['displayName'],
            player.get('jersey'),
            player['position']['displayName'],
            player.get('age'),
            player.get('displayWeight'),
            player.get('displayHeight'),
            player.get('headshot', {}).get('href', ''),
        )
coaches = data.get('coach', [])
# Confirmed (2026-04-18): 3 position groups (offense 34, defense 29, special teams)
# Player fields include: id, firstName, lastName, displayName, jersey, age,
#   dateOfBirth, weight/displayWeight, height/displayHeight, position,
#   birthPlace, college, headshot, injuries, experience, status
```

### Athlete (player) detail

```python
import json
from helpers import http_get

ATHLETE_ID = 3139477   # Patrick Mahomes
data = json.loads(http_get(
    f"https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/{ATHLETE_ID}"
))
a = data['athlete']
print(
    a['displayName'],                          # 'Patrick Mahomes'
    a['position']['displayName'],              # 'Quarterback'
    a['jersey'],                               # '15'
    a['team']['displayName'],                  # 'Kansas City Chiefs'
    a['status']['name'],                       # 'Active'
    a['active'],                               # True
    a.get('college'),                          # 'Texas Tech'
    a['headshot']['href'],                     # CDN image URL
)
injuries = a.get('injuries', [])
for inj in injuries:
    print(inj['status'], inj['type']['name'])  # 'Questionable', 'INJURY_STATUS_QUESTIONABLE'
# Confirmed (2026-04-18): athlete endpoint returns id, firstName, lastName,
# displayName, fullName, debutYear, jersey, college, headshot, position,
# team, active, status, injuries. Does NOT include dateOfBirth/draft/stats.
```

### Athlete season statistics (via core API)

```python
import json
from helpers import http_get

# season_type: 1=preseason, 2=regular, 3=postseason
resp = json.loads(http_get(
    "https://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
    "/seasons/2024/types/2/athletes/3139477/statistics"
))
for category in resp['splits']['categories']:
    stats = {s['displayName']: s['displayValue'] for s in category['stats']}
    print(f"{category['displayName']}:", {k: v for k, v in list(stats.items())[:4]})
# Confirmed output (2026-04-18):
# General: {'Fumbles': '2', 'Fumbles Lost': '0', ...}
# Passing: {'Completion Percentage': '67.5', 'Completions': '392', 'Interceptions': '11', ...}
# Rushing: {'Long Rushing': '33', 'Rushing Attempts': '58', ...}
# Scoring: {'Passing Touchdowns': '26', ...}
```

### Standings — full divisional breakdown

```python
import json
from helpers import http_get

data = json.loads(http_get(
    "https://site.web.api.espn.com/apis/v2/sports/football/nfl/standings?level=3"
    # level=3 required — without it, children have no division entries
))
for conference in data['children']:
    print(f"\n{conference['name']}")
    for division in conference['children']:
        print(f"  {division['name']}")
        for entry in division['standings']['entries']:
            stats = {s['name']: s['displayValue'] for s in entry['stats']}
            print(f"    {entry['team']['displayName']:30s} {stats.get('wins')}-{stats.get('losses')} {stats.get('winPercent')}")
# Confirmed output (2026-04-18):
# American Football Conference
#   AFC East
#     New England Patriots               14-3 .824
#     Buffalo Bills                      12-5 .706
# ...
```

### News — league and team-specific

```python
import json
from helpers import http_get

# League-wide news
data = json.loads(http_get(
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=20"
))
for article in data['articles']:
    print(
        article['type'],           # 'HeadlineNews' | 'Story' | 'Media'
        article['published'],      # ISO-8601 timestamp
        article['headline'],
        article['links']['web']['href'],
        article.get('premium'),    # True for ESPN+ paywalled content
    )
    for img in article.get('images', []):
        if img['type'] == 'header':
            print('  img:', img['url'], f"{img['width']}x{img['height']}")

# Team-specific news (use team id from /teams endpoint)
chiefs_news = json.loads(http_get(
    "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?team=12&limit=10"
))
# Confirmed: limit up to 20+ works; team= filters to team-relevant articles
```

### Article full text

```python
import json
from helpers import http_get

# article_id from news endpoint: article['id'] or article['links']['api']['self']['href']
article_id = 48526634
data = json.loads(http_get(
    f"https://content.core.api.espn.com/v1/sports/news/{article_id}"
))
headline = data['headlines'][0]
print(headline['headline'])        # title
print(headline['description'])     # lede summary
story_html = headline['story']     # full HTML body string (anchors, paragraph tags)
# Strip HTML tags if needed:
import re
plain = re.sub(r'<[^>]+>', '', story_html)
print(plain[:200])
# Confirmed: story is an HTML string with <p>, <a data-player-guid=...>, etc.
# article['premium'] = True means ESPN+ paywall; full story may be truncated
```

### Sports and leagues — URL path segments

All endpoints follow `/{sport}/{league}/` pattern:

| Sport | League slug | Example scoreboard path |
|---|---|---|
| `football` | `nfl` | `/sports/football/nfl/scoreboard` |
| `football` | `college-football` | `/sports/football/college-football/scoreboard` |
| `basketball` | `nba` | `/sports/basketball/nba/scoreboard` |
| `basketball` | `mens-college-basketball` | `/sports/basketball/mens-college-basketball/scoreboard` |
| `baseball` | `mlb` | `/sports/baseball/mlb/scoreboard` |
| `hockey` | `nhl` | `/sports/hockey/nhl/scoreboard` |
| `soccer` | `eng.1` (EPL) | `/sports/soccer/eng.1/scoreboard` |
| `mma` | `ufc` | `/sports/mma/ufc/scoreboard` |

All confirmed returning events (2026-04-18). Same pattern works for `/teams`, `/news`.

## URL reference

### Base hosts

```
https://site.web.api.espn.com    — scoreboard, teams, roster, summary, standings
https://site.api.espn.com        — news
https://sports.core.api.espn.com — athlete statistics, deep season/team data (ref-based)
https://content.core.api.espn.com — full article HTML
```

### Key endpoints

```
/apis/site/v2/sports/{sport}/{league}/scoreboard          GET games, scores, status
/apis/site/v2/sports/{sport}/{league}/scoreboard?dates=YYYYMMDD
/apis/site/v2/sports/{sport}/{league}/scoreboard?seasontype=2&week=18&dates=2025
/apis/site/v2/sports/{sport}/{league}/summary?event={game_id}   GET full game detail
/apis/site/v2/sports/{sport}/{league}/teams                     GET all teams list
/apis/site/v2/sports/{sport}/{league}/teams/{team_id}           GET team + record
/apis/site/v2/sports/{sport}/{league}/teams/{team_id}/roster    GET roster + coaches
/apis/common/v3/sports/{sport}/{league}/athletes/{athlete_id}   GET athlete profile
/apis/v2/sports/{sport}/{league}/standings?level=3              GET standings
/apis/site/v2/sports/{sport}/{league}/news?limit=N              GET news headlines
/apis/site/v2/sports/{sport}/{league}/news?team={team_id}&limit=N

# Core API (returns {$ref} references — follow with https:// prefix)
https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/{year}/types/{type}/athletes/{id}/statistics
https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes?limit=100&active=true

# Content API
https://content.core.api.espn.com/v1/sports/news/{article_id}
```

### Scoreboard parameters

| Parameter | Values | Notes |
|---|---|---|
| `dates` | `YYYYMMDD` or `YYYY` | Filter by date or season year |
| `seasontype` | `1` `2` `3` | Pre / regular / post |
| `week` | integer | Week number within season type |

### Logo / image CDN

```python
# Team logos — size in URL path
logo = f"https://a.espncdn.com/i/teamlogos/nfl/500/{abbr.lower()}.png"   # 500px
logo_dark = f"https://a.espncdn.com/i/teamlogos/nfl/500-dark/{abbr.lower()}.png"
# Player headshots
headshot = f"https://a.espncdn.com/i/headshots/nfl/players/full/{athlete_id}.png"
```

## Gotchas

- **SSL certificate verification fails with the default `http_get` helper.** `site.web.api.espn.com` uses a self-signed certificate in the chain. The default `helpers.http_get` (which uses `urllib.request` without SSL context override) raises `SSLCertVerificationError`. Workaround: use `requests` with `verify=False`, or patch `urllib` with a permissive SSL context:
  ```python
  import ssl, urllib.request, gzip, json
  _ctx = ssl.create_default_context()
  _ctx.check_hostname = False
  _ctx.verify_mode = ssl.CERT_NONE

  def espn_get(url, timeout=20.0):
      req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"})
      with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
          data = r.read()
          if r.headers.get("Content-Encoding") == "gzip":
              data = gzip.decompress(data)
          return data.decode()
  ```

- **No API key, no auth, no rate limiting detected.** 5 rapid successive requests each completed in ~0.15–0.19 s with no throttling or 429. No `Referer` or `Origin` header is required. Standard `User-Agent` or even an empty one both work.

- **`score` is a string, not an int.** `competitor['score']` returns `'29'`, not `29`. Cast with `int()` before arithmetic.

- **`?level=3` is required for divisional standings.** Without it, `standings['children']` contains conferences only (no divisions), so `children[0]['children']` is an empty list. The `?expanded=true` parameter has no effect.

- **`competitors[0]` is home, `[1]` is away for NFL.** Verify using `competitor['homeAway']` (`'home'` or `'away'`) rather than relying on index order, since other sports may differ.

- **Athlete profile endpoint does NOT return birth date, draft info, or stats.** The `common/v3/.../athletes/{id}` endpoint returns `id, jersey, college, headshot, position, team, active, status, injuries` only. For birth date / draft: use team roster endpoint (fields `dateOfBirth`, `birthPlace`, `college` are present on roster players). For stats: use `sports.core.api.espn.com/v2/.../statistics`.

- **Core API returns `$ref` strings, not embedded objects.** `sports.core.api.espn.com/v2/.../athletes?limit=100` returns `{"items": [{"$ref": "http://..."}]}`. You must fetch each ref separately (HTTP not HTTPS in the ref URL — switch to HTTPS before fetching). Use `ThreadPoolExecutor` for bulk fetching.

- **`drives['previous']` contains full play-by-play.** The `drives.previous[].plays` array in the game summary holds every play in the drive with `type.text`, `text` (description), `clock`, `period`, `scoringPlay`, `isTurnover`, field position start/end. The top-level `plays` key is always an empty list — do not use it.

- **`odds` is empty after the game is final.** The `odds` array in the summary response is populated pre-game (spread, over/under, provider). Once the game ends it becomes `[]`. Confirmed for completed games.

- **Article `story` field is HTML, not plain text.** `content.core.api.espn.com/v1/sports/news/{id}` returns `headlines[0]['story']` as an HTML string with `<p>`, `<a data-player-guid=...>`, and team link tags. Strip with `re.sub(r'<[^>]+>', '', html)` for plain text.

- **Premium/ESPN+ articles are only partially available.** `article['premium'] = True` signals paywalled content. The `story` HTML may be a short teaser only. The news list endpoint always shows the headline regardless.

- **College football scoreboard can return 100+ events.** `college-football/scoreboard` returns all games in progress on a Saturday, potentially 96+ events. Paginate or filter by group/conference if needed.
