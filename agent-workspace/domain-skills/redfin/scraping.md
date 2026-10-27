# Redfin — For-sale listings by city or ZIP, plus listing details

Field-tested against www.redfin.com on 2026-10-23 (reworked the same day to use only robots.txt-allowed pages) using a Browser Use cloud browser.

robots.txt (checked 2026-10-23) disallows `/stingray/` for `User-agent: *`; this skill never requests it. It only loads search pages (`/zipcode/<zip>` and `/city/<id>/<ST>/<City>`, the two tested here; block 1 also accepts `/neighborhood/...` and `/county/...` paths), their `/page-<n>` pages, and listing pages (`/<ST>/<City>/<address>/home/<id>`). None of those is disallowed for that group.

## Quick summary

- A Redfin search page (`/zipcode/78704`, `/city/30818/TX/Austin`) renders about 41 listing cards per page and also embeds, in its HTML, the server-rendered map data for up to 350 homes: address, price, beds, baths, sqft, status, lot size, year built, HOA, days on market, MLS id, lat/long and URL.
- A ZIP with 350 homes or fewer comes back complete from one page load: ZIP 78704 gave all 332 homes the page header counted.
- Bigger results are paged through `/page-<n>` (the site's own pagination links). Homes beyond the first 350 come from the card itself (address, price, beds, baths, sqft, lat/long, URL) without status, lot, year built, HOA or MLS id. The city of Austin, TX (header: 5,788 homes + 120 early access) took 150 page loads in about 15 minutes and gave 5,796 unique homes, 112 (1.9%) short of the header, so with its default 1% tolerance block 1 raises there; details below.
- Listing pages carry a `["Product", "RealEstateListing"]` JSON-LD block (price, beds, baths, sqft, year built, geo, photos, description) and embed the detail data the page was rendered from (status, lot size, full/half baths, every MLS fact group).
- Plain HTTP is blocked (status 429); this skill uses a normal browser session.

## What works

### 1. Search a ZIP or city and collect every listing (browser)

Self-contained. Change `SEARCH` to a ZIP or to a search page path. Writes JSON and CSV to the system temp dir.

```python
import json, time, csv, os, re, tempfile

SEARCH = "78704"     # a ZIP, or a Redfin search page path such as "/city/30818/TX/Austin"
MAX_PAGES = 200      # safety cap on list pages (raises if hit); Austin needed 150
PAUSE = 3.0          # seconds between page loads
MAX_SHORT = 0.01     # raise if more than this share of the header count is missing (a live count drifts a little)
BASE = "https://www.redfin.com"

def search_path(s):
    s = s.strip()
    if re.fullmatch(r"\d{5}", s):
        return f"/zipcode/{s}"
    s = re.sub(r"/page-\d+$", "", s.replace(BASE, "").split("?")[0].rstrip("/"))
    if not re.match(r"^/(city|zipcode|neighborhood|county)/", s):
        raise SystemExit(f"SEARCH must be a ZIP or a Redfin /city/, /zipcode/, /neighborhood/ or /county/ path, got {s!r}")
    return s

BLOCKED = re.compile(r"request could not be satisfied|ratelimited|access denied|are you a human|captcha", re.I)
CARDS = '[data-rf-test-name="basicNode-homeCard"]'
ZERO = ".ZeroResultsText, .nearbyHomesTitle"   # "We didn't find any exact matches" / "Homes within 1 mile of ..."
POLL_JS = ("JSON.stringify({old: !!window.__bhOld, u: location.href, t: document.title, r: document.readyState, "
           "n: document.querySelectorAll('%s').length, z: !!document.querySelector('%s')})" % (CARDS.replace("'", "\\'"), ZERO))

def open_page(url, budget=120, per_try=30):
    """Load url in the tab and wait for the new document. Returns the URL it landed on: url itself once result
    cards (or Redfin's no-exact-matches view) have rendered, or the redirect target, which the caller must check.
    A block or challenge page raises at once (stop and back off). A page that never renders is retried after
    10 s, then 20 s, all inside one budget-second deadline; then it raises."""
    end, pause, attempt = time.time() + budget, 10, 0
    while True:
        attempt += 1
        before = js("window.__bhOld = 1, location.href")   # tag the old document; the new one will not carry the tag
        try:
            goto_url(url)
        except Exception as e:       # Page.navigate often outlives the 5 s daemon wait on these heavy pages
            print("navigate still running:", str(e)[:80])
        stop, n, z, last = min(end, time.time() + per_try), -1, False, None
        while time.time() + 1 < stop:   # the last poll starts before the deadline
            time.sleep(1)
            try:
                st = last = json.loads(js(POLL_JS))
            except Exception:
                continue                 # page still busy; poll again
            if st["old"]:
                continue                 # still the document from before the navigation
            if BLOCKED.search(st["t"]) or "ratelimited" in st["u"]:
                raise RuntimeError(f"Redfin served a block/challenge page ({st['t']!r} at {st['u']}). Stop and back off.")
            if st["r"] != "complete":
                continue
            if st["u"].rstrip("/") != url.rstrip("/"):
                return st["u"]           # a new document at another URL: redirected
            if (st["n"] > 0 and st["n"] == n) or (st["z"] and z):
                return st["u"]           # card count (or the zero-results view) stable across two polls
            n, z = st["n"], st["z"]
        print(f"try {attempt}: {url} not ready (navigated from {before}; last state {last})")
        if time.time() + pause + 15 > end:
            break                        # no time left for a backoff and another try; no sleep after the last one
        time.sleep(pause)
        pause *= 2
    raise RuntimeError(f"{url} did not render within the {budget} s budget ({attempt} tries)")

def header_total():
    """'323 homes + 9 early access' -> 332."""
    t = js("(document.querySelector('.homes.summary, [data-rf-test-id=\"homes-description\"]') || {}).innerText || ''")
    nums = [int(x.replace(",", "")) for x in re.findall(r"([\d,]+) (?:homes?|early access)", t)]
    if not nums:
        if js("!!document.querySelector('%s')" % ZERO):
            return 0, "no exact matches"
        raise RuntimeError(f"could not read the result count from the page header: {t!r}")
    return sum(nums), t

# The search page HTML embeds the server-rendered map data (up to 350 homes) in __reactServerState.
GIS_JS = r"""(() => {
  const s = [...document.scripts].find(s => !s.src && s.textContent.includes('__reactServerState.InitialContext = '));
  if (!s) return null;
  const p = 'root.__reactServerState.InitialContext = ';
  const line = s.textContent.split('\n').find(l => l.startsWith(p));
  const dc = JSON.parse(line.slice(p.length, -1))['ReactServerAgent.cache'].dataCache;
  const k = Object.keys(dc).find(k => k.startsWith('/stingray/api/gis?'));
  return k ? dc[k].res.text : null;
})()"""

def embedded_homes():
    t = js(GIS_JS)
    if not t or not t.startswith("{}&&"):
        raise RuntimeError("no embedded map data on the search page: " + str(t)[:120])
    d = json.loads(t[4:])                # strip the "{}&&" prefix
    if d.get("resultCode") != 0 or not isinstance((d.get("payload") or {}).get("homes"), list):
        raise RuntimeError("unexpected embedded map data: " + t[:160])
    return {h["propertyId"]: h for h in d["payload"]["homes"]}

CARD_JS = r"""JSON.stringify([...document.querySelectorAll('[data-rf-test-name="basicNode-homeCard"]')].map(c => {
  const t = s => { const e = c.querySelector(s); return e ? e.textContent.trim() : null; };
  const a = c.querySelector('a.bp-Homecard__Address');
  let ld = null; const s = c.querySelector('script[type="application/ld+json"]');
  if (s) { try { ld = JSON.parse(s.textContent); } catch (e) {} }
  return {href: a && a.getAttribute('href'), address: a && a.textContent.trim(), price: t('.bp-Homecard__Price--value'),
    beds: t('.bp-Homecard__Stats--beds'), baths: t('.bp-Homecard__Stats--baths'), sqft: t('.bp-Homecard__Stats--sqft'),
    sashes: [...c.querySelectorAll(':scope > .bp-Homecard__Sashes [data-rf-test-id="home-sash"]')].map(e => e.textContent.trim()),
    ld};
}))"""

def num(s):
    m = re.search(r"[\d,.]+", s or "")
    return float(m.group().replace(",", "")) if m and m.group().strip(".,") else None

def v(x):
    return x.get("value") if isinstance(x, dict) else x

def from_embedded(h):
    ll = v(h.get("latLong")) or {}
    return {
        "property_id": h.get("propertyId"), "listing_id": h.get("listingId"), "mls_id": v(h.get("mlsId")),
        "address": v(h.get("streetLine")), "city": h.get("city"), "state": h.get("state"), "zip": h.get("zip"),
        "price": v(h.get("price")), "beds": h.get("beds"), "baths": h.get("baths"), "sqft": v(h.get("sqFt")),
        "lot_sqft": v(h.get("lotSize")), "year_built": v(h.get("yearBuilt")), "price_per_sqft": v(h.get("pricePerSqFt")),
        "hoa_month": v(h.get("hoa")), "days_on_market": v(h.get("dom")), "status": h.get("mlsStatus"),
        "neighborhood": v(h.get("location")), "lat": ll.get("latitude"), "lon": ll.get("longitude"),
        "url": BASE + h["url"] if h.get("url") else None, "source": "embedded",
    }

def from_card(c, pid):
    ld = c.get("ld") or []
    ld = [x for x in (ld if isinstance(ld, list) else [ld]) if isinstance(x, dict)]   # a card's JSON-LD can be one object or a list
    home = next((x for x in ld if x.get("address")), {})
    offer = next((x.get("offers") for x in ld if x.get("offers")), {}) or {}
    addr, geo = home.get("address") or {}, home.get("geo") or {}
    price = offer.get("price") or num(c.get("price"))
    sq, sqft, lot = c.get("sqft") or "", None, None
    if "(lot)" in sq:                    # land cards say "Land" and "0.38 acre (lot)" or "9,557 sq ft (lot)"
        n = num(sq)
        lot = None if n is None else round(n * 43560 if "acre" in sq else n)
    else:
        sqft = num(sq)
    return {
        "property_id": pid, "listing_id": None, "mls_id": None,
        "address": addr.get("streetAddress") or (c.get("address") or "").split(",")[0],
        "city": addr.get("addressLocality"), "state": addr.get("addressRegion"), "zip": addr.get("postalCode"),
        "price": int(float(price)) if price else None, "beds": num(c.get("beds")), "baths": num(c.get("baths")),
        "sqft": sqft, "lot_sqft": lot, "year_built": None, "price_per_sqft": None, "hoa_month": None,
        "days_on_market": None, "status": None, "neighborhood": None,
        "lat": geo.get("latitude"), "lon": geo.get("longitude"), "url": BASE + c["href"], "source": "card",
    }

path = search_path(SEARCH)
new_tab()
landed = open_page(BASE + path)
if landed.rstrip("/") != BASE + path:
    raise RuntimeError(f"{BASE + path} redirected to {landed}; check SEARCH")
total, header = header_total()
emb = embedded_homes() if total else {}
print(f"{path}: header says {header!r} -> {total}; embedded map data has {len(emb)} homes")

rows = {}
if len(emb) >= total:                     # the whole result set is in the page's embedded map data
    for pid, h in emb.items():
        rows[pid] = from_embedded(h)
else:                                     # page through the list (about 41 cards per page)
    page = 1
    while True:
        cards = json.loads(js(CARD_JS))
        new = 0
        for c in cards:
            m = re.search(r"/home/(\d+)", c.get("href") or "")
            if not m:
                continue
            pid = int(m.group(1))
            if pid not in rows:
                rows[pid] = from_embedded(emb[pid]) if pid in emb else from_card(c, pid)
                new += 1
        print(f"page {page}: {len(cards)} cards, {new} new, {len(rows)} unique so far")
        if len(rows) >= total or new == 0:
            break
        page += 1
        if page > MAX_PAGES:
            raise RuntimeError(f"hit MAX_PAGES={MAX_PAGES}; {len(rows)} of {total} rows so far. Raise MAX_PAGES and rerun.")
        time.sleep(PAUSE)
        want = f"{BASE}{path}/page-{page}"
        landed = open_page(want)
        if landed.rstrip("/") != want:
            print(f"page-{page} redirected to {landed}; treating it as the end of the list")
            break
    for pid, h in emb.items():            # embedded homes no card showed are still part of the result
        rows.setdefault(pid, from_embedded(h))

rows = list(rows.values())
short = total - len(rows)
if short > max(2, total * MAX_SHORT):
    raise RuntimeError(f"collected {len(rows)} of the {total} homes the page header reports ({header!r}), {short} missing. "
                       "Raise MAX_SHORT only if you accept an incomplete result.")

out = os.path.join(tempfile.gettempdir(), "redfin_listings")
with open(out + ".json", "w") as f:
    json.dump(rows, f)
with open(out + ".csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(from_embedded({})))   # same columns even when rows is empty
    w.writeheader()
    w.writerows(rows)
print("saved", len(rows), "rows to", out + ".json", "and .csv;", sum(r["source"] == "card" for r in rows), "from cards only;",
      f"header count {total}, {max(short, 0)} short")
print(json.dumps(rows[:2], indent=1))
```

Observed output (trimmed):

```text
/zipcode/78704: header says '323 homes + 9 early access' -> 332; embedded map data has 332 homes
saved 332 rows to /tmp/.../redfin_listings.json and .csv; 0 from cards only; header count 332, 0 short
[
 {"property_id": 31703545, "listing_id": 224677425, "mls_id": "3820245",
  "address": "503 S Park Dr", "city": "Austin", "state": "TX", "zip": "78704",
  "price": 1120000, "beds": 3, "baths": 2.5, "sqft": 1640, "lot_sqft": 11704, "year_built": 2023,
  "price_per_sqft": 683, "hoa_month": null, "days_on_market": 1, "status": "Active",
  "neighborhood": "SOUTH PARK SEC 2", "lat": 30.232246, "lon": -97.7638868,
  "url": "https://www.redfin.com/TX/Austin/503-S-Park-Dr-78704/home/31703545", "source": "embedded"},
 {"property_id": 31205095, "address": "1818 Margaret St", "price": 2995000, "beds": 3, "baths": 4.0,
  "status": "Coming Soon", "days_on_market": null, ...}
]
```

That ZIP run took one page load. Null counts across the 332 rows: address 1, price 1, baths 7, sqft 10, lot_sqft 19, year_built 10, price_per_sqft 11, hoa_month 173, days_on_market 9, neighborhood 1. Status values: Active 322, Coming Soon 9, New 1.

Results over 350 homes page through the list. `SEARCH = "78745"` (header `357 homes + 8 early access`) took 10 page loads in 54 s and saved 369 rows, 19 of them from cards only. `SEARCH = "/city/30818/TX/Austin"`, run with `MAX_SHORT = 0.02` as the only other change, printed:

```text
/city/30818/TX/Austin: header says '5,788 homes + 120 early access' -> 5908; embedded map data has 350 homes
page 1: 41 cards, 41 new, 41 unique so far
...
page 9: 22 cards, 22 new, 350 unique so far
page 10: 41 cards, 41 new, 391 unique so far
...
page 144: 22 cards, 22 new, 5597 unique so far
page 145: 41 cards, 40 new, 5637 unique so far
...
page 149: 36 cards, 36 new, 5796 unique so far
page 150: 41 cards, 0 new, 5796 unique so far
saved 5796 rows to /tmp/.../redfin_listings.json and .csv; 5446 from cards only
```

That crawl took 14 min 39 s and ran an earlier version of block 1, whose save line did not yet print the header count and shortfall. The 78745 paging run was repeated with the current block: same 10 pages and 369 rows, ending `header count 365, 0 short`. The 112 missing homes are close to the 120 early-access homes in the header count, so the paged list may leave most early-access homes out past the first 350; that was not checked home by home. With the default `MAX_SHORT = 0.01` the same numbers raise instead of saving (112 > 59), and an earlier full Austin crawl the same afternoon (5,795 of 5,903) did raise. The paged list is the whole crawl this skill makes, so a big city's result can stay short of the header count; block 1 raises rather than report it as complete. Across the 5,446 Austin card rows: price null 14, beds 431, baths 402, sqft 412; 390 were land cards whose lot size went to `lot_sqft`.

### 2. Key facts from a listing detail page (browser)

Reads the first URL saved by block 1; pass any `https://www.redfin.com/.../home/<id>` URL to `listing_details()` instead. Everything comes from the one listing page: its JSON-LD plus the detail data embedded in its HTML.

```python
import json, os, re, time, tempfile

# Take a listing URL from the search output (block above); any redfin.com/.../home/<id> URL works.
saved = os.path.join(tempfile.gettempdir(), "redfin_listings.json")
listings = json.load(open(saved)) if os.path.exists(saved) else []
URL = listings[0]["url"] if listings else None
if not URL:
    raise SystemExit("Run the search block first, or set URL to a redfin.com listing URL")

BLOCKED = re.compile(r"request could not be satisfied|ratelimited|access denied|are you a human|captcha", re.I)
READY_JS = ("[...document.querySelectorAll('script[type=\"application/ld+json\"]')].some(s => s.textContent.includes('RealEstateListing'))"
            " && [...document.scripts].some(s => !s.src && s.textContent.includes('__reactServerState.InitialContext = '))")

def open_listing(url, budget=120, per_try=30):
    """Load a listing page and wait for the new document. Returns the URL it landed on: url itself once its JSON-LD
    and embedded data are there, or the redirect target (a gone listing redirects away). A block or challenge page
    raises at once (stop and back off). A page that never finishes is retried after 10 s, then 20 s, all inside
    one budget-second deadline; then it raises."""
    end, pause, attempt = time.time() + budget, 10, 0
    while True:
        attempt += 1
        before = js("window.__bhOld = 1, location.href")   # tag the old document; the new one will not carry the tag
        try:
            goto_url(url)
        except Exception as e:       # Page.navigate often outlives the 5 s daemon wait on these heavy pages
            print("navigate still running:", str(e)[:80])
        stop, last = min(end, time.time() + per_try), None
        while time.time() + 1 < stop:   # the last poll starts before the deadline
            time.sleep(1)
            try:
                st = last = json.loads(js("JSON.stringify({old: !!window.__bhOld, u: location.href, t: document.title, "
                                          "r: document.readyState, ok: %s})" % READY_JS))
            except Exception:
                continue                 # page still busy; poll again
            if st["old"]:
                continue                 # still the document from before the navigation
            if BLOCKED.search(st["t"]) or "ratelimited" in st["u"]:
                raise RuntimeError(f"Redfin served a block/challenge page ({st['t']!r} at {st['u']}). Stop and back off.")
            if st["r"] == "complete" and (st["ok"] or st["u"].rstrip("/") != url.rstrip("/")):
                return st["u"]           # ready, or a new document at another URL (redirected)
        print(f"try {attempt}: {url} not ready (navigated from {before}; last state {last})")
        if time.time() + pause + 15 > end:
            break                        # no time left for a backoff and another try; no sleep after the last one
        time.sleep(pause)
        pause *= 2
    raise RuntimeError(f"{url} did not finish loading within the {budget} s budget ({attempt} tries)")

# The listing page HTML embeds the server-rendered detail data in __reactServerState.
STATE_JS = r"""(() => {
  const s = [...document.scripts].find(s => !s.src && s.textContent.includes('__reactServerState.InitialContext = '));
  const p = 'root.__reactServerState.InitialContext = ';
  const line = s.textContent.split('\n').find(l => l.startsWith(p));
  const dc = JSON.parse(line.slice(p.length, -1))['ReactServerAgent.cache'].dataCache;
  const pick = part => { const k = Object.keys(dc).find(k => k.split('?')[0].endsWith(part)); return k ? dc[k].res.text : null; };
  return JSON.stringify({info: pick('/home/details/initialInfo'), atf: pick('/home/details/aboveTheFold'),
                         btf: pick('/home/details/belowTheFold')});
})()"""

def payload(text, name):
    if not text or not text.startswith("{}&&"):
        raise RuntimeError(f"{name} is missing from the page's embedded data: {str(text)[:120]}")
    d = json.loads(text[4:])             # strip the "{}&&" prefix
    if d.get("resultCode") != 0 or not isinstance(d.get("payload"), dict):
        raise RuntimeError(f"unexpected embedded {name}: {text[:160]}")
    return d["payload"]

def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()

def listing_details(url):
    landed = open_listing(url)
    if landed.rstrip("/") != url.rstrip("/"):
        print(f"{url} redirected to {landed}")
        return None                      # listing gone or moved: never read another page's facts
    # 1) JSON-LD block typed ["Product", "RealEstateListing"]
    ld = None
    for t in js("[...document.querySelectorAll('script[type=\"application/ld+json\"]')].map(s => s.textContent)") or []:
        try:
            d = json.loads(t)
        except ValueError:
            continue
        if isinstance(d, dict) and "RealEstateListing" in (d.get("@type") or []):
            ld = d
    if not ld:
        raise RuntimeError("no RealEstateListing JSON-LD on " + landed)
    me, offer = ld.get("mainEntity", {}), ld.get("offers", {})
    facts = {
        "url": url,
        "address": me.get("address", {}),
        "price": offer.get("price"),
        "availability": (offer.get("availability") or "").rsplit("/", 1)[-1],
        "date_posted": ld.get("datePosted"),
        "home_type": me.get("accommodationCategory"),
        "beds": me.get("numberOfBedrooms"),
        "baths": me.get("numberOfBathroomsTotal"),
        "sqft": (me.get("floorSize") or {}).get("value"),
        "year_built": me.get("yearBuilt"),
        "lat": (me.get("geo") or {}).get("latitude"),
        "lon": (me.get("geo") or {}).get("longitude"),
        "amenities": [a.get("name") for a in me.get("amenityFeature", [])],
        "photos": [i.get("url") for i in me.get("image", [])],
        "description": (ld.get("description") or "").strip(),
    }
    # 2) the same page's embedded detail data (no extra requests)
    st = json.loads(js(STATE_JS))
    p = payload(st["info"], "initialInfo")
    atf = payload(st["atf"], "aboveTheFold").get("addressSectionInfo")
    if not isinstance(atf, dict):
        raise RuntimeError("aboveTheFold has no addressSectionInfo on " + landed)
    btf = payload(st["btf"], "belowTheFold")
    facts.update({
        "property_id": p.get("propertyId"), "listing_id": p.get("listingId"), "mls_id": p.get("mlsId"),
        "status": (atf.get("status") or {}).get("displayValue"),
        "lot_sqft": atf.get("lotSize"),
        "price_per_sqft": atf.get("pricePerSqFt"),
        "full_baths": atf.get("numFullBaths"), "half_baths": atf.get("numPartialBaths"),
    })
    groups = {}
    for sg in (btf.get("amenitiesInfo") or {}).get("superGroups", []):
        for g in sg.get("amenityGroups", []):
            for e in g.get("amenityEntries", []):
                vals = ", ".join(strip_tags(x) for x in e.get("amenityValues", []))
                groups.setdefault(g.get("groupTitle") or "untitled", []).append(f'{e.get("amenityName") or e.get("referenceName")}: {vals}')
    facts["mls_details"] = groups
    return facts

d = listing_details(URL)
if d is None:
    print("listing page not available:", URL)
else:
    out = dict(d, description=d["description"][:120] + "...", photos=f'{len(d["photos"])} urls, first: {d["photos"][0] if d["photos"] else None}',
               mls_details={k: v[:3] for k, v in list(d["mls_details"].items())[:6]} if d.get("mls_details") else None)
    print(json.dumps(out, indent=1))
```

Observed output (trimmed):

```text
{
 "url": "https://www.redfin.com/TX/Austin/503-S-Park-Dr-78704/home/31703545",
 "address": {"@type": "PostalAddress", "streetAddress": "503 S Park Dr", "addressLocality": "Austin",
             "addressRegion": "TX", "postalCode": "78704", "addressCountry": "US"},
 "price": 1120000, "availability": "InStock", "date_posted": "2026-10-23T18:45:28.294Z",
 "home_type": "Single Family Residential", "beds": 3, "baths": 2.5, "sqft": 1640, "year_built": 2023,
 "lat": 30.232246, "lon": -97.7638868,
 "amenities": ["Heating & cooling: Has A/C"],
 "photos": "22 urls, first: https://ssl.cdn-redfin.com/photo/92/bigphoto/245/3820245_0.jpg",
 "property_id": 31703545, "listing_id": 224677425, "mls_id": "3820245",
 "status": "Active", "lot_sqft": 11704, "price_per_sqft": 683, "full_baths": 2, "half_baths": 1,
 "mls_details": {
  "Bedroom Information": ["# of Main Level Bedrooms: 3"],
  "Bathroom Information": ["# of Full Bathrooms: 2", "# of Half Bathrooms: 1"],
  "Room 1 Information": ["Level: First"],
  "Laundry Information": ["Features: Inside"],
  ...
 }
}
```

A second listing (ZIP 78745, 4 bed / 2.5 bath) gave 40 photo URLs and MLS groups Parking, Virtual Tour, Bedroom Information, Bathroom Information, Laundry Information and Equipment.

## Fields

Search rows. `source` says where the row came from: `embedded` (the search page's embedded map data, every field below) or `card` (a list card for a home outside the embedded 350; the fields marked "embedded only" are `null`). In the embedded data many numeric fields are wrapped as `{"value": X, "level": 1}`; a wrapper with no `value` means hidden.

| Output field | Embedded map data (`payload.homes[]`) | Card | Example |
|---|---|---|---|
| property_id | `propertyId` | `/home/<id>` in the card link | `31703545` |
| listing_id, mls_id | `listingId`, `mlsId.value` | embedded only | `224677425`, `"3820245"` |
| address | `streetLine.value` (includes unit, e.g. `#1303`) | JSON-LD `address.streetAddress` | `"503 S Park Dr"` |
| city / state / zip | `city`, `state`, `zip` | JSON-LD `address` | `"Austin"`, `"TX"`, `"78704"` |
| price | `price.value` (USD int) | JSON-LD `offers.price`, else the card price text | `1120000` |
| beds / baths | `beds`, `baths` | card text `"3 beds"`, `"2.5 baths"` (floats; `null` on land cards, which say `"Land"`) | `3`, `2.5` |
| sqft | `sqFt.value` | card text `"1,640 sq ft"` (float; `null` on land cards) | `1640` |
| lot_sqft | `lotSize.value` | land cards only: `"0.38 acre (lot)"` (x 43,560) or `"9,557 sq ft (lot)"` | `11704` |
| year_built, price_per_sqft | `yearBuilt.value`, `pricePerSqFt.value` | embedded only | `2023`, `683` |
| hoa_month, days_on_market | `hoa.value`, `dom.value` | embedded only | `null`, `1` |
| status | `mlsStatus` | embedded only | `"Active"`, `"Coming Soon"`, `"New"` |
| neighborhood | `location.value` | embedded only | `"SOUTH PARK SEC 2"` |
| lat / lon | `latLong.value.latitude/longitude` | JSON-LD `geo` | `30.232246`, `-97.7638868` |
| url | `"https://www.redfin.com" + url` | card link | `.../home/31703545` |
| source | `"embedded"` | `"card"` | |
| (not flattened) | `listingRemarks`, `keyFacts`, `listingTags`, `sashes`, `numPictures`, `stories`, `isNewConstruction`, `uiPropertyType`, `timeZone` | | |

Detail page:

| Field | Source | Example |
|---|---|---|
| price, availability | JSON-LD `offers.price`, `offers.availability` | `1120000`, `InStock` |
| address, geo | JSON-LD `mainEntity.address`, `mainEntity.geo` | PostalAddress dict |
| home_type | JSON-LD `mainEntity.accommodationCategory` | `"Single Family Residential"` |
| beds, baths, sqft, year_built | JSON-LD `numberOfBedrooms`, `numberOfBathroomsTotal`, `floorSize.value`, `yearBuilt` | `3`, `2.5`, `1640`, `2023` |
| amenities | JSON-LD `mainEntity.amenityFeature[].name` | `["Heating & cooling: Has A/C"]` |
| photos | JSON-LD `mainEntity.image[].url` | 22 URLs |
| description, date_posted | JSON-LD `description`, `datePosted` | full remarks text |
| property_id, listing_id, mls_id | embedded initialInfo `propertyId`, `listingId`, `mlsId` | `31703545`, `224677425`, `"3820245"` |
| status | embedded aboveTheFold `addressSectionInfo.status.displayValue` | `"Active"` |
| lot_sqft, price_per_sqft, full/half baths | embedded aboveTheFold `lotSize`, `pricePerSqFt`, `numFullBaths`, `numPartialBaths` | `11704`, `683`, `2`, `1` |
| mls_details | embedded belowTheFold `amenitiesInfo.superGroups[].amenityGroups[].amenityEntries[]` | `{"Laundry Information": ["Features: Inside"]}` |

## Gotchas

- The embedded data sits in an inline script as one line, `root.__reactServerState.InitialContext = {...};`, under `ReactServerAgent.cache.dataCache`. Each entry is keyed by the internal URL the server used to render the page and holds the response text with a `{}&&` prefix; strip 4 characters before `json.loads`. The skill only reads this from the page HTML it already loaded.
- The embedded map data is capped at 350 homes and is the same on every `/page-<n>` (Austin page 1 and page 2 embedded the identical first 350). Only the list cards change from page to page.
- The list comes in chunks of 350: every 9th page rendered only 22 cards (8 x 41 + 22 = 350). Austin had 16 such pages (9, 18, ..., 144) and ZIP 78745 had page 9; the next page carries on with the next chunk. In ZIP 78745, 5 of page 10's 24 cards repeated earlier ones, so keep the `property_id` dedupe.
- The end of the list is not one fixed signal. In one probe Austin page-144 and page-146 redirected to `/city/30818/TX/Austin`; in the full crawls the list ran to page 149 and page 150 showed 41 cards that were all repeats. Block 1 stops on a redirect, on a page with no new homes, or once it has the header's count.
- The site counts nearby homes: ZIP 78704's embedded data held 3 homes with ZIP 78745, and the header total (323 + 9 = 332) included them. ZIP 78745 gave 369 unique rows against a header of 365. City results follow Redfin's boundary, not the mailing city (Austin's first 350 included Pflugerville, Manchaca, Del Valle, Manor and Cedar Park addresses).
- The header count moves while you crawl (Austin's header read 5,789 on one load and 5,786 on a later one the same afternoon), so block 1 allows a shortfall of `MAX_SHORT` (1%) and raises beyond that.
- `goto_url()` on these pages often raised `Page.navigate timed out after 5s waiting for the daemon` while the page went on loading. The open helpers swallow that and poll the page instead, so a slow load is not mistaken for a failure. If the navigation never starts, the old page stays up and looks ready (tested by replacing `goto_url` with a call that only raises: `open_page` read nothing and raised after 120 s), so each helper first tags the current document (`window.__bhOld`) and records its URL, then reads nothing until a new document without the tag is there, and compares its `location.href` with the requested URL: a different URL is returned as a redirect, never read as the requested page. Both checks matter here: a listing page matches the card selector too (31 cards on one), and `/TX/Austin/503-S-Park-Dr-78704/home/1` redirected to a different listing in Seattle, for which block 2 returns `None`. Retries share one 120 s deadline (two backoffs, 10 s and 20 s, and no sleep after the last try).
- A ZIP with no homes for sale has no header count. ZIP 20500 showed "We didn't find any exact matches" (`.ZeroResultsText`, 0 cards, empty embedded `homes`); ZIP 10020 showed 20 nearby homes under "Homes within 1 mile of 10020, NY" (`.nearbyHomesTitle`) and no `homes` key in the embedded data. Block 1 treats both as 0 homes and saves an empty JSON list and a header-only CSV.
- There is no ZIP or city id lookup in this skill. ZIPs need no id (`/zipcode/78704`). City ids come from the address bar after searching on redfin.com by hand, or from the "Popular Cities" links on `/state/<State>` (16 cities on `/state/Texas`, including `/city/30818/TX/Austin`).
- A card's JSON-LD is usually a list (`SingleFamilyResidence` or `Accommodation`, plus a `Product` with `offers.price`), but 3 of the 41 cards on Austin page 35 carried a single object with no `Product`. Block 1 accepts both and then takes the price from the card text.
- Land cards put `Land` where beds go and the lot size where sqft goes (`0.38 acre (lot)`, `9,557 sq ft (lot)`); 7 of the 22 cards on Austin page 18 were land. Block 1 moves that number to `lot_sqft`.
- Selectors: block 1 reads cards by `data-rf-test-name="basicNode-homeCard"` and the `bp-Homecard__*` class names (price, stats, address link). If cards stop being found, the block raises after its retries; check those names first.
- The JSON-LD `datePosted` of the same listing changed in its milliseconds from load to load (`.271Z`, `.291Z`, `.294Z`), so do not use it as a change detector.
- The page loads a OneTrust (cookielaw) consent script. Nothing in this skill required dismissing it.
- Pacing used here: 3 s between search pages, one listing page at a time. No 429 or challenge page appeared in three back-to-back 150-page Austin crawls (about 15 minutes each), a partial one, and several dozen other page loads the same afternoon.

## What does not work

- Plain HTTP is blocked: `curl https://www.redfin.com/robots.txt` was redirected to `ratelimited.redfin.com` with status 429, so even robots.txt was read in the browser.
- `/stingray/` (the JSON API behind the site's map, autocomplete and detail panels) is disallowed for `User-agent: *`. This skill does not call it; the pages' own scripts still use it while they render.
- Typing into the home page search box from the cloud browser did nothing: the box sat in a container marked `disabled` and the typed text never landed, so the skill takes a ZIP or a search page path instead.
- `/sitemap_com_city.xml` (listed in robots.txt) returned a CloudFront 403 "Request blocked" page in the browser, so it is not a way to look up city ids.
- Fields only the embedded data has (status, year built, HOA, days on market, MLS id, and lot size except on land cards) are `null` on card rows; open those listings with block 2 if you need them.
