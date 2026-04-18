# Open Library — Book Data Extraction

`https://openlibrary.org` — Internet Archive's free book catalog. All endpoints are public JSON APIs — no auth, no browser, no scraping required.

## Do this first

**Every task is a direct HTTP call — never open the browser.**

```python
import json
from helpers import http_get

# Search by title
results = json.loads(http_get("https://openlibrary.org/search.json?q=dune&limit=5"))
# results['numFound']  == 49090
# results['docs']      == list of work objects
# results['start']     == 0  (offset for pagination)
```

The search API is your entry point for everything. It returns work-level records (all editions grouped). To get edition details, follow the `key` to the Works or Books API.

---

## Common workflows

### Search by query, author, title, or ISBN

```python
import json
from helpers import http_get

# Free-text search
r = json.loads(http_get("https://openlibrary.org/search.json?q=dune+frank+herbert&limit=5"))

# Author search
r = json.loads(http_get(
    "https://openlibrary.org/search.json?author=tolkien&limit=5"
    "&fields=title,author_name,first_publish_year,isbn"
))
# fields=* returns all available fields; default returns ~15

# Title + author combined
r = json.loads(http_get(
    "https://openlibrary.org/search.json?title=dune&author=frank+herbert&limit=3"
    "&fields=title,author_name,edition_count,first_publish_year"
))
# r['docs'][0]['title']              == 'Dune'
# r['docs'][0]['author_name']        == ['Frank Herbert']
# r['docs'][0]['first_publish_year'] == 1965
# r['docs'][0]['edition_count']      == 120

# ISBN lookup (returns 0–2 results for the same work)
r = json.loads(http_get("https://openlibrary.org/search.json?isbn=9780743273565"))
# r['numFound']            == 2
# r['docs'][0]['title']    == 'The Great Gatsby'
# r['docs'][0]['key']      == '/works/OL468431W'
```

**Sort options** (`&sort=`): `new` (recently added), `old`, `random`, `editions` (most editions), `scans` (most scans). Default is relevance.

**Language filter**: `&language=fre` (ISO 639-2/B codes: `eng`, `fre`, `ger`, `spa`, `ita`, etc.)

**Pagination**: `&limit=N&offset=N`. Max limit not enforced but keep under 100 for reliability.

#### Search doc fields (default — ~15 keys always present)

| Field | Type | Notes |
|---|---|---|
| `key` | str | `/works/OL893415W` — use for Works API |
| `title` | str | Work title |
| `author_name` | list[str] | e.g. `['Frank Herbert']` |
| `author_key` | list[str] | e.g. `['OL79034A']` |
| `first_publish_year` | int | |
| `edition_count` | int | Number of editions across all languages |
| `cover_i` | int | Cover image ID — use with covers API |
| `cover_edition_key` | str | e.g. `OL7353617M` |
| `language` | list[str] | ISO codes of all editions |
| `ia` | list[str] | Internet Archive identifiers (when has_fulltext=true) |
| `ebook_access` | str | `'public'`, `'borrowable'`, `'no_ebook'` |
| `has_fulltext` | bool | |

#### Extra fields with `&fields=*`

```python
# With fields=* you also get:
# 'isbn'                   list[str]   All ISBNs across editions
# 'publisher'              list[str]   All publishers ever
# 'publish_date'           list[str]   All publish dates (strings, inconsistent formats)
# 'publish_year'           list[int]   Parsed years
# 'subject'                list[str]   Subject headings
# 'person'                 list[str]   Subject persons (e.g. 'Big Brother')
# 'place'                  list[str]   Subject places
# 'time'                   list[str]   Subject times
# 'number_of_pages_median' int         Median page count across editions
# 'ratings_average'        float       e.g. 4.29
# 'ratings_count'          int
# 'want_to_read_count'     int
# 'already_read_count'     int
# 'currently_reading_count'int
# 'readinglog_count'       int         Total of all reading log entries
# 'first_sentence'         list[str]
# 'id_goodreads'           list[str]
# 'id_librarything'        list[str]
# 'id_wikidata'            list[str]
# 'ddc'                    list[str]   Dewey Decimal Classification
# 'lcc'                    list[str]   Library of Congress Classification
# 'lccn'                   list[str]
```

