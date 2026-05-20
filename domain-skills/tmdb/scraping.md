# TMDB — Data Extraction

`https://api.themoviedb.org/3` — The Movie Database REST API. **Requires a free API key** on every request. No bypass exists.

---

## API key setup

Free keys are available at `https://www.themoviedb.org/settings/api` after signing up (no credit card).
Store as `TMDB_API_KEY` in `.env`.

```python
import os, json
KEY = os.environ.get('TMDB_API_KEY')
if not KEY:
    raise RuntimeError("Set TMDB_API_KEY in .env — get one free at https://www.themoviedb.org/settings/api")
```

All examples below assume `KEY` is set. Append `&api_key={KEY}` to every v3 URL.

---

## Approach: Direct REST API with `http_get`

Pure JSON — no browser, no HTML parsing. All responses are structured dicts.

### Movie search (simplest entry point)

```python
import json, os
from helpers import http_get

KEY = os.environ['TMDB_API_KEY']

results = json.loads(http_get(
    f"https://api.themoviedb.org/3/search/movie?query=inception&api_key={KEY}"
))
# results['total_results']  -> 14
# results['total_pages']    -> 1
# results['page']           -> 1
# results['results']        -> list of movie objects

for m in results['results'][:3]:
    print(f"{m['title']} ({m['release_date'][:4]}) id={m['id']} rating={m['vote_average']}")
# Inception (2010) id=27205 rating=8.369
```

Movie object fields in search results:
`id`, `title`, `original_title`, `overview`, `release_date` (YYYY-MM-DD),
`vote_average` (0–10), `vote_count`, `popularity`, `poster_path`, `backdrop_path`,
`genre_ids` (list of ints), `adult`, `video`, `original_language`

### Movie details (full metadata by ID)

```python
# Inception = id 27205
movie = json.loads(http_get(
    f"https://api.themoviedb.org/3/movie/27205?api_key={KEY}"
))
print(movie['title'])           # Inception
print(movie['runtime'])         # 148  (minutes)
print(movie['revenue'])         # 825532764
print(movie['budget'])          # 160000000
print(movie['status'])          # Released
print(movie['tagline'])         # Your mind is the scene of the crime.
print(movie['imdb_id'])         # tt1375666
print(movie['homepage'])        # https://www.warnerbros.com/movies/inception

# Genres (full objects, not just IDs):
print([g['name'] for g in movie['genres']])
# ['Action', 'Science Fiction', 'Adventure']

# Production companies:
print([c['name'] for c in movie['production_companies']])
# ['Legendary Pictures', 'Syncopy', 'Warner Bros. Pictures']

# Spoken languages:
print([l['english_name'] for l in movie['spoken_languages']])
# ['English', 'French', 'Japanese', 'Swahili']
```

Extra fields in detail (vs search): `runtime`, `budget`, `revenue`, `status`, `tagline`,
`imdb_id`, `homepage`, `genres` (full objects), `production_companies`, `production_countries`,
`spoken_languages`, `belongs_to_collection`

### Append `append_to_response` for credits, videos, keywords in one call

```python
# Fetch movie + credits + videos in a single API call
movie = json.loads(http_get(
    f"https://api.themoviedb.org/3/movie/27205"
    f"?api_key={KEY}&append_to_response=credits,videos,keywords,release_dates"
))

# Credits
cast = movie['credits']['cast'][:5]
for actor in cast:
    print(f"{actor['name']} as {actor['character']} (order={actor['order']})")
# Leonardo DiCaprio as Cobb (order=0)
# Joseph Gordon-Levitt as Arthur (order=1)

crew = [p for p in movie['credits']['crew'] if p['job'] == 'Director']
print(crew[0]['name'])  # Christopher Nolan

# Trailers
trailers = [v for v in movie['videos']['results'] if v['type'] == 'Trailer' and v['site'] == 'YouTube']
print(f"https://www.youtube.com/watch?v={trailers[0]['key']}")

# Keywords
print([k['name'] for k in movie['keywords']['keywords'][:5]])
# ['dream', 'spy', 'paris', 'subconscious', 'theft']
```

### Popular movies

```python
popular = json.loads(http_get(
    f"https://api.themoviedb.org/3/movie/popular?api_key={KEY}&page=1"
))
# popular['results'] -> 20 movies per page, sorted by TMDB popularity score
# popular['total_pages'] -> total pages available

for m in popular['results'][:5]:
    print(f"#{popular['results'].index(m)+1} {m['title']} popularity={m['popularity']:.1f}")
```

Other list endpoints (same shape, 20 results/page):
- `/movie/top_rated` — highest `vote_average` with enough votes
- `/movie/now_playing` — currently in theaters (includes `dates.minimum`/`dates.maximum`)
- `/movie/upcoming` — releasing soon

### TV search

