# Semantic Scholar — Scraping & Data Extraction

`https://api.semanticscholar.org` — free academic paper graph API. **Never use the browser.** All data is reachable via `http_get` or HTTP POST to the REST API. No API key required for basic use; key unlocks higher rate limits.

## Do this first

**Use the batch POST endpoint for known paper IDs — fast (0.2s for 5 papers), position-aligned results, up to 500 IDs per call.**

```python
import json
from helpers import http_get

# Batch fetch by S2 paper ID or external ID (ArXiv, PMID, CorpusID)
import urllib.request

ids = [
    'arXiv:1706.03762',         # Attention Is All You Need
    'arXiv:1810.04805',         # BERT
    'arXiv:2005.14165',         # GPT-3
]
body = json.dumps({'ids': ids}).encode()
req = urllib.request.Request(
    'https://api.semanticscholar.org/graph/v1/paper/batch'
    '?fields=title,year,citationCount,influentialCitationCount,authors,tldr',
    data=body,
    headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'},
)
with urllib.request.urlopen(req, timeout=20) as r:
    papers = json.loads(r.read())

for p in papers:
    if p is None:
        continue   # null = ID not found; result list is position-aligned with request
    print(p['year'], p['citationCount'], p['title'][:60])
    if p.get('tldr'):
        print('  TL;DR:', p['tldr']['text'][:80])
# Confirmed output (2026-04-19):
# 2017 173155 Attention is All you Need
#   TL;DR: A new simple network architecture, the Transformer, based solely on attention me...
# 2019 113137 BERT: Pre-training of Deep Bidirectional Transform
#   TL;DR: A new language representation model, BERT, designed to pre-train deep bidirectio...
# 2020  56710 Language Models are Few-Shot Learners
#   TL;DR: GPT-3 achieves strong performance on many NLP datasets, including translation, q...
```

For full-text **keyword search**, use `/paper/search/bulk` — it returns relevance-ranked results and supports sort, year filter, and token-based pagination. The `/paper/search` endpoint has extremely low unauthenticated rate limits (see Gotchas).

## Common workflows

### Fetch a single paper by ID

```python
import json
from helpers import http_get

# Supported ID prefixes: S2 hash (bare), arXiv:, PMID:, CorpusID:, MAG:
fields = 'title,year,authors,citationCount,influentialCitationCount,abstract,tldr,' \
         'externalIds,publicationDate,venue,journal,fieldsOfStudy,s2FieldsOfStudy,' \
         'openAccessPdf,publicationTypes,referenceCount'

paper = json.loads(http_get(
    f'https://api.semanticscholar.org/graph/v1/paper/arXiv:1706.03762?fields={fields}'
))
print(paper['paperId'])           # S2 hash ID (stable)
print(paper['externalIds'])       # {'ArXiv': '1706.03762', 'MAG': '...', 'CorpusId': 13756489}
print(paper['citationCount'])     # 173155
print(paper['influentialCitationCount'])  # 19629
print(paper['tldr']['text'])      # AI-generated one-sentence summary
print(paper['publicationDate'])   # '2017-06-12'
print(paper['openAccessPdf'])     # {'url': '...', 'status': None, 'license': None}
# Confirmed output (2026-04-19):
# paperId: 204e3073870fae3d05bcbc2f6a8e263d9b72e776
# citationCount: 173155  influentialCitationCount: 19629
```

### Keyword search — use /paper/search/bulk

The bulk search endpoint supports large result sets with token pagination, sort, and filters. Returns up to 1000 papers per page regardless of the `limit` param.

