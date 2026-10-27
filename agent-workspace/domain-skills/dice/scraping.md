# Dice — Tech Job Search Scraping

Field-tested against www.dice.com on 2026-10-23 and 2026-10-24 using a Browser Use cloud browser and plain HTTP (Python urllib).

robots.txt (fetched 2026-10-24) disallows `/jobs?q*`, `/jobsearch/` and `/job` for `User-agent: *` but allows `/jobs` and `/job-detail`, so this skill only requests the `/jobs/q-<keyword>-l-<location>-jobs` search pages (the same shape Dice lists in its own `sitemap_ts.xml` / `sitemap_tsl1.xml`) and `/job-detail/<guid>`.

## Quick summary

- Search result pages are server-rendered Next.js (App Router). Every page embeds the full result set as JSON inside `self.__next_f.push([1,"..."])` script strings, under a `"jobList":` key: `data` (20 jobs) + `meta` (`currentPage`, `pageCount`, `totalResults`, facets).
- Plain HTTP works: a truthful custom User-Agent got HTTP 200 and the full JSON on every request in these runs (about 100 page requests, mostly at a 2 s pace, no 429, no challenge, no consent banner).
- Page size is fixed at 20. Pages past 25 are clamped: `?page=26` and `?page=46` both returned `currentPage: 25`. So one search yields at most 500 jobs even when `pageCount` says 46. Treat that as a hard stop.
- Relevance order is not stable between requests, so deep pagination repeats and skips some jobs (78-99 unique per 100 slots measured). De-dup on `guid`, and the helpers below return `status: "partial"` with a reason whenever fewer than `totalResults` jobs were collected or `totalResults` changed between pages. They never return `"complete"`: Dice serves no stable snapshot, so the best case is `status: "count_matched"` (unique jobs reached a steady `totalResults`), which is still not proof that every posting was seen.
- `/job-detail/<guid>` pages carry a schema.org `JobPosting` JSON-LD block (full description, `validThrough`, postal address).
- The browser path works too (same JSON, read from the inline scripts), but it is not needed for logged-out search.

## What works

### 1. Search + paginate over plain HTTP (main method)

Self-contained, standard library only. Builds the public `/jobs/q-...-jobs` path, follows `?page=N`, stops at `pageCount`, at `max_pages` or at Dice's 25-page cap, de-duplicates by `guid`, validates each page, and raises on challenge pages, blocks or layout changes. `fetch` retries only 429/5xx and network errors (timeouts, resets) inside one 120 s deadline, with no sleep after the last attempt; a challenge page is never retried.

