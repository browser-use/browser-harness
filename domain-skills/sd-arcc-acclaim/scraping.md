# San Diego ARCC AcclaimWeb — Recorder Doc-Type Index (scraping)

`https://arcc-acclaim.sdcounty.ca.gov` — the San Diego County Assessor/Recorder/County
Clerk (ARCC) **AcclaimWeb** official-records portal. This skill covers the FREE
`SearchTypeDocType` recorder-event index: search recorded documents by document type +
recording-date window, read the result grid, page through it, open a row detail.

## The one load-bearing fact — this site is Akamai-walled

AcclaimWeb sits behind an **AkamaiGHost WAF**. It **403s datacenter / CI / cloud IPs**
(and even plain `curl`/`http_get` from a residential IP) with an "Access Denied" edge
page. **Do NOT use Browser Use cloud / `run_agent_task`** — cloud egress is a datacenter
IP and gets denied, and it burns credits. The only path that loads is a **real browser
on a residential IP** driven through the harness (e.g. `browser-harness <<'PY' ...` on a
residential-IP machine, or a Camoufox session). A stealth residential browser (Camoufox,
or the harness-attached Chrome) is what passes; the WAF keys on IP + browser fingerprint.

- If the real residential browser is ALSO denied, that is an **honest block**, not
  something to defeat. Record the exact Akamai reference and stop. Never bypass a WAF.
- There is **no private JSON/XHR endpoint** (verified — the search + grid are
  server-rendered ASP.NET MVC; direct HTTP is Akamai-denied). DOM/grid parsing inside
  the residential browser is the path. If a future run finds a grid-data XHR in the
  Network tab (some AcclaimWeb deployments POST to a `…/Search/…` data endpoint), add it
  here — it is ~10× faster than DOM scraping.

## URLs

| URL | Role |
|---|---|
| `https://arcc-acclaim.sdcounty.ca.gov/AcclaimWeb/` | Landing / **disclaimer gate**. Accept the agree/disclaimer once to set the Akamai + ASP.NET session cookies. |
| `https://arcc-acclaim.sdcounty.ca.gov/search/SearchTypeDocType` | The free **doc-type search** page (form + result grid). |

## Recipe (residential browser, one doc type per query)

```python
# On a residential-IP machine, driving its own real Chrome via the harness.
new_tab("https://arcc-acclaim.sdcounty.ca.gov/AcclaimWeb/")   # landing / disclaimer
wait_for_load()
# Accept the agree/disclaimer gate ONCE — this sets the Akamai + ASP.NET session
# cookies the search needs. (Locate the accept control by its visible text / role,
# never by pixel — screenshot() first to see it.)

new_tab("https://arcc-acclaim.sdcounty.ca.gov/search/SearchTypeDocType")
wait_for_load()
# 1) open the doc-type picker, tick the checkbox whose value == <arcc_value> (§ below)
# 2) fill RecordDateFrom / RecordDateTo (m/d/Y). Rolling window, newest-first.
# 3) submit (#btnSearch).
wait_for_load()
# 4) SAVE the rendered grid HTML — it IS the data; parse it offline.
html = js("document.documentElement.outerHTML")
open("/tmp/arcc_<doctype>_<page>.html", "w").write(html)
print(page_info())
```

**Rate-limit: ≥ 20s + jitter between doc types / pages.** Rapid looping trips Akamai.
Never run an all-types loop from production — query only the P0 values you need.

## Form fields (the search POST)

| Field | Role |
|---|---|
| `DocTypes` | the selected doc-type **`value`** (the checkbox value, e.g. `536` — see the map). One doc type per request. |
| `DocTypesDisplay-input` / `DocTypesDisplay` | the type-ahead display box + its hidden mirror. |
| `DateRangeList` | preset date-range selector (e.g. "custom"). |
| `RecordDateFrom` | recording-date window start, **m/d/Y**. |
| `RecordDateTo` | recording-date window end, **m/d/Y**. |
| `btnSearch` | submit. |

**Doc-type checkboxes** in the type picker each carry:
- `name="DocTypeInfoCheckBox"`
- a **title** like `NOTICE OF DEFAULT (025)` — the human name + its ARCC code in parens.
- an internal checkbox **`value`** like `536` — this is what goes into `DocTypes` and is
  the stable key to select the type. **Locate the checkbox by its `value` / label /
  role, never by pixel.**

### 90-day window mechanic

`RecordDateFrom = today − 90 days`, `RecordDateTo = today`, newest-first. m/d/Y format.
If ARCC clamps `RecordDateTo` to the prior business day, persist the portal-visible max
date rather than assuming today.

## P0 doc-type value map (the high-signal subset)

Select a type by putting its **value** into `DocTypes`. `code` is the ARCC document-type
code that prints in parens after the name.

| Doc type | Code | `DocTypes` value |
|---|---|---|
| NOTICE OF DEFAULT | 025 | `536` |
| NOTICE OF TRUSTEES SALE | 243 | `753` |
| AFFIDAVIT OF DEATH | 482 | `1001` |
| NOTICE OF STATE TAX LIEN | 441 | `948` |
| STATE TAX LIEN | 030 | `541` |
| TRUSTEES DEED | 028 | `539` |
| FEDERAL TAX LIEN | 029 | `540` |
| ABSTRACT OF JUDGMENT | 010 | `522` |
| NOTICE OF PENDING ACTION (lis pendens) | 026 | `537` |
| MECHANICS LIEN | 022 | `534` |
| NOTICE OF ASSESSMENT LIEN - HOMEOWNERS | 251 | `761` |