```python
import json
from helpers import http_get

# Sort options: citationCount:desc, publicationDate:desc, paperId (default, random-ish)
resp = json.loads(http_get(
    'https://api.semanticscholar.org/graph/v1/paper/search/bulk'
    '?query=attention+transformer'
    '&fields=title,year,citationCount'
    '&sort=citationCount:desc'
    '&year=2020-2026'              # optional year range
    # '&publicationTypes=JournalArticle,Conference'  # optional type filter
    # '&fieldsOfStudy=Computer+Science'              # optional domain filter
))

print(resp['total'])               # e.g. 50908 total matches
token = resp.get('token')         # use for next page
for p in resp['data'][:5]:
    print(p['year'], p['citationCount'], p['title'][:60])
# Confirmed output (2026-04-19):
# total: 50908
# 2017 173155 Attention is All you Need
# 2020  60619 An Image is Worth 16x16 Words: Transformers for Im
# 2021  31188 Swin Transformer: Hierarchical Vision Transformer
# 2020   8846 Training data-efficient image transformers & disti
# 2021   7880 SegFormer: Simple and Efficient Design for Semanti
```

### Pagination through bulk search results

```python
import json
from helpers import http_get

BASE = (
    'https://api.semanticscholar.org/graph/v1/paper/search/bulk'
    '?query=large+language+models&fields=title,year,citationCount&sort=citationCount:desc'
)

resp = json.loads(http_get(BASE))
all_papers = list(resp['data'])
total = resp['total']
token = resp.get('token')

while token and len(all_papers) < total:
    resp = json.loads(http_get(f'{BASE}&token={token}'))
    all_papers.extend(resp['data'])
    token = resp.get('token')
    # Add time.sleep(1) here for sustained crawls to stay within rate limits

print(f'Fetched {len(all_papers)} of {total} papers')
```

### Best-match search (single result, fast)

Use `/paper/search/match` when you want the closest title match for a known paper name — faster than bulk search and rarely rate-limited.

```python
import json
from helpers import http_get

result = json.loads(http_get(
    'https://api.semanticscholar.org/graph/v1/paper/search/match'
    '?query=attention+is+all+you+need'
    '&fields=title,year,paperId,citationCount'
))
p = result['data'][0]
print(p['paperId'], p['year'], p['citationCount'], p['title'])
# Confirmed output (2026-04-19):
# 204e3073870fae3d05bcbc2f6a8e263d9b72e776 2017 173155 Attention is All you Need
# matchScore is also present in each result
```

### Paginated citations and references

```python
import json
from helpers import http_get

paper_id = '204e3073870fae3d05bcbc2f6a8e263d9b72e776'

# Citations: papers that cite this paper
# 'citingPaper' key wraps each result
resp = json.loads(http_get(
    f'https://api.semanticscholar.org/graph/v1/paper/{paper_id}/citations'
    '?fields=title,year,citationCount,authors&limit=100&offset=0'
))
print('offset:', resp['offset'], 'next:', resp['next'])   # 'next' is None at last page
for item in resp['data']:
    cp = item['citingPaper']
    print(cp['year'], cp['citationCount'], cp['title'][:50])

# References: papers this paper cites
# 'citedPaper' key wraps each result
resp = json.loads(http_get(
    f'https://api.semanticscholar.org/graph/v1/paper/{paper_id}/references'
    '?fields=title,year,citationCount&limit=50&offset=0'
))
# resp also contains 'citingPaperInfo' with metadata about the source paper
for item in resp['data']:
    ref = item['citedPaper']
    print(ref.get('year'), ref.get('title', '')[:50])
```

### Author lookup and search

```python
import json
from helpers import http_get

# Direct author fetch by S2 author ID
author = json.loads(http_get(
    'https://api.semanticscholar.org/graph/v1/author/1751762'
    '?fields=name,affiliations,homepage,paperCount,citationCount,hIndex,papers'
))
print(author['name'])            # 'Yoshua Bengio'
print(author['hIndex'])          # 213
print(author['citationCount'])   # 566931
# 'papers' list is capped at 500 inline — use /author/{id}/papers endpoint for full list

# Author search by name
results = json.loads(http_get(
    'https://api.semanticscholar.org/graph/v1/author/search'
    '?query=yoshua+bengio&fields=name,paperCount,citationCount,hIndex&limit=3'
))
print(results['total'])          # 17
for a in results['data']:
    print(a['authorId'], a['citationCount'], a['name'])
# Confirmed output (2026-04-19):
# total: 17
# 1751762 566931 Yoshua Bengio
# 2211024206 1019 Y. Bengio
# 1865800402 20339 Y. Bengio

# Paginated papers for an author
papers_resp = json.loads(http_get(
    'https://api.semanticscholar.org/graph/v1/author/1751762/papers'
    '?fields=title,year,citationCount,venue&limit=10&offset=0'
))
print(papers_resp['next'])       # offset for next page; None when exhausted
```

