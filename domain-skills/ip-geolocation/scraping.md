# IP Geolocation APIs — Data Extraction

Three tested free-tier services, no browser needed. Best free option: **ip-api.com** (no key, 45 req/min, HTTP only). Use **ipinfo.io** when HTTPS is required without a key.

All calls use `http_get` from helpers — no browser, no JS, pure HTTP.

## Do this first: pick your service

| Service | Key required | HTTPS free | Rate limit (free) | Batch | Proxy/mobile/hosting detect |
|---|---|---|---|---|---|
| **ip-api.com** | No | No (HTTP only; HTTPS = paid) | 45 req/min | Yes, 100 IPs/call | Yes (free) |
| **ipinfo.io** | No (basic) | Yes | 50K req/month | No (token required) | No (paid) |
| **ipgeolocation.io** | Yes (free tier) | Yes | 1K req/day (free) | Yes (paid) | Yes (paid) |
| **abstractapi.com** | Yes (free tier) | Yes | 1K req/month (free) | No | Yes (paid) |

**Never use a browser for any of these.** All return JSON over HTTP/HTTPS.

---

## ip-api.com — best free option (no key)

### Single IP lookup

```python
import json
from helpers import http_get

data = json.loads(http_get("http://ip-api.com/json/8.8.8.8"))
# Confirmed output (2026-04-18):
# {
#   "status": "success",
#   "country": "United States",
#   "countryCode": "US",
#   "region": "VA",
#   "regionName": "Virginia",
#   "city": "Ashburn",
#   "zip": "20149",
#   "lat": 39.03,
#   "lon": -77.5,
#   "timezone": "America/New_York",
#   "isp": "Google LLC",
#   "org": "Google Public DNS",
#   "as": "AS15169 Google LLC",
#   "query": "8.8.8.8"
# }
assert data["status"] == "success"
print(data["city"], data["countryCode"])    # Ashburn US
print(data["lat"], data["lon"])             # 39.03 -77.5
print(data["isp"], data["as"])              # Google LLC  AS15169 Google LLC
```

### Own IP (omit the IP segment)

```python
import json
from helpers import http_get

data = json.loads(http_get("http://ip-api.com/json/"))
print(data["query"])    # your public IP address
print(data["city"], data["regionName"], data["countryCode"])
```

### All available fields (including proxy/mobile/hosting detection)

```python
import json
from helpers import http_get

FIELDS = "status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,asname,reverse,mobile,proxy,hosting,query"
data = json.loads(http_get(f"http://ip-api.com/json/9.9.9.9?fields={FIELDS}"))
# Confirmed extra fields for 9.9.9.9 (Quad9 DNS):
# "asname": "QUAD9-AS-1"
# "reverse": "dns9.quad9.net"
# "mobile": False          — not a mobile network
# "proxy": False           — not a known proxy/VPN
# "hosting": False         — not a datacenter/hosting range
# Note: 8.8.8.8 returns "hosting": True (Google datacenter)
```

### Batch lookup — up to 100 IPs per call

Single POST to `/batch` beats parallel individual calls for throughput.

```python
import json, urllib.request
from helpers import http_get

ips = ["8.8.8.8", "1.1.1.1", "9.9.9.9"]

data = json.dumps(ips).encode()
req = urllib.request.Request(
    "http://ip-api.com/batch",
    data=data,
    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
)
with urllib.request.urlopen(req, timeout=20) as r:
    results = json.loads(r.read().decode())
    remaining = r.headers.get("X-Rl")    # requests left in current minute window
    ttl       = r.headers.get("X-Ttl")   # seconds until window resets

for item in results:
    if item["status"] == "success":
        print(item["query"], item["city"], item["countryCode"], item["isp"])
# Confirmed output:
# 8.8.8.8  Ashburn   US  Google LLC
# 1.1.1.1  South Brisbane  AU  Cloudflare, Inc
# 9.9.9.9  Berkeley  US  Quad9
```

### Batch with per-IP field filtering and language

```python
import json, urllib.request

payload = [
    {"query": "8.8.8.8",  "fields": "status,country,city,lat,lon,isp", "lang": "de"},
    {"query": "1.1.1.1",  "fields": "status,country,city,lat,lon,isp", "lang": "de"},
]
data = json.dumps(payload).encode()
req = urllib.request.Request(
    "http://ip-api.com/batch",
    data=data,
    headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
)
with urllib.request.urlopen(req, timeout=20) as r:
    results = json.loads(r.read().decode())
# Returns country names in German: "Vereinigte Staaten", "Australien"
```

Supported `lang` values: `en` (default), `de`, `es`, `pt-BR`, `fr`, `ja`, `zh-CN`, `ru`.

### Chunked bulk lookup (> 100 IPs)

