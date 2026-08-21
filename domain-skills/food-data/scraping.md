# Food Data — Scraping & Nutrition Lookup

Two free APIs cover almost every food data use case:

| API | Best for | Auth | Rate limit |
|-----|----------|------|------------|
| **USDA FoodData Central** (`api.nal.usda.gov/fdc`) | Authoritative nutrient data (USDA Foundation/SR Legacy), ingredient search | Free key (register at `fdc.nal.usda.gov`) or `DEMO_KEY` | `DEMO_KEY`: 30 req/hr, 50 req/day. Free key: 1,000 req/hr |
| **Open Food Facts** (`world.openfoodfacts.org`) | Packaged products by barcode, nutriscore, nova group, ingredients | None | ~100 req/min (no auth) |

**Use Open Food Facts for packaged products (barcode known).** Use USDA FDC for raw/whole foods and precise nutrient values. Never use the browser for either — both are pure JSON REST APIs.

---

## USDA FoodData Central

### Search foods

```python
import json
from helpers import http_get

# GET search — supports query string params
result = json.loads(http_get(
    "https://api.nal.usda.gov/fdc/v1/foods/search"
    "?query=chicken+breast"
    "&dataType=Foundation"   # Foundation | SR+Legacy | Branded | Survey+%28FNDDS%29
    "&pageSize=5"
    "&api_key=DEMO_KEY"      # replace with your free key for production
))

print("totalHits:", result["totalHits"])   # 437 for "chicken breast"
for food in result["foods"][:2]:
    print(f"  fdcId={food['fdcId']} dataType={food['dataType']} desc={food['description']}")
    for n in food.get("foodNutrients", [])[:4]:
        print(f"    {n['nutrientName']}: {n.get('value','?')} {n['unitName']}")
# Confirmed output (2026-04-18):
# totalHits: 437
#   fdcId=171515 dataType=SR Legacy desc=Chicken breast tenders, breaded, uncooked
#     Galactose: 0.0 G
#     Fiber, total dietary: 1.1 G
#   fdcId=2646170 dataType=Foundation desc=Chicken, breast, boneless, skinless, raw
#     Iron, Fe: 0.354 MG
#     Protein: 20.787 G
```

### POST search (filter by specific nutrients)

```python
import json
from helpers import http_get
import urllib.request

body = json.dumps({
    "query": "banana",
    "dataType": ["Foundation"],
    "pageSize": 3,
    "nutrients": [1003, 1004, 1005, 1008]  # Protein, Fat, Carbs, Energy
}).encode()
req = urllib.request.Request(
    "https://api.nal.usda.gov/fdc/v1/foods/search?api_key=DEMO_KEY",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=20) as r:
    result = json.loads(r.read())

for food in result["foods"][:2]:
    print(f"{food['description']} (fdcId={food['fdcId']})")
    for n in food.get("foodNutrients", []):
        print(f"  {n['nutrientName']}: {n.get('value','?')} {n['unitName']}")
# Confirmed (2026-04-18):
# Bananas, overripe, raw (fdcId=1105073)
#   Protein: 0.73 G  |  Total lipid (fat): 0.22 G
#   Carbohydrate, by difference: 20.1 G  |  Energy: 85.0 KCAL
```

### Fetch single food by fdcId

```python
import json
from helpers import http_get

food = json.loads(http_get(
    "https://api.nal.usda.gov/fdc/v1/food/2262074?api_key=DEMO_KEY"
))
print(food["description"])   # Almond butter, creamy
print(food["dataType"])       # Foundation

for n in food["foodNutrients"][:6]:
    nut = n["nutrient"]
    print(f"  id={nut['id']} {nut['name']}: {n.get('amount','?')} {nut['unitName']}")
# id=1051 Water: 1.751 g
# id=1003 Protein: 20.787 g
# id=1004 Total lipid (fat): 53.04 g
# id=1008 Energy: 645.456 kcal
```

### List foods (paginate all)

