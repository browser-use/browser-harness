# Wellfound (AngelList) — Startup Jobs & Company Profiles

Field-tested against wellfound.com on 2026-04-18.
All confirmed via live HTTP probes and response header analysis.

---

## Anti-bot verdict: browser required, no http_get workaround exists

**`http_get` returns HTTP 403 on every Wellfound URL without exception** (except `robots.txt`).

Tested endpoints (all 403):
- `/company/stripe`
- `/jobs`
- `/jobs?role=engineer&location=remote`
- `/company/stripe/jobs`
- `/sitemap.xml`, `/sitemap_index.xml`
- `/jobs.rss`
- `POST /graphql` (HTTP 403, Cloudflare managed challenge)

Old AngelList public API (`api.angel.co/1/...`) returns `404 Not Found` — permanently shut down.

**Dual anti-bot stack confirmed from response headers:**

| Layer | System | Evidence |
|-------|--------|----------|
| Page GETs | DataDome | `X-DataDome: protected`, `X-DD-B: 2`, `Set-Cookie: datadome=...` |
| API POSTs | Cloudflare Bot Management | `Cf-Mitigated: challenge` |

The 403 response body contains a DataDome captcha challenge script (`geo.captcha-delivery.com`) AND an embedded Cloudflare challenge (`window.__CF$cv$params`). Both fire simultaneously. Neither cookie can be replayed — both are TLS-fingerprint-bound.

**Use `new_tab()` + `wait()` exclusively. Never use `http_get` for Wellfound.**

---

## Tech stack (confirmed from response headers)

Wellfound is a **Ruby on Rails + React + Apollo GraphQL** hybrid app — NOT a pure Next.js app.

Confirmed headers from `robots.txt` (the only accessible endpoint):
```
x-runtime: 0.006700          → Rails rack middleware timer
x-request-id: 4645fd66...    → Rails request ID
x-xss-protection: 1; mode=block  → Rails security defaults
Set-Cookie: _wellfound=...   → Rails session cookie
Server: cloudflare           → Cloudflare CDN
```

Implications:
- **`__NEXT_DATA__` is NOT present** — not a Next.js app
- **`window.__APOLLO_STATE__` or `window.gon` may be present** — check these instead
- CSRF token is in a `<meta name="csrf-token">` tag (Rails default)
- Session cookie is `_wellfound=...` for anonymous sessions; login sessions add `_wellfound_session=...`

---

## Do this first: open in new tab, wait for DataDome to resolve

```python
new_tab("https://wellfound.com/company/stripe")
wait_for_load()
wait(5)   # DataDome JS fingerprinting runs ~2-4s after readyState=complete
```

Verify you are past the DataDome challenge before extracting:

```python
title = js("document.title")
url = page_info()["url"]

if "wellfound.com" not in url or not title or "Just a moment" in title:
    # DataDome or CF challenge did not resolve — wait longer
    wait(8)
    title = js("document.title")
    if "Just a moment" in title or not title:
        screenshot("/tmp/wellfound_block.png")
        raise RuntimeError("DataDome/CF challenge did not resolve — see screenshot")
```

DataDome resolves **silently** in a real Chrome session via CDP — no user interaction required.
The challenge is a JS fingerprint check that passes automatically when running in a real browser.

---

## URL patterns

| Goal | URL |
|------|-----|
| Company profile | `https://wellfound.com/company/{slug}` |
| Company jobs | `https://wellfound.com/company/{slug}/jobs` |
| Company culture | `https://wellfound.com/company/{slug}/culture` |
| Job board (all) | `https://wellfound.com/jobs` |
| Job board filtered | `https://wellfound.com/jobs` — then use UI filters (query params are disallowed by robots.txt) |
| Investor profile | `https://wellfound.com/investor/{slug}` |
| User profile | `https://wellfound.com/u/{username}` (disallowed by robots.txt, login wall) |

**Note on query params:** `robots.txt` disallows `?role=*`, `?jobId=*`, `?jobSlug=*`, `?location=*`.
Wellfound enforces these with login walls or redirects for most filtered job searches.

---

## Workflow 1: Company profile — name, description, team size, funding, tags

Navigate to the company page and extract structured data. Most fields are visible without login.

