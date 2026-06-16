# itch.io — Scraping & Data Extraction

Field-tested against itch.io on 2026-04-18. All code blocks validated with live requests.

---

## TL;DR — fastest approaches by task

| Task | Method | Notes |
|---|---|---|
| Browse listings (36/page) | `http_get` HTML | Works, no key, no bot block |
| Game detail (name, price, rating) | `http_get` + JSON-LD | `<script type="application/ld+json">` Product block |
| Info table (tags, genre, status) | `http_get` + regex on `game_info_panel_widget` | Always present |
| Top N games from any category | RSS `.xml` feed | Cleaner than HTML for bulk |
| API (key endpoints) | `http_get` + key in path | Free keys at itch.io/docs/api |
| Download/purchase counts | Not public | Owners only via dashboard |

`http_get` works on all itch.io game and browse pages with no extra headers needed.
No Cloudflare, no JS challenge, no CAPTCHA on standard game/browse routes.

---

## Approach 1 (Fastest for listings): RSS feeds — 36 games per call, clean XML

Every browse URL has an `.xml` RSS variant. Returns price, pub/update dates, platforms, thumbnail. No HTML parsing.

```python
import re
from helpers import http_get

def parse_rss(url):
    """
    Parse any itch.io RSS listing feed.
    url examples:
      https://itch.io/games/top-rated.xml
      https://itch.io/games/newest.xml
      https://itch.io/games/featured.xml
      https://itch.io/games/on-sale.xml
      https://itch.io/games/free.xml
      https://itch.io/games/tag-puzzle.xml    # any tag slug works
      https://itch.io/games/top-rated.xml?page=2
    """
    xml = http_get(url)
    items = []
    for m in re.finditer(r'<item>(.*?)</item>', xml, re.DOTALL):
        ix = m.group(1)
        def get(tag, s=ix):
            tm = re.search(rf'<{tag}>(.*?)</{tag}>', s, re.DOTALL)
            return tm.group(1).strip() if tm else None
        items.append({
            'url':         get('guid'),
            'title':       get('plainTitle'),          # clean title, no [tags]
            'price':       get('price'),               # "$0.00", "$7.99", etc.
            'currency':    get('currency'),            # "USD"
            'pub_date':    get('pubDate'),
            'update_date': get('updateDate'),
            'image':       get('imageurl'),            # 315x250 thumbnail
            'platforms': {
                k: get(k) == 'yes'
                for k in ['windows', 'osx', 'linux', 'android', 'html']
                if get(k) is not None
            },
        })
    return items

# Confirmed output:
items = parse_rss("https://itch.io/games/top-rated.xml")
# items[0] -> {
#   'url':         'https://gbpatch.itch.io/our-life',
#   'title':       'Our Life: Beginnings & Always',
#   'price':       '$0.00',
#   'currency':    'USD',
#   'pub_date':    'Fri, 07 Jun 2019 23:47:57 GMT',
#   'update_date': 'Sun, 22 May 2022 15:48:27 GMT',
#   'image':       'https://img.itch.zone/aW1nLzcwMTIxNDMucG5n/315x250%23c/BalGQb.png',
#   'platforms':   {'windows': True, 'osx': True, 'linux': True, 'android': True},
# }
```

**RSS limitations:** no rating score or count. Use HTML scraping (Approach 2) when you need ratings.

---

## Approach 2: HTML listings — ratings, genre, price, 36 games per page

