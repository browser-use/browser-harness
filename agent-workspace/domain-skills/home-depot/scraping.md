# Home Depot — Category Listings, Specs & Store Availability

Field-tested against www.homedepot.com on 2026-10-23 using a Browser Use cloud browser.

robots.txt (checked 2026-10-23) for `User-agent: *` disallows `/s/` (search), any URL containing `NCNI-5` (where a search redirect lands), `Ntt-`, `Ntk-` and `/b/Featured-Products*`, and does not disallow `/`, `/sitemap/...`, `/b/<category>/N-<id>`, `/b/<category>/N-<id>?Nao=<offset>` or `/p/<slug>/<itemId>`. This skill uses only those allowed paths, and blocks 2 and 3 re-check every URL they open or land on against the live robots.txt. `apionline.homedepot.com/robots.txt` returned 403, so this skill never sends its own requests to that host; it only reads the responses of calls the pages make themselves.

## Quick summary

- **No search.** `/s/<query>` and the `NCNI-5` category redirect a search lands on are disallowed. Find a category instead: the site's own sitemap `https://www.homedepot.com/sitemap/B/PLPs.xml` points to `PLP_CORE_TAX-0.xml` with 5356 category URLs (`/b/<slug>/N-<id>`); block 1 filters them by words in the slug.
- **Plain HTTP is blocked (status 403)** on product pages (`/p/320326875` returned a 2,259-byte "Error Page": "Oops!! Something went wrong. Please refresh page"); the sitemap and robots.txt answered 200 to a plain request. Blocks 2 and 3 use a normal browser session.
- **Category page** (`/b/<slug>/N-<id>`) carries the product grid as JSON, not just HTML:
  - server-rendered Apollo cache `window.__APOLLO_STATE__` (`SearchModel` -> `products(...)` -> `base-searchNav-<itemId>` entries), and
  - the page's own `POST https://apionline.homedepot.com/federation-gateway/graphql?opname=searchModel`.
  On both category pages tried, the server rendered 12 products and the page fetched the full grid (24 for Power Drills, 27 for Lawn Mowers) via that GraphQL call. Block 2 records the page's own response and waits for whichever source is complete.
- **Pagination** is `?Nao=<offset>` on the category path, 24 products per step (robots.txt does not disallow it). Block 2 raises if a page comes back at a different path or `startIndex`, and prints why it stopped (short page, page of repeats, or the `MAX_PAGES` cap).
- **Store.** A brand-new session's first page was priced and stocked for store 121 (Cumberland) before the site's script set the `THD_LOCALIZER` cookie; later pages used a store near the exit IP. The blocks open the home page first and wait for that cookie, and block 2 tags every row with the store of its own response.
- **Product page** (`/p/<itemId>` redirects to `/p/<slug>/<itemId>`): JSON-LD `Product` (name, brand, model, sku, gtin13, price, rating, review count, images, 10 reviews) plus the page's own `opname=productClientOnlyProduct` GraphQL response, which has the spec table and pickup/delivery inventory for the store the site picked from the browser's location.
- **Rate limit is real.** After about 30 page loads plus ~12 API calls in ~25 minutes, every URL in that browser session returned the 403 "Error Page". Treat that as a stop condition: the blocks raise on the Error Page or a 4xx from the page's own API call without retrying; stop and back off. Keep runs small and paced. Only a timeout, network error, 429 or 5xx is retried, twice, with backoff capped at 120 s (a longer `Retry-After` stops the run) and no sleep after the last try. The blocks never return a partial result as if it were complete.

## What works

### 1. Find category pages (plain HTTP, the site's sitemap)

