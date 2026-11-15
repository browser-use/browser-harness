# Sleeper - League Rosters, Matchups and Trending Players (official read-only API + sleeper.com player pages)

Field-tested against api.sleeper.app and sleeper.com on 2026-11-04 (UTC) using a Browser Use cloud browser, logged out. API calls are same-origin `fetch()` from an api.sleeper.app tab; Rostered % and Started % come from sleeper.com player pages. No CAPTCHA, 403 or 429 across about 130 API calls and about 20 sleeper.com page loads.

robots.txt (read in the browser 2026-11-04): api.sleeper.app has only comments (its `User-agent: *` / `Disallow: /` lines are commented out), so nothing is disallowed; sleeper.com is `User-Agent: *` / `Allow: /` (sleeper.app/robots.txt redirects there). The API is Sleeper's documented public read-only API (https://docs.sleeper.com): no key, free for non-commercial use, and "stay under 1000 API calls per minute, otherwise, you risk being IP-blocked".

## Quick summary

- **API first.** JSON, no key, no cookies, `access-control-allow-origin: *`. All under `https://api.sleeper.app/v1`:
  - `/state/nfl` - current NFL season and week (`week`, `season`, `season_type`, `league_season`).
  - `/league/<league_id>` - name, season, status (`pre_draft`, `drafting`, `in_season`, `complete`), settings, scoring, `roster_positions`.
  - `/league/<league_id>/users` and `/league/<league_id>/rosters` - managers and their rosters (player ids, starters, IR, taxi, W-L, points).
  - `/league/<league_id>/matchups/<week>` - one row per team; two rows with the same `matchup_id` play each other.
  - `/league/<league_id>/winners_bracket` and `/losers_bracket` - playoff games by `roster_id`.
  - `/players/nfl/trending/<add|drop>?lookback_hours=<h>&limit=<n>` - most added or dropped players across all Sleeper leagues.
  - `/players/nfl` - the player map that turns ids like `"4046"` or `"PHI"` into names. 14.7 MB and 12,229 players today (the docs say about 5 MB); the docs ask for at most one call a day, so the blocks cache it in `sleeper-players-nfl.json` for 24 h. `?position=QB&active=true` (435 KB, 355 players) and `?position=DEF` (5.7 KB, 32 teams) are documented filters.
- **League pages on sleeper.com need a login.** `https://sleeper.com/leagues/<id>` redirected to `https://sleeper.com/?redirect=%2Fleagues%2F<id>&login=` logged out, so league data comes only from the API.
- **Finding a league id:** it is the number in the league's URL (`sleeper.com/leagues/<league_id>/...`). From a username: `/user/<username>` gives `user_id`, then `/user/<user_id>/leagues/nfl/<season>` lists that user's leagues. An unknown username returns HTTP 200 with body `null`.
- **sleeper.com player pages** (`https://sleeper.com/nfl/players/<player_id>`) show position rank, overall rank, Rostered % and Started % across Sleeper. Block 3 reads them for the top trending players.
- `get()` runs one call at a time with a 0.1 s pause (far under 1000/min), retries 429/5xx with backoff, and otherwise raises. A failed call never comes back as an empty result.
- Sleeper's official trending embed, `https://sleeper.app/embed/players/nfl/trending/add?lookback_hours=24&limit=25`, is an HTML table of name, position - team and count (the player id only appears in the thumbnail URL). It loaded fine; the blocks use the JSON endpoint instead.

## What works

Every block carries the same helpers so it runs on its own: `on_api_tab()` opens `https://api.sleeper.app/v1/state/nfl` once (later blocks reuse that tab), `get(path)` fetches `https://api.sleeper.app/v1<path>` and reads the body back in 500 KB slices, `player_map()` loads or refreshes the cached player map, `pname()` formats a player id as `Name POS TEAM`, `pts()` joins Sleeper's split point fields, and `team_names()` maps `roster_id` to the team name a manager set (else their display name). The cache file is written to the current directory.

The examples use league `289646328504385536`, the league id in Sleeper's API docs examples; today it is the "Sleeper Friends League" (2018, complete). Put your own league id in `LEAGUE_ID`.

### 1. League, standings and every roster with player names (browser)

