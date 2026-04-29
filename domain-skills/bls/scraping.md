# U.S. Bureau of Labor Statistics (BLS) API — Data Extraction

`https://api.bls.gov/publicAPI/v2` — public U.S. economic statistics. **No browser needed.** All data is reachable via `http_get` or Python's `urllib`. No API key required for basic access; a free registered key unlocks higher limits and extra features.

## Do this first

**Use the POST multi-series endpoint — it fetches up to 50 series in one call and supports year-range filtering.**

```python
import json, urllib.request

def bls_post(series_ids, start_year, end_year, api_key=None):
    """Fetch one or more BLS series via POST. No API key = 25 req/day (IP-shared)."""
    payload = {"seriesid": series_ids, "startyear": str(start_year), "endyear": str(end_year)}
    if api_key:
        payload["registrationkey"] = api_key
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

data = bls_post(["LNS14000000", "CUUR0000SA0"], 2020, 2024)
# Always check status first — limit exhaustion returns status='REQUEST_NOT_PROCESSED'
assert data["status"] == "REQUEST_SUCCEEDED", data["message"]

for series in data["Results"]["series"]:
    sid = series["seriesID"]
    for obs in series["data"][:3]:
        print(sid, obs["year"], obs["period"], obs["periodName"], obs["value"])
# LNS14000000  2024  M12  December   4.1
# LNS14000000  2024  M11  November   4.2
# CUUR0000SA0  2024  M12  December   314.175
```

Data is returned newest-first. Iterate in reverse (`series["data"][::-1]`) for chronological order.

## Rate limits

| Tier | Requests/day | Series/query | Year range | Extra fields |
|---|---|---|---|---|
| Unregistered | 25 (shared per IP) | 25 | 3 years max | No |
| Registered (free key) | 500 | 50 | 20 years | catalog, calculations |

Register at: `https://data.bls.gov/registrationEngine/` (instant, free, email only).

The unregistered 25-req/day limit is **per IP address** — shared across all users on the same network. Hit the limit and every call returns `REQUEST_NOT_PROCESSED`. Recovery resets at midnight ET.

## Response shape

```python
{
    "status": "REQUEST_SUCCEEDED",  # or "REQUEST_NOT_PROCESSED" / "REQUEST_FAILED"
    "responseTime": 118,            # ms
    "message": [],                  # list of strings; non-empty on errors/warnings
    "Results": {
        "series": [
            {
                "seriesID": "LNS14000000",
                "data": [
                    {
                        "year": "2024",
                        "period": "M12",         # M01-M12, Q01-Q04, A01, S01-S02
                        "periodName": "December",
                        "value": "4.1",          # ALWAYS a string — cast to float
                        "footnotes": [{"code": "P", "text": "Preliminary."}]
                        # With api_key: also "calculations": {"net_changes": {...}, "pct_changes": {...}}
                    },
                    ...
                ]
            }
        ]
    }
}
```

## Common workflows

### Single series — GET (no POST needed for one series)

```python
import json, urllib.request

url = "https://api.bls.gov/publicAPI/v2/timeseries/data/LNS14000000"
with urllib.request.urlopen(url, timeout=20) as r:
    data = json.loads(r.read())

series = data["Results"]["series"][0]
latest = series["data"][0]  # newest first
print(f"Unemployment rate: {latest['value']}% ({latest['periodName']} {latest['year']})")
# Unemployment rate: 4.1% (December 2024)
```

### Multi-series fetch and flatten to records

```python
import json, urllib.request

def bls_fetch(series_ids, start_year, end_year, api_key=None):
    payload = {"seriesid": series_ids, "startyear": str(start_year), "endyear": str(end_year)}
    if api_key:
        payload["registrationkey"] = api_key
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    if resp["status"] != "REQUEST_SUCCEEDED":
        raise RuntimeError(resp["message"])
    records = []
    for series in resp["Results"]["series"]:
        sid = series["seriesID"]
        for obs in series["data"]:
            records.append({
                "series_id": sid,
                "year": int(obs["year"]),
                "period": obs["period"],
                "period_name": obs["periodName"],
                "value": float(obs["value"]),
                "preliminary": any(f.get("code") == "P" for f in obs.get("footnotes", []) if f),
            })
    return records

records = bls_fetch(["LNS14000000", "CUUR0000SA0"], 2022, 2024)
print(len(records))  # e.g. 72 (2 series × 36 monthly observations)
```

### Monthly time-series: convert period to date

