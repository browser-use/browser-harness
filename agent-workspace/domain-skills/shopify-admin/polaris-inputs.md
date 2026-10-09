# Polaris React inputs require CDP-native keystrokes

Shopify admin uses Polaris (their design system). Until January 2026 it was React-based. Polaris React text inputs and textareas are controlled components that **reject the standard "React-friendly" synthetic value setter pattern.**

## The trap

This pattern looks like it works — the field's `value` shows the right text:

```js
const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
setter.call(inputEl, "my text");
inputEl.dispatchEvent(new Event('input', { bubbles: true }));
```

But the **Save / Submit button stays disabled**. Polaris's onChange handler reads from React's internal state, which the synthetic event chain doesn't fully update.

## What works

CDP-native keystrokes via `Input.insertText`:

```python
from helpers import js, type_text

# 1. Focus the input via JS — this works fine
js("""
(() => {
  const input = Array.from(document.querySelectorAll('input[type="text"], input:not([type])'))
    .find(x => { const r = x.getBoundingClientRect(); return r.width > 100 && r.height > 0; });
  if (input) input.focus();
})()
""", target_id=tid)

# 2. Type via CDP — fires Input.insertText which is the lowest-level
#    text-entry signal. React's controlled-input subscriber catches this.
type_text("My question text")
```

For textareas, same pattern with `document.querySelectorAll('textarea')`.

## Full add-FAQ pattern (Knowledge Base App)

```python
import time
from helpers import iframe_target, js, type_text, page_info, screenshot

def add_faq(question: str, answer: str) -> tuple[bool, str]:
    tid = iframe_target("qa-pairs-app")

    # 1. Make sure the form is rendered
    for _ in range(15):
        ready = js("""
        (() => {
          const i = Array.from(document.querySelectorAll('input[type="text"], input:not([type])'))
            .find(x => { const r = x.getBoundingClientRect(); return r.width > 100; });
          const t = Array.from(document.querySelectorAll('textarea'))
            .find(x => { const r = x.getBoundingClientRect(); return r.width > 100; });
          if (i && t) { i.focus(); return true; }
          return false;
        })()
        """, target_id=tid)
        if ready: break
        time.sleep(0.3)

    # 2. Type question (input has focus from step 1)
    type_text(question)
    time.sleep(0.2)

    # 3. Focus textarea, type answer
    js("""
    (() => {
      const t = Array.from(document.querySelectorAll('textarea'))
        .find(x => { const r = x.getBoundingClientRect(); return r.width > 100; });
      if (t) t.focus();
    })()
    """, target_id=tid)
    time.sleep(0.2)
    type_text(answer)
    time.sleep(0.4)

    # 4. Click Save (now enabled because Polaris saw real keystrokes)
    saved = js("""
    (() => {
      const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Save');
      if (!btn || btn.disabled) return {clicked: false, disabled: btn?.disabled};
      btn.click();
      return {clicked: true};
    })()
    """, target_id=tid)
    if not saved.get("clicked"):
        return False, "save_button_disabled"

    # 5. Poll URL for save success — Shopify redirects to /pairs/<id>
    for _ in range(20):
        time.sleep(0.3)
        url = page_info().get("url", "")
        if "/pairs/" in url and "/new" not in url:
            return True, url.split("/pairs/")[-1]
    return False, "save_timeout"
```

## Why this works

Polaris React components subscribe to native `inputType` events (e.g., `insertText` from IME / accessibility tools / paste). The synthetic React-friendly setter fires `input` events but skips the lower-level `inputType` signal that Polaris validates against to enable Save buttons.

CDP `Input.insertText` (which the harness's `type_text()` calls) emits the full native event chain, including `inputType: 'insertText'`, which React catches via its synthetic event system.

## Polaris Web Components (post January 2026)

The `polaris-react` repo was archived January 6, 2026. New Polaris is web-component-based. For new admin surfaces (Catalog Mapping, parts of Settings), the pattern shifts:

```js
// Web components expose value setter on the element itself
const wc = document.querySelector('s-text-field');
wc.value = 'my text';
wc.dispatchEvent(new CustomEvent('input', { bubbles: true, detail: { value: 'my text' } }));
```

But until Shopify completes the migration (probably late 2026), **always test the React pattern first** — most legacy surfaces still use it.

## How to know which pattern to use

Screenshot the form first. Then JS-introspect:

```js
// Check if React-based (Polaris-* class names) or web-component-based (s-* tags)
const hasReact = document.querySelector('[class*="Polaris-"]');
const hasWC = document.querySelector('s-text-field, s-button, s-textarea');
return { hasReact: !!hasReact, hasWC: !!hasWC };
```

If both, lean web component (the surface is mid-migration and the WC will be authoritative).

## Avoid

- Coordinate-based typing via `Input.dispatchKeyEvent` keypress-by-keypress — slower, more brittle, no real benefit over `Input.insertText`
- `el.value = 'x'` without the setter prototype trick — won't even fill the visible field on Polaris React
- `dispatchEvent(new Event('change', ...))` only — Polaris listens for `input`, not `change`, on text fields
