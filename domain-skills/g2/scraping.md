# G2 — B2B Software Reviews

Field-tested against g2.com on 2026-04-18.

## Anti-bot verdict: browser required — DataDome blocks every http_get request

`http_get` returns HTTP 403 on every g2.com URL without exception.

Tested URLs (all 403):
- `https://www.g2.com/products/slack/reviews`
- `https://www.g2.com/categories/team-collaboration`
- `https://www.g2.com/products/slack`
- `https://www.g2.com/products/slack/reviews.json`
- `https://www.g2.com/blog/` (and most `www.g2.com/*`)

UAs tested (all blocked): `Mozilla/5.0`, full Chrome 124 macOS, Googlebot.

**Stack:**
- **Primary:** DataDome 5.6.1 (`X-DataDome: protected`, `X-DD-B: 1`). Response mode `rt:'c'` = CAPTCHA challenge. Mode `rt:'i'` = invalid/replayed cookie. The `datadome=...` cookie returned in the 403 response is TLS-fingerprint-bound — replaying it yields `rt:'i'` regardless of headers.
- **Secondary:** Cloudflare CDN (`Server: cloudflare`, `CF-RAY` header present).

DataDome's challenge is **silent** — no CAPTCHA widget appears in a real browser. JS fingerprinting runs post-DOM-ready and resolves automatically. A real Chrome session via CDP passes cleanly.

Pages **not** behind DataDome (safe to `http_get`): `help.g2.com`, `research.g2.com`, `learn.g2.com`, `data.g2.com/api/docs`.

**Use `goto_url()` + `wait()` exclusively. Never use `http_get` for www.g2.com.**

---

## Fastest approach: official vendor API (if you have a key)

G2 provides a public REST API at `https://data.g2.com/api/v1` documented at `https://data.g2.com/api/docs`. This API requires a `Token token=<key>` — obtainable by signing up as a G2 vendor/partner. If you have a key, it is faster and more reliable than browser scraping.

```python
import json, urllib.request

API_KEY = "your_token_here"

def g2_api_get(path, params=""):
    url = f"https://data.g2.com/api/v1/{path}?{params}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Token token={API_KEY}",
        "Content-Type": "application/vnd.api+json",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

# 1. Lookup product UUID by slug
products = g2_api_get("products", "filter[slug]=slack")
product = products["data"][0]
product_id = product["id"]  # UUID, e.g. "ac7841ad-cca8-4125-ac6f-6ef6b5848781"
attrs = product["attributes"]
print(f"{attrs['name']}: {attrs['star_rating']} stars, {attrs['review_count']} reviews")
# star_rating: float 0-5 (overall)
# avg_rating: string e.g. "4.5" (same thing, different format)
# review_count: total published reviews
# public_detail_url: "https://www.g2.com/products/slack/reviews"

# 2. Fetch reviews (survey-responses) for that product
# page[size] max 100, page[number] starts at 1
page = 1
all_reviews = []
while True:
    batch = g2_api_get(
        f"products/{product_id}/survey-responses",
        f"page[number]={page}&page[size]=100"
    )
    reviews = batch["data"]
    if not reviews:
        break
    for r in reviews:
        a = r["attributes"]
        all_reviews.append({
            "id":           r["id"],
            "title":        a["title"],
            "star_rating":  a["star_rating"],    # float 0-5
            "pros":         a["comment_answers"].get("love", ""),  # varies by product
            "cons":         a["comment_answers"].get("hate", ""),
            "user_name":    a["user_name"],
            "country":      a["country_name"],
            "submitted_at": a["submitted_at"],
            "source":       a["review_source"],
        })
    meta = batch.get("meta", {})
    if page >= meta.get("page_count", 1):
        break
    page += 1

print(f"Fetched {len(all_reviews)} reviews")
```

### API filter parameters

**Products** (`GET /api/v1/products`):