```python
import http.client, json, re, time, urllib.error, urllib.parse, urllib.request

UA = "dice-jobs-research/1.0 (python-urllib; personal job search script)"
BASE = "https://www.dice.com"
MAX_PAGE = 25          # Dice's cap: pages past 25 come back as page 25. Hard stop.
PAUSE_S = 2.0          # polite gap between page requests
DEADLINE_S = 120       # one budget per fetch(), across all attempts and backoff
DELAYS = (5, 15, 40)   # backoff between attempts, never after the last one
CHALLENGE = re.compile(r"cf-chl|/cdn-cgi/challenge-platform|px-captcha|captcha-delivery\.com|"
                       r"_Incapsula_Resource|g-recaptcha|h-captcha|"
                       r"<title>\s*(?:Access Denied|Just a moment|Attention Required)", re.I)
UNVERIFIED = "unique jobs reached totalResults, but Dice has no stable snapshot: not verified complete"

def search_url(keyword=None, location=None, page=1, filters=None):
    """Public search path /jobs/q-<kw>-l-<loc>-jobs. Hyphens are path separators
    there, so hyphens inside the keyword/location are replaced with spaces."""
    parts = []
    if keyword:
        parts.append("q-" + urllib.parse.quote_plus(keyword.replace("-", " ").strip()))
    if location:
        parts.append("l-" + urllib.parse.quote_plus(location.replace("-", " ").strip()))
    if not parts:
        raise ValueError("need a keyword or a location")
    params = dict(filters or {})
    if page > 1:
        params["page"] = page
    url = f"{BASE}/jobs/{'-'.join(parts)}-jobs"
    return url + ("?" + urllib.parse.urlencode(params) if params else "")

def fetch(url, attempts=4, deadline_s=DEADLINE_S):
    """GET under one overall deadline. Retries 429/5xx, timeouts and connection
    errors with DELAYS backoff; raises at once on redirects, other HTTP errors
    and challenge pages."""
    if not 1 <= attempts <= len(DELAYS) + 1:
        raise ValueError(f"attempts must be 1..{len(DELAYS) + 1}")
    if not 0 < deadline_s <= 120:
        raise ValueError("deadline_s must be in (0, 120]")
    end = time.monotonic() + deadline_s
    for i in range(attempts):
        left = end - time.monotonic()
        if left <= 0:
            raise TimeoutError(f"{deadline_s}s deadline used up for {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=min(30, left)) as r:
                final, html = r.geturl(), r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or i == attempts - 1:
                raise
            err = f"HTTP {e.code}"
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as e:
            if i == attempts - 1:
                raise
            err = repr(e)
        else:
            if final != url:
                raise RuntimeError(f"redirected to {final}")
            if CHALLENGE.search(html):
                raise RuntimeError(f"challenge/block page at {url} - stop, do not retry")
            return html
        if time.monotonic() + DELAYS[i] >= end:
            raise TimeoutError(f"{deadline_s}s deadline reached for {url} after {i + 1} attempts ({err})")
        time.sleep(DELAYS[i])

def is_count(v):
    """A real non-negative int. bool is an int subclass, so True/False are rejected too."""
    return type(v) is int and v >= 0

def parse_joblist(html):
    """Concatenate the RSC strings, decode the object after "jobList":, validate it."""
    chunks = re.findall(r'self\.__next_f\.push\(\[1,(".*?")\]\)</script>', html, re.S)
    flight = "".join(json.loads(c) for c in chunks)
    i = flight.find('"jobList":')
    if i < 0:
        raise RuntimeError("no jobList in page (layout change or block page) - stop and inspect")
    jl = json.JSONDecoder().raw_decode(flight, i + len('"jobList":'))[0]
    meta, data = jl.get("meta"), jl.get("data")
    if (not isinstance(meta, dict) or not isinstance(data, list)
            or any(not is_count(meta.get(k)) for k in ("currentPage", "pageCount", "totalResults"))):
        raise RuntimeError("jobList without valid data/meta counts - layout change, stop")
    bad = sum(1 for j in data if not (j.get("guid") and j.get("title") and j.get("detailsPageUrl")))
    if bad:
        raise RuntimeError(f"{bad} jobs missing guid/title/detailsPageUrl - layout change, stop")
    return jl

def normalize(j):
    loc = j.get("jobLocation") or {}
    return {
        "title": j.get("title"),
        "company": j.get("companyName"),
        "location": loc.get("displayName"),
        "workplace": ", ".join(j.get("workplaceTypes") or []),
        "employment_type": j.get("employmentType"),
        "posted": j.get("postedDate"),
        "salary": j.get("salary"),
        "url": j.get("detailsPageUrl"),
        "guid": j.get("guid"),
    }

def search_dice(keyword=None, location=None, max_pages=3, filters=None):
    """Returns (jobs, info). info["status"] is never "complete": Dice serves no
    stable snapshot, so a matching count does not prove every job was seen.
    "count_matched" = every requested page came back as asked, totalResults stayed
    the same on every page and at least that many unique jobs were collected
    (still unverified, see reason); otherwise "partial" with a reason."""
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")
    jobs, seen, meta, reason, totals, counts = [], set(), {}, None, [], []
    for page in range(1, min(max_pages, MAX_PAGE) + 1):
        if page > 1:
            time.sleep(PAUSE_S)
        jl = parse_joblist(fetch(search_url(keyword, location, page, filters)))
        meta = jl["meta"]
        totals.append(meta["totalResults"])
        counts.append(meta["pageCount"])
        if meta["currentPage"] != page:      # count shrank or clamp: stop, do not guess
            reason = f"asked for page {page}, Dice returned page {meta['currentPage']}"
            break
        for j in jl["data"]:
            if j["guid"] not in seen:
                seen.add(j["guid"])
                jobs.append(normalize(j))
        if page >= meta["pageCount"]:
            break
    fetched = page if reason is None else page - 1
    # Largest count seen, so a total that shrank mid-crawl cannot make a short crawl look complete.
    total, pages = max(totals), max(counts)
    # A failed pagination step (reason already set) is always partial, whatever the count says.
    if reason is None and len(jobs) >= total and min(totals) == total:
        # Order reshuffles and postings can swap without changing the count,
        # so a matching count is the best signal available, not proof.
        status, reason = "count_matched", UNVERIFIED
    else:
        status = "partial"
        if reason is None and pages > fetched:
            reason = ("Dice 25-page cap (500 jobs max per search)" if fetched == MAX_PAGE
                      else f"max_pages={max_pages} reached")
        if reason is None and min(totals) != total:
            reason = f"totalResults changed during the crawl ({min(totals)} to {total})"
        reason = reason or "relevance order reshuffled between pages (repeats/skips)"
    return jobs, {"status": status, "reason": reason, "total": total, "page_count": pages,
                  "pages_fetched": fetched, "collected": len(jobs)}

jobs, info = search_dice("Python Developer", "Houston, TX", max_pages=3)
print(info)
for r in jobs[:3]:
    print(json.dumps(r))

# Narrowing with Dice's own filter params (values come from meta.facetQueryResults):
remote, rinfo = search_dice("DevOps Engineer", max_pages=2,
                            filters={"filters.workplaceTypes": "Remote"})
print("remote devops:", rinfo)

# Small search, every page: the best case is "count_matched", never "complete".
full, finfo = search_dice("Python Developer", "Houston, TX", max_pages=30)
print("houston all pages:", finfo)
```

