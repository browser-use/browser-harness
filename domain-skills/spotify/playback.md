# Spotify — Web Player UI Automation

Driving open.spotify.com's player via the DOM. For HTTP-only library/search/lyrics/playback, see `api-internals.md` — it's usually faster than clicking through the UI. Use this file when you genuinely need the user's visible tab to do the work.

Requires the user to be logged in to the Web Player.

## Trap: coordinate clicks don't trigger playback

`click(x, y)` on a play button or track row is the obvious move, but Spotify's React handlers **do not fire** on `Input.dispatchMouseEvent`. The row visibly highlights and the tooltip appears, but player state does not change. Drive playback through the DOM instead:

```python
js("""document.querySelector('button[aria-label="Play Never Gonna Give You Up by Rick Astley"]').click()""")
```

One of the SKILL.md "if compositor clicks are the wrong tool" cases. Reserve `click(x, y)` for non-reactive targets (e.g. the scrubber position on the progress bar).

## Stable selector: `aria-label="Play <Track> by <Artist>"`

Every in-page play button exposes the same aria-label shape — it survives React re-renders and is exact-match unique, so `querySelector` via aria-label beats DOM position.

- Song row:       `Play <Track> by <Artist>`
- Album/playlist: `Play <Album name>` / `Play <Playlist name>`
- Top Result:     just `Play` — scope with `[data-testid="top-result-card"] button[aria-label="Play"]`
- Collab tracks:  `Play <Track> by <Artist A>, <Artist B>` (full comma-joined list)

## Player state selectors

Read playback state without screenshots:

| What                 | Selector                                                 | Value                                          |
|----------------------|----------------------------------------------------------|------------------------------------------------|
| Current track title  | `[data-testid="context-item-link"]`                      | `innerText`                                    |
| Current artist       | `[data-testid="context-item-info-artist"]`               | `innerText`                                    |
| Play/pause state     | `[data-testid="control-button-playpause"]`               | aria-label `"Play"` (paused) / `"Pause"` (playing) |
| Now-playing widget   | `[data-testid="now-playing-widget"]`                     | presence check                                 |

```python
state = js("""(() => ({
  title:  document.querySelector('[data-testid="context-item-link"]')?.innerText,
  artist: document.querySelector('[data-testid="context-item-info-artist"]')?.innerText,
  state:  document.querySelector('[data-testid="control-button-playpause"]')?.getAttribute('aria-label'),
}))()""")
```

**Invert the `state` field** — the button shows the *action available*, not the current state. `state == "Pause"` means currently playing.

## URL patterns

```
https://open.spotify.com/search/<url-encoded query>   # client-side search results page
https://open.spotify.com/track/<id>                   # track page (big Play button)
https://open.spotify.com/album/<id>
https://open.spotify.com/playlist/<id>
https://open.spotify.com/collection/tracks            # your Liked Songs
```

Navigate directly, then `wait_for_load()` + a short `wait(2)` for React to hydrate. On track/album pages the main play button is `button[data-testid="play-button"]` (same `Play`/`Pause` aria-label convention).

Spotify IDs can be looked up via oEmbed / embed (see `scraping.md`) or via `searchDesktop` (see `api-internals.md`), both without a browser.

## Traps

- **First track title lags.** Immediately after clicking Play, `context-item-link` can still show the *previous* track for ~500ms. Sleep 1-2s before reading, or poll until the title changes.
- **Autoplay policies.** If the tab has never had user interaction, Chrome may block audio autoplay. The UI will show `Pause` (meaning it thinks it's playing) but no audio comes out. A real DOM `click()` counts as a user gesture; `new_tab` + DOM click has been reliable.
