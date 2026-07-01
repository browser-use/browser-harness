# San Diego CISPublic — Legacy Court Index Probate Name Search (scraping)

`https://courtindex.sdcourt.ca.gov/CISPublic/` — the **legacy San Diego Superior Court
Index** (CISPublic). It carries the county case index (incl. probate) back to ~1974. This
skill covers the **name-indexed** search: query by surname, read the result table, filter
to probate + a date window, page through it.

## The one load-bearing fact — Cloudflare, and Camoufox on a residential IP

CISPublic sits behind **Cloudflare**. A plain client (`curl`/`http_get`) and any
datacenter / CI / cloud IP get a **403 / "Just a moment" challenge**. A **warm Camoufox
session on a residential IP** (Camoufox is a stealth Firefox build — install it on your
residential-IP machine) passes the Cloudflare challenge **transparently** — after the
first `/enter` load clears it, each subsequent search runs ~1.2s with no re-challenge.

- **Do NOT use Browser Use cloud / `run_agent_task`** — datacenter egress re-triggers the
  403. **The entire sweep must run inside ONE warm Camoufox session** — the CF clearance
  does NOT hand off to a separate `curl_cffi` / `http_get`; a second client is re-challenged.
- The sibling Odyssey/Tyler Register-of-Actions SPA (`https://odyroa.sdcourt.ca.gov/`) is
  **hard Cloudflare-blocked from every IP** — do not bother with it; CISPublic is the path.
- **The data IS the HTML.** There is **no JSON endpoint** — `/viewname` returns a rendered
  `<table>`. Parse the HTML.
- If Camoufox is unavailable or the IP is non-residential, the run is an **honest block**
  (0 rows) — never a fabricated row, never a bypass.

## URLs

| URL | Method | Role |
|---|---|---|
| `https://courtindex.sdcourt.ca.gov/CISPublic/enter` | GET | Terms / warm-up. Sets the session + Cloudflare cookies (`JSESSIONID`, `__cf_bm`, `_cfuvid`). |
| `https://courtindex.sdcourt.ca.gov/CISPublic/viewname` | POST | Name-search results: a `<table class="data">` of matches. |
| `https://courtindex.sdcourt.ca.gov/CISPublic/casedetailp?casenum=...` | GET | Per-case detail (linked from each result row). |

## Recipe (one warm Camoufox session, residential IP)

The search is **name-indexed** — you drive it by **surname** (a top-N San Diego surname
dictionary) and **filter each result page to your date window + `caseType=P`**. It is NOT
a "dump every filing in a date range" query.

```python
from camoufox.sync_api import Camoufox   # residential-only; unavailable -> honest block

with Camoufox(headless=True) as browser:
    page = browser.new_page()
    # 1) Warm the session: /enter clears the CF challenge + sets JSESSIONID/__cf_bm/_cfuvid.
    page.goto("https://courtindex.sdcourt.ca.gov/CISPublic/enter", wait_until="networkidle")
    body = (page.content() or "").lower()
    if "just a moment" in body or "cf-browser-verification" in body:
        raise SystemExit("Cloudflare challenge on /enter (non-residential IP?) — honest block")

    # 2) Per surname, POST /viewname from the PAGE's own fetch (same-origin, carries the
    #    warm CF/session cookies), walking page=N until the result table / page= link stops.
    for surname in SURNAMES:                       # e.g. ["SMITH", "GARCIA", "JOHNSON", ...]
        for page_no in range(1, 40):               # generous ceiling; stops early
            form = (f"lastname={surname}&firstname=&dateOfBirth="
                    f"&fileDateBegin={YEAR_FROM}&fileDateEnd={YEAR_TO}"
                    f"&caseType=P&site=A&partyType=A&page={page_no}")
            html = page.evaluate(
                """async (a) => {
                    const r = await fetch(a.url, {method:'POST',
                        headers:{'Content-Type':'application/x-www-form-urlencoded'},
                        body:a.form, credentials:'include'});
                    return r.ok ? await r.text() : null;
                }""",
                {"url": "https://courtindex.sdcourt.ca.gov/CISPublic/viewname", "form": form},
            )
            if not html:
                break
            save(html)                             # concatenate pages; parse offline
            low = html.lower()
            if "class=data" not in low or "page=" not in low:
                break                              # last page for this surname
```

`SURNAMES` is a top-N surname dictionary (measured anchors: `SMITH` ≈ 54, `GARCIA` ≈ 44
distinct 2025 probate cases). `YEAR_FROM`/`YEAR_TO` are 4-digit years; the finer date
window is applied by filtering each parsed row's `Date Filed`.

## POST /viewname form fields

