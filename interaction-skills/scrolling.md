# Scrolling

Separate page scroll, nested containers, virtualized lists, and dropdown menus, and identify which element is actually consuming wheel events before scrolling.

## Hidden tabs

Start with the normal `scroll(...)` helper. Chrome on Windows can leave a
mouse-wheel command unanswered when the attached tab is not visible. If that
scroll times out:

1. Do not call `activate_tab()`; a timeout is not permission to foreground
   Chrome.
2. Temporarily call
   `cdp("Emulation.setFocusEmulationEnabled", enabled=True)`, retry the same
   `scroll(...)` once, and re-read the page or container scroll position.
3. Disable focus emulation in a `finally` block.

If background scrolling still fails, stop and name that exact limitation.
Call `activate_tab()` only when the user explicitly asks to see or visibly
switch to the tab. Do not replace wheel input with custom `Runtime.evaluate`
scrolling or a cross-frame JavaScript walker; those paths change page semantics
and require context the agent does not have.