Output observed (trimmed):

```
{'status': 'partial', 'reason': 'max_pages=3 reached', 'total': 132, 'page_count': 7, 'pages_fetched': 3, 'collected': 60}
{"title": "Python Developer - Houston, TX (Locals only)", "company": "Source Mantra Inc", "location": "Houston, Texas, USA", "workplace": "On-Site", "employment_type": "Third Party, Contract", "posted": "2026-10-23T19:05:49Z", "salary": "$$65 - $70", "url": "https://www.dice.com/job-detail/7a92a6a3-2b6f-49be-9f2a-c6737ea95e2e", "guid": "7a92a6a3-2b6f-49be-9f2a-c6737ea95e2e"}
{"title": "Python Developer", "company": "Mindlance", "location": "Houston, Texas, USA", "workplace": "On-Site", "employment_type": "Contract", "posted": "2026-10-15T21:57:49Z", "salary": "50 - 58", ...}
{"title": "Python Developer - AWS, AI, LLM -  ZL", "company": "SES", "location": null, "workplace": "Remote", "employment_type": "Full-time", ...}
remote devops: {'status': 'partial', 'reason': 'max_pages=2 reached', 'total': 239, 'page_count': 12, 'pages_fetched': 2, 'collected': 39}
houston all pages: {'status': 'count_matched', 'reason': 'unique jobs reached totalResults, but Dice has no stable snapshot: not verified complete', 'total': 132, 'page_count': 7, 'pages_fetched': 7, 'collected': 132}
```

`collected` for the remote DevOps search was 39 on this run and 38, 39 and 40 on earlier 2026-10-24 runs, because page 2 repeats some page-1 jobs. The Houston `max_pages=30` search fetched all 7 pages and stopped at `pageCount`: 132 of 132 unique jobs on this run and on 2026-10-23, 131 of 132 on an earlier 2026-10-24 run (returned as `status: "partial"`, reason `relevance order reshuffled between pages`). Never report a `partial` result as the full set, and present `count_matched` as "count reached, not verified complete".

