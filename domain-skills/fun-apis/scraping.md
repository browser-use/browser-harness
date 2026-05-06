# Fun / Random Public APIs — Data Extraction

No-auth, no-browser APIs great for testing, demos, and data generation. All work with `http_get`. Confirmed 2026-04-18.

| API | Base URL | Auth | Rate limit |
|-----|----------|------|------------|
| The Cat API | `https://api.thecatapi.com/v1` | None (or optional key) | ~10 req/min anon |
| Dog CEO | `https://dog.ceo/api` | None | None documented |
| Random User | `https://randomuser.me/api` | None | None documented |
| JokeAPI | `https://v2.jokeapi.dev/joke` | None | 120 req/min |
| ZenQuotes | `https://zenquotes.io/api` | None | ~5 req/30s |
| Open Trivia DB | `https://opentdb.com/api.php` | None | ~5 req/5s |

---

## Animals

### Cat API — random images

```python
import json
from helpers import http_get

# 5 random cat images (no API key needed)
cats = json.loads(http_get("https://api.thecatapi.com/v1/images/search?limit=5"))
for cat in cats:
    print(cat["url"], cat["width"], "x", cat["height"])
# Confirmed keys: id (str), url, width (int), height (int)
# Confirmed: ?limit=5 returns UP TO 10 without an API key (limit param ignored anon — returns ~10)

# Filter to JPG/PNG only (no GIFs)
cats = json.loads(http_get("https://api.thecatapi.com/v1/images/search?limit=5&mime_types=jpg,png"))
```

### Cat API — images with breed data

```python
import json
from helpers import http_get

# Returns images that have breed metadata attached
cats = json.loads(http_get("https://api.thecatapi.com/v1/images/search?limit=3&has_breeds=1"))
for cat in cats:
    if cat.get("breeds"):
        b = cat["breeds"][0]
        print(b["name"], b["origin"], b["temperament"])
        print(f"  Intelligence: {b['intelligence']}/5, Energy: {b['energy_level']}/5")
        print(f"  Life span: {b['life_span']} years")
```

### Cat API — full breed catalog (67 breeds)

```python
import json
from helpers import http_get

breeds = json.loads(http_get("https://api.thecatapi.com/v1/breeds"))
# Returns list of 67 breed dicts — confirmed 2026-04-18
for b in breeds[:3]:
    print(b["id"], b["name"])
    # b keys: id, name, origin, temperament, description, life_span
    #         adaptability, affection_level, child_friendly, dog_friendly,
    #         energy_level, grooming, health_issues, intelligence,
    #         shedding_level, social_needs, stranger_friendly, vocalisation
    #         hypoallergenic, indoor, lap, natural, rare, rex
    #         wikipedia_url, reference_image_id

# Get image for a breed using reference_image_id
breed = breeds[0]
img_url = f"https://cdn2.thecatapi.com/images/{breed['reference_image_id']}.jpg"
```

### Dog CEO — random images

```python
import json
from helpers import http_get

# Single random dog image
dog = json.loads(http_get("https://dog.ceo/api/breeds/image/random"))
print(dog["message"])   # "https://images.dog.ceo/breeds/husky/n02110185_8860.jpg"
print(dog["status"])    # "success"

# Multiple random images (any breed), up to 50
dogs = json.loads(http_get("https://dog.ceo/api/breeds/image/random/10"))
for url in dogs["message"]:
    print(url)
# message is a list of URLs when requesting multiple
```

### Dog CEO — breed-specific images

```python
import json
from helpers import http_get

# Random image from a specific breed
lab = json.loads(http_get("https://dog.ceo/api/breed/labrador/images/random/5"))
print(lab["message"])    # list of 5 URLs

# Sub-breed (breed/sub-breed)
french = json.loads(http_get("https://dog.ceo/api/breed/bulldog/french/images/random"))
print(french["message"]) # single URL string

# List all sub-breeds for a breed
subs = json.loads(http_get("https://dog.ceo/api/breed/bulldog/list"))
print(subs["message"])   # ["boston", "english", "french"]

# Full breed list — dict where key=breed, value=list of sub-breeds (empty list if none)
all_breeds = json.loads(http_get("https://dog.ceo/api/breeds/list/all"))
breeds = all_breeds["message"]   # {"affenpinscher": [], "african": ["wild"], "bulldog": ["boston","english","french"], ...}
print(list(breeds.items())[:3])
```

