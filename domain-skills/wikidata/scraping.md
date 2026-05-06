# Wikidata — Structured Knowledge Base

`https://www.wikidata.org` — free structured knowledge base. All APIs are free, no auth required. No browser needed for any workflow on this page.

## Do this first

**Use the MediaWiki API (`wbgetentities`) when you have QIDs — batch up to 50 at once, one HTTP call.**

```python
import json
data = json.loads(http_get(
    "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=Q42|Q64|Q30&languages=en|mul&props=labels|descriptions&format=json"
))
# data['entities'] is a dict keyed by QID
for qid, ent in data['entities'].items():
    label = (ent['labels'].get('en') or ent['labels'].get('mul') or {}).get('value', '')
    desc = ent['descriptions'].get('en', {}).get('value', '')
    print(qid, label, '—', desc)
# Q42 Douglas Adams — British science fiction writer and humorist (1952–2001)
# Q64 Berlin — federated state, capital and largest city of Germany
# Q30 United States — country located primarily in North America
```

**Use SPARQL when you need to query by property values, filter, or aggregate — it returns already-labelled rows.**

**Use `Special:EntityData/{QID}.json` when you need the full entity including all claims with qualifiers.**

No browser needed. No auth. No API key.

---

## Key concepts

### QID and PID format

- **Items** (things): `Q42`, `Q7186`, `Q60` — entities like people, places, concepts
- **Properties**: `P31`, `P279`, `P17` — define the type of relationship in a claim
- A **claim** = subject (QID) + property (PID) + value (another QID, string, date, quantity, coordinate, ...)

Common property IDs confirmed working:

| PID | Label |
|-----|-------|
| P31 | instance of |
| P279 | subclass of |
| P17 | country |
| P18 | image (Wikimedia Commons URL) |
| P50 | author |
| P57 | director |
| P106 | occupation |
| P214 | VIAF cluster ID |
| P569 | date of birth |
| P570 | date of death |
| P577 | publication date |
| P625 | coordinate location |
| P1082 | population |

Look up any PID: `https://www.wikidata.org/w/api.php?action=wbgetentities&ids=P31|P569|P1082&languages=en&props=labels&format=json`

### SPARQL prefixes (built-in, no need to declare)

```sparql
wd:   = https://www.wikidata.org/entity/         (items: wd:Q42)
wdt:  = https://www.wikidata.org/prop/direct/    (truthy property: wdt:P31)
p:    = https://www.wikidata.org/prop/           (full statement node: p:P31)
ps:   = https://www.wikidata.org/prop/statement/ (statement value: ps:P31)
pq:   = https://www.wikidata.org/prop/qualifier/ (qualifier value: pq:P580)
```

`wdt:` is the shorthand for most queries — it picks the preferred-rank value (or best normal-rank). Use `p:/ps:` only when you need qualifiers or multiple ranked values.

---

## Common workflows

### Search for an entity by name (API)

```python
import json
data = json.loads(http_get(
    "https://www.wikidata.org/w/api.php?action=wbsearchentities&search=Marie+Curie&language=en&type=item&limit=5&format=json"
))
for r in data['search']:
    print(r['id'], r['label'], '—', r.get('description', '')[:60])
# Q7186  Marie Curie — Polish-French physicist and chemist (1867–1934)
# Q114939443  Marie Curie — 2022 Czech book edition
```

To search for properties instead of items: `&type=property`

### Batch entity lookup (API) — up to 50 QIDs per call

```python
import json
ids = "|".join(["Q42", "Q7186", "Q64", "Q30", "Q5"])
data = json.loads(http_get(
    f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={ids}&languages=en|mul&props=labels|descriptions|sitelinks&format=json"
))
for qid, ent in data['entities'].items():
    if 'missing' in ent:
        continue  # entity does not exist
    label = (ent['labels'].get('en') or ent['labels'].get('mul') or {}).get('value', '')
    desc  = ent['descriptions'].get('en', {}).get('value', '')
    wiki  = ent.get('sitelinks', {}).get('enwiki', {}).get('title', '')
    print(qid, label, wiki)
```

