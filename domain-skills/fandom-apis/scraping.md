# Fandom / Fictional Universe APIs — Data Extraction

Public REST (and GraphQL) APIs for Rick and Morty, Star Wars, Pokémon, and Harry Potter. **No auth, no browser needed.** All data is reachable via `http_get`. Confirmed working 2026-04-18.

## Do this first: pick your universe

| Universe | Base URL | Best approach | Latency |
|---|---|---|---|
| Rick and Morty | `https://rickandmortyapi.com/api/` | REST or GraphQL | ~100ms |
| Star Wars | `https://swapi.info/api/` | REST, bulk list | ~150ms |
| Pokémon | `https://pokeapi.co/api/v2/` | REST, by name or id | ~100ms |
| Harry Potter | `https://hp-api.onrender.com/api/` | REST, list then filter | ~300ms |

**Never use a browser for any of these.** All responses are plain JSON, no JS rendering required.

---

## Rick and Morty (`rickandmortyapi.com`)

826 characters, 51 episodes, 126 locations. Supports both REST and GraphQL.

### REST: list with filters and pagination

```python
import json
from helpers import http_get

# All characters — 20 per page, 42 pages total
data = json.loads(http_get("https://rickandmortyapi.com/api/character"))
# data['info'] = {'count': 826, 'pages': 42, 'next': '...?page=2', 'prev': None}
# data['results'] = list of 20 character dicts

# Filter: status, species, gender, name, type
data = json.loads(http_get(
    "https://rickandmortyapi.com/api/character?status=alive&species=Human&name=Rick"
))
# data['info']['count'] = 22  (alive human Ricks)
# data['results'][0] = {'id': 1, 'name': 'Rick Sanchez', 'status': 'Alive', ...}

# Paginate
page2 = json.loads(http_get("https://rickandmortyapi.com/api/character?page=2"))
# Or follow data['info']['next'] directly
```

Character fields: `id`, `name`, `status` (Alive/Dead/unknown), `species`, `type`, `gender`, `origin` (dict with name+url), `location` (dict), `image` (JPEG URL), `episode` (list of episode URLs), `url`, `created`

### REST: batch fetch by ID (comma-separated — returns list, not paginated dict)

```python
import json
from helpers import http_get

# Batch: returns a plain list, NOT the {info, results} wrapper
chars = json.loads(http_get("https://rickandmortyapi.com/api/character/1,2,3"))
# [{'id': 1, 'name': 'Rick Sanchez', ...}, {'id': 2, 'name': 'Morty Smith', ...}, ...]

# Same works for episodes and locations
eps = json.loads(http_get("https://rickandmortyapi.com/api/episode/1,2,3"))
# [{'id': 1, 'name': 'Pilot', 'episode': 'S01E01', 'air_date': 'December 2, 2013',
#   'characters': ['https://.../character/1', ...], ...}, ...]
```

### REST: episodes and locations

```python
import json
from helpers import http_get

# Episodes: 51 total, 3 pages
eps = json.loads(http_get("https://rickandmortyapi.com/api/episode"))
# ep fields: id, name, air_date, episode (e.g. 'S01E01'), characters (list of URLs), url, created

# Filter by episode code (partial match)
s1 = json.loads(http_get("https://rickandmortyapi.com/api/episode?episode=S01"))
# s1['info']['count'] = 11

# Locations: 126 total, 7 pages
locs = json.loads(http_get("https://rickandmortyapi.com/api/location"))
# loc fields: id, name, type, dimension, residents (list of character URLs), url, created
```

### GraphQL endpoint

```python
import json, urllib.request

query = """{
  characters(filter: {status: "Alive", species: "Human"}) {
    info { count }
    results { id name status species gender }
  }
}"""
body = json.dumps({"query": query}).encode()
req = urllib.request.Request(
    "https://rickandmortyapi.com/graphql",
    data=body,
    headers={"Content-Type": "application/json", "Accept": "application/json"},
    method="POST",
)
with urllib.request.urlopen(req, timeout=20) as r:
    resp = json.loads(r.read())
# resp['data']['characters']['info']['count'] = 245
# resp['data']['characters']['results'] = list of {id, name, status, species, gender}

# Filter episodes by season
query2 = '{ episodes(filter: {episode: "S01"}) { info { count } results { id name episode air_date } } }'
```

GraphQL also supports `locations` with `filter: {name, type, dimension}`. Use REST for bulk; use GraphQL when you need specific filtered subsets without pagination loops.

### Fetch all characters (paginate to completion)

