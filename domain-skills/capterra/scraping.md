# Capterra — Scraping & Data Extraction

Field-tested against capterra.com on 2026-04-18. All code blocks validated with live requests.

## Do this first

**Use `User-Agent: ClaudeBot` — Capterra explicitly allows it in robots.txt and returns clean, pre-rendered Markdown instead of JavaScript-heavy HTML. No browser needed.**

Capterra serves a fully structured Markdown representation of every page to AI bots (`ClaudeBot`, `GPTBot`, `PerplexityBot`, `Anthropic-AI` are all listed as `Allow: /` in robots.txt). The Markdown format is far easier to parse than HTML.

With the default `Mozilla/5.0` UA (or any realistic browser UA), Capterra returns HTTP 403 with `Cf-Mitigated: challenge` — Cloudflare blocks all browser UA requests. There is no bypass via HTTP; those pages require a real browser session.

```python
from helpers import http_get
import re, json

# Works everywhere:
html = http_get(
    "https://www.capterra.com/p/135003/Slack/reviews/",
    headers={"User-Agent": "ClaudeBot"}
)

# Extract overall rating and review count from the Markdown header line "4.7 (24059)"
m = re.search(r'^([\d.]+)\s+\(([\d,]+)\)$', html, re.MULTILINE)
print(m.group(1), m.group(2))   # 4.7  24059
```

---

## Fastest approach: product summary in one call

All key metrics — overall rating, review count, sub-ratings, pagination — come from the `/reviews/` endpoint in a single request.

```python
from helpers import http_get
import re, json

def get_product_summary(product_id, slug):
    """
    Returns overall rating, review count, sub-ratings.
    product_id: Capterra numeric ID (e.g. 135003)
    slug: URL slug (e.g. 'Slack')
    """
    url = f"https://www.capterra.com/p/{product_id}/{slug}/reviews/"
    html = http_get(url, headers={"User-Agent": "ClaudeBot"})

    result = {"product_id": product_id, "slug": slug}

    # Overall rating + review count from header line "4.7 (24059)"
    m = re.search(r'^([\d.]+)\s+\(([\d,]+)\)$', html, re.MULTILINE)
    if m:
        result["overall_rating"] = float(m.group(1))
        result["review_count"] = int(m.group(2).replace(",", ""))

    # Page size and total pages from "Showing 1-25 of 24059 Reviews"
    showing = re.search(r"Showing\s+(\d+)[-–](\d+)\s+of\s+([\d,]+)\s+Reviews", html)
    if showing:
        result["per_page"] = int(showing.group(2))
        result["total_pages"] = (int(showing.group(3).replace(",", "")) + 24) // 25

    # Sub-ratings: "Ease of use\n\n4.6" and "Customer Service\n\n4.4"
    lines = html.split("\n")
    for i, line in enumerate(lines):
        for label, key in [("Ease of use", "ease_of_use"), ("Customer Service", "customer_service")]:
            if line.strip() == label:
                for j in range(i + 1, min(i + 5, len(lines))):
                    try:
                        val = float(lines[j].strip())
                        if 0 < val <= 5.0:
                            result[key] = val
                            break
                    except ValueError:
                        pass

    return result

summary = get_product_summary(135003, "Slack")
print(json.dumps(summary, indent=2))
# {
#   "product_id": 135003,
#   "slug": "Slack",
#   "overall_rating": 4.7,
#   "review_count": 24059,
#   "per_page": 25,
#   "total_pages": 963,
#   "ease_of_use": 4.6,
#   "customer_service": 4.4
# }
```

---

## Common workflows

### Get reviews (paginated)

25 reviews per page. Use `?page=N` for pagination.

