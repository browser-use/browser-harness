# Scrolling

Separate page scroll, nested containers, virtualized lists, and dropdown menus, and identify which element is actually consuming wheel events before scrolling.

## Hidden tabs

Start with the normal `scroll(...)` helper. Chrome on Windows can leave a
mouse-wheel command unanswered when the attached tab is not visible. If that
scroll times out:

1. Call `activate_tab(current_tab())` so Chrome shows the attached tab.
2. Retry the same `scroll(...)` once.
3. Re-read the page or container scroll position before continuing.

The activation is visible to the user, so it is a fallback after a proven
timeout, not the default. If the user has forbidden visible tab changes, stop
and name that exact limitation instead. Do not replace wheel input with custom
`Runtime.evaluate` scrolling or a cross-frame JavaScript walker; those paths
change page semantics and require context the agent does not have.
