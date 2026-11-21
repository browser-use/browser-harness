# Telegram Web — notes

Host: `web.telegram.org` (versions `/k/` and `/a/`). The skill lookup uses the
first host label, so this file lives in `domain-skills/web/`.

## One tab per account

Telegram Web keeps one active web session per account per browser profile.
If you open a second tab, the first tab shows a "logged out" / "open in this tab"
screen, and the user loses the session they were using.

- Never `new_tab("https://web.telegram.org/...")` when a Telegram tab already exists.
- Find the existing tab with `list_tabs()` (match on `web.telegram.org`) and attach to it with `switch_tab(tid)`.
  It stays in the background; do not call `activate_tab()`.
- Change chats inside that tab with the URL fragment (for example `#@username` or `#<peer id>` in `/k/`) instead of a new navigation.

## Background tab

The chat list and messages render while the tab is hidden. If an input or a
modal does not react, enable focus emulation on that tab first:

```python
cdp("Emulation.setFocusEmulationEnabled", enabled=True)
```

## Prefer the Bot API for bots

To send messages as a bot, use `https://api.telegram.org/bot<token>/sendMessage`
with `http_get`/HTTP, not the web UI.
