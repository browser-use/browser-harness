# X — direct-message reply batches (field-tested Jul 2026)

## Routes and stable selectors

Accepted conversations use `https://x.com/i/chat/<participant-ids>`. Message
requests use `https://x.com/i/chat/requests/<participant-ids>`.

| Purpose | Selector / signal |
| --- | --- |
| Conversation is ready | `[data-testid="dm-conversation-panel"]` |
| Displayed participant | `[data-testid="dm-conversation-username"]` |
| Composer | `[data-testid="dm-composer-textarea"]` |
| Send button | `[data-testid="dm-composer-send-button"]` |
| Accept request | `[data-testid="dm-message-request-accept-button"]` |
| Message wrappers | `[data-testid^="message-"]`, excluding `message-text-*` |

Message direction is visible on the outer wrapper: sent messages have
`justify-end`; received messages have `justify-start`.

## Authentication

Try the harness before opening a fresh Chrome window. Its dedicated automation
profile may already contain the usable X session even when a newly opened
Default-profile window redirects to login.

```python
new_tab("https://x.com/i/chat/<participant-ids>")
wait_for_load()
wait_for_element('[data-testid="dm-conversation-panel"]', timeout=8)
print(page_info())
```

If `page_info()["url"]` contains `/login` or `onboarding`, stop and ask the user
to sign in. Do not type credentials recovered from the page or machine.

## Read the thread without the timestamp trap

X puts the visible time inside the same message wrapper as the message text,
often twice. A message that looks like `Thanks` in the UI may read as
`Thanks\n8:39 PM\n8:39 PM` through `innerText`.

Do not use equality for duplicate detection or send verification. Normalize
whitespace, then test whether the draft is contained in an outgoing wrapper.

```python
import json
import re


def normalize(value):
    return re.sub(r"\s+", " ", value or "").strip()


def thread_snapshot():
    raw = js(
        """JSON.stringify((()=>{
          const messages=[...document.querySelectorAll('[data-testid^="message-"]')]
            .filter(e=>!e.dataset.testid.startsWith('message-text-'))
            .map(e=>({
              direction:e.className.includes('justify-end')?'out':'in',
              text:(e.innerText||e.textContent||'').trim()
            }));
          return {
            href:location.href,
            name:(document.querySelector('[data-testid="dm-conversation-username"]')?.innerText||'').trim(),
            hasComposer:!!document.querySelector('[data-testid="dm-composer-textarea"]'),
            messages
          };
        })())"""
    )
    return json.loads(raw or "{}")


draft = normalize(draft_text)
outgoing = [
    normalize(message["text"])
    for message in thread_snapshot().get("messages", [])
    if message["direction"] == "out"
]
already_sent = any(draft in message for message in outgoing)
```

Exact equality caused a duplicate acknowledgement in the field. Treat
substring containment here as a hard safety rule.

## Accept a request only when a reply is due

A request route has no composer until it is accepted. Do not bulk-accept every
request. Accept only the rows the reply plan marks for sending.

```python
snapshot = thread_snapshot()
if not snapshot.get("hasComposer"):
    accept = query_deep('[data-testid="dm-message-request-accept-button"]')
    if accept:
        click(accept["x"], accept["y"])
        wait_for_element('[data-testid="dm-composer-textarea"]', timeout=8)
        snapshot = thread_snapshot()

if not snapshot.get("hasComposer"):
    raise RuntimeError("conversation has no composer")
```

## Compose, send, verify

Focus the textarea, insert text through CDP, and confirm the textarea value
before clicking Send. The send button appears only after the composer contains
text.

```python
import time

js("document.querySelector('[data-testid=dm-composer-textarea]').focus()")
type_text(draft_text)
wait(0.35)

composed = normalize(
    js("document.querySelector('[data-testid=dm-composer-textarea]').value") or ""
)
if composed != normalize(draft_text):
    raise RuntimeError(f"composer mismatch: {composed!r}")

send = query_deep('[data-testid="dm-composer-send-button"]')
if not send:
    raise RuntimeError("send button unavailable after composing")
click(send["x"], send["y"])

deadline = time.time() + 12
while time.time() < deadline:
    outgoing = [
        normalize(message["text"])
        for message in thread_snapshot().get("messages", [])
        if message["direction"] == "out"
    ]
    if any(normalize(draft_text) in message for message in outgoing):
        break
    time.sleep(0.4)
else:
    raise RuntimeError("sent message was not verified in the thread")
```

## Batch discipline

- Run one pilot, inspect its screenshot, then continue.
- Use batches of 5–10 so a selector or rate-limit failure cannot affect the
  whole queue.
- Persist one result per candidate after every attempt. Make reruns idempotent
  by checking for the exact draft substring before composing.
- Keep no-reply and other-channel rows outside the send list. A row in a sheet
  is not permission to accept or message its request.
- Stop the batch on authentication redirects. Log missing composers and other
  failures instead of improvising a different message.
- Verify the final sent count from the threads, then update the tracker. Do not
  infer success from an empty composer alone.

