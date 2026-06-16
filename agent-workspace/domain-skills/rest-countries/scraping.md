# REST Countries — Scraping & Data Extraction

`https://restcountries.com` — open JSON API for country data. **Never use the browser.** All data is reachable via `http_get`. No auth required, no API key.

## Do this first

**Fetch all 250 countries in one call with a field filter — almost always the fastest approach.**

```python
import json
from helpers import http_get

data = http_get("https://restcountries.com/v3.1/all?fields=name,cca2,capital,population,area,region")
countries = json.loads(data)
# countries is a list of 250 dicts — confirmed 2026-04-18

for c in countries:
    name       = c["name"]["common"]          # "Germany"
    official   = c["name"]["official"]        # "Federal Republic of Germany"
    code       = c["cca2"]                    # "DE"
    capital    = c["capital"][0] if c.get("capital") else None   # list — may be empty
    population = c["population"]              # 83491249
    area       = c["area"]                    # 357114.0 (km²)
    region     = c["region"]                  # "Europe"
    print(code, name, population)
# Confirmed output (first result varies — API returns unsorted):
# CI Ivory Coast 31719275
```

Use the `?fields=` query param to limit response size — essential when fetching all 250.

## Common workflows

### Lookup a single country by code (ISO 3166-1 alpha-2 or alpha-3)

```python
import json
from helpers import http_get

# Single code — returns a list (one element)
data = http_get("https://restcountries.com/v3.1/alpha/DE")
country = json.loads(data)[0]

# But: /alpha/CODE?fields=... returns a plain dict, not a list — watch for this
data2 = http_get("https://restcountries.com/v3.1/alpha/DE?fields=name,cca2,currencies,languages,flags")
country2 = json.loads(data2)          # dict, NOT list

name       = country2["name"]["common"]                             # "Germany"
currencies = country2["currencies"]                                 # {"EUR": {"name": "euro", "symbol": "€"}}
currency_codes = list(currencies.keys())                            # ["EUR"]
currency_name  = currencies["EUR"]["name"]                          # "euro"
languages  = country2["languages"]                                  # {"deu": "German"}
lang_names = list(languages.values())                               # ["German"]
flag_png   = country2["flags"]["png"]                               # "https://flagcdn.com/w320/de.png"
flag_svg   = country2["flags"]["svg"]                               # "https://flagcdn.com/de.svg"
flag_alt   = country2["flags"]["alt"]                               # description text

print(name, currency_codes, lang_names)
# Confirmed: Germany ['EUR'] ['German']
```

### Batch lookup — multiple codes in one call

Use `/alpha?codes=` for fetching a known list of countries — always returns a list.

```python
import json
from helpers import http_get

codes = ["US", "GB", "FR", "DE", "JP", "CN", "IN", "BR", "AU", "CA"]
data = http_get(f"https://restcountries.com/v3.1/alpha?codes={','.join(codes)}&fields=name,cca2,population")
countries = json.loads(data)
# Returns list, order NOT guaranteed to match input order
for c in countries:
    print(c["cca2"], c["name"]["common"], c["population"])
# Confirmed: 10 results, returned in arbitrary order
```

### Search by name

```python
import json
from helpers import http_get

# Partial match (default) — may return multiple results
data = http_get("https://restcountries.com/v3.1/name/united")
results = json.loads(data)
# Returns 7 countries: United States, UK, UAE, Tanzania, Mexico, ...

# Exact match — use fullText=true with the full common or official name
data2 = http_get("https://restcountries.com/v3.1/name/united%20kingdom?fullText=true")
results2 = json.loads(data2)
# Returns exactly 1 result: United Kingdom
print(results2[0]["name"]["common"])  # United Kingdom
```

### Filter by region

```python
import json
from helpers import http_get

data = http_get("https://restcountries.com/v3.1/region/europe?fields=name,cca2,population")
countries = json.loads(data)
# 53 European countries — confirmed

# Sort by population
ranked = sorted(countries, key=lambda x: x["population"], reverse=True)
for c in ranked[:5]:
    print(c["cca2"], c["name"]["common"], f"{c['population']:,}")
# Confirmed top 5: RU Russia, DE Germany, FR France, GB United Kingdom, IT Italy
```

Valid region values: `africa`, `americas`, `asia`, `europe`, `oceania`, `antarctic`

### Filter by subregion

```python
import json
from helpers import http_get

data = http_get("https://restcountries.com/v3.1/subregion/Western%20Europe?fields=name,cca2")
countries = json.loads(data)
print([c["cca2"] for c in countries])
# Confirmed: ['FR', 'NL', 'MC', 'DE', 'BE', 'LI', 'CH', 'LU']
```

### Filter by language

```python
import json
from helpers import http_get

data = http_get("https://restcountries.com/v3.1/lang/arabic")
countries = json.loads(data)
print(f"Arabic-speaking countries: {len(countries)}")
# Confirmed: 25 countries

# Language param is the language name (English), not the ISO 639-3 code
# Works: arabic, french, spanish, english, portuguese, german, russian, chinese
```