---

### Bulk ISBN lookups (parallel)

```python
import json
from helpers import http_get
from concurrent.futures import ThreadPoolExecutor

isbns = ['9780743273565', '9780451524935', '9780618346257']

def lookup_isbn(isbn):
    url = f"https://openlibrary.org/search.json?isbn={isbn}&fields=title,author_name,first_publish_year,key"
    r = json.loads(http_get(url))
    if r['docs']:
        d = r['docs'][0]
        return {'isbn': isbn, 'title': d.get('title'), 'author': d.get('author_name', [None])[0],
                'year': d.get('first_publish_year'), 'key': d.get('key')}
    return {'isbn': isbn, 'found': False}

with ThreadPoolExecutor(max_workers=5) as ex:
    books = list(ex.map(lookup_isbn, isbns))

# [{'isbn': '9780743273565', 'title': 'The Great Gatsby', 'author': 'F. Scott Fitzgerald', 'year': 1920, ...},
#  {'isbn': '9780451524935', 'title': 'Nineteen Eighty-Four', 'author': 'George Orwell',      'year': 1949, ...},
#  {'isbn': '9780618346257', 'title': 'The Fellowship of the Ring', 'author': 'J.R.R. Tolkien', 'year': 1954, ...}]
```

---

### Works API (editions grouped by title)

Returns all metadata for a work (all editions combined). Get the work ID from `key` in search results.

```python
import json
from helpers import http_get

work_id = 'OL893415W'  # from search doc['key'] = '/works/OL893415W'
work = json.loads(http_get(f"https://openlibrary.org/works/{work_id}.json"))

# work['title']           == 'Dune'
# work['key']             == '/works/OL893415W'
# work['covers']          == [11481354, 12375564, 11157826]  ← cover IDs for covers API
# work['subjects']        == ['Dune (Imaginary place)', 'Fiction', ...]
# work['subject_places']  == [...]   ← geographic subjects (may be absent)
# work['subject_people']  == [...]   ← person subjects (may be absent)
# work['subject_times']   == [...]   ← time subjects (may be absent)
# work['authors']         == [{'author': {'key': '/authors/OL79034A'}, 'type': {...}}]
# work['description']     → either str OR {'type': '/type/text', 'value': str}  ← see gotchas
# work['created']         == {'type': '/type/datetime', 'value': '2009-10-15T11:34:21.437031'}
# work['last_modified']   same shape as created
```

Helper for the description field (which has two possible shapes):

```python
def get_description(work: dict) -> str:
    desc = work.get('description', '')
    if isinstance(desc, dict):
        return desc.get('value', '')
    return desc or ''
```

#### Works editions (paginated list of all editions)

```python
editions_resp = json.loads(http_get(
    f"https://openlibrary.org/works/{work_id}/editions.json?limit=10&offset=0"
))
# editions_resp['size']    == 120      (total edition count)
# editions_resp['entries'] == [...]    (up to limit items)
# editions_resp['links']   == {'self': '...', 'work': '...', 'next': '...', 'prev': '...'}
# ← use links['next'] for pagination when offset+limit < size

e = editions_resp['entries'][0]
# e['title']           == 'Duna'
# e['publishers']      == ['Editora Aleph']
# e['publish_date']    == '19/08/2017'   ← inconsistent format, string
# e['isbn_13']         == ['9788576573135']
# e['isbn_10']         == ['857657313X']
# e['covers']          == [10368109]
# e['number_of_pages'] == 680
# e['languages']       == [{'key': '/languages/por'}]
# e['key']             == '/books/OL28969075M'
# e['physical_format'] == 'Paperback'   (often missing)
# e['notes']           → str or {'value': str}  (often missing)
```

---

### Books API (specific edition)