```python
import html, re, time, urllib.error, urllib.parse, urllib.request
from email.utils import parsedate_to_datetime

KEYWORDS = ["lawn", "mowers"]   # words that must all appear in the category URL path
UA = "browser-harness-domain-skill/1.0 (+https://github.com/browser-use/browser-harness)"   # truthful client UA
MAX_WAIT = 120                  # longest backoff / Retry-After sleep in seconds; a longer ask stops the run

def retry_after_seconds(value, default):
    """Retry-After is either delay-seconds or an HTTP-date."""
    if not value:
        return default
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError):
        return default

def get(url, tries=3):
    """Plain GET with a truthful UA. Retries timeouts, network errors, 429 and 5xx (Retry-After honored,
    capped at MAX_WAIT, no sleep after the last try). Any other error raises (403 = blocked: stop)."""
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise RuntimeError(f"{url}: HTTP {e.code}; blocked or gone, not retried") from e
            why, retry_after = f"HTTP {e.code}", e.headers.get("Retry-After")
        except OSError as e:   # URLError, timeouts, dropped connections
            why, retry_after = f"network error ({e})", None
        if attempt == tries:
            raise RuntimeError(f"{url}: {why} on {tries} tries; stop and back off")
        wait = retry_after_seconds(retry_after, 10 * attempt)
        if wait > MAX_WAIT:
            raise RuntimeError(f"{url}: server asked to wait {wait:.0f}s (over {MAX_WAIT}s); stopping")
        print(f"{url}: {why}; retry {attempt}/{tries - 1} in {wait:.0f}s")
        time.sleep(wait)

def robots_rules(text):
    """(allow, pattern) rules of the `User-agent: *` group."""
    rules, active = [], False
    for line in text.splitlines():
        key, _, val = line.split("#")[0].partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent":
            active = val == "*"
        elif active and key in ("allow", "disallow") and val:
            rules.append((key == "allow", val))
    return rules

def allowed(url, rules):
    """Longest matching rule wins, Allow wins a tie; `*` is a wildcard and a trailing `$` anchors."""
    u = urllib.parse.urlsplit(url)
    path = (u.path or "/") + ("?" + u.query if u.query else "")
    best = (-1, True)
    for allow, pat in rules:
        rx = re.escape(pat).replace(r"\*", ".*")
        rx = rx[:-2] + "$" if rx.endswith(r"\$") else rx
        if re.match(rx, path) and (len(pat), allow) > best:
            best = (len(pat), allow)
    return best[1]

rules = robots_rules(get("https://www.homedepot.com/robots.txt"))
if not rules:
    raise RuntimeError("robots.txt has no User-agent: * rules (layout change?); stop")
index = get("https://www.homedepot.com/sitemap/B/PLPs.xml")
core = [u for u in re.findall(r"<loc>([^<]+)</loc>", index) if "/PLP_CORE_TAX/" in u]
if not core:
    raise RuntimeError("no PLP_CORE_TAX sitemap listed in sitemap/B/PLPs.xml (layout change?)")
cats = []
for sm in core:
    time.sleep(2)   # polite pacing
    cats += [html.unescape(u) for u in re.findall(r"<loc>([^<]+)</loc>", get(sm))]
if not cats:
    raise RuntimeError(f"no category URLs in {core}")
print(f"{len(core)} core category sitemap(s), {len(cats)} category URLs")

words = [w.lower() for w in KEYWORDS]
match = [u for u in cats if all(w in urllib.parse.urlsplit(u).path.lower() for w in words)]
ok = sorted((u for u in match if allowed(u, rules)), key=len)   # shortest (broadest) first
print(f"{len(match)} match {KEYWORDS}; {len(match) - len(ok)} dropped as disallowed by robots.txt")
for u in ok[:10]:
    print(u)
```

Observed output:

```
1 core category sitemap(s), 5356 category URLs
15 match ['lawn', 'mowers']; 0 dropped as disallowed by robots.txt
https://www.homedepot.com/b/Outdoors-Outdoor-Power-Equipment-Lawn-Mowers/N-5yc1vZc5ar
https://www.homedepot.com/b/Outdoors-Outdoor-Power-Equipment-Riding-Lawn-Mowers/N-5yc1vZc5ax
https://www.homedepot.com/b/Outdoors-Outdoor-Power-Equipment-Lawn-Mowers-Push-Mowers/N-5yc1vZc5ah
https://www.homedepot.com/b/Outdoors-Outdoor-Power-Equipment-Lawn-Mowers-Reel-Lawn-Mowers/N-5yc1vZc5av
... (10 printed)
```

The sitemap index also lists `PLP_REFINED-*.xml` files (45,000 URLs in the first one alone, many with `?lowerBound=...` price filters). Block 1 reads only `PLP_CORE_TAX`.

### 2. Category listing, 2+ pages (browser, JSON from the page itself)

