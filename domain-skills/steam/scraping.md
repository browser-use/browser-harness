# Steam — Scraping & Data Extraction

Field-tested against store.steampowered.com on 2026-04-18. All code blocks validated with live requests.

## Fastest approach: App Details API (no auth, no browser)

The `appdetails` endpoint is the primary source for all game data. No API key, no cookies, no auth required. Returns clean JSON for any appid.

```python
import json
from helpers import http_get

def get_app(appid, cc="US"):
    """
    Fetch full game/DLC/software data by Steam appid.
    cc = ISO-3166 country code for correct regional pricing (default: US).
    Returns None if appid not found or no longer on Steam.
    """
    resp = http_get(
        f"https://store.steampowered.com/api/appdetails?appids={appid}&cc={cc}"
    )
    data = json.loads(resp)
    entry = data[str(appid)]
    if not entry["success"]:
        return None
    return entry["data"]

game = get_app(292030)   # The Witcher 3
# game["name"]               -> "The Witcher 3: Wild Hunt"
# game["steam_appid"]        -> 292030
# game["type"]               -> "game" | "dlc" | "demo" | "advertising" | "mod" | "video"
# game["required_age"]       -> 18    (int, 0 if no restriction)
# game["is_free"]            -> False
# game["short_description"]  -> plain-text one-liner
# game["about_the_game"]     -> HTML
# game["detailed_description"]-> HTML
# game["website"]            -> "https://www.thewitcher.com/witcher3"
# game["header_image"]       -> URL to 460x215px header image
# game["capsule_image"]      -> URL to smaller capsule image
# game["background"]         -> URL to store page background
# game["supported_languages"]-> HTML string with language list (use html.unescape())
# game["developers"]         -> ["CD PROJEKT RED"]
# game["publishers"]         -> ["CD PROJEKT RED"]
# game["platforms"]          -> {"windows": True, "mac": False, "linux": False}
# game["metacritic"]         -> {"score": 93, "url": "https://www.metacritic.com/..."}
# game["genres"]             -> [{"id": "3", "description": "RPG"}]
# game["categories"]         -> [{"id": 2, "description": "Single-player"}, ...]
# game["release_date"]       -> {"coming_soon": False, "date": "May 18, 2015"}
# game["dlc"]                -> [355880, 378649, ...]  (list of DLC appids)
# game["legal_notice"]       -> copyright text
# game["ratings"]            -> per-region rating board data (ESRB, PEGI, USK, ...)
# game["content_descriptors"]-> {"ids": [1, 5], "notes": "..."}
# game["recommendations"]    -> {"total": 812249}
# game["achievements"]       -> {"total": 78, "highlighted": [...]}
# game["support_info"]       -> {"url": "...", "email": "..."}
# game["pc_requirements"]    -> {"minimum": "<html>...", "recommended": "<html>..."}
# game["mac_requirements"]   -> same structure or []
# game["linux_requirements"] -> same structure or []
```

---

## Price overview

Prices are always in **cents** (integer). Use `final_formatted` for display.

```python
game = get_app(292030)
po = game.get("price_overview")
# po is None for free-to-play games (is_free=True)

if po:
    print(po["currency"])           # "USD"
    print(po["final"])              # 3999          (cents — $39.99)
    print(po["initial"])            # 3999          (original price in cents)
    print(po["discount_percent"])   # 0             (0–100)
    print(po["final_formatted"])    # "$39.99"       (always present, ready to display)
    print(po["initial_formatted"])  # ""             (EMPTY when not discounted!)
                                    # "$49.99"       (only set when discount_percent > 0)
```

**Critical**: `initial_formatted` is an empty string when `discount_percent == 0`.
Always use `final_formatted` for displaying current price.

```python
def price_display(game):
    """Returns (current_price_str, original_price_str_or_None, discount_pct)."""
    if game.get("is_free"):
        return ("Free", None, 0)
    po = game.get("price_overview")
    if not po:
        return ("N/A", None, 0)
    disc = po["discount_percent"]
    orig = po["initial_formatted"] if disc > 0 else None
    return (po["final_formatted"], orig, disc)

# Witcher3: ("$39.99", None, 0)
# Discounted game: ("$24.99", "$49.99", 50)
# Dota2: ("Free", None, 0)
```

### Regional pricing

Pass `cc=` (ISO-3166 country code) to get local currency:

