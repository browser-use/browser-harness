# OpenAlex — Scraping & Data Extraction

`https://api.openalex.org` — open academic knowledge graph covering 260M+ works, 90M+ authors, 110K+ institutions. **Never use the browser for OpenAlex.** The entire API is JSON over HTTPS, completely free, no API key required. Add `mailto=your@email.com` to every request to use the polite pool (10 req/s vs 100 req/s limit, more reliable).

## Do this first

**Use `http_get` with the REST JSON API — one call, JSON response, no auth, no parsing library.**

```python
from helpers import http_get
import json

data = json.loads(http_get(
    "https://api.openalex.org/works?search=transformer+attention&per-page=5&mailto=you@example.com"
))
works = data["results"]
total = data["meta"]["count"]
```

Always include `mailto=` to stay in the polite pool. Always parse with `json.loads()`.

## Common workflows

### Search papers (works)

```python
from helpers import http_get
import json

data = json.loads(http_get(
    "https://api.openalex.org/works"
    "?search=transformer+attention"
    "&per-page=5"
    "&sort=cited_by_count:desc"
    "&select=id,doi,display_name,publication_year,cited_by_count,open_access,primary_location"
    "&mailto=you@example.com"
))
print("total matching:", data["meta"]["count"])
for w in data["results"]:
    oa   = w["open_access"]
    loc  = w["primary_location"] or {}
    src  = loc.get("source") or {}
    print(w["id"].split("/")[-1], w["publication_year"], w["cited_by_count"], w["display_name"][:60])
    print("  doi:", w["doi"])
    print("  open access:", oa["is_oa"], "| pdf:", oa["oa_url"])
    print("  journal:", src.get("display_name"))
# Confirmed output (2026-04-18):
# W3151130473 2021 1887 CrossViT: Cross-Attention Multi-Scale Vision Transformer for I
#   doi: https://doi.org/10.1109/iccv48922.2021.00041
#   open access: False | pdf: None
#   journal: 2021 IEEE/CVF International Conference on Computer Vision (ICCV)
```

### Fetch single paper by OpenAlex ID or DOI

```python
from helpers import http_get
import json

# By OpenAlex ID (bare or full URL form both work)
w = json.loads(http_get("https://api.openalex.org/works/W2626778328?mailto=you@example.com"))
print(w["display_name"], w["cited_by_count"])
# Confirmed: Attention Is All You Need 6526

# By DOI (pass the full DOI URL as the entity ID)
w = json.loads(http_get(
    "https://api.openalex.org/works/https://doi.org/10.1038/nature14539?mailto=you@example.com"
))
print(w["display_name"], w["cited_by_count"])
# Confirmed: Deep learning 79790
```

### Reconstruct abstract from inverted index

OpenAlex does not return abstracts as plain strings — they come as an inverted index (`{word: [position, ...], ...}`) due to publisher agreements. Reconstruct as follows:

```python
from helpers import http_get
import json

w = json.loads(http_get(
    "https://api.openalex.org/works/W2626778328"
    "?select=id,display_name,abstract_inverted_index"
    "&mailto=you@example.com"
))
aii = w.get("abstract_inverted_index") or {}
words_pos = [(pos, word) for word, positions in aii.items() for pos in positions]
abstract = " ".join(word for _, word in sorted(words_pos))
print(abstract[:200])
# Confirmed: The dominant sequence transduction models are based on complex recurrent
# or convolutional neural networks in an encoder-decoder configuration...
```

### Author lookup

```python
from helpers import http_get
import json

# Search by name
data = json.loads(http_get(
    "https://api.openalex.org/authors?search=geoffrey+hinton&per-page=3&mailto=you@example.com"
))
for a in data["results"]:
    bare_id = a["id"].split("/")[-1]    # e.g. A5108093963
    print(bare_id, a["display_name"], a["works_count"], "works |", a["cited_by_count"], "cites")
    affils = a.get("affiliations", [])
    if affils:
        print("  latest affil:", affils[0]["institution"]["display_name"])
# Confirmed:
# A5108093963 Geoffrey E. Hinton 384 works | 446018 cites
#   latest affil: University of New Brunswick

# Fetch by bare ID
a = json.loads(http_get("https://api.openalex.org/authors/A5108093963?mailto=you@example.com"))
print(a["display_name"], a["works_count"])
# Confirmed: Geoffrey E. Hinton 384

# Get all works by this author (sorted by citations)
works_data = json.loads(http_get(
    "https://api.openalex.org/works"
    "?filter=author.id:A5108093963"
    "&per-page=5&sort=cited_by_count:desc"
    "&select=id,display_name,cited_by_count,publication_year"
    "&mailto=you@example.com"
))
for w in works_data["results"]:
    print(w["publication_year"], w["display_name"][:55], w["cited_by_count"])
# Confirmed:
# 2015 Deep learning 79790
# 2017 ImageNet classification with deep convolutional neural netwo 75670
# 2008 Visualizing Data using t-SNE 35710
```

