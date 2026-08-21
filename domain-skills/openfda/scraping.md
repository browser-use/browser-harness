# OpenFDA — Scraping & Data Extraction

`https://api.fda.gov` — FDA open data API covering drug adverse events, drug labels, recalls, device events, and more. **Never use the browser for OpenFDA.** Everything is reachable via `http_get`. No auth required for basic use (up to 500 results/call, 40 req/min); free API key lifts limit to 1,000 results/call and 240 req/min.

## Do this first

**Use `http_get` directly against the JSON REST API — one call returns structured JSON with full pagination metadata.**

```python
import json
from helpers import http_get

# Drug adverse events (20M+ records)
r = json.loads(http_get("https://api.fda.gov/drug/event.json?limit=5"))
total = r['meta']['results']['total']   # 20,006,989
events = r['results']                   # list of report dicts
```

All endpoints return the same envelope:

```python
{
    "meta": {
        "results": {"skip": 0, "limit": 5, "total": 20006989},
        "last_updated": "2026-01-27"
    },
    "results": [...]
}
```

## URL structure

```
https://api.fda.gov/{type}/{dataset}.json?search=&count=&limit=&skip=&sort=&api_key=
```

| Segment | Examples |
|---------|---------|
| `type` | `drug`, `food`, `device`, `other`, `tobacco` |
| `dataset` | `event`, `label`, `ndc`, `drugsfda`, `enforcement`, `recall`, `510k`, `pma`, `registrationlisting` |

### All confirmed live endpoints (2026-04-18)

| Endpoint | Total records |
|----------|--------------|
| `drug/event` | 20,006,989 |
| `drug/label` | 257,050 |
| `drug/ndc` | 134,294 |
| `drug/drugsfda` | 29,009 |
| `food/enforcement` | 28,759 |
| `food/event` | 148,459 |
| `device/event` | 24,443,693 |
| `device/recall` | 57,846 |
| `device/enforcement` | 38,612 |
| `device/510k` | 174,612 |
| `device/pma` | 56,116 |
| `device/registrationlisting` | 322,943 |
| `other/historicaldocument` | 8,858 |
| `tobacco/problem` | 1,337 |

## Common workflows

### Drug adverse events

```python
import json
from helpers import http_get

# Fetch 5 recent adverse event reports
r = json.loads(http_get("https://api.fda.gov/drug/event.json?limit=5"))
for ev in r['results']:
    report_id  = ev['safetyreportid']              # '5801206-7'
    received   = ev['receivedate']                 # '20240101' (YYYYMMDD string)
    serious    = ev.get('serious')                 # '1' = serious, '2' = not serious
    patient    = ev['patient']
    age        = patient.get('patientonsetage')    # '26' (years, as string)
    sex        = patient.get('patientsex')         # '1'=male, '2'=female, '0'=unknown
    reactions  = [rx['reactionmeddrapt'] for rx in patient.get('reaction', [])]
    drugs      = [d['medicinalproduct'] for d in patient.get('drug', [])]
    print(report_id, received, reactions[:2], drugs[:2])
# 5801206-7 20240101 ['DRUG ADMINISTRATION ERROR', 'OVERDOSE'] ['DURAGESIC-100']
```

### Search adverse events by reaction

```python
import json
from helpers import http_get

r = json.loads(http_get(
    'https://api.fda.gov/drug/event.json'
    '?search=patient.reaction.reactionmeddrapt:"headache"'
    '&limit=5'
))
print(r['meta']['results']['total'])   # 611,037
for ev in r['results']:
    drugs = [d['medicinalproduct'] for d in ev['patient'].get('drug', [])]
    reactions = [rx['reactionmeddrapt'] for rx in ev['patient'].get('reaction', [])]
    print(drugs[:2], "->", reactions[:3])
```

### Search with AND / date range

```python
import json
from helpers import http_get

# AND two search terms
r = json.loads(http_get(
    'https://api.fda.gov/drug/event.json'
    '?search=patient.reaction.reactionmeddrapt:"nausea"'
    '+AND+patient.drug.medicinalproduct:"aspirin"'
    '&limit=5'
))
print(r['meta']['results']['total'])   # 31,055

# Date range: receivedate field is YYYYMMDD, range syntax [X+TO+Y]
r = json.loads(http_get(
    "https://api.fda.gov/drug/event.json"
    "?search=receivedate:[20240101+TO+20240131]"
    "&limit=5"
))
print(r['meta']['results']['total'])   # 106,399 in Jan 2024
for ev in r['results']:
    print(ev['receivedate'])           # '20240101'
```

