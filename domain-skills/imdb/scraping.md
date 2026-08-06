# IMDb — Scraping & Data Extraction

`https://www.imdb.com` — the main site is **fully blocked by AWS WAF** (HTTP 202 with `x-amzn-waf-action: challenge`) for all `http_get` requests. Do not try to scrape HTML pages directly. Instead use the two public unauthenticated APIs documented below — both work reliably with a plain `User-Agent` header and no cookies.

**Primary paths (validated):**
1. **GraphQL API** (`https://api.graphql.imdb.com/`) — titles, persons, charts, box office. Full structured JSON. No auth.
2. **Suggest API** (`https://v3.sg.media-imdb.com/suggestion/x/{query}.json`) — search autocomplete. No auth.

**Unavailable via `http_get`:** All `www.imdb.com` HTML pages (title pages, chart pages, person pages, search results). AWS WAF returns HTTP 202 + empty body for every bot-looking request regardless of User-Agent.

---

## Do this first

For title lookups: **search with the Suggest API to get the `tt` ID, then fetch details with GraphQL.**

```python
import json, urllib.request

def imdb_graphql(query, variables={}):
    req_data = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.graphql.imdb.com/",
        data=req_data,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/json",
            "x-imdb-client-name": "imdb-web-next-localized",
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

def imdb_suggest(query):
    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
    return json.loads(http_get(
        f"https://v3.sg.media-imdb.com/suggestion/x/{query.replace(' ', '+')}.json",
        headers=headers
    ))
```

---

## Suggest API — fast search

**Endpoint:** `https://v3.sg.media-imdb.com/suggestion/x/{query}.json`

Variants:
- `/suggestion/x/{query}.json` — titles and names mixed
- `/suggestion/titles/x/{query}.json` — titles only (same results in practice)
- `/suggestion/names/x/{query}.json` — persons only

No authentication. No cookies needed. Works with any User-Agent. Returns JSON immediately.

```python
import json
from helpers import http_get

headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}
data = json.loads(http_get("https://v3.sg.media-imdb.com/suggestion/x/inception.json", headers=headers))
# data keys: 'd' (results list), 'q' (echo of query), 'v' (version, always 1)

for r in data.get('d', [])[:5]:
    print(r.get('l'), r.get('y'), r.get('id'), r.get('q'), r.get('s'))
# Inception 2010 tt1375666 feature Leonardo DiCaprio, Joseph Gordon-Levitt
```

### Suggest response fields (per result)

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | IMDb ID (`tt…` for titles, `nm…` for persons) |
| `l` | str | Label / title or person name |
| `y` | int | Year (release year for titles) |
| `yr` | str | Year range for TV series (e.g. `"2019-2023"`) |
| `q` | str | Human-readable type: `"feature"`, `"TV series"`, `"video"`, `"short"`, `"TV movie"` |
| `qid` | str | Machine type: `"movie"`, `"tvSeries"`, `"video"`, `"short"`, `"tvMovie"` |
| `s` | str | Stars / known-for (top cast for titles, known-for role for persons) |
| `rank` | int | IMDb popularity rank |
| `i` | obj | Image: `{imageUrl, width, height}` — direct CDN URL, no auth needed |

**Filter to movies only:**
```python
movies = [r for r in data.get('d', []) if r.get('qid') == 'movie']
```

**Look up by `tt` ID directly:**
```python
data = json.loads(http_get("https://v3.sg.media-imdb.com/suggestion/x/tt0468569.json", headers=headers))
# Returns the exact title entry for that ID
```

**Person search:**
```python
data = json.loads(http_get("https://v3.sg.media-imdb.com/suggestion/names/x/christopher+nolan.json", headers=headers))
# id=nm0634240, l='Christopher Nolan', rank=71, s='Producer, Tenet (2020)'
```

---

## GraphQL API — full title data

**Endpoint:** `POST https://api.graphql.imdb.com/`

Required headers:
- `Content-Type: application/json`
- `x-imdb-client-name: imdb-web-next-localized`

No auth token needed. Tested at 10+ rapid sequential requests with 100% success rate. No rate-limit headers observed.

**Important legal note:** IMDb's API response includes a disclaimer: *"Public, commercial, and/or non-private use of the IMDb data provided by this API is not allowed."* Use only for non-commercial personal tasks.

### Title details

