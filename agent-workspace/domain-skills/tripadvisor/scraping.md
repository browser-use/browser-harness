# Tripadvisor — Scraping hotels and restaurants for a city

Field-tested against www.tripadvisor.com on 2026-10-23 using a Browser Use cloud browser (plain HTTP was also tried and is blocked); every code block re-run verbatim in a fresh cloud browser the same day.

robots.txt (checked 2026-10-23) allows the paths this skill loads (`/`, `/Tourism-`, `/Hotels-`, `/Restaurants-`, `/Hotel_Review-`, `/Restaurant_Review-`) for `User-agent: *` and disallows `/Search`; it disallows `/` entirely for named AI crawlers such as ClaudeBot, GPTBot and CCBot.

## Quick summary

- Plain HTTP is blocked (status 403, 778-byte block page) on the city hotel list and the city restaurant list; this skill uses a normal browser session.
- In the browser, logged out, no consent banner or captcha appeared across ~30 page loads (Boston and Lisbon, US-English site, USD).
- Every list page embeds a schema.org **`ItemList` JSON-LD** with the 30 organic results of that page (name, rating, review count, URL, address, geo, phone, price range). Rank, the "#N Best Value" text and the hotel "from $X" price come from the cards (`data-automation` attributes).
- Pagination is a URL offset: insert `-oa30-`, `-oa60-`, ... right after the `g<geoId>` segment. 30 ranked results per page, plus sponsored cards to skip.
- Hotels page 1 is special: it renders only 5 ranked hotels until you click **"See all N hotels"**; after that it has 30 like every other page.
- Detail pages (`Hotel_Review-...`, `Restaurant_Review-...`) embed `LodgingBusiness` / `FoodEstablishment` JSON-LD, and the visible "#N of M ... in City" popularity rank.

## What works

### 1. Find a city's list URLs (site typeahead)

The `/Search?q=` page rendered no results in this run. The header search box typeahead does, and its city option links to `Tourism-g<geoId>-<Slug>-Vacations.html`, from which the hotel and restaurant list URLs follow.

```python
import re, time

QUERY = "Lisbon"

new_tab("https://www.tripadvisor.com/")
time.sleep(2)
wait_for_load(30)
time.sleep(2)
xy = js("""(() => {
  const i = document.querySelector('input[aria-label="Search"], input[type="search"]');
  if (!i) return null;
  i.scrollIntoView({block: 'center'});
  const r = i.getBoundingClientRect();
  return [r.x + r.width / 2, r.y + r.height / 2];
})()""")
if not xy:
    raise SystemExit("search box not found")
click_at_xy(*xy)
time.sleep(1)
type_text(QUERY)
time.sleep(4)   # typeahead suggestions render as role="option" elements
options = js("""[...document.querySelectorAll('[role="option"]')].map(o => ({
  label: o.innerText.replace(/\\n/g, ' | ').trim(),
  href: (o.querySelector('a') || o.closest('a') || {}).href || null,
}))""") or []
cities = [o for o in options if o["href"] and "/Tourism-g" in o["href"]]
for o in cities:
    m = re.search(r"/Tourism-(g\d+)-(.+)-Vacations\.html", o["href"])
    o["restaurants_url"] = f"https://www.tripadvisor.com/Restaurants-{m.group(1)}-{m.group(2)}.html"
    o["hotels_url"] = f"https://www.tripadvisor.com/Hotels-{m.group(1)}-{m.group(2)}-Hotels.html"
    print(o)
press_key("Escape")
```

Real output (trimmed):

```
{'label': 'Lisbon | Central Portugal, Portugal', 'href': 'https://www.tripadvisor.com/Tourism-g189158-Lisbon_Lisbon_District_Central_Portugal-Vacations.html', 'restaurants_url': 'https://www.tripadvisor.com/Restaurants-g189158-Lisbon_Lisbon_District_Central_Portugal.html', 'hotels_url': 'https://www.tripadvisor.com/Hotels-g189158-Lisbon_Lisbon_District_Central_Portugal-Hotels.html'}
{'label': 'Lisbon | Ohio, United States', 'href': 'https://www.tripadvisor.com/Tourism-g50559-Lisbon_Ohio-Vacations.html', ...}
```

Same-name places exist (Lisbon, Portugal / Ohio / New Hampshire), so pick by label. Both derived URLs loaded correctly for Lisbon in this run.

