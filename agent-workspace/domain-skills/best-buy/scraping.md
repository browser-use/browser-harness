# Best Buy — Product Search, Prices, Availability & Specs

Field-tested against www.bestbuy.com on 2026-10-23 using a Browser Use cloud browser (plain HTTP was tried too and does not work, see below).

robots.txt (read in the browser on 2026-10-23; plain HTTP to it timed out like the rest of the site) does not disallow `/site/searchpage.jsp`, `/site/<sku>.p` or `/product/<slug>/<code>` for `User-agent: *`, but disallows any URL containing `cp=1` (so `cp=1` and `cp=10`-`19`), `cp=20`, or `cp=6` through `cp=9`. The search block therefore loads page 1 with no `cp` parameter, pages 2-5 with `cp=2` to `cp=5`, and stops there: pages 6-20 are disallowed. The product block uses `/site/<sku>.p?skuId=<sku>`, its redirect to `/product/<slug>/<code>`, and a search URL without `cp`.

## Quick summary

- **Plain HTTP is blocked** (no status: curl's default HTTP/2 request failed with a stream error, exit 92; HTTP/1.1 and `http_get` hit a 20 s read timeout with zero bytes); this skill uses a normal browser session. The official `api.bestbuy.com` returns `403 {"errorMessage":"We were unable to locate your API Key."}` without a key; if you can register a key at developer.bestbuy.com, that API is the stable source (see "What does not work").
- **Use a real browser.** Search results (`/site/searchpage.jsp?st=<query>` for page 1, `&cp=<2-5>` for pages 2-5) and product pages render normally in a cloud browser, logged out, no CAPTCHA seen.
- **Search results are client-rendered and lazy.** Cards get prices only after they scroll into view, so scroll the page, then read the DOM cards (`.product-list-item[data-product-id]`). 20-24 cards per page, sponsored cards included.
- **Product pages carry JSON-LD `Product`** (SKU, model, brand, price, availability, rating, review count, open-box offers). Full specs sit behind the "See all specifications" button; click it and read the sheet.
- **The blocks need a visible tab.** A hidden (background) tab stayed on "Loading..." skeletons, also with focus emulation and with `document.visibilityState` faked to `visible`; `activate_tab(current_tab())` fixed it. `new_tab()` opens a hidden tab, so run the blocks in a dedicated or cloud browser with `FOREGROUND_TAB = True`, which brings the tab to the front. The flag defaults to `False` so that on your own Chrome a hidden tab raises a clear error instead of taking over the window you are using.

---

## What works: search results across pages

Title, SKU, price, sale price, rating, review count, availability and URL for result pages 1-5 of `gaming laptop`, the pages robots.txt allows. Self-contained; opens one new tab.

```python
# NEEDS A VISIBLE TAB: Best Buy never renders a hidden (background) tab, and new_tab() opens a
# hidden one. Run this in a dedicated or cloud browser with FOREGROUND_TAB = True, which brings
# the tab to the front. Left False, a hidden tab raises instead of taking over your window.
FOREGROUND_TAB = False

import json, math, time
from urllib.parse import quote_plus, urlparse, parse_qs

EXTRACT_CARDS = r"""(() => {
  const money = s => { const m = (s || '').match(/\$([\d,]+\.\d{2})/); return m ? parseFloat(m[1].replace(/,/g, '')) : null; };
  const txt = (el, sel) => { const e = el.querySelector(sel); return e ? e.innerText.trim() : null; };
  return [...document.querySelectorAll('.product-list-item[data-product-id]')].map(card => {
    const h3 = card.querySelector('h3');
    const link = h3 ? h3.closest('a') : null;
    const rnr = txt(card, '[data-testid="rnr-stats-link"] p') || '';
    const rm = rnr.match(/rating,? ([\d.]+) out of 5 stars with ([\d,]+) review/i);
    const price = money(txt(card, '[data-testid="price-block-customer-price"]'));
    const regular = money(txt(card, '[data-testid="price-block-regular-price"]'));
    // plp-add-to-cart-<sku>-label, plp-sold-out-<sku>-label, plp-unavailable-<sku>-label, plp_openbox-unavailable-<sku>-label
    const btn = card.querySelector('[data-testid^="plp"][data-testid$="-label"]');
    const button = btn ? btn.innerText.trim() : null;
    const status = button === 'Add to cart' ? 'in_stock' : button === 'Sold Out' ? 'sold_out'
      : button === 'Unavailable' ? 'unavailable' : /High demand product/.test(card.innerText) ? 'high_demand'
      : button ? button.toLowerCase() : null;
    return {
      sku: card.getAttribute('data-product-id'),
      title: h3 ? (h3.getAttribute('title') || h3.innerText).trim() : null,
      url: link ? link.href.split('?')[0] : null,
      price,                       // what the customer pays now
      regular_price: regular,      // "Comp. Value", only shown when discounted
      on_sale: regular !== null && price !== null && price < regular,
      savings: txt(card, '[data-testid="price-block-total-savings-text"]'),
      rating: rm ? parseFloat(rm[1]) : null,
      review_count: rm ? parseInt(rm[2].replace(/,/g, ''), 10) : (/Not yet reviewed/i.test(card.innerText) ? 0 : null),
      availability: status,
      button,
      pickup: txt(card, '[data-testid^="plp-pickup-messaging-"]'),
      shipping: txt(card, '[data-testid^="plp-shipping-messaging-"]'),
      sponsored: !!card.closest('li.slContainer'),
    };
  });
})()"""

def safe_js(expr, tries=6, deadline=None):
    # The page's main thread is busy for a few seconds after navigation and
    # Runtime.evaluate can time out; retry instead of failing, but not past the deadline.
    for _ in range(tries):
        try:
            return js(expr)
        except (RuntimeError, TimeoutError):
            if deadline is not None and time.monotonic() + 2 > deadline:
                break
            wait(2)
    return None

class NotReady(RuntimeError):
    """The page did not render, or showed an error, in this attempt."""

def nav(url, href_ok, timeout):
    # Best Buy keeps the main thread busy; give Page.navigate more than the 5 s default.
    # A tab can hang mid-navigation: stop it and navigate once more (a second timeout raises).
    end = time.monotonic() + timeout
    left = lambda: max(1, min(30, end - time.monotonic()))  # no CDP wait runs past the caller's deadline
    # Record where the tab was and mark that document, so a reload of the same URL is told apart.
    before = safe_js("(window.__bhOldDoc = true, location.href)", tries=1)
    try:
        cdp("Page.navigate", url=url, _response_timeout=left())
    except TimeoutError:
        cdp("Page.stopLoading", _response_timeout=left())
        cdp("Page.navigate", url=url, _response_timeout=left())
    here = None
    while time.monotonic() < end:  # read nothing until the tab is on a new document at the requested URL
        wait(1)
        here = safe_js("({href: location.href, old: !!window.__bhOldDoc,"
                       " status: (performance.getEntriesByType('navigation')[0] || {}).responseStatus})", tries=1) or here
        if here and not here["old"] and href_ok(here["href"]):
            if here["status"] in (403, 429):  # a block: stop, never retry
                raise RuntimeError(f"HTTP {here['status']} at {here['href']}: blocked, stop and back off")
            return here["href"]
    raise NotReady(f"navigation to {url} not confirmed within {timeout:.0f} s "
                   f"(was {before}, now {here['href'] if here else 'unreadable'})")

def ensure_visible():
    if safe_js("document.visibilityState") == "visible":
        return
    if not FOREGROUND_TAB:
        raise RuntimeError("tab is hidden and Best Buy does not render hidden tabs: run this in a dedicated or "
                           "cloud browser with FOREGROUND_TAB = True (brings the tab to the front), or show the tab yourself")
    activate_tab(current_tab())

# robots.txt (User-agent: *) disallows any URL containing cp=1 (cp=1, cp=10-19), cp=20 and cp=6..9.
# Page 1 is the URL without cp; pages 2-5 are the only other pages it allows in sequence.
ROBOTS_PAGES = (1, 2, 3, 4, 5)

def search_url(query, page):
    if page not in ROBOTS_PAGES:
        raise ValueError(f"page {page}: robots.txt disallows cp={page} for User-agent: *")
    url = f"https://www.bestbuy.com/site/searchpage.jsp?st={quote_plus(query)}"
    return url if page == 1 else f"{url}&cp={page}"

def search_href_ok(query, page):
    def ok(href):  # Best Buy may add id=pcat17071 and reorder the parameters; st and cp must match
        u = urlparse(href)
        q = parse_qs(u.query)
        return (u.netloc == "www.bestbuy.com" and u.path == "/site/searchpage.jsp"
                and q.get("st") == [query] and q.get("cp", ["1"]) == [str(page)])
    return ok

def load_search_page(query, page, deadline):
    def check_time(step):
        if time.monotonic() > deadline:
            raise NotReady(f"out of time while {step}")
    nav(search_url(query, page), search_href_ok(query, page), timeout=min(45, deadline - time.monotonic()))
    for _ in range(20):  # wait until product titles have rendered
        wait(1.5)
        if (safe_js("document.querySelectorAll('.product-list-item h3').length", deadline=deadline) or 0) > 0:
            break
        # The block never asks for a page past the end (see PAGE_SIZE), so this is an error page.
        if safe_js("document.body.innerText.includes('unable to display products')", deadline=deadline):
            raise NotReady("Best Buy showed \"unable to display products\"")
        check_time("waiting for product titles")
    else:
        raise NotReady("no product titles rendered in 30 s")
    # Cards and price blocks render lazily when they scroll into view.
    for _ in range(25):
        check_time("scrolling")
        safe_js("window.scrollBy(0, 800)", deadline=deadline)
        wait(0.6)
        if safe_js("window.innerHeight + window.scrollY >= document.body.scrollHeight - 50", deadline=deadline):
            break
    for _ in range(3):  # revisit cards whose title or price block has not rendered yet
        missing = safe_js("""[...document.querySelectorAll('.product-list-item[data-product-id]')]
            .filter(c => !c.querySelector('h3') || !c.querySelector('[data-testid="price-block-customer-price"]'))
            .map(c => c.getAttribute('data-product-id'))""", deadline=deadline) or []
        if not missing:
            break
        for sku in missing:
            check_time("revisiting unrendered cards")
            safe_js(f"document.querySelector('.product-list-item[data-product-id=\"{sku}\"]')?.scrollIntoView({{block: 'center'}})", deadline=deadline)
            wait(0.8)
        wait(1.5)
    cards = safe_js(EXTRACT_CARDS, deadline=deadline)
    if not cards:
        raise NotReady("no product cards could be read")
    # A card shell that never hydrated has a SKU but no h3 or link; sponsored cards render both too.
    shells = [c["sku"] for c in cards if not (c["sku"] and c["title"] and c["url"])]
    if shells:
        raise NotReady(f"{len(shells)} of {len(cards)} cards still lack SKU, title or URL: {shells[:5]}")
    # listResult.count is sometimes {} and searchResultsNum is "" or a numeric string: accept numbers only
    meta = safe_js("""(() => {
      const num = v => (v === '' || v === null || v === undefined || typeof v === 'object') ? null
        : (Number.isFinite(Number(v)) ? Number(v) : null);
      const lr = (window._BBY_DATA_ || {}).listResult || {}, d = window.dioPageData || {};
      return {total: num(lr.count) ?? num(d.searchResultsNum), page: num(d.listPageNum) ?? num(lr.pageNumber)};
    })()""", deadline=deadline) or {}
    if meta.get("page") is None or meta.get("total") is None:
        raise NotReady(f"Best Buy did not report the page number and result count ({meta})")
    if meta["page"] != page:  # also confirms the cp-less URL is page 1
        raise RuntimeError(f"asked for page {page}, Best Buy rendered page {meta['page']}")
    return cards, meta["total"], meta["page"]

RETRY_BUDGET_S = 120  # one deadline per result page, covering every attempt and every backoff
MIN_ATTEMPT_S = 40    # do not back off and retry unless an attempt this long still fits

def fetch_page(query, page):
    deadline = time.monotonic() + RETRY_BUDGET_S
    attempt = 0
    while True:
        attempt += 1
        try:
            return load_search_page(query, page, deadline)
        except NotReady as e:
            backoff = 15 * attempt
            if time.monotonic() + backoff + MIN_ATTEMPT_S > deadline:  # last attempt: raise now, no sleep
                raise RuntimeError(f"page {page} failed after {attempt} attempt(s) within {RETRY_BUDGET_S} s: {e}. "
                                   "Results so far are incomplete; do not report them as the full crawl") from None
            print(f"page {page}: {e}; backing off {backoff} s, then retrying")
            time.sleep(backoff)

# Best Buy paginates 18 organic results per page (24 cards = 18 organic + 6 sponsored; 1236 results
# gave a last-page link of 69 = ceil(1236 / 18)). The crawl stops at the last page the count implies.
PAGE_SIZE = 18

new_tab("about:blank")
ensure_visible()

query = "gaming laptop"
all_items, seen = [], set()
for page in ROBOTS_PAGES:
    cards, total, shown_page = fetch_page(query, page)  # raises rather than return a partial crawl
    new = 0
    for c in cards:  # the same SKU can show up as a sponsored and an organic card
        if c["sku"] and c["sku"] not in seen:
            seen.add(c["sku"])
            c["page"] = page
            all_items.append(c)
            new += 1
    print(f"page {page} (site says page {shown_page}): {len(cards)} cards, {new} new, "
          f"{sum(c['price'] is not None for c in cards)} priced, total results {total}")
    if page >= math.ceil(total / PAGE_SIZE):
        print(f"page {page} is the last page for {total} results: done")
        break
    if page != ROBOTS_PAGES[-1]:
        time.sleep(3)  # polite pacing between result pages
else:
    print(f"stopped after page {ROBOTS_PAGES[-1]}: robots.txt disallows cp=6 to cp=20 for User-agent: *, "
          f"so the rest of the {total} results are not fetched")

from collections import Counter
print(len(all_items), "unique products;", Counter(c["availability"] for c in all_items))
for item in all_items[:3]:
    print(json.dumps(item))
```

Real output (trimmed, 2026-10-23, latest fresh-browser run):

```
page 1 (site says page 1): 24 cards, 23 new, 24 priced, total results 1233
page 2 (site says page 2): 24 cards, 19 new, 24 priced, total results 1235
page 3 (site says page 3): 24 cards, 22 new, 24 priced, total results 1235
page 4 (site says page 4): 24 cards, 24 new, 24 priced, total results 1235
page 5 (site says page 5): 24 cards, 24 new, 24 priced, total results 1235
stopped after page 5: robots.txt disallows cp=6 to cp=20 for User-agent: *, so the rest of the 1235 results are not fetched
112 unique products; Counter({'in_stock': 110, 'sold_out': 1, 'unavailable': 1})
{"sku": "6687893", "title": "HP - Googlebook 14\" 3K OLED Touchscreen - Snapdragon X Elite - 16GB Memory - 512GB SSD - Atmospheric Blue",
 "url": "https://www.bestbuy.com/product/hp-googlebook-14-3k-oled-touchscreen-snapdragon-x-elite-16gb-memory-512gb-ssd-atmospheric-blue/J3PPHVH9QX/sku/6687893",
 "price": 1299, "regular_price": null, "on_sale": false, "savings": null, "rating": 4.5, "review_count": 33,
 "availability": "in_stock", "button": "Add to cart", "pickup": "Pick up in 1 hour", "shipping": "Get it tomorrow \u2022 FREE",
 "sponsored": true, "page": 1}
```

Earlier runs of the same crawl gave 99 and 104 unique products. Every card on all 5 pages, the 6 sponsored ones per page included, had a SKU, title and URL, so the block's card-shell check passed.

So 5 pages give about 100 unique products; the other ~1,100 results sit on pages robots.txt disallows for `User-agent: *` (`cp=6` to `cp=20`). The permitted crawl of a query is capped at those 5 pages; for more, use the official API (see "What does not work"). Page 1 has no `cp` in the URL; the block checks that the page the site reports (`dioPageData.listPageNum`, else `listResult.pageNumber`) matches the page it asked for and raises if not, and it also raises when the site reports no page number or result count. Without `cp`, Best Buy rendered page 1 (`listPageNum` 1, the only pagination link pointing to `cp=2`), and `cp=2` shared 3 of about 20 SKUs with it, in line with the cross-page repeats noted under Gotchas.

How the block ends and fails:

- **Short result sets end on the count.** Best Buy pages 18 organic results at a time (`gaming laptop` pages 1, 2 and 5 each had 24 cards, 6 of them sponsored; 1,236 results gave a last-page link of 69, which is 1,236 / 18 rounded up). After each page the block stops once the page number reaches the reported total / 18, rounded up, so it never requests a page past the end. For `rtx 5090 founders edition` that is page 2 (`cp=2` reported 28 results in one run, 30 in another); `cp=3` there showed "unable to display products" with 0 cards.
- **Anything else is an error, not the end.** "Unable to display products", no rendered titles, no readable cards, any card still missing its SKU, title or URL after the revisit passes, or a missing page number or count on a page the count says exists fails that attempt. Each page gets one 120 s deadline covering all attempts and backoffs (15 s, then 30 s); a retry starts only if at least 40 s would remain after its backoff, so the last attempt is followed by a raise, not a sleep. The error says the results so far are incomplete.
- **Blocks are not retried.** Before reading a page, `nav()` records the tab's URL, waits until the tab is on a new document whose `location.href` is the requested URL (Best Buy may add `id=pcat17071` and reorder parameters, so `st` and `cp` are compared), and raises at once on HTTP 403 or 429 instead of retrying. Normal pages reported 200.

Counts vary run to run: an earlier run of pages 1-3 had 20 of 24 cards priced on page 1, and in another fresh-browser run page 1 came back with 14 of 24 priced and 9 cards that never rendered at all (`title` and `url` also `null`), even after the 3 revisit passes. The block now treats a page with any such card shell as not ready, so it reloads that page within the page's 120 s deadline and raises if the shells persist. A card whose price block alone never rendered is kept with `price: null`, so check the `priced` count per page. "Unavailable" and "Sold Out" cards still carry a price once they scroll into view: on an `rtx 5090` search, all 5 "Unavailable" cards on pages 1-3 had a price (e.g. $1,799.99, $799.99). `price` is `null` only when a card never rendered its price block.

### Search result fields

| Field | Source on the card | Notes |
|---|---|---|
| `sku` | `data-product-id` attribute | Best Buy SKU, e.g. `6674559` |
| `title` | `h3[title]` | Brand, " - ", name |
| `url` | `href` of the link wrapping the `h3` | `/product/<slug>/<code>`; sponsored cards append `/sku/<sku>` |
| `price` | `[data-testid="price-block-customer-price"]` | Current price, float |
| `regular_price` | `[data-testid="price-block-regular-price"]` ("Comp. Value: $1,924.99") | Only shown when discounted |
| `on_sale` | `price < regular_price` | |
| `savings` | `[data-testid="price-block-total-savings-text"]` | e.g. `Save $750` |
| `rating`, `review_count` | `[data-testid="rnr-stats-link"] p` ("Rating 4.6 out of 5 stars with 38 reviews") | Some items say "Syndicated rating, 4.76 out of 5 stars with 59 reviews on <vendor site>"; the regex takes both. "Not yet reviewed" gives `0` |
| `button`, `availability` | `[data-testid^="plp"][data-testid$="-label"]` | Seen: "Add to cart" (`plp-add-to-cart-<sku>-label`), "Sold Out" (`plp-sold-out-…`), "Unavailable" (`plp-unavailable-…`, `plp_openbox-unavailable-…`), "Shop Open-Box". Collectibles marked "High demand product" have no such button (`high_demand`). `null` when no button rendered |
| `pickup`, `shipping` | `[data-testid^="plp-pickup-messaging-"]`, `[data-testid^="plp-shipping-messaging-"]` | e.g. "Pick up in 1 hour", "Get it tomorrow • FREE", "Unavailable"; depends on the store Best Buy assigns to your IP |
| `sponsored` | card is inside `li.slContainer` | Dedupe on `sku` |

Page level: total result count is `window._BBY_DATA_.listResult.count` (sometimes an empty object), fallback `window.dioPageData.searchResultsNum` (an empty string until the page hydrates; a number on one page, a numeric string like `"1234"` on another). The block takes whichever parses as a number, else `null`. The current page number is `dioPageData.listPageNum` (a number) or `listResult.pageNumber` (a string such as `"1"`). `window._BBY_DATA_.skus` lists the page's SKUs in rank order with `isSponsored` flags before the cards finish rendering.

---

## What works: product page with full specs

Price, regular price, availability, rating, open-box offers and every spec row. Reuses the current tab, takes the organic SKUs from a live `laptop` search, and scrapes product pages until it has shown one discounted and one full-price product (about 30-50 s per product). Call `get_product(sku)` with any SKU from the search block.

```python
# NEEDS A VISIBLE TAB, like the search block: in a hidden tab the main price block never renders.
# Run it in a dedicated or cloud browser with FOREGROUND_TAB = True, which brings the tab to the
# front. Left False, a hidden tab raises instead of taking over your window.
FOREGROUND_TAB = False

import json, time
from urllib.parse import urlparse, parse_qs

PRODUCT_LD = r"""(() => {
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try { const d = JSON.parse(s.textContent); if (d['@type'] === 'Product') return d; } catch (e) {}
  }
  return null;
})()"""

SPEC_SHEET = r"""(() => {
  const root = document.querySelector('[data-testid="brix-sheet-content"]');
  if (!root) return null;
  const out = {};
  for (const h3 of root.querySelectorAll('h3')) {
    const rows = {};
    for (const row of h3.parentElement.querySelectorAll(':scope > div')) {
      if (row.children.length < 2) continue;
      const k = row.children[0].innerText.trim(), v = row.children[1].innerText.trim();
      if (k) rows[k] = v;
    }
    out[h3.innerText.trim()] = rows;
  }
  return out;
})()"""

def safe_js(expr, tries=6):
    for _ in range(tries):
        try:
            return js(expr)
        except (RuntimeError, TimeoutError):  # main thread busy right after navigation
            wait(2)
    return None

def nav(url, href_ok, timeout=45):
    # Best Buy pages keep the main thread busy; give Page.navigate more than the 5 s default.
    # A tab can hang mid-navigation: stop it and navigate once more (a second timeout raises).
    end = time.monotonic() + timeout
    left = lambda: max(1, min(30, end - time.monotonic()))
    # Record where the tab was and mark that document, so a reload of the same URL is told apart.
    before = safe_js("(window.__bhOldDoc = true, location.href)", tries=1)
    try:
        cdp("Page.navigate", url=url, _response_timeout=left())
    except TimeoutError:
        cdp("Page.stopLoading", _response_timeout=left())
        cdp("Page.navigate", url=url, _response_timeout=left())
    here = None
    while time.monotonic() < end:  # read nothing until the tab is on a new document at the requested URL
        wait(1)
        here = safe_js("({href: location.href, old: !!window.__bhOldDoc,"
                       " status: (performance.getEntriesByType('navigation')[0] || {}).responseStatus})", tries=1) or here
        if here and not here["old"] and href_ok(here["href"]):
            if here["status"] in (403, 429):  # a block: stop, never retry
                raise RuntimeError(f"HTTP {here['status']} at {here['href']}: blocked, stop and back off")
            return here["href"]
    raise RuntimeError(f"navigation to {url} not confirmed within {timeout:.0f} s "
                       f"(was {before}, now {here['href'] if here else 'unreadable'})")

def ensure_visible():
    if safe_js("document.visibilityState") == "visible":
        return
    if not FOREGROUND_TAB:
        raise RuntimeError("tab is hidden and Best Buy does not render hidden tabs: run this in a dedicated or "
                           "cloud browser with FOREGROUND_TAB = True (brings the tab to the front), or show the tab yourself")
    activate_tab(current_tab())

def click_button_named(name):
    try:  # every CDP call here can exceed the 5 s default while the page is busy
        nodes = cdp("Accessibility.getFullAXTree", _response_timeout=30)["nodes"]
        for n in nodes:
            if n.get("role", {}).get("value") == "button" and (n.get("name", {}).get("value") or "").strip().lower() == name.lower():
                bid = n["backendDOMNodeId"]
                cdp("DOM.scrollIntoViewIfNeeded", backendNodeId=bid, _response_timeout=30)
                wait(0.5)
                q = cdp("DOM.getBoxModel", backendNodeId=bid, _response_timeout=30)["model"]["content"]
                click_at_xy(sum(q[0::2]) / 4, sum(q[1::2]) / 4)
                return True
    except (RuntimeError, TimeoutError):
        pass  # the caller retries
    return False

# The main product's price block. Accessory, warranty, sponsored and "consider" carousels
# also use data-testid="price-block" and "price-block-regular-price", but sit outside this
# container, so never read those test ids page-wide.
MAIN_PRICE = '[data-testid="bestbuy-price-ui-price-experience"] [data-testid="price-block"]'

MAIN_PRICES = r"""(() => {
  const money = e => { const m = e && e.innerText.match(/\$([\d,]+\.\d{2})/); return m ? parseFloat(m[1].replace(/,/g, '')) : null; };
  const block = document.querySelector('%s');
  if (!block) return null;
  return {price: money(block.querySelector('[data-testid="price-block-customer-price"]')),
          regular: money(block.querySelector('[data-testid="price-block-regular-price"]'))};
})()""" % MAIN_PRICE

def get_product(sku):
    # /site/<sku>.p?skuId=<sku> redirects to the canonical /product/<slug>/<code> URL
    nav(f"https://www.bestbuy.com/site/{sku}.p?skuId={sku}",
        lambda h: urlparse(h).netloc == "www.bestbuy.com" and urlparse(h).path.startswith("/product/"))
    ld, state = None, None
    for _ in range(30):  # JSON-LD arrives with the HTML; the page state and price block hydrate later
        wait(1.5)
        ld = ld or safe_js(PRODUCT_LD)
        # a second isPDP entry for the same SKU can appear with priceType null; take the filled one
        state = safe_js(f"((window._BBY_DATA_ || {{}}).skus || []).find(s => s.id === '{sku}' && s.isPDP && s.priceType) || null")
        if ld and state and safe_js(f"!!document.querySelector('{MAIN_PRICE} [data-testid=\"price-block-customer-price\"]')"):
            break
    if not ld:
        return None
    if str(ld.get("sku")) != str(sku):  # the redirect target must be the product that was asked for
        raise RuntimeError(f"asked for SKU {sku}, the page is SKU {ld.get('sku')}")
    state = state or {}
    offers = ld.get("offers") or []
    if isinstance(offers, dict):
        offers = [offers]
    new = next((o for o in offers if "NewCondition" in (o.get("itemCondition") or "")), offers[0] if offers else {})
    # Main product only: its "Comp. Value" line shows when it is discounted, else regular is None
    main = safe_js(MAIN_PRICES) or {}
    regular = main.get("regular")
    specs = None
    for _ in range(3):  # a click before hydration finishes does nothing, so retry
        if not click_button_named("See all specifications"):
            wait(2)
            continue
        for _ in range(8):
            wait(1)
            specs = safe_js(SPEC_SHEET)
            if specs:
                break
        if specs:
            break
    try:
        press_key("Escape")  # close the sheet
    except (RuntimeError, TimeoutError):
        pass
    rating = ld.get("aggregateRating") or {}
    return {
        "sku": ld.get("sku"),
        "title": ld.get("name"),
        "brand": (ld.get("brand") or {}).get("name"),
        "model": ld.get("model"),
        "url": ld.get("url"),
        "price": new.get("price"),
        "price_block_price": main.get("price"),          # should equal price
        "regular_price": regular,                        # None when the main product is not discounted
        "on_sale": regular is not None and main.get("price") is not None and main["price"] < regular,
        "availability": (new.get("availability") or "").rsplit("/", 1)[-1],
        "price_type": state.get("priceType"),           # "regular" / "onSale"; None if the state never hydrated
        "button_state": state.get("primaryButtonState"),  # e.g. "ADD_TO_CART"
        "rating": rating.get("ratingValue"),
        "review_count": rating.get("reviewCount"),
        "other_offers": [{"condition": o.get("description"), "price": o.get("price")} for o in offers if o is not new],
        "specs": specs,
    }

ensure_visible()
# Pick a SKU from a live search so this block does not depend on a hard-coded product.
nav("https://www.bestbuy.com/site/searchpage.jsp?st=laptop",
    lambda h: urlparse(h).path == "/site/searchpage.jsp" and parse_qs(urlparse(h).query).get("st") == ["laptop"]
    and "cp" not in parse_qs(urlparse(h).query))
skus = []
for _ in range(20):
    wait(1.5)
    skus = safe_js("[...new Set(((window._BBY_DATA_ || {}).skus || []).filter(s => s.id && !s.isSponsored).map(s => s.id))]") or []
    if len(skus) >= 5:  # the list fills in as the page hydrates
        break
print("organic SKUs on page:", skus[:5])
# Scrape organic SKUs until there is one discounted and one full-price product to show both cases.
shown = set()
for sku in skus[:12]:
    product = get_product(sku)
    if not product:
        print(sku, "no product data")
        continue
    specs = product.pop("specs") or {}
    print(sku, "on_sale", product["on_sale"], "price", product["price"], "price block", product["price_block_price"],
          "regular", product["regular_price"], "price_type", product["price_type"])
    if product["on_sale"] in shown:
        continue
    shown.add(product["on_sale"])
    print(json.dumps(product, indent=1))
    print(sum(len(v) for v in specs.values()), "spec rows in", len(specs), "sections")
    print(json.dumps({k: specs[k] for k in list(specs)[:3]}, indent=1))
    if shown == {True, False}:
        break
```

Real output (trimmed, 2026-10-23, latest fresh-browser run):

```
organic SKUs on page: ['6667483', '12756229', '12341769', '6667482', '6681674']
6667483 on_sale True price 209.99 price block 209.99 regular 349.99 price_type onSale
{
 "sku": "6667483",
 "title": "HP - 14\" Laptop - Intel N150 Processor - 4GB Memory - 128GB Storage - Pale Rose Gold",
 "brand": "HP", "model": "14-dq6105dx",
 "url": "https://www.bestbuy.com/product/hp-14-laptop-intel-n150-processor-4gb-memory-128gb-storage-pale-rose-gold/JJGW3FGF9T",
 "price": 209.99, "price_block_price": 209.99, "regular_price": 349.99, "on_sale": true,
 "availability": "InStock", "price_type": "onSale", "button_state": "ADD_TO_CART", "rating": 4.4, "review_count": 135,
 "other_offers": [{"condition": "Open-Box Excellent", "price": 197.99}, {"condition": "Open-Box Good", "price": 191.99},
                  {"condition": "Open-Box Fair", "price": 184.99}]
}
83 spec rows in 17 sections
{"Key Specs": {"Screen Type": "TN", "Screen Size": "14 inches", "Processor Model": "Intel Processor N150", ...},
 "General": {"Brand": "HP", "Model Number": "14-dq6105dx", "Color": "Pale Rose Gold", "Year of Release": "2026"},
 "Display": {"Display Type": "LED", "Screen Size": "14 inches", "Refresh Rate": "60Hz", "Brightness": "250 nits", ...}}
12756229 on_sale True price 337 price block 337 regular 399.99 price_type onSale
12341769 on_sale True price 829 price block 829 regular 1199.99 price_type onSale
6667482 on_sale True price 199.99 price block 199.99 regular 349.99 price_type onSale
6681674 on_sale True price 539.99 price block 539.99 regular 699.99 price_type onSale
6615874 on_sale False price 699 price block 699 regular None price_type regular
{
 "sku": "6615874",
 "title": "Apple - MacBook Neo 13-inch Laptop - A18 Pro chip with 6‑core CPU and 5‑core GPU - 8GB Memory - 256GB SSD - Indigo",
 "brand": "Apple", "model": "MHFF4LL/A",
 "price": 699, "price_block_price": 699, "regular_price": null, "on_sale": false,
 "availability": "InStock", "price_type": "regular", "button_state": "ADD_TO_CART", "rating": 4.9, "review_count": 1470, ...
}
52 spec rows in 16 sections
...
```

`regular_price` is `null` for the full-price MacBook even though its page has 6+ other `price-block-regular-price` elements in carousels (31 after scrolling to the bottom).

### Product page fields

| Field | Source | Notes |
|---|---|---|
| `sku`, `title`, `brand`, `model`, `url` | JSON-LD `Product`: `sku`, `name`, `brand.name`, `model`, `url` | In the initial HTML; there are also `BreadcrumbList` and video `ItemList` JSON-LD blocks. `get_product` first confirms the tab landed on a `/product/` URL, then raises if the JSON-LD `sku` is not the SKU it asked for |
| `price`, `availability` | JSON-LD `offers[]` entry whose `itemCondition` is `NewCondition` | `availability` is the schema.org suffix, e.g. `InStock` |
| `other_offers` | other JSON-LD `offers[]` | Open-Box Excellent / Good / Fair |
| `price_block_price`, `regular_price` | `[data-testid="price-block-customer-price"]` and `[data-testid="price-block-regular-price"]` inside the main product's `[data-testid="bestbuy-price-ui-price-experience"] [data-testid="price-block"]` | `regular_price` (the main block's "Comp. Value: $419.00" line) is `None` when the main product is not discounted. `price_block_price` matched JSON-LD `price` on all 6 laptops checked. Never read these test ids page-wide: warranty, sponsored, "consider" and other product carousels reuse them, and on the undiscounted $699.00 MacBook the first page-wide match was another card's "The price was $419.00". The container appears twice (top and a lower duplicate), both for the main product |
| `on_sale` | `regular_price` present and above `price_block_price` | Works even when `price_type` is `None` |
| `price_type`, `button_state` | `window._BBY_DATA_.skus` entry with `isPDP: true` and a non-null `priceType` (`priceType`, `primaryButtonState`) | Hydrates 10-20 s after JSON-LD, and a second `isPDP` entry with `priceType: null` can show up. In an earlier run, on 1 of 6 laptops (`13214744`) it never hydrated within the 45 s wait, so both were `None`; in the latest run all 7 laptops hydrated. Same entry has `unitPrice`, `altSellerPriceMin/Max`, `userGeneratedContent.ratingAverage/reviewsCount` |
| `rating`, `review_count` | JSON-LD `aggregateRating.ratingValue` / `reviewCount` | |
| `specs` | "See all specifications" sheet `[data-testid="brix-sheet-content"]`: each `h3` is a section, each direct child `div` is a row of label and value | Section "Other" holds `UPC`, `BSIN` (the code at the end of the product URL) and `SKU`. 52, 83 and 84 rows on the three laptops checked. `specs` is `None` when the sheet did not open after 3 clicks: in one of two later fresh-browser runs that happened on the MacBook (`0 spec rows`), while the other run got its 52 rows |

