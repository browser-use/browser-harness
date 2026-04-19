# arXiv Bulk Harvest + Semantic Scholar — OAI-PMH & Citation Enrichment

Companion to `domain-skills/arxiv/scraping.md`. Use the **arxiv** skill for search-and-fetch workflows. Use **this skill** when you need:

- Bulk-harvesting all papers in a subject area or date window (OAI-PMH)
- Citation counts, influential-citation scores, and cross-database IDs (Semantic Scholar)
- Per-paper version history and submitter info (`arXivRaw` metadata)

No API key required for either endpoint. Both return JSON or XML over plain HTTP.

---

## OAI-PMH bulk harvest

### Endpoint (confirmed 2026-04-19)

```
https://oaipmh.arxiv.org/oai
```

`https://export.arxiv.org/oai2` is the old URL — it 301-redirects to the new one. Use the new URL directly to avoid the extra round-trip.

### Harvest all cs papers from a date window

```python
import xml.etree.ElementTree as ET
from helpers import http_get

OAI_NS = {
    'oai': 'http://www.openarchives.org/OAI/2.0/',
    'arXiv': 'http://arxiv.org/OAI/arXiv/',
}

def fetch_oai_page(url):
    """Fetch one OAI-PMH page; return (records_xml_list, next_token_or_None)."""
    xml = http_get(url)
    root = ET.fromstring(xml)
    records = root.findall('.//oai:record', OAI_NS)
    token_el = root.find('.//oai:resumptionToken', OAI_NS)
    token = token_el.text if token_el is not None and token_el.text else None
    return records, token

def parse_arxiv_record(rec):
    """Extract fields from one <record> element (metadataPrefix=arXiv)."""
    header = rec.find('oai:header', OAI_NS)
    meta   = rec.find('.//arXiv:arXiv', OAI_NS)
    if meta is None:
        return None   # deleted record (header has status="deleted")
    authors_el = meta.findall('arXiv:authors/arXiv:author', OAI_NS)
    authors = []
    for a in authors_el:
        fn = (a.findtext('arXiv:forenames', namespaces=OAI_NS) or '').strip()
        ln = (a.findtext('arXiv:keyname',   namespaces=OAI_NS) or '').strip()
        authors.append(f"{fn} {ln}".strip())
    return {
        'id':           meta.findtext('arXiv:id', namespaces=OAI_NS),
        'datestamp':    header.findtext('oai:datestamp', namespaces=OAI_NS),
        'created':      meta.findtext('arXiv:created',  namespaces=OAI_NS),
        'updated':      meta.findtext('arXiv:updated',  namespaces=OAI_NS),
        'title':        (meta.findtext('arXiv:title',    namespaces=OAI_NS) or '').strip(),
        'authors':      authors,
        'categories':   (meta.findtext('arXiv:categories', namespaces=OAI_NS) or '').split(),
        'abstract':     (meta.findtext('arXiv:abstract',   namespaces=OAI_NS) or '').strip(),
        'doi':          meta.findtext('arXiv:doi',         namespaces=OAI_NS),
        'journal_ref':  meta.findtext('arXiv:journal-ref', namespaces=OAI_NS),
        'license':      meta.findtext('arXiv:license',     namespaces=OAI_NS),
    }

# --- Main harvest loop ---
import time

BASE = 'https://oaipmh.arxiv.org/oai'
first_url = (
    f"{BASE}?verb=ListRecords"
    f"&metadataPrefix=arXiv"
    f"&set=cs"
    f"&from=2024-01-01"
    f"&until=2024-01-02"
)

papers = []
url = first_url
while url:
    records, token = fetch_oai_page(url)
    for rec in records:
        p = parse_arxiv_record(rec)
        if p:
            papers.append(p)
    print(f"  fetched {len(records)} records, total so far: {len(papers)}")
    if token:
        url = f"{BASE}?verb=ListRecords&resumptionToken={token}"
        time.sleep(5)   # OAI-PMH policy: >=5s between pages
    else:
        url = None

print(f"Done. {len(papers)} papers harvested.")
# Confirmed output for cs, 2024-01-01 to 2024-01-02:
# fetched 44 records, total so far: 44
# Done. 44 papers harvested.
# For 2024-01-01 to 2024-01-07 (cs): multiple pages, resumptionToken issued when >~200 records
```

### Available verbs

| Verb | Purpose | Key params |
|---|---|---|
| `Identify` | Repository info, earliest datestamp (`2005-09-16`) | — |
| `ListSets` | All harvestable sets (see table below) | — |
| `ListMetadataFormats` | `oai_dc`, `arXiv`, `arXivOld`, `arXivRaw` | — |
| `ListRecords` | Bulk harvest with date/set filter | `metadataPrefix`, `set`, `from`, `until` |
| `GetRecord` | Single record by OAI identifier | `identifier`, `metadataPrefix` |

### Top-level sets (confirmed)

