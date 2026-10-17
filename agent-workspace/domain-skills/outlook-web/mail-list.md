# Outlook on the web (outlook.live.com / outlook.office.com) — reading a folder's messages

## Trap: request hooks see nothing
OWA fetches mail through a web worker/service worker. Wrapping `window.fetch` / `XMLHttpRequest` in the page (even via `Page.addScriptToEvaluateOnNewDocument`) captures zero list calls. Don't spend rounds on it.

## What works: the virtualised list's aria-labels
Each message row is `[role=option]` and its `aria-label` carries: read state, sender, subject, **date/time as OWA displays it** (`Sat 23:52` for the last week, `dd/mm/yyyy` older), and the preview text (first ~300 chars of the body). For notification emails (payment confirmations, receipts) the preview usually contains every field you need, so no message has to be opened.

- Folder pane: `[role=treeitem]`, text = folder name + unread count. Locate by regex on `textContent`, `scrollIntoView`, then `click_at_xy` on its rect (a real click; JS `.click()` does not switch folders).
- The list is virtualised. Find the scroller as the element with `scrollHeight > clientHeight` that contains `[role=option]`; step `scrollTop += 0.8 * clientHeight`, wait ~500 ms, collect `aria-label`s keyed by `data-convid`, until the bottom. 66 items ≈ 6 steps.
- Times are minute precision, in the mailbox's display timezone. Older than ~7 days you get a date only; the reading-pane header shows the full `Sat 19/09/2026 23:52`.

## Attaching
Filter targets with `t["type"] == "page"`; the same URL also appears as a worker target and `js()` there fails with `window is not defined`.

## Seconds-precision timestamps: "View message source"
The list and reading pane show minutes only. Raw headers (with `Date:` to the second) come from **View message source**, which on outlook.com is hidden until enabled: open a message → `More items` (the message-header `...`) → `Customise actions` → tick "View message source" (also "Download as EML") → Save. It then appears as an **icon button with `aria-label="View message source"`** in the message header, not as a menu item. Click it, read `[role=dialog]` innerText, regex `^Date: (.*)$`, `Escape`. ~6 s per message; 66 messages ≈ 7 min in one loop. The list is virtualised — start with `scrollTop = 0` and step down; skip rows already done (key on a body field from the aria-label preview).
OWA's `service.svc` cannot be replayed from page context: the canary is httpOnly and the app authenticates with an MSAL bearer token → 401.