Confirmed breed name format: `"bulldog/french"` → URL path is `/breed/bulldog/french/...`. Breed names are all lowercase.

---

## Random User Data

### randomuser.me — generate test personas

```python
import json
from helpers import http_get

# 5 random US users
data = json.loads(http_get("https://randomuser.me/api/?results=5&nat=us"))
for u in data["results"]:
    name = f"{u['name']['title']} {u['name']['first']} {u['name']['last']}"
    print(name, u["email"], u["phone"])
    print(f"  DOB: {u['dob']['date'][:10]}, age {u['dob']['age']}")
    print(f"  City: {u['location']['city']}, {u['location']['state']}")
    print(f"  Avatar: {u['picture']['large']}")
    # login: uuid, username, password, salt, md5, sha1, sha256
    # id: {"name": "SSN", "value": "576-49-7178"}
```

### Filter fields and nationality

```python
import json
from helpers import http_get

# Only fetch the fields you need — much smaller response
data = json.loads(http_get(
    "https://randomuser.me/api/"
    "?results=10&nat=gb,fr,de&inc=name,email,nat,dob,picture"
))
for u in data["results"]:
    print(u["nat"], u["name"]["first"], u["name"]["last"], u["email"])
# info.seed is returned — reuse for reproducibility

# Reproducible results with a seed
data = json.loads(http_get("https://randomuser.me/api/?results=5&seed=abc123&nat=us"))
# Same seed always returns same users — good for test fixtures
```

Available nationalities: `au, br, ca, ch, de, dk, es, fi, fr, gb, ie, in, ir, mx, nl, no, nz, rs, tr, ua, us`

Available `inc` fields: `gender, name, location, email, login, dob, registered, phone, cell, id, picture, nat`

---

## Jokes

### JokeAPI — single joke

```python
import json
from helpers import http_get

# Safe single joke from any category
joke = json.loads(http_get("https://v2.jokeapi.dev/joke/Any?safe-mode"))

if joke["type"] == "twopart":
    print(joke["setup"])
    print(joke["delivery"])
else:  # type == "single"
    print(joke["joke"])

# Metadata always present:
# joke["category"]    — "Programming", "Misc", "Pun", "Dark", "Spooky", "Christmas"
# joke["id"]          — int, unique per joke
# joke["flags"]       — {"nsfw": bool, "religious": bool, "political": bool,
#                        "racist": bool, "sexist": bool, "explicit": bool}
# joke["lang"]        — "en"
# joke["safe"]        — True when ?safe-mode used
# joke["error"]       — False on success
```

### JokeAPI — batch and filter

```python
import json
from helpers import http_get

# Up to 10 jokes at once, multiple categories
data = json.loads(http_get(
    "https://v2.jokeapi.dev/joke/Programming,Pun?safe-mode&amount=5"
))
# When amount > 1: data["jokes"] is a list, data["amount"] = count returned
# When amount = 1: joke is a flat dict (no "jokes" key)
for j in data["jokes"]:
    text = j["setup"] + " / " + j["delivery"] if j["type"] == "twopart" else j["joke"]
    print(f"[{j['category']}] {text}")

# Blacklist specific flags (comma-separated)
joke = json.loads(http_get(
    "https://v2.jokeapi.dev/joke/Any?blacklistFlags=nsfw,political,sexist"
))
```

Valid categories (case-insensitive): `Any, Misc, Programming, Dark, Pun, Spooky, Christmas`

---

## Quotes

### ZenQuotes — single or batch

