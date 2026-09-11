# LinkedIn — Send Connection Request

Send connection requests (with or without note) to a profile at `https://www.linkedin.com/in/<handle>/`.

## Connect button is an `<a>`, not a `<button>`

Critical gotcha: LinkedIn renders the primary Connect action in the profile header as an `<a>` tag styled as a button. Querying `button` only misses it.

```python
# Works
link = "document.querySelector('a[aria-label*=\"Invite\"][aria-label*=\"connect\"]')"
js(f"{link}.click()")
```

The `aria-label` is `"Invite <FirstName> <LastName> to connect"` (use `*=` substring match to be robust across casing/punctuation).

## Initial modal is in main DOM

After clicking Connect, the first modal — "Add a note to your invitation?" — has two buttons both in the top-level document:

- `button[aria-label="Add a note"]`
- `button[aria-label="Send without a note"]`

These ARE queryable via JS against the main doc. Poll for `document.querySelector('button[aria-label="Send without a note"]')` to detect when the modal is ready (modal render takes 500–2500ms after click).

## Custom-note dialog is inside an iframe → paywalled on free tier

Clicking "Add a note" navigates to a second dialog rendered inside an iframe at `src="https://www.linkedin.com/preload/"` (747×770). JS scoped to the top document cannot see its buttons. `iframe_target("linkedin.com/preload")` returns `None` in my testing (CDP does not expose this frame through the normal iframe target map).

On a free LinkedIn account, this second dialog is the paywall surface. After a small number of personalized notes per month (observed cap ~5), the iframe renders:

> **"Send unlimited personalized invites with Premium"**
> "You're out of free custom notes. Bypass the limit with Premium..."

The first "Add a note" modal still appears — the paywall doesn't kick in until you click Add-a-note. So detect the paywall by screenshotting after clicking Add-a-note, or by checking if a textarea is queryable in the top doc afterwards (if not, you've hit the paywall).

## Flow: Send plain connection (no note)

Simplest, always works on free tier. Use this unless you need personalization.

```python
# 1. Navigate
goto('https://www.linkedin.com/in/<handle>/')
time.sleep(5)  # profile header load

# 2. Click Connect (a tag, not button)
r = js("""(() => {
  const a = document.querySelector('a[aria-label*="Invite"][aria-label*="connect"]');
  if (!a) return 'no-connect';
  a.click();
  return 'clicked';
})()""")

# 3. Poll for initial modal (up to 5s)
for _ in range(10):
    time.sleep(0.5)
    if js("!!document.querySelector('button[aria-label=\"Send without a note\"]')"):
        break

# 4. Click Send without a note
js("""document.querySelector('button[aria-label="Send without a note"]').click()""")
time.sleep(2.5)

# 5. Verify — either Pending button present, or Connect link is gone
pending = js("""({
  stillInvitable: !!document.querySelector('a[aria-label*="Invite"][aria-label*="connect"]'),
  pending: !!document.querySelector('button[aria-label*="Pending"]')
})""")
```

Signals of success:
- `stillInvitable: false` (profile header no longer shows Connect)
- OR `pending: true` (header now shows a Pending button)

## Flow: Send with custom note (free tier, rate-limited)

Use only when you have quota left. Failure mode is the Premium paywall.

```python
# 1-3: Same as plain-connect up to the initial modal appearing

# 4. Click Add a note
js("""document.querySelector('button[aria-label="Add a note"]').click()""")
time.sleep(1.5)

# 5. Check for paywall — if no textarea queryable, you've hit the cap
ta_exists = js("!!document.querySelector('textarea')")
if not ta_exists:
    screenshot('/tmp/paywall.png')
    # Paywall screenshot will show "Send unlimited personalized invites with Premium"
    raise RuntimeError("Hit free-tier custom-note quota — no textarea rendered")

# 6. Focus + type
js("document.querySelector('textarea').focus()")
type_text(note)  # ≤ 300 chars
time.sleep(0.8)

# 7. Click Send invitation
js("""document.querySelector('button[aria-label="Send invitation"], button[aria-label="Send"]').click()""")
```

## Coordinate-click fallback (when JS can't reach)

If a modal/element is in an iframe or shadow DOM that `js()` can't target, and the element IS visible in a screenshot, use `click(x, y)` with coordinates read from an earlier DOM walk.

Earlier in-doc DOM walk captured the rect:

```python
# Walk that includes shadow DOMs — catches elements before they migrate to iframes
r = js("""(() => {
  function walk(root, out) {
    root.querySelectorAll('*').forEach(el => {
      const text = (el.textContent || '').replace(/\\s+/g,' ').trim();
      if (text === 'Add a note' || text === 'Send without a note') {
        const rect = el.getBoundingClientRect();
        if (rect.width > 0 && rect.height > 0) {
          out.push({
            tag: el.tagName, text,
            aria: el.getAttribute('aria-label') || '',
            rect: {top: Math.round(rect.top), left: Math.round(rect.left), w: Math.round(rect.width), h: Math.round(rect.height)}
          });
        }
      }
      if (el.shadowRoot) walk(el.shadowRoot, out);
    });
  }
  const results = [];
  walk(document, results);
  return results;
})()""")

# Read rect and click the center
if r:
    rect = r[0]['rect']
    click(rect['left'] + rect['w']//2, rect['top'] + rect['h']//2)
```

## Rate limit notes

- Custom-note invites: ~5/month on free tier (actual cap varies). Hitting it shows the Premium paywall dialog.
- Plain "Send without a note" invites: higher cap (hundreds/month, but LinkedIn may throttle if bulk-sent too fast). Space them 2+ seconds apart.
- LinkedIn also tracks total weekly connection invites separately — ~100/week is the soft cap before "You're approaching the weekly limit" warnings.

## Alternative when Connect isn't shown at all

For very-far-network profiles (4th+ degree, or profiles with "Only mutuals" setting), the Connect link won't appear in the header at all — only Follow and Message (if Open Profile). `a[aria-label*="Invite"][aria-label*="connect"]` returns null. In that case the only options are:

1. Click Follow instead: `button[aria-label^="Follow "]`
2. Try the sidebar "People similar to X" cards, which may include Connect buttons for 2nd-degree adjacent people
3. InMail (Premium)