```python
import json, os, time

LEAGUE_ID = "289646328504385536"   # the number in a league URL, sleeper.com/leagues/<league_id>/...; this is the example league from Sleeper's API docs

API = "https://api.sleeper.app/v1"
PAUSE = 0.1        # serial calls; Sleeper's docs: stay under 1000 calls/min or risk an IP block
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab
PLAYERS_FILE = "sleeper-players-nfl.json"   # full NFL player map (~15 MB); the docs ask for at most one fetch a day

def on_api_tab():
    """All calls run as same-origin fetch() in a logged-out api.sleeper.app tab; reuse it if already there."""
    try:
        if js("location.origin") == "https://api.sleeper.app":
            return
    except Exception:
        pass
    new_tab(API + "/state/nfl")   # small JSON answer on the API host
    wait_for_load()

FETCH_JS = """(async () => {
  try {
    const r = await fetch(%s, {credentials: 'omit'});
    window.__sl = await r.text();
    return {status: r.status, len: window.__sl.length, retry_after: r.headers.get('retry-after')};
  } catch (e) { window.__sl = ''; return {status: 0, error: String(e)}; }
})()"""

def get(path, tries=4):
    """Serial GET of api.sleeper.app/v1<path>. Returns parsed JSON, or None on 404 or a JSON null (unknown user).
    Retries 429/5xx with backoff, then raises: a failed call never looks like an empty result."""
    url = API + path
    for attempt in range(tries):
        meta = js(FETCH_JS % json.dumps(url))
        status = meta["status"]
        if status in (200, 404):
            text = "".join(js(f"window.__sl.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
            js("window.__sl = ''")
            time.sleep(PAUSE)
            return json.loads(text) if status == 200 else None
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('error', '')}; stopping")
        ra = meta.get("retry_after") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def player_map():
    """player_id -> player dict. Reuses PLAYERS_FILE if under 24 h old, else downloads /players/nfl once and saves it."""
    try:
        if time.time() - os.path.getmtime(PLAYERS_FILE) < 86400:
            with open(PLAYERS_FILE) as f:
                return json.load(f)
    except OSError:
        pass
    players = get("/players/nfl")
    with open(PLAYERS_FILE, "w") as f:
        json.dump(players, f)
    return players

def pname(players, pid):
    """'Name POS TEAM' for a player id; team defenses use their abbreviation as id ('PHI'); '0' is an empty slot."""
    if pid in (None, "0"):
        return "(empty)"
    p = players.get(pid) or {}
    name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid
    return f"{name} {p.get('position') or '?'} {p.get('team') or 'FA'}"

def pts(settings, key):
    """Season points are split into an int and a hundredths field: fpts=1617, fpts_decimal=78 -> 1617.78."""
    if settings.get(key) is None:
        return None
    return round(settings[key] + settings.get(key + "_decimal", 0) / 100, 2)

def team_names(users, rosters):
    """roster_id -> team name: the owner's team_name, else their display_name, else 'Team <roster_id>'."""
    by_id = {u["user_id"]: u for u in users}
    out = {}
    for r in rosters:
        u = by_id.get(r.get("owner_id")) or {}
        out[r["roster_id"]] = (u.get("metadata") or {}).get("team_name") or u.get("display_name") or f"Team {r['roster_id']}"
    return out

# 1. League, teams and standings
on_api_tab()
state = get("/state/nfl")
league = get(f"/league/{LEAGUE_ID}")
if league is None:
    raise SystemExit(f"league {LEAGUE_ID}: HTTP 404, no such league")
users = get(f"/league/{LEAGUE_ID}/users") or []
rosters = get(f"/league/{LEAGUE_ID}/rosters") or []
players = player_map()
names = team_names(users, rosters)
by_user = {u["user_id"]: u for u in users}
s = league["settings"]
print(json.dumps({
    "league": league["name"], "season": league["season"], "status": league["status"], "teams": league["total_rosters"],
    "rec_points": (league.get("scoring_settings") or {}).get("rec"), "playoff_week_start": s.get("playoff_week_start"),
    "last_scored_leg": s.get("last_scored_leg"), "roster_positions": league["roster_positions"],
    "nfl_now": f"{state['season']} {state['season_type']} week {state['week']}", "players_in_map": len(players)}))

table = []
for r in rosters:
    st = r.get("settings") or {}
    table.append({"roster_id": r["roster_id"], "team": names[r["roster_id"]],
                  "manager": (by_user.get(r.get("owner_id")) or {}).get("display_name"),
                  "co_managers": [(by_user.get(c) or {}).get("display_name", c) for c in r.get("co_owners") or []],
                  "w": st.get("wins", 0), "l": st.get("losses", 0), "t": st.get("ties", 0),
                  "pf": pts(st, "fpts"), "pa": pts(st, "fpts_against"), "max_pf": pts(st, "ppts"),
                  "faab_used": st.get("waiver_budget_used"), "moves": st.get("total_moves")})
table.sort(key=lambda t: (-t["w"], -(t["pf"] or 0)))
print(f"{'#':>2} {'rid':>3} {'team':<26} {'manager':<15} {'W-L-T':<7} {'PF':>8} {'PA':>8}")
for i, t in enumerate(table, 1):
    print(f"{i:>2} {t['roster_id']:>3} {t['team'][:26]:<26} {(t['manager'] or '-')[:15]:<15} {t['w']}-{t['l']}-{t['t']:<3} {t['pf'] or 0:>8} {t['pa'] or 0:>8}")

# 2. Every roster: starters by slot, bench, IR (reserve) and taxi, with player names
slots = [p for p in league["roster_positions"] if p != "BN"]
out = []
for r in rosters:
    starters = r.get("starters") or []
    held = set(starters) | set(r.get("reserve") or []) | set(r.get("taxi") or [])
    out.append({"roster_id": r["roster_id"], "team": names[r["roster_id"]],
                "starters": [{"slot": sl, "player_id": pid, "player": pname(players, pid)} for sl, pid in zip(slots, starters)],
                "bench": [pname(players, p) for p in r.get("players") or [] if p not in held],
                "ir": [pname(players, p) for p in r.get("reserve") or []],
                "taxi": [pname(players, p) for p in r.get("taxi") or []]})
top = next(o for o in out if o["roster_id"] == table[0]["roster_id"])
print(f"\n{top['team']} (roster {top['roster_id']}):")
for x in top["starters"]:
    print(f"  {x['slot']:<5} {x['player']}")
print("  BN   ", "; ".join(top["bench"]))
print("  IR   ", "; ".join(top["ir"]) or "-", "| taxi", "; ".join(top["taxi"]) or "-")
print(f"{len(out)} rosters, {sum(len(o['bench']) + len(o['starters']) + len(o['ir']) + len(o['taxi']) for o in out)} roster spots read")
```

