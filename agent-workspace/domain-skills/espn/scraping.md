# ESPN - NBA and NFL Scores, Schedules and Standings

Field-tested against www.espn.com on 2026-10-31 using a Browser Use cloud browser, logged out. No CAPTCHA, consent wall or block seen across 20+ page loads.

robots.txt (checked 2026-10-31, `User-agent: *`) has no rule matching `/nba/scoreboard`, `/nfl/scoreboard`, `/nba/schedule`, `/nfl/schedule`, `/{nba,nfl}/standings` or their `/_/week/<n>/year/<yyyy>/seasontype/<n>`, `/_/group/<g>` and `/_/season/<yyyy>` forms, but disallows `*/date/` (every NBA day-picker URL), `*/boxscore?`, `*/playbyplay?`, `*/season/200`, `*/year/200`, `/*&sort=*`, `/*?platform=` and `/*&xhr=1`. `site.api.espn.com` answered its robots.txt with 403, so this skill reads only the state the allowed page ships in its own HTML.

## Quick summary

- **One object has everything.** Every scoreboard, schedule and standings page server-renders its data into `window.__espnfitt__.page.content`. Read it with one `js()` call; no clicking, scrolling or DOM parsing. Values matched the rendered page (checked: NE 24 @ CHI 30, week 7; NBA East order DET, PHI, BOS...).
- **Scores:** `/nba/scoreboard` = today, `/nfl/scoreboard` = current week. Past or future NFL weeks: `/nfl/scoreboard/_/week/7/year/2026/seasontype/2` (the page lists every week's path in `season.weeks`).
- **NBA past days:** day URLs (`/nba/scoreboard/_/date/YYYYMMDD`) are robots-disallowed. Use `/nba/schedule` instead: it shows 9 days starting yesterday, and yesterday carries final scores. Older NBA days are out of scope for this skill.
- **Standings:** `/nba/standings` (conferences), `/nfl/standings` (divisions). `/_/group/league|conference|division` and `/_/season/2026` work. Stats are a flat array; map it with the page's own `headers` (`i` = array index).
- The block fetches robots.txt once and refuses any path it disallows, including a redirect target.

## What works: scores, schedule and standings in one run

Self-contained; opens one tab and reuses it for 11 page loads (15-20 s in a cloud browser).

```python
import json, re, time, urllib.request
from urllib.parse import urlparse

BASE = "https://www.espn.com"

# robots.txt, group "User-agent: *", wildcard rules matched Google-style:
# longest matching pattern wins, Allow wins a tie.
def _robots_rules():
    txt = urllib.request.urlopen(BASE + "/robots.txt", timeout=20).read().decode()
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

RULES = _robots_rules()

def robots_allowed(path):
    best_len, ok = -1, True
    for allow, pat in RULES:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best_len or (len(pat) == best_len and allow)):
            best_len, ok = len(pat), allow
    return ok

_TAB = []

def espn_content(path):
    """Open an allowed www.espn.com page and return the state it ships in its own HTML
    (window.__espnfitt__.page.content). Raises on a disallowed path or a page without that state."""
    if not robots_allowed(path):
        raise PermissionError(f"robots.txt disallows {path}")
    if _TAB:
        goto_url(BASE + path)
    else:
        new_tab(BASE + path)
        _TAB.append(current_tab())
    wait_for_load()
    for _ in range(30):
        raw = js("(() => { const f = window.__espnfitt__;"
                 " return f && f.page && f.page.content ? JSON.stringify(f.page.content) : null })()")
        if raw:
            u = urlparse(page_info()["url"])
            final = u.path + ("?" + u.query if u.query else "")
            if not robots_allowed(final):
                raise PermissionError(f"{path} redirected to disallowed {final}")
            return json.loads(raw)
        time.sleep(0.5)
    info = page_info()
    raise RuntimeError(f"no page state on {info['url']} ({info['title']!r}); "
                       "a block or challenge page? Stop here, do not retry around it.")

def _game(e):
    comps = e.get("competitors") or []
    home = next((c for c in comps if c.get("isHome")), {})
    away = next((c for c in comps if not c.get("isHome")), {})
    st = e.get("status") or {}
    venue = e.get("vnue") or e.get("venue") or {}
    pre = st.get("state") == "pre"                  # schedule pages send 0-0 for games not started
    return {
        "id": e.get("id"),
        "date_utc": e.get("date"),                  # "2026-10-30T00:15Z"
        "state": st.get("state"),                   # pre | in | post
        "status": st.get("detail"),                 # "Final", "Final/OT", "11/1 - 1:00 PM EST", "Q3 5:12"
        "away": away.get("abbrev"), "away_score": None if pre else away.get("score"),
        "home": home.get("abbrev"), "home_score": None if pre else home.get("score"),
        "winner": next((c.get("abbrev") for c in comps if c.get("winner")), None),
        "venue": venue.get("fullName"),
        "tv": [b["name"] for b in e.get("broadcasts") or [] if isinstance(b, dict) and b.get("name")],
        "url": BASE + e["link"] if e.get("link") else None,
    }

def _week_path(week, year, seasontype):
    # NFL only. NBA days live under */date/, which robots.txt disallows.
    return f"/_/week/{week}/year/{year}/seasontype/{seasontype}" if week is not None else ""

def scoreboard(league, week=None, year=None, seasontype=2):
    """Games on the default scoreboard: NBA = today, NFL = current week (or week/year/seasontype)."""
    sb = espn_content(f"/{league}/scoreboard" + _week_path(week, year, seasontype))["scoreboard"]
    weeks = (sb.get("season") or {}).get("weeks") or []
    return {
        "heading": sb.get("pgeHding"),
        "requested": sb.get("requestedDates"),      # NBA {'date':...} / NFL {'year','seasontype','week'}
        "games": [_game(e) for e in sb.get("evts") or []],
        "bye": [t.get("abbrev") for t in sb.get("byeTms") or []],
        "weeks": [{"label": w.get("label"), "path": w.get("url"), "dates": w.get("dateRange")} for w in weeks],
    }

def schedule(league, week=None, year=None, seasontype=2):
    """Schedule page: NBA = 9 days from yesterday (yesterday has final scores), NFL = one week."""
    c = espn_content(f"/{league}/schedule" + _week_path(week, year, seasontype))
    return {
        "heading": c.get("pageHeading"),
        "requested": c.get("requestedDates"),
        "days": {d: [_game(e) for e in evs] for d, evs in (c.get("events") or {}).items()},
        "bye": [t.get("abbrev") for t in c.get("byeTeams") or []],
    }

def standings(league, group=None, season=None):
    """Standings rows in page order. group: league | conference | division (default = page default)."""
    path = f"/{league}/standings"
    if season or group:
        path += "/_" + (f"/season/{season}" if season else "") + (f"/group/{group}" if group else "")
    st = espn_content(path)["standings"]
    cols = {h["i"]: h["t"] for h in st["groups"]["headers"].values()}
    rows = []
    def walk(g, names):
        names = names + [g["name"]] if g.get("name") else names
        for pos, s in enumerate(g.get("standings") or [], 1):
            t = s.get("team") or {}
            row = {"group": " / ".join(names), "pos": pos, "team": t.get("displayName"), "abbrev": t.get("abbrev")}
            row.update({cols[i]: v for i, v in enumerate(s.get("stats") or []) if i in cols})
            rows.append(row)
        for ch in g.get("children") or []:
            walk(ch, names)
    for g in st["groups"]["groups"]:
        walk(g, [])
    return {"heading": st.get("pageHeading"), "requested": st.get("requestedDates"),
            "active": (st.get("filters") or {}).get("active"), "rows": rows}

def show(g):
    a = f"{g['away']} {g['away_score']}" if g["away_score"] is not None else g["away"]
    h = f"{g['home']} {g['home_score']}" if g["home_score"] is not None else g["home"]
    return f"{a} @ {h} | {g['status']} | {g['venue']}"

# 1. Scores: NBA today, NFL current week, NFL last week
boards = {lg: scoreboard(lg) for lg in ("nba", "nfl")}
for sb in boards.values():
    print(sb["heading"], sb["requested"], len(sb["games"]), "games")
    for g in sb["games"][:4]:
        print("  ", show(g))
cur = boards["nfl"]["requested"]
prev = scoreboard("nfl", week=cur["week"] - 1, year=cur["year"], seasontype=cur["seasontype"])
print(prev["heading"], prev["requested"], "bye:", prev["bye"])
for g in prev["games"][:3]:
    print("  ", show(g), "| winner", g["winner"])
time.sleep(1)

# 2. Schedule: NBA next days (yesterday's finals included), NFL current week
nba_sched = schedule("nba")
for d, games in nba_sched["days"].items():
    print("NBA", d, len(games), "games;", (show(games[0]) if games else "-"))
nfl_sched = schedule("nfl")
print(nfl_sched["requested"], {d: len(v) for d, v in nfl_sched["days"].items()}, "bye:", nfl_sched["bye"])
time.sleep(1)

# 3. Standings: NBA by conference (page default), NFL by division (page default)
for lg, keys in (("nba", ("wins", "losses", "winpercent", "gamesbehind", "streak", "lasttengames")),
                 ("nfl", ("wins", "losses", "ties", "winpercent", "pointsfor", "pointsagainst", "streak"))):
    s = standings(lg)
    print(s["heading"], s["active"], len(s["rows"]), "rows")
    for r in s["rows"][:5]:
        print("  ", r["group"], r["pos"], r["abbrev"], [r.get(k) for k in keys])

# 4. Variants: whole league, NFL by conference, last NBA season; a /date/ URL is refused before loading
for lg, grp, season in (("nba", "league", None), ("nfl", "conference", None), ("nba", None, 2026)):
    s = standings(lg, group=grp, season=season)
    top = s["rows"][0]
    print(s["heading"], s["active"], len(s["rows"]), "rows; first:", top["group"], top["abbrev"], top.get("wins"), top.get("losses"))
nxt = schedule("nfl", week=cur["week"] + 1, year=cur["year"], seasontype=cur["seasontype"])
print("NFL next week", nxt["requested"], sum(len(v) for v in nxt["days"].values()), "games, bye:", nxt["bye"])
print("date URL allowed?", robots_allowed("/nba/scoreboard/_/date/20261030"))
```

Output observed on 2026-10-31 (trimmed):

```text
NBA Scoreboard {'year': 2027, 'seasontype': 2, 'date': '2026-10-31'} 7 games
   POR @ UTAH | 10/31 - 3:00 PM EDT | Delta Center
NFL Scoreboard {'year': 2026, 'seasontype': 2, 'week': 8} 14 games
   CAR 19 @ GB 27 | Final | Lambeau Field
   BAL @ BUF | 11/1 - 1:00 PM EST | Highmark Stadium
NFL Scoreboard {'year': 2026, 'seasontype': 2, 'week': 7} bye: ['BUF', 'LAC', 'WSH', 'JAX']
   NE 24 @ CHI 30 | Final | Soldier Field | winner CHI
   PIT 16 @ NO 10 | Final | Stade de France | winner PIT
NBA 20261030 10 games; CHA 79 @ WSH 95 | Final | Capital One Arena
NBA 20261031 7 games; POR @ UTAH | Sat, October 31st at 3:00 PM EDT | Delta Center
NBA 20261103 0 games; -
{'year': 2026, 'seasontype': 2, 'week': 8} {'20261029': 1, '20261101': 12, '20261102': 1} bye: ['NO', 'NYG', 'SF', 'HOU']
NBA Standings 2026-27 {'group': 'conference', 'view': 'standings'} 30 rows
   Eastern Conference 1 DET ['5', '1', '.833', '-', 'W2', '5-1']
NFL Standings 2026 {'group': 'division', 'view': 'standings'} 32 rows
   American Football Conference / AFC East 1 BUF ['5', '1', '0', '.833', '197', '171', 'W2']
NBA Standings 2026-27 {'group': 'league', 'view': 'standings'} 30 rows; first: National Basketball Association MEM 5 0
NFL Standings 2026 {'group': 'conference', 'view': 'standings'} 32 rows; first: American Football Conference KC 5 1
NBA Standings 2025-26 {'group': 'conference', 'view': 'standings'} 30 rows; first: Eastern Conference DET 60 22
NFL next week {'year': 2026, 'seasontype': 2, 'week': 9} 15 games, bye: ['TEN', 'PIT']
date URL allowed? False
```

## Fields

| Page | Path in `page.content` | Notes |
|---|---|---|
| Scoreboard | `scoreboard.evts[]` | `competitors[]` (`abbrev`, `isHome`, `score`, `winner`, `records`), `status.{state,detail}`, `vnue`, `broadcasts`, `lnescrs` (`{awy, hme, lbls}` per period), `odds`, `link` |
| Scoreboard | `scoreboard.requestedDates`, `scoreboard.byeTms`, `scoreboard.season.weeks[]` | NFL week list has `url`, `label`, `dateRange` |
| Schedule | `events` = `{YYYYMMDD: [game]}`, `byeTeams`, `requestedDates` | Same game shape, but `venue` (not `vnue`) and `status.detail` like "Sun, November 1st at 1:00 PM EST" |
| Standings | `standings.groups.headers` = `{key: {t, a, d, i}}` | `i` indexes each team's `stats` array, `a` is the column label (W, L, PCT, GB, STRK, L10...) |
| Standings | `standings.groups.groups[]` | NBA: `{name, standings[]}`. NFL division view: `{name, children: [{name, standings[]}]}` |

`_game()` output: `id, date_utc, state (pre|in|post), status, away, away_score, home, home_score, winner, venue, tv, url`. Standings rows: `group, pos, team, abbrev` plus every header key (`wins, losses, ties, winpercent, gamesbehind, streak, home, road, vsdiv, vsconf, pointsfor, pointsagainst, lasttengames...`), all as display strings.

## Gotchas

- Schedule pages send `score: 0` for games not yet played; `_game()` sets scores to `None` when `state == "pre"`.
- Key names differ by page: scoreboard uses `vnue`, `byeTms`, `pgeHding`; schedule uses `venue`, `byeTeams`, `pageHeading`.
- NBA `requestedDates.year` is the season's end year (2027 for 2026-27); `/_/season/2026` gives 2025-26 standings.
- `*/season/200` and `*/year/200` mean seasons 2000-2009 are disallowed; the guard catches them.
- NFL `stats` columns `divisionties` / `divisionwins` hold odd values ("0.000"); use `vsdiv` for the division record.
- Standings rows come in the page's display order; `pos` is the position inside its group, `playoffseed` is ESPN's seed.

## What does not work

- NBA day navigation (`/nba/scoreboard/_/date/...`, `/nba/schedule/_/date/...`): robots-disallowed. Not used.
- Box scores and play-by-play query URLs (`*/boxscore?`, `*/playbyplay?`): robots-disallowed. Game links in `url` are `/nba/game/_/gameId/<id>/...` summary pages.
- `site.api.espn.com` JSON endpoints: its robots.txt answered 403 to a plain request on 2026-10-31, so this skill does not call them.
