# NVD / CVE API — Scraping & Data Extraction

`https://services.nvd.nist.gov` — NIST National Vulnerability Database REST API v2.0. **Never use the browser.** All CVE data is available via direct HTTP. No API key required for public access; key unlocks higher rate limit.

## Do this first

**`http_get` from helpers.py fails on NVD due to macOS SSL cert chain issues. Use `requests` or a manual SSL-bypass wrapper instead.**

```python
import urllib.request, ssl, json, time

# SSL bypass — required on macOS where system cert chain may not include NIST root
_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

def nvd_get(url, api_key=None):
    headers = {"User-Agent": "Mozilla/5.0"}
    if api_key:
        headers["apiKey"] = api_key
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ctx) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise RuntimeError("NVD rate limit hit (5 req/30s without key). Wait 30s or add apiKey header.")
        raise

BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
```

Alternatively, `import requests; r = requests.get(url, headers={"apiKey": key}); r.raise_for_status(); return r.json()` also works and handles SSL automatically.

## Common workflows

### Single CVE lookup

```python
import json, urllib.request, ssl

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

def nvd_get(url, api_key=None):
    headers = {"User-Agent": "Mozilla/5.0"}
    if api_key:
        headers["apiKey"] = api_key
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30, context=_ctx) as r:
        return json.loads(r.read().decode())

BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"

data = nvd_get(f"{BASE}?cveId=CVE-2021-44228")
cve = data["vulnerabilities"][0]["cve"]

# English description
desc = next(d["value"] for d in cve["descriptions"] if d["lang"] == "en")

# CWE IDs
cwes = [
    w["description"][0]["value"]
    for w in cve.get("weaknesses", [])
    if w.get("description")
]

# CISA KEV (Known Exploited Vulnerabilities) fields — only present if in catalog
cisa_name = cve.get("cisaVulnerabilityName")     # e.g. "Apache Log4j2 Remote Code Execution Vulnerability"
cisa_add  = cve.get("cisaExploitAdd")             # e.g. "2021-12-10"
cisa_due  = cve.get("cisaActionDue")              # e.g. "2021-12-24"

print(cve["id"], cve["published"][:10], cve["vulnStatus"])
# CVE-2021-44228 2021-12-10 Analyzed
print(cwes)
# ['CWE-20', 'CWE-917']
print(cisa_name)
# Apache Log4j2 Remote Code Execution Vulnerability
```

### Extract CVSS score (handles v2 / v3.0 / v3.1 / v4.0)

**CVSS version differences are the main gotcha — see Gotchas section.**

```python
def extract_cvss(cve: dict) -> dict:
    """Return highest-priority CVSS entry: v4 > v3.1 > v3.0 > v2. Prefers 'Primary' source."""
    m = cve.get("metrics", {})
    for key in ("cvssMetricV40", "cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        metrics = m.get(key, [])
        entry = next((x for x in metrics if x.get("type") == "Primary"), metrics[0] if metrics else None)
        if not entry:
            continue
        d = entry["cvssData"]
        return {
            "version":  d.get("version"),
            "score":    d.get("baseScore"),
            # v2: severity lives at metric level, NOT in cvssData
            "severity": entry.get("baseSeverity") if key == "cvssMetricV2" else d.get("baseSeverity"),
            "vector":   d.get("vectorString"),
        }
    return {}

# Confirmed outputs:
# CVE-2021-44228 → {'version': '3.1', 'score': 10.0, 'severity': 'CRITICAL', 'vector': 'CVSS:3.1/...'}
# CVE-2008-7261  → {'version': '2.0', 'score': 2.1,  'severity': 'LOW',      'vector': 'AV:L/AC:L/...'}
# CVE-2026-34477 → {'version': '4.0', 'score': 6.3,  'severity': 'MEDIUM',   'vector': 'CVSS:4.0/...'}
```

### Keyword search

```python
data = nvd_get(f"{BASE}?keywordSearch=log4j")
print(data["totalResults"])   # 31 (2026-04-18)

for v in data["vulnerabilities"]:
    cve  = v["cve"]
    cvss = extract_cvss(cve)
    print(cve["id"], cvss.get("score"), cvss.get("severity"))
# CVE-2008-7261 2.1 LOW
# CVE-2021-44228 10.0 CRITICAL
# ...
```