URL shapes that returned 200 with a `jobList`:

| Shape | Example |
|---|---|
| keyword | `/jobs/q-Rust+Engineer-jobs` (works for any keyword, not only sitemap ones) |
| keyword + location | `/jobs/q-Python+Developer-l-Houston%2C+TX-jobs` |
| location only | `/jobs/l-Austin%2C+TX-jobs` |
| page N | append `?page=2` |
| filters | `?filters.workplaceTypes=Remote`, `?filters.postedDate=ONE`, `?filters.employmentType=FULLTIME` (combine with `&page=N`) |

### 2. Same data in the browser (when you are already driving a tab)

The in-memory `self.__next_f` array is emptied after hydration (length 0 observed), but the inline `<script>` tags stay in the DOM, so read those. This runs in the attached tab in the background; it never calls `activate_tab`.

```python
import json, time, urllib.parse

def search_url(keyword=None, location=None, page=1):
    parts = []
    if keyword:
        parts.append("q-" + urllib.parse.quote_plus(keyword.replace("-", " ").strip()))
    if location:
        parts.append("l-" + urllib.parse.quote_plus(location.replace("-", " ").strip()))
    if not parts:
        raise ValueError("need a keyword or a location")
    url = "https://www.dice.com/jobs/" + "-".join(parts) + "-jobs"
    return url if page == 1 else f"{url}?page={page}"

READ_JOBLIST = r"""(()=>{
  const pre = 'self.__next_f.push([1,', parts = [];
  for (const s of document.querySelectorAll('script:not([src])')) {
    const t = s.textContent;
    if (!t.startsWith(pre)) continue;
    try { parts.push(JSON.parse(t.slice(pre.length, t.lastIndexOf(']')))); } catch (e) {}
  }
  const f = parts.join(''), i = f.indexOf('"jobList":');
  return i < 0 ? null : f.slice(i + 10);
})()"""

IS_CHALLENGE = r"""(()=>!!document.querySelector(
  'script[src*="challenge-platform"],#px-captcha,iframe[src*="captcha"],.g-recaptcha,.h-captcha')
  || /^(Access Denied|Just a moment|Attention Required)/i.test(document.title))()"""

def open_page(url, first=False):
    new_tab(url) if first else goto_url(url)
    wait_for_load()
    for _ in range(20):                      # confirm we are on the requested page (incl. query)
        if js("location.href") == url:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError(f"expected {url}, got {js('location.href')}")
    if js(IS_CHALLENGE):
        raise RuntimeError(f"challenge/block page at {url} - stop and tell the user, do not retry")

def is_count(v):
    return type(v) is int and v >= 0      # rejects bools and negatives

def browser_search(keyword=None, location=None, max_pages=2):
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")
    rows, seen, meta, page, reason, totals, counts = [], set(), {}, 0, None, [], []
    for page in range(1, min(max_pages, 25) + 1):
        if page > 1:
            time.sleep(2)
        open_page(search_url(keyword, location, page), first=(page == 1))
        raw = js(READ_JOBLIST)
        if not raw:
            raise RuntimeError("no jobList on page - stop and inspect (layout change or block page)")
        jl = json.JSONDecoder().raw_decode(raw)[0]
        meta, data = jl.get("meta"), jl.get("data")
        if (not isinstance(meta, dict) or not isinstance(data, list)
                or any(not is_count(meta.get(k)) for k in ("currentPage", "pageCount", "totalResults"))):
            raise RuntimeError("jobList without valid data/meta counts - layout change, stop")
        if any(not (j.get("guid") and j.get("title") and j.get("detailsPageUrl")) for j in data):
            raise RuntimeError("job without guid/title/detailsPageUrl - layout change, stop")
        totals.append(meta["totalResults"])
        counts.append(meta["pageCount"])
        if meta["currentPage"] != page:
            reason = f"asked for page {page}, Dice returned page {meta['currentPage']}"
            page -= 1
            break
        for j in data:
            if j["guid"] in seen:
                continue
            seen.add(j["guid"])
            loc = j.get("jobLocation") or {}
            rows.append({"title": j["title"], "company": j.get("companyName"),
                         "location": loc.get("displayName"), "employment_type": j.get("employmentType"),
                         "posted": j.get("postedDate"), "url": j["detailsPageUrl"]})
        if page >= meta["pageCount"]:
            break
    total, pages = max(totals), max(counts)   # largest seen: a shrinking total cannot fake a match
    if reason is None and len(rows) >= total and min(totals) == total:   # page mismatch = partial
        # Never "complete": order reshuffles and postings can swap without changing the count.
        status = "count_matched"
        reason = "unique jobs reached totalResults, but Dice has no stable snapshot: not verified complete"
    else:
        status = "partial"
        if reason is None and pages > page:
            reason = "Dice 25-page cap" if page == 25 else f"max_pages={max_pages} reached"
        if reason is None and min(totals) != total:
            reason = f"totalResults changed during the crawl ({min(totals)} to {total})"
        reason = reason or "relevance order reshuffled between pages (repeats/skips)"
    return rows, {"status": status, "reason": reason, "total": total,
                  "pages_fetched": page, "collected": len(rows)}

rows, info = browser_search("DevOps Engineer", "Remote", max_pages=2)
print(info)
for r in rows[:3]:
    print(json.dumps(r))
```

