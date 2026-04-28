# Coursera — Course & Catalog Data Extraction

Field-tested against coursera.org and api.coursera.org on 2026-04-18.
No authentication required for the public catalog API.

## TL;DR — Fastest Approach

Use `http_get` against `api.coursera.org`. The public REST API returns clean JSON with no
auth, no bot-detection, and sub-600ms latency. Use `q=search` with a keyword
only when you need full-text search (requires a browser POST workaround — see below).
For bulk enumeration, iterate the catalog list with `start` pagination.

---

## 1. Catalog List (http_get — always works)

The default list query (`q=list` implied) returns ALL courses in Coursera's catalog —
20,659 as of the test date.

```python
from helpers import http_get
import json

resp = http_get(
    "https://api.coursera.org/api/courses.v1"
    "?fields=name,slug,description,primaryLanguages,workload,"
    "partnerIds,courseType,instructorIds,domainTypes,photoUrl,certificates"
    "&limit=100&start=0"
)
data = json.loads(resp)
courses = data["elements"]   # list of dicts
next_start = data["paging"].get("next")   # e.g. "100", None when exhausted
total = data["paging"].get("total")       # 20659
```

### Response structure (confirmed field names)

```json
{
  "courseType": "v2.ondemand",
  "description": "Gamification is the application of game elements...",
  "domainTypes": [
    {"domainId": "computer-science", "subdomainId": "design-and-product"},
    {"domainId": "business",         "subdomainId": "marketing"}
  ],
  "photoUrl": "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/https://coursera-course-photos.s3.amazonaws.com/...",
  "id":             "69Bku0KoEeWZtA4u62x6lQ",
  "slug":           "gamification",
  "instructorIds":  ["226710"],
  "specializations": [],
  "workload":       "4-8 hours/week",
  "primaryLanguages": ["en"],
  "partnerIds":     ["6"],
  "certificates":   ["VerifiedCert"],
  "name":           "Gamification"
}
```

Field notes:
- `id` — opaque base64-ish string, stable identifier. Use for batch lookups and linking.
- `slug` — URL-safe identifier. Course page: `https://www.coursera.org/learn/{slug}`
- `courseType` — always `"v2.ondemand"` for self-paced courses in practice.
- `workload` — free-text string, e.g. `"4-8 hours/week"`, `"1 hour 30 minutes"`, `"4 weeks of study, 1-2 hours/week"`. Not normalized.
- `primaryLanguages` — ISO 639-1 list, e.g. `["en"]`, `["fr"]`.
- `partnerIds` — list of partner (university/org) IDs. Join to `partners.v1` by id.
- `instructorIds` — list of instructor IDs. Join to `instructors.v1` by id.
- `domainTypes` — list of `{domainId, subdomainId}` objects. Domain IDs include `"data-science"`, `"computer-science"`, `"business"`, `"information-technology"`.
- `certificates` — list of cert types, typically `["VerifiedCert"]`.
- `photoUrl` — direct CDN URL to course image. Works without auth.
- `specializations` — list of specialization IDs this course belongs to (often empty; not always populated here — use `onDemandSpecializations.v1` instead).
- `previewLink` — field exists but was empty in all tested records; skip it.
- `avgRating` — field does NOT appear in public API responses; not available.

### Pagination

```python
def iter_all_courses(fields=None, page_size=100):
    base_fields = "name,slug,description,primaryLanguages,workload,partnerIds,courseType,domainTypes,photoUrl"
    if fields:
        base_fields = fields
    start = 0
    while True:
        url = (
            f"https://api.coursera.org/api/courses.v1"
            f"?fields={base_fields}&limit={page_size}&start={start}"
        )
        data = json.loads(http_get(url))
        yield from data["elements"]
        nxt = data["paging"].get("next")
        if nxt is None:
            break
        start = int(nxt)
```

- `paging.next` is a string offset (e.g. `"100"`), or absent when exhausted.
- `paging.total` is present on the first page (e.g. `20659`) but absent on subsequent pages.
- `limit` up to at least 1000 works (tested: 1000 returned 1000 items). Use 100–500 for safe batches.

---

## 2. Partners API (http_get — works)

422 partners (universities, companies) as of test date.

```python
resp = http_get(
    "https://api.coursera.org/api/partners.v1"
    "?fields=name,squareLogo,description,shortName&limit=50&start=0"
)
data = json.loads(resp)
partners = data["elements"]
# paging.next and paging.total follow same structure as courses
```

### Partner record structure

