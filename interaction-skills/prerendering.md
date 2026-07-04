# Verifying speculation-rules prefetch/prerender

You **cannot** observe a speculation-rules prerender activate while the harness is attached:
Chrome disables prerendering whenever a CDP debugger is connected. Every attempt fails with
`PrerenderingDisabledByDevTools`, and after navigation
`performance.getEntriesByType('navigation')[0].activationStart` is `0`. This is the harness
causing the failure, not the page — do not "fix" the site's rules based on this signal.

What you CAN verify over CDP:

```python
import time, json
cdp("Preload.enable")
js("location.reload()")
wait_for_load()
time.sleep(5)
evs = [e for e in drain_events() if e.get("method", "").startswith("Preload")]
for e in evs:
    if e["method"] == "Preload.prerenderStatusUpdated":
        p = e["params"]
        print(p["key"]["url"], p.get("status"), p.get("prerenderStatus"))
```

- `Preload.ruleSetUpdated` fires → the `<script type=speculationrules>` parsed correctly.
- `Preload.prerenderStatusUpdated` with your target URLs → Chrome accepted the candidates.
- Status `Failure` + `PrerenderingDisabledByDevTools` → rules are fine; they will prerender
  in normal (non-automated) browsing. Any *other* failure reason is a real problem worth
  fixing (e.g. cross-origin URL, `no-store`, exceeded candidate limits).

Related limits worth knowing when writing rules: Chrome caps `immediate`/`eager` prerenders
at 10 and `moderate`/`conservative` at 2 (FIFO), and skips prerendering entirely under Data
Saver, battery saver, or low memory.