Output observed on 2026-11-04 (the first run downloads the 14.7 MB player map; runs within 24 h reuse the file):

```text
{"league": "Sleeper Friends League", "season": "2018", "status": "complete", "teams": 12, "rec_points": 1.0, "playoff_week_start": 14, "last_scored_leg": 16, "roster_positions": ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "DEF", "BN", "BN", "BN", "BN", "BN", "BN"], "nfl_now": "2026 regular week 9", "players_in_map": 12229}
 # rid team                       manager         W-L-T         PF       PA
 1   6 Bless em 🙏🇨🇱               evbettor        11-2-0    1899.78  1668.68
 2   3 🔥Gordon x Gordon 🔥         feiyingx        10-3-0    1731.72  1560.98
 3  10 canzhi                     canzhi          8-5-0    1805.46  1632.36
 4   5 tobrepeels                 tobrepeels      8-5-0    1635.28  1548.98
 5   1 Kamara is the new DJ       progamer        7-6-0    1776.06  1695.36
 6   2 Giant Dolphins             2KSports        6-7-0    1736.02  1678.44
 7  12 TOBOT                      TOBOT           6-7-0    1706.44   1698.9
 8   7 Pickle Rick Mahomes        deshine         6-7-0    1704.54  1694.44
 9   4 PA champ. 💩                akahotcheetos   5-8-0    1736.52  1811.18
10   9 🍿🏖🍻                        liangsharon24   5-8-0    1664.06   1774.4
11   8 Who needs RB’s             Discarded       4-9-0    1538.12   1814.2
12  11 Not saved by the Bell      TKO             2-11-0    1374.54  1730.62

Bless em 🙏🇨🇱 (roster 6):
  QB    Dak Prescott QB DAL
  RB    Christian McCaffrey RB SF
  RB    Damien Williams RB FA
  WR    DeAndre Hopkins WR FA
  WR    Michael Thomas WR FA
  TE    George Kittle TE SF
  FLEX  Calvin Ridley WR TEN
  FLEX  Alshon Jeffery WR FA
  DEF   Tennessee Titans DEF TEN
  BN    Spencer Ware RB FA; Jordy Nelson WR FA; Alfred Blue RB FA; Peyton Barber RB FA; Josh Reynolds WR FA; Dante Pettis WR FA
  IR    - | taxi -
12 rosters, 187 roster spots read
```

### 2. One week's matchups, a box score, and the playoff brackets (browser)

`WEEK = None` picks the current NFL week (`/state/nfl` `week`) for a league that is `in_season` this season, and `settings.last_scored_leg` for a finished one.

