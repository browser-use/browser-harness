# RAWG — Scraping & Data Extraction

Field-tested against rawg.io on 2026-04-18.
`https://rawg.io` — world's largest video game database with 500K+ games.

---

## API status — key required, no workaround

`https://api.rawg.io/api/` requires a valid API key on every request.
Empty key, dummy key, and header spoofing all return **HTTP 401**. Confirmed:

```
api.rawg.io/api/games?page_size=5          -> 401
api.rawg.io/api/games?page_size=5&key=     -> 401
api.rawg.io/api/games?page_size=5&key=DEMO -> 401
rawg.io/api/games?page_size=5              -> 401
# Referer/Origin headers make no difference
```

Free API keys are available at `https://rawg.io/apidocs` after signing up at
`https://rawg.io/signup` (no credit card, ~1 minute). Free tier: **20,000 requests/month**.
Set the key in `.env` as `RAWG_API_KEY=<your_key>`.

---

## Approach 1 (Fastest, no key): HTML scraping via `window.CLIENT_PARAMS`

The website server-renders all game data into `window.CLIENT_PARAMS` in the page HTML.
One `http_get` call, pure JSON parse, no browser required.
Confirmed working on all tested game pages.

### Single game page

```python
import json
from helpers import http_get

def extract_game(slug):
    """
    Fetch full game data from rawg.io/games/{slug}.
    Handles canonical-slug redirects (e.g. 'disco-elysium-the-final-cut'
    transparently becomes 'disco-elysium-final-cut').
    Returns game dict or None.
    """
    resp = http_get(f"https://rawg.io/games/{slug}")
    idx = resp.find('window.CLIENT_PARAMS = {')
    if idx < 0:
        return None
    chunk = resp[idx + len('window.CLIENT_PARAMS = '):]
    # Extract JSON by counting braces
    depth, end = 0, 0
    for i, c in enumerate(chunk):
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    params = json.loads(chunk[:end])
    initial_state = params['initialState']
    entities = initial_state['entities']
    games = entities.get('games', {})
    # game.slug has 'g-' prefix and reflects the canonical slug after any redirect
    canonical_key = initial_state.get('game', {}).get('slug', '')
    game = games.get(canonical_key)
    if not game:
        game = games.get(f'g-{slug}')
    if not game:
        for g in games.values():
            if isinstance(g, dict) and g.get('slug') == slug:
                return g
    return game

game = extract_game('the-witcher-3-wild-hunt')
# All fields confirmed present:
# game['name']             -> 'The Witcher 3: Wild Hunt'
# game['id']               -> 3328
# game['slug']             -> 'the-witcher-3-wild-hunt'
# game['rating']           -> 4.64          (RAWG community score, 0-5)
# game['rating_top']       -> 5
# game['ratings_count']    -> 7184
# game['metacritic']       -> 92            (None if no score)
# game['released']         -> '2015-05-18'
# game['updated']          -> '2026-04-17T23:18:04'
# game['playtime']         -> 43            (average hours)
# game['website']          -> 'https://thewitcher.com/en/witcher3'
# game['background_image'] -> 'https://media.rawg.io/media/games/618/618c2031a07bbff6b4f611f10b6bcdbc.jpg'
# game['added']            -> 22198         (count of users who added to library)
# game['esrb_rating']      -> {'id': 4, 'name': 'Mature', 'slug': 'mature'}
# game['genres']           -> [{'id': 4, 'name': 'Action', 'slug': 'action'}, ...]
# game['platforms']        -> ['playstation5', 'xbox-series-x', 'pc', ...]  (slugs, cross-ref entities)
# game['parent_platforms'] -> ['pc', 'playstation', 'xbox', 'mac', 'nintendo']
# game['developers']       -> [{'id': 9023, 'name': 'CD PROJEKT RED', 'slug': '...'}]
# game['publishers']       -> [{'id': 7411, 'name': 'CD PROJEKT RED', 'slug': '...'}]
# game['tags']             -> [{'id': 31, 'name': 'Singleplayer', ...}, ...]
# game['description_raw']  -> plain-text description (detail page only)
# game['description']      -> HTML description
# game['ratings']          -> [{'title': 'exceptional', 'percent': 76.53}, ...]
# game['metacritic_platforms'] -> [{'metascore': 93, 'platform': {...}}, ...]
```

### Extract specific fields