```python
get_app(292030, cc="GB")["price_overview"]
# {"currency": "GBP", "initial": 2499, "final": 2499, ..., "final_formatted": "£24.99"}

get_app(292030, cc="DE")["price_overview"]
# {"currency": "EUR", "initial": 2999, "final": 2999, ..., "final_formatted": "29,99€"}
```

---

## Bulk / concurrent fetching

10 games in 0.54s with 5 workers — no rate-limit errors observed:

```python
import json
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

def fetch_game(appid, cc="US"):
    resp = http_get(
        f"https://store.steampowered.com/api/appdetails?appids={appid}&cc={cc}"
    )
    data = json.loads(resp)
    entry = data[str(appid)]
    return entry["data"] if entry["success"] else None

appids = [292030, 570, 413150, 427520, 730, 550, 220, 400, 218620, 105600]

with ThreadPoolExecutor(max_workers=5) as ex:
    games = list(ex.map(fetch_game, appids))
# Completed in ~0.54s
# games[i] is None if appid not found
```

**Confirmed field values for common appids:**
- `570` (Dota 2): `is_free=True`, `price_overview=None`, `required_age=0`
- `292030` (Witcher 3): `is_free=False`, `required_age=18`, `metacritic.score=93`
- `413150` (Stardew Valley): `is_free=False`, `required_age=0`, `metacritic=None`
- `427520` (Factorio): `is_free=False`, `required_age=0`

---

## Partial field fetch (filters=)

Fetch only specific fields to reduce payload size:

```python
# Price only (tiny response)
resp = http_get("https://store.steampowered.com/api/appdetails?appids=292030&filters=price_overview")
data = json.loads(resp)["292030"]["data"]
# data keys: ["price_overview"]

# Basic metadata (no price, no media)
resp = http_get("https://store.steampowered.com/api/appdetails?appids=292030&filters=basic")
# data keys: about_the_game, capsule_image, capsule_imagev5, detailed_description, dlc,
#            header_image, is_free, legal_notice, linux_requirements, mac_requirements,
#            name, pc_requirements, required_age, reviews, short_description,
#            steam_appid, supported_languages, type, website

# Multiple filters comma-separated
resp = http_get("https://store.steampowered.com/api/appdetails?appids=292030&filters=screenshots,price_overview")
# data keys: ["price_overview", "screenshots"]
```

---

## Media fields

### Screenshots

```python
game = get_app(292030)
for ss in game["screenshots"]:       # 18 screenshots for Witcher 3
    print(ss["id"])                  # 0, 1, 2, ...
    print(ss["path_thumbnail"])      # 600x338 JPEG URL
    print(ss["path_full"])           # 1920x1080 JPEG URL
```

### Movies / trailers

```python
for m in game["movies"]:             # 4 trailers for Witcher 3
    print(m["id"])                   # integer
    print(m["name"])                 # trailer title
    print(m["thumbnail"])            # thumbnail URL
    print(m["highlight"])            # bool — main trailer flag
    # m["webm"]  -> None (old format, mostly absent)
    # m["mp4"]   -> None (old format, mostly absent)
    # m["dash_av1"]  -> dash_av1 stream URL (present on modern entries)
    # m["dash_h264"] -> dash_h264 stream URL
    # m["hls_h264"]  -> HLS stream URL
```

---

## Ratings and content descriptors

The `ratings` dict contains per-region rating board data for mature games:

```python
game = get_app(292030)

# ESRB (North America)
esrb = game["ratings"].get("esrb", {})
esrb["rating"]          # "m" (lowercase)  -> M for Mature
esrb["descriptors"]     # "Blood and Gore\r\nIntense Violence\r\nNudity\r\n..."
esrb["use_age_gate"]    # "true" (string, not bool)
esrb["required_age"]    # "17" (string, not int)

# PEGI (Europe)
pegi = game["ratings"].get("pegi", {})
pegi["rating"]          # "18"
pegi["descriptors"]     # "Violence\r\nBad language"

# USK (Germany)
usk = game["ratings"].get("usk", {})
usk["rating"]           # "18"

# steam_germany (Germany digital-only classification)
sg = game["ratings"].get("steam_germany", {})
sg["rating"]            # "16"
sg["banned"]            # "0"  (1 = banned in Germany)

# igrs (Indonesia)
igrs = game["ratings"].get("igrs", {})
igrs["rating"]          # "BANNED" if banned there
igrs["banned"]          # "1"

# Other keys: oflc, nzoflc, kgrb, dejus, mda, fpb, csrr, crl
```

