# Job Boards — Indeed, Glassdoor, Stepstone

Covers: `indeed.com`, `glassdoor.com`, `stepstone.de`

---

## Do this first: construct search URLs directly

Never type into the search box on the homepage — bot detection triggers immediately. Build search URLs directly and navigate straight to results.

```python
from urllib.parse import quote_plus

# Indeed — English (US)
query, location = "Python developer", "San Francisco"
goto_url(f"https://www.indeed.com/jobs?q={quote_plus(query)}&l={quote_plus(location)}")
wait_for_load()
wait(2)

# Indeed — last 24 hours
goto_url(f"https://www.indeed.com/jobs?q={quote_plus(query)}&l={quote_plus(location)}&fromage=1")
wait_for_load()
wait(2)

# Glassdoor — public search (no login required for result cards)
goto_url(f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={quote_plus(query)}")
wait_for_load()
wait(2)

# Stepstone (Germany)
keyword, city = "Data Scientist", "Berlin"
goto_url(f"https://www.stepstone.de/jobs/{quote_plus(keyword)}/in-{quote_plus(city)}.html")
wait_for_load()
wait(2)
```

---

## URL patterns

### Indeed

| Goal | URL pattern |
|---|---|
| Keyword + location | `/jobs?q={title}&l={location}` |
| Last 24 hours | `/jobs?q={title}&l={location}&fromage=1` |
| Last 3 days | `/jobs?q={title}&l={location}&fromage=3` |
| Last week | `/jobs?q={title}&l={location}&fromage=7` |
| Remote only | `/jobs?q={title}&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11` |
| Full-time only | `/jobs?q={title}&l={location}&jt=fulltime` |
| Part-time | `/jobs?q={title}&l={location}&jt=parttime` |
| With salary | `/jobs?q={title}&l={location}&rbl=%24{min}%2B` |
| Page 2 (results 11-20) | append `&start=10` |
| Page 3 (results 21-30) | append `&start=20` |
| Job detail page | `https://www.indeed.com/viewjob?jk={job_key}` |

**Indeed country variants**: `.co.uk`, `.de`, `.fr`, `.com.au` — same URL structure, different base domain.

### Glassdoor

| Goal | URL pattern |
|---|---|
| Keyword search | `/Job/jobs.htm?sc.keyword={title}` |
| Keyword + city name | `/Job/jobs.htm?sc.keyword={title}&locT=C&locKeyword={city}` |
| Remote filter | `/Job/jobs.htm?sc.keyword={title}&remoteWorkType=1` |
| Next page | append `&p=2`, `&p=3` |

### Stepstone (Germany)

| Goal | URL pattern |
|---|---|
| Keyword in city | `/jobs/{keyword}/in-{city}.html` |
| Page 2 | `/jobs/{keyword}/in-{city}/page-2.html` |
| Page 3 | `/jobs/{keyword}/in-{city}/page-3.html` |
| Full-time | `/jobs/{keyword}/in-{city}.html?of=1` |

For Stepstone, keyword and city go directly in the path — encode spaces as `-`:
```python
kw_path = keyword.replace(" ", "-")
city_path = city.replace(" ", "-")
goto_url(f"https://www.stepstone.de/jobs/{kw_path}/in-{city_path}.html")
```

---

## Cookie / consent banner dismissal

Indeed (EU/UK) and Glassdoor show GDPR consent overlays. Dismiss before extraction.

```python
def dismiss_cookie_banner():
    """Try common consent button patterns. Safe to call even if no banner is present."""
    dismissed = js("""
    (function() {
      // Indeed: "Accept all cookies" button
      var selectors = [
        'button[id*="onetrust-accept"]',
        'button[id*="accept-all"]',
        '#onetrust-accept-btn-handler',
        'button[data-testid="cookie-consent-accept"]',
        // Glassdoor: consent modal
        'button[data-test="accept-cookies"]',
        // Generic patterns
        'button[class*="accept"]',
        'button[class*="consent"]',
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
    if dismissed:
        wait(1)
    return dismissed
```

Call immediately after `wait_for_load()` on `.co.uk`, `.de`, or `glassdoor.com`:

```python
goto_url("https://www.indeed.co.uk/jobs?q=Python+developer&l=London")
wait_for_load()
wait(2)
dismiss_cookie_banner()
wait(1)
```

---

## Workflow 1: Indeed — search result card extraction

Each result card on Indeed carries a `data-jk` attribute (the job key). Use it to construct direct URLs.