### Institution lookup

```python
from helpers import http_get
import json

data = json.loads(http_get(
    "https://api.openalex.org/institutions?search=MIT&per-page=3&mailto=you@example.com"
))
for inst in data["results"]:
    bare_id = inst["id"].split("/")[-1]     # e.g. I63966007
    print(bare_id, inst["display_name"], inst["country_code"], inst["works_count"], "works")
# Confirmed: I63966007 Massachusetts Institute of Technology US 340302 works

# Works from an institution
works = json.loads(http_get(
    "https://api.openalex.org/works"
    "?filter=institutions.id:I63966007"
    "&per-page=3&sort=cited_by_count:desc"
    "&select=id,display_name,cited_by_count,publication_year"
    "&mailto=you@example.com"
))
print("total MIT works:", works["meta"]["count"])
# Confirmed: 323992
```

### Concept/Topic lookup

Concepts (legacy, level-based hierarchy) and Topics (newer, 4-level hierarchy) are both available.

```python
from helpers import http_get
import json

# Concepts endpoint (Wikidata-linked)
data = json.loads(http_get(
    "https://api.openalex.org/concepts?search=machine+learning&per-page=5&mailto=you@example.com"
))
for c in data["results"]:
    bare_id = c["id"].split("/")[-1]    # e.g. C119857082
    print(bare_id, c["display_name"], "level:", c["level"], "works:", c["works_count"])
# Confirmed: C119857082 Machine learning level: 1 works: 4960536

# Topics endpoint (newer: domain > field > subfield > topic)
data2 = json.loads(http_get(
    "https://api.openalex.org/topics?search=machine+learning&per-page=3&mailto=you@example.com"
))
for t in data2["results"]:
    print(t["id"].split("/")[-1], t["display_name"])
    print("  ", t.get("domain", {}).get("display_name"), ">",
          t.get("field", {}).get("display_name"), ">",
          t.get("subfield", {}).get("display_name"))
# Confirmed: T11948 Machine Learning in Materials Science
#   Physical Sciences > Materials Science > Materials Chemistry
```

### Source (journal/venue) lookup

```python
from helpers import http_get
import json

data = json.loads(http_get(
    "https://api.openalex.org/sources?search=nature&per-page=3&mailto=you@example.com"
))
for s in data["results"]:
    bare_id = s["id"].split("/")[-1]    # e.g. S137773608
    print(bare_id, s["display_name"], s["type"], "issn:", s["issn"], "oa:", s["is_oa"])
# Confirmed: S137773608 Nature journal issn: ['0028-0836', '1476-4687'] oa: False

# Works in a source
works = json.loads(http_get(
    "https://api.openalex.org/works?filter=primary_location.source.id:S137773608"
    "&per-page=3&sort=cited_by_count:desc"
    "&select=id,display_name,cited_by_count"
    "&mailto=you@example.com"
))
print("Nature works:", works["meta"]["count"])
```

### Funder lookup

```python
from helpers import http_get
import json

data = json.loads(http_get(
    "https://api.openalex.org/funders?search=national+science+foundation&per-page=3&mailto=you@example.com"
))
for f in data["results"]:
    bare_id = f["id"].split("/")[-1]    # e.g. F4320306076
    print(bare_id, f["display_name"], f["country_code"], f["works_count"], "works")
# Confirmed: F4320306076 National Science Foundation US
```

### Citation traversal

```python
from helpers import http_get
import json

paper_id = "W2626778328"  # Attention Is All You Need

# Papers that CITE this paper (forward citations)
citing = json.loads(http_get(
    f"https://api.openalex.org/works?filter=cites:{paper_id}"
    "&per-page=5&sort=cited_by_count:desc"
    "&select=id,display_name,publication_year,cited_by_count"
    "&mailto=you@example.com"
))
print("papers citing Attention:", citing["meta"]["count"])
for w in citing["results"]:
    print(f"  {w['publication_year']} {w['display_name'][:55]} ({w['cited_by_count']} cites)")
# Confirmed: 6536 papers cite it; top: AlphaFold2 (43435), ViT (21409)

# Papers THIS paper cites (backward — list of IDs in the work object)
paper = json.loads(http_get(
    f"https://api.openalex.org/works/{paper_id}?select=referenced_works&mailto=you@example.com"
))
refs = paper.get("referenced_works", [])
ref_ids = [r.split("/")[-1] for r in refs]     # bare IDs like W1632114991
print(f"references {len(ref_ids)} works:", ref_ids[:3])
# Confirmed: references 28 works
```

