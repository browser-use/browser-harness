# ArXiv — Scraping & Data Extraction

`https://arxiv.org` — open-access preprint server. **Never use the browser for ArXiv.** All data is reachable via `http_get` using the Atom API or HTML meta tags. No API key required.

## Do this first

**Use the Atom API for any paper search or metadata fetch — one call, XML response, no auth.**

```python
import xml.etree.ElementTree as ET
from helpers import http_get

NS = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

xml = http_get("http://export.arxiv.org/api/query?search_query=ti:transformer+AND+cat:cs.LG&max_results=5&sortBy=submittedDate&sortOrder=descending")
root = ET.fromstring(xml)
entries = root.findall('atom:entry', NS)
```

Use `id_list` for known paper IDs — supports comma-separated batch fetch in a single call.

Use `http_get` on `https://arxiv.org/abs/{id}` + regex for `citation_*` meta tags when you need the full abstract from an HTML page.

## Common workflows

### Search papers (API)

```python
import xml.etree.ElementTree as ET
from helpers import http_get

NS = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

xml = http_get(
    "http://export.arxiv.org/api/query"
    "?search_query=ti:transformer+AND+cat:cs.LG"
    "&max_results=5&sortBy=submittedDate&sortOrder=descending"
)
root = ET.fromstring(xml)
entries = root.findall('atom:entry', NS)
for e in entries:
    title     = e.find('atom:title', NS).text.strip().replace('\n', ' ')
    arxiv_id  = e.find('atom:id', NS).text.split('/')[-1]   # e.g. '2604.15259v1'
    published = e.find('atom:published', NS).text[:10]       # '2026-04-16'
    updated   = e.find('atom:updated', NS).text[:10]
    abstract  = e.find('atom:summary', NS).text.strip()
    authors   = [a.find('atom:name', NS).text for a in e.findall('atom:author', NS)]
    cats      = [c.get('term') for c in e.findall('atom:category', NS)]
    primary   = e.find('arxiv:primary_category', NS).get('term')
    comment   = e.find('arxiv:comment', NS)
    pdf_link  = next((l.get('href') for l in e.findall('atom:link', NS) if l.get('title') == 'pdf'), None)
    abs_link  = next((l.get('href') for l in e.findall('atom:link', NS) if l.get('rel') == 'alternate'), None)
    print(arxiv_id, published, title[:60])
    print("  Authors:", authors[:2])
    print("  PDF:", pdf_link)
# Confirmed output (2026-04-18):
# 2604.15259v1 2026-04-16 Stability and Generalization in Looped Transformers
#   Authors: ['Asher Labovich']
#   PDF: https://arxiv.org/pdf/2604.15259v1
```

### Fetch single paper by ID (API)

```python
import xml.etree.ElementTree as ET
from helpers import http_get

NS = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

xml = http_get("http://export.arxiv.org/api/query?id_list=1706.03762")
root = ET.fromstring(xml)
e = root.find('atom:entry', NS)
title      = e.find('atom:title', NS).text.strip()
abstract   = e.find('atom:summary', NS).text.strip()
categories = [c.get('term') for c in e.findall('atom:category', NS)]
pdf_link   = next((l.get('href') for l in e.findall('atom:link', NS) if l.get('title') == 'pdf'), None)
print("Title:", title)
print("Categories:", categories)
print("PDF:", pdf_link)
print("Abstract:", abstract[:200])
# Confirmed output:
# Title: Attention Is All You Need
# Categories: ['cs.CL', 'cs.LG']
# PDF: https://arxiv.org/pdf/1706.03762v7
# Abstract: The dominant sequence transduction models are based on complex recurrent...
```

### Batch fetch by comma-separated IDs (single call — fast)

Fetching 10 IDs in one call takes ~2s. Prefer this over parallel single-ID fetches.

```python
import xml.etree.ElementTree as ET
from helpers import http_get

NS = {'atom': 'http://www.w3.org/2005/Atom'}

ids = ['1706.03762', '1810.04805', '2005.14165']  # Transformer, BERT, GPT-3
xml = http_get(f"http://export.arxiv.org/api/query?id_list={','.join(ids)}&max_results={len(ids)}")
root = ET.fromstring(xml)
for e in root.findall('atom:entry', NS):
    arxiv_id  = e.find('atom:id', NS).text.split('/')[-1]
    title     = e.find('atom:title', NS).text.strip()
    published = e.find('atom:published', NS).text[:10]
    print(arxiv_id, published, title[:60])
# Confirmed output:
# 1512.03385v1 2015-12-10 Deep Residual Learning for Image Recognition
# 1706.03762v7 2017-06-12 Attention Is All You Need
# 2005.14165v4 2020-05-28 Language Models are Few-Shot Learners
# 1810.04805v2 2018-10-11 BERT: Pre-training of Deep Bidirectional Transformers...
# Note: order returned may differ from order requested
```

