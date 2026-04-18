# Letterboxd — Film Data Scraping

`https://letterboxd.com` — film logging, rating, and review site. Film pages and user profile root pages are publicly accessible via `http_get` (~200–350ms). Most sub-pages (reviews, ratings, user film lists, browse/genre pages) return 403 and require the browser.

## Access path decision table

| Goal | Method | Latency |
|------|--------|---------|
| Film metadata (title, year, director, cast, genres, rating) | `http_get` + JSON-LD | ~200–350ms |
| Film synopsis, poster, OG data | `http_get` + meta tags | same request |
| Film popular reviews (top 12 inline) | `http_get` film page | same request |
| User profile stats (film count, followers) | `http_get` user root | ~150ms |
| Recent global activity stream | `http_get /films/` | ~200ms |
| User watched film list | browser (`/{username}/films/`) | |
| Ratings distribution histogram | browser (`/film/{slug}/ratings/`) | |
| All reviews (paginated) | browser (`/film/{slug}/reviews/`) | |
| Popular / browse / genre film lists | browser (`/films/popular/`, etc.) | |
| Director / actor pages | browser (`/director/{slug}/`, `/actor/{slug}/`) | |
| User diary / lists | browser (`/{username}/diary/`, `/{username}/lists/`) | |

**Letterboxd's public API** (`api.letterboxd.com/api/v0/`) returns 401 on all endpoints — it requires OAuth2 client credentials (apply at letterboxd.com/api-beta/).

**Cloudflare Turnstile** is configured in the page JS but is not blocking `http_get` on accessible pages. It only activates on the login form.

---

## Path 1: Film page via http_get (fastest for metadata + ratings)

Film pages at `letterboxd.com/film/{slug}/` are fully accessible. The JSON-LD block (Movie schema) contains everything you need in one parse.

**URL slug format:** lowercase title, spaces replaced with hyphens. For disambiguation (same title, different year) append `-{year}`: e.g. `parasite-2019`, `alien-1979`.

```python
import json, re, html as htmllib
from helpers import http_get

def extract_film_data(slug):
    """
    Fetch and parse a Letterboxd film page.
    slug examples: 'the-godfather', 'parasite-2019', 'inception', '2001-a-space-odyssey'
    """
    html = http_get(f"https://letterboxd.com/film/{slug}/")
    result = {}

    # --- JSON-LD (primary source) ---
    jsonld_raw = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
    for block in jsonld_raw:
        # Strip CDATA wrapper that Letterboxd wraps around JSON-LD
        cleaned = re.sub(r'/\*\s*<!\[CDATA\[.*?\*/\s*', '', block, flags=re.DOTALL)
        cleaned = re.sub(r'/\*\s*\]\]>.*?\*/', '', cleaned, flags=re.DOTALL)
        try:
            data = json.loads(cleaned.strip())
        except json.JSONDecodeError:
            continue
        if data.get('@type') != 'Movie':
            continue

        result['title']     = data['name']
        result['year']      = data['releasedEvent'][0]['startDate'] if data.get('releasedEvent') else None
        result['directors'] = [d['name'] for d in data.get('director', [])]
        result['genres']    = data.get('genre', [])
        result['countries'] = [c['name'] for c in data.get('countryOfOrigin', [])]
        result['studios']   = [s['name'] for s in data.get('productionCompany', [])]
        result['actors']    = [a['name'] for a in data.get('actors', [])]
        result['poster_url'] = data.get('image')
        result['url']       = data.get('url')
        r = data.get('aggregateRating', {})
        result['rating']       = r.get('ratingValue')   # float 0.0–5.0
        result['rating_count'] = r.get('ratingCount')   # int, total ratings cast
        result['review_count'] = r.get('reviewCount')   # int, written reviews only

    # --- OG / meta tags (fast fallback, redundant) ---
    og = lambda prop: next(iter(re.findall(
        rf'<meta[^>]+property="og:{prop}"[^>]+content="([^"]*)"', html)), None)
    result['og_title']  = og('title')    # includes year: "The Godfather (1972)"
    result['synopsis']  = htmllib.unescape(og('description') or '')
    result['og_image']  = og('image')    # large 1200x675 crop

    # --- Film ID (internal numeric ID) ---
    m = re.search(r'data-film-id="(\d+)"', html)
    result['film_id'] = m.group(1) if m else None

    # --- Tagline ---
    m = re.search(r'<h4 class="tagline">([^<]+)</h4>', html)
    result['tagline'] = htmllib.unescape(m.group(1)) if m else None

    # --- Themes (from tab-genres section) ---
    m = re.search(r'<h3><span>Themes</span></h3>.*?<p>(.*?)</p>', html, re.DOTALL)
    result['themes'] = re.findall(r'class="text-slug">([^<]+)</a>', m.group(1)) if m else []

    # --- Languages ---
    result['languages'] = re.findall(r'href="/films/language/[^/]+/"[^>]*>([^<]+)</a>', html)

    # --- Fans count ---
    m = re.search(r'class="accessory"[^>]*>\s*([\d,KkMm]+)\s*fans</a>', html)
    result['fans'] = m.group(1) if m else None  # e.g. "133K"

    # --- Popular reviews (top 12 inline on the page) ---
    result['reviews'] = []
    for vid, person, block in re.findall(
        r'<article class="production-viewing[^"]*"[^>]*data-viewing-id="(\d+)"[^>]*data-person="([^"]+)">(.*?)</article>',
        html, re.DOTALL
    ):
        dm = re.search(r'<strong class="displayname">([^<]+)</strong>', block)
        tm = re.search(r'class="body-text -prose -reset[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
        lm = re.search(r'data-count="(\d+)"', block)
        result['reviews'].append({
            'viewing_id':   vid,
            'username':     person,
            'display_name': dm.group(1) if dm else person,
            'review':       re.sub(r'<[^>]+>', '', tm.group(1)).strip() if tm else '',
            'likes':        int(lm.group(1)) if lm else 0,
        })

    return result
```