```python
import json, re, time, urllib.error, urllib.parse, urllib.request
from email.utils import parsedate_to_datetime

CATEGORY = "https://www.homedepot.com/b/Outdoors-Outdoor-Power-Equipment-Lawn-Mowers/N-5yc1vZc5ar"   # from block 1, no query string
MAX_PAGES = 3             # safety cap; the run prints when it stops because of it
MAX_WAIT = 120            # longest backoff / Retry-After sleep in seconds; a longer ask stops the run
UA = "browser-harness-domain-skill/1.0 (+https://github.com/browser-use/browser-harness)"   # robots.txt fetch only

# Record the page's own searchModel GraphQL responses before any page script runs.
HOOK = """
(() => {
  if (window.__gql) return;
  window.__gql = [];
  const orig = window.fetch;
  window.fetch = async function (input, init) {
    const url = String((input && input.url) || input);
    const rec = url.includes('/federation-gateway/graphql?opname=searchModel') ? {url} : null;
    if (rec) window.__gql.push(rec);
    let res;
    try { res = await orig.apply(this, arguments); } catch (e) { if (rec) rec.err = String(e); throw e; }
    if (rec) {
      rec.status = res.status; rec.retryAfter = res.headers.get('Retry-After');
      try { rec.resp = await res.clone().text(); } catch (e) { rec.err = String(e); }
    }
    return res;
  };
})();
"""

# Products come from the server-rendered Apollo cache (window.__APOLLO_STATE__) or, when the
# server rendered only part of the grid, from the page's own POST ...graphql?opname=searchModel.
READ = """(() => {
  const st = window.__APOLLO_STATE__ || {};
  const sm = Object.values(st).find(v => v && v.__typename === 'SearchModel');
  const key = sm && Object.keys(sm).find(k => k.startsWith('products'));
  const ssr = key && Array.isArray(sm[key]) ? sm[key].map(r => r && st[r.__ref]).filter(Boolean) : [];
  const recs = window.__gql || [];
  const g = recs.filter(r => r.status === 200 && r.resp)
    .map(r => { try { return JSON.parse(r.resp).data.searchModel; } catch (e) { return null; } }).filter(Boolean).pop();
  const meta = (g || sm || {}).metadata || {};
  return {stale: !!window.__stale, ready: document.readyState, href: location.href,
          path: location.origin + location.pathname, title: document.title,
          cookie: document.cookie.includes('THD_LOCALIZER='),
          report: (g || sm || {}).searchReport || null, ssr, gql: g ? g.products : null, stores: meta.stores || null,
          failed: recs.filter(r => r.err || (r.status && r.status !== 200))
                      .map(r => ({status: r.status || null, retryAfter: r.retryAfter || null, err: r.err || null}))};
})()"""

def retry_after_seconds(value, default):
    """Retry-After is either delay-seconds or an HTTP-date."""
    if not value:
        return default
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError):
        return default

def backoff(retry_after, default, label):
    """Seconds to sleep before a retry: Retry-After when readable, else `default`. Over MAX_WAIT: raise."""
    wait = retry_after_seconds(retry_after, default)
    if wait > MAX_WAIT:
        raise RuntimeError(f"{label}: server asked to wait {wait:.0f}s (over {MAX_WAIT}s); stopping")
    return wait

def get(url, tries=3):
    """Plain GET with a truthful UA (used for robots.txt). Retries timeouts, network errors, 429, 5xx."""
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise RuntimeError(f"{url}: HTTP {e.code}; blocked or gone, not retried") from e
            why, retry_after = f"HTTP {e.code}", e.headers.get("Retry-After")
        except OSError as e:
            why, retry_after = f"network error ({e})", None
        if attempt == tries:
            raise RuntimeError(f"{url}: {why} on {tries} tries; stop and back off")
        wait = backoff(retry_after, 10 * attempt, url)
        print(f"{url}: {why}; retry {attempt}/{tries - 1} in {wait:.0f}s")
        time.sleep(wait)

def robots_rules(text):
    rules, active = [], False
    for line in text.splitlines():
        key, _, val = line.split("#")[0].partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent":
            active = val == "*"
        elif active and key in ("allow", "disallow") and val:
            rules.append((key == "allow", val))
    return rules

def allowed(url, rules):
    """Longest matching rule wins, Allow wins a tie; `*` is a wildcard and a trailing `$` anchors."""
    u = urllib.parse.urlsplit(url)
    path = (u.path or "/") + ("?" + u.query if u.query else "")
    best = (-1, True)
    for allow, pat in rules:
        rx = re.escape(pat).replace(r"\*", ".*")
        rx = rx[:-2] + "$" if rx.endswith(r"\$") else rx
        if re.match(rx, path) and (len(pat), allow) > best:
            best = (len(pat), allow)
    return best[1]

def peek(expr):
    """js() that returns None while a navigation swaps the document.
    The harness reports a CDP timeout from js() as RuntimeError('Runtime.evaluate timed out ...')
    and from cdp() as TimeoutError; both are retried by the poll loops below."""
    try:
        return js(expr)
    except TimeoutError:
        return None
    except RuntimeError as e:
        if "timed out" in str(e) or "context" in str(e).lower():   # also "Execution context was destroyed"
            return None
        raise

def navigate(url):
    if not allowed(url, RULES):
        raise RuntimeError(f"robots.txt disallows {url}; not opening it")
    peek("window.__stale = true")   # marks the old document; polls skip it until the new one loads
    try:
        goto_url(url)
    except TimeoutError:
        pass   # Page.navigate can outlast the harness's 5 s IPC timeout; the navigation still runs

def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None

def obj(v):
    return v if isinstance(v, dict) else {}

def arr(v):
    return v if isinstance(v, list) else []

def blocked(label, what, url):
    return RuntimeError(f"{label}: blocked ({what}) at {url}. Stop and back off; this is not retried.")

def open_page(url, done, label, secs=45, tries=3):
    """Navigate, then poll READ on the new document until done(data) holds on two polls in a row.
    The 403 'Error Page' or a searchModel 4xx other than 429 raises at once (blocked: stop).
    A timeout, network error, 429 or 5xx is retried with backoff, then raised."""
    for attempt in range(1, tries + 1):
        navigate(url)
        data, last, why = None, None, f"no complete product grid within {secs}s"
        for _ in range(secs):
            time.sleep(1)
            cur = peek(READ)
            if not cur or cur["stale"] or cur["ready"] != "complete":
                continue
            data = cur
            if "Error Page" in (data["title"] or ""):
                raise blocked(label, "403 'Error Page'", url)
            if not allowed(data["href"], RULES):
                raise RuntimeError(f"{label}: landed on {data['href']}, which robots.txt disallows; stop")
            if data["failed"] and not data["gql"]:
                f = data["failed"][-1]
                if f["status"] and f["status"] != 429 and f["status"] < 500:
                    raise blocked(label, f"searchModel HTTP {f['status']}", url)
                why = f"searchModel call failed (HTTP {f['status']} {f['err'] or ''})"
                break
            if done(data) and data["href"] == last:
                return data
            last = data["href"]
        if attempt == tries:
            raise RuntimeError(f"{label}: {why} on {tries} tries ({url}); stop and back off")
        retry_after = data["failed"][-1]["retryAfter"] if data and data["failed"] else None
        wait = backoff(retry_after, 20 * attempt, label)
        print(f"{label}: {why}; retry {attempt}/{tries - 1} in {wait:.0f}s")
        time.sleep(wait)

def grid_done(start):
    def done(d):
        rep = d["report"]
        if not isinstance(rep, dict):
            return False
        expected = min(24, max(int(num(rep.get("totalProducts")) or 0) - start, 0))
        return bool(d["gql"]) or len(d["ssr"]) >= expected
    return done

def field(o, name):
    # SSR keys carry arguments, e.g. 'pricing({"storeId":"121"})'; GraphQL keys do not.
    o = obj(o)
    if name in o:
        return o[name]
    return next((v for k, v in o.items() if k.startswith(name + "(")), None)

def stock(p):
    out = []
    for opt in arr(obj(field(p, "fulfillment")).get("fulfillmentOptions")):
        for svc in arr(obj(opt).get("services")):
            for loc in arr(obj(svc).get("locations")):
                inv = obj(obj(loc).get("inventory"))
                out.append({"service": svc.get("type"), "store": loc.get("storeName"), "store_id": loc.get("locationId"),
                            "qty": num(inv.get("quantity")), "in_stock": inv.get("isInStock"),
                            "limited": inv.get("isLimitedQuantity")})
    return out

def row(p, store_id):
    ids = obj(p.get("identifiers"))
    pricing = obj(field(p, "pricing"))
    rr = obj(obj(p.get("reviews")).get("ratingsReviews"))
    reviews = num(rr.get("totalReviews"))
    url = ids.get("canonicalUrl")
    item_id = p.get("itemId")
    return {
        "item_id": item_id if isinstance(item_id, str) and item_id else None,
        "title": ids.get("productLabel"),
        "brand": ids.get("brandName"),
        "model": ids.get("modelNumber"),
        "price": num(pricing.get("value")),
        "was_price": num(pricing.get("original")),
        "priced_for_store": store_id,          # metadata.stores.storeId of the same response
        "rating": num(rr.get("averageRating")),
        "reviews": int(reviews) if reviews is not None else None,
        "url": "https://www.homedepot.com" + url if isinstance(url, str) and url.startswith("/") else None,
        "sponsored": bool(obj(p.get("info")).get("isSponsored")),
        "stock": stock(p),
    }

if urllib.parse.urlsplit(CATEGORY).query or not re.match(r"https://www\.homedepot\.com/b/", CATEGORY):
    raise ValueError("CATEGORY must be a https://www.homedepot.com/b/... URL without a query string")
RULES = robots_rules(get("https://www.homedepot.com/robots.txt"))
if not RULES:
    raise RuntimeError("robots.txt has no User-agent: * rules (layout change?); stop")

tab = new_tab("about:blank")
cdp("Page.enable")
cdp("Page.addScriptToEvaluateOnNewDocument", source=HOOK)

# A brand-new session is served a default store until the site's own script sets the
# THD_LOCALIZER cookie. Open the home page first so every listing page uses the same store.
open_page("https://www.homedepot.com/", lambda d: d["cookie"], "home page warm-up")
time.sleep(3)

data = open_page(CATEGORY, grid_done(0), "category page 1")
base = data["path"]
if not re.match(r"https://www\.homedepot\.com/b/", base):
    raise RuntimeError(f"category landed on an unexpected page: {data['href']}")
print("landed on:", base, "|", data["title"])

rows, seen, stores, stop = [], set(), {}, None
for page in range(MAX_PAGES):
    start = page * 24
    if page:
        time.sleep(4)   # polite pacing between page loads
        data = open_page(f"{base}?Nao={start}", grid_done(start), f"category page {page + 1}")
    rep = obj(data["report"])
    if data["path"] != base or num(rep.get("startIndex")) != start:
        raise RuntimeError(f"page {page + 1}: got {data['href']} startIndex={rep.get('startIndex')}, "
                           f"expected {base} at {start}")
    products = [p for p in arr(data["gql"] or data["ssr"]) if isinstance(p, dict)]
    st = obj(data["stores"])
    stores[st.get("storeId")] = st
    ads = dupes = 0
    for p in products:
        r = row(p, st.get("storeId"))
        if r["sponsored"]:
            ads += 1
            continue
        if r["item_id"] is not None:
            if r["item_id"] in seen:
                dupes += 1
                continue
            seen.add(r["item_id"])
        rows.append(r)
    print(f"page {page + 1}: {len(products)} products from {'graphql' if data['gql'] else 'ssr'} "
          f"({ads} sponsored, {dupes} repeats), {len(rows)} unique so far, "
          f"store {st.get('storeId')}, totalProducts={rep.get('totalProducts')}")
    if len(products) < 24:
        stop = "end of results (short page)"
        break
    if len(products) == ads + dupes:
        stop = f"page {page + 1} added no new items; the rest of the {rep.get('totalProducts')} were NOT collected"
        break
else:
    stop = f"MAX_PAGES={MAX_PAGES} cap hit; about {rep.get('totalProducts')} products in total, the rest NOT collected"
print("stopped:", stop)

for sid, st in stores.items():
    print("store", sid, st.get("storeName"), "| nearby:",
          [(s.get("storeName"), s.get("storeId")) for s in arr(st.get("nearByStores")) if isinstance(s, dict)])
if len(stores) > 1:
    print("warning: pages were priced for different stores; use priced_for_store per row")
print(json.dumps(rows[:2], indent=1))
close_tab(tab)
```

