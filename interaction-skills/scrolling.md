# Scrolling

Separate page scroll, nested containers, virtualized lists, and dropdown menus, and identify which element is actually consuming wheel events before scrolling.

## Hidden tabs

Use the normal `scroll(...)` helper. Chrome can leave a mouse-wheel command
unanswered when the tab is hidden. On cloud and `BU_CDP_URL` browsers the daemon
brings its own tab forward first; on local Chrome `scroll` retries once with
focus emulation, which does not move the user's tabs. Re-read the page or
container scroll position to confirm it moved.

If background scrolling still fails, do not call `activate_tab()`; a timeout is
not permission to foreground Chrome. Stop and name that exact limitation.
Call `activate_tab()` only when the user explicitly asks to see or visibly
switch to the tab. Do not replace wheel input with custom `Runtime.evaluate`
scrolling or a cross-frame JavaScript walker; those paths change page semantics
and require context the agent does not have.