```python
results = json.loads(http_get(
    f"https://api.themoviedb.org/3/search/tv?query=breaking+bad&api_key={KEY}"
))
show = results['results'][0]
print(show['name'], show['id'], show['first_air_date'])
# Breaking Bad 1396 2008-01-20

# TV detail by ID
tv = json.loads(http_get(f"https://api.themoviedb.org/3/tv/1396?api_key={KEY}"))
print(tv['number_of_seasons'])   # 5
print(tv['number_of_episodes'])  # 62
print(tv['status'])              # Ended
print(tv['networks'][0]['name']) # AMC

# Season detail
s1 = json.loads(http_get(f"https://api.themoviedb.org/3/tv/1396/season/1?api_key={KEY}"))
print(len(s1['episodes']))           # 7
print(s1['episodes'][0]['name'])     # Pilot
print(s1['episodes'][0]['runtime'])  # 58
```

TV show fields: `id`, `name`, `original_name`, `overview`, `first_air_date`, `last_air_date`,
`status`, `type`, `vote_average`, `vote_count`, `popularity`, `number_of_seasons`,
`number_of_episodes`, `episode_run_time`, `networks`, `genres`, `created_by`, `languages`,
`origin_country`, `poster_path`, `backdrop_path`, `in_production`, `seasons`

### Person / actor lookup

```python
# Search by name
results = json.loads(http_get(
    f"https://api.themoviedb.org/3/search/person?query=christopher+nolan&api_key={KEY}"
))
person = results['results'][0]
print(person['id'], person['name'], person['known_for_department'])
# 525 Christopher Nolan Directing

# Person detail
p = json.loads(http_get(f"https://api.themoviedb.org/3/person/525?api_key={KEY}"))
print(p['birthday'])      # 1970-07-30
print(p['place_of_birth']) # Westminster, London, England, UK
print(p['biography'][:120])

# Combined credits (movies + TV)
credits = json.loads(http_get(
    f"https://api.themoviedb.org/3/person/525/combined_credits?api_key={KEY}"
))
# credits['cast']  -> roles they acted in
# credits['crew']  -> roles they directed/wrote/produced
directed = [c for c in credits['crew'] if c['job'] == 'Director']
for d in sorted(directed, key=lambda x: x.get('release_date',''), reverse=True)[:5]:
    title = d.get('title') or d.get('name')
    print(f"{title} ({d.get('release_date','')[:4]})")
# Oppenheimer (2023), Tenet (2020), Dunkirk (2017), Interstellar (2014), The Dark Knight Rises (2012)
```

### Configuration — image base URLs

Call this once and cache. Needed to build full image URLs.

```python
config = json.loads(http_get(
    f"https://api.themoviedb.org/3/configuration?api_key={KEY}"
))
img = config['images']
base_url    = img['secure_base_url']   # 'https://image.tmdb.org/t/p/'
poster_sizes = img['poster_sizes']     # ['w92','w154','w185','w342','w500','w780','original']
backdrop_sizes = img['backdrop_sizes'] # ['w300','w780','w1280','original']
profile_sizes = img['profile_sizes']   # ['w45','w185','h632','original']
```

### Image URL construction

```python
def poster_url(poster_path, size='w500'):
    """Build full poster URL from TMDB poster_path field."""
    if not poster_path:
        return None
    return f"https://image.tmdb.org/t/p/{size}{poster_path}"

def backdrop_url(backdrop_path, size='w1280'):
    if not backdrop_path:
        return None
    return f"https://image.tmdb.org/t/p/{size}{backdrop_path}"

# Usage
movie = json.loads(http_get(f"https://api.themoviedb.org/3/movie/27205?api_key={KEY}"))
print(poster_url(movie['poster_path']))
# https://image.tmdb.org/t/p/w500/ljsZTbVsrQSqZgWeep2B1QiDKuh.jpg
print(backdrop_url(movie['backdrop_path'], size='w1280'))
# https://image.tmdb.org/t/p/w1280/s3TBrRGB1iav7gFOCNx3H31MoES.jpg
```

Size options by type:
- **Poster**: `w92`, `w154`, `w185`, `w342`, `w500`, `w780`, `original`
- **Backdrop**: `w300`, `w780`, `w1280`, `original`
- **Profile**: `w45`, `w185`, `h632`, `original`
- **Logo**: `w45`, `w92`, `w154`, `w185`, `w300`, `w500`, `original`

### Genre list (ID → name mapping)

```python
genres = json.loads(http_get(
    f"https://api.themoviedb.org/3/genre/movie/list?api_key={KEY}"
))
genre_map = {g['id']: g['name'] for g in genres['genres']}
# {28: 'Action', 12: 'Adventure', 16: 'Animation', 35: 'Comedy', ...}

# For TV genres:
tv_genres = json.loads(http_get(
    f"https://api.themoviedb.org/3/genre/tv/list?api_key={KEY}"
))
```