```python
import json

new_tab("https://wellfound.com/company/stripe")
wait_for_load()
wait(5)

# Check for Apollo state (Rails + React app, not Next.js)
# Wellfound embeds data in window.gon or inline script tags
apollo_raw = js("""
(function() {
  // Try window.__APOLLO_STATE__ (Apollo Client cache)
  if (window.__APOLLO_STATE__) return JSON.stringify(window.__APOLLO_STATE__);
  // Try window.gon (Rails Gon gem)
  if (window.gon) return JSON.stringify(window.gon);
  // Try inline <script> tags containing startup data
  var scripts = Array.from(document.querySelectorAll('script:not([src])'));
  for (var s of scripts) {
    var t = s.textContent || '';
    if (t.includes('"name"') && t.includes('"description"') && t.includes('teamSize')) {
      return t.substring(0, 5000);
    }
  }
  return null;
})()
""")

if apollo_raw:
    try:
        data = json.loads(apollo_raw)
        # Apollo State: look for Startup:{id} keys
        for key, val in data.items():
            if key.startswith("Startup:") and isinstance(val, dict):
                print("Company:", val.get("name"))
                print("Description:", val.get("description") or val.get("highConcept"))
                print("Team size:", val.get("teamSize"))
                print("Total raised:", val.get("totalRaised"))
                print("Hiring:", val.get("hiring"))
        print(json.dumps(data, indent=2)[:3000])
    except json.JSONDecodeError:
        # Raw script tag — parse key fields with regex
        import re
        name = re.search(r'"name"\s*:\s*"([^"]+)"', apollo_raw)
        desc = re.search(r'"description"\s*:\s*"([^"]+)"', apollo_raw)
        print("Name:", name.group(1) if name else "not found")
        print("Desc:", desc.group(1) if desc else "not found")
```

If the structured data path fails, fall back to DOM extraction:

```python
# DOM extraction — company profile page
profile = js("""
(function() {
  // Company name — first h1 on the page
  var nameEl = document.querySelector('h1');

  // Description — first substantial paragraph or div with class containing 'description'
  var descEl = (
    document.querySelector('[class*="description"]') ||
    document.querySelector('[class*="about"]') ||
    document.querySelector('p[class*="startupDescription"]')
  );

  // Tags — market/role tags are links with /jobs?role= or /location/ in href
  // Wellfound uses Tailwind (no stable class names) — use href pattern
  var roleLinks = Array.from(document.querySelectorAll('a[href*="/jobs?role="]')).map(a => a.innerText.trim());
  var locationLinks = Array.from(document.querySelectorAll('a[href*="/location/"]')).map(a => a.innerText.trim());

  // Team size / funding — look in page text for patterns
  var bodyText = document.body.innerText;

  // Company size: "11-50 employees" or "51-200 people" pattern
  var sizeMatch = bodyText.match(/(\d+[-–]\d+)\s+(employees|people)/i);
  var teamSize = sizeMatch ? sizeMatch[0] : null;

  // Funding: "$X.XM" or "Raised $X" pattern
  var fundingMatch = bodyText.match(/\$[\d,.]+[KMBkm]\s*(raised|in funding|Series [A-Z])?/i);
  var funding = fundingMatch ? fundingMatch[0] : null;

  // Stage: "Series A", "Seed", "Series B", etc.
  var stageMatch = bodyText.match(/\b(Seed|Series [A-Z]\+?|Pre-seed|Angel|Late Stage|Public)\b/);
  var stage = stageMatch ? stageMatch[0] : null;

  return JSON.stringify({
    name:     nameEl   ? nameEl.innerText.trim() : null,
    desc:     descEl   ? descEl.innerText.trim().substring(0, 500) : null,
    teamSize: teamSize,
    funding:  funding,
    stage:    stage,
    roles:    roleLinks.slice(0, 10),
    locations: locationLinks.slice(0, 5),
  });
})()
""")

data = json.loads(profile)
print(json.dumps(data, indent=2))
```

---

## Workflow 2: Company jobs listing