```python
import json
from urllib.parse import quote_plus

query, location = "machine learning engineer", "New York"
goto_url(f"https://www.indeed.com/jobs?q={quote_plus(query)}&l={quote_plus(location)}")
wait_for_load()
wait(2)
dismiss_cookie_banner()

jobs = js("""
(function() {
  // Cards live in <div data-jk="..."> or <li> with data-jk attribute
  var cards = document.querySelectorAll('[data-jk]');
  var out = [];
  for (var i = 0; i < cards.length; i++) {
    var c = cards[i];
    var jk = c.getAttribute('data-jk') || '';
    if (!jk) continue;

    // Title
    var titleEl = c.querySelector('h2.jobTitle span[title], h2.jobTitle span:not(.visually-hidden), [data-testid="job-title"]');
    var title = titleEl ? titleEl.innerText.trim() : '';

    // Company name
    var compEl = c.querySelector('[data-testid="company-name"], .companyName, span[data-testid="company-name"]');
    var company = compEl ? compEl.innerText.trim() : '';

    // Location
    var locEl = c.querySelector('[data-testid="text-location"], .companyLocation');
    var location = locEl ? locEl.innerText.trim() : '';

    // Salary — may not always be present in the card
    var salEl = c.querySelector('[data-testid="attribute_snippet_testid"], .salary-snippet-container, .metadata.salary-snippet');
    var salary = salEl ? salEl.innerText.trim() : '';

    // Posting date / age
    var dateEl = c.querySelector('[data-testid="myJobsStateDate"], span.date, .result-link-bar-container .date');
    var posted = dateEl ? dateEl.innerText.trim() : '';

    // Direct URL via job key
    var url = 'https://www.indeed.com/viewjob?jk=' + jk;

    if (title) {
      out.push({jk, title, company, location, salary, posted, url});
    }
  }
  return JSON.stringify(out);
})()
""")

results = json.loads(jobs)
for r in results:
    print(r)
# Typically returns 10–15 cards per page
```

---

## Workflow 2: Indeed — pagination (multi-page extraction)

Indeed paginates using `&start=N` where N increments by 10 per page.

```python
import json
from urllib.parse import quote_plus

query, location = "data scientist", "remote"
base_url = f"https://www.indeed.com/jobs?q={quote_plus(query)}&l={quote_plus(location)}"

all_jobs = []

for page in range(3):   # 3 pages = up to ~30 results
    start = page * 10
    url = base_url if start == 0 else f"{base_url}&start={start}"
    goto_url(url)
    wait_for_load()
    wait(2)   # mandatory — bot detection is aggressive on rapid loads

    if page == 0:
        dismiss_cookie_banner()

    batch_json = js("""
    (function() {
      var cards = document.querySelectorAll('[data-jk]');
      var out = [];
      for (var i = 0; i < cards.length; i++) {
        var c = cards[i];
        var jk = c.getAttribute('data-jk') || '';
        if (!jk) continue;
        var titleEl = c.querySelector('h2.jobTitle span[title], [data-testid="job-title"]');
        var compEl  = c.querySelector('[data-testid="company-name"], .companyName');
        var locEl   = c.querySelector('[data-testid="text-location"], .companyLocation');
        var salEl   = c.querySelector('[data-testid="attribute_snippet_testid"], .salary-snippet-container');
        var dateEl  = c.querySelector('[data-testid="myJobsStateDate"], span.date');
        out.push({
          jk,
          title:   titleEl ? titleEl.innerText.trim() : '',
          company: compEl  ? compEl.innerText.trim()  : '',
          location: locEl  ? locEl.innerText.trim()   : '',
          salary:  salEl   ? salEl.innerText.trim()   : '',
          posted:  dateEl  ? dateEl.innerText.trim()  : '',
          url: 'https://www.indeed.com/viewjob?jk=' + jk,
        });
      }
      return JSON.stringify(out.filter(j => j.title));
    })()
    """)

    batch = json.loads(batch_json)
    if not batch:
        break   # no results on this page — stop
    all_jobs.extend(batch)

print(f"Collected {len(all_jobs)} jobs across {page+1} pages")
```

**For `fromage` (date filter) + pagination**: keep the `fromage` param in the base URL:
```python
base_url = f"https://www.indeed.com/jobs?q={quote_plus(query)}&l={quote_plus(location)}&fromage=1"
```

---

## Workflow 3: Indeed — job detail page extraction

Fetch the full job description from the detail page. The `viewjob?jk=` URL is canonical and stable.

