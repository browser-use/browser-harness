# Downloads

Use `browser_fetch_to_file(url, path)` when a download requires the current
page's authentication, origin, or anti-bot state. It performs an in-renderer
`fetch(..., {credentials: 'include'})`, waits internally, and transfers the
response in bounded chunks. It accepts `method`, `headers`, `body`, and
`timeout`; a dict/list body is JSON-encoded automatically. Direct
`http_get(...)` is appropriate only when the resource is genuinely public and
does not depend on browser state.

For a normal browser-triggered download, capture the network cursor before the
click, perform the click, wait once, then inspect `network_events(since=cursor)`
for the request/response that proves the action started. Do not repeatedly poll
the shell or print the entire event ring.