Use `keywordExactMatch` (no value — boolean flag) to require exact phrase rather than any word match:
```
?keywordSearch=apache+log4j&keywordExactMatch
```

### Filter by CVSS severity

```python
# cvssV3Severity values: CRITICAL, HIGH, MEDIUM, LOW
data = nvd_get(f"{BASE}?cvssV3Severity=CRITICAL&resultsPerPage=5")
print(data["totalResults"])   # 30049 (2026-04-18)

# cvssV2Severity also supported
data = nvd_get(f"{BASE}?cvssV2Severity=HIGH&resultsPerPage=5")
print(data["totalResults"])   # 56837
```

### Filter by date range

```python
# pubStartDate / pubEndDate — publication date (ISO 8601, milliseconds required)
data = nvd_get(
    f"{BASE}?pubStartDate=2024-01-01T00:00:00.000"
    f"&pubEndDate=2024-01-07T23:59:59.999"
    f"&resultsPerPage=5"
)
print(data["totalResults"])   # 394

# lastModStartDate / lastModEndDate — last modification date (same format)
data = nvd_get(
    f"{BASE}?lastModStartDate=2024-01-01T00:00:00.000"
    f"&lastModEndDate=2024-01-02T23:59:59.999"
    f"&resultsPerPage=3"
)
print(data["totalResults"])   # 69
```

### Filter by CPE (affected software)

```python
# cpeName — exact CPE 2.3 URI
data = nvd_get(f"{BASE}?cpeName=cpe:2.3:a:apache:log4j:2.14.1:*:*:*:*:*:*:*")
print(data["totalResults"])   # 5
for v in data["vulnerabilities"]:
    print(v["cve"]["id"])
# CVE-2021-44228, CVE-2021-45046, CVE-2021-45105, ...
```

### Filter to CISA KEV catalog

```python
# hasKev — boolean flag (no value), returns CVEs in CISA's Known Exploited Vulnerabilities catalog
data = nvd_get(f"{BASE}?hasKev&resultsPerPage=5")
print(data["totalResults"])   # 1569 (2026-04-18)
```

### Paginate full result sets

Max `resultsPerPage` is 2000. Default (omitted) is also 2000. Use `startIndex` to page through.

```python
import time

def fetch_all_cves(params: dict, page_size=2000, sleep_s=6.5) -> list:
    """Paginate NVD CVE results. sleep_s=6.5 keeps safely under 5 req/30s limit."""
    all_cves = []
    idx = 0
    total = None
    qs_base = "&".join(f"{k}={v}" for k, v in params.items())

    while total is None or idx < total:
        url = f"{BASE}?{qs_base}&resultsPerPage={page_size}&startIndex={idx}"
        data = nvd_get(url)
        total = data["totalResults"]
        batch = data["vulnerabilities"]
        all_cves.extend(batch)
        idx += len(batch)
        if idx < total:
            time.sleep(sleep_s)

    return all_cves

# Fetch all CRITICAL CVEs published in a week
cves = fetch_all_cves({
    "pubStartDate": "2024-01-01T00:00:00.000",
    "pubEndDate":   "2024-01-07T23:59:59.999",
    "cvssV3Severity": "CRITICAL",
})
print(f"Fetched {len(cves)} CVEs")
```

### CPE match strings (affected product ranges)

```python
CPE_BASE = "https://services.nvd.nist.gov/rest/json/cpematch/2.0"

data = nvd_get(f"{CPE_BASE}?cveId=CVE-2021-44228")
print(data["totalResults"])   # 395

# Each matchString shows a version range and the specific CPE names that match
for ms in data["matchStrings"][:2]:
    ms = ms["matchString"]
    print(ms["criteria"])          # e.g. cpe:2.3:a:apache:log4j:2.0:rc1:*:*:*:*:*:*
    print(ms["status"])            # Active
    print(len(ms.get("matches", [])), "specific CPEs")
```

### Parallel batch lookup (multiple known CVE IDs)