Two sub-APIs: direct JSON for raw data, or `api/books` for enriched data.

#### Direct edition JSON

```python
import json
from helpers import http_get

edition_id = 'OL7353617M'  # from editions list e['key'] or cover_edition_key in search
edition = json.loads(http_get(f"https://openlibrary.org/books/{edition_id}.json"))

# edition['title']           == 'Fantastic Mr. Fox'
# edition['publishers']      == ['Puffin']
# edition['publish_date']    == 'October 1, 1988'
# edition['isbn_13']         == ['9780140328721']
# edition['isbn_10']         == ['0140328726']
# edition['number_of_pages'] == 96
# edition['covers']          == [...]   ← cover IDs
# edition['languages']       == [{'key': '/languages/eng'}]
# edition['works']           == [{'key': '/works/OL45804W'}]
# edition['authors']         == [{'key': '/authors/OL34184A'}]
# edition['identifiers']     == {'goodreads': [...], 'librarything': [...]}
# edition['first_sentence']  == {'value': '...'} or str  (often missing)
# edition['ocaid']           == 'fantast00dahl'  ← Internet Archive ID (if available)
```

#### Bibkeys API (enriched, multiple books at once)

```python
# jscmd=data: cleaned up dict with cover URLs pre-built
r = json.loads(http_get(
    "https://openlibrary.org/api/books"
    "?bibkeys=ISBN:9780743273565,ISBN:9780451524935"
    "&format=json&jscmd=data"
))
# r == {'ISBN:9780743273565': {...}, 'ISBN:9780451524935': {...}}

book = r['ISBN:9780743273565']
# book['title']           == 'The Great Gatsby'
# book['authors']         == [{'url': '...', 'name': 'F. Scott Fitzgerald'}]
# book['publish_date']    == '2021'
# book['publishers']      == [{'name': 'Independently Published'}]
# book['number_of_pages'] == 208
# book['url']             == 'http://openlibrary.org/books/OL46773254M/The_Great_Gatsby'
# book['key']             == '/books/OL46773254M'
# book['cover']           == {'small': '...S.jpg', 'medium': '...M.jpg', 'large': '...L.jpg'}
# book['identifiers']     == {'isbn_13': [...], 'openlibrary': [...]}
# book['subjects']        == [{'name': 'Modern fiction', 'url': '...'}, ...]
# book['subject_places']  == None  ← often null even with jscmd=data

# jscmd=details: raw edition JSON + extra fields
r2 = json.loads(http_get(
    "https://openlibrary.org/api/books"
    "?bibkeys=ISBN:9780743273565&format=json&jscmd=details"
))
item = r2['ISBN:9780743273565']
# item['bib_key']      == 'ISBN:9780743273565'
# item['info_url']     == 'http://openlibrary.org/books/OL...'
# item['preview']      == 'noview' | 'restricted' | 'full'
# item['preview_url']  == URL to read on OL or IA
# item['thumbnail_url']== 'https://covers.openlibrary.org/b/id/14314120-S.jpg'
# item['details']      → raw edition JSON (same as /books/OL...M.json)

# Supported bibkey prefixes: ISBN:, OCLC:, LCCN:, OLID: (e.g. OLID:OL46773254M)
```

---

### Authors API

```python
import json
from helpers import http_get

# Lookup by known author key
author = json.loads(http_get("https://openlibrary.org/authors/OL26320A.json"))
# OL26320A is J.R.R. Tolkien (note: not Frank Herbert as originally stated — verify with search)

# author['name']           == 'J.R.R. Tolkien'
# author['fuller_name']    == 'John Ronald Reuel Tolkien'
# author['personal_name']  == 'J. R. R. Tolkien'
# author['birth_date']     == '3 January 1892'   ← string, not parsed
# author['death_date']     == '2 September 1973'
# author['bio']            → str or {'type': '/type/text', 'value': str}
# author['photos']         == [6155606, 6433524, ...]   ← photo IDs for covers API
# author['links']          == [{'title': '...', 'url': '...', 'type': {...}}, ...]
# author['remote_ids']     == {'wikidata': 'Q892', 'viaf': '95218067', ...}
# author['alternate_names']== ['J. R. R. Tolkien', 'TOLKIEN', ...]
# author['key']            == '/authors/OL26320A'
# author['wikipedia']      → URL string or None

# Author works (paginated)
works = json.loads(http_get("https://openlibrary.org/authors/OL26320A/works.json?limit=5"))
# works['size']    == 415
# works['entries'] == [{title, key, covers, authors, created, ...}, ...]
# works['links']   == {'self': '...', 'next': '...'}
```