```python
def game_summary(slug):
    g = extract_game(slug)
    if not g:
        return None
    return {
        'id':           g['id'],
        'name':         g['name'],
        'slug':         g['slug'],
        'rating':       g['rating'],
        'metacritic':   g['metacritic'],
        'released':     g['released'],
        'playtime_hrs': g['playtime'],
        'website':      g.get('website'),
        'esrb':         (g.get('esrb_rating') or {}).get('name'),
        'genres':       [ge['name'] for ge in g.get('genres', []) if isinstance(ge, dict)],
        'platforms':    g.get('parent_platforms', []),
        'developers':   [d['name'] for d in g.get('developers', []) if isinstance(d, dict)],
        'publishers':   [p['name'] for p in g.get('publishers', []) if isinstance(p, dict)],
        'tags':         [t['name'] for t in g.get('tags', []) if isinstance(t, dict)][:10],
        'image':        g.get('background_image'),
    }

# Confirmed results:
print(game_summary('red-dead-redemption-2'))
# {'id': 28, 'name': 'Red Dead Redemption 2', 'rating': 4.59, 'metacritic': 96,
#  'released': '2018-10-26', 'playtime_hrs': 21,
#  'esrb': 'Mature',
#  'genres': ['Action'],
#  'platforms': ['pc', 'playstation', 'xbox'],
#  'developers': ['Rockstar Games'], 'publishers': ['Rockstar Games'],
#  'tags': ['Singleplayer', 'Multiplayer', 'Atmospheric', 'Great Soundtrack', 'Co-op', ...]}
```

### Top 40 games from the listing page

The listing page always returns the same ~40 popular games regardless of URL params
(ordering/search/genres params are client-side only — the server returns the same SSR payload).

```python
def top_games():
    """Returns list of 40 game dicts from rawg.io/games listing page."""
    resp = http_get("https://rawg.io/games")
    idx = resp.find('window.CLIENT_PARAMS = {')
    if idx < 0:
        return []
    chunk = resp[idx + len('window.CLIENT_PARAMS = '):]
    depth, end = 0, 0
    for i, c in enumerate(chunk):
        if c == '{': depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    params = json.loads(chunk[:end])
    return list(params['initialState']['entities'].get('games', {}).values())

games = top_games()
# 40 games, each with: id, slug, name, released, rating, rating_top, ratings_count,
# metacritic, playtime, added, genres (full objects), parent_platforms (slugs),
# platforms (slugs), tags (full objects), esrb_rating, background_image, short_screenshots
# NOTE: listing omits description, website, developers, publishers vs detail pages

for g in games[:5]:
    print(f"{g['name']} | rating={g['rating']} | metacritic={g['metacritic']}")
# Grand Theft Auto V | rating=4.47 | metacritic=92
# The Witcher 3: Wild Hunt | rating=4.64 | metacritic=92
# Portal 2 | rating=4.58 | metacritic=95
# Counter-Strike: Global Offensive | rating=3.57 | metacritic=81
# Tomb Raider (2013) | rating=4.06 | metacritic=86
```

### Bulk / concurrent fetching

```python
from concurrent.futures import ThreadPoolExecutor

slugs = ['portal-2', 'dark-souls-iii', 'minecraft', 'hades', 'celeste']
with ThreadPoolExecutor(max_workers=3) as ex:
    results = list(ex.map(extract_game, slugs))
# Tested: 4 games in ~2.8s at max_workers=4
# Occasional timeout at high concurrency — keep max_workers<=3 to stay reliable
```

---

## Approach 2: REST API (requires free key)

All endpoints live at `https://api.rawg.io/api/`. Append `&key=YOUR_API_KEY` to every request.

### Get a free key

1. Sign up at `https://rawg.io/signup`
2. Visit `https://rawg.io/apidocs` — click "Get API key"
3. The key is a 40-char hex string
4. Store as `RAWG_API_KEY` in `.env`

### Games list / search

```python
import json, os
from helpers import http_get

KEY = os.environ['RAWG_API_KEY']

# Search
results = json.loads(http_get(
    f"https://api.rawg.io/api/games?search=witcher&page_size=5&key={KEY}"
))
# results['count']   -> total matching games
# results['next']    -> next page URL (pagination)
# results['results'] -> list of game objects

# Top-rated
top = json.loads(http_get(
    f"https://api.rawg.io/api/games?ordering=-metacritic&page_size=10&key={KEY}"
))

# By date range
recent = json.loads(http_get(
    f"https://api.rawg.io/api/games?dates=2024-01-01,2024-12-31&ordering=-added&page_size=20&key={KEY}"
))

# By platform (PC=4, PS4=18, Xbox One=1, Switch=7)
pc_games = json.loads(http_get(
    f"https://api.rawg.io/api/games?platforms=4&ordering=-rating&page_size=10&key={KEY}"
))
```

### Game detail

```python
# By ID (faster if you have it)
game = json.loads(http_get(f"https://api.rawg.io/api/games/3328?key={KEY}"))
# game['name'], game['rating'], game['metacritic'], game['description_raw'], ...

# By slug
game = json.loads(http_get(
    f"https://api.rawg.io/api/games/the-witcher-3-wild-hunt?key={KEY}"
))
```