### Drug labels (FDA-approved prescribing information)

```python
import json
from helpers import http_get

r = json.loads(http_get(
    'https://api.fda.gov/drug/label.json'
    '?search=openfda.brand_name:"aspirin"'
    '&limit=3'
))
print(r['meta']['results']['total'])   # 441

label = r['results'][0]
openfda = label.get('openfda', {})
print(openfda.get('brand_name'))       # ['Low Dose Aspirin']
print(openfda.get('generic_name'))     # ['ASPIRIN']
print(openfda.get('route'))            # ['ORAL']
print(openfda.get('rxcui'))            # ['1191']
print(openfda.get('product_ndc'))      # ['69536-014']
print(openfda.get('application_number'))  # ['NDA019952']
print(openfda.get('manufacturer_name'))   # ['Bayer HealthCare LLC']

# Text sections — all are lists of strings; take [0] for the full text block
print(label.get('purpose', [''])[0][:100])
print(label.get('warnings', [''])[0][:100])
print(label.get('dosage_and_administration', [''])[0][:100])
print(label.get('indications_and_usage', [''])[0][:100])
# Note: 'adverse_reactions' is absent on many OTC labels; always use .get()
```

Label text fields (not always present — use `.get(field, [''])[0]`):

| Field | Description |
|-------|-------------|
| `purpose` | Drug purpose/use |
| `warnings` | Warnings text |
| `dosage_and_administration` | Dosing instructions |
| `indications_and_usage` | What it treats |
| `adverse_reactions` | Known adverse reactions |
| `do_not_use` | Contraindications |
| `active_ingredient` | Active ingredient list |
| `inactive_ingredient` | Inactive ingredients |
| `keep_out_of_reach_of_children` | Storage warning |
| `stop_use` | When to stop |
| `ask_doctor` | When to consult physician |

### Drug NDC (National Drug Code) directory

```python
import json
from helpers import http_get

r = json.loads(http_get(
    'https://api.fda.gov/drug/ndc.json'
    '?search=brand_name:"advil"'
    '&limit=5'
))
ndc = r['results'][0]
print(ndc['brand_name'])        # 'Advil PM'
print(ndc['generic_name'])      # 'Ibuprofen and Diphenhydramine citrate'
print(ndc['product_ndc'])       # '66715-9733'
print(ndc['dosage_form'])       # 'TABLET, COATED'
print(ndc['route'])             # ['ORAL']
print(ndc['labeler_name'])      # 'Lil\' Drug Store Products, Inc.'
```

### Drug approvals (drugsfda — ANDA/NDA applications)

```python
import json
from helpers import http_get

r = json.loads(http_get(
    'https://api.fda.gov/drug/drugsfda.json'
    '?search=openfda.brand_name:"tylenol"'
    '&limit=3'
))
print(r['meta']['results']['total'])   # 3

app = r['results'][0]
print(app['application_number'])       # 'ANDA211544'  (ANDA=generic, NDA=brand)
print(app['sponsor_name'])             # 'GRANULES'
print(app['openfda']['brand_name'])    # list of brand names
print(app['openfda']['generic_name'])  # ['ACETAMINOPHEN', 'PAIN RELIEF']

# Submission history
for sub in app['submissions'][:3]:
    print(sub['submission_type'])          # 'SUPPL', 'ORIG'
    print(sub['submission_status'])        # 'AP' = approved, 'TA' = tentatively approved
    print(sub['submission_status_date'])   # '20240118' (YYYYMMDD)
```

### Food recalls

