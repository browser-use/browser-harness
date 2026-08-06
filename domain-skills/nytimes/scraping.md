# New York Times — Data Extraction

`https://www.nytimes.com` and `https://api.nytimes.com` — Two entirely separate access paths exist. The **RSS feeds** are free, no key, no JS rendering, return 17–58 articles per section. The **official APIs** (`api.nytimes.com`) require a free key from `https://developer.nytimes.com/get-started` and cover search, top stories, books, and more. Article full-text is behind a paywall and Cloudflare blocks direct `http_get` on article URLs (403).

## Do this first: pick your access path

| Goal | Best approach | Latency | Auth needed |
|------|--------------|---------|------------|
| Current headlines by section | RSS feed | ~60–110ms | None |
| Most viewed / most emailed | RSS feed | ~77ms | None |
| Homepage article list with summaries | `window.__preloadedData` parse | ~250ms | None |
| Keyword search across all NYT content | Article Search API | ~300ms | Free API key |
| Top stories by section | Top Stories API | ~250ms | Free API key |
| Best-seller book lists | Books API | ~250ms | Free API key |
| Archive by month | Archive API | ~400ms | Free API key |
| Article full text | Browser + subscription session | Slow | Paid sub |

**Never use a browser for RSS feeds or API calls.** `http_get` is sufficient for all metadata tasks.

**Article pages 403 immediately** — Cloudflare DDoS protection blocks all non-browser `http_get` calls regardless of User-Agent. Full text requires a subscribed browser session.

---

## Path 1: RSS feeds (fastest, no key — confirmed working 2026-04-18)

55 section feeds. Cache TTL is 5 minutes (`Cache-Control: public, max-age=300`). Each feed returns 15–60 items.

```python
import xml.etree.ElementTree as ET
from helpers import http_get

MEDIA = 'http://search.yahoo.com/mrss/'
DC    = 'http://purl.org/dc/elements/1.1/'

def fetch_rss(section_url):
    """Parse any NYT RSS feed. Returns list of article dicts."""
    _, _, body = http_get(section_url)
    root    = ET.fromstring(body)
    channel = root.find('channel')
    results = []
    for item in channel.findall('item'):
        media   = item.find(f'{{{MEDIA}}}content')
        results.append({
            'title':       item.findtext('title'),
            'url':         item.findtext('link'),
            'description': item.findtext('description'),
            'pub_date':    item.findtext('pubDate'),         # 'Sat, 18 Apr 2026 20:17:14 +0000'
            'byline':      item.findtext(f'{{{DC}}}creator'),
            'categories':  [c.text for c in item.findall('category')],
            'image_url':   media.get('url') if media is not None else None,
        })
    return results

# Usage
articles = fetch_rss('https://rss.nytimes.com/services/xml/rss/nyt/World.xml')
# articles[0] confirmed output:
# {'title': 'Iran War Live Updates: Tensions Rise in Strait of Hormuz...',
#  'url': 'https://www.nytimes.com/live/2026/04/18/world/iran-us-war-trump-hormuz',
#  'description': "Iran's Revolutionary Guards said they were closing...",
#  'pub_date': 'Sat, 18 Apr 2026 23:51:55 +0000',
#  'byline': 'The New York Times',
#  'categories': [],
#  'image_url': 'https://static01.nyt.com/images/...mediumSquareAt3X.jpg'}
```

### Complete RSS feed catalog (55 feeds total)

