# BBB — Business Search by Category + Location, Ratings, Accreditation and Complaint Counts

Field-tested against www.bbb.org on 2026-10-24 using a Browser Use cloud browser (plus plain HTTP for robots.txt and sitemaps).

robots.txt (fetched 2026-10-24) for `User-agent: *` disallows every URL with a query string (`Disallow: /*?`) except profile pages, so `/search?find_text=...` and `?page=2` pagination are off limits; everything below requests only query-free category pages, profile pages and the published sitemaps.

## Quick summary

- Category + location pages (`/us/<state>/<city>/category/<category>`) are server-rendered and carry the result list in a `window.__PRELOADED_STATE__ = {...};` script tag: name, BBB rating, accreditation flag, street, city, state, postal code, phone, categories, profile URL. 15 rows per page plus `totalResults`.
- Plain HTTP (`curl`/`urllib`) to category and profile pages gets HTTP 403 with a Cloudflare "Just a moment..." page. A real browser loads them with no challenge. Sitemaps (`/sitemap-*.xml`) return 200 over plain HTTP.
- Only page 1 (15 rows) of each listing is robots-allowed. Treat that as a hard cap: the helpers mark every listing with `truncated: true` when `totalResults` is larger, and nothing here tries to reach rows 16+ another way. A different city or category is a different search, run only because the user asked for it.
- Business profile pages carry complaint counts (last 3 years, last 12 months), review count, average stars, BBB rating, accreditation and website in the same preloaded state, plus a schema.org `LocalBusiness` JSON-LD block as a cross-check.
- No name search: BBB's own search is under `/search?...`, which robots.txt disallows.

## What works

### 1. Search a category in the cities the user named (browser)

Self-contained. Opens one tab, reads page 1 of each city's listing, dedupes, saves JSON with an explicit partial status. About 3 s between page loads. Raises on a Cloudflare challenge, an unexpected landing URL, missing page state or a short page; returns `None` only for BBB's 404 page or an unknown city slug.

