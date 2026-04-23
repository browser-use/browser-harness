# OpenSky Network — Real-Time & ADS-B Flight Data

`https://opensky-network.org/api` — live and historical ADS-B/MLAT flight state data. **No browser needed.** All responses are JSON over HTTPS. Anonymous access covers the live states endpoint; historical data and flight records require a free account.

## Do this first

**Use `http_get` with SSL verification disabled** — the OpenSky cert chain fails with Python's default `urllib` on some systems. Wrap once at the top of your script:

```python
import json, ssl, urllib.request, gzip

_ctx = ssl.create_default_context()
_ctx.check_hostname = False
_ctx.verify_mode = ssl.CERT_NONE

def opensky_get(url, username=None, password=None, timeout=20.0):
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}
    if username and password:
        import base64
        creds = base64.b64encode(f"{username}:{password}".encode()).decode()
        headers["Authorization"] = f"Basic {creds}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.decompress(data)
        remaining = r.headers.get("X-Rate-Limit-Remaining")
        return json.loads(data.decode()), remaining
```

---

## State vector field index (position matters — it's an array, not a dict)

Every aircraft in `states` is a 17-element list. Fields are always in this order:

| Index | Name | Type | Units / Notes |
|---|---|---|---|
| 0 | `icao24` | str | ICAO 24-bit hex transponder address, e.g. `"4bb46f"` |
| 1 | `callsign` | str or None | 8-char padded with trailing spaces — always `.strip()` |
| 2 | `origin_country` | str | Derived from ICAO prefix |
| 3 | `time_position` | int or None | Unix epoch of last position update |
| 4 | `last_contact` | int | Unix epoch of last message received |
| 5 | `longitude` | float or None | Degrees WGS-84, −180 to +180 |
| 6 | `latitude` | float or None | Degrees WGS-84, −90 to +90 |
| 7 | `baro_altitude` | float or None | Barometric altitude in **meters** |
| 8 | `on_ground` | bool | True = aircraft reports on ground |
| 9 | `velocity` | float or None | Ground speed in **m/s** |
| 10 | `true_track` | float or None | Track angle degrees clockwise from north |
| 11 | `vertical_rate` | float or None | Climb/descent in **m/s**, negative = descending |
| 12 | `sensors` | list or None | ICAO ids of receivers that contributed (usually None anon) |
| 13 | `geo_altitude` | float or None | GPS/geometric altitude in **meters** |
| 14 | `squawk` | str or None | 4-digit octal transponder code as string, e.g. `"6015"` |
| 15 | `spi` | bool | Special Purpose Indicator (distress flag) |
| 16 | `position_source` | int | 0=ADS-B, 1=ASTERIX, 2=MLAT, 3=FLARM |

---

## Common workflows

### Live states — anonymous, global

```python
obj, remaining = opensky_get("https://opensky-network.org/api/states/all")
print(f"Data timestamp: {obj['time']}  Aircraft: {len(obj['states'])}  Rate limit left: {remaining}")
# Confirmed: ~6300 aircraft worldwide, epoch time matches wall clock
```

### Live states — bounding box (Western Europe)

```python
obj, remaining = opensky_get(
    "https://opensky-network.org/api/states/all"
    "?lamin=45.0&lomin=-5.0&lamax=55.0&lomax=15.0"
)
# Confirmed: ~96 aircraft in bounding box
states = obj["states"]
```

### Live states — filter by one or more ICAO24

Repeat the `icao24` param for multiple aircraft:

```python
# Single
obj, _ = opensky_get("https://opensky-network.org/api/states/all?icao24=4bb46f")
# Returns {'time': ..., 'states': None} when aircraft not currently visible

# Multiple
icaos = ["4bb46f", "440209", "471f00"]
params = "&".join(f"icao24={i}" for i in icaos)
obj, _ = opensky_get(f"https://opensky-network.org/api/states/all?{params}")
# Confirmed: returns exactly the matching aircraft
```

### Parse state vectors into dicts

```python
obj, _ = opensky_get(
    "https://opensky-network.org/api/states/all"
    "?lamin=45.0&lomin=-5.0&lamax=55.0&lomax=15.0"
)

aircraft = []
for s in obj["states"]:
    if s[8]:          # on_ground — skip if you only want airborne
        continue
    if s[7] is None:  # no altitude
        continue
    aircraft.append({
        "icao24":       s[0],
        "callsign":     (s[1] or "").strip(),
        "country":      s[2],
        "lon":          s[5],
        "lat":          s[6],
        "baro_alt_m":   s[7],
        "baro_alt_ft":  s[7] / 0.3048,
        "velocity_ms":  s[9],
        "heading_deg":  s[10],
        "vert_rate_ms": s[11],   # None if unknown
        "squawk":       s[14],
        "source":       s[16],   # 0=ADS-B
    })

# Sort by altitude descending
aircraft.sort(key=lambda x: x["baro_alt_m"], reverse=True)
for a in aircraft[:5]:
    print(f"{a['icao24']}  {a['callsign']:8s}  alt={a['baro_alt_ft']:.0f}ft  vel={a['velocity_ms']:.0f}m/s")
# Confirmed output (Western Europe box):
# 4bb46f  MNB213    alt=39000ft  vel=258m/s
# 4bccaf  SXS7KN    alt=39000ft  vel=237m/s
# 4bce1a  SXS3WE    alt=39000ft  vel=242m/s
```

