# Goodreads — Book Data Extraction

Field-tested against goodreads.com on 2026-04-18 via `http_get` (no browser required).
All five URL types return full HTML with no bot-wall, CAPTCHA, or login gate.

## Access Summary

| Page type          | `http_get` works? | Data format              |
|--------------------|-------------------|--------------------------|
| Book show page     | Yes               | `__NEXT_DATA__` + JSON-LD |
| Search results     | Yes               | Server-rendered HTML (schema.org microdata) |
| Author show page   | Yes               | Server-rendered HTML + OG meta |
| Listopia list page | Yes               | Server-rendered HTML (schema.org microdata) |

Goodreads shut down its public API in 2020. All extraction is HTML-based.
Open Library is a reliable supplement with a free JSON API (see [Open Library fallback](#open-library-api-fallback)).

---

## Book Page — Full Data (`__NEXT_DATA__`)

URL pattern: `https://www.goodreads.com/book/show/{book_id}` or `/{book_id}.{Slug}`

The slug is optional — numeric ID alone works and redirects cleanly.

```python
import re, json
from helpers import http_get

def parse_book(book_id):
    html = http_get(f"https://www.goodreads.com/book/show/{book_id}")

    # Parse Apollo state from Next.js page
    nd = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL)
    ap = json.loads(nd.group(1))['props']['pageProps']['apolloState']

    # The primary Book entity matches the URL's legacy ID
    book = next(v for v in ap.values()
                if v.get('__typename') == 'Book' and v.get('legacyId') == int(book_id))
    work = next((v for v in ap.values() if v.get('__typename') == 'Work'), {})
    author_ref = book['primaryContributorEdge']['node']['__ref']
    author = ap.get(author_ref, {})

    stats = work.get('stats', {})
    work_details = work.get('details', {})
    book_details = book.get('details', {})

    return {
        'title':            book['title'],
        'title_complete':   book['titleComplete'],
        'book_id':          book['legacyId'],
        'url':              book['webUrl'],
        'cover_url':        book['imageUrl'],
        # Strip HTML tags from description
        'description':      re.sub(r'<[^>]+>', '', book.get('description({"stripped":true})',
                                   book.get('description', ''))).strip(),
        'genres':           [g['genre']['name'] for g in book.get('bookGenres', [])],
        'series':           [{'name': s['series']['title'], 'position': s.get('userPosition')}
                             for s in book.get('bookSeries', [])],
        # Author
        'author_name':      author.get('name'),
        'author_url':       author.get('webUrl'),
        # Edition details
        'format':           book_details.get('format'),
        'num_pages':        book_details.get('numPages'),
        'publisher':        book_details.get('publisher'),
        'language':         (book_details.get('language') or {}).get('name'),
        'isbn':             book_details.get('isbn'),
        'isbn13':           book_details.get('isbn13'),
        'pub_timestamp_ms': book_details.get('publicationTime'),
        # Ratings (from Work, not Book)
        'avg_rating':       stats.get('averageRating'),
        'ratings_count':    stats.get('ratingsCount'),
        'text_reviews':     stats.get('textReviewsCount'),
        # ratings_dist is list of counts for [1-star, 2-star, 3-star, 4-star, 5-star]
        'ratings_dist':     stats.get('ratingsCountDist'),
        # Awards
        'awards':           [a['name'] + (' — ' + a['category'] if a.get('category') else '')
                             for a in work_details.get('awardsWon', [])],
    }

# Example
book = parse_book(149267)  # The Stand by Stephen King
# book['title']        => "The Stand"
# book['avg_rating']   => 4.35
# book['ratings_count']=> 845591
# book['genres']       => ["Horror", "Fiction", "Fantasy", ...]
# book['awards']       => ["Locus Award — Best SF Novel", ...]
```

**Field notes:**
- `book['legacyId']` is the integer in the URL (e.g. `149267`). Use it to match the correct entity — the `apolloState` often contains 2-3 Book entries for different editions.
- Ratings and awards live in the `Work` entity, not `Book`. The `Work` is always `__typename == 'Work'`.
- `description` comes in two forms: `description` (HTML) and `description({"stripped":true})` (plain text). Prefer the stripped version.
- `pub_timestamp_ms` is a Unix timestamp in **milliseconds**. Convert: `datetime.fromtimestamp(ts/1000)`.
- `isbn` / `isbn13` are often `null` on older editions — the JSON-LD path (below) is no more reliable.

---

## Book Page — Fast Path (JSON-LD)

Use when you only need title, author, rating, page count, and awards. ~3× less parsing code.

```python
import re, json
from helpers import http_get

def parse_book_fast(book_id):
    html = http_get(f"https://www.goodreads.com/book/show/{book_id}")
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    if not blocks:
        return None
    ld = json.loads(blocks[0])
    return {
        'title':        ld.get('name'),
        'author':       ld['author'][0]['name'] if ld.get('author') else None,
        'avg_rating':   ld.get('aggregateRating', {}).get('ratingValue'),
        'ratings_count':ld.get('aggregateRating', {}).get('ratingCount'),
        'review_count': ld.get('aggregateRating', {}).get('reviewCount'),
        'num_pages':    ld.get('numberOfPages'),
        'isbn':         ld.get('isbn'),
        'cover_url':    ld.get('image'),
        'awards':       ld.get('awards'),   # single string, comma-separated
        'format':       ld.get('bookFormat'),
    }

book = parse_book_fast(149267)
# book['avg_rating']   => 4.35
# book['ratings_count']=> 845591
```

**JSON-LD does NOT include:** description, genres, series membership, per-star rating distribution, publisher, language.
Use `parse_book()` (the `__NEXT_DATA__` path) when you need any of those.

---

## Search Results

URL: `https://www.goodreads.com/search?q={query}&search_type=books&page={n}`

Search uses server-rendered HTML with schema.org microdata `<tr>` rows. No `__NEXT_DATA__`.

```python
import re, json
from helpers import http_get

def search_books(query, page=1):
    from urllib.parse import quote_plus
    url = f"https://www.goodreads.com/search?q={quote_plus(query)}&search_type=books&page={page}"
    html = http_get(url)

    rows = re.findall(
        r'<tr itemscope itemtype="http://schema.org/Book">(.*?)</tr>',
        html, re.DOTALL
    )

    results = []
    for row in rows:
        bid    = re.search(r'<div id="(\d+)" class="u-anchorTarget">', row)
        title  = re.search(r"itemprop='name'[^>]*>([^<]+)</span>", row)
        author = re.search(r'class="authorName"[^>]*><span[^>]*>([^<]+)</span>', row)
        avg    = re.search(r'(\d+\.\d+)\s*avg rating', row)
        cnt    = re.search(r'(\d[\d,]*)\s*rating', row)
        cover  = re.search(r'img alt="[^"]*" class="bookCover"[^>]*src="([^"]+)"', row)
        if not (bid and title):
            continue
        results.append({
            'book_id':      bid.group(1),
            'title':        title.group(1).strip(),
            'author':       author.group(1).strip() if author else None,
            'avg_rating':   float(avg.group(1)) if avg else None,
            'ratings_count':cnt.group(1).replace(',', '') if cnt else None,
            'cover_url':    cover.group(1) if cover else None,
            'url':          f"https://www.goodreads.com/book/show/{bid.group(1)}",
        })

    total_m = re.search(r'([\d,]+)\s+results', html)
    total   = int(total_m.group(1).replace(',', '')) if total_m else None

    return {'total': total, 'page': page, 'results': results}

# Example
r = search_books("dune")
# r['total']   => 101026
# r['results'] => [{'book_id':'44767458', 'title':'Dune (Dune, #1)', 'avg_rating':4.29, ...}, ...]
```

**Field notes:**
- Returns exactly 20 results per page.
- `total` is the result count shown in `"N results for…"` header.
- The `avg rating` regex uses `&mdash;` (HTML entity) in the raw HTML — the pattern above matches the decoded text.
- `ratings_count` regex hits the first occurrence of `\d+ rating` in the row, which is always the book's count (not a user review count).
- `cover_url` is a 75px thumbnail (`._SY75_.jpg`). Swap `_SY75_` → `_SX315_` for a larger image.

---

## Author Page

URL: `https://www.goodreads.com/author/show/{author_id}.{Slug}`

Author pages are **not** Next.js — they use classic server-rendered HTML with OG meta tags and microdata.
The author ID and slug can be obtained from a book's `author_url` field.

```python
import re, json
from helpers import http_get

def parse_author(author_id_and_slug):
    # author_id_and_slug e.g. "58.Frank_Patrick_Herbert"
    html = http_get(f"https://www.goodreads.com/author/show/{author_id_and_slug}")

    # Name and basic info from OG/meta tags
    name    = re.search(r"<meta content='([^']+)' property='og:title'>", html)
    img     = re.search(r"<meta content='([^']+)' property='og:image'>", html)
    website = re.search(r"Website\s*</div>\s*<div[^>]*>\s*<a[^>]*href=\"([^\"]+)\"", html)

    # Full biography from hidden span (shown/hidden by "...more" toggle in browser)
    bio_span = re.search(
        r'<span id="freeText(?:author|long)\d+"[^>]*>(.*?)</span>',
        html, re.DOTALL
    )
    bio = re.sub(r'<[^>]+>', '', bio_span.group(1)).strip() if bio_span else None

    # Top books listed on the page (10 rows, same microdata format as search)
    rows = re.findall(
        r'<tr itemscope itemtype="http://schema.org/Book">(.*?)</tr>',
        html, re.DOTALL
    )
    books = []
    for row in rows:
        bid   = re.search(r'<div id="(\d+)" class="u-anchorTarget">', row)
        title = re.search(r"itemprop='name'[^>]*>([^<]+)</span>", row)
        avg   = re.search(r'(\d+\.\d+)\s*avg rating', row)
        cnt   = re.search(r'(\d[\d,]*)\s*rating', row)
        if bid and title:
            books.append({
                'book_id':      bid.group(1),
                'title':        title.group(1).strip(),
                'avg_rating':   float(avg.group(1)) if avg else None,
                'ratings_count':cnt.group(1).replace(',', '') if cnt else None,
                'url':          f"https://www.goodreads.com/book/show/{bid.group(1)}",
            })

    return {
        'name':         name.group(1) if name else None,
        'profile_image':img.group(1) if img else None,
        'bio':          bio,
        'website':      website.group(1) if website else None,
        'top_books':    books,
    }

# Example
author = parse_author("58.Frank_Patrick_Herbert")
# author['name']    => "Frank Patrick Herbert"
# author['bio']     => "Franklin Patrick Herbert Jr. was an American science fiction..."
# len(author['top_books']) => 10
```

**Field notes:**
- Author IDs can be found in a book's `author_url` (from `__NEXT_DATA__` or JSON-LD).
- The slug is optional in the URL — numeric ID alone redirects correctly.
- `profile_image` from OG tag is a large portrait (p8 suffix = 800px). Swap to `p5` for 500px.
- The bio is server-rendered in a `<span id="freeTextauthor{ID}">` or `<span id="freeTextlong{ID}">` — which variant appears depends on length.
- Follower count is **not** present in the static HTML — it requires JS execution to appear.
- Page lists exactly 10 books. To get all books, paginate `/author/list/{author_id}?page=N`.

---

## Listopia List Page

URL: `https://www.goodreads.com/list/show/{list_id}.{Slug}?page={n}`

Returns 100 books per page with rank numbers.

```python
import re, json
from helpers import http_get

def parse_list(list_id_and_slug, page=1):
    url = f"https://www.goodreads.com/list/show/{list_id_and_slug}?page={page}"
    html = http_get(url)

    rows = re.findall(
        r'<tr itemscope itemtype="http://schema.org/Book">(.*?)</tr>',
        html, re.DOTALL
    )

    results = []
    for row in rows:
        rank   = re.search(r'<td[^>]*class="number"[^>]*>(\d+)</td>', row)
        bid    = re.search(r'<div id="(\d+)" class="u-anchorTarget">', row)
        title  = re.search(r"itemprop='name'[^>]*>([^<]+)</span>", row)
        author = re.search(r'class="authorName"[^>]*><span[^>]*>([^<]+)</span>', row)
        avg    = re.search(r'(\d+\.\d+)\s*avg rating', row)
        cnt    = re.search(r'(\d[\d,]*)\s*rating', row)
        if not (bid and title):
            continue
        results.append({
            'rank':         int(rank.group(1)) if rank else None,
            'book_id':      bid.group(1),
            'title':        title.group(1).strip(),
            'author':       author.group(1).strip() if author else None,
            'avg_rating':   float(avg.group(1)) if avg else None,
            'ratings_count':cnt.group(1).replace(',', '') if cnt else None,
            'url':          f"https://www.goodreads.com/book/show/{bid.group(1)}",
        })

    return {'page': page, 'results': results}

# Example
lst = parse_list("1.Best_Books_Ever")
# lst['results'][0] => {'rank': 1, 'book_id': '2767052',
#                       'title': 'The Hunger Games (The Hunger Games, #1)',
#                       'author': 'Suzanne Collins', 'avg_rating': 4.35, ...}
```

**Field notes:**
- 100 rows per page. Ranks are sequential across pages (page 2 starts at rank 101).
- Paginate with `?page=2`, `?page=3` etc.
- List pages do not use `__NEXT_DATA__` — same classic HTML format as author pages.

---

## Open Library API Fallback

Use Open Library when you need structured JSON without HTML parsing, or when you want supplementary data (birth/death dates, ISBNs across editions, subjects).

Open Library's ratings are from its own user base (~400 ratings vs. Goodreads' 800k+ for Dune) — use Goodreads ratings when accuracy matters.

### Search

```python
import json
from urllib.parse import quote_plus
from helpers import http_get

def ol_search(query, limit=10):
    url = f"https://openlibrary.org/search.json?q={quote_plus(query)}&limit={limit}"
    data = json.loads(http_get(url))
    results = []
    for doc in data.get('docs', []):
        cover_id = doc.get('cover_i')
        results.append({
            'ol_key':           doc['key'],           # e.g. "/works/OL893415W"
            'title':            doc.get('title'),
            'author':           (doc.get('author_name') or [''])[0],
            'author_key':       (doc.get('author_key') or [''])[0],
            'first_pub_year':   doc.get('first_publish_year'),
            'edition_count':    doc.get('edition_count'),
            'series':           doc.get('series_name'),
            'cover_url':        f"https://covers.openlibrary.org/b/id/{cover_id}-M.jpg" if cover_id else None,
        })
    return {'total': data.get('numFound'), 'results': results}

r = ol_search("dune frank herbert", limit=5)
# r['results'][0]['ol_key']  => "/works/OL893415W"
# r['results'][0]['title']   => "Dune"
```

### Work (book details)

```python
def ol_work(ol_key):
    # ol_key like "/works/OL893415W" or just "OL893415W"
    key = ol_key if ol_key.startswith('/') else f'/works/{ol_key}'
    data = json.loads(http_get(f"https://openlibrary.org{key}.json"))
    desc = data.get('description', '')
    if isinstance(desc, dict):
        desc = desc.get('value', '')
    return {
        'title':    data.get('title'),
        'subjects': data.get('subjects', []),
        'series':   data.get('series', []),
        'description': desc,
        'covers':   data.get('covers', []),
        'links':    data.get('links', []),
    }

work = ol_work("OL893415W")
# work['title']    => "Dune"
# work['subjects'] => ["Dune (Imaginary place)", "Fiction", ...]
```

### Ratings for a work

```python
def ol_ratings(ol_key):
    key = ol_key if ol_key.startswith('/') else f'/works/{ol_key}'
    data = json.loads(http_get(f"https://openlibrary.org{key}/ratings.json"))
    return data.get('summary', {})

# {'average': 4.30, 'count': 414, 'sortable': 4.21}
```

### Author

```python
def ol_author(author_key):
    # author_key like "OL79034A"
    data = json.loads(http_get(f"https://openlibrary.org/authors/{author_key}.json"))
    bio = data.get('bio', '')
    if isinstance(bio, dict):
        bio = bio.get('value', '')
    return {
        'name':        data.get('name'),
        'birth_date':  data.get('birth_date'),
        'death_date':  data.get('death_date'),
        'bio':         bio,
        'ol_key':      data.get('key'),
    }

author = ol_author("OL79034A")
# author['name']       => "Frank Herbert"
# author['birth_date'] => "8 October 1920"
# author['death_date'] => "11 February 1986"
```

---

## Combining Goodreads + Open Library

```python
# Get full book data: Goodreads for ratings/genres/description, OL for ISBNs/edition details
def get_book_full(goodreads_book_id, ol_work_key=None):
    gr = parse_book(goodreads_book_id)
    result = dict(gr)
    if ol_work_key:
        ol = ol_work(ol_work_key)
        result['ol_subjects']    = ol['subjects']
        result['ol_description'] = ol['description']
        result['ol_covers']      = ol['covers']
    return result
```

---

## Gotchas

- **Goodreads API is gone**: The official API was shut down in December 2020. All data must come from HTML scraping or the unofficial paths documented here.

- **Book ID 5107 redirects**: The URL `goodreads.com/book/show/5107.The_Stand` actually resolves to *The Catcher in the Rye* (ID 5107). The Stand is ID `149267`. Always verify `book['legacyId']` matches the URL ID.

- **Author page ID mismatch**: Author ID `10538` in the URL resolves to Carl Sagan, not Frank Herbert (ID `58`). Always obtain author IDs from the `author_url` field inside a book's data rather than guessing.

- **Two Book entities in `apolloState`**: The `apolloState` contains multiple `Book:` entries — one is a stub (only has `legacyId` and `webUrl`), and one is full. Filter by `legacyId == int(book_id)` AND check that the entry has more than 3 fields.

- **Ratings are on `Work`, not `Book`**: `avg_rating`, `ratingsCount`, and `ratingsCountDist` are in the `Work` entity's `stats` key. The `Book` entity has no rating fields.

- **Author pages are old-style HTML**: Author pages (`/author/show/`) do not use Next.js or `__NEXT_DATA__`. Use OG meta tags and regex for extraction. The follower count only loads via JS — it will be missing from `http_get` responses.

- **Search has no `__NEXT_DATA__`**: Search result pages (`/search`) are classic server-rendered HTML. JSON-LD is absent. Use the `<tr itemscope itemtype="http://schema.org/Book">` microdata rows.

- **`ratings_count` regex order matters**: The pattern `r'(\d[\d,]*)\s*rating'` always matches the book's aggregate rating count first in each search row — this is reliable. Do not use `minirating` span text as it contains nested HTML.

- **Open Library cover URLs return binary JPEG**: `http_get()` will raise a `UnicodeDecodeError` on cover image URLs. Use `urllib.request.urlopen()` directly and read bytes, or just store the URL string without fetching.

- **Open Library ratings are sparse**: OL has ~400 community ratings for Dune vs. Goodreads' 1.6M. Use OL ratings only as a last resort.

- **Search page `&mdash;` entity**: The raw HTML uses `&mdash;` (not `—`) between rating value and count in search and author pages. The regex patterns above match the decoded text because Python's `re` operates on the decoded string after `http_get()` decodes UTF-8.

- **Book slug is optional**: `goodreads.com/book/show/44767458` (no slug) works identically to `goodreads.com/book/show/44767458-dune`. Redirects are transparent.
