# Awin (app.awin.com) — Advertiser dashboard scraping

Awin's advertiser dashboard is a Vue/React SPA hosted on `app.awin.com`, with auth on `id.awin.com`. KPI tiles, charts, and tables render asynchronously after the SPA boots, behind a cookie banner that blocks lazy load until dismissed.

## URL patterns

| Page | URL |
|---|---|
| Login | `https://app.awin.com/login` (redirects to `id.awin.com/u/login/identifier?...`) |
| User home (account picker) | `https://ui.awin.com/user` |
| Advertiser home | `https://app.awin.com/en/awin/advertiser/{merchant_id}/home` |
| Publisher Performance report | `https://app.awin.com/en/awin/advertiser/{merchant_id}/reports/publisher-performance` |
| All partnerships | `https://app.awin.com/en/awin/advertiser/{merchant_id}/partnerships/all` |
| Commissions | `https://app.awin.com/en/awin/advertiser/{merchant_id}/commissions` |
| Campaigns (new UI) | `https://app.awin.com/en/awin/advertiser/{merchant_id}/campaigns` |

Merchant IDs are stable integers (5–7 digits) — read them off the URL after picking an account on `ui.awin.com/user`. The same advertiser brand may have separate IDs per region (US / EU / APAC).

## Login flow

Two-step: email → Continue → password → Sign in. Note that after successful login the URL still contains `/login` for a moment (`id.awin.com/u/login/password?...` → `ui.awin.com/user`) — **detect success by visible text ("Your Accounts", "Manage Accounts", "Advertiser Reports"), not by URL.**

```python
async () => {
  // dismiss cookie banner first — it blocks lazy-loaded KPIs
  const ck = [...document.querySelectorAll('button')].find(b => /accept all/i.test(b.textContent||''));
  if (ck) ck.click();

  const email = document.querySelector('input[type="email"], input[name="username"]');
  if (email) { email.focus(); email.value = EMAIL;
    email.dispatchEvent(new Event('input', {bubbles:true}));
    email.dispatchEvent(new Event('change', {bubbles:true}));
  }
  const cont = [...document.querySelectorAll('button')].find(b => /continue/i.test(b.textContent));
  if (cont) cont.click();
  // wait ~3s for password page transition
  const pw = document.querySelector('input[type="password"]');
  if (pw) { pw.focus(); pw.value = PASSWORD;
    pw.dispatchEvent(new Event('input', {bubbles:true}));
    pw.dispatchEvent(new Event('change', {bubbles:true}));
  }
  const submit = [...document.querySelectorAll('button')].find(b => /sign in|log in|submit/i.test(b.textContent));
  if (submit) submit.click();
}
```

## The cookie-banner trap

If the cookie banner ("Cookies and privacy") is still visible, the advertiser home renders **only skeleton placeholders** — gray bars where KPI cards should be. `wait_for_load()` returns immediately because the SPA is "ready," but the actual data fetches are deferred until the banner is dismissed. Symptom: screenshot shows three loading dots and a sidebar full of gray rectangles.

**Always dismiss the banner before waiting for content.** Dismiss runs on every page visit, not just login — Awin re-shows it on some routes.

## Skeleton-load polling pattern

`domcontentloaded` + a fixed `sleep(6)` is not enough. The home page can take 8–15s for KPI tiles to render. Poll for either:

1. Skeleton placeholder count to drop below ~5: `[class*=skeleton],[class*=Skeleton],[class*=placeholder]`
2. Specific KPI text to appear: `Revenue`, `Transactions`, `Clicks`, `Performance`

```js
async () => {
  const skel = document.querySelectorAll('[class*=skeleton],[class*=Skeleton],[class*=placeholder]').length;
  const txt = document.body.innerText || '';
  return { skel, ready: skel < 5 && txt.length > 800 };
}
```

Poll every 1s, max 45s. Also do a slow scroll to bottom + back to top — it triggers IntersectionObserver-driven lazy mounts for sections below the fold.

## Where the real data lives

Awin renders KPIs in styled `<h1>`/`<strong>` blocks, NOT in `<table>` elements. The home page exposes everything in `document.body.innerText` in a predictable order:

```
<Advertiser Name> (<merchant_id>)
Home
Campaigns
...
Revenue
<date> Yesterday
<currency><value>
<delta>%
Transactions
<date> Yesterday
<value>
<delta>%
Clicks
<date> Yesterday
<value>
<delta>%
...
Revenue trend
Last 7 days
<currency><value>
<delta>%
...
Top partners
<date> Yesterday
Chart
Bar chart with 5 bars.
...
<currency><value>​<currency><value>   ← value doubled with U+200B zero-width space between
<currency><value>​<currency><value>
...
<currency>0
<currency><axis>
<currency><axis>
<Partner 1 name>                     ← partner names in same order as bar values
<Partner 2 name>
<Partner 3 name>
<Partner 4 name>
<Partner 5 name>
See publisher performance report
```