| setSpec | Name |
|---|---|
| `cs` | Computer Science (all) |
| `cs:cs` | Computer Science (subset notation — same scope) |
| `math` | Mathematics |
| `physics` | Physics |
| `stat` | Statistics |
| `eess` | Electrical Engineering and Systems Science |
| `econ` | Economics |
| `q-bio` | Quantitative Biology |
| `q-fin` | Quantitative Finance |

Subset sets use `topic:topic:SUBCATEGORY` notation, e.g. `cs:cs:LG` for Machine Learning. List all with `verb=ListSets`.

### Available metadata formats

- `arXiv` — rich: id, created/updated dates, authors (keyname + forenames separately), categories, abstract, doi, journal-ref, license. **Use this.**
- `arXivRaw` — adds `<submitter>`, per-version history (`<version version="v1">` with date and file size), author list as flat string. Use when you need version history.
- `oai_dc` — Dublin Core, minimal. Skip unless you need cross-system compatibility.
- `arXivOld` — legacy format pre-2007. Skip.

### GetRecord + arXivRaw (version history)

```python
import xml.etree.ElementTree as ET
from helpers import http_get

RAW_NS = {
    'oai': 'http://www.openarchives.org/OAI/2.0/',
    'raw': 'http://arxiv.org/OAI/arXivRaw/',
}

xml = http_get(
    "https://oaipmh.arxiv.org/oai"
    "?verb=GetRecord"
    "&metadataPrefix=arXivRaw"
    "&identifier=oai:arXiv.org:1706.03762"
)
root = ET.fromstring(xml)
meta = root.find('.//raw:arXivRaw', RAW_NS)

title     = meta.findtext('raw:title',     namespaces=RAW_NS)
submitter = meta.findtext('raw:submitter', namespaces=RAW_NS)
versions  = meta.findall('raw:version',    RAW_NS)
for v in versions:
    print(v.get('version'), v.findtext('raw:date', namespaces=RAW_NS))
# Confirmed output for 1706.03762 ("Attention Is All You Need"):
# v1 Mon, 12 Jun 2017 17:57:34 GMT
# v2 Mon, 19 Jun 2017 16:49:45 GMT
# ...
# v7 Wed, 02 Aug 2023 00:41:18 GMT
# submitter: Llion Jones
```

---

## Semantic Scholar — citation enrichment for arXiv papers

No API key required (unauthenticated: 1 req/s, 5000 req/day). With a free key the limit rises to 100 req/s.

Base URL: `https://api.semanticscholar.org/graph/v1/`

### Single paper lookup by arXiv ID

```python
import json
from helpers import http_get

paper = json.loads(http_get(
    "https://api.semanticscholar.org/graph/v1/paper/arXiv:1706.03762"
    "?fields=title,year,venue,publicationDate,citationCount,"
    "influentialCitationCount,authors,abstract,externalIds"
))
print(paper['title'])                    # "Attention is All you Need"
print(paper['citationCount'])            # 173155  (confirmed 2026-04-19)
print(paper['influentialCitationCount']) # 19629
print(paper['venue'])                    # "Neural Information Processing Systems"
print(paper['externalIds']['ArXiv'])     # "1706.03762"
print(paper['externalIds']['DOI'])       # missing if no DOI
for a in paper['authors']:
    print(a['name'], a['authorId'])
```

The ID format `arXiv:NNNN.NNNNN` is accepted directly — no conversion needed.

### Batch lookup (up to 500 IDs per POST)

```python
import json
from helpers import http_get
import urllib.request

ids = ["arXiv:1706.03762", "arXiv:1810.04805", "arXiv:2005.14165"]
fields = "paperId,externalIds,title,year,citationCount,influentialCitationCount"

body = json.dumps({"ids": ids}).encode()
req = urllib.request.Request(
    f"https://api.semanticscholar.org/graph/v1/paper/batch?fields={fields}",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as r:
    results = json.loads(r.read())

for p in results:
    print(p['externalIds'].get('ArXiv'), p['citationCount'], p['title'][:50])
# Confirmed output (2026-04-19):
# 1706.03762  173155  Attention is All you Need
# 1810.04805  113138  BERT: Pre-training of Deep Bidirectional Tran...
# 2005.14165  (varies)  Language Models are Few-Shot Learners
```

Note: `helpers.http_get` only does GET. For POST use `urllib.request.Request` directly as above.

### Paper search

```python
import json
from helpers import http_get

results = json.loads(http_get(
    "https://api.semanticscholar.org/graph/v1/paper/search"
    "?query=large+language+model"
    "&fields=paperId,externalIds,title,year,citationCount"
    "&limit=5"
))
total = results['total']   # e.g. 3473582 for "large language model"
for p in results['data']:
    arxiv_id = p['externalIds'].get('ArXiv', 'no-arxiv')
    print(arxiv_id, p['year'], p['citationCount'], p['title'][:50])
# next page: use offset=5, offset=10, etc.
```

### Available fields (pass as comma-separated `fields=` query param)

