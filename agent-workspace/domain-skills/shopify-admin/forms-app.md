# Shopify Forms app — editing popup forms

The Forms app (`admin.shopify.com/store/<store>/apps/shopify-forms`) edits signup popups. Form detail URL: `/apps/shopify-forms/forms/<id>`.

## Iframes

Two `forms.shopifyapps.com` iframes coexist:

- `forms.shopifyapps.com/forms/<id>` — the form detail editor. Target this for field edits.
- `forms.shopifyapps.com/?embedded=1&hmac=...` — hosts App Bridge modals (e.g. the "Select discount" picker). Target THIS one to drive the picker's search input and option list.

## Trap: attaching a discount overwrites copy

Selecting a discount on the Success section AUTO-OVERWRITES four fields with generic text (e.g. "10% off entire order • For 2 customer segments • One use per customer" — customer-facing!):

1. Teaser title
2. Form title
3. Success title
4. Success content (rich text)

Always re-fix all four after attaching, BEFORE saving.

## Editing text inputs (works)

```python
js("""(() => { const i = <find input>; i.focus(); i.select(); })()""", target_id=tid)
type_text("NEW VALUE")  # Input.insertText replaces the selection, React state updates
```

## Editing rich-text Content fields (Lexical-style contenteditable)

These desync React state if touched via JS selection, `execCommand`, or `Input.insertText` — the DOM looks right but the char counter shows 0/150 and validation says "Content is required". Once desynced, the only recovery is Discard and redo.

The ONLY reliable path:

```python
click_at_xy(x, y, clicks=3)          # real triple-click selects the paragraph natively
for ch in "New content text.":
    cdp("Input.dispatchKeyEvent", type="char", text=ch, key=ch, modifiers=0)
```

- The first char event replaces the native selection and updates editor state; the rest append.
- Do NOT use `press_key(ch)` — it sends keyDown-with-text plus a char event, doubling every character (`UUssee  iitt`).
- Cmd+A via CDP (`commands:["selectAll"]`) selects but Backspace deletion doesn't register with the editor state.

## Verifying

Char counter next to the field is the source of truth for React state, not the DOM text. After edits, counter must match the visible text length. Then Save (top save-bar) and look for the "Changes saved" toast.
