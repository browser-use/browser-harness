# Chicago — building permits & inspection records

Two sources for "what permits exist at address X":

## 1. Open-data Socrata API (fastest — try first, no browser)

Dataset `ydr8-5enu` (Building Permits) on `data.cityofchicago.org`. No auth. Updated daily (verify with `$select=max(issue_date)`).

```python
import json, urllib.parse
q = urllib.parse.urlencode({
    "$where": "street_number='853' AND street_direction='W' AND upper(street_name) like 'BLACKHAWK%'",
    "$order": "issue_date DESC", "$limit": "100",
    "$select": "permit_,permit_type,issue_date,work_description",
})
rows = json.loads(http_get(f"https://data.cityofchicago.org/resource/ydr8-5enu.json?{q}"))
```

- Address is split into `street_number` / `street_direction` / `street_name` (name WITHOUT the `ST`/`AVE` suffix — use `like 'BLACKHAWK%'`).
- **Corner buildings file under multiple addresses.** Read the work descriptions — they often name the alternate frontage (e.g. `OIA '1450 N DAYTON ST'`). Query that address too.
- Occupancy group changes (e.g. R-2 → R-1 hotel conversion) appear in `work_description` of `PERMIT - RENOVATION/ALTERATION` rows as "(OCC GROUPS ...)" / "CHANGE OF USE/OCCUPANCY".

## 2. Official portal `webapps1.chicago.gov/buildingrecords` (issued permits + inspections + code violations)

Shows more than the dataset: inspection history with pass/fail, violation details, building attributes. Session-gated behind a user-agreement page, but the whole flow works as fetch() POSTs from page context — no UI clicking needed after the agreement.

```python
new_tab("https://webapps1.chicago.gov/buildingrecords/home")
wait_for_load()
# 1. accept agreement (radio whose label says "I accept", then button)
js("""(()=>{const r=[...document.querySelectorAll('input[type=radio]')].find(r=>(r.parentElement.textContent||'').toLowerCase().includes('i accept'));r.click();document.querySelector('#submit').click();})()""")
```

Then two chained POSTs (both need the page's `_csrf` hidden input and session cookie, so run via `fetch` in page JS):

1. `POST /buildingrecords/validateaddress` with `fullAddress=853 W BLACKHAWK ST` → returns an intermediate page whose form has the address parsed into `streetNumber/streetDirection/streetName/streetType`.
2. `POST /buildingrecords/doSearch` with those four fields + `fullAddress` + `_csrf` → full results page.

Parse the result with `DOMParser`; the data lives in four tables by id:
`resultstable_attributes`, `resultstable_permits`, `resultstable_inspections`, `resultstable_violations`.

### Traps

- **`form.submit()` is shadowed** — the submit button has `id="submit"`, so `form.submit` is the button element, not the method. Clicking the button via JS or coordinates also silently fails to navigate (typeahead validation). The fetch() chain above is the reliable path.
- The agreement page sets a session cookie; fetch() calls reuse it automatically since you're on the same origin.
- `resultstable_attributes` can describe a **demolished prior building** at the address (old BLDG ID, wrong story count) — don't read it as the current structure. Cross-check against the new-construction permit description.
- Issued permits only. Pending applications live in a separate "Building Permit Application Status" lookup (needs an application number).
