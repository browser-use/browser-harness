# Best Coast Pairings (bestcoastpairings.com)

Tournament pairings/results platform for tabletop wargames. **You almost never
need the browser** — the SPA's REST API is fully readable logged-out with one
header. Use `http_get`.

## Private API

Base: `https://newprod-api.bestcoastpairings.com`

**Required header: `client-id: web-app`** (the literal string — it's
`REACT_APP_AUTH_CLIENT_ID` baked into `main.*.js`; without it every request
400s with `{"error":"client-id header parameter is missing"}`). No auth/login
needed for public reads. Authenticated calls add `Authorization: Bearer <cognito token>`,
but event search and placings don't need it.

### Event search

```
GET /v2/events?limit=40&startDate=2026-06-01T00:00:00Z&endDate=2026-07-12T23:59:59Z
    &sortKey=eventDate&sortAscending=true
    &location={"distance":50,"center":{"lat":33.44,"long":-112.07},"distanceType":"miles"}
```

- `location` is URL-encoded JSON. Omit it for global search.
- Response `{data: [...], nextKey, prevKey}` — paginate by passing `nextKey` back.
- Useful event fields: `id`, `name`, `dates.start/end` (UTC Z), `status.{started,ended,currentRound,numberOfRounds}`, `playerCounts.{checkedIn,dropped,active}`, `location.name` (venue), `gameSystem.name`, `owner`, `ticketing`.

### Placings / roster

```
GET /v1/events/{eventId}/players?placings=true&limit=250
```

- **Trap: response has NO `data` key.** Players are under `active` and `dropped` arrays.
- Per player: `placing`, `user.{firstName,lastName}`, `team.name` (club/team affiliation — how you find a club's members), `faction.name`, `subFaction`, `checkedIn`, `dropped`.
- Placings exist once an event has run; upcoming events return empty arrays.
- **Trap: for UPCOMING events, `placings=true` returns empty `active`.** Drop the
  `placings` param (`GET /v1/events/{id}/players?limit=500`) and the registered
  roster is under `active` — but with a `deleted` key that exactly mirrors
  `active` (same ids), so read `active` only, don't concatenate. Row shape is
  slimmer than post-event: just `user.{id,firstName,lastName}`, `checkedIn`,
  `dropped` — no faction/team. `event.playerCounts.total` (from `/v2/events/{id}`)
  matches this registered count.

### Team events

If `event.format.teamEvent` is true, individual placings are NOT the story —
team standings live at:

```
GET /v1/events/{eventId}/teamplayers?placings=true&limit=200
```

- Same `{active, dropped}` shape (note: top-level key `deleted` may replace `dropped`).
- Per team: `name`, `placing`, `overallPlacing`, `captain`, `metrics`.
- **Trap:** a player row's `team`/`teamId` is their CLUB affiliation, not their
  event team. The event team is `teamPlayerId`, which matches a teamplayers
  row's `id`. Build rosters by grouping players on `teamPlayerId`.

### Army lists (login required)

Player rows carry `listId`/`listUrl` (`/list/{id}`). `GET /v1/armylists/{listId}`
returns 401 without `Authorization: Bearer <cognito access token>` — this is
the only common read that needs auth. The web app is AWS Amplify/Cognito;
tokens live in the logged-in browser's localStorage
(`CognitoIdentityServiceProvider.*`). Player `faction.name` on the placings
row is usually populated anyway; the list is the fallback when it's null.

### Other observed endpoints

- `GET /v2/events/{id}?role=true` — single event detail (includes `format.teamEvent`, `teamPlayerCounts`)
- `GET /v1/gamesystems?limit=100` — game system list (paginated via nextKey)

## UI notes (if you must drive the page)

- React + MUI. Event pages at `/event/{id}`, search at `/play/events`.
- The location filter is a dropdown containing a nested "Search Location"
  autocomplete input (Google Places) — click the dropdown, then click the
  inner input, then type; suggestions render below.
- Cookie consent banner on first visit; "Essential Only" button dismisses.
- Watch API traffic with `performance.getEntriesByType('resource')` — the SPA
  calls `newprod-api` and the URLs are replayable via `http_get` + `client-id`.

### Pairings / match results (per round)

```
GET /v1/events/{eventId}/pairings?eventId={eventId}&round=N&pairingType=Pairing&limit=500
```

- **Trap: like `/players`, the list is under `active`, NOT `data`** — `.get("data")`
  silently returns nothing.
- No auth. One request per round; `event.status.numberOfRounds` says how many rounds.
- Per pairing: `round`, `table`, `isDone`, `player1Id`/`player2Id` (roster row ids),
  embedded `player1`/`player2` objects (`user.{id,firstName,lastName}` — `user.id` is the
  **stable cross-event user id** — plus `faction`, `parentFaction`, `team`, `listId`),
  and `player1Game`/`player2Game` = `{id, result, points}` (result: 2 win / 0 loss;
  1 presumably draw).
- Key-naming quirk: pairing game objects use `result`/`points`; the roster row's `games`
  array holds the same values as `gameResult`/`gamePoints` keyed by `gameNum`.
- Together with the roster this is the full match graph (who played whom, both scores,
  factions) — enough for Elo or meta analysis, all logged-out.