```python
import json
from helpers import http_get

all_chars = []
url = "https://rickandmortyapi.com/api/character"
while url:
    data = json.loads(http_get(url))
    all_chars.extend(data["results"])
    url = data["info"]["next"]  # None on last page
# len(all_chars) == 826  (confirmed 2026-04-18)
```

---

## Star Wars — SWAPI (`swapi.info`)

Use `swapi.info` (faster unofficial clone) for bulk reads. Fall back to `swapi.dev` for `?search=` filtering. `swapi.info` list endpoints return the full array in one call — no pagination needed.

```python
import json
from helpers import http_get

# swapi.info: single call returns ALL 82 people (no pagination)
people = json.loads(http_get("https://swapi.info/api/people/"))
# people = list of 82 dicts, each: name, height, mass, hair_color, skin_color,
#   eye_color, birth_year, gender, homeworld (URL), films (list of URLs),
#   species, vehicles, starships, created, edited, url

# Single resource by ID (no trailing slash required on swapi.info)
luke = json.loads(http_get("https://swapi.info/api/people/1"))
# luke['name'] = 'Luke Skywalker', luke['birth_year'] = '19BBY'

# Available resources on swapi.info
root = json.loads(http_get("https://swapi.info/api/"))
# root keys: ['films', 'people', 'planets', 'species', 'vehicles', 'starships']

films = json.loads(http_get("https://swapi.info/api/films/"))      # 6 films
ships = json.loads(http_get("https://swapi.info/api/starships/"))  # 36 starships
```

**Film fields:** `title`, `episode_id`, `opening_crawl`, `director`, `producer`, `release_date`, `characters` (list of URLs), `planets`, `starships`, `vehicles`, `species`

### Search (use swapi.dev for this — swapi.info ignores `?search=`)

```python
import json
from helpers import http_get

# swapi.dev supports ?search= but is slower (~700-900ms per call)
results = json.loads(http_get("https://swapi.dev/api/people/?search=luke"))
# results['count'] = 1
# results['results'][0]['name'] = 'Luke Skywalker'
# Paginates with results['next'] URL (10 items per page)

# swapi.info ignores ?search= — returns all 82 people regardless
# For client-side search on swapi.info:
people = json.loads(http_get("https://swapi.info/api/people/"))
luke = next(p for p in people if "luke" in p["name"].lower())
```

### Resolve URLs to data

All related resources (homeworld, films, starships) are returned as URL strings. Resolve them with `http_get`:

```python
import json
from helpers import http_get

luke = json.loads(http_get("https://swapi.info/api/people/1"))
homeworld = json.loads(http_get(luke["homeworld"]))
# homeworld['name'] = 'Tatooine', homeworld['climate'] = 'arid',
# homeworld['terrain'] = 'desert', homeworld['population'] = '200000'

# Bulk resolve with ThreadPoolExecutor
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=5) as ex:
    film_data = list(ex.map(lambda u: json.loads(http_get(u)), luke["films"]))
```

---

## Pokémon (`pokeapi.co`)

1350 Pokémon. Free, no auth. Supports name or numeric ID in all endpoints.

### Fetch a Pokémon

```python
import json
from helpers import http_get

# By name or ID — both work
p = json.loads(http_get("https://pokeapi.co/api/v2/pokemon/pikachu"))
# or: http_get("https://pokeapi.co/api/v2/pokemon/25")

print(p["id"])           # 25
print(p["name"])         # pikachu
print(p["height"])       # 4  (decimetres)
print(p["weight"])       # 60 (hectograms)
print(p["base_experience"])  # 112
print([t["type"]["name"] for t in p["types"]])       # ['electric']
print([a["ability"]["name"] for a in p["abilities"]]) # ['static', 'lightning-rod']
print({s["stat"]["name"]: s["base_stat"] for s in p["stats"]})
# {'hp': 35, 'attack': 55, 'defense': 40, 'special-attack': 50, 'special-defense': 50, 'speed': 90}
print(p["sprites"]["front_default"])
# 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png'
```

### List with pagination

```python
import json
from helpers import http_get

# Default: 20 per page, offset=0
data = json.loads(http_get("https://pokeapi.co/api/v2/pokemon?limit=20&offset=0"))
# data['count'] = 1350 (total)
# data['next'] = 'https://pokeapi.co/api/v2/pokemon?offset=20&limit=20'
# data['results'] = [{'name': 'bulbasaur', 'url': 'https://pokeapi.co/api/v2/pokemon/1/'}, ...]

# Fetch ALL at once (no server-side cap enforced)
all_pokemon = json.loads(http_get("https://pokeapi.co/api/v2/pokemon?limit=100000&offset=0"))
# all_pokemon['results'] length == 1350  (~150ms, confirmed 2026-04-18)
names = [p["name"] for p in all_pokemon["results"]]
```

