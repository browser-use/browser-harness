# AGENTS.md

For agents **modifying** harnesless. For using it, see SKILL.md.

## Philosophy

Both agent-browser (60+ verbs) and browser-use (~20 verbs) are walled gardens. Harnesless inverts this: few helpers, LLM edits them at runtime. Every design decision flows from that.

## Architecture

```
Chrome (127.0.0.1:9222) ── CDP WS ─▶ daemon.py ── /tmp/harnesless.sock ─▶ run.py (one per tool call)
                                     (long-running)                        (from helpers import *; exec(stdin))
```

Protocol: one JSON line per direction. Request: `{method, params, session_id}` (CDP passthrough) or `{meta: ...}`. Response: `{result}` / `{error}` / `{events}` / `{session_id}`.

Daemon attaches to the first real page target at startup, buffers events in `deque(maxlen=500)`.

## Design decisions worth preserving

- **Coordinate clicks default.** `Input.dispatchMouseEvent` goes through iframes/shadow/cross-origin at the compositor level — no per-frame session juggling.
- **Connect to user's running Chrome**, never launch one. User sees what's happening; cookies/logins are theirs.
- **cdp-use is used only for `CDPClient.send_raw`.** The 36k lines of typed wrappers are IDE sugar; raw CDP strings tokenize better and the LLM knows method names from training.
- **`run.py` is 3 lines on purpose.** No argparse, no subcommands. LLM writes Python.
- **helpers.py is editable at runtime.** This is the whole point.

## Rules when extending

- Helpers ≤ 15 lines. No classes. No deps beyond stdlib + cdp-use + websockets.
- Don't add meta verbs lightly; if it can be a helper calling `cdp()`, it's a helper.
- Never add: CLI argparse, tests, logging framework, config files, session manager, retries, multi-daemon.
- Taste test: could the LLM rewrite this from scratch after reading it once?

## Known gotchas

- **Chrome 144+ `chrome://inspect/#remote-debugging` does NOT serve `/json/version`.** Daemon reads `<ChromeProfile>/DevToolsActivePort` instead. Don't suggest the user launch with `--remote-debugging-port` — they don't want that.
- **Omnibox popups are `type: "page"` CDP targets** with ~50px viewports. Filter by URL prefix (`is_real_page` in daemon.py, `INTERNAL` tuple shared with helpers.py).
- `type_in`/clear uses Cmd+A (macOS). Linux/Windows: `2` instead of `4` for modifiers.
- `send_raw` has no timeout — stuck call hangs forever. Add a wrapper if it bites.
- Daemon's default session goes stale if user closes the attached tab manually. `ensure_real_tab()` re-attaches.
- Two tuples named `INTERNAL` (daemon.py, helpers.py) — cross-process, can't share module. Keep in sync.

## Session lessons

- **Half the original helpers were never called in practice.** Dropped: `get_dom`, `element_pos`, `click_element`, `type_in`, `save_cookies`, `load_cookies`, `set_viewport`, `screenshot_full`, `double_click`, `right_click`, `move_mouse`, `new_tab`, `close_tab`, `handle_dialog`, `back`, `reload`. Every DOM interaction went through `js("...")` with a bespoke selector.
- **`http_get` + `ThreadPoolExecutor` beats the browser for static scrapes.** 249 Netflix pages in 2.8s parallel.
- **`wait(5)` after goto is fragile.** `wait_for_load()` polls `document.readyState`.
- **Auth-gated sites (Upwork, X) redirect to login.** Not our problem; bail and ask the user.
