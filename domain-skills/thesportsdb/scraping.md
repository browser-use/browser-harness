# TheSportsDB — Data Extraction

`https://www.thesportsdb.com/api/v1/json/3/` — free tier, no registration needed. Pure JSON REST API, no browser required.

## Do this first

**Use `http_get` directly — no browser needed.**

```python
import json
data = json.loads(http_get(
    "https://www.thesportsdb.com/api/v1/json/3/searchteams.php?t=Arsenal"
))
team = data["teams"][0]
print(team["strTeam"], team["strLeague"], team["strStadium"])
# Arsenal  English Premier League  Emirates Stadium
```

## Critical: API key "1" is dead — use "3"

The free API key in all official documentation is `1`, but as of 2025 that returns HTTP 404 for every endpoint. **Use `3` instead.** Key `2` also returns 404. Key `3` works identically to the old "free" key `1`.

```python
# WRONG — returns 404
BASE = "https://www.thesportsdb.com/api/v1/json/1/"

# CORRECT
BASE = "https://www.thesportsdb.com/api/v1/json/3/"
```

## Setup

```python
import json, urllib.request, urllib.error

BASE = "https://www.thesportsdb.com/api/v1/json/3"

def sdb(path):
    """TheSportsDB API call. Returns parsed JSON dict."""
    url = f"{BASE}/{path}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())
```

## Rate limits

**Very generous — no observable limit on the free tier.** 10 rapid-fire calls in a loop all return 200 with no throttling. No `Retry-After` headers observed. No API key registration required.

## Common workflows

### Search for a team

```python
r = sdb("searchteams.php?t=Arsenal")
teams = r["teams"]          # None if no match, not []
if not teams:
    print("No results")
else:
    t = teams[0]
    print(t["idTeam"])          # "133604"  — always a string, not int
    print(t["strTeam"])         # "Arsenal"
    print(t["strLeague"])       # "English Premier League"
    print(t["idLeague"])        # "4328"
    print(t["strSport"])        # "Soccer"
    print(t["strCountry"])      # "England"
    print(t["strStadium"])      # "Emirates Stadium"
    print(t["intFormedYear"])   # "1892"
    print(t["intStadiumCapacity"])  # "60338"
    print(t["strBadge"])        # image URL (PNG)
    print(t["strLogo"])         # transparent logo URL (PNG)
    print(t["strFanart1"])      # fan art image URL
    print(t["strColour1"])      # "#EF0107"
    print(t["strDescriptionEN"][:200])  # long Wikipedia-style bio
```

Full team object has 64 keys. Key subset:
`idTeam`, `idLeague`, `idLeague2`–`idLeague7`, `idVenue`, `strTeam`, `strTeamAlternate`, `strTeamShort`, `strSport`, `strLeague`, `strLeague2`–`strLeague7`, `strCountry`, `strLocation`, `strStadium`, `intFormedYear`, `intStadiumCapacity`, `strBadge`, `strLogo`, `strBanner`, `strFanart1`–`strFanart4`, `strEquipment`, `strColour1`–`strColour3`, `strGender`, `strKeywords`, `strWebsite`, `strFacebook`, `strTwitter`, `strInstagram`, `strYoutube`, `strDescriptionEN`, `strDescriptionDE`, `strDescriptionFR`, `strDescriptionES`, `strDescriptionPT`, `strDescriptionIT`, `strDescriptionRU`, `strDescriptionJP`, `strDescriptionNO`, `strLocked`

### Lookup team by ID

```python
r = sdb("lookupteam.php?id=133604")
team = r["teams"][0]   # same 64-key structure as searchteams
```

### Get all teams in a league

```python
r = sdb("lookup_all_teams.php?id=4328")   # EPL id=4328
teams = r["teams"]    # up to 24 teams on free tier (actual EPL has 20)
```

**Free tier limit: 24 results** (confirmed with EPL which has exactly 20 — so all returned).

### Search for a player

```python
r = sdb("searchplayers.php?p=Mbappe")
players = r["player"]   # None if not found (note: key is "player" not "players")
if players:
    p = players[0]
    print(p["idPlayer"])        # "34162098"
    print(p["strPlayer"])       # "Kylian Mbappé"
    print(p["idTeam"])          # "133738"
    print(p["strTeam"])         # "Real Madrid"
    print(p["strNationality"])  # "France"
    print(p["strPosition"])     # "Centre-Forward"
    print(p["dateBorn"])        # "1998-12-20"
    print(p["strStatus"])       # "Active"
    print(p["strSport"])        # "Soccer"
    print(p["strThumb"])        # player photo URL
    print(p["strCutout"])       # transparent cutout URL
    print(p["relevance"])       # float — search relevance score
```