```python
import datetime

def period_to_date(year: int, period: str) -> datetime.date:
    """Convert BLS year+period to a date. M01='Jan 1', Q01='Jan 1', A01='Jan 1'."""
    if period.startswith("M"):
        month = int(period[1:])
        return datetime.date(year, month, 1)
    elif period.startswith("Q"):
        quarter = int(period[1:])
        month = (quarter - 1) * 3 + 1
        return datetime.date(year, month, 1)
    elif period.startswith("A"):
        return datetime.date(year, 1, 1)
    elif period.startswith("S"):
        half = int(period[1:])
        month = 1 if half == 1 else 7
        return datetime.date(year, month, 1)
    return datetime.date(year, 1, 1)

for rec in sorted(records, key=lambda r: (r["year"], r["period"])):
    dt = period_to_date(rec["year"], rec["period"])
    print(dt, rec["series_id"], rec["value"])
```

### Fetch 20 years of data (requires API key)

```python
import json, urllib.request

API_KEY = "your_key_here"  # from https://data.bls.gov/registrationEngine/

payload = {
    "seriesid": ["LNS14000000"],
    "startyear": "2005",
    "endyear": "2024",
    "registrationkey": API_KEY,
    "catalog": True,          # adds series metadata (title, survey, etc.)
    "calculations": True,     # adds net_changes and pct_changes per observation
    "annualaverage": True,    # adds annual average (period="M13") where available
}
body = json.dumps(payload).encode()
req = urllib.request.Request(
    "https://api.bls.gov/publicAPI/v2/timeseries/data/",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=30) as r:
    data = json.loads(r.read())

series = data["Results"]["series"][0]
# With catalog=True: series["catalog"] dict with survey name, measure, area, etc.
print(series.get("catalog", {}))
# With calculations=True: each obs has "calculations" sub-dict
obs = series["data"][0]
print(obs.get("calculations", {}))
# {'net_changes': {'1': '-0.1', '3': '0.2', '6': '-0.2', '12': '0.4'},
#  'pct_changes': {'1': '-2.4', '3': '5.0', '6': '-4.8', '12': '10.8'}}
```

`calculations` keys `'1'`, `'3'`, `'6'`, `'12'` are 1-month, 3-month, 6-month, 12-month changes. Values are strings — cast to float.

### Parallel fetch for independent year ranges (stays within 500/day limit)

```python
import json, urllib.request
from concurrent.futures import ThreadPoolExecutor

API_KEY = "your_key_here"

def fetch_chunk(args):
    series_ids, start, end = args
    payload = {
        "seriesid": series_ids,
        "startyear": str(start),
        "endyear": str(end),
        "registrationkey": API_KEY,
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.bls.gov/publicAPI/v2/timeseries/data/",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# Split 40 years into two 20-year chunks (v2 max is 20 years per call)
chunks = [
    (["LNS14000000", "CUUR0000SA0"], 1985, 2004),
    (["LNS14000000", "CUUR0000SA0"], 2005, 2024),
]
with ThreadPoolExecutor(max_workers=2) as ex:
    results = list(ex.map(fetch_chunk, chunks))
```

## Popular series IDs

### Employment & Unemployment (BLS Current Population Survey)

| Series ID | Description | Frequency |
|---|---|---|
| `LNS14000000` | Unemployment rate, seasonally adjusted | Monthly |
| `LNS11000000` | Civilian labor force level | Monthly |
| `LNS12000000` | Employment level | Monthly |
| `LNS13000000` | Unemployed persons | Monthly |
| `LAUCN040010000000006` | Arizona unemployment rate (county-level LAUS) | Monthly |

### Nonfarm Payrolls (CES / Establishment Survey)

| Series ID | Description | Frequency |
|---|---|---|
| `CES0000000001` | Total nonfarm employment, seasonally adjusted | Monthly |
| `CES0500000001` | Total private employment | Monthly |
| `CES1000000001` | Mining and logging | Monthly |
| `CES2000000001` | Construction | Monthly |
| `CES3000000001` | Manufacturing | Monthly |
| `CES6000000001` | Professional and business services | Monthly |
| `CES7000000001` | Leisure and hospitality | Monthly |

### Inflation / Consumer Price Index (CPI-U)

| Series ID | Description | Frequency |
|---|---|---|
| `CUUR0000SA0` | CPI-U, All items, not seasonally adjusted | Monthly |
| `CUSR0000SA0` | CPI-U, All items, seasonally adjusted | Monthly |
| `CUUR0000SA0L1E` | CPI-U, All items less food and energy (core) | Monthly |
| `CUUR0000SAF1` | CPI-U, Food | Monthly |
| `CUUR0000SA0E` | CPI-U, Energy | Monthly |

