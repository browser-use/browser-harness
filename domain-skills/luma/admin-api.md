# Luma (luma.com) — calendar admin & guest lists

Event platform. Public event pages scrape fine; anything admin (guest lists with
emails, full event management) needs the **internal cookie-authed API** described here.
The official API (`public-api.luma.com`, `x-luma-api-key` header) requires a paid
Luma Plus subscription per calendar — the internal API below works with any
logged-in host session.

## Internal API: `https://api.luma.com`

Cookie auth with SameSite cookies, so **fetches must run from a luma.com page
context** — `js("fetch(...)", ...)` from any other origin returns 400. Ensure a
luma.com tab first:

```python
if "luma.com" not in (page_info().get("url") or ""):
    tabs = [t for t in list_tabs(include_chrome=False) if "luma.com" in t["url"]]
    switch_tab(tabs[0]["targetId"]) if tabs else (new_tab("https://luma.com/home"), wait_for_load())
```

A 400 right after opening/navigating the tab can also just be the page still
settling — wait ~3s and retry once before concluding auth is broken.

### List a calendar's events

```
GET /calendar/admin/get-events?calendar_api_id=cal-XXXX&pagination_limit=20&period=past
```

- `period` is `past` or `future`. **`upcoming` is invalid and returns 400** (easy trap).
- Returns `{entries: [{api_id: "calev-...", event: {api_id: "evt-...", name, start_at,
  end_at, url, geo_address_info, ...}, guest_count}], has_more, next_cursor}`.
- Paginate with `&pagination_cursor=<next_cursor>`.
- Calendar id is in the manage URL: `luma.com/calendar/manage/cal-XXXX`.

### Full guest list with emails (host only)

```
GET /event/admin/get-guests?event_api_id=evt-XXXX&pagination_limit=100
```

- Returns `{entries: [...], has_more, next_cursor}`; paginate with `pagination_cursor`.
- Each guest: `name`, `email`, `approval_status`, `registered_at`, `checked_in_at`,
  `registration_answers`, social handles, `user_api_id`.
- **`approval_status` semantics:** `approved` / `going` = actually registered;
  `invited` = host sent an invite, never registered (these dominate the list —
  a 24-guest event can return 238 rows, 210 of them `invited`); `declined` = declined.
  Filter on status or your "guest list" will be 10x the real size.
- `checked_in_at` is null unless the host scanned people in — for casual events,
  registered ≠ attended.

## Traps

- The event page UI count ("24 guests") = approved only, not the raw entries count.
- Email notifications to hosts (`noreply@luma-mail.com`) contain per-guest
  register/cancel updates — usable as a fallback data source but not complete.
- CSV export exists at Manage Event → Guests → ⋯ → Download if you only need a
  one-off list and don't want the API.
