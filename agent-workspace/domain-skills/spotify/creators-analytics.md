# Spotify for Creators — Show Analytics (read-only)

Field-tested against creators.spotify.com on 2026-10-01, logged in as the show owner. (For public open.spotify.com
data, see `scraping.md`.)

## Routes

- `https://creators.spotify.com/analytics/show/<showId>/overview`: plays, audience, streams, consumption time,
  followers gained
- same path with `/audience` (new vs returning, gender, age, country) and `/engagement` (completion rate, retention,
  plays in the first 7 days per episode)
- `https://creators.spotify.com/home/show/<showId>`: the follower total

`<showId>` is the 22-character id from the show's open.spotify.com URL.

## Traps

- **The big numbers are animated counters.** `innerText` returns the digit strip (`0123456789...`) of each
  counter, not the value. Read them from a `screenshot()` instead.
- Each tab, and the "Detailed stream count" modal, has its own date dropdown (Last 7 / 30 / 90 days, Year to date,
  All time, Custom). Choose the option by its visible text; changing it on one tab does not carry over.
- Plays use a 30-second rule (since June 2026), streams a 60-second rule: the two numbers differ by design.
- Leave the cookie banner alone.
