# Sofascore - Player Stats, Match Events and Lineups

Field-tested against www.sofascore.com on 2026-11-02 using a Browser Use cloud browser, logged out. About 45 page loads; no CAPTCHA, challenge page, login wall or non-200 API answer.

robots.txt (read in the browser 2026-11-02, `User-agent: *`) disallows `/*/2017-` through `/*/2025-`, `/standings/`, `/*/standings/`, `/images/share/` and the localized standings paths (`/de/tabelle/`, `/fr/classement/`...); it has no rule for `/`, `/football/player/...`, `/football/match/...` or `/api/v1/player|event|search...`. `api.sofascore.com/robots.txt` served the same file inside the browser. The block reads robots.txt in the browser and refuses any page or API path it disallows.

## Quick summary

- **Browser only.** Plain HTTP to `www.sofascore.com/robots.txt`, `/api/v1/...` and `api.sofascore.com` all returned `403 {"error": {"code": 403, "reason": "Forbidden"}}` (curl, 2026-11-02). Do not try to get around it.
- **Data = the page's own JSON.** The web app loads everything from same-origin `www.sofascore.com/api/v1/...`. The block opens the public page and reads those responses with CDP `Network.getResponseBody`; it never requests an API URL itself.
- **Player page** (`/football/player/<slug>/<id>#tab:season`): profile, last ~30 matches with Sofascore rating, minutes, goals, assists, and season stats (137 fields for Haaland: goals, xG, shots, passes, duels, rating...). Other competitions/seasons: the block picks them in the page's own dropdowns and reads the response that loads.
- **Match page** (`/football/match/<slug>/<customId>#id:<eventId>`): score, venue, referee, incidents (goals with assist, cards, subs), both lineups with formation, shirt, position, rating, minutes, missing players, and team stats (possession, xG, shots, corners...).
- **Find ids** with the site's own search box (block types the name, reads `search/all?q=...`).
- **Ad hijack:** without ad blocking, a malicious ad redirected the tab to a scam page on `*.web.core.windows.net` 6-7 s after load in 5 of 5 loads while authoring; a later run the same day saw 0 redirects in 3 unblocked loads, so it depends on which ad serves. The block blocks three ad hosts and stops if the tab ever leaves `www.sofascore.com`.

## What works: search, player stats, match events and lineups in one run

Self-contained; opens one background tab and closes it; 5 page loads (robots.txt, home, player twice, match), about 35 s in a cloud browser.