Observed output (trimmed):

```
landed on: https://www.homedepot.com/b/Outdoors-Outdoor-Power-Equipment-Lawn-Mowers/N-5yc1vZc5ar | Lawn Mowers - The Home Depot
page 1: 27 products from graphql (3 sponsored, 0 repeats), 24 unique so far, store 4158, totalProducts=275
page 2: 26 products from graphql (3 sponsored, 0 repeats), 47 unique so far, store 4158, totalProducts=275
page 3: 27 products from graphql (3 sponsored, 0 repeats), 71 unique so far, store 4158, totalProducts=275
stopped: MAX_PAGES=3 cap hit; about 275 products in total, the rest NOT collected
store 4158 Hilltown | nearby: [('Montgomeryville', '4104'), ('Warrington', '4143'), ('West Norriton', '4145'), ('Willow Grove', '4187')]
[
 {
  "item_id": "337561634",
  "title": "40V HP Brushless 20 in. Cordless Battery Walk Behind Push Lawn Mower with 6.0 Ah Battery and Charger",
  "brand": "RYOBI",
  "model": "RY40HPLM06K",
  "price": 359,
  "was_price": 359,
  "priced_for_store": "4158",
  "rating": 4.5112,
  "reviews": 1254,
  "url": "https://www.homedepot.com/p/RYOBI-40V-HP-Brushless-20-in-Cordless-Battery-Walk-Behind-Push-Lawn-Mower-with-6-0-Ah-Battery-and-Charger-RY40HPLM06K/337561634",
  "sponsored": false,
  "stock": [
   {"service": "bopis", "store": "Hilltown", "store_id": "4158", "qty": 3, "in_stock": true, "limited": false},
   {"service": "sth", "store": null, "store_id": "8119", "qty": 531, "in_stock": true, "limited": false},
   {"service": "express delivery", "store": "Hilltown", "store_id": "4158", "qty": 423, "in_stock": true, "limited": false}
  ]
 },
 {
  "item_id": "327711060",
  "title": "21 in. 150cc Briggs and Stratton 625ex Engine Rear Wheel Drive 2-in-1 Gas Self Propelled Walk Behind Lawn Mower",
  "brand": "DEWALT",
  "model": "12A-O1T9739",
  ...
  "stock": []
 }
]
```

