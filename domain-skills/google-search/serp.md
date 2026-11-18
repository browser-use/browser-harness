# Google Search — SERP extraction and rate limits

## URLs

- Results: `https://www.google.com/search?hl=<lang>&gl=<country>&pws=0&q=<urlencoded>`.
  `pws=0` turns off personalization. `gl` sets the country.
- Autocomplete, without a browser: `https://suggestqueries.google.com/complete/search?client=chrome&hl=<lang>&gl=<country>&q=<prefix>`.
  The response is a JSON array `[q, suggestions[], descs[], [], {"google:suggestrelevance":[...], "google:suggesttype":[...]}]`.
  Fetch it with `http_get` and keep the request rate low (see below).

## Selectors (tested Nov 2026, hl=sl)

- Organic results: `#rso h3`, `closest('a').href`. The snippet block is `h3.closest('.MjjYud')`.
- People Also Ask: `[data-q]`. The question text is in the `data-q` attribute.
- Related searches: `#botstuff a`. Keep only short link texts.
- AI Overview: there is no stable class. Look for its localized heading in
  `[role=heading]` texts, e.g. "Pregled, generiran z umetno inteligenco" (sl) or "AI Overview" (en).
- A "Missing: <word>" line (sl: "Manjka:") in a snippet means the result does not contain all query words.

## Rate limits and CAPTCHA (the main trap)

- **Search:** at 6–10 s spacing, Google redirected to `/sorry/index?...` (CAPTCHA) after
  about 40 queries. The block stayed for hours. At 50–80 s spacing it ran without a block.
  Detect the block with `"/sorry" in location.href` or the "unusual traffic" text,
  stop the loop, and do not solve the CAPTCHA.
- **Autocomplete endpoint:** about 7 requests/s from one IP returned 403 after
  about 4k requests. After a few hours it worked again. 1 thread with 2.5–4.5 s sleep
  then ran 4.5k requests without a block. Poll every 5 min for HTTP 200 before resuming.
- Use one dedicated tab for the loop (`goto_url` in that tab, not `new_tab` per query),
  so the user's tabs stay untouched.
