# App Store Connect — architecture & gotchas (appstoreconnect.apple.com)

Shared notes for driving ASC. Read this first, then the per-flow file (`promo-codes.md`, `pricing-and-availability.md`). Requires an already-signed-in session — if redirected to an Apple ID / 2FA wall, stop and hand back to the user; never type credentials.

## Two eras of UI live side by side

ASC is half modern SPA, half legacy WebObjects. Which one you're on changes how you read and drive the page:

- **Modern "Distribution" pages** (App Information, Pricing and Availability, App Privacy, …) are an Angular/React SPA. The **left sidebar nav is rendered in shadow DOM** — a plain `document.querySelectorAll('a')` will NOT find "Promo Codes" / "Pricing and Availability". Either deep-walk shadow roots, or click by coordinate (compositor-level clicks pass through shadow DOM).
- **Legacy pages** (notably **Promo Codes**, `/distribution/promo_codes/generate`) are a WebObjects view **embedded in a same-origin iframe** whose `src` is `/WebObjects/iTunesConnect.woa/…`. The light/shadow DOM of the top page is nearly empty — everything real is inside `document.querySelector('iframe').contentDocument`. Same-origin, so `contentDocument` is directly accessible.

Quick test for "why can't I find this element": if `js()` returns empty for visible controls, check for an iframe (`document.querySelectorAll('iframe')`) before assuming shadow DOM.

## Deep-walk shadow DOM (modern pages)

```python
js(r"""(()=>{const hits=[];
  function walk(root){for(const e of root.querySelectorAll('*')){
    if(e.shadowRoot) walk(e.shadowRoot);
    if(e.childElementCount===0 && /^promo codes$/i.test((e.textContent||'').trim())){
      const r=e.getBoundingClientRect(); hits.push({x:Math.round(r.x+r.width/2),y:Math.round(r.y+r.height/2)});}
  }}
  walk(document); return JSON.stringify(hits);
})()""")
```

`getBoundingClientRect()` returns CSS px that match `click_at_xy` directly. **Prefer DOM-located coords over reading pixels off a screenshot** — on a HiDPI display the screenshot is downscaled for viewing, so eyeballed pixels are off by the device-pixel-ratio.

## Multi-tab targeting (the big time-sink)

When several tabs are open (e.g. a Themis dashboard, X, YouTube Studio alongside ASC), the daemon's default `js()` / `click_at_xy` target is often NOT the ASC tab — it silently runs against whichever tab it last attached to. Symptoms: `page_info()` suddenly shows a different URL; `js()` returns "no-iframe".

Pin every call to the ASC tab:

```python
ts = cdp("Target.getTargets")["targetInfos"]
asc = [t for t in ts if t["type"]=="page" and "appstoreconnect.apple.com" in t["url"]][0]["targetId"]
cdp("Target.activateTarget", targetId=asc)      # needed before any coordinate click_at_xy
js("…", target_id=asc)                            # DOM reads/writes hit the right document
```

Driving the page through `iframe.contentDocument` + `js(target_id=…)` with DOM `.click()` / `.value=` is far more reliable here than coordinate clicks, because it does not depend on which tab is frontmost.

## Don't type credentials

If a navigation lands on `idmsa.apple.com` / an Apple ID sign-in or 2FA prompt, stop and ask the user. The session is expected to be pre-authenticated.
