# Make.com — Scenario debugging via UI

The Make.com REST API exposes 80% of what you need for scenario engineering, but a few critical things only live in the editor UI:

- The **list of validation problems** behind a `BlueprintValidationError: N problem(s) found` (the API returns the count, never the list).
- The **stuck-execution queue** for a webhook (no `/queue/clear` endpoint on Celonis Enterprise — every probe returns 404).
- **Per-module execution traces** with filter-pass-through reasons ("the bundle did not pass through the filter").

This skill covers driving those UI flows with browser-harness.

## URL patterns (Celonis Enterprise = `eu1.make.celonis.com`)

All scenario/hook/connection routes are **team-id-prefixed**. Forgetting the prefix returns a 404 page.

```
https://eu1.make.celonis.com/{teamId}/scenarios/{scenarioId}        # scenario detail (read-only)
https://eu1.make.celonis.com/{teamId}/scenarios/{scenarioId}/edit   # editor (canvas)
https://eu1.make.celonis.com/{teamId}/hooks/{hookId}/queue          # webhook queue
https://eu1.make.celonis.com/{teamId}/connections                   # connections list
```

If you don't know `teamId` for the active scenario: navigate to anywhere first, observe `page_info()['url']` — it'll redirect through SSO and land on `/{teamId}/team/dashboard`.

## Read the actual validation errors

After a scenario fails to initialize, the API logs only show the count:

```
GET /api/v2/scenarios/{id}/logs?pg[limit]=5
→ {"error":{"name":"BlueprintValidationError",
            "message":"Cannot initialize the scenario because of the reason
                       'Scenario validation failed - 11 problem(s) found.'"}}
```

To see the **actual list of problems**:

1. Navigate to scenario detail page (NOT `/edit`):
   `https://eu1.make.celonis.com/{teamId}/scenarios/{id}`
2. Find the most recent `Error` badge in the History panel on the right and click it. JS to locate:
   ```js
   const errs = Array.from(document.querySelectorAll('*'))
     .filter(e => e.children.length === 0 && (e.textContent||'').trim() === 'Error');
   if (errs.length) {
     const r = errs[0].getBoundingClientRect();
     return {x: r.x+10, y: r.y+10};
   }
   ```
3. The right panel switches to "Run detail" mode. The error block at the bottom contains the full `BlueprintValidationError` block with one line per problem (e.g. `Missing value of required parameter '__IMTCONN__'.` repeated 11 times for our case).
4. Extract via JS — the panel is heavy on nested elements, so dump leaf text:
   ```js
   const out = [];
   document.querySelectorAll('*').forEach(e => {
     if (e.children.length === 0) {
       const t = (e.textContent||'').trim();
       if (/missing|required|parameter|validation|error|filter/i.test(t)
           && t.length < 300 && t.length > 5) out.push(t);
     }
   });
   return [...new Set(out)];
   ```

For run-time errors on individual modules (filter blocks, kVASy fault text, etc.), do the same but click a specific History run and scroll the right panel — every module shows a status line like `The operation was completed.`, `The bundle did not pass through the filter.`, or `The operation failed with an error.` followed by error details.

## Clear a stuck webhook queue

When a scenario fails to initialize and webhooks keep retrying, the hook's `queueCount` climbs. Each failed retry **re-invalidates the scenario** even after you've fixed the blueprint — until you drain the queue. Celonis Enterprise has no API for this. UI flow:

```python
import time

# 1. Open the queue page
goto_url(f'https://eu1.make.celonis.com/{teamId}/hooks/{hookId}/queue')
time.sleep(4)

# 2. Select-all checkbox is the first checkbox in the table header row
res = js('''const cbs = document.querySelectorAll("input[type=checkbox]");
            if (cbs.length) { const r = cbs[0].getBoundingClientRect();
                              return {x: r.x+r.width/2, y: r.y+r.height/2}; }
            return null;''')
click_at_xy(int(res['x']), int(res['y']))
time.sleep(1)

# 3. Top-right red "Delete all (N)" button activates after selection
res = js('''const btns = document.querySelectorAll("button");
            for (const b of btns) {
              if ((b.textContent||"").toLowerCase().includes("delete all")) {
                const r = b.getBoundingClientRect();
                return {x: r.x+r.width/2, y: r.y+r.height/2};
              }
            } return null;''')
click_at_xy(int(res['x']), int(res['y']))
time.sleep(2)

# 4. Two confirmation dialogs in sequence — both have a "Delete" button
for _ in range(2):
    r = js('''const btns = document.querySelectorAll("button");
              for (const b of btns) {
                const t = (b.textContent||"").trim();
                if (t === "Delete") {
                  const r = b.getBoundingClientRect();
                  if (r.x > 300) return {x: r.x+r.width/2, y: r.y+r.height/2};
                }
              } return null;''')
    if r: click_at_xy(int(r['x']), int(r['y'])); time.sleep(2)
```

