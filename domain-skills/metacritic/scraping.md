# Metacritic — Scraping & Data Extraction

Field-tested against metacritic.com on 2026-04-18. All code blocks validated with live requests.

## Do this first

**Use the backend API — it returns clean JSON with both scores in one call, no HTML parsing.**

Metacritic's internal backend API is publicly accessible with a stable key embedded in every page. It covers games, movies, and TV shows.

```python
import json

API_KEY = "1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"

def get_game_scores(slug):
    """slug = URL slug e.g. 'elden-ring', 'the-last-of-us'"""
    base = f"https://backend.metacritic.com"
    product = json.loads(http_get(
        f"{base}/games/metacritic/{slug}/web"
        f"?componentName=product&componentType=Product&apiKey={API_KEY}"
    ))
    user_stats = json.loads(http_get(
        f"{base}/reviews/metacritic/user/games/{slug}/stats/web"
        f"?componentName=user-score-summary&componentType=ScoreSummary&apiKey={API_KEY}"
    ))
    item = product["data"]["item"]
    crit = item["criticScoreSummary"]
    user = user_stats["data"]["item"]
    return {
        "title": item["title"],
        "platform": item["platform"],           # lead platform
        "platforms": item["platforms"],          # list with per-platform scores
        "metascore": crit["score"],              # int 0–100 or None
        "critic_reviews": crit["reviewCount"],  # int
        "critic_sentiment": crit["sentiment"],   # e.g. "Universal acclaim"
        "user_score": user["score"],             # float 0.0–10.0 or None
        "user_reviews": user["reviewCount"],     # int
        "user_sentiment": user["sentiment"],
        "release_date": item["releaseDate"],     # "YYYY-MM-DD"
    }

print(get_game_scores("the-last-of-us"))
# {'title': 'The Last of Us', 'platform': 'PlayStation 3',
#  'metascore': 95, 'critic_reviews': 98,
#  'user_score': 9.2, 'user_reviews': 17207, ...}
```

Use the browser **only** if you need music pages — `metacritic.com/music/*` returns HTTP 403 to `http_get` (Cloudflare blocks those routes). Games, movies, and TV all work with plain HTTP.

---

## Fastest approach: JSON-LD (critic score + review count only)

If you only need the Metascore and critic review count and don't need the user score, JSON-LD is the single-call option — no API key, no separate request:

```python
import json, re

url = "https://www.metacritic.com/game/elden-ring/"   # or /movie/ or /tv/
html = http_get(url)

block = re.findall(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
    html, re.DOTALL
)[0]
ld = json.loads(block)

agg = ld["aggregateRating"]
print(ld["name"])                   # "Elden Ring"
print(agg["ratingValue"])           # 96  (metascore)
print(agg["reviewCount"])           # 93  (critic reviews count)
print(ld.get("gamePlatform"))       # ['Xbox One', 'PC', 'PlayStation 4', 'Xbox Series X', 'PlayStation 5']
print(ld.get("genre"))              # "Action RPG"
print(ld.get("contentRating"))      # "M"
print(ld.get("datePublished"))      # "2022-02-25"
```

**JSON-LD limitations:**
- Only contains Metascore and critic review count — **no user score, no user review count**.
- For multi-platform games, `ratingValue` is the lead platform score; all platforms are listed in `gamePlatform` but without individual scores.
- `@type` is `VideoGame` for games, `Movie` for movies, `TVSeries` for TV shows.

---

## Common workflows

### Get scores for a single title (backend API)