### 3. Product page: specs + store availability (browser)

```python
import json, re, time, urllib.error, urllib.parse, urllib.request

ITEM_ID = "320326875"   # the digits at the end of any /p/ URL, or item_id from the block 2 rows
UA = "browser-harness-domain-skill/1.0 (+https://github.com/browser-use/browser-harness)"   # robots.txt fetch only

# Record the product page's own GraphQL call (request + response) before page scripts run.
HOOK = """
(() => {
  if (window.__gql) return;
  window.__gql = [];
  const orig = window.fetch;
  window.fetch = async function (input, init) {
    const url = String((input && input.url) || input);
    const rec = url.includes('/federation-gateway/graphql?opname=productClientOnlyProduct')
      ? {url, body: init && init.body} : null;
    if (rec) window.__gql.push(rec);
    let res;
    try { res = await orig.apply(this, arguments); } catch (e) { if (rec) rec.err = String(e); throw e; }
    if (rec) { rec.status = res.status; try { rec.resp = await res.clone().text(); } catch (e) { rec.err = String(e); } }
    return res;
  };
})();
"""

READ = """(() => {
  const el = document.getElementById('thd-helmet__script--productStructureData');
  let ld = null; try { ld = el ? JSON.parse(el.textContent) : null; } catch (e) {}
  return {stale: !!window.__stale, ready: document.readyState, href: location.href, path: location.pathname,
          title: document.title, cookie: document.cookie.includes('THD_LOCALIZER='), ld,
          gql: (window.__gql || []).filter(r => r.status || r.err)};
})()"""

def get(url, tries=3):
    """Plain GET with a truthful UA (used for robots.txt). Retries timeouts, network errors, 429, 5xx
    with 10 s / 20 s backoff; any other error raises. No sleep after the last try."""
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code != 429 and e.code < 500:
                raise RuntimeError(f"{url}: HTTP {e.code}; blocked or gone, not retried") from e
            why = f"HTTP {e.code}"
        except OSError as e:
            why = f"network error ({e})"
        if attempt == tries:
            raise RuntimeError(f"{url}: {why} on {tries} tries; stop and back off")
        print(f"{url}: {why}; retry {attempt}/{tries - 1} in {10 * attempt}s")
        time.sleep(10 * attempt)

def robots_rules(text):
    rules, active = [], False
    for line in text.splitlines():
        key, _, val = line.split("#")[0].partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent":
            active = val == "*"
        elif active and key in ("allow", "disallow") and val:
            rules.append((key == "allow", val))
    return rules

def allowed(url, rules):
    """Longest matching rule wins, Allow wins a tie; `*` is a wildcard and a trailing `$` anchors."""
    u = urllib.parse.urlsplit(url)
    path = (u.path or "/") + ("?" + u.query if u.query else "")
    best = (-1, True)
    for allow, pat in rules:
        rx = re.escape(pat).replace(r"\*", ".*")
        rx = rx[:-2] + "$" if rx.endswith(r"\$") else rx
        if re.match(rx, path) and (len(pat), allow) > best:
            best = (len(pat), allow)
    return best[1]

def peek(expr):
    """js() that returns None while a navigation swaps the document (the harness reports a CDP
    timeout from js() as RuntimeError('Runtime.evaluate timed out') and from cdp() as TimeoutError)."""
    try:
        return js(expr)
    except TimeoutError:
        return None
    except RuntimeError as e:
        if "timed out" in str(e) or "context" in str(e).lower():
            return None
        raise

def open_page(url, done, label, secs=45, tries=3):
    """Navigate, poll READ on the new document until done(data). The 403 'Error Page' raises at once
    (blocked: stop and back off). A timeout is retried with backoff (20 s, 40 s), then raised."""
    if not allowed(url, RULES):
        raise RuntimeError(f"robots.txt disallows {url}; not opening it")
    for attempt in range(1, tries + 1):
        peek("window.__stale = true")
        try:
            goto_url(url)
        except TimeoutError:
            pass   # Page.navigate can outlast the harness's 5 s IPC timeout; the navigation still runs
        for _ in range(secs):
            time.sleep(1)
            d = peek(READ)
            if not d or d["stale"] or d["ready"] != "complete":
                continue
            if "Error Page" in (d["title"] or ""):
                raise RuntimeError(f"{label}: blocked (403 'Error Page') at {url}. Stop and back off; this is not retried.")
            if not allowed(d["href"], RULES):
                raise RuntimeError(f"{label}: landed on {d['href']}, which robots.txt disallows; stop")
            if done(d):
                return d
        if attempt == tries:
            raise RuntimeError(f"{label}: page not ready within {secs}s on {tries} tries ({url}); stop and back off")
        print(f"{label}: page not ready within {secs}s; retry {attempt}/{tries - 1} in {20 * attempt}s")
        time.sleep(20 * attempt)

def num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None

def obj(v):
    return v if isinstance(v, dict) else {}

def arr(v):
    return v if isinstance(v, list) else []

def ld_product(ld):
    """The JSON-LD Product for ITEM_ID (dict, list or @graph), else None."""
    items = ld if isinstance(ld, list) else arr(obj(ld).get("@graph")) or [ld]
    for it in items:
        if isinstance(it, dict) and it.get("@type") == "Product" and str(it.get("productID")) == ITEM_ID:
            return it
    return None

def first_image(img):
    # schema.org image: a URL string, an ImageObject dict, or a list of either
    for x in (img if isinstance(img, list) else [img]):
        if isinstance(x, str) and x:
            return x
        if isinstance(x, dict) and isinstance(x.get("url") or x.get("contentUrl"), str):
            return x.get("url") or x.get("contentUrl")
    return None

def for_item(rec):
    try:
        return str(json.loads(rec.get("body") or "{}")["variables"]["itemId"]) == ITEM_ID
    except (ValueError, KeyError, TypeError):
        return False

RULES = robots_rules(get("https://www.homedepot.com/robots.txt"))
if not RULES:
    raise RuntimeError("robots.txt has no User-agent: * rules (layout change?); stop")

tab = new_tab("about:blank")
cdp("Page.enable")
cdp("Page.addScriptToEvaluateOnNewDocument", source=HOOK)
# Warm-up: let the site pick a store (THD_LOCALIZER cookie) before the product page asks for stock.
open_page("https://www.homedepot.com/", lambda d: d["cookie"], "home page warm-up")
time.sleep(3)
# /p/<id> redirects to the canonical /p/<slug>/<id>; wait for that page's own JSON-LD.
d = open_page(f"https://www.homedepot.com/p/{ITEM_ID}",
              lambda d: d["path"].rstrip("/").endswith("/" + ITEM_ID) and ld_product(d["ld"]) is not None,
              "product page")
ld = ld_product(d["ld"])

# The page's own productClientOnlyProduct response: specs + fulfillment for the store the site picked.
rec = None
for _ in range(30):
    rec = next((r for r in arr(peek("(window.__gql || []).filter(r => r.status || r.err)")) if for_item(r)), None)
    if rec:
        break
    time.sleep(1)
product, avail_error = {}, None
if not rec:
    avail_error = "no productClientOnlyProduct call for this item within 30s"
elif rec.get("status") != 200:
    # Seen: HTTP 206 {"data":{"Generic Errors API":null}} after about a dozen page loads in one session.
    avail_error = f"productClientOnlyProduct HTTP {rec.get('status')} {(rec.get('resp') or rec.get('err') or '')[:80]}"
else:
    try:
        product = obj(obj(json.loads(rec["resp"]).get("data")).get("product"))
    except (ValueError, TypeError):
        avail_error = "productClientOnlyProduct returned non-JSON"
    if not product and not avail_error:
        avail_error = "productClientOnlyProduct returned no product"
if avail_error:
    print("warning:", avail_error, "- availability is null; stop and back off before more requests")
    # Specs only: the server-rendered Apollo cache has the spec table but no store inventory.
    product = obj(peek(f"(window.__APOLLO_STATE__ || {{}})['base-catalog-{ITEM_ID}'] || null"))

def availability(p):
    out = []
    for opt in arr(obj(p.get("fulfillment")).get("fulfillmentOptions")):
        for svc in arr(obj(opt).get("services")):
            for loc in arr(obj(svc).get("locations")):
                inv = obj(obj(loc).get("inventory"))
                out.append({
                    "option": opt.get("type"),            # pickup / delivery
                    "service": svc.get("type"),           # bopis, boss, sth, express delivery
                    "store": loc.get("storeName"),
                    "store_id": loc.get("locationId"),
                    "qty": num(inv.get("quantity")),
                    "in_stock": inv.get("isInStock"),
                    "limited": inv.get("isLimitedQuantity"),
                    "out_of_stock": inv.get("isOutOfStock"),
                    "dates": svc.get("deliveryDates"),
                })
    return out

offers = ld.get("offers")
offers = obj(offers[0] if isinstance(offers, list) and offers else offers)
agg = obj(ld.get("aggregateRating"))
brand = ld.get("brand")
reviews = num(agg.get("reviewCount"))
groups = [g for g in arr(product.get("specificationGroup")) if isinstance(g, dict)]
detail = {
    "item_id": ITEM_ID,
    "title": ld.get("name"),
    "brand": brand.get("name") if isinstance(brand, dict) else brand if isinstance(brand, str) else None,
    "model": ld.get("model"),
    "store_sku": ld.get("sku"),
    "gtin13": ld.get("gtin13"),
    "price": num(offers.get("price")),
    "rating": num(agg.get("ratingValue")),
    "reviews": int(reviews) if reviews is not None else None,
    "url": offers.get("url"),
    "image": first_image(ld.get("image")),
    "specs": {s.get("specName"): s.get("specValue")
              for g in groups for s in arr(g.get("specifications")) if isinstance(s, dict)},
    "spec_groups": [g.get("specTitle") for g in groups],
    "availability": None if avail_error else availability(product),
    "availability_error": avail_error,
    "discontinued": obj(product.get("availabilityType")).get("discontinued"),
}
print(json.dumps(detail, indent=1)[:3500])
close_tab(tab)
```

