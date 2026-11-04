# NHL - Standings, Schedule, Scores and Player Stats

Field-tested against www.nhl.com, api-web.nhle.com and search.d3.nhle.com on 2026-11-04 using a Browser Use cloud browser, logged out. 5 full runs of the block below (about 20 API calls each); no CAPTCHA, challenge page, 403 or 429 inside the browser.

robots.txt (read in the browser 2026-11-04, `User-agent: *`): www.nhl.com allows `/` but disallows `/search`, `/js/`, `/css/`, `/errors`, `/redirect`, `/layouts`, `/templates`, `/views`, `/_*` and `/*/_*`; api-web.nhle.com and search.d3.nhle.com both say `Allow: /` with `Content-Signal: search=yes,ai-train=no,use=reference`, so use this for live lookups only, not for building datasets or training. Both API hosts also disallow `/` for named AI and training crawlers (GPTBot, ClaudeBot, anthropic-ai, CCBot, Google-Extended, Bytespider and others); a crawler running under one of those names must not use them. The block reads all three files and refuses any disallowed URL, including a redirect target.

## Quick summary

- **No scraping.** nhl.com's own app reads its data as JSON: the `/standings` page requests `api-web.nhle.com/v1/standings/now` (seen in its resource timing), and its player search calls `search.d3.nhle.com/api/v1/search/player` (in its `main.bundle.js`). Both answer CORS for `https://www.nhl.com`, so the block opens one nhl.com page and `fetch()`es from it with `credentials: 'omit'`. No key, no cookies.
- **Endpoints used** (all GET, `now` or a date):
  - `v1/standings/{now|YYYY-MM-DD}` - all 32 teams with league, conference, division and wild-card rank, GP, W-L-OTL, points, P%, RW, ROW, GF/GA, home/road/L10 splits, streak.
  - `v1/score/{now|YYYY-MM-DD}` - one game day with scores and how it ended (REG/OT/SO), plus `prevDate`/`nextDate`.
  - `v1/schedule/{now|YYYY-MM-DD}` - 7 days of league games. `v1/club-schedule/{TEAM}/month/{now|YYYY-MM}` - one team's month.
  - `v1/player/{id}/landing` - bio, current season, career totals, last 5 games (skaters and goalies).
  - `v1/skater-stats-leaders/current` and `v1/goalie-stats-leaders/current` - league leaders.
- **Values match the page.** `/standings` showed BOS 16 GP, 11-4-1, 23 pts, .719, L10 7-2-1, W2; the API row was the same.
- **Browser only.** Python `urllib` got 403 from www.nhl.com/robots.txt and api-web data paths on 2026-11-04. Do not change the user agent to get past it; run the calls in the tab.
- Serial calls with a 0.5 s pause; 429/5xx back off and retry, anything else raises. A 404 (unknown player id or team) returns `None`, never an empty list.

## What works: standings, scores, schedules and player stats in one run

Self-contained; opens one background tab (3 robots.txt files, then `/standings`), makes about 20 API calls, closes the tab. About 20 s in a cloud browser.