```json
{
  "id":          "6",
  "name":        "University of Pennsylvania",
  "shortName":   "penn",
  "description": "The University of Pennsylvania (commonly referred to as Penn)...",
  "squareLogo":  "http://coursera-university-assets.s3.amazonaws.com/.../logo.png"
}
```

### Partner by ID (with courseIds)

```python
resp = http_get(
    "https://api.coursera.org/api/partners.v1"
    "?ids=6&fields=name,squareLogo,description,shortName,courseIds"
)
data = json.loads(resp)
partner = data["elements"][0]
# partner["courseIds"] is a list of course ID strings (150+ for large universities)
```

---

## 3. Specializations API (http_get — works)

```python
resp = http_get(
    "https://api.coursera.org/api/onDemandSpecializations.v1"
    "?fields=name,slug,description,partnerIds,courseIds,tagline&limit=100&start=0"
)
data = json.loads(resp)
specs = data["elements"]
```

### Specialization record structure

```json
{
  "id":          "AbCdEfGhIjKl",
  "name":        "SIEM Splunk",
  "slug":        "siem-splunk",
  "tagline":     "Learn SIEM fundamentals with Splunk",
  "description": "Course Overview:\n\nIn the \"SIEM Splunk\" specialization course...",
  "partnerIds":  ["1441"],
  "courseIds":   ["pu2XQCuEEe6qTBJCf71DPw", "Xc46mVFkEe6a4wrvTcwXPw", "YH1ok1FXEe62cBI5JZME2w"]
}
```

Note: Specializations paging does NOT include `paging.total` — iterate until `paging.next` is absent.

---

## 4. Instructors API (http_get — works)

Only useful for lookups by ID (from course `instructorIds`). The plain list endpoint
returns many empty records (empty name/bio).

```python
# Lookup specific instructors by ID
resp = http_get(
    "https://api.coursera.org/api/instructors.v1"
    "?ids=226710&fields=fullName,bio,department,title,photo"
)
data = json.loads(resp)
instructor = data["elements"][0]
```

### Instructor record structure

```json
{
  "id":         "226710",
  "fullName":   "Kevin Werbach",
  "title":      "Professor of Legal Studies and Business Ethics",
  "department": "Legal Studies and Business Ethics",
  "bio":        "Kevin Werbach is professor of Legal Studies...",
  "photo":      "https://d3njjcbhbojbot.cloudfront.net/api/utilities/v1/imageproxy/..."
}
```

---

## 5. Batch ID Lookup

Fetch multiple courses (or partners/instructors) in one request by passing a comma-separated `ids` list:

```python
ids = ",".join(["69Bku0KoEeWZtA4u62x6lQ", "hOzhxVNuEfCW8Q55q1kSNQ", "0HiU7Oe4EeWTAQ4yevf_oQ"])
resp = http_get(
    f"https://api.coursera.org/api/courses.v1"
    f"?ids={ids}&fields=name,slug,description,primaryLanguages,workload,partnerIds"
)
data = json.loads(resp)
# data["elements"] has exactly the courses you asked for
```

No observed limit on the number of IDs per request in testing (tried up to 3).

---

## 6. Keyword Search — BLOCKED for GET (405)

`q=search&query=...` returns **HTTP 405 Method Not Allowed** on GET.
This applies to all three resource types:
- `courses.v1?q=search&query=python` → 405
- `onDemandSpecializations.v1?q=search&query=data+science` → 405
- `partners.v1?q=search&query=stanford` → 405

The search endpoint requires a POST request (Coursera's public Autocomplete/Search
service). For keyword-based discovery without a browser, use the catalog list and filter
client-side, or use the browser approach below.

### Browser fallback for keyword search

```python
new_tab("https://www.coursera.org/search?query=machine+learning")
wait_for_load()
wait(3)  # Results load asynchronously via React
capture_screenshot()
```

Note: The search results page (`/search?query=...`) is a client-rendered React app. The
HTML returned by `http_get` does NOT contain course cards — it's a bare shell with no
`__NEXT_DATA__` or embedded JSON. A live browser is required to see rendered results.

---

## 7. Course Detail HTML Page (http_get — works, limited data)

```python
html = http_get("https://www.coursera.org/learn/machine-learning")
# html is ~980KB of server-rendered HTML (no NEXT_DATA, no Apollo state)
```

The course detail page IS served as full HTML (no JS-gate), but contains very
little machine-readable course data. What you can extract:

```python
import re, json

# Page title (includes course name)
title = re.search(r'<title[^>]*>(.*?)</title>', html).group(1)
# "Supervised Machine Learning: Regression and Classification  | Coursera"

# JSON-LD blocks (2 present)
jsonld_blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
# Block 0: FAQPage schema (common Q&A about how courses work)
# Block 1: BreadcrumbList (category path, e.g. Browse > Data Science > Machine Learning)
faq   = json.loads(jsonld_blocks[0])   # {"@type": "FAQPage", "mainEntity": [...]}
crumb = json.loads(jsonld_blocks[1])   # {"@type": "BreadcrumbList", "itemListElement": [...]}

# Extract breadcrumb categories
categories = [item["item"]["name"] for item in crumb["@graph"][0]["itemListElement"]]
# e.g. ["Browse", "Data Science", "Machine Learning"]
```

The HTML does NOT embed: description, rating, instructor names, enrollment count,
price, or any course-specific metadata as machine-readable fields.
Use the API (`courses.v1?ids=...`) to get those from the slug.

### Slug-to-ID lookup pattern

```python
# Get course data from slug (need ID first — get it from catalog or search)
# Pattern: enumerate catalog, match by slug
resp = http_get("https://api.coursera.org/api/courses.v1?fields=name,slug,description&limit=100&start=0")
data = json.loads(resp)
by_slug = {el["slug"]: el for el in data["elements"]}
course = by_slug.get("machine-learning")
```

---

## Endpoints Summary

| Endpoint | Method | Result |
|---|---|---|
| `courses.v1` (list) | GET | 200 OK — full catalog, 20,659 courses |
| `courses.v1?ids=...` | GET | 200 OK — batch lookup by ID |
| `courses.v1?q=search&query=...` | GET | **405 Method Not Allowed** |
| `partners.v1` (list) | GET | 200 OK — 422 partners |
| `partners.v1?ids=...` | GET | 200 OK — with courseIds |
| `partners.v1?q=search&query=...` | GET | **405 Method Not Allowed** |
| `onDemandSpecializations.v1` (list) | GET | 200 OK — paginated (no total) |
| `onDemandSpecializations.v1?q=search&query=...` | GET | **405 Method Not Allowed** |
| `instructors.v1?ids=...` | GET | 200 OK — rich records by ID |
| `instructors.v1` (list) | GET | 200 OK — mostly empty records |
| `degrees.v1` | GET | 403 Forbidden |
| `/search?query=...` page HTML | GET | 200 OK — React shell only, no data |
| `/learn/{slug}` page HTML | GET | 200 OK — HTML with JSON-LD breadcrumb only |

---

## Rate Limits

No rate limiting observed in testing:
- 5 consecutive requests with no delay: all succeeded, avg 0.55s each.
- No `X-RateLimit-*` or `Retry-After` headers in responses.
- No auth headers needed for any working endpoint.

Response headers that are present: `X-Coursera-Request-Id`, `X-Coursera-Trace-Id-Hex`,
`x-envoy-upstream-service-time`. No rate-limit indicators.

Use a small delay (0.5s) between requests if doing bulk enumeration of the full 20K+
catalog as a courtesy, but no hard cap was observed.

---

## Gotchas

- **`q=search` is POST-only**: All three resource types (courses, specializations,
  partners) return 405 on GET when `q=search` is added. There is no documented public
  POST endpoint. For keyword filtering, enumerate the catalog and filter client-side.

- **`paging.total` absent after page 1**: Only the first page response includes
  `paging.total`. Subsequent pages have only `paging.next`. Check for the `"next"` key
  being absent to detect end-of-list.

- **Specializations never include `paging.total`**: The `onDemandSpecializations.v1`
  endpoint never returns `paging.total` in any page. Iterate until `"next"` is absent.

- **`workload` is free-text, unnormalized**: Values include `"4-8 hours/week"`,
  `"1 hour 30 minutes"`, `"4 weeks of study, 1-2 hours/week"`. Do not parse as a number
  without normalization logic.

- **`instructors.v1` list returns empty records**: The plain list endpoint returns many
  instructors with empty `fullName`, `bio`, `title`. Always look up by `ids=` using
  IDs from course records.

- **`degrees.v1` is 403**: Degree programs are not accessible via the public API.

- **HTML pages contain no embedded course data**: Both the search page and the course
  detail page are React-rendered. `http_get` on `/search?query=...` returns an HTML
  shell with no course listings. `http_get` on `/learn/{slug}` returns HTML with only
  a FAQ JSON-LD and a breadcrumb JSON-LD — no course description, rating, price, or
  enrollment data as machine-readable fields.

- **`linked` resources don't populate**: Passing `includes=partners.v1` to the courses
  endpoint returns an empty `linked: {}` object. Cross-resource joins require separate
  requests by IDs.

- **`previewLink` and `avgRating` fields**: These field names are accepted without error
  but return no data in the response objects. Do not request them.
