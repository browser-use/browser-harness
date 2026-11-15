# Shopify Storefronts — Full Product Catalog Extraction

Field-tested against www.allbirds.com, colourpop.com, www.deathwishcoffee.com, www.tentree.com, kith.com, shop.ruggable.com, www.gymshark.com and www.fashionnova.com on 2026-10-23 using a Browser Use cloud browser and plain HTTP (Python `urllib`).

robots.txt (checked 2026-10-23) on all 8 stores allows `/products.json`, `/products/<handle>.js`, `/collections.json`, `/sitemap.xml` and product pages for all user agents; gymshark.com disallows `/collections/*/products*`, which this skill does not use there.

## Quick summary

- Most Shopify stores run on the standard Online Store theme engine and serve the whole public catalog as JSON at `/products.json?limit=250&page=N`. No browser, no auth, no API key. Observed: Allbirds 461 products / 5,288 variants in 2 pages, ColourPop 1,064 in 5 pages, tentree 1,847 / 8,203 variants in 8 pages, Death Wish Coffee 153 in 1 page.
- Pagination ends with an empty `{"products":[]}` page (HTTP 200). `limit` is capped at 250 (asking for 500 returned 250).
- Hard cap: `page * limit` may not exceed 25,000. kith.com returned 250 products on page 100 and `400 {"errors":"Page * Limit exceeds the 25000 limit."}` on page 101. For bigger stores, enumerate handles from `/sitemap.xml` -> `sitemap_products_N.xml` and fetch `/products/<handle>.js`.
- `/products/<handle>.js` adds fields the list endpoint lacks: prices in cents, `barcode`, `inventory_management`, `inventory_policy`, and on some stores `inventory_quantity`.
- Headless Shopify stores (Hydrogen/Oxygen, Next.js) do not serve `/products.json`: fashionnova.com returned 404, gymshark.com returned 403 (CloudFront), in both plain HTTP and an in-page browser `fetch`. Their product pages do embed a schema.org `ProductGroup` in JSON-LD with per-variant SKU, price, currency and availability, and their sitemaps list every product URL.
- Browser fallback: open the storefront and call `fetch('/products.json?...')` from the page (same origin). On allbirds.com this returned the same 250/211/0 pages as plain HTTP.

## Detect which kind of store you have

| Probe | Online Store theme (allbirds, colourpop, tentree, deathwish, kith, ruggable) | Headless (fashionnova, gymshark) |
|---|---|---|
| `GET /products.json?limit=1` | 200 JSON | 404 HTML (fashionnova), 403 CloudFront HTML (gymshark) |
| `GET /products/<handle>.js` | 200 `text/javascript` JSON | 404 HTML |
| `window.Shopify.shop` in the browser | e.g. `weareallbirds.myshopify.com` | `null` |
| `window.ShopifyAnalytics.meta.product` on a product page | present (variant ids, price in cents, sku) | `null` |
| JSON-LD on product page | `ProductGroup` (allbirds) | `ProductGroup` (both) |
| Response header `powered-by` | `Shopify` | `Shopify, Oxygen, Hydrogen` (fashionnova), absent (gymshark) |

## What works

### 1. Full catalog via `/products.json` (plain Python, no browser)

Stdlib only. Paginates until the empty page, reports the 25,000 cap when the 400 body is the cap message (any other 400 raises), retries 429/5xx and network errors with `Retry-After` (seconds or HTTP-date) or exponential backoff, stops if the server asks for more than 120 s, raises when retries run out, dedupes on product `id`, and writes one row per variant.

