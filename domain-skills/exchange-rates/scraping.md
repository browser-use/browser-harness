# Exchange Rate APIs — Data Extraction

Three tested free services, no browser needed. Best free option: **fawazahmed0 CDN** (no key, no rate limit, 301 currencies + crypto, historical back to 2024-03-02). Use **Frankfurter** for ECB-sourced fiat-only data with clean time-series. Use **open.er-api.com** for all-in-one latest rates across 166 currencies.

All calls use `http_get` from helpers — no browser, no JS, pure HTTP.

## Do this first: pick your service

| Service | Key required | Historical | Currencies | Update freq | Rate limit |
|---|---|---|---|---|---|
| **fawazahmed0 CDN** | No | Yes (2024-03-02+) | 301 (incl. crypto, gold) | Daily | None observed |
| **Frankfurter** | No | Yes (ECB data, multi-decade) | 30 fiat only | ~16:00 CET weekdays | None observed |
| **open.er-api.com** | No (basic) | No (paid only) | 166 fiat | Daily | None observed |
| **exchangerate.host** | Yes (required) | Paid | Many | — | — |

**Never use a browser for any of these.** All return JSON over HTTPS.

---

## fawazahmed0 CDN — best free option (no key, widest coverage)

Served via jsDelivr CDN. Includes crypto, precious metals, and 301 total assets. Historical data available from 2024-03-02 onward via versioned npm package URLs.

### Latest rates

```python
import json
from helpers import http_get

data = json.loads(http_get(
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies/usd.json"
))
# Confirmed output (2026-04-18):
# {
#   "date": "2026-04-18",
#   "usd": {
#     "eur": 0.84940406,
#     "gbp": 0.73942577,
#     "jpy": 158.6450315,
#     "btc": 1.2934433e-05,
#     "eth": 0.0004132211,
#     "xau": 0.00020640519,   # gold
#     "xag": 0.01234354,      # silver
#     ...301 total entries
#   }
# }
rates = data["usd"]
print(rates["eur"])    # 0.84940406
print(rates["jpy"])    # 158.6450315
print(rates["btc"])    # 1.2934433e-05
```

The outer key always matches the base currency code (lowercase). `data["usd"]` for USD base, `data["eur"]` for EUR base.

### All supported currencies (with names)

```python
import json
from helpers import http_get

currencies = json.loads(http_get(
    "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@latest/v1/currencies.json"
))
# 301 entries. Keys are lowercase codes, values are display names.
# Includes fiat (aed, aud, ...), crypto (btc, eth, sol, ada, ...), metals (xau, xag)
print(currencies["usd"])    # "US Dollar"
print(currencies["btc"])    # "Bitcoin"
print(currencies["xau"])    # "Gold Ounce"
```

### Historical rates

Version format is `YYYY.M.D` (no zero-padding on month or day). Oldest available: 2024-03-02.

```python
import json
from datetime import date
from helpers import http_get

def fawazahmed0_historical(base: str, target_date: date) -> dict:
    """Fetch all rates for `base` on `target_date`. Returns dict of {currency: rate}."""
    version = f"{target_date.year}.{target_date.month}.{target_date.day}"
    base = base.lower()
    url = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{version}/v1/currencies/{base}.json"
    data = json.loads(http_get(url))
    return data[base]

# Confirmed: date(2024, 4, 18) → EUR 0.93691965
rates = fawazahmed0_historical("usd", date(2024, 4, 18))
print(rates["eur"])    # 0.93691965
print(rates["gbp"])    # ...
print(rates["btc"])    # crypto included in historical too
```

Version string for `date(2025, 6, 15)` is `"2025.6.15"` (not `"2025.06.15"`).

### Fallback CDN (if jsDelivr is down)

```python
import json
from helpers import http_get

# Identical response, alternate CDN
data = json.loads(http_get(
    "https://latest.currency-api.pages.dev/v1/currencies/usd.json"
))
```

---

## Frankfurter — best for ECB fiat data + time series

ECB (European Central Bank) source. Data only on business days. 30 fiat currencies, no crypto. Default base is EUR; any of the 30 supported currencies can be the base.

### Latest rates

```python
import json
from helpers import http_get

# All rates against USD base
data = json.loads(http_get("https://api.frankfurter.app/latest?from=USD"))
# {
#   "amount": 1.0,
#   "base": "USD",
#   "date": "2026-04-17",   ← last ECB business day
#   "rates": {"AUD": 1.3934, "BRL": 4.9764, "CAD": 1.3672, ..., "ZAR": 18.44}
# }
# 29 target currencies (all supported except the base)
print(data["rates"]["EUR"])    # 0.84767
print(data["rates"]["GBP"])    # 0.7389
print(data["date"])            # "2026-04-17"
```