| Field | Type | Notes |
|---|---|---|
| `paperId` | str | Semantic Scholar internal ID |
| `externalIds` | dict | Keys: `ArXiv`, `DOI`, `DBLP`, `MAG`, `ACL`, `CorpusId` |
| `title` | str | |
| `abstract` | str | |
| `year` | int | Publication year |
| `publicationDate` | str | `YYYY-MM-DD` |
| `venue` | str | Conference/journal name |
| `citationCount` | int | Total citations |
| `influentialCitationCount` | int | Citations deemed highly influential |
| `authors` | list | Each: `{authorId, name}` |
| `references` | list | List of paper objects (needs own `fields`) |
| `citations` | list | Citing papers (needs own `fields`) |
| `openAccessPdf` | dict | `{url, status, license}` |

---

## Downloading PDFs

Direct PDF download — no auth, no redirect for versionless URLs (returns 200 + PDF body directly).

```python
import urllib.request

def download_pdf(arxiv_id, dest_path, version=None):
    """
    arxiv_id: bare ID like '1706.03762' or versioned '1706.03762v7'
    version:  if given, appended as 'v{version}' — ignored if arxiv_id already has version
    dest_path: where to save, e.g. '/tmp/paper.pdf'
    """
    if 'v' not in arxiv_id.split('.')[-1] and version:
        arxiv_id = f"{arxiv_id}v{version}"
    url = f"https://arxiv.org/pdf/{arxiv_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        with open(dest_path, 'wb') as f:
            f.write(r.read())
    print(f"Saved {r.headers.get('content-length', '?')} bytes to {dest_path}")

download_pdf('1706.03762', '/tmp/attention.pdf')
# Confirmed: saves 2215244 bytes, filename hint in header: '1706.03762v7.pdf'
# Versionless URL resolves to latest version server-side (no redirect, 200 direct)
```

---

## Gotchas

- **OAI-PMH endpoint moved.** `https://export.arxiv.org/oai2` 301-redirects to `https://oaipmh.arxiv.org/oai`. Use the new URL. `helpers.http_get` (which uses `urllib`) does NOT follow redirects — you'll get an empty string or error. Either use `urllib.request.urlopen` with `follow_redirects` logic, or just use the canonical URL directly.

- **OAI-PMH rate limit: 5 seconds between pages.** The protocol requires a `Retry-After` interval. The server embeds an `expirationDate` on the resumptionToken. Violating the rate limit causes the token to be invalidated and the harvest fails silently. Always `time.sleep(5)` between pages.

- **Resumption token is opaque but URL-encoded.** The token looks like `verb%3DListRecords%26...%26skip%3D247`. Pass it verbatim as `&resumptionToken=<token>` — do not URL-encode it again.

- **`datestamp` in OAI-PMH is last-modified date, not submission date.** A paper submitted in 2008 can appear in a 2024 harvest window if it was revised then. The `<created>` and `<updated>` fields inside `<arXiv>` metadata are the actual submission/revision dates.

- **Deleted records have no `<metadata>` element.** The `<header>` will carry `status="deleted"`. Always check `meta is None` after `find('.//arXiv:arXiv', ...)`.

- **Author structure differs between OAI-PMH formats.** In `arXiv` metadata, authors are structured: `<author><keyname>Vaswani</keyname><forenames>Ashish</forenames></author>`. In `arXivRaw`, they're a flat comma-separated string: `Ashish Vaswani, Noam Shazeer, ...`. In the Atom API, it's `<name>Ashish Vaswani</name>` (first-last order). Pick the source that matches your downstream use.

- **Semantic Scholar 429 under unauthenticated bursts.** The unauthenticated limit is ~1 req/s. Rapid parallel calls return `{"code": "429"}`. Add `time.sleep(1)` between single lookups or use the batch POST endpoint (up to 500 IDs, single request) to stay under the limit. The batch endpoint itself counts as 1 request.

- **Semantic Scholar `externalIds` may lack `ArXiv` key.** Not all papers have an arXiv preprint. When enriching an arXiv list with S2 data, always use `.get('ArXiv')` not `['ArXiv']`.

- **Atom API rate limit: 1 request per 3 seconds for sustained crawls.** The API returns HTTP 429 `"Rate exceeded."` on rapid-fire requests. The OAI-PMH endpoint is designed for bulk and is more tolerant, but still requires the 5s sleep between resumption pages.

- **OAI-PMH `set` param uses colon-separated hierarchy, not dot.** The Atom API uses `cat:cs.LG`; OAI-PMH uses `set=cs:cs:LG`. Using `set=cs.LG` returns zero results.

- **`http_get` in helpers.py does NOT follow HTTP redirects.** If you must use it with the old OAI URL, you'll get an empty body. Either update the URL to the canonical one or use `urllib.request.urlopen` with a redirect handler.

---

## How this complements the existing arxiv skill

| Task | Use |
|---|---|
| Search by keyword, author, or category | `arxiv` skill — Atom API |
| Fetch 1–2000 specific papers by ID | `arxiv` skill — `id_list` batch |
| Harvest all papers in a subject over a date range | **this skill** — OAI-PMH |
| Get citation counts / influential citations | **this skill** — Semantic Scholar |
| Get per-version history and submitter name | **this skill** — OAI-PMH `arXivRaw` |
| Download a PDF | either skill (same URL structure) |