```python
result = imdb_graphql("""
query FullTitle($id: ID!) {
  title(id: $id) {
    id
    titleText { text }
    originalTitleText { text }
    titleType { id text }
    releaseYear { year }
    releaseDate { year month day }
    ratingsSummary { aggregateRating voteCount }
    genres { genres { text } }
    runtime { seconds }
    plot { plotText { plainText } }
    certificate { rating }
    metacritic { metascore { score reviewCount } url }
    primaryImage { url width height }
    countriesOfOrigin { countries { text } }
    spokenLanguages { spokenLanguages { text } }
    keywords(first: 10) { edges { node { text } } }
    credits(first: 20) {
      edges {
        node {
          name { nameText { text } id }
          category { text }
          ... on Cast { characters { name } }
        }
      }
    }
    productionBudget { budget { amount currency } }
    openingWeekendGross(boxOfficeArea: DOMESTIC) {
      weekendStartDate weekendEndDate theaterCount
      gross { total { amount currency } }
    }
    lifetimeGross(boxOfficeArea: DOMESTIC) { total { amount currency } }
    rankedLifetimeGross(boxOfficeArea: WORLDWIDE) { rank total { amount currency } }
  }
}
""", {"id": "tt0468569"})

t = result['data']['title']
# Validated output for The Dark Knight (tt0468569):
# t['titleText']['text']                         → 'The Dark Knight'
# t['titleType']['id']                           → 'movie'
# t['releaseYear']['year']                       → 2008
# t['releaseDate']                               → {year:2008, month:7, day:18}
# t['ratingsSummary']['aggregateRating']         → 9.1
# t['ratingsSummary']['voteCount']               → 3158885
# t['metacritic']['metascore']['score']          → 85
# t['metacritic']['metascore']['reviewCount']    → 41
# t['genres']['genres']                          → [{'text':'Action'},{'text':'Crime'},...]
# t['runtime']['seconds']                        → 9120  (=152 min)
# t['certificate']['rating']                     → 'PG-13'
# t['countriesOfOrigin']['countries']            → [{'text':'United States'},{'text':'United Kingdom'}]
# t['spokenLanguages']['spokenLanguages']        → [{'text':'English'},{'text':'Mandarin'}]
# t['keywords']['edges']                         → [{'node':{'text':'psychopath'}},...]
# t['productionBudget']['budget']                → {amount:185000000, currency:'USD'}
# t['openingWeekendGross']['gross']['total']     → {amount:158411483, currency:'USD'}
# t['openingWeekendGross']['theaterCount']       → 4366
# t['lifetimeGross']['total']                    → {amount:534987076, currency:'USD'}
# t['rankedLifetimeGross']['total']              → {amount:1008477382, currency:'USD'}
# t['rankedLifetimeGross']['rank']               → 59  (worldwide rank)
# t['primaryImage']['url']                       → 'https://m.media-amazon.com/images/M/...'
```

**Credits note:** `credits` returns all categories mixed. Use `category.text` to filter:
- Actor, Actress → cast
- Director, Writer, Producer → crew

The `... on Cast { characters { name } }` inline fragment is required — `characters` is not on the base `Credit` type.

### Person details

```python
result = imdb_graphql("""
query PersonQuery($id: ID!) {
  name(id: $id) {
    nameText { text }
    birthDate { displayableProperty { value { plainText } } }
    birthLocation { text }
    bio { text { plainText } }
    primaryImage { url }
    knownFor(first: 5) {
      edges {
        node {
          title { id titleText { text } releaseYear { year } }
        }
      }
    }
  }
}
""", {"id": "nm0000151"})

p = result['data']['name']
# p['nameText']['text']                                          → 'Morgan Freeman'
# p['birthDate']['displayableProperty']['value']['plainText']   → 'June 1, 1937'
# p['birthLocation']['text']                                     → 'Memphis, Tennessee, USA'
# p['bio']['text']['plainText']                                  → (full biography text)
# p['knownFor']['edges'][0]['node']['title']['titleText']['text'] → 'Seven'
```

**Note:** `birthDate` field type is `DisplayableDate`, not a structured date object. Fields `year`, `month`, `day` do not exist on it — only `displayableProperty.value.plainText` (human-readable string like `"June 1, 1937"`).

### Top 250 / Charts

```python
result = imdb_graphql("""
query ChartQuery {
  chartTitles(first: 250, chart: {chartType: TOP_RATED_MOVIES}) {
    edges {
      currentRank
      node {
        id
        titleText { text }
        releaseYear { year }
        ratingsSummary { aggregateRating voteCount }
      }
    }
  }
}
""")

for edge in result['data']['chartTitles']['edges'][:5]:
    print(edge['currentRank'], edge['node']['titleText']['text'], edge['node']['ratingsSummary']['aggregateRating'])
# 1 The Shawshank Redemption 9.3
# 2 The Godfather 9.2
# 3 The Dark Knight 9.1
```