### Authenticated endpoints (account required)

Register free at `https://opensky-network.org/index.php?option=com_users&view=registration`. Pass credentials as HTTP Basic Auth.

```python
USERNAME = "your_username"
PASSWORD = "your_password"

# Arrivals at Frankfurt airport — time window as Unix epoch
obj, _ = opensky_get(
    "https://opensky-network.org/api/flights/arrival"
    "?airport=EDDF&begin=1517227200&end=1517313600",
    username=USERNAME, password=PASSWORD
)
# Returns list of flight records (not state vectors)

# Departures
obj, _ = opensky_get(
    "https://opensky-network.org/api/flights/departure"
    "?airport=EDDF&begin=1517227200&end=1517313600",
    username=USERNAME, password=PASSWORD
)

# Track for a specific aircraft at a given time
obj, _ = opensky_get(
    "https://opensky-network.org/api/tracks/all?icao24=3c6444&time=0",
    username=USERNAME, password=PASSWORD
)
# time=0 returns the most recent track

# Historical states at a past time (authenticated only)
obj, _ = opensky_get(
    "https://opensky-network.org/api/states/all"
    "?time=1517227200&lamin=45.0&lomin=-5.0&lamax=55.0&lomax=15.0",
    username=USERNAME, password=PASSWORD
)
```

### Rate limit check

```python
obj, remaining = opensky_get(
    "https://opensky-network.org/api/states/all?lamin=51.0&lomin=-0.5&lamax=52.0&lomax=1.0"
)
print(f"Requests remaining in window: {remaining}")
# Anonymous pool: ~400 per day (resets daily). No per-minute window observed.
# Authenticated accounts get higher limits.
```

---

## Gotchas

**SSL cert verification fails with Python's default opener on some systems.** `opensky-network.org` uses a cert chain that may not be trusted by the system store. Always create an `ssl.SSLContext` with `check_hostname=False` / `CERT_NONE` as shown above, or install `certifi` and pass `cafile=certifi.where()`.

**`states` is `None` when no aircraft match**, not an empty list. Always guard: `for s in (obj.get("states") or []):`.

**`icao24=` filter returns `None` states when the aircraft is not currently transmitting.** Even valid ICAO24s return `{'time': ..., 'states': None}` if the aircraft is out of coverage or on the ground with transponder off.

**Callsign is padded to 8 characters with trailing spaces.** `"MBU6146 "` not `"MBU6146"`. Always `.strip()`.

**All altitudes are in meters, not feet.** Convert: `feet = meters / 0.3048`. Barometric (`baro_altitude`, index 7) and geometric GPS (`geo_altitude`, index 13) differ by 10–200 m in cruise.

**Velocity is ground speed in m/s, not knots.** Convert: `knots = m_per_s * 1.944`.

**`squawk` is a string, not an int.** `"6015"`, `"7700"`, etc. Leading zeros are preserved. Parse as string, not int.

**`baro_altitude` is `None` for grounded aircraft** (when `on_ground=True`). `geo_altitude` and `vertical_rate` are also frequently `None`. The `sensors` field (index 12) is always `None` in anonymous responses.

**Historical states (`?time=...`) require authentication.** Anonymous requests with a `time` parameter return HTTP 403, not an empty result.

**Flights and tracks endpoints require authentication.** Anonymous calls return HTTP 403 for flights and HTTP 404 for tracks.

**The `time` field in the response is a Unix epoch integer (seconds), not milliseconds.** Use `datetime.utcfromtimestamp(obj['time'])` to convert.

**Rate limit is tracked by `X-Rate-Limit-Remaining` response header.** Anonymous pool is approximately 400 requests per day per IP. There is no observed per-minute throttle for anonymous state queries — rapid sequential calls are allowed until the daily pool depletes.

**Bounding box params are `lamin`, `lamax`, `lomin`, `lomax`** — latitude min/max, longitude min/max. Order matters: `lamin` < `lamax`, `lomin` < `lomax`. The API does not validate reversed bounds; it simply returns no results.

**Multiple `icao24=` params must be repeated, not comma-separated.** `?icao24=abc&icao24=def` works. `?icao24=abc,def` does not match anything.