### Verified output (2026-04-18)

```python
data = extract_film_data('the-godfather')
# {
#   'title': 'The Godfather',
#   'year': '1972',
#   'directors': ['Francis Ford Coppola'],
#   'genres': ['Crime', 'Drama'],
#   'countries': ['USA'],
#   'studios': ['Paramount Pictures', 'Alfran Productions'],
#   'actors': ['Marlon Brando', 'Al Pacino', 'James Caan', ...],  # full cast list
#   'rating': 4.52,
#   'rating_count': 2619662,
#   'review_count': 372579,
#   'fans': '133K',
#   'film_id': '51818',
#   'tagline': "An offer you can't refuse.",
#   'genres': ['Crime', 'Drama'],
#   'themes': ['Crime, drugs and gangsters', 'Gritty crime and ruthless gangsters', ...],
#   'languages': ['English', 'Latin', 'English', 'Italian'],  # may have dupes; deduplicate
#   'og_title': 'The Godfather (1972)',
#   'synopsis': 'Spanning the years 1945 to 1955...',
#   'poster_url': 'https://a.ltrbxd.com/resized/film-poster/.../51818-the-godfather-0-230-0-345-crop.jpg...',
#   'og_image': 'https://a.ltrbxd.com/resized/sm/upload/.../the-godfather-1200-1200-675-675-crop-000000.jpg...',
#   'reviews': [
#     {'username': 'wizardchurch', 'display_name': 'Hannah', 'likes': 30944,
#      'review': 'haha they made that scene from zootopia into a movie'},
#     ...  # 12 total
#   ]
# }

data = extract_film_data('parasite-2019')
# title: 'Parasite', year: '2019', rating: 4.53, rating_count: 5264520, review_count: 690652
# fans: '175K', directors: ['Bong Joon Ho'], countries: ['South Korea']

data = extract_film_data('inception')
# title: 'Inception', year: '2010', rating: 4.23, rating_count: 3913620
```

---

## Path 2: User profile via http_get

