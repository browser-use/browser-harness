# Google Voice - reading threads and sending in EXISTING threads

Verified live 2026-08-05 (send + screenshot proof) and 2026-08-03 (new-recipient failure).

## The one rule that decides automatability

- **Existing thread (any prior message with that number): sending WORKS.** The send
  button enables once text is in the box.
- **New recipient (no thread yet): sending does NOT work.** Send stays
  `disabled=true` no matter what you type. Two materially different approaches
  failed on 2026-08-03. Escalate to manual, do not retry variations.

So check for a thread first; it also tells you which lane you are in.

## Go straight to a thread by phone number

The thread URL is deterministic. `itemId` is `t.` + the E.164 number, URL-encoded:

```text
https://voice.google.com/u/0/messages?itemId=t.%2B15551230100
```

No scroll hunt needed when you know the number. Verify with `location.href` and the
header text ("Messages with <label>") after load; give it ~8-10s, GV is slow.

## Thread list (only needed when you do not know the number)

- Container: `cdk-virtual-scroll-viewport`. Rows: `GV-THREAD-LIST-ITEM` /
  `GV-MESSAGE-THREAD-LIST-ITEM` inside `<li>`.
- The list is VIRTUALIZED: only ~12 rows exist in DOM at once. Loop
  `v.scrollTop += 450-500` via `js()` and re-query each step. JS scroll only,
  never `Input.dispatchMouseEvent` wheel (blocks forever on background tabs).
- Thread label = whatever Google Contacts calls the number, NOT the business name.
  Two 2026-08-03 sends landed under unrelated stale contact labels from the
  account's own address book. Match by number when possible.

## Sending in an existing thread (working recipe)

1. Open the thread by itemId URL (above), wait, verify header.
2. Compose box: the VISIBLE `<textarea>` (aria-label "Type a message"). Click its
   center coordinates to focus, confirm `document.activeElement.tagName === 'TEXTAREA'`.
3. `cdp("Input.insertText", text=MSG)` into the focused box. Then verify
   `document.activeElement.value === MSG` EXACTLY before sending.
4. Click `button[aria-label="Send message"]` via element `.click()` (check
   `disabled` first; enabled means existing-thread lane).
5. Verify with `screenshot()`: the new bubble in the conversation pane AND the
   compose box back to placeholder. DOM text reads are unreliable here (below).

## Traps

- **A second, HIDDEN `<textarea>` holds a ~2.4KB token blob.** "Some textarea has
  content" does NOT mean the compose box is unsent. Scope reads to the visible
  textarea or `activeElement`.
- **`body.innerText` mixes both panes.** "Latest messages" appears in the thread
  LIST pane too, so a marker-based slice can return the list, not the
  conversation. Scope to the conversation pane or trust the screenshot.
- **Fresh bubbles may not appear in smallest-div text heuristics** right after
  send. The screenshot is the ground truth; the sent bubble renders within ~5s.
- Outbound messages read as "You: ..." / "Message from you, ..." in innerText;
  anything else on a thread's latest line is inbound. That is the whole
  reply-detection signal, with one trap: GV stamps 1-6 day-old threads with a
  bare weekday abbreviation ("Mon"/"Tue"), which parses as a fake inbound reply
  unless filtered.