```python
import json, re, time, urllib.parse
from urllib.parse import urlparse

PAGE = "https://www.nhl.com/standings"          # robots-allowed page; its own app calls api-web.nhle.com
API = "https://api-web.nhle.com/v1/"
SEARCH = "https://search.d3.nhle.com/api/v1/search/player"
PAUSE = 0.5                                     # seconds between calls; serial only
HOSTS = ("www.nhl.com", "api-web.nhle.com", "search.d3.nhle.com")

# robots.txt, group "User-agent: *", Google-style wildcards: longest match wins, Allow wins a tie.
# Python urllib got 403 from www.nhl.com/robots.txt and api-web data paths (2026-11-04), so robots.txt is read in the tab.
def _parse_robots(txt):
    rules, in_star, prev_ua = [], False, False
    for line in txt.splitlines():
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        k = k.lower()
        if k == "user-agent":
            in_star = (in_star and prev_ua) or v == "*"
            prev_ua = True
            continue
        prev_ua = False
        if in_star and k in ("allow", "disallow") and v:
            rules.append((k == "allow", v))
    return rules

RULES = {}

def robots_allowed(url):
    u = urlparse(url)
    if u.hostname not in RULES:
        return False
    path = u.path + ("?" + u.query if u.query else "")
    best_len, ok = -1, True
    for allow, pat in RULES[u.hostname]:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best_len or (len(pat) == best_len and allow)):
            best_len, ok = len(pat), allow
    return ok

def _read_robots(host):
    goto_url(f"https://{host}/robots.txt")
    wait_for_load()
    txt = js("document.body ? document.body.innerText : ''") or ""
    if "user-agent" not in txt.lower():
        raise RuntimeError(f"no robots.txt at {host} ({page_info()['title']!r}); a challenge? Stop here.")
    RULES[host] = _parse_robots(txt)

def open_nhl_tab():
    """Reads the three robots.txt files, then opens one logged-out www.nhl.com page.
    The APIs answer CORS for that origin, so every fetch() runs from this tab. Returns the tab id."""
    tab = new_tab()
    for host in HOSTS:
        _read_robots(host)
    if not robots_allowed(PAGE):
        raise PermissionError(f"robots.txt disallows {PAGE}")
    goto_url(PAGE)
    wait_for_load()
    if js("location.origin") != "https://www.nhl.com":
        raise RuntimeError(f"landed on {page_info()['url']}; a block or challenge? Stop here.")
    return tab

FETCH_JS = """(async () => {
  try {
    const r = await fetch(%s, {credentials: 'omit'});
    return {status: r.status, url: r.url, text: await r.text(), retry_after: r.headers.get('retry-after')};
  } catch (e) { return {status: 0, error: String(e)}; }
})()"""

def get(url, tries=4):
    """Serial GET from the nhl.com tab. Returns parsed JSON, or None on 404.
    Retries 429/5xx with backoff, then raises; a failed call never looks like an empty result."""
    if not robots_allowed(url):
        raise PermissionError(f"robots.txt disallows {url}")
    for attempt in range(tries):
        r = js(FETCH_JS % json.dumps(url))
        st = r["status"]
        if st in (200, 404):
            if not robots_allowed(r["url"]):
                raise PermissionError(f"{url} redirected to disallowed {r['url']}")
            time.sleep(PAUSE)
            return json.loads(r["text"]) if st == 200 else None
        if st not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {st} {r.get('error', '')}; stopping, do not retry around it")
        ra = r.get("retry_after") or ""
        time.sleep(min(int(ra) if ra.isdigit() else 5 * 2 ** attempt, 60))

def _n(x):  # {"default": "Oilers", "fr": ...} -> "Oilers"
    return x.get("default") if isinstance(x, dict) else x

def standings(date="now"):
    """Rows in league order. date = 'now' or 'YYYY-MM-DD' (standings as of that day)."""
    d = get(API + f"standings/{date}")
    return [{
        "team": _n(s["teamAbbrev"]), "name": _n(s["teamName"]),
        "conf": s["conferenceName"], "div": s["divisionName"],
        "league_rank": s["leagueSequence"], "conf_rank": s["conferenceSequence"], "div_rank": s["divisionSequence"],
        "wildcard_rank": s["wildcardSequence"],
        "gp": s["gamesPlayed"], "w": s["wins"], "l": s["losses"], "otl": s["otLosses"], "pts": s["points"],
        "p_pct": round(s["pointPctg"], 3), "rw": s["regulationWins"], "row": s["regulationPlusOtWins"],
        "gf": s["goalFor"], "ga": s["goalAgainst"], "diff": s["goalDifferential"],
        "l10": f'{s["l10Wins"]}-{s["l10Losses"]}-{s["l10OtLosses"]}', "streak": f'{s["streakCode"]}{s["streakCount"]}',
        "clinch": s.get("clinchIndicator"),
    } for s in sorted(d["standings"], key=lambda s: s["leagueSequence"])]

def _game(g, date=None):
    a, h = g["awayTeam"], g["homeTeam"]
    out = g.get("gameOutcome") or {}
    return {
        "id": g["id"], "date": date or g.get("gameDate"), "start_utc": g["startTimeUTC"],
        "state": g["gameState"],                      # FUT/PRE not started, LIVE/CRIT in progress, FINAL/OFF over
        "away": a["abbrev"], "away_score": a.get("score"), "home": h["abbrev"], "home_score": h.get("score"),
        "ended_in": out.get("lastPeriodType"),        # REG | OT | SO
        "venue": _n(g.get("venue")), "type": {1: "pre", 2: "reg", 3: "playoff"}.get(g["gameType"], g["gameType"]),
        "url": "https://www.nhl.com" + g["gameCenterLink"] if g.get("gameCenterLink") else None,
    }

def league_week(date="now"):
    """7 days of league games starting at date ('now' = today, US Eastern)."""
    d = get(API + f"schedule/{date}")
    return {w["date"]: [_game(g, w["date"]) for g in w["games"]] for w in d["gameWeek"]}

def scores(date="now"):
    """One day's games with live or final scores, plus the API's own prev/next game days."""
    d = get(API + f"score/{date}")
    return {"date": d["currentDate"], "prev": d.get("prevDate"), "next": d.get("nextDate"),
            "games": [_game(g) for g in d["games"]]}

def team_month(team, month="now"):
    """A club's games for a month ('now' or 'YYYY-MM'), past ones with scores."""
    d = get(API + f"club-schedule/{team.upper()}/month/{month}")
    if d is None:
        raise ValueError(f"unknown team {team!r}")
    return [_game(g) for g in d["games"]]

def find_player(name, active=None, limit=20):
    """nhl.com's own player search (active=True/False filters, None = all). Its order is not by relevance
    ("mcdavid" lists Brian before Connor), so rank: exact name, then every word matched, then active first."""
    params = {"culture": "en-us", "limit": limit, "q": name}
    if active is not None:
        params["active"] = str(active).lower()
    words = name.lower().split()
    hits = [{"id": int(p["playerId"]), "name": p["name"], "pos": p["positionCode"], "active": p.get("active"),
             "team": p.get("teamAbbrev") or p.get("lastTeamAbbrev"), "number": p.get("sweaterNumber")}
            for p in get(f"{SEARCH}?{urllib.parse.urlencode(params)}")]
    return sorted(hits, key=lambda h: (h["name"].lower() != name.lower(),
                                       not all(w in h["name"].lower() for w in words), not h["active"]))

def player(pid):
    """Bio, current regular season, career totals and last 5 games. Skater or goalie."""
    p = get(API + f"player/{pid}/landing")
    if p is None:
        return None
    fs = (p.get("featuredStats") or {}).get("regularSeason") or {}
    return {
        "id": p["playerId"], "name": f'{_n(p["firstName"])} {_n(p["lastName"])}', "pos": p["position"],
        "team": p.get("currentTeamAbbrev"), "number": p.get("sweaterNumber"), "born": p.get("birthDate"),
        "country": p.get("birthCountry"), "shoots": p.get("shootsCatches"),
        "season": (p.get("featuredStats") or {}).get("season"), "this_season": fs.get("subSeason"),
        "career_regular": (p.get("careerTotals") or {}).get("regularSeason"),
        "last5": p.get("last5Games") or [],
        "url": f'https://www.nhl.com/player/{p["playerSlug"]}' if p.get("playerSlug") else None,
    }

def leaders(category="points", goalie=False, limit=5):
    """Current-season leaders. Skater: points goals assists plusMinus goalsPp goalsSh penaltyMins toi faceoffLeaders.
    Goalie: wins savePctg goalsAgainstAverage shutouts."""
    kind = "goalie" if goalie else "skater"
    d = get(API + f"{kind}-stats-leaders/current?categories={category}&limit={limit}")
    return [(f'{_n(x["firstName"])} {_n(x["lastName"])}', x["teamAbbrev"], x["value"]) for x in d[category]]

def line(g):
    sc = lambda s: "" if s is None else f" {s}"
    tail = f' ({g["ended_in"]})' if g["ended_in"] in ("OT", "SO") else ""
    return f'{g["away"]}{sc(g["away_score"])} @ {g["home"]}{sc(g["home_score"])} | {g["state"]}{tail} | {g["start_utc"]}'

tab = open_nhl_tab()
try:
    # 1. Standings: top 3 per division
    rows = standings()
    print("standings", len(rows), "teams")
    for div in ("Atlantic", "Metropolitan", "Central", "Pacific"):
        top = [r for r in rows if r["div"] == div][:3]
        print(" ", div, " | ".join(f'{r["team"]} {r["gp"]}gp {r["w"]}-{r["l"]}-{r["otl"]} {r["pts"]}pts L10 {r["l10"]} {r["streak"]}' for r in top))

    # 2. Scores: yesterday's finals (date from the API's own prevDate), then today's slate
    today = scores()
    last = scores(today["prev"])
    print("scores", last["date"], len(last["games"]), "games")
    for g in last["games"][:4]:
        print("  ", line(g))
    print("today", today["date"], len(today["games"]), "games;", [line(g) for g in today["games"][:2]])

    # 3. League schedule for the next 7 days, and one team's month
    wk = league_week()
    print("week", {d: len(gs) for d, gs in wk.items()})
    tor = team_month("TOR")
    print("TOR month", len(tor), "games; first:", line(tor[0]), "; last:", line(tor[-1]))

    # 4. Player lookup: search by name, then stats
    for name in ("McDavid", "Ullmark", "zzqx nobody"):
        hits = find_player(name)
        if not hits:
            print("no player", repr(name)); continue
        p = player(hits[0]["id"])
        print(p["name"], p["pos"], p["team"], f'#{p["number"]}', p["season"], p["this_season"])
        print("   career", {k: p["career_regular"].get(k) for k in ("gamesPlayed", "goals", "assists", "points", "wins", "savePctg") if k in p["career_regular"]})
        print("   last game", p["last5"][0] if p["last5"] else None, "|", p["url"])

    # 5. Leaders
    print("points", leaders("points"))
    print("save%", leaders("savePctg", goalie=True, limit=3))
    print("player 1 ->", player(1))

    # 6. Variants: standings as of a past day, a past month for one team, a retired player
    old = standings("2026-10-15")
    print("standings 2026-10-15 leader:", old[0]["team"], old[0]["gp"], "gp", old[0]["pts"], "pts")
    oct_ = team_month("EDM", "2026-10")
    print("EDM 2026-10", len(oct_), "games; last:", line(oct_[-1]))
    print("retired:", find_player("Wayne Gretzky", active=False)[:1])
    print("all players, 'mcdavid':", [(h["name"], h["active"]) for h in find_player("mcdavid")])
    try:
        team_month("XXX")
    except ValueError as e:
        print("bad team ->", e)
    print("robots /search on nhl.com allowed?", robots_allowed("https://www.nhl.com/search?q=mcdavid"))
finally:
    close_tab(tab)
```

