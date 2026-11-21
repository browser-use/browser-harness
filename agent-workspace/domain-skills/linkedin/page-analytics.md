# LinkedIn — Company Page Analytics (read-only)

Field-tested against linkedin.com on 2026-10-01, logged in as a page admin.

## Routes

The numeric page id is in the "My pages" list in the left rail of `/feed/` (the admin link is
`/company/<pageId>/admin/...`).

- `https://www.linkedin.com/company/<pageId>/admin/analytics/followers/`: total followers, new followers (organic,
  sponsored, auto-invited)
- `.../admin/analytics/updates/`: impressions, reactions, comments, reposts for the period, and the per-post table
- `.../admin/analytics/visitors/`: page views, unique visitors, custom button clicks

## The per-post table (Updates tab)

It gives per post: impressions, views (video), clicks, CTR, reactions, comments, reposts, follows, engagement rate.
That makes it the free source of per-post impressions and engagement rate for a page.

1. It defaults to "Last 15 days" and 10 rows. Open "Time range:", pick "Last 30 days", then set "Show" to 20.
2. Read it as a plain table:

```python
rows = js("""[...document.querySelectorAll('table tr')].map(tr =>
  [...tr.querySelectorAll('th,td')].map(c => c.innerText.trim()))""")
```

## Traps

- Every row has a "Boost" button (a paid promotion flow). Never click by coordinates near the rows; use the table
  read above.
- The "Metrics" dropdown on the Updates chart (engagement rate, members reached) responds to coordinate clicks only,
  not to `element.click()`.
- Posts less than a day old keep changing between reads; leave them out of comparisons.