```python
import json, urllib.request, time

def ip_api_bulk(ips: list[str], fields: str = None, sleep_between=0.0) -> list[dict]:
    """Look up any number of IPs in batches of 100."""
    results = []
    chunk_size = 100
    for i in range(0, len(ips), chunk_size):
        chunk = ips[i:i + chunk_size]
        payload = chunk
        if fields:
            payload = [{"query": ip, "fields": fields} for ip in chunk]
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            "http://ip-api.com/batch",
            data=data,
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            batch = json.loads(r.read().decode())
            remaining = int(r.headers.get("X-Rl", 45))
            ttl = int(r.headers.get("X-Ttl", 60))
            results.extend(batch)
        # Only sleep if nearly rate-limited (< 5 requests left in window)
        if remaining < 5:
            time.sleep(ttl + 1)
        elif sleep_between:
            time.sleep(sleep_between)
    return results
```

### Rate limit headers

Every response carries:
- `X-Rl` — integer, requests remaining in the current 60-second window (starts at 45)
- `X-Ttl` — integer seconds until the window resets

```python
import json, urllib.request

req = urllib.request.Request("http://ip-api.com/json/8.8.8.8", headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=20) as r:
    data   = json.loads(r.read().decode())
    rl     = int(r.headers.get("X-Rl",  45))   # e.g. 44
    ttl    = int(r.headers.get("X-Ttl", 60))   # e.g. 60
```

---

## ipinfo.io — best free HTTPS option (no key for basic)

Returns fewer fields than ip-api.com but works over HTTPS without a token for up to ~50K req/month.

### Single IP lookup

```python
import json
from helpers import http_get

data = json.loads(http_get("https://ipinfo.io/8.8.8.8/json"))
# Confirmed output (2026-04-18):
# {
#   "ip": "8.8.8.8",
#   "hostname": "dns.google",
#   "city": "Mountain View",
#   "region": "California",
#   "country": "US",
#   "loc": "37.4056,-122.0775",    ← combined "lat,lon" string, NOT separate fields
#   "org": "AS15169 Google LLC",   ← ASN + org name combined
#   "postal": "94043",
#   "timezone": "America/Los_Angeles",
#   "readme": "https://ipinfo.io/missingauth",   ← appears when no token; data still valid
#   "anycast": true
# }

lat, lon = map(float, data["loc"].split(","))    # split "37.4056,-122.0775"
asn, org = data["org"].split(" ", 1)             # "AS15169" and "Google LLC"
```

### Own IP

```python
import json
from helpers import http_get

data = json.loads(http_get("https://ipinfo.io/json"))
print(data["ip"], data["city"], data["country"])
```

### Single-field endpoints (ultra-lightweight)

```python
from helpers import http_get

country  = http_get("https://ipinfo.io/8.8.8.8/country").strip()   # "US"
city     = http_get("https://ipinfo.io/8.8.8.8/city").strip()      # "Mountain View"
org      = http_get("https://ipinfo.io/8.8.8.8/org").strip()       # "AS15169 Google LLC"
```

Returns plain text, not JSON. Strip trailing newline.

---

## ipgeolocation.io — key required (free tier available)

Requires API key (free tier: 1,000 req/day). Sign up at `https://app.ipgeolocation.io/login`.

```python
import json
from helpers import http_get

API_KEY = "YOUR_KEY_HERE"
data = json.loads(http_get(f"https://api.ipgeolocation.io/ipgeo?apiKey={API_KEY}&ip=8.8.8.8"))
# Returns: ip, continent_code, country_name, country_code2, state_prov,
#          city, zipcode, latitude, longitude, isp, organization,
#          time_zone.name, currency.code, languages, calling_code
```

Without a key: `HTTP 401 {"message": "Please provide an API key..."}`.

---

## abstractapi.com — key required (free tier available)

Free tier: 1,000 req/month. Sign up at `https://app.abstractapi.com/`.

```python
import json
from helpers import http_get

API_KEY = "YOUR_KEY_HERE"
data = json.loads(http_get(
    f"https://ipgeolocation.abstractapi.com/v1/?api_key={API_KEY}&ip_address=8.8.8.8"
))
# Returns: ip_address, city, city_geoname_id, region, region_geoname_id,
#          postal_code, country, country_code, country_geoname_id,
#          latitude, longitude, is_vpn, connection.*, timezone.*, flag.*
```

Without a key: `HTTP 401 {"error": {"message": "Invalid API key provided.", "code": "unauthorized"}}`.

---

## Comparison: field coverage