Search response has only 13 keys. For full player biography (69 keys including height, weight, description, social links):

```python
r = sdb("lookupplayer.php?id=34162098")
player = r["players"][0]   # note: "players" not "player"
print(player["strHeight"])         # "180 cm"
print(player["strWeight"])         # "73 kg"
print(player["strDescriptionEN"])  # Wikipedia-style bio
print(player["strFanart1"])        # fan art URL
```

### Get squad for a team

```python
r = sdb("lookup_all_players.php?id=133604")   # Arsenal
players = r["player"]    # up to 10 on free tier
```

**Free tier limit: 10 players per team** (usually returns coaching staff + selected players, not full squad).

### League metadata

```python
# Lookup a specific league by ID
r = sdb("lookupleague.php?id=4328")
league = r["leagues"][0]
print(league["strLeague"])          # "English Premier League"
print(league["strCurrentSeason"])   # "2025-2026"
print(league["intFormedYear"])      # "1992"
print(league["strCountry"])         # "England"
print(league["strSport"])           # "Soccer"
print(league["dateFirstEvent"])     # "1992-08-15"
print(league["strComplete"])        # "yes"
print(league["strBadge"])           # badge image URL
print(league["strLogo"])            # logo URL
print(league["strTvRights"])        # TV broadcast info (freeform text)
print(league["strNaming"])          # "{strHomeTeam} vs {strAwayTeam}"
```

League object has 47 keys including multi-language descriptions.

### Search leagues by country/sport

```python
# Both params required to get useful results
r = sdb("search_all_leagues.php?c=England&s=Soccer")
leagues = r["countries"]    # note: "countries" not "countrys"
# Returns up to 10 leagues on free tier

# Country only (still returns up to 36, all in UK Soccer for England)
r2 = sdb("search_all_leagues.php?c=England")
leagues2 = r2["countries"]
for l in leagues2:
    print(l["idLeague"], l["strLeague"], l["intDivision"])
# 4328  English Premier League  0
# 4329  English League Championship  2
# 4396  English League 1  3
# 4397  English League 2  4
# ...
```

**Response key is always `"countries"`, not `"countrys"`** (the URL path says "countrys" but the JSON response key is "countries").

**Free tier limit: 10 results** regardless of how many leagues exist.

### League seasons

```python
r = sdb("search_all_seasons.php?id=4328&round=1")
seasons = r["seasons"]
# Free tier limit: 5 seasons
# Each entry is just: {"strSeason": "2023-2024"}
for s in seasons:
    print(s["strSeason"])
# 1992-1993
# 1993-1994  ...
```

**Free tier limit: 5 seasons** per query. Newer seasons appear first (descending order).

### Standings / league table

```python
r = sdb("lookuptable.php?l=4328&s=2023-2024")
table = r["table"]
# Free tier limit: 5 rows (not the full 20-team table)
for row in table:
    print(f"{row['intRank']:2d}. {row['strTeam']:<25} {row['intPoints']}pts "
          f"P{row['intPlayed']} W{row['intWin']} D{row['intDraw']} L{row['intLoss']} "
          f"GD{row['intGoalDifference']}")
# 1. Manchester City           91pts P38 W28 D7 L3 GD62
```

Standings fields: `intRank`, `strTeam`, `idTeam`, `strBadge`, `intPlayed`, `intWin`, `intDraw`, `intLoss`, `intGoalsFor`, `intGoalsAgainst`, `intGoalDifference`, `intPoints`, `strForm`, `strDescription`, `strLeague`, `strSeason`, `dateUpdated`

**Free tier limit: 5 rows** — use a paid key to get the full table.

### Events (fixtures & results)

```python
# Next 15 events for a league
r = sdb("eventsnextleague.php?id=4328")
events = r["events"]

# Past 15 events for a league
r = sdb("eventspastleague.php?id=4328")
events = r["events"]

# All events for a season (free tier: 15)
r = sdb("eventsseason.php?id=4328&s=2023-2024")
events = r["events"]

# Events on a specific date (optionally filter by league name)
r = sdb("eventsday.php?d=2023-08-11&l=English+Premier+League")
events = r["events"]

# Next events for a specific team (returns 5 typically)
r = sdb("eventsnext.php?id=133604")
events = r["events"]

# Last events for a specific team
r = sdb("eventslast.php?id=133604")
events = r["results"]   # NOTE: key is "results" not "events"

# Lookup specific event by ID
r = sdb("lookupevent.php?id=1818395")
events = r["events"]
```