```python
import base64, json, re, time
from datetime import datetime, timezone
from urllib.parse import urlparse

BASE = "https://www.sofascore.com"
API = BASE + "/api/v1/"
PACE_S = 3  # pause between page loads
# Third-party ad scripts. Without this block, an ad sometimes redirects the whole tab to a scam page
# on *.web.core.windows.net 6-7 s after load (2026-11-02: 5 of 5 unblocked loads, later 0 of 3).
AD_BLOCK = ["*cdn.adverge.ai*", "*securepubads.g.doubleclick.net*", "*googlesyndication.com*"]

def _ev_body(rid):
    b = cdp("Network.getResponseBody", requestId=rid)
    return json.loads(base64.b64decode(b["body"]) if b.get("base64Encoded") else b["body"])

def _robots_rules():
    # robots.txt answers 403 to plain HTTP clients, so read it in the browser tab.
    cdp("Page.navigate", url=BASE + "/robots.txt")
    for _ in range(40):
        time.sleep(0.25)
        try:
            txt = js("location.href.endsWith('/robots.txt') && document.readyState === 'complete' ? document.body.innerText : ''")
        except Exception:
            txt = ""
        if txt and "User-agent" in txt:
            break
    else:
        raise RuntimeError("could not read robots.txt in the browser")
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
    """Google-style match: longest matching rule wins, Allow wins a tie."""
    best, ok = -1, True
    for allow, pat in RULES:
        rx = re.escape(pat.rstrip("$")).replace(r"\*", ".*") + ("$" if pat.endswith("$") else "")
        if re.match(rx, path) and (len(pat) > best or (len(pat) == best and allow)):
            best, ok = len(pat), allow
    return ok

def _collect(want, timeout=25, optional=()):
    """Read the API responses the page itself loads. want = {name: regex for the path after /api/v1/}.
    Returns {name: json or None (404)}; PATHS[name] keeps the matched API path."""
    reqs, got, t0 = {}, {}, time.time()
    while time.time() - t0 < timeout and len(got) < len(want):
        for e in drain_events():
            if e.get("session_id") != SESSION:
                continue
            m, p = e.get("method"), e.get("params") or {}
            if m == "Page.frameNavigated" and not p["frame"].get("parentId"):
                u = p["frame"]["url"]
                if u != "about:blank" and urlparse(u).hostname != "www.sofascore.com":
                    raise RuntimeError(f"tab was redirected off-site to {u[:80]}; stop")
            elif m == "Network.requestWillBeSent" and p["request"]["url"].startswith(API):
                api = p["request"]["url"][len(API):]
                name = next((n for n, rx in want.items() if n not in got and re.fullmatch(rx, api)), None)
                if name:
                    reqs[p["requestId"]] = {"name": name, "api": api}
            elif p.get("requestId") in reqs:
                r = reqs[p["requestId"]]
                if m == "Network.responseReceived":
                    r["status"] = p["response"]["status"]
                elif m == "Network.loadingFinished" and r["name"] not in got:
                    if not robots_allowed("/api/v1/" + r["api"]):
                        raise PermissionError(f"robots.txt disallows /api/v1/{r['api']}")
                    if r.get("status") == 404:
                        got[r["name"]] = None          # e.g. no lineups for this match
                    elif r.get("status") != 200:
                        raise RuntimeError(f"/api/v1/{r['api']} answered HTTP {r.get('status')}: stop, do not retry around it")
                    else:
                        got[r["name"]] = _ev_body(p["requestId"])
                    PATHS[r["name"]] = r["api"]
                # Network.loadingFailed: the page aborts and re-sends its first requests; wait for the re-send.
        time.sleep(0.2)
    missing = [n for n in want if n not in got and n not in optional]
    if missing:
        t = (js("document.title") or "").lower()
        if "just a moment" in t or "attention required" in t:
            raise RuntimeError("challenge page: stop and back off, do not retry around it")
        raise RuntimeError(f"page did not load {missing} within {timeout} s ({js('location.href')})")
    return got

def sofa_load(path, want, timeout=25, optional=()):
    if not robots_allowed(path.split("#")[0]):
        raise PermissionError(f"robots.txt disallows {path}")
    cdp("Page.navigate", url="about:blank")    # a hash-only change would not reload the page
    time.sleep(PACE_S)
    drain_events()
    cdp("Page.navigate", url=BASE + path)
    return _collect(want, timeout, optional)

def _ax_center(role, name, timeout=10):
    t0 = time.time()
    while time.time() - t0 < timeout:
        for n in cdp("Accessibility.getFullAXTree")["nodes"]:
            if (n.get("role") or {}).get("value") == role and (n.get("name") or {}).get("value") == name:
                cdp("DOM.scrollIntoViewIfNeeded", backendNodeId=n["backendDOMNodeId"])
                q = cdp("DOM.getBoxModel", backendNodeId=n["backendDOMNodeId"])["model"]["content"]
                return sum(q[0::2]) / 4, sum(q[1::2]) / 4
        time.sleep(0.5)
    raise RuntimeError(f"no {role} {name!r} on the page")

def pick_option(combobox, text):
    """Open a Sofascore dropdown (AX name 'tournaments' or 'seasons') and click the option with this text."""
    dismiss_survey()
    click_at_xy(*_ax_center("combobox", combobox))
    time.sleep(0.8)
    xy = js("""(t => { const c = document.querySelector('[role=combobox][aria-expanded=true]');
      const ul = c && document.getElementById(c.getAttribute('aria-controls'));
      const li = ul && [...ul.querySelectorAll('[role=option]')].find(o => o.textContent.trim() === t);
      if (!li) return null; li.scrollIntoView({block: 'center'});
      const b = li.getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; })(%s)""" % json.dumps(text))
    if not xy:
        raise ValueError(f"no option {text!r} in the {combobox} dropdown")
    drain_events()
    click_at_xy(*xy)

def _day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d") if ts else None

def dismiss_survey():
    """A 'Help us improve' survey modal can cover the page and swallow clicks."""
    xy = js("""(() => { const b = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Ask me later');
      if (!b) return null; const r = b.getBoundingClientRect(); return r.width ? [r.x + r.width / 2, r.y + r.height / 2] : null; })()""")
    if xy:
        click_at_xy(*xy)
        time.sleep(0.5)

def find_player(name):
    """Type into the site's own search box; return player hits from the search response the page loads."""
    sofa_load("/", {"sport": r"sport/-?\d+/event-count"})
    time.sleep(2)
    dismiss_survey()
    click_at_xy(*_ax_center("button", "Search Sofascore"))
    time.sleep(0.8)
    drain_events()
    type_text(name)
    q = re.escape(name).replace(r"\ ", r"(?:%20|\+| )")
    res = _collect({"search": r"search/all\?q=" + q + r"&page=0"}, 15)["search"]
    return [{"id": r["entity"]["id"], "slug": r["entity"]["slug"], "name": r["entity"]["name"],
             "team": (r["entity"].get("team") or {}).get("name")}
            for r in res["results"] if r.get("type") == "player"]

def player(pid, slug, competition=None, season=None):
    """Profile, recent matches (rating, minutes, goals) and season stats from the player page.
    competition / season: names as the page's dropdowns show them ('Premier League', '25/26').
    Default: the page's first competition and its latest season."""
    stats_rx = rf"player/{pid}/unique-tournament/\d+/season/\d+/statistics/overall"
    want = {"profile": rf"player/{pid}", "matches": rf"player/{pid}/events/last/0",
            "seasons": rf"player/{pid}/statistics/seasons", "season_stats": stats_rx}
    d = sofa_load(f"/football/player/{slug}/{pid}#tab:season", want)
    all_uts = d["seasons"]["uniqueTournamentSeasons"]
    comps = [u["uniqueTournament"]["name"] for u in all_uts]
    uts = next((u for u in all_uts if u["uniqueTournament"]["name"] == (competition or comps[0])), None)
    if not uts:
        raise ValueError(f"{competition!r} not in {comps}")
    if uts is not all_uts[0]:
        pick_option("tournaments", competition)
        d.update(_collect({"season_stats": stats_rx}, 15))
    if season and season != uts["seasons"][0]["year"]:
        if season not in [s["year"] for s in uts["seasons"]]:
            raise ValueError(f"{season!r} not in {[s['year'] for s in uts['seasons']]}")
        pick_option("seasons", season)
        d.update(_collect({"season_stats": stats_rx}, 15))
    ut, season_id = map(int, re.findall(r"/(\d+)", PATHS["season_stats"])[1:3])
    want_season = next(s["id"] for s in uts["seasons"] if s["year"] == (season or uts["seasons"][0]["year"]))
    if (ut, season_id) != (uts["uniqueTournament"]["id"], want_season):
        raise RuntimeError(f"page loaded stats for {(ut, season_id)}, wanted {(uts['uniqueTournament']['id'], want_season)}")
    p = d["profile"]["player"]
    m = d["matches"]
    games = []
    for e in m["events"]:
        k = str(e["id"])
        st = m["statisticsMap"].get(k) or {}
        inc = m["incidentsMap"].get(k) or {}
        games.append({"id": e["id"], "slug": e["slug"], "custom_id": e["customId"], "date": _day(e["startTimestamp"]),
                      "competition": e["tournament"]["uniqueTournament"]["name"], "status": e["status"]["type"],
                      "home": e["homeTeam"]["name"], "away": e["awayTeam"]["name"],
                      "score": f'{e["homeScore"].get("current")}-{e["awayScore"].get("current")}' if e["status"]["type"] == "finished" else None,
                      "rating": st.get("rating"), "minutes": st.get("minutesPlayed"), "bench": k in m["onBenchMap"],
                      "goals": inc.get("goals", 0), "assists": inc.get("assists", 0)})
    s = d["season_stats"]["statistics"]
    return {
        "profile": {"name": p["name"], "team": p["team"]["name"], "position": p.get("position"),
                    "born": _day(p.get("dateOfBirthTimestamp")), "country": p["country"]["name"],
                    "height_cm": p.get("height"), "foot": p.get("preferredFoot"), "shirt": p.get("shirtNumber"),
                    "market_value": p.get("proposedMarketValueRaw")},
        "competitions": comps,
        "season": {"competition": uts["uniqueTournament"]["name"],
                   "season": next(x["year"] for x in uts["seasons"] if x["id"] == season_id),
                   "ids": (ut, season_id), "stats": s},
        "matches": sorted(games, key=lambda g: g["date"], reverse=True),
    }

def match(event_id, slug, custom_id):
    """Score, events (goals, cards, subs), lineups and team stats from the match page."""
    eid = event_id
    want = {"event": rf"event/{eid}", "incidents": rf"event/{eid}/incidents",
            "lineups": rf"event/{eid}/lineups", "statistics": rf"event/{eid}/statistics"}
    d = sofa_load(f"/football/match/{slug}/{custom_id}#id:{eid}", want, optional=("incidents", "lineups", "statistics"))
    ev = d["event"]["event"]
    def who(x):
        return (x or {}).get("name")
    events = []
    for i in reversed((d.get("incidents") or {}).get("incidents", [])):
        t = i["incidentType"]
        if t in ("goal", "card", "substitution", "varDecision", "period"):
            events.append({"min": i.get("time"), "added": i.get("addedTime") if i.get("addedTime") != 999 else None,
                           "type": t, "class": i.get("incidentClass"), "text": i.get("text"),
                           "side": None if i.get("isHome") is None else ("home" if i["isHome"] else "away"),
                           "player": who(i.get("player")), "assist": who(i.get("assist1")),
                           "in": who(i.get("playerIn")), "out": who(i.get("playerOut")),
                           "score": f'{i["homeScore"]}-{i["awayScore"]}' if "homeScore" in i else None})
    lineups = None
    if d.get("lineups"):
        lineups = {"confirmed": d["lineups"].get("confirmed")}
        for side in ("home", "away"):
            t = d["lineups"][side]
            lineups[side] = {"formation": t.get("formation"), "players": [
                {"name": x["player"]["name"], "shirt": x.get("shirtNumber") or x.get("jerseyNumber"),
                 "pos": x.get("position"), "sub": x.get("substitute", False),
                 "rating": (x.get("statistics") or {}).get("rating"),
                 "minutes": (x.get("statistics") or {}).get("minutesPlayed")} for x in t["players"]],
                "missing": [who(x.get("player")) for x in t.get("missingPlayers", [])]}
    stats = {}
    for per in (d.get("statistics") or {}).get("statistics", []):
        if per["period"] == "ALL":
            for g in per["groups"]:
                for it in g["statisticsItems"]:
                    stats[it["name"]] = (it.get("home"), it.get("away"))
    hs, as_ = ev["homeScore"].get("current"), ev["awayScore"].get("current")
    return {"match": f'{ev["homeTeam"]["name"]} {"vs" if hs is None else f"{hs}-{as_}"} {ev["awayTeam"]["name"]}',
            "status": ev["status"]["description"], "date": _day(ev["startTimestamp"]),
            "competition": ev["tournament"]["uniqueTournament"]["name"],
            "venue": (ev.get("venue") or {}).get("name"), "referee": who(ev.get("referee")),
            "events": events, "lineups": lineups, "stats": stats}

PATHS = {}
tab = cdp("Target.createTarget", url="about:blank", background=True)["targetId"]
SESSION = switch_tab(tab)
try:
    cdp("Network.enable")
    cdp("Network.setBlockedURLs", urls=AD_BLOCK)
    RULES = _robots_rules()
    print("robots: /football/player/x/1 ->", robots_allowed("/football/player/x/1"),
          "| /api/v1/tournament/1/season/2/standings/total ->", robots_allowed("/api/v1/tournament/1/season/2/standings/total"))

    hits = find_player("Erling Haaland")
    print("search:", hits[:3])
    h = hits[0]

    keys = ("appearances", "minutesPlayed", "goals", "expectedGoals", "assists", "totalShots", "rating")
    pl = player(h["id"], h["slug"], competition="Premier League")
    print(json.dumps(pl["profile"], ensure_ascii=False))
    print("competitions:", pl["competitions"][:6])
    s = pl["season"]
    print(s["competition"], s["season"], s["ids"], {k: s["stats"].get(k) for k in keys})
    for g in pl["matches"][:4]:
        print("  ", g["date"], g["competition"], g["home"], g["score"], g["away"], "| rating", g["rating"], "min", g["minutes"], "G", g["goals"], "A", g["assists"])

    s = player(h["id"], h["slug"], competition="Premier League", season="25/26")["season"]
    print(s["competition"], s["season"], s["ids"], {k: s["stats"].get(k) for k in keys})

    last = next(g for g in pl["matches"] if g["status"] == "finished")
    mt = match(last["id"], last["slug"], last["custom_id"])
    print(mt["match"], "|", mt["status"], mt["date"], mt["competition"], "|", mt["venue"], "| ref", mt["referee"])
    for e in mt["events"]:
        if e["type"] == "substitution":
            print("  ", f'{e["min"]}\'', "sub", e["side"], "in:", e["in"], "out:", e["out"])
        elif e["type"] != "period":
            print("  ", f'{e["min"]}\'', e["type"], e["class"], e["side"], e["player"], "assist:", e["assist"], e["score"] or "")
    for side in ("home", "away"):
        L = mt["lineups"][side]
        xi = [f'{p["shirt"]} {p["name"]} ({p["pos"]}, {p["rating"]})' for p in L["players"] if not p["sub"]]
        print(side, L["formation"], len(xi), "starters:", "; ".join(xi[:3]), "... | bench:",
              sum(p["sub"] for p in L["players"]), "| missing:", L["missing"][:3])
    print({k: mt["stats"][k] for k in ("Ball possession", "Expected goals", "Total shots", "Corner kicks") if k in mt["stats"]})
finally:
    close_tab(tab)
```