```python
import json
from helpers import http_get

# Most recent recalls
r = json.loads(http_get(
    "https://api.fda.gov/food/enforcement.json"
    "?limit=5&sort=report_date:desc"
))
print(r['meta']['results']['total'])   # 28,759

recall = r['results'][0]
print(recall['product_description'])   # 'Prickly Pear Jelly. 9 oz (268 g)...'
print(recall['reason_for_recall'])     # 'Undeclared milk.'
print(recall['classification'])        # 'Class II'
print(recall['status'])               # 'Ongoing' | 'Terminated'
print(recall['report_date'])           # '20260408' (YYYYMMDD)
print(recall['recall_initiation_date'])
print(recall['recalling_firm'])        # 'The Maros Group, LLC'
print(recall['city'], recall['state']) # 'Scottsdale', 'AZ'
print(recall['country'])               # 'United States'
print(recall['voluntary_mandated'])    # 'Voluntary: Firm initiated'
print(recall['distribution_pattern'])
print(recall['product_quantity'])

# Search by reason
r = json.loads(http_get(
    'https://api.fda.gov/food/enforcement.json'
    '?search=reason_for_recall:"allergen"'
    '&limit=5'
))
print(r['meta']['results']['total'])   # 1,722 allergen recalls
```

Recall classification meanings:
- `Class I` — reasonable probability of serious adverse health consequences or death
- `Class II` — may cause adverse health consequences (temporary/reversible)
- `Class III` — not likely to cause adverse health consequences

### Food adverse events (CFSAN CAERS)

```python
import json
from helpers import http_get

r = json.loads(http_get("https://api.fda.gov/food/event.json?limit=5"))
fev = r['results'][0]
print(fev['date_created'])             # '20230717' (YYYYMMDD)

# Products are a list of dicts
for prod in fev['products']:
    print(prod.get('name_brand'))       # 'KROGER FUN DAYS SUNDAES'
    print(prod.get('industry_name'))    # 'Ice Cream Prod'

# Reactions and outcomes are lists of STRINGS (not dicts)
print(fev['reactions'])    # ['Vomiting']
print(fev['outcomes'])     # ['Disability']

consumer = fev.get('consumer', {})
print(consumer.get('age'), consumer.get('age_unit'))
print(consumer.get('gender'))
```

### Device recalls

```python
import json
from helpers import http_get

r = json.loads(http_get(
    "https://api.fda.gov/device/recall.json"
    "?limit=5&sort=event_date_terminated:desc"
))
dr = r['results'][0]
print(dr['product_description'])    # 'Zoll AED Plus Defibrillator'
print(dr['reason_for_recall'])      # 'Device fails to discharge...'
print(dr['recalling_firm'])
print(dr['event_date_initiated'])   # '2024-01-15' (ISO date, not YYYYMMDD)
print(dr['event_date_terminated'])  # '2026-04-09'
print(dr['recall_status'])          # 'Terminated' | 'Ongoing'
print(dr['openfda'].get('device_class'))   # '3' (I=lowest, III=highest risk)
print(dr['distribution_pattern'])
print(dr['root_cause_description'])
```

### Device adverse events (MAUDE database)

```python
import json
from helpers import http_get

r = json.loads(http_get("https://api.fda.gov/device/event.json?limit=3"))
ev = r['results'][0]
print(ev['event_type'])       # 'Injury' | 'Malfunction' | 'Death' | 'Other'
print(ev['date_received'])    # '19920310' (YYYYMMDD)
print(ev['mdr_report_key'])

# Device details
device = ev['device'][0]
print(device['brand_name'])
print(device['generic_name'])      # 'MANUAL HOSPITAL BED'
print(device['manufacturer_d_name'])

# Patient outcomes
patient = ev['patient'][0]
print(patient['patient_sequence_number'])
print(patient['sequence_number_outcome'])  # ['Required Intervention']

# Narrative text
for txt in ev.get('mdr_text', []):
    if txt.get('text_type_code') == 'D':   # D=event description
        print(txt.get('text', '')[:200])
```

### Device 510(k) clearances

```python
import json
from helpers import http_get

r = json.loads(http_get("https://api.fda.gov/device/510k.json?limit=3"))
k = r['results'][0]
print(k['k_number'])               # 'K251300'
print(k['applicant'])              # 'Dentsply Sirona, Inc.'
print(k['device_name'])            # 'Plastic Surgical Kits'
print(k['decision_date'])          # '2025-07-22'
print(k['decision_description'])   # 'Substantially Equivalent'
print(k['decision_code'])          # 'SESE'
print(k['advisory_committee'])     # 'DE'
print(k['advisory_committee_description'])  # 'Dental'
print(k['product_code'])
print(k['clearance_type'])         # 'Traditional'
print(k['third_party_flag'])       # 'N'
```

