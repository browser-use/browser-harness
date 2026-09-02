# Instagram on marco__lobo

Field guidance for Browser Harness work on the `marco__lobo` Instagram account.
Read [`safety-caps.md`](safety-caps.md) and
[`friction-detection.md`](friction-detection.md) before any write action.

## Scope

Use Instagram first for chef-founder accounts, one-person grid-run marketing
teams, accounts with fewer than 2 LinkedIn marketing contacts, and German
targets. Warm first through follows, likes, and a Story reply. Never place a
link in DM 1 and never unfollow.

No Instagram page, selector, modal, or account state was observed for this
documentation pass. All selector-shaped guidance below is `TO-VERIFY` unless
explicitly marked otherwise.

## Verified harness facts

- **VERIFIED 2026-09-02, Marco's Chrome:** Browser Harness marks the controlled
  tab with a green dot at the start of the title.
- **VERIFIED 2026-09-02:** harness execution scoping hides top-level helper
  definitions from nested calls, so wrap helpers and task steps in one `run()`
  function.
- **VERIFIED 2026-09-02:** retina screenshots are twice the CSS viewport size.
  Click current `getBoundingClientRect()` centres, never screenshot pixels.
- **VERIFIED 2026-09-02:** `WebSocket connection closed` indicates a stale
  daemon and is fixed by one `admin.restart_daemon()` call. Read the tab back
  before resuming.

## URL patterns

| Surface | URL pattern | Status |
|---------|-------------|--------|
| Profile | `https://www.instagram.com/{handle}/` | TO-VERIFY |
| Tagged posts | `https://www.instagram.com/{handle}/tagged/` | TO-VERIFY |
| Direct inbox | `https://www.instagram.com/direct/inbox/` | TO-VERIFY |
| Direct thread | `https://www.instagram.com/direct/t/{id}/` | TO-VERIFY |

Treat any other path or redirect as `TO-VERIFY` and inspect it before acting.

## Harness and selector rules

1. Use one controlled tab and confirm the green dot in its title.
2. Put helper functions and task steps inside one `run()` function because
   harness execution scoping hides top-level definitions from nested calls.
3. Start from a screenshot, find the visible target, click its CSS viewport
   centre, then take another screenshot.
4. Prefer `aria-label`, role, visible text, and stable `href` patterns. Never use
   hashed classes.
5. When DOM location is needed, use a fresh `getBoundingClientRect()` centre.
   Retina screenshots are twice the CSS viewport size, so never click from
   screenshot pixels.
6. `wait_for_load()` misses SPA hydration. Poll for a known visible label or
   semantic anchor. Exact anchors are `TO-VERIFY` on first use.
7. If `WebSocket connection closed` appears, run `admin.restart_daemon()` once
   and read back the tab before continuing.

## Mandatory human navigation path

Use the same path before a profile action or DM:

1. Open Instagram's main feed. Its exact URL is `TO-VERIFY`.
2. Scroll 2 to 4 screens with random pauses.
3. Click the search control by accessible name or visible text and type the
   handle or account name. Search selectors are `TO-VERIFY`.
4. Open the matching result after checking the visible handle and account name.
5. Scroll through the profile and recent posts.
6. Dwell for a random 8 to 25 seconds.
7. Take the planned action.
8. Take and inspect an after-screenshot.

Do not deep-link a target profile for a write action. Type message text in
short chunks with natural pauses.

## Warm-up and Story reply opener

Warm the target across 2 days with a follow and 2 to 4 likes. Never follow and
DM within 15 minutes. Use a relevant Story reply as the preferred opener when a
Story exists. Story ring, viewer, reply box, send control, and sent-state
selectors are `TO-VERIFY`.

DM 1 must be 2 to 3 lines and contain no link. DM 2 may go only after `Seen` or
7 days. DM 3 may include the audit link only after a reply, or after `Seen` plus
a profile visit.

## Direct inbox and Requests reality

Cold DMs may land in `Requests`, not the recipient's main inbox. Business
accounts may expose `Primary`, `General`, and `Requests` tabs. These labels and
their selectors are `TO-VERIFY`, but the workflow must check all available
folders before treating a conversation as absent or unanswered.

On the first `/direct/` open, Instagram may show a notifications modal. This is
a trap, not proof that the inbox failed to load. The modal text, buttons, and
dismiss action are `TO-VERIFY`. Take a screenshot, identify the safe dismiss
choice by visible text, dismiss once, then poll for an inbox label.

## DM composer

1. Open an existing thread from the inbox, or reach the account through the
   mandatory navigation path and use its visible message action.
2. Locate the composer by role, placeholder, accessible name, or
   `contenteditable="true"`. Every composer selector is `TO-VERIFY`.
3. Click and type in chunks. Inspect the exact text before sending.
4. **TO-VERIFY:** Enter may send. Do not press Enter until the live composer
   behaviour is known.
5. Prefer a verified visible Send control.
6. Count the DM only after the outgoing text appears in the right thread and an
   after-screenshot confirms it.

## Likes and follows

Open a post through normal profile browsing. Find Like and Follow by role,
`aria-label`, or visible text. Exact selectors and changed-state labels are
`TO-VERIFY`. Click once and count the action only when the after-screenshot
shows the state changed. Never unfollow, including as a retry or cleanup step.

## Read sweeps

Inbox and Requests reads do not count as writes. Open each available folder,
poll for hydration, and inspect unread threads without focusing or typing into
the composer. Read back `Seen`, reply, and thread state from visible text.
Unread markers, folder tabs, thread rows, timestamps, and pagination are all
`TO-VERIFY`.

## Related files

- [`safety-caps.md`](safety-caps.md): DM caps, timing, sequence, and state
- [`friction-detection.md`](friction-detection.md): action blocks and recovery
