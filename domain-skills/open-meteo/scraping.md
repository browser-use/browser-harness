# Open-Meteo — Complete API Reference

Free weather data with no API key. Four subdomain APIs tested: **forecast**, **historical archive**, **air quality**, **marine**. All return JSON via `http_get` — no browser needed.

## Quick reference

| Need | Endpoint | Notes |
|------|----------|-------|
| Current conditions + forecast | `api.open-meteo.com/v1/forecast` | Up to 16 days out |
| Historical data (back to 1940) | `archive-api.open-meteo.com/v1/archive` | `start_date` + `end_date` required |
| Air quality / AQI | `air-quality-api.open-meteo.com/v1/air-quality` | PM2.5, PM10, AQI, gases |
| Ocean waves | `marine-api.open-meteo.com/v1/marine` | Coastal coords may return nulls — use open-ocean |
| City name → lat/lon | `geocoding-api.open-meteo.com/v1/search` | Free, no key |

---

## Step 0: city name → coordinates

Required for all other calls unless you already have lat/lon.

```python
import json

geo = json.loads(http_get(
    "https://geocoding-api.open-meteo.com/v1/search?name=Tokyo&count=1"
))
loc = geo['results'][0]
lat = loc['latitude']    # 35.6895
lon = loc['longitude']   # 139.69171
tz  = loc['timezone']    # 'Asia/Tokyo'

# Also available:
# loc['elevation']     44.0 (metres)
# loc['country']       'Japan'
# loc['country_code']  'JP'
# loc['admin1']        'Tokyo' (state/province)
# loc['population']    9733276
```

Always pass `count=1` and take `results[0]`. Returns `{}` (no `results` key) for unknown names.

---

## Current forecast (simplest call)

```python
import json

data = json.loads(http_get(
    "https://api.open-meteo.com/v1/forecast"
    "?latitude=40.71&longitude=-74.01"
    "&current=temperature_2m,wind_speed_10m,precipitation"
    "&timezone=America/New_York"
))

cur   = data['current']        # dict
units = data['current_units']  # dict

# Confirmed live values (2026-04-18, New York):
# cur['time']           '2026-04-18T21:30'   (local ISO8601)
# cur['interval']       900                  (update cadence, seconds)
# cur['temperature_2m'] 9.9                  (°C)
# cur['wind_speed_10m'] 14.1                 (km/h)
# cur['precipitation']  0.0                  (mm)

print(cur['temperature_2m'], units['temperature_2m'])  # 9.9 °C
```

### Extended current — recommended

```python
data = json.loads(http_get(
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={lat}&longitude={lon}"
    f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
    f"precipitation,weathercode,wind_speed_10m,wind_direction_10m,"
    f"wind_gusts_10m,uv_index,surface_pressure,cloud_cover"
    f"&timezone={tz}"
))

cur = data['current']
# All available current variables and their units:
# temperature_2m          °C      apparent_temperature   °C
# relative_humidity_2m    %       precipitation          mm
# weathercode             wmo code int                   (see WMO table below)
# wind_speed_10m          km/h    wind_direction_10m     °
# wind_gusts_10m          km/h    uv_index               (unitless)
# surface_pressure        hPa     cloud_cover            %
# is_day                  1 or 0
```

### Hourly forecast

```python
data = json.loads(http_get(
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={lat}&longitude={lon}"
    f"&hourly=temperature_2m,precipitation_probability,precipitation,"
    f"weathercode,cloud_cover,visibility,wind_speed_10m,wind_gusts_10m"
    f"&forecast_days=3&timezone={tz}"
))

hourly = data['hourly']   # dict of parallel arrays
units  = data['hourly_units']
# hourly['time']  — ISO8601 strings, one per hour: '2026-04-18T00:00', ...
# 3 forecast days → 72 entries. forecast_days max = 16.

for i, t in enumerate(hourly['time'][:24]):  # first day
    print(t,
          hourly['temperature_2m'][i],             # °C
          hourly['precipitation_probability'][i],   # %
          hourly['wind_speed_10m'][i])              # km/h

# Note: visibility is in metres (not km). Divide by 1000 for km.
# Units confirmed: visibility → 'm'
```

### Daily forecast