```python
import json, os, re, tempfile, time

def bbb_state():
    # The page deletes window.__PRELOADED_STATE__ after hydrating, so parse the script text instead.
    t = js("(() => { const s = [...document.scripts].find(s => /__PRELOADED_STATE__\\s*=/.test(s.textContent)); return s ? s.textContent : null })()")
    if not t:
        return None
    # Seen both as `__PRELOADED_STATE__ = {...};` and minified `__PRELOADED_STATE__={...}`.
    return json.loads(t.split("=", 1)[1].strip().rstrip(";"))

def bbb_open(url, settle=2.0):
    """Open url. None for BBB's 404 page; raises on a challenge or if the tab is not on url."""
    goto_url(url)
    wait_for_load()
    time.sleep(settle)
    href, title = js("location.href"), js("document.title") or ""
    challenge = js("!!document.querySelector('#challenge-form, iframe[src*=\"challenges.cloudflare.com\"]')")
    if "Just a moment" in title or challenge:
        raise RuntimeError(f"Cloudflare challenge on {url}: stop and tell the user; do not retry around it")
    if "Page not found" in title:
        return None
    if href.rstrip("/") != url.rstrip("/"):
        raise RuntimeError(f"asked for {url} but the tab is on {href}; not reading it")
    return href

SLUG = re.compile(r"^[a-z0-9-]+$")
PAGE_SIZE = 15

def bbb_category(country, state, city, category, accredited=False):
    """Page 1 of a query-free listing. country 'us' or 'ca'; city=None for the state-level page.
    Returns None for unknown slugs."""
    parts = [country, state] + ([city] if city else []) + ["category", category]
    if not all(SLUG.match(p) for p in parts):
        raise ValueError("slugs must be lowercase-hyphenated, e.g. 'san-francisco', 'plumber'")
    url = "https://www.bbb.org/" + "/".join(parts) + ("/accredited" if accredited else "")
    if not bbb_open(url):
        return None
    sr = (bbb_state() or {}).get("searchResult")
    if not isinstance(sr, dict):
        raise RuntimeError(f"{url}: no searchResult in the page state; refusing to call it an empty listing")
    loc = (sr.get("location") or {}).get("displayText")
    if city and not loc:
        return None  # unknown city slug: BBB silently serves the state-level list instead
    results, total = sr.get("results"), sr.get("totalResults")
    if not isinstance(results, list) or not isinstance(total, int) or len(results) != min(total, PAGE_SIZE):
        got = len(results) if isinstance(results, list) else repr(results)
        raise RuntimeError(f"{url}: {got} rows for totalResults={total!r}, expected min(total, {PAGE_SIZE})")
    rows = []
    for r in results:
        if not (r.get("id") and r.get("reportUrl") and (r.get("businessName") or "").strip()):
            raise RuntimeError(f"{url}: a listing row lacks id, reportUrl or businessName")
        rows.append({
            "id": r["id"],
            "name": r["businessName"].strip(),
            "rating": r.get("rating"),
            "accredited_flag": r.get("bbbMember"),
            "street": r.get("address") or None,
            "city": (r.get("city") or "").strip(),
            "state": r.get("state"),
            "postal_code": r.get("postalcode"),
            "phone": (r.get("phone") or [None])[0],
            "primary_category": r.get("tobText"),
            "categories": [c["name"] for c in r.get("categories") or []],
            "profile_url": "https://www.bbb.org" + r["reportUrl"],
        })
    return {
        "url": url,
        "location": loc,
        "total_results": total,
        "truncated": total > len(rows),  # rows 16+ are on ?page=2+, which robots.txt disallows
        "related_categories": [c["url"].rsplit("/", 1)[1] for c in sr.get("relatedCategories") or []],
        "rows": rows,
    }

new_tab("about:blank")
cities = ["san-francisco", "oakland", "san-jose", "berkeley", "daly-city", "not-a-real-city"]
found, listings, last = {}, [], None
for city in cities:
    p = bbb_category("us", "ca", city, "plumber")
    time.sleep(3)
    if p is None:
        print(f"{city:15} -> no listing")
        continue
    last = p
    listings.append({k: p[k] for k in ("url", "total_results", "truncated")} | {"rows_read": len(p["rows"])})
    for row in p["rows"]:
        found.setdefault(row["profile_url"], row)  # one profile can appear twice in a listing
    print(f'{city:15} total={p["total_results"]:<5} rows={len(p["rows"])} truncated={p["truncated"]} unique_so_far={len(found)}')
partial = any(l["truncated"] for l in listings)
print(len(listings), "listings ->", len(found), "unique businesses;",
      "PARTIAL: page 1 only of each listing (robots.txt disallows ?page=2+)" if partial else "complete")
print(json.dumps(next(iter(found.values()), None), indent=1))
print("related:", last["related_categories"] if last else None)
out = os.path.join(tempfile.gettempdir(), "bbb_plumbers.json")
with open(out, "w") as f:
    json.dump({"complete": not partial, "listings": listings, "rows": list(found.values())}, f, indent=1)
print("saved", out)
```

Output from the test run (trimmed):

```
san-francisco   total=4426  rows=15 truncated=True unique_so_far=15
oakland         total=4588  rows=15 truncated=True unique_so_far=27
san-jose        total=4713  rows=15 truncated=True unique_so_far=42
berkeley        total=4574  rows=15 truncated=True unique_so_far=47
daly-city       total=4388  rows=15 truncated=True unique_so_far=61
not-a-real-city -> no listing
5 listings -> 61 unique businesses; PARTIAL: page 1 only of each listing (robots.txt disallows ?page=2+)
{
 "id": "1116_116593_30865",
 "name": "Atlas Plumbing & Rooter",
 "rating": "A+",
 "accredited_flag": true,
 "street": "3311 Mission St Ste 165",
 "city": "San Francisco",
 "state": "CA",
 "postal_code": "94110-5008",
 "phone": "(415) 845-9199",
 "primary_category": "Plumber",
 "categories": [
  "Plumber",
  "Sewer Cleaning",
  "Water Heater Repair",
  "Tankless Water Heaters"
 ],
 "profile_url": "https://www.bbb.org/us/ca/san-francisco/profile/plumber/atlas-plumbing-rooter-1116-116593"
}
related: ['sewer-cleaning', 'plumbing-renovation', 'commercial-plumber', 'water-heater-repair', 'water-heater-installation', 'tankless-water-heaters', 'general-contractor', 'drain-cleaning', 'heating-and-air-conditioning']
saved /var/folders/.../T/bbb_plumbers.json
```