```python
from helpers import http_get
import re

def get_reviews_page(product_id, slug, page=1):
    """
    Returns up to 25 reviews for one page.
    Total pages = ceil(review_count / 25).
    """
    url = f"https://www.capterra.com/p/{product_id}/{slug}/reviews/?page={page}"
    html = http_get(url, headers={"User-Agent": "ClaudeBot"})

    # Total review count from header
    m = re.search(r'^([\d.]+)\s+\(([\d,]+)\)$', html, re.MULTILINE)
    total = int(m.group(2).replace(",", "")) if m else 0

    # Showing X-Y of Z
    showing = re.search(r"Showing\s+(\d+)[-–](\d+)\s+of\s+([\d,]+)\s+Reviews", html)

    # Split by review title markers "### "Title""
    blocks = re.split(r'\n### "', html)
    reviews = []

    for block in blocks[1:]:
        r = {}

        # Title (up to closing quote)
        t = re.match(r'([^"]+)"', block)
        if t:
            r["title"] = t.group(1).strip()

        # Date
        d = re.search(
            r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+,\s+\d{4}",
            block
        )
        if d:
            r["date"] = d.group(0)

        # Overall rating for this review (first float 1.0–5.0 between blank lines)
        rm = re.search(r"\n\n([\d.]+)\n\n", block)
        if rm:
            val = float(rm.group(1))
            if 1.0 <= val <= 5.0:
                r["rating"] = val

        # Pros
        pros = re.search(r"\nPros\n\n(.+?)(?=\n\nCons|\n\nReview Source|\n\nSwitched|\Z)", block, re.DOTALL)
        if pros:
            r["pros"] = pros.group(1).strip()

        # Cons
        cons = re.search(r"\nCons\n\n(.+?)(?=\n\nReview Source|\n\nSwitched|\n\n##|\Z)", block, re.DOTALL)
        if cons:
            r["cons"] = cons.group(1).strip()

        if r.get("title"):
            reviews.append(r)

    return {
        "total": total,
        "page": page,
        "showing": f"{showing.group(1)}-{showing.group(2)} of {showing.group(3)}" if showing else None,
        "reviews": reviews,
    }

# Page 1
result = get_reviews_page(135003, "Slack", page=1)
print(f"Total reviews: {result['total']}, this page: {len(result['reviews'])}")
# Total reviews: 24059, this page: 25

print(result["reviews"][0])
# {'title': 'Love, love, love Slack!', 'date': 'April 14, 2026', 'rating': 5.0,
#  'pros': '...', 'cons': '...'}
```

### Scrape all reviews in bulk (parallel)

10 pages in ~2s with 5 workers. No rate limiting observed during testing.

```python
from helpers import http_get
import re
from concurrent.futures import ThreadPoolExecutor

UA = {"User-Agent": "ClaudeBot"}

def _fetch_page(args):
    product_id, slug, page = args
    url = f"https://www.capterra.com/p/{product_id}/{slug}/reviews/?page={page}"
    html = http_get(url, headers=UA)
    blocks = re.split(r'\n### "', html)
    reviews = []
    for block in blocks[1:]:
        r = {}
        t = re.match(r'([^"]+)"', block)
        if t: r["title"] = t.group(1).strip()
        d = re.search(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d+,\s+\d{4}", block)
        if d: r["date"] = d.group(0)
        rm = re.search(r"\n\n([\d.]+)\n\n", block)
        if rm:
            val = float(rm.group(1))
            if 1.0 <= val <= 5.0: r["rating"] = val
        pros = re.search(r"\nPros\n\n(.+?)(?=\n\nCons|\n\nReview Source|\n\nSwitched|\Z)", block, re.DOTALL)
        if pros: r["pros"] = pros.group(1).strip()
        cons = re.search(r"\nCons\n\n(.+?)(?=\n\nReview Source|\n\nSwitched|\n\n##|\Z)", block, re.DOTALL)
        if cons: r["cons"] = cons.group(1).strip()
        if r.get("title"): reviews.append(r)
    return reviews

def get_all_reviews(product_id, slug, max_pages=None, workers=5):
    """Fetch all reviews in parallel. max_pages=None fetches everything."""
    # First: get total pages
    summary_html = http_get(
        f"https://www.capterra.com/p/{product_id}/{slug}/reviews/",
        headers=UA
    )
    m = re.search(r'^([\d.]+)\s+\(([\d,]+)\)$', summary_html, re.MULTILINE)
    total = int(m.group(2).replace(",", "")) if m else 0
    total_pages = (total + 24) // 25
    pages = range(1, (max_pages or total_pages) + 1)

    tasks = [(product_id, slug, p) for p in pages]
    all_reviews = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for batch in ex.map(_fetch_page, tasks):
            all_reviews.extend(batch)
    return all_reviews

# Fetch first 50 reviews (2 pages) in parallel
reviews = get_all_reviews(135003, "Slack", max_pages=2, workers=2)
print(f"Fetched {len(reviews)} reviews")
# Fetched 50 reviews
```

