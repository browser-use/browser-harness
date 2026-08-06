# X (Twitter) — UI Automation

`https://x.com` — DOM-level reads when the API path (see `auth-api.md`) is overkill.

## Do this first

**If you need structured data for a timeline, notifications, or search — use `auth-api.md`. It's faster, paginates cleanly, and bypasses DOM quirks.**

DOM scraping is the right tool for:
- A quick single-profile read
- Page regions the API doesn't expose (hovercards, badges rendered client-side)
- When the user needs the visible tab to respond (mimicking interaction)

## Profile page — `/<screen_name>`

Stable `data-testid` selectors survive the re-renders X ships weekly. Anchored counts (`a[href$="/following"]`) survive localization and compact-number changes.

```python
js("window.location.href = 'https://x.com/SCREENNAME'")
wait_for_load(); wait(2)   # React hydration

info = js("""(() => ({
  name:   document.querySelector('[data-testid="UserName"]')?.innerText,        // 'display name\\n@handle'
  bio:    document.querySelector('[data-testid="UserDescription"]')?.innerText,
  following: document.querySelector('a[href$="/following"] span')?.innerText,
  followers: document.querySelector('a[href$="/verified_followers"] span, a[href$="/followers"] span')?.innerText,
  url: location.href,
}))()""")
```

Notes:
- `UserName` innerText contains **both** the display name and `@handle` separated by `\n` — split on newline if you need them apart.
- The follower count link is `/verified_followers` on accounts with X Premium visible, `/followers` otherwise — query both with a comma fallback.
- Numbers are pre-formatted (`1.2K`, `313`) — parse if you need integers.

## Traps

- **`UserProfileHeader_Items`** is the container shown in older docs; still present but less reliable across redesigns than the item-level testids above.
- **`setCacheDisabled` can bite you.** X's own service worker aggressively caches route chunks; with cache disabled, first navigation can 30s-timeout on chunk loads. Leave the cache on for UI reads.
- **Timeline scrolling in the DOM is virtualized.** Scrolling `window` works visually, but the tweet rows are destroyed/recreated off-screen. For bulk reads, use the API in `auth-api.md` (`HomeTimeline`, `UserTweets`); don't scroll-and-scrape.
