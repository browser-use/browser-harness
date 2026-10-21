# google-search-console/check — inspect indexing & submit sitemaps (battle-tested 2026-06-29)

Driving `search.google.com/search-console` with browser-harness against the user's logged-in Google account. **No API here** unless service-account/OAuth is set up — this is the browser path. GSC is a heavy Angular SPA: use coordinate clicks + `Input.insertText`, and **read reports via screenshots** (text extraction is sparse).

## Property URL
Everything is scoped by `resource_id`. For a **domain property** it's `sc-domain:<domain>` (e.g. `sc-domain:tryskilly.app`). Deep-link directly:
- Overview: `…/search-console?resource_id=sc-domain:<domain>`
- Sitemaps: `…/search-console/sitemaps?resource_id=sc-domain:<domain>`
- Pages (indexing): `…/search-console/index?resource_id=sc-domain:<domain>`
- Performance: `…/search-console/performance/search-analytics?resource_id=sc-domain:<domain>` (**hyphen**, not `search_analytics` — the underscore form 404s)

Confirm login + property by reading the top-left property name and the left nav (Overview / Performance / URL inspection / Pages / Sitemaps…). If it redirects to a Google login, pause and ask the user.

## The 4 checks (priority order)

### 1. Submit / re-submit the sitemap (highest value after a deploy)
- Go to the Sitemaps page. The "Add a new sitemap" card has an input + **SUBMIT** button.
- **GOTCHA — domain properties require the FULL URL.** Entering a relative path (`sitemap-index.xml`) returns **"Invalid sitemap address"**. Enter `https://<domain>/sitemap-index.xml`.
- **GOTCHA — two inputs on the page.** The top header has an "Inspect any URL" bar AND the card has the sitemap input — both are `<input>`. `document.querySelector('input')` grabs the **wrong** (top) one. Target the sitemap card's input (it sits lower in the main content, ~y 239 at 1080p), then `click` it → `Input.insertText` the full URL → click SUBMIT.
- Success = a green **"Sitemap submitted successfully"** dialog; the submitted-sitemaps table shows the row with Status **Success**, Last read, and **Discovered pages**.
- Re-submitting after adding pages nudges a fresh read (Google also re-reads on its own schedule).

### 2. Pages (indexing) report — the real "is everything indexed?" answer
- Two tiles: **Indexed** (count) and **Not indexed (N reasons)**.
- Scroll to **"Why pages aren't indexed"** for the per-reason table.
- **GOTCHA — data lags ~2 weeks** ("Last update" date at top). Pages deployed today won't show here for a while; the sitemap submit (step 1) is what accelerates discovery.

### 3. URL inspection
- Top "Inspect any URL" bar → type a full URL → Enter. Shows whether it's on Google + why. Click **"Request indexing"** to push a priority page into the queue (rate-limited, ~10–20/day).

### 4. Performance
- Impressions / clicks / avg position / top queries. Early-stage sites show little — that's expected.
- **Read the tables via DOM, not screenshots.** The report tables ARE in the DOM (unlike most GSC reports) and extract cleanly — far cheaper than paging through screenshots:
  ```python
  js("""(() => [...document.querySelectorAll('table tr')]
        .map(tr => [...tr.querySelectorAll('td,th')].map(td => td.innerText.trim()).join(' | '))
        .filter(Boolean).slice(0, 40).join('\\n'))()""")
  ```
  Gives `query | clicks | impressions | CTR | position` rows. The first ~6 rows are Core Web Vitals / HTTPS / Breadcrumbs cards — skip them.
- **GOTCHA — `window.scrollTo()` does nothing.** The report scrolls an inner container, so the queries table never comes into view that way; use the DOM extraction above instead.
- **GOTCHA — the QUERIES/PAGES/COUNTRIES/DEVICES tabs ignore coordinate clicks** (at least at 1080p). If you need the PAGES breakdown, add a filter or use EXPORT rather than burning turns on the tab strip.

## Interpreting "not indexed" reasons
- **"Discovered – currently not indexed"** → Google found the URL (via sitemap/links) but deprioritized crawling it. This is a **domain-authority / crawl-budget** signal, NOT a technical error. Fix: earn backlinks, strengthen internal linking (hub→spoke), Request-Indexing the key pages, and wait. If most pages sit here, **do not mass-generate more pages** — they'll pile up unindexed; raise authority first.
- **"Crawled – currently not indexed"** → crawled but judged low-value/thin/duplicate. Improve content quality/uniqueness.
- **"Page with redirect"** → usually benign (trailing-slash or http→https canonicalization); the redirect target is the indexed URL.
- **"Duplicate without user-selected canonical" / "Alternate page with canonical"** → set/confirm canonical tags.
- **"Not found (404)"** → a referenced URL is broken; find + fix or remove the reference.

## Why no API
GSC has a Search Console API (sitemaps, URL inspection, search analytics) but it needs a **service account added to the property** or an **OAuth client** — neither is set up here (a prior attempt stalled on service-account propagation). Until that's configured, this browser flow is the way. If you do set it up, the `searchconsole.googleapis.com` URL-inspection + `webmasters` sitemaps endpoints replace steps 1–3.
