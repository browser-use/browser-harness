# SF Symphony — Seat map & availability (seats.sfsymphony.org)

`https://seats.sfsymphony.org/single/{performanceId}` — Tessitura-backed seat picker with a tk3d DVM 3D map. No login needed to read availability and prices.

## Do this first

**Read seats from the JSON API, not the 3D map.** The page calls same-origin endpoints that return every seat with status, zone, and a physical sequence number. Run `fetch` from inside the tab with `js(...)` so the session cookie is sent (`http_get` from outside gets a different session).

```python
new_tab("https://seats.sfsymphony.org/single/23885")
wait_for_load()
data = js("""
(async () => {
  const pid = 23885;
  const get = async u => (await fetch(u, {credentials:'include'})).json();
  const pricing = await get(`/api/pricing/performance/${pid}`);
  const groups  = await get(`/api/sectionAvailability/performance/${pid}`);
  const seats = {};
  for (const g of groups.filter(g => g.totalAvailableSeats > 0)) {
    seats[g.sectionGroupId] = await get(`/api/seatinfo/sectiongroup?groupId=${g.sectionGroupId}&performanceId=${pid}`);
  }
  return JSON.stringify({pricing, groups, seats});
})()
""")
```

## Endpoints (GET, same origin)

| Route | Returns |
|---|---|
| `/api/settings/performance/{id}` | Performance metadata: date, facility, `maxTicketsAllowed`, cart URLs |
| `/api/pricing/performance/{id}` | Zones: `zoneId`, `zoneRank` (1 = best), `zoneDescription`, `availableCount`, `prices[]` with `priceTypeId` and `priceDescription` (e.g. `Single Ticket Price`, `Children 17 and under`) |
| `/api/sectionAvailability/performance/{id}` | Section groups (`sectionGroupId` like `Orchestra`, `LogeLeft`, `Premier2ndTier`) with per-section `availableCount` and `zoneIds` |
| `/api/seatinfo/sectiongroup?groupId={sectionGroupId}&performanceId={id}` | Every seat in the group, bucketed: `available`, `unavailable`, `carted`, `wheelchair`, `companion`, `killed`, `restricted`, `transfer`, `obstructed`, `promo` |
| `/api/seatinfo/all?performanceId={id}` | **Broken** — HTTP 500 `An item with the same key has already been added. Key: sectionName`. Use the sectiongroup route per group. |

Other routes in the bundle: `/api/BestAvailable/performance/{id}`, `/api/reserveseat/performance/{id}`, `/api/cart/{id}`, `/api/Promotion?promoCode=`.

Seat record shape: `{"key":"S_49-U-13","sec":49,"row":"U","num":"13","zone":3113,"no":299xxx,"seatType":1,"hotSeatHitCount":170,"custom":{"sectionName":"Upper Orchestra"}}`. Join `zone` to `pricing[].zoneId` for the price. `hotSeatHitCount` rises with how often a seat gets viewed or carted.

## Adjacency trap (Davies Symphony Hall numbering)

Seat numbers in a row are **not** a single sequence. Orchestra and tier rows use three blocks:

- odd `1..23` — house-left side block, `1` at the centre aisle, `23` at the wall aisle
- even `2..24` — house-right side block, `2` at the centre aisle, `24` at the wall aisle
- `101..114` — centre block

So seats 8 and 9 are on opposite sides of the hall. Two seats are side by side only when they are in the same `sec`+`row`, in the same block (same parity, or both ≥100), and their `no` values differ by exactly 1. Boxes (`row` = `"0"`) have two short rows; use the `no` diff there too.

```python
import json, re
from collections import defaultdict
d = json.loads(data)
price = {z["zoneId"]: z for z in d["pricing"]}
block = lambda n: "C" if int(n) >= 100 else int(n) % 2
rows = defaultdict(list)
for g in d["seats"].values():
    for s in g["available"].values():
        rows[(s["sec"], s["row"])].append(s)
pairs = []
for lst in rows.values():
    lst.sort(key=lambda s: s["no"])
    for a, b in zip(lst, lst[1:]):
        if abs(a["no"] - b["no"]) == 1 and block(a["num"]) == block(b["num"]):
            pairs.append((price[a["zone"]]["zoneDescription"], a["row"], a["num"], b["num"]))
```

Zone boundaries move per performance (the 2020 PDF shows row R outer seats as Upper Orchestra; the API can price them as Orchestra). Trust `zone` from the API.

## 3D map (tk3d DVM)

- First load shows `Loading seat map...` for ~5 s, then a section overview. `click_at_xy` on a section opens the seat-level view after another `Loading <Section>` spinner (~4 s). Re-screenshot after each.
- Zoom with the `+` / `-` buttons on the right edge of the map; a minimap appears bottom-right.
- **CDP `mouseMoved` and `mouseWheel` time out** on this page through the daemon (5 s, no response). Hover tooltips and wheel zoom are not reachable; clicks work. Get seat details from the API instead.
- Legend colours: green = available, blue = wheelchair companion, purple = lifting armrest, red = selected.

## Hall layout reference

The `View Seat Map (PDF)` link in the header is the official 4-page chart (Orchestra, 1st Tier, 2nd Tier, Loge) at `https://www.sfsymphony.org//SanFrancisco/media/SanFrancisco/Template%20Images/digital-seating-charts-2020-02-20.pdf`. Render with `pdftoppm` to read seat numbers; it shows the odd/even/100s blocks above.