Output observed on 2026-11-02:

```text
robots: /football/player/x/1 -> True | /api/v1/tournament/1/season/2/standings/total -> False
search: [{'id': 839956, 'slug': 'erling-haaland', 'name': 'Erling Haaland', 'team': 'Manchester City'}, {'id': 1436462, 'slug': 'erling-haaland', 'name': 'Erling Haaland', 'team': 'Ukumari'}]
{"name": "Erling Haaland", "team": "Manchester City", "position": "F", "born": "2000-07-21", "country": "Norway", "height_cm": 195, "foot": "Left", "shirt": 9, "market_value": {"value": 240000000, "currency": "EUR"}}
competitions: ['UEFA Champions League', 'UEFA Nations League', 'Premier League', 'Community Shield', 'FIFA World Cup', 'World Cup Qual. UEFA']
Premier League 26/27 (17, 96668) {'appearances': 9, 'minutesPlayed': 800, 'goals': 9, 'expectedGoals': 6.5654, 'assists': 0, 'totalShots': 34, 'rating': 7.7888888888889}
   2026-11-14 UEFA Nations League Norway None Wales | rating None min None G 0 A 0
   2026-11-07 Premier League Nottingham Forest None Manchester City | rating None min None G 0 A 0
   2026-10-31 Premier League Manchester City 0-1 Brighton & Hove Albion | rating 6.7 min 90 G 0 A 0
   2026-10-24 Premier League Aston Villa 2-1 Manchester City | rating 7.9 min 90 G 1 A 0
Premier League 25/26 (17, 76986) {'appearances': 35, 'minutesPlayed': 2958, 'goals': 27, 'expectedGoals': 25.4326, 'assists': 8, 'totalShots': 126, 'rating': 7.3114285714286}
Manchester City 0-1 Brighton & Hove Albion | Ended 2026-10-31 Premier League | Etihad Stadium | ref Craig Pawson
   11' goal regular away Yasin Ayari assist: Maxim De Cuyper 0-1
   20' card yellow away Chema Andrés assist: None 
   49' card yellow away Maxim De Cuyper assist: None 
   55' sub home in: Rayan Cherki out: Ayyoub Bouaddi
   64' sub away in: Jaouen Hadjam out: Olivier Boscagli
   64' sub away in: Mats Wieffer out: Chema Andrés
   64' sub home in: Nico O'Reilly out: Enzo Fernández
   72' sub away in: Malick Yalcouyé out: Maxim De Cuyper
   72' sub away in: Jack Hinshelwood out: Charalampos Kostoulas
   79' sub home in: Allan out: Iliman Ndiaye
   79' sub home in: Phil Foden out: Joško Gvardiol
   81' card yellow away Pascal Groß assist: None 
   84' sub away in: Georginio Rutter out: Diego Gómez
home 4-3-3 11 starters: 1 Gianluigi Donnarumma (G, 7.4); 27 Matheus Nunes (D, 6.5); 45 Abdukodir Khusanov (D, 7) ... | bench: 9 | missing: ['Antoine Semenyo']
away 4-2-3-1 11 starters: 1 Bart Verbruggen (G, 9.6); 20 Costinha (D, 7); 44 Luka Vušković (D, 7.1) ... | bench: 9 | missing: ['Evan Ferguson', 'Femi Azeez', 'Ferdi Kadıoğlu']
{'Ball possession': ('62%', '38%'), 'Expected goals': ('1.64', '1.00'), 'Total shots': ('21', '7'), 'Corner kicks': ('8', '2')}
```