```python
import json, re

def get_indeed_job_detail(jk: str) -> dict:
    """Fetch full job details from an Indeed job key."""
    goto_url(f"https://www.indeed.com/viewjob?jk={jk}")
    wait_for_load()
    wait(2)

    detail = js("""
    (function() {
      // Title
      var titleEl = document.querySelector('[data-testid="jobsearch-JobInfoHeader-title"], h1.jobsearch-JobInfoHeader-title');
      var title = titleEl ? titleEl.innerText.trim() : '';

      // Company
      var compEl = document.querySelector('[data-testid="inlineHeader-companyName"] a, [data-company-name="true"]');
      var company = compEl ? compEl.innerText.trim() : '';

      // Location
      var locEl = document.querySelector('[data-testid="inlineHeader-companyLocation"], [data-testid="job-location"]');
      var location = locEl ? locEl.innerText.trim() : '';

      // Salary — shown when available in header
      var salEl = document.querySelector('[data-testid="jobsearch-OtherJobDetailsContainer"] [aria-label*="alary"], #salaryInfoAndJobType span');
      var salary = salEl ? salEl.innerText.trim() : '';

      // Full job description text
      var descEl = document.getElementById('jobDescriptionText');
      var description = descEl ? descEl.innerText.trim() : '';

      // Job type (Full-time, Part-time, Contract, etc.)
      var typeEl = document.querySelector('[data-testid="attribute_snippet_testid"]');
      var jobType = typeEl ? typeEl.innerText.trim() : '';

      // "Apply on company site" link — external application URL
      var externalBtn = document.querySelector('[data-jk][href*="indeed.com/applystart"], a[href*="indeed.com/applystart"]');
      var externalUrl = externalBtn ? externalBtn.href : '';

      return JSON.stringify({title, company, location, salary, jobType, description, externalUrl});
    })()
    """)
    return json.loads(detail)

# Example
detail = get_indeed_job_detail("abc123def456xyz")
print(detail["title"], "—", detail["salary"])
print(detail["description"][:500])  # first 500 chars
```

---

## Workflow 4: Glassdoor — search result extraction

Glassdoor shows a login modal after a few scrolls. Extract cards from the first visible load before triggering that wall.

```python
import json
from urllib.parse import quote_plus

query = "product manager"
goto_url(f"https://www.glassdoor.com/Job/jobs.htm?sc.keyword={quote_plus(query)}")
wait_for_load()
wait(3)   # Glassdoor JS rendering takes longer

# Dismiss cookie banner if present
dismiss_cookie_banner()

# Extract cards before any scroll (avoid triggering login modal)
jobs = js("""
(function() {
  // Glassdoor job cards: li[data-jobid] or article[data-id]
  var cards = document.querySelectorAll('li[data-jobid], li[class*="JobsList_jobListItem"]');
  if (!cards.length) {
    // Fallback: try generic article cards
    cards = document.querySelectorAll('[data-test="jobListing"], [id^="job-listing-"]');
  }
  var out = [];
  for (var i = 0; i < cards.length; i++) {
    var c = cards[i];

    // Job ID (used for canonical URL)
    var jobId = c.getAttribute('data-jobid') || c.getAttribute('data-id') || '';

    // Title
    var titleEl = c.querySelector('[data-test="job-title"], a[class*="JobCard_jobTitle"], .job-title');
    var title = titleEl ? titleEl.innerText.trim() : '';

    // Company
    var compEl = c.querySelector('[data-test="employer-name"], [class*="JobCard_employer"], .employer-name');
    var company = compEl ? compEl.innerText.trim() : '';

    // Location
    var locEl = c.querySelector('[data-test="emp-location"], [class*="JobCard_location"], .location');
    var location = locEl ? locEl.innerText.trim() : '';

    // Salary estimate (not always shown in card)
    var salEl = c.querySelector('[data-test="detailSalary"], [class*="salary"], .salaryEstimate');
    var salary = salEl ? salEl.innerText.trim() : '';

    // Company rating
    var ratingEl = c.querySelector('[data-test="rating"], [class*="ratingNumber"], .rating');
    var rating = ratingEl ? ratingEl.innerText.trim() : '';

    // Canonical URL
    var linkEl = c.querySelector('a[href*="/job-listing/"], a[href*="glassdoor.com/job"]');
    var url = linkEl ? linkEl.href : (jobId ? 'https://www.glassdoor.com/job-listing/glassdoor-jl' + jobId + '.htm' : '');

    if (title) out.push({jobId, title, company, location, salary, rating, url});
  }
  return JSON.stringify(out);
})()
""")

results = json.loads(jobs)
for r in results:
    print(r)
```

**If `jobs` returns an empty list**, Glassdoor has changed its DOM structure. Take a screenshot and inspect:

```python
capture_screenshot()
# Look for the actual card selector, then update the querySelectorAll above
```

---

