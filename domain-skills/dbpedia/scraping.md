# DBpedia — Structured Wikipedia Data via SPARQL

`https://dbpedia.org` — structured data extracted from Wikipedia infoboxes, exposed as Linked Open Data. **Never use the browser.** All data is reachable via `http_get` using the SPARQL endpoint, the Lookup API, or the entity JSON API.

DBpedia has ~1.4 billion triples. It cross-links to Wikidata via `owl:sameAs`, carries Wikipedia infobox fields as `dbp:` properties, and maps them to a cleaner ontology as `dbo:` properties.

---

## Do this first

**Use the SPARQL endpoint for structured queries. Use the Lookup API for fuzzy name → URI resolution. Use `data/{Name}.json` for a quick property dump of a single entity.**

```python
import json, urllib.parse, urllib.request, urllib.error

def sparql(query: str, timeout_ms: int = 30000) -> list[dict]:
    """Run a SPARQL SELECT query. Returns list of binding dicts."""
    url = "https://dbpedia.org/sparql?" + urllib.parse.urlencode({
        "query": query,
        "format": "application/sparql-results+json",
        "timeout": str(timeout_ms),
    })
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout_ms / 1000 + 10) as r:
        return json.loads(r.read())["results"]["bindings"]
```

The function is synchronous and safe to call directly. `format=json` (shorthand) also works.

---

## Common workflows

### Name → URI (Lookup API)

Fuzzy search: accepts misspellings and partial names. Always do this before querying SPARQL if you only have a human-readable name.

```python
import json, urllib.parse
from helpers import http_get

def lookup(query: str, max_results: int = 5, type_filter: str = "") -> list[dict]:
    """Resolve a human-readable name to DBpedia resource URIs."""
    params = {"query": query, "format": "json", "maxResults": str(max_results)}
    if type_filter:
        params["typeName"] = type_filter  # e.g. 'City', 'Person', 'Film'
    raw = http_get(
        "https://lookup.dbpedia.org/api/search?" + urllib.parse.urlencode(params)
    )
    return json.loads(raw)["docs"]

docs = lookup("Albert Einstein")
# docs[0]['resource'][0]   == 'http://dbpedia.org/resource/Albert_Einstein'
# docs[0]['id'][0]         == 'http://dbpedia.org/resource/Albert_Einstein'
# docs[0]['label'][0]      == '<B>Albert</B> <B>Einstein</B>'  (HTML-highlighted)
# docs[0]['comment'][0]    == '<B>Albert</B> <B>Einstein</B> ( EYEN-styne...'  (snippet)
# docs[0]['typeName']      == ['Person', 'Scientist', 'Agent']
# docs[0]['type']          == ['http://dbpedia.org/ontology/Person', ...]
# docs[0]['score'][0]      == '10724.388'
# docs[0]['refCount'][0]   == '71'   (number of inbound links)
# docs[0]['category']      == ['http://dbpedia.org/resource/Category:...', ...]
# docs[0]['redirectlabel'] == ['A. <B>Einstein</B>', ...]  (alternate spellings)

resource_uri = docs[0]['resource'][0]
resource_name = resource_uri.split('/')[-1]  # 'Albert_Einstein'

# Type-filtered example: only cities named Paris
city_docs = lookup("Paris", type_filter="City")
# city_docs[0]['resource'][0] == 'http://dbpedia.org/resource/Paris'
# city_docs[1]['resource'][0] == 'http://dbpedia.org/resource/Paris,_Texas'
# Confirmed 2026-04-18
```

### Entity property dump (data.json)

Returns all RDF triples where the entity is the subject. Fast, no SPARQL needed. Does **not** include `dbo:abstract` — see gotchas.

```python
import json
from helpers import http_get

raw = http_get("https://dbpedia.org/data/Nikola_Tesla.json")
d = json.loads(raw)
resource_uri = "http://dbpedia.org/resource/Nikola_Tesla"
props = d[resource_uri]   # dict: predicate URI → list of value dicts

# Value dict shape:
# {'type': 'literal', 'value': '1856-07-10', 'lang': 'en'}     ← string literal
# {'type': 'literal', 'value': '1856-07-10', 'datatype': 'http://www.w3.org/2001/XMLSchema#date'}
# {'type': 'uri', 'value': 'http://dbpedia.org/resource/Smiljan,_Croatia'}  ← URI ref

# Common predicates:
birthdate = props.get("http://dbpedia.org/ontology/birthDate", [{}])[0].get("value")
# '1856-07-10'
birthplace = props.get("http://dbpedia.org/ontology/birthPlace", [{}])[0].get("value")
# 'http://dbpedia.org/resource/Smiljan,_Croatia'
thumbnail  = props.get("http://dbpedia.org/ontology/thumbnail", [{}])[0].get("value")
# 'http://commons.wikimedia.org/wiki/Special:FilePath/Tesla_circa_1890.jpeg?width=300'

# Filter labels by language (data.json uses 'lang' key, NOT 'xml:lang')
labels = props.get("http://www.w3.org/2000/01/rdf-schema#label", [])
en_label = next((l["value"] for l in labels if l.get("lang") == "en"), None)
# 'Nikola Tesla'
# Confirmed 2026-04-18
```