### 2. Restaurants: 3 pages (90 ranked restaurants)

```python
import json, re, time
from urllib.parse import urljoin

CITY_URL = "https://www.tripadvisor.com/Restaurants-g60745-Boston_Massachusetts.html"
PAGES = 3          # 30 ranked restaurants per page
PER_PAGE = 30

def page_url(city_url, page):
    # page 1 = city URL; page N inserts -oa<30*(N-1)>- right after the g<geoId> segment
    if page == 1:
        return city_url
    return re.sub(r"-(g\d+)-", lambda m: f"-{m.group(1)}-oa{PER_PAGE * (page - 1)}-", city_url, count=1)

def open_page(url, first=False):
    new_tab(url) if first else goto_url(url)
    time.sleep(2)
    wait_for_load(30)
    wait_for_element('[data-automation="restaurantCard"]', timeout=20)
    time.sleep(1.5)

def ld_itemlist():
    for s in js("[...document.querySelectorAll('script[type=\"application/ld+json\"]')].map(s => s.textContent)") or []:
        try:
            d = json.loads(s)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "ItemList":
            return [e.get("item", {}) for e in d.get("itemListElement", [])]
    return []

CARDS_JS = r"""
[...document.querySelectorAll('[data-automation="restaurantCard"]')].map(c => {
  const a = c.querySelector('a[href*="Restaurant_Review-"]');
  const lines = c.innerText.split('\n').map(s => s.trim()).filter(Boolean);
  const title = lines.find(l => /^\d+\.\s/.test(l)) || null;
  return {
    href: a ? a.getAttribute('href') : null,
    rank: title ? parseInt(title) : null,           // null = Sponsored card
    name: title ? title.replace(/^\d+\.\s*/, '') : lines.find(l => l !== 'MICHELIN'),
    rating: (c.querySelector('[data-automation="bubbleRatingValue"]') || {}).innerText || null,
    reviews: (c.querySelector('[data-automation="bubbleReviewCount"]') || {}).innerText || null,
    price: lines.find(l => /^\$+( - \$+)?$/.test(l)) || null,
  };
})
"""

def loc_id(url):
    m = re.search(r"-d(\d+)-", url or "")
    return m.group(1) if m else None

rows, seen = [], set()
for p in range(1, PAGES + 1):
    open_page(page_url(CITY_URL, p), first=(p == 1))
    ld = {loc_id(i.get("url")): i for i in ld_itemlist()}
    total = js("(document.querySelector('[data-automation=\"resultsTotal\"]') || {}).innerText || null")
    for c in js(CARDS_JS) or []:
        lid = loc_id(c["href"])
        if c["rank"] is None or not lid or lid in seen:
            continue                                   # skip sponsored cards and repeats
        seen.add(lid)
        j = ld.get(lid, {})
        agg = j.get("aggregateRating") or {}
        addr = j.get("address") or {}
        rows.append({
            "rank": c["rank"],
            "name": j.get("name") or c["name"],
            "rating": float(agg.get("ratingValue") or c["rating"] or 0) or None,
            "review_count": agg.get("reviewCount") or int(re.sub(r"\D", "", c["reviews"] or "") or 0) or None,
            "price_level": j.get("priceRange") or c["price"],
            "cuisine": j.get("servesCuisine"),
            "address": addr.get("streetAddress"),
            "telephone": j.get("telephone"),
            "url": urljoin("https://www.tripadvisor.com", c["href"]).split("?")[0].split("#")[0],
            "location_id": lid,
        })
    print(f"page {p}: {js('location.href')} total={total} rows so far={len(rows)}")
    time.sleep(4)   # polite pacing between pages

print(json.dumps(rows[:2], indent=1))
print([(r["rank"], r["name"]) for r in rows[-3:]])
print("ranks contiguous:", [r["rank"] for r in rows] == list(range(1, len(rows) + 1)))
```

Real output (trimmed):

