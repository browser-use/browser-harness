# Instagram — Engagement (like · follow · comment · DM)

Selector playbook for **engaging** on instagram.com web (not posting). Attach to a
Chrome profile already logged into the target account. Two action *shapes*:

- **Text-input shape** (comment, DM): focus an editable input → type → submit.
- **Click-toggle shape** (like, follow): click a button whose `aria-label`/text
  flips state after the action (`Like`→`Unlike`, `Follow`→`Following`).

> This file documents the same DOM contract the SmartSocial stagehand executor
> pins to (`agents/bob/runtime/stagehand-executor.ts`): identity-first, fixed
> selector allowlist, editable/clickable verification, block scan, fail-closed.

## Identity (assert BEFORE any action)

The logged-in handle is read from the **session chrome**, never from page text
(a post comment containing the handle could spoof an LLM read). Left-nav own-profile
entry renders the session avatar:

```js
// returns the logged-in handle, or "" (fail closed)
(() => {
  const scope = document.querySelector('div[role="navigation"], nav') || document;
  const img = scope.querySelector('img[alt$="profile picture"]');
  if (!img) return "";
  const a = img.closest('a[href^="/"]');
  const m = a && (a.getAttribute("href") || "").match(/^\/([A-Za-z0-9._]+)\/?$/);
  if (m) return m[1];
  const am = (img.getAttribute("alt") || "").match(/^(.+?)'s profile picture$/);
  return am ? am[1] : "";
})()
```

If this returns `""` → treat as logged-out, do nothing.

## Selectors

| Action | Element | Selector / signal |
|---|---|---|
| **Like** | heart button on a post | `svg[aria-label="Like"]` (liked → `svg[aria-label="Unlike"]`); click the enclosing `div[role="button"]`/`button` |
| **Comment** | comment input under a post | `textarea[aria-label="Add a comment…"]` (note the ellipsis char `…`, U+2026) |
| **Comment submit** | Post button | adjacent `[role="button"]` with text `Post`, or press `Enter` in the textarea |
| **Follow** | profile-header button | `button` whose trimmed text is `Follow` (followed → `Following` / `Requested`) |
| **DM input** | conversation composer | `div[role="textbox"][contenteditable="true"]` (aria-label `Message`) |
| **DM send** | — | press `Enter` in the composer |

### Like — click-toggle

```python
# Verify it's a real button, not a link/report-flow, then click the heart.
# Success = aria-label flips Like -> Unlike (read AFTER the click).
js(r'''(() => {
  const svg = document.querySelector('svg[aria-label="Like"], svg[aria-label="Unlike"]');
  if (!svg) return null;
  const btn = svg.closest('div[role="button"], button');
  if (!btn) return null;
  const r = btn.getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2),
                         state: svg.getAttribute("aria-label")});
})()''')
# click_at_xy(...) then re-read: state must now be "Unlike"
```

### Follow — click-toggle

```python
# Click the header Follow button. Success = text becomes "Following" or "Requested"
# (private accounts return "Requested"; treat both as success).
js(r'''(() => {
  const b = [...document.querySelectorAll('button')]
    .find(b => ["Follow"].includes((b.textContent||"").trim()));
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.x+r.width/2), y: Math.round(r.y+r.height/2)});
})()''')
```

### Comment — text-input

```python
js('document.querySelector(\'textarea[aria-label="Add a comment…"]\').focus()')
type_text("your brand-voice comment")
press_key("Enter")   # or click the adjacent "Post" role=button
# Success = the comment text appears in the page AND was not pre-existing.
```

## Block / safety markers (any present → stop, do not retry)

Soft-block toast text (case-insensitive): `Action Blocked`, `Try Again Later`,
`We limit how often`, `restrict certain activity`.

URL fragments that mean "not on target / logged out": `/accounts/login`, `/login`,
`/challenge/`, `/checkpoint/`.

## Gotchas

- The comment textarea aria-label uses a real **ellipsis** `…` (U+2026), not three dots.
- **Like is an SVG inside a button** — verify `div[role="button"]`/`button`, never click the bare `<svg>` or a wrapping `<a>` (could be a report/profile link).
- A second un-acted **`Like` may exist** (e.g. nested reels/suggested) — pin to the first under the target post container; the stagehand observe instruction scopes "under this post".
- **Follow/unfollow churn is a known IG flag.** No auto-unfollow. Keep follow conservative.
- `Following` vs `Requested`: private accounts return `Requested` — both are success.
- Read like/follow state **after** the click for the post-condition; reading before proves nothing (idempotent re-runs would false-positive).
- All engagement is human-paced + rate-capped + (during ramp) approval-gated upstream; this file is selectors only.
