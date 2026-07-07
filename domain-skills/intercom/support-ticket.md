# Intercom (app.intercom.com) — filing a support ticket with Intercom itself

How to report a bug / open a ticket with Intercom support from inside the admin app.

## Entry point

- The admin app has Intercom's own messenger for admin support: a dark circular
  launcher pinned to the bottom-right corner of the viewport. Click it to open the
  "Fin" support panel. No URL route for it — it's an overlay widget.
- The messenger identifies the **logged-in admin** (greets them by first name).
  Replies to the conversation are delivered to that admin's messenger AND their
  login email — check who you're logged in as before filing if follow-up routing
  matters.
- The workspace (app) ID is in the inbox URL: `app.intercom.com/a/inbox/<workspace-id>/...`.
  Include it in bug reports.

## Flow

1. Fin (AI agent) answers first. Give it a complete bug report in ONE message:
   steps to reproduce, expected vs actual, workspace ID. It will validate against
   documented behavior — useful confirmation that what you're seeing is a bug.
2. Fin does NOT create a ticket on its own. Explicitly ask it to "escalate this
   conversation to your support team so it is logged as a bug ticket." It then
   hands off: "connecting you with a human agent" → categorizes the conversation
   → confirms team reply time (~4 hours) and the email replies will go to.
3. There's no ticket number surfaced at handoff time — the human team provides
   references later in the same conversation.

## Composer quirks

- The message input is single-line-styled and **sends on Enter**. Type the whole
  message via `type_text()` with no newline characters, then `press_key('Enter')`.
- Fin's longer replies overflow the panel; scroll inside the messenger panel
  (mouse over it) to read the full response before replying.
- Fin responses stream in over ~10-15s with a typing indicator — wait before
  screenshotting or you'll capture a partial reply.