### URL patterns

| URL | Observed |
|---|---|
| `/site/searchpage.jsp?st=<url-encoded query>` | Search results, page 1; Best Buy sometimes adds `id=pcat17071` itself |
| `/site/searchpage.jsp?st=<url-encoded query>&cp=<2-5>` | Pages 2-5. robots.txt disallows `cp=1` (and `cp=10`-`19`), `cp=6` to `cp=9` and `cp=20` for `User-agent: *`; the site's own pagination links also use `cp` |
| `/site/<sku>.p?skuId=<sku>` | Redirects to the canonical `/product/<slug>/<code>` page |
| `/product/<slug>/<code>` | Product page |
| `cp` past the last page | "We're unable to display products at the moment", 0 cards. Example: `rtx 5090 founders edition` reported 24 results on page 1 and 30 on `cp=2` (12 cards), and `cp=3` showed the message with 0 cards |

---

## Gotchas

- **Background tab means endless skeletons.** With `document.visibilityState == "hidden"` the search page stayed at "Main Content / Loading..." with 0 titles and 0 prices for 24 s (rechecked 2026-10-23 in a fresh cloud browser). It stayed that way with `Emulation.setFocusEmulationEnabled(enabled=True)`, and also with `document.visibilityState` and `document.hidden` faked to `visible` / `false` by a script added before navigation. After `activate_tab(current_tab())`, titles rendered within 2 s. A hidden product page got its JSON-LD and `_BBY_DATA_` entry but no main price block in 30 s; it appeared within 2 s of activating the tab. So a visible tab is required, not optional. `activate_tab` brings the tab to the front, which is why the blocks call it only when you set `FOREGROUND_TAB = True` (do that in a dedicated or cloud browser); on your own Chrome leave it `False` and show the tab yourself. Keep one visible working tab and close extras.
- **Busy main thread.** Right after navigation, `Runtime.evaluate` and `Page.navigate` sometimes exceeded browser-harness's 5 s IPC default (`Runtime.evaluate timed out`, `Page.navigate timed out after 5s`). `DOM.getBoxModel` timed out the same way while clicking "See all specifications". The blocks pass `_response_timeout=30` to those CDP calls and retry on `RuntimeError` or `TimeoutError` (browser-harness raises a `TimeoutError` subclass for IPC timeouts). Once a tab hung mid-navigation (title stuck as the URL, every evaluate timing out); `cdp("Page.stopLoading")` plus a new navigate recovered it, so `nav()` does exactly that when `Page.navigate` times out, and raises if the retry times out too. In a later probe a tab stayed hung even after `Page.stopLoading` and a navigate to `about:blank` (every `Runtime.evaluate` timed out); the search block bounds every wait by its page deadline, so a tab like that ends in an error instead of an endless wait.
- **Lazy price blocks.** One top-to-bottom scroll left some cards unpriced; scrolling each unpriced card into view filled them in (24 of 24 on pages 2 and 3). The retry includes "Unavailable" and "Sold Out" cards, which do get a price block when in view; the loop gives up after 3 passes, so a card that never renders one keeps `price: null`.
- **Hydration order on product pages.** JSON-LD is there first; the main price block and `_BBY_DATA_.skus` arrive later (the `isPDP` entry took 12-18 s in one trace, and once did not appear within 20 s). A "See all specifications" click before hydration did nothing, hence the wait and retry.
- **Card shells mean the product API is failing.** In 2 fresh cloud browsers on 2026-10-23, page 1 of `gaming laptop` loaded but 17 and 15 of its 24 cards stayed shells: an `h3` with no title, a link with no `href`, "Not Yet Reviewed", "See price in cart" and no price block. A reload with Network events on showed 149 of the page's 156 `/gateway/graphql` requests failing with `net::ERR_HTTP2_PROTOCOL_ERROR` (7 returned 200), the same HTTP/2 stream error plain curl gets. The search block raised `page 1 failed after 1 attempt(s) within 120 s: 15 of 24 cards still lack SKU, title or URL`; revisiting that many shells used enough of the 120 s that no second attempt fit. Treat it like a block: stop, back off, and use a new session later (the next session, about 15 minutes later, rendered every card on pages 1-4, and the one after it crawled all 5 pages).
- **Page 5 can run out of time.** In 2 other fresh browsers that day, pages 1-4 completed and page 5 used its whole 120 s in the first attempt, raising `out of time while revisiting unrendered cards` once and `out of time while waiting for product titles` once. In the second case every `Runtime.evaluate` on the tab then timed out (a hung tab, see "Busy main thread"). The block raises rather than return 4 pages as the full crawl; rerun in a new browser.
- **Store and ZIP come from your IP.** The header shows a nearby store; pickup and shipping text depend on it. A different exit location can change those fields and sometimes ranking.
- **Sponsored duplicates.** One SKU appeared as both a sponsored and an organic card on the same page, and a few SKUs repeat across `cp` pages. Dedupe on `sku`.
- **Selector drift.** The site is a Next.js app with utility-class styling. Rely on `data-testid`, `data-product-id`, JSON-LD and `_BBY_DATA_`; avoid class names other than `product-list-item` and `slContainer`.
- **No consent banner** appeared for the US cloud browser, so there is nothing to dismiss.
- **Pacing.** About 40 page loads over roughly an hour from one session produced no block page or CAPTCHA. The search block sleeps 3 s between pages; do not go faster across many queries.
- **Page depth.** robots.txt caps a `User-agent: *` crawl of one query at 5 pages (see the top). `search_url()` raises `ValueError` for any other page number rather than skipping ahead.

## What does not work

- `http_get`, curl or urllib against `www.bestbuy.com` search or product pages: no response before timeout, so plain HTTP is blocked; this skill uses a normal browser session.
- `api.bestbuy.com/v1/products(...)` without an API key: HTTP 403 `{"errorMessage":"We were unable to locate your API Key."}`. This is Best Buy's official, structured product API: developer.bestbuy.com has a "Get API Key" signup, and the documented form is `https://api.bestbuy.com/v1/products(search=laptop)?format=json&apiKey=<your key>` (the docs warn about per-second query limits). If you can register for a key, prefer it over scraping; it was not tested here because no key was used.
- Embedded data on search pages: no `__NEXT_DATA__`, no JSON-LD, the Apollo SSR transport was empty and `self.__next_f` contained no `skuId`. Prices and fulfillment load through client-side POSTs to `/gateway/graphql` (operations such as `PriceBlockInit_Compact_GetProduct`); those were not replayed here, so read the rendered DOM.
- Specs in the initial product page DOM: the UPC was absent from `document.body.innerText` until the sheet was opened.
