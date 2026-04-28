# Amazon — Product Search & Data Extraction

Field-tested against amazon.com on 2025-04-18 using a logged-in Chrome session.
No CAPTCHA or bot detection was triggered during any test run.

## Navigation

### Direct search URL (fastest, always use this)
```python
goto_url("https://www.amazon.com/s?k=mechanical+keyboard")
wait_for_load()
wait(2)  # dynamic content needs ~2s after readyState=complete
```

### Search box typing (use when you need category filtering)
```python
goto_url("https://www.amazon.com")
wait_for_load()
wait(1)
js("document.querySelector('#twotabsearchtextbox').focus()")
js("document.querySelector('#twotabsearchtextbox').click()")
wait(0.3)
type_text("wireless mouse")
wait(0.3)
press_key("Enter")
wait_for_load()
wait(2)
```

### Direct product page
```python
# URL pattern: /dp/{ASIN}  or  /dp/{ASIN}?th=1 (Amazon may redirect to add ?th=1)
goto_url("https://www.amazon.com/dp/B08Z6X4NK3")
wait_for_load()
wait(2)
```

## Session Gotcha

**Always use `new_tab()` when opening Amazon for the first time in a harness session.**
`goto_url()` can silently fail to navigate if the current tab resists the navigation
(observed when the daemon attached to a different real tab). The safe pattern:

```python
tid = new_tab("https://www.amazon.com/s?k=mechanical+keyboard")
wait_for_load()
wait(2)
```

After that, `goto_url()` works fine within the same Amazon session.

## Search Results Extraction

### Container selector
`[data-component-type="s-search-result"]` — confirmed working, yields ~22 results per page.

### Full extraction (field-tested)
```python
results = js("""
  Array.from(document.querySelectorAll('[data-component-type="s-search-result"]')).map(el => ({
    asin: el.getAttribute('data-asin'),
    title: el.querySelector('h2 span')?.innerText?.trim(),
    price: el.querySelector('.a-price .a-offscreen')?.innerText,
    list_price: el.querySelector('.a-text-price .a-offscreen')?.innerText,
    rating: el.querySelector('[aria-label*="out of 5 stars"]')?.getAttribute('aria-label')?.split(' ')[0],
    reviews: el.querySelector('[aria-label*="ratings"]')?.getAttribute('aria-label'),
    is_sponsored: !!el.querySelector('.puis-sponsored-label-text'),
    url: el.querySelector('h2 a')?.href
  }))
""")
```

### Field notes
- **`asin`**: `data-asin` attribute on the container div — always present, matches the `/dp/{ASIN}` URL.
- **`title`**: `h2 span` works consistently. `h2 a.a-link-normal span` also works.
- **`price`**: `.a-price .a-offscreen` returns the formatted string e.g. `"$69.99"`. Use this, not `.a-price-whole`.
- **`list_price`**: `.a-text-price .a-offscreen` — only present when item is on sale (was/now pricing).
- **`rating`**: Use `aria-label` on `[aria-label*="out of 5 stars"]` — gives `"4.5 out of 5 stars, rating details"`, split on space for the number.
- **`reviews`**: Use `[aria-label*="ratings"]` attribute — gives `"1,514 ratings"`. Do NOT use `.a-size-base.s-underline-text` — that element exists on sponsored results and shows "Xbox" (a cross-sell widget text).
- **`is_sponsored`**: `.puis-sponsored-label-text` is present on sponsored listings; first 2-3 results are usually sponsored.
- **`url`**: `h2 a` href — contains the full `/dp/{ASIN}/...` URL.

## Product Detail Page Extraction

### Confirmed selectors (field-tested on B08Z6X4NK3)
```python
detail = js("""
  ({
    title: document.querySelector('#productTitle')?.innerText?.trim(),
    price: (function() {
      var whole = document.querySelector('.a-price-whole')?.innerText?.replace(/[\\n.]/g,'');
      var frac  = document.querySelector('.a-price-fraction')?.innerText;
      return (whole && frac) ? '$' + whole + '.' + frac
           : document.querySelector('.a-price .a-offscreen')?.innerText || null;
    })(),
    list_price: document.querySelector('.basisPrice .a-offscreen')?.innerText,
    rating: document.querySelector('#acrPopover')?.getAttribute('title'),
    review_count: document.querySelector('#acrCustomerReviewText')?.innerText,
    availability: document.querySelector('#availability span')?.innerText?.trim(),
    brand: document.querySelector('#bylineInfo')?.innerText?.trim(),
    asin: document.querySelector('input[name="ASIN"]')?.value,
    bullet_points: Array.from(document.querySelectorAll('#feature-bullets li span.a-list-item'))
                       .map(e => e.innerText?.trim()).filter(t => t)
  })
""")
```