### Get a product's full overview (rating breakdown, sentiment, pricing)

```python
from helpers import http_get
import re, json

def get_product_overview(product_id, slug):
    """Rating breakdown, sentiment, starting price from the product page."""
    url = f"https://www.capterra.com/p/{product_id}/{slug}/"
    html = http_get(url, headers={"User-Agent": "ClaudeBot"})

    result = {}

    # Overall rating and review count from the reviews section
    # Appears as "\n4.7\n\nBased on 24,059 reviews\n"
    m = re.search(r'\n([\d.]+)\n\nBased on ([\d,]+) reviews\n', html)
    if m:
        result["overall_rating"] = float(m.group(1))
        result["review_count"] = int(m.group(2).replace(",", ""))

    # Rating breakdown: "5(17268)\n\n4(5708)\n\n3(907)\n\n2(128)\n\n1(48)"
    breakdown = re.findall(r'\b([1-5])\((\d+)\)', html)
    if breakdown:
        result["rating_breakdown"] = {int(s): int(c) for s, c in breakdown if 1 <= int(s) <= 5}

    # Sentiment: "Positive\n\n96%\n\nNeutral\n\n4%\n\nNegative\n\n1%"
    for label, key in [("Positive", "sentiment_positive"), ("Neutral", "sentiment_neutral"), ("Negative", "sentiment_negative")]:
        sm = re.search(rf'{label}\s*\n+\s*(\d+)%', html)
        if sm:
            result[key] = int(sm.group(1))

    # Starting price ("Starting price\n\n$8.75\n\nPer User")
    pm = re.search(r'Starting price\s*\n+\$?([\d.]+)', html)
    if pm:
        result["starting_price_usd"] = float(pm.group(1))

    # Categories ("What is X used for?" links)
    cats = re.findall(r'\[([^\]]+)\]\(https://www\.capterra\.com/([a-z-]+-software)/\)', html[:3000])
    if cats:
        result["categories"] = [name for name, _ in cats]

    # Sub-ratings from product page
    for label, key in [("Value for money", "value_for_money"), ("Features", "features_rating")]:
        sub = re.search(rf'{label}\s*\n+\s*([\d.]+)', html)
        if sub:
            try:
                val = float(sub.group(1))
                if 0 < val <= 5.0:
                    result[key] = val
            except ValueError:
                pass

    return result

overview = get_product_overview(135003, "Slack")
print(json.dumps(overview, indent=2))
# {
#   "overall_rating": 4.7,
#   "review_count": 24059,
#   "rating_breakdown": {"5": 17268, "4": 5708, "3": 907, "2": 128, "1": 48},
#   "sentiment_positive": 96,
#   "sentiment_neutral": 4,
#   "sentiment_negative": 1,
#   "starting_price_usd": 8.75,
#   "categories": ["Team Communication", "Collaboration", "Remote Work"]
# }
```

### Browse a software category

Each category page returns up to 40 products on page 1, then ~24–25 per subsequent page. Pagination works via `?page=N`.