```python
import json, time, gzip, email.utils, urllib.request, urllib.error
from datetime import datetime, timezone

STORE = "https://www.deathwishcoffee.com"   # any Shopify storefront origin, no trailing slash
UA = "browser-harness-skill-example"        # a truthful client UA; every Online Store store tested returned 200 to it
CAP_MSG = "Page * Limit exceeds the 25000 limit."   # the 400 body seen at the cap; any other 400 raises

def retry_delay(value, attempt):
    """Retry-After is either delay-seconds or an HTTP-date; fall back to exponential backoff. Stop if asked to wait > 120 s."""
    wait = None
    if value:
        try:
            wait = max(0.0, float(value))
        except ValueError:
            try:
                when = email.utils.parsedate_to_datetime(value)
                wait = max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError):
                pass
    if wait is None:
        return 2 ** (attempt + 1)
    if wait > 120:
        raise RuntimeError(f"server asked to wait {wait:.0f} s (Retry-After: {value}); stopping, back off and try later")
    return wait

def get_json(url, tries=4):
    """Return (status, parsed_json_or_error_text). Raises if 429/5xx/network errors persist."""
    for attempt in range(tries):
        if attempt:
            time.sleep(delay)
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    data = gzip.decompress(data)
                try:
                    return r.status, json.loads(data)
                except ValueError:
                    return r.status, "not JSON: " + data[:120].decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                last, delay = f"HTTP {e.code}", retry_delay(e.headers.get("Retry-After"), attempt)
                continue
            body = e.read()
            if e.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            return e.code, body[:200].decode("utf-8", "replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last, delay = repr(e), retry_delay(None, attempt)
    raise RuntimeError(f"{url}: still failing after {tries} tries ({last})")

def fetch_catalog(store, limit=250, pause=1.0):
    products, page = [], 1
    while True:
        status, data = get_json(f"{store}/products.json?limit={limit}&page={page}")
        if status == 400 and CAP_MSG in str(data):
            print(f"hit the 25,000 product cap at page {page}; use the sitemap path for the rest")
            break
        if status != 200 or not isinstance(data, dict):
            raise RuntimeError(f"/products.json not available ({status}): {str(data)[:120]} - headless store or blocked, see browser fallback")
        batch = data.get("products") or []
        if not batch:
            break
        products += batch
        print(f"page {page}: {len(batch)} products")
        page += 1
        time.sleep(pause)
    unique = list({p["id"]: p for p in products}.values())   # rows can shift between pages if the store edits mid-crawl
    if len(unique) != len(products):
        print(f"dropped {len(products) - len(unique)} duplicate products")
    return unique

def variant_rows(p, store):
    images = p.get("images") or []
    by_id = {img["id"]: img["src"] for img in images}
    for v in p.get("variants") or []:
        fi = v.get("featured_image") or {}
        yield {
            "product_id": p["id"], "handle": p["handle"], "title": p["title"],
            "vendor": p.get("vendor"), "product_type": p.get("product_type"), "tags": p.get("tags") or [],
            "variant_id": v["id"], "variant_title": v.get("title"), "sku": v.get("sku") or None,
            "options": [o for o in (v.get("option1"), v.get("option2"), v.get("option3")) if o],
            "price": v.get("price"), "compare_at_price": v.get("compare_at_price"),
            "available": v.get("available"), "grams": v.get("grams"),
            "image": fi.get("src") or by_id.get(fi.get("id")) or (images[0]["src"] if images else None),
            "all_images": [img["src"] for img in images],
            "url": f"{store}/products/{p['handle']}?variant={v['id']}",
        }

products = fetch_catalog(STORE)
rows = [r for p in products for r in variant_rows(p, STORE)]
out = STORE.split("//")[1].replace(".", "_") + "_variants.jsonl"
with open(out, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(len(products), "products,", len(rows), "variants ->", out)
print(json.dumps(rows[0], indent=1)[:900] if rows else "store has no public products")
```

Observed output (trimmed, Death Wish Coffee):

```text
page 1: 153 products
153 products, 436 variants -> www_deathwishcoffee_com_variants.jsonl
{
 "product_id": 7526979862583,
 "handle": "boos-cruise-silicone-cup",
 "title": "Boos Cruise Silicone Cup",
 "vendor": "Silipint",
 "product_type": "Accessories",
 "tags": ["Merch", "OTG"],
 "variant_id": 42450103631927,
 "variant_title": "Default Title",
 "sku": "UCDRSC26",
 "options": ["Default Title"],
 "price": "8.00",
 "compare_at_price": null,
 "available": true,
 "grams": 191,
 "image": "https://cdn.shopify.com/s/files/1/0271/7209/files/DeathWishCoffee_October26_Product_Silipint_SoloCup_Front_Web.jpg?v=1792676155",
 "all_images": [...],
 ...
}
```