```python
data = json.loads(http_get(
    f"https://api.open-meteo.com/v1/forecast"
    f"?latitude={lat}&longitude={lon}"
    f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum,"
    f"precipitation_probability_max,wind_speed_10m_max,weathercode,"
    f"sunrise,sunset,uv_index_max"
    f"&forecast_days=7&timezone={tz}"
))

daily = data['daily']
units = data['daily_units']
for i, date in enumerate(daily['time']):
    print(date,
          daily['temperature_2m_max'][i], '/', daily['temperature_2m_min'][i],
          f"pop={daily['precipitation_probability_max'][i]}%",
          f"precip={daily['precipitation_sum'][i]}mm",
          daily['sunrise'][i], daily['sunset'][i])
# sunrise/sunset are full ISO8601 datetimes: '2026-04-18T06:29'
```

---

## Historical weather (archive API)

Different subdomain. Requires `start_date` and `end_date` in `YYYY-MM-DD` format.

```python
import json

data = json.loads(http_get(
    "https://archive-api.open-meteo.com/v1/archive"
    "?latitude=40.71&longitude=-74.01"
    "&start_date=2024-01-01&end_date=2024-01-07"
    "&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
    "&timezone=America/New_York"
))

daily = data['daily']
# daily['time']               ['2024-01-01', '2024-01-02', ...]
# daily['temperature_2m_max'] [7.7, 5.7, 7.7, ...]   °C
# daily['temperature_2m_min'] [...]                   °C
# daily['precipitation_sum']  [0.0, 0.0, 0.0, ...]   mm

for i, date in enumerate(daily['time']):
    print(date, daily['temperature_2m_max'][i], daily['temperature_2m_min'][i], daily['precipitation_sum'][i])
```

### Full daily variable list (all confirmed units)

```python
data = json.loads(http_get(
    f"https://archive-api.open-meteo.com/v1/archive"
    f"?latitude={lat}&longitude={lon}"
    f"&start_date=2024-06-01&end_date=2024-06-30"
    f"&daily=temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
    f"apparent_temperature_max,apparent_temperature_min,"
    f"precipitation_sum,rain_sum,snowfall_sum,precipitation_hours,"
    f"wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant,"
    f"shortwave_radiation_sum,et0_fao_evapotranspiration,"
    f"weathercode,sunrise,sunset"
    f"&timezone={tz}"
))

# Confirmed daily units (live test, 2026-04-18):
# temperature_2m_max/min/mean         °C
# apparent_temperature_max/min        °C
# precipitation_sum                   mm
# rain_sum                            mm
# snowfall_sum                        cm   (NOTE: cm not mm)
# precipitation_hours                 h
# wind_speed_10m_max                  km/h
# wind_gusts_10m_max                  km/h
# wind_direction_10m_dominant         °
# shortwave_radiation_sum             MJ/m²
# et0_fao_evapotranspiration          mm   (reference evapotranspiration)
# weathercode                         wmo code
# sunrise / sunset                    iso8601 local datetime
```

### Hourly historical variables (all confirmed units)

```python
data = json.loads(http_get(
    f"https://archive-api.open-meteo.com/v1/archive"
    f"?latitude={lat}&longitude={lon}"
    f"&start_date=2024-06-01&end_date=2024-06-07"
    f"&hourly=temperature_2m,relative_humidity_2m,dewpoint_2m,"
    f"apparent_temperature,precipitation,rain,snowfall,snow_depth,"
    f"weathercode,surface_pressure,cloud_cover,visibility,"
    f"wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
    f"soil_temperature_0_to_7cm,soil_moisture_0_to_7cm"
    f"&timezone={tz}"
))

hourly = data['hourly']
# Confirmed hourly units (live test, 2026-04-18):
# temperature_2m              °C      relative_humidity_2m  %
# dewpoint_2m                 °C      apparent_temperature  °C
# precipitation               mm      rain                  mm
# snowfall                    cm      snow_depth            m
# weathercode                 wmo code surface_pressure     hPa
# cloud_cover                 %       visibility            'undefined' (metres in practice)
# wind_speed_10m              km/h    wind_direction_10m    °
# wind_gusts_10m              km/h
# soil_temperature_0_to_7cm   °C
# soil_moisture_0_to_7cm      m³/m³

# NOTE: visibility returns None for many historical hourly entries (sparse coverage)
```

### Data range

- Goes back to **1940** for most locations. Precipitation before ~1950 may have `None` entries.
- Goes up to **yesterday** (sometimes same-day). Future dates for archive return data up to the most recently available day without error.

