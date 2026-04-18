# HowLongToBeat — Scraping & Data Extraction

Field-tested against howlongtobeat.com on 2026-04-18. All code blocks validated with live requests.

## Do this first

**Use the search API — it returns structured JSON with all completion times in one POST call.**

HLTB runs a token-gated POST endpoint at `/api/find`. You must first fetch a session token from `/api/find/init`, then include it in the search request. Both steps are plain HTTP — no browser required.

```python
import json, re, urllib.request, time
from helpers import http_get

UA = "Mozilla/5.0"

def get_token():
    """Fetch a fresh session token. Token encodes IP+UA+timestamp, reusable for ~15 min."""
    url = f"https://howlongtobeat.com/api/find/init?t={int(time.time()*1000)}"
    data = http_get(url, headers={"Referer": "https://howlongtobeat.com/"})
    return json.loads(data)  # {token, hpKey, hpVal}

def search_hltb(title, size=20, page=1, token_data=None):
    """
    Search HLTB for games. Returns raw API dict:
    {count, pageCurrent, pageTotal, pageSize, data: [...]}
    token_data can be reused across searches (fetch once, use many times).
    """
    if token_data is None:
        token_data = get_token()
    hp_key, hp_val = token_data['hpKey'], token_data['hpVal']
    payload = {
        "searchType": "games",
        "searchTerms": title.split(),
        "searchPage": page,
        "size": size,
        "searchOptions": {
            "games": {
                "userId": 0, "platform": "", "sortCategory": "popular",
                "rangeCategory": "main", "rangeTime": {"min": None, "max": None},
                "gameplay": {"perspective": "", "flow": "", "genre": "", "difficulty": ""},
                "rangeYear": {"min": "", "max": ""}, "modifier": ""
            },
            "users": {"sortCategory": "postcount"},
            "lists": {"sortCategory": "follows"},
            "filter": "", "sort": 0, "randomizer": 0
        },
        "useCache": True,
        hp_key: hp_val      # honeypot field — key and value vary per token
    }
    req = urllib.request.Request(
        "https://howlongtobeat.com/api/find",
        data=json.dumps(payload).encode(),
        headers={
            "User-Agent": UA,
            "Content-Type": "application/json",
            "Origin": "https://howlongtobeat.com",
            "Referer": "https://howlongtobeat.com/",
            "x-auth-token": token_data['token'],
            "x-hp-key": hp_key,
            "x-hp-val": hp_val,
        },
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

# Usage
tok = get_token()

result = search_hltb("elden ring", token_data=tok, size=3)
for g in result['data']:
    print(g['game_id'], g['game_name'], g['release_world'])
    print(f"  Main: {g['comp_main']/3600:.1f}h  +Extras: {g['comp_plus']/3600:.1f}h  100%: {g['comp_100']/3600:.1f}h")

# Confirmed output (2026-04-18):
# 68151 Elden Ring 2022
#   Main: 60.0h  +Extras: 101.2h  100%: 135.5h
# 160589 Elden Ring: Nightreign 2025
#   Main: 28.1h  +Extras: 40.1h  100%: 66.9h
# 139385 Elden Ring: Shadow of the Erdtree 2024
#   Main: 25.7h  +Extras: 39.0h  100%: 51.1h
```

Token is reusable — fetch it once and pass it to multiple `search_hltb()` calls. No need to re-fetch per search.

---

## Fastest approach: search + parse in one helper