### Selective targets and amount conversion

```python
import json
from helpers import http_get

# Convert 100 USD to EUR and GBP
data = json.loads(http_get(
    "https://api.frankfurter.app/latest?from=USD&to=EUR,GBP&amount=100"
))
# {"amount": 100.0, "base": "USD", "date": "2026-04-17", "rates": {"EUR": 84.77, "GBP": 73.892}}
print(data["rates"]["EUR"])    # 84.77
```

### Historical rate on a specific date

```python
import json
from helpers import http_get

# Date is snapped to the nearest prior business day
data = json.loads(http_get("https://api.frankfurter.app/2024-01-01"))
# {"amount": 1.0, "base": "EUR", "date": "2023-12-29", "rates": {...}}
# Note: 2024-01-01 is a holiday, snapped back to 2023-12-29
print(data["date"])              # "2023-12-29"
print(data["rates"]["USD"])      # 1.105
print(data["rates"]["JPY"])      # 156.33
```

Default base on date endpoints is **EUR**. Pass `?from=USD` to change it.

```python
data = json.loads(http_get("https://api.frankfurter.app/2024-01-01?from=USD&to=EUR,GBP,JPY"))
print(data["rates"]["JPY"])    # 141.48 (USD/JPY on 2023-12-29)
```

### Time series

```python
import json
from helpers import http_get

# Daily rates for a date range — only business days are included
data = json.loads(http_get(
    "https://api.frankfurter.app/2023-01-01..2023-12-31?from=USD&to=EUR"
))
# {
#   "amount": 1.0,
#   "base": "USD",
#   "start_date": "2022-12-30",   ← snapped to nearest prior business day
#   "end_date": "2023-12-29",
#   "rates": {
#     "2022-12-30": {"EUR": 0.93756},
#     "2023-01-02": {"EUR": 0.93607},
#     ...256 business days total
#   }
# }
rates_dict = data["rates"]     # keyed by ISO date string
print(len(rates_dict))         # 256 business days for full year
print(rates_dict["2023-06-15"])  # {"EUR": 0.92028}

# Multiple targets
data = json.loads(http_get(
    "https://api.frankfurter.app/2024-01-01..2024-01-07?from=USD&to=EUR,GBP,JPY"
))
for date_str, rates in data["rates"].items():
    print(date_str, rates)
# 2023-12-29  {'EUR': 0.90498, 'GBP': 0.78647, 'JPY': 141.48}
# 2024-01-02  {'EUR': 0.90832, 'GBP': 0.78758, 'JPY': 141.62}
# ...
```

### Supported currencies list

```python
import json
from helpers import http_get

currencies = json.loads(http_get("https://api.frankfurter.app/currencies"))
# 30 entries: {"AUD": "Australian Dollar", "BRL": "Brazilian Real", ...}
# All 30 can be used as base or target.
```

---

## open.er-api.com — simple latest rates (166 currencies)

No key for latest rates. 166 fiat currencies (no crypto). Updates once daily. Historical data requires a paid registered API key.

### Latest rates

```python
import json
from helpers import http_get

data = json.loads(http_get("https://open.er-api.com/v6/latest/USD"))
# {
#   "result": "success",
#   "base_code": "USD",
#   "time_last_update_utc": "Sun, 19 Apr 2026 00:02:31 +0000",
#   "time_next_update_utc": "Mon, 20 Apr 2026 00:05:01 +0000",
#   "rates": {
#     "USD": 1.0, "EUR": 0.848763, "GBP": 0.739001,
#     "JPY": 158.669348, "CAD": 1.368266, ...166 total
#   }
# }
assert data["result"] == "success"
rates = data["rates"]
print(rates["EUR"])    # 0.848763
print(rates["JPY"])    # 158.669348

# Update schedule
print(data["time_last_update_utc"])   # "Sun, 19 Apr 2026 00:02:31 +0000"
print(data["time_next_update_utc"])   # "Mon, 20 Apr 2026 00:05:01 +0000"
```

Any of the 166 supported currencies can be the base: `/v6/latest/EUR`, `/v6/latest/JPY`, etc. Crypto codes (`BTC`) and metals (`XAU`) return `{"result": "error", "error-type": "unsupported-code"}`.

---

## Cross-rate calculation (any pair)

None of these APIs return arbitrary cross-rates directly (e.g., GBP/JPY). Calculate via USD or EUR:

```python
import json
from helpers import http_get

def get_cross_rate(from_ccy: str, to_ccy: str) -> float:
    """Calculate cross-rate using USD as pivot via open.er-api.com."""
    data = json.loads(http_get("https://open.er-api.com/v6/latest/USD"))
    rates = data["rates"]
    # from_ccy/to_ccy = (USD/to_ccy) / (USD/from_ccy)
    return rates[to_ccy] / rates[from_ccy]

print(get_cross_rate("GBP", "JPY"))   # ~214.7
print(get_cross_rate("EUR", "CHF"))   # ~0.921
```

Alternatively, Frankfurter accepts any of its 30 currencies as `from=`:
```python
data = json.loads(http_get("https://api.frankfurter.app/latest?from=GBP&to=JPY,CHF,AUD"))
print(data["rates"]["JPY"])    # 215.35
```

---

## Batch: fetch time series for multiple pairs

```python
import json
from datetime import date
from helpers import http_get

def fawazahmed0_range(base: str, start: date, end: date) -> dict[str, dict]:
    """Fetch daily rates for `base` over a date range. Business days only.
    Returns {date_str: {currency: rate, ...}}."""
    from datetime import timedelta
    base = base.lower()
    results = {}
    current = start
    while current <= end:
        version = f"{current.year}.{current.month}.{current.day}"
        url = f"https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{version}/v1/currencies/{base}.json"
        try:
            data = json.loads(http_get(url))
            results[str(current)] = data[base]
        except Exception:
            pass   # weekends/holidays have no data file — skip silently
        current += timedelta(days=1)
    return results

# Note: for long ranges, prefer Frankfurter's built-in time-series endpoint
# (one call vs one-per-day). Frankfurter only covers 30 fiat currencies.
```

---

## Gotchas

**exchangerate.host requires an API key.** Despite being listed as "free", `https://api.exchangerate.host/latest` returns `{"success": false, "error": {"code": 101, "type": "missing_access_key"}}` without a key. Not usable anonymously.

**fawazahmed0 version strings are not zero-padded.** `2024.04.18` returns 404. Use `2024.4.18`. Build the string with `f"{dt.year}.{dt.month}.{dt.day}"` — Python's default int formatting has no leading zeros.

**fawazahmed0 historical only goes back to 2024-03-02.** Attempting versions before `2024.3.2` returns HTTP 404. For pre-2024 historical fiat data, use Frankfurter instead.

**fawazahmed0 base currency key is lowercase.** `data["usd"]` not `data["USD"]`. The URL path is also lowercase: `/currencies/usd.json`.

**Frankfurter dates snap to prior business day.** Requesting `2024-01-01` (New Year's Day) returns data dated `2023-12-29`. The `date` field in the response always shows the actual data date, not your requested date. Always read `data["date"]` to confirm.

**Frankfurter time series start/end dates also snap.** `start_date` and `end_date` in the response may differ from your requested range. Read them from the response, not from your input.

**Frankfurter covers 30 fiat currencies only.** No crypto, no precious metals, no exotic currencies. CNY is supported (despite being outside the ECB basket) but many EM currencies are not. Invalid currency codes return `HTTP 404 {"message": "not found"}`.

**open.er-api.com includes USD in its own rates dict.** `rates["USD"]` is always `1.0` when `base=USD`. This is harmless but don't confuse it for an error.

**open.er-api.com has no historical endpoint on the free tier.** `/v6/history/*` returns HTTP 404 without a registered API key. Use fawazahmed0 or Frankfurter for historical lookups.

**open.er-api.com does not support crypto or metals.** `BTC`, `ETH`, `XAU`, `XAG` as base return `{"result": "error", "error-type": "unsupported-code"}`. Use fawazahmed0 for those.

**All three services observed zero rate-limiting** in tests (5+ rapid-fire calls, all succeeded without throttling). The CDN-backed fawazahmed0 in particular is effectively unlimited for reasonable workloads. Don't abuse it.

**Frankfurter `amount` parameter scales the output, not the base.** `?from=USD&to=EUR&amount=100` returns EUR equivalent of 100 USD in the `rates.EUR` field. Without `amount`, the default is `1.0`.

**SSL certificates may fail with the standard `http_get` from helpers.** If you get `CERTIFICATE_VERIFY_FAILED`, add an SSL context or use `certifi`:
```python
import ssl, urllib.request, json
ctx = ssl.create_default_context()
# or: import certifi; ctx = ssl.create_default_context(cafile=certifi.where())
with urllib.request.urlopen(url, context=ctx) as r:
    data = json.loads(r.read())
```
