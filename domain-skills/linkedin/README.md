# LinkedIn on Marco's account

Field notes for Browser Harness work on Marco's real LinkedIn account. Read
[`safety-caps.md`](safety-caps.md) and
[`friction-detection.md`](friction-detection.md) before any write action.

## Scope and account facts

- **VERIFIED 2026-09-02, Marco's Chrome:** Marco's profile is
  `https://www.linkedin.com/in/lobomarco/`.
- **VERIFIED 2026-09-02, Marco's Chrome:** the account is free and has no
  Premium. `Try Premium` appears in the main navigation.
- **VERIFIED 2026-09-02, Marco's Chrome:** `/feed/` loads without friction.
- **VERIFIED 2026-09-02, Marco's Chrome:** Browser Harness marks the tab it
  controls with a green dot at the start of the title.

This skill covers normal navigation, profile viewing, connection requests,
messages, feed reactions, comments, invitation withdrawal, inbox reading, and
company follows. It does not permit credentials, challenge handling, Premium
features, or action counts above [`safety-caps.md`](safety-caps.md).

## URL patterns

| Surface | URL pattern | Status |
|---------|-------------|--------|
| Feed | `https://www.linkedin.com/feed/` | VERIFIED 2026-09-02 |
| Marco's profile | `https://www.linkedin.com/in/lobomarco/` | VERIFIED 2026-09-02 |
| Member profile | `https://www.linkedin.com/in/{public-identifier}/` | TO-VERIFY before relying on it |
| Search results | `https://www.linkedin.com/search/results/{type}/?keywords={query}` | TO-VERIFY |
| Network growth | `https://www.linkedin.com/mynetwork/grow/` | VERIFIED 2026-09-02 |
| Sent invitations | `https://www.linkedin.com/mynetwork/invitation-manager/sent/` | VERIFIED 2026-09-02 |
| Messaging inbox | `https://www.linkedin.com/messaging/` | TO-VERIFY |
| Conversation | `https://www.linkedin.com/messaging/thread/{id}/` | TO-VERIFY |
| Company page | `https://www.linkedin.com/company/{slug}/` | TO-VERIFY |

Treat route variants and query parameters not listed as `TO-VERIFY` until a
live, friction-free page confirms them.

## Harness rules

1. Use one controlled tab and the default `BU_NAME` for Marco's Chrome.
2. Put all helper functions and the task body inside one `run()` function.
   **VERIFIED 2026-09-02:** harness execution scoping hides top-level
   definitions from nested calls.
3. Start with `screenshot()`. Use the image to understand the page, then locate
   the visible control and click its current CSS viewport centre.
4. Prefer semantic discovery in this order: `aria-label`, role, visible text,
   then stable `href` patterns. Never use hashed classes.
5. Use `getBoundingClientRect()` immediately before a click when DOM discovery
   is needed. **VERIFIED 2026-09-02:** retina screenshots are twice the CSS
   viewport size, so screenshot pixels are not valid `click()` coordinates.
6. Take a screenshot after every meaningful action and confirm the expected
   visible state before counting the action.
7. `wait_for_load()` only covers document readiness. LinkedIn is a SPA, so poll
   for known visible text or a semantic anchor after navigation and menu opens.
   The exact anchor for each surface is `TO-VERIFY` on first use.
8. If the harness returns `WebSocket connection closed`, treat the daemon as
   stale. **VERIFIED 2026-09-02:** one `admin.restart_daemon()` fixes this
   state. Resume only after page and account state are read back.

## Mandatory human navigation path

Use this path for profile actions, including connects and messages:

1. Open the feed.
2. Scroll 2 to 4 screens with random pauses.
3. Click the search control found by visible text or `aria-label`, then type the
   person's name as input. Search selectors are `TO-VERIFY`.