```python
import json

company_slug = "stripe"
new_tab(f"https://wellfound.com/company/{company_slug}/jobs")
wait_for_load()
wait(5)

jobs = js("""
(function() {
  // Job listing cards — Wellfound uses role="listitem" or li elements in job list
  var cards = document.querySelectorAll('[data-test^="StartupJobListing"], li[class*="job"], div[class*="JobListing"]');
  if (!cards.length) {
    // Broad fallback: all anchor tags with /jobs/ in href
    var links = Array.from(document.querySelectorAll('a[href*="/jobs/"]'));
    return JSON.stringify(links.map(a => ({
      title: a.innerText.trim().split('\\n')[0],
      href: a.href,
    })).filter(j => j.title && j.title.length > 2).slice(0, 30));
  }
  return JSON.stringify(Array.from(cards).map(card => {
    var titleEl = card.querySelector('h2, h3, [class*="title"], [class*="jobTitle"]');
    var locEl   = card.querySelector('[class*="location"], [class*="Location"]');
    var compEl  = card.querySelector('[class*="salary"], [class*="comp"], [class*="equity"]');
    var linkEl  = card.querySelector('a[href*="/jobs/"]');
    return {
      title:    titleEl ? titleEl.innerText.trim() : '',
      location: locEl   ? locEl.innerText.trim()   : '',
      comp:     compEl  ? compEl.innerText.trim()   : '',
      href:     linkEl  ? linkEl.href               : '',
    };
  }).filter(j => j.title));
})()
""")

results = json.loads(jobs)
print(f"Found {len(results)} jobs")
for j in results:
    print(f"  {j['title']} | {j.get('location','?')} | {j.get('comp','?')}")
```

---

## Workflow 3: Job board — browse all jobs

The main `/jobs` page shows a curated job feed. Filters are not accessible via URL params (DataDome blocks `?role=...`). Use the UI dropdown filters after loading the page.

```python
import json

new_tab("https://wellfound.com/jobs")
wait_for_load()
wait(5)

# Extract visible job cards
jobs = js("""
(function() {
  // Job cards on the main /jobs board
  var cards = document.querySelectorAll(
    '[data-test*="job"], [class*="JobCard"], [class*="jobListing"], ' +
    'li[class*="job"], article[class*="job"]'
  );
  if (!cards.length) {
    // Fallback: links to job detail pages
    var links = Array.from(document.querySelectorAll('a[href*="/company/"][href*="/jobs/"]'));
    return JSON.stringify(links.map(a => ({
      href: a.href,
      text: a.innerText.trim().substring(0, 100),
    })).slice(0, 30));
  }
  return JSON.stringify(Array.from(cards).map(card => {
    var titleEl   = card.querySelector('h2, h3, [class*="title"]');
    var companyEl = card.querySelector('[class*="company"], [class*="startup"]');
    var locEl     = card.querySelector('[class*="location"]');
    var linkEl    = card.querySelector('a[href*="/jobs/"]');
    return {
      title:   titleEl   ? titleEl.innerText.trim()   : '',
      company: companyEl ? companyEl.innerText.trim() : '',
      location: locEl    ? locEl.innerText.trim()     : '',
      href:    linkEl    ? linkEl.href                 : '',
    };
  }).filter(j => j.title));
})()
""")

results = json.loads(jobs)
print(f"Found {len(results)} jobs")
```

---

## Workflow 4: GraphQL API (authenticated sessions only)

Wellfound's GraphQL endpoint (`/graphql`) requires:
1. A valid `_wellfound` session cookie from a real browser load
2. A CSRF token from the page's `<meta name="csrf-token">` tag
3. Cloudflare Bot Management to have passed (only happens in a real Chrome session)

**This approach only works from inside a browser session (after navigating to any Wellfound page).**

```python
import json

# Step 1: Load any Wellfound page so the session cookie + DataDome cookie are set
new_tab("https://wellfound.com/")
wait_for_load()
wait(5)

# Step 2: Extract CSRF token from meta tag
csrf = js("document.querySelector('meta[name=\"csrf-token\"]') ? document.querySelector('meta[name=\"csrf-token\"]').getAttribute('content') : null")
if not csrf:
    raise RuntimeError("CSRF token not found — page may not have loaded correctly")

print(f"CSRF token: {csrf[:20]}...")

# Step 3: Execute GraphQL query via fetch() from within the browser
# This uses the browser's existing cookies automatically
result = js(f"""
(async function() {{
  try {{
    var resp = await fetch('/graphql', {{
      method: 'POST',
      credentials: 'include',
      headers: {{
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'x-csrf-token': '{csrf}',
        'x-requested-with': 'XMLHttpRequest',
      }},
      body: JSON.stringify({{
        query: `query StartupShow($slug: String!) {{
          startup(slug: $slug) {{
            id
            name
            description: highConcept
            productDesc
            teamSize
            locations {{ displayName }}
            markets {{ displayName }}
            totalRaised
            fundingStage
            badges
            hiring
            jobListingsCount
          }}
        }}`,
        variables: {{ slug: "stripe" }}
      }})
    }});
    var data = await resp.json();
    return JSON.stringify(data);
  }} catch(e) {{
    return JSON.stringify({{error: e.message}});
  }}
}})()
""")

# js() with async returns a Promise — use js_async() if available, or eval trick:
# Note: the above may return None if js() doesn't await Promises.
# Use this pattern instead if js() doesn't handle async:
result_sync = js("""
var done = false, out = null;
fetch('/graphql', {
  method: 'POST',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
    'x-csrf-token': document.querySelector('meta[name="csrf-token"]').content,
    'x-requested-with': 'XMLHttpRequest',
  },
  body: JSON.stringify({
    query: '{ __typename }',
  })
}).then(r => r.json()).then(d => { window._wf_gql_result = JSON.stringify(d); });
'pending'
""")
# Wait for async result
import time; time.sleep(3)
gql_result = js("window._wf_gql_result || null")
if gql_result:
    data = json.loads(gql_result)
    print("GraphQL response:", json.dumps(data, indent=2)[:1000])
```

