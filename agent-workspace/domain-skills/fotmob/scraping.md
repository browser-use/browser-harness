# FotMob - League Tables, Fixtures and Match Stats

Field-tested against www.fotmob.com on 2026-11-03 using a Browser Use cloud browser, logged out. About 22 page loads; no CAPTCHA, challenge page, login wall or error page.

robots.txt (read in the browser 2026-11-03, `User-agent: *`): `Allow: /`, `Disallow: /api/*`, `/auth/*`, `/info`, `/health`, `/contact_us`. `/leagues/...` and `/matches/...` are allowed; the block reads robots.txt in the browser and refuses any path it disallows, and never requests `/api/*`.

## Quick summary

- **Data = the page's own embedded JSON.** FotMob is a Next.js site. Every league and match page ships its full data in `<script id="__NEXT_DATA__">` (about 1 MB). The block does a full page load and parses that tag. No `/api/*` call, no network sniffing.
- **League table page** (`/leagues/<id>/table/<slug>`): league name, country, season list, the table in 5 views (`all`, `home`, `away`, `xg`, `form`), and every fixture of the season with score, status and match URL (380 for the Premier League).
- **Past seasons:** add `?season=2025-2026` (what the page's own season dropdown puts in the URL). Calendar-year leagues use `?season=2025`.
- **Match page** (`/matches/<slug>/<code>`): score, status, venue, referee, player of the match, goals (with xG), cards, subs, both lineups with formation, coach, shirt and rating, and about 40 team stats (possession, xG, shots...).
- **Plain HTTP** also gets the same HTML with `__NEXT_DATA__` (curl, default UA, `/leagues/47/table/premier-league`: HTTP 200, 1.1 MB on 2026-11-03). The block below uses the browser.

## What works: table, fixtures, past season and match stats in one run

Self-contained; opens one background tab and closes it; 6 page loads (robots.txt, 3 league pages, 2 match pages), each after `about:blank` and a 3 s pause.

```python
import json, re, time
from urllib.parse import urlparse

BASE = "https://www.fotmob.com"
PACE_S = 3        # pause between page loads
CHUNK = 400_000   # characters per js() read of the embedded JSON

def _goto(url):
    cdp("Page.navigate", url="about:blank")   # always a full page load, never a client-side route change
    time.sleep(PACE_S)
    cdp("Page.navigate", url=url)
    wait_for_load()

def _robots_rules():
    _goto(BASE + "/robots.txt")
    txt = js("document.body.innerText")
    if "User-agent" not in (txt or ""):
        raise RuntimeError("could not read robots.txt")
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

def robots_allowed(path):
    """Google-style match for User-agent: *. Longest matching rule wins, Allow wins a tie."""
    best, ok = -1, True
    for allow, pat in RULES:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best or (len(pat) == best and allow)):
            best, ok = len(pat), allow
    return ok

def page_data(path):
    """Full page load of a www.fotmob.com page, then read the JSON the server embedded in it
    (<script id="__NEXT_DATA__">). Returns the parsed __NEXT_DATA__ object."""
    if not robots_allowed(path.split("#")[0].split("?")[0]):
        raise PermissionError(f"robots.txt disallows {path}")
    _goto(BASE + path)
    t0 = time.time()
    while True:
        host = urlparse(js("location.href")).hostname
        if host != "www.fotmob.com":
            raise RuntimeError(f"tab left www.fotmob.com ({host}); stop")
        n = js("(() => { const s = document.getElementById('__NEXT_DATA__'); if (!s) return -1;"
               " window.__fm = s.textContent; return window.__fm.length; })()")
        if n > 0:
            break
        title = (js("document.title") or "").lower()
        if "just a moment" in title or "attention required" in title or "access denied" in title:
            raise RuntimeError("challenge or block page: stop and back off, do not retry around it")
        if time.time() - t0 > 20:
            raise RuntimeError(f"no embedded data on {path}")
        time.sleep(0.5)
    text = "".join(js(f"window.__fm.slice({i}, {i + CHUNK})") for i in range(0, n, CHUNK))
    js("delete window.__fm")
    nd = json.loads(text)
    if nd.get("page") in ("/404", "/_error") or not nd.get("props", {}).get("pageProps"):
        raise LookupError(f"{path}: FotMob served its not-found page")
    return nd

def league(league_id, slug, season=None):
    """Table (all / home / away / xG / form) and every fixture of one season from the league's table page.
    season: '2025/2026' (or '2026' for calendar-year leagues); default = current."""
    q = f"?season={season.replace('/', '-')}" if season else ""
    nd = page_data(f"/leagues/{league_id}/table/{slug}{q}")
    pp = nd["props"]["pageProps"]
    d = pp["details"]
    if season and d["selectedSeason"] != season:
        raise RuntimeError(f"page shows season {d['selectedSeason']}, wanted {season} (valid: {pp['allAvailableSeasons'][:6]}...)")
    tables = []
    for block in pp.get("table") or []:
        data = block["data"]
        for t in ([data] if "table" in data else data.get("tables", [])):
            tables.append({"name": t.get("leagueName"), "rows": t["table"]})
    fixtures = [{"id": m["id"], "round": m.get("round"), "utc": m["status"].get("utcTime"),
                 "home": m["home"]["name"], "away": m["away"]["name"],
                 "score": m["status"].get("scoreStr"), "status": m["status"].get("reason", {}).get("short"),
                 "finished": m["status"].get("finished"), "cancelled": m["status"].get("cancelled"),
                 "url": m["pageUrl"]}
                for m in (pp.get("fixtures") or {}).get("allMatches", [])]
    return {"id": d["id"], "name": d["name"], "country": d["country"], "season": d["selectedSeason"],
            "seasons": pp["allAvailableSeasons"], "tables": tables, "fixtures": fixtures}

def standings(t, view="all"):
    """view: 'all', 'home', 'away', 'xg' or 'form' (last 5)."""
    rows = t["rows"][view]
    out = []
    for r in rows:
        row = {"pos": r["idx"], "team": r["name"], "id": r["id"], "p": r["played"], "w": r["wins"],
               "d": r["draws"], "l": r["losses"], "goals": r["scoresStr"], "gd": r["goalConDiff"], "pts": r["pts"]}
        if view == "xg":
            row.update(xg=round(r["xg"], 2), xga=round(r["xgConceded"], 2), xpts=round(r.get("xPoints") or 0, 2))
        out.append(row)
    return out

def match(page_url):
    """Score, events, lineups and team stats from a match page.
    page_url: a fixture 'url' from league(), e.g. '/matches/everton-vs-newcastle-united/2yo9qd#5795503'."""
    nd = page_data(page_url.split("#")[0])
    pp = nd["props"]["pageProps"]
    g, h, c = pp["general"], pp["header"], pp["content"]
    if "#" in page_url and str(g["matchId"]) != page_url.split("#")[1]:
        raise RuntimeError(f"page is match {g['matchId']}, wanted {page_url.split('#')[1]}")
    side = lambda e: None if e.get("isHome") is None else ("home" if e["isHome"] else "away")
    events = []
    for e in (c.get("matchFacts") or {}).get("events", {}).get("events", []):
        t = e["type"]
        if t not in ("Goal", "Card", "Substitution"):
            continue
        ev = {"min": e["time"], "added": e.get("overloadTime") or None, "type": t, "side": side(e)}
        if t == "Goal":
            ev.update(player=e.get("nameStr"), assist=e.get("assistStr"), own_goal=bool(e.get("ownGoal")),
                      xg=round((e.get("shotmapEvent") or {}).get("expectedGoals") or 0, 2) or None,
                      score="-".join(map(str, e["newScore"])) if e.get("newScore") else None)
        elif t == "Card":
            ev.update(player=e.get("nameStr"), card=e.get("card"))
        else:
            ev.update(player_in=e["swap"][0]["name"], player_out=e["swap"][1]["name"])
        events.append(ev)
    lineups = {}
    lu = c.get("lineup") or {}
    for s in ("homeTeam", "awayTeam"):
        t = lu.get(s)
        if not t:
            continue
        p = lambda x: {"name": x["name"], "shirt": x.get("shirtNumber"), "rating": (x.get("performance") or {}).get("rating")}
        lineups["home" if s == "homeTeam" else "away"] = {
            "team": t["name"], "formation": t.get("formation"), "coach": (t.get("coach") or {}).get("name"),
            "xi": [p(x) for x in t.get("starters", [])], "bench": [p(x) for x in t.get("subs", [])],
            "unavailable": [x["name"] for x in t.get("unavailable", [])]}
    stats = {}
    for grp in ((c.get("stats") or {}).get("Periods") or {}).get("All", {}).get("stats", []):
        for it in grp["stats"]:
            if it.get("type") != "title":
                stats.setdefault(it["title"], tuple(it["stats"]))
    info = (c.get("matchFacts") or {}).get("infoBox") or {}
    potm = (c.get("matchFacts") or {}).get("playerOfTheMatch") or {}
    st = h["status"]
    return {"id": g["matchId"], "league": g["leagueName"], "round": g.get("leagueRoundName"),
            "utc": g["matchTimeUTCDate"], "home": h["teams"][0]["name"], "away": h["teams"][1]["name"],
            "score": st.get("scoreStr"),
            "status": (st.get("reason") or {}).get("long") or ("Cancelled" if st.get("cancelled") else "Not started" if not st.get("started") else "Live"),
            "venue": (info.get("Stadium") or {}).get("name"), "referee": (info.get("Referee") or {}).get("text"),
            "player_of_match": ((potm.get("name") or {}).get("fullName"), (potm.get("rating") or {}).get("num")) if potm else None,
            "lineup_type": lu.get("lineupType"), "events": events, "lineups": lineups, "stats": stats}

tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
switch_tab(tab)
try:
    RULES = _robots_rules()
    print("robots: /leagues/47/table/x ->", robots_allowed("/leagues/47/table/x"),
          "| /matches/a/b ->", robots_allowed("/matches/a/b"), "| /api/data/leagues ->", robots_allowed("/api/data/leagues"))

    pl = league(47, "premier-league")
    t = pl["tables"][0]
    print(pl["name"], pl["country"], pl["season"], "| seasons:", pl["seasons"][:4], "| fixtures:", len(pl["fixtures"]))
    for r in standings(t)[:5]:
        print("  ", r)
    print("  xG leader:", max(standings(t, "xg"), key=lambda r: r["xg"]))

    done = [f for f in pl["fixtures"] if f["finished"]]
    nxt = [f for f in pl["fixtures"] if not f["finished"] and not f["cancelled"]][:3]
    print("played:", len(done), "| last:", done[-1]["utc"], done[-1]["home"], done[-1]["score"], done[-1]["away"])
    for f in nxt:
        print("  next:", f["utc"], f["home"], "vs", f["away"], f["url"])

    old = league(47, "premier-league", season="2025/2026")
    print(old["season"], "champion:", standings(old["tables"][0])[0], "| fixtures:", len(old["fixtures"]))

    mls = league(130, "mls")   # calendar-year season, several tables
    print(mls["name"], mls["season"], [(t["name"], len(t["rows"]["all"])) for t in mls["tables"]], "| fixtures:", len(mls["fixtures"]))

    m = match(done[-1]["url"])
    print(m["home"], m["score"], m["away"], "|", m["status"], m["utc"], m["league"], "round", m["round"],
          "|", m["venue"], "| ref", m["referee"], "| POTM", m["player_of_match"], "| lineups:", m["lineup_type"])
    for e in m["events"]:
        print("  ", e)
    for s in ("home", "away"):
        L = m["lineups"][s]
        print(s, L["team"], L["formation"], "coach", L["coach"], "| XI:", ", ".join(f'{p["shirt"]} {p["name"]} ({p["rating"]})' for p in L["xi"][:4]),
              "... | bench", len(L["bench"]), "| out:", L["unavailable"][:3])
    print({k: m["stats"][k] for k in ("Ball possession", "Expected goals (xG)", "Total shots", "Shots on target", "Corners") if k in m["stats"]})
    print("stat names:", len(m["stats"]))

    u = match(nxt[0]["url"])
    print("upcoming:", u["home"], "vs", u["away"], "|", u["status"], "| score", u["score"], "| lineups:", u["lineup_type"],
          {s: L["formation"] for s, L in u["lineups"].items()}, "| events", len(u["events"]), "| stats", len(u["stats"]))
finally:
    close_tab(tab)
```

Output observed on 2026-11-03:

```text
robots: /leagues/47/table/x -> True | /matches/a/b -> True | /api/data/leagues -> False
Premier League ENG 2026/2027 | seasons: ['2026/2027', '2025/2026', '2024/2025', '2023/2024'] | fixtures: 380
   {'pos': 1, 'team': 'Arsenal', 'id': 9825, 'p': 9, 'w': 8, 'd': 0, 'l': 1, 'goals': '14-5', 'gd': 9, 'pts': 24}
   {'pos': 2, 'team': 'Manchester City', 'id': 8456, 'p': 9, 'w': 7, 'd': 0, 'l': 2, 'goals': '20-10', 'gd': 10, 'pts': 21}
   {'pos': 3, 'team': 'Brighton & Hove Albion', 'id': 10204, 'p': 9, 'w': 6, 'd': 1, 'l': 2, 'goals': '24-7', 'gd': 17, 'pts': 19}
   {'pos': 4, 'team': 'Chelsea', 'id': 8455, 'p': 9, 'w': 5, 'd': 1, 'l': 3, 'goals': '19-15', 'gd': 4, 'pts': 16}
   {'pos': 5, 'team': 'Liverpool', 'id': 8650, 'p': 9, 'w': 4, 'd': 3, 'l': 2, 'goals': '11-9', 'gd': 2, 'pts': 15}
  xG leader: {'pos': 2, 'team': 'Manchester City', 'id': 8456, 'p': 9, 'w': 7, 'd': 0, 'l': 2, 'goals': '20-10', 'gd': 10, 'pts': 21, 'xg': 18.32, 'xga': 11.66, 'xpts': 17.24}
played: 90 | last: 2026-11-02T20:00:00Z Newcastle United 0 - 1 Everton
  next: 2026-11-06T20:00:00Z Everton vs Coventry City /matches/everton-vs-coventry-city/2hhimq#5795508
  next: 2026-11-07T12:30:00Z Leeds United vs Tottenham Hotspur /matches/leeds-united-vs-tottenham-hotspur/2ejdsf#5795511
  next: 2026-11-07T15:00:00Z Arsenal vs Hull City /matches/hull-city-vs-arsenal/2tt1fr#5795505
2025/2026 champion: {'pos': 1, 'team': 'Arsenal', 'id': 9825, 'p': 38, 'w': 26, 'd': 7, 'l': 5, 'goals': '71-27', 'gd': 44, 'pts': 85} | fixtures: 380
MLS 2026 [('Eastern', 15), ('Western', 15), ('Supporters Shield', 30)] | fixtures: 510
Newcastle United 0 - 1 Everton | Full-Time 2026-11-02T20:00:00.000Z Premier League round 9 | St. James' Park | ref John Brooks | POTM ('Thierno Barry', '7.8') | lineups: standard
   {'min': 32, 'added': None, 'type': 'Card', 'side': 'home', 'player': 'Daniel Burn', 'card': 'Yellow'}
   {'min': 49, 'added': None, 'type': 'Goal', 'side': 'away', 'player': 'Thierno Barry', 'assist': None, 'own_goal': False, 'xg': 0.99, 'score': '0-1'}
   {'min': 52, 'added': None, 'type': 'Card', 'side': 'away', 'player': 'Tyrique George', 'card': 'Yellow'}
   {'min': 64, 'added': None, 'type': 'Substitution', 'side': 'home', 'player_in': 'Yoane Wissa', 'player_out': 'Joseph Willock'}
   {'min': 64, 'added': None, 'type': 'Substitution', 'side': 'home', 'player_in': 'Sean Steur', 'player_out': 'Nico González'}
   {'min': 73, 'added': None, 'type': 'Card', 'side': 'away', 'player': 'David Moyes', 'card': 'Yellow'}
   {'min': 75, 'added': None, 'type': 'Substitution', 'side': 'home', 'player_in': 'Jacob Ramsey', 'player_out': 'Joelinton'}
   {'min': 76, 'added': None, 'type': 'Substitution', 'side': 'home', 'player_in': 'Jacob Murphy', 'player_out': 'Anthony Elanga'}
   {'min': 80, 'added': None, 'type': 'Substitution', 'side': 'away', 'player_in': 'Brennan Johnson', 'player_out': 'Thierno Barry'}
   {'min': 82, 'added': None, 'type': 'Substitution', 'side': 'away', 'player_in': 'Michael Keane', 'player_out': 'Jarrad Branthwaite'}
   {'min': 87, 'added': None, 'type': 'Substitution', 'side': 'home', 'player_in': 'Bazoumana Touré', 'player_out': 'Amar Dedić'}
   {'min': 90, 'added': 2, 'type': 'Substitution', 'side': 'away', 'player_in': 'Hayden Hackney', 'player_out': 'Tyrique George'}
   {'min': 90, 'added': 6, 'type': 'Card', 'side': 'home', 'player': 'Jacob Ramsey', 'card': 'Yellow'}
   {'min': 90, 'added': 8, 'type': 'Card', 'side': 'home', 'player': 'Jacob Ramsey', 'card': 'YellowRed'}
   {'min': 90, 'added': 9, 'type': 'Card', 'side': 'away', 'player': 'Brennan Johnson', 'card': 'Yellow'}
   {'min': 90, 'added': 9, 'type': 'Card', 'side': 'home', 'player': 'Fabian Schär', 'card': 'Yellow'}
home Newcastle United 4-2-3-1 coach Matthias Jaissle | XI: 21 Lukás Hornícek (7.5), 37 Amar Dedić (6.6), 5 Fabian Schär (7), 33 Daniel Burn (6.7) ... | bench 9 | out: []
away Everton 4-2-3-1 coach David Moyes | XI: 1 Jordan Pickford (7.7), 15 Jake O'Brien (7.6), 6 James Tarkowski (7.4), 4 Jarrad Branthwaite (7.8) ... | bench 9 | out: []
{'Ball possession': (52, 48), 'Expected goals (xG)': ('1.29', '2.34'), 'Total shots': (17, 16), 'Shots on target': (2, 5), 'Corners': (4, 5)}
stat names: 41
upcoming: Everton vs Coventry City | Not started | score None | lineups: predicted {'home': '4-2-3-1', 'away': '4-2-3-1'} | events 0 | stats 0
```

Checked against the rendered pages the same day: the table page showed `1 Arsenal 9 8 0 1 14-5 +9 24` and `2 Manchester City 9 7 0 2 20-10 +10 21`; the match page header showed `Newcastle United | Red cards: 1 | 0 - 1 | Full time | Everton | Barry 49'` and Top stats `Ball possession 52% 48%`, `Expected goals (xG) 1.29 2.34`, `Total shots 17 16`.

## Finding league ids

Ids and slugs are in every league URL (`/leagues/<id>/overview/<slug>`). The full list is in the robots-allowed sitemap `https://www.fotmob.com/sitemap/en/leagues.xml` (an index of 11 files, 426 league overview URLs on 2026-11-03). Some from it:

| id | slug | id | slug |
|---|---|---|---|
| 47 | premier-league | 42 | champions-league |
| 87 | laliga | 73 | europa-league |
| 54 | bundesliga | 77 | world-cup |
| 55 | serie | 50 | euro |
| 53 | ligue-1 | 57 | eredivisie |
| 130 | mls | 61 | liga-portugal |

Names repeat across countries: id 38 is Austria's `bundesliga`, Germany's is 54. Check `league()["country"]`.

## Fields

| Function | `__NEXT_DATA__.props.pageProps` path | Returned |
|---|---|---|
| `league()` | `details` | `id, name, country` (3-letter code), `season` (`selectedSeason`) |
| `league()` | `allAvailableSeasons` | `seasons`, newest first (`'2026/2027'` or `'2026'`) |
| `league()` | `table[].data.table` or `table[].data.tables[].table` | `tables[] {name, rows}`; `rows` has views `all, home, away, form, xg` |
| `standings()` | a `rows[view]` list | `pos, team, id, p, w, d, l, goals ('14-5'), gd, pts`; view `xg` adds `xg, xga, xpts` |
| `league()` | `fixtures.allMatches` | `id, round, utc, home, away, score ('0 - 1' or None), status ('FT'...), finished, cancelled, url` |
| `match()` | `general`, `header` | `id, league, round, utc, home, away, score, status ('Full-Time', 'Not started')` |
| `match()` | `content.matchFacts.infoBox`, `.playerOfTheMatch` | `venue, referee, player_of_match (name, rating)` |
| `match()` events | `content.matchFacts.events.events` | Goal: `player, assist, own_goal, xg, score`; Card: `player, card ('Yellow', 'YellowRed')`; Substitution: `player_in, player_out`; all have `min, added, side` |
| `match()` lineups | `content.lineup` | `lineup_type ('standard' or 'predicted')`; per side `team, formation, coach, xi[], bench[] {name, shirt, rating}, unavailable[]` |
| `match()` stats | `content.stats.Periods.All.stats[].stats[]` | `{title: (home, away)}`, 41 names for a Premier League match (ints, or strings like `'1.29'`) |

The raw page data has more: `content.shotmap.shots` (every shot with xG and coordinates), `content.playerStats` (per-player match stats keyed by player id), `content.h2h`, `content.momentum`, `content.weather`, and on the league page `stats` (top players/teams) and `transfers`.

## Gotchas

- Always a full page load. FotMob is a single-page app: picking 2025/2026 in the season dropdown changed the URL client-side, fetched `/api/data/leagues?id=47&...` (robots-disallowed), and left `__NEXT_DATA__` on 2026/2027. `_goto()` loads `about:blank` first so every page is a fresh server render.
- Season: the dropdown writes `?season=2025-2026`; the sitemap uses `?season=2025%2F2026`. The block uses the dropdown form and checks `details.selectedSeason` matches.
- Match slugs are not "home-vs-away": Arsenal (home) v Hull City is `/matches/hull-city-vs-arsenal/2tt1fr`. Take `url` from `league()["fixtures"]`, never build it. The `#<id>` part is client-only; `match()` strips it and checks `general.matchId`.
- Substitution `swap[0]` is the player coming on, `swap[1]` the player going off (checked: `swap[0]` names are in the `subs` list).
- Cards include coaches: `David Moyes` (Everton manager) got a Yellow event.
- `assist` was `None` for the one goal seen; no own goal or penalty was seen, so `own_goal=True` is untested.
- Upcoming match: `status` "Not started", no events or stats, `lineup_type` `'predicted'` with 11 per side. `header.status.reason` is missing before kick-off.
- `header.status.halfs` times are not UTC (`"02.11.2026 21:00:31"` for a 20:00 UTC kick-off); use `general.matchTimeUTCDate`.
- Multi-table competitions: MLS returns `Eastern`, `Western` and `Supporters Shield`; the Champions League 2026/2027 league phase is one 36-team table.
- Unknown league id (`/leagues/999999/table/nope`): FotMob serves its not-found page and `page_data` raises `LookupError`.
- The block reads `__NEXT_DATA__` in 400 KB slices; the payload is about 1 MB per page.

## What does not work

- `/api/*`: robots-disallowed for `User-agent: *`. Never requested. Pages call it themselves (seen: the season dropdown); the block does not read those responses.
- Season changes inside one loaded page: data comes from `/api/data/leagues`, not `__NEXT_DATA__`. Load the `?season=` URL instead.
- Site search: not used. Take ids from the league sitemap or the league URL.