### SPARQL: entity metadata

```python
import json, urllib.parse, urllib.request

def sparql(query: str, timeout_ms: int = 30000) -> list[dict]:
    url = "https://dbpedia.org/sparql?" + urllib.parse.urlencode({
        "query": query,
        "format": "application/sparql-results+json",
        "timeout": str(timeout_ms),
    })
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout_ms / 1000 + 10) as r:
        return json.loads(r.read())["results"]["bindings"]

bindings = sparql("""
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dbr: <http://dbpedia.org/resource/>
SELECT ?name ?birthDate ?birthPlace ?bpLabel WHERE {
  dbr:Nikola_Tesla rdfs:label ?name ;
                   dbo:birthDate ?birthDate ;
                   dbo:birthPlace ?birthPlace .
  ?birthPlace rdfs:label ?bpLabel .
  FILTER(lang(?name) = 'en')
  FILTER(lang(?bpLabel) = 'en')
} LIMIT 3
""")
for b in bindings:
    print(b["name"]["value"], b["birthDate"]["value"], b["bpLabel"]["value"])
# Nikola Tesla 1856-07-10 Smiljan, Croatia
# Confirmed 2026-04-18

# SPARQL JSON response uses 'xml:lang' key, NOT 'lang':
# bindings[0]['name'] == {'type': 'literal', 'xml:lang': 'en', 'value': 'Nikola Tesla'}
# Access with: b['name'].get('xml:lang') or b['name'].get('lang')
# BUT: lang() FILTER in SPARQL works correctly regardless — use FILTER(lang(?x)='en')
```

### SPARQL: batch lookup by known URIs (VALUES)

```python
bindings = sparql("""
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX dbo: <http://dbpedia.org/ontology/>
SELECT ?person ?name ?birthDate WHERE {
  VALUES ?person {
    <http://dbpedia.org/resource/Albert_Einstein>
    <http://dbpedia.org/resource/Nikola_Tesla>
    <http://dbpedia.org/resource/Marie_Curie>
  }
  ?person rdfs:label ?name ;
          dbo:birthDate ?birthDate .
  FILTER(lang(?name) = 'en')
}
""")
for b in bindings:
    print(b["name"]["value"], b["birthDate"]["value"])
# Albert Einstein 1879-03-14
# Marie Curie 1867-11-07
# Nikola Tesla 1856-07-10
# Confirmed 2026-04-18
```

### SPARQL: films by director

```python
bindings = sparql("""
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?film ?title WHERE {
  ?film a dbo:Film ;
        dbo:director <http://dbpedia.org/resource/Christopher_Nolan> ;
        rdfs:label ?title .
  FILTER(lang(?title) = 'en')
} ORDER BY ?title LIMIT 10
""")
for b in bindings:
    print(b["title"]["value"])
# Batman Begins
# Doodlebug (film)
# Dunkirk (2017 film)
# Following
# Inception
# ... (10 total)
# Confirmed 2026-04-18

# With optional budget (scientific notation — see gotchas):
bindings2 = sparql("""
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?film ?title ?budget WHERE {
  ?film a dbo:Film ;
        dbo:director <http://dbpedia.org/resource/Christopher_Nolan> ;
        rdfs:label ?title .
  OPTIONAL { ?film dbo:budget ?budget }
  FILTER(lang(?title) = 'en')
} LIMIT 10
""")
for b in bindings2:
    budget = b.get("budget", {}).get("value", "N/A")
    print(f"{b['title']['value']}: {budget}")
# Inception: 1.6E8    ← $160M, stored as float
# Batman Begins: 1.5E8
# Following: 6000.0
# Confirmed 2026-04-18
```

### SPARQL: cities by population

```python
bindings = sparql("""
PREFIX dbo: <http://dbpedia.org/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT DISTINCT ?city ?name ?pop WHERE {
  ?city a dbo:City ;
        rdfs:label ?name ;
        dbo:populationTotal ?pop .
  FILTER(lang(?name) = 'en')
  FILTER(?pop > 5000000)
  FILTER(?pop < 100000000)
} ORDER BY DESC(?pop) LIMIT 10
""")
for b in bindings:
    print(f"{b['name']['value']}: {b['pop']['value']}")
# Beijing: 21893095
# Chengdu: 20937757
# Karachi: 18868021
# ...
# Confirmed 2026-04-18 — upper bound filter required; see dirty data gotcha
```