```python
import json
from helpers import http_get

page = json.loads(http_get(
    "https://api.nal.usda.gov/fdc/v1/foods/list"
    "?dataType=Foundation"
    "&pageSize=20"
    "&pageNumber=1"
    "&api_key=DEMO_KEY"
))
for food in page[:3]:
    print(f"{food['fdcId']}: {food['description']} ({food['dataType']})")
# 2262074: Almond butter, creamy (Foundation)
# 2257045: Almond milk, unsweetened, plain, refrigerated (Foundation)
# 2747652: Anchovies, canned in olive oil, with salt, drained (Foundation)
```

### Key nutrient IDs

| ID | Nutrient | Unit |
|----|---------|------|
| 1003 | Protein | g |
| 1004 | Total lipid (fat) | g |
| 1005 | Carbohydrate, by difference | g |
| 1008 | Energy | kcal |
| 1051 | Water | g |
| 1079 | Fiber, total dietary | g |
| 2000 | Sugars, Total | g |
| 1087 | Calcium, Ca | mg |
| 1089 | Iron, Fe | mg |
| 1090 | Magnesium, Mg | mg |
| 1092 | Potassium, K | mg |
| 1093 | Sodium, Na | mg |

### dataType values

| dataType | Description |
|----------|-------------|
| `Foundation` | USDA reference foods — most accurate nutrient profiles |
| `SR Legacy` | Standard Reference (legacy, broad coverage) |
| `Survey (FNDDS)` | USDA dietary survey foods |
| `Branded` | 400K+ CPG branded products (less consistent nutrients) |

Use `Foundation` or `SR Legacy` for reliable nutrient data. Use `Branded` if you need real product SKUs.

---

## Open Food Facts (packaged products, no auth)

### Barcode lookup (most reliable endpoint)

```python
import json
from helpers import http_get

# v2 barcode lookup — pass ?fields= to trim response (product JSON is often very large)
product = json.loads(http_get(
    "https://world.openfoodfacts.org/api/v2/product/3017620422003.json"
    # barcode above = Nutella
))

p = product["product"]
n = p.get("nutriments", {})

print(p.get("product_name"))       # Nutella
print(p.get("brands"))             # Ferrero
print(p.get("nutriscore_grade"))   # e  (a/b/c/d/e — best to worst)
print(p.get("nova_group"))         # 4  (1=unprocessed .. 4=ultra-processed)
print(p.get("serving_size"))       # 15 g
print(p.get("quantity"))           # 400 g

# Nutriments are per 100g (key suffix _100g) or per serving (_serving)
print(n.get("energy-kcal_100g"))   # 539
print(n.get("proteins_100g"))      # 6.3
print(n.get("carbohydrates_100g")) # 57.5
print(n.get("fat_100g"))           # 30.9
print(n.get("fiber_100g"))         # 0
print(n.get("sugars_100g"))        # 56.3
print(n.get("salt_100g"))          # 0.107
# Confirmed (2026-04-18) — status=1 means product found, status=0 means not found
```

### Product lookup with field selection (faster for bulk)

```python
import json
from helpers import http_get

# Request only the fields you need — saves bandwidth on large product records
product = json.loads(http_get(
    "https://world.openfoodfacts.org/api/v2/product/0048151623426.json"
    "?fields=code,product_name,brands,nutriscore_grade,nova_group,nutriments,serving_size,categories_tags"
))
p = product["product"]
# categories_tags is a list like ['en:snacks', 'en:cookies']
print(p.get("categories_tags", [])[:3])
```

### Text search (use sparingly — endpoint is unstable)

```python
import json
from helpers import http_get

# The CGI search endpoint works but returns an HTML error page if OFF servers are under load.
# Always check that the response starts with '{' before parsing.
raw = http_get(
    "https://world.openfoodfacts.org/cgi/search.pl"
    "?search_terms=greek+yogurt"
    "&action=process"
    "&json=1"
    "&page_size=5"
    "&fields=code,product_name,brands,nutriscore_grade,nutriments"
)
if not raw.strip().startswith("{"):
    raise RuntimeError("OFF search returned non-JSON (server under load — retry or use barcode lookup)")

result = json.loads(raw)
print("count:", result.get("count"))
for p in result.get("products", [])[:3]:
    print(f"  {p.get('code')} {p.get('product_name','?')} [{p.get('nutriscore_grade','?')}]")
```

### Key Open Food Facts fields