`props` options: `labels`, `descriptions`, `aliases`, `claims`, `sitelinks` — omit `claims` for faster responses when you just need metadata.

### Full entity data with claims

```python
import json
data = json.loads(http_get("https://www.wikidata.org/wiki/Special:EntityData/Q42.json"))
ent = data['entities']['Q42']

label = (ent['labels'].get('en') or ent['labels'].get('mul') or {}).get('value', '')
desc  = ent['descriptions'].get('en', {}).get('value', '')

# Claims: each property maps to a list of statement objects
for claim in ent['claims'].get('P31', []):          # instance of
    snak = claim['mainsnak']
    if snak.get('datavalue'):
        val = snak['datavalue']['value']
        print('P31 value:', val['id'])               # e.g. 'Q5' (human)
    print('rank:', claim['rank'])                    # 'preferred', 'normal', 'deprecated'

# Sitelinks — Wikipedia page name for this entity
print('enwiki:', ent['sitelinks'].get('enwiki', {}).get('title'))   # 'Douglas Adams'
```

### Reading claim value types

Claim values differ by datatype — always check `snak['datavalue']['type']`:

```python
import json
data = json.loads(http_get("https://www.wikidata.org/wiki/Special:EntityData/Q60.json"))
q60 = data['entities']['Q60']

# Item reference (type='wikibase-entityid')
place_claims = q60['claims'].get('P17', [])
for c in place_claims:
    val = c['mainsnak']['datavalue']['value']
    print(val['id'])         # e.g. 'Q30' (United States)

# Time (type='time')
# {'time': '+1952-03-11T00:00:00Z', 'precision': 11, ...}
# precision: 9=year, 10=month, 11=day

# Coordinate (type='globecoordinate')
coord = q60['claims']['P625'][0]['mainsnak']['datavalue']['value']
print(coord['latitude'], coord['longitude'])  # 40.71277... -74.00611...

# Quantity (type='quantity')
pop = q60['claims']['P1082'][0]['mainsnak']['datavalue']['value']
print(pop['amount'])   # '+8405837'  (string with sign prefix)
print(pop['unit'])     # '1' means dimensionless (no unit item)

# String (type='string') — no nesting, just a plain string value
# Monolingualtext (type='monolingualtext') — {'text': '...', 'language': 'en'}
```

### Claim qualifiers

Qualifiers are metadata on statements (e.g., start/end dates for employment):

```python
import json
data = json.loads(http_get("https://www.wikidata.org/wiki/Special:EntityData/Q42.json"))
q42 = data['entities']['Q42']

for claim in q42['claims'].get('P69', []):  # educated at
    school_id = claim['mainsnak']['datavalue']['value']['id']
    quals = claim.get('qualifiers', {})
    start = quals.get('P580', [{}])[0].get('datavalue', {}).get('value', {}).get('time', '')
    end   = quals.get('P582', [{}])[0].get('datavalue', {}).get('value', {}).get('time', '')
    print(f"school={school_id}, {start[:5]}–{end[:5]}")
# school=Q4961791, +1959–+1970
```

### SPARQL queries

All SPARQL requests require `User-Agent` and `Accept` headers — the endpoint returns HTTP errors without them:

```python
import json, urllib.parse
from helpers import http_get

SPARQL_URL = "https://query.wikidata.org/sparql"
HEADERS = {
    "User-Agent": "browser-harness/1.0",
    "Accept": "application/sparql-results+json",
}

def sparql(query):
    url = SPARQL_URL + "?query=" + urllib.parse.quote(query) + "&format=json"
    return json.loads(http_get(url, headers=HEADERS, timeout=30))['results']['bindings']
```

**Countries by population (ORDER BY + LIMIT):**