## Workflow 5: Glassdoor — handling the login wall

Glassdoor increasingly shows a login modal after viewing a few listings. Detect and dismiss it.

```python
def dismiss_glassdoor_login_modal():
    """Close the Glassdoor sign-in / register modal if it appears."""
    closed = js("""
    (function() {
      // Close button on the modal
      var closeBtn = document.querySelector(
        '[alt="Close"], button[class*="modal_closeIcon"], [data-test="close-modal"]'
      );
      if (closeBtn && closeBtn.offsetParent !== null) {
        closeBtn.click();
        return 'closed';
      }
      // Sometimes the modal has an X with aria-label
      var ariaClose = document.querySelector('[aria-label="Close"]');
      if (ariaClose && ariaClose.offsetParent !== null) {
        ariaClose.click();
        return 'aria-closed';
      }
      return null;
    })()
    """)
    if closed:
        wait(1)
    return closed

# Strategy: extract as much as possible before the modal appears
# If the modal blocks results, dismiss it and try again
result = dismiss_glassdoor_login_modal()
if result:
    wait(1)
    # Re-run extraction after dismissal
```

If the modal is persistent and cannot be closed, switch to Indeed for the same search — it has more accessible public results.

---

## Workflow 6: Stepstone (German) — job extraction

Stepstone is server-rendered. Most data can be extracted with `http_get` for speed, or via `goto` + `js()` for dynamic content.

```python
import json, re
from urllib.parse import quote_plus

keyword = "Sachbearbeiter Einkauf"
city = "Regensburg"

# Stepstone encodes keyword/city in the path
kw_path = keyword.replace(" ", "-")
city_path = city.replace(" ", "-")

goto_url(f"https://www.stepstone.de/jobs/{kw_path}/in-{city_path}.html")
wait_for_load()
wait(2)
dismiss_cookie_banner()

jobs = js("""
(function() {
  // Stepstone result cards
  var cards = document.querySelectorAll(
    'article[data-at="job-item"], [data-genesis-element="JOB_CARD"], article.sc-fhzFiK'
  );
  var out = [];
  for (var i = 0; i < cards.length; i++) {
    var c = cards[i];

    // Title
    var titleEl = c.querySelector('h2[data-at="job-item-title"] a, [data-at="job-title"], .listing__title a');
    var title   = titleEl ? titleEl.innerText.trim() : '';
    var url     = titleEl ? (titleEl.href || '') : '';

    // Company
    var compEl = c.querySelector('[data-at="job-item-company-name"], [data-at="company-name"], .listing__company');
    var company = compEl ? compEl.innerText.trim() : '';

    // Location
    var locEl = c.querySelector('[data-at="job-item-location"], .listing__location');
    var location = locEl ? locEl.innerText.trim() : '';

    // Posting date
    var dateEl = c.querySelector('[data-at="job-posting-date"], time, .listing__date');
    var posted = dateEl ? (dateEl.getAttribute('datetime') || dateEl.innerText.trim()) : '';

    if (title) out.push({title, company, location, posted, url});
  }
  return JSON.stringify(out);
})()
""")

results = json.loads(jobs)
for r in results:
    print(r)
```

### Stepstone pagination

```python
import json

all_jobs = []
for page in range(1, 4):   # pages 1-3
    if page == 1:
        url = f"https://www.stepstone.de/jobs/{kw_path}/in-{city_path}.html"
    else:
        url = f"https://www.stepstone.de/jobs/{kw_path}/in-{city_path}/page-{page}.html"

    goto_url(url)
    wait_for_load()
    wait(2)

    if page == 1:
        dismiss_cookie_banner()

    batch_json = js("""
    (function() {
      var cards = document.querySelectorAll('article[data-at="job-item"], [data-genesis-element="JOB_CARD"]');
      var out = [];
      for (var i = 0; i < cards.length; i++) {
        var c = cards[i];
        var titleEl = c.querySelector('[data-at="job-item-title"] a, [data-at="job-title"]');
        var compEl  = c.querySelector('[data-at="job-item-company-name"]');
        var locEl   = c.querySelector('[data-at="job-item-location"]');
        var dateEl  = c.querySelector('time');
        out.push({
          title:    titleEl ? titleEl.innerText.trim() : '',
          company:  compEl  ? compEl.innerText.trim()  : '',
          location: locEl   ? locEl.innerText.trim()   : '',
          posted:   dateEl  ? dateEl.getAttribute('datetime') || dateEl.innerText.trim() : '',
          url:      titleEl ? titleEl.href : '',
        });
      }
      return JSON.stringify(out.filter(j => j.title));
    })()
    """)

    batch = json.loads(batch_json)
    if not batch:
        break
    all_jobs.extend(batch)

print(f"Stepstone: {len(all_jobs)} jobs collected")
```