### Discover — filtered listing

```python
# Top-rated sci-fi movies from 2020+
discover = json.loads(http_get(
    f"https://api.themoviedb.org/3/discover/movie"
    f"?api_key={KEY}"
    f"&with_genres=878"          # 878 = Science Fiction
    f"&primary_release_date.gte=2020-01-01"
    f"&sort_by=vote_average.desc"
    f"&vote_count.gte=200"       # require enough votes for meaningful average
    f"&page=1"
))
for m in discover['results'][:5]:
    print(f"{m['title']} ({m['release_date'][:4]}) {m['vote_average']:.1f}")
```

`sort_by` options: `popularity.desc`, `popularity.asc`, `release_date.desc`,
`release_date.asc`, `vote_average.desc`, `vote_average.asc`, `revenue.desc`, `revenue.asc`

### Bulk / concurrent fetching

```python
from concurrent.futures import ThreadPoolExecutor

movie_ids = [27205, 157336, 49026, 155, 372058]  # Inception, Interstellar, TDKR, Batman Begins, Your Name

def fetch_movie(mid):
    try:
        return json.loads(http_get(
            f"https://api.themoviedb.org/3/movie/{mid}"
            f"?api_key={KEY}&append_to_response=credits"
        ))
    except Exception as e:
        return {'id': mid, 'error': str(e)}

with ThreadPoolExecutor(max_workers=5) as ex:
    movies = list(ex.map(fetch_movie, movie_ids))
# ~5 movies in ~1.5s at max_workers=5 — reliable at this concurrency
```

### Pagination

```python
def get_all_popular(max_pages=5):
    movies = []
    for page in range(1, max_pages + 1):
        data = json.loads(http_get(
            f"https://api.themoviedb.org/3/movie/popular?api_key={KEY}&page={page}"
        ))
        movies.extend(data['results'])
        if page >= data['total_pages']:
            break
    return movies
# 20 movies per page; max page=500 per TMDB docs
```

---

## Gotchas

- **API key required on every request** — HTTP 401 without it. Even `?api_key=` (empty) returns 401. Free keys don't expire and have no stated rate limit for read operations, but TMDB asks for fair use (<50 calls/sec).

- **`poster_path` and `backdrop_path` can be `None`** — Common for obscure titles, older films, or recently added entries. Always guard: `poster_url(m['poster_path']) if m['poster_path'] else None`.

- **Image paths start with `/`** — `poster_path` is `'/ljsZTbVsrQSqZgWeep2B1QiDKuh.jpg'`. The base URL already ends with `/`, so concatenate directly: `base_url + size + poster_path` (not `base_url + size + '/' + poster_path`).

- **`vote_average` is meaningless with low `vote_count`** — A film with 3 votes and a 9.0 average means nothing. Always filter with `vote_count.gte=100` (or 200) when sorting by rating in Discover.

- **Search returns `genre_ids` (ints), details return `genres` (objects)** — Search results give `[28, 878]`; use the genre map from `/genre/movie/list` to resolve names. Detail endpoints give `[{'id': 28, 'name': 'Action'}, ...]` directly.

- **`release_date` is empty string `''` for unreleased films** — Not `None`. Guard with `m.get('release_date') or 'TBD'` before slicing `[:4]`.

- **`append_to_response` is a single API call** — Requesting `credits,videos,keywords` together costs 1 API call, not 3. Use it for any time you need multiple sub-resources for the same movie/show.

- **TV uses `name` / `first_air_date`, movies use `title` / `release_date`** — Search results from `/search/multi` mix both; check `media_type` field (`'movie'` or `'tv'`) to pick the right field.

- **Person `combined_credits` mixes movies and TV** — Each entry has a `media_type` field (`'movie'` or `'tv'`). Movie entries use `title`/`release_date`; TV entries use `name`/`first_air_date`.

- **`/search/multi` searches movies, TV, and people in one call** — Useful when you don't know the type: `?query=nolan&api_key={KEY}`. Returns `media_type` on each result.

- **External IDs** — Find TMDB ID from an IMDb ID: `/find/tt1375666?external_source=imdb_id&api_key={KEY}`. Returns `{'movie_results': [...], 'tv_results': [...], ...}`.

- **Rate limit: ~40 requests/10 seconds** — TMDB enforces ~40 req/10s per IP. At `max_workers=5` with typical response times this stays safe. For aggressive bulk scraping (hundreds of IDs), add `time.sleep(0.25)` between batches or use `ThreadPoolExecutor(max_workers=10)` with caution.

- **Language / region params** — Append `&language=en-US` (default) or `&region=US` to localize results. `popular` and `now_playing` respect `region` to filter by theatrical release country.