```python
import json, os, time

LEAGUE_ID = "289646328504385536"   # the number in a league URL, sleeper.com/leagues/<league_id>/...; this is the example league from Sleeper's API docs
WEEK = None                        # None = this NFL week for a live league, the last scored week for a finished one

API = "https://api.sleeper.app/v1"
PAUSE = 0.1        # serial calls; Sleeper's docs: stay under 1000 calls/min or risk an IP block
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab
PLAYERS_FILE = "sleeper-players-nfl.json"   # full NFL player map (~15 MB); the docs ask for at most one fetch a day

def on_api_tab():
    """All calls run as same-origin fetch() in a logged-out api.sleeper.app tab; reuse it if already there."""
    try:
        if js("location.origin") == "https://api.sleeper.app":
            return
    except Exception:
        pass
    new_tab(API + "/state/nfl")   # small JSON answer on the API host
    wait_for_load()

FETCH_JS = """(async () => {
  try {
    const r = await fetch(%s, {credentials: 'omit'});
    window.__sl = await r.text();
    return {status: r.status, len: window.__sl.length, retry_after: r.headers.get('retry-after')};
  } catch (e) { window.__sl = ''; return {status: 0, error: String(e)}; }
})()"""

def get(path, tries=4):
    """Serial GET of api.sleeper.app/v1<path>. Returns parsed JSON, or None on 404 or a JSON null (unknown user).
    Retries 429/5xx with backoff, then raises: a failed call never looks like an empty result."""
    url = API + path
    for attempt in range(tries):
        meta = js(FETCH_JS % json.dumps(url))
        status = meta["status"]
        if status in (200, 404):
            text = "".join(js(f"window.__sl.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
            js("window.__sl = ''")
            time.sleep(PAUSE)
            return json.loads(text) if status == 200 else None
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('error', '')}; stopping")
        ra = meta.get("retry_after") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def player_map():
    """player_id -> player dict. Reuses PLAYERS_FILE if under 24 h old, else downloads /players/nfl once and saves it."""
    try:
        if time.time() - os.path.getmtime(PLAYERS_FILE) < 86400:
            with open(PLAYERS_FILE) as f:
                return json.load(f)
    except OSError:
        pass
    players = get("/players/nfl")
    with open(PLAYERS_FILE, "w") as f:
        json.dump(players, f)
    return players

def pname(players, pid):
    """'Name POS TEAM' for a player id; team defenses use their abbreviation as id ('PHI'); '0' is an empty slot."""
    if pid in (None, "0"):
        return "(empty)"
    p = players.get(pid) or {}
    name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid
    return f"{name} {p.get('position') or '?'} {p.get('team') or 'FA'}"

def pts(settings, key):
    """Season points are split into an int and a hundredths field: fpts=1617, fpts_decimal=78 -> 1617.78."""
    if settings.get(key) is None:
        return None
    return round(settings[key] + settings.get(key + "_decimal", 0) / 100, 2)

def team_names(users, rosters):
    """roster_id -> team name: the owner's team_name, else their display_name, else 'Team <roster_id>'."""
    by_id = {u["user_id"]: u for u in users}
    out = {}
    for r in rosters:
        u = by_id.get(r.get("owner_id")) or {}
        out[r["roster_id"]] = (u.get("metadata") or {}).get("team_name") or u.get("display_name") or f"Team {r['roster_id']}"
    return out

on_api_tab()
state = get("/state/nfl")
league = get(f"/league/{LEAGUE_ID}")
if league is None:
    raise SystemExit(f"league {LEAGUE_ID}: HTTP 404, no such league")
s = league["settings"]
live = league["status"] == "in_season" and league["season"] == state["league_season"]
week = WEEK or (state["week"] if live else s.get("last_scored_leg") or s.get("leg"))
users = get(f"/league/{LEAGUE_ID}/users") or []
rosters = get(f"/league/{LEAGUE_ID}/rosters") or []
names = team_names(users, rosters)
players = player_map()
rows = get(f"/league/{LEAGUE_ID}/matchups/{week}") or []
print(f"{league['name']} {league['season']} week {week} ({'live' if live else league['status']}): {len(rows)} team rows")

# Teams with the same matchup_id play each other; matchup_id None = no game that week (e.g. out of the playoffs)
games, idle = {}, []
for r in rows:
    (games.setdefault(r["matchup_id"], []) if r["matchup_id"] is not None else idle).append(r)
def score(r):
    return r["custom_points"] if r.get("custom_points") is not None else r["points"]   # commissioner override wins
for mid in sorted(games):
    g = sorted(games[mid], key=score, reverse=True)
    if len(g) == 2:
        a, b = g
        res = "tie" if score(a) == score(b) else f"{names[a['roster_id']]} wins"
        print(f"  m{mid:<2} {names[a['roster_id']][:24]:>24} {score(a):>7.2f} - {score(b):<7.2f} {names[b['roster_id']][:24]:<24} | {res}")
    else:   # a matchup_id held by one team: no head-to-head opponent that week
        print(f"  m{mid:<2} " + ", ".join(f"{names[r['roster_id']]} {score(r):.2f}" for r in g) + "  (no opponent)")
if idle:
    print("  no matchup:", ", ".join(f"{names[r['roster_id']]} {score(r):.2f}" for r in idle))

# Box score of the first game: starters by slot with points, then bench points
slots = [p for p in league["roster_positions"] if p != "BN"]
if games:
    for r in sorted(games[min(games)], key=lambda r: r["roster_id"]):
        print(f"\n{names[r['roster_id']]} (roster {r['roster_id']}) {score(r):.2f}")
        pp = r.get("players_points") or {}
        for sl, pid, p in zip(slots, r["starters"], r.get("starters_points") or []):
            print(f"  {sl:<5} {pname(players, pid):<34} {p:>6.2f}")
        bench = [pid for pid in r["players"] or [] if pid not in r["starters"]]
        print("  BN   ", "; ".join(f"{pname(players, pid)} {pp.get(pid, 0):.2f}" for pid in bench))

# Playoff brackets; t1/t2/w/l are roster_ids, TBD = not decided yet. Live leagues can show current seeds mid-season.
for side in ("winners_bracket", "losers_bracket"):
    br = get(f"/league/{LEAGUE_ID}/{side}") or []
    if br:
        print(f"\n{side}: {len(br)} games")
        for m in br:
            t = lambda rid: names.get(rid, "TBD") if isinstance(rid, int) else "TBD"
            print(f"  r{m['r']} m{m['m']:<2} {t(m.get('t1'))[:22]:>22} vs {t(m.get('t2'))[:22]:<22} winner {t(m.get('w'))}" + (f"  (place {m['p']})" if m.get("p") else ""))
    else:
        print(f"\n{side}: none yet")
```