### Bulk author fetch

```python
import json, urllib.request

ids = ['1751762', '2262347']     # Yoshua Bengio, A. Turing
body = json.dumps({'ids': ids}).encode()
req = urllib.request.Request(
    'https://api.semanticscholar.org/graph/v1/author/batch'
    '?fields=name,paperCount,citationCount,hIndex',
    data=body,
    headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'},
)
with urllib.request.urlopen(req, timeout=20) as r:
    authors = json.loads(r.read())
for a in authors:
    print(a['authorId'], a['hIndex'], a['name'])
# Confirmed output (2026-04-19):
# 1751762 213 Yoshua Bengio
# 2262347  20 A. Turing
```

### Paper recommendations

```python
import json, urllib.request

# POST: supply positive (and optionally negative) paper IDs as seeds
body = json.dumps({
    'positivePaperIds': ['649def34f8be52c8b66281af98ae884c09aef38b'],
    'negativePaperIds': [],
}).encode()
req = urllib.request.Request(
    'https://api.semanticscholar.org/recommendations/v1/papers/'
    '?fields=title,year,citationCount&limit=5',
    data=body,
    headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'},
)
with urllib.request.urlopen(req, timeout=20) as r:
    recs = json.loads(r.read())['recommendedPapers']
for p in recs:
    print(p['year'], p['citationCount'], p['title'][:60])
# Confirmed working (2026-04-19) — returns 5 results ordered by model score
```

## API reference

### ID formats for `/paper/{id}` and batch `ids` list

| Format | Example |
|---|---|
| S2 hash (bare) | `204e3073870fae3d05bcbc2f6a8e263d9b72e776` |
| `arXiv:` | `arXiv:1706.03762` |
| `PMID:` | `PMID:25462856` |
| `CorpusID:` | `CorpusID:13756489` |
| `MAG:` | `MAG:2963403868` |

### Paper fields

| Field | Type | Notes |
|---|---|---|
| `paperId` | string | Stable S2 hash ID |
| `externalIds` | object | `ArXiv`, `MAG`, `DBLP`, `CorpusId`, `PMID`, `DOI` |
| `title` | string | |
| `abstract` | string | May be null |
| `year` | int | May be null |
| `publicationDate` | string | `YYYY-MM-DD`, may be null |
| `venue` | string | Conference/journal name |
| `journal` | object | `{pages, name}` |
| `publicationTypes` | list | `JournalArticle`, `Conference`, `Review`, etc. |
| `citationCount` | int | Total citations |
| `influentialCitationCount` | int | Highly-influential citations only |
| `referenceCount` | int | Number of references |
| `authors` | list | `[{authorId, name}]`; request `authors.affiliations` for more |
| `fieldsOfStudy` | list | Coarse field labels, e.g. `["Computer Science"]` |
| `s2FieldsOfStudy` | list | `[{category, source}]`, finer-grained |
| `openAccessPdf` | object | `{url, status, license}` |
| `tldr` | object | `{model, text}` — AI-generated one-sentence summary |
| `embedding` | object | S2 vector embedding (often null without API key) |
| `citations` | list | Inline, capped at 1000 — use `/citations` endpoint instead |
| `references` | list | Inline, complete — or use `/references` endpoint |

### Author fields

`authorId`, `name`, `affiliations`, `homepage`, `paperCount`, `citationCount`, `hIndex`, `papers`

### Bulk search filters (`/paper/search/bulk`)