Output observed (trimmed):

```
{'status': 'partial', 'reason': 'max_pages=2 reached', 'total': 1588, 'pages_fetched': 2, 'collected': 40}
{"title": "DevOps Engineer", "company": "Dexian DISYS", "location": "Charlotte, North Carolina, USA", "employment_type": "Contract", "posted": "2026-10-15T20:11:32Z", "url": "https://www.dice.com/job-detail/be07b58c-3595-4790-a5c4-fed0892f9c8c"}
{"title": "DevOps Engineer", "company": "TechNix LLC", "location": "Raleigh, North Carolina, USA", "employment_type": "Contract, Third Party", ...}
```

This run got 40 unique jobs out of 40 slots; across runs the same call collected 38 and 28 (2026-10-23) and 35, 39 and 40 (2026-10-24), because the relevance order reshuffles between requests and page 2 repeats some page-1 jobs. See "Unstable order" under Gotchas.

DOM fallback if the JSON ever disappears: each result is `[data-testid="job-card"][role="article"]` inside `role="list"` with `aria-label="Job search results"`; the card link `a[data-testid="job-search-job-card-link"]` has `href="/job-detail/<guid>"` and `aria-label="View Details for <title> (<id>)"`. Card text only has relative dates ("Yesterday", "2d ago"), so prefer the JSON.

### 3. Job detail via JSON-LD (description, expiry, postal address)

Self-contained. Returns `None` only for Dice's own "Job Not Found" page (what an unknown or removed guid returned: HTTP 200, `<title>Job Not Found | Dice.com</title>`, no JSON-LD). Any other page without a valid `JobPosting` raises, so a challenge or block page is never mistaken for an expired posting.

