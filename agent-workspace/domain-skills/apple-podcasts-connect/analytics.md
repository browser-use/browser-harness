# Apple Podcasts Connect — Show Analytics (read-only)

Field-tested against podcastsconnect.apple.com on 2026-10-01, logged in with a show admin account.

## Routes

- `https://podcastsconnect.apple.com/analytics/show/<show-slug>/<showId>/overview`: followers, listeners, engaged
  listeners, plays, time listened (split following / not following)
- same path with `/episodes`: per-episode listeners, engaged listeners, plays, average consumption

`<showId>` is the numeric id from the show's Apple Podcasts URL (`.../id<showId>`). Open these paths directly:
other guessed `/analytics/show/...` shapes bounced to the Apple sign-in page even with a valid session.

## JSON

The overview is fed by

```
/podcasts/pcc/v1/analytics/showOverviewV3?showId=<showId>&start=YYYY-MM-DD&end=YYYY-MM-DD&mode=ALL_TIME|ROLLING_60|MONTHLY
```

which returns plain JSON when fetched from the page. It also carries exact values where the UI rounds
("1.2K" listeners in the UI, 1,227 in the JSON). The episodes endpoint returns protobuf: read the episode table from
the page instead.

## Traps

- There is no "last 30 days" preset. The presets are Last 60 Days and All Time, plus Week and Month calendars.
- Data can lag up to 72 hours: a new episode is missing from the episodes table for its first days.
- Some cells in the episodes table show "-". That is not zero; report it as "not shown".