```python
rows = sparql("""
SELECT ?country ?countryLabel ?population WHERE {
  ?country wdt:P31 wd:Q6256 ;
           wdt:P1082 ?population .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul" }
}
ORDER BY DESC(?population)
LIMIT 10
""")
for r in rows:
    print(r['countryLabel']['value'], int(r['population']['value']))
# India 1477519529
# People's Republic of China 1442965000
```

**Films by director, deduplicated (multiple release dates cause row explosion without GROUP BY):**

```python
rows = sparql("""
SELECT ?film ?filmLabel (MIN(?date) AS ?firstRelease) WHERE {
  ?film wdt:P31 wd:Q11424 ;
        wdt:P57 wd:Q25191 ;   # directed by Christopher Nolan
        wdt:P577 ?date .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul" }
}
GROUP BY ?film ?filmLabel
ORDER BY ?firstRelease
""")
for r in rows:
    print(r['firstRelease']['value'][:4], r['filmLabel']['value'])
# 1998 Following
# 2000 Memento
# 2023 Oppenheimer
```

**Books by author:**

```python
rows = sparql("""
SELECT ?book ?bookLabel ?year WHERE {
  ?book wdt:P31 wd:Q571 ;
        wdt:P50 wd:Q3335 .   # author: George Orwell
  OPTIONAL { ?book wdt:P577 ?date . BIND(YEAR(?date) AS ?year) }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul" }
}
ORDER BY ?year
""")
```

**Humans born in a city (FILTER on date):**

```python
rows = sparql("""
SELECT ?person ?personLabel ?born WHERE {
  ?person wdt:P31 wd:Q5 ;
          wdt:P106 wd:Q36180 ;  # occupation: writer
          wdt:P27 wd:Q145 ;     # citizenship: United Kingdom
          wdt:P569 ?born .
  FILTER(YEAR(?born) >= 1900 && YEAR(?born) <= 1910)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul" }
}
LIMIT 10
""")
for r in rows:
    print(r['personLabel']['value'], r['born']['value'][:4])
# George Orwell 1903
# W. H. Auden 1907
```

**Look up specific items with VALUES clause:**

```python
rows = sparql("""
SELECT ?item ?itemLabel ?population WHERE {
  VALUES ?item { wd:Q60 wd:Q64 wd:Q90 wd:Q84 }
  OPTIONAL { ?item wdt:P1082 ?population }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en,mul" }
}
""")
for r in rows:
    print(r['itemLabel']['value'], r.get('population', {}).get('value', ''))
# New York City 8804190
# Berlin 3782202
```

**Multilingual labels inline (without SERVICE block):**

```python
rows = sparql("""
SELECT ?item ?label_en ?label_fr WHERE {
  VALUES ?item { wd:Q42 wd:Q64 wd:Q30 }
  OPTIONAL { ?item rdfs:label ?label_en . FILTER(LANG(?label_en) = "en") }
  OPTIONAL { ?item rdfs:label ?label_fr . FILTER(LANG(?label_fr) = "fr") }
}
""")
```

### Parallel entity fetches

```python
import json
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

def fetch_entity(qid):
    data = json.loads(http_get(
        f"https://www.wikidata.org/w/api.php?action=wbgetentities&ids={qid}&languages=en|mul&props=labels|descriptions&format=json"
    ))
    ent = data['entities'][qid]
    label = (ent['labels'].get('en') or ent['labels'].get('mul') or {}).get('value', '')
    return qid, label

qids = ['Q42', 'Q7186', 'Q64', 'Q30', 'Q5']
with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_entity, qids))
# 5 entities in ~0.35s
# Prefer the batch API endpoint when QIDs are known upfront
```

---

## Gotchas

