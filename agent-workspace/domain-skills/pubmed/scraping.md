# PubMed / NCBI — Scraping & Data Extraction

`https://pubmed.ncbi.nlm.nih.gov` — 37 M+ biomedical citations. **Never use the browser for PubMed.** All data is reachable via `http_get` using the NCBI E-utilities REST API. No API key required; a free key raises the rate limit from 3 to 10 req/s.

## Do this first

**ESearch → ESummary is the fastest pipeline for most tasks — two calls, JSON responses, no XML parsing.**

```python
import json
from helpers import http_get

# Step 1: search → get PMIDs
search = json.loads(http_get(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&term=deep+learning+radiology&retmax=10&retmode=json"
))
pmids = search['esearchresult']['idlist']   # e.g. ['41999029', '41998456', ...]
count = search['esearchresult']['count']    # total hits across all pages

# Step 2: fetch lightweight metadata for all PMIDs in one call
summary = json.loads(http_get(
    f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    f"?db=pubmed&id={','.join(pmids)}&retmode=json"
))
result = summary['result']
for uid in result['uids']:
    art = result[uid]
    print(uid, art['pubdate'], art['source'])
    print("  ", art['title'][:80])
    print("  authors:", [a['name'] for a in art['authors'][:3]])
# Confirmed output (2026-04-18):
# 41999029 2026 Apr 18 Med Sci Monit
#    Use of Deep Learning Models in the Diagnosis of Proptosis Through Orbi
#    authors: ['Kesimal U', 'Akkaya HE', 'Polat Ö']
# 41998456 2026 Apr 17 Sci Rep
#    ...
```

Use **EFetch XML** when you need: full abstract text, MeSH terms, complete author names (not just "Last I"), structured abstract labels, or the DOI from within the article record.

## Common workflows

### Search PubMed (ESearch)

```python
import json
from helpers import http_get

data = json.loads(http_get(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed"
    "&term=large+language+models+clinical"
    "&retmax=5"
    "&retmode=json"
    "&sort=pub+date"                          # newest first; default is relevance
    "&datetype=pdat"                          # filter by publication date
    "&mindate=2024/01/01&maxdate=2024/12/31"  # YYYY/MM/DD format
))
result = data['esearchresult']
print("Total hits:", result['count'])         # '24160' — note: string, not int
print("PMIDs:", result['idlist'])
print("Query translation:", result['querytranslation'])
# Confirmed output (2026-04-18):
# Total hits: 24160
# PMIDs: ['41996895', '41996722', '41996006', '41995888', '41995759']
# Query translation: "large language models"[MeSH Terms] OR ...
```

#### ESearch field tags (append to term)

```
machine learning[MeSH Terms]        MeSH controlled vocabulary
Hinton GE[Author]                   author last + initials
attention is all you need[Title]    title words
Nature[Journal]                     journal name
2024[pdat]                          publication year
```

Boolean operators: `AND`, `OR`, `NOT`. Phrase search: `"exact phrase"[Title]`.

#### Sort options (`sort=`)

| Value | Effect |
|---|---|
| *(omit)* | Relevance (default) |
| `pub+date` | Most recent publication first |
| `Author` | First author alphabetical |
| `JournalName` | Journal alphabetical |

### Lightweight metadata — ESummary (JSON, no XML)

```python
import json
from helpers import http_get

data = json.loads(http_get(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
    "?db=pubmed&id=41999029,41998456,41997837&retmode=json"
))
result = data['result']
for uid in result['uids']:
    art = result[uid]
    # Key fields available:
    title         = art['title']            # full title string
    source        = art['source']           # abbreviated journal name
    fulljournalname = art['fulljournalname']
    pubdate       = art['pubdate']          # e.g. '2026 Apr 18'
    epubdate      = art['epubdate']         # e-pub ahead of print date (may be empty)
    authors       = art['authors']          # list of {'name': 'Last I', 'authtype': ...}
    volume        = art['volume']
    issue         = art['issue']
    pages         = art['pages']
    pubtype       = art['pubtype']          # list: ['Journal Article', 'Review', ...]
    # Extract DOI from elocationid or articleids:
    doi_field     = art['elocationid']      # e.g. 'doi: 10.12659/MSM.951157'
    article_ids   = {x['idtype']: x['value'] for x in art['articleids']}
    doi           = article_ids.get('doi')
    pmc_id        = article_ids.get('pmc')  # PMC ID if open access
    print(uid, pubdate, source)
    print(" ", title[:70])
    print("  doi:", doi, "| pmc:", pmc_id)
# Confirmed output (2026-04-18):
# 41999029 2026 Apr 18 Med Sci Monit
#    Use of Deep Learning Models in the Diagnosis of Proptosis Through Orbi
#   doi: 10.12659/MSM.951157 | pmc: None
```