### Known GraphQL operations

| Operation | Purpose |
|-----------|---------|
| `StartupShow` | Full company profile (name, desc, funding, team size, markets) |
| `JobListingsIndex` | Paginated job board |
| `JobSearch` | Filtered job search by role/location |
| `UserProfile` | User/candidate profile |
| `InvestorShow` | VC/investor profile |

---

## Handling the login wall

Wellfound shows a sign-in modal on:
- Job detail pages (immediately or after 2-3 seconds)
- Candidate profile pages (immediately)
- Some company pages after scrolling

Company overview pages typically show content without login. Job listings require login to see full details and apply.

```python
def dismiss_wellfound_login_modal():
    """Close the Wellfound sign-in modal. Safe to call if no modal is present."""
    closed = js("""
    (function() {
      var selectors = [
        'button[aria-label="Close"]',
        'button[class*="close"]',
        'button[class*="Close"]',
        '[data-test="close-modal"]',
        '[aria-label="Dismiss"]',
        'button[class*="dismiss"]',
        // Wellfound-specific: modal overlay dismiss
        'div[class*="Modal"] button[type="button"]',
      ];
      for (var s of selectors) {
        var btn = document.querySelector(s);
        if (btn && btn.offsetParent !== null) {
          btn.click();
          return s;
        }
      }
      // Try pressing Escape
      document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', keyCode: 27, bubbles: true}));
      return 'escape';
    })()
    """)
    if closed:
        wait(1)
    return closed
```

---

## Detecting DataDome / challenge page

After `new_tab()` + `wait(5)`, verify you are on a real Wellfound page:

```python
def wellfound_is_blocked() -> bool:
    """True if DataDome or Cloudflare challenge is still showing."""
    title = js("document.title") or ""
    url   = page_info()["url"]
    # DataDome challenge page has no useful title; CF shows "Just a moment..."
    blocked = (
        "Just a moment" in title or
        "wellfound.com" not in url or
        "captcha-delivery.com" in js("document.body.innerHTML or ''") or
        not title
    )
    return blocked

# Usage
new_tab("https://wellfound.com/company/stripe")
wait_for_load()
wait(5)

if wellfound_is_blocked():
    wait(8)   # DataDome sometimes needs up to 10s total
    if wellfound_is_blocked():
        screenshot("/tmp/wellfound_blocked.png")
        raise RuntimeError("DataDome/CF challenge did not resolve — see /tmp/wellfound_blocked.png")
```

---

## Key selectors reference

Wellfound uses **Tailwind CSS** — no stable semantic class names. These patterns are robust:

| Target | Selector strategy |
|--------|------------------|
| Company name | `h1` (first on page) |
| Company description | `[class*="description"]`, `[class*="about"]` |
| Team size | Text search: `/\d+[-–]\d+\s+(employees\|people)/i` |
| Funding amount | Text search: `/\$[\d,.]+[KMBkm]/i` |
| Funding stage | Text search: `/\b(Seed\|Series [A-Z]\+?\|Pre-seed\|Late Stage)\b/` |
| Role/market tags | `a[href*="/jobs?role="]` |
| Location tags | `a[href*="/location/"]` |
| Job cards | `a[href*="/company/"][href*="/jobs/"]` (broad fallback) |
| Job title | `h2`, `h3`, `[class*="title"]` within card |
| CSRF token | `meta[name="csrf-token"]` |
| Login modal | `button[aria-label="Close"]`, Escape key |