### Species, evolution chain, type

```python
import json
from helpers import http_get

# Species: lore, capture rate, generation, Pokédex flavor text
species = json.loads(http_get("https://pokeapi.co/api/v2/pokemon-species/pikachu"))
# species['capture_rate'] = 190
# species['is_legendary'] = False
# species['generation']['name'] = 'generation-i'
# species['evolution_chain']['url'] = 'https://pokeapi.co/api/v2/evolution-chain/10/'
en_text = next(
    e["flavor_text"] for e in species["flavor_text_entries"]
    if e["language"]["name"] == "en"
)

# Evolution chain
evo_url = species["evolution_chain"]["url"]
evo = json.loads(http_get(evo_url))
# evo['chain']['species']['name'] = 'pichu'
# evo['chain']['evolves_to'][0]['species']['name'] = 'pikachu'
# evo['chain']['evolves_to'][0]['evolves_to'][0]['species']['name'] = 'raichu'

# All Pokémon of a type
electric = json.loads(http_get("https://pokeapi.co/api/v2/type/electric"))
# electric['pokemon'] = list of 114 dicts, each {'pokemon': {'name': '...', 'url': '...'}, 'slot': 1}
names = [p["pokemon"]["name"] for p in electric["pokemon"]]

# Move details
move = json.loads(http_get("https://pokeapi.co/api/v2/move/thunderbolt"))
# move['power'] = 90, move['pp'] = 15, move['accuracy'] = 100
# move['type']['name'] = 'electric', move['damage_class']['name'] = 'special'

# Ability details
ability = json.loads(http_get("https://pokeapi.co/api/v2/ability/overgrow"))
effect = next(e["effect"] for e in ability["effect_entries"] if e["language"]["name"] == "en")
# 'When this Pokémon has 1/3 or less of its HP remaining, its grass-type moves inflict 1.5×...'
```

### Parallel bulk fetch

```python
import json
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

def fetch_pokemon(name):
    d = json.loads(http_get(f"https://pokeapi.co/api/v2/pokemon/{name}"))
    return {
        "name": d["name"],
        "id": d["id"],
        "types": [t["type"]["name"] for t in d["types"]],
        "stats": {s["stat"]["name"]: s["base_stat"] for s in d["stats"]},
    }

names = ["bulbasaur", "charmander", "squirtle", "pikachu", "mewtwo"]
with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_pokemon, names))
# Confirmed: 5 Pokémon in ~0.15s  (2026-04-18)
```

### Other resource endpoints

| Endpoint | Example | Notes |
|---|---|---|
| `/api/v2/ability/{name}` | `overgrow` | Effect, Pokémon that have it |
| `/api/v2/move/{name}` | `thunderbolt` | Power, PP, accuracy, type |
| `/api/v2/type/{name}` | `electric` | All Pokémon of that type, damage relations |
| `/api/v2/generation/{id}` | `1` | All 151 species in Gen I |
| `/api/v2/berry/{name}` | `cheri` | Firmness, natural gift type |
| `/api/v2/evolution-chain/{id}` | `10` | Full evolution tree |
| `/api/v2/item/{name}` | `poke-ball` | Item details |

---

## Harry Potter (`hp-api.onrender.com`)

437 characters, 77 spells. No auth. No search/filter params — fetch all and filter client-side.

### Characters

```python
import json
from helpers import http_get

# All 437 characters in one call
chars = json.loads(http_get("https://hp-api.onrender.com/api/characters"))
# Each dict: id (UUID), name, alternate_names (list), species, gender, house,
#   dateOfBirth ('31-07-1980'), yearOfBirth (int), wizard (bool), ancestry,
#   eyeColour, hairColour, wand {wood, core, length}, patronus,
#   hogwartsStudent (bool), hogwartsStaff (bool), actor, alternate_actors,
#   alive (bool), image (URL or '')

# Filter client-side
alive = [c for c in chars if c["alive"]]           # 307
dead  = [c for c in chars if not c["alive"]]        # 130
wizards = [c for c in chars if c["wizard"]]
gryff   = [c for c in chars if c["house"] == "Gryffindor"]

# By house (server-side filter — faster if you only need one house)
g = json.loads(http_get("https://hp-api.onrender.com/api/characters/house/gryffindor"))  # 47
s = json.loads(http_get("https://hp-api.onrender.com/api/characters/house/slytherin"))   # 46
h = json.loads(http_get("https://hp-api.onrender.com/api/characters/house/hufflepuff"))  # 19
r = json.loads(http_get("https://hp-api.onrender.com/api/characters/house/ravenclaw"))   # 23

# Students only / Staff only
students = json.loads(http_get("https://hp-api.onrender.com/api/characters/students"))  # 103
staff    = json.loads(http_get("https://hp-api.onrender.com/api/characters/staff"))     # 25

# Individual character by UUID — returns a list (always wrap with [0])
char = json.loads(http_get("https://hp-api.onrender.com/api/character/9e3f7ce4-b9a7-4244-b709-dae5c1f1d4a8"))[0]
# char['name'] = 'Harry Potter'
```

