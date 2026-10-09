# Flipkart — Gift & Product Shopping (Field-Tested)

Field-tested against flipkart.com on 2026-04-27/28 using `browser-harness` CDP
helpers (`goto_url`, `js`, `click_at_xy`, `type_text`, `capture_screenshot`,
`scroll`, `press_key`, `page_info`).

---

## TL;DR

**Build your search via URL parameters** with price and category filters baked
in. Dismiss the login popup immediately on every new session. For delivery
checks, enter the pincode on the product page — but note that changing pincode
may require login on some pages. Use `__NEXT_DATA__` JSON extraction when
available, fall back to DOM selectors.

---

## Gift Search URL Template

```
https://www.flipkart.com/search?q={query}&marketplace=FLIPKART&p%5B%5D=facets.price_range.from%3DMin&p%5B%5D=facets.price_range.to%3D{max_price}
```

### Example — Gifts for kids under ₹500:

```python
goto_url("https://www.flipkart.com/search?"
         "q=gifts+for+kids+under+10+years"
         "&marketplace=FLIPKART"
         "&p%5B%5D=facets.price_range.from%3DMin"
         "&p%5B%5D=facets.price_range.to%3D500")
```

### Example — Toys under ₹200, sorted by price:

```python
goto_url("https://www.flipkart.com/search?"
         "q=toys+for+kids"
         "&sort=price_asc"
         "&p%5B%5D=facets.price_range.from%3DMin"
         "&p%5B%5D=facets.price_range.to%3D200")
```

---

## URL Parameters Reference

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `q` | string | `gifts+for+kids` | Search query |
| `page` | int | `2` | Pagination (1-based) |
| `sort` | string | `price_asc` | `relevance`, `price_asc`, `price_desc`, `recency_desc`, `popularity` |
| `marketplace` | string | `FLIPKART` | Restrict to Flipkart marketplace |
| `p[]` | string | `facets.price_range.from=Min` | Min price filter |
| `p[]` | string | `facets.price_range.to=500` | Max price filter |
| `p[]` | string | `facets.brand=Samsung` | Brand filter |
| `p[]` | string | `facets.rating=4` | Minimum rating |

**Note:** `p[]` parameters must be URL-encoded as `p%5B%5D=facets.price_range.to%3D500`.

---

## Login Popup — MUST DISMISS FIRST

Flipkart shows a login/signup modal on **every new session**. It blocks all
interaction until dismissed. This is the #1 cause of automation failures.

```python
js("""(()=>{
    var btn = document.querySelector('button._2KpZ6l._2doB4z')
           || document.querySelector('[class*="close-btn"]')
           || document.querySelector('button[aria-label="Close"]');
    if (btn) { btn.click(); return 'closed'; }
    var overlay = document.querySelector('._2fS1Rz, ._3_UOR0');
    if (overlay) { overlay.click(); return 'overlay_dismissed'; }
    document.dispatchEvent(new KeyboardEvent('keydown', {key:'Escape', keyCode:27}));
    return 'escape_sent';
})()""")
```

If the modal persists after JS dismiss, use coordinate click on the ✕ button
(typically top-right of the modal):

```python
click_at_xy(720, 180)  # adjust based on screenshot
```

---

## Delivery Check by Pincode

### On search results page

Flipkart search results show estimated delivery per product. To check delivery
for a specific pincode, you must visit individual product pages.

### On product detail page

The delivery/pincode input is typically near the "Add to Cart" button:

```python
# Step 1: Find and click the pincode input or "Change" link
js("""(()=>{
    var change = [...document.querySelectorAll('span, a')].find(
        e => e.textContent.includes('Change') && e.closest('[class*="pincode"], [class*="delivery"]')
    );
    if (change) { change.click(); return 'clicked change'; }
    var input = document.querySelector('input[placeholder*="pincode"], input[placeholder*="Pincode"]');
    if (input) { input.focus(); input.select(); return 'focused input'; }
    return 'not found';
})()""")

# Step 2: Clear and type new pincode
type_text("560077")
press_key("Enter")

# Step 3: Wait and read delivery estimate
wait(3)
delivery = js("""(()=>{
    var el = document.querySelector('[class*="delivery"], [class*="shipping"]');
    return el ? el.innerText.trim() : 'not found';
})()""")
```

**Gotcha:** Changing pincode on some product pages requires login. If you see a
login prompt after entering pincode, the delivery check won't work without
authentication. In this case, use the default delivery estimate shown on the
search results page.

---

## Product Evaluation Workflow

For gift shopping, evaluate products on these criteria:

```python
# After navigating to a product page:
evaluation = js("""(()=>{
    var price = document.querySelector('div._30jeq3, [class*="selling-price"]')?.innerText?.trim();
    var rating = document.querySelector('div._3LWZlK')?.innerText?.trim();
    var ratingCount = document.querySelector('span._2_R_DZ')?.innerText?.trim();
    var highlights = Array.from(document.querySelectorAll('li._21Ahn-'))
                         .map(e => e.innerText.trim()).filter(Boolean);
    var delivery = document.querySelector('[class*="delivery"]')?.innerText?.trim();
    var inStock = !document.querySelector('[class*="out-of-stock"], [class*="sold-out"]');
    var seller = document.querySelector('[id*="seller"] a, div._3enH42')?.innerText?.trim();
    
    return JSON.stringify({price, rating, ratingCount, highlights, delivery, inStock, seller});
})()""")
```

