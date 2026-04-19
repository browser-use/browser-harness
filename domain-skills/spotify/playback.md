# Spotify — Web Player Playback

Field-tested against open.spotify.com on 2026-04-19. Requires the user to be logged in to the Web Player.

---

## Trap: coordinate clicks don't trigger playback

`click(x, y)` on a play button or a track row is the obvious move, but Spotify's React handlers **do not fire** on `Input.dispatchMouseEvent`. The row visibly highlights and the tooltip appears, but the player state does not change.

Drive playback through the DOM instead:

```python
js("""document.querySelector('button[aria-label="Play BKJB by Nation"]').click()""")
```

This is one of the cases in the SKILL.md "if compositor clicks are the wrong tool" bucket. Use coordinate clicks only for things that aren't reactive buttons (e.g. scrubber position on the progress bar).

## Stable selector: `aria-label="Play <Track> by <Artist>"`

Every in-page play button — top result, song rows, artist/album tiles — exposes the same aria-label shape:

- Song row:       `Play <Track> by <Artist>`
- Album/playlist: `Play <Album name>` / `Play <Playlist name>`
- Top Result:     aria-label is just `Play` — use `[data-testid="top-result-card"] button[aria-label="Play"]` to scope.

These survive React re-renders and are exact-match unique, so `querySelector` via aria-label is more reliable than DOM position.

## Search URL pattern

```
https://open.spotify.com/search/<url-encoded query>
```

Loads full search results SSR-free (client-side render). No need to click into the search box and type — navigate directly, then `wait_for_load()` + a short `wait(2)` for React to hydrate.

```python
from urllib.parse import quote
new_tab(f"https://open.spotify.com/search/{quote('bkjb nation')}")
wait_for_load(); wait(2)
js('document.querySelector(\'button[aria-label="Play BKJB by Nation"]\').click()')
```

## Player state selectors

Read current playback state without screenshots:

| What                 | Selector                                                 | Value        |
|----------------------|----------------------------------------------------------|--------------|
| Current track title  | `[data-testid="context-item-link"]`                      | `innerText`  |
| Current artist       | `[data-testid="context-item-info-artist"]`               | `innerText`  |
| Play/pause state     | `[data-testid="control-button-playpause"]`               | aria-label is `"Play"` (paused) or `"Pause"` (playing) |
| Now-playing widget   | `[data-testid="now-playing-widget"]`                     | presence check |
| Top result card      | `[data-testid="top-result-card"]`                        | scope container |

```python
state = js("""(() => ({
  title:   document.querySelector('[data-testid="context-item-link"]')?.innerText,
  artist:  document.querySelector('[data-testid="context-item-info-artist"]')?.innerText,
  state:   document.querySelector('[data-testid="control-button-playpause"]')?.getAttribute('aria-label'),
}))()""")
# {'title': 'BKJB', 'artist': 'Nation', 'state': 'Pause'}  # state='Pause' means currently playing
```

Invert the `state` field when reading — the button shows the *action available*, not the current state.

## Deep links that skip search entirely

If you already have a Spotify ID, prefer a direct URL over search → click:

```
https://open.spotify.com/track/<id>     # opens the track page, then click the big Play
https://open.spotify.com/album/<id>
https://open.spotify.com/playlist/<id>
```

On the track/album page the main play button is `button[data-testid="play-button"]` (also has aria-label `Play` / `Pause`).

Spotify IDs can be looked up via the oEmbed / embed approaches in `scraping.md` without needing a browser.

## Traps

- **Row-hover tooltip ≠ play triggered.** If a screenshot shows the "Play X by Y" tooltip appearing over a row, that only means the hover fired. Verify with the `control-button-playpause` aria-label, not the tooltip.
- **First track title may lag.** Immediately after clicking, `context-item-link` can still show the *previous* track for ~500ms. Sleep 1-2 seconds before reading, or poll until the title changes.
- **Coordinate click on the play-button area sometimes works on the top-result card but not on song rows.** Don't rely on it — use the DOM click path everywhere for consistency.
- **Autoplay policies.** If the tab has never had user interaction, Chrome may block audio autoplay. The UI will show "Pause" (meaning it thinks it's playing) but no audio comes out. A real `click()` (dispatched via the DOM) counts as a user gesture for this purpose; navigating with `new_tab` + DOM click has been reliable.