### API response fields (same as HTML scraping)

```
id, slug, name, released, tba, background_image,
rating (0-5 RAWG community), rating_top, ratings, ratings_count,
metacritic, playtime, added, added_by_status,
platforms (list of {platform:{id,name,slug}, released_at}),
parent_platforms (list of {platform:{id,name,slug}}),
genres (list of {id,name,slug}),
tags (list of {id,name,slug,language,games_count}),
developers (list of {id,name,slug}),
publishers (list of {id,name,slug}),
stores (list of {id,store:{id,name,slug}}),
esrb_rating ({id,name,slug}),
website, description_raw, description, screenshots_count,
movies_count, creators_count, achievements_count,
metacritic_url, metacritic_platforms
```

### Platforms and Genres lists

```python
# All platforms
platforms = json.loads(http_get(f"https://api.rawg.io/api/platforms?key={KEY}"))
# results: [{id, name, slug, games_count, year_start, year_end, ...}]

# Parent platforms only
parents = json.loads(http_get(f"https://api.rawg.io/api/platforms/lists/parents?key={KEY}"))

# Genres
genres = json.loads(http_get(f"https://api.rawg.io/api/genres?key={KEY}"))
# results: [{id, name, slug, games_count, image_background}]
```

### Pagination

```python
def get_all_pages(url_template, max_pages=5):
    """Paginate through API results."""
    results = []
    url = url_template + "&page=1"
    for _ in range(max_pages):
        data = json.loads(http_get(url))
        results.extend(data.get('results', []))
        if not data.get('next'):
            break
        url = data['next']
    return results
```

---

## Gotchas

- **API is fully blocked without a key** — `401` for every endpoint, including empty key and
  `rawg.io/api/` (non-`api.rawg.io` subdomain). No auth bypass exists.

- **URL params are client-side on listing pages** — `rawg.io/games?ordering=-rating` and
  `rawg.io/games?search=witcher` return identical 40-game SSR payloads. Params only affect
  the React client after hydration. Use the API for real filtering, or scrape individual game
  pages by slug.

- **Slug canonical redirects** — Some slugs redirect internally:
  `disco-elysium-the-final-cut` → `disco-elysium-final-cut`. The URL you fetch returns HTTP 200
  but the routing state inside `CLIENT_PARAMS` reflects the canonical path. Always use
  `initial_state['game']['slug']` as the lookup key (it already has the `g-` prefix),
  not a constructed `'g-' + url_slug`.

- **`g-` prefix on entity keys** — Game entities in `CLIENT_PARAMS.initialState.entities.games`
  are keyed as `g-{slug}` (e.g. `g-the-witcher-3-wild-hunt`), not bare slugs.
  The game state slug field also carries this prefix: `{'slug': 'g-the-witcher-3-wild-hunt'}`.

- **Listing page gives 40 games, detail pages give full fields** — `description`, `website`,
  `developers`, `publishers` are absent from the listing page payload. Only present on
  individual game pages.

- **Concurrent requests: keep max_workers ≤ 3** — At `max_workers=5` with 10 requests,
  some pages timed out (20s default) or returned 502. Sequential or 3-worker parallel is
  reliable. A brief `time.sleep(0.5)` between sequential requests avoids 502 spikes.

- **`platforms` field in game entities uses slugs, `platform_entities` has full objects** —
  In the HTML payload, `game['platforms']` is a list of slug strings
  (`['playstation5', 'pc', ...]`). Full platform details live in
  `entities.platforms[slug]` as `{'platform': {id, name, slug, ...}, 'released_at': '...'}`.
  `game['parent_platforms']` is also a list of slug strings (`['pc', 'playstation', ...]`).

- **`metacritic` is `None` for games without a score** — Always check `if game['metacritic']`
  before using. Many indie/older games have no Metacritic score.

- **`esrb_rating` is `None` for non-US-rated games** — Common for Japanese games and
  anything outside the ESRB's jurisdiction.

- **`god-of-war` slug resolves to God of War I (PS2, 2005)** — The PS4 2018 title uses
  `god-of-war-4` or has its own entity key. Always verify the game name in the response.

- **Free API tier: 20,000 requests/month** — Roughly 650/day. Listing endpoint returns
  20 results per page by default (max `page_size=40`). For bulk data collection, the HTML
  scraping approach has no documented rate limit but times out under heavy parallel load.

- **`description_raw` vs `description`** — `description` is HTML with escaped unicode
  (`\u003C` = `<`). `description_raw` is plain text, easier to work with. Both present
  on detail pages only.

- **`updated` field reflects last RAWG edit, not release date** — Use `released` for
  the release date. `updated` changes frequently as the community edits entries.