Content descriptor IDs (from `content_descriptors.ids`):
- `1` = Some Nudity or Sexual Content
- `5` = Frequent Violence or Gore

---

## Age-gated store pages

**The `appdetails` API completely bypasses age gates.** It returns full data for any game regardless of rating or age restriction — no cookies needed.

The **store webpage** (`store.steampowered.com/app/{appid}/`) redirects mature games to an age verification form:

```
GET https://store.steampowered.com/app/292030/
-> 302 -> https://store.steampowered.com/agecheck/app/292030/
```

To bypass the age gate on the store page, send the `birthtime` cookie:

```python
import urllib.request

def get_store_page(appid):
    """Fetch game store HTML page, bypassing age gate."""
    req = urllib.request.Request(
        f"https://store.steampowered.com/app/{appid}/",
        headers={
            "User-Agent": "Mozilla/5.0",
            "Cookie": "birthtime=631152001; lastagecheckage=1-January-1990"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        html = r.read().decode("utf-8", errors="replace")
        if "agecheck" in r.url:
            return None   # Age gate not bypassed
        return html
```

`birthtime=631152001` = January 1, 1990 in Unix time. Steam accepts any date before the current year minus the required age.

---

## Search

### storesearch API (title search, up to 10 results)

```python
import json, urllib.parse
from helpers import http_get

def search_games(term, cc="US", lang="english"):
    """
    Returns up to 10 matching apps/DLC/bundles.
    No pagination — always exactly 10 results max.
    """
    q = urllib.parse.quote(term)
    resp = http_get(
        f"https://store.steampowered.com/api/storesearch/?term={q}&l={lang}&cc={cc}"
    )
    data = json.loads(resp)
    return data["items"]

results = search_games("witcher")
# [
#   {"type": "app", "name": "The Witcher 3: Wild Hunt", "id": 292030,
#    "price": {"currency": "USD", "initial": 3999, "final": 3999},
#    "tiny_image": "https://...", "metascore": "93",
#    "platforms": {"windows": True, "mac": False, "linux": False},
#    "streamingvideo": False},
#   {"type": "sub", ...},  # bundles have type="sub"
#   ...
# ]
```

**Search result fields:**
- `id` — appid (or subid for bundles)
- `type` — `"app"` | `"sub"` (bundle)
- `name` — game title
- `price` — `{"currency": "USD", "initial": cents, "final": cents}` — `None` for F2P
- `metascore` — string e.g. `"93"`, `"0"` if no score
- `platforms` — `{"windows": bool, "mac": bool, "linux": bool}`
- `tiny_image` — 231x87px capsule image URL
- `streamingvideo` — bool

**Note:** `price` in search results has only `initial` and `final` — no `discount_percent` or `formatted` strings. Use `appdetails` for full pricing.

---

## Review scores and user reviews

```python
import json, urllib.parse
from helpers import http_get

def get_reviews(appid, num=10, language="english", filter="recent",
                review_type="all", purchase_type="all", cursor="*"):
    """
    filter: "recent" | "updated" | "all"
    review_type: "all" | "positive" | "negative"
    purchase_type: "all" | "steam" | "non_steam_purchase"
    language: "english" | "all" | ISO code
    cursor: use returned cursor for next page (URL-encode it)
    """
    encoded_cursor = urllib.parse.quote(cursor)
    resp = http_get(
        f"https://store.steampowered.com/appreviews/{appid}"
        f"?json=1&num_per_page={num}&language={language}"
        f"&filter={filter}&review_type={review_type}"
        f"&purchase_type={purchase_type}&cursor={encoded_cursor}"
    )
    return json.loads(resp)

result = get_reviews(292030, num=5, language="english")

# result["success"]          -> 1 (int, not bool)
# result["cursor"]           -> "AoJ4rq..."  (base64, URL-encode for next page)
# result["query_summary"]["review_score"]      -> 9      (0–9 score)
# result["query_summary"]["review_score_desc"] -> "Overwhelmingly Positive"
# result["query_summary"]["total_positive"]    -> 226883
# result["query_summary"]["total_negative"]    -> 7499
# result["query_summary"]["total_reviews"]     -> 234382  (steam purchase only)
# result["reviews"]          -> list of review objects
```

**Review score descriptions (review_score int to string):**

| Score | Description |
|-------|-------------|
| 9 | Overwhelmingly Positive |
| 8 | Very Positive |
| 7 | Mostly Positive |
| 6 | Positive (Mixed) |
| 5 | Mixed |
| 4 | Mostly Negative |
| 3 | Negative |
| 2 | Mostly Negative |
| 1 | Overwhelmingly Negative |
| 0 | No reviews |