Output observed on 2026-11-04:

```text
standings 32 teams
  Atlantic BOS 16gp 11-4-1 23pts L10 7-2-1 W2 | MTL 15gp 9-3-3 21pts L10 7-1-2 OT1 | TBL 14gp 9-3-2 20pts L10 6-2-2 W1
  Metropolitan CAR 17gp 12-3-2 26pts L10 7-2-1 L1 | NJD 15gp 10-5-0 20pts L10 8-2-0 W2 | NYR 16gp 8-7-1 17pts L10 4-5-1 W1
  Central MIN 17gp 11-3-3 25pts L10 7-1-2 W2 | UTA 16gp 10-6-0 20pts L10 6-4-0 W1 | DAL 15gp 9-5-1 19pts L10 7-3-0 W2
  Pacific EDM 16gp 11-2-3 25pts L10 6-2-2 OT1 | VGK 17gp 10-5-2 22pts L10 5-3-2 W1 | SEA 14gp 8-5-1 17pts L10 6-3-1 L1
scores 2026-11-03 11 games
   UTA 3 @ TOR 2 | OFF | 2026-11-04T00:00:00Z
   WPG 5 @ MTL 4 | OFF (OT) | 2026-11-04T00:00:00Z
   DET 2 @ TBL 4 | OFF | 2026-11-04T00:00:00Z
   STL 1 @ NYR 3 | OFF | 2026-11-04T00:00:00Z
today 2026-11-04 4 games; ['OTT @ BUF | FUT | 2026-11-05T00:30:00Z', 'CHI @ FLA | FUT | 2026-11-05T00:30:00Z']
week {'2026-11-04': 4, '2026-11-05': 11, '2026-11-06': 3, '2026-11-07': 12, '2026-11-08': 6, '2026-11-09': 3, '2026-11-10': 7}
TOR month 13 games; first: UTA 3 @ TOR 2 | OFF | 2026-11-04T00:00:00Z ; last: PHI @ TOR | FUT | 2026-12-01T00:30:00Z
Connor McDavid C EDM #97 20262027 {'assists': 31, 'gameWinningGoals': 0, 'gamesPlayed': 16, 'goals': 9, 'otGoals': 0, 'pim': 2, 'plusMinus': 20, 'points': 40, 'powerPlayGoals': 0, 'powerPlayPoints': 16, 'shootingPctg': 0.209302, 'shorthandedGoals': 1, 'shorthandedPoints': 1, 'shots': 43}
   career {'gamesPlayed': 810, 'goals': 418, 'assists': 842, 'points': 1260}
   last game {'assists': 1, 'gameDate': '2026-11-03', 'gameId': 2026020239, 'gameTypeId': 2, 'goals': 0, 'homeRoadFlag': 'R', 'opponentAbbrev': 'NJD', 'pim': 0, 'plusMinus': 0, 'points': 1, 'powerPlayGoals': 0, 'shifts': 27, 'shorthandedGoals': 0, 'shots': 1, 'teamAbbrev': 'EDM', 'toi': '24:15'} | https://www.nhl.com/player/connor-mcdavid-8478402
Linus Ullmark G OTT #35 20262027 {'gamesPlayed': 8, 'goalsAgainstAvg': 1.333136, 'losses': 1, 'otLosses': 0, 'savePctg': 0.945055, 'shutouts': 0, 'wins': 7}
   career {'gamesPlayed': 348, 'goals': 1, 'assists': 6, 'wins': 198, 'savePctg': 0.914588}
   last game {'decision': 'W', 'gameDate': '2026-10-21', 'gameId': 2026020153, 'gameTypeId': 2, 'gamesStarted': 1, 'goalsAgainst': 1, 'homeRoadFlag': 'H', 'opponentAbbrev': 'FLA', 'penaltyMins': 0, 'savePctg': 0.944444, 'shotsAgainst': 18, 'teamAbbrev': 'OTT', 'toi': '43:35'} | https://www.nhl.com/player/linus-ullmark-8476999
no player 'zzqx nobody'
points [('Connor McDavid', 'EDM', 40), ('Leon Draisaitl', 'EDM', 29), ('Evan Bouchard', 'EDM', 28), ('Nathan MacKinnon', 'COL', 27), ('Kirill Kaprizov', 'MIN', 26)]
save% [('Linus Ullmark', 'OTT', 0.945055), ('Daniil Tarasov', 'DET', 0.926829), ('Igor Shesterkin', 'NYR', 0.926606)]
player 1 -> None
standings 2026-10-15 leader: VGK 9 gp 14 pts
EDM 2026-10 13 games; last: EDM 4 @ NYI 0 | OFF | 2026-10-31T18:00:00Z
retired: [{'id': 8447400, 'name': 'Wayne Gretzky', 'pos': 'C', 'active': False, 'team': 'NYR', 'number': 99}]
all players, 'mcdavid': [('Connor McDavid', True), ('Brian McDavid', False)]
bad team -> unknown team 'XXX'
robots /search on nhl.com allowed? False
```