Neighboring cities overlap (Oakland/Berkeley share rows), so the unique count grows slower than 15 per city. `related_categories` lists other category slugs BBB links from the page; each is its own search, not a way to get past the 15-row cap.

### 2. Profiles: complaint counts, rating, accreditation, website (browser)

Self-contained. Reads the JSON written by block 1 if present and enriches the first `LIMIT` rows, then shows a profile with many complaints and a stale profile URL that BBB redirects. About 3 s between profiles. Raises on a challenge, a landing URL that is neither the requested one nor the same profile id, missing `businessProfile` state or missing name, rating or complaint counts; returns `None` only for BBB's 404 page.

```python
import json, os, re, tempfile, time

def bbb_state():
    t = js("(() => { const s = [...document.scripts].find(s => /__PRELOADED_STATE__\\s*=/.test(s.textContent)); return s ? s.textContent : null })()")
    if not t:
        return None
    # Seen both as `__PRELOADED_STATE__ = {...};` and minified `__PRELOADED_STATE__={...}`.
    return json.loads(t.split("=", 1)[1].strip().rstrip(";"))

def bbb_open(url, settle=2.0, same=None):
    """Open url. None for BBB's 404 page; raises on a challenge or if the tab is not on url
    (a different landing URL is read only when same(href) says it is the same page)."""
    goto_url(url)
    wait_for_load()
    time.sleep(settle)
    href, title = js("location.href"), js("document.title") or ""
    challenge = js("!!document.querySelector('#challenge-form, iframe[src*=\"challenges.cloudflare.com\"]')")
    if "Just a moment" in title or challenge:
        raise RuntimeError(f"Cloudflare challenge on {url}: stop and tell the user; do not retry around it")
    if "Page not found" in title:
        return None
    if href.rstrip("/") != url.rstrip("/") and not (same and same(href)):
        raise RuntimeError(f"asked for {url} but the tab is on {href}; not reading it")
    return href

# Profile URLs end in <bbbId>-<businessId>; BBB redirects stale name/city/category slugs to the canonical URL.
PROFILE = re.compile(r"^https://www\.bbb\.org/(?:us|ca)/[a-z]{2}/[a-z0-9-]+/profile/[a-z0-9-]+/[a-z0-9-]*-(\d{4}-\d+)/?$")

def profile_id(url):
    m = PROFILE.match(url or "")
    return m.group(1) if m else None

def bbb_profile(profile_url):
    pid = profile_id(profile_url)
    if not pid:
        raise ValueError(f"not a BBB profile URL: {profile_url}")
    href = bbb_open(profile_url, same=lambda h: profile_id(h) == pid)  # query-free, same id, or raise
    if not href:
        return None
    bp = (bbb_state() or {}).get("businessProfile")
    if not isinstance(bp, dict):
        raise RuntimeError(f"{profile_url}: no businessProfile in the page state; refusing to call it a missing profile")
    s = bp.get("reviewsComplaintsSummary")
    name = (bp.get("names") or {}).get("primary")
    rating = (bp.get("rating") or {}).get("bbbRating")
    if not (name and rating and isinstance(s, dict) and isinstance(s.get("totalClosedComplaintsPastThreeYears"), int)
            and isinstance(s.get("totalClosedComplaintsPastTwelveMonths"), int)):
        raise RuntimeError(f"{profile_url}: profile state lacks name, rating or complaint counts")
    loc = bp.get("location") or {}
    ld = {}
    for raw in js("[...document.querySelectorAll('script[type=\"application/ld+json\"]')].map(s => s.textContent)") or []:
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        for x in data if isinstance(data, list) else [data]:
            if x.get("@type") == "LocalBusiness":
                ld = {p["name"]: p["value"] for p in x.get("additionalProperty") or []}
    return {
        "requested_url": profile_url,
        "profile_url": href,
        "name": name,
        "rating": rating,
        "accredited": (bp.get("accreditationInformation") or {}).get("isAccredited"),
        "complaints_3y": s["totalClosedComplaintsPastThreeYears"],
        "complaints_12m": s["totalClosedComplaintsPastTwelveMonths"],
        "reviews": s.get("reviewsTotal"),
        "avg_stars": s.get("averageOfReviewStarRatings"),
        "website": (bp.get("urls") or {}).get("primary"),
        "phone": (bp.get("contactInformation") or {}).get("phoneNumber"),
        "address": (loc.get("formattedAddress") or "").lstrip(", "),
        "jsonld_complaints_3y": ld.get("BBB Complaints Filed in Last 3 Years"),
        "jsonld_accreditation": ld.get("BBB Accreditation"),
    }

LIMIT = 5
src = os.path.join(tempfile.gettempdir(), "bbb_plumbers.json")
rows = json.load(open(src))["rows"] if os.path.exists(src) else []
for row in rows[:LIMIT]:
    prof = bbb_profile(row["profile_url"])
    time.sleep(3)
    if prof is None:
        print("no profile (404):", row["profile_url"])
        continue
    print(f'{row["name"][:34]:34} {prof["rating"]:3} acc={prof["accredited"]!s:5} '
          f'complaints_3y={prof["complaints_3y"]} 12m={prof["complaints_12m"]} reviews={prof["reviews"]} site={prof["website"]}')
    if prof["profile_url"].rstrip("/") != row["profile_url"].rstrip("/"):
        print("  redirected to", prof["profile_url"])
if len(rows) > LIMIT:
    print(f"PARTIAL: enriched {LIMIT} of {len(rows)} rows (LIMIT={LIMIT})")

print(json.dumps(bbb_profile("https://www.bbb.org/us/ny/new-york/profile/telephones/verizon-communications-0011-1568"), indent=1))
time.sleep(3)
moved = bbb_profile("https://www.bbb.org/us/ca/oakland/profile/plumber/atlas-plumbing-rooter-1116-116593")
print("redirected:", moved["requested_url"], "->", moved["profile_url"])
```

