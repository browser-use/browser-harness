# App Store Connect — minting promo codes

Read `_architecture.md` first (this page is a **legacy WebObjects iframe**, and multi-tab targeting bites hard here).

There is **no ASC API** for one-time-purchase app promo codes (the API's promo/offer-code resources are subscription / IAP only). The web UI is the only path, and it's the old WebObjects view embedded in a same-origin iframe.

## URL & scope

- `https://appstoreconnect.apple.com/apps/<appId>/distribution/promo_codes/generate` — the page. Reach it from the app's left sidebar → **Promo Codes** (under GROWTH & MARKETING) if the deep link 404s.
- Only available once the app version is **approved / released** (`PENDING_DEVELOPER_RELEASE` / `READY_FOR_SALE`). Before that the Generate button is disabled — there's nothing to automate.
- Quota: **100 codes per app version**, refreshed quarterly. Codes are single-use, expire 28 days after generation or end of calendar year (whichever is first).
- The yellow banner about "offer codes have replaced promo codes" applies to **in-app purchases only** — app-level codes for a paid app still work.

## All real elements are inside the iframe

```python
js("(()=>{const d=document.querySelector('iframe').contentDocument; return d.body.innerText;})()", target_id=asc)
```

## Generate flow

1. **Set the quantity.** The Generate tab has a table row per version; the count is an `<input type=text>` that starts at `"0"`. Set it via the iframe DOM and fire events — coordinate typing is unreliable and the field **clamps to the max (100)** if mis-cleared (fat-fingering it mints the entire quota, which is irreversible):
   ```python
   js(r"""(()=>{const d=document.querySelector('iframe').contentDocument;
     const t=[...d.querySelectorAll('input[type=text]')].find(i=>i.value==='0');
     t.focus(); t.value='25';
     ['input','change','keyup','blur'].forEach(e=>t.dispatchEvent(new Event(e,{bubbles:true})));
     return t.value;})()""", target_id=asc)
   ```
2. **The "N of 100 codes remaining" counter is OPTIMISTIC** — it updates the instant you type a quantity and is NOT proof anything was generated. Do not trust it.
3. **Click the page's "Generate Codes" button** (DOM `.click()` on the element whose text matches `/generate codes?/i` with the smallest `y`) → opens a license-agreement modal.
4. **The agreement checkbox is a styled `span.itc-checkbox`** wrapping a hidden input. Setting the hidden `input.checked=true` may NOT trip the page's enable logic — the confirm button can stay effectively disabled. Drive the page's own handler and verify the modal actually submits.
5. **Click the modal's confirm "Generate Codes"** (the `/generate codes?/i` element with the *largest* `y` — bottom of the dialog). On success the modal shows: *"Your promo codes have been generated… view or download from the History tab."*

## History tab is the source of truth

After generating, **verify on the History tab** — it is authoritative:

- "You have not requested any codes in the past 60 days" → **nothing was minted** (the confirm click silently failed; common when the tab switched mid-flow). Safe to retry — you have not burned quota.
- A dated row (`<date> | <email> | … | <count>`) → it worked.

This check is what prevents accidental double-minting. The optimistic counter will happily show "75 of 100 remaining" even when zero codes exist.

## Reading the codes — no download needed

History → **View Codes** opens a modal that renders the codes **directly in the DOM**. Scrape them; there's no need to capture a file download:

```python
js(r"""(()=>{const d=document.querySelector('iframe').contentDocument;
  return JSON.stringify([...new Set((d.body.innerText.match(/\b[A-Z0-9]{12}\b/g)||[]))]);})()""", target_id=asc)
```

Codes are 12-char uppercase alphanumeric. (A "Download the Promotional Code Distribution Terms" link in the same modal fetches the legal PDF, not the codes — the codes themselves are the on-screen list and are also emailed to the account holder.)