```python
import json

API_KEY = "1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"
BASE = "https://backend.metacritic.com"

# Games
def game_scores(slug):
    p = json.loads(http_get(f"{BASE}/games/metacritic/{slug}/web?componentName=product&componentType=Product&apiKey={API_KEY}"))
    u = json.loads(http_get(f"{BASE}/reviews/metacritic/user/games/{slug}/stats/web?componentName=user-score-summary&componentType=ScoreSummary&apiKey={API_KEY}"))
    c = p["data"]["item"]["criticScoreSummary"]
    us = u["data"]["item"]
    return {"metascore": c["score"], "critic_reviews": c["reviewCount"],
            "user_score": us["score"], "user_reviews": us["reviewCount"]}

# Movies
def movie_scores(slug):
    p = json.loads(http_get(f"{BASE}/movies/metacritic/{slug}/web?componentName=product&componentType=Product&apiKey={API_KEY}"))
    u = json.loads(http_get(f"{BASE}/reviews/metacritic/user/movies/{slug}/stats/web?componentName=user-score-summary&componentType=ScoreSummary&apiKey={API_KEY}"))
    c = p["data"]["item"]["criticScoreSummary"]
    us = u["data"]["item"]
    return {"metascore": c["score"], "critic_reviews": c["reviewCount"],
            "user_score": us["score"], "user_reviews": us["reviewCount"]}

# TV shows
def show_scores(slug):
    p = json.loads(http_get(f"{BASE}/shows/metacritic/{slug}/web?componentName=product&componentType=Product&apiKey={API_KEY}"))
    u = json.loads(http_get(f"{BASE}/reviews/metacritic/user/shows/{slug}/stats/web?componentName=user-score-summary&componentType=ScoreSummary&apiKey={API_KEY}"))
    c = p["data"]["item"]["criticScoreSummary"]
    us = u["data"]["item"]
    return {"metascore": c["score"], "critic_reviews": c["reviewCount"],
            "user_score": us["score"], "user_reviews": us["reviewCount"]}

# Verified results:
print(game_scores("the-last-of-us"))
# {'metascore': 95, 'critic_reviews': 98, 'user_score': 9.2, 'user_reviews': 17207}
print(movie_scores("the-godfather"))
# {'metascore': 100, 'critic_reviews': 16, 'user_score': 9.2, 'user_reviews': 4450}
print(show_scores("breaking-bad"))
# {'metascore': 87, 'critic_reviews': 98, 'user_score': 9.4, 'user_reviews': 19070}
```

### Parallel fetching (multiple titles at once)

10 API calls in 0.68s with 5 workers — no rate-limit errors:

```python
import json
from concurrent.futures import ThreadPoolExecutor
import urllib.request, gzip

API_KEY = "1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"

def _fetch(url):
    h = {"User-Agent": "Mozilla/5.0", "Accept-Encoding": "gzip"}
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=15) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip": data = gzip.decompress(data)
        return json.loads(data.decode())

def batch_game_scores(slugs, workers=5):
    """Fetch critic+user scores for multiple game slugs in parallel."""
    BASE = "https://backend.metacritic.com"
    AK = f"apiKey={API_KEY}"

    def fetch_one(slug):
        c = _fetch(f"{BASE}/reviews/metacritic/critic/games/{slug}/stats/web?componentName=critic-score-summary&componentType=ScoreSummary&{AK}")
        u = _fetch(f"{BASE}/reviews/metacritic/user/games/{slug}/stats/web?componentName=user-score-summary&componentType=ScoreSummary&{AK}")
        ci = c["data"]["item"]
        ui = u["data"]["item"]
        return {"slug": slug, "metascore": ci["score"], "critic_reviews": ci["reviewCount"],
                "user_score": ui["score"], "user_reviews": ui["reviewCount"]}

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fetch_one, slugs))

results = batch_game_scores([
    "the-last-of-us", "elden-ring", "god-of-war",
    "red-dead-redemption-2", "the-witcher-3-wild-hunt"
])
# the-last-of-us: meta=95/98critics, user=9.2/17207
# elden-ring: meta=96/86critics, user=8.4/23344
# god-of-war: meta=94/118critics, user=9.0/30439
# red-dead-redemption-2: meta=97/99critics, user=9.0/35306
# the-witcher-3-wild-hunt: meta=92/79critics, user=9.1/19370
```

### Search by title

```python
import json, urllib.parse

API_KEY = "1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"

def search(query, media_type=None, limit=10):
    """
    media_type: None='all', 'games' (mcoTypeId=13), 'movies' (2), 'shows' (1)
    Returns list of {title, type, slug, premiereYear, metascore, user_score}
    """
    type_map = {"games": 13, "movies": 2, "shows": 1}
    q = urllib.parse.quote(query)
    type_param = f"&mcoTypeId={type_map[media_type]}" if media_type else "&mcoTypeId=1%2C2%2C3%2C13"
    url = (
        f"https://backend.metacritic.com/finder/metacritic/search/{q}/web"
        f"?offset=0&limit={limit}&sortBy=META_SCORE&sortDirection=DESC"
        f"{type_param}&componentName=search&componentType=SearchResult"
        f"&apiKey={API_KEY}"
    )
    data = json.loads(http_get(url))
    items = data["data"]["items"]
    return [
        {
            "title": i["title"],
            "type": i["type"],          # "game-title", "movie", "tv-show"
            "slug": i["slug"],
            "year": i.get("premiereYear"),
            "metascore": i.get("criticScoreSummary", {}).get("score"),
            "user_score": i.get("userScore"),  # None in search results (use stats API for this)
        }
        for i in items
    ]

results = search("elden ring", media_type="games")
# [{'title': 'Elden Ring', 'type': 'game-title', 'slug': 'elden-ring', 'year': 2022, 'metascore': 96, ...}]
```