Output observed on 2026-11-04:

```text
Sleeper Friends League 2018 week 16 (complete): 12 team rows
  m1              Bless em 🙏🇨🇱  177.34 - 135.04  🔥Gordon x Gordon 🔥       | Bless em 🙏🇨🇱 wins
  m2      Kamara is the new DJ  140.94 - 139.86  Giant Dolphins           | Kamara is the new DJ wins
  m4            Who needs RB’s  166.52 - 136.18  Not saved by the Bell    | Who needs RB’s wins
  m5       Pickle Rick Mahomes  121.32 - 87.34   🍿🏖🍻                      | Pickle Rick Mahomes wins
  no matchup: PA champ. 💩  120.64, tobrepeels 128.06, canzhi 132.26, TOBOT 88.88

🔥Gordon x Gordon 🔥 (roster 3) 135.04
  QB    Russell Wilson QB FA                34.54
  RB    Melvin Gordon RB FA                 14.40
  RB    Joe Mixon RB FA                      9.80
  WR    DaeSean Hamilton WR FA              16.00
  WR    Robbie Chosen WR FA                 29.00
  TE    Jared Cook TE FA                     4.00
  FLEX  Dede Westbrook WR FA                12.40
  FLEX  Kalen Ballage RB FA                  6.90
  DEF   Chicago Bears DEF CHI                8.00
  BN    C.J. Anderson RB FA 23.20; Chris Thompson RB FA 3.80; Adrian Peterson RB FA 13.70; Chris Godwin Jr. WR TB 6.90; Zay Jones WR ARI 17.70; Tim Patrick WR NYJ 6.70; Emmanuel Sanders WR FA 0.00

Bless em 🙏🇨🇱 (roster 6) 177.34
  QB    Dak Prescott QB DAL                 18.64
  RB    Christian McCaffrey RB SF           29.80
  RB    Damien Williams RB FA               25.00
  WR    DeAndre Hopkins WR FA               19.40
  WR    Michael Thomas WR FA                27.90
  TE    George Kittle TE SF                 14.40
  FLEX  Calvin Ridley WR TEN                18.00
  FLEX  Alshon Jeffery WR FA                11.20
  DEF   Tennessee Titans DEF TEN            13.00
  BN    Spencer Ware RB FA 0.00; Jordy Nelson WR FA 14.50; Alfred Blue RB FA 8.00; Peyton Barber RB FA 8.60; Josh Reynolds WR FA 6.40; Dante Pettis WR FA 5.10

winners_bracket: 7 games
  r1 m1              tobrepeels vs Kamara is the new DJ   winner Kamara is the new DJ
  r1 m2          Giant Dolphins vs canzhi                 winner Giant Dolphins
  r2 m3            Bless em 🙏🇨🇱 vs Kamara is the new DJ   winner Bless em 🙏🇨🇱
  r2 m4      🔥Gordon x Gordon 🔥 vs Giant Dolphins         winner 🔥Gordon x Gordon 🔥
  r2 m5              tobrepeels vs canzhi                 winner canzhi  (place 5)
  r3 m6            Bless em 🙏🇨🇱 vs 🔥Gordon x Gordon 🔥     winner Bless em 🙏🇨🇱  (place 1)
  r3 m7    Kamara is the new DJ vs Giant Dolphins         winner Kamara is the new DJ  (place 3)

losers_bracket: 7 games
  r1 m1            PA champ. 💩  vs Pickle Rick Mahomes    winner Pickle Rick Mahomes
  r1 m2                   TOBOT vs 🍿🏖🍻                    winner 🍿🏖🍻
  r2 m3   Not saved by the Bell vs Pickle Rick Mahomes    winner Not saved by the Bell
  r2 m4          Who needs RB’s vs 🍿🏖🍻                    winner Who needs RB’s
  r2 m5            PA champ. 💩  vs TOBOT                  winner TOBOT  (place 5)
  r3 m6   Not saved by the Bell vs Who needs RB’s         winner Not saved by the Bell  (place 1)
  r3 m7     Pickle Rick Mahomes vs 🍿🏖🍻                    winner 🍿🏖🍻  (place 3)
```

### 3. Trending adds or drops, who has them in your league, and sleeper.com Rostered % (browser)

Opens a second tab for sleeper.com and loads the top `PAGES` player pages one at a time, 2 s apart. If a page ever shows a challenge, it stops.