### Full article metadata — EFetch XML

Use this for full abstracts, complete author names, MeSH terms, structured abstract sections.

```python
import json, xml.etree.ElementTree as ET
from helpers import http_get

raw = http_get(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    "?db=pubmed&id=41999029,36328784&retmode=xml&rettype=abstract"
)
root = ET.fromstring(raw)

for art in root.findall('.//PubmedArticle'):
    mc      = art.find('MedlineCitation')
    pmid    = mc.find('PMID').text
    article = mc.find('Article')

    # Title — use itertext() to handle embedded tags like <i>, <sub>
    title   = ''.join(article.find('ArticleTitle').itertext()).strip()

    # Abstract — plain or structured (BACKGROUND / METHODS / RESULTS / CONCLUSION)
    abstract_el = article.find('Abstract')
    if abstract_el is not None:
        sections = []
        for t in abstract_el.findall('AbstractText'):
            label = t.get('Label', '')          # e.g. 'BACKGROUND', 'METHODS'
            text  = ''.join(t.itertext()).strip()
            sections.append(f"[{label}] {text}" if label else text)
        abstract = ' '.join(sections)
    else:
        abstract = ''                           # ~15% of articles have no abstract

    # Journal + year
    journal  = article.find('Journal')
    j_title  = journal.find('Title').text if journal is not None else ''
    pub_date = journal.find('.//PubDate') if journal is not None else None
    if pub_date is not None:
        year_el    = pub_date.find('Year')
        medline_el = pub_date.find('MedlineDate')   # fallback for old/seasonal dates
        season_el  = pub_date.find('Season')        # e.g. 'Jul-Aug', 'Oct-Dec'
        year = (year_el.text if year_el is not None
                else medline_el.text[:4] if medline_el is not None else '')

    # DOI
    doi_el = next(
        (e for e in article.findall('ELocationID') if e.get('EIdType') == 'doi'),
        None
    )
    doi = doi_el.text if doi_el is not None else ''

    # Authors — handle CollectiveName (consortium/group authors)
    author_list = article.find('AuthorList')
    authors = []
    if author_list is not None:
        for a in author_list.findall('Author'):
            collective = a.find('CollectiveName')
            last       = a.find('LastName')
            fore       = a.find('ForeName')
            initials   = a.find('Initials')
            if collective is not None:
                authors.append(collective.text)
            elif last is not None:
                full = last.text
                if fore is not None:
                    full += f", {fore.text}"
                authors.append(full)

    # MeSH controlled vocabulary terms
    mesh_list = mc.find('MeshHeadingList')
    mesh_terms = []
    if mesh_list is not None:
        mesh_terms = [
            mh.find('DescriptorName').text
            for mh in mesh_list.findall('MeshHeading')
            if mh.find('DescriptorName') is not None
        ]

    print(f"PMID={pmid} ({year}) {j_title}")
    print(f"  Title: {title[:70]}")
    print(f"  Authors: {authors[:3]}")
    print(f"  DOI: {doi}")
    print(f"  MeSH: {mesh_terms[:4]}")
    print(f"  Abstract: {abstract[:120]}")
# Confirmed output (2026-04-18):
# PMID=41999029 (2026) Medical science monitor : international medical...
#   Title: Use of Deep Learning Models in the Diagnosis of Proptosis Thro
#   Authors: ['Kesimal, Uğur', 'Akkaya, Habip Eser', 'Polat, Önder']
#   DOI: 10.12659/MSM.951157
#   MeSH: ['Humans', 'Deep Learning', 'Exophthalmos', 'Magnetic Resonance Imaging']
#   Abstract: BACKGROUND Proptosis is a common manifestation of orbital disease...
# PMID=36328784 (...)
#   Abstract: [OBJECTIVES] Physical inactivity and sedentary behaviour...  ← structured
```

### Large result sets — usehistory + WebEnv

When `count` exceeds `retmax` (max 10 000), use server-side history to paginate EFetch without re-running ESearch on every page.