### Producer Price Index (PPI)

| Series ID | Description | Frequency |
|---|---|---|
| `PPIACO` | PPI, All commodities | Monthly |
| `WPSSOP3000` | PPI, Finished goods | Monthly |

### Productivity & Costs

| Series ID | Description | Frequency |
|---|---|---|
| `PRS85006092` | Nonfarm business productivity, % change | Quarterly |
| `PRS85006112` | Nonfarm business unit labor costs, % change | Quarterly |

### Average Wages

| Series ID | Description | Frequency |
|---|---|---|
| `CES0500000003` | Average hourly earnings, all private, SA | Monthly |
| `CES0500000008` | Average weekly hours, all private, SA | Monthly |

## Series ID structure

BLS series IDs encode all query dimensions. Pattern: `PREFIX + region + measure + adjustment + ...`

```
LNS 14 000000 0  →  Local Area Unemployment Stats, Unemployment Rate, National, Seasonally Adj
CES 000 0000 001 →  Current Employment Statistics, Total Nonfarm, All Employees
CUU R0000 SA0   →  CPI-U, US city average, Not Seasonally Adjusted, All Items
```

Find series IDs using BLS Data Finder: `https://www.bls.gov/data/`

## Period codes

| Period | Meaning |
|---|---|
| `M01` – `M12` | January – December (monthly data) |
| `M13` | Annual average (only with `annualaverage=True` and API key) |
| `Q01` – `Q04` | Q1–Q4 (quarterly data, e.g. productivity) |
| `A01` | Annual (yearly data) |
| `S01` / `S02` | Semi-annual (H1 / H2) |

The `periodName` field gives the human-readable label: `"January"`, `"1st Quarter"`, `"Annual"`, etc.

## Gotchas

- **`value` is always a string** — `obs["value"]` is `"4.1"`, not `4.1`. Always cast: `float(obs["value"])`. Occasional values are `"-"` for suppressed data; guard with `obs["value"] != "-"` before casting.

- **Data is newest-first** — `series["data"][0]` is the most recent observation. Use `series["data"][::-1]` or `sorted(..., key=lambda o: (o["year"], o["period"]))` for chronological order.

- **Unregistered limit is shared per IP** — 25 queries/day is not per-user; it applies to all traffic from the same public IP. In a shared environment (office, cloud NAT) this exhausts quickly. Register a free key to get 500/day tied to your email.

- **Unregistered is limited to 3 years** — A call with `startyear=2000&endyear=2024` without a key silently truncates to the last 3 years. You won't get an error — you just get fewer rows. Always use a key for long time ranges.

- **`REQUEST_NOT_PROCESSED` means rate limited** — Check `data["status"]` before processing. When limited, `data["Results"]` is `{}` or `[]`, causing a `KeyError` if you skip the check.

- **POST body must be `application/json`** — The Content-Type header is required. Without it the server returns a 400 or processes the request as a form (ignoring `seriesid`).

- **No SSL certificate on some Python installs** — macOS Python 3.11+ may fail with `CERTIFICATE_VERIFY_FAILED` against `api.bls.gov`. Fix: `ssl._create_default_https_context = ssl._create_unverified_context` (dev only), or install `certifi` and pass `context=ssl.create_default_context(cafile=certifi.where())`.

- **Preliminary data footnote** — The most recent 1-2 observations are often marked preliminary (`footnotes[].code == "P"`). They will be revised in subsequent releases. Track the `"P"` footnote if revision-awareness matters.

- **`calculations` keys are strings `'1'`/`'3'`/`'6'`/`'12'`** — Not integers. Access as `obs["calculations"]["net_changes"]["12"]` and cast to float. Only present when `calculations=True` is passed in the POST body (requires API key).

- **`catalog` requires API key** — Passing `catalog=True` without a `registrationkey` is silently ignored. The `series["catalog"]` key won't appear in the response.

- **Quarterly series use Q-periods, not M-periods** — Productivity (`PRS...`) and some GDP-linked series use `Q01`–`Q04`. Mixing monthly and quarterly series in one POST call works fine — each series has its own period codes.

- **Max 20 years per call, max 50 series per call (with key)** — To retrieve more than 20 years, split into chunks and make multiple calls. To fetch more than 50 series, batch them. Without a key the limits are 3 years / 25 series.

- **Annual averages are a separate period** — `M13` (annual average) only appears when `annualaverage=True` is set in the POST body and you have an API key. Do not confuse `A01` (an actual annual-frequency series) with `M13` (the annual average of a monthly series).