```python
import time
from concurrent.futures import ThreadPoolExecutor

def fetch_cve(cve_id):
    data = nvd_get(f"{BASE}?cveId={cve_id}")
    if not data["vulnerabilities"]:
        return None
    return data["vulnerabilities"][0]["cve"]

cve_ids = ["CVE-2021-44228", "CVE-2021-45046", "CVE-2021-45105", "CVE-2021-44832"]

# Without API key: max ~4-5 parallel workers before hitting 429
# With API key: safe up to ~10 workers
with ThreadPoolExecutor(max_workers=3) as ex:
    results = list(ex.map(fetch_cve, cve_ids))

for cve in results:
    if cve:
        cvss = extract_cvss(cve)
        print(cve["id"], cvss.get("score"), cvss.get("severity"))
# CVE-2021-44228 10.0 CRITICAL
# CVE-2021-45046 9.0 CRITICAL
# CVE-2021-45105 5.9 MEDIUM
# CVE-2021-44832 6.6 MEDIUM
# Time: ~5s for 4 CVEs with workers=3
```

### With API key (higher rate limit)

```python
API_KEY = "your-nvd-api-key"   # Register free at https://nvd.nist.gov/developers/request-an-api-key

data = nvd_get(f"{BASE}?cveId=CVE-2021-44228", api_key=API_KEY)
# Key goes in header: apiKey: {key}
# Rate limit with key: 50 requests per 30 seconds (vs 5 without)
# Use sleep_s=0.6 between pages (50/30s = 1 req/0.6s)
```

## API reference

### Endpoints

| Endpoint | Notes |
|---|---|
| `GET /rest/json/cves/2.0` | CVE list (default 2000/page, max 2000/page) |
| `GET /rest/json/cves/2.0?cveId=CVE-YYYY-NNNNN` | Single CVE |
| `GET /rest/json/cpematch/2.0?cveId=CVE-YYYY-NNNNN` | CPE match strings for a CVE |

### Query parameters (CVE endpoint)

| Parameter | Example | Notes |
|---|---|---|
| `cveId` | `CVE-2021-44228` | Single CVE lookup |
| `keywordSearch` | `log4j` | Searches description text |
| `keywordExactMatch` | *(flag, no value)* | Require exact phrase match |
| `pubStartDate` | `2024-01-01T00:00:00.000` | ISO 8601 with milliseconds |
| `pubEndDate` | `2024-01-07T23:59:59.999` | Pair with `pubStartDate` |
| `lastModStartDate` | `2024-01-01T00:00:00.000` | Filter by last-modified |
| `lastModEndDate` | `2024-01-02T23:59:59.999` | Pair with `lastModStartDate` |
| `cvssV3Severity` | `CRITICAL` | CRITICAL, HIGH, MEDIUM, LOW |
| `cvssV2Severity` | `HIGH` | HIGH, MEDIUM, LOW |
| `cpeName` | `cpe:2.3:a:apache:log4j:...` | Exact CPE 2.3 URI |
| `hasKev` | *(flag, no value)* | CISA KEV catalog members only |
| `resultsPerPage` | `2000` | Max 2000; default 2000 |
| `startIndex` | `0` | Pagination offset |

### Top-level response fields

```json
{
  "resultsPerPage": 2000,
  "startIndex": 0,
  "totalResults": 345194,
  "format": "NVD_CVE",
  "version": "2.0",
  "timestamp": "2026-04-19T01:02:03.536",
  "vulnerabilities": [...]
}
```

### CVE object structure (key fields)

```json
{
  "cve": {
    "id": "CVE-2021-44228",
    "sourceIdentifier": "security@apache.org",
    "published": "2021-12-10T10:15:09.143",
    "lastModified": "2026-02-20T16:15:59.363",
    "vulnStatus": "Analyzed",
    "descriptions": [{"lang": "en", "value": "..."}],
    "metrics": {
      "cvssMetricV40": [...],   // present for recent CVEs
      "cvssMetricV31": [...],   // most CVEs from 2019+
      "cvssMetricV30": [...],   // older format
      "cvssMetricV2":  [...]    // pre-2019; always present for historical CVEs
    },
    "weaknesses": [{"source": "...", "type": "Primary|Secondary", "description": [{"lang":"en","value":"CWE-20"}]}],
    "configurations": [...],    // CPE match trees (complex nested AND/OR)
    "references": [{"url": "...", "source": "...", "tags": [...]}],
    "cisaExploitAdd": "2021-12-10",           // only if in CISA KEV
    "cisaActionDue": "2021-12-24",            // only if in CISA KEV
    "cisaVulnerabilityName": "...",           // only if in CISA KEV
    "cisaRequiredAction": "..."               // only if in CISA KEV
  }
}
```