Observed output (trimmed):

```
{
 "item_id": "320326875",
 "title": "Milwaukee M18 FUEL 18V Lithium-Ion Brushless Cordless 1/4 in. Hex Impact Driver (Tool-Only) 2953-20",
 "brand": "Milwaukee",
 "model": "2953-20",
 "store_sku": "1007901520",
 "gtin13": "0045242637867",
 "price": 179,
 "rating": 4.7,
 "reviews": 2491,
 "url": "https://www.homedepot.com/p/Milwaukee-M18-FUEL-18V-Lithium-Ion-Brushless-Cordless-1-4-in-Hex-Impact-Driver-Tool-Only-2953-20/320326875",
 "image": "https://images.thdstatic.com/productImages/3ca82630-d888-44f5-bd56-b2798a6d59f8/svn/milwaukee-impact-drivers-2953-20-64_100.jpg",
 "specs": {
  "Battery Voltage (V)": "18V",
  "Battery/Charger": "Tool Only",
  "Drive Size": "1/4 In. Hex",
  "Maximum Speed (RPM)": "3900 RPM",
  "Motor Type": "Brushless",
  "Torque (In-Lbs)": "2000",
  "Manufacturer Warranty": "5 Year Limited Warranty",
  "Product Width (in.)": "9.5 in",
  ... (22 specs)
 },
 "spec_groups": ["Details", "Warranty / Certifications", "Dimensions"],
 "availability": [
  {"option": "pickup", "service": "bopis", "store": "Hilltown", "store_id": "4158",
   "qty": 0, "in_stock": false, "limited": true, "out_of_stock": false,
   "dates": {"startDate": "2026-10-23", ...}},
  {"option": "delivery", "service": "express delivery", "store": null, "store_id": "4104",
   "qty": 14, "in_stock": true, "limited": false, "out_of_stock": false,
   "dates": {"startDate": "2026-10-24", ...}}
 ],
 "availability_error": null,
 "discontinued": false
}
```