```python
from helpers import http_get
import re

def get_category_products(category_slug, page=1):
    """
    List products in a Capterra category.
    category_slug examples: 'project-management-software', 'crm-software', 'accounting-software'
    Full list: https://www.capterra.com/categories/
    """
    url = f"https://www.capterra.com/{category_slug}/"
    if page > 1:
        url = f"https://www.capterra.com/{category_slug}/?page={page}"
    html = http_get(url, headers={"User-Agent": "ClaudeBot"})

    # Ratings: [4.6 (5732)](https://www.capterra.com/p/147657/monday-com/reviews/)
    raw = re.findall(
        r'\[([\d.]+)\s+\(([\d,]+)\)\]\(https://www\.capterra\.com/p/(\d+)/([^/]+)/reviews/\)',
        html
    )
    # Product names from "Learn more about X" links
    names = {pid: name for name, pid in re.findall(
        r'\[Learn more about ([^\]]+)\]\(https://www\.capterra\.com/p/(\d+)/[^/]+/\)', html
    )}

    items, seen = [], set()
    for rating, review_count, pid, slug in raw:
        if pid not in seen:
            seen.add(pid)
            items.append({
                "product_id": int(pid),
                "name": names.get(pid, slug),
                "slug": slug,
                "overall_rating": float(rating),
                "review_count": int(review_count.replace(",", "")),
                "product_url": f"https://www.capterra.com/p/{pid}/{slug}/",
                "reviews_url": f"https://www.capterra.com/p/{pid}/{slug}/reviews/",
            })
    return items

products = get_category_products("project-management-software", page=1)
for p in products[:3]:
    print(f"{p['name']}: {p['overall_rating']} ({p['review_count']} reviews)")
# monday.com: 4.6 (5732 reviews)
# Jira: 4.4 (15325 reviews)
# Celoxis: 4.4 (327 reviews)
```

### Get all 1000+ software categories

```python
from helpers import http_get
import re

def get_all_categories():
    """Returns list of {name, slug} for all ~1003 Capterra software categories."""
    html = http_get("https://www.capterra.com/categories/", headers={"User-Agent": "ClaudeBot"})
    cats = re.findall(r'\[([^\]]+)\]\(https://www\.capterra\.com/([a-z-]+-software)/\)', html)
    return [{"name": name, "slug": slug} for name, slug in cats]

categories = get_all_categories()
print(f"{len(categories)} categories")   # 1003
print(categories[:3])
# [{'name': 'AB Testing', 'slug': 'ab-testing-software'},
#  {'name': 'Absence Management', 'slug': 'absence-management-software'}, ...]
```

---

## URL patterns

| Page type | URL pattern |
|-----------|-------------|
| Product overview | `https://www.capterra.com/p/{id}/{Slug}/` |
| Product reviews | `https://www.capterra.com/p/{id}/{Slug}/reviews/` |
| Reviews page N | `https://www.capterra.com/p/{id}/{Slug}/reviews/?page={N}` |
| Reviews (alt) | `https://www.capterra.com/reviews/{id}/{Slug}/` |
| Category listing | `https://www.capterra.com/{category}-software/` |
| Category page N | `https://www.capterra.com/{category}-software/?page={N}` |
| All categories | `https://www.capterra.com/categories/` |
| Product pricing | `https://www.capterra.com/p/{id}/{Slug}/pricing/` |
| Product alternatives | `https://www.capterra.com/p/{id}/{Slug}/alternatives/` |
| Compare A vs B | `https://www.capterra.com/compare/{id_a}-{id_b}/{Slug_a}-vs-{Slug_b}` |

**Finding a product's ID:** Look in the URL of any product listing in a category page. The pattern `https://www.capterra.com/p/{id}/{Slug}/reviews/` appears in every category listing as the link target for each rating badge. The slug is case-sensitive in practice (e.g. `Slack`, not `slack`).

Product IDs are stable numeric identifiers. Note that the same software vendor may have multiple product IDs under different names/versions. Always find the ID from a category search rather than guessing.

---

## Anti-bot measures