### Spells

```python
import json
from helpers import http_get

spells = json.loads(http_get("https://hp-api.onrender.com/api/spells"))
# 77 spells, each: id (UUID), name, description
# Example: {'id': 'c76a2922-...', 'name': 'Aberto', 'description': 'Opens locked doors'}
```

### HP API endpoints summary

| Endpoint | Returns |
|---|---|
| `/api/characters` | All 437 characters |
| `/api/characters/students` | 103 Hogwarts students |
| `/api/characters/staff` | 25 Hogwarts staff |
| `/api/characters/house/{house}` | House members (gryffindor/slytherin/hufflepuff/ravenclaw) |
| `/api/character/{uuid}` | Single character as a 1-element list |
| `/api/spells` | All 77 spells |

---

## Gotchas

- **Rick and Morty batch ID returns a list, not the paginated wrapper.** `/api/character/1,2,3` returns `[{...}, {...}, {...}]` directly. `/api/character` returns `{info: {...}, results: [...]}`. Check `isinstance(data, list)` if you handle both paths.

- **Rick and Morty GraphQL is POST to `/graphql`, not `/api/graphql`.** Endpoint is `https://rickandmortyapi.com/graphql`. The REST base is `https://rickandmortyapi.com/api/`. Don't mix them.

- **`swapi.info` ignores `?search=`.** The unofficial clone returns all 82 people regardless of the search parameter. Use `swapi.dev` if you need server-side name filtering (costs ~700-900ms vs. 150ms). Alternatively fetch all from `swapi.info` and filter client-side with `next(p for p in people if keyword in p["name"].lower())`.

- **`swapi.info` URLs have no trailing slash for single resources.** `/api/people/1` works; `/api/people/1/` also works. List endpoints like `/api/people/` require the trailing slash or you get a redirect.

- **SWAPI related fields are URL strings, not nested objects.** `luke["homeworld"]` is `"https://swapi.info/api/planets/1"`, not a dict. You must make a separate `http_get` call to resolve it. Use `ThreadPoolExecutor` to parallelize resolution of multiple related URLs.

- **SWAPI `height` and `mass` are strings, not numbers.** Values like `"172"`, `"77"`, `"unknown"`. Always cast with `int(p["height"])` inside a try/except.

- **PokeAPI `height` is decimetres, `weight` is hectograms.** Pikachu: `height=4` (0.4m), `weight=60` (6.0kg). Divide by 10 for metric SI units.

- **PokeAPI `flavor_text` contains control characters.** The Pokédex entry strings include `\n`, `\x0c` (form feed), and `\u00ad` (soft hyphen). Clean with `text.replace("\n", " ").replace("\x0c", " ").replace("\u00ad", "")`.

- **PokeAPI has no search endpoint.** There is no `?search=` or `?name=` parameter. Fetch by exact name (`/pokemon/pikachu`) or numeric ID (`/pokemon/25`). For fuzzy search, fetch the full name list with `?limit=100000` (one call, ~150ms) and filter locally.

- **HP API `/api/character/{uuid}` returns a list, not an object.** The single-character endpoint wraps the result in `[{...}]`. Always index with `[0]`.

- **HP API has no search or filter params.** No `?name=`, `?alive=`, `?house=`. The only server-side filtering is by house and by student/staff role. Everything else requires fetching all 437 characters and filtering in Python.

- **HP API is hosted on Render free tier — cold starts.** First request after idle may take 15-30 seconds. If you get a timeout, retry once. Subsequent calls respond in ~300ms.

- **Rick and Morty character `episode` field is a list of episode URLs, not IDs.** To get episode IDs, parse the URL: `ep_id = url.split('/')[-1]`. Or fetch the episodes endpoint and join on character URLs.

- **`pokeapi.co` has implicit rate limiting.** Responses include `X-RateLimit-Limit` and `X-RateLimit-Remaining` headers (not accessible via `http_get`'s raw urllib). For bulk crawls, cap `ThreadPoolExecutor` at `max_workers=10` and add `time.sleep(0.05)` between batches of 50+.
