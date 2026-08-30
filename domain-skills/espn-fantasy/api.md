# ESPN Fantasy (football) — private API

ESPN's fantasy site is a React SPA over a clean JSON API. **Never scrape the DOM.**
Every number the site renders — projections, ADP, live draft picks — is available
from three endpoints.

## Auth: fetch from inside the tab

The API needs the `espn_s2` session cookie, which is `httpOnly` (invisible to
`document.cookie`). Do **not** try to extract and replay it. Run `fetch()` from
inside a logged-in espn.com tab and the cookie rides along:

```python
js("""(async()=>{
  const r = await fetch(URL, {credentials:'include'});
  return JSON.stringify(await r.json());
})()""")
```

Check login state with CDP, which *can* see httpOnly cookies:

```python
cookies = {c["name"]: c["value"] for c in
           cdp("Network.getCookies", urls=["https://fantasy.espn.com/"])["cookies"]}
logged_in = "espn_s2" in cookies      # SWID alone is set for anonymous visitors
```

**Trap:** an anonymous visitor still gets a `SWID` cookie, so `SWID` is not a
login check. Only `espn_s2` is.

## Base URL

```
https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/{SEASON}/segments/0/leagues/{LEAGUE_ID}
```

`lm-api-reads` is the read replica and is the right host for polling.
The older `fantasy.espn.com/apis/v3/...` path still works but is rate-limited harder.

Find the league id and your team id in the clubhouse URL:
`fantasy.espn.com/football/team?leagueId=...&teamId=...&seasonId=...`

## Views

Append `?view=X&view=Y`. Combine freely.

| view | gives you |
|---|---|
| `mSettings` | scoring, roster slots, draft type/date, `pickOrder` |
| `mTeam` | team ids, names, owners |
| `mDraftDetail` | every draft pick — **poll this during a draft** |
| `kona_player_info` | player pool: projections, ADP, injury status, draft ranks |
| `mRoster` | current rosters |
| `mMatchup` | schedule and scores |

## Player pool — the `x-fantasy-filter` header

`kona_player_info` returns almost nothing useful until you pass a JSON filter
in the `x-fantasy-filter` **header** (not a query param):

```json
{"players":{
  "filterStatsForExternalIds":{"value":[2026]},
  "filterSlotIds":{"value":[0,2,4,6,16,17,23]},
  "filterStatsForSourceIds":{"value":[0,1]},
  "useFullProjectionTable":{"value":true},
  "sortAppliedStatTotal":{"sortAsc":false,"sortPriority":3,"value":"102026"},
  "sortDraftRanks":{"sortPriority":2,"sortAsc":true,"value":"PPR"},
  "limit":600,
  "filterRanksForRankTypes":{"value":["PPR"]}
}}
```

- `sortAppliedStatTotal.value` is `"10" + season` — the `10` prefix means
  *projected* season total. `"00" + season` is actual//historical.
- `limit` above ~1000 gets truncated silently. 600 covers everyone draftable.
- `filterRanksForRankTypes`: `STANDARD | PPR | HALF_PPR | SUPERFLEX | ELIMINATION`.

### Reading a player

```
player.stats[]           -> statSourceId==1 && statSplitTypeId==0 is the season projection
                            .appliedTotal is ALREADY scored for this league's rules
player.ownership.averageDraftPosition   -> ADP (0 means undrafted, not "pick 0")
player.draftRanksByRankType.PPR.rank    -> ESPN's own PPR rank
player.injuryStatus      -> ACTIVE | QUESTIONABLE | DOUBTFUL | OUT |
                            INJURY_RESERVE | SUSPENSION
player.defaultPositionId -> 1 QB, 2 RB, 3 WR, 4 TE, 5 K, 16 DST
player.eligibleSlots[]   -> lineup slot ids (below)
```

Use `appliedTotal` rather than summing raw stats — it already applies the
league's scoring, including PPR.

## Lineup slot ids

```
0 QB   2 RB   4 WR   6 TE   16 DST   17 K   20 BENCH   21 IR   23 FLEX
```

`settings.rosterSettings.lineupSlotCounts` is keyed by these ids. Sum everything
except IR to get roster size (= number of rounds in the draft).

