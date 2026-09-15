# Google Calendar — Sharing & subscribing across accounts

`https://calendar.google.com` — SPA, no iframes, coordinate clicks work everywhere. Covers: share a calendar with a person, subscribe to a calendar you were given access to, Workspace org-wide access.

## URL patterns

- `https://calendar.google.com/calendar/u/<n>/r` — `u/<n>` picks the signed-in Google account. Map `n` → email from the open Gmail tab titles (`mail.google.com/mail/u/<n>` shows the address in the title) before you start.
- `https://calendar.google.com/calendar/u/<n>/r/settings/calendar/<id>` — settings page for one calendar. `<id>` is base64 of the calendar id with `=` padding stripped; the primary calendar's id is the account email:

```python
import base64
cid = base64.b64encode(b"someone@example.com").decode().rstrip("=")
navigate(f"https://calendar.google.com/calendar/u/1/r/settings/calendar/{cid}")
```

- `https://calendar.google.com/calendar/u/<n>/r/settings/addcalendar` — "Subscribe to calendar" page (skips the sidebar `+` menu).

UI language follows each **account's** language setting, not the browser — two accounts in the same Chrome can render pt-BR and en. Layout and order are identical; navigate by structure, not by string matching.

## Share a calendar with a specific person

On the calendar's settings page, scroll to **Shared with** → click **+ Add people and groups** → dialog "Share with specific people".

1. The email input is focused on open. `type_text(email)`; a suggestion list drops directly under the input.
2. Click the suggestion (or `press_key("Enter")`) to commit it as a chip. The Permissions dropdown is hidden under the suggestion list until the chip commits.
3. Permissions dropdown, options in this order (default is the second):
   - See only free/busy (hide details)
   - See all event details
   - Make changes to events
   - Make changes and manage sharing
4. Click **Send**. Toast "Sharing settings saved" at the bottom; the person appears in the Shared with list with a per-row permission dropdown and an `×`.

Suggestion sources differ: a Gmail account suggests from contacts; a Workspace account suggests from the org directory (every domain in the org). Workspace dialogs also show "Some sharing options may have been turned off for your organization by your administrator" — sharing outside the org can be blocked by policy.

## Trap: the shared calendar does not show up on the recipient

After sharing, the recipient's "Other calendars" sidebar does **not** list the calendar right away (a reload does not help; it can lag). Don't wait — subscribe explicitly from the recipient account:

```python
goto("https://calendar.google.com/calendar/u/1/r/settings/addcalendar"); wait_for_load()
click(<Add calendar input>); type_text("sharer@example.com"); wait(2)
click(<first suggestion>)   # navigates straight to /r/settings/calendar/<id> of the new subscription
```

The landing page confirms access under **Permissions settings → You can** (e.g. "See only free/busy (hide details)") and the calendar is now under "Settings for other calendars".

## Workspace org-wide access

Workspace calendars have an extra row under **Access permissions for events**: "Make available for <Org>" with its own dropdown (same option set as above). That is the default access for everyone in the org and is independent of per-person shares — check it before adding people one by one; if it already says "See event details", org members only need to subscribe.

The settings page also shows an **Organization** field (the Workspace primary domain), which may differ from the account's email domain when the org uses domain aliases.

## Booking pages

Sidebar section **Booking pages** (Workspace). A subscribed calendar with only free/busy access is enough for a booking page to treat its events as busy.