### Event object fields

```python
e = events[0]
print(e["idEvent"])          # "1818395"
print(e["strEvent"])         # "Burnley vs Manchester City"
print(e["strHomeTeam"])      # "Burnley"
print(e["strAwayTeam"])      # "Manchester City"
print(e["intHomeScore"])     # "0"  — STRING when finished, None when upcoming
print(e["intAwayScore"])     # "3"  — STRING when finished, None when upcoming
print(e["strStatus"])        # "Match Finished" | "Not Started" | None (older events)
print(e["dateEvent"])        # "2023-08-11"
print(e["strTime"])          # "19:00:00"  (UTC)
print(e["strTimeLocal"])     # "19:00:00"  (local)
print(e["dateEventLocal"])   # "2023-08-11"
print(e["strTimestamp"])     # "2023-08-11T19:00:00"
print(e["strLeague"])        # "English Premier League"
print(e["idLeague"])         # "4328"
print(e["strSeason"])        # "2023-2024"
print(e["intRound"])         # "1"
print(e["strVenue"])         # "Turf Moor"
print(e["strCountry"])       # "England"
print(e["strCity"])          # "Burnley"
print(e["strSport"])         # "Soccer"
print(e["strPostponed"])     # "no"
print(e["idHomeTeam"])       # "133604"
print(e["idAwayTeam"])       # "133613"
print(e["strHomeTeamBadge"]) # badge URL or None
print(e["strResult"])        # "" (empty string, not useful)
print(e["intSpectators"])    # "21567" or None
print(e["strThumb"])         # match thumbnail URL or None
print(e["strVideo"])         # highlight video URL or ""
```

Full event has 47 keys. Additional: `strEventAlternate`, `strFilename`, `strGroup`, `strDescriptionEN`, `strLeagueBadge`, `strBanner`, `strFanart`, `strSquare`, `strMap`, `strPoster`, `strOfficial`, `strWeather`, `strTweet1`, `intScore`, `intScoreVotes`, `idVenue`, `idAPIfootball`, `strLocked`.

### Search events by name

```python
r = sdb("searchevents.php?e=Arsenal+vs+Chelsea&s=2023-2024")
events = r["event"]    # note: "event" not "events"
# Returns up to 25 matching events across all seasons
# s= parameter filters by season string
```

### Lineup (match squads)

```python
r = sdb("lookuplineup.php?id=1818395")
lineup = r["lineup"]    # None for events with no lineup data
if lineup:
    for player in lineup:
        print(player["strPlayer"])       # "Emiliano Martinez"
        print(player["strTeam"])         # "Aston Villa"
        print(player["strPosition"])     # "Goalkeeper"
        print(player["strSubstitute"])   # "No" | "Yes"
        print(player["intSquadNumber"])  # "26"
        print(player["strHome"])         # "Yes" (home team) | "No" (away team)
        print(player["idPlayer"])        # player ID for lookupplayer
        print(player["strThumb"])        # player photo URL
        print(player["strCutout"])       # transparent cutout URL
```

### Venue details

```python
r = sdb("lookupvenue.php?id=15528")    # idVenue from team or event objects
venue = r["venues"][0]
print(venue["strVenue"])          # "Emirates Stadium"
print(venue["intCapacity"])       # "60338"
print(venue["strCountry"])        # "England"
print(venue["strLocation"])       # city/area
print(venue["strTimezone"])       # "Europe/London"
print(venue["strArchitect"])      # architect name
print(venue["intFormedYear"])     # year opened
print(venue["strDescriptionEN"])  # long description
print(venue["strMap"])            # Google Maps embed URL
print(venue["strThumb"])          # stadium photo URL
```

## Supported sports

The free tier (key=3) returns data across multiple sports. Confirmed working:
- Soccer / Football
- American Football (NFL)
- Basketball (NBA, etc.)
- Baseball (MLB, etc.)
- Ice Hockey (NHL, etc.)
- Tennis
- Rugby
- Cricket

Sport names are exact strings — use them verbatim in `s=` parameters.

```python
# NBA example
r = sdb("lookupleague.php?id=4387")     # NBA
r = sdb("searchteams.php?t=Los+Angeles+Lakers")
teams = r["teams"]   # returns 1 result
team = teams[0]
print(team["strSport"])   # "Basketball"
```