```
page 1: https://www.tripadvisor.com/Restaurants-g60745-Boston_Massachusetts.html total=2,561 results rows so far=30
page 2: https://www.tripadvisor.com/Restaurants-g60745-oa30-Boston_Massachusetts.html total=2,561 results rows so far=60
page 3: https://www.tripadvisor.com/Restaurants-g60745-oa60-Boston_Massachusetts.html total=2,561 results rows so far=90
[
 {
  "rank": 1,
  "name": "Cafe Bonjour",
  "rating": 4.7,
  "review_count": 312,
  "price_level": "$$ - $$$",
  "cuisine": "French, Cafe",
  "address": "55 Temple Place, Boston, MA 02111",
  "telephone": "+1 617-779-0062",
  "url": "https://www.tripadvisor.com/Restaurant_Review-g60745-d19799010-Reviews-Cafe_Bonjour-Boston_Massachusetts.html",
  "location_id": "19799010"
 }, ...
]
[(88, "Rino's Place"), (89, 'Krasi'), (90, 'Sweet Cheeks Q')]
ranks contiguous: True
```

The same script with the Lisbon URL returned 60 rows over 2 pages, `total=6,462 results`, first row `Floresta Das Escadinhas`, rating 4.8, 7365 reviews, `$`.

### 3. Hotels: 2 pages (60 ranked hotels)

```python
import json, re, time
from urllib.parse import urljoin

CITY_URL = "https://www.tripadvisor.com/Hotels-g60745-Boston_Massachusetts-Hotels.html"
PAGES = 2          # 30 ranked hotels per page
PER_PAGE = 30
TITLES = '[data-automation="hotel-card-title"]'

def page_url(city_url, page):
    if page == 1:
        return city_url
    return re.sub(r"-(g\d+)-", lambda m: f"-{m.group(1)}-oa{PER_PAGE * (page - 1)}-", city_url, count=1)

def ranked_count():
    return js(f"[...document.querySelectorAll('{TITLES}')].filter(e => /^\\d+\\./.test(e.innerText)).length") or 0

def open_page(url, first=False):
    new_tab(url) if first else goto_url(url)
    time.sleep(2)
    wait_for_load(30)
    wait_for_element(TITLES, timeout=20)
    time.sleep(2)

SEE_ALL_JS = """[...document.querySelectorAll('button')].find(b => /^See all [\\d,]+ hotels/.test(b.innerText.trim()))"""

def expand_first_page():
    """Page 1 renders only 5 ranked hotels until 'See all N hotels' is clicked. Raises instead of scraping 5."""
    m = re.search(r"([\d,]+) properties in ", js("document.body.innerText") or "")
    if not m:
        raise RuntimeError("'N properties in City' total not found on page 1")
    want = min(PER_PAGE, int(m.group(1).replace(",", "")))   # small cities have fewer than 30
    if ranked_count() >= want:
        return
    if not js(f"(() => {{ const b = {SEE_ALL_JS}; if (!b) return false; b.scrollIntoView({{block: 'center'}}); return true; }})()"):
        raise RuntimeError(f"'See all N hotels' button not found; page 1 has {ranked_count()} of {want} ranked hotels")
    time.sleep(1.5)
    press_key("Escape")          # scrolling can pop the sticky date picker over the button
    time.sleep(1)
    xy = js(f"(() => {{ const r = ({SEE_ALL_JS}).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }})()")
    click_at_xy(*xy)
    for _ in range(20):
        if ranked_count() >= want:
            return
        time.sleep(0.5)
    raise RuntimeError(f"'See all' click did not expand page 1: {ranked_count()} of {want} ranked hotels after 10 s")

def ld_itemlist():
    for s in js("[...document.querySelectorAll('script[type=\"application/ld+json\"]')].map(s => s.textContent)") or []:
        try:
            d = json.loads(s)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") == "ItemList":
            return [e.get("item", {}) for e in d.get("itemListElement", [])]
    return []

CARDS_JS = r"""
[...document.querySelectorAll('[data-automation="hotel-card-title"]')].map(t => {
  const c = t.closest('li') || t.parentElement;
  const a = c.querySelector('a[href*="Hotel_Review-"]');
  const text = c.innerText;
  const price = text.match(/(?:^|\n)from\n([^\n]*\d[^\n]*)/);   // "from\n$165"; descriptions also say "from South Station"
  return {
    title: t.innerText.trim(),
    href: a ? a.getAttribute('href') : null,
    rating: (c.querySelector('[data-automation="bubbleRatingValue"]') || {}).innerText || null,
    reviews: (c.querySelector('[data-automation="bubbleReviewCount"]') || {}).innerText || null,
    rank_text: (text.match(/#\d[\d,]* [^\n]* of [\d,]+ [^\n]*/) || [null])[0],
    price_from: price ? price[1] : null,
  };
})
"""

def loc_id(url):
    m = re.search(r"-d(\d+)-", url or "")
    return m.group(1) if m else None

rows, seen = [], set()
for p in range(1, PAGES + 1):
    open_page(page_url(CITY_URL, p), first=(p == 1))
    if p == 1:
        expand_first_page()
    ld = {loc_id(i.get("url")): i for i in ld_itemlist()}
    for c in js(CARDS_JS) or []:
        m = re.match(r"(\d+)\.\s*(.+)", c["title"])
        lid = loc_id(c["href"])
        if not m or not lid or lid in seen:
            continue                                   # no "N." prefix = Sponsored card
        seen.add(lid)
        j = ld.get(lid, {})
        addr = j.get("address") or {}
        rows.append({
            "rank": int(m.group(1)),
            "name": m.group(2),
            "rating": float(c["rating"]) if c["rating"] else None,
            "review_count": int(re.sub(r"\D", "", c["reviews"] or "") or 0) or None,
            "rank_text": c["rank_text"],
            "price_from": c["price_from"],
            "price_tier": j.get("priceRange"),
            "address": ", ".join(filter(None, [addr.get("streetAddress"), addr.get("addressLocality")])) or None,
            "url": urljoin("https://www.tripadvisor.com", c["href"]).split("?")[0].split("#")[0],
            "location_id": lid,
        })
    print(f"page {p}: {js('location.href')} rows so far={len(rows)}")
    time.sleep(4)   # polite pacing between pages

print(json.dumps(rows[:2], indent=1))
print([(r["rank"], r["name"], r["price_from"]) for r in rows[-3:]])
print("ranks contiguous:", [r["rank"] for r in rows] == list(range(1, len(rows) + 1)))
print("rows joined to JSON-LD:", sum(1 for r in rows if r["address"]))
print("rows with a price:", sum(1 for r in rows if r["price_from"]))
```