## Fields

Category rows (block 2), one dict per non-sponsored product, deduped by `item_id` (rows without an id are kept):

| Key | Source | Example / notes |
|---|---|---|
| `item_id` | `itemId` | the number at the end of `/p/` URLs; `None` if missing |
| `title` | `identifiers.productLabel` | without brand and model |
| `brand` | `identifiers.brandName` | |
| `model` | `identifiers.modelNumber` | |
| `price` | `pricing.value` | number, store-specific; SSR key is `pricing({"isBrandPricingPolicyCompliant":false,"storeId":"..."})` |
| `was_price` | `pricing.original` | number |
| `priced_for_store` | `metadata.stores.storeId` of the same page | |
| `rating` | `reviews.ratingsReviews.averageRating` | site sends a string; returned as float or `None` |
| `reviews` | `reviews.ratingsReviews.totalReviews` | site sends a string; returned as int or `None` |
| `url` | `identifiers.canonicalUrl` | made absolute |
| `sponsored` | `info.isSponsored` | always `False` in `rows` (sponsored items are skipped and counted) |
| `stock` | `fulfillment.fulfillmentOptions[].services[].locations[]` | list of `{service, store, store_id, qty, in_stock, limited}`; services seen: `bopis` (store pickup), `boss` (ship to store), `sth` (ship to home), `express delivery` |

Block 2 also prints the landing path and page title, per-page counts, the stop reason, and `metadata.stores` (`storeId`, `storeName`, `nearByStores[]`).

Product detail (block 3):