```python
import json, xml.etree.ElementTree as ET
from helpers import http_get

# Step 1: ESearch with usehistory=y — NCBI holds result set on server
search = json.loads(http_get(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    "?db=pubmed&term=CRISPR+gene+editing&retmax=0&retmode=json&usehistory=y"
))
webenv    = search['esearchresult']['webenv']       # server-side session token
query_key = search['esearchresult']['querykey']     # result set ID within session
total     = int(search['esearchresult']['count'])
print(f"Total: {total}, WebEnv: {webenv[:30]}..., query_key: {query_key}")
# Confirmed output (2026-04-18):
# Total: 24160, WebEnv: MCID_69e4203757db89391008d6f1..., query_key: 1

# Step 2: EFetch pages using WebEnv (no re-searching)
batch_size = 200
for start in range(0, min(total, 1000), batch_size):  # cap at 1000 for demo
    raw = http_get(
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pubmed&query_key={query_key}&WebEnv={webenv}"
        f"&retstart={start}&retmax={batch_size}&retmode=xml&rettype=abstract"
    )
    root = ET.fromstring(raw)
    articles = root.findall('.//PubmedArticle')
    print(f"  Fetched {len(articles)} articles (start={start})")
    # process articles here...
```

### EInfo — list available NCBI databases

```python
import json
from helpers import http_get

data = json.loads(http_get(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?retmode=json"
))
dbs = data['einforesult']['dblist']
print(f"Total databases: {len(dbs)}")   # Confirmed: 39 (2026-04-18)
print(dbs[:10])
# ['pubmed', 'protein', 'nuccore', 'ipg', 'nucleotide', 'structure',
#  'genome', 'annotinfo', 'assembly', 'bioproject']
```

Get PubMed-specific metadata (field list, link list):

```python
import json
from helpers import http_get

data = json.loads(http_get(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi?db=pubmed&retmode=json"
))
db_info = data['einforesult']['dbinfo'][0]
print("DB name:", db_info['dbname'])
print("Record count:", db_info['count'])    # total PubMed records
link_names = [l['name'] for l in db_info.get('linklist', [])]
print(f"Link types ({len(link_names)}):", link_names[:5])
# Confirmed (2026-04-18):
# DB name: pubmed
# Record count: 37620453
# Link types (48): ['pubmed_assembly', 'pubmed_bioproject', ...]
```

### ELink — cross-database linking

ELink connects a PubMed record to associated data in other NCBI databases. The `pubmed_pubmed` "related articles" linkname relies on a similarity server that is intermittently unavailable (returns `"Couldn't resolve #exLinkSrv2, the address table is empty."`). Use the non-similarity links below instead.

```python
import json
from helpers import http_get

# Link a PMID to its free full-text in PMC (if open access)
# linkname=pubmed_pmc — may also hit the server outage; check error field
data = json.loads(http_get(
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
    "?dbfrom=pubmed&id=38325330&linkname=pubmed_pmc&retmode=json"
))
error = data.get('ERROR', '')
if error:
    print("ELink error:", error)   # 'Couldn't resolve #exLinkSrv2...' — NCBI server issue
else:
    for ls in data.get('linksets', []):
        for lsdb in ls.get('linksetdbs', []):
            print(lsdb['linkname'], "→", lsdb['links'][:5])
```

Available ELink linknames from pubmed (48 total):

| linkname | Target |
|---|---|
| `pubmed_pmc` | Free full text in PMC |
| `pubmed_pubmed_citedin` | Articles citing this paper |
| `pubmed_pubmed_refs` | References cited by this paper |
| `pubmed_gene` | Related Gene records |
| `pubmed_clinvar` | Clinical variants associated with publication |
| `pubmed_gds` | Related GEO datasets |

**Practical alternative**: If ELink is down, extract DOI from EFetch/ESummary and use `https://doi.org/{doi}` directly for the full-text link.

## URL and parameter reference

### E-utilities base URLs

```
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi   # search → PMIDs
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi  # PMIDs → JSON summary
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi    # PMIDs → full XML
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi     # cross-db links
https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi     # DB metadata
```

### ESearch parameters

| Parameter | Values | Notes |
|---|---|---|
| `db` | `pubmed` | Always `pubmed` for PubMed |
| `term` | query string | Supports field tags like `[Author]`, `[Title]`, `[MeSH Terms]` |
| `retmax` | integer, max 10000 | Results returned per call |
| `retmode` | `json` | JSON output |
| `sort` | `pub+date`, `Author`, `JournalName` | Default is relevance |
| `datetype` | `pdat` (pub), `edat` (entrez), `mdat` (modified) | |
| `mindate`, `maxdate` | `YYYY/MM/DD` or `YYYY` | Requires `datetype` |
| `usehistory` | `y` | Store results on server; returns `webenv` + `querykey` |

### EFetch parameters

| Parameter | Values | Notes |
|---|---|---|
| `db` | `pubmed` | |
| `id` | `38000000,37999999` | Comma-separated PMIDs; max ~200 per call |
| `query_key` + `WebEnv` | from ESearch `usehistory=y` | Alternative to `id` for large sets |
| `retstart` | integer | Offset for pagination with WebEnv |
| `retmax` | integer, max 10000 | Batch size |
| `retmode` | `xml` | Use XML for EFetch (JSON not available for full records) |
| `rettype` | `abstract` | Returns abstract + core metadata |