```python
import json, re, urllib.request, time
from helpers import http_get

UA = "Mozilla/5.0"

def hltb_search(title, size=5):
    """One-shot: get token + search, return list of dicts with hours."""
    url = f"https://howlongtobeat.com/api/find/init?t={int(time.time()*1000)}"
    tok = json.loads(http_get(url, headers={"Referer": "https://howlongtobeat.com/"}))
    hp_key, hp_val = tok['hpKey'], tok['hpVal']
    payload = {
        "searchType": "games", "searchTerms": title.split(), "searchPage": 1, "size": size,
        "searchOptions": {
            "games": {"userId": 0, "platform": "", "sortCategory": "popular",
                      "rangeCategory": "main", "rangeTime": {"min": None, "max": None},
                      "gameplay": {"perspective": "", "flow": "", "genre": "", "difficulty": ""},
                      "rangeYear": {"min": "", "max": ""}, "modifier": ""},
            "users": {"sortCategory": "postcount"}, "lists": {"sortCategory": "follows"},
            "filter": "", "sort": 0, "randomizer": 0
        },
        "useCache": True, hp_key: hp_val
    }
    req = urllib.request.Request(
        "https://howlongtobeat.com/api/find", data=json.dumps(payload).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/json",
                 "Origin": "https://howlongtobeat.com", "Referer": "https://howlongtobeat.com/",
                 "x-auth-token": tok['token'], "x-hp-key": hp_key, "x-hp-val": hp_val},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())

    def h(secs):
        return round(secs / 3600, 1) if secs else None

    return [
        {
            "game_id":      g["game_id"],
            "name":         g["game_name"],
            "type":         g["game_type"],         # "game" | "dlc" | "expansion" | "hack"
            "year":         g["release_world"],
            "platforms":    g["profile_platform"],
            "main":         h(g["comp_main"]),       # Main Story hours (polled average)
            "main_plus":    h(g["comp_plus"]),       # Main + Extras hours
            "completionist":h(g["comp_100"]),        # Completionist hours
            "all_styles":   h(g["comp_all"]),        # All playstyles combined
            "main_count":   g["comp_main_count"],    # Number of submissions
            "plus_count":   g["comp_plus_count"],
            "comp_count":   g["comp_100_count"],
            "review_score": g["review_score"],       # 0–100
            "image_url":    f"https://howlongtobeat.com/games/{g['game_image']}",
            "page_url":     f"https://howlongtobeat.com/game/{g['game_id']}",
        }
        for g in data["data"]
    ]

# Verified results (2026-04-18):
print(hltb_search("the witcher 3")[0])
# {'game_id': 10270, 'name': 'The Witcher 3: Wild Hunt', 'type': 'game', 'year': 2015,
#  'main': 51.6, 'main_plus': 103.8, 'completionist': 174.4, 'all_styles': 103.8,
#  'main_count': 2681, 'plus_count': 6708, 'comp_count': 2327, 'review_score': 93, ...}

print(hltb_search("gone home")[0])
# {'game_id': 4010, 'name': 'Gone Home', 'main': 2.0, 'main_plus': 2.5, 'completionist': 3.1, ...}
```

---

## Game detail page (full stat breakdown, speedrun data, per-platform times)

When you have a `game_id`, fetch the game page and extract `__NEXT_DATA__` for the complete dataset — includes median/avg/low/high times, speedrun data, co-op/multiplayer times, and per-platform breakdowns.

```python
import json, re
from helpers import http_get

def get_game_detail(game_id):
    """
    Fetch complete game data from the HLTB game page.
    Returns pageProps['game']['data'] with keys: 'game', 'individuality', 'relationships'.
    """
    html = http_get(f"https://howlongtobeat.com/game/{game_id}")
    nd = json.loads(re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
    ).group(1))
    return nd['props']['pageProps']['game']['data']

data = get_game_detail(10270)   # Witcher 3
g = data['game'][0]

# Core completion times (all in seconds — divide by 3600 for hours)
print(g['comp_main'] / 3600)       # 51.6  — Main Story (polled avg)
print(g['comp_main_med'] / 3600)   # 50.0  — Main Story median
print(g['comp_main_l'] / 3600)     # 32.7  — Main Story low
print(g['comp_main_h'] / 3600)     # 85.8  — Main Story high
print(g['comp_main_count'])        # 2681  — submission count

print(g['comp_plus'] / 3600)       # 103.8 — Main + Extras
print(g['comp_100'] / 3600)        # 174.4 — Completionist
print(g['comp_all'] / 3600)        # 103.8 — All Styles

# Speedrun times
print(g['comp_lvl_spd'])           # 1 if speedrun data exists, 0 if not
print(g['comp_speed'] / 3600)      # 19.2  — any% (polled avg)
print(g['comp_speed_min'] / 3600)  # 3.2   — fastest submission
print(g['comp_speed_max'] / 3600)  # 30.0  — slowest speedrun
print(g['comp_speed_count'])       # 15    — speedrun submissions

print(g['comp_speed100'] / 3600)   # 59.4  — 100% speedrun
print(g['comp_speed100_count'])    # 4

# Multiplayer / co-op invested time
print(g['comp_lvl_co'])            # 1 if co-op data exists
print(g['comp_lvl_mp'])            # 1 if multiplayer data exists
print(g['invested_co'] / 3600)     # hours in co-op mode
print(g['invested_mp'] / 3600)     # hours in competitive multiplayer
print(g['invested_co_count'])      # submission count

# Metadata
print(g['profile_dev'])            # "CD Projekt RED"
print(g['profile_pub'])            # "CD Projekt, Warner Bros..."
print(g['profile_platform'])       # "Nintendo Switch, PC, PlayStation 4, ..."
print(g['profile_genre'])          # "Third-Person, Action, Open World, Role-Playing"
print(g['profile_steam'])          # 292030  — Steam App ID (0 if not on Steam)
print(g['release_world'])          # "2015-05-19"
print(g['rating_esrb'])            # "M"
print(g['review_score'])           # 93  (0–100)
print(g['count_comp'])             # 26007  — times completed
print(g['count_backlog'])          # 31083

# Per-platform breakdown (individuality)
for plat in data['individuality']:
    print(plat['platform'],
          int(plat['comp_main'])/3600,    # main hours
          int(plat['comp_plus'])/3600,    # +extras hours
          int(plat['comp_100'])/3600,     # 100% hours
          plat['count_comp'])             # completions on this platform
# Example:
# Nintendo Switch  57.0h  112.3h  194.9h  236
# PC, PS4, Xbox One  52.9h  110.0h  179.4h  11136
# PS5, Xbox Series X/S  52.1h  92.5h  168.8h  343

# DLC / expansion completion times
for rel in data['relationships'][:3]:
    print(rel['game_id'], rel['game_name'], rel['game_type'],
          rel['comp_main']/3600 if rel['comp_main'] else None)
```

