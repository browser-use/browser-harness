# Shopify embedded apps run in iframes

Every Shopify app surfaced in the admin (first-party like Knowledge Base, third-party like Okendo) renders inside a sandboxed iframe. Your top-level `document` queries find the Shopify chrome (sidebar, header, search bar) but **none of the app's UI**.

## How to target the iframe

```python
from helpers import iframe_target, js, type_text

# 1. Find the iframe by URL substring
tid = iframe_target("qa-pairs-app")  # Knowledge Base App

# 2. Run JS inside the iframe by passing target_id
result = js("""
(() => {
  const button = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Add FAQ');
  if (button) { button.click(); return {clicked: true}; }
  return {clicked: false};
})()
""", target_id=tid)
```

## Finding the URL substring

The iframe's URL contains the app slug. Run:

```python
import json
for t in cdp("Target.getTargets")["targetInfos"]:
    if t["type"] == "iframe" and "shopify" in t.get("url", "").lower():
        print(t["url"])
```

Then pick a substring unique to your target app.

## Known Shopify app iframe slugs

| App | iframe URL substring |
|---|---|
| Shopify Knowledge Base (qa-pairs-app) | `qa-pairs-app` |
| Shopify Online Store editor | `online-store-web.shopifyapps.com` |
| Shopify Hydrogen Storefront | `hydrogen-storefronts` (or similar — verify) |

Add to this table when you discover new ones.

## Why iframes

Shopify uses App Bridge to embed third-party apps with isolation. Your top-level page CAN'T directly access app DOM for security reasons — you need iframe targeting (which the harness does via CDP `Target.attachToTarget`).

## Coordinate clicks vs JS clicks

Coordinate clicks (`click(x, y)`) pass through iframes at the compositor level — they work. But JS clicks scoped to the iframe target are more reliable for routine button taps because:

- Element text content is stable across UI redesigns
- DPR scaling on retina is automatic
- React event handlers are guaranteed to fire (vs. CDP mouse events which sometimes hit a transparent layer above the button)

## Gotcha — multiple iframes from same app

The Online Store editor renders the storefront preview AND the editor toolbar in two separate iframes. Pick the right one by URL substring; don't assume the first match is correct.

```python
# WRONG — picks first match
tid = iframe_target("online-store-web")

# RIGHT — disambiguate
for t in cdp("Target.getTargets")["targetInfos"]:
    url = t.get("url", "")
    if "online-store-web" in url and "editor" in url:
        tid = t["targetId"]
        break
```
