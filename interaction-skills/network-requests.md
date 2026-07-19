# Network Requests

`network_events()` reads the active tab's dedicated Network event ring without
consuming it. `wait_for_network_idle()` uses the same ring, so waiting no longer
destroys evidence needed afterward.

Capture a cursor before an action, then inspect only new events:

```python
cursor = network_events()["next_seq"]
click_backend_node(button_backend_id)
wait_for_network_idle(timeout=15)
batch = network_events(since=cursor)
for event in batch["events"]:
    if event["method"] in {"Network.requestWillBeSent", "Network.responseReceived"}:
        print(event)
```

The result includes `next_seq`, `dropped`, and `truncated`. Increase `limit` for
targeted debugging; keep printed output bounded. Raw CDP remains available for
request bodies and response bodies.

For public stateless data, prefer the runtime's native retrieval tool. Use an
in-renderer fetch only for data that requires the current browser origin,
cookies, or authenticated session:

```python
result = js("""
(async () => {
  const response = await fetch('/api/data', {credentials: 'include'});
  return {status: response.status, type: response.headers.get('content-type'), text: (await response.text()).slice(0, 5000)};
})()
""")
print(result)
```

Use `method`, `headers`, and `body` in the fetch options for POST downloads or
API calls. Save large or binary results as artifacts in bounded chunks instead
of printing them into the model context.