Real output (trimmed):

```
page 1: https://www.tripadvisor.com/Hotels-g60745-Boston_Massachusetts-Hotels.html rows so far=30
page 2: https://www.tripadvisor.com/Hotels-g60745-oa30-Boston_Massachusetts-Hotels.html rows so far=60
[
 {
  "rank": 1,
  "name": "Cambria Hotel Boston Downtown",
  "rating": 4.2,
  "review_count": 244,
  "rank_text": "#1 Best Value of 293 places to stay in Boston",
  "price_from": "$165",
  "price_tier": "€",
  "address": "6 W Broadway, Boston",
  "url": "https://www.tripadvisor.com/Hotel_Review-g60745-d15618152-Reviews-Cambria_Hotel_Boston_Downtown-Boston_Massachusetts.html",
  "location_id": "15618152"
 }, ...
]
[(58, 'Hyatt Regency Boston', '$237'), (59, 'Boston Harbor Hotel', '$502'), (60, 'Boston Marriott Long Wharf', '$234')]
ranks contiguous: True
rows joined to JSON-LD: 60
rows with a price: 60
```

With the Lisbon hotels URL and `PAGES = 3` the same script returned 90 contiguous ranks, `#1 Best Value of 2,494 places to stay in Lisbon` (Hotel Da Baixa, 4.9, 3479 reviews, from $273), all 90 joined to JSON-LD.

### 4. Detail page basics (hotel or restaurant)