```python
import json, os, re, time

TREND = "add"             # "add" or "drop"
LOOKBACK_HOURS = 24       # the API's default is 24; a non-number is ignored silently (24 again)
LIMIT = 25                # the API returned at most 100 rows even with limit=200
LEAGUE_ID = "289646328504385536"   # mark who in this league already rosters each player; None to skip
PAGES = 5                 # read Rostered %, Started % and rankings from sleeper.com player pages for the top N

API = "https://api.sleeper.app/v1"
PAUSE = 0.1        # serial calls; Sleeper's docs: stay under 1000 calls/min or risk an IP block
MAX_WAIT = 120     # longest backoff this code sleeps; a longer one stops the run
CHUNK = 500_000    # characters per js() read when pulling a big body out of the tab
PLAYERS_FILE = "sleeper-players-nfl.json"   # full NFL player map (~15 MB); the docs ask for at most one fetch a day

def on_api_tab():
    """All calls run as same-origin fetch() in a logged-out api.sleeper.app tab; reuse it if already there."""
    try:
        if js("location.origin") == "https://api.sleeper.app":
            return
    except Exception:
        pass
    new_tab(API + "/state/nfl")   # small JSON answer on the API host
    wait_for_load()

FETCH_JS = """(async () => {
  try {
    const r = await fetch(%s, {credentials: 'omit'});
    window.__sl = await r.text();
    return {status: r.status, len: window.__sl.length, retry_after: r.headers.get('retry-after')};
  } catch (e) { window.__sl = ''; return {status: 0, error: String(e)}; }
})()"""

def get(path, tries=4):
    """Serial GET of api.sleeper.app/v1<path>. Returns parsed JSON, or None on 404 or a JSON null (unknown user).
    Retries 429/5xx with backoff, then raises: a failed call never looks like an empty result."""
    url = API + path
    for attempt in range(tries):
        meta = js(FETCH_JS % json.dumps(url))
        status = meta["status"]
        if status in (200, 404):
            text = "".join(js(f"window.__sl.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
            js("window.__sl = ''")
            time.sleep(PAUSE)
            return json.loads(text) if status == 200 else None
        retryable = status in (429, 500, 502, 503, 504) or (status == 0 and attempt == 0)
        if not retryable or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {status} {meta.get('error', '')}; stopping")
        ra = meta.get("retry_after") or ""
        wait = int(ra) if ra.isdigit() else 15 * 2 ** attempt
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: asked to wait {wait} s (> {MAX_WAIT} s); stopping")
        time.sleep(wait)

def player_map():
    """player_id -> player dict. Reuses PLAYERS_FILE if under 24 h old, else downloads /players/nfl once and saves it."""
    try:
        if time.time() - os.path.getmtime(PLAYERS_FILE) < 86400:
            with open(PLAYERS_FILE) as f:
                return json.load(f)
    except OSError:
        pass
    players = get("/players/nfl")
    with open(PLAYERS_FILE, "w") as f:
        json.dump(players, f)
    return players

def pname(players, pid):
    """'Name POS TEAM' for a player id; team defenses use their abbreviation as id ('PHI'); '0' is an empty slot."""
    if pid in (None, "0"):
        return "(empty)"
    p = players.get(pid) or {}
    name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid
    return f"{name} {p.get('position') or '?'} {p.get('team') or 'FA'}"

def pts(settings, key):
    """Season points are split into an int and a hundredths field: fpts=1617, fpts_decimal=78 -> 1617.78."""
    if settings.get(key) is None:
        return None
    return round(settings[key] + settings.get(key + "_decimal", 0) / 100, 2)

def team_names(users, rosters):
    """roster_id -> team name: the owner's team_name, else their display_name, else 'Team <roster_id>'."""
    by_id = {u["user_id"]: u for u in users}
    out = {}
    for r in rosters:
        u = by_id.get(r.get("owner_id")) or {}
        out[r["roster_id"]] = (u.get("metadata") or {}).get("team_name") or u.get("display_name") or f"Team {r['roster_id']}"
    return out

def player_page(pid):
    """Read one sleeper.com player page (robots: Allow /). Returns rankings and Rostered/Started % as shown there."""
    url = f"https://sleeper.com/nfl/players/{pid}"   # the id alone is enough; the site's own links add a name slug
    goto_url(url)
    wait_for_load()
    text = ""
    for _ in range(30):   # the page renders client-side; wait for the rankings box
        text = js("document.body.innerText") or ""
        title = js("document.title") or ""
        if "Just a moment" in title or "Access denied" in text or "captcha" in text.lower():
            raise RuntimeError(f"{url}: challenge page; stopping, do not retry around it")
        if "ROSTERED" in text:
            break
        time.sleep(0.5)
    m = re.search(r"PLAYER RANKINGS\s+#(\d+)\s+(\S+)\s+#(\d+)\s+OVERALL\s+(\d+)%\s+ROSTERED\s+(\d+)%\s+STARTED", text)
    if not m:
        return {"url": url, "error": "rankings box not found"}
    return {"url": url, "pos_rank": f"{m[2]}{m[1]}", "overall_rank": int(m[3]),
            "rostered_pct": int(m[4]), "started_pct": int(m[5])}

on_api_tab()
state = get("/state/nfl")
trend = get(f"/players/nfl/trending/{TREND}?lookback_hours={LOOKBACK_HOURS}&limit={LIMIT}") or []
players = player_map()
owner = {}
if LEAGUE_ID:
    league = get(f"/league/{LEAGUE_ID}")
    rosters = get(f"/league/{LEAGUE_ID}/rosters") or []
    names = team_names(get(f"/league/{LEAGUE_ID}/users") or [], rosters)
    owner = {pid: names[r["roster_id"]] for r in rosters for pid in r.get("players") or []}
    print(f"league: {league['name']} {league['season']} ({league['status']}), {len(owner)} rostered players")
print(f"NFL {state['season']} week {state['week']}: top {len(trend)} {TREND}s, last {LOOKBACK_HOURS} h, all Sleeper leagues")

rows = []
for i, t in enumerate(trend, 1):
    p = players.get(t["player_id"]) or {}
    rows.append({"rank": i, "player_id": t["player_id"], "player": pname(players, t["player_id"]), "count": t["count"],
                 "injury": p.get("injury_status"), "league_team": owner.get(t["player_id"]),
                 "sleeper_url": f"https://sleeper.com/nfl/players/{t['player_id']}"})
for r in rows:
    print(f"{r['rank']:>3} {r['player']:<34} {r['count']:>9,} {r['injury'] or '':<12} {('on ' + r['league_team']) if r['league_team'] else 'free agent' if LEAGUE_ID else ''}")

# sleeper.com player pages for the top PAGES rows: one tab, one page at a time, 2 s apart
if PAGES:
    new_tab("about:blank")
    for r in rows[:PAGES]:
        r.update(player_page(r["player_id"]))
        print(f"  {r['player']:<34} {r.get('pos_rank', '?'):>5} overall #{r.get('overall_rank', '?'):<4} rostered {r.get('rostered_pct', '?')}%  started {r.get('started_pct', '?')}%  {r['url']}")
        time.sleep(2)
```

