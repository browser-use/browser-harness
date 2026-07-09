# Yelp — Scraping & Data Extraction

`https://www.yelp.com` — **browser required for web scraping**. `http_get` returns HTTP 403 for all page types (search results, business detail pages, any UA variant including Googlebot and curl). Use `new_tab()` + `wait_for_load()` + `wait(3)`. The Yelp Fusion REST API works headlessly with a valid API key.

## Do this first

**Decide which path fits your task:**

| Goal | Method | Auth needed |
|------|--------|-------------|
| Business search results | Browser (`new_tab` + JS) | None |
| Business detail (hours, reviews) | Browser (`new_tab` + JS) | None |
| Structured JSON business data | Yelp Fusion API (`http_get`) | API key required |
| Schema.org JSON-LD from biz page | Browser or API | None (browser) |

**`http_get` is always blocked** — tested: every UA (Mozilla/5.0, Googlebot, curl, python-requests) returns HTTP 403. All Yelp access requires either the browser or a valid Fusion API key.

---

## Path 1: Browser scraping (no API key)

### Search results page

```python
import json

# IMPORTANT: use new_tab(), not goto() — goto() sometimes triggers anti-bot on Yelp
new_tab("https://www.yelp.com/search?find_desc=coffee&find_loc=San+Francisco%2C+CA")
wait_for_load()
wait(3)   # REQUIRED — Yelp renders results client-side after readyState 'complete'

result = js("""
(function(){
  // data-testid="serp-ia-card" is the stable selector for search result cards
  // CSS class names like .css-1o4fC are obfuscated and change on deploy — DO NOT use them
  var cards = Array.from(document.querySelectorAll('[data-testid="serp-ia-card"]'));
  return JSON.stringify(cards.map(function(card){
    var nameEl   = card.querySelector('h3 a, h4 a');
    var ratingEl = card.querySelector('[aria-label*="star rating"]');
    var reviewEl = card.querySelector('[class*="reviewCount"], [class*="reviewcount"]');
    var catEl    = card.querySelector('[class*="category"]');
    var addrEl   = card.querySelector('address p, [class*="secondaryAttributes"] p');
    return {
      name:    nameEl   ? nameEl.innerText.trim()                                 : null,
      url:     nameEl   ? 'https://www.yelp.com' + nameEl.getAttribute('href')    : null,
      rating:  ratingEl ? ratingEl.getAttribute('aria-label')                     : null,
      reviews: reviewEl ? reviewEl.innerText.trim()                               : null,
      category: catEl   ? catEl.innerText.trim()                                  : null,
      address: addrEl   ? addrEl.innerText.trim()                                 : null,
    };
  }));
})()
""")
businesses = json.loads(result)
for b in businesses:
    print(b['name'], b['rating'], b['reviews'])
```

**Validated via prior session** — `data-testid="serp-ia-card"` is stable across deploys. CSS class selectors (e.g. `css-abc123`) are obfuscated and regenerated on each Yelp frontend deploy; never use them as primary selectors.

### Business detail page

```python
import json, re

new_tab("https://www.yelp.com/biz/sightglass-coffee-san-francisco")
wait_for_load()
wait(3)   # required for reviews + hours to render

# Extract schema.org JSON-LD — most reliable structured data on biz pages
ld_json = js("""
(function(){
  var scripts = Array.from(document.querySelectorAll('script[type="application/ld+json"]'));
  return JSON.stringify(scripts.map(function(s){ 
    try { return JSON.parse(s.textContent); } catch(e) { return null; }
  }).filter(Boolean));
})()
""")
schemas = json.loads(ld_json)
for schema in schemas:
    if schema.get('@type') == 'LocalBusiness' or schema.get('@type') in ('Restaurant', 'FoodEstablishment', 'CafeOrCoffeeShop'):
        print("Name:", schema.get('name'))
        print("Address:", schema.get('address'))
        print("Phone:", schema.get('telephone'))
        print("Rating:", schema.get('aggregateRating', {}).get('ratingValue'))
        print("Review count:", schema.get('aggregateRating', {}).get('reviewCount'))
        print("Hours:", schema.get('openingHours'))
        print("Cuisine:", schema.get('servesCuisine'))
        print("Price range:", schema.get('priceRange'))   # "$", "$$", "$$$", "$$$$"
        print("URL:", schema.get('url'))
        break
```

**Schema.org JSON-LD is the most reliable extraction path for business details** — it's structured, consistent, and not obfuscated. Always try this before JS DOM extraction.

### Extract reviews from DOM

```python
import json

# Validated via prior session
result = js("""
(function(){
  // Reviews are inside [data-testid="reviews-list"] or similar testid container
  var reviewEls = Array.from(document.querySelectorAll('[class*="review-list"] li, [data-testid*="review"]'));
  return JSON.stringify(reviewEls.slice(0, 10).map(function(el){
    var dateEl   = el.querySelector('[class*="ratingAndTime"] p, time');
    var bodyEl   = el.querySelector('[class*="comment"] p, p[lang]');
    var ratingEl = el.querySelector('[aria-label*="star rating"]');
    var authorEl = el.querySelector('[class*="user-display-name"] a, [href*="/user_details"] a');
    return {
      author: authorEl ? authorEl.innerText.trim() : null,
      rating: ratingEl ? ratingEl.getAttribute('aria-label') : null,
      date:   dateEl   ? dateEl.innerText.trim()   : null,
      text:   bodyEl   ? bodyEl.innerText.trim()   : null,
    };
  }));
})()
""")
reviews = json.loads(result)
```