```python
import http.client, json, re, time, urllib.error, urllib.request

UA = "dice-jobs-research/1.0 (python-urllib; personal job search script)"
DELAYS = (5, 15, 40)
CHALLENGE = re.compile(r"cf-chl|/cdn-cgi/challenge-platform|px-captcha|captcha-delivery\.com|"
                       r"_Incapsula_Resource|g-recaptcha|h-captcha|"
                       r"<title>\s*(?:Access Denied|Just a moment|Attention Required)", re.I)

def fetch(url, attempts=4, deadline_s=120):
    """Same contract as section 1: one deadline, bounded retries, raise on challenge."""
    if not 1 <= attempts <= len(DELAYS) + 1 or not 0 < deadline_s <= 120:
        raise ValueError("attempts must be 1..4 and deadline_s in (0, 120]")
    end = time.monotonic() + deadline_s
    for i in range(attempts):
        left = end - time.monotonic()
        if left <= 0:
            raise TimeoutError(f"{deadline_s}s deadline used up for {url}")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
            with urllib.request.urlopen(req, timeout=min(30, left)) as r:
                final, html = r.geturl(), r.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or i == attempts - 1:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException):
            if i == attempts - 1:
                raise
        else:
            if final != url:
                raise RuntimeError(f"redirected to {final}")
            if CHALLENGE.search(html):
                raise RuntimeError(f"challenge/block page at {url} - stop, do not retry")
            return html
        if time.monotonic() + DELAYS[i] >= end:
            raise TimeoutError(f"{deadline_s}s deadline reached for {url} after {i + 1} attempts")
        time.sleep(DELAYS[i])

def job_detail(detail_url):
    html = fetch(detail_url)
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        d = json.loads(block)
        if isinstance(d, dict) and d.get("@type") == "JobPosting":
            missing = [k for k in ("title", "datePosted", "hiringOrganization", "description") if not d.get(k)]
            if missing:
                raise RuntimeError(f"JobPosting missing {missing} at {detail_url} - stop and inspect")
            return d
    if re.search(r"<title>Job Not Found \| Dice\.com</title>", html):
        return None
    raise RuntimeError(f"no JobPosting JSON-LD and not a Job Not Found page at {detail_url} - stop and inspect")

# Take a fresh URL from a search page so this does not depend on one posting staying live.
first = re.search(r'href="(/job-detail/[0-9a-f-]{36})"', fetch("https://www.dice.com/jobs/q-Python+Developer-jobs"))
if not first:
    raise RuntimeError("no job-detail link on the search page")
jp = job_detail("https://www.dice.com" + first.group(1))
if jp is None:
    print("posting is gone (Job Not Found)")
else:
    addr = (jp.get("jobLocation") or {}).get("address") or {}
    print(jp["title"], "|", jp["hiringOrganization"].get("name"), "|", jp.get("employmentType"),
          "|", jp["datePosted"], "|", jp.get("validThrough"), "|", addr.get("addressLocality"), addr.get("addressRegion"))
    print(len(jp["description"]), "chars of description HTML")

print(job_detail("https://www.dice.com/job-detail/00000000-0000-0000-0000-000000000000"))  # unknown guid
```

Output observed (trimmed):

```
Equity Derivatives Python Developer - New York - COntract | SANS | CONTRACTOR | 2026-10-22T21:49:51.000Z | 2026-11-23T18:06:44.000Z | New York NY
7726 chars of description HTML
None
```

JSON-LD keys seen: `title, datePosted, validThrough, employmentType, hiringOrganization{name,sameAs,logo}, jobLocation{address{addressLocality,addressRegion,postalCode,addressCountry}}, baseSalary, description, identifier, applicantLocationRequirements, url`. Note `employmentType` here is the schema.org enum (`CONTRACTOR`), not the search-card label (`Contract`).

## Fields (search `jobList.data[]`)

| Field | Example | Notes |
|---|---|---|
| `title` | `"Python Developer"` | |
| `companyName` | `"Mindlance"` | |
| `jobLocation.displayName` | `"Houston, Texas, USA"` | `jobLocation` is `null` for many remote jobs; also has `city`, `state`, `region`, `country` |
| `workplaceTypes` | `["Remote", "On-Site"]` | list: `On-Site`, `Remote`, `Hybrid` |
| `isRemote` | `false` | |
| `employmentType` | `"Third Party, Contract"` | comma-joined labels: `Full-time`, `Part-time`, `Contract`, `Third Party` |
| `employerType` | `"Recruiter"` | `Direct Hire`, `Recruiter`, `Other` |
| `postedDate` | `"2026-10-23T19:05:49Z"` | ISO 8601 UTC; `modifiedDate` also present |
| `salary` | `"Depends on Experience"` | free text, key missing on some jobs |
| `detailsPageUrl` | `"https://www.dice.com/job-detail/<guid>"` | absolute URL |
| `guid` / `id` | UUID / 32-hex | `guid` is the detail-page id; use it to de-dup |
| `summary` | first ~500 chars of description | |
| `easyApply`, `workFromHomeAvailability`, `companyProfileId`, `companyLogoUrl`, `score` | | |

