# Impact.com — Reporting & Data Scraping

Tested: May 2026, TCL US program. App at `https://app.impact.com`.

## Auth

Impact uses Google SSO only for `affiliate@celldigital.co`. No password login path.
- Login page: `https://app.impact.com/login` → redirects to Google OAuth
- In live Chrome (browser-harness), click the correct Google account from the account chooser
- Check login success by `document.body.innerText` containing "Dashboard", "Performance", or "TCL US"

## SPA Architecture

Ractive.js SPA with hash-based routing. Key quirks:
- **Never use `goto_url()` to report paths** — causes `chrome-error://` on direct hash-path navigation
- **Navigate from within the loaded SPA** via `js("window.location.href = 'https://...'")` only
- After navigation, wait `time.sleep(3-8)` — no reliable `DOMContentLoaded` event for SPA route changes
- `wait_for_load()` is unreliable for in-SPA navigation; poll for DOM elements instead

## Report URLs

All accessed via JS navigation from a loaded `app.impact.com` page:

```
Performance by Partner: https://app.impact.com/secure/advertiser/reporting/advertiser-report.ihtml?execution=e1s1#handle=att_adv_performance_by_media_pm_only
Performance by Day:     https://app.impact.com/secure/advertiser/reporting/advertiser-report.ihtml?execution=e1s1#handle=att_adv_performance_by_day
Applications:           https://app.impact.com/secure/advertiser/contracts/applications/adv-manage-pending-public-ios-v2-flow.ihtml
```

## Table DOM Structure

Split-partition design (NOT standard `<table>` elements):

```
[class*=partitionFixed]   ← partner names (checkbox + <a> link per div.tr)
[class*=partitionFree]    ← metrics aligned by row index (div.tr > div.td)
```

Extraction pattern (ES5, works in `js()` IIFE):
```javascript
(function(){
  var fixedPart = null, freePart = null, maxF = 0, maxS = 0;
  var parts = document.querySelectorAll("[class*=tablePartition]");
  for (var i = 0; i < parts.length; i++) {
    var rows = parts[i].querySelectorAll("div.tr");
    if (parts[i].className.indexOf("partitionFixed") >= 0 && rows.length > maxF) {
      fixedPart = parts[i]; maxF = rows.length;
    }
    if (parts[i].className.indexOf("partitionFree") >= 0 && rows.length > maxS) {
      freePart = parts[i]; maxS = rows.length;
    }
  }
  var nr = fixedPart.querySelectorAll("div.tr");
  var mr = freePart.querySelectorAll("div.tr");
  var out = [];
  for (var j = 0; j < nr.length; j++) {
    var link = nr[j].querySelector("a");
    var name = link ? link.textContent.trim() : "";
    var tds = mr[j] ? mr[j].querySelectorAll("div.td") : [];
    var cells = [];
    for (var k = 0; k < tds.length; k++) cells.push(tds[k].textContent.trim());
    if (name) out.push({name: name, clicks: cells[0], actions: cells[1], revenue: cells[2]});
  }
  return JSON.stringify(out);
})()
```

Partner names come from `nr[j].querySelector("a").textContent` — the `div.tr` in fixedPart has only a checkbox + link, not metric cells.

## Date Picker

CSS class names are hashed/obfuscated. Find shortcuts and Apply button by exact text match:

```javascript
// Find element by exact textContent
(function(){
  var t = "Last 7 Days"; // exact text to find
  var els = document.querySelectorAll("*");
  for (var i = 0; i < els.length; i++) {
    var el = els[i];
    if (el.children.length === 0 && el.textContent.trim() === t) {
      var r = el.getBoundingClientRect();
      if (r.width > 0 && r.height > 0)
        return JSON.stringify({cx: Math.round(r.left+r.width/2), cy: Math.round(r.top+r.height/2)});
    }
  }
  return "null";
})()
```

Shortcut texts (exact strings): `"Last 7 Days"`, `"Last 14 Days"`, `"This Month"`, `"Last Month"`
Apply button text: `"Apply"`

Flow: click date button `[class*=dateRangeButton]` → click shortcut → click Apply → wait 3s for reload.

## IIFE Requirement

All `js()` calls that use `var` at top level will fail with "Identifier already declared" if called twice.
Always wrap in `(function(){...})()` IIFE to avoid var hoisting conflicts.

## Traps

- **Calendar DOM overlap**: When date picker is open, its calendar `<table>` is in the DOM alongside the report table. Close picker with `press_key("Escape")` before extracting table data.
- **`var` at top level in js()**: Causes identifier collision on second call. Always use IIFE.
- **Selector `[class*=dateShortcut]`**: Does NOT work — class names are hashed. Use text-match approach.
- **Direct `goto_url()` to report path**: Returns `chrome-error://` because SPA isn't loaded. Navigate via `js("window.location.href = '...'")`  from within the app.
- **`goto_url()` to the root app.impact.com**: Works fine for initial load.
- **freePart row index alignment**: Use the same index `j` in both `nr[j]` and `mr[j]` — the two partitions are row-aligned, not DOM-adjacent.