**Regex extractors that work** (Python; currency in `$€£`):

```python
# Yesterday tile (revenue/txns/clicks):
re.findall(r"(Revenue|Transactions|Clicks)\s+\w+\s+\d+\s+\d{4}\s+Yesterday\s+([$€£]?[\d,\.]+)\s+(-?[\d\.]+)%", raw)

# 7-day trend:
re.search(r"Revenue trend\s+Last 7 days\s+([$€£][\d,\.]+)\s+(-?[\d\.]+)%", raw)

# Top-5 bar chart values (note zero-width space U+200B between the duplicate):
re.findall(r"([$€£][\d,\.]+)​[$€£][\d,\.]+", raw)
```

The Top-5 partner *names* sit between `End of interactive chart.` and `See publisher performance report` — split that slice by newline, drop axis labels (`$0`, `$400`, `$800`, `End of...`).

## Publisher Performance page

`/reports/publisher-performance` renders an embedded Looker/BI iframe. The default view ships with **no date range applied** — `document.body.innerText` returns essentially just the page chrome ("Take a quick tour", "Need help? Ask Ava", "Date Last Refreshed - ...") plus an empty canvas. To get tabular data you must click into the date selector and the visualization first; even then most data is canvas-rendered and unreachable via DOM.

**Recommended workaround**: skip DOM scraping here. Either
1. Use the full-page screenshot for visual evidence in the report, or
2. Export the report via Awin's CSV download (button: "Export → CSV") — the URL is a signed S3 link, easy to grab via the network panel.

## Partnerships ("All partnerships") page

`/partnerships/all` is the best source for publisher details — it's plain DOM, fully scrapable. Default sort is `Joined: Newest-to-oldest`, ~10 rows per page, ~197 pages for an established program (use the `1 2 3 ⋯ 197` pager).

Each row follows this exact `innerText` block — extractable with one regex:

```
<Publisher Name>
<numeric publisher id>
Status
Partners                    ← or "Pending" or "Left your program"
Website
<domain>
Primary promotional type
<type>                      ← may be empty string!
Primary sector
<sector>
Partners since              ← or "Left on"
<Month DD, YYYY>
```

```python
re.compile(
  r"([A-Za-z][\w\s\.,&\-\(\)']{1,60})\n(\d{4,7})\nStatus\nPartners\n"
  r"Website\n([^\n]+)\n"
  r"Primary promotional type\n([^\n]*)\n"
  r"Primary sector\n([^\n]*)\n"
  r"Partners since\n([A-Z][a-z]{2,8} \d{1,2}, \d{4})"
)
```

**Trap**: `Primary promotional type` can be blank (the line below it is just `\n`). Don't require non-empty — capture as `[^\n]*` not `[^\n]+`. Status can also be `Pending` (visible above `Your partnerships` count) or `Left your program` — those rows have `Left on` instead of `Partners since`.

## Account picker (`ui.awin.com/user`)

After login, users with multiple advertiser accounts land here. The page lists each account with merchant ID. To jump straight to a specific advertiser, skip the picker and navigate directly to `https://app.awin.com/en/awin/advertiser/{merchant_id}/home` — Awin's auth carries across, no click required.

## Network APIs (worth investigating, not yet documented)

The dashboard hits `https://app.awin.com/api/...` and `https://api.awin.com/...` endpoints with bearer tokens stored in `localStorage`. Direct API calls would be 10×+ faster than DOM scraping. Untested but visible XHRs:

- `GET /api/advertiser/{mid}/dashboard/kpi?period=yesterday`
- `GET /api/advertiser/{mid}/publishers?sort=joined_desc&page=1`

Next agent on this domain: drop into DevTools Network tab on a fresh dashboard load, copy the bearer header, and replay. If the bearer is in `localStorage` rather than an HttpOnly cookie, the scraper can grab it via `js("localStorage.getItem('access_token')")` and bulk-fetch.

## Isolated profile pattern (concurrent with MCP browser)

The MCP Playwright server locks `~/Library/Caches/ms-playwright/mcp-chrome-*` exclusively. To run a second scraper concurrently without disturbing the user's active MCP session, launch your own persistent context with a different `user_data_dir`:

```python
from playwright.sync_api import sync_playwright
PROFILE = Path.home() / ".cache" / "awin-isolated-profile"
PROFILE.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE),
        headless=True,
        viewport={"width": 1600, "height": 1000},
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
    )
```

Persistent profile means session cookies survive between runs — login once, scrape many times. After the first successful login, subsequent runs land directly on the dashboard.