### Count/aggregation queries

Count returns `{term, count}` pairs (or `{time, count}` for date fields), sorted by count descending. No `results` envelope — just the list. Useful for finding top values without iterating all records.

```python
import json
from helpers import http_get

# Top 10 most-reported adverse reactions across all drugs
r = json.loads(http_get(
    "https://api.fda.gov/drug/event.json"
    "?count=patient.reaction.reactionmeddrapt.exact"
    "&limit=10"
))
for item in r['results']:
    print(f"{item['count']:>10,}  {item['term']}")
# 1,260,866  DRUG INEFFECTIVE
#   824,385  DEATH
#   815,408  OFF LABEL USE
#   752,672  NAUSEA
#   742,327  FATIGUE
#   610,644  DIARRHOEA
#   599,931  HEADACHE
#   592,586  PAIN
#   541,768  DYSPNOEA
#   476,776  DIZZINESS

# Top drug manufacturers by adverse event count
r = json.loads(http_get(
    "https://api.fda.gov/drug/event.json"
    "?count=patient.drug.openfda.manufacturer_name.exact"
    "&limit=5"
))
for item in r['results']:
    print(f"{item['count']:>10,}  {item['term']}")
# 4,907,099  Aurobindo Pharma Limited
# 3,724,435  Chartwell RX, LLC
# 3,609,145  Rising Pharma Holdings, Inc.
# 3,529,567  Mylan Pharmaceuticals Inc.

# Count by date field — key is 'time' not 'term'
r = json.loads(http_get(
    "https://api.fda.gov/drug/event.json"
    "?count=receivedate"
    "&limit=5"
))
for item in r['results']:
    print(f"{item['time']}: {item['count']:,}")
# Date fields return ascending order by default

# Count food recalls by top recalling firms
r = json.loads(http_get(
    "https://api.fda.gov/food/enforcement.json"
    "?count=recalling_firm.exact"
    "&limit=5"
))
for item in r['results']:
    print(f"{item['count']:>8,}  {item['term']}")
# 633  Garden-Fresh Foods, Inc.
```

Count-able fields that confirm working (2026-04-18):

| Field | Notes |
|-------|-------|
| `patient.reaction.reactionmeddrapt.exact` | Use `.exact` for exact term grouping |
| `patient.drug.openfda.manufacturer_name.exact` | |
| `patient.drug.openfda.pharm_class_epc.exact` | Pharmacological class |
| `patient.drug.drugcharacterization` | 1=suspect, 2=concomitant, 3=interacting |
| `serious` | 1=serious, 2=not |
| `patient.patientsex` | 1=male, 2=female, 0=unknown |
| `receivedate` | Returns `{time, count}` not `{term, count}` |
| `recalling_firm.exact` | On food/enforcement |

### Pagination with skip

```python
import json
from helpers import http_get

PAGE_SIZE = 100

def paginate(endpoint_url, max_records=1000):
    """Yield all results up to max_records."""
    skip = 0
    seen = 0
    while seen < max_records:
        limit = min(PAGE_SIZE, max_records - seen)
        r = json.loads(http_get(f"{endpoint_url}&limit={limit}&skip={skip}"))
        batch = r['results']
        if not batch:
            break
        yield from batch
        seen += len(batch)
        total = r['meta']['results']['total']
        if skip + limit >= total:
            break
        skip += limit

for ev in paginate("https://api.fda.gov/drug/event.json?search=receivedate:[20240101+TO+20240131]", max_records=250):
    print(ev['safetyreportid'], ev['receivedate'])
```

### Parallel fetch across datasets

```python
import json
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

def fetch_dataset(url):
    r = json.loads(http_get(url))
    return url, r['meta']['results']['total'], r['results']

urls = [
    "https://api.fda.gov/drug/event.json?limit=5",
    "https://api.fda.gov/food/enforcement.json?limit=5&sort=report_date:desc",
    "https://api.fda.gov/device/recall.json?limit=5",
    "https://api.fda.gov/drug/event.json?count=patient.reaction.reactionmeddrapt.exact&limit=10",
    "https://api.fda.gov/drug/label.json?search=openfda.brand_name:%22aspirin%22&limit=3",
]
with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_dataset, urls))
# 5 parallel requests complete in ~4s confirmed
```