Confirm PPR from scoring, not from the league name:

```python
rec = next(i for i in settings.scoringSettings.scoringItems if i["statId"] == 53)
rec["points"]      # 1 = full PPR, 0.5 = half, 0 = standard
```

## Draft state

`?view=mDraftDetail` → `draftDetail.picks[]` is **pre-populated with every slot
of the whole draft before it starts**, with `playerId: -1` for picks not yet
made. This is a gift:

```python
EMPTY = -1
made    = [p for p in picks if p["playerId"] != EMPTY]
on_deck = next(p for p in picks if p["playerId"] == EMPTY)   # who is on the clock
```

**Do not write `playerId > 0`.** Team defenses have *negative* ids
(−16001..−16034), so that test reads every D/ST pick as "not yet made" and
freezes your tracker from the first defense taken onward. `-1` is the only
sentinel.

Each pick has `overallPickNumber`, `roundId`, `roundPickNumber`, `teamId`,
`playerId`, and `autoDraftTypeId` (non-zero = the pick was auto-drafted).
Polling every 3s is comfortable; the payload is small.

`draftDetail.inProgress` flips true when the room opens, and `drafted` true when
it finishes.

### Snake pick numbers

`settings.draftSettings.pickOrder` is a list of **team ids in first-round order**,
so your slot is `pickOrder.index(my_team_id) + 1`, not your team id.

```python
for rnd in range(1, rounds + 1):
    in_round = slot if rnd % 2 else (n_teams - slot + 1)
    overall  = (rnd - 1) * n_teams + in_round
```

## Projected stat ids

`useFullProjectionTable: true` gives the full stat line, not just `appliedTotal`.
Aggregate these by `proTeamId` to profile an offense without any second source:

```
 0 pass att    1 completions   3 pass yds    4 pass TD   20 INT
23 rush att   24 rush yds     25 rush TD
42 rec yds    43 rec TD       53 receptions  58 targets
```

Useful derivations: team pass volume (starter's `0`), QB rush rate
(`23 / (0 + 23)`), player target share (`58 / team 0`).

## Team strength: FPI

```
https://site.web.api.espn.com/apis/fitt/v3/sports/football/nfl/powerindex
    ?region=us&lang=en&season={season}&limit=1000
```

Public, no auth. `teams[].categories[]` — find the one named `projections`;
`values` is positional, matching `names`:

```
projectedw, projectedl, probwinout, probwinconf, probwindiv,
probmakeplayoffs, probmakedivplayoffs, probmaketitlegame,
probwintitle, probmakeconfchamp
```

So `values[0]` is projected wins and `values[5]` is playoff odds.

## Player age

**Age and experience are not in the fantasy player payload.** Get them from the
core athlete API, which is public and keyed by the *same* id:

```
https://sports.core.api.espn.com/v3/sports/football/nfl/athletes/{id}
-> {fullName, age, dateOfBirth, experience:{years}}
```

No auth, so run it as plain parallel HTTP rather than through the browser —
~570 players in about 5 seconds with a `ThreadPoolExecutor`. Skip negative ids
(team defenses have no athlete record).

## Traps

- **`SWID` without `espn_s2` means logged out.** Anonymous visitors get a SWID.
- **ADP of `0` means undrafted**, not "goes first overall". Treat it as null.
- **Team defenses have negative player ids** (−16001..−16034). Any `id > 0`
  filter silently drops them; this is the single easiest way to break a live
  draft tracker.
- **ADP values are not ADP ranks.** Across the top 70, ADP *value* runs ~4 picks
  higher than ADP *rank* (a player who goes undrafted in some leagues carries an
  inflated average). If you simulate a draft one-player-per-pick, your realized
  positions track rank, so a constant offset versus ADP values is expected and
  should **not** be "corrected" away.
- **Team names need `str` keys** if you round-trip them through JSON — ESPN's
  `teamId` is an int and `json.dump` will silently stringify the keys.
- Kickers and defenses are absent from `kona_player_info` unless slot ids
  `16` and `17` are in `filterSlotIds`.
- The draft room UI itself is a websocket app; do not try to drive it by polling
  this REST API. Use the API to *decide*, and click to *act*.