| Field | Description |
|-------|-------------|
| `product_name` | Product name |
| `brands` | Brand name(s) |
| `quantity` | Package size (e.g. `"400 g"`) |
| `serving_size` | Serving size string |
| `nutriscore_grade` | `a`–`e` (nutritional quality) |
| `nova_group` | `1`–`4` (processing level) |
| `categories_tags` | List of `en:category-name` tags |
| `ingredients_text` | Ingredients list as string |
| `allergens_tags` | List of `en:allergen` tags |
| `nutriments` | Dict with `_100g` and `_serving` suffixes |
| `image_front_url` | Front-of-pack image URL |

Nutriment keys use hyphens: `energy-kcal_100g`, `saturated-fat_100g`, `trans-fat_100g`.

---

## Bulk fetch pattern (multiple foods)

```python
import json, time
from concurrent.futures import ThreadPoolExecutor
from helpers import http_get

FDC_KEY = "DEMO_KEY"  # replace with real key for production

def fetch_fdc(fdc_id):
    url = f"https://api.nal.usda.gov/fdc/v1/food/{fdc_id}?api_key={FDC_KEY}"
    try:
        return json.loads(http_get(url))
    except Exception as e:
        return {"error": str(e), "fdcId": fdc_id}

# With DEMO_KEY: do NOT parallelize — rate limit is 30 req/hr.
# With a real free key (1,000 req/hr): safe to use ThreadPoolExecutor(max_workers=4)
fdc_ids = [2262074, 1750340, 1105073]  # almond butter, apple (fuji), banana
results = []
for fdc_id in fdc_ids:
    results.append(fetch_fdc(fdc_id))
    time.sleep(2)  # conservative — with real key drop to time.sleep(0.1)

for r in results:
    if "error" not in r:
        print(r["description"], r.get("dataType"))
```

---

## Gotchas

- **DEMO_KEY has a very tight rate limit: 30 requests/hour and 50/day per IP.** It hits `OVER_RATE_LIMIT` fast in any loop. Register a free key at `fdc.nal.usda.gov/api-guide.html` for real work (1,000 req/hr). Error response looks like `{"error": {"code": "OVER_RATE_LIMIT", "message": "..."}}` — always check `"error" in result` before accessing `result["foods"]`.

- **`format=abridged` strips nutrient names.** Using `?format=abridged` in the food detail endpoint returns `id=None, name=None` for every nutrient — the names are gone. Use the default (no `format` param) to get `nutrient.id`, `nutrient.name`, and `nutrient.unitName`.

- **POST search nutrient filter is additive, not exclusive.** When you pass `"nutrients": [1003, 1004]` to the POST body, the response only returns those nutrient values in `foodNutrients` — it does NOT filter to foods that have those nutrients. All foods still match; you just get a trimmed nutrient list back.

- **`dataType` URL encoding:** In GET queries, multi-value dataType must use comma separation or repeated params — `dataType=Foundation,SR+Legacy` works. Branded data has wildly inconsistent nutrient coverage; stick to `Foundation` or `SR Legacy` for nutrition queries.

- **Open Food Facts barcode lookup is reliable; text search is not.** The `/api/v2/product/{barcode}.json` endpoint is stable. The CGI search endpoint (`/cgi/search.pl`) returns a raw HTML error page (`<!DOCTYPE html>`) instead of JSON when their servers are overloaded — check `raw.strip().startswith("{")` before parsing.

- **Open Food Facts nutriment keys use hyphens, not underscores.** The key is `energy-kcal_100g`, not `energy_kcal_100g`. Missing nutrients are absent from the dict (don't default to 0) — always use `.get(key)` with a fallback.

- **`status=0` in Open Food Facts means product not found**, not an error. `product["status"] == 0` returns `{"status": 0, "status_verbose": "product not found"}`. Check status before accessing `product["product"]`.

- **Open Food Facts product JSON can be very large** (10–50 KB for well-documented products). Use `?fields=` to request only the fields you need when doing bulk lookups.

- **USDA Foundation foods have the most complete nutrient profiles** — they include 100+ nutrients with analytical measurements. SR Legacy is broad but older. Branded foods often have only the 12 label-required nutrients.

- **USDA fdcId is stable across API versions** — the same fdcId resolves to the same food permanently. Safe to cache and store for future lookups.
