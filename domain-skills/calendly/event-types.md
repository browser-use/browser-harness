# Calendly — event types & availability editing

## URL patterns

- Event types list: `https://calendly.com/app/scheduling/meeting_types/user/me`
- Editor opens as a right-side pane on the same URL (`?pane=event_type_editor&paneState=...`); the pane scrolls independently of the page.
- Public booking page: `https://calendly.com/<slug>/<event-slug>?month=YYYY-MM&date=YYYY-MM-DD` — use the query params to open a specific day's slot list.
- **Trap:** `https://calendly.com/<slug>/<event-slug>/YYYY-MM-DD` is NOT a day view — Calendly parses the path segment as a spot-booking deep link and lands on an "Enter Details" form for 12:00am that date.

## Creating an event type

`+ Create` (top right) → "One-on-one" opens the editor pane with Duration / Location / Availability / Host sections. The `Create` button (bottom right of the pane) saves; a green "Saved" toast confirms.

## Editor pane mechanics

- **Title**: the heading is an `<h2>`; clicking it swaps in a `<textarea>`. React resets `el.select()` immediately, so select-all via JS or Cmd+A modifier bit does NOT work — typed text appends instead of replacing. Use the CDP editing command instead:
  `cdp("Input.dispatchKeyEvent", type="keyDown", key="a", code="KeyA", modifiers=4, windowsVirtualKeyCode=65, commands=["selectAll"])` then `type_text(...)`. Same applies to the time fields.
- **Location**: "All options" dropdown holds Google Meet / Teams / Webex / GoToMeeting / Custom / Ask invitee; Zoom, Phone, In-person are top-level buttons.
- **Date-range**: Availability section → click the "60 days" link → radio "Within a date range" → click the empty range field → two-month calendar; click start day, end day, then `Apply`.
- **Schedule**: `Schedule:` dropdown → "Custom schedule" scopes hours to this event without touching the account's default "Working hours" schedule.
- **Weekly hours rows**: one row per weekday (S M T W T F S top-to-bottom, Sunday first). `×` clears a day to "Unavailable" (remove bottom-up — row heights change). `+` on a day adds another interval (defaults to last interval shifted; each new interval's inputs appear in DOM order under that day).
- **Time fields** are comboboxes: click opens a filtered listbox; typing filters; Enter commits. Reliable non-coordinate pattern: focus the input via JS, then `commands=["selectAll"]` keyDown, `type_text("1:00pm")`, `press_key("Enter")`. Values are validated on commit — a garbled value silently snaps to something weird (saw `11:41pm`), so read back `input.value` after every commit.
  Handy selector: time inputs are the only inputs whose value matches `/am|pm/` — index into `[...document.querySelectorAll('input')].filter(i=>/am|pm/.test(i.value))` in DOM order to address them without coordinates.
- **Timezone trap:** a new custom schedule inherits the *account's* timezone (e.g. Pacific), not the browser's. If the host is in another zone the typed hours silently mean the wrong wall-clock time. The schedule TZ control is the blue "<Zone> Time - US & Canada" button *inside the editor pane* below the weekly hours — the identically-labeled control in the left preview panel only changes the invitee preview display. Distinguish them by `getBoundingClientRect().left` (editor pane sits right of ~1000px at 1505px viewport).
- After edits on a saved event, click `Save changes` (bottom right); "Saved" toast confirms.

## Onboarding noise

Fresh accounts show a "Set up your first event type" coach-mark, a terms banner, and a "Get started" widget — all safe to dismiss; the coach-mark's × must be clicked before elements under it are clickable.