### PubMed article URL construction

```python
pmid = "41999029"
pubmed_url  = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
doi         = "10.12659/MSM.951157"
doi_url     = f"https://doi.org/{doi}"        # resolves to publisher page
pmc_id      = "PMC9876543"                    # from ESummary articleids
pmc_url     = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/"
```

## Gotchas

- **`count` is a string, not int.** `search['esearchresult']['count']` returns `'24160'`, not `24160`. Always cast with `int()` before arithmetic.

- **EFetch retmode must be `xml` for full records.** Unlike ESearch and ESummary, EFetch with `retmode=json` returns flat text (the MEDLINE citation text format), not structured JSON. Parse EFetch responses with `xml.etree.ElementTree`.

- **`ArticleTitle` may contain embedded XML tags.** Titles with italics (`<i>Staphylococcus aureus</i>`) or math (`<sub>2</sub>`) are mixed-content nodes. Always use `''.join(el.itertext())` instead of `el.text`, which silently drops everything after the first child tag.

- **~15% of articles have no abstract.** `article.find('Abstract')` returns `None` for short communications, editorials, letters, and older records. Always guard with `if abstract_el is not None`.

- **Author names vary in structure — always handle `CollectiveName`.** Consortium papers list a group name (`'GeKeR Study Group'`, `'Breast Cancer Association Consortium'`) under `<CollectiveName>` instead of `<LastName>/<ForeName>`. Individual authors have `<LastName>` + optionally `<ForeName>` and `<Initials>`. Check `CollectiveName` first; falling through to `LastName` without the check produces `None` errors.
  - Confirmed real examples (2026-04-18): PMID 37586835 (`GeKeR Study Group`), PMID 36328784 (`Breast Cancer Association Consortium`)

- **PubDate has three possible structures.** Most articles have `<Year>` + optional `<Month>` + optional `<Day>`. Seasonal journals use `<Season>` (e.g. `Jul-Aug`, `Oct-Dec`) instead of `<Month>`. A minority of older records use `<MedlineDate>` (e.g. `1995 Fall`) with no `<Year>`. Safe extraction pattern:
  ```python
  pub_date = journal.find('.//PubDate')
  year_el    = pub_date.find('Year')    if pub_date is not None else None
  medline_el = pub_date.find('MedlineDate') if pub_date is not None else None
  year = (year_el.text if year_el is not None
          else medline_el.text[:4] if medline_el is not None else '')
  ```

- **Batch EFetch: keep IDs to ~200 per call.** The API accepts comma-separated IDs in `id=`, but very large batches (500+) occasionally time out or return truncated XML. For >200 articles, iterate in chunks or use `usehistory` + `WebEnv`.

- **ELink `pubmed_pubmed` (related articles) is intermittently broken.** The NCBI similarity server returns `"Couldn't resolve #exLinkSrv2, the address table is empty."` — this is a persistent server-side issue as of 2026-04-18, not a rate-limit error. Other linknames (`pubmed_gene`, `pubmed_pmc`, `pubmed_clinvar`) fail with the same error. Use the DOI as a fallback link to publisher full text.

- **Rate limits: 3 req/s without API key, 10 req/s with free key.** Exceeding 3 req/s returns HTTP 429. Insert `time.sleep(0.34)` between sequential calls without a key. Get a free API key at https://www.ncbi.nlm.nih.gov/account/ and append `&api_key=YOUR_KEY` to all URLs.

- **`retmax` upper bound is 10 000 for ESearch.** To retrieve more than 10 000 PMIDs for a search, use `usehistory=y` and page through EFetch with `retstart` offsets. EFetch itself also accepts `retmax` up to 10 000 per call.

- **`retmax=0` in ESearch returns only the count, not IDs — useful for counting.** Combine with `usehistory=y` to store the result for later paging without fetching IDs upfront:
  ```python
  search = json.loads(http_get(
      "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
      "?db=pubmed&term=cancer&retmax=0&retmode=json&usehistory=y"
  ))
  total  = int(search['esearchresult']['count'])   # e.g. 4800000
  webenv = search['esearchresult']['webenv']
  ```

- **ESummary `authors` field uses abbreviated names (`Last I`), not full names.** Use EFetch XML to get `ForeName` (e.g. `'Kesimal, Uğur'` vs ESummary `'Kesimal U'`). For bulk tasks where full names are not needed, ESummary is faster.

- **`querytranslation` shows how NCBI interpreted your term.** The ESearch response includes `esearchresult.querytranslation` — a MeSH-expanded version of your query. Inspect it to verify the search matched what you intended.
