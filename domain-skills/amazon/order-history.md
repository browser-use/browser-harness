# Amazon — Order History Extraction

Field-tested against amazon.co.uk on 2026-07-16 using a logged-in session in the dedicated harness Chrome. Works the same on amazon.com (swap domain).

## Auth

Order history requires login. An unauthenticated visit to any orders URL redirects to
`/ap/signin` (title "Amazon Sign-In") — detect this via `page_info()["url"]` and stop for a
human login rather than typing credentials. A one-time headed login persists in the profile;
no re-challenge was observed on later headless runs from the same profile/IP.

## URL pattern

```python
goto("https://www.amazon.co.uk/your-orders/orders?timeFilter=year-2019&startIndex=0")
```

- `timeFilter` values come from the page's `#time-filter` dropdown: `last30`, `months-3`,
  then `year-YYYY` going back to the account's first year (2010 accounts list every year).
  Read them rather than guessing:
  ```python
  js("JSON.stringify(Array.from(document.querySelectorAll('#time-filter option')).map(o => o.value))")
  ```
- Pagination is `startIndex=0,10,20,...` — 10 orders per page. Stop when a page yields
  fewer than 10 cards (or zero).

## Extraction

Each order renders as an `.order-card`. Titles are the product links inside it; the order
date is loose text matching `\d{1,2} Month \d{4}`:

```python
data = js("""JSON.stringify(Array.from(document.querySelectorAll('.order-card')).map(c => {
  const m = c.innerText.match(/(\\d{1,2}\\s+[A-Za-z]+\\s+\\d{4})/);
  const titles = Array.from(new Set(Array.from(
    c.querySelectorAll('.yohtmlc-product-title, a.a-link-normal[href*="/dp/"], a.a-link-normal[href*="/gp/product/"]')
  ).map(a => a.innerText.trim()).filter(t => t && t.length > 2)));
  return {date: m ? m[1] : '', titles};
}))""")
```

## Traps

- **Recent years render a different (React) layout with no `.order-card` nodes.** On a
  2010-2026 account, `year-2010`…`year-2023` extracted fine; `year-2024`+ returned zero
  cards despite orders existing. If you need recent years, inspect the new DOM first —
  don't interpret empty results as "no orders".
- **~1.5-2s settle after `wait_for_load()`** before querying cards; the list hydrates late.
- **Digital items** (Kindle/Prime Video) appear alongside physical ones; there is no
  reliable in-card type marker — classify by title downstream.
- Long multi-year scrapes are slow (~2-3s/page, grocery-heavy years run 10+ pages).
  Checkpoint results to disk after every year and `print(..., flush=True)` — a killed run
  with buffered stdout loses everything.
