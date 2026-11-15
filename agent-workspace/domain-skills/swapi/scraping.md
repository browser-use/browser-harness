# SWAPI - Star Wars Starship and Character Specs by Name (swapi.dev REST API)

Field-tested against swapi.dev on 2026-11-10 using a Browser Use cloud browser (logged out) plus plain HTTP (Python urllib, curl) from a laptop. About 18 browser requests (5 page loads, 13 in-page `fetch()` calls) and about 45 plain HTTP calls, all serial: every API answer was HTTP 200 except the deliberate 404 probes below; no 429, no challenge, no key, no login.

robots.txt (checked 2026-11-10): https://swapi.dev/robots.txt answers HTTP 403 with an S3 `AccessDenied` XML body, in the logged-out cloud browser and to curl with User-Agent `*`, ChatGPT-User, Claude-User, Claude-Web, Perplexity-User, anthropic-ai, ClaudeBot and GPTBot. RFC 9309 treats a 4xx robots.txt as unavailable (allow all), so no groups and no named AI-agent groups apply. Terms: no ToS page. /about: "Star Wars and all associated names are copyright Lucasfilm ltd. This project is open source and carries a BSD licence. All data has been freely collected from open sources such as Wookiepedia." /documentation: "No authentication is required to query and get data" and rate limiting "is currently limited to 10,000 API request per day" per IP. No AI, scraping or non-commercial clause.

## Quick summary

- **No scraping.** `GET https://swapi.dev/api/starships/?search=<name>` and `GET https://swapi.dev/api/people/?search=<name>` return JSON `{count, next, previous, results}`, 10 results per page. Records carry absolute URLs to related records (`pilots`, `films`, `starships`), one GET each.
- **Search is a case-insensitive substring match** (docs: "case-insensitive partial matches on the set of search fields"). Starship search fields are `name` and `model` (`?search=YT-1300` finds the Millennium Falcon); people search `name` only. No fuzzy spelling: `millenium` returns 0. Pick the exact name from `results` yourself.
- **Every value is a string.** `hyperdrive_rating` `"0.5"`, `crew` `"4"`, `cargo_capacity` `"100000"` (docs: "The maximum number of kilograms"). Others are `"342,953"`, `"30-165"`, `"unknown"`, `"n/a"`; block 1's `num()` handles them.
- **Browser:** CORS is open (`Access-Control-Allow-Origin: *` when the request carries an `Origin`), so `fetch()` works from any tab; block 1 uses a swapi.dev tab anyway. A browser opening `https://swapi.dev/api/` gets the Django REST framework HTML view; block 1 sends `Accept: application/json` and gets JSON. **Plain HTTP** needs no browser (blocks 2, 3).
- **Small, static dataset:** 36 starships and 82 people on 2026-11-10; the Falcon record was last `edited` 2014-12-20.

## What works

### 1. A starship's hyperdrive rating, crew and cargo capacity by name, plus pilots and films (browser)

Self-contained. `on_swapi_tab()` opens the API root once and later calls reuse the tab. `get()` returns parsed JSON on 200, backs off on 429/5xx and otherwise raises, so an error never looks like "no match".