### Gift suitability checklist:
1. **Price** — within budget (parse `₹` and Indian comma format)
2. **Rating** — prefer 4.0+ with 50+ ratings
3. **Delivery** — check pincode delivery estimate (within required days)
4. **Availability** — ensure "In Stock" / "Add to Cart" visible
5. **Reusability** — read highlights/description for durability indicators

---

## Filtering on Search Results Page

### By price (via sidebar click)

If you need to adjust price after page load:

```python
# Flipkart's price filter is in the left sidebar
# Look for price range inputs
js("""(()=>{
    var inputs = document.querySelectorAll('input[class*="price"], input[name*="price"]');
    return inputs.length + ' price inputs found';
})()""")
```

### By rating (via sidebar click)

```python
js("""(()=>{
    var stars = [...document.querySelectorAll('div, label')].find(
        e => e.textContent.includes('4★') && e.closest('[class*="filter"]')
    );
    if (stars) { stars.click(); return 'clicked 4-star filter'; }
    return 'not found';
})()""")
```

### By availability / delivery speed

Flipkart doesn't always expose delivery speed as a sidebar filter on all pages.
When available, look for "Delivery in X days" checkboxes.

---

## Data Extraction from Search Results

### Strategy 1: `__NEXT_DATA__` (Preferred)

```python
import json

nd_raw = js("document.getElementById('__NEXT_DATA__')?.textContent")
if nd_raw:
    nd = json.loads(nd_raw)
    # Walk the JSON tree to find product arrays
    def find_products(obj, depth=0):
        if depth > 8: return None
        if isinstance(obj, list) and len(obj) > 3:
            if isinstance(obj[0], dict) and any(k in obj[0] for k in ['title','name','price','productId']):
                return obj
        if isinstance(obj, dict):
            for v in obj.values():
                result = find_products(v, depth + 1)
                if result: return result
        return None
    items = find_products(nd)
```

### Strategy 2: DOM Selectors (Fallback)

```python
results = js("""(()=>{
    var links = Array.from(document.querySelectorAll('a[href*="/p/"]'));
    var seen = new Set();
    return links.map(a => {
        var href = a.getAttribute('href');
        if (seen.has(href)) return null;
        seen.add(href);
        var card = a.closest('[data-id]') || a.closest('div[class]');
        if (!card) return null;
        return {
            title: card.querySelector('div._4rR01T, a.IRpwTa, a.s1Q9rs')?.innerText?.trim()
                || a.getAttribute('title')
                || card.querySelector('img')?.getAttribute('alt'),
            price: card.querySelector('div._30jeq3')?.innerText?.trim(),
            rating: card.querySelector('div._3LWZlK')?.innerText?.trim(),
            url: 'https://www.flipkart.com' + href,
        };
    }).filter(Boolean);
})()""")
```

---

## Key Lessons (Field-Tested)

1. **URL-first strategy** — Encode search query, price range, sort order, and
   brand filters directly in the URL. Avoid interacting with sidebar filters
   when possible — they trigger React re-renders that can reset scroll position.

2. **Login popup is mandatory** — Every new browser session hits the login modal.
   Dismiss it before ANY other interaction. If JS dismiss fails, use a
   coordinate click on the close button.

3. **Pincode delivery check has limitations** — Changing delivery pincode on
   product pages may require login. The search results page shows a default
   delivery estimate that works without login.

4. **Image overlay traps** — Product pages have image zoom overlays that can
   capture clicks intended for other elements. If interactions stop working,
   press `Escape` first to dismiss any overlays, then retry.

5. **Indian price format** — Prices use `₹` prefix with Indian grouping:
   `₹1,23,456` = 123,456 INR. Parse: `.replace(/[₹,]/g, '')`.

6. **Wait 3s after `wait_for_load()`** — Product cards load asynchronously via
   React. `readyState=complete` fires before cards render.

7. **Use `new_tab()` for first Flipkart load** — `goto_url()` on the first visit
   can silently fail if the current tab resists navigation.

8. **Flipkart blocks datacenter IPs** — Remote/headless browsers from cloud
   providers (e.g., Playwright Service) get `ERR_CONNECTION_TIMED_OUT`. Flipkart
   only works from residential IPs (local Chrome). For cloud-based automation,
   consider alternative sites like FirstCry for kids' products.

9. **Category browse pages** — Use `sid` parameter for category navigation:
   `https://www.flipkart.com/toys/pr?sid=tng` for toys. Combine with price
   facets for filtered browsing.

10. **Obfuscated class names change frequently** — Flipkart uses Webpack-hashed
    CSS classes (`_4rR01T`, `_30jeq3`). When selectors break, use
    `a[href*="/p/"]` as the stable anchor and walk up to card containers.
    Prefer `__NEXT_DATA__` extraction which is immune to class name changes.
