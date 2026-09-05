# Network Requests

Each event reader keeps its own cursor. Reading does not consume another reader's
history or affect request tracking:

```python
batch = read_events()  # up to 500 retained events
cursor = batch["cursor"]
print(batch["dropped"], batch["events"])
# Later, in this reader; persist cursor yourself across CLI invocations.
batch = read_events(cursor, session_id=None)
cursor = batch["cursor"]
```

`dropped` counts overwritten events since the cursor (across all sessions).
Events larger than 16 KiB retain method/session and set `truncated: true` with
empty params. Check both before drawing conclusions. A daemon restart raises
`EventCursorExpired`; explicitly start a new reader. `drain_events()` retains its
legacy shared-reader behavior, but no longer deletes the retained history.
MCP exposes the same cursor interface as `browser_read_events`.

`wait_for_network_idle()` tracks requests as they arrive, including redirects
and failed loads. It returns `True` after no pending requests and a quiet window,
or `False` on timeout. It raises if the session changes or coverage is unknown.
Coverage requires Network enabled before a top-level navigation. Requests that
started before attachment cannot be reconstructed reliably. After attachment or
recovery, navigate explicitly or use a specific DOM condition instead. Tracking
more than 4096 concurrent requests fails closed; reattach and navigate to reset.

For form submission, verify the actual result in the UI. Network quiet is not
proof that a save succeeded. Do not print headers, cookies, or full event payloads
when a status/method summary answers the question.