### Parallel fetch (ThreadPoolExecutor for independent IDs)

Use only when IDs are not known upfront or when mixing with other work. For pure batch, single comma-separated `id_list` call is faster.

```python
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

NS = {'atom': 'http://www.w3.org/2005/Atom'}

def fetch_paper(arxiv_id):
    xml = http_get(f"http://export.arxiv.org/api/query?id_list={arxiv_id}")
    root = ET.fromstring(xml)
    e = root.find('atom:entry', NS)
    if e is None:
        return None
    return {
        'id': arxiv_id,
        'title': e.find('atom:title', NS).text.strip(),
        'published': e.find('atom:published', NS).text[:10],
    }

ids = ['1706.03762', '1810.04805', '2005.14165']
with ThreadPoolExecutor(max_workers=3) as ex:
    papers = list(ex.map(fetch_paper, ids))
for p in papers:
    print(p['id'], p['published'], p['title'][:60])
# Confirmed working — max_workers=3 is safe; don't exceed 5 for continuous crawling
```

### HTML abstract page — citation_* meta tags

Use this when you want the full abstract or the versionless PDF URL without parsing Atom XML.

```python
import re
from helpers import http_get

html = http_get("https://arxiv.org/abs/1706.03762", headers={"User-Agent": "Mozilla/5.0"})
# HTML page is ~48 KB, fully static, no JS required

title   = re.search(r'<meta name="citation_title" content="([^"]+)"', html)
pdf_url = re.search(r'<meta name="citation_pdf_url" content="([^"]+)"', html)
authors = re.findall(r'<meta name="citation_author" content="([^"]+)"', html)
date    = re.search(r'<meta name="citation_date" content="([^"]+)"', html)
arxiv_id = re.search(r'<meta name="citation_arxiv_id" content="([^"]+)"', html)
abstract = re.search(r'<meta name="citation_abstract" content="([^"]+)"', html)

print("Title:", title.group(1) if title else None)
print("PDF:", pdf_url.group(1) if pdf_url else None)
print("Authors:", authors[:3])
print("Date:", date.group(1) if date else None)
print("ID:", arxiv_id.group(1) if arxiv_id else None)
# Confirmed output for 1706.03762:
# Title: Attention Is All You Need
# PDF: https://arxiv.org/pdf/1706.03762   (no version suffix — always latest)
# Authors: ['Vaswani, Ashish', 'Shazeer, Noam', 'Parmar, Niki']
# Date: 2017/06/12
# ID: 1706.03762
```

All `citation_*` meta tags present on the abs page:
- `citation_title` — paper title
- `citation_author` — one tag per author, format `"Last, First"`
- `citation_date` — submission date `YYYY/MM/DD`
- `citation_online_date` — latest version date `YYYY/MM/DD`
- `citation_pdf_url` — versionless PDF URL (redirects to latest)
- `citation_arxiv_id` — bare ID without version suffix
- `citation_abstract` — full abstract text

### Category search with pagination

```python
import xml.etree.ElementTree as ET
from helpers import http_get

NS = {
    'atom': 'http://www.w3.org/2005/Atom',
    'opensearch': 'http://a9.com/-/spec/opensearch/1.1/',
}

# Page 1
xml = http_get(
    "http://export.arxiv.org/api/query"
    "?search_query=cat:cs.AI"
    "&max_results=10&start=0&sortBy=lastUpdatedDate&sortOrder=descending"
)
root = ET.fromstring(xml)
total   = root.find('opensearch:totalResults', NS).text   # e.g. '172726'
start_i = root.find('opensearch:startIndex', NS).text
per_pg  = root.find('opensearch:itemsPerPage', NS).text
print(f"Total cs.AI papers: {total}")  # Confirmed: 172726 (2026-04-18)

entries = root.findall('atom:entry', NS)

# Page 2: increment start
xml2 = http_get(
    "http://export.arxiv.org/api/query"
    "?search_query=cat:cs.AI"
    "&max_results=10&start=10&sortBy=lastUpdatedDate&sortOrder=descending"
)
```

## URL and ID reference

### API base URL

```
http://export.arxiv.org/api/query
```

HTTPS also works: `https://export.arxiv.org/api/query`

### Query parameters

| Parameter | Values | Notes |
|---|---|---|
| `search_query` | `ti:word`, `au:name`, `abs:phrase`, `cat:cs.LG`, combine with `AND`/`OR`/`ANDNOT` | URL-encode spaces as `+` |
| `id_list` | `1706.03762` or `1706.03762,1810.04805` | Comma-separated; version suffix optional |
| `max_results` | integer (default 10, max 2000) | |
| `start` | integer (default 0) | Offset for pagination |
| `sortBy` | `relevance`, `lastUpdatedDate`, `submittedDate` | |
| `sortOrder` | `ascending`, `descending` | |

### Search field prefixes

