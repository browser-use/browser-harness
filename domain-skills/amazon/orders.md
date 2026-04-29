# Amazon — Orders, Search & Tracking

Field-tested against amazon.com on 2026-04-22 using a logged-in Chrome session.

## Order list

```
https://www.amazon.com/gp/your-account/order-history    (legacy, still works)
https://www.amazon.com/your-orders/orders               (current)
```

Both render the same DOM. Default view is the last ~10 orders.

### Order card selector

`.js-order-card` (or `.order-card` / `.a-box-group.order` — all three match). Each card's `innerText` contains a stable, line-broken block:

```
ORDER PLACED
April 20, 2026
TOTAL
$51.57
SHIP TO
<recipient name>
ORDER # 113-0977973-5845019
View order details  View invoice
Arriving April 24 - April 28
<item title>
Buy it again
Track package
...
```

For each card you can pull:
- **Order date**: line after `ORDER PLACED`.
- **Total**: line after `TOTAL` (absent on cancelled orders — those carry `Cancelled` instead).
- **Order #**: regex `ORDER # (\d{3}-\d{7}-\d{7})` against the card text.
- **ETA / status**: the `Arriving …` / `Delivered …` / `Picked up …` / `Cancelled` line.
- **Item title(s)**: line(s) following the ETA.
- **Track-package URL**: the `<a>` whose visible text is exactly `Track package` — its `href` goes straight to the tracking page.

```python
url = js("""
  (() => {
    const cards = document.querySelectorAll('.js-order-card');
    for (const c of cards) {
      if (c.innerText.includes('113-0977973-5845019')) {
        const links = Array.from(c.querySelectorAll('a'));
        const trk = links.find(a => a.innerText.trim().toLowerCase() === 'track package');
        return trk ? trk.href : null;
      }
    }
    return null;
  })()
""")
```

## Order search

**The `?search=` URL parameter alone does not filter the order list.** Hitting `/your-orders/orders?search=calvin+klein` directly returns the unfiltered last ~10 orders.

To actually search, submit the search form:

```python
goto("https://www.amazon.com/your-orders/orders")
wait_for_load()
js("""
  (() => {
    const input = document.querySelector('#searchOrdersInput');
    const form  = input.closest('form');
    input.value = 'calvin klein';
    form.submit();
  })()
""")
wait_for_load()
```

The submit redirects to `/your-orders/search/ref=ppx_yo2ov_dt_b_search?opt=ab&search=<query>`. That URL **does** filter when navigated to directly — the trick is the `opt=ab` param + the `/your-orders/search/` path (not `/your-orders/orders`).

### Search results page DOM differs

The search results page is **not** a list of `.js-order-card` elements. `document.querySelectorAll('.js-order-card').length === 1` regardless of how many matches there are. All matched orders are rendered into a single container as plain text, repeating the block:

```
View order details Ordered on March 25, 2026

<item title>

Buy it again
View your item
```

Extract by walking `body.innerText` from the first occurrence of "calvin klein" (case-insensitive, or your search term). Product links to the matched items are `<a href="/dp/{ASIN}?...">` whose closest enclosing `div` contains the search term — useful for jumping to a product PDP for current pricing.

## Tracking page

URL pattern returned by the order-card "Track package" link:

```
/gp/your-account/ship-track?itemId=...&packageIndex=0&orderId=...&shipmentId=...
```

### Structured selectors are unreliable

Selectors like `[data-test-id="primary-status-eta"]`, `[data-test-id="tracking-number"]`, `[data-test-id="carrier-name"]` all return `null` on this page. The text is rendered into generic containers that don't expose stable test IDs.

**Extract from `body.innerText` anchored at "Arriving":**

```python
chunk = js("""
  (() => {
    const t = document.body.innerText;
    const i = t.indexOf('Arriving');
    return i >= 0 ? t.slice(i, i + 1500) : null;
  })()
""")
```

The chunk has a stable shape:

```
Arriving April 24 - April 28
Shipped
Package arrived at a carrier facility.
Ordered
Shipped
Out for delivery
Delivered
...
Shipped with USPS
Tracking ID: 9300110990513346924683
...
Tracking info provided by <seller name>
```

Pull individual fields with regexes against that chunk:
- ETA: `^Arriving (.+)$` (first line).
- Carrier: `Shipped with (\w+)`.
- Tracking #: `Tracking ID:\s*(\S+)`.
- Seller (if 3P): `Tracking info provided by (.+)`.

The milestone words (`Ordered` / `Shipped` / `Out for delivery` / `Delivered`) are always present as a static legend regardless of how far the package has actually moved — they are not a source of truth for current status. Use the line **above** the legend (e.g. `Package arrived at a carrier facility.`) for the live carrier message.

## Gotchas

- **`?search=` alone does nothing on `/your-orders/orders`.** You must submit the form, or hit the post-submit URL `/your-orders/search/ref=...?opt=ab&search=<query>` directly.
- **Search results page has only one `.js-order-card`.** Don't iterate cards; walk `body.innerText`.
- **Tracking page `data-test-id` selectors are null.** Anchor on the `"Arriving"` line in `body.innerText`.
- **The milestone words on the tracking page are a static legend**, not progress. Read the line above them for the live status.
- **Cancelled orders have no `TOTAL` line.** They carry the literal word `Cancelled` plus `Your order was cancelled. You have not been charged for this order.` instead.
- **Order # regex**: Amazon order numbers are always `\d{3}-\d{7}-\d{7}` (17 digits + 2 hyphens).