Same code against `https://www.allbirds.com` printed `page 1: 250`, `page 2: 211`, then `461 products, 5288 variants`. Each 250-product page took 0.2-1.5 s and was 0.6-4.5 MB.

### 2. One product in detail via `/products/<handle>.js`

Prices here are integer cents. `inventory_quantity` is present on some stores and missing on others (KeyError on tentree), so read it with `.get`.

```python
import json, gzip, urllib.request, urllib.parse

STORE = "https://colourpop.com"
UA = "browser-harness-skill-example"

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        return gzip.decompress(data) if r.headers.get("Content-Encoding") == "gzip" else data

# take a live handle instead of hard-coding one
first = json.loads(get(f"{STORE}/products.json?limit=1"))["products"]
if not first:
    raise SystemExit("store has no public products")
handle = first[0]["handle"]

p = json.loads(get(f"{STORE}/products/{urllib.parse.quote(handle)}.js"))
print(p["title"], "|", p["vendor"], "|", p["type"], "| from", p["price_min"] / 100, "to", p["price_max"] / 100)
for v in p["variants"][:5]:
    print(" ", v["id"], v.get("sku"), v["price"] / 100, "available" if v["available"] else "sold out",
          "qty", v.get("inventory_quantity"), v.get("inventory_policy"), "barcode", v.get("barcode"))
print("images:", ["https:" + u if u.startswith("//") else u for u in p["images"]][:3])
```

Observed output (ColourPop, trimmed):

```text
Colour Me Merry | ColourPop | Advent Calendar 2026 | from 99.0 to 99.0
  42754994372690 Kit-ColourMeMerry 99.0 available qty 3750 deny barcode FG007713
images: ['https://cdn.shopify.com/s/files/1/1338/0845/files/Kit-ColourMeMerry-Hero.jpg?v=1792618081', ...]
```

Observed `inventory_quantity` values: ColourPop 3750, Death Wish 100, Allbirds 0 on sold-out variants, key absent on tentree. Treat it as whatever the store chooses to expose, not as audited stock.

### 3. Stores with more than 25,000 products: sitemap handles + `.js`

`/sitemap.xml` on Online Store themes links `sitemap_products_N.xml?from=..&to=..` files that list every product URL. kith.com had 36 product sitemap files. Enumerate handles, then fetch `.js` per handle at ~1 request/second.

```python
import re, json, time, gzip, urllib.request, urllib.parse

STORE = "https://kith.com"
UA = "browser-harness-skill-example"
SAMPLE = 5   # raise for a full crawl; budget ~1 s per product

def get(url, accept="application/xml"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept, "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
        return (gzip.decompress(data) if r.headers.get("Content-Encoding") == "gzip" else data).decode("utf-8", "replace")

index = get(f"{STORE}/sitemap.xml")
product_maps = [u.replace("&amp;", "&") for u in re.findall(r"<loc>([^<]+)</loc>", index) if "sitemap_products" in u]
handles = []
for sm in product_maps:
    handles += re.findall(r"<loc>[^<]*/products/([^<?/]+)</loc>", get(sm))
    time.sleep(0.5)
handles = list(dict.fromkeys(handles))
print(len(product_maps), "product sitemaps,", len(handles), "product handles")

for h in handles[:SAMPLE]:
    p = json.loads(get(f"{STORE}/products/{urllib.parse.quote(h)}.js", accept="application/json"))
    v = p["variants"][0] if p["variants"] else {}
    print(h, "|", p["vendor"], "|", p["type"], "|", len(p["variants"]), "variants | first", v.get("sku"), (v.get("price") or 0) / 100, v.get("available"))
    time.sleep(1)
```

Observed output (kith.com, trimmed): 35,177 handles, well past the 25,000 ceiling on `/products.json`.

```text
36 product sitemaps, 35177 product handles
just-don-76ers-acid-wash-red | Just Don | Accessories | 1 variants | first 98094272 450.0 False
just-don-miami-hurricanes-orange | Just Don | Accessories | 1 variants | first 98094256 400.0 False
```

### 4. Browser fallback: same-origin `fetch` from the storefront

Use this when plain HTTP is blocked but a normal browser session loads the store. Rows are compacted in the page so each `js()` call returns a small payload.