**Confirmed scores:** Witcher 3 = 9, Counter-Strike 2 = 8, Stardew Valley = 9, Factorio = 9.

### Review object fields

```python
review = result["reviews"][0]
review["recommendationid"]           # "221423937"  — unique review ID
review["voted_up"]                   # True/False  — positive/negative
review["votes_up"]                   # 213         — helpful votes
review["votes_funny"]                # 66
review["weighted_vote_score"]        # 0.8405...   — Steam's helpfulness score
review["comment_count"]              # 20
review["steam_purchase"]             # True
review["received_for_free"]          # False
review["written_during_early_access"]# False
review["timestamp_created"]          # 1774209092  (Unix timestamp)
review["timestamp_updated"]          # Unix timestamp
review["language"]                   # "english"
review["review"]                     # review text
review["app_release_date"]           # Unix timestamp of game release

review["author"]["steamid"]              # "76561198..."
review["author"]["personaname"]          # display name
review["author"]["num_games_owned"]      # 1039
review["author"]["num_reviews"]          # 180
review["author"]["playtime_forever"]     # 1146  (minutes total)
review["author"]["playtime_last_two_weeks"] # minutes in last 2 weeks
review["author"]["playtime_at_review"]   # minutes at time of review
review["author"]["last_played"]          # Unix timestamp
```

### Cursor-based pagination

```python
import urllib.parse, json
from helpers import http_get

def get_all_reviews(appid, max_pages=5, num_per_page=100, language="all"):
    """Paginate through reviews using cursor."""
    cursor = "*"
    all_reviews = []
    for _ in range(max_pages):
        resp = http_get(
            f"https://store.steampowered.com/appreviews/{appid}"
            f"?json=1&num_per_page={num_per_page}&language={language}"
            f"&filter=recent&cursor={urllib.parse.quote(cursor)}"
        )
        data = json.loads(resp)
        batch = data.get("reviews", [])
        if not batch:
            break
        all_reviews.extend(batch)
        cursor = data.get("cursor", "")
        if not cursor:
            break
    return all_reviews
```

---

## Featured games

### Featured items (rotating store front)

```python
import json
from helpers import http_get

data = json.loads(http_get("https://store.steampowered.com/api/featured/"))
# data["large_capsules"]  -> 1-3 hero banner items
# data["featured_win"]    -> 10 featured items for Windows
# data["featured_mac"]    -> macOS featured
# data["featured_linux"]  -> Linux featured
# data["status"]          -> 1

item = data["featured_win"][0]
# item["id"]                -> appid
# item["name"]              -> game title
# item["discounted"]        -> bool
# item["discount_percent"]  -> 0-100
# item["original_price"]    -> cents
# item["final_price"]       -> cents
# item["currency"]          -> "USD"
# item["windows_available"] -> bool
# item["mac_available"]     -> bool
# item["linux_available"]   -> bool
# item["large_capsule_image"] -> URL
# item["small_capsule_image"] -> URL
# item["header_image"]      -> URL
# item["controller_support"] -> "full" | "partial" | ""
```

### Featured categories (top sellers, specials, new releases, coming soon)

```python
data = json.loads(http_get("https://store.steampowered.com/api/featuredcategories/"))

# Named sections (most useful):
specials    = data["specials"]["items"]      # 10 on-sale games
top_sellers = data["top_sellers"]["items"]  # 10 top sellers
new_releases= data["new_releases"]["items"] # 30 new releases
coming_soon = data["coming_soon"]["items"]  # 10 upcoming games

# Numbered keys "0" through "7" are spotlight banners (deals/events)

item = top_sellers[0]
# item["id"]                   -> appid
# item["name"]                 -> game title
# item["discounted"]           -> bool
# item["discount_percent"]     -> 0-100
# item["original_price"]       -> cents (None for upcoming games)
# item["final_price"]          -> cents (0 for upcoming)
# item["currency"]             -> "USD"
# item["discount_expiration"]  -> Unix timestamp (present for active sales)
# item["windows_available"]    -> bool
# item["mac_available"]        -> bool
# item["linux_available"]      -> bool
# item["header_image"]         -> URL
```

---

## App list (all Steam apps)

The `ISteamApps/GetAppList` API endpoint (v1, v2, v0001, v0002) currently returns **HTTP 404** from `api.steampowered.com` as of 2026-04-18. The endpoint is effectively retired without a Steamworks API key.

