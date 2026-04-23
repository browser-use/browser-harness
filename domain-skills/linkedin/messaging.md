# LinkedIn — Messaging

## URL

Direct route: `https://www.linkedin.com/messaging/`

No required query params. Loads the full inbox list immediately.

## Navigation

Use `goto("https://www.linkedin.com/messaging/")` on an existing tab — `new_tab()` hangs on LinkedIn (see `interaction-skills/connection.md` for the general rule).

## Stable selectors

| Target | Selector |
|---|---|
| Conversation card (each row) | `.msg-conversation-card__content--selectable` |
| Sender name | `.msg-conversation-card__participant-names` |
| Timestamp | `time.msg-conversation-card__time-stamp` (or `time[datetime]` inside the card) |
| Message preview snippet | `.msg-conversation-card__message-snippet` |

## Extracting the inbox via JS

```python
cards = js("""
Array.from(document.querySelectorAll('.msg-conversation-card__content--selectable')).map(c => ({
    name: c.querySelector('.msg-conversation-card__participant-names')?.innerText?.trim(),
    ts:   c.querySelector('time')?.getAttribute('datetime'),
    preview: c.querySelector('.msg-conversation-card__message-snippet')?.innerText?.trim()
}))
""")
```

The `datetime` attribute on `time` is ISO 8601 (e.g. `2026-04-22T14:30:00.000Z`) — use it for date filtering instead of the display text.

## Invocation note

When calling the harness from a background or sub-agent context, use:

```bash
uv run python -c "
import sys; sys.path.insert(0, '.')
from helpers import *
goto('https://www.linkedin.com/messaging/')
wait_for_load()
# ...
"
```

The `browser-harness <<'PY' ... PY` heredoc form hangs in background invocations on this repo.