```
# Top-level sections
https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml        # 17 items
https://rss.nytimes.com/services/xml/rss/nyt/World.xml           # 58 items
https://rss.nytimes.com/services/xml/rss/nyt/Africa.xml
https://rss.nytimes.com/services/xml/rss/nyt/Americas.xml
https://rss.nytimes.com/services/xml/rss/nyt/AsiaPacific.xml
https://rss.nytimes.com/services/xml/rss/nyt/Europe.xml
https://rss.nytimes.com/services/xml/rss/nyt/MiddleEast.xml
https://rss.nytimes.com/services/xml/rss/nyt/US.xml              # 20 items
https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml        # 20 items
https://rss.nytimes.com/services/xml/rss/nyt/Education.xml
https://rss.nytimes.com/services/xml/rss/nyt/NYRegion.xml
https://rss.nytimes.com/services/xml/rss/nyt/Upshot.xml

# Business / Economy
https://rss.nytimes.com/services/xml/rss/nyt/Business.xml        # 50 items
https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml
https://rss.nytimes.com/services/xml/rss/nyt/EnergyEnvironment.xml
https://rss.nytimes.com/services/xml/rss/nyt/SmallBusiness.xml
https://rss.nytimes.com/services/xml/rss/nyt/Dealbook.xml
https://rss.nytimes.com/services/xml/rss/nyt/MediaandAdvertising.xml
https://rss.nytimes.com/services/xml/rss/nyt/YourMoney.xml
https://rss.nytimes.com/services/xml/rss/nyt/PersonalTech.xml

# Sports
https://rss.nytimes.com/services/xml/rss/nyt/Sports.xml
https://rss.nytimes.com/services/xml/rss/nyt/Baseball.xml
https://rss.nytimes.com/services/xml/rss/nyt/ProBasketball.xml
https://rss.nytimes.com/services/xml/rss/nyt/ProFootball.xml
https://rss.nytimes.com/services/xml/rss/nyt/CollegeBasketball.xml
https://rss.nytimes.com/services/xml/rss/nyt/CollegeFootball.xml
https://rss.nytimes.com/services/xml/rss/nyt/Golf.xml
https://rss.nytimes.com/services/xml/rss/nyt/Hockey.xml
https://rss.nytimes.com/services/xml/rss/nyt/Soccer.xml
https://rss.nytimes.com/services/xml/rss/nyt/Tennis.xml

# Science / Health
https://rss.nytimes.com/services/xml/rss/nyt/Science.xml         # 20 items
https://rss.nytimes.com/services/xml/rss/nyt/Climate.xml
https://rss.nytimes.com/services/xml/rss/nyt/Space.xml
https://rss.nytimes.com/services/xml/rss/nyt/Well.xml

# Arts / Culture
https://rss.nytimes.com/services/xml/rss/nyt/Arts.xml            # 44 items
https://rss.nytimes.com/services/xml/rss/nyt/ArtandDesign.xml
https://rss.nytimes.com/services/xml/rss/nyt/Books.xml
https://rss.nytimes.com/services/xml/rss/nyt/SundayBookReview.xml
https://rss.nytimes.com/services/xml/rss/nyt/Dance.xml
https://rss.nytimes.com/services/xml/rss/nyt/Movies.xml
https://rss.nytimes.com/services/xml/rss/nyt/Music.xml
https://rss.nytimes.com/services/xml/rss/nyt/Television.xml
https://rss.nytimes.com/services/xml/rss/nyt/Theater.xml
https://rss.nytimes.com/services/xml/rss/nyt/FashionandStyle.xml
https://rss.nytimes.com/services/xml/rss/nyt/DiningandWine.xml
https://rss.nytimes.com/services/xml/rss/nyt/tmagazine.xml

# Opinion
https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml         # 49 items
https://rss.nytimes.com/services/xml/rss/nyt/sunday-review.xml

# Engagement lists
https://rss.nytimes.com/services/xml/rss/nyt/MostViewed.xml      # 19 items
https://rss.nytimes.com/services/xml/rss/nyt/MostEmailed.xml     # 17 items
https://rss.nytimes.com/services/xml/rss/nyt/MostShared.xml

# Other
https://rss.nytimes.com/services/xml/rss/nyt/Jobs.xml
https://rss.nytimes.com/services/xml/rss/nyt/RealEstate.xml
https://rss.nytimes.com/services/xml/rss/nyt/Automobiles.xml
https://rss.nytimes.com/services/xml/rss/nyt/Lens.xml
https://rss.nytimes.com/services/xml/rss/nyt/Obituaries.xml
```

Full feed index: `https://archive.nytimes.com/www.nytimes.com/services/xml/rss/`

---

## Path 2: Homepage `window.__preloadedData` (no key, richer fields)

The homepage embeds a 576KB JS object with full article metadata including summaries. The structure uses JS `undefined` (invalid JSON) — replace before parsing.

```python
import json, re
from helpers import http_get

def fetch_homepage_articles():
    """Returns list of article dicts from homepage embedded JSON. No API key needed."""
    _, _, body = http_get('https://www.nytimes.com/')
    
    idx = body.find('window.__preloadedData =')
    if idx < 0:
        return []
    
    # Extract JSON by brace-counting (regex .+ fails due to undefined values)
    start = body.index('{', idx)
    depth = 0
    for i in range(start, start + 2_000_000):
        c = body[i]
        if c == '{':   depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                raw = re.sub(r'\bundefined\b', 'null', body[start:i+1])
                break
    
    pd = json.loads(raw)
    
    results = []
    seen    = set()
    ARTICLE_URL = re.compile(r'https://www\.nytimes\.com/\d{4}/\d{2}/\d{2}/')

    def walk(node, depth=0):
        if not isinstance(node, dict) or depth > 15:
            return
        url = node.get('url', '')
        if isinstance(url, str) and ARTICLE_URL.match(url) and url not in seen:
            seen.add(url)
            hl = node.get('headline', {})
            results.append({
                'url':      url,
                'headline': hl.get('default', '') if isinstance(hl, dict) else '',
                'summary':  node.get('summary', ''),
                'type':     node.get('__typename', ''),   # 'Article', 'Video', 'Interactive'
            })
        for v in node.values():
            if isinstance(v, dict):
                walk(v, depth + 1)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        walk(item, depth + 1)

    walk(pd)
    return results

articles = fetch_homepage_articles()
# Confirmed output (2026-04-18, 51 unique articles):
# articles[0] = {
#   'url': 'https://www.nytimes.com/2026/04/18/us/politics/iran-hormuz-strait-trump.html',
#   'headline': 'For Iran, Flexing Control Over Waterway Is New Deterrent',
#   'summary': "Iran's government could emerge from the conflict with a blueprint...",
#   'type': 'Article'
# }
```