| Field | ip-api.com | ipinfo.io | ipgeolocation.io |
|---|---|---|---|
| IP | `query` | `ip` | `ip` |
| City | `city` | `city` | `city` |
| Region/State | `regionName` + `region` (code) | `region` (full name only) | `state_prov` |
| Country | `country` + `countryCode` | `country` (code only) | `country_name` + `country_code2` |
| Latitude | `lat` (float) | first part of `loc` (string) | `latitude` (string) |
| Longitude | `lon` (float) | second part of `loc` (string) | `longitude` (string) |
| Timezone | `timezone` | `timezone` | `time_zone.name` |
| ISP | `isp` | part of `org` | `isp` |
| ASN | `as` (combined) | part of `org` | `asn` |
| Hostname/reverse | `reverse` | `hostname` | — |
| Proxy/VPN detect | `proxy` (free) | — (paid) | `threat.*` (paid) |
| Mobile detect | `mobile` (free) | — (paid) | — |
| Hosting/datacenter | `hosting` (free) | — (paid) | — |
| Anycast flag | — | `anycast` (free) | — |
| Currency | — | — | `currency.code` |

---

## Complete end-to-end pattern: enrich a list of IPs

```python
import json, urllib.request, time

def enrich_ips(ips: list[str]) -> list[dict]:
    """Return geolocation data for up to 100 IPs in one call.
    
    Returns list of dicts. Failed lookups have status='fail' and message field.
    """
    payload = json.dumps(ips).encode()
    req = urllib.request.Request(
        "http://ip-api.com/batch",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        results = json.loads(r.read().decode())
        remaining = int(r.headers.get("X-Rl", 45))
        if remaining < 5:
            ttl = int(r.headers.get("X-Ttl", 60))
            time.sleep(ttl + 1)
    return results


# Usage
ips = ["8.8.8.8", "1.1.1.1", "192.168.1.1", "9.9.9.9"]
rows = enrich_ips(ips)
for row in rows:
    if row["status"] == "success":
        print(f"{row['query']:16s}  {row['city']:20s}  {row['countryCode']}  {row['isp']}")
    else:
        print(f"{row['query']:16s}  FAILED: {row['message']}")
# Confirmed output:
# 8.8.8.8           Ashburn               US  Google LLC
# 1.1.1.1           South Brisbane        AU  Cloudflare, Inc
# 192.168.1.1       FAILED: private range
# 9.9.9.9           Berkeley              US  Quad9
```

---

## Gotchas

**ip-api.com HTTPS is paid.** `https://ip-api.com/json/8.8.8.8` returns `HTTP 403 {"status":"fail","message":"SSL unavailable for this endpoint, order a key at https://members.ip-api.com/"}`. Always use `http://` for the free tier.

**ip-api.com rate limit is 45 req/min per IP address** (not per key). The batch endpoint counts as 1 request regardless of how many IPs are in the payload. Sending 100 IPs in one POST uses 1 of your 45 requests. Track `X-Rl` and sleep when it approaches 0.

**ip-api.com batch max is 100 IPs.** Sending 101 returns `HTTP 422 Unprocessable Entity` (empty body). Chunk at 100.

**ip-api.com private/reserved IPs return `status: "fail"`, not an error.** `192.168.x.x`, `10.x.x.x`, `127.x.x.x`, `::1` all return `{"status":"fail","message":"private range","query":"..."}`. Always check `data["status"] == "success"` before reading geo fields.

**ip-api.com invalid IPs return `status: "fail"` too.** `{"status":"fail","message":"invalid query","query":"..."}`. HTTP status is still 200.

**ip-api.com `fields` param filters the JSON keys in the response.** Use it to reduce payload size when you only need a subset. Both named fields (`fields=city,country`) and numeric bitmask (`fields=61439`) work. If `fields` omits `status`, a failed lookup returns an empty object `{}`.

**ipinfo.io `loc` is a combined `"lat,lon"` string**, not two separate fields. Always split: `lat, lon = map(float, data["loc"].split(","))`.

**ipinfo.io `org` combines ASN and org name**: `"AS15169 Google LLC"`. Split on first space to separate them: `asn, name = data["org"].split(" ", 1)`.

**ipinfo.io `readme` key appears when no token is provided.** Its presence does not indicate an error — the data is still valid. The field simply points to the auth docs.

**ipinfo.io `anycast` key is only present for anycast IPs** (e.g., `8.8.8.8`, `1.1.1.1`). Use `.get("anycast", False)` — don't assume it's always in the response.

**ipinfo.io single-field endpoints return plain text, not JSON.** `https://ipinfo.io/8.8.8.8/country` returns `US\n`. Always `.strip()` before use.

**ipinfo.io batch requires a token.** `POST https://ipinfo.io/batch` with a payload returns `{"error":"API token required"}` without a token. For free batch lookups use ip-api.com instead.

**ipgeolocation.io and abstractapi.com require signup even for free use.** Both return `HTTP 401` immediately without a key — there is no anonymous/no-key path. Use ip-api.com or ipinfo.io for keyless access.

**ip-api.com returns `lat`/`lon` as JSON floats.** ipinfo.io returns them as a single `"lat,lon"` string inside `loc`. ipgeolocation.io returns them as numeric strings (`"37.4056"`). Normalize to float before any math.