Checked against the rendered pages: Premier League 26/27 card showed APPEARANCES 9, MINUTES PER GAME 89, GOALS 9, xG 6.57, ASSISTS 0; the 25/26 card showed APPEARANCES 35, GOALS 27, xG 25.43, ASSISTS 8, 2958 minutes; the match Statistics tab showed xG 1.64 / 1.00, total shots 21 / 7, possession 62% / 38%.

## Fields

| Function | API response the page loads (`/api/v1/...`) | Returned |
|---|---|---|
| `find_player(name)` | `search/all?q=<name>&page=0` | `id, slug, name, team` for `type == "player"` hits (same name can match several players; check `team`) |
| `player()` profile | `player/<id>` | name, team, position (G/D/M/F), born, country, height_cm, foot, shirt, market_value (`proposedMarketValueRaw`, EUR) |
| `player()` matches | `player/<id>/events/last/0` | per match: id, slug, custom_id, date, competition, status, home, away, score, rating, minutes, bench, goals, assists (from `statisticsMap`, `incidentsMap`, `onBenchMap`) |
| `player()` season | `player/<id>/statistics/seasons` + `player/<id>/unique-tournament/<ut>/season/<s>/statistics/overall` | `competition, season, ids=(ut, s), stats` (raw dict: appearances, matchesStarted, minutesPlayed, goals, expectedGoals, assists, expectedAssists, totalShots, shotsOnTarget, keyPasses, accuratePassesPercentage, totalDuelsWonPercentage, tackles, yellowCards, rating, saves, cleanSheet...) |
| `match()` | `event/<id>` | match, status, date, competition, venue, referee |
| `match()` events | `event/<id>/incidents` | chronological `min, added, type (goal/card/substitution/varDecision/period), class (seen: regular, yellow), side, player, assist, in, out, score` |
| `match()` lineups | `event/<id>/lineups` | `confirmed`, per side `formation`, `players[] {name, shirt, pos, sub, rating, minutes}`, `missing[]` |
| `match()` stats | `event/<id>/statistics` | period `ALL` items as `{name: (home, away)}` display strings |