**Valid `chartType` enum values** (from schema introspection):
- `TOP_RATED_MOVIES` — IMDb Top 250 movies
- `TOP_RATED_TV_SHOWS` — Top 250 TV
- `MOST_POPULAR_MOVIES`
- `MOST_POPULAR_TV_SHOWS`
- `TOP_RATED_ENGLISH_MOVIES`
- `TOP_RATED_INDIAN_MOVIES`
- `TOP_RATED_MALAYALAM_MOVIES`
- `TOP_RATED_TAMIL_MOVIES`
- `TOP_RATED_TELUGU_MOVIES`
- `LOWEST_RATED_MOVIES`

### Currently trending titles

```python
result = imdb_graphql("""
query TrendingQuery {
  topMeterTitles(first: 10) {
    edges {
      node {
        id
        titleText { text }
        releaseYear { year }
        ratingsSummary { aggregateRating voteCount }
        genres { genres { text } }
      }
    }
  }
}
""")
# Returns IMDb MeterTitles — currently most-viewed/searched titles
```

---

## Common workflows

### Search then fetch title details

```python
import json, urllib.request
from helpers import http_get

headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

# Step 1: search
suggest = json.loads(http_get("https://v3.sg.media-imdb.com/suggestion/x/the+dark+knight.json", headers=headers))
movies = [r for r in suggest['d'] if r.get('qid') == 'movie']
title_id = movies[0]['id']   # 'tt0468569'
print(f"Found: {movies[0]['l']} ({movies[0]['y']}) — {title_id}")

# Step 2: fetch full data
def imdb_graphql(query, variables={}):
    req_data = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.graphql.imdb.com/",
        data=req_data,
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "x-imdb-client-name": "imdb-web-next-localized"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

result = imdb_graphql("""
query Q($id: ID!) {
  title(id: $id) {
    titleText { text }
    ratingsSummary { aggregateRating voteCount }
    plot { plotText { plainText } }
    runtime { seconds }
    genres { genres { text } }
    certificate { rating }
  }
}
""", {"id": title_id})
t = result['data']['title']
print(t['titleText']['text'], t['ratingsSummary']['aggregateRating'], f"({t['ratingsSummary']['voteCount']:,} votes)")
print("Runtime:", t['runtime']['seconds'] // 60, "min")
print("Genres:", [g['text'] for g in t['genres']['genres']])
print("Plot:", t['plot']['plotText']['plainText'])
```

### Bulk title fetch (parallel)

```python
from concurrent.futures import ThreadPoolExecutor
import json, urllib.request

def fetch_title(tt_id):
    req_data = json.dumps({
        "query": "query Q($id:ID!){title(id:$id){titleText{text}ratingsSummary{aggregateRating voteCount}}}",
        "variables": {"id": tt_id}
    }).encode()
    req = urllib.request.Request(
        "https://api.graphql.imdb.com/",
        data=req_data,
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "x-imdb-client-name": "imdb-web-next-localized"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())['data']['title']

ids = ["tt0111161", "tt0068646", "tt0468569", "tt0071562", "tt0050083"]
with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_title, ids))
for t in results:
    print(t['titleText']['text'], t['ratingsSummary']['aggregateRating'])
# 10/10 requests succeeded in rapid succession — no rate limiting observed
```

### Get Top 250 with ranks and ratings

```python
import json, urllib.request

def imdb_graphql(query, variables={}):
    req_data = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        "https://api.graphql.imdb.com/",
        data=req_data,
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json", "x-imdb-client-name": "imdb-web-next-localized"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())

result = imdb_graphql("""
query Top250 {
  chartTitles(first: 250, chart: {chartType: TOP_RATED_MOVIES}) {
    edges {
      currentRank
      node {
        id
        titleText { text }
        releaseYear { year }
        ratingsSummary { aggregateRating voteCount }
      }
    }
  }
}
""")

top250 = [
    {
        "rank": e['currentRank'],
        "id": e['node']['id'],
        "title": e['node']['titleText']['text'],
        "year": e['node']['releaseYear']['year'],
        "rating": e['node']['ratingsSummary']['aggregateRating'],
        "votes": e['node']['ratingsSummary']['voteCount'],
    }
    for e in result['data']['chartTitles']['edges']
]
# top250[0] → {'rank':1, 'id':'tt0111161', 'title':'The Shawshank Redemption', 'year':1994, 'rating':9.3, 'votes':3179483}
```

---

## Bot detection & rate limits

### AWS WAF on `www.imdb.com`