```python
import json, time

STORE = "https://www.allbirds.com"
CAP_MSG = "Page * Limit exceeds the 25000 limit."   # the 400 body seen at the cap; any other 400 raises

PAGE_JS = """
(async (page) => {
  let r;
  try { r = await fetch('/products.json?limit=250&page=' + page, {headers: {Accept: 'application/json'}}); }
  catch (e) { return JSON.stringify({status: 0, rows: null}); }   // network error
  if (!r.ok) return JSON.stringify({status: r.status, body: (await r.text()).slice(0, 200), rows: null});
  const d = await r.json();
  const rows = [];
  for (const p of d.products || []) for (const v of p.variants || []) rows.push({
    handle: p.handle, title: p.title, vendor: p.vendor, product_type: p.product_type,
    variant_id: v.id, variant_title: v.title, sku: v.sku || null, price: v.price,
    compare_at_price: v.compare_at_price, available: v.available,
    image: (v.featured_image && v.featured_image.src) || (p.images[0] && p.images[0].src) || null});
  return JSON.stringify({status: r.status, products: (d.products || []).length, rows: rows});
})(%d)
"""

new_tab(STORE + "/")
wait_for_load()
print("shop:", js("(window.Shopify && window.Shopify.shop) || null"), "| currency:", js("(window.Shopify && window.Shopify.currency && window.Shopify.currency.active) || null"))

rows, page, retries = [], 1, 0
while True:
    res = json.loads(js(PAGE_JS % page))
    status = res["status"]
    if status in (0, 429) or status >= 500:   # transient: back off and retry the same page
        retries += 1
        if retries > 4:
            raise RuntimeError(f"page {page}: status {status} after 4 retries; catalog incomplete")
        time.sleep(2 ** retries)
        continue
    if status == 400 and CAP_MSG in res.get("body", ""):
        print(f"page {page}: 400 = 25,000 product cap; catalog truncated, use block 3 (sitemaps) for the rest")
        break
    if res["rows"] is None:
        raise RuntimeError(f"page {page}: status {status} {res.get('body', '')[:120]!r} (403/404 = headless or blocked)")
    retries = 0
    if res["products"] == 0:
        break
    rows += res["rows"]
    print("page", page, res["products"], "products")
    page += 1
    time.sleep(1)
print(len(rows), "variant rows; first:", rows[0] if rows else None)
```

Observed output (allbirds.com):

```text
shop: weareallbirds.myshopify.com | currency: USD
page 1 250 products
page 2 211 products
5288 variant rows; first: {'handle': 'mens-runner-nz-tweed', 'title': "Men's Runner NZ Tweed - Dark Grey (Stormy Grey Sole)", 'vendor': 'Allbirds', 'product_type': 'Shoes', ..., 'price': '120.00', 'compare_at_price': None, 'available': False, ...}
```

### 5. Headless stores: sitemap + product-page JSON-LD in the browser

Hydrogen/Next.js storefronts have no `/products.json`, but each product page carries a `ProductGroup` with `hasVariant[]` (sku, offers.price, offers.priceCurrency, offers.availability). Product URLs come from the sitemap, fetched with `http_get`. Runs in the same tab as block 4.