---

## Path 3: Official APIs (requires free key)

Register at `https://developer.nytimes.com/get-started`. Key arrives instantly via email. Rate limits: **10 requests/minute, 4,000/day** (free tier). Pass the key as `?api-key=YOUR_KEY`.

Error format on invalid/missing key (HTTP 401):
```json
{"fault": {"faultstring": "Invalid ApiKey", "detail": {"errorcode": "oauth.v2.InvalidApiKey"}}}
```

Rate limit exceeded returns HTTP 429. No rate-limit headers in responses — stay under 10/minute manually.

### Article Search API

Searches the full NYT archive (1851–present).

```python
import json
from helpers import http_get

KEY = "your_api_key_here"

# Basic search
data = json.loads(http_get(
    f"https://api.nytimes.com/svc/search/v2/articlesearch.json"
    f"?q=climate+change&api-key={KEY}"
)[2])

# data structure:
# data['response']['docs']    — list of article objects
# data['response']['meta']    — {'hits': 123456, 'offset': 0, 'time': 30}

docs = data['response']['docs']
for doc in docs[:3]:
    print(doc['headline']['main'])   # Main headline
    print(doc['web_url'])            # Full article URL
    print(doc['abstract'])           # Short summary
    print(doc['pub_date'])           # '2026-04-18T12:00:00+0000'
    print(doc['byline']['original']) # 'By Jane Smith'
    print(doc['section_name'])       # 'U.S.'
    print(doc['news_desk'])          # 'Washington'
    print(doc['word_count'])         # integer
    print(doc['_id'])                # 'nyt://article/uuid...'

# Pagination: use page= param (0-indexed, max 100 pages = 1000 results)
page2 = json.loads(http_get(
    f"https://api.nytimes.com/svc/search/v2/articlesearch.json"
    f"?q=climate&page=1&api-key={KEY}"
)[2])

# Date range filter
filtered = json.loads(http_get(
    f"https://api.nytimes.com/svc/search/v2/articlesearch.json"
    f"?q=elections&begin_date=20260101&end_date=20260418&api-key={KEY}"
)[2])

# Field filter (reduce response size)
compact = json.loads(http_get(
    f"https://api.nytimes.com/svc/search/v2/articlesearch.json"
    f"?q=economy&fl=headline,web_url,pub_date,byline&api-key={KEY}"
)[2])

# Sort (newest first)
recent = json.loads(http_get(
    f"https://api.nytimes.com/svc/search/v2/articlesearch.json"
    f"?q=technology&sort=newest&api-key={KEY}"
)[2])
```

**Article Search field reference:**
```
doc['headline']['main']         — primary headline
doc['headline']['print_headline'] — print edition headline (may differ)
doc['abstract']                 — short description (~1 sentence)
doc['snippet']                  — excerpt matching query
doc['lead_paragraph']           — first paragraph of article
doc['web_url']                  — canonical article URL
doc['pub_date']                 — ISO 8601 timestamp
doc['byline']['original']       — 'By First Last and First Last'
doc['byline']['person']         — list of {firstname, lastname, role}
doc['section_name']             — e.g. 'U.S.', 'World', 'Technology'
doc['subsection_name']          — e.g. 'Politics'
doc['news_desk']                — editorial desk, e.g. 'Washington'
doc['type_of_material']         — 'News', 'Op-Ed', 'Review', 'Letter', etc.
doc['word_count']               — integer
doc['keywords']                 — list of {name, value, rank} for tags
doc['multimedia']               — list of image objects with url, subtype
doc['_id']                      — 'nyt://article/<uuid>'
doc['uri']                      — same as _id
```

### Top Stories API

Returns the current top stories for a given section. ~15–40 articles per section.