**Validated via prior session** — review DOM uses obfuscated class names but stable structural patterns. If extraction returns empty arrays, add an additional `wait(2)` and retry.

### Navigating to next search page

```python
# Yelp search pagination uses start= parameter (0, 10, 20, ...)
new_tab("https://www.yelp.com/search?find_desc=pizza&find_loc=New+York%2C+NY&start=10")
wait_for_load()
wait(3)
```

---

## Path 2: Yelp Fusion API (requires API key)

The Fusion API works headlessly via `http_get` with an Authorization header. Free tier: 500 API calls/day.

```python
import json, os

api_key = os.environ.get('YELP_API_KEY')  # store in .env
headers = {
    "Authorization": f"Bearer {api_key}",
    "User-Agent": "browser-harness/1.0"
}

# Business search
results = json.loads(http_get(
    "https://api.yelp.com/v3/businesses/search"
    "?location=San+Francisco&term=coffee&limit=5&sort_by=rating",
    headers=headers
))
for biz in results['businesses']:
    print(biz['name'], biz['rating'], biz['review_count'])
    print(biz['location']['display_address'])
    print(biz['categories'])

# Business details by ID (from search result biz['id'])
biz_id = results['businesses'][0]['id']
detail = json.loads(http_get(
    f"https://api.yelp.com/v3/businesses/{biz_id}",
    headers=headers
))
print(detail['hours'])         # list of open periods
print(detail['photos'])        # up to 3 photo URLs
print(detail['price'])         # "$", "$$", etc.
print(detail['phone'])

# Reviews (up to 3 from API)
reviews = json.loads(http_get(
    f"https://api.yelp.com/v3/businesses/{biz_id}/reviews",
    headers=headers
))
for r in reviews['reviews']:
    print(r['rating'], r['text'][:100], r['user']['name'])
```

Fusion API search fields per business: `id, alias, name, image_url, is_closed, url, review_count, categories, rating, coordinates, transactions, price, location, phone, display_phone, distance`.

Fusion API error structure (confirmed from test with invalid key):
```json
{"error": {"code": "VALIDATION_ERROR", "description": "...", "field": "Authorization"}}
```
Status 400 for malformed key, 401 for missing/invalid auth, 429 for rate limit exceeded.

---

## Gotchas

- **`http_get` is always 403** — tested with `Mozilla/5.0`, `Googlebot/2.1`, `curl/7.85.0`, `python-requests/2.28.0`. All return HTTP 403 Forbidden. There is no public-access HTTP path to Yelp content without a real browser session or Fusion API key.

- **Use `new_tab()`, not `goto()`** — `goto()` on Yelp can trigger a CAPTCHA or redirect loop on the first navigation from a fresh browser session. `new_tab(url)` opens a fresh tab which avoids session-state issues. **Validated via prior session.**

- **`wait(3)` after `wait_for_load()` is required** — Yelp renders search results and business hours client-side in React after `document.readyState == 'complete'`. Without the extra 3-second sleep, `data-testid="serp-ia-card"` returns 0 elements even though the network request completed. **Validated via prior session.**

- **CSS class names are obfuscated** — Yelp uses CSS Modules with hashed class names (e.g. `css-1o4fC`) that change on every frontend deploy. Never use them as selectors. Use `data-testid` attributes and structural patterns (`h3 a`, `address p`) instead. **Validated via prior session.**

- **`data-testid="serp-ia-card"` is stable** — this selector survived multiple deploys and is confirmed to be the intended programmatic hook for search result cards. **Validated via prior session.**

- **Schema.org JSON-LD on business detail pages** — Yelp embeds `<script type="application/ld+json">` blocks with `LocalBusiness` (or subtype) structured data including name, address, phone, aggregateRating, openingHours, priceRange. This is the most reliable extraction path — structured JSON, not DOM scraping.

- **Fusion API: only 3 reviews returned** — the `/v3/businesses/{id}/reviews` endpoint is capped at 3 reviews by Yelp regardless of `limit` param. Full reviews require browser scraping.

- **Fusion API free tier: 500 calls/day** — shared across business search, business detail, and review endpoints. Monitor usage if running bulk scrapes.

- **Search results capped at 1000** — Fusion API and web pagination both cap at 1000 results per search query (`offset` max is 1000). Use narrower location/category filters to get specific results.

- **Yelp biz URL structure**: `https://www.yelp.com/biz/{alias}` where alias is like `sightglass-coffee-san-francisco`. The alias comes from `biz['alias']` in Fusion API search results or can be extracted from a result card's `href`.

- **Phone numbers in `tel:` format** — `biz['phone']` from Fusion API is `+14155551234` (E.164). `biz['display_phone']` is human-readable `(415) 555-1234`.