Output observed on 2026-11-04:

```text
league: Sleeper Friends League 2018 (complete), 187 rostered players
NFL 2026 week 9: top 25 adds, last 24 h, all Sleeper leagues
  1 Adonai Mitchell WR NYJ             1,533,648              free agent
  2 Devin Singletary RB NYG            1,044,288              free agent
  3 Tyler Allgeier RB ARI                730,615              free agent
  4 Emmett Johnson RB KC                 671,382              free agent
  5 Detroit Lions DEF DET                645,507              on canzhi
  6 Chris Rodriguez Jr. RB JAX           634,707              free agent
  7 Gardner Minshew II QB ARI            555,780              free agent
  8 Houston Texans DEF HOU               525,450              on tobrepeels
  9 Malik Willis QB MIA                  479,297              free agent
 10 New Orleans Saints DEF NO            457,120              on PA champ. 💩 
 11 Tyler Bass K BUF                     396,180              free agent
 12 Cairo Santos K CHI                   388,150              free agent
 13 Joe Milton QB PHI                    352,316              free agent
 14 Mike Gesicki TE CIN                  346,904              free agent
 15 Jadarian Price RB SEA                306,270              free agent
 16 Ryan Flournoy WR DAL                 293,824              free agent
 17 New York Giants DEF NYG              270,688              free agent
 18 Elijah Mitchell RB PHI               265,653              free agent
 19 Dylan Sampson RB CLE                 257,470              free agent
 20 Malik Washington WR MIA              254,648              free agent
 21 Treylon Burks WR WAS                 226,401              free agent
 22 Sione Vaki RB DET                    206,710              free agent
 23 Alvin Kamara RB NO                   179,512 Questionable on Kamara is the new DJ
 24 Shedeur Sanders QB CLE               163,616              free agent
 25 Kirk Cousins QB LV                   153,336              on Who needs RB’s
  Adonai Mitchell WR NYJ              WR66 overall #203  rostered 46%  started 6%  https://sleeper.com/nfl/players/11625
  Devin Singletary RB NYG             RB55 overall #275  rostered 37%  started 9%  https://sleeper.com/nfl/players/6130
  Tyler Allgeier RB ARI               RB21 overall #80   rostered 83%  started 44%  https://sleeper.com/nfl/players/8132
  Emmett Johnson RB KC                RB38 overall #196  rostered 40%  started 5%  https://sleeper.com/nfl/players/13337
  Detroit Lions DEF DET              DEF24 overall #244  rostered 31%  started 24%  https://sleeper.com/nfl/players/DET
```

## Fields