```python
import json, re, time

STORE = "https://www.gymshark.com"
SAMPLE = 3   # product pages to visit; keep pacing >= 2 s per page
UA = {"User-Agent": "browser-harness-skill-example"}   # a truthful client UA

def locs(xml):
    return [u.replace("&amp;", "&") for u in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", xml)]

# sitemaps are plain XML: fetch them over HTTP, not through js() (multi-request js() calls hit its 5 s timeout)
maps = [u for u in locs(http_get(STORE + "/sitemap.xml", headers=UA))
        if "product" in u and not re.search(r"/[a-z]{2}-[A-Z]{2}/", u)]
urls = []
for m in maps:
    urls += [u for u in locs(http_get(m, headers=UA)) if "/products/" in u]
    time.sleep(0.5)
urls = list(dict.fromkeys(urls))

LD_JS = """
JSON.stringify([...document.querySelectorAll('script[type="application/ld+json"]')].flatMap(s => {
  let d; try { d = JSON.parse(s.textContent) } catch (e) { return [] }
  const items = Array.isArray(d) ? d : (d['@graph'] || [d]);
  return items.filter(i => i['@type'] === 'ProductGroup' || i['@type'] === 'Product');
}))
"""

def image_url(img):
    """schema.org image: a URL string, an ImageObject dict, or a list of either."""
    if isinstance(img, list):
        img = img[0] if img else None
    if isinstance(img, dict):
        img = img.get("url") or img.get("contentUrl")
    return img

def to_rows(item, page_url):
    variants = item.get("hasVariant") or [item]
    brand = item.get("brand")
    for v in variants:
        offer = v.get("offers") or item.get("offers") or {}
        if isinstance(offer, list):
            offer = offer[0] if offer else {}
        yield {"title": item.get("name"), "brand": brand.get("name") if isinstance(brand, dict) else brand,
               "group_id": item.get("productGroupID"), "variant_name": v.get("name"), "sku": v.get("sku"),
               "size": v.get("size") if not isinstance(v.get("size"), dict) else v["size"].get("name"),
               "color": v.get("color"), "price": offer.get("price"), "currency": offer.get("priceCurrency"),
               "availability": (offer.get("availability") or "").rsplit("/", 1)[-1] or None,
               "image": image_url(v.get("image") or item.get("image")),
               "url": page_url}

print(len(maps), "product sitemap(s),", len(urls), "product URLs")

rows = []
for url in urls[:SAMPLE]:
    goto_url(url)
    wait_for_load()
    time.sleep(2)
    items = json.loads(js(LD_JS))
    got = [r for it in items for r in to_rows(it, url)]
    print(url.rsplit("/", 1)[-1], "->", len(got), "variants")
    rows += got
print(rows[0] if rows else "no Product JSON-LD found")
```

Observed output (gymshark.com, trimmed):

```text
1 product sitemap(s), 2984 product URLs
gift-card -> 4 variants
gymshark-fit-seamless-cropped-leggings-smokey-grey -> 5 variants
gymshark-1-3-litre-water-bottle-black -> 1 variants
{'title': 'eGift Card', 'brand': 'Gymshark | We Do Gym', 'group_id': '6453246788', 'variant_name': 'eGift Card', 'sku': 'GSGFTCRD-10', 'size': '10.00', 'color': None, 'price': 10, 'currency': 'USD', 'availability': 'InStock', 'image': 'https://cdn.shopify.com/s/files/1/0156/6146/files/Gift_001_Rescale1.png?v=1787226157', 'url': 'https://www.gymshark.com/products/gift-card'}
```

With `STORE = "https://www.fashionnova.com"` the same block printed `1 product sitemap(s), 37840 product URLs` and rows like `{'title': '00 Inferno Layered Mesh Jersey', 'brand': 'Fashion Nova', 'group_id': 'CLML508F', 'sku': 'CLML508F_Olive_S', 'size': 'S', 'color': 'Olive', 'price': '4.98', 'currency': 'USD', 'availability': 'OutOfStock', ...}`. Note `price` is a number on gymshark and a string on fashionnova; cast with `float()`.

The same JSON-LD is server-rendered: a plain HTTP GET of a gymshark product page (2.4 MB HTML) and a fashionnova product page (1.6 MB) both contained the `ProductGroup` block, so for headless stores you can also regex it out of `http_get` HTML without a browser.

## Fields

`/products.json` product object (identical keys on allbirds, colourpop and deathwish, the three inspected key by key):