**Note:** `userScore` is `None` in search results. Call the stats API with the `slug` to get it.

### Browse/list titles by score

```python
import json

API_KEY = "1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"

def browse_games(sort_by="-metaScore", year_min=None, year_max=None, offset=0, limit=24):
    """
    sort_by: '-metaScore' | '-releaseDate' | '-popularityCount'
    Returns up to `limit` games with criticScoreSummary and userScore.
    Total available: ~14,160 games.
    """
    params = f"sortBy={sort_by}&mcoTypeId=13&offset={offset}&limit={limit}"
    if year_min: params += f"&releaseYearMin={year_min}"
    if year_max: params += f"&releaseYearMax={year_max}"
    url = f"https://backend.metacritic.com/finder/metacritic/web?{params}&componentName=finder&componentType=Finder&apiKey={API_KEY}"
    data = json.loads(http_get(url))
    total = data["data"]["totalResults"]
    items = data["data"]["items"]
    return total, [
        {
            "title": i["title"],
            "slug": i["slug"],
            "year": i.get("premiereYear"),
            "metascore": i.get("criticScoreSummary", {}).get("score"),
            "critic_reviews": i.get("criticScoreSummary", {}).get("reviewCount"),
            "user_score": i.get("userScore", {}).get("score") if isinstance(i.get("userScore"), dict) else i.get("userScore"),
        }
        for i in items
    ]

total, games = browse_games(year_min=2023, year_max=2024)
print(f"{total} games 2023-2024")   # 953
for g in games[:3]:
    print(g)
# {'title': "Baldur's Gate 3", 'year': 2023, 'metascore': 96, 'user_score': 9.2}
# {'title': 'The Legend of Zelda: Tears of the Kingdom', 'year': 2023, 'metascore': 96, ...}
```

Finder API totals (confirmed 2026-04-18):
- Games (mcoTypeId=13): 14,160
- Movies (mcoTypeId=2): 17,152
- TV Shows (mcoTypeId=1): 3,392

### Get per-platform scores for multi-platform games

```python
import json

API_KEY = "1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"

def game_platforms(slug):
    url = (
        f"https://backend.metacritic.com/games/metacritic/{slug}/web"
        f"?componentName=product&componentType=Product&apiKey={API_KEY}"
    )
    data = json.loads(http_get(url))
    platforms = data["data"]["item"]["platforms"]
    return [
        {
            "name": p["name"],
            "slug": p["slug"],
            "is_lead": p["isLeadPlatform"],
            "metascore": p["criticScoreSummary"]["score"],        # None if <4 reviews
            "critic_reviews": p["criticScoreSummary"]["reviewCount"],
            "release_date": p["releaseDate"],
        }
        for p in platforms
    ]

print(game_platforms("elden-ring"))
# [{'name': 'Xbox One', 'slug': 'xbox-one', 'is_lead': False, 'metascore': None, ...},
#  {'name': 'PC', 'slug': 'pc', 'is_lead': False, 'metascore': 94, 'critic_reviews': 63},
#  {'name': 'PlayStation 4', 'slug': 'playstation-4', 'is_lead': False, 'metascore': None, 'critic_reviews': 1},
#  {'name': 'Xbox Series X', 'slug': 'xbox-series-x', 'is_lead': False, 'metascore': 96, 'critic_reviews': 19},
#  {'name': 'PlayStation 5', 'slug': 'playstation-5', 'is_lead': True, 'metascore': 96, 'critic_reviews': 93}]
```

### Get critic reviews (paginated)

