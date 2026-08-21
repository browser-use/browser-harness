# World Time APIs — Current Time & Timezone Data

No-browser, JSON-over-HTTP APIs for current time, UTC offsets, and DST detection. All work with `http_get`. Confirmed live 2026-04-18.

| API | Base URL | Auth | IANA zones | Rate limit |
|-----|----------|------|------------|------------|
| WorldTimeAPI | `worldtimeapi.org` | None | ~400 | ~1 req/s (informal) |
| TimeAPI.io | `timeapi.io` | None | 597 | None documented |
| WorldClockAPI | `worldclockapi.com` | None | ~10 fixed codes | None documented |
| TimezoneDB | `api.timezonedb.com` | Free API key | 400+ | 1 req/s free tier |

**Status as of 2026-04-18:** WorldTimeAPI (`worldtimeapi.org`) is currently returning TLS/connection resets on both HTTP and HTTPS — the API is unreachable. Use **TimeAPI.io** as the primary no-key alternative; it supports the same IANA zone names and returns richer DST data.

---

## WorldTimeAPI (when available)

WorldTimeAPI is the canonical reference; the endpoints below match its documented spec. If it comes back online, the HTTP (not HTTPS) endpoint was historically more reliable on some client stacks.

### Documented response shape

```python
import json

# GET http://worldtimeapi.org/api/timezone/America/New_York
# Returns:
{
    "abbreviation": "EDT",           # current timezone abbreviation
    "client_ip": "1.2.3.4",
    "datetime": "2024-06-15T10:23:45.123456-04:00",  # ISO8601 with offset
    "day_of_week": 6,               # 0=Sunday … 6=Saturday
    "day_of_year": 167,
    "dst": True,                    # DST currently active?
    "dst_from": "2024-03-10T07:00:00+00:00",  # DST start (UTC), null if no DST
    "dst_offset": 3600,             # DST offset in seconds (0 if no DST)
    "dst_until": "2024-11-03T06:00:00+00:00", # DST end (UTC), null if no DST
    "raw_offset": -18000,           # standard UTC offset in seconds (no DST)
    "timezone": "America/New_York",
    "unixtime": 1718447025,
    "utc_datetime": "2024-06-15T14:23:45.123456+00:00",
    "utc_offset": "-04:00",         # current UTC offset string (includes DST)
    "week_number": 24
}
```

### List all available timezones

```python
import json

# GET http://worldtimeapi.org/api/timezone
zones = json.loads(http_get("http://worldtimeapi.org/api/timezone"))
# Returns a flat list of IANA strings:
# ["Africa/Abidjan", "Africa/Accra", ..., "UTC"]
print(len(zones))   # ~400 zones

# Filter to US zones:
us_zones = [z for z in zones if z.startswith("America/")]
```

### By caller IP (auto-detect timezone)

```python
import json

data = json.loads(http_get("http://worldtimeapi.org/api/ip"))
# Returns same shape as /api/timezone/{zone}
# timezone field reflects IP geolocation — not reliable inside cloud/VPN
print(data["timezone"])     # e.g. "America/New_York"
print(data["utc_offset"])   # e.g. "-04:00"
```

---

## TimeAPI.io (confirmed working, no key)

Drop-in replacement for WorldTimeAPI. Uses full IANA zone names. 597 supported zones.

### Current time in a zone

```python
import json

data = json.loads(http_get(
    "https://timeapi.io/api/Time/current/zone?timeZone=America/New_York"
))

# Confirmed live response (2026-04-18):
# data["year"]          2026
# data["month"]         4
# data["day"]           18
# data["hour"]          21
# data["minute"]        49
# data["seconds"]       42
# data["milliSeconds"]  630
# data["dateTime"]      "2026-04-18T21:49:42.6309083"
# data["date"]          "04/18/2026"
# data["time"]          "21:49"
# data["timeZone"]      "America/New_York"
# data["dayOfWeek"]     "Saturday"
# data["dstActive"]     True

print(data["dateTime"], data["timeZone"])
print("DST active:", data["dstActive"])
```

### Timezone info with UTC offsets and DST window

