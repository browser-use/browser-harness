# Timely (app.gettimely.com) — Messages: SMS inbox + Sent messages

Server-rendered ASP.NET MVC (jQuery). No JSON API for messages, but there is an
HTML-fragment paging endpoint that is far faster than scrolling the UI.

## URLs

- `/message` — SMS inbox (received SMS). Same as `/Message?messageTypeId=2`.
- `/message?messagetypeid=1` — Sent messages (SMS + email).
- `/message/getNextPageMessage?messageTypeId=<1|2>&page=<n>` — **the paging endpoint.**
  Returns a bare `<tr>…</tr>` HTML fragment (100 rows per page, ~93 pages for a
  year of sent traffic). The last row is `<tr class="view-more">` whose
  `<button data-href="…page=n+1">` points at the next page; when that row is
  absent you are done. Page 1 of this endpoint is the same as the initial list.
- `/message/EmailFrame/<id>` — body of a sent email.
- `/Message/AdhocContactCustomer/<customerId>?messagetypeid=2` — "Send reply" modal.
- `/Customer/Customers/<customerId>`, `/Calendar/BookingGroupEdit/<bookingGroupId>` — links in rows.

Query params like `?page=2` / `?skip=` on `/message` itself are ignored (always
returns the first 100). Only `getNextPageMessage` pages.

## Row shape

Each `tr.table-card` has `td[data-label=…]` cells, so parse by label, not column index:

- Inbox: `Date/time`, `Customer`, `Booking`, `Received from` (E.164 digits, no +), `Message`, `Action taken`, `Reply`. `tr.unread` marks unread. Checkbox value is `<messageId>-sms`.
- Sent: `Date/time`, `Customer`, `Booking`, `Destination`, `Type`, `Message`, `Status`. Checkbox value is `<id>-sms` or `<id>-email`; `i[title]` is `SMS message` or `Email`.
- `Type` values seen: `Marketing`, `Appointment reminder SMS`, `Ad hoc SMS`, `Appointment confirmed email`, `Appointment reminder email`, `Appointment amendment email`, `Customer follow-up email v1/v2`, `Appointment cancelled email`, `Invoice copy`, `Ad hoc email`, `Consultation email`, `Appointment pencilled-in email`.
- `Status` values: `Sent`, `Sent as 2 SMS`, `Error`, `Invalid`, and `Not sent` — **`Date/time` is the literal string `Not sent` for those rows**, so guard your date parser.
- Dates are `9 Nov 2026 11:37` (`%d %b %Y %H:%M`) in the account's local time.

## Fetching

Run `fetch(url, {credentials:'include'})` from inside the logged-in tab via `js(...)`
and parse with `DOMParser` (wrap the fragment in `<table><tbody>`). Fetching the
page's own script bundles from inside the page fails with `Failed to fetch`
(CORS/CSP); use `curl` for those if you need to read them.

## Traps

- Inbox only shows received SMS that are not archived; archived replies do not
  appear anywhere in this UI. Reply-rate numbers are therefore a floor.
- Retention appears to be ~13 months of rows (oldest row ≈ 13 months back on
  both lists).
- Other mutating endpoints on the page (`/Message/SetToReadUnreadMessages`,
  `/Message/ArchiveReceivedSms`, `/Message/ResendMessages`,
  `/Message/StopAllPendingMessages`) are POST JSON `{ids:[…], businessId}`.