Block 1 standings row: `roster_id` (1..teams, stable for the season), `team` (`users[].metadata.team_name`, else `display_name`), `manager` (owner's `display_name`), `co_managers` (from `rosters[].co_owners`), `w`/`l`/`t` (`settings.wins/losses/ties`), `pf`/`pa`/`max_pf` (`fpts`/`fpts_against`/`ppts` plus their `_decimal` hundredths), `faab_used` (`waiver_budget_used`), `moves` (`total_moves`).

Block 1 roster: `starters` zipped with the non-`BN` entries of `league.roster_positions` (same order), `bench` = `players` minus starters, `reserve` (IR) and `taxi`.

| Raw field | Where | Notes |
|---|---|---|
| `starters` | rosters, matchups | ordered like `roster_positions` without `BN`; `"0"` = empty slot |
| `players` | rosters, matchups | every player id on the team, starters included |
| `reserve`, `taxi` | rosters | IR and taxi squad ids; `null` when the league has none |
| `matchup_id` | matchups | same id = opponents; `null` = no game that week |
| `points`, `custom_points` | matchups | team total; `custom_points` is a commissioner override (block 2 prefers it) |
| `starters_points`, `players_points` | matchups | per starter (same order as `starters`) and per player id |
| `r`, `m`, `t1`, `t2`, `w`, `l`, `p` | brackets | round, game, the two `roster_id`s, winner, loser, and the place a final decides |
| `count` | trending | adds or drops across all Sleeper leagues in the lookback window |
| `full_name`, `position`, `team`, `injury_status` | player map | team defenses have no `full_name`: use `first_name` + `last_name` |
| `rec` | `league.scoring_settings` | points per reception: 1.0, 0.5 or 0 |

The player map also carries `espn_id`, `yahoo_id`, `sportradar_id`, `gsis_id`, `rotowire_id` and similar ids for joining with other sources, plus `age`, `years_exp`, `depth_chart_position`, `depth_chart_order`, `status` and `active`.

## Gotchas

- **Teams in the player map are today's.** The map has no history, so a 2018 roster shows `Dak Prescott QB DAL` but `Damien Williams RB FA`. Use it for names and positions, not for where a player played that season.
- **Users and rosters are separate lists.** The 2018 league has 14 users for 12 rosters; join on `rosters[].owner_id`. `username` was `null` in every row of that league's `/users` today, so the blocks use `display_name`.
- **Unscored weeks are all zeros.** On Wednesday 2026-11-04, every row of week 9 (the current week) had `points` 0.00 in all 8 live 2026 leagues checked; week 8 was scored in all 8. Block 2 prints such games as `0.00 - 0.00 | tie`. Empty starter slots are `"0"`: one best-ball roster (`settings.best_ball` 1) had all 8 `starters` set to `"0"` before the week's games.
- **Not every league is head-to-head.** Two live leagues with `settings.type` 3 (16 and 18 teams; one `best_ball` 1, one `best_ball` 0) gave every team its own `matchup_id`; block 2 prints those as "no opponent". Count `matchup_id`s rather than trusting `best_ball`. In playoff weeks, teams out of the bracket get `matchup_id: null` (4 of 12 teams in week 16 of the 2018 league).
- **Median games double the record.** A live league with `settings.league_average_match` 1 showed 16 results per team after 8 scored weeks: Sleeper counts the weekly game against the league median as a second W or L.
- **Brackets exist before the playoffs.** In week 9, 5 of 8 live leagues already returned both brackets (7 games each) with current seeds and every `w` still `null`. The other 3 (the two `type` 3 leagues with `playoff_teams` null, and one median league) returned HTTP 200 `null`; block 2 prints that as "none yet".
- **Errors are uneven.** Unknown league: `/league/<id>`, `/rosters` and `/matchups/<w>` are HTTP 404 with body `null`, but `/users` is HTTP 200 `[]`. Out-of-range weeks (`/matchups/0`, `/matchups/19`) are HTTP 200 `[]`; `/matchups/abc` is 404. Unknown username: HTTP 200 `null`. `/trending/foo`: HTTP 200 `[]`.
- **Trending limits.** `limit=200` returned 100 rows. `lookback_hours=abc` was ignored (24 h result). Counts move as the window rolls and responses carry `Cache-Control: s-maxage=600`, so two calls minutes apart differ (top add 1,607,944 then 1,531,168). Sleeper's docs ask for attribution when you show its trending data.
- **Caching seen today:** `s-maxage=86400` on the finished 2018 league and its matchups, 600 on trending and player-map responses, 120 on `/user/<username>`, 60 on `/state/nba`.
- **sleeper.com player pages** render client-side; block 3 polls up to 15 s for the rankings box. The id alone works (`/nfl/players/6804`), as do the site's slugged links (`/nfl/players/jordan-love-6804`). Team defenses use the team code (`/nfl/players/DET`).
- **Plain HTTP:** `curl https://api.sleeper.app/v1/state/nfl` answered 200 today, so the same endpoints work without a browser.
- **Terms:** the docs say the API is free for non-commercial use; for commercial use they ask you to contact api@sleeper.app to discuss licensing.

## What does not work

- **League pages on sleeper.com** need a login (redirect to `/?redirect=...&login=`); this skill does not log in.
- **More than 100 trending rows:** not available from the endpoint.
- **Projections** are not in the documented API; this skill does not read them.
- **Untested:** the documented `/league/<id>/transactions/<week>`, `/league/<id>/traded_picks` and draft endpoints, and leagues of other sports (`/state/nba` answered, NBA leagues were not tried).