### Error handling

OpenFDA returns gzip-compressed error bodies. Decompress before parsing:

```python
import json, gzip, urllib.error
from helpers import http_get

def safe_get(url):
    try:
        return json.loads(http_get(url))
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            body = json.loads(gzip.decompress(raw).decode())
        except Exception:
            body = {"raw": raw.decode("utf-8", errors="replace")}
        code = body.get("error", {}).get("code", "UNKNOWN")
        msg  = body.get("error", {}).get("message", str(body))
        raise RuntimeError(f"OpenFDA {e.code} {code}: {msg}") from e

# Example: no matches returns 404 NOT_FOUND
try:
    r = safe_get('https://api.fda.gov/drug/event.json?search=patient.reaction.reactionmeddrapt:"xyzzy_nonexistent"')
except RuntimeError as e:
    print(e)
# OpenFDA 404 NOT_FOUND: No matches found!
```

Error codes:

| HTTP | code | Meaning |
|------|------|---------|
| 404 | `NOT_FOUND` | No results match your search |
| 400 | `BAD_REQUEST` | Invalid query syntax or field name |
| 403 | `API_KEY_MISSING` | `limit` exceeds 500 and no `api_key` provided |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |

## Query parameter reference

| Param | Description | Notes |
|-------|-------------|-------|
| `search` | Filter expression | `field:"value"` or `field:[X+TO+Y]` |
| `count` | Aggregate by field | Returns term+count pairs, max 1,000 terms |
| `limit` | Results per page | Max 500 without key, max 1,000 with key |
| `skip` | Offset for pagination | Max 25,000; use narrow `search` to page deeper |
| `sort` | Sort results | `field:asc` or `field:desc`; not valid with `count` |
| `api_key` | Your API key | Pass as `&api_key=YOUR_KEY`; increases limits |

### Search syntax

```
# Exact phrase (quote the value)
search=openfda.brand_name:"tylenol"

# Number/date field exact match
search=serious:1

# Date range (YYYYMMDD format for most date fields)
search=receivedate:[20240101+TO+20241231]

# AND (use + as URL-encoded space)
search=patient.reaction.reactionmeddrapt:"nausea"+AND+patient.drug.medicinalproduct:"aspirin"

# OR
search=patient.reaction.reactionmeddrapt:"nausea"+OR+patient.reaction.reactionmeddrapt:"vomiting"

# Field existence (any non-null value)
search=_exists_:patient.drug.openfda.brand_name
```

### .exact suffix for counts

Without `.exact` the field is tokenized (word-split) before counting — useful for text search but gives inflated counts. With `.exact` the full field value is used as a single token — required for drug names, firm names, reaction terms:

```python
# Wrong: tokenizes "DRUG INEFFECTIVE" into "DRUG" and "INEFFECTIVE"
# ?count=patient.reaction.reactionmeddrapt

# Correct: counts the full MedDRA term as-is
# ?count=patient.reaction.reactionmeddrapt.exact
```

## Rate limits

| Mode | Limit | How to supply key |
|------|-------|-------------------|
| No API key | 40 req/min, max 500 per call | (nothing) |
| With API key | 240 req/min, max 1,000 per call | `&api_key=YOUR_KEY` |

Get a free key at `https://api.fda.gov/` — instant, no payment required.

## Key field reference

### drug/event — patient.drug fields

| Field | Description |
|-------|-------------|
| `medicinalproduct` | Drug name as reported |
| `drugcharacterization` | `1`=suspect, `2`=concomitant, `3`=interacting |
| `drugindication` | Indication for use |
| `drugdosagetext` | Free-text dosage |
| `openfda.brand_name` | Standardized brand names (list) |
| `openfda.generic_name` | Standardized generic names (list) |
| `openfda.manufacturer_name` | Manufacturer name(s) (list) |
| `openfda.pharm_class_epc` | Pharmacological class (list) |
| `openfda.rxcui` | RxNorm CUI codes (list) |

