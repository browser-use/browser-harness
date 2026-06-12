# Klaviyo onsite signup forms (popups embedded on host sites)

Klaviyo popups are injected into the host page's DOM by `klaviyo.js` (no
iframe). Everything below applies on any site running them.

## Force-open a form (no waiting for triggers)

Popups fire on Klaviyo-side targeting (delay/exit-intent/once-per-visitor
cookies). Skip all of it:

```python
js("window._klOnsite.push(['openForm', '<FORM_ID>'])")
```

The form ID is the suffix of the teaser class (`kl-teaser-<FORM_ID>`) or of
`.klaviyo-form-<FORM_ID>` embed divs.

## DOM map

- Every Klaviyo node carries `kl-private-reset-css-<hash>`; layout/skin
  classes are obfuscated (`go<digits>`) — don't select on those.
- Popup overlay: `div[role=dialog][aria-label="Form Dialog"]` — inline-styled
  `position:fixed; z-index:90000` full-viewport flex container, direct
  child of a plain div under `<body>`.
- The form: `form.klaviyo-form` inside `[data-testid="POPUP"]`.
- Close button: `button[aria-label="Close dialog"]`.
- Teaser (minimized bubble after dismissal): fixed div classed
  `kl-teaser-<FORM_ID>`, contains `[data-testid="animated-teaser"]` and a
  `span[role=button][tabindex=0]`.
- While the popup is open Klaviyo puts `klaviyo-prevent-body-scrolling` on
  `<body>` — a reliable open/closed signal.

## Trap: hiding the teaser with display:none freezes the whole page

The popup-close sequence hands off to the teaser and only finalizes cleanup
once the teaser renders. If host CSS sets the teaser `display:none`, close
stalls forever: the full-viewport overlay stays mounted at `opacity:0` with
`pointer-events:auto` (z-index 90000) and the body scroll-lock class stays
on — every click on the page is swallowed until reload, with zero console
errors. Diagnose with `document.elementFromPoint(x, y)` returning a
`kl-private-reset-css-*` div over page chrome.

To hide the teaser safely, keep it rendered:

```css
div[class*='kl-teaser-'] { opacity: 0 !important; pointer-events: none !important; }
div[class*='kl-teaser-'] * { visibility: hidden !important; pointer-events: none !important; }
```

`opacity` must go on the wrapper (descendants can't undo a composited parent
opacity). Plain `visibility:hidden` on the wrapper does NOT work — Klaviyo's
reset CSS re-sets `visibility:visible` on every descendant (without
`!important`, so an `!important` descendant rule still wins).

## Other notes

- Klaviyo injects styles via CSSOM `insertRule` into empty `<style>` tags, so
  its forms render even under strict CSP; the host page's own cross-origin
  stylesheets are the ones whose `cssRules` you can't read.
- After closing a popup, verify cleanup before trusting further clicks:
  no fixed `kl-private-reset-css` div wider than the viewport remains and
  `document.body.className` no longer contains `klaviyo-prevent-body-scrolling`.
