# Castos — Podcast Analytics (read-only)

Field-tested against app.castos.com on 2026-10-01, logged in as the show owner.

## Routes

- `https://app.castos.com/analytics`: show totals (Listens, Spotify listens, Followers) with a date picker
- `https://app.castos.com/analytics/episodes/all?podcast=<podcastId>`: per episode (followers, all-time listens)
- `https://app.castos.com/analytics/platforms-and-apps`: listens by app and by OS

Guessing `/podcasts/<podcastId>/analytics` lands on a "not found" page. The public Castos API token has no
stats endpoint, so the dashboard (or its JSON, below) is the only source.

## Fastest: the page's own JSON

While a tab is on app.castos.com, `fetch` these from the page (session cookies apply). Leave out `start`/`end` to
get all time.

```python
base = "/data/analytics"
q = "podcast=<podcastId>&start=2026-09-01&end=2026-10-01"
for path in ("listens/day", "spotify/listens/day", "followers/total", "listens/platform", "listens/browser"):
    print(path, js(f"fetch('{base}/{path}?{q}').then(r => r.text())"))
# per episode, paged:
js(f"fetch('{base}/listens/episode?{q}&page=1&sort=post_date&sort_order=desc').then(r => r.text())")
```

`listens/browser` is the per-app split (Apple Podcasts, Overcast, Chrome, ...). Spotify is not in it: it is the
separate `spotify/listens` series.

## Traps

- The date range resets to "Last 90 days" every time you switch tabs in the UI. Set it again, or use the JSON.
- Episode numbers come from the show's metadata and can be wrong or missing on older entries (a re-released episode
  can carry the next number). Match episodes by title and publish date, not by number.
- Listens for an episode keep growing for weeks. To compare episodes fairly, use the same window after release, e.g.
  `start` = release day and `end` = release day + 6 for "first 7 days".
