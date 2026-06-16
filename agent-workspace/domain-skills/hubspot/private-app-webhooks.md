# HubSpot — editing a Private App's webhook subscriptions

For adding or removing property-change subscriptions on a Private App (the v3 webhook surface). Assumes the app already exists.

## URL map

- `https://app-<region>.hubspot.com/private-apps/{portalId}/{appId}/webhooks` — **read-only view** of current subscriptions. Useful for verification after a change. `<region>` is `na1`, `na2`, `eu1`, etc.
- `https://app-<region>.hubspot.com/private-apps/{portalId}/{appId}/edit` — drops you into the editor. From here, click the **Webhooks** tab in the left rail to reach the subscription editor.

The read-only `/webhooks` page does **not** have a "Create subscription" button. Get into edit mode first.

## Flow (add a single property subscription)

1. Go to `/private-apps/{portalId}/{appId}/edit` and click the **Webhooks** tab in the left sidebar.
2. Click **Create subscription** — a right-side drawer opens titled "Create new webhook subscriptions".
3. Select **Which object types?** → e.g. `Company`. (Coordinate-click required — see gotcha below.)
4. Select **Listen for which events?** → e.g. `Property changed`. A new "Which properties?" picker appears.
5. Click the property picker → type the property name into its search box → click the matching option.
6. Click **Subscribe** at the drawer footer. The new row appears in the *draft* subscription list with `Details / Pause / Unsubscribe` buttons.
7. Close the drawer (Cancel is fine — it cancels *only further additions*, not the subscription you just created).
8. Click **Commit changes** at the top-right. A short "Saving…" indicator appears; on success the page transitions out of edit mode back to the app detail view.

After commit, HubSpot's docs say webhook settings can take up to 5 minutes to propagate. In practice the new subscription is usually live in seconds — observed sub-30s end-to-end (property edit → webhook delivery) with no provisioning delay.

## Gotchas

### Object-type / event-type dropdowns are React-Select; `.click()` on the `<div role="option">` doesn't stick

The dropdown items render as `<div class="Select-option" role="option">` inside a `<div role="listbox">` portal. Calling `.click()` on that div from JS opens the dropdown and may visually highlight the row, but the selection chip never appears in the form. The form state only updates on a real synthesized mouse event at the option's screen coordinates.

Pattern that works:

```js
// 1. Open the dropdown via the trigger button
const trigger = [...document.querySelectorAll('button')]
  .find(b => b.textContent.trim() === 'Select one or more object types');
trigger.click();

// 2. Read the option's coordinates...
const opt = [...document.querySelectorAll('[role="option"]')]
  .find(o => o.textContent.trim() === 'Company');
const r = opt.getBoundingClientRect();
// → r.x + r.width/2, r.y + r.height/2
```

Then issue a **coordinate click** through CDP at the returned (x, y). `.click()` from JS will not work; the React-Select widget swallows it.

### The Subscribe button's `textContent` is `"SubscribeLoading"`

The button renders a co-located loading indicator inside it whose text concatenates with the visible label. Searching for `b.textContent.trim() === 'Subscribe'` returns nothing. Match with a prefix instead:

```js
const btn = [...document.querySelectorAll('button')]
  .find(b => /^Subscribe/.test(b.textContent.trim()));
```

The button is still functional — the issue is only matching it.

### Two-step save: drawer Subscribe ≠ commit

Clicking **Subscribe** in the drawer adds the row to a *draft* list that's visible on the left side of the screen *while the drawer stays open* (so you can keep adding more). Nothing is persisted until you click **Commit changes** at the top-right. If you close the page after Subscribe but before Commit, the draft is discarded silently.

This is also why **Cancel** in the drawer doesn't undo the Subscribe you just clicked — it only closes the drawer without adding *more* subscriptions. The committed/uncommitted state of existing draft rows is independent of the drawer.

### Read-only Webhooks tab has its own `/webhooks` URL; navigation can leave you on the wrong tab

After **Commit changes**, the page redirects to the app detail view (no `/webhooks` suffix), which doesn't list the subscriptions. To verify, explicitly navigate to `/private-apps/{portalId}/{appId}/webhooks` — that's the read-only listing. Don't rely on the post-commit redirect to show you the result.

### Cache delay claim: "up to 5 minutes"

HubSpot's banner says "Webhook settings can be cached for up to five minutes. When making changes to the webhook URL, concurrency limit, or subscription settings, it may take up to five minutes to see your changes go into effect." Observed reality: a new subscription delivered events within seconds in one test. Don't *rely* on the 5-min ceiling for cutover ordering — assume it could be near-instant.

## Verification

The read-only Webhooks tab lists each property subscription as its own row. To check programmatically that a specific property is subscribed:

```js
const subscribedProps = (() => {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const out = new Set();
  let n;
  while ((n = walker.nextNode())) {
    const t = n.nodeValue.trim();
    if (/^(type|name|target_)/.test(t) && t.length < 50 && !t.includes(' ')) {
      out.add(t);
    }
  }
  return [...out];
})();
```

Adjust the regex to your property naming. The "no space" filter excludes the human-readable labels that share the same text node area.

## What this skill doesn't cover

- The `expanded object support` beta toggle in the drawer — not needed for standard property-change subscriptions; leave OFF unless the task explicitly requires it.
- Removing a subscription (the `Unsubscribe` per-row button) — straightforward; same Commit-changes gate applies.
- Webhook target URL changes — different flow (single text input near the top of the Webhooks tab), not covered here.
- Concurrency limit — same; single text input.
