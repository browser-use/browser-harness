---
name: quick-diagnostics
description: Inspect authenticated Quick sites without changing their deployment, pin browser reads to the right tab, and safely summarize warehouse results.
---

# Quick site diagnostics

Quick sites live at `https://<site>.quick.shopify.io` and require IAP authentication. They serve static frontend assets, with platform APIs exposed through the Quick client. This guide covers inspection; deployment and application writes are separate actions.

## Start with source and deployment provenance

If the Quick CLI is installed and authenticated, use `quick curl` for read-only GETs. It handles IAP credentials internally; do not extract a token or construct an Authorization header manually.

```bash
# Replace <site> with the requested site. Keep retrieved content local.
QUICK_DIAGNOSTIC_ORIGIN='https://<site>.quick.shopify.io'
quick curl "$QUICK_DIAGNOSTIC_ORIGIN/" -fsS -o /tmp/quick-page.html
quick curl "$QUICK_DIAGNOSTIC_ORIGIN/metadata.json" -fsS -o /tmp/quick-metadata.json
quick curl "$QUICK_DIAGNOSTIC_ORIGIN/client/quick.js" -fsS -o /tmp/quick-client.js
```

The first response is HTML source, not an executed browser page. Inspect its actual script and stylesheet URLs, then fetch the specific assets needed for the investigation. Do not guess application endpoints from the site's name.

`/metadata.json` contains deployment information, but available fields depend on how the site was deployed. Inspect the returned schema before selecting a revision or source-origin field; do not assume a fixed metadata shape. Keep any identity fields out of shared output.

Record the host, retrieval time, available deployment revision, and hashes of the relevant assets. Compare the served assets with the intended local build before attributing behavior to a code change. A local SDK version, deployed application revision, and served `/client/quick.js` are different pieces of evidence.

For a backend diagnostic, distinguish the submitted configuration from any resolved version or runtime metadata the application actually returns. A UI control or requested version alone does not prove which configuration was served. Discover those fields from the application's source or observed response; Quick does not impose a universal schema for them.

## The browser client

Quick pages load the shared client with:

```html
<script src="/client/quick.js"></script>
```

The script exposes `window.quick`. Read the deployed client and the application's call sites to establish which methods and result shapes are available. Do not transplant an API signature from a different installed SDK version without checking it.

Use the browser when the question needs executed JavaScript, a session-dependent response, or visual verification. If authentication redirects to a sign-in page, stop the dependent work and let the user complete sign-in. Do not attempt to recover credentials from browser storage.

## Serialize operations on a shared native browser

The harness has one default selected session per daemon. `new_tab()` and `switch_tab()` change it; an unqualified `js()` or screenshot uses it. Two workers switching tabs can therefore make each other's operations land on the wrong page.

Assign one worker at a time to a shared native-browser daemon, including launch, navigation, screenshots and inspection. Do not assume separate Python processes have separate browser selection. The launcher's health probe can restart a daemon when its CDP probe does not respond, so concurrent invocations during a long operation add another failure mode.

Create a task-owned tab for the first navigation, retain its returned target ID, and pin later JavaScript reads explicitly:

```python
tid = new_tab("https://<site>.quick.shopify.io")
wait_for_load()
capture_screenshot("/tmp/quick-initial.png")

print(js("""({
  url: location.href,
  hasQuickClient: typeof window.quick !== 'undefined',
  hasWarehouseQuery: typeof window.quick?.dw?.querySync === 'function'
})""", target_id=tid))
```

Reinspect the screenshot and URL before relying on the page state. Later native clicks and `capture_screenshot()` still require the correct selected tab and serialized ownership; `target_id` only pins the JavaScript call above.

For raw CDP operations, attach to the known target and pass the resulting `session_id` explicitly. The signatures are in [helpers.py](../../helpers.py). A target ID is not the browser's visible tab index. See [tabs](../../interaction-skills/tabs.md) for that distinction.

## Keep JavaScript requests below the socket line limit

The daemon receives one JSON request per line through `asyncio`'s `StreamReader.readline()`. In the implementation using the default stream limit, a request line is limited to roughly 64 KiB. This is a request-size limit, not a JavaScript syntax error or a limit on the complete website.

- Keep each serialized request comfortably below that limit; a budget such as 24 KiB leaves room for JSON escaping and the CDP envelope.
- Count encoded bytes, not characters. Quotes, backslashes and non-ASCII text can expand during JSON serialization.
- Break large analyses into small expressions and bounded inputs. Reuse a small helper instead of sending a whole bundle in every call.
- Paginate large reads and project only the fields needed for each step. Do not embed entire HTML documents or result dumps in another JavaScript request.

If a request fails with a line-length error, reduce or chunk the payload before retrying. Do not repeatedly restart the browser for a deterministic transport-size error. Check [daemon.py](../../daemon.py) if the installed harness changes its stream configuration.

## Whitelist warehouse output before returning it

BigQuery access through `quick.dw` requires the user's warehouse authorization. Site sign-in alone does not establish that authorization. Use only the read-only query needed for the task and follow the existing authorization flow if it is missing.

Quick SDK results may contain a `job`, whose `client` references the warehouse client. That client can hold cached authentication state such as `_token`. Consequently, printing or serializing an entire query result or job can expose more than query rows.

Destructure the result and construct an explicit output object. For example, after warehouse access is authorized, this diagnostic query returns one harmless value:

```python
print(js("""(async () => {
  const { results, rowCount } = await quick.dw.querySync(
    'SELECT 1 AS probe_value',
    [],
    { maxResults: 1, timeoutMs: 10000 }
  );
  return {
    rowCount,
    rows: (results || []).slice(0, 1).map(row => ({
      probe_value: row.probe_value
    }))
  };
})()""", target_id=tid))
```

For a real query, replace the projection with the exact authorized columns; limiting the row count does not sanitize sensitive columns. Apply the same explicit projection to Node SDK output. Do not serialize `job`, `job.client`, the Quick client, authentication objects, or unfiltered SDK errors.

Prefer short structured status summaries over full response dumps. Preserve detailed evidence locally only when needed, and remove credentials and user-specific state from reusable documentation or shared reports.