```python
# Checking data availability (1940 confirmed live):
data = json.loads(http_get(
    "https://archive-api.open-meteo.com/v1/archive"
    "?latitude=40.71&longitude=-74.01"
    "&start_date=1940-01-01&end_date=1940-01-03"
    "&daily=temperature_2m_max,precipitation_sum&timezone=UTC"
))
# Returns: {'time': ['1940-01-01', '1940-01-02', '1940-01-03'],
#           'temperature_2m_max': [-1.7, -1.4, 0.3],
#           'precipitation_sum': [None, 0.0, 0.0]}   ← None is normal pre-1950
```

---

## Air quality API

```python
import json

data = json.loads(http_get(
    "https://air-quality-api.open-meteo.com/v1/air-quality"
    "?latitude=40.71&longitude=-74.01"
    "&current=pm10,pm2_5,us_aqi,european_aqi,"
    "carbon_monoxide,nitrogen_dioxide,ozone"
    "&timezone=America/New_York"
))

cur = data['current']
# Confirmed live values (2026-04-18, New York):
# cur['time']             '2026-04-18T21:00'
# cur['interval']         3600               (1-hour update cadence)
# cur['pm10']             11.5   μg/m³
# cur['pm2_5']            10.1   μg/m³
# cur['us_aqi']           48     USAQI
# cur['european_aqi']     29     EAQI
# cur['carbon_monoxide']  195.0  μg/m³
# cur['nitrogen_dioxide'] 20.7   μg/m³
# cur['ozone']            72.0   μg/m³

print(f"AQI (US): {cur['us_aqi']} — PM2.5: {cur['pm2_5']} μg/m³")
```

### Air quality AQI thresholds (US)

```python
AQI_LEVELS = [
    (50,  "Good"),
    (100, "Moderate"),
    (150, "Unhealthy for Sensitive Groups"),
    (200, "Unhealthy"),
    (300, "Very Unhealthy"),
    (500, "Hazardous"),
]

def aqi_label(aqi):
    for threshold, label in AQI_LEVELS:
        if aqi <= threshold:
            return label
    return "Hazardous"
```

### Hourly air quality forecast

```python
data = json.loads(http_get(
    f"https://air-quality-api.open-meteo.com/v1/air-quality"
    f"?latitude={lat}&longitude={lon}"
    f"&hourly=pm10,pm2_5,us_aqi,european_aqi"
    f"&forecast_days=3&timezone={tz}"
))

hourly = data['hourly']
# hourly['time']           ISO8601 strings, one per hour
# hourly['pm10']           μg/m³
# hourly['pm2_5']          μg/m³
# hourly['us_aqi']         USAQI integer
# hourly['european_aqi']   EAQI integer
```

---

## Marine API

Use open-ocean or coastal coordinates. Shallow nearshore or landlocked coordinates may return `None` for all wave variables.

```python
import json

# Atlantic open ocean (confirmed non-null values)
data = json.loads(http_get(
    "https://marine-api.open-meteo.com/v1/marine"
    "?latitude=35.0&longitude=-60.0"
    "&hourly=wave_height,wave_direction,wave_period,"
    "wind_wave_height,swell_wave_height"
    "&daily=wave_height_max,wave_direction_dominant,wind_wave_height_max"
    "&timezone=UTC"
))

hourly = data['hourly']
daily  = data['daily']

# Confirmed units (live test, 2026-04-18):
# wave_height            m    wave_direction         °
# wave_period            s    wind_wave_height       m
# swell_wave_height      m

# Daily:
# wave_height_max        m    wave_direction_dominant °
# wind_wave_height_max   m

for i, t in enumerate(hourly['time'][:6]):
    print(t,
          f"wave={hourly['wave_height'][i]}m",
          f"dir={hourly['wave_direction'][i]}°",
          f"period={hourly['wave_period'][i]}s")

# Confirmed live (Atlantic 35°N, 60°W):
# 2026-04-19T00:00 wave=1.3m dir=None° period=9.66s
```

---

## Unit overrides (all APIs)

Server-side conversion — just add query params:

```
&temperature_unit=fahrenheit    # default: celsius
&windspeed_unit=mph             # default: kmh  (also: ms, kn)
&precipitation_unit=inch        # default: mm
&wind_speed_unit=mph            # alias for windspeed_unit (both work)
```

---

## WMO weather code table

Used by `weathercode` in forecast and archive hourly/daily.

```python
WMO_CODES = {
    0: "Clear sky",
    1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Icy fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains",
    80: "Slight showers", 81: "Moderate showers", 82: "Violent showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail", 99: "Thunderstorm with heavy hail",
}

def wmo_desc(code):
    return WMO_CODES.get(code, f"Unknown ({code})")
```

---

## End-to-end pattern: city → climate summary

