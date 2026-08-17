# Google Maps — business profile reviews

Scrape all reviews for a business (name, stars, date, text) without an API key.

## URL patterns

- Search: `https://www.google.com/maps/search/<business>+<city>` — a unique match redirects straight to the place page.
- Direct by place_id: `https://www.google.com/maps/place/?q=place_id:<PLACE_ID>` — resolves and redirects to the canonical place URL.
- **Language matters:** Google auto-translates reviews into the UI language. Add `hl=fr` (etc.) and re-scrape to get originals — for each review, one language is the reviewer's original and the other is Google's translation. Scrape both if you need the pair.
- The place URL contains the ftid `!1s0x...:0x<hex>` — the hex after the colon is the CID: `int(hex, 16)` → `https://maps.google.com/?cid=<decimal>`.
- All-reviews / write-review deep links (no Maps UI): `https://search.google.com/local/reviews?placeid=<PLACE_ID>` and `https://search.google.com/local/writereview?placeid=<PLACE_ID>`.

## Flow

1. Navigate to the place. Click the reviews tab: `[...document.querySelectorAll('button[role=tab]')].find(b => /Avis|Reviews/i.test(b.textContent)).click()`.
2. Reviews live in a lazy feed. Scroll the feed container (NOT the window): `document.querySelector('div[role=feed], div.m6QErb.DxyBCb').scrollBy(0, 3000)` in a loop with ~1 s sleeps until no new cards appear.
3. Expand truncated texts: click all `button.w8nwRe` ("More"/"Plus").
4. Extract per card:

```js
document.querySelectorAll('div[data-review-id][jsaction]').forEach(el => {
  const name  = el.querySelector('.d4r55')?.textContent?.trim();   // reviewer name
  const stars = el.querySelector('.kvMYJc')?.getAttribute('aria-label'); // "5 stars"/"5 étoiles"
  const date  = el.querySelector('.rsqaWe')?.textContent?.trim();  // relative ("2 months ago")
  const text  = el.querySelector('.wiI7pd')?.textContent?.trim();  // review body
  const meta  = el.querySelector('.RfnDt')?.textContent?.trim();   // "Local Guide · 15 reviews"
});
```

## Traps

- **Rating-only reviews leak the owner's response as the text.** If a reviewer left stars but no text, `.wiI7pd` inside that card can be the *owner's reply* ("Thank you X for..."). Detect: text addresses the reviewer by name / thanks them. Treat as empty.
- Dates are relative ("a day ago") — convert against scrape date immediately, they age.
- Duplicate `div[data-review-id]` nodes exist (card + expanded state); the `[jsaction]` filter plus name-presence check dedupes.
- Class names (`.d4r55`, `.wiI7pd`, `.rsqaWe`, `.kvMYJc`, `.RfnDt`, `.w8nwRe`) are obfuscated CSS-modules — they've been stable for a while but verify with a screenshot before a long scrape; `div[data-review-id]` and `div[role=feed]` are the durable anchors.
- No consent-wall in CA/US normally; EU IPs may get a consent interstitial before Maps loads.