Output from the test run (trimmed):

```
Atlas Plumbing & Rooter            A+  acc=True  complaints_3y=1 12m=0 reviews=1 site=https://www.atlasplumbingandrooter.com
A G Quality Plumbing               A+  acc=True  complaints_3y=0 12m=0 reviews=1 site=https://www.agqualityplumbing.com/
Jimenez Construction               A+  acc=True  complaints_3y=0 12m=0 reviews=1 site=https://jimenezconstructionsf.com/
J. E. Brown Mechanical Co., Inc.   A+  acc=True  complaints_3y=0 12m=0 reviews=0 site=None
Mr. Rooter Plumbing of San Francis A+  acc=True  complaints_3y=0 12m=0 reviews=0 site=https://www.mrrooter.com/san-francisco/
PARTIAL: enriched 5 of 61 rows (LIMIT=5)
{
 "requested_url": "https://www.bbb.org/us/ny/new-york/profile/telephones/verizon-communications-0011-1568",
 "profile_url": "https://www.bbb.org/us/ny/new-york/profile/telephones/verizon-communications-0011-1568",
 "name": "Verizon Communications",
 "rating": "A+",
 "accredited": false,
 "complaints_3y": 3730,
 "complaints_12m": 871,
 "reviews": 718,
 "avg_stars": 1.1,
 "website": "https://www.verizon.com/",
 "phone": "(800) 779-4116",
 "address": "140 West St, New York, NY 10007-2141",
 "jsonld_complaints_3y": "3730",
 "jsonld_accreditation": "Not BBB Accredited"
}
redirected: https://www.bbb.org/us/ca/oakland/profile/plumber/atlas-plumbing-rooter-1116-116593 -> https://www.bbb.org/us/ca/san-francisco/profile/plumber/atlas-plumbing-rooter-1116-116593
```

### 3. Discover valid category slugs for a state from the sitemap (plain Python, no browser)

Category slugs are not guessable (`telephone-companies` is a 404, `telephones` works). The state-category sitemaps list them, sorted by state. `fetch` retries only network errors and 5xx, raises at once on any other HTTP status (403/429 reported as blocked) or an undecodable body, and every attempt, backoff and read shares one deadline (no new wait starts after 110 s and each socket wait is capped at 10 s, so a call ends within 120 s).