---

## Indeed job key (jk) — direct URL construction

Indeed search result links go through a tracking redirect. **Do not use those redirect URLs.** Instead, extract the `data-jk` attribute directly for the stable canonical URL.

```python
# Correct approach: extract data-jk from the card
job_keys = js("""
JSON.stringify(
  Array.from(document.querySelectorAll('[data-jk]'))
    .map(el => el.getAttribute('data-jk'))
    .filter(jk => jk && jk.length > 0)
    .filter((jk, i, arr) => arr.indexOf(jk) === i)  // dedupe
)
""")
import json
jks = json.loads(job_keys)

# Canonical job detail URL for any job key:
for jk in jks:
    direct_url = f"https://www.indeed.com/viewjob?jk={jk}"
    print(direct_url)
```

If you already have a redirect URL and need to extract the `jk` from it:

```python
import re
def extract_jk(url: str) -> str | None:
    m = re.search(r'[?&]jk=([a-f0-9]+)', url)
    return m.group(1) if m else None
```

---

## Salary extraction and normalization

Salary appears in different places and formats depending on the job and site.

### Indeed salary patterns

```python
import re

def parse_indeed_salary(raw: str) -> dict:
    """
    Parse Indeed salary strings like:
      "$85,000 - $110,000 a year"
      "Up to $65 an hour"
      "$25 - $30 an hour"
      "From $120,000 a year"
      "Employer est.: $90,000 - $120,000 a year"
    Returns: {low, high, period, source}
    """
    if not raw:
        return {"raw": raw, "low": None, "high": None, "period": None, "source": None}

    source = None
    if "Employer est." in raw:
        source = "employer"
        raw = raw.replace("Employer est.:", "").strip()
    elif "Glassdoor est." in raw:
        source = "glassdoor"
        raw = raw.replace("Glassdoor est.:", "").strip()

    raw_clean = raw.replace(",", "")

    # Period
    period = None
    if "a year" in raw or "per year" in raw or "/yr" in raw:
        period = "year"
    elif "an hour" in raw or "per hour" in raw or "/hr" in raw:
        period = "hour"
    elif "a month" in raw or "per month" in raw:
        period = "month"

    # Range: two dollar amounts
    range_m = re.findall(r'\$?([\d]+(?:\.\d+)?)', raw_clean)
    low  = float(range_m[0]) if len(range_m) >= 1 else None
    high = float(range_m[1]) if len(range_m) >= 2 else low

    return {"raw": raw, "low": low, "high": high, "period": period, "source": source}

# Examples
parse_indeed_salary("$85,000 - $110,000 a year")
# -> {"low": 85000.0, "high": 110000.0, "period": "year", "source": None}

parse_indeed_salary("Employer est.: $90,000 - $120,000 a year")
# -> {"low": 90000.0, "high": 120000.0, "period": "year", "source": "employer"}

parse_indeed_salary("Up to $65 an hour")
# -> {"low": 65.0, "high": 65.0, "period": "hour", "source": None}
```

### Glassdoor salary note

Glassdoor shows two types of salary estimates:
- **"Employer est."** — the company provided a range in the job post
- **"Glassdoor est."** — Glassdoor estimated based on similar roles; shown with "(est.)" in the card

Both are shown as text inside the card. Parse the same way as Indeed.

If the salary is absent in the search result card, it is only available on the job detail page (requires a click through to the individual listing).

---

## Date normalization ("3 days ago" → actual date)

All three sites use relative timestamps. Convert to absolute dates when needed.

```python
import re
from datetime import datetime, timedelta

def parse_relative_date(text: str, reference_date: datetime = None) -> datetime | None:
    """
    Convert relative job posting dates to datetime objects.
    Handles: "Just posted", "Today", "1 day ago", "3 days ago", "30+ days ago"
    """
    if reference_date is None:
        reference_date = datetime.utcnow()

    text = text.strip().lower()

    if not text or text in ("", "unknown"):
        return None
    if text in ("just posted", "today", "active today"):
        return reference_date
    if "hour" in text:
        m = re.search(r'(\d+)', text)
        hours = int(m.group(1)) if m else 1
        return reference_date - timedelta(hours=hours)
    if "day" in text:
        m = re.search(r'(\d+)', text)
        days = int(m.group(1)) if m else 1
        return reference_date - timedelta(days=days)
    if "week" in text:
        m = re.search(r'(\d+)', text)
        weeks = int(m.group(1)) if m else 1
        return reference_date - timedelta(weeks=weeks)
    if "month" in text:
        m = re.search(r'(\d+)', text)
        months = int(m.group(1)) if m else 1
        return reference_date - timedelta(days=months * 30)
    if "30+" in text:
        return reference_date - timedelta(days=30)

    return None  # unparseable

# Examples
parse_relative_date("3 days ago")    # datetime ~3 days before now
parse_relative_date("Just posted")  # datetime.utcnow()
parse_relative_date("30+ days ago") # datetime 30 days ago
```