Trap: the JS exact-match `t === "Delete"` also matches the still-visible top-right "Delete all (N)" button if you don't filter — use a position filter (e.g. `r.x > 300`) to grab the dialog button instead.

## Editor cache is sticky

After you `PATCH /scenarios/{id}` via the API, an open editor tab keeps showing the **previous** blueprint. Hard-reload doesn't always help — the editor pulls from local storage / IndexedDB. To force a refresh:

```python
js('localStorage.clear(); sessionStorage.clear();')
js('location.reload(true);')
import time; time.sleep(8)
```

The detail page (`/scenarios/{id}` without `/edit`) re-fetches from the server on every load, so prefer that view when you only need to inspect History/state.

## Run-once: trigger validation without a real caller

For sync validation feedback in the editor:

1. Click `Run once` (bottom-left of `/edit` view). The webhook module gets a red "listening" ring.
2. Trigger the webhook from outside (curl). When the scenario is in instant/sync mode and the blueprint validates, the curl returns the actual `WebhookRespond` body. When validation fails, you get HTTP 500 `Scenario failed to initialize.` synchronously — useful for fast iteration.
3. After the run completes (or errors), the canvas modules light up with green checkmarks (success) or no badge (skipped via filter). The right panel has the per-module trace.

`Run once` button locator:

```js
const btns = document.querySelectorAll('button');
for (const b of btns) {
  if ((b.textContent||'').trim().includes('Run once')
      && !b.textContent.includes('Replay')) {
    const r = b.getBoundingClientRect();
    return {x: r.x+r.width/2, y: r.y+r.height/2};
  }
}
```

## DOM gotchas

Make's editor renders the canvas via Angular custom elements (`<INTEGROMAT>`, `<IMT-OVERLAY-CONTAINER>`, `<IMT-BLUEPRINT-DROP-OVERLAY>`). There is **no `<canvas>` and no SVG** for the flow graph — modules are absolutely-positioned div trees. Consequences:

- `document.querySelector('canvas')` returns null. Don't use canvas-coord math.
- Module IDs (`75`, `76`, …) are not in `data-id` attributes — they appear as plain text labels under the icon. `querySelectorAll('[data-id]')` returns nothing.
- The internal scenario state is at `window.activeScenario` (read-only summary; `isActive`, `isInvalid`, `dlqCount`, etc.). It does **not** include the live blueprint — fetch that via API.
- `window.ImtInspector._instance` exposes the Angular injector but not a redux/store you can introspect. Don't bother.

For pixel-coordinate clicks on canvas modules, the reliable strategy is screenshot → coord-pick → `click_at_xy`. Do not try to compute coords from DOM rectangles for canvas-module elements; the icons are nested several levels deep with their own transforms.

## Scenario activation toggle

Top-right of the scenario detail page. Easiest selector:

```js
const t = document.querySelector('[role="switch"]');
const r = t.getBoundingClientRect();
return {x: r.x+r.width/2, y: r.y+r.height/2,
        currentState: t.getAttribute('aria-checked')};
```

After a re-PATCH that flipped `isActive` to false (auto-deactivation on validation failure), POST `/api/v2/scenarios/{id}/start` is equivalent and faster than the UI toggle.

## Login state

Make uses Celonis SSO. If you land on `/sso/oauth?code=...` after a `goto_url`, just `time.sleep(5)` — the redirect chain finishes on the team dashboard. No interactive login needed if Chrome is already authenticated.
