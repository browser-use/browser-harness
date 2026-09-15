# Kibana Dev Tools Console

- Console route: `/app/dev_tools#/console/shell`.
- The left Monaco editor holds requests; the right editor shows responses. Editor DOM text is virtualized, so `document.body.innerText` may contain only the visible portion of a large response.
- Verify the complete request before running it. A fresh console can contain example index-creation and document-write requests. Replace them with the intended request first.

## Read-only requests and response capture

Run one verified GET or search request through the visible console and observe its `Network.requestWillBeSent` event. Kibana 9.5.1 used:

`POST /api/console/proxy?path=<URL-encoded Elasticsearch path>&method=<Elasticsearch method>`

The outer POST is the console transport; the query parameter specifies the Elasticsearch operation. A GET document lookup and a POST `_search` are reads, whereas indexing or deletion operations mutate data.

- Preserve the current UI's noncredential API metadata when replaying through same-origin `fetch`. The tested console sent `x-elastic-internal-origin: Kibana`, `kbn-version`, `kbn-build-number`, and `Content-Type: application/json`.
- Do not hardcode build/version metadata across deployments. Capture it from the working UI request. Supplying only a version or XSRF header returned HTTP 400 with “exists but is not available with the current configuration” in the tested version.
- Use the existing authenticated browser session; do not extract or publish authentication headers or cookies.
- `Network.getResponseBody` with the observed request ID returns the full response even when the editor only renders some lines. Save the request body alongside it for reproducibility.

## Editor input

In a tested Monaco session, one bulk `Input.insertText` call left only the first two characters. Pacing single-character insertions recovered full input. Reinspect the complete request before clicking Run; an immediate screenshot or successful input call does not establish that the editor accepted all text.