## Gotchas

- Wrong tournament by default: the Season tab opens on the first competition in `statistics/seasons` (UEFA Champions League for Haaland), not the league. Pass `competition=` with the name exactly as the dropdown shows it.
- The page sends its first `player/...`, `event/.../lineups` and `.../statistics` requests twice and aborts the first copy (`net::ERR_ABORTED`). `_collect` ignores failed copies and waits for the one that finishes.
- `events/last/0` also contains upcoming fixtures (score `None`, no rating). Only this first page loads with the player page; the block does not page further back.
- Upcoming match: `match()` returns status "Not started", no events or stats, and predicted lineups with `confirmed: False` (11 per side). It waits the full 25 s for the responses that never come (28 s observed).
- A "Help us improve" survey modal can cover the page and swallow clicks; `dismiss_survey()` clicks "Ask me later".
- A hash-only URL change does not reload the page, so `sofa_load` goes through `about:blank` (with a 3 s pause) before every page.
- `/football` redirects to `/`. Match slugs are not always "home-away" (`brighton-and-hove-albion-manchester-city` for Man City at home); take `slug` and `customId` from `player()` matches or search, never build them.
- The match page also loads `tournament/1/season/<id>/standings/total`, which `/*/standings/` disallows. The block never reads it.
- `Network.setBlockedURLs` applies per tab: while authoring, a tab opened without it got redirected to the scam page again.
- Pages loaded while authoring carried a Cloudflare Turnstile widget; it never challenged at this pace. On a challenge page or a 403/429 the block raises; stop, do not retry around it.

## What does not work

- Plain HTTP (curl/urllib) to any sofascore.com URL tested, including robots.txt: 403.
- Calling `/api/v1/...` directly: not attempted. It is the site's internal API, not a public one; this skill only reads what the public pages load.
- Standings pages and season-archive paths containing `/2017-` ... `/2025-`: robots-disallowed, not used.
- Other sports: only `/football/...` pages were tested.