---

## Common workflows

### Quick lookup: name → completion times

```python
import json, re, urllib.request, time
from helpers import http_get

UA = "Mozilla/5.0"

def get_times(title):
    """Return Main/+Extras/100% hours for the top search match."""
    tok_url = f"https://howlongtobeat.com/api/find/init?t={int(time.time()*1000)}"
    tok = json.loads(http_get(tok_url, headers={"Referer": "https://howlongtobeat.com/"}))
    hp_key, hp_val = tok['hpKey'], tok['hpVal']
    payload = {
        "searchType": "games", "searchTerms": title.split(), "searchPage": 1, "size": 1,
        "searchOptions": {
            "games": {"userId": 0, "platform": "", "sortCategory": "popular",
                      "rangeCategory": "main", "rangeTime": {"min": None, "max": None},
                      "gameplay": {"perspective": "", "flow": "", "genre": "", "difficulty": ""},
                      "rangeYear": {"min": "", "max": ""}, "modifier": ""},
            "users": {"sortCategory": "postcount"}, "lists": {"sortCategory": "follows"},
            "filter": "", "sort": 0, "randomizer": 0
        },
        "useCache": True, hp_key: hp_val
    }
    req = urllib.request.Request(
        "https://howlongtobeat.com/api/find", data=json.dumps(payload).encode(),
        headers={"User-Agent": UA, "Content-Type": "application/json",
                 "Origin": "https://howlongtobeat.com", "Referer": "https://howlongtobeat.com/",
                 "x-auth-token": tok['token'], "x-hp-key": hp_key, "x-hp-val": hp_val},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    if not data['data']:
        return None
    g = data['data'][0]
    h = lambda s: round(s/3600, 1) if s else None
    return {
        "id": g['game_id'], "name": g['game_name'],
        "main": h(g['comp_main']), "main_plus": h(g['comp_plus']),
        "completionist": h(g['comp_100'])
    }

# Verified:
print(get_times("celeste"))
# {'id': 42818, 'name': 'Celeste', 'main': 8.3, 'main_plus': 14.6, 'completionist': 39.2}
print(get_times("stardew valley"))
# {'id': 34716, 'name': 'Stardew Valley', 'main': 53.4, 'main_plus': 94.6, 'completionist': 171.5}
print(get_times("hades"))
# {'id': 62941, 'name': 'Hades', 'main': 23.4, 'main_plus': 48.5, 'completionist': 95.0}
```

### Paginated search (all results for a query)

`count` = total matches, `pageTotal` = total pages with current `size`. The same token works across all pages.