#### Author search

```python
r = json.loads(http_get("https://openlibrary.org/search/authors.json?q=tolkien"))
# r['numFound'] == 40
# r['docs'][0]:
#   'name'                   == 'Christopher Tolkien'
#   'key'                    == 'OL2623360A'     ← NOTE: no /authors/ prefix here
#   'birth_date'             == '21 November 1924'
#   'death_date'             == '16 January 2020'
#   'top_work'               == 'The War of the Ring'
#   'work_count'             == 43
#   'top_subjects'           == [...]
#   'alternate_names'        == [...]
#   'ratings_average'        float
#   'want_to_read_count'     int
#   'already_read_count'     int
#   'currently_reading_count'int
```

---

### Cover images

Covers are served directly as JPEG — redirect to Internet Archive CDN. No auth needed.

```
# Book covers — three key types:
https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg      # by cover ID (most reliable)
https://covers.openlibrary.org/b/isbn/{isbn}-{size}.jpg        # by ISBN
https://covers.openlibrary.org/b/olid/{edition_id}-{size}.jpg  # by edition OLID (unreliable — see gotchas)

# Author photos:
https://covers.openlibrary.org/a/id/{photo_id}-{size}.jpg

# Sizes: S (small), M (medium), L (large)
```

```python
import urllib.request

def get_cover_bytes(cover_id: int, size: str = 'M') -> bytes | None:
    """Fetch cover image bytes. Returns None if no cover (43-byte GIF placeholder)."""
    url = f"https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    return None if len(data) == 43 else data   # 43-byte GIF = no cover placeholder

# Or just get the URL for embedding:
def cover_url(cover_id: int, size: str = 'M') -> str:
    return f"https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg"

# Usage:
from helpers import http_get
import json
work = json.loads(http_get("https://openlibrary.org/works/OL893415W.json"))
if work.get('covers'):
    img = get_cover_bytes(work['covers'][0], 'L')   # first cover, large
    # img is ~20–80KB JPEG bytes, redirected from ia*.archive.org
```

To get cover by ISBN directly (e.g. for UI without a full book lookup):
```python
# Medium-size cover by ISBN:
url = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"
# Redirects to Internet Archive CDN, content-type: image/jpeg
# Use ?default=false to get 404 instead of 1×1 GIF placeholder for missing covers
url_safe = f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg?default=false"
```

---

### Subjects API

```python
import json
from helpers import http_get

# Subject slugs: lowercase, underscores for spaces
r = json.loads(http_get("https://openlibrary.org/subjects/science_fiction.json?limit=5"))
# r['name']          == 'science fiction'
# r['subject_type']  == 'subject'   ← also: 'person', 'place', 'time'
# r['work_count']    == 20973
# r['works']         == [{title, key, cover_id, authors, edition_count, ...}, ...]

w = r['works'][0]
# w['title']           == 'Alice\'s Adventures in Wonderland'
# w['key']             == '/works/OL138052W'
# w['cover_id']        == 10527843
# w['cover_edition_key']== 'OL...'
# w['authors']         == [{'key': '/authors/OL22098A', 'name': 'Lewis Carroll'}]
# w['edition_count']   == 3546
# w['first_publish_year']== ...
# w['has_fulltext']    == True | False
# w['ia']              == 'identifier'   (Internet Archive ID when available)

# Pagination: &offset=N
# Place subject:
r2 = json.loads(http_get("https://openlibrary.org/subjects/place:london.json?limit=5"))
# r2['subject_type'] == 'place', r2['work_count'] == 23927

# Person subject:
# https://openlibrary.org/subjects/person:napoleon.json?limit=5
# Time subject:
# https://openlibrary.org/subjects/time:middle_ages.json?limit=5

# Combine with ebooks=true to filter to only freely readable books:
r3 = json.loads(http_get("https://openlibrary.org/subjects/science_fiction.json?limit=5&ebooks=true"))
# r3['works'][i]['has_fulltext'] == True for all results
```