```python
import json, re, time

URLS = [
    "https://www.tripadvisor.com/Hotel_Review-g60745-d15618152-Reviews-Cambria_Hotel_Boston_Downtown-Boston_Massachusetts.html",
    "https://www.tripadvisor.com/Restaurant_Review-g60745-d19799010-Reviews-Cafe_Bonjour-Boston_Massachusetts.html",
]
TYPES = {"LodgingBusiness", "Hotel", "FoodEstablishment", "Restaurant"}

def detail(url, first=False):
    new_tab(url) if first else goto_url(url)
    time.sleep(2)
    wait_for_load(30)
    time.sleep(2)
    j = {}
    for s in js("[...document.querySelectorAll('script[type=\"application/ld+json\"]')].map(s => s.textContent)") or []:
        try:
            d = json.loads(s)
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("@type") in TYPES:
            j = d
            break
    text = js("document.body.innerText") or ""
    rank = re.search(r"#\d[\d,]* of [\d,]+ [^\n]+", text)
    stars = re.search(r"(\d(?:\.\d)?) of 5 stars", text)
    agg = j.get("aggregateRating") or {}
    addr = j.get("address") or {}
    cuisine = j.get("servesCuisine")
    return {
        "type": j.get("@type"),
        "name": j.get("name"),
        "rating": float(agg["ratingValue"]) if agg.get("ratingValue") else None,
        "review_count": agg.get("reviewCount"),
        "popularity_rank": rank.group(0) if rank else None,
        "price_level": j.get("priceRange"),
        "hotel_class": float(stars.group(1)) if stars and j.get("@type") in ("LodgingBusiness", "Hotel") else None,
        "cuisine": ", ".join(cuisine) if isinstance(cuisine, list) else cuisine,
        "address": ", ".join(filter(None, [addr.get("streetAddress"), addr.get("addressLocality"), addr.get("postalCode")])),
        "telephone": j.get("telephone"),
        "geo": [j["geo"]["latitude"], j["geo"]["longitude"]] if j.get("geo") else None,
        "amenities": [a["name"] for a in j.get("amenityFeatures") or [] if a.get("value")][:10],
        "opening_hours": [(h.get("dayOfWeek"), h.get("opens"), h.get("closes")) for h in j.get("openingHoursSpecification") or []],
        "url": j.get("url") or url,
        "location_id": (re.search(r"-d(\d+)-", url) or [None, None])[1],
    }

for i, u in enumerate(URLS):
    print(json.dumps(detail(u, first=(i == 0)), indent=1))
    time.sleep(4)
```

Real output (trimmed):

```
{
 "type": "LodgingBusiness",
 "name": "Cambria Hotel Boston Downtown",
 "rating": 4.2,
 "review_count": 244,
 "popularity_rank": "#68 of 96 hotels in Boston",
 "price_level": "$ (Based on Average Nightly Rates for a Standard Room from our Partners)",
 "hotel_class": 4.0,
 "address": "6 W Broadway, Boston, 02127-1016",
 "telephone": "1 (617) 463-9147",
 "geo": [42.343216, -71.05699],
 "amenities": ["Valet parking", "Free High Speed Internet (WiFi)", "Fitness Center with Gym / Workout Room", ...],
 ...
 "location_id": "15618152"
}
{
 "type": "FoodEstablishment",
 "name": "Cafe Bonjour",
 "rating": 4.7,
 "review_count": 312,
 "popularity_rank": "#2 of 2,612 Restaurants in Boston",
 "price_level": "$$ - $$$",
 "cuisine": "French, Cafe",
 "opening_hours": [["Sunday", "07:00:00", "15:00:00"], ...],
 ...
 "location_id": "19799010"
}
```

## Fields

| Field | Where | Source | Example |
|---|---|---|---|
| `rank` | lists | card title `"N. Name"` (`hotel-card-title` / `restaurantCard`) | `1` |
| `name` | lists, detail | JSON-LD `name` or card title | `"Cafe Bonjour"` |
| `rating` | lists, detail | JSON-LD `aggregateRating.ratingValue` or `bubbleRatingValue` | `4.7` |
| `review_count` | lists, detail | JSON-LD `aggregateRating.reviewCount` or `bubbleReviewCount` `"(312 reviews)"` | `312` |
| `price_level` | restaurant list, detail | JSON-LD `priceRange` | `"$$ - $$$"`, `"$$$$"`, `"$"` |
| `rank_text` | hotel list | card text | `"#1 Best Value of 293 places to stay in Boston"` |
| `price_from` | hotel list | card text after `from` (default dates, USD) | `"$165"` |
| `price_tier` | hotel list | ItemList JSON-LD `priceRange` | `"€"`, `"€€"` |
| `cuisine` | restaurant list, detail | JSON-LD `servesCuisine` (string in list, array on detail) | `"French, Cafe"` |
| `address` | lists, detail | JSON-LD `address` | `"55 Temple Place, Boston, MA 02111"` |
| `telephone` | restaurant list, detail | JSON-LD `telephone` | `"+1 617-779-0062"` |
| `geo` | detail | JSON-LD `geo` (also in the list ItemList, not extracted above) | `[42.343216, -71.05699]` |
| `popularity_rank` | detail | page text `#N of M ... in City` | `"#68 of 96 hotels in Boston"` |
| `hotel_class` | hotel detail | page text `N of 5 stars` | `4.0` |
| `amenities` | hotel detail | JSON-LD `amenityFeatures[].name` | `"Valet parking"` |
| `opening_hours` | restaurant detail | JSON-LD `openingHoursSpecification` | `("Sunday", "07:00:00", "15:00:00")` |
| `location_id` | lists, detail | `-d<id>-` in the URL, stable join key | `"19799010"` |
| total results | restaurant list | `[data-automation="resultsTotal"]` | `"2,561 results"` |