```python
import json

info = json.loads(http_get(
    "https://timeapi.io/api/timezone/zone?timeZone=America/New_York"
))

# Confirmed live (2026-04-18, during EDT):
# info["timeZone"]                        "America/New_York"
# info["currentLocalTime"]                "2026-04-18T21:49:52.4722691"
# info["currentUtcOffset"]["seconds"]     -14400   # -4 hours (EDT)
# info["standardUtcOffset"]["seconds"]    -18000   # -5 hours (EST, no DST)
# info["hasDayLightSaving"]               True
# info["isDayLightSavingActive"]          True
# info["dstInterval"]["dstName"]          "EDT"
# info["dstInterval"]["dstStart"]         "2026-03-08T07:00:00Z"
# info["dstInterval"]["dstEnd"]           "2026-11-01T06:00:00Z"
# info["dstInterval"]["dstOffsetToStandardTime"]["seconds"]  3600  # +1 hour

# For a non-DST zone (Tokyo):
# info["hasDayLightSaving"]              False
# info["isDayLightSavingActive"]         False
# info["dstInterval"]                    None

# Extract current UTC offset in hours:
offset_hours = info["currentUtcOffset"]["seconds"] / 3600
print(f"UTC{offset_hours:+.0f}")   # UTC-4

# Detect DST:
is_dst = info["isDayLightSavingActive"]

# DST offset vs standard (seconds):
dst_shift = info["currentUtcOffset"]["seconds"] - info["standardUtcOffset"]["seconds"]
# → 3600 when DST active, 0 when not
```

### DST detection pattern

```python
import json

def get_utc_offset(zone: str) -> dict:
    """Returns current and standard UTC offset, DST flag, and DST name."""
    info = json.loads(http_get(
        f"https://timeapi.io/api/timezone/zone?timeZone={zone}"
    ))
    current_offset_s  = info["currentUtcOffset"]["seconds"]
    standard_offset_s = info["standardUtcOffset"]["seconds"]
    dst_active        = info["isDayLightSavingActive"]
    dst_name          = info["dstInterval"]["dstName"] if dst_active else None

    return {
        "zone":             zone,
        "offset_hours":     current_offset_s / 3600,
        "standard_hours":   standard_offset_s / 3600,
        "dst_active":       dst_active,
        "dst_name":         dst_name,
        "dst_start":        info["dstInterval"]["dstStart"] if dst_active else None,
        "dst_end":          info["dstInterval"]["dstEnd"]   if dst_active else None,
    }

# Confirmed live (2026-04-18):
ny  = get_utc_offset("America/New_York")
# → {'offset_hours': -4.0, 'standard_hours': -5.0, 'dst_active': True, 'dst_name': 'EDT', ...}
tok = get_utc_offset("Asia/Tokyo")
# → {'offset_hours': 9.0, 'standard_hours': 9.0, 'dst_active': False, 'dst_name': None, ...}
lon = get_utc_offset("Europe/London")
# → {'offset_hours': 1.0, 'standard_hours': 0.0, 'dst_active': True, 'dst_name': 'BST', ...}
```

### Convert time between zones

```python
import json

# POST endpoint — converts a specific datetime from one zone to another
import urllib.request

body = json.dumps({
    "fromTimeZone": "America/New_York",
    "dateTime":     "2026-04-18 12:00:00",
    "toTimeZone":   "Europe/London",
    "dstAmbiguity": ""
}).encode()

req = urllib.request.Request(
    "https://timeapi.io/api/Conversion/convertTimeZone",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=20) as r:
    result = json.loads(r.read())

# Confirmed live (2026-04-18, both in DST):
# result["fromTimezone"]                       "America/New_York"
# result["fromDateTime"]                       "2026-04-18T12:00:00"
# result["toTimeZone"]                         "Europe/London"
# result["conversionResult"]["dateTime"]       "2026-04-18T17:00:00"
# result["conversionResult"]["dstActive"]      True
# result["conversionResult"]["timeZone"]       "Europe/London"

print(result["conversionResult"]["dateTime"])   # "2026-04-18T17:00:00"
```

### Current time by IP address

```python
import json

# IP address → timezone → current time
data = json.loads(http_get(
    "https://timeapi.io/api/Time/current/ip?ipAddress=8.8.8.8"
))
# Confirmed: 8.8.8.8 → America/Los_Angeles
# Same response shape as /current/zone

print(data["timeZone"])     # "America/Los_Angeles"
print(data["dateTime"])     # "2026-04-18T18:51:05.5840305"
print(data["dstActive"])    # True
```

### List all supported timezones

```python
import json

zones = json.loads(http_get(
    "https://timeapi.io/api/timezone/availabletimezones"
))
# Returns a flat JSON array of 597 IANA zone strings (confirmed 2026-04-18)
# ["Africa/Abidjan", "Africa/Accra", ..., "UTC", "W-SU", "WET", "Zulu"]

print(len(zones))   # 597
us_zones = [z for z in zones if z.startswith("America/")]
print(us_zones[:5]) # ['America/Adak', 'America/Anchorage', ...]
```

---

## WorldClockAPI (simple, HTTP only)

Fixed set of ~10 named zones. No IANA names — use only for UTC/EST/PST/etc. shorthand lookups.