Only the user root page `letterboxd.com/{username}/` is accessible. Sub-pages (`/films/`, `/diary/`, `/lists/`) return 403.

```python
import re, html as htmllib
from helpers import http_get

def extract_user_profile(username):
    html = http_get(f"https://letterboxd.com/{username}/")

    # Display name
    dm = re.search(r'class="displayname tooltip"[^>]*><span class="label">([^<]+)</span>', html)

    # Stats block (Films / This year / Lists / Following / Followers)
    stats = re.findall(
        r'<span class="value">(\d[\d,]*)</span>'
        r'<span class="definition[^"]*">([^<]+)</span>',
        html
    )

    # Favorites from OG description
    od = re.search(r'<meta[^>]+property="og:description"[^>]+content="([^"]*)"', html)
    favorites = []
    if od:
        fm = re.search(r'Favorites:\s*([^.]+)\.', od.group(1))
        if fm:
            favorites = [f.strip() for f in fm.group(1).split(',')]

    # Film IDs of films shown on profile page (recent activity)
    film_ids_on_page = list(set(re.findall(r'data-film-id="(\d+)"', html)))

    return {
        'username':    username,
        'display_name': dm.group(1) if dm else None,
        'stats':       {label.strip(): int(val.replace(',', '')) for val, label in stats},
        'favorites':   favorites,
        'film_ids_on_page': film_ids_on_page,
    }
```

### Verified output

```python
data = extract_user_profile('dave')
# {
#   'username': 'dave',
#   'display_name': 'Dave Vis',
#   'stats': {'Films': 2553, 'This year': 63, 'Lists': 155, 'Following': 77, 'Followers': 34512},
#   'favorites': ['High and Low (1963)', 'Burning (2018)', 'My Neighbor Totoro (1988)', 'Mulholland Drive (2001)'],
#   'film_ids_on_page': ['51818', '47756', ...]  # ~32 film IDs from recent activity blocks
# }
```

---

## Path 3: Global activity stream from /films/

`letterboxd.com/films/` returns the recent global activity feed — approximately 6 full viewing entries, plus many more film slugs from the UI. Use this to discover recently-logged films.

```python
import re, html as htmllib
from helpers import http_get

def extract_activity_stream():
    html = http_get("https://letterboxd.com/films/")
    entries = []
    for owner, obj_id, block in re.findall(
        r'class="production-viewing[^"]*"[^>]*data-owner="([^"]+)"[^>]*data-object-id="([^"]+)"[^>]*>(.*?)</article>',
        html, re.DOTALL
    ):
        film_m = re.search(
            r'data-item-name="([^"]*)".*?data-item-slug="([^"]*)".*?data-film-id="(\d+)"',
            block, re.DOTALL
        )
        if film_m:
            entries.append({
                'owner':     owner,
                'film_name': htmllib.unescape(film_m.group(1)),
                'film_slug': film_m.group(2),
                'film_id':   film_m.group(3),
            })
    return entries

# Returns ~6 entries. Film names are in "Title (Year)" format.
# Example: [{'owner': 'sidduww', 'film_name': 'The Drama (2026)',
#            'film_slug': 'the-drama', 'film_id': '1205494'}, ...]
```

---

## Path 4: Browser for list pages and sub-pages (403 via http_get)

These pages require the browser — use `goto()` + `wait_for_load()` + `wait(2)`:

```python
from helpers import goto, wait_for_load, wait, js
import json

# Popular films
goto("https://letterboxd.com/films/popular/")
wait_for_load()
wait(2)

films = json.loads(js("""
(function() {
  var items = Array.from(document.querySelectorAll('li.film-list-entry, li[class*="poster-container"]'));
  return JSON.stringify(items.slice(0, 30).map(function(el) {
    var poster = el.querySelector('[data-item-slug]') || el.querySelector('[data-film-slug]');
    return {
      name: poster ? (poster.dataset.itemName || poster.dataset.filmName) : null,
      slug: poster ? (poster.dataset.itemSlug || poster.dataset.filmSlug) : null,
      film_id: poster ? poster.dataset.filmId : null
    };
  }).filter(function(x){ return x.slug; }));
})()
"""))

# User watched films list (paginated, 72/page)
goto("https://letterboxd.com/dave/films/")
wait_for_load()
wait(2)

films = json.loads(js("""
(function() {
  var items = Array.from(document.querySelectorAll('li[data-film-id]'));
  return JSON.stringify(items.map(function(el) {
    return {
      film_id:   el.dataset.filmId,
      film_slug: el.dataset.targetLink ? el.dataset.targetLink.replace(/\\/film\\/|\\/$/g,'') : null,
      rating:    el.dataset.ownerRating || null
    };
  }));
})()
"""))

# User diary entries
goto("https://letterboxd.com/dave/diary/")
wait_for_load()
wait(2)

# For paginated browsing, check next page link
next_page_url = js("""
(function() {
  var a = document.querySelector('a.next');
  return a ? a.href : null;
})()
""")
# Returns URL for next page or null. Load it with goto(next_page_url).
```

---

## Gotchas

**JSON-LD is wrapped in CDATA comments** — `json.loads(block)` will fail without stripping the wrapper. Always strip `/* <![CDATA[ */` and `/* ]]> */` first:
```python
cleaned = re.sub(r'/\*\s*<!\[CDATA\[.*?\*/\s*', '', block, flags=re.DOTALL)
cleaned = re.sub(r'/\*\s*\]\]>.*?\*/', '', cleaned, flags=re.DOTALL)
data = json.loads(cleaned.strip())
```

**JSON-LD `name` is bare title, not "Title (Year)"** — `data['name']` returns `'Parasite'`, not `'Parasite (2019)'`. Year is in `data['releasedEvent'][0]['startDate']`. The OG `og:title` meta tag does include the year.

**OG description contains HTML entities** — `og:description` and `tagline` use `&#039;` etc. Always call `html.unescape()` on them.

**`languages` list can have duplicates** — e.g. Parasite returns `['Korean', 'English', 'German', 'Korean']`. Call `list(dict.fromkeys(result['languages']))` to deduplicate while preserving order.

**Disambiguation slugs** — when two films share a title, Letterboxd appends the year to the slug: `parasite-2019` (Bong's film), vs `parasite` (1982 film). If your slug 404s, try appending `-{year}`.

**403 pages** — `/film/{slug}/reviews/`, `/film/{slug}/ratings/`, `/film/{slug}/cast/`, `/film/{slug}/details/`, `/{username}/films/`, `/films/popular/`, `/films/by/rating/`, `/genre/{slug}/`, `/director/{slug}/`, `/actor/{slug}/` all return 403 to `http_get`. These require the browser.

**CSI endpoints are 403** — Letterboxd loads the ratings histogram via `/csi/film/{slug}/rating-histogram/` which returns 403 without a session cookie. Access ratings distribution via browser on `/film/{slug}/ratings/`.

**`/csi/` and `/ajax/` endpoints need session cookies** — these are used to populate the ratings histogram, friend activity, and popular review sections after page load. Only the inline HTML data (top 12 popular reviews) is available via `http_get`.

**Cloudflare Turnstile is present but passive** — the `configuration.cloudflare.turnstile` object is in the page JS, but it only activates on the login form. It does not block unauthenticated reads on public film/user pages.

**The official API requires OAuth** — `api.letterboxd.com/api/v0/` returns 401 on all endpoints. Apply for API access at letterboxd.com/api-beta/ to get client credentials.

**Fans count is abbreviated** — `'133K'`, `'175K'`. Parse with:
```python
def parse_abbrev(s):
    s = s.strip().upper()
    if s.endswith('K'): return int(float(s[:-1]) * 1000)
    if s.endswith('M'): return int(float(s[:-1]) * 1000000)
    return int(s.replace(',', ''))
```

**Film slug from unknown title** — Letterboxd has no public search API. Construct the slug by lowercasing the title and replacing spaces with hyphens, then `http_get` and check for a 403/404 vs a valid JSON-LD block.