| Parameter | Description |
|---|---|
| `filter[slug]` | Exact URL slug (e.g. `slack`) |
| `filter[name]` | Product name (fuzzy) |
| `filter[domain]` | Domain of product website |
| `page[size]` | Default 10, max 100 |
| `page[number]` | Page number |

**Survey-responses** (`GET /api/v1/survey-responses` or `/api/v1/products/{id}/survey-responses`):

| Parameter | Description |
|---|---|
| `filter[submitted_at_gt]` | Min review submission time (RFC 3339) |
| `filter[submitted_at_lt]` | Max review submission time |
| `filter[moderated_at_gt]` | Min publication time |
| `filter[star_rating]` | Filter by star rating |
| `page[size]` | Default 10, max 100 |

**Rate limit:** 100 requests/second. Exceeded = blocked for 60 seconds.

### Survey-response field reference

```
star_rating       float 0-5
title             string (review headline)
comment_answers   dict — keys vary by product's question set
                  common keys: "love" (pros), "hate" (cons), "benefit" (who benefits)
secondary_answers dict — additional structured answers
is_public         bool — reviewer consented to attribution
user_name         string
country_name      string
regions           list[string]
submitted_at      ISO 8601 datetime
moderated_at      ISO 8601 datetime (when published)
review_source     "Organic review..." or incentivized text
votes_up          int — helpful votes
votes_down        int
product_id        UUID
slug              URL slug for the individual review
```

---

## Browser approach (no API key required)

### Setup: open in new tab, wait for DataDome to clear

```python
new_tab("https://www.g2.com/products/slack/reviews")
wait_for_load()
wait(5)  # DataDome JS fingerprinting runs 2-4s after readyState=complete
```

`wait(5)` is mandatory. Extracting before it completes returns empty or blocked content.

Verify you are on the real page, not the DataDome challenge page:

```python
title = js("document.title")
url_now = page_info()["url"]
if "g2.com" not in url_now or "captcha-delivery.com" in url_now:
    wait(5)
    title = js("document.title")
    url_now = page_info()["url"]
    assert "captcha-delivery.com" not in url_now, f"Still on DataDome challenge: {url_now}"
```

---

## URL patterns

| Goal | URL |
|---|---|
| Product reviews | `/products/{slug}/reviews` |
| Product reviews page 2+ | `/products/{slug}/reviews?page=2` |
| Single review | `/products/{slug}/reviews/{review-slug}` |
| Product overview | `/products/{slug}` |
| Category listing | `/categories/{slug}` |
| Category grid | `/categories/{slug}/grids` (disallowed in robots.txt — may not render) |
| Compare | `/compare/{slug1}-vs-{slug2}` |

Product slug is the lowercase hyphenated name from the URL: `slack`, `microsoft-teams`, `notion`, `salesforce-sales-cloud`.

---

## Workflow 1: Product rating and review count

G2 is a **Rails app** (not Next.js) — there is no `__NEXT_DATA__`. Use schema.org microdata attributes.

```python
import json

goto_url("https://www.g2.com/products/slack/reviews")
wait_for_load()
wait(5)

summary = js("""
(function() {
  // Schema.org AggregateRating microdata — most reliable, SSR-rendered
  var aggEl = document.querySelector('[itemtype*="AggregateRating"]');
  var ratingVal = aggEl ? aggEl.querySelector('[itemprop="ratingValue"]') : null;
  var reviewCt  = aggEl ? aggEl.querySelector('[itemprop="reviewCount"]') : null;

  // Fallback: plain text in the header band
  var ratingFb  = document.querySelector('.x-current-rating, [data-next-head] ~ * .fw-bold, .star-rating__stars');
  var countFb   = document.querySelector('.link-color-inherit, .reviews-count');

  // Product name
  var nameEl = document.querySelector('[itemprop="name"], h1.l1');

  return JSON.stringify({
    name:         nameEl   ? nameEl.innerText.trim()          : '',
    rating:       ratingVal ? ratingVal.getAttribute('content') || ratingVal.innerText.trim() : '',
    review_count: reviewCt  ? reviewCt.getAttribute('content')  || reviewCt.innerText.trim()  : '',
    rating_fb:    ratingFb  ? ratingFb.innerText.trim()          : '',
    count_fb:     countFb   ? countFb.innerText.trim()           : '',
  });
})()
""")

data = json.loads(summary)
print("Product:", data["name"])
print("Rating:", data["rating"] or data["rating_fb"])
print("Reviews:", data["review_count"] or data["count_fb"])
```

