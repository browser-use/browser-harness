# Cal.com booking reconciliation

- Signed-in booking routes use `https://app.cal.com/bookings/{past,upcoming,cancelled,unconfirmed,recurring}`.
- The booking list reads `/api/trpc/bookings/get?batch=1&input=...`. Discover the current request through resource timing or network capture before replaying it; do not assume the schema remains unchanged.
- The observed input is a tRPC batch object with key `0`, containing `json` with `limit`, `offset`, `cursorMode`, optional `cursor`, and `filters`. Observed filters include `statuses`, `afterStartDate`, `beforeEndDate`, `afterCreatedDate`, and `beforeCreatedDate`.
- An empty statuses array may default to upcoming bookings rather than all bookings. Explicitly request the relevant status buckets. Appointment-date filters and creation-date filters answer different questions.
- The observed response is `[0].result.data.json` with `bookings`, `nextCursor`, `hasMore`, and sometimes `totalCount`. A null total is not zero. In cursor mode, use the returned cursor until `hasMore` is false, and verify unique booking UIDs across pages.
- Booking data includes `responses.email`, `responses.name`, optional booking-form phone fields, and `attendees`. The attendee array can include guests; use the primary booking response for a count of bookers and state whether guests are included.
- The public connector's booking summary may omit attendee emails. The signed-in booking list can supply identity fields for reconciliation; compare UID coverage between both sources.
- Repeat and rescheduled bookings are not distinct leads. Deduplicate normalized email, then investigate alternate emails with name and phone evidence. A shared practice phone alone does not prove two people are the same.
- Keep cancellation status, internal/test records, and ambiguous identities visible in the counting method. `ACCEPTED` does not prove attendance.

Use authenticated same-origin reads. Never copy cookies, tokens, meeting passwords, or account-specific records into documentation.