The portal exposes ~505 doc types; the full inventory + all 59 real-estate-relevant
build rows live in the deal-os ARCC guide. **The `value` numbers are the portal's, not
ours** — if ARCC re-numbers the dropdown, re-extract the `DocTypeInfoCheckBox` option set
(`name` + title-code + `value`) from a live page before trusting a hard-coded value. A
"rows fetched, zero kept" result on a non-blocked run is the canary that a value or the
grid skin drifted.

## Result grid — columns + selectors

Fixed column order:

```
Cart | Row | # Pages | Grantor | Grantee | Document # | Record Date | Doc Type | Book Type | Map # | Map Bk/Pg
```

Parse by **reading the header row to map column-label → index**, then read each body
row's cells in that order — **locate by header label / semantic cell, never by pixel**.
A minor grid-skin change then can't silently drop rows. Column-label hints to match:
`record date`, `document type`, `document number` / `instrument`, `grantor`, `grantee`,
`book/page`, `legal` / `parcel` / `apn`.

**APN note (AB 1785, eff. 2024-12-09):** the online APN/parcel *search* index was removed
from CA recorder portals (SD included) — APN search is in-person-kiosk only. An APN may
still **print** in a row's Legal cell; extract it with
`\b\d{3}[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}\b` when present, else key the row event-only on
its public Document Number. Never guess an APN.

## Detail page

Click into a row (free when accessible) to get: book/page, secondary number, document
number, page count, document type, grantor, grantee, and the valuable one — **`Reference
To`** (the prior deed-of-trust / related instrument a NOD/NOTS points back to). Capture
`Reference To` only when the detail is free and you need it.

## Pagination

Standard AcclaimWeb server-rendered grid. For a short recent window on one doc type,
volume is usually one page. When a type does page:
- Read the grid's page controls (next-page link / page-number control) — **by semantic
  control, not pixel** — and collect each page's grid HTML.
- Concatenate page HTMLs and parse all `<tr>` rows across the concatenation.
- Dedupe on `document_number + doc_type_code` so a boundary-repeated row collapses to one.
- Keep the ≥20s + jitter throttle between page fetches too.

## Honest states — no_rows vs blocked

- **kept rows** — a real result grid with rows.
- **`no_rows`** — a real, reachable grid that simply had no recording for that doc type in
  the window. This is EXPECTED for many low-volume types in a short window; it is **not a
  failure**.
- **`blocked`** — an Akamai/WAF "Access Denied" edge page, a missing doc-type option, a
  malformed grid, or missing required fields (document_number / record_date). Record the
  exact Akamai reference, **do not retry-storm**, back off.

## Akamai "Access Denied" signature

A blocked request returns the AkamaiGHost edge page, not the AcclaimWeb app: the title/body
reads **"Access Denied"** / "You don't have permission to access ... on this server", and
the page carries an Akamai **Reference #** (e.g. `Reference #18.xxxxxxxx.xxxxxxxxxx.xxxxxxxx`).
Seeing this = honest block for that query. It is NOT a 0-row success — never treat a denied
page as `no_rows`.

## Gotchas

- **Datacenter/cloud IP = guaranteed denial.** The whole point of running on the
  residential box is the IP. Browser Use cloud / `run_agent_task` egress is datacenter —
  it will be denied. Coordinate-click + CDP on the residential real browser is the path.
- **Accept the disclaimer gate first**, or the search page won't have the Akamai +
  ASP.NET session cookies and will bounce.
- **One `DocTypes` value per request.** The picker allows multi-select, but a many-type
  loop trips the WAF and blurs provenance — prove the shared grid mechanics once, then
  query only the values you need.
- **The data IS the HTML.** Save the rendered grid HTML and parse offline; there is no
  JSON endpoint to shortcut to (until/unless a Network-tab XHR is found and added here).
- **Never persist recorder party names to a shared/public artifact.** Grantor/grantee are
  party PII — route them operator-only, keep only the public Document Number + doc type +
  record date (+ printed APN) on any shared surface.

## Related public endpoint — free County owner→parcel resolver (no WAF)

A recorder row names a party but (post-AB-1785) rarely a searchable APN. The San Diego
County assessor's own public ArcGIS layer resolves an **owner name → parcel(s)** for free,
no auth, no WAF — a different host from AcclaimWeb:

```
https://gis-public.sandiegocounty.gov/arcgis/rest/services/WorkflowLayers/FeatureServer/0/query
  ?where=OWN_NAME1 LIKE '<SURNAME STEM>%'
  &outFields=APN,OWN_NAME1,OWN_ADDR1,SITUS_STREET,SITUS_COMMUNITY,OWNEROCC,ASR_TOTAL
  &returnGeometry=false&f=json
```

Use it to turn a recorder party name into an APN. A common name returns many parcels —
accept a match only when it is unique (or corroborated by the doc's own printed APN /
address); never pin a name→APN on a common-name guess.