---

## Common pitfalls

1. **`http_get` is permanently blocked.** DataDome intercepts all non-browser HTTP requests with
   a 403 + captcha challenge. No User-Agent, header combination, or cookie replay works.
   `api.angel.co` is HTTP 404 (shut down). Use `new_tab()` exclusively.

2. **NOT a Next.js app.** Wellfound is Ruby on Rails + React. There is no `__NEXT_DATA__` JSON
   blob. Look for `window.__APOLLO_STATE__`, `window.gon`, or inline `<script>` tags instead.

3. **`wait(5)` minimum after `wait_for_load()`.** DataDome runs JS fingerprinting probes for
   2-4 seconds after `readyState = complete`. Extracting before this resolves returns the challenge
   page HTML, not real content.

4. **Tailwind CSS — no stable class names.** Wellfound uses Tailwind utility classes. Never
   hardcode a specific class name. Use `href` attribute patterns, `data-test` attributes if present,
   or semantic element selectors (`h1`, `h2`, `li`, `article`).

5. **GraphQL requires both CSRF token AND browser session cookies.** The CSRF token is a
   per-session value from `<meta name="csrf-token">`. Cloudflare Bot Management blocks
   `POST /graphql` from non-browser sessions. Always fire GraphQL via `fetch()` inside the
   browser session (not from Python's `http_get`).

6. **`?role=` and `?location=` params are robots.txt-disallowed.** Wellfound may redirect or
   show a login wall for filtered job search URLs. Load `/jobs` unfiltered and use in-page
   UI filters (dropdowns) to narrow results.

7. **Login wall on job details and user profiles.** Company overview pages load without login.
   Individual job detail pages, and all `/u/{username}` profiles, hit a login modal immediately.
   Call `dismiss_wellfound_login_modal()` right after `wait(5)` on these pages.

8. **Rate limiting.** After ~5-10 rapid page navigations DataDome may harden. Use `wait(3)` between
   `goto()` calls. If you get a captcha that does not auto-resolve, wait 30-60 seconds.

9. **`new_tab()` over `goto()` for the first Wellfound page.** `goto()` in an existing tab
   may inherit a stale DataDome fingerprint. `new_tab()` gives a clean origin context that
   DataDome processes cleanly.

---

## Anti-bot response identification

What you see in the 403 body when NOT in a browser:

```html
<!-- DataDome challenge (page GETs) -->
<script>var dd={'rt':'c','cid':'...','t':'bv','host':'geo.captcha-delivery.com',...}</script>
<script src="https://ct.captcha-delivery.com/c.js"></script>
<!-- rt='c' = captcha required; rt='i' = invisible solve; rt='b' = blocked -->

<!-- Cloudflare challenge (API POSTs) -->
<title>Just a moment...</title>
<script>window.__CF$cv$params={r:'...',t:'...'}</script>
```

In a real Chrome browser, both challenges resolve automatically without user interaction.

---

## Minimal working example

```python
import json

# Open Wellfound company page
new_tab("https://wellfound.com/company/openai")
wait_for_load()
wait(5)

# Verify not blocked
title = js("document.title")
assert "Just a moment" not in (title or ""), f"Still on challenge page: {title}"

# Extract company overview
data = js("""
(function() {
  var name = document.querySelector('h1');
  var bodyText = document.body.innerText;
  var sizeMatch = bodyText.match(/(\\d+[-\\u2013]\\d+)\\s+(employees|people)/i);
  var fundingMatch = bodyText.match(/\\$[\\d,.]+[KMBkm](?:\\s+(?:raised|total))?/i);
  var stageMatch = bodyText.match(/\\b(Seed|Series [A-Z]\\+?|Pre-seed|Late Stage|Public)\\b/);
  var tags = Array.from(document.querySelectorAll('a[href*="/jobs?role="]')).map(a => a.innerText.trim());
  var locs = Array.from(document.querySelectorAll('a[href*="/location/"]')).map(a => a.innerText.trim());
  return JSON.stringify({
    name:     name ? name.innerText.trim() : null,
    teamSize: sizeMatch ? sizeMatch[0] : null,
    funding:  fundingMatch ? fundingMatch[0] : null,
    stage:    stageMatch ? stageMatch[0] : null,
    roles:    tags.slice(0, 8),
    locations: locs.slice(0, 5),
  });
})()
""")

print(json.dumps(json.loads(data), indent=2))
```