```python
import json, time, urllib.parse

SHIP = "Millennium Falcon"  # starship name as a person would type it
FIELDS = ["hyperdrive_rating", "crew", "cargo_capacity", "passengers", "MGLT", "max_atmosphering_speed", "consumables",
          "model", "starship_class", "manufacturer", "length", "cost_in_credits"]

SITE = "https://swapi.dev"
API = SITE + "/api/"
PAUSE = 0.5  # docs: 10,000 requests per day per IP; keep calls serial anyway

def on_swapi_tab():
    """fetch() runs from a logged-out swapi.dev tab (the API root, rendered by Django REST framework). CORS is open
    too, but a same-origin tab keeps it simple. Reuse the tab if already there."""
    try:
        if js("location.origin") == SITE:
            return
    except Exception:
        pass
    new_tab(API)
    wait_for_load()
    if js("location.origin") != SITE or "Django REST framework" not in (js("document.title") or ""):
        raise RuntimeError(f"swapi.dev did not serve the API root (at {js('location.href')}, title {js('document.title')!r}): stop")

# js() gives up after a few seconds, so start the fetch, then poll for it.
START_JS = """(() => { window.__sw = window.__sw || {}; const id = String(Math.random()).slice(2); window.__sw[id] = null;
  fetch(%s, {credentials: 'omit', headers: {Accept: 'application/json'}})
    .then(async r => { window.__sw[id] = {status: r.status, type: r.headers.get('content-type'), text: await r.text()}; })
    .catch(e => { window.__sw[id] = {status: 0, type: '', text: String(e)}; });
  return id; })()"""
POLL_JS = """(() => { const v = window.__sw[%s]; if (v) delete window.__sw[%s]; return v; })()"""

def get(url, tries=3, timeout=60):
    """GET url from inside the tab -> parsed JSON. A missing id or page is HTTP 404 {"detail":"Not found."}.
    Backs off on 429/5xx, raises on anything else, so an error never looks like "no match"."""
    for attempt in range(tries):
        rid = json.dumps(js(START_JS % json.dumps(url)))
        t0 = time.time()
        while (r := js(POLL_JS % (rid, rid))) is None:
            if time.time() - t0 > timeout:
                raise RuntimeError(f"{url}: no answer after {timeout}s")
            time.sleep(0.3)
        time.sleep(PAUSE)
        if r["status"] == 200 and "json" in (r["type"] or ""):
            return json.loads(r["text"])
        if r["status"] not in (0, 429, 500, 502, 503, 504) or attempt == tries - 1:
            raise RuntimeError(f"{url}: HTTP {r['status']} {r['type']} {r['text'][:200]!r}; stopping")
        time.sleep(30)

def search(resource, q):
    """Every result of /api/<resource>/?search=q (case-insensitive substring of name, and of model for starships), all pages."""
    url, rows = API + f"{resource}/?search=" + urllib.parse.quote(q), []
    while url:
        d = get(url)
        rows += d["results"]
        url = d["next"]  # absolute https://swapi.dev/api/... URL, 10 results per page
    if len(rows) != d["count"]:
        raise RuntimeError(f"got {len(rows)} rows, count says {d['count']}")
    return rows

def num(s):
    """SWAPI numbers are strings: '0.5', '100000', '342,953', '30-165' (a range), 'unknown', 'n/a'. Returns float, (lo, hi) or None."""
    s = s.replace(",", "")
    if "-" in s:
        lo, hi = s.split("-")
        return float(lo), float(hi)
    try:
        return float(s)
    except ValueError:
        return None

on_swapi_tab()
hits = search("starships", SHIP)
print(f"starships ?search={SHIP!r}: {len(hits)} hit(s): {[h['name'] for h in hits]}")
exact = [h for h in hits if h["name"].lower() == SHIP.lower()]
if len(exact) != 1:
    raise RuntimeError(f"no single exact name match for {SHIP!r}; candidates {[h['name'] for h in hits]}")
s = exact[0]
print(f"\n{s['name']}  ({s['url']})")
for f in FIELDS:
    print(f"  {f:<23} {s[f]!r:<40} -> {num(s[f]) if f not in ('model', 'starship_class', 'manufacturer', 'consumables') else ''}")
pilots = [get(u)["name"] for u in s["pilots"]]
films = [get(u)["title"] for u in s["films"]]
print("  pilots:", pilots)
print("  films:", films)

# Cross-check from the people side: Han Solo's starships should include the same URL.
han = search("people", "Han Solo")
if len(han) != 1:
    raise RuntimeError(f"expected one 'Han Solo' person, got {[p['name'] for p in han]}")
print(f"\nHan Solo starships: {[get(u)['name'] for u in han[0]['starships']]}; includes {s['url']}: {s['url'] in han[0]['starships']}")
print(f"\nanswer: hyperdrive rating {s['hyperdrive_rating']}, crew {s['crew']}, cargo capacity {int(num(s['cargo_capacity'])):,} kg")
```

Output (from the run on 2026-11-10):