- **`mul` label fallback is required.** Wikidata migrated many entities to language code `mul` (multilingual) instead of `en`. `Q7186` (Marie Curie) has no `en` label in the entity JSON — only `mul`. Always fetch `languages=en|mul` and fall back: `(ent['labels'].get('en') or ent['labels'].get('mul') or {}).get('value', '')`. In SPARQL, use `"en,mul"` in the language service param.

- **SPARQL `SERVICE wikibase:label` returns the QID string when no label matches the language.** If you use `"en"` and the entity only has a `mul` label, `?itemLabel` will be `"Q7186"` not `"Marie Curie"`. Fix: always use `"en,mul"` or `"en,mul,fr,de"`.

- **Duplicate rows from multiple property values.** A film has multiple P577 (release date) statements for different countries. `wdt:P577` returns all of them, one row each. Fix: wrap with `MIN(?date)` and `GROUP BY ?film ?filmLabel`.

- **`wdt:` picks preferred rank; use `p:/ps:` for all statements.** `wdt:P31` returns the preferred-rank value. To iterate all statements including deprecated, use `p:P31 ?stmt . ?stmt ps:P31 ?value`.

- **Property values are complex objects, not strings.** Dates come as `{'time': '+1952-03-11T00:00:00Z', 'precision': 11, ...}`. Coordinates come as `{'latitude': 40.71, 'longitude': -74.0, ...}`. Quantities come as `{'amount': '+8405837', 'unit': '1', ...}` — `amount` is a signed string, not a number. SPARQL quantities bind as plain string literals (`type='literal'`).

- **Missing entities have `'missing' in ent`, not a raised error.** The API returns `{'id': 'Q999999999', 'missing': ''}` for non-existent QIDs. Check `'missing' in ent` before accessing labels/claims.

- **SPARQL rate limit: 60 req/min.** The endpoint will return HTTP 429 if exceeded. Add `time.sleep(1)` between bulk SPARQL calls. The MediaWiki API has a higher limit (hundreds per minute). For lookup-heavy workflows, batch with `wbgetentities` (50 QIDs/call) rather than per-QID SPARQL.

- **SPARQL timeout at 60 seconds.** Unbounded traversals (no LIMIT, cross-product joins) hit the server-side 60s wall and raise a timeout error. Always use `LIMIT`, and `FILTER` early to reduce the search space. Avoid `?x ?p ?y` open property traversal patterns without filters.

- **`Special:EntityData/Q42.json` works; `Q42.json` returns 404.** The redirect URL `/wiki/Q42.json` does not exist. Use `/wiki/Special:EntityData/Q42.json` or the API endpoint. The `?format=json` query param also works: `/wiki/Special:EntityData/Q42?format=json`.

- **User-Agent is required for SPARQL.** Without it the endpoint may reject requests. Use `"browser-harness/1.0"` or include your project name. The `http_get` helper sends `Mozilla/5.0` by default, which works, but setting an explicit user agent is good practice.

- **Sitelinks give Wikipedia page names, not URLs.** `ent['sitelinks']['enwiki']['title']` returns `"Douglas Adams"`. Build the Wikipedia URL as `"https://en.wikipedia.org/wiki/" + title.replace(' ', '_')`.

- **Image URLs are Wikimedia Commons `Special:FilePath` links.** `wdt:P18` SPARQL values look like `http://commons.wikimedia.org/wiki/Special:FilePath/Douglas%20adams%20portrait.jpg`. These redirect to the actual image file and can be downloaded directly.

- **`wbgetentities` props parameter controls payload size.** Fetching `claims` for 50 entities can return megabytes. If you only need labels/descriptions/sitelinks, set `props=labels|descriptions|sitelinks` to skip claims entirely.

---

## Rate limits summary

| Endpoint | Limit |
|----------|-------|
| SPARQL (`query.wikidata.org`) | 60 req/min per IP |
| MediaWiki API (`wikidata.org/w/api.php`) | ~500 req/min unauthenticated |
| `Special:EntityData` | same as MediaWiki API |
| No auth required | across all endpoints |