| Prefix | Searches |
|---|---|
| `ti:` | Title |
| `au:` | Author name |
| `abs:` | Abstract |
| `co:` | Comment |
| `jr:` | Journal reference |
| `cat:` | Category (e.g. `cat:cs.LG`) |
| `all:` | All fields |

### PDF and abstract URL construction

```python
import re

arxiv_id = "1706.03762v7"                        # from API atom:id field
bare_id = re.sub(r'v\d+$', '', arxiv_id)          # strip version: '1706.03762'

pdf_versioned   = f"https://arxiv.org/pdf/{arxiv_id}"   # specific version
pdf_latest      = f"https://arxiv.org/pdf/{bare_id}"    # always redirects to latest
abs_versioned   = f"https://arxiv.org/abs/{arxiv_id}"
abs_latest      = f"https://arxiv.org/abs/{bare_id}"
```

The API's `atom:link[@title='pdf']` href includes the version suffix. The HTML `citation_pdf_url` meta tag does not — it always resolves to the latest.

### Category codes (confirmed paper counts, 2026-04-18)

| Code | Area | Papers |
|---|---|---|
| `cs.LG` | Machine Learning | 261,782 |
| `cs.CV` | Computer Vision | 189,049 |
| `cs.AI` | Artificial Intelligence | 172,726 |
| `cs.CL` | Computation and Language (NLP) | 106,724 |
| `stat.ML` | Statistics - Machine Learning | 76,902 |
| `math.OC` | Optimization and Control | 60,669 |
| `eess.AS` | Audio and Speech Processing | 21,288 |
| `cs.NE` | Neural and Evolutionary Computing | 17,475 |
| `q-bio.NC` | Neurons and Cognition | 11,903 |

Full category taxonomy: https://arxiv.org/category_taxonomy

## Gotchas

- **Never use the browser for ArXiv.** The abstract page (`/abs/`) and search results are fully server-side rendered static HTML. `http_get` is sufficient for everything including full abstracts, author lists, and PDF URLs.

- **Always define the namespace dict.** Without `NS = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}`, `findall('atom:entry')` silently returns `[]`. All ArXiv Atom elements live in the `http://www.w3.org/2005/Atom` namespace; ArXiv-specific fields (`comment`, `primary_category`, `journal_ref`, `doi`) live in `http://arxiv.org/schemas/atom`.

- **Batch single `id_list` call is faster than ThreadPoolExecutor.** A comma-separated `id_list` with 10 IDs resolved in one call (1.91s) vs. 10 separate `ThreadPoolExecutor` calls (6.34s). Use the batch form when you already have the IDs.

- **`atom:id` contains a URL, not a bare ID.** The element text is `http://arxiv.org/abs/1706.03762v7` — always split on `/` and take `[-1]` to get the bare ID with version. Strip version with `re.sub(r'v\d+$', '', id)` if needed.

- **Batch `id_list` returns entries in unpredictable order.** When fetching `1706.03762,1810.04805,2005.14165`, entries came back ordered by publication date, not by the order given in the request. Index by ID, not position.

- **`max_results` must be set explicitly when using `id_list` batches.** If you request 10 IDs but omit `max_results`, the API defaults to 10, which happens to work — but set it explicitly to `len(ids)` to be safe.

- **Nonexistent IDs return zero entries, not an error.** `id_list=9999.99999` gives `totalResults=0` and an empty `atom:entry` list. Always check `len(entries) > 0` before accessing `entries[0]`.

- **`arxiv:comment` and `arxiv:journal_ref` / `arxiv:doi` may be absent.** Not all papers have these fields. Use `e.find('arxiv:comment', NS)` and check `if el is not None and el.text`.

- **Rate limit: 3 seconds between requests recommended for bulk crawling.** In practice, rapid bursts of 10 individual requests complete in ~6s (avg 0.63s/req) without being blocked. For sustained crawls over hundreds of papers, insert `time.sleep(3)` between requests. The API does not return rate limit headers — it just starts slowing responses or returns HTTP 503 silently.

- **`citation_author` tags are in `"Last, First"` format**, not `"First Last"` like the Atom API. The Atom `atom:author/atom:name` field gives `"First Last"` order. Pick the format that matches your downstream use.

- **The `arxiv:affiliation` sub-element of `atom:author` is rarely populated.** Most institutional affiliations are absent from the API response even when listed on the paper. The HTML abs page doesn't expose them in meta tags either.

- **`sortBy=relevance` applies only with `search_query`.** Using `sortBy=relevance` with `id_list` has no effect — results still come back in date order.

- **`max_results` cap is 2000 per call.** For bulk harvesting of a category, use `start` offset pagination and add 3s sleep between pages. `opensearch:totalResults` tells you the total so you can compute how many pages are needed.

- **HTML `citation_abstract` meta tag contains the full abstract.** Unlike the Atom `atom:summary` which can have trailing whitespace and embedded newlines, the meta tag version is a single clean string — no `.strip()` needed.
