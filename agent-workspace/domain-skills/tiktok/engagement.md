# TikTok — Engagement (like · follow · comment)

Selector playbook for **engaging** on tiktok.com web (not posting — see
`upload.md` for TikTok Studio uploads). Attach to a Chrome profile already
logged into the target account. Two action *shapes*:

- **Text-input shape** (comment): focus an editable input → type → submit.
- **Click-toggle shape** (like, follow): click a button whose state flips after
  the action (like `aria-pressed` `false`→`true`; follow text `Follow`→`Following`).

> This file documents the same DOM contract the SmartSocial stagehand executor
> pins to (`agents/bob/runtime/stagehand-executor.ts`): identity-first, fixed
> selector allowlist, editable/clickable verification, block scan, fail-closed.
> **DM is intentionally NOT supported** — TikTok gates DM to followed/eligible
> accounts with no stable unsolicited-DM web flow, so `tiktok:dm` fails closed.

## Identity (assert BEFORE any action)

The logged-in handle is read from the **session chrome** (the header profile
link), never from page text. Returns `""` (fail closed) if not logged in:

```js
(() => {
  const a = document.querySelector('a[data-e2e="nav-profile"], a[data-e2e="profile-icon"]');
  const href = a ? a.getAttribute("href") : null;
  const m = href ? href.match(/\/@([A-Za-z0-9._]+)/) : null;
  return m ? m[1] : "";
})()
```

## Selectors

| Action | Element | Selector / signal |
|---|---|---|
| **Like** | like button on a video | `button[data-e2e="like-icon"]` (in-feed: `browse-like-icon`); state via `aria-pressed` (`"false"` → `"true"`) |
| **Follow** | profile-header / card button | `button[data-e2e="follow-button"]` whose trimmed text is `Follow` (followed → `Following`) |
| **Comment** | comment composer under a video | `div[contenteditable="true"][data-e2e="comment-input"]` (or the `[data-e2e="comment-text"]` editable) |
| **Comment submit** | Post button | `[data-e2e="comment-post"]`, or press `Enter` in the composer |
| **DM** | — | **unsupported** (fail closed) |

### Like — click-toggle (read `aria-pressed`)

TikTok's like button is itself the toggle and carries `aria-pressed`. This is
more robust than scraping the icon's red-fill swap. **Idempotency: if
`aria-pressed` is already `"true"`, DO NOT click — a second click un-likes.**

```python
# Verify it's a real, enabled button, read aria-pressed, click only if "false",
# then re-read: state must become "true".
js(r'''(() => {
  const b = document.querySelector('button[data-e2e="like-icon"], button[data-e2e="browse-like-icon"]');
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2),
                         pressed: b.getAttribute("aria-pressed")});
})()''')
# if pressed === "true": already liked → done, no click.
# else click_at_xy(...) then re-read aria-pressed; success when it flips to "true".
```

### Follow — click-toggle (read button text)

```python
# Click the profile Follow button. Success = text becomes "Following".
# Already "Following" → done, no click (no auto-unfollow — churn is a ban signal).
js(r'''(() => {
  const b = document.querySelector('button[data-e2e="follow-button"]');
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2),
                         text: (b.textContent||"").trim()});
})()''')
```

### Comment — text-input

```python
# Focus the composer, type, submit. Post-condition: the typed text appears in
# the page after submit (and was not pre-existing).
js('document.querySelector(\'div[contenteditable="true"][data-e2e="comment-input"]\').focus()')
type_text("your comment here")
press_key("Enter")   # or click [data-e2e="comment-post"]
```

## Notes / drift

- Selectors are **supervised-first**: confirm each `aria-pressed` / `data-e2e`
  read against the live UI before unsupervised runs (TikTok rotates `data-e2e`
  values less than IG rotates class names, but still verify).
- Block / rate-limit markers ("Something went wrong", captcha) and a redirect
  to `/login` map to fail-closed outcomes upstream — never retry-spam.
