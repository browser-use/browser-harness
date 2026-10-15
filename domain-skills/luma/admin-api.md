# Luma (luma.com) — internal admin API

Luma's event-admin UI is a thin client over `https://api.luma.com`. With a
logged-in Chrome session you can do everything the Manage Event pages do via
`fetch` — 10× faster than driving the dashboard DOM.

## Auth model

- Cookie auth with SameSite: **requests must run from a luma.com page context**
  (`js("fetch('https://api.luma.com/...',{credentials:'include'})...")`).
  A tab on any luma.com URL works; open `https://luma.com/home` if none exists.
- No official API on free accounts. (Luma Plus has a public API at
  `public-api.luma.com` with `x-luma-api-key` — different surface.)
- A 4xx right after opening the tab is usually the page still settling, not an
  auth failure. Wait ~3s and retry once before concluding you're logged out.

## Endpoints (introspected from the dashboard's own calls)

- `GET calendar/admin/get-events?calendar_api_id=cal-XXX&pagination_limit=20&period=future`
  — events for a calendar you admin. `period` is `past` / `future` (not
  `upcoming`). Entries wrap the event: `{event: {...}, guest_count}`.
- `GET event/admin/get-guests?event_api_id=evt-XXX&pagination_limit=100`
  — guest list incl. invited-but-unregistered. Paginate with `has_more` +
  `next_cursor` → `&pagination_cursor=...`. Guest fields: `email`, `name`,
  `approval_status` (`invited` / `approved` / `going` / `declined`),
  `invited_at`, `registered_at`, `checked_in_at`, `registration_answers`.
- `POST event/admin/invite/send` — send email invites. JSON body:
  `{"event_api_id": "evt-XXX", "message": "", "people": [{"type": "email", "email": "a@b.com"}, ...]}`.
  Accepts hundreds of people per call.

## Invite capacity (the trap)

- Invites are capped per account. The Invite Guests dialog header shows the
  live budget (`N LEFT`); it replenishes over time (observed: exhausted → back
  at 500 two weeks later). There is no visible counter outside the dialog.
- The dialog silently selects at most capacity−1 of a pasted list (pasted 500
  with "500 LEFT", got "499 Selected" — observed twice on different days).
- Luma silently drops invalid/undeliverable addresses from a send — no error,
  no per-address feedback. **Always reconcile after sending**: re-pull
  `get-guests`, diff emails against your batch, and treat the diff as the
  true landed count.
- Already-invited and already-registered addresses are deduped by Luma, but
  they may still consume selection slots — remove them from your batch first
  (via `get-guests`) when capacity is scarce.

## Invite dialog (UI fallback)

Manage Event → Guests → Invite Guests → **Enter Emails** tab: paste a
comma-separated list into the "Paste or enter emails here" input (one
`type_text()` of the whole string works, 500 emails fine) → Add → Next →
Send Invites. The send runs async (button spinner) — wait ~10s, then verify
via `get-guests`, not the dialog.

## Misc

- Event manage URLs: `https://luma.com/event/manage/evt-XXX/guests` (also
  `/overview`, `/registration`, `/blasts`, `/insights`).
- Public event URL slug lives in `event.url` (e.g. `https://luma.com/vzqyfjzw`).
- CSV import exists next to Enter Emails if you'd rather upload a file.