```python
import json
from helpers import http_get

KEY = "your_api_key_here"

# Available sections: arts, automobiles, books, business, fashion, food,
# health, home, insider, magazine, movies, nyregion, obituaries, opinion,
# politics, realestate, science, sports, sundayreview, technology, theater,
# t-magazine, travel, upshot, us, world

data = json.loads(http_get(
    f"https://api.nytimes.com/svc/topstories/v2/technology.json?api-key={KEY}"
)[2])

# data structure:
# data['section']              — section name
# data['last_updated']         — ISO 8601
# data['num_results']          — count
# data['results']              — list of story objects

for story in data['results'][:3]:
    print(story['title'])
    print(story['abstract'])
    print(story['url'])
    print(story['byline'])          # 'By First Last'
    print(story['published_date'])  # '2026-04-18T20:08:40-04:00'
    print(story['updated_date'])
    print(story['section'])
    print(story['subsection'])
    print(story['des_facet'])       # list of topic tags
    print(story['geo_facet'])       # list of location tags
    print(story['per_facet'])       # list of person tags
    print(story['org_facet'])       # list of org tags
    # Multimedia: story['multimedia'] — list of images with url, format, caption
    if story.get('multimedia'):
        img = story['multimedia'][0]
        print(img['url'], img['format'])  # format: 'Standard Thumbnail', 'Large Thumbnail', etc.
```

### Most Popular API

```python
import json
from helpers import http_get

KEY = "your_api_key_here"

# periods: 1, 7, or 30 (days)
# types: viewed, shared, emailed

most_viewed = json.loads(http_get(
    f"https://api.nytimes.com/svc/mostpopular/v2/viewed/1.json?api-key={KEY}"
)[2])
# most_viewed['results'] — 20 articles, same shape as Top Stories

most_shared_week = json.loads(http_get(
    f"https://api.nytimes.com/svc/mostpopular/v2/shared/7.json?api-key={KEY}"
)[2])
```

### Books API — Best Seller Lists

```python
import json
from helpers import http_get

KEY = "your_api_key_here"

# Get all available list names
lists = json.loads(http_get(
    f"https://api.nytimes.com/svc/books/v3/lists/names.json?api-key={KEY}"
)[2])
# lists['results'] — each has: list_name, list_name_encoded, display_name,
#                   updated (WEEKLY/MONTHLY), oldest_published_date, newest_published_date

# Current best sellers for a list
fiction = json.loads(http_get(
    f"https://api.nytimes.com/svc/books/v3/lists/current/hardcover-fiction.json?api-key={KEY}"
)[2])
# fiction['results']['books'] — list of book objects
for book in fiction['results']['books'][:3]:
    print(book['rank'])              # 1, 2, 3...
    print(book['title'])
    print(book['author'])
    print(book['description'])
    print(book['weeks_on_list'])
    print(book['primary_isbn13'])
    print(book['buy_links'])         # list of {name, url} for retailers
    print(book['book_image'])        # cover image URL

# Historical list (specific date)
historical = json.loads(http_get(
    f"https://api.nytimes.com/svc/books/v3/lists/2025-01-05/hardcover-fiction.json?api-key={KEY}"
)[2])

# Common list_name_encoded values:
# hardcover-fiction, hardcover-nonfiction, trade-fiction-paperback,
# paperback-nonfiction, combined-print-and-e-book-fiction,
# young-adult-hardcover, childrens-middle-grade-hardcover, business-books,
# graphic-books-and-manga, science, advice-how-to-and-miscellaneous
```

### Archive API

Returns all articles for a given month — useful for historical bulk fetching.

```python
import json
from helpers import http_get

KEY = "your_api_key_here"

# All articles from January 2025
data = json.loads(http_get(
    f"https://api.nytimes.com/svc/archive/v1/2025/1.json?api-key={KEY}"
)[2])
# data['response']['docs'] — list of all articles (same shape as Article Search)
# Typically 5,000–9,000 articles per month
print(len(data['response']['docs']))
```

---

## Article URL structure

```
https://www.nytimes.com/{YYYY}/{MM}/{DD}/{section}/{subsection}/{slug}.html

# Examples:
https://www.nytimes.com/2026/04/18/us/politics/iran-hormuz-strait-trump.html
https://www.nytimes.com/2026/04/18/world/middleeast/hezbollah-cease-fire.html
https://www.nytimes.com/2026/04/18/opinion/pope-trump-hegseth-iran.html

# Live blogs use /live/ path:
https://www.nytimes.com/live/2026/04/18/world/iran-us-war-trump-hormuz

# Interactive / multimedia:
https://www.nytimes.com/interactive/2026/04/18/world/middleeast/iran-us-war-drones-cost.html
```