```text
starships ?search='Millennium Falcon': 1 hit(s): ['Millennium Falcon']

Millennium Falcon  (https://swapi.dev/api/starships/10/)
  hyperdrive_rating       '0.5'                                    -> 0.5
  crew                    '4'                                      -> 4.0
  cargo_capacity          '100000'                                 -> 100000.0
  passengers              '6'                                      -> 6.0
  MGLT                    '75'                                     -> 75.0
  max_atmosphering_speed  '1050'                                   -> 1050.0
  consumables             '2 months'                               ->
  model                   'YT-1300 light freighter'                ->
  starship_class          'Light freighter'                        ->
  manufacturer            'Corellian Engineering Corporation'      ->
  length                  '34.37'                                  -> 34.37
  cost_in_credits         '100000'                                 -> 100000.0
  pilots: ['Chewbacca', 'Han Solo', 'Lando Calrissian', 'Nien Nunb']
  films: ['A New Hope', 'The Empire Strikes Back', 'Return of the Jedi']

Han Solo starships: ['Millennium Falcon', 'Imperial shuttle']; includes https://swapi.dev/api/starships/10/: True

answer: hyperdrive rating 0.5, crew 4, cargo capacity 100,000 kg
```

### 2. Several ships, the odd number formats, and errors (plain HTTP, no browser)

Python standard library only, truthful User-Agent, serial at 0.5 s spacing.

```python
import json, time, urllib.error, urllib.parse, urllib.request

SHIPS = ["Millennium Falcon", "Death Star", "CR90 corvette", "X-wing", "millenium"]  # last one is misspelled on purpose
UA = {"User-Agent": "browser-harness-skill/1.0 (Python urllib)"}
API = "https://swapi.dev/api/"

def get(url):
    """GET -> parsed JSON. 404 = {"detail":"Not found."}, raised as LookupError. Waits 30 s once on 429/5xx or a network error, then stops."""
    for attempt in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                status, body = r.status, r.read()
        except urllib.error.HTTPError as e:
            status, body = e.code, e.read()
        except (urllib.error.URLError, TimeoutError) as e:  # DNS failure, reset, timeout: no HTTP status
            status, body = 0, str(e).encode()
        time.sleep(0.5)  # serial
        if status == 200:
            return json.loads(body)
        if status == 404:
            raise LookupError(f"HTTP 404 {body.decode()[:100]}")
        if status not in (0, 429, 500, 502, 503, 504) or attempt == 1:
            raise RuntimeError(f"{url}: HTTP {status} {body[:200]!r}; stopping")
        time.sleep(30)

def search(resource, q):
    url, rows = API + f"{resource}/?" + urllib.parse.urlencode({"search": q}), []
    while url:
        d = get(url)
        rows += d["results"]
        url = d["next"]
    if len(rows) != d["count"]:
        raise RuntimeError(f"got {len(rows)} rows, count says {d['count']}")
    return rows

def num(s):
    s = s.replace(",", "")
    if "-" in s:
        lo, hi = s.split("-")
        return float(lo), float(hi)
    try:
        return float(s)
    except ValueError:
        return None

print(f"{'query':<18} {'match':<18} {'hyperdrive':>10} {'crew':>9} {'-> parsed':>16} {'cargo kg':>15}  url")
for q in SHIPS:
    hits = [h for h in search("starships", q) if h["name"].lower() == q.lower()]
    if not hits:
        print(f"{q:<18} (no exact match; ?search= is a substring match, no fuzzy spelling)")
        continue
    s = hits[0]
    print(f"{q:<18} {s['name']:<18} {s['hyperdrive_rating']:>10} {s['crew']:>9} {str(num(s['crew'])):>16} {s['cargo_capacity']:>15}  {s['url']}")

star = search("starships", "star")  # matches name OR model, 10 per page
print(f"\n?search=star: {len(star)} starships over {-(-len(star) // 10)} pages, e.g. {[s['name'] for s in star[:4]]}")
for bad in ("starships/9999/", "starships/schema/", "starships/?page=99"):
    try:
        get(API + bad)
    except LookupError as e:
        print(f"{bad:<20} {e}")
```

Output (from the run on 2026-11-10):

```text
query              match              hyperdrive      crew        -> parsed        cargo kg  url
Millennium Falcon  Millennium Falcon         0.5         4              4.0          100000  https://swapi.dev/api/starships/10/
Death Star         Death Star                4.0   342,953         342953.0   1000000000000  https://swapi.dev/api/starships/9/
CR90 corvette      CR90 corvette             2.0    30-165    (30.0, 165.0)         3000000  https://swapi.dev/api/starships/2/
X-wing             X-wing                    1.0         1              1.0             110  https://swapi.dev/api/starships/12/
millenium          (no exact match; ?search= is a substring match, no fuzzy spelling)

?search=star: 15 starships over 2 pages, e.g. ['Star Destroyer', 'Death Star', 'Executor', 'Calamari Cruiser']
starships/9999/      HTTP 404 {"detail":"Not found."}
starships/schema/    HTTP 404 {"detail":"Not found."}
starships/?page=99   HTTP 404 {"detail":"Not found."}
```

