# Amazon — Order History Extraction

Field-tested against amazon.co.uk on a 2010-2026 account (1,007 orders), first on
2026-07-16 and re-verified end-to-end on 2026-07-29. Complements
[product-search.md](product-search.md), which covers the public catalogue; this file covers the
logged-in `/your-orders` pages.

## Auth

Order history requires login. An unauthenticated visit to any orders URL redirects to
`/ap/signin` (title "Amazon Sign-In") — detect this and stop for a human login rather than
typing credentials:

```python
if "/ap/signin" in page_info()["url"]:
    raise RuntimeError("Amazon session not logged in — do a one-time headed login first")
```

A one-time headed login persists in the profile; no re-challenge was observed on later
headless runs from the same profile/IP.

## Navigation

First visit uses `new_tab()`, the same gotcha documented in product-search.md; `goto_url()`
is fine for every page after that.

```python
new_tab("https://www.amazon.co.uk/your-orders/orders?timeFilter=year-2025&startIndex=0")
wait_for_load()
wait(2)  # the order list hydrates after readyState=complete
```

- `timeFilter` takes `last30`, `months-3`, then `year-YYYY` back to the account's first year.
  Read the valid values off the page rather than guessing:
  ```python
  years = json.loads(js(
      "JSON.stringify(Array.from(document.querySelectorAll('#time-filter option')).map(o => o.value))"
  ))
  ```
- `startIndex` steps in 10s (`0, 10, 20, ...`) — 10 orders per page.

## Know the expected count before you paginate

The page states its own total, so a scrape can verify itself instead of guessing when to
stop. This is the difference between a complete run and a short one that looks complete.

```python
import re
count_text = js("document.querySelector('.num-orders')?.innerText")  # '186 orders' / '1 order'
expected = int(re.sub(r"[^\d]", "", count_text or "0") or 0)
```

Stop on the pagination control, not on a short page — `.a-last` carries `a-disabled` on the
final page and the whole `.a-pagination` block is absent when a year fits on one page:

```python
is_last_page = bool(js("""
  (function () {
    const l = document.querySelector('.a-pagination .a-last');
    return !l || l.classList.contains('a-disabled');
  })()
"""))
```

Then assert what you collected against what the page promised, and fail loudly on a
mismatch rather than writing a truncated file:

```python
if len(collected) != expected:
    raise RuntimeError(f"year-{year}: got {len(collected)} of {expected} orders — investigate before trusting output")
```

Verified on `year-2026`: 57 expected, 6 pages, 57 collected, every order dated.

## Extraction

Each order is an `.order-card`. Titles are the product links inside it; the order date is
loose text in the card. `js()` hands back whatever the expression evaluates to, so a
`JSON.stringify` payload needs `json.loads` on the Python side to become a list:

```python
import json

page_orders = json.loads(js("""JSON.stringify(Array.from(document.querySelectorAll('.order-card')).map(c => {
  const m = c.innerText.match(/(\\d{1,2}\\s+[A-Za-z]+\\s+\\d{4}|[A-Za-z]+\\s+\\d{1,2},\\s+\\d{4})/);
  const titles = Array.from(new Set(Array.from(
    c.querySelectorAll('.yohtmlc-product-title, a.a-link-normal[href*="/dp/"], a.a-link-normal[href*="/gp/product/"]')
  ).map(a => a.innerText.trim()).filter(t => t && t.length > 2)));
  return {date: m ? m[1] : '', titles};
}))"""))
```

The date alternation covers both `31 December 2024` (co.uk) and `December 31, 2024` (.com);
a UK-only pattern silently yields `date: ''` for every order on the US site.

## Gotchas

- **Wait ~2s after `wait_for_load()`** before querying cards. `readyState=complete` fires
  before the list renders, exactly as on search results.
- **Trust `.num-orders`, not an empty page.** A year returning zero cards is a signal to
  inspect the DOM, never evidence of "no orders" — an earlier run on this account read
  `year-2024`+ as empty and was wrong. Re-verified 2026-07-29: `year-2010` through
  `year-2026` all extract with `.order-card`, 10 per page.
- **Don't stop on a short page alone.** The final page is legitimately short (7 of 10 on
  `year-2026`), so a short-page-means-done rule is indistinguishable from a page that
  under-rendered. Use `.a-last` plus the count assertion.
- **Digital items** (Kindle, Prime Video) sit alongside physical ones with no reliable
  in-card type marker — classify by title downstream.
- **Long runs**: ~2-3s per page, and grocery-heavy years run 20+ pages. Checkpoint to disk
  after each year and `print(..., flush=True)` — a killed run with buffered stdout loses
  everything.