```python
import json
from helpers import http_get

# Single random quote
data = json.loads(http_get("https://zenquotes.io/api/random"))
quote = data[0]          # always a list, even for single
print(quote["q"])        # "Don't be afraid that you do not know something..."
print(quote["a"])        # "Zen Proverb"
# quote["h"] — pre-formatted HTML <blockquote>
# quote["c"] — character count (only in /quotes batch endpoint)

# Today's quote of the day (stable for 24h — good for caching)
data = json.loads(http_get("https://zenquotes.io/api/today"))
print(data[0]["q"], "—", data[0]["a"])

# Batch: 50 quotes at once — more efficient than repeated single calls
batch = json.loads(http_get("https://zenquotes.io/api/quotes"))
print(f"Got {len(batch)} quotes")
for q in batch[:3]:
    print(q["q"], "—", q["a"], f"({q['c']} chars)")
```

Rate limit: ~5 requests per 30 seconds for the `/random` endpoint. Use `/quotes` (50 at once) then shuffle locally to avoid hitting limits.

---

## Trivia

### Open Trivia DB — fetch questions

```python
import json, html
from helpers import http_get

# 5 multiple-choice questions (any category)
data = json.loads(http_get("https://opentdb.com/api.php?amount=5&type=multiple"))
# response_code 0 = success, 1 = no results, 2 = invalid param,
#               3 = token not found, 4 = token empty (all questions exhausted)
assert data["response_code"] == 0

for q in data["results"]:
    question = html.unescape(q["question"])   # CRITICAL: questions use HTML entities
    correct  = html.unescape(q["correct_answer"])
    wrong    = [html.unescape(a) for a in q["incorrect_answers"]]
    print(f"[{q['difficulty']}] {question}")
    print(f"  Answer: {correct}")
    # q keys: type, difficulty, category, question, correct_answer, incorrect_answers
```

### Filter by category and difficulty

```python
import json, html, random
from helpers import http_get

# Category 18 = Science: Computers, difficulty = easy, type = multiple
data = json.loads(http_get(
    "https://opentdb.com/api.php?amount=10&category=18&difficulty=easy&type=multiple"
))

for q in data["results"]:
    question = html.unescape(q["question"])
    # Shuffle answers for display
    answers = [html.unescape(a) for a in q["incorrect_answers"]] + [html.unescape(q["correct_answer"])]
    random.shuffle(answers)
    print(question)
    for i, a in enumerate(answers, 1):
        print(f"  {i}. {a}")

# True/False questions (type=boolean — returns "True"/"False" strings)
data = json.loads(http_get(
    "https://opentdb.com/api.php?amount=5&category=9&difficulty=easy&type=boolean"
))
for q in data["results"]:
    print(html.unescape(q["question"]))
    print(f"  Answer: {q['correct_answer']}")  # "True" or "False"
```

### Session token (no question repeats)

```python
import json
from helpers import http_get

# Get a session token — valid 6 hours, guarantees no repeats until all questions served
tok = json.loads(http_get("https://opentdb.com/api_token.php?command=request"))
token = tok["token"]   # long hex string

# Pass token with every question request
data = json.loads(http_get(
    f"https://opentdb.com/api.php?amount=5&type=multiple&token={token}"
))
# When all questions in category exhausted: response_code=4 — reset with:
# http_get(f"https://opentdb.com/api_token.php?command=reset&token={token}")
```

### Category reference

```python
import json
from helpers import http_get

categories = json.loads(http_get("https://opentdb.com/api_category.php"))
for c in categories["trivia_categories"]:
    print(c["id"], c["name"])
# 9 General Knowledge | 10 Books | 11 Film | 12 Music | 14 Television
# 15 Video Games | 17 Science & Nature | 18 Science: Computers | 19 Science: Mathematics
# 20 Mythology | 21 Sports | 22 Geography | 23 History | 24 Politics
# 25 Art | 26 Celebrities | 27 Animals | 28 Vehicles | 32 Cartoons
```

---

## Combined: build a demo dataset

