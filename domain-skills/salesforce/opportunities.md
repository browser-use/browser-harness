# salesforce — opportunities (Lightning)

Patterns for reading Opportunity data out of Salesforce Lightning. Tested against Sales Cloud with the standard pipeline.

## URL patterns

- `https://<instance>.lightning.force.com/lightning/o/Opportunity/list?filterName=<ViewName>` — list view.
- `https://<instance>.lightning.force.com/lightning/o/Opportunity/pipelineInspection?filterName=<viewId>` — Pipeline Inspection. This is the view you want when you need a **Stage** column without modifying the user's saved list view.

## Shadow DOM is mandatory

Most Salesforce Lightning structural elements (tables, rows, cells, toolbar buttons) live inside nested `shadowRoot`s. `document.querySelectorAll('table')` returns 0. Always walk shadow roots:

```js
function* walk(root) {
  const q = [root];
  while (q.length) {
    const el = q.shift();
    if (el.nodeType === 1) yield el;
    if (el.shadowRoot) q.push(el.shadowRoot);
    for (const c of (el.childNodes || [])) q.push(c);
  }
}
// usage: for (const el of walk(document)) { ... }
```

Every selector in this file assumes this walk. Without it, counts come back as 0 and you waste time doubting your target.

## Kanban board — virtualizer cap

Kanban view (`Select list display` → `Kanban`) columns use the class `.runtime_sales_pipelineboardPipelineViewColumnHeader` for the header; cards are `li.runtime_sales_pipelineboardPipelineViewCardStencil`; the per-column scroll container is `div.listContent`.

Each card's Opportunity ID is embedded in a class on the inner `.pipelineViewCard` div — e.g. `<div class="006Ts00000V5K5tIAF pipelineViewCard uiDraggable">`. Parse it out with `className.split(/\s+/).find(c => /^006[A-Za-z0-9]{12,15}$/.test(c))`.

**Trap — cards/column cap at 13.** The column virtualizer renders at most ~13 cards regardless of how much you scroll (`scrollTop`, CDP `mouseWheel`, `Emulation.setDeviceMetricsOverride` to a tall viewport — none of these change it). The column **header** still shows the true count in parentheses, e.g. `Proposal sent   (16)`, so when rendered cards < header count you know you're missing rows. Don't fight the virtualizer — switch to Pipeline Inspection instead.

## Pipeline Inspection — the Stage column

Top-right of the list view there's a `Pipeline Inspection` button. It opens a different view (`/lightning/o/Opportunity/pipelineInspection?...`) with a real `Stage` column and a proper virtualized table.

The table has a `Stage` header (matchable via `th.innerText.match(/Stage/)`). Example row extraction:

```js
// inside walk(document)
for (const el of walk(document)) {
  if (el.tagName === 'TABLE') {
    const ths = [...el.querySelectorAll('th')].map(th => th.innerText || '');
    if (ths.some(t => t.match(/Stage/))) {
      return [...el.querySelectorAll('tbody tr')].map(tr =>
        [...tr.querySelectorAll('th, td')].map(c => c.innerText.trim().split('\n')[0])
      );
    }
  }
}
```

Defaults that will surprise you:

- **`Close Date = This Quarter`** — hides opportunities with close dates outside the current quarter even when the stage filter is broad. Open the Close Date dropdown, pick `Custom`, and set Start/End to something like `1/1/2020` and `31/12/2030`. Set the `<input placeholder="Pick a date">` value via the native `HTMLInputElement` setter and dispatch `input`+`change`+`blur`, otherwise Lightning won't enable the Apply button:

  ```js
  const set = (el, v) => {
    const s = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    s.call(el, v);
    ['input','change','blur'].forEach(e => el.dispatchEvent(new Event(e, {bubbles:true})));
  };
  ```

- **`Forecast filter = Open Pipeline`** — hides `Closed Won` / `Closed Lost`. If you need won/lost, change the filter via the top-right dropdown.
- **Scroll stalls before rendering all rows.** Re-rendering on filter change reshuffles the window; scroll-and-collect across multiple passes (before and after the filter change) rather than expecting one scroll to reveal every row.

## List view — "Select Fields to Display" is destructive

The gear icon on the list view offers `Select Fields to Display`. **Saving changes here persists to the user's saved list view** — it is not a temporary tweak. If all you need is a `Stage` column, use Pipeline Inspection; don't mutate someone's list view.

## Filter chooser and other toolbar buttons

The `List View Controls`, `Select list display`, and date-filter dropdowns are buttons with `title` attributes like `List View Controls` and `Select list display`, but they live inside shadow roots. Enumerate them via the shadow-walk above and click with CDP `click(x,y)` at the `getBoundingClientRect` center — calling `.click()` on a shadow-hosted button occasionally no-ops because focus events don't fire the same way.

## Don't try

- `fetch('/services/data/...')` from the page context. Lightning Locker / CSP blocks it. Salesforce REST API calls need to be made from `myinstance.my.salesforce.com` with a session ID, not from `lightning.force.com`.
- Directly opening each opportunity detail page just to read its Stage — Pipeline Inspection already exposes it.