### Cursor pagination (bulk harvest)

Use cursor pagination (not page-based) for more than 10,000 results. Page-based fails with HTTP 400 beyond page 50 at per-page=200.

```python
from helpers import http_get
import json, urllib.parse

def harvest_works(query_filter, max_results=1000, mailto="you@example.com"):
    """Yield work dicts using cursor pagination."""
    cursor = "*"
    collected = 0
    while collected < max_results:
        per_page = min(200, max_results - collected)
        encoded_cursor = urllib.parse.quote(cursor, safe="")
        url = (
            f"https://api.openalex.org/works"
            f"?filter={query_filter}"
            f"&per-page={per_page}"
            f"&cursor={encoded_cursor}"
            f"&select=id,display_name,publication_year,cited_by_count"
            f"&mailto={mailto}"
        )
        data = json.loads(http_get(url))
        results = data.get("results", [])
        if not results:
            break
        for w in results:
            yield w
        collected += len(results)
        next_cursor = data["meta"].get("next_cursor")
        if not next_cursor:
            break
        cursor = next_cursor

for w in harvest_works("concepts.id:C119857082,publication_year:2023", max_results=400):
    print(w["id"].split("/")[-1], w["display_name"][:55])
```

### Group-by analytics

```python
from helpers import http_get
import json

# Publication counts by year for machine learning papers
data = json.loads(http_get(
    "https://api.openalex.org/works"
    "?filter=concepts.id:C119857082"    # C119857082 = Machine learning concept
    "&group_by=publication_year"
    "&mailto=you@example.com"
))
print("groups_count:", data["meta"]["groups_count"])
for g in data.get("group_by", [])[:5]:
    print(f"  {g['key']}: {g['count']:,} works")
# Confirmed (2026-04-18):
#   2026: 5,678,538 works
#   2025: 5,332,194 works
#   2020: 3,966,880 works

# Other useful group_by fields: open_access.oa_status, type, institutions.country_code
# authorships.institutions.country_code, primary_location.source.id
```

## Filter syntax reference

Filters go in the `filter=` param as comma-separated `field:value` pairs. All conditions are AND-ed.

```
# Exact match
filter=publication_year:2023

# Full-text search on a field
filter=title.search:deep+learning

# Combine multiple (AND)
filter=title.search:CRISPR,publication_year:2022,open_access.is_oa:true

# OR within one field (pipe operator)
filter=publication_year:2022|2023

# Negation
filter=publication_year:!2020

# Range
filter=cited_by_count:>1000
filter=publication_year:<2010
filter=cited_by_count:100-500

# Nested field access
filter=author.id:A5108093963
filter=institutions.id:I63966007
filter=concepts.id:C119857082
filter=primary_location.source.id:S137773608
filter=open_access.is_oa:true
filter=cites:W2626778328         # papers citing this work
```

Commonly useful filter fields for works:

| Filter field | Example | Notes |
|---|---|---|
| `title.search` | `title.search:machine+learning` | Full-text on title |
| `abstract.search` | `abstract.search:attention` | Full-text on abstract |
| `publication_year` | `publication_year:2023` | Exact year |
| `from_publication_date` | `from_publication_date:2023-01-01` | Date range start |
| `to_publication_date` | `to_publication_date:2023-12-31` | Date range end |
| `cited_by_count` | `cited_by_count:>500` | Range with `>`, `<`, `-` |
| `open_access.is_oa` | `open_access.is_oa:true` | OA filter |
| `author.id` | `author.id:A5108093963` | By author OpenAlex ID |
| `institutions.id` | `institutions.id:I63966007` | By institution ID |
| `concepts.id` | `concepts.id:C119857082` | By concept ID |
| `primary_location.source.id` | `primary_location.source.id:S137773608` | By journal/source |
| `type` | `type:journal-article` | Work type |
| `language` | `language:en` | ISO 639-1 language code |
| `cites` | `cites:W2626778328` | Works citing this paper |
| `doi` | `doi:10.1038/nature14539` | By DOI (no `https://doi.org/` prefix) |

## URL and parameter reference

### API base

```
https://api.openalex.org/{entity_type}
```

Entity types: `works`, `authors`, `institutions`, `sources`, `concepts`, `topics`, `funders`, `publishers`

### Query parameters

| Parameter | Example | Notes |
|---|---|---|
| `search` | `search=deep+learning` | Full-text relevance search across entity |
| `filter` | `filter=publication_year:2023` | Structured filters (see above) |
| `sort` | `sort=cited_by_count:desc` | Sort field + direction; use `relevance_score:desc` with `search` |
| `per-page` | `per-page=200` | Max 200 per page |
| `page` | `page=2` | Page number; fails (HTTP 400) if `per-page * page > 10000` |
| `cursor` | `cursor=*` | Cursor for bulk pagination; `*` = first page |
| `select` | `select=id,doi,display_name` | Return only these fields (reduces payload) |
| `group_by` | `group_by=publication_year` | Aggregate counts by field (returns `group_by` array) |
| `mailto` | `mailto=you@example.com` | **Always include** — enables polite pool |

