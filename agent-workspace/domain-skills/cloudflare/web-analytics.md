# Cloudflare — Web Analytics (read-only)

Field-tested against dash.cloudflare.com on 2026-10-01, logged in as an account member.

## Routes and URL filters

- `https://dash.cloudflare.com/<accountId>/web-analytics/sites`: the sites list. Each "Manage site" link ends in
  the site tag (`/web-analytics/edit/<siteTag>`).
- `https://dash.cloudflare.com/<accountId>/web-analytics/overview/visits?siteTag~in=<siteTag>&time-window=10080`:
  visits for the last 7 days (`time-window` is in minutes), with breakdowns by referer, path, host, country, browser,
  OS and device.

Filters go straight into the query string, so there is no need to click the filter UI:

- `host=<hostname>`: only one hostname of a zone-wide site
- `country~neq=<ISO2>`: exclude a country (e.g. your own team's)
- general shape: `key=value` for "equals", `key~neq=value` for "does not equal", `key~in=value` for "is in"

Guessed names such as `requestHost~in=` or `countryName~neq=` are silently ignored: check the filter chips under
"Add filter" to confirm a filter took.

## Reading

`(document.querySelector('main') or body).innerText` gives "Total visits", then "Visits by source" with "Referers",
"Paths", "Hosts", "Browsers" lists as label / count pairs. Each list row is an `li[role=button]`; a coordinate
click on the row reveals its "Filter" and "Exclude" buttons (the URL filters above are simpler).

## Traps

- A zone-wide site in "Automatic setup" covers every proxied hostname of the zone. A hostname served elsewhere (a
  DNS-only record, e.g. a site on Vercel) gets no beacon and no data.
- "Enable, excluding visitor data in the EU" injects no beacon for EU visitors: testing from an EU location shows no
  `cloudflareinsights` script, and EU visits never appear in the numbers. That is the setting, not a broken install.
- Stay away from "Manage site": its radio buttons change the injection setting for the whole zone.