## Fields

| Function | Returns | Notes |
|---|---|---|
| `standings(date)` | list of team dicts, league order | `team, name, conf, div, league_rank, conf_rank, div_rank, wildcard_rank, gp, w, l, otl, pts, p_pct, rw, row, gf, ga, diff, l10, streak, clinch`. Raw rows also carry `home*`, `road*`, `l10*`, `shootoutWins/Losses`, `waiversSequence`. |
| `scores(date)` | `{date, prev, next, games}` | Game: `id, date, start_utc, state, away, away_score, home, home_score, ended_in, venue, type, url`. Raw games also carry `goals[]` (scorer, assists, time) and `clock`. |
| `league_week(date)` | `{YYYY-MM-DD: [game]}` | 7 days from `date`. Raw games carry `tvBroadcasts`, `ticketsLink`, odds. |
| `team_month(team, month)` | `[game]` | `team` = 3-letter abbrev (`TOR`, `EDM`, `UTA`...). |
| `find_player(name, active)` | `[{id, name, pos, active, team, number}]` | Ranked: exact name, all words matched, active first. |
| `player(id)` | dict or `None` | `this_season` and `career_regular` keys differ by position: skaters `goals, assists, points, plusMinus, shots...`; goalies `wins, losses, otLosses, savePctg, goalsAgainstAvg, shutouts`. Raw landing also has `seasonTotals[]` (every season and league), `careerTotals.playoffs`, `awards`, `draftDetails`. |
| `leaders(category, goalie)` | `[(name, team, value)]` | Skater: `points goals assists plusMinus goalsPp goalsSh penaltyMins toi faceoffLeaders`. Goalie: `wins savePctg goalsAgainstAverage shutouts`. |