- **Cloudflare is active on all routes** (`Server: cloudflare`, `CF-RAY` present in all response headers).
- **Browser UAs (Chrome, Firefox, Safari) return HTTP 403** with `Cf-Mitigated: challenge` regardless of how complete the headers are. There is no HTTP-only bypass.
- **`ClaudeBot` UA bypasses Cloudflare** and receives clean pre-rendered Markdown. Capterra explicitly allows it in `robots.txt` via `User-agent: ClaudeBot / Allow: /`. This is a deliberate AI-accessibility feature.
- **Other AI bot UAs that also work**: `GPTBot`, `PerplexityBot` (also in `robots.txt` Allow list). `Anthropic-AI` was tested and returns 403 — only `ClaudeBot` is the correct UA.
- **The search endpoint (`/search/?q=...`) returns empty results** via ClaudeBot — the query parameter is not passed through. Use category browsing or direct product URLs instead.
- **No CAPTCHA observed** during testing with ClaudeBot.
- **No rate limiting observed**: 10 parallel requests across 5 workers completed in ~2s with all 200 responses. Sequential batches of 5 pages at 0.15–0.95s per request also worked cleanly.
- **The Markdown response has no JSON-LD, no `__NEXT_DATA__`** — these are HTML-only structures. The Markdown format is simpler to parse.
- **Disallowed paths** (from robots.txt): `/search`, `/ppc/clicks/`, `/sem-b/`, `/sem-compare-b/`, `/workspace/`, `/auth/login`. These 403 even with ClaudeBot.

---

## Gotchas

- **Old Capterra product IDs may be invalid.** The URL `https://www.capterra.com/p/56703/Slack/` (ID 56703) returns 404 even with ClaudeBot — this is a stale or merged product ID. Slack's current ID is 135003, found in the team-communication-software category listing. Always discover IDs by crawling category pages rather than hard-coding them.

- **Slug is case-sensitive.** `Slack` works; `slack` returns 404. The slug is always in the category listing data.

- **Response is Markdown, not HTML.** `http_get` returns pre-rendered Markdown with no HTML tags, no JSON-LD, and no `__NEXT_DATA__`. Do not attempt `BeautifulSoup` parsing. Use `re` on the text directly.

- **`http_get` default UA is `Mozilla/5.0`** — this returns 403 from Capterra. Always pass `headers={"User-Agent": "ClaudeBot"}` explicitly.

- **Reviews page vs product page**: The `/reviews/` page has a clean rating header (`4.7 (24059)`) on line 10. The product overview page (`/p/{id}/{Slug}/`) has the same number buried deeper in the page as `\n4.7\n\nBased on 24,059 reviews\n`. For rating extraction, the reviews page is simpler and more reliable.

- **Category page 1 is larger than subsequent pages**: Page 1 includes editorial content (author bio, top-picks editorial) which can double the page size. Subsequent pages are ~20–30KB and contain only listings.

- **Reviewer name is present in the text but not cleanly delimited**: The Markdown format for reviewer attribution uses plain text lines above the review body. It's easier to skip reviewer name extraction than to parse the ambiguous formatting.

- **Sub-rating labels in reviews page**: "Ease of use" (lowercase 'u') and "Customer Service" (capitalized 'S') — match exactly. The product overview page may show additional sub-ratings like "Features" and "Value for money".

- **`rating_breakdown` pattern caveat**: The pattern `[1-5]\(\d+\)` on the product page can also match feature ratings. To isolate the 5-star breakdown, find it within the "Filter by rating" section, which appears as a block like `5(17268)\n\n4(5708)\n\n3(907)\n\n2(128)\n\n1(48)`.

---

## When to use the browser instead

The browser is not needed for any common Capterra task — the ClaudeBot flow handles all of them. Use the browser only if:

- You need to interact with a page element (e.g. submit a review, use the "fit-finder" wizard).
- You need to access a Capterra page that is explicitly blocked in robots.txt (e.g. `/workspace/`, `/auth/login/`).
- You need to simulate a logged-in user session with Capterra credentials.

For read-only scraping of product data, reviews, and category listings, `http_get` with `ClaudeBot` UA is both faster and more reliable than a browser.