| Key | Source | Example / notes |
|---|---|---|
| `item_id` | `ITEM_ID`, checked against JSON-LD `productID` | `"320326875"` |
| `title` | JSON-LD `name` | brand + label + model |
| `brand` | JSON-LD `brand.name` (or a plain string) | `"Milwaukee"` |
| `model` | JSON-LD `model` | `"2953-20"` |
| `store_sku` | JSON-LD `sku` | `"1007901520"` |
| `gtin13` | JSON-LD `gtin13` | `"0045242637867"` |
| `price` | JSON-LD `offers.price` | number |
| `rating` | JSON-LD `aggregateRating.ratingValue` | site sends `"4.7"`; returned as float |
| `reviews` | JSON-LD `aggregateRating.reviewCount` | int |
| `url` | JSON-LD `offers.url` | canonical `/p/<slug>/<id>` |
| `image` | JSON-LD `image` | first image URL (string or ImageObject handled) |
| `specs` | GraphQL `product.specificationGroup[].specifications[]` | `{specName: specValue}` |
| `spec_groups` | `specificationGroup[].specTitle` | `["Details", "Warranty / Certifications", "Dimensions"]` |
| `availability` | GraphQL `product.fulfillment` | list of `{option, service, store, store_id, qty, in_stock, limited, out_of_stock, dates}`; `None` when the call failed |
| `availability_error` | | `None`, or why availability is missing (e.g. HTTP 206) |
| `discontinued` | `product.availabilityType.discontinued` | `false` |

## Gotchas

- **Install the fetch hook before navigating.** Blocks open `about:blank`, call `Page.addScriptToEvaluateOnNewDocument`, then navigate. A first version of the hook that pushed the record from an un-awaited `.then()` captured nothing in a background tab; awaiting `res.clone().text()` inside the wrapper (as in the blocks) worked in hidden tabs.
- **Read only the new document.** Before each navigation the blocks set `window.__stale` on the old page and skip any read where it is still set, then check the path (`/b/`, the same base path for later pages, `/<ITEM_ID>` for products) and, for products, that the JSON-LD `productID` and the GraphQL call's `variables.itemId` are the requested item.
- **Harness timeouts.** `goto_url()` and `js()` go through a 5 s IPC timeout. `cdp()` raises `TimeoutError`; `js()` re-raises it as `RuntimeError("Runtime.evaluate timed out ...")`. The blocks treat both as "not ready yet" inside their poll loops.
- **Server render is partial on category pages.** Both category pages tried had 12 products in `__APOLLO_STATE__` and fetched the full grid client-side; the Power Drills page reported `totalProducts` 260 in the server render and 271 in the GraphQL response a second later. Block 2 waits for the GraphQL grid (or a full server render) and does not use `totalProducts` to decide the end.
- **Sponsored items.** Lawn Mowers pages held 26 or 27 products, 3 of them sponsored, with no repeats across 3 pages. Block 2 skips `info.isSponsored` and dedupes by item ID. A short page (< 24 products) is treated as the end; a page of only repeats stops the run and says the rest was not collected.
- **Prices and stock are per store.** The store is picked from the browser's exit IP and changed between sessions (stores in several states across sessions on the same day). Before the `THD_LOCALIZER` cookie exists, the server rendered store 121 (Cumberland) on the first page of fresh sessions; after the cookie was set, the SSR keys switched to the local store. So a run that skips the warm-up can mix stores across pages. Each response's `metadata.stores.storeId` matches its own rows: block 2 copies it into `priced_for_store`, and `stock[].store_id` / `availability[].store_id` carry the `locationId` of each stock line (`sth` lines use a distribution center id such as 8119, not a store).
- **`quantity: 0` with `isLimitedQuantity: true`** (and `isOutOfStock: false`) appeared for in-store pickup on some rows, so 0 is not always "out of stock". Check `isOutOfStock`.
- **Out of stock at the home store** can return a second pickup location: one session got Secaucus `qty 0`, `out_of_stock: true` plus North Bergen (8475) qty 8; another got its home store out of stock plus `San Carlos` qty 2 and the page tile read "Pickup Nearby ... In stock 19 mi away".
- **Block page detection.** A blocked session serves `<title>Error Page</title>` with HTTP 403 for every URL. The blocks raise on it at once and do not retry; stop and back off.
- **Soft block on the product API.** After about a dozen page loads in one session, the product page's own `productClientOnlyProduct` call answered **HTTP 206** with `{"data":{"Generic Errors API":null},"error":[...]}` while the page itself still rendered. Block 3 then returns `availability: None` with `availability_error` set and takes the spec table from the already loaded Apollo cache (`base-catalog-<itemId>`, which has `specificationGroup` but no store inventory). Stop and back off.
- **Retry-After.** Block 2 honors `Retry-After` (seconds or HTTP-date) when the browser can read it, capped at 120 s (a longer ask stops the run); on the cross-origin `apionline.homedepot.com` calls it may not be exposed, and the block falls back to fixed backoff. No sleep follows the final attempt.
- **First page of a fresh session.** `wait_for_load()` returned while the tab was still an empty document (no title, no body) for about 10 s before the real page arrived and `THD_LOCALIZER` was set. The blocks poll for the data they need (cookie, JSON-LD, GraphQL, `SearchModel`) instead of trusting `wait_for_load()`.
- **Hidden tab scrolling.** `scroll()` timed out (5 s) on a background tab; no scrolling is needed for the blocks above, and none of them brings the tab to the foreground.
- No cookie/consent banner appeared from a US exit IP.

## What does not work

- **Keyword search**: `/s/<query>` and the `/b/...?NCNI-5&searchRedirect=...` page it redirects to are disallowed by robots.txt. Use block 1 to pick a category.
- **Availability at a store other than the session's**: the page's API lives on `apionline.homedepot.com`, whose robots.txt returned 403, so this skill does not re-send that request with another `storeId`.
- **Plain HTTP** (`curl`, `http_get`) to product pages: HTTP 403 "Error Page".
- **Heavy sessions**: after ~30 page loads in ~25 minutes, all pages in that session returned the 403 "Error Page". That is a block: stop and back off.