---

## Workflow 2: Star distribution (rating breakdown)

The rating distribution histogram (5-star, 4-star, …) is rendered server-side with a progress bar or percentage spans.

```python
import json

goto_url("https://www.g2.com/products/slack/reviews")
wait_for_load()
wait(5)

dist = js("""
(function() {
  // G2 renders star distribution in a table or bar list
  // Selector targets the rating breakdown rows
  var rows = document.querySelectorAll(
    '[data-star-rating], .rating-breakdown__row, .star-distribution tr, [class*="StarBreakdown"]'
  );
  var result = {};
  for (var i = 0; i < rows.length; i++) {
    var r = rows[i];
    // Star level: look for a number or aria-label containing the star count
    var starEl = r.querySelector('[data-star], .star-count, [class*="starCount"], td:first-child');
    var pctEl  = r.querySelector('[data-percentage], .pct, [class*="percentage"], td:last-child');
    var countEl = r.querySelector('[data-count], .count-text');
    var star = starEl ? starEl.innerText.trim() : '';
    if (star && /^[1-5]/.test(star)) {
      result[star] = {
        pct:   pctEl   ? pctEl.innerText.trim()   : '',
        count: countEl ? countEl.innerText.trim() : '',
      };
    }
  }
  // If nothing found, try aria-label approach for SVG-based bars
  if (!Object.keys(result).length) {
    var bars = document.querySelectorAll('[aria-label*="star"], [aria-label*="-star"]');
    for (var j = 0; j < bars.length; j++) {
      var lbl = bars[j].getAttribute('aria-label') || '';
      var m = lbl.match(/(\d)-star.*?(\d+\.?\d*)%/i);
      if (m) result[m[1]] = { pct: m[2] + '%', count: '' };
    }
  }
  return JSON.stringify(result);
})()
""")

distribution = json.loads(dist)
for star in ["5", "4", "3", "2", "1"]:
    d = distribution.get(star, {})
    print(f"{star}★: {d.get('pct','?')} ({d.get('count','?')})")
```

If the distribution returns empty, take a screenshot and inspect the actual element structure:

```python
capture_screenshot("/tmp/g2_reviews.png")
# Inspect the image, then adjust selectors above
```

---

## Workflow 3: Extract individual review cards

G2 renders reviews server-side as schema.org `Review` microdata items. Extract before scrolling — a sign-in modal may appear after scrolling past 5 visible reviews.