```python
import http.client, re, time, urllib.error, urllib.request

UA = "bbb-sitemap-reader/1.0 (python-urllib)"
BUDGET_S, WAIT_S = 110, 10

def fetch(url, tries=3):
    deadline = time.monotonic() + BUDGET_S
    delay, err, attempt = 5, None, 0
    while True:
        attempt += 1
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=min(WAIT_S, deadline - time.monotonic())) as r:
                body = bytearray()
                while chunk := r.read1(65536):
                    body += chunk
                    if time.monotonic() > deadline:
                        raise TimeoutError("deadline hit mid-download")
                return body.decode("utf-8-sig")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                raise RuntimeError(f"{url}: HTTP {e.code}, blocked or rate limited; stopping, not retrying") from e
            if e.code < 500:
                raise RuntimeError(f"{url}: HTTP {e.code}; not retrying") from e
            err = e  # 5xx: retry
        except (OSError, http.client.HTTPException) as e:
            err = e  # network error or timeout: retry; decode and other errors propagate at once
        if attempt >= tries or deadline - time.monotonic() <= delay:
            break  # last attempt, or no budget left after a backoff: raise now, no sleep
        time.sleep(delay)  # 5 s, 10 s, ...
        delay *= 2
    raise RuntimeError(f"{url}: failed after {attempt} attempt(s) within the {BUDGET_S} s budget: {err}")

def state_category_slugs(state):
    idx = fetch("https://www.bbb.org/sitemap-us-state-categories-index.xml")
    files = re.findall(r"<loc>([^<]+)</loc>", idx)
    if not files:
        raise RuntimeError("sitemap index has no <loc> entries")
    slugs, seen_state = [], False
    for sm in files:
        locs = re.findall(r"<loc>https://www\.bbb\.org/us/([a-z]{2})/category/([^<]+)</loc>", fetch(sm))
        if not locs:
            raise RuntimeError(f"{sm}: no state category URLs")
        mine = [c for s, c in locs if s == state]
        slugs += mine
        if mine:
            seen_state = True
        elif seen_state:
            break  # files are sorted by state, so we are past it
        time.sleep(1)
    if not slugs:
        raise RuntimeError(f"no category slugs found for state {state!r}")
    return slugs

slugs = state_category_slugs("ca")
print(len(slugs), "category slugs for CA")
print([s for s in slugs if "plumb" in s])
```

Output from the test run:

```
2564 category slugs for CA
['wholesale-plumbing-supplies', 'plumbing-fixtures', 'plumbing-and-heating', 'plumber', 'plumbing-plan', 'propane-gas-plumbing', 'plumbing-renovation', 'commercial-plumber', 'plumbing-supplies']
```

## Fields

| Field | Source | Notes |
|---|---|---|
| `id` | listing `results[].id` | `<bbbId>_<businessId>_<n>`; required |
| `name` | `businessName` | trailing spaces stripped; required |
| `rating` | `rating` | `A+` ... `F`, `NR` (not rated) |
| `accredited_flag` | `bbbMember` | matched profile `accreditationInformation.isAccredited` for every listing row checked (14 profiles) |
| `street` | `address` | `None` when the business hides its street (empty string in the raw data) |
| `city`, `state`, `postal_code` | `city`, `state`, `postalcode` | ZIP+4 in the US |
| `phone` | `phone[0]` | business phone; a list in the raw data |
| `primary_category` | `tobText` | BBB's main "type of business" for the row |
| `categories` | `categories[].name` | BBB "type of business" names |
| `profile_url` | `reportUrl` | relative path, prefix `https://www.bbb.org`; required; dedupe key (the same profile appeared twice in one listing with different `id`s) |
| `total_results` | `searchResult.totalResults` | size of the whole listing; must be an int, and the page must hold `min(total, 15)` rows |
| `truncated` | `total_results > len(rows)` | `True` means rows 16+ exist but are robots-disallowed; the data is partial |
| `related_categories` | `searchResult.relatedCategories[].url` | last path segment = category slug |
| `complaints_3y` / `complaints_12m` | profile `reviewsComplaintsSummary.totalClosedComplaintsPastThreeYears` / `...PastTwelveMonths` | required ints; JSON-LD `additionalProperty` "BBB Complaints Filed in Last 3 Years" matches |
| `reviews`, `avg_stars` | `reviewsTotal`, `averageOfReviewStarRatings` | 0 when no reviews |
| `requested_url`, `profile_url` (profile) | URL asked for, final `location.href` | differ only after a redirect to the same `<bbbId>-<businessId>` profile; report `profile_url` |
| `website` | profile `urls.primary` | not present in listings |
| `rating` (profile) | `rating.bbbRating` | required; `NR` comes with `ratingReasonNotRated` text |
| `jsonld_complaints_3y`, `jsonld_accreditation` | JSON-LD `additionalProperty` | strings, e.g. `"3730"`, `"Not BBB Accredited"` |