---

### Trending books

```python
import json
from helpers import http_get

for period in ['daily', 'weekly', 'monthly']:
    r = json.loads(http_get(f"https://openlibrary.org/trending/{period}.json?limit=10"))
    # r['works']  == list of search-doc-style objects
    # r['days']   == int (time window)
    # r['hours']  == int
    # Same fields as search docs (title, author_name, cover_i, key, ...)
    print(period, r['works'][0]['title'])  # e.g. 'Atomic Habits'
```

---

## Rate limits

No authentication required. No API key. No explicit rate limit published.

Observed in testing: 5 requests completed in ~1 second with no throttling, no 429s. The API is served from CDN/Solr — in practice you can make 10–20 parallel requests without issue. For bulk operations (hundreds of ISBNs), use `ThreadPoolExecutor(max_workers=5)` to be a good citizen.

**No `User-Agent` override needed** — the default `Mozilla/5.0` from `http_get` is accepted by all Open Library endpoints (unlike Nominatim which blocks it).

---

## Gotchas

**`description` field has two shapes.** Both are real — check at runtime:
```python
desc = work.get('description', '')
text = desc.get('value', '') if isinstance(desc, dict) else (desc or '')
```

**`/works/OL45804W` is Fantastic Mr. Fox, not Dune.** The OL IDs in the original prompt were placeholders. Always resolve real IDs via the search API rather than hardcoding them.

**Author search `key` has no prefix.** `/search/authors.json` returns `key: 'OL26320A'`, but the Authors API and all other APIs use `/authors/OL26320A`. Add the prefix manually when constructing follow-up URLs.

**Missing cover → 43-byte GIF placeholder, not 404.** Without `?default=false`, the covers API returns a 1×1 transparent GIF instead of HTTP 404 for unknown IDs. Check `len(data) == 43` to detect missing covers.

**`covers.openlibrary.org/b/olid/{work_id}` is unreliable.** OLID-based cover URLs for work IDs (OL...W) return the placeholder even when covers exist. Always use `b/id/{cover_id}` (from `work['covers'][0]`) or `b/isbn/{isbn}` instead.

**Bibkeys API picks one edition per ISBN.** When the same ISBN appears on multiple editions (reprint, reissue), `api/books?bibkeys=ISBN:...` returns one — and it may not be the most common edition.

**`publish_date` is a raw string.** Values like `'October 1, 1988'`, `'19/08/2017'`, `'2021'`, and `'1965-01-01'` all appear. Don't parse without normalization.

**`/works/.../editions.json` pagination uses `links.next`.** Unlike search (which uses `offset=`), check `links['next']` in the response to know if more pages exist:
```python
resp = json.loads(http_get("https://openlibrary.org/works/OL893415W/editions.json?limit=50"))
while 'next' in resp.get('links', {}):
    resp = json.loads(http_get("https://openlibrary.org" + resp['links']['next']))
    # process resp['entries']
```

**404 for non-existent IDs.** `/works/OL99999999W.json`, `/books/OL99999999M.json`, and `/authors/OL99999999A.json` all raise `HTTPError: HTTP Error 404: Not Found`. Wrap in try/except.

**Search `docs` default fields are minimal.** The default response includes ~15 fields. Add `&fields=*` to get all 100+ Solr fields (ratings, ISBNs, publishers, subjects, Goodreads IDs, etc.). Alternatively specify exactly what you need: `&fields=title,isbn,ratings_average`.