### drug/event — patient fields

| Field | Description |
|-------|-------------|
| `patientonsetage` | Age at onset (string) |
| `patientonsetageunit` | Age unit (`801`=year, `802`=month, etc.) |
| `patientsex` | `1`=male, `2`=female, `0`=unknown |
| `reaction[].reactionmeddrapt` | MedDRA reaction term |
| `reaction[].reactionoutcome` | `1`=recovered, `2`=recovering, `3`=not recovered, `4`=fatal, `5`=unknown, `6`=death |

### drug/event — report-level fields

| Field | Description |
|-------|-------------|
| `safetyreportid` | Unique report ID |
| `receivedate` | Date received by FDA (YYYYMMDD) |
| `serious` | `1`=serious, `2`=not serious |
| `seriousnessdeath` | `1`=death reported |
| `seriousnesshospitalization` | `1`=hospitalization |
| `primarysource.reportercountry` | ISO country code |

## Gotchas

- **Never use the browser for OpenFDA.** The entire API is fully accessible via `http_get`. No JavaScript, no cookies, no session state needed.

- **404 NOT_FOUND means no matches, not a bad URL.** When `search` returns zero results, OpenFDA returns HTTP 404 with `{"error": {"code": "NOT_FOUND", "message": "No matches found!"}}`. Always wrap in try/except and check for this case. The error body is gzip-compressed — use `gzip.decompress(e.read())` before parsing.

- **`limit` > 500 without API key returns 403 `API_KEY_MISSING`.** The limit without a key is 500 per call, not 100. With a key, max is 1,000. There is no way to page past 25,000 total records via `skip` — narrow your `search` to work within that constraint.

- **`.exact` suffix is required for meaningful count aggregations.** Without it, multi-word terms like `"DRUG INEFFECTIVE"` are tokenized and counted as individual words. Always append `.exact` to string fields used in `count=` queries: `count=patient.reaction.reactionmeddrapt.exact`.

- **Date fields return `{time, count}` not `{term, count}`.** When you use a date field in `count=` (e.g. `count=receivedate`), each result object has key `time` instead of `term`. Your loop must use `item.get('time', item.get('term'))` if you want generic code.

- **Sort is not compatible with count.** Adding `sort=` to a `count=` query returns 400. Count results are always ordered by count descending; there is no way to reorder them.

- **Most date fields are YYYYMMDD strings, not ISO dates.** `receivedate`, `transmissiondate`, `submission_status_date` are all `"20240101"` format. Device recall fields (`event_date_initiated`, `event_date_terminated`) are ISO `"2026-04-09"` format. Check before parsing.

- **`count=` on some food/enforcement fields returns 500.** `classification`, `status`, `product_type`, `state`, `country`, `voluntary_mandated` all return HTTP 500 on `food/enforcement`. Only `recalling_firm.exact` (and a few others) work reliably. On `drug/event`, almost all fields work in count.

- **`food/event` reactions and outcomes are lists of strings, not lists of dicts.** Unlike `drug/event` where reactions are `[{"reactionmeddrapt": "Headache", ...}]`, the food event endpoint returns `reactions: ["Vomiting", "Headache"]` — plain strings. Do not call `.get()` on them.

- **`openfda` sub-object is absent or empty on many records.** Not every event or label has standardized `openfda` fields populated. Always use `ev.get('openfda', {})` and then `.get('brand_name', [])` on the result. Never assume the key exists.

- **`skip` is capped at 25,000.** For datasets with millions of records, `search` + narrowing by date range or other filters is the only way to access arbitrary records beyond position 25,000.

- **`animal/event` endpoint returns 404** — confirmed not live as of 2026-04-18.

- **No response headers expose rate limit status.** Unlike GitHub or Twitter APIs, OpenFDA does not return `X-RateLimit-*` headers. You will receive HTTP 429 when rate-limited — implement exponential backoff.

- **The `meta.last_updated` field in count responses is a date string only.** It reflects when the dataset was last updated, not the query time. Regular (non-count) responses include `meta.results.total` which reflects live data.

- **`sort=count:desc` does NOT work on count queries** — sort is for regular search queries only. Count results are always by count descending with no override.