```python
import json

def climate_summary(city: str, year: int = 2024) -> dict:
    """Monthly averages for a full year using the historical archive."""
    # 1. Geocode
    geo = json.loads(http_get(
        f"https://geocoding-api.open-meteo.com/v1/search?name={city.replace(' ', '+')}&count=1"
    ))
    if not geo.get('results'):
        raise ValueError(f"City not found: {city}")
    loc = geo['results'][0]
    lat, lon, tz = loc['latitude'], loc['longitude'], loc['timezone']

    # 2. Full year of daily data
    data = json.loads(http_get(
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={year}-01-01&end_date={year}-12-31"
        f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
        f"&timezone={tz}"
    ))

    # 3. Aggregate by month
    daily = data['daily']
    from collections import defaultdict
    months = defaultdict(lambda: {'tmax': [], 'tmin': [], 'precip': []})
    for i, date in enumerate(daily['time']):
        m = date[5:7]  # '01'..'12'
        if daily['temperature_2m_max'][i] is not None:
            months[m]['tmax'].append(daily['temperature_2m_max'][i])
        if daily['temperature_2m_min'][i] is not None:
            months[m]['tmin'].append(daily['temperature_2m_min'][i])
        if daily['precipitation_sum'][i] is not None:
            months[m]['precip'].append(daily['precipitation_sum'][i])

    result = {}
    for m, vals in sorted(months.items()):
        result[m] = {
            'avg_tmax': round(sum(vals['tmax']) / len(vals['tmax']), 1) if vals['tmax'] else None,
            'avg_tmin': round(sum(vals['tmin']) / len(vals['tmin']), 1) if vals['tmin'] else None,
            'total_precip_mm': round(sum(vals['precip']), 1) if vals['precip'] else None,
        }
    return {'city': loc['name'], 'country': loc.get('country'), 'year': year, 'months': result}

summary = climate_summary("London", 2024)
for month, stats in summary['months'].items():
    print(f"{month}: {stats['avg_tmax']}°C / {stats['avg_tmin']}°C  {stats['total_precip_mm']}mm")
```

Total: 2 API calls (~1.4 s combined).

---

## Gotchas

**Always pass `&timezone={tz}`.** Without it, the API uses GMT. Daily buckets (max/min, sunrise) shift to UTC boundaries — daily highs for New York in summer will be attributed to the wrong day. Hourly timestamps will also be UTC, not local.

**`wind_speed_10m` (forecast) vs `wind_speed_10m_max` (daily).** The current and hourly variable is `wind_speed_10m`; the daily aggregate is `wind_speed_10m_max`. Using `wind_speed_10m` in a `&daily=` request returns an HTTP 400.

**`snowfall_sum` is in centimetres, not millimetres.** All other precipitation variables (`precipitation_sum`, `rain_sum`) are in mm. The `snowfall` hourly variable is also cm.

**`visibility` unit is listed as `'undefined'`** in the hourly_units dict (confirmed live). The actual values are in metres — divide by 1000 for km. The archive historical visibility is sparse (many `None` entries).

**Marine API returns `None` for nearshore/landlocked coordinates.** Use open-ocean coordinates (e.g. 35°N 60°W for the Atlantic). Coastal points like `51.5°N, 0.0°E` (London) may return all nulls despite being near the coast.

**HTTP 400 on bad params — error body is gzip-compressed.** The `http_get` helper raises `urllib.error.HTTPError` on 4xx. To read the reason:
```python
import urllib.error, gzip
try:
    data = json.loads(http_get(bad_url))
except urllib.error.HTTPError as e:
    body = e.read()
    if e.headers.get("Content-Encoding") == "gzip":
        body = gzip.decompress(body)
    print(json.loads(body)['reason'])
    # e.g. "Latitude must be in range of -90 to 90°. Given: 999.0."
```

**Geocoding returns `{}` (no `results` key) for unknown names** — not an error, not an empty list. Guard with `geo.get('results')`.

**Rate limit: 10,000 requests/day (free tier).** Geocoding and forecast/archive count separately. No rate-limit headers are returned on success — track usage yourself.

**`forecast_days` max is 16 for the forecast API.** Requesting more raises HTTP 400. Default is 7.

**Archive API max date range is not documented but is very large** — a full year (366 days) works fine in a single call. There is no documented per-call row limit.

**`data['elevation']` is the terrain elevation at the requested coordinates (metres), not related to any weather variable.** Useful to confirm the geocoded point is sensible (e.g. a mountain vs a city).