```python
import json

goto_url("https://www.g2.com/products/slack/reviews")
wait_for_load()
wait(5)

# Dismiss cookie consent banner (GDPR regions)
dismissed = js("""
(function() {
  var btns = [
    '#onetrust-accept-btn-handler',
    'button[id*="accept"]',
    'button[class*="consent"]',
    '.js-cookie-consent-button',
  ];
  for (var i = 0; i < btns.length; i++) {
    var b = document.querySelector(btns[i]);
    if (b && b.offsetParent !== null) { b.click(); return btns[i]; }
  }
  return null;
})()
""")
if dismissed:
    wait(1)

reviews = js("""
(function() {
  // Primary: schema.org Review microdata (SSR-rendered, stable)
  var cards = document.querySelectorAll(
    '[itemtype*="schema.org/Review"], [data-survey-id], .paper--box[data-id]'
  );
  if (!cards.length) {
    // Fallback: G2's newer CSS class patterns
    cards = document.querySelectorAll(
      '[class*="ReviewCard"], [class*="review-card"], article[class*="review"]'
    );
  }
  var out = [];
  for (var i = 0; i < cards.length; i++) {
    var c = cards[i];

    // Overall star rating
    var ratingEl  = c.querySelector('[itemprop="ratingValue"], [class*="starRating"], .x-star-rating');
    var stars     = ratingEl ? (ratingEl.getAttribute('content') || ratingEl.innerText.trim()) : '';

    // Review title
    var titleEl   = c.querySelector('[itemprop="name"], h3[class*="title"], .review-title');
    var title     = titleEl ? titleEl.innerText.trim() : '';

    // Review body (pros/cons are usually separate elements within reviewBody)
    var bodyEl    = c.querySelector('[itemprop="reviewBody"]');
    var body      = bodyEl ? bodyEl.innerText.trim() : '';

    // Explicit pros / cons when rendered as separate sections
    var prosEl    = c.querySelector('[class*="pros"], [data-pros]');
    var consEl    = c.querySelector('[class*="cons"], [data-cons]');
    var pros      = prosEl ? prosEl.innerText.trim() : '';
    var cons      = consEl ? consEl.innerText.trim() : '';

    // Reviewer job title / company
    var jobEl     = c.querySelector('[class*="reviewer-title"], [class*="authorTitle"], [itemprop="jobTitle"]');
    var jobTitle  = jobEl ? jobEl.innerText.trim() : '';

    // Date
    var dateEl    = c.querySelector('time[itemprop="datePublished"], [itemprop="datePublished"]');
    var date      = dateEl ? (dateEl.getAttribute('datetime') || dateEl.innerText.trim()) : '';

    // Survey ID (internal review ID)
    var surveyId  = c.getAttribute('data-survey-id') || c.getAttribute('data-id') || '';

    if (title || pros || body) {
      out.push({ surveyId, stars, title, pros, cons, body, jobTitle, date });
    }
  }
  return JSON.stringify(out);
})()
""")

results = json.loads(reviews)
for r in results:
    print(f"{r['stars']}★ | {r['title']} | {r['jobTitle']} | {r['date']}")
    if r['pros']:  print(f"  + {r['pros'][:120]}")
    if r['cons']:  print(f"  - {r['cons'][:120]}")
    if r['body'] and not r['pros']: print(f"  {r['body'][:200]}")
```

**If `results` is empty:** G2 may have re-skinned. Take a screenshot and inspect the DOM:

```python
capture_screenshot("/tmp/g2_page.png")
# Check element structure with:
structure = js("""
(function() {
  // Dump first article/div with 'review' in its classes
  var el = document.querySelector(
    'article, [class*="review"], [class*="Review"], [data-survey-id]'
  );
  return el ? el.outerHTML.slice(0, 2000) : 'NOT FOUND';
})()
""")
print(structure)
```

---

## Workflow 4: Review pagination

G2 paginates reviews via `?page=N` query parameter (Rails standard).

```python
import json

slug = "slack"
all_reviews = []

for page_num in range(1, 6):  # up to 5 pages (~10 reviews each)
    url = f"https://www.g2.com/products/{slug}/reviews?page={page_num}"
    if page_num == 1:
        goto_url(url)
    else:
        goto_url(url)
    wait_for_load()
    wait(4 if page_num == 1 else 2)  # DataDome only challenges on first page in session

    batch_json = js("""
    (function() {
      var cards = document.querySelectorAll(
        '[itemtype*="schema.org/Review"], [data-survey-id], [class*="ReviewCard"]'
      );
      var out = [];
      for (var i = 0; i < cards.length; i++) {
        var c = cards[i];
        var ratingEl = c.querySelector('[itemprop="ratingValue"]');
        var titleEl  = c.querySelector('[itemprop="name"]');
        var bodyEl   = c.querySelector('[itemprop="reviewBody"]');
        var dateEl   = c.querySelector('time[itemprop="datePublished"]');
        var jobEl    = c.querySelector('[itemprop="jobTitle"]');
        out.push({
          stars:    ratingEl ? (ratingEl.getAttribute('content') || ratingEl.innerText.trim()) : '',
          title:    titleEl  ? titleEl.innerText.trim()   : '',
          body:     bodyEl   ? bodyEl.innerText.trim()    : '',
          date:     dateEl   ? (dateEl.getAttribute('datetime') || dateEl.innerText.trim()) : '',
          jobTitle: jobEl    ? jobEl.innerText.trim()     : '',
        });
      }
      return JSON.stringify(out.filter(r => r.title || r.body));
    })()
    """)

    batch = json.loads(batch_json)
    if not batch:
        break  # no more reviews
    all_reviews.extend(batch)
    print(f"Page {page_num}: {len(batch)} reviews")

print(f"Total: {len(all_reviews)} reviews")
```