## Gotchas

- `window.__PRELOADED_STATE__` is `undefined` by the time you run JS; parse the `<script>` text that assigns it. The same URL was served once as `__PRELOADED_STATE__ = {...};` and later minified as `__PRELOADED_STATE__={...}`, so match with a regex, not a fixed string. The same object holds a `user` section with session cookies and an IP-derived location; read only `searchResult` / `businessProfile`.
- Page 1 is sorted "Best Match". In every listing tried (plumbers, movers, telephones, used car dealers; 6 cities and 1 state page) all 15 page-1 rows had `bbbMember: true` and a rating of B or better. Unaccredited and low-rated businesses sit on pages 2+, which robots.txt disallows. Page 1 is not a representative sample, and the helpers say so with `truncated`.
- `/accredited` pages report a smaller `totalResults` (San Francisco plumbers: 640 vs 4426) but page 1 was the same 15 businesses in the same order as the unfiltered page (rechecked 2026-10-24). Use it only when the user wants accredited businesses, not to extend an unfiltered search.
- Listings mix categories: a "plumber" page included rows whose primary category is building contractors or boiler repair.
- Unknown city slug: the URL keeps the fake city but BBB serves the state-level list (`location.displayText` is `None`, heading location "USA"). The helper returns `None`. Unknown category slug: title "Page not found", no state; the helper returns `None`.
- One company can have several BBB profiles under different local BBBs with different accreditation: the New York "telephones" listing links Verizon Communications at `...-0121-411` (accredited, 3,730 complaints in 3 years), while `...-0011-1568` is "Not BBB Accredited" with the same complaint counts. Report the profile URL with every number.
- A listing's `reportUrl` can point to another state (a San Francisco movers row linked to a Massachusetts headquarters profile). Keep the profile URL, not the listing's city, as the business location.
- Stale profile URLs redirect: a wrong name slug, another city or `plumbers` instead of `plumber` in front of `atlas-plumbing-rooter-1116-116593` all landed on the canonical `/us/ca/san-francisco/profile/plumber/atlas-plumbing-rooter-1116-116593` (2026-10-24). `bbb_profile` reads the page only when the final URL ends in the same `<bbbId>-<businessId>` with no query, and returns both `requested_url` and the final `profile_url`; any other landing raises.
- Cookie banner ("Accept All Cookies") is shown but does not block the embedded data; no click needed.
- Canada uses the same layout under `/ca/<province>/<city>/category/<category>` (Toronto plumbers: 1,259 results, 15 rows).
- Profile JSON-LD and `contactInformation` can include named owners/contacts and an obfuscated email. The helpers do not read them; leave them out unless you have a reason and a lawful basis to store them.
- No challenge or rate limiting was hit in about 85 browser page loads at 2 to 3 s spacing on 2026-10-23, nor in the 16 page loads of the first 2026-10-24 run or the 18 of the second. If a "Just a moment..." title or a Cloudflare challenge frame appears, the helpers raise: stop and tell the user.

## What does not work

- Plain HTTP to category or profile pages: HTTP 403, Cloudflare "Just a moment..." page (curl, 2026-10-23). Use the browser; do not change user agents to get around it.
- Name search (`/search?find_text=...&find_loc=...`) and listing pagination (`?page=2` ... `?page=15`, linked from the page's `pagination` nav): disallowed by robots.txt for `User-agent: *` (`Disallow: /*?`). Not used, and not worked around by splitting a search into smaller ones.
- Individual complaint texts: the `/complaints` page server-renders only the summary ("3,730 complaints in the last 3 years. 871 complaints in the last 12 months." for the Verizon profile); `customerComplaints.items` was empty (`numFound: 0`) and the page said "There are no matching results." Counts work, complaint bodies do not this way.
- Finding a business by name via sitemaps is impractical: `sitemap-business-profiles-index.xml` lists 578 files of 10,000 profile URLs each (about 2.3 MB per file).