### Current time

```python
import json

# HTTP only — HTTPS not supported
data = json.loads(http_get("http://worldclockapi.com/api/json/utc/now"))

# Confirmed response (2026-04-18):
# data["currentDateTime"]       "2026-04-19T01:50Z"   (ISO8601, offset appended for non-UTC)
# data["utcOffset"]             "00:00:00"             (HH:MM:SS string)
# data["isDayLightSavingsTime"] False
# data["dayOfTheWeek"]          "Sunday"
# data["timeZoneName"]          "UTC"
# data["currentFileTime"]       134210370220836830     (Windows FILETIME — ignore)
# data["ordinalDate"]           "2026-109"             (YYYY-DDD)
# data["serviceResponse"]       None                   (non-null = error message)

print(data["currentDateTime"])          # "2026-04-19T01:50Z"
print(data["utcOffset"])                # "00:00:00"
print(data["isDayLightSavingsTime"])    # False

# EST zone — currentDateTime includes offset
est = json.loads(http_get("http://worldclockapi.com/api/json/est/now"))
print(est["currentDateTime"])   # "2026-04-18T21:50-04:00"
print(est["utcOffset"])         # "-04:00:00"
print(est["isDayLightSavingsTime"])  # True  (confirming EDT is active)
```

### Confirmed valid zone codes

```python
# Confirmed working (2026-04-18):
WORLDCLOCK_ZONES = {
    "utc":  "UTC",
    "gmt":  "GMT Standard Time",        # UTC+1 during BST
    "est":  "Eastern Standard Time",    # UTC-4 during EDT
    "cst":  "Central Standard Time",    # UTC-5 during CDT
    "mst":  "Mountain Standard Time",   # UTC-6 during MDT
    "pst":  "Pacific Standard Time",    # UTC-7 during PDT
    "cet":  "Central Europe Standard Time",  # UTC+2 during CEST
    "nst":  "Newfoundland Standard Time",
}

# Invalid (confirmed errors): jst, ist, bst, aest, hst, akt, sydney
# Error response: data["serviceResponse"] = "{code} is not a valid Time Zone"
#                 data["currentDateTime"] = None

for code in WORLDCLOCK_ZONES:
    data = json.loads(http_get(f"http://worldclockapi.com/api/json/{code}/now"))
    print(code, data["utcOffset"], data["isDayLightSavingsTime"])
```

---

## TimezoneDB (free key required)

Register at `https://timezonedb.com` for a free key. 1 req/s on free tier.

### Get timezone info

```python
import json

API_KEY = "YOUR_KEY"  # register free at timezonedb.com

data = json.loads(http_get(
    f"https://api.timezonedb.com/v2.1/get-time-zone"
    f"?key={API_KEY}&format=json&by=zone&zone=America/New_York"
))

# Response shape (from API docs — key required to verify live):
# data["status"]          "OK"          (or "FAILED" with error message)
# data["countryCode"]     "US"
# data["countryName"]     "United States"
# data["regionName"]      "New York"
# data["cityName"]        "New York"
# data["zoneName"]        "America/New_York"
# data["abbreviation"]    "EDT"
# data["gmtOffset"]       -14400        # current UTC offset in seconds
# data["dst"]             1             # 1=DST active, 0=not
# data["zoneStart"]       1710054000    # unix timestamp when this offset started
# data["zoneEnd"]         1730613600    # unix timestamp when this offset ends
# data["nextAbbreviation"] "EST"
# data["timestamp"]       1718447025    # current unix time
# data["formatted"]       "2024-06-15 10:23:45"

if data["status"] == "OK":
    offset_hours = data["gmtOffset"] / 3600
    print(f"UTC{offset_hours:+.0f}, DST={bool(data['dst'])}")

# Lookup by lat/lon instead of zone name:
data = json.loads(http_get(
    f"https://api.timezonedb.com/v2.1/get-time-zone"
    f"?key={API_KEY}&format=json&by=position&lat=40.71&lng=-74.01"
))

# List all zones:
zones = json.loads(http_get(
    f"https://api.timezonedb.com/v2.1/list-time-zone"
    f"?key={API_KEY}&format=json&fields=countryCode,zoneName,gmtOffset"
))
# zones["zones"] — list of dicts with countryCode, zoneName, gmtOffset
```

---

## End-to-end: compare current time across multiple zones