---

## Workflow 5: Category product listing

```python
import json

goto_url("https://www.g2.com/categories/team-collaboration")
wait_for_load()
wait(5)

products = js("""
(function() {
  // Product cards in category listing
  var cards = document.querySelectorAll(
    '[itemtype*="SoftwareApplication"], [data-product-id], [class*="ProductCard"], [class*="product-listing"]'
  );
  var out = [];
  for (var i = 0; i < cards.length; i++) {
    var c = cards[i];
    var nameEl   = c.querySelector('[itemprop="name"], h3, h2, [class*="productName"]');
    var ratingEl = c.querySelector('[itemprop="ratingValue"], [class*="rating"]');
    var countEl  = c.querySelector('[itemprop="reviewCount"], [class*="reviewCount"]');
    var linkEl   = c.querySelector('a[href*="/products/"]');
    var imgEl    = c.querySelector('img[itemprop="image"], img[class*="logo"]');
    out.push({
      name:    nameEl   ? nameEl.innerText.trim()   : '',
      rating:  ratingEl ? (ratingEl.getAttribute('content') || ratingEl.innerText.trim()) : '',
      reviews: countEl  ? (countEl.getAttribute('content') || countEl.innerText.trim()) : '',
      url:     linkEl   ? linkEl.href                                                    : '',
      logo:    imgEl    ? imgEl.src                                                      : '',
    });
  }
  return JSON.stringify(out.filter(p => p.name));
})()
""")

listing = json.loads(products)
for p in listing:
    print(f"{p['name']}: {p['rating']}★ ({p['reviews']} reviews)")
```

---

## Detecting DataDome challenge vs. real page

```python
def g2_is_datadome_blocked() -> bool:
    """True if DataDome challenge is still running (not on the real G2 page)."""
    url_now = page_info()["url"]
    title   = js("document.title") or ""
    return (
        "captcha-delivery.com" in url_now
        or "datadome" in url_now.lower()
        or title.strip() == "g2.com"          # DataDome 403 response has title="g2.com"
    )

# Usage
new_tab("https://www.g2.com/products/slack/reviews")
wait_for_load()
wait(5)

if g2_is_datadome_blocked():
    wait(10)  # give DataDome JS extra time to complete
    if g2_is_datadome_blocked():
        capture_screenshot("/tmp/g2_dd_block.png")
        raise RuntimeError("DataDome challenge did not resolve — check screenshot")
```

---

## Handling the sign-in modal

A login modal appears after scrolling past ~5 reviews (triggered by scroll, not on load). Extract all visible review cards **before scrolling**. If you need to scroll:

```python
def dismiss_g2_login_modal():
    """Close G2's sign-in overlay. Safe to call if no modal is present."""
    closed = js("""
    (function() {
      var selectors = [
        '[data-close-modal], [data-modal-close]',
        'button[aria-label="Close"]',
        '[class*="modal"] button[class*="close"]',
        '[class*="Modal"] button[class*="close"]',
        '.modal-dialog .close',
        'button.close',
      ];
      for (var i = 0; i < selectors.length; i++) {
        var btn = document.querySelector(selectors[i]);
        if (btn && btn.offsetParent !== null) {
          btn.click();
          return selectors[i];
        }
      }
      return null;
    })()
    """)
    if closed:
        wait(1)
    return closed
```

