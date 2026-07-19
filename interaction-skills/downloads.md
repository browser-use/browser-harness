# Downloads

Prefer the runtime's native fetch, URL reader, download, or web-search tool for
public stateless retrieval. Do not use Browser Harness merely to fetch bytes.

Use `browser_fetch_to_file(url, path)` only when a download requires the current
page's authentication, origin, or anti-bot state. Record that reason before
using it. It performs an in-renderer
`fetch(..., {credentials: 'include'})`, waits internally, and transfers the
response in bounded chunks. It accepts `method`, `headers`, `body`, and
`timeout`; a dict/list body is JSON-encoded automatically. `http_get(...)` is a
fallback when no native retrieval tool exists and the resource is genuinely
public.

For a normal browser-triggered download, capture the network cursor before the
click, perform the click, wait once, then inspect `network_events(since=cursor)`
for the request/response that proves the action started. Do not repeatedly poll
the shell or print the entire event ring.