All requests to `www.imdb.com` pages (HTML title pages, search, charts) are blocked:
- HTTP status **202** (not 403 — intentional deception)
- Header: `x-amzn-waf-action: challenge`
- Body: empty (`Content-Length: 0`) OR a 2 KB JS challenge page that requires `AwsWafIntegration.getToken()` to run
- Affected regardless of User-Agent string (Googlebot, Chrome, curl — all blocked)
- The WAF uses cryptographic token validation that requires JavaScript execution in a real browser

**Workaround:** Use the two APIs documented above. They are hosted on different domains that are not WAF-protected.

### Suggest API (`v3.sg.media-imdb.com`)

- No rate limiting observed at conversational usage (1–5 req/s)
- Returns in < 100 ms
- No cookies or tokens needed
- Any User-Agent works

### GraphQL API (`api.graphql.imdb.com`)

- No rate limiting observed: 10 rapid sequential requests all succeeded (HTTP 200)
- Parallel fetching at 5 workers tested successfully
- No auth token needed
- Required header: `x-imdb-client-name: imdb-web-next-localized` (without this, schema introspection fails with 500 but regular queries still work)
- Partial introspection allowed (single-type `__type` queries work; full `__schema` queries return 500 Unauthorized)

---

## GraphQL schema gotchas

- **`birthDate` is `DisplayableDate`, not a date struct.** Use `birthDate { displayableProperty { value { plainText } } }` — returns human string like `"June 1, 1937"`. Fields `year`, `month`, `day` do not exist on this type.

- **`characters` requires inline fragment.** Must use `... on Cast { characters { name } }` inside `credits` — cannot query `characters` directly on `Credit`.

- **`lifetimeGross` and `rankedLifetimeGross` are different types.** `lifetimeGross` returns `BoxOfficeGross` (just `total { amount currency }`). `rankedLifetimeGross` returns `RankedLifetimeBoxOfficeGross` (has `rank` + `total { amount currency }`). Both take `boxOfficeArea: DOMESTIC | WORLDWIDE`.

- **`openingWeekendGross.gross` is nested.** Path is `openingWeekendGross(boxOfficeArea: DOMESTIC) { gross { total { amount currency } } }`.

- **`metacriticScore` does not exist.** Use `metacritic { metascore { score reviewCount } url }`.

- **`chartTitles` requires `chart` argument as an object.** Use `chart: {chartType: TOP_RATED_MOVIES}` not `chartType: TOP_RATED_MOVIES` directly.

- **`worldwideGross` does not exist.** Use `rankedLifetimeGross(boxOfficeArea: WORLDWIDE) { rank total { amount currency } }` instead.

- **`productionBudget.budget` contains `amount` (integer) + `currency` (string).** E.g. `{amount: 185000000, currency: "USD"}`.

---

## Browser-based extraction (secondary path — not validated due to Chrome session expiry)

If the GraphQL API becomes unavailable and a live browser session exists, IMDb title pages use Next.js with `data-testid` attributes. Recommended selectors based on IMDb's known structure:

```python
# Requires an active browser session with goto() called first
from helpers import goto, js, wait_for_load

goto("https://www.imdb.com/title/tt0468569/")
wait_for_load()

# Title
title = js("document.querySelector('[data-testid=\"hero__pageTitle\"] span')?.textContent")

# Rating
rating = js("document.querySelector('[data-testid=\"hero-rating-bar__aggregate-rating__score\"] span:first-child')?.textContent")

# Plot
plot = js("document.querySelector('[data-testid=\"plot-xl\"]')?.textContent")

# Genre chips
genres = js("Array.from(document.querySelectorAll('[data-testid=\"genres\"] a')).map(a => a.textContent)")

# Cast
cast = js("Array.from(document.querySelectorAll('[data-testid=\"title-cast-item__actor\"]')).slice(0,5).map(el => el.textContent)")

# JSON-LD (available in page source when not WAF-blocked)
ld_json = js("""
const s = document.querySelector('script[type="application/ld+json"]');
s ? JSON.parse(s.textContent) : null
""")
# ld_json.name, ld_json.aggregateRating.ratingValue, ld_json.genre, ld_json.director, ld_json.description
```

**When this path is viable:** Only when `goto()` loads a full HTML page (check `page_info()['title']` is not empty). IMDb loads Next.js client-side — `wait_for_load()` is usually sufficient, but rating widgets may need an additional `wait(1.0)`.

**`__NEXT_DATA__` script tag** is present in browser-rendered pages and contains `props.pageProps` with structured title data — faster to parse than DOM queries if you need many fields at once.
