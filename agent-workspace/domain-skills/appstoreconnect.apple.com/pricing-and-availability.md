# App Store Connect — pricing & availability

Read `_architecture.md` first. This is a **modern SPA** page (sidebar nav in shadow DOM), NOT an iframe.

- URL: `https://appstoreconnect.apple.com/apps/<appId>/distribution/pricing`
- **Price and availability are decoupled** — a correct base price tells you nothing about which territories the app actually sells in. Check both.

## Reading the current price

The summary view shows "Current Price · N Countries or Regions · May Adjust Automatically" but **not the amounts**. To see real per-storefront values, click the **"Current Price"** row (or "All Prices and Currencies") — it expands an inline table. Then scrape from the DOM rather than the screenshot:

```python
js(r"""(()=>{return document.body.innerText.split('\n').map(s=>s.trim())
  .filter(s=>/€|\$|£|USD|EUR|GBP|\d+[.,]\d{2}/.test(s)).slice(0,60).join(' | ');})()""")
```

Each storefront shows two numbers: **price** then **proceeds** (after Apple's commission). Apple **auto-equalizes** non-base storefronts for local tax/FX, so outliers (e.g. base $3.99 but Albania/Armenia at $4.99–$5.99) are **normal**, not a bug — only the base storefront is the price you set. Apple tiers map cleanly: e.g. Tier 4 = €3.99 / $3.99 / £3.99.

## Availability — verify after every release

A freshly created app frequently ships with availability **never affirmatively configured**: the price grid seeds ~174 storefronts but the **App Availability** panel still shows a "Set Up Availability" prompt, so the app is NOT live in all 175 territories. No automated check flags this — verify by hand at launch.

Flow:

1. On the pricing page, find the **"Set Up Availability"** button. It's in the App Availability panel; locate via DOM (`getBoundingClientRect` → `click_at_xy`) since the SPA nav/buttons are unreliable to eyeball on HiDPI.
2. The modal offers three radios: **All Countries or Regions (175)** / Specific Countries or Regions / Publish as Pre-Order. Public/Discoverable is the default visibility. For a normal launch, leave **All Countries or Regions** selected.
3. **Next** → confirmation: *"Make app available in all 175 countries or regions after releasing it?"* → **Confirm**.
4. After confirm the URL becomes `…/distribution/pricing/availability` and the page lists every territory at status **"Processing to Available"**. Apple propagates this to all storefronts in **~24h**. Header should read **"Availability (175 Countries or Regions)"**.

Verify the result from the DOM:

```python
js(r"""(()=>{const h=[...document.querySelectorAll('h1,h2,h3')].map(e=>e.innerText)
  .find(t=>/Availability\s*\(/i.test(t))||'';
  const proc=(document.body.innerText.match(/Processing to Available/g)||[]).length;
  return JSON.stringify({header:h, processingCount:proc});})()""")
```

The confirm dialog commits the change directly — there's no separate Save button to chase.