Parse section from URL:
```python
parts = url.split('/')
# parts: ['https:', '', 'www.nytimes.com', 'YYYY', 'MM', 'DD', 'section', ...]
section = parts[6] if len(parts) > 7 else None  # 'us', 'world', 'opinion', etc.
```

Image URLs follow the pattern:
```
https://static01.nyt.com/images/{YYYY}/{MM}/{DD}/multimedia/{slug}/{slug}-mediumSquareAt3X.jpg
```
Common image format suffixes: `mediumSquareAt3X`, `thumbStandard`, `jumbo`, `superJumbo`, `videoSixteenByNine1050`

---

## Parallel fetch across multiple feeds

```python
from concurrent.futures import ThreadPoolExecutor
import xml.etree.ElementTree as ET
from helpers import http_get

MEDIA = 'http://search.yahoo.com/mrss/'
DC    = 'http://purl.org/dc/elements/1.1/'

FEEDS = [
    'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
    'https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml',
    'https://rss.nytimes.com/services/xml/rss/nyt/Science.xml',
    'https://rss.nytimes.com/services/xml/rss/nyt/Opinion.xml',
]

def fetch_one(url):
    try:
        _, _, body = http_get(url)
        root = ET.fromstring(body)
        channel = root.find('channel')
        return [
            {
                'title':    item.findtext('title'),
                'url':      item.findtext('link'),
                'desc':     item.findtext('description'),
                'byline':   item.findtext(f'{{{DC}}}creator'),
                'pub_date': item.findtext('pubDate'),
                'cats':     [c.text for c in item.findall('category')],
            }
            for item in channel.findall('item')
        ]
    except Exception:
        return []

with ThreadPoolExecutor(max_workers=4) as ex:
    all_results = list(ex.map(fetch_one, FEEDS))

articles = [a for feed in all_results for a in feed]
print(f"Total articles: {len(articles)}")  # ~150 across 4 feeds
```

---

## Gotchas

- **Article pages return 403 unconditionally.** Cloudflare blocks all `http_get` calls to `www.nytimes.com/{year}/...` regardless of User-Agent (Chrome, Googlebot tested — both 403). The only way to read article full text is via a browser with a valid subscriber session cookie. For metadata only, RSS + API are sufficient.

- **`window.__preloadedData` contains JS `undefined`, not valid JSON.** Running `json.loads()` directly on the extracted blob fails. Replace `undefined` with `null` first: `re.sub(r'\bundefined\b', 'null', raw)`. The blob is ~576KB; do brace-counting extraction, not regex `.+`, which will OOM on the 1MB homepage.

- **RSS `<title>` and `<description>` are plain text, not CDATA.** Parse with `item.findtext('title')` — no CDATA unwrapping needed. Exception: older or less common feeds may use CDATA; ET handles both transparently.

- **RSS `dc:creator` can be "The New York Times" for wire-service or multi-byline pieces,** not a named journalist. Check before treating as a person name.

- **API `section` field in the URL is not the same as `section_name` in the response.** URL might be `/us/politics/` but `section_name` returns `"U.S."` and `news_desk` returns `"Washington"`. Use `section_name` for display; use the URL path for programmatic grouping.

- **Article Search `fl=` field filter silently drops missing fields.** If you request `fl=headline,byline` and a doc has no byline, the key is absent from the dict (not `null`). Always use `.get()`.

- **Top Stories and Most Popular return at most ~20–40 results per call.** There is no pagination param. For more results, use Article Search with `sort=newest`.

- **Archive API responses are large** — January 2025 returns ~6,000 articles in one call (~15MB JSON). Parse iteratively or filter fields with `fl=` if using Article Search instead.

- **Rate limit 429 response has no `Retry-After` header.** The API uses Google Apigee; after hitting 10 req/min you get a bare 429 with no backoff hint. Wait 60 seconds and retry.

- **RSS `pubDate` is in RFC 2822 format** (`Sat, 18 Apr 2026 20:17:14 +0000`), not ISO 8601. Parse with `email.utils.parsedate_to_datetime()` or `datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %z")`.

- **Image URLs from RSS are `mediumSquareAt3X` (1800×1800 px).** For smaller sizes, substitute the suffix: `thumbStandard` (75×75), `thumbLarge` (150×150), `articleInline` (~190px wide), `jumbo` (1024px wide).

- **`www.nytimes.com/section/{name}` pages load correctly** (200 OK, ~963KB), but their `initialData.data` dict is empty — section page data lives in `initialState` keyed by a base64 section ID, not a predictable string. Use RSS feeds for section content instead.