---

## Workflow 7: Fast bulk extraction with `http_get` (no browser)

For Indeed, the raw HTML of search results contains structured JSON in a `window.mosaic.providerData` script tag. This is faster and more reliable than DOM extraction.

```python
import json, re
from urllib.parse import quote_plus

def indeed_http_search(query: str, location: str = "", fromage: int = 0, start: int = 0) -> list[dict]:
    """
    Extract Indeed jobs via HTTP (no browser). Parses the embedded JSON payload.
    Returns up to ~15 jobs per call.
    """
    params = f"q={quote_plus(query)}&l={quote_plus(location)}&start={start}"
    if fromage:
        params += f"&fromage={fromage}"

    html = http_get(
        f"https://www.indeed.com/jobs?{params}",
        headers={
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml",
        }
    )

    # Check for CAPTCHA before parsing
    if "captcha" in html.lower() or "robot check" in html.lower():
        return []  # fall back to browser-based extraction

    # Indeed embeds job data in window.mosaic.providerData["mosaic-provider-jobcards"]
    m = re.search(
        r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});',
        html, re.DOTALL
    )
    if not m:
        return []

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []

    results_list = (
        data
        .get("metaData", {})
        .get("mosaicProviderJobCardsModel", {})
        .get("results", [])
    )

    jobs = []
    for r in results_list:
        jk = r.get("jobkey", "")
        jobs.append({
            "jk":       jk,
            "title":    r.get("title", ""),
            "company":  r.get("company", ""),
            "location": r.get("formattedLocation", ""),
            "salary":   r.get("salarySnippet", {}).get("text", ""),
            "posted":   r.get("formattedRelativeTime", ""),
            "url":      f"https://www.indeed.com/viewjob?jk={jk}",
            "snippet":  r.get("snippet", ""),  # short description preview
        })
    return jobs

# Example — last 24h remote jobs
jobs = indeed_http_search("software engineer", "remote", fromage=1)
for j in jobs:
    print(j["title"], "|", j["company"], "|", j["salary"])
```

If `http_get` returns 0 results (CAPTCHA or structure change), fall back to the `goto` + `js()` browser workflow above.

---

## Workflow 8: "Easy Apply" vs external application detection

Some Indeed listings apply on Indeed directly ("Easy Apply") while others redirect to the company site. Detect which type before deciding what to do.

```python
def get_application_type(jk: str) -> dict:
    """Returns {type: 'easy_apply'|'external'|'unknown', external_url: str|None}"""
    goto_url(f"https://www.indeed.com/viewjob?jk={jk}")
    wait_for_load()
    wait(2)

    return js("""
    (function() {
      // "Apply now" button pointing to /applystart = indeed-hosted Easy Apply
      var easyBtn = document.querySelector(
        'button[data-testid="applyButton"], [id="indeedApplyButton"], button[class*="IndeedApplyButton"]'
      );
      // "Apply on company site" button
      var extBtn = document.querySelector(
        'a[data-testid="applyButton"][href*="indeed.com/applystart"], a[href*="indeed.com/applystart"]'
      );
      // External redirect — check the main CTA
      var mainCta = document.querySelector('[data-testid="applyButton"]');
      var ctaHref = mainCta ? mainCta.href : '';

      if (easyBtn && !ctaHref.includes('apply.indeed')) {
        return {type: 'easy_apply', externalUrl: null};
      }
      if (extBtn || (ctaHref && !ctaHref.includes('indeed.com/viewjob'))) {
        return {type: 'external', externalUrl: ctaHref || null};
      }
      return {type: 'unknown', externalUrl: null};
    })()
    """)
```

---

## Bot detection and rate limiting

Indeed and Glassdoor have active bot detection. Violating these limits leads to CAPTCHA walls, IP blocks, or silently degraded results (cards with empty fields).

### Safe request cadence

```python
# Minimum wait between page loads
INTER_PAGE_WAIT = 2.5   # seconds — don't go below 2

# Between job detail page fetches
INTER_DETAIL_WAIT = 3.0  # seconds

# http_get concurrency limit
MAX_HTTP_CONCURRENT = 2  # never more than 2 at once for Indeed/Glassdoor
```

