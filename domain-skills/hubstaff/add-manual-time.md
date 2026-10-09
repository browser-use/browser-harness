# Hubstaff — add manual time entry (UI)

The Hubstaff **v2 API cannot create time entries** (it's an unshipped roadmap
request; the only write path, `custom_activities`, needs a custom-activity
integration and records "custom activity", not manual timesheet entries). So
backfilling billable hours must go through the web UI.

## Route

`https://app.hubstaff.com/organizations/{ORG_ID}/time_entries/calendar`
Reached via left nav **Timesheets → View & edit**. Has Daily / Weekly /
**Calendar** view toggle. The calendar renders in the org's display timezone
(shown next to the date range, e.g. "AEST") — entries are created in that tz.

Filter to a person via the member picker (top-right, shows the selected name);
the URL carries `filters[user]={user_id}`.

## Add-time dialog (button top-right: "Add time")

Fields, in order:
- **Work break** toggle (leave off for normal time)
- **PROJECT\*** — searchable dropdown. Click, type to filter, click the option.
- **TO-DO\*** — appears/becomes **required only after a project is selected**,
  and the required tasks are project-specific (e.g. Transdirect exposes
  "Client Support", "Maintenance", "Meetings", plus MOD-* task IDs). You cannot
  save without it. There is no generic "no task" option — the caller must know
  which task the time belongs to.
- **TIME SPAN (AEST)\*** — a date field (opens a month picker; prev-month days
  appear greyed at the top row and ARE selectable) plus **FROM** and **TO**
  time fields. A slider under them mirrors From/To and shows the duration
  (e.g. "4:47:00"). Duration = To − From.
- **Billable** checkbox — checked by default; billable time generates the $
  amounts on the dashboard.
- **REASON\*** — dropdown ("Why are you adding this time entry?"), becomes
  required for manual admin-added time.
- **Add note** — optional.
- Cancel / **Save**.

## Setting the FROM/TO time fields (finicky — this recipe works)

The time inputs are masked (`input.default-input`, values like `8:00`) with a
SEPARATE am/pm toggle rendered as the "am"/"pm" text beside each field. Naive
typing corrupts them. Reliable recipe:

- **Never use Tab to blur** — a `Tab` keypress inserts a literal tab char into
  the next field (the duration `input.input-default`) and corrupts the widget,
  which then reverts TO back to FROM on recompute. Blur by CLICKING a neutral
  spot instead (e.g. the Billable label area).
- **To clear a field**: triple-click it (selects all), then type the new value.
  Cmd/Ctrl+A does NOT select inside these fields.
- **am/pm resets the minutes.** Clicking the "am"/"pm" toggle resets that field
  to `9:00`. So set am/pm FIRST, THEN triple-click + type the minutes.
- Full sequence for e.g. TO = 1:47 pm: click the am/pm toggle (→ `9:00 pm`),
  then triple-click the TO field, type `1:47`, then click to blur.
- Read back state via JS to confirm before saving:
  `[...document.querySelectorAll('input.default-input')].map(e=>e.value)` gives
  `[hiddenFrom, hiddenTo, FROM, TO]` (first two belong to a hidden dialog
  instance — the active ones are indices 2 and 3); the duration is
  `input.input-default` (second one). A "Next day" tooltip on TO + a huge
  duration means TO is still am when you meant pm.

## Overlap constraint & finding gaps

Existing tracked entries are "locked" — a new manual block that overlaps ANY of
them shows "This time entry overlaps with a locked time entry and cannot be
saved" and Save is blocked. So each backfill block must fit entirely inside a
free gap. The dialog's slider renders the selected day's occupied windows;
`overlap:false` can be checked via
`document.body.textContent.includes('overlaps with a locked')`. Watch for
zero-width entries (e.g. `12:12 pm - 12:12 pm`) mid-day that still block a range.
A day already fragmented by many small entries may have NO gap large enough for a
big block — you then have to split across gaps (a decision worth confirming with
the user, since placement is visible on client-billed timesheets).

## Traps

- **Pressing Escape inside the dialog resets the whole form** (clears project,
  jumps the date/time) rather than closing it — don't use Escape to dismiss a
  dropdown. Click elsewhere to close a dropdown; use the **X** (top-right) or
  **Cancel** to close the dialog.
- An NPS/"recommend Hubstaff" survey can pop up bottom-right and overlap the
  Save button — dismiss its X first.
- Viewport here is 1800 CSS px wide; screenshots are 2× (3600). Map click
  coords accordingly.
- Because TO-DO and REASON are mandatory and task attribution on billable
  client time is a human decision, don't guess them — confirm with the user
  before saving.

## Reopening the dialog for a second entry (field state is NOT reset)

When you click **Add time** again in the same page session, the dialog does not
reliably return to its `8:00 am` / `9:00 am` defaults — it can come back carrying
the **previously saved entry's FROM/TO values and am/pm state**. Never assume the
defaults. Read the state back first and branch on what you actually find:

```js
JSON.stringify({
  t: [...document.querySelectorAll('input.default-input')].map(e => e.value),   // [hidden, hidden, FROM, TO]
  a: (() => { const a = []; document.querySelectorAll('*').forEach(e => {
        if (!e.children.length) { const x = (e.textContent || '').trim();
          if (x === 'am' || x === 'pm') { const b = e.getBoundingClientRect(); if (b.width > 0) a.push(x); } } });
      return a; })(),                                                            // [FROM ampm, TO ampm]
  dur: [...document.querySelectorAll('input.input-default')].map(e => e.value),  // [_, duration]
  overlap: document.body.textContent.includes('overlaps with a locked'),
})
```

## The triple-click + type recipe silently fails maybe 1 in 3 times

Setting a time field can land a value that is neither the old one nor the one you
typed (observed: typing `8:30` produced `9:41`; typing `7:15` left the field on the
previous entry's `3:15`). There is no error — the widget just holds a wrong value.

**Treat every time-field write as write-then-verify-then-retry.** Read back the
`input.default-input` values and the computed duration after each edit; if either
is wrong, triple-click and retype the same field. The retry succeeds reliably.
Verifying only at the end is not enough, because a wrong FROM changes how a later
TO edit recomputes.

Ordering that worked consistently: set am/pm first (it resets that field to
`9:00`), then triple-click + type the minutes, then blur by clicking a neutral
spot, then read back.

## Save is async — the DOM lags the write

After clicking **Save**, the `Total:` header and the day columns take a second or
two to re-render. Reading them immediately shows the *pre-save* state and looks
exactly like a failed save. Wait ~4-6s and re-read before concluding anything, and
prefer a screenshot over a text read when in doubt.

Per-day entry list, useful for confirming what actually landed:

```js
document.querySelector('.fc-day-mon .fc-timegrid-col-events').innerText   // fc-day-tue, -wed, ...
```

The week `Total:` is the cheapest check that a save committed: it should move by
exactly the duration you added (allow for a *running* tracker quietly growing a
live entry by a few minutes while you work).

## Reason values available

`Forgot to start/stop timer`, `Used a wrong task/project`, `Was AFK on a call`,
`Other`. Pick the one that is actually true — these are visible on client-billed
timesheets.