### 3. Same API with curl

```bash
curl -sS --fail 'https://swapi.dev/api/starships/?search=millennium%20falcon' | python3 -c '
import json, sys
d = json.load(sys.stdin)
print("count", d["count"])
for s in d["results"]:
    print(s["name"], "|", s["model"], "| hyperdrive_rating", s["hyperdrive_rating"], "| crew", s["crew"], "| cargo_capacity", s["cargo_capacity"], "kg |", s["url"])
'
sleep 1
curl -sS --fail 'https://swapi.dev/api/people/?search=chewbacca' | python3 -c '
import json, sys
p = json.load(sys.stdin)["results"][0]
print(p["name"], "| starships", p["starships"])
'
sleep 1
curl -sS -o /dev/null -w 'robots.txt: HTTP %{http_code} %{content_type}\n' https://swapi.dev/robots.txt
```

Output (from the run on 2026-11-10):

```text
count 1
Millennium Falcon | YT-1300 light freighter | hyperdrive_rating 0.5 | crew 4 | cargo_capacity 100000 kg | https://swapi.dev/api/starships/10/
Chewbacca | starships ['https://swapi.dev/api/starships/10/', 'https://swapi.dev/api/starships/22/']
robots.txt: HTTP 403 application/xml
```

## Fields (starships)

| Field | Notes |
|---|---|
| `name`, `model`, `starship_class`, `manufacturer` | text; `name` and `model` are the search fields |
| `hyperdrive_rating` | docs: "The class of this starships hyperdrive"; string `"0.5"`, `"4.0"`, or `"unknown"` |
| `crew` | docs: "The number of personnel needed to run or pilot this starship"; `"4"`, `"342,953"`, `"30-165"` (range), `"unknown"` |
| `cargo_capacity` | docs: "The maximum number of kilograms that this starship can transport"; `"100000"`, `"unknown"` |
| `passengers`, `MGLT`, `max_atmosphering_speed`, `length`, `cost_in_credits` | strings; `passengers` can be `"n/a"`; `length` in meters, cost in Galactic Credits (docs) |
| `consumables` | free text, `"2 months"` |
| `pilots[]`, `films[]` | absolute URLs (`https://swapi.dev/api/people/13/`); fetch each for names |
| `url`, `created`, `edited` | the record's own URL (stable id) and ISO timestamps |

People records (`/api/people/`) carry `name`, `height`, `mass`, `birth_year`, `gender`, `homeworld`, `films[]`, `starships[]`, `vehicles[]`, all strings or URL lists.

## Gotchas

- **Substring, not exact.** `?search=star` returns 15 starships over 2 pages (name or model contains "star"). Always filter `results` for the exact name and follow `next` until it is `null`.
- **Numbers need parsing.** Across all 36 starships on 2026-11-10: `crew` had `279,144`, `30-165`, `342,953`, `47,060`, `unknown`; `passengers` had `843,342`, `n/a`, `unknown`; `hyperdrive_rating`, `cargo_capacity` and `MGLT` had `unknown`.
- **Errors are HTTP 404 `{"detail":"Not found."}`** for an unknown id and for a page past the end (`?page=99`). A search with no match is HTTP 200, `count: 0`.
- **CORS is open, but curl hides it.** `Access-Control-Allow-Origin: *` comes back only when the request sends an `Origin` header (`Vary: Origin`). On 2026-11-10 a `fetch()` from an example.com tab got HTTP 200.
- **http redirects.** `http://swapi.dev/...` answers a CloudFront 301 to https.
- **Tab marker.** The harness prefixes the tab title with a horse emoji; block 1 matches a substring of the title only.

## What does not work

- **`/api/<resource>/schema/`**: the documentation lists it, but `/api/starships/schema/` is HTTP 404 on 2026-11-10.
- **Fuzzy or misspelled names**: `millenium` (one n) gives 0 results. Try a shorter substring (`falcon`) and pick from the results.
- **Not tested:** `?format=wookiee` beyond one record (it returns translated keys and values, not JSON field names), planets, species, vehicles, films endpoints, rate-limit behaviour (10,000 per day per IP, never approached).