```python
import json, html, random
from helpers import http_get

def get_cat_image():
    cats = json.loads(http_get("https://api.thecatapi.com/v1/images/search?limit=1&mime_types=jpg,png"))
    return cats[0]["url"]

def get_dog_image(breed=None):
    if breed:
        url = f"https://dog.ceo/api/breed/{breed}/images/random"
    else:
        url = "https://dog.ceo/api/breeds/image/random"
    return json.loads(http_get(url))["message"]

def get_random_user(nat="us"):
    data = json.loads(http_get(
        f"https://randomuser.me/api/?results=1&nat={nat}&inc=name,email,picture,dob"
    ))
    u = data["results"][0]
    return {
        "name": f"{u['name']['first']} {u['name']['last']}",
        "email": u["email"],
        "age": u["dob"]["age"],
        "avatar": u["picture"]["thumbnail"],
    }

def get_joke():
    j = json.loads(http_get("https://v2.jokeapi.dev/joke/Programming,Pun?safe-mode"))
    if j["type"] == "twopart":
        return f"{j['setup']} / {j['delivery']}"
    return j["joke"]

def get_trivia(category=18, difficulty="easy"):
    data = json.loads(http_get(
        f"https://opentdb.com/api.php?amount=1&category={category}&difficulty={difficulty}&type=multiple"
    ))
    if data["response_code"] != 0:
        return None
    q = data["results"][0]
    return {
        "question": html.unescape(q["question"]),
        "correct": html.unescape(q["correct_answer"]),
        "wrong": [html.unescape(a) for a in q["incorrect_answers"]],
        "difficulty": q["difficulty"],
    }

# Example usage
user = get_random_user()
print(f"User: {user['name']} ({user['email']}, age {user['age']})")
print(f"Joke: {get_joke()}")
q = get_trivia()
if q:
    print(f"Trivia [{q['difficulty']}]: {q['question']} -> {q['correct']}")
```

---

## Gotchas

**Cat API `?limit=` param is silently ignored for anonymous requests.** Without an API key the response returns up to ~10 images regardless of `limit`. Register for a free key at `https://thecatapi.com` and pass `x-api-key: YOUR_KEY` header to get true `limit` control and higher-quality images.

**Cat API `has_breeds=1` often returns images with empty `breeds` list anyway.** The filter is best-effort — always guard with `if cat.get("breeds")`.

**Dog CEO `message` is a string for single-image endpoints, list for multi-image.** `/breeds/image/random` → string; `/breeds/image/random/5` → list. Don't assume type.

**Dog CEO breed path uses hyphens for sub-breeds:** `/breed/bulldog-french` does NOT work — correct is `/breed/bulldog/french`.

**JokeAPI response shape differs between `amount=1` and `amount>1`.** Single joke: flat dict with `joke["setup"]` or `joke["joke"]`. Multiple: `data["jokes"]` is a list. Always check `amount` param or test for the `"jokes"` key.

**JokeAPI categories are specific strings, not freeform.** Valid: `Any, Misc, Programming, Dark, Pun, Spooky, Christmas`. Anything else returns error code 106. `Science` is NOT a valid category (confirmed error in testing).

**OpenTDB questions use HTML entities.** `&quot;`, `&amp;`, `&#039;` appear in raw strings. Always pass through `html.unescape()` before display.

**OpenTDB `response_code=1` means "no results for your filters"**, not an HTTP error. Happens when category + difficulty combination has fewer questions than your `amount` — reduce `amount` or remove `difficulty`.

**OpenTDB rate limit is ~5 requests per 5 seconds.** Exceeding it returns HTTP 429. Add `time.sleep(1)` between calls in loops. Use session tokens + batch `amount=50` to minimize round trips.

**ZenQuotes `/random` rate-limits aggressively (~5 req/30s).** For bulk use, call `/quotes` once (returns 50 quotes) and shuffle locally. `/today` is stable for 24h and not rate-limited.

**randomuser.me `nat` codes are lowercase 2-letter country codes**, not language codes. `nat=us` for American names, `nat=gb` for British, `nat=fr` for French, etc.

**quotable.io (`api.quotable.io`) is offline** as of 2026-04-18. Use ZenQuotes instead.

**loripsum.net is offline** as of 2026-04-18. For Lorem Ipsum, generate with Python's `lorem` package or use `https://loremipsum.io/api/` if you need a live endpoint.
