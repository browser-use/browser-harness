# Gmail — compose & drafts

## Account routing

Multi-account sessions: `https://mail.google.com/mail/u/<email>/` routes to that signed-in account directly — no clicking through the account switcher. Works with `#drafts`, `#sent`, etc. appended. First load sometimes lands on a "Temporary Error" page title that resolves itself; wait a beat and re-check `page_info()` before assuming failure.

## Compose window

- Open: click `[gh="cm"]` (stable attr on the Compose button). Fallback: `div[role=button]` with text `Compose`.
- The window can open **minimized**: `div[aria-label='Message Body']` exists but `offsetParent` is null. Click the `New Message` header bar to restore before filling.
- Fields:
  - To: `input[aria-label='To recipients']` (older UIs: `textarea[name=to]`)
  - Subject: `input[name=subjectbox]`
  - Body: `div[aria-label='Message Body']` (contenteditable)
- Plain text into To/Subject: `.focus()` then `document.execCommand('insertText', false, text)` — works fine.

## Trap: Trusted Types blocks HTML insertion into the body

Gmail ships a `require-trusted-types-for 'script'` CSP. Both of these throw `TypeError: This document requires 'TrustedHTML' assignment`:

- `document.execCommand('insertHTML', false, html)`
- `body.innerHTML = html`

**Fix:** Gmail does not restrict Trusted Types policy names, so create your own:

```js
const p = window.trustedTypes.createPolicy('fill-' + Math.floor(Math.random()*1e6), {createHTML: s => s});
const b = document.querySelector("div[aria-label='Message Body']");
b.focus();
b.innerHTML = p.createHTML(html);   // hyperlinks, <p>, <br> all preserved
b.dispatchEvent(new InputEvent('input', {bubbles: true, inputType: 'insertText'}));
```

The dispatched `input` event is required — without it Gmail's autosave doesn't register the change and the draft saves empty.

## Saving drafts

- Autosave fires off input events; the draft (with subject) appears in `#drafts` within seconds.
- Close-and-save: Escape, or click `img[aria-label='Save & close']` (also matches `.Ha`).
- Verify a draft's body actually saved by reading the list row snippets: `tr.zA` innerText includes the body preview after the subject.