### SPARQL: cross-link to Wikidata

```python
bindings = sparql("""
PREFIX dbr: <http://dbpedia.org/resource/>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?wd WHERE {
  dbr:Albert_Einstein owl:sameAs ?wd .
  FILTER(strstarts(str(?wd), 'http://www.wikidata.org/entity/Q'))
}
""")
print([b["wd"]["value"] for b in bindings])
# ['http://www.wikidata.org/entity/Q937']
# Confirmed 2026-04-18
```

---

## Prefix reference

These are the five prefixes you need for 95% of queries:

```sparql
PREFIX dbo:  <http://dbpedia.org/ontology/>      # clean ontology: dbo:birthDate, dbo:Film, dbo:populationTotal
PREFIX dbr:  <http://dbpedia.org/resource/>      # named resources: dbr:Albert_Einstein
PREFIX dbp:  <http://dbpedia.org/property/>      # raw Wikipedia infobox properties (messier)
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>   # rdfs:label
PREFIX owl:  <http://www.w3.org/2002/07/owl#>    # owl:sameAs (Wikidata cross-links)
```

Additional prefixes seen in responses:

```sparql
PREFIX foaf: <http://xmlns.com/foaf/0.1/>        # foaf:depiction (images), foaf:isPrimaryTopicOf
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>  # skos:exactMatch
PREFIX dct:  <http://purl.org/dc/terms/>         # dct:subject (categories)
PREFIX xsd:  <http://www.w3.org/2001/XMLSchema#> # xsd:date, xsd:integer (for typed literals in FILTER)
```

---

## SPARQL endpoint reference

| Parameter | Value | Notes |
|-----------|-------|-------|
| Endpoint | `https://dbpedia.org/sparql` | GET with URL-encoded params |
| `format` | `application/sparql-results+json` or `json` | Both work |
| `timeout` | milliseconds, e.g. `30000` | Soft limit; server may ignore for cheap queries |
| `default-graph-uri` | `http://dbpedia.org` | Optional; omitting still works for most queries |
| Error on bad query | HTTP 400 | Body: `Virtuoso 37000 Error SP030: ...` |
| Total triples | ~1.43 billion | As of 2026-04-18 |

---

## Gotchas

**`dbo:abstract` is not available on the public SPARQL endpoint.** As of 2026-04-18, `SELECT (count(*) as ?c) WHERE { ?s dbo:abstract ?ab }` returns 0. The predicate is documented but the data is not loaded into the public instance. Use the Lookup API `comment` field for a snippet, or `dbo:description` (multi-language, short) as a fallback.

**`data.json` uses `'lang'` key; SPARQL JSON responses use `'xml:lang'`.** Both formats: `{'type': 'literal', 'value': 'Nikola Tesla', 'lang': 'en'}` (data.json) vs `{'type': 'literal', 'xml:lang': 'en', 'value': 'Nikola Tesla'}` (SPARQL JSON). Use `b['name'].get('xml:lang') or b['name'].get('lang')` if you read both. Inside SPARQL, `FILTER(lang(?x) = 'en')` always works regardless.

**Dirty numeric data from Wikipedia infoboxes.** `dbo:populationTotal` can contain wildly wrong values: Dusmareb (Somalia) shows 680,000,407; Rabaul shows 388,517,044. Always add sanity bounds: `FILTER(?pop > 0) FILTER(?pop < 100000000)`. Budget values are stored as floats with scientific notation (`1.6E8`); some have clearly wrong values from parsing failures.

**`dbo:` vs `dbp:` — prefer `dbo:` for reliability.** `dbp:` properties are raw Wikipedia infobox keys (e.g., `dbp:wikiPageUsesTemplate`, `dbp:nativeNameLang`) and vary by article. `dbo:` is the cleaned ontological mapping and is more consistent across entities. For numeric data always use `dbo:` when available.

**Duplicate results without `DISTINCT`.** Joining via multiple predicates (e.g., `dbo:birthPlace` with multiple values) multiplies rows. Always use `SELECT DISTINCT` unless you specifically want all combinations.

**Resource names are underscore-encoded Wikipedia article titles.** `"Albert Einstein"` → `dbr:Albert_Einstein` or `https://dbpedia.org/resource/Albert_Einstein`. Construct directly only when you are certain of the article title; use the Lookup API otherwise.

**The `label` and `comment` fields in Lookup API contain HTML `<B>` bold tags** around matched query terms. Strip with regex before displaying: `re.sub(r'<[^>]+>', '', s)`.

**`default-graph-uri` matters for unbound subject queries.** `SELECT ?s ?p ?o WHERE { ?s ?p ?o }` without `default-graph-uri=http://dbpedia.org` may return results from internal Virtuoso system graphs. Specify `default-graph-uri=http://dbpedia.org` when doing full-graph scans.

