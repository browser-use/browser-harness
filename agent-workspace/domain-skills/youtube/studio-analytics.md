# YouTube Studio — Channel Analytics (read-only)

Field-tested against studio.youtube.com on 2026-10-01, logged in as a channel owner. (For public video data
without login, see `scraping.md`.)

## Routes

- `https://studio.youtube.com/channel/<channelId>/analytics/tab-overview/period-default`: views, watch time and
  subscribers for the last 28 days, plus the realtime card (subscribers, views in the last 48 hours)
- swap `period-default` for `period-lifetime` for all time
- `https://studio.youtube.com/channel/<channelId>/videos/short`: each Short with visibility, date, views, comments

## Traps

- Studio follows the Chrome profile, not a URL parameter: in a profile whose Google account cannot manage the channel,
  the route shows "Oops, you don't have permission", and `authuser=0..3` does not switch accounts. Open the tab in
  the right profile (see `interaction-skills/tabs.md`, "Several Chrome profiles").
- Public view counts for a single video are also on the watch page (`"viewCount":"N"` in its HTML), which needs no
  login. Use Studio only for what is private (watch time, subscribers, realtime).