### Price field notes
- `#priceblock_ourprice` and `#priceblock_dealprice` are **legacy** — they return `null` on modern product pages.
- Construct price from `.a-price-whole` + `.a-price-fraction` (both stripped of `\n` and `.`).
- As a fallback: first `.a-price .a-offscreen` on the page also works (confirmed `$69.99`).
- `list_price` from `.basisPrice .a-offscreen` shows the crossed-out "was" price when a discount exists.

## Best Sellers Page

URL: `https://www.amazon.com/Best-Sellers-{Category}/zgbs/{slug}/`
e.g. `https://www.amazon.com/Best-Sellers-Electronics/zgbs/electronics/`

### DOM structure (2025)
`.zg-item-immersion` **does not exist** — Amazon migrated to CSS modules. Use `[data-asin]` anchored on `[id="gridItemRoot"]`:

```python
goto_url("https://www.amazon.com/Best-Sellers-Electronics/zgbs/electronics/")
wait_for_load()
wait(2)

items = js("""
  Array.from(document.querySelectorAll('[data-asin]')).map(el => {
    var container = el.closest('[id="gridItemRoot"]') || el;
    return {
      asin: el.getAttribute('data-asin'),
      rank: container.querySelector('[class*="zg-bdg-text"]')?.innerText,
      title: container.querySelector('img[alt]')?.getAttribute('alt'),
      price: container.querySelector('.p13n-sc-price, .a-size-base.a-color-price')?.innerText,
      url: 'https://www.amazon.com/dp/' + el.getAttribute('data-asin')
    }
  }).filter(r => r.rank)
""")
```

Note: Title comes from the product image `alt` attribute — the text title elements use obfuscated CSS module class names that change between deployments.

## Pagination

```python
# Get next page URL directly
next_url = js("document.querySelector('.s-pagination-next')?.href")
if next_url:
    goto_url(next_url)
    wait_for_load()
    wait(2)

# Or construct by page number
goto_url("https://www.amazon.com/s?k=wireless+mouse&page=2")
```

## Result Count

```python
count_text = js("document.querySelector('[data-component-type=\"s-result-info-bar\"] h1')?.innerText?.trim()")
# Returns e.g.: '1-16 of over 40,000 results for "wireless mouse"\nSort by:\n...'
# Extract just the count: count_text.split('\n')[0]
```

## CAPTCHA Detection

No CAPTCHA was encountered during testing with a logged-in Chrome session. To detect defensively:

```python
def check_captcha():
    text = js("document.body.innerText.slice(0,500)") or ""
    url  = page_info()["url"]
    return (
        "captcha" in text.lower()
        or "enter the characters" in text.lower()
        or "sorry, we just need to make sure" in text.lower()
        or "captcha" in url.lower()
        or "validateCaptcha" in url
    )

if check_captcha():
    raise RuntimeError("Amazon CAPTCHA hit — stop and notify user")
```

Amazon may serve a CAPTCHA on fresh/anonymous sessions. Using the browser's existing logged-in session avoids this in practice.

## Gotchas

- **`goto_url()` silent failure**: On first visit, use `new_tab(url)` instead. After the tab is on Amazon, `goto_url()` works.
- **`.zg-item-immersion` is gone**: Best Sellers page uses CSS module classes (obfuscated). Use `[data-asin]` + `img[alt]` for title.
- **`.a-size-base.s-underline-text` is unreliable for review count**: On sponsored results it shows unrelated text (e.g. "Xbox"). Use `[aria-label*="ratings"]` instead.
- **`#priceblock_ourprice` is legacy**: Returns `null` on modern pages. Construct from `.a-price-whole` + `.a-price-fraction`.
- **Sponsored results appear first**: First 2-3 results are almost always `is_sponsored: true`. Filter them out with `!el.querySelector('.puis-sponsored-label-text')` when you need organic results.
- **`data-asin` can be empty string on non-product rows**: Filter with `.filter(r => r.asin)`.
- **Price split DOM**: `.a-price-whole` innerText includes a trailing `\n.` — strip it: `.replace(/[\n.]/g,'')`.
- **ASIN from URL**: Use `/dp/([A-Z0-9]{10})/` regex on the product URL. `data-asin` on search results is always the canonical ASIN.
- **`?th=1` redirect**: Amazon appends `?th=1` (and sometimes `?psc=1`) to product URLs after redirect. This is normal — `input[name="ASIN"]` always has the clean ASIN.
- **Wait 2s after `wait_for_load()`**: Amazon search results load the listing cards asynchronously. `readyState=complete` fires before cards render. A hard 2s wait is required.
