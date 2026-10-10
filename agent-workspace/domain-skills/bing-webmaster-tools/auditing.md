# Bing Webmaster Tools — SEO audits and authenticated APIs

Bing Webmaster Tools (BWT) is a client-rendered app at `https://www.bing.com/webmasters/`. When the user is already signed in, attach browser-harness to that browser and prefer the page's same-origin JSON APIs over scraping tables from the DOM.

## Connect to an authorized Edge profile

Recent Edge builds require the user to enable **Allow remote debugging for this browser instance** at:

`edge://inspect/#remote-debugging`

When the page reports `Server running at: 127.0.0.1:9222`, connect to that existing profile:

```powershell
$env:BU_NAME = "bing-webmaster-tools"
$env:BU_CDP_URL = "http://127.0.0.1:9222"
@'
ensure_real_tab()
print(page_info())
'@ | browser-harness
```

Do not open `chrome://inspect` through the Windows protocol handler and do not repeatedly run setup. If `/json/version` returns 404 after authorization, browser-harness can discover the Edge profile's `DevToolsActivePort` WebSocket automatically.

## Stable page routes

All routes take a URL-encoded `siteUrl` query parameter. Preserve the property's exact scheme and trailing slash.

- Recommendations: `https://www.bing.com/webmasters/seoreports?siteUrl=<encoded-property>`
- Site Scan: `https://www.bing.com/webmasters/sitescan?siteUrl=<encoded-property>`
- Sitemaps: `https://www.bing.com/webmasters/sitemaps?siteUrl=<encoded-property>`
- URL submission: `https://www.bing.com/webmasters/submiturl?siteUrl=<encoded-property>`

Open a new tab for the first navigation so the user's active tab is not clobbered.

## Prefer same-origin API reads

The SPA already carries the required cookies and anti-CSRF state. Run `fetch()` inside the BWT tab with `js(...)`; never copy cookies or tokens out of the browser.

Verified endpoints (July 2026):

- `/webmasters/api/reports/seo/overview?siteurl=<encoded-property>` — SEO rule totals, severities, and affected-page counts.
- `/webmasters/api/indexnow/detectsource?siteurl=<encoded-property>` — whether Bing detects IndexNow (`isAlreadyUsingIndexNow`).
- `/webmasters/api/sitescan/overview?siteurl=<encoded-property>` — scan sessions and status.
- `/webmasters/api/sitescan/remainingquota?siteurl=<encoded-property>` — remaining Site Scan quota.
- `/webmasters/api/sitescan/ignoreurlparams?siteurl=<encoded-property>` — configured URL parameter exclusions.
- `/webmasters/api/submiturls/listcount` — URL submission quota/count metadata loaded by the SPA.
- `/webmasters/api/sitemaps/overview?siteurl=<encoded-property>` — sitemap totals.
- `/webmasters/api/sitemaps/list?siteurl=<encoded-property>&pageSize=25&sortBy=UrlCount&sortingOrder=Desc&pageNum=1` — known sitemaps and current crawl status.
- `/webmasters/api/globalelements/settings` — account-level communication preferences.
- `/webmasters/api/globalelements/messages` — notification-center messages and their site association.

Example read:

```powershell
@'
site = "https://example.com/"
script = """
Promise.all([
  '/webmasters/api/reports/seo/overview?siteurl=' + encodeURIComponent(%s),
  '/webmasters/api/indexnow/detectsource?siteurl=' + encodeURIComponent(%s),
  '/webmasters/api/sitescan/overview?siteurl=' + encodeURIComponent(%s)
].map(url => fetch(url, {credentials: 'include'}).then(async response => ({
  url,
  status: response.status,
  body: await response.json()
})))).then(JSON.stringify)
""" % (repr(site), repr(site), repr(site))
print(js(script))
'@ | browser-harness
```

If a new endpoint is needed, inspect the page's resource entries instead of guessing:

```python
print(js("JSON.stringify(performance.getEntriesByType('resource').map(e => e.name).filter(u => u.includes('/webmasters/api/')))"))
```

## Site Scan behavior

`sitescan/overview` returns records with fields such as `SessionId`, `ScanUrl`, `ScanName`, `LastScannedUtc`, `PagesScanned`, `Errors`, `Warnings`, and `ScanStatus`. A newly accepted scan can remain `NotStarted` with `PagesScanned: 0` while queued; do not report it as completed. Poll the overview endpoint later.

The account or property can restrict concurrent scans and quota. Capture the SPA's actual request to `/webmasters/api/sitescan/start?...` before automating scan creation; do not invent its method or body.

## IndexNow verification

After publishing the key file and submitting URLs, verify BWT recognition with `indexnow/detectsource`. A successful response looks like:

```json
{"isAlreadyUsingIndexNow": true}
```

The public IndexNow aggregator may temporarily return `403 SiteVerificationNotCompleted` immediately after a new key file appears. Check that the key file is public, then submit to Bing's endpoint (`https://www.bing.com/indexnow`). Treat only 200/202 responses as accepted, and re-read `detectsource`; never convert a 403 into a success claim.

## Audit discipline and traps

- BWT SEO warnings can lag the live page. Re-fetch affected URLs and compare title, H1, canonical, description, indexability, and static body before changing code.
- The Chinese text length can be adequate even when BWT applies a Latin-character description heuristic. Do not pad every description mechanically.
- A noindex page can still appear in an old H1 warning. Verify the current `X-Robots-Tag` or robots meta and sitemap membership first.
- Discovered sitemap aliases can remain listed after the live aliases become 301 redirects. Count unique URLs from the canonical live sitemap, not the sum of BWT's historical rows.
- Backlink warnings are off-page signals; do not fabricate links or mark them fixed by code.
- Separate `generated`, `verified`, `deployed`, and `submitted`. A queued Site Scan or accepted code commit is not evidence of live deployment.
- Keep account email, cookies, request headers, and property verification tokens out of logs and domain skills.