| Param | Example | Notes |
|---|---|---|
| `query` | `attention+transformer` | URL-encoded keyword query |
| `fields` | `title,year,citationCount` | Comma-separated field names |
| `sort` | `citationCount:desc` | `citationCount:asc/desc`, `publicationDate:asc/desc`, `paperId` |
| `year` | `2020-2024` or `2023` | Year range or single year |
| `publicationTypes` | `JournalArticle,Conference` | Comma-separated |
| `fieldsOfStudy` | `Computer+Science` | URL-encoded |
| `token` | opaque string | From previous response, for next page |

### Rate limits (unauthenticated)

| Endpoint | Observed limit |
|---|---|
| `/paper/{id}` GET | ~1–5 req/min |
| `/paper/search` GET | Very strict — ~1 req/hour or less; **avoid without API key** |
| `/paper/search/match` GET | Moderate; rarely blocked |
| `/paper/search/bulk` GET | Most generous search option |
| `/paper/batch` POST | Moderate; 500 IDs max per call |
| `/author/{id}` GET | ~1–5 req/min |
| `/author/search` GET | Moderate |
| `/author/batch` POST | Moderate |
| `/author/{id}/papers` GET | Moderate |
| `/paper/{id}/citations` GET | Moderate |
| `/paper/{id}/references` GET | Moderate |
| `/recommendations/v1/papers/` POST | Most generous |

No rate limit headers in 429 responses — no `Retry-After`. For sustained crawls, add `time.sleep(1)` between calls. Apply for an API key at `https://www.semanticscholar.org/product/api#api-key-form` for 1 req/s+ limits.

## Gotchas

- **`/paper/search` is effectively unusable unauthenticated.** After just a few calls it returns 429 for 60+ minutes. Use `/paper/search/bulk` for keyword search (more generous limit, returns 1000 results per page with token pagination) or `/paper/search/match` for single best-title-match lookups.

- **`/paper/search/bulk` ignores the `limit` parameter** — it always returns up to 1000 results per page. The `token` field in the response is the cursor for the next page; when absent, you've exhausted results.

- **Batch result list is position-aligned, not filtered.** Missing IDs return `null` at their position in the result array. Always check `if p is not None` before accessing fields.

- **Batch max is 500 IDs.** Sending 501 returns `HTTP 400: Maximum 500 ids allowed in input list`.

- **`citations` and `references` inline in paper detail are capped.** `citations` is capped at 1000 (even when `citationCount` is 173,000+). Use `/paper/{id}/citations?limit=1000&offset=N` for full traversal. `references` inline appears complete.

- **`/citations` response wraps each item in `{citingPaper: {...}}`**, not a flat paper object. `/references` wraps in `{citedPaper: {...}}`. The `/references` response also includes a top-level `citingPaperInfo` field with metadata about the source paper.

- **Pagination on `/citations` and `/references` has no `total` field.** The total citation count is only available from the paper's `citationCount` field. Use `next` key — when it's absent (or equal to offset + returned items past total), you've hit the last page. Max `limit` is 1000 per request.

- **`tldr` is null for many older or low-profile papers.** The AI summary model has limited coverage; always check `if p.get('tldr')` before accessing `.text`.

- **`openAccessPdf.url` is often an empty string**, even when the paper is on ArXiv. The `externalIds.ArXiv` field is more reliable for constructing a PDF URL: `f"https://arxiv.org/pdf/{paper['externalIds']['ArXiv']}"`.

- **Author `papers` list inline is capped at 500.** Use `/author/{id}/papers?limit=1000&offset=N` for the full publication list.

- **Author search returns duplicates for the same person.** The API may return multiple `authorId` values for the same real-world author (disambiguation is imperfect). Pick the entry with highest `citationCount` or largest `paperCount` when looking up a well-known researcher.

- **No `Retry-After` header on 429.** The API gives no guidance on when to retry. For the `/paper/search` endpoint, don't retry without a key — the cooldown is very long (observed 60+ minutes). For other endpoints, 10–15s is usually sufficient.

- **`http_get` from helpers.py works for GET requests.** For POST (batch, recommendations), use `urllib.request.Request` with `data=` and `Content-Type: application/json` header directly, as `http_get` does not support POST bodies.