### CAPTCHA detection

```python
def is_captcha_page() -> bool:
    """Check if the current page is a CAPTCHA or block page."""
    url = page_info()["url"]
    title = js("document.title") or ""
    body_text = js("document.body ? document.body.innerText.substring(0, 500) : ''") or ""

    signals = [
        "captcha" in url.lower(),
        "robot" in title.lower(),
        "are you a human" in body_text.lower(),
        "verify you are human" in body_text.lower(),
        "unusual traffic" in body_text.lower(),
        "indeed.com/error" in url,
        "sorry" in title.lower() and "indeed" in url,
    ]
    return any(signals)

# Use after every goto:
goto_url(some_url)
wait_for_load()
wait(2)
if is_captcha_page():
    capture_screenshot()
    # Wait longer and retry once
    wait(10)
    goto_url(some_url)
    wait_for_load()
    wait(3)
```

### Glassdoor session hygiene

Glassdoor's bot detection is more fingerprint-based. If results stop loading:

1. Take a `capture_screenshot()` — confirm whether it is a login modal vs a block page
2. Dismiss any login modal first (`dismiss_glassdoor_login_modal()`)
3. If a block page appears, pause 30+ seconds before retrying
4. Switch to Indeed for the same query — results are similar and bot tolerance is higher

---

## Filtering by date, job type, and salary

### Indeed URL filter parameters

```python
from urllib.parse import quote_plus

def build_indeed_url(
    query: str,
    location: str = "",
    fromage: int = 0,       # days: 1=last 24h, 3=last 3 days, 7=last week
    job_type: str = "",     # "fulltime", "parttime", "contract", "internship", "temporary"
    remote: bool = False,
    start: int = 0,
) -> str:
    base = f"https://www.indeed.com/jobs?q={quote_plus(query)}&l={quote_plus(location)}"
    if fromage:
        base += f"&fromage={fromage}"
    if job_type:
        base += f"&jt={job_type}"
    if remote:
        base += "&remotejob=032b3046-06a3-4876-8dfd-474eb5e7ed11"
    if start:
        base += f"&start={start}"
    return base

# Examples
url = build_indeed_url("backend engineer", "Austin, TX", fromage=7, job_type="fulltime")
url = build_indeed_url("data analyst", remote=True, fromage=1)
```

---

## Collecting N results across pages

```python
import json
from urllib.parse import quote_plus

def collect_indeed_jobs(query: str, location: str = "", max_results: int = 20,
                        fromage: int = 0, job_type: str = "") -> list[dict]:
    """
    Collect up to max_results jobs from Indeed across multiple pages.
    Waits between pages to avoid bot detection.
    """
    all_jobs = []
    seen_jks = set()
    page = 0

    while len(all_jobs) < max_results:
        start = page * 10
        url = build_indeed_url(query, location, fromage=fromage, job_type=job_type, start=start)
        goto_url(url)
        wait_for_load()
        wait(2.5)

        if page == 0:
            dismiss_cookie_banner()

        if is_captcha_page():
            print(f"CAPTCHA on page {page+1}, stopping")
            break

        batch_json = js("""
        (function() {
          var cards = document.querySelectorAll('[data-jk]');
          var out = [];
          for (var i = 0; i < cards.length; i++) {
            var c = cards[i];
            var jk = c.getAttribute('data-jk') || '';
            if (!jk) continue;
            var titleEl = c.querySelector('h2.jobTitle span[title], [data-testid="job-title"]');
            var compEl  = c.querySelector('[data-testid="company-name"], .companyName');
            var locEl   = c.querySelector('[data-testid="text-location"], .companyLocation');
            var salEl   = c.querySelector('[data-testid="attribute_snippet_testid"], .salary-snippet-container');
            var dateEl  = c.querySelector('[data-testid="myJobsStateDate"], span.date');
            out.push({
              jk,
              title:    titleEl ? titleEl.innerText.trim() : '',
              company:  compEl  ? compEl.innerText.trim()  : '',
              location: locEl   ? locEl.innerText.trim()   : '',
              salary:   salEl   ? salEl.innerText.trim()   : '',
              posted:   dateEl  ? dateEl.innerText.trim()  : '',
              url: 'https://www.indeed.com/viewjob?jk=' + jk,
            });
          }
          return JSON.stringify(out.filter(j => j.title && j.jk));
        })()
        """)

        batch = json.loads(batch_json)
        if not batch:
            break  # no more results

        new_jobs = [j for j in batch if j["jk"] not in seen_jks]
        seen_jks.update(j["jk"] for j in new_jobs)
        all_jobs.extend(new_jobs)
        page += 1

    return all_jobs[:max_results]

# Examples
jobs = collect_indeed_jobs("Python developer", "San Francisco", max_results=20)
jobs = collect_indeed_jobs("remote software engineer", fromage=1, max_results=10)
jobs = collect_indeed_jobs("machine learning engineer", max_results=30, fromage=7, job_type="fulltime")
```