**Workaround:** Use the featured categories and search APIs to discover appids, then batch-fetch via `appdetails`.

```python
# Discover appids from top sellers + new releases
import json
from helpers import http_get

def get_all_store_appids():
    data = json.loads(http_get("https://store.steampowered.com/api/featuredcategories/"))
    appids = set()
    for key in ["specials", "top_sellers", "new_releases", "coming_soon"]:
        for item in data.get(key, {}).get("items", []):
            appids.add(item["id"])
    for key in ["featured_win", "featured_mac", "featured_linux"]:
        for item in data.get(key, []):
            appids.add(item["id"])
    return sorted(appids)

# Returns ~50 store-front appids (enough to seed further discovery)
```

---

## Rate limits

Steam's public APIs are generous. Confirmed during testing:

- **10 sequential requests in 1.59s** — all HTTP 200, no throttling
- **10 concurrent requests (5 workers) in 0.54s** — all succeeded
- **No `Retry-After` header** observed at any concurrency level

Practical limits (undocumented, inferred from community reports):
- ~200 requests/5 minutes per IP to `appdetails` before soft throttling (returns `success: false`)
- Review API is more restrictive — keep to ~50 requests/minute

---

## Gotchas

**`success: false` with no data field** — When an appid is invalid, removed, or unreleased, the response is `{"999999": {"success": false}}` with no `data` key. Always check `entry["success"]` before accessing `entry["data"]`.

```python
entry = json.loads(resp)[str(appid)]
if not entry["success"]:
    return None   # game removed or never existed
game = entry["data"]
```

**Multiple appids in one call — not supported** — `appids=292030,570` returns HTTP 400. The API only accepts a single appid per call. Use `ThreadPoolExecutor` for bulk fetching.

**`price_overview` is `None` for free games** — When `is_free=True`, the `price_overview` key is absent or `None`. Never index `game["price_overview"]["final"]` without a None check.

**`initial_formatted` is empty string when not on sale** — When `discount_percent == 0`, `initial_formatted` is `""`. Only `final_formatted` is reliably present and non-empty. Use `final_formatted` for display in all cases.

**Store page age gate** — `store.steampowered.com/app/{appid}/` redirects mature games to `/agecheck/app/{appid}/`. The `appdetails` API completely bypasses this — no cookies needed. For browser-based scraping of the store page, send `Cookie: birthtime=631152001; lastagecheckage=1-January-1990`.

**`storesearch` always returns ≤ 10 results** — No pagination. `total` in the response is always 10, not the true result count. For finding specific games, this is sufficient. For catalog browsing, use `appdetails` with known appids.

**`metascore` is string `"0"` in search results, int `93` in appdetails** — Inconsistent types. In `storesearch` results, `metascore` is a string (e.g. `"93"`, `"0"`). In `appdetails`, `metacritic` is a dict `{"score": 93, "url": "..."}` or absent entirely. Always `int()` the storesearch value.

**`appdetails` returns `type: "dlc"` for DLC** — Check `game["type"]` before treating every appid as a standalone game. Type values: `"game"`, `"dlc"`, `"demo"`, `"advertising"`, `"mod"`, `"video"`.

**`ratings` dict uses string booleans** — `use_age_gate` and `required_age` inside `ratings[board]` are strings (`"true"`, `"17"`), not native types. `banned` is also a string `"0"` or `"1"`.

**`ISteamApps/GetAppList` is dead** — HTTP 404 for v1, v2, v0001, v0002 endpoints as of 2026-04-18. Use store front APIs and search to discover appids instead.

**`supported_languages` is HTML** — The field contains escaped HTML like `English<strong>*</strong>, French`. Starred languages have full audio. Use `html.unescape()` and strip tags to get a clean list.

**`release_date.date` is a locale string, not ISO** — Value is `"May 18, 2015"` not `"2015-05-18"`. Parse with `datetime.strptime(d, "%B %d, %Y")` or use regex.

**Review `purchase_type` changes total counts** — `purchase_type=all` includes reviews from non-Steam purchases (physical, Humble, etc.). `purchase_type=steam` is Steam-only. Witcher 3 example: `all`=802,072 reviews, `steam`=234,385.

**Currency requires `cc=` param** — Without `cc=`, you get USD by default. Pass `cc=GB` for GBP, `cc=DE` for EUR, etc. Country codes are ISO-3166 (2-letter, uppercase).