| Field | Value / role |
|---|---|
| `lastname` | the surname to search (the name index key). |
| `firstname` | optional given-name narrowing (usually empty for a sweep). |
| `dateOfBirth` | optional; empty for a sweep. |
| `fileDateBegin` / `fileDateEnd` | 4-digit **year** bounds. |
| `caseType` | `P` = Probate. |
| `site` | `A`. |
| `partyType` | `A`. |
| `page` | 1-based page number. |

## Result table — structure + selectors

`/viewname` returns a **50-row** result table. Columns, fixed order:

```
Case Number | Party Name | Opposing Party | Location | Case Type | Date Filed
```

- **The table tag uses an UNQUOTED HTML4 attribute: `<table class=data border="1" ...>`**
  — not `class="data"`. Match it quote-tolerantly, e.g.
  `<table[^>]*\bclass=["']?data["']?[^>]*>`. A strict `class="data"` match misses the live
  page and mislabels it a block.
- A live sweep **concatenates many `/viewname` pages** into one string, so iterate **every**
  `<table class=data>` block (not just the first) and **dedupe by Case Number** across pages
  — a first-table-only parse silently drops everything after page 1.
- Each row links to `/CISPublic/casedetailp?casenum=...` for detail.
- `Date Filed` is `MM/DD/YYYY`; normalize to ISO `YYYY-MM-DD`.

## Probate precision — gate on the Case NUMBER, not the Case Type column

A surname search can cross-return non-probate divisions. Two gates:

1. **Case Type column** must start with "Probate".
2. **The case NUMBER's prefix decides probate-ness** (authoritative). The division code
   sits after the 4-digit year, e.g. `37-2025-PE000101-CTL` → `PE`:

   | Prefix | Meaning | Keep? |
   |---|---|---|
   | `PE` | decedent estate (the ownership-transition trigger) | ✅ |
   | `PG` | guardianship | ✅ |
   | `PC` | conservatorship (aging-out pre-signal) | ✅ |
   | `PT` | trust | ✅ |
   | `MH` | mental health | ✅ |
   | `DW` / `W` / bare-`P####` (e.g. `P164692`) | legacy/microfilm probate | ✅ (decode as LEGACY) |
   | `CU` (civil) / `CR` (criminal) / `FL` (family) / `SC` (small claims) / … | modern non-probate | ❌ DROP even if the Case Type column claims "Probate" |

   Never bucket an unknown modern prefix as legacy; an unrecognized *legacy* shape decodes
   honestly as LEGACY, never guessed as a decedent estate.

## Honest-block signature (off a non-residential IP)

Cloudflare answers a challenge with an interstitial — sometimes a 403, but often an
**HTTP 200 "Just a moment" body** that parses to 0 rows. Treat as a block (never a 0-row
success) when ANY of:

- body contains `just a moment`, `cf-browser-verification`, `attention required! | cloudflare`,
- body contains an **active** challenge token: `__cf_chl`, or `challenges.cloudflare.com`,
- body has **no `<table class=data>` result structure** at all.

**False-positive trap (do NOT treat as a block):** Cloudflare injects a **passive** JS
beacon `/cdn-cgi/challenge-platform/scripts/jsd/main.js` into **every** successfully-served
page, including a genuinely-cleared CISPublic result page. The bare substring
`challenge-platform` is therefore NOT a block signal. A real interstitial carries an
**active** token (`__cf_chl`) AND lacks the result table; a cleared page has the passive
beacon AND a real `<table class=data>`.

## Gotchas

- **One warm session for the whole sweep.** CF clearance is bound to the Camoufox
  session's cookies + fingerprint; a fresh client (or cloud IP) is re-challenged. Do the
  `/enter` warm-up once, then loop all surnames × pages inside the same session.
- **The `class=data` attribute is unquoted** — quote-tolerant matching only.
- **Iterate every result table + dedupe by Case Number** — multi-page bodies are
  concatenated; a first-match parse drops later pages.
- **Gate probate on the case NUMBER prefix**, not the possibly-mislabeled Case Type column.
- **Reap orphaned browsers before launching a Camoufox sweep.** A SIGKILL'd prior sweep
  orphans browser children (a `with` block can't reap after SIGKILL); they accumulate
  until the host hits its per-user process limit (`kern.maxprocperuid`) and can no longer
  fork a login shell — the box goes silently offline. Before a sweep: reap orphaned
  browsers (`ppid==1`) and refuse to start if near the process limit (that refusal is
  itself an honest block, not a failure). Always run the sweep inside a
  descendants-only cleanup context so exit (normal, exception, or Ctrl-C) reaps only the
  children this sweep spawned.
- **Never persist decedent / party names to a shared or public artifact.** The Party Name
  is PII — a probate filing is a name + case number + date, no property. Route names
  operator-only; keep only the public case number + decoded sub-type + filing date on any
  shared surface.
