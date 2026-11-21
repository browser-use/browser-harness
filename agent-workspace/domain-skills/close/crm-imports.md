# Close: authenticated CRM imports

Prefer a working connector or API key. The logged-in `app.close.com` tab can call the same-origin `/api/v1/` REST API when a connector cannot return valid responses.

## Request shape

- GET requests need `organization_id` in the query string.
- POST/PUT requests need `organization_id` in the JSON body; a query parameter alone did not satisfy creation requests.
- Read the `_csrf_token` cookie inside the page, decode it, and pass it as `X-CSRFToken`. Never print or export cookies.
- Use an explicit CDP session for the existing Close tab when another site is attached as the default harness tab.
- Existing tabs can cache pipeline/status metadata. If a correctly assigned opportunity renders “Select status,” reload the page and verify the label before changing any records.
- Read existing pipelines, statuses, fields and records before creating them. Journal returned IDs and reconcile an interrupted request before retrying.

## Historical email imports

`POST /api/v1/activity/email/` with `status: "inbox"` logs received mail; `status: "sent"` logs already sent mail. `outbox` and `scheduled` initiate sending and are inappropriate for historical imports.

Observed creation behavior for `sent`: `date_sent` and the returned `activity_at` were derived from `date_created`, overriding a different supplied `activity_at`. Set `date_created` to the original send timestamp when preserving sent-mail chronology; retain the source CRM record-creation timestamp separately. Read back all three timestamps. Updating `activity_at` afterward changes the timeline date but leaves `date_sent` unchanged.

`message_ids` was returned but ignored when supplied on creation. `date_sent` was also ignored on update. Do not claim those read-only fields were preserved natively; retain original message IDs and source metadata in an archive. Match existing synced mail by message ID when available, with exact sender/recipient/subject/timestamp matching as a fallback. Never deduplicate on subject alone.

While email sync is active, a previously imported activity ID can become unavailable while a matching RFC message remains under another ID. Reconcile against current messages on the expected lead before recreating anything. Verify identity and content before removing only migration-created duplicates, and retain exact source attachment versions when synced files have different names or sizes.

Received emails require a sender. When the source lacks one, do not invent it: preserve the message as an explicitly labeled historical note, including recipients, content, source ID, date and attachments.

## Notes and files

Note rich text is restricted XHTML. `<body>` cannot directly contain non-whitespace text or inline elements; wrap them in a paragraph. Arbitrary source HTML must be normalized, with the original retained separately. Treat plain meeting text as text: angle-bracketed URLs can otherwise be parsed as unknown tags. Use an HTML-aware parser to repair malformed nesting and ensure void elements such as `br` have no child content.

For files:

1. POST `files/upload/` with filename and content type.
2. Immediately submit the returned form fields and file bytes as multipart data to `upload.url`; a successful upload returns 201.
3. Use `download.url` in an activity attachment or POST it to `lead/{lead_id}/files/` with filename and content type.
4. Verify the resulting persisted attachment, not merely the temporary upload response.

Email attachments use `url`, `filename`, `content_type` and `size`. Archive source property histories when they cannot be represented by editable Close fields.

## Browser payload size

The harness's newline-delimited IPC reader may reject a large `Runtime.evaluate` request near its default stream limit. For large email bodies, initialize a task-specific string in the page, append small JSON-escaped chunks through separate CDP calls, then perform one fetch using the assembled body. A broken pipe is an unknown outcome until the target record is checked; never blindly repeat a create request.