## Key league IDs (commonly used)

| League | id |
|--------|----|
| English Premier League | 4328 |
| English League Championship | 4329 |
| English League 1 | 4396 |
| English League 2 | 4397 |
| EFL Cup | 4570 |
| FA Cup | 4482 |
| UEFA Champions League | 4480 |
| NFL | 4391 |
| NBA | 4387 |
| MLB | 4424 |
| NHL | 4380 |

## Free tier result limits (confirmed)

| Endpoint | Limit |
|----------|-------|
| `eventsseason.php` | 15 events |
| `eventsnextleague.php` | 15 events |
| `eventspastleague.php` | 15 events |
| `eventsnext.php` (team) | ~5 events |
| `searchevents.php` | 25 events |
| `lookup_all_teams.php` | 24 teams |
| `lookup_all_players.php` | 10 players |
| `search_all_seasons.php` | 5 seasons |
| `search_all_leagues.php` | 10 leagues |
| `all_leagues.php` | 10 leagues |
| `lookuptable.php` | 5 rows |
| `all_sports.php` | 1 sport (Soccer only!) |
| `searchteams.php` | up to 1 (exact match only) |
| `searchplayers.php` | 2-5 results |

## V2 livescores (not available)

All v2 endpoints (`/api/v2/json/*/livescore.php`) return HTTP 404 regardless of the key used — including the example paid key `50130162` mentioned in various tutorials. As of April 2026, the v2 livescore endpoint appears to be decommissioned or never publicly released. There is no working livescore endpoint on the free tier.

## No-result behavior

```python
# Missing data returns None, NOT an empty list
r = sdb("searchteams.php?t=ZZZZNOTATEAM")
print(r["teams"])    # None  ← not []

r = sdb("searchplayers.php?p=ZZZZNOTAPLAYER")
print(r["player"])   # None  ← not []

# ALWAYS guard with: teams = r.get("teams") or []
```

## Gotchas

**API key "1" is dead** — Returns HTTP 404 for all endpoints. Use key `3`. Keys `2` and any string ("free", "test") also return 404. Only `3` (and presumably paid numeric keys) work.

**Scores are strings, not ints** — `intHomeScore` is `"3"` (a string), not `3`, when a match is finished. It is `None` (Python None) for upcoming matches. Cast before arithmetic: `int(e["intHomeScore"] or 0)`.

**"player" vs "players" key inconsistency** — `searchplayers.php` returns `r["player"]`, but `lookupplayer.php` returns `r["players"]`. These are different keys.

**"results" key for last team events** — `eventslast.php` returns `r["results"]`, not `r["events"]`. All other event endpoints use `r["events"]`.

**"countries" key for league search** — `search_all_leagues.php` returns JSON key `"countries"` (correct English), not `"countrys"` (which the endpoint URL path suggests).

**`lookuplineup` ignores invalid event IDs** — Passing a non-existent event ID does not return `None` or an empty list. It returns the lineup for the last cached event instead. Always cross-check `lineup[0]["idEvent"]` matches your requested event ID.

**All numeric IDs are strings** — `idTeam`, `idLeague`, `idEvent`, `idPlayer`, etc. are all returned as strings (`"133604"`), not integers. Don't use `==` against integer literals.

**`strStatus` can be `None` for historical events** — Older completed events have `strStatus: null` (Python `None`), not `"Match Finished"`. Check `intHomeScore is not None` as a more reliable way to detect a completed match.

**`eventsday.php?id=` filters by event ID, not league** — The `id=` parameter on `eventsday.php` does NOT filter by league ID. Use `l=` (league name as string) to filter by league.

**`searchteams.php` does partial matching inconsistently** — Searching for "Lakers" returns `None` (no match), but "Los Angeles Lakers" returns a result. For teams, use the full official name or use `lookup_all_teams.php` for a league and filter client-side.

**`all_sports.php` returns only Soccer on free tier** — Despite the endpoint name suggesting all sports, key=3 returns only one sport entry (Soccer). Use `search_all_leagues.php?s=Basketball` etc. to work with other sports.

**Image URLs are on r2.thesportsdb.com CDN** — Badge, logo, fanart, and player photo URLs use `https://r2.thesportsdb.com/images/media/...`. These load without authentication.

**`strTime` is in UTC** — Match times are stored in UTC. `strTimeLocal` and `dateEventLocal` reflect local kickoff time. Both are present on all event objects.