```python
import json

ZONES = [
    "America/New_York",
    "Europe/London",
    "Europe/Paris",
    "Asia/Tokyo",
    "Australia/Sydney",
    "UTC",
]

def zone_snapshot(zone: str) -> dict:
    """Current time + UTC offset + DST for any IANA zone."""
    data = json.loads(http_get(
        f"https://timeapi.io/api/Time/current/zone?timeZone={zone}"
    ))
    info = json.loads(http_get(
        f"https://timeapi.io/api/timezone/zone?timeZone={zone}"
    ))
    offset_h = info["currentUtcOffset"]["seconds"] / 3600
    return {
        "zone":       zone,
        "datetime":   data["dateTime"][:19],  # trim microseconds
        "weekday":    data["dayOfWeek"],
        "utc_offset": f"UTC{offset_h:+.1f}".replace(".0", ""),
        "dst":        data["dstActive"],
        "dst_name":   info["dstInterval"]["dstName"] if data["dstActive"] else None,
    }

for zone in ZONES:
    snap = zone_snapshot(zone)
    dst_tag = f" ({snap['dst_name']})" if snap["dst"] else ""
    print(f"{snap['zone']:25s}  {snap['datetime']}  {snap['utc_offset']}{dst_tag}")

# Example output (2026-04-18):
# America/New_York           2026-04-18T21:49:42  UTC-4 (EDT)
# Europe/London              2026-04-19T02:49:51  UTC+1 (BST)
# Europe/Paris               2026-04-19T03:49:51  UTC+2 (CEST)
# Asia/Tokyo                 2026-04-19T10:49:51  UTC+9
# Australia/Sydney           2026-04-19T11:49:51  UTC+10
# UTC                        2026-04-19T01:49:51  UTC+0
```

Two API calls per zone (current + timezone info). For bulk, batch the `timezone/zone` calls first.

---

## Gotchas

**WorldTimeAPI is currently down (2026-04-18).** Both HTTP and HTTPS return `Connection reset by peer` at the TLS layer. Use TimeAPI.io instead — it accepts the same IANA zone names and returns equivalent data with additional DST window fields.

**WorldTimeAPI used HTTP, not HTTPS.** Historically the documented base was `http://worldtimeapi.org` (plain HTTP). Calling it with HTTPS caused SSL errors on some clients even when the server was up.

**TimeAPI.io `currentDateTime` has trailing microseconds** — truncate to 19 chars (`[:19]`) for a clean `YYYY-MM-DDTHH:MM:SS` string.

**UTC offset is in seconds, not hours.** `currentUtcOffset["seconds"]` is `-14400` for EDT. Divide by 3600 to get hours. Do NOT use `milliseconds` or `ticks` — they are the same value scaled, not separate fields.

**DST detection: compare `currentUtcOffset` vs `standardUtcOffset`.** If `currentUtcOffset["seconds"] != standardUtcOffset["seconds"]`, DST is active. The `isDayLightSavingActive` field does the same check — prefer it directly.

**`isDayLightSavingActive=True` does NOT mean DST is always active.** Tokyo (`Asia/Tokyo`) returns `hasDayLightSaving=False` and `dstInterval=null`. `isDayLightSavingActive` is always False for zones without DST rules.

**TimeAPI.io returns `"Invalid Timezone"` (a plain string, not JSON object)** for unknown zone names. Wrap in a try/except:
```python
try:
    data = json.loads(http_get(f"https://timeapi.io/api/Time/current/zone?timeZone={zone}"))
    if isinstance(data, str):
        raise ValueError(f"Invalid timezone: {zone}")
except Exception as e:
    print(f"Error: {e}")
```

**WorldClockAPI uses HTTP only** — HTTPS is not supported. The zone codes are short abbreviations (`est`, `utc`, `cet`), not IANA names. Many common codes (`jst`, `ist`, `bst`, `aest`) are invalid. Check `data["serviceResponse"]` for errors — `currentDateTime` will be `None` on error.

**WorldClockAPI `isDayLightSavingsTime` is unreliable** — the zone is labelled "Eastern Standard Time" year-round, but during EDT `isDayLightSavingsTime=True` and the offset correctly shows `-04:00`. The name does not update to "Eastern Daylight Time".

**TimezoneDB requires a free API key.** Register at `https://timezonedb.com`. Free tier is capped at 1 request/second; paid tiers allow higher throughput. Always check `data["status"] == "OK"` before reading other fields — invalid keys return `status="FAILED"` with zeroed-out numeric fields (not an HTTP error).

**`raw_offset` (WorldTimeAPI) vs `standardUtcOffset` (TimeAPI.io) are the same concept** — the UTC offset without DST applied. Use `utc_offset` / `currentUtcOffset` for the *current* offset which already incorporates DST.

**Rate limits are informal or undocumented.** WorldTimeAPI historically asked for ~1 req/s. TimeAPI.io has no documented limit but may throttle burst traffic. Add `time.sleep(0.5)` between calls when iterating over many zones.