```python
import re
from helpers import http_get

def parse_game_cards(html):
    """
    Extract all game cards from any itch.io browse/listing/search/profile HTML page.
    Works on:
      https://itch.io/games/top-rated
      https://itch.io/games/newest
      https://itch.io/games/featured
      https://itch.io/games/on-sale
      https://itch.io/games/free
      https://itch.io/games/tag-puzzle      (genre/tag path)
      https://itch.io/search?q=platformer   (search — 54 cards per page)
      https://<author>.itch.io              (author profile)
    All accept ?page=N for pagination.
    """
    games = []
    for m in re.finditer(r'data-game_id="(\d+)"', html):
        game_id = m.group(1)
        start = m.start()
        chunk = html[start:start + 3000]

        # Title + URL — attribute order differs between page 1 and pages 2+
        title_m = re.search(
            r'class="title game_link"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>', chunk
        )
        if not title_m:
            title_m = re.search(
                r'href="([^"]+)"[^>]*class="title game_link"[^>]*>([^<]+)</a>', chunk
            )

        rating_m  = re.search(
            r'data-tooltip="([\d.]+) average rating from ([\d,]+) total ratings"', chunk
        )
        genre_m   = re.search(r'class="game_genre">([^<]+)</div>', chunk)
        price_m   = re.search(r'class="price_value">([^<]+)</div>', chunk)
        desc_m    = re.search(r'class="game_text" title="([^"]+)"', chunk)
        img_m     = re.search(r'data-lazy_src="([^"]+)"', chunk)
        platforms = re.findall(r'title="Download for ([^"]+)"', chunk)

        games.append({
            'id':           game_id,
            'url':          title_m.group(1) if title_m else None,
            'title':        title_m.group(2).strip() if title_m else None,
            'rating':       float(rating_m.group(1)) if rating_m else None,
            'rating_count': int(rating_m.group(2).replace(',', '')) if rating_m else None,
            'genre':        genre_m.group(1) if genre_m else None,
            'price':        price_m.group(1) if price_m else 'Free',
            'description':  desc_m.group(1) if desc_m else None,
            'thumbnail':    img_m.group(1) if img_m else None,
            'platforms':    platforms,      # ['Windows', 'macOS', 'Linux', 'Android']
        })
    return games

# Usage:
html = http_get("https://itch.io/games/top-rated")
games = parse_game_cards(html)
# games[0] -> {
#   'id': '434554', 'url': 'https://gbpatch.itch.io/our-life',
#   'title': 'Our Life: Beginnings & Always',
#   'rating': 4.94, 'rating_count': 7191,
#   'genre': 'Visual Novel', 'price': 'Free',
#   'platforms': ['Windows', 'Linux', 'macOS', 'Android'],
# }

# Paid game example:
html = http_get("https://itch.io/games/top-rated?page=5")
games = parse_game_cards(html)
# Returns games where price_m captures '$7.99' when present
```

### CSS selector reference (for browser/JS use)

```
.game_cell                        — one card per game
.game_cell[data-game_id]          — get game ID from attribute
.game_cell .title.game_link       — title text + href
.game_cell .game_rating           — rating container
.game_cell .game_rating[data-tooltip]  — "4.94 average rating from 7,191 total ratings"
.game_cell .star_fill             — inline style width: NN% (rating as percentage of 5)
.game_cell .rating_count          — "(7,191)"
.game_cell .game_genre            — genre text
.game_cell .price_tag .price_value — price e.g. "$7.99" (absent = Free)
.game_cell .game_text             — one-line description (also in title attr)
.game_cell .game_author a         — author name + href
.game_cell img.lazy_loaded        — thumbnail (src in data-lazy_src before JS runs)
```

**Gotcha — attribute order flips on page >= 2.** Page 1 uses `class="..." data-game_id="..."`, page 2+ uses `data-game_id="..." class="..."`. The regex above handles both. If you use a CSS selector engine, `[data-game_id]` is unambiguous.

**Gotcha — ratings absent on some listing types.** The tag/genre browse pages (e.g. `/games/tag-puzzle`) sometimes omit the rating tooltip on the card even when the game has ratings. Fetch the detail page for the authoritative rating.

---

## Approach 3: Game detail page — JSON-LD Product schema

The cleanest source for individual game data. All confirmed fields:

```python
import json, re
from helpers import http_get

def extract_game_detail(url):
    """
    Fetch full metadata for a single itch.io game.
    url format: https://<author>.itch.io/<game-slug>
    """
    html = http_get(url)

    # --- JSON-LD (always present, covers name/description/price/rating) ---
    ld_product = None
    for block in re.findall(
        r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        html, re.DOTALL
    ):
        ld = json.loads(block.strip())
        if ld.get('@type') == 'Product':
            ld_product = ld
            break

    # --- Info panel table (Status, Platforms, Genre, Tags, Author, etc.) ---
    info = {}
    panel_m = re.search(
        r'class="game_info_panel_widget[^"]*"[^>]*><table>(.*?)</table>',
        html, re.DOTALL
    )
    if panel_m:
        for row in re.finditer(
            r'<tr><td>([^<]+)</td><td>(.*?)</td></tr>',
            panel_m.group(1), re.DOTALL
        ):
            key = row.group(1).strip()
            val = re.sub(r'<[^>]+>', '', row.group(2)).strip()
            # Multi-value fields become lists (Tags, Platforms, Genre, Links)
            info[key] = [v.strip() for v in val.split(',')] if ',' in val else val

    # --- Cover image ---
    cover_m = re.search(r'<meta property="og:image" content="([^"]+)"', html)

    offers = (ld_product or {}).get('offers', {})
    agg    = (ld_product or {}).get('aggregateRating', {})

    return {
        'url':          url,
        'name':         (ld_product or {}).get('name'),
        'description':  (ld_product or {}).get('description'),
        'price':        offers.get('price'),          # "0.00" for free, "7.99" for paid
        'currency':     offers.get('priceCurrency'),  # "USD"
        'rating':       agg.get('ratingValue'),       # "4.9" string
        'rating_count': agg.get('ratingCount'),       # int
        'cover':        cover_m.group(1) if cover_m else None,
        'info':         info,
    }

# Free game:
r = extract_game_detail("https://gbpatch.itch.io/our-life")
# {
#   'name': 'Our Life: Beginnings & Always',
#   'description': 'Grow from childhood to adulthood with the lonely boy next door...',
#   'price': None, 'currency': None,   <- no 'offers' block for free games
#   'rating': '4.9', 'rating_count': 7191,
#   'cover': 'https://img.itch.zone/aW1hZ2Uv.../347x500/7HqrvV.jpg',
#   'info': {
#     'Status':    'Released',
#     'Platforms': ['Windows', 'macOS', 'Linux', 'Android'],
#     'Rating':    'Rated 4.9 out of 5 stars(7,191 total ratings)',
#     'Author':    'GBPatch',
#     'Genre':     ['Visual Novel', 'Interactive Fiction'],
#     'Tags':      ['Amare', 'Comedy', 'Dating Sim', 'Gay', 'LGBT', ...],
#     'Links':     'Steam',
#   }
# }

# Paid game:
r = extract_game_detail("https://adamgryu.itch.io/a-short-hike")
# {
#   'name': 'A Short Hike',
#   'price': '7.99', 'currency': 'USD',
#   'rating': '4.9', 'rating_count': 4307,
#   'info': {
#     'Status':          'Released',
#     'Platforms':       ['Windows', 'macOS', 'Linux'],
#     'Release date':    'Jul 30, 2019',
#     'Genre':           ['Adventure', 'Platformer'],
#     'Made with':       'Unity',
#     'Tags':            ['3D', 'Atmospheric', 'Cute', 'Relaxing', 'Short', ...],
#     'Average session': 'About an hour',
#     'Languages':       ['English', 'Spanish; Latin America', 'French', ...],
#     'Inputs':          ['Keyboard', 'Mouse', 'Xbox controller', ...],
#     'Accessibility':   ['Subtitles', 'Configurable controls'],
#     'Links':           ['Steam', 'Homepage', 'Soundtrack', 'Twitter/X'],
#   }
# }
```

**JSON-LD available fields:**

| Field | Free game | Paid game |
|---|---|---|
| `@type` | `Product` | `Product` |
| `name` | yes | yes |
| `description` | yes | yes |
| `aggregateRating.ratingValue` | yes | yes |
| `aggregateRating.ratingCount` | yes | yes |
| `offers.price` | absent | yes ("7.99") |
| `offers.priceCurrency` | absent | yes ("USD") |
| `offers.seller.name` | absent | yes (author name) |
| `offers.seller.url` | absent | yes (author profile URL) |

---

## Pagination

Browse pages: `?page=N`. Detect end of results by HTTP 404 (page too high) or absent `<link rel="next">`.

```python
import re
from helpers import http_get

def paginate_listing(base_url, max_pages=10):
    """
    Scrape multiple pages from any itch.io browse URL.
    base_url: https://itch.io/games/top-rated  (no ?page= suffix)
    Returns flat list of game dicts.
    Stops when HTTP 404 or no <link rel="next"> found.
    """
    all_games = []
    page = 1
    while page <= max_pages:
        url = base_url if page == 1 else f"{base_url}?page={page}"
        try:
            html = http_get(url)
        except Exception:
            break   # 404 = past last page
        all_games.extend(parse_game_cards(html))
        if not re.search(r'<link[^>]+rel="next"[^>]*/>', html):
            break
        page += 1
    return all_games

# Confirmed: page 1 has <link href="?page=2" rel="next"/>
#            page 2 has <link rel="prev" href="/games/top-rated"/> and <link rel="next" href="?page=3"/>
#            past last page returns HTTP 404
# top-rated has at least 200 pages (each 36 games); page 300+ -> 404
```

---

## Browse URL patterns

All confirmed working via `http_get`:

```python
BASE = "https://itch.io/games"

# Sort orders
f"{BASE}/top-rated"      # all-time top rated (rated by community, 0–5 stars)
f"{BASE}/newest"         # most recently published
f"{BASE}/featured"       # itch.io staff picks
f"{BASE}/on-sale"        # discounted games
f"{BASE}/free"           # free games only

# Genre/tag paths (append .xml for RSS)
f"{BASE}/tag-puzzle"     # tag slug — prefix with 'tag-'
f"{BASE}/genre-action"   # genre — prefix with 'genre-' (less common)

# Combine: tag + sort via separate pages (no combined URL that survives http_get)
# Note: https://itch.io/games/top-rated/tag-puzzle -> HTTP 403
# Note: ?tag= query param does NOT filter server-side (returns same games)

# Pagination
f"{BASE}/top-rated?page=2"
f"{BASE}/tag-puzzle?page=3"

# RSS equivalents (36 items, no pagination needed for small sets)
f"{BASE}/top-rated.xml"
f"{BASE}/tag-puzzle.xml"
f"{BASE}/tag-puzzle.xml?page=2"

# Search (54 results/page, no server-side pagination beyond page 1 via http_get)
"https://itch.io/search?q=platformer"

# Author profile
"https://<author-slug>.itch.io"
```

---

## API (requires key)

itch.io has an official REST API. A free key is issued per-account with no rate limit published.
Get one at: `https://itch.io/user/settings/api-keys`

Base URL: `https://itch.io/api/1/<key>/`

```python
import json
from helpers import http_get

ITCH_KEY = "your_api_key_here"   # from https://itch.io/user/settings/api-keys

def api(path):
    return json.loads(http_get(f"https://itch.io/api/1/{ITCH_KEY}/{path}"))

# Authenticated user info
api("me")
# -> {"user": {"id": ..., "username": "...", "url": "...", "display_name": "...", ...}}

# Games owned by authenticated user
api("my-games")
# -> {"games": [{"id": ..., "title": "...", "url": "...", "created_at": "...",
#                "published": true/false, "min_price": 0, ...}, ...]}

# Download keys for a game (owner only)
api("game/434554/download_keys")

# Credentials (for authenticated purchases)
api("game/434554/credentials")
```

**Error structure:** invalid/missing key returns `{"errors": ["invalid key"]}` with HTTP 200.
Non-existent endpoints return HTTP 404.

**No unauthenticated game lookup API.** `https://itch.io/api/1/x/games` -> HTTP 404.
Use HTML scraping or RSS for unauthenticated game data.

---

## Gotchas

1. **Attribute order flips page 1 vs 2+.** On page 1, game cards use `class="game_cell ..." data-game_id="..."`. On pages 2+, the order is `data-game_id="..." class="game_cell ..."`. Always match `data-game_id` independently of class ordering.

2. **Ratings absent on tag/genre listing pages.** The `data-tooltip` with rating is often missing from card HTML on `/games/tag-*` pages even though the game has ratings. Fetch the detail page for `aggregateRating` via JSON-LD.

3. **`price_value` absent = Free.** Paid games have `<div class="price_tag meta_tag" title="Pay $7.99 or more..."><div class="price_value">$7.99</div></div>`. Free games have no such element. Default to `'Free'` when absent.

4. **Free-game JSON-LD has no `offers` block.** Only paid games include the `offers` object. For free games, use absence of `offers` as the signal, not presence of `price: 0`.

5. **`/games/top-rated/tag-puzzle` returns HTTP 403.** Cannot combine sort + tag in a path. Use separate `/games/tag-puzzle` (top-rated is the default sort anyway).

6. **`?tag=` query param is ignored server-side.** `https://itch.io/games/top-rated?tag=puzzle` returns the same games as `?top-rated`. Use `/games/tag-puzzle` path instead.

7. **Download/purchase counts are not public.** No count field appears anywhere in the public HTML, JSON-LD, RSS, or unauthenticated API. Game owners see their stats in the dashboard only.

8. **Search beyond page 1 is AJAX-only.** `https://itch.io/search?q=X&page=2` via `http_get` returns the same 54 results as page 1. To get more search results use the browser and scroll/click "load more".

9. **RSS is capped at 36 items per page.** Paginate with `?page=N`. Very high page numbers (300+) return HTTP 404 on browse pages.

10. **Unicode zero-width space in some titles.** `\u200b` (zero-width space) appears at the start of certain titles (e.g. "​Our Life: Beginnings & Always"). Strip with `.replace('\u200b', '').strip()` or `.strip()` alone won't remove it — use `title.replace('\u200b', '').strip()`.