`meta` holds `currentPage`, `pageSize` (20), `pageCount`, `totalResults`, `searchedLocation` (resolved city, lat/long, 30 mi radius), `sortBy` (`relevance`) and `facetQueryResults` (counts per employment type, posted date `ONE`/`THREE`/`SEVEN`, employer type, workplace type, easy apply, willing to sponsor).

## Gotchas

- Use the `/jobs/q-...-jobs` path, not the `/jobs?q=...` query form: robots.txt disallows `/jobs?q*`.
- Hyphens split the path: `q-Front-End+Developer-jobs` was read as "Front" (top hits were "Front Office ..." and "Front Desk ..."). Replace hyphens with spaces first; `q-Front+End+Developer-jobs` returned real front-end roles. `Winston-Salem, NC` as `Winston+Salem%2C+NC` still resolved to "Winston-Salem, NC, USA".
- URL-encode with `quote_plus`: `C#` must be `C%23` (`/jobs/q-C%23+Developer-jobs` worked), commas become `%2C`.
- 25-page clamp: any `page` above 25 silently returns page 25, so compare `meta.currentPage` to the page you asked for. `pageCount` can exceed 25 (46 for "Python Developer"); 500 jobs is the per-search ceiling. Treat it as a hard stop (`search_dice` returns `status: "partial"`, reason `Dice 25-page cap`); do not split one search into many slices or reshape the query to get around it.
- `pageSize` query param is ignored; always 20 per page. `page=0` returns page 1.
- Unstable order: results are always sorted by `relevance` and the order reshuffles between requests, so consecutive pages repeat some jobs and skip others. Unique jobs over pages 1-5 (100 slots) measured on 2026-10-23: "Python Developer" 99, "Data Engineer" in Chicago 91, "DevOps Engineer" 89, "DevOps Engineer" + `l-Remote` 78. Reloading the same page 2 returned only 8 of the same 20 jobs. Small result sets came back at or near the full count (Houston "Python Developer": 132 of 132 over 7 pages on 2026-10-23 and in the latest 2026-10-24 run, 131 of 132 in an earlier 2026-10-24 run). `sortBy=date`, `sort=date`, `sortBy=postedDate` were all ignored (`meta.sortBy` stayed `relevance`). Always de-dup on `guid` and report `len(jobs)` against `totalResults` instead of assuming full coverage.
- The same title can be posted twice under different `guid`s (seen for one recruiter); those are separate postings, keep both.
- `l-Remote` does not filter to remote jobs (top hits were On-Site); use `filters.workplaceTypes=Remote`.
- Counts drift between requests (918 vs 919 total within minutes) because postings update continuously. Both search helpers keep the largest `totalResults` seen and return `status: "partial"` (reason `totalResults changed during the crawl`) when it changed between pages, so a shrinking count never turns a short crawl into a match. A steady count does not prove a steady set either (one posting can close as another opens), which is why the best status is `count_matched`, not `complete`.
- No cookie/consent banner appeared on these pages in the cloud browser (US). No region redirect seen.
- Polite pacing: 2 s between pages was used for the whole run without any 429. `fetch` retries 429/5xx and network errors only inside one 120 s deadline; a 403, a challenge page or a page without `jobList` raises at once. Stop there and tell the user; do not retry around it or change the User-Agent.

## What does not work / not used

- `/jobs?q=...`, `/jobsearch/`, `/job/...`, `/apply-redirect*`, `/profile/`, `/rss/`, `/feed/`: disallowed in robots.txt, not requested.
- Reading `window.self.__next_f` in the browser after load: it is an empty array (length 0) once hydrated; read the inline `<script>` text instead.
- Unknown keywords return an empty page cleanly: `/jobs/q-zzqqxxnotarealskill-jobs` gave `data: []`, `pageCount: 0`, `totalResults: 0`.
- Applying and saved/recommended jobs were not tested (account features, out of scope for logged-out scraping).