```python
import json

API_KEY = "1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"

def get_critic_reviews(slug, media="games", offset=0, limit=10, sort="date"):
    """sort: 'date' | 'score' | 'publication'"""
    url = (
        f"https://backend.metacritic.com/reviews/metacritic/critic/{media}/{slug}/web"
        f"?offset={offset}&limit={limit}&sort={sort}"
        f"&componentName=latest-critic-reviews&componentType=CriticReviewList&apiKey={API_KEY}"
    )
    data = json.loads(http_get(url))
    total = data["data"]["totalResults"]   # e.g. 98
    items = data["data"]["items"]
    return total, [
        {
            "score": r["score"],                # int 0–100
            "publication": r["publicationName"],
            "quote": r["quote"],
            "date": r["date"],
            "url": r.get("url"),
        }
        for r in items
    ]

total, reviews = get_critic_reviews("the-last-of-us", sort="score")
print(f"{total} critic reviews")   # 98
print(reviews[0])
# {'score': 97, 'publication': 'GamingXP', 'quote': 'Flawless in its ambition...', 'date': '...'}
```

### Get user reviews (paginated)

```python
import json

API_KEY = "1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u"

def get_user_reviews(slug, media="games", offset=0, limit=10, order_by="score", order_type="desc"):
    """order_by: 'score' | 'date' | 'helpfulness'"""
    url = (
        f"https://backend.metacritic.com/reviews/metacritic/user/{media}/{slug}/web"
        f"?offset={offset}&limit={limit}&orderBy={order_by}&orderType={order_type}"
        f"&componentName=top-user-reviews&componentType=UserReviewList&apiKey={API_KEY}"
    )
    data = json.loads(http_get(url))
    total = data["data"]["totalResults"]   # e.g. 2983 for The Last of Us
    items = data["data"]["items"]
    return total, [
        {
            "score": r["score"],   # int 0–10
            "quote": r["quote"],
            "date": r["date"],
            "spoiler": r.get("spoiler", False),
        }
        for r in items
    ]

total, reviews = get_user_reviews("the-last-of-us")
print(f"{total} user reviews")   # 2983
```

### NUXT_DATA extraction (alternative, no API key)

If you need to avoid the backend API (e.g., the API key rotates), the HTML page embeds all score data in `<script id="__NUXT_DATA__">` as a flat pool with integer cross-references. This is more fragile but requires no API key:

```python
import json, re

url = "https://www.metacritic.com/game/the-last-of-us/"
html = http_get(url)

pool = json.loads(
    re.search(r'<script[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL).group(1)
)

def deref(pool, idx, depth=0, visited=None):
    if visited is None: visited = set()
    if not isinstance(idx, int) or idx in visited or depth > 4: return idx
    visited.add(idx)
    val = pool[idx]
    if isinstance(val, dict):
        return {k: deref(pool, v, depth+1, visited) if isinstance(v, int) else v for k, v in val.items()}
    elif isinstance(val, list) and len(val) == 2 and isinstance(val[0], str) and val[0] in ('Ref','Reactive','ShallowReactive','ShallowRef'):
        return deref(pool, val[1], depth+1, visited)
    elif isinstance(val, list):
        return [deref(pool, v, depth+1, visited) if isinstance(v, int) else v for v in val]
    return val

# Find components
components_idx = next(
    pool[i] for i, v in enumerate(pool)
    if isinstance(v, list) and len(v) > 3 and all(isinstance(x, int) for x in v[:3])
    and isinstance(pool[v[0]], dict) and 'data' in pool[v[0]] and 'meta' in pool[v[0]]
)

def find_component(pool, name):
    for i, val in enumerate(pool):
        if not isinstance(val, dict) or 'data' not in val or 'meta' not in val: continue
        meta = pool[val['meta']] if isinstance(val.get('meta'), int) else {}
        if not isinstance(meta, dict): continue
        cname = pool[meta.get('componentName')] if isinstance(meta.get('componentName'), int) else ''
        if cname == name: return deref(pool, val['data'])
    return None

critic = find_component(pool, 'critic-score-summary')
user = find_component(pool, 'user-score-summary')
print("Metascore:", critic['item']['score'])        # 95
print("Critic reviews:", critic['item']['reviewCount'])  # 98
print("User score:", user['item']['score'])         # 9.2
print("User reviews:", user['item']['reviewCount']) # 17207
```

---

## URL slug patterns

Metacritic slugs are lowercased, spaces replaced with hyphens, special chars dropped:

| Title | Slug |
|-------|------|
| `The Last of Us` | `the-last-of-us` |
| `Baldur's Gate 3` | `baldurs-gate-3` |
| `Elden Ring: Shadow of the Erdtree` | `elden-ring-shadow-of-the-erdtree` |
| `Breaking Bad` | `breaking-bad` |
| `The Godfather` | `the-godfather` |

Derive slug from the page URL: everything between the media-type path and the trailing slash.

```python
import re

def slug_from_url(url):
    # Works for /game/, /movie/, /tv/
    m = re.search(r'/(?:game|movie|tv)/([^/]+)/', url)
    return m.group(1) if m else None

slug_from_url("https://www.metacritic.com/game/the-last-of-us/")  # "the-last-of-us"
```

---

## Anti-bot measures

- **Cloudflare** is in front of both `metacritic.com` and `backend.metacritic.com` (confirmed via `CF-Ray` and `Server: cloudflare` headers).
- **Frontend pages** (`metacritic.com/*`): Require a non-empty User-Agent. `Mozilla/5.0` works. `python-requests/...` or empty UA returns HTTP 403.
- **Backend API** (`backend.metacritic.com`): Same rule — any non-empty User-Agent works, including `curl/7.84.0` and `python-requests/2.31.0`. Only truly empty UA gets 403.
- **Music pages** (`metacritic.com/music/*`): HTTP 403 even with valid User-Agent — Cloudflare blocks that path category. The backend API for music also 404s. Use the browser via CDP for music pages.
- **Cache**: Frontend pages are Cloudflare-cached (10 minute TTL, `Cache-Control: public, max-age=600`). Backend API responses are not cached (`CF-Cache-Status: MISS`).
- **No CAPTCHA** observed during testing with any of the approaches above.
- **No rate limit** hit during testing: 10 sequential calls at 3.6 calls/sec, 10 parallel calls in 0.68s — all succeeded.
- **PerimeterX**: Not detected in response headers or HTML.

---

## Gotchas

- **API key is embedded in every Metacritic page HTML** — find it by searching for `apiKey=` in `backend.metacritic.com` URLs. The key `1MOZgmNFxvmljaQR1X9KAij9Mo4xAY3u` was confirmed active as of 2026-04-18. If it rotates, fetch any Metacritic page and extract it: `re.search(r'apiKey=([A-Za-z0-9]+)', html).group(1)`.

- **userScore is None in search results** — the `/finder/metacritic/search/` endpoint returns `userScore: null` for all results. Call the stats API separately with the slug to get user score + review count.

- **Metascore None means < 4 reviews** — the backend API returns `score: null` (not 0) when a title has fewer than 4 critic reviews. Always check `if score is not None` before using.

- **Multi-platform games: JSON-LD shows lead platform score** — for a game on PS5 and Xbox, `aggregateRating.ratingValue` in JSON-LD is the lead platform's score (the platform marked `isLeadPlatform: True` in the backend API). All platforms are listed in `gamePlatform` but without individual scores. Use the product API's `platforms` array for per-platform breakdown.

- **Music is blocked** — `metacritic.com/music/*` returns HTTP 403 even with a real browser User-Agent. The backend API for albums (`/albums/metacritic/...`) also returns 404. Music data requires a real browser session via CDP.

- **NUXT_DATA pool deref is fragile** — the pool structure is a flat array where every value is either a primitive or an integer index pointing elsewhere in the array. Component locations shift between page loads but the component names (`critic-score-summary`, `user-score-summary`) are stable.

- **`http_get` default UA is `Mozilla/5.0`** — this works for Metacritic. No need to override it.

- **Backend API `componentName` and `componentType` params are required** — omitting them returns HTTP 400. Use the exact values shown in the code examples above.

- **Finder `userScore` format**: In finder/browse results, `userScore` is `{"score": 9.1}` (a dict with just `score`). In the stats API, it's a full object with `reviewCount`, `sentiment`, etc. In search results, it's `null`.

- **Media type URL paths**: games=`/games/`, movies=`/movies/`, TV shows=`/shows/`. There is no `/tv/` path in the backend API (the frontend uses `/tv/` but the API uses `/shows/`).

- **Finder API does not support free-text search** — the `q=` param is silently ignored and returns 0 results. Use the `/finder/metacritic/search/{query}/web` endpoint for title search.