### CVSS metric structure per version

| Version key | `baseSeverity` location | Unique fields |
|---|---|---|
| `cvssMetricV2` | `metric["baseSeverity"]` (NOT in `cvssData`) | `acInsufInfo`, `obtainAllPrivilege`, `obtainUserPrivilege` |
| `cvssMetricV30` / `cvssMetricV31` | `cvssData["baseSeverity"]` | `scope`, `privilegesRequired`, `userInteraction` |
| `cvssMetricV40` | `cvssData["baseSeverity"]` | `attackRequirements`, `vulnConfidentialityImpact`, `subIntegrityImpact`, `exploitMaturity` |

Each metric entry also has `"type": "Primary"` or `"Secondary"` — always prefer `Primary` when multiple sources score the same CVE.

## Gotchas

- **`http_get` from helpers.py fails with SSL error on macOS.** The NIST server uses a cert chain not trusted by macOS's system store. Use the `ssl.create_default_context()` bypass shown above, or use `requests` (which bundles `certifi` and works out of the box). Do not modify helpers.py.

- **v2 `baseSeverity` is at the metric level, not inside `cvssData`.** For `cvssMetricV2`, `entry["baseSeverity"]` exists but `entry["cvssData"]["baseSeverity"]` does not. For v3.x and v4.0, it's inside `cvssData`. The `extract_cvss()` function above handles this correctly.

- **`metrics` key may be empty or missing entirely.** Some CVEs (especially newly published or disputed ones) have `"metrics": {}`. Always guard with `.get("metrics", {})` before checking version keys.

- **Multiple CVSS entries per version (Primary vs Secondary).** A single CVE can have multiple v3.1 entries from different sources (`nvd@nist.gov` as Primary, CNA as Secondary). Use `type == "Primary"` for the authoritative NVD score; Secondary scores are from the assigning CNA and may differ.

- **CVSS v4.0 is increasingly common** (all-new CVEs from 2026+). A CVE may have only `cvssMetricV40` with no v3 at all. Hardcoded `cvssMetricV31` access will miss these — always iterate the precedence list.

- **Rate limit: 5 req/30s without key, 50 req/30s with key.** The window is a sliding 30-second window per IP. HTTP 429 is returned with `Retry-After: 0` header and body `error code: 1015`. Recovery is automatic after ~30s. Safe pacing: 6.5s sleep between requests without a key; 0.6s with one.

- **`resultsPerPage` max is 2000.** Requesting more returns HTTP 403 (empty body). The default when omitted is also 2000.

- **Date parameters require milliseconds.** `pubStartDate=2024-01-01T00:00:00` fails silently (returns 0 results). Must include `.000`: `pubStartDate=2024-01-01T00:00:00.000`.

- **`startIndex` + `resultsPerPage` can overshoot `totalResults`.** The API returns whatever is available — the last page will have fewer items than `resultsPerPage`. Always check `len(batch)` not `page_size` when advancing the index.

- **`totalResults` can shift between pages during bulk harvesting.** NVD updates continuously. For consistency, use `lastModStartDate`/`lastModEndDate` windows rather than offset pagination over unbounded queries.

- **`vulnStatus` values:** `Analyzed` (NVD fully reviewed), `Modified` (updated post-analysis), `Awaiting Analysis`, `Undergoing Analysis`, `Deferred`, `Rejected`. Only `Analyzed` CVEs are guaranteed to have complete CPE configurations.

- **`configurations` is complex nested AND/OR.** The `configurations[]` array uses `"operator": "AND"|"OR"` with nested `nodes` — not a flat list of affected versions. Parse it recursively or use the `cpematch` endpoint for a flat list of matching CPEs instead.

- **CISA KEV fields are absent (not null) when not in catalog.** Do `cve.get("cisaExploitAdd")` — if the CVE is not in KEV, the key simply doesn't exist in the response object.