### Filter by currency

```python
import json
from helpers import http_get

data = http_get("https://restcountries.com/v3.1/currency/EUR")
countries = json.loads(data)
print(f"EUR countries: {len(countries)}")  # Confirmed: 36
names = [c["name"]["common"] for c in countries]
print(names[:5])

# Use ISO 4217 currency code (uppercase)
```

### Filter by capital city

```python
import json
from helpers import http_get

data = http_get("https://restcountries.com/v3.1/capital/berlin?fields=name,cca2,capital")
result = json.loads(data)
print(result[0]["name"]["common"], result[0]["capital"])
# Confirmed: Germany ['Berlin']
# Capital param is case-insensitive
```

### Full country detail — all fields

```python
import json
from helpers import http_get

data = http_get("https://restcountries.com/v3.1/alpha/US")
c = json.loads(data)[0]

# Available top-level keys (confirmed for US/DE):
# name, tld, cca2, ccn3, cca3, cioc, independent, status, unMember,
# currencies, idd, capital, altSpellings, region, subregion, languages,
# translations, latlng, landlocked, borders, area, demonyms, flag (emoji),
# maps, population, gini, fifa, car, timezones, continents, flags,
# coatOfArms, startOfWeek, capitalInfo, postalCode

print(c["idd"])          # {"root": "+1", "suffixes": ["201", "202", ...]}
print(c["car"]["side"])  # "right" or "left"
print(c["gini"])         # {"2018": 41.4}  — year keyed, may be absent
print(c["timezones"])    # list of UTC offset strings
print(c["borders"])      # list of cca3 codes for bordering countries
print(c["latlng"])       # [lat, lng] of geographic center
```

## URL reference

| Endpoint | Pattern | Notes |
|---|---|---|
| All countries | `/v3.1/all` | Always add `?fields=` |
| By code | `/v3.1/alpha/{code}` | cca2 or cca3; single code → list (no fields) or dict (with fields) |
| By codes | `/v3.1/alpha?codes=DE,FR,JP` | Always returns list |
| By name | `/v3.1/name/{name}` | Partial; add `?fullText=true` for exact match |
| By region | `/v3.1/region/{region}` | africa, americas, asia, europe, oceania, antarctic |
| By subregion | `/v3.1/subregion/{subregion}` | URL-encode spaces as `%20` |
| By language | `/v3.1/lang/{language}` | English language name |
| By currency | `/v3.1/currency/{code}` | ISO 4217 (EUR, USD, GBP) |
| By capital | `/v3.1/capital/{city}` | Case-insensitive |

All endpoints accept `?fields=field1,field2,...` to limit response payload.

## Gotchas

- **`name` is a nested object, not a string.** Use `c["name"]["common"]` for the familiar English name, `c["name"]["official"]` for the full official name. `nativeName` is a dict keyed by ISO 639-3 language code.

- **`/alpha/CODE` return type depends on whether `?fields=` is present.** Without `?fields=`, returns a list (one element). With `?fields=...`, returns a plain dict. Use `json.loads(data)[0]` for the no-fields case, `json.loads(data)` for the fields case. Using `/alpha?codes=CODE` always returns a list regardless.

- **`currencies` is a dict keyed by ISO 4217 code, not a list.** `c["currencies"]["EUR"]["name"]` → `"euro"`, `c["currencies"]["EUR"]["symbol"]` → `"€"`. A country can have multiple currencies — iterate `currencies.items()`.

- **`languages` is a dict keyed by ISO 639-3 code.** `c["languages"]["deu"]` → `"German"`. Use `list(c["languages"].values())` for a simple list of language names.

- **`capital` is a list and may be empty.** Some territories (Antarctica, Bouvet Island, Macau, Heard Island) have no capital — `c.get("capital")` returns `[]`, not `None`. Guard with `c["capital"][0] if c.get("capital") else None`. South Africa has 3 capitals.

- **`gini` is a dict keyed by year string, may be absent entirely.** `c["gini"]` → `{"2016": 31.9}`. Many small countries or territories have no gini data — always check `c.get("gini")`.

- **`borders` uses cca3 codes, not cca2.** `c["borders"]` → `["AUT", "BEL", ...]`. Cross-reference with another `/alpha?codes=` call to resolve to names.

- **`translations` covers ~45 languages.** Each entry: `c["translations"]["deu"]` → `{"official": "Bundesrepublik Deutschland", "common": "Deutschland"}`. Useful for multilingual apps.

- **No rate limit headers, no documented rate limit.** In practice the API handles rapid sequential calls fine. For bulk crawling hundreds of per-country requests, add a short sleep (`time.sleep(0.5)`) between calls to be polite.

- **404 returns JSON, not HTML.** `{"message": "Not Found", "status": 404}`. Wrap calls in try/except and check for this pattern when handling user-supplied country names or codes.

- **`?fields=` is the key performance lever.** The full all-countries payload without field filtering is ~1.5 MB. With `?fields=name,cca2,population` it drops to ~50 KB. Always filter when you don't need all fields.