**DBpedia SPARQL availability is unreliable.** The public endpoint at `dbpedia.org/sparql` has periods of downtime or very slow response. If you get HTTP 500 or a connection timeout, retry once after 5s. There is no official mirror; the endpoint either responds within ~3s or hangs.

**HTTP 400 on query errors, not HTTP 200 with error body.** Unlike some SPARQL endpoints that return HTTP 200 with an error inside the JSON, DBpedia returns HTTP 400 with a Virtuoso error string in the body. Wrap calls in `try/except urllib.error.HTTPError`.

**SSL certificates may fail with Python's default context on some systems.** The `helpers.http_get` function uses `urllib` and may raise `SSLCertVerificationError` on macOS Python 3.11 without the `certifi` bundle. The SPARQL endpoint works fine with `curl`. If `http_get` raises SSL errors, use `urllib.request.urlopen` directly or install `certifi`.

**`dbo:releaseDate` on films is frequently absent or multi-valued.** Many films have multiple release dates (premiere, wide release, country-specific). Use `OPTIONAL { ?film dbo:releaseDate ?year }` and take the minimum, or drop the date filter entirely and filter by title substring.

**Wikidata `owl:sameAs` links return multiple Wikidata entity IDs** (e.g., Einstein returns Q937, Q19088, Q215627 — the person, the wikidata type for physicists, etc.). Filter by `strstarts(str(?wd), 'http://www.wikidata.org/entity/Q')` and look for the lowest Q-number, which is typically the main entity.

---

## Complete working example

```python
import json, re, urllib.parse, urllib.request, urllib.error
from helpers import http_get

def sparql(query: str, timeout_ms: int = 30000) -> list[dict]:
    """Run SPARQL SELECT. Returns list of binding dicts."""
    url = "https://dbpedia.org/sparql?" + urllib.parse.urlencode({
        "query": query,
        "format": "application/sparql-results+json",
        "timeout": str(timeout_ms),
    })
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout_ms / 1000 + 10) as r:
            return json.loads(r.read())["results"]["bindings"]
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"SPARQL error {e.code}: {e.read().decode()[:300]}")

def lookup_uri(name: str, type_filter: str = "") -> str | None:
    """Resolve a human name to a DBpedia resource URI. Returns None if not found."""
    params = {"query": name, "format": "json", "maxResults": "1"}
    if type_filter:
        params["typeName"] = type_filter
    raw = http_get("https://lookup.dbpedia.org/api/search?" + urllib.parse.urlencode(params))
    docs = json.loads(raw)["docs"]
    return docs[0]["resource"][0] if docs else None

def entity_props(resource_uri: str) -> dict:
    """Fetch all properties for an entity. Returns predicate→values dict."""
    name = resource_uri.split("/")[-1]
    raw = http_get(f"https://dbpedia.org/data/{name}.json")
    return json.loads(raw).get(resource_uri, {})

def strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s)

# --- Example: look up a scientist and get structured data ---
uri = lookup_uri("Nikola Tesla", type_filter="Scientist")
# uri == 'http://dbpedia.org/resource/Nikola_Tesla'

props = entity_props(uri)
birthdate  = props.get("http://dbpedia.org/ontology/birthDate", [{}])[0].get("value")
thumbnail  = props.get("http://dbpedia.org/ontology/thumbnail", [{}])[0].get("value")
labels     = props.get("http://www.w3.org/2000/01/rdf-schema#label", [])
en_label   = next((l["value"] for l in labels if l.get("lang") == "en"), None)
print(en_label, birthdate, thumbnail)
# Nikola Tesla  1856-07-10  http://commons.wikimedia.org/.../Tesla_circa_1890.jpeg?width=300

# SPARQL for richer context: birthplace label + Wikidata cross-link
bindings = sparql(f"""
PREFIX dbo:  <http://dbpedia.org/ontology/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:  <http://www.w3.org/2002/07/owl#>
SELECT ?bpLabel ?wd WHERE {{
  <{uri}> dbo:birthPlace ?bp .
  ?bp rdfs:label ?bpLabel .
  OPTIONAL {{
    <{uri}> owl:sameAs ?wd .
    FILTER(strstarts(str(?wd), 'http://www.wikidata.org/entity/Q'))
  }}
  FILTER(lang(?bpLabel) = 'en')
}} LIMIT 3
""")
for b in bindings:
    bp  = b.get("bpLabel", {}).get("value")
    wd  = b.get("wd", {}).get("value")
    print(f"  birthPlace: {bp}  wikidata: {wd}")
# birthPlace: Smiljan, Croatia  wikidata: http://www.wikidata.org/entity/Q9036
# Confirmed 2026-04-18
```