### Entity ID prefix convention

OpenAlex IDs use a letter prefix on the numeric ID:

| Prefix | Entity | Example |
|---|---|---|
| `W` | Work (paper) | `W2626778328` |
| `A` | Author | `A5108093963` |
| `I` | Institution | `I63966007` |
| `S` | Source (journal) | `S137773608` |
| `C` | Concept | `C119857082` |
| `T` | Topic | `T11948` |
| `F` | Funder | `F4320306076` |
| `P` | Publisher | `P4310319965` |

Full entity URLs: `https://openalex.org/{ID}` (canonical form returned in `id` field).
Bare ID is always `entity_url.split("/")[-1]`.

### Sort fields

Works: `cited_by_count`, `publication_date`, `relevance_score` (only with `search`), `fwci`
Authors: `cited_by_count`, `works_count`
All: append `:desc` or `:asc`

## Rate limits

| Pool | Rate | Daily cap |
|---|---|---|
| Polite pool (with `mailto=`) | 10 req/s | 100,000 req/day |
| Common pool (no `mailto`) | 100 req/s | 100,000 req/day |

- No API key required — the polite pool is opt-in via `mailto=`.
- Response includes `meta.cost_usd` (typically $0.001 per call).
- No `Retry-After` header when throttled — just add a short sleep on 429.
- For bulk harvesting >1,000 results, use cursor pagination + respect the polite pool.

## Gotchas

- **Never use the browser for OpenAlex.** The API returns complete structured JSON for all entity types. No HTML scraping needed.

- **`mailto=` goes in every call, not just once.** It is a query parameter, not a header. There is no session. Omitting it puts you in the common pool (higher contention, less predictable).

- **OpenAlex IDs in the `id` field are full URLs, not bare IDs.** The field returns `https://openalex.org/W2626778328`. Always `.split("/")[-1]` to get the bare `W2626778328` form needed for `filter=cites:`, `filter=author.id:`, etc.

- **DOI lookup uses the full DOI URL as the path parameter.** Correct: `GET /works/https://doi.org/10.1038/nature14539`. Incorrect: `GET /works/10.1038/nature14539` (returns 404).

- **Page-based pagination hard stops at 10,000 results.** `per-page=200&page=51` returns HTTP 400. Use `cursor=*` pagination for harvesting more than 10K results — it has no such limit.

- **`cursor=*` must be URL-encoded on subsequent pages.** The `next_cursor` value contains `+`, `=`, `/` characters. Always `urllib.parse.quote(cursor, safe="")` before interpolating into the URL.

- **`group_by` and `page` are incompatible — use `group_by` without `page`/`cursor`.** Group-by returns a `group_by` list, not `results`. The `per-page` param sets max groups returned (default 200).

- **`abstract_inverted_index` may be `null` for some papers.** Publisher agreements prevent OpenAlex from providing abstracts for many closed-access works. Always check `if aii:` before reconstructing.

- **`select` significantly reduces response size and latency.** A full work object has 50+ fields; specifying `select=id,doi,display_name,cited_by_count` cuts payload by ~90%. Always use `select=` in bulk harvests.

- **`sort=relevance_score:desc` only works with `search=`.** Using it without a `search` param returns results in undefined order. Use `cited_by_count:desc` or `publication_date:desc` for filter-only queries.

- **The `concepts` field is deprecated in favor of `topics`.** Concepts (Wikidata-linked, 5 levels) are still populated and useful, but OpenAlex now recommends `topics` (4-level hierarchy: domain > field > subfield > topic) going forward.

- **`open_access.oa_url` can be `null` even when `is_oa=true`.** Check `best_oa_location.pdf_url` instead — it is more reliably populated when an OA PDF exists.

- **Negation filter syntax is `field:!value`, not `field!=value`.** Example: `filter=publication_year:!2020` excludes 2020.

- **Author disambiguation is imperfect.** The same person may appear as multiple author entities. Use ORCID (`ids.orcid`) when available to cross-reference. The `display_name_alternatives` field lists name variants.

- **The `funders.grants_count` field returns `None` in API responses** despite the docs mentioning it. Use `works_count` and `cited_by_count` instead for funder-level metrics.

- **`per-page` with `cursor=*` ignores `page=`.** When cursor pagination is active, `page` is set to `null` in `meta`. Do not combine cursor + page.