## Gotchas

- **Hotels page 1 shows only 5 ranked hotels.** The 30-item list appears only after clicking "See all N hotels" (URL does not change; ItemList JSON-LD grows from 8 to 30). Scrolling that button into view opened the sticky check-in date picker on top of it in this run, and a blind click picked a date instead. Press Escape, then click. `expand_first_page()` raises if the button is missing or the list does not grow, so a failed click never yields a silent 5-row page. Its target is `min(30, "N properties in City")`: Lisbon, Ohio shows `6 properties in Lisbon` with all 6 ranked and a "See all 34 hotels" button (nearby towns), so small cities need no click.
- **Pages 2+ need no click.** `-oa30-`, `-oa60-` load 30 ranked hotels directly. `-oa0-` and `-oa5-` redirect to page 1 (the 5-hotel view).
- **JSON-LD `position` restarts at 1 on every page.** Take the global rank from the card title (`"31. The Bostonian Hotel Boston"`), not from `position`.
- **Sponsored cards** have no `"N."` prefix (hotels: a `Sponsored` label; the same sponsored hotel appeared twice on one page). Sponsored hotel links are absolute and carry `?spAttributionToken=`. Skip them and dedupe by `location_id`.
- **List rank is not the detail rank.** Hotel lists default to "Best Value" sort (`#1 Best Value of 293 places`), restaurant lists to "Featured". The detail page shows a different popularity rank (Cambria: #1 Best Value in the list, `#68 of 96 hotels` on its page; Cafe Bonjour: rank 1 in the list, `#2 of 2,612 Restaurants`). Record which one you store. List counts also differ from detail counts (2,561 list results vs 2,612 on detail).
- **Hotel `price_from` depends on the default dates** the site pre-fills (here 1 night, Nov 01-02, 1 room, 2 guests) and on currency (USD). Hotel list JSON-LD `priceRange` is a tier written in euro signs even on the USD site; hotel detail `priceRange` is `"$ (Based on Average Nightly Rates ...)"`.
- **Do not regex `from (\S+)` for the hotel price.** AI-written card descriptions contain phrases like "from South Station"; a loose regex returned `"South"` once. The price sits on its own line after a line that is exactly `from`.
- **Hotel order on pages 2+ shifted between two loads minutes apart** (rank 58 was Hyatt Regency Boston in one run, HI Boston - Hostel in the next). Scrape all pages in one session and dedupe by `location_id`; do not stitch pages from different runs.
- **Hotel list JSON-LD `url` points to `HotelHighlight-...?m=...`**, not `Hotel_Review-...`. Join on `location_id` and use the card link for the canonical URL. Restaurant list JSON-LD uses `Restaurant_Review-...?m=...`.
- **Restaurant list `address.streetAddress` holds the full address**; `addressLocality` is empty in the list but filled on the detail page.
- **`wait_for_load()` right after `goto_url()` can return for the previous page.** Sleep ~2 s first and wait for a card selector.
- **Pacing:** ~30 page loads with 3-5 s between them produced no captcha, block or consent dialog. Keep the delay; Tripadvisor bot-protects the plain HTTP path, so do not hammer the browser path either.
- Detail pages also show reviewer names and review text; this skill does not extract them.

## What does not work

- **Plain HTTP:** plain HTTP is blocked (status 403) for `Hotels-g60745-Boston_Massachusetts-Hotels.html` and `Restaurants-g60745-Boston_Massachusetts.html`; this skill uses a normal browser session.
- **`/Search?q=Lisbon+Portugal`** rendered only the header and footer in the browser (no result links after 10+ s). Use the typeahead (block 1).
- **Clicking "See all N hotels" without closing the date picker** selects a calendar date instead and leaves 5 hotels on the page.
- **`-oa0-` / `-oa5-` offsets** redirect to the unexpanded page 1; only multiples of 30 from `-oa30-` up behaved as pages in this run.