---

## Gotchas

- **`data-jk` is the job key, not a DOM id** — Always use `[data-jk]` to select cards, not `#job-...` ids which vary by page layout and A/B test variant.

- **Indeed redirect links are NOT stable URLs** — Anchor `href` values in search results go through `https://www.indeed.com/rc/clk?...` tracking redirects which expire. Always extract `data-jk` from the card and construct `https://www.indeed.com/viewjob?jk={jk}` yourself.

- **Salary is on the detail page, not the card** — Many listings show no salary in the search result card. If salary is required, fetch the individual `viewjob?jk=` page and extract it there. Budget `wait(3)` per detail page and do not fetch more than 5 detail pages per minute.

- **"Employer est." vs "Glassdoor est."** — These are two distinct data signals. Employer estimates come from the job post itself; Glassdoor estimates are crowd-sourced. The distinction matters when reporting salary accuracy to users.

- **Glassdoor login modal appears after 2-3 scrolls** — Extract all visible cards immediately on load before scrolling. If you need to load more results via scroll/infinite scroll, dismiss the modal first.

- **Glassdoor public results are limited** — Without login, Glassdoor shows ~10-15 cards. If the task requires 30+ results, use Indeed instead (no login required, up to ~15 per page with full pagination).

- **Stepstone uses path-based URL routing, not query params** — Spaces in keyword or city must be replaced with `-` for the path, not `%20` or `+`. `quote_plus()` is wrong for path segments. Use `.replace(" ", "-")`.

- **Stepstone pagination is in the path** — `/page-2.html`, `/page-3.html` — not `?page=2`. There is no `&start=N` param as in Indeed.

- **`http_get` for Glassdoor fails more often** — Glassdoor requires JS to render job cards. Use the browser path for Glassdoor. `http_get` only works reliably for Indeed and Stepstone where server-rendered HTML contains structured data.

- **Indeed embeds JSON in a `<script>` tag** — The `window.mosaic.providerData` block in the HTML source is the fastest extraction path but it can break if Indeed changes the key. Always have the DOM-based `js()` approach as a fallback.

- **Date strings are relative, not absolute** — "3 days ago", "30+ days ago", "Just posted" — none of these are machine-parseable dates without a reference point. Use `datetime.utcnow()` as the reference. "30+" means at least 30 days ago; treat as stale.

- **`fromage=1` on Indeed means "last 24 hours" but uses the listing creation date, not the apply-by date** — Fresh listings can appear in `fromage=3` results a day later due to indexing lag.

- **Indeed CAPTCHA appears as a clean-looking page** with an image puzzle or just a "continue" button — it will not raise an error. Always check `is_captcha_page()` before assuming extraction results are valid.

- **Glassdoor location IDs for `locT=C&locId=`** — Programmatic location filtering by ID requires a separate city-ID lookup (Glassdoor's internal city registry). For basic scraping, omit `locId` and use `locKeyword=` with the city name instead — results are less precise but don't require a lookup step.

- **User-agent matters** — `http_get` uses `Mozilla/5.0` by default (see `helpers.py`). For Indeed `http_get`, also set `Accept-Language: en-US,en;q=0.9` to avoid getting German or localized results based on IP geolocation.

- **Stepstone cookie modal is fullscreen** — On first load, Stepstone shows a fullscreen consent overlay that blocks the entire page. Always call `dismiss_cookie_banner()` before any extraction. If the overlay cannot be dismissed with the generic pattern, use a coordinate click: `capture_screenshot()` first to find the "Alle akzeptieren" (Accept all) button position, then `click_at_xy(x, y)`.

- **Glassdoor salary in card vs detail** — Salary text in the card may be truncated ("$90K - $120K (Glassdoor est.)"). The full salary breakdown (base, bonus, total comp) is only on the job detail page, which requires a click through.

- **"Easy Apply" listings may not have an external URL** — If the job only has an Indeed-hosted application, there is no company site URL. The `externalUrl` will be `null` — this is expected, not a scraping failure.

- **Empty cards on Indeed mobile breakpoints** — If the browser viewport is very narrow, Indeed may render a different card layout with different selectors. Keep viewport at normal desktop width (1280px+) to get consistent `[data-jk]` card rendering.
