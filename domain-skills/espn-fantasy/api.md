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

## Driving the draft room UI

The room is at `/football/draft?leagueId=...&teamId=...`. It only exists from
roughly an hour before the draft; before that the URL redirects to the fantasy
home page. To develop against it earlier, use the **league-specific practice
draft** in `/football/mockdraftlobby` — same settings, auto opponents, and it is
listed as "Practice Draft" next to your league name.

**Practice and mock drafts do NOT report to the API.** `mDraftDetail` shows
`made: 0` while the practice room is visibly in round 9. So a practice room can
only validate UI mechanics; anything that polls the API has to be tested against
a real draft.

### The player pool is a virtualized FixedDataTable

Every cell is an independently positioned `<div>`; **there is no row element
containing both the player name and the action button**, so `closest('tr')` and
any DOM-climbing approach returns nothing. Associate a button with its player by
**vertical position** instead:

```python
# cells in the same visual row share a Y centre
same_row = abs(name_cell.y_center - button.y_center) < 14
```

Two refinements that matter:
- Take the name from `[class*="player-column"]` specifically. The news and
  injury-status icons sit between the name and the button, so "nearest cell to
  the left" picks up a tooltip instead of a player.
- Scope candidates to the **same FixedDataTable root** (`fixedDataTableLayout_main`).
  The pick-queue and roster panels share vertical positions with pool rows, and
  without scoping you will match a name from a different panel — which means
  clicking DRAFT on the wrong player.

### Buttons

Each pool row has a `QUEUE` button. When you are on the clock those become
`DRAFT` buttons (plus one extra `DRAFT` in the "You are on the clock!" banner —
exclude it, it has no player name).

Filter the list first with `input[placeholder="Player Name"]`, setting the value
through the native setter so React notices:

```python
set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set
set.call(input, name); input.dispatchEvent(new Event('input',{bubbles:true}))
```

**The pool re-renders a beat AFTER your turn starts.** Checking once at the
moment the clock flips finds only the banner button and no identifiable rows.
Retry for a couple of seconds before concluding the pick cannot be made.

### Autopick

`.on-autopick` present means autopick is on, and **autopick hides the queue and
draft controls entirely** — if the buttons are missing, this is why. There is a
"Disable Autopick" button.

**ESPN silently re-enables autopick after you miss a pick.** Re-check it every
poll, not just at startup, or the rest of the draft quietly goes to ESPN's own
rankings.

### Budget the clock

The pick clock is short (90s in a normal league) and every probe costs a search
plus a re-render wait. Probing 25 players at ~3s each spends 65s and the turn is
gone before anything is clicked.

Only the **first** probe of a turn needs to be patient — that is the one racing
the post-turn re-render. Every probe after it can be a single check at ~0.7s.
Give the whole walk a hard budget (30s works) and spend what is left on reading
the board directly.

### Last resort: read the board, do not trust your state

Rather than failing when your idea of who is available disagrees with the room,
enumerate the rows that actually have DRAFT buttons, match them against your own
rankings, and take the best one. Measured at **under one second**, and it cannot
fail while the page renders. With the API deliberately stale for an entire
rehearsal draft this produced a sensible pick every single time.

### The pick queue is the safety net

ESPN drafts from your pick queue when the clock expires. Keeping the queue
loaded with your ranked choices means a hung script, a dead browser, or an
absent user still produces your pick rather than ESPN's default. Queue state is
readable from `.pick-queue`.

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
