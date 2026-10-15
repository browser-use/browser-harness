# Facebook — Engagement (like · comment)

Selector playbook for **engaging** on facebook.com web — **like and comment only**.
This brand acts as a **dedicated personal profile** (not a Page). **DM (Messenger)
and follow/friend are intentionally NOT supported** — they are the highest Meta-ban
actions and fail closed.

> This file documents the DOM contract the SmartSocial stagehand executor pins to
> (`agents/bob/runtime/stagehand-executor.ts`): identity-first, fixed selector
> allowlist, editable/clickable verification, block scan, fail-closed. Facebook
> obfuscates its DOM heavily and rotates class names constantly — these are
> **supervised-first**: confirm every read against the live UI before unsupervised
> runs, and expect to re-verify after Facebook redesigns.

## Identity (assert BEFORE any action)

Facebook does not expose a clean handle in the chrome. The most stable logged-in
signal is the **`c_user` cookie** — the numeric profile id, not httpOnly. So set
the brand's `account_handle` to that numeric id. Fallback: the top-nav "Your
profile" shortcut's vanity username. Returns `""` (fail closed) if not logged in:

```js
(() => {
  const m = document.cookie.match(/(?:^|;\s*)c_user=(\d+)/);
  if (m) return m[1];                       // numeric profile id (preferred)
  const a = document.querySelector('a[aria-label="Your profile"], [aria-label="Your profile"] a[href]');
  const href = a ? a.getAttribute("href") : null;
  const um = href ? href.match(/facebook\.com\/([A-Za-z0-9.]+)\/?(?:$|\?)/) : null;
  return um ? um[1] : "";                    // vanity username fallback
})()
```

## Selectors

| Action | Element | Selector / signal |
|---|---|---|
| **Like** | post Like control | `div[aria-label="Like"][role="button"]` — aria-label flips to `Remove Like` once liked |
| **Comment** | comment composer | `div[contenteditable="true"][role="textbox"]` (aria-label `Write a comment…`) |
| **Comment submit** | — | press `Enter` in the composer |
| **DM / follow / friend** | — | **unsupported** (fail closed) |

### Like — click-toggle (read `aria-label`)

Facebook's Like button has no reliable `aria-pressed`; the signal is the button's
own `aria-label` flipping `Like` → `Remove Like`. **Idempotency: if it already reads
`Remove Like`, DO NOT click — a second click un-likes (or opens the reaction
picker).** Click triggers a plain Like (don't hover — hovering opens Love/Haha/etc).

```python
js(r'''(() => {
  const b = document.querySelector('div[aria-label="Like"][role="button"], div[aria-label="Remove Like"][role="button"]');
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2),
                         label: b.getAttribute("aria-label")});
})()''')
# if label === "Remove Like": already liked → done, no click.
# else click_at_xy(...) then re-read: success when label becomes "Remove Like".
```

### Comment — text-input

```python
js('document.querySelector(\'div[contenteditable="true"][role="textbox"]\').focus()')
type_text("your comment here")
press_key("Enter")
```

## Notes / risk

- **Meta ban risk is real.** Use a warmed, dedicated brand profile on a residential
  IP, conservative caps, slow ramp — the same posture as Instagram. A flagged
  profile can take the linked Instagram account down too.
- Block / checkpoint markers ("You're Temporarily Blocked", captcha) and any
  redirect to `/login` or `/checkpoint/` map to fail-closed outcomes upstream.
- Facebook redesigns frequently — treat these selectors as a starting point to
  re-confirm, not a guarantee.