| Field | Example | Notes |
|---|---|---|
| `id` | `7340901859408` | product id, stable |
| `handle` | `womens-allbirds-flip-flop-dusty-pink` | URL slug, `/products/<handle>` |
| `title` | `Women's Allbirds Flip Flop - Dusty Pink` | |
| `vendor` | `Allbirds` | brand; multi-brand stores have many (ColourPop: ColourPop, Fourth Ray Beauty, SOL Body) |
| `product_type` | `Shoes` | free text, can be `""` (7 Allbirds products) |
| `tags` | `["allbirds::gender => womens", ...]` | list of strings, store-specific conventions |
| `body_html` | `<p>Sun on your feet...` | description HTML |
| `options` | `[{"name":"Size","position":1,"values":["5","6",...]}]` | single-variant products show `Title` / `Default Title` |
| `images[]` | `{id, src, width, height, position, variant_ids}` | `src` is absolute `https://cdn.shopify.com/...` |
| `created_at`, `updated_at`, `published_at` | `2026-09-25T16:58:13-07:00` | ISO with store offset |
| `variants[].id` | | add `?variant=<id>` to the product URL |
| `variants[].title`, `option1..3` | `8.5` | |
| `variants[].sku` | `A12513W050` | can be empty (1 of 1,064 at ColourPop) |
| `variants[].price` | `"25.00"` | string, store currency |
| `variants[].compare_at_price` | `"50.00"` or `null` | original price when on sale |
| `variants[].available` | `true` / `false` | the only stock signal in this endpoint |
| `variants[].featured_image` | `null` or image object | fall back to `images[0]` |
| `variants[].grams`, `requires_shipping`, `taxable`, `position` | | |

Extra in `/products/<handle>.js`: `price`, `price_min`, `price_max`, `compare_at_price_*` (integer cents), `type` (= product_type), `description`, `url`, `media`, `featured_image`, `selling_plan_groups`, and per variant `barcode`, `inventory_management`, `inventory_policy`, `inventory_quantity` (store-dependent), `public_title`, `name`, `options`. Image URLs here are protocol-relative (`//cdn.shopify.com/...`).

`/products/<handle>.json` also returned 200 on allbirds, colourpop and deathwish with Admin-style variant keys (`price_currency`, `inventory_quantity`, `weight_unit`, `fulfillment_service`).

## Gotchas

- Use the store's real public domain. Market-prefixed paths did not work: `/en-ca/products.json` returned 404 on tentree, allbirds and colourpop, and a 301 to a blog page on kith.
- `since_id` is ignored on the storefront endpoint: `?limit=5&since_id=1` returned the same first 5 products as without it. Use `page`.
- Default sort is not by id (Allbirds' list is in neither ascending nor descending id order). If the store edits products mid-crawl, rows can shift between pages; block 1 dedupes on `id` and reports any drops (the full crawls here had 0 duplicates).
- Collections: `/collections.json?limit=250` lists collections with `products_count` (Death Wish: 126), and `/collections/<handle>/products.json` has the same shape. `/collections/all/products.json` returned the full 153 products. Some collections are empty (returned 0).
- Error bodies are gzip-encoded when you send `Accept-Encoding: gzip`; decompress before reading the 400 cap message.
- Not every 400 is the cap: `?page=abc` returned `400 {"errors":"expected String to be a Integer: page"}` on allbirds.com. Blocks 1 and 4 print the cap notice and stop only when the body contains `Page * Limit exceeds the 25000 limit.` and raise with the body for any other 400.
- Unknown handles: `/products/<missing>.js` returns 404.
- No browser User-Agent is needed: the truthful UA `browser-harness-skill-example` got 200 from every Online Store store and from both headless sitemaps. No 429 was observed (roughly 100 requests across 8 stores, paced 0.5-1 s apart), so keep that pace and honor `Retry-After` if one appears.
- Prices are in the storefront's default currency (USD on every store tested; `window.Shopify.currency.active` shows it in the browser). The `.js` endpoint returns cents, the `.json` list returns decimal strings.
- Headless store JSON-LD is per product page, so a full crawl costs one page load per product: fashionnova's product sitemap had 37,840 URLs, gymshark's 2,984. Budget time accordingly and pace at >= 2 s per page.
- Gymshark's sitemap index also lists localized copies (`/es-US/sitemap_products_1.xml`); block 5 filters `xx-YY` locale paths to avoid duplicates.

## What does not work

- `/products.json` on headless stores: fashionnova.com 404 (Hydrogen/Oxygen), gymshark.com 403 from CloudFront. The in-browser `fetch('/products.json')` returned the same 404/403, so the browser is not a workaround there; use JSON-LD.
- `/products/<handle>.js` on headless stores: 404 HTML on both.
- More than 25,000 products through `/products.json`: `page * limit > 25000` returns HTTP 400 (`limit=100&page=251` too). Use sitemaps.
- `limit` above 250 is silently clamped to 250.
- Inventory counts are not reliable: the list endpoint only has `available`; `inventory_quantity` in `.js` is absent on some stores.