4. Open the matching result after checking the visible name and role or company.
5. On the profile, scroll to Experience.
6. Dwell for a random 8 to 25 seconds.
7. Take the planned action.
8. Take and inspect an after-screenshot.

Never deep-link a target profile for an action. Type searches as a person would.
For messages, type in short chunks with natural pauses. Defer if Marco already
has LinkedIn open, if the IP changed, or if any other automation controls the
same Chrome session.

## Connect flow

1. Complete the mandatory navigation path.
2. Look for a visible `Connect` button by accessible name or visible text.
3. If it is absent, open `More` and look for `Connect` in the menu. The exact
   menu and button selectors are `TO-VERIFY`.
4. Click by the current bounding-rectangle centre and inspect the modal.
5. For a bare request, use the visible send-without-note action. Its exact label
   and selector are `TO-VERIFY`.
6. For an approved note recipient, choose `Add a note`, read the visible
   character counter, and record the current free-account quota before typing.
   The counter, limit, and send selector are `TO-VERIFY` until read from the
   modal on first use.
7. Send only when the caps and note budget allow it. Verify the modal closes and
   the profile shows a pending state before recording the write.

`Connect` often lives under `More`; absence from the profile's first button row
does not mean the action is unavailable.

## Message flow

1. Reach the person through the mandatory navigation path or open an existing
   thread from the inbox.
2. Find the composer by role, accessible name, visible placeholder, or
   `contenteditable="true"`. All LinkedIn composer selectors are `TO-VERIFY`.
3. Click the composer, type in chunks, and inspect the text before sending.
4. **TO-VERIFY:** Enter may send instead of adding a line. Do not press Enter
   until the live composer behaviour and send control have been confirmed.
5. Prefer the visible Send control once verified. Count the write only after the
   outgoing text appears in the thread and an after-screenshot confirms it.

## Like and comment flow

1. Reach the post through normal feed browsing or typed search.
2. Confirm the target post by visible author and post text.
3. Find Like by role, `aria-label`, or visible text. Selector is `TO-VERIFY`.
4. Click once and confirm the control changes state before counting the like.
5. For a comment, find the visible comment control and composer. Selectors are
   `TO-VERIFY`.
6. Type a comment of at least 12 words in chunks. Inspect it before submission.
7. **TO-VERIFY:** Enter may submit the comment. Use the visible submit control
   only after its behaviour is confirmed.
8. Confirm the comment appears under the correct post and save an
   after-screenshot.

## Withdraw old sent invitations

- **VERIFIED 2026-09-02, Marco's Chrome:** the sent manager is
  `/mynetwork/invitation-manager/sent/`.
- **VERIFIED 2026-09-02, Marco's Chrome:** its body renders `People (N)` and
  rows shaped as `Name | headline | Sent X ago | Withdraw`.
- **VERIFIED 2026-09-02, Marco's Chrome:** it showed 61 pending invitations on
  2026-09-02.

For each withdrawal, read the name and age from the same visible row. Only
withdraw requests older than 21 days, never more than 5 per day. Find the row
and its `Withdraw` control by visible text or role. Exact selectors and any
confirmation dialog are `TO-VERIFY`. Confirm the row disappears or its state
changes before updating the authoritative counter.

## Read the inbox

Inbox reads do not count as writes. Open the messaging route, wait for a known
inbox label to hydrate, and inspect Primary and unread conversations by visible
text and roles. The tab labels, thread anchors, unread markers, and pagination
behaviour are all `TO-VERIFY`. Do not type in a composer during a read sweep.

## Follow a company page

Reach the company through typed search, open the matching result, and confirm
the visible company name. Find `Follow` by accessible name or visible text.
Exact selectors and the followed-state label are `TO-VERIFY`. Click once, take
an after-screenshot, and count the action only if the control visibly changes.

## Related files

- [`safety-caps.md`](safety-caps.md): caps, pacing, governors, and counter state
- [`friction-detection.md`](friction-detection.md): stop signals and halt ladder