## Gotchas

- Game dates are US Eastern game days; `startTimeUTC` is often the next UTC day (UTA @ TOR on 2026-11-03 started `2026-11-04T00:00:00Z`). The November TOR month ends with a game at `2026-12-01T00:30:00Z`, which is Nov 30 in Toronto.
- `gameState`: `FUT` not started (no `score` key, so scores are `None`), `OFF` over (all 11 games of 2026-11-03). `PRE`, `LIVE`, `CRIT` and `FINAL` are the other states in nhl.com's `main.bundle.js`; no game was live during this test, so check `state` rather than assuming a score is final.
- `/now` and `current` paths 307-redirect to dated or season paths (`/v1/standings/2026-11-04`, `/v1/skater-stats-leaders/20262027/2`); `fetch()` follows them and the block re-checks the final URL against robots.txt.
- Seasons are 8-digit ids (`20262027`); `gameType` 1 = preseason (VGK Sept 2026), 2 = regular, 3 = playoffs (VGK May 2026).
- Names are objects like `{"default": "Oilers", "fr": "..."}`; `_n()` takes `default`.
- Player search order is not relevance: `mcdavid` lists Brian McDavid before Connor, `Wayne Gretzky` lists Wayne Savage first. `find_player()` re-ranks; use the full name for retired players. `active=true` returns only current players, `active=false` only retired ones; omit it for both.
- `last5Games` is newest first and only lists games the player appeared in (Ullmark's latest was 2026-10-21 on 2026-11-04).
- Unknown player ids and team codes return HTTP 404 with an HTML body; `get()` returns `None` and `team_month()` raises `ValueError`.

## What does not work

- `www.nhl.com/search`: robots-disallowed. The block finds players through `search.d3.nhle.com`, the endpoint nhl.com's own player search uses.
- Plain HTTP from Python (`urllib`): 403 on www.nhl.com/robots.txt and api-web data paths. Not worked around.
- `fetch()` from any origin other than `https://www.nhl.com`: the APIs send `access-control-allow-origin: https://www.nhl.com`, so open an nhl.com page first.
- Not covered: `api.nhle.com/stats/rest/...` (the stats-table backend), game play-by-play and box scores.