Call `dismiss_g2_login_modal()` after any scroll action that might trigger the modal.

---

## Gotchas

- **`http_get` is permanently blocked.** DataDome 5.6.1 intercepts every Python `urllib` / `requests` call. The blocking signal is `X-DataDome: protected` + `X-DD-B: 1` in the response header, response body `rt:'c'` (CAPTCHA). No User-Agent, header set, or cookie replay bypasses it because the `datadome` cookie is bound to the originating TLS fingerprint. Without a real browser's TLS/JA3 fingerprint, the cookie is rejected as `rt:'i'` (invalid).

- **DataDome does NOT block real Chrome via CDP.** The harness connects to Chrome via CDP. Chrome presents a genuine JA3 TLS fingerprint plus browser APIs (canvas, WebGL, Navigator). DataDome's fingerprinting sees a real browser and issues a valid `datadome` cookie silently (no CAPTCHA widget, no user action needed).

- **`wait(5)` minimum after `wait_for_load()`.** DataDome's JS runs 2–4 seconds after `readyState='complete'`. The challenge page title is `"g2.com"` (not "G2 | Software Reviews..."). Checking `document.title` reliably distinguishes challenge from real page.

- **G2 is a Rails app — no `__NEXT_DATA__`.** Unlike Next.js sites, G2 does NOT embed page data in a JSON script tag. All data must be extracted from the rendered HTML or via the official API. G2 uses Hotwire (Turbo + Stimulus) for frontend interactivity.

- **Schema.org microdata is the reliable extraction path.** G2 bakes `itemtype` / `itemprop` attributes into their SSR HTML. These are stable across visual redesigns because they serve SEO purposes. Prefer `[itemprop="ratingValue"]` over class-based selectors.

- **`comment_answers` key names vary by product.** The API's `comment_answers` dict uses question-specific keys that differ across products. Common keys include `"love"` (what do you like best?), `"hate"` (what do you dislike?), `"benefit"` (what benefits?), but these are not guaranteed. Inspect the raw response first.

- **Sign-in modal triggers on scroll.** G2 limits anonymous visitors to the reviews visible in the initial viewport (~5 reviews). Scrolling triggers a login modal. Extract all initial cards before any scroll call. To get more reviews without login, use `?page=2`, `?page=3`, etc. instead of scrolling.

- **Rate limiting on navigation.** G2 does not publish a browser-facing rate limit, but rapid consecutive `goto_url()` calls (< 2s apart) can trigger soft blocks. Use `wait(3)` between product page navigations and `wait(2)` between paginated review pages in the same session.

- **Cloudflare is CDN-only here, not Bot Management.** The `Server: cloudflare` header and `__cf_bm` cookie are standard Cloudflare CDN features (not the Cloudflare Bot Management product). The actual anti-bot protection is DataDome. Do not apply Glassdoor-style CF challenge waits — the DataDome wait is what matters.

- **`data.g2.com` API needs a vendor token.** The API requires `Authorization: Token token=<key>`. The key is obtained by registering as a G2 vendor or partner at `https://www.g2.com/sells`. The 401 response body is `{"errors":[{"status":"401","title":"Bad Credentials"}]}` — no further auth clues.

- **Product UUIDs are required for the API.** The API uses UUIDs (e.g. `ac7841ad-cca8-4125-ac6f-6ef6b5848781`) not slugs for relationship endpoints like `/products/{id}/survey-responses`. Look up the UUID first via `GET /api/v1/products?filter[slug]=slack`.

- **`/categories/*/grids` is disallowed in robots.txt** — may return 403 or empty content even in a browser session.