```python
def search_all_pages(title, size=20):
    """Yield every search result for a query across all pages."""
    tok_url = f"https://howlongtobeat.com/api/find/init?t={int(time.time()*1000)}"
    tok = json.loads(http_get(tok_url, headers={"Referer": "https://howlongtobeat.com/"}))
    hp_key, hp_val = tok['hpKey'], tok['hpVal']

    page = 1
    while True:
        payload = {
            "searchType": "games", "searchTerms": title.split(),
            "searchPage": page, "size": size,
            "searchOptions": {
                "games": {"userId": 0, "platform": "", "sortCategory": "popular",
                          "rangeCategory": "main", "rangeTime": {"min": None, "max": None},
                          "gameplay": {"perspective": "", "flow": "", "genre": "", "difficulty": ""},
                          "rangeYear": {"min": "", "max": ""}, "modifier": ""},
                "users": {"sortCategory": "postcount"}, "lists": {"sortCategory": "follows"},
                "filter": "", "sort": 0, "randomizer": 0
            },
            "useCache": True, hp_key: hp_val
        }
        req = urllib.request.Request(
            "https://howlongtobeat.com/api/find", data=json.dumps(payload).encode(),
            headers={"User-Agent": UA, "Content-Type": "application/json",
                     "Origin": "https://howlongtobeat.com", "Referer": "https://howlongtobeat.com/",
                     "x-auth-token": tok['token'], "x-hp-key": hp_key, "x-hp-val": hp_val},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read().decode())
        yield from data['data']
        if page >= data['pageTotal']:
            break
        page += 1

# "mario" returns 308 results across 16 pages (size=20)
mario_games = list(search_all_pages("mario", size=20))
print(len(mario_games))   # 308
```

### Batch lookup by game ID (parallel)

```python
import json, re, urllib.request
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

def fetch_game(game_id):
    html = http_get(f"https://howlongtobeat.com/game/{game_id}")
    nd = json.loads(re.search(
        r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.DOTALL
    ).group(1))
    g = nd['props']['pageProps']['game']['data']['game'][0]
    return {
        "id": g['game_id'], "name": g['game_name'],
        "main": round(g['comp_main']/3600, 1) if g['comp_main'] else None,
        "main_plus": round(g['comp_plus']/3600, 1) if g['comp_plus'] else None,
        "completionist": round(g['comp_100']/3600, 1) if g['comp_100'] else None,
    }

ids = [10270, 68151, 42818, 26803, 34716]   # Witcher3, Elden Ring, Celeste, DS3, Stardew
with ThreadPoolExecutor(max_workers=5) as ex:
    results = list(ex.map(fetch_game, ids))

for r in results:
    print(f"[{r['id']}] {r['name']}: {r['main']}h / {r['main_plus']}h / {r['completionist']}h")

# Confirmed output:
# [10270] The Witcher 3: Wild Hunt: 51.6h / 103.8h / 174.4h
# [68151] Elden Ring: 60.0h / 101.2h / 135.5h
# [42818] Celeste: 8.3h / 14.6h / 39.2h
# [26803] Dark Souls III: 31.2h / 48.4h / 100.5h
# [34716] Stardew Valley: 53.4h / 94.6h / 171.5h
```

---

## Search response field reference

Every item in `data[]` from `/api/find`:

| Field | Type | Description |
|-------|------|-------------|
| `game_id` | int | HLTB internal game ID |
| `game_name` | str | Full game title |
| `game_alias` | str | Alternate title / edition name |
| `game_type` | str | `"game"` \| `"dlc"` \| `"expansion"` \| `"hack"` |
| `game_image` | str | Image filename → `https://howlongtobeat.com/games/{game_image}` |
| `release_world` | int | Release year (just the year integer, not a date) |
| `profile_platform` | str | Comma-separated platform list |
| `comp_main` | int | Main Story seconds (polled average), 0 if no data |
| `comp_plus` | int | Main + Extras seconds |
| `comp_100` | int | Completionist seconds |
| `comp_all` | int | All Styles combined seconds |
| `comp_main_count` | int | Submission count for Main Story |
| `comp_plus_count` | int | Submission count for Main + Extras |
| `comp_100_count` | int | Submission count for Completionist |
| `comp_all_count` | int | Total submissions across all categories |
| `comp_lvl_sp` | int | 1 if single-player data exists |
| `comp_lvl_co` | int | 1 if co-op data exists |
| `comp_lvl_mp` | int | 1 if multiplayer data exists |
| `invested_co` | int | Average co-op time in seconds |
| `invested_mp` | int | Average multiplayer time in seconds |
| `count_comp` | int | Total completions logged |
| `count_backlog` | int | Users with game in backlog |
| `count_playing` | int | Currently playing |
| `count_speedrun` | int | Speedrun entries |
| `count_review` | int | Review count |
| `review_score` | int | Community review score 0–100 |
| `profile_popular` | int | Popularity rank |

Additional fields in `__NEXT_DATA__` game page only:

| Field | Description |
|-------|-------------|
| `comp_main_med/avg/l/h` | Median / average / low / high for main time |
| `comp_plus_med/avg/l/h` | Same for Main + Extras |
| `comp_100_med/avg/l/h` | Same for Completionist |
| `comp_speed` | Speedrun any% average seconds |
| `comp_speed_min/max/med` | Speedrun spread |
| `comp_speed100` | 100% speedrun average |
| `comp_speed_count` | Speedrun submission count |
| `comp_lvl_spd` | 1 if speedrun data exists |
| `profile_dev` | Developer name |
| `profile_pub` | Publisher name |
| `profile_genre` | Comma-separated genres |
| `profile_steam` | Steam App ID (0 if not on Steam) |
| `release_world` | Full release date `"YYYY-MM-DD"` |
| `rating_esrb` | ESRB rating string (may be empty) |
| `count_replay` | Times replayed |
| `count_total` | Total user entries |

---

## Anti-bot measures

- **Cloudflare** is present (confirmed by `CF-Ray` response header), but does not block plain HTTP with a browser UA.
- **Token system**: Every search requires a fresh token from `/api/find/init`. Token encodes `timestamp::IP|UA|hpKey|hmacHash`. The server validates that the UA used to fetch the token matches the UA used in the search POST.
- **Honeypot field**: `hpKey` and `hpVal` from the init response must appear as a top-level field in the POST body (e.g., `{"ign_7671546b": "a6679ea54598d502", ...}`). The key name rotates per request.
- **Required headers on search POST**: `Origin: https://howlongtobeat.com` AND `Referer: https://howlongtobeat.com/` — missing either causes HTTP 403 or 404. `x-auth-token`, `x-hp-key`, `x-hp-val` are also required.
- **Required header on init GET**: `Referer: https://howlongtobeat.com/` — missing causes HTTP 403.
- **Token reuse**: A single token works for multiple searches and multiple pages. No per-request token fetch needed.
- **No CAPTCHA** observed during testing with standard UA strings.
- **Rate limits**: Not triggered during testing (token fetches + 10+ searches sequentially). Fetching many game pages in parallel (5 workers) worked without 429s.

---

## Gotchas

- **Completion times are in seconds** — all `comp_*` fields are integer seconds. Divide by 3600 for hours. `0` means no data (not 0 hours).

- **`release_world` is a year int in search, a full date in game page** — in the `/api/find` response, `release_world` is an integer year (e.g., `2015`). In `__NEXT_DATA__` on the game page, it's `"2015-05-19"`.

- **UA fingerprinting** — the token from `/api/find/init` encodes the User-Agent. The search POST must use the identical UA that fetched the token, or you'll get HTTP 403. Since `http_get` sends `Mozilla/5.0`, use that same string for the search POST.

- **Honeypot key name rotates** — `hpKey` is something like `ign_7671546b` (changes each token fetch). Always read it from the init response and use it dynamically. Never hardcode it.

- **Both `x-hp-key`/`x-hp-val` headers AND the body field are required** — the server checks the request headers (`x-hp-key`, `x-hp-val`) against the dynamic key in the POST body. If either is wrong or missing, you get HTTP 404 (wrong body value) or HTTP 403 (missing/wrong header).

- **`game_type` in search results** — can be `"game"`, `"dlc"`, `"expansion"`, or `"hack"`. Search results mix these by default. Filter with `if g['game_type'] == 'game'` if you only want base games.

- **Games with no submission data** — `comp_main`, `comp_plus`, `comp_100` are `0` (not `None`) when no users have submitted times. Always check `if g['comp_main']:` before dividing.

- **`individuality` (per-platform) data** — available only in `__NEXT_DATA__` on the game page, not in search results. `comp_main` etc. are strings, not ints, in this sub-object — cast with `int(plat['comp_main'])`.

- **`profile_platform` in search** — a comma-separated string that HLTB displays. Not structured. Use game page `individuality` for per-platform time breakdowns.

- **Token expiry** — if a long-running loop gets HTTP 403 with `{"error":"Session expired or invalid fingerprint"}`, call `get_token()` again and retry. Token lifetime appears to be ~15 minutes based on the timestamp embedded in the decoded value.

- **No slug-based URLs** — HLTB uses integer `game_id` for all game pages, not slugs. There is no `title-to-slug` mapping; use search to find the `game_id` first.

- **`sortCategory` options** — `"popular"` ranks by community engagement (best for "top result = intended game"). `"name"` sorts alphabetically. Other values (`"madnessTime"`, `"mainThenExtras"`) exist but return same results as `"name"` in testing.
