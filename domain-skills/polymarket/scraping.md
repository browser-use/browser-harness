# Polymarket — Market Data, Outcomes & Comments

Polymarket (`polymarket.com`) is a Next.js SPA. Its DOM is **selector-hostile** — class names are CSS-module hashes that rotate on every deploy (`styles_row__aB3cD`), and there are **no `data-testid` attributes anywhere on the event pages** (confirmed April 2026: `document.querySelectorAll('[data-testid]').length === 0` on a live event page).

**Always try the public Gamma API first.** It returns everything the page shows — outcomes, prices, volume, comments, tags — as clean JSON, and it doesn't need a browser at all.

## URL patterns

- Event page: `https://polymarket.com/event/<slug>` — a group of related markets (e.g. "Iran x Israel/US conflict ends by…" holds one market per proposed end-date).
- Single market (rare nowadays; most UI routes are events): `https://polymarket.com/market/<slug>`.
- Event slug is visible in the browser URL and is the stable join key for the API.

## Path 1: Gamma API (preferred — no browser needed)

Base: `https://gamma-api.polymarket.com`. No auth, no key, no rate limit observed under normal use. All data structured JSON. **Use `http_get` from `helpers.py`.**

### Event metadata + outcomes

```python
import json
from helpers import http_get

ev = json.loads(http_get(
    "https://gamma-api.polymarket.com/events?slug=iran-x-israelus-conflict-ends-by"
))[0]

print(ev["title"])          # "Iran x Israel/US conflict ends by...?"
print(ev["volume"])          # 96575490.91253869  (float USD)
print(ev["endDate"])         # "2026-03-31T00:00:00Z"
print(ev["closed"])          # bool
print([t["label"] for t in ev["tags"]])   # ["Middle East", "Iran", "World", ...]
print(len(ev["markets"]))    # 9 — one sub-market per outcome (grouped event)
```

Event top-level keys (Apr 2026): `active archived closed commentCount competitive createdAt description endDate id image liquidity markets negRisk negRiskAugmented openInterest slug startDate tags ticker title updatedAt volume volume1mo volume1wk volume1yr volume24hr`.

Each entry in `ev["markets"]` is a binary market with these useful keys:
`question groupItemTitle outcomes outcomePrices volume lastTradePrice bestBid bestAsk conditionId clobTokenIds closed endDate slug orderPriceMinTickSize`.

**Critical quirk:** `outcomes` and `outcomePrices` are **JSON-encoded strings**, not lists. Parse them:

```python
for m in ev["markets"]:
    outcomes = json.loads(m["outcomes"])           # ["Yes", "No"]
    prices   = json.loads(m["outcomePrices"])      # ["0", "1"]
    yes_price, no_price = float(prices[0]), float(prices[1])
    print(f"{m['groupItemTitle']}: YES {yes_price:.3f} / NO {no_price:.3f} | vol ${m.get('volume') or 0:,.0f}")
```

`groupItemTitle` is the human label for the outcome within a grouped event ("April 7", "May 15", "June 30"). `question` is the full binary phrasing ("Iran x Israel/US conflict ends by March 7?"). For non-grouped single markets, `groupItemTitle` may be empty and the outcome label is implicit (the market's `question` is the Yes/No phrasing).

**`lastTradePrice` ≠ midpoint.** For live markets, the UI shows the Yes/No **cents** derived from the order book, which is closer to the **mid of `bestBid` and `bestAsk`**. `lastTradePrice` can be stale. Prefer:

```python
def yes_cents(m):
    if m.get("bestBid") and m.get("bestAsk"):
        return (float(m["bestBid"]) + float(m["bestAsk"])) / 2 * 100
    return float(json.loads(m["outcomePrices"])[0]) * 100
```

### Comments

Endpoint: `https://gamma-api.polymarket.com/comments` (NOT `comments-api.polymarket.com` — that hostname no longer resolves as of Apr 2026).

Required query params: `parent_entity_type=Event` + `parent_entity_id=<event_id>`. For a market-level comment thread (rare), use `parent_entity_type=Market` + the `conditionId` or market id.

```python
import json
from helpers import http_get

ev = json.loads(http_get("https://gamma-api.polymarket.com/events?slug=iran-x-israelus-conflict-ends-by"))[0]

raw = http_get(
    f"https://gamma-api.polymarket.com/comments"
    f"?parent_entity_type=Event&parent_entity_id={ev['id']}"
    f"&limit=10&order=reactionCount&ascending=false"
)
for c in json.loads(raw):
    if "body" not in c:     # deleted/removed comments have no body field
        continue
    author = (c.get("profile") or {}).get("pseudonym") or c.get("userAddress", "")[:8]
    print(f"[{c['createdAt'][:10]}] {author} (+{c['reactionCount']}): {c['body'][:100]}")
```

Comment keys: `id body parentEntityID parentEntityType profile userAddress createdAt updatedAt reactionCount reportCount`.

Profile keys: `name pseudonym displayUsernamePublic proxyWallet baseAddress profileImage`. Prefer `profile.pseudonym` over `profile.name` — Polymarket assigns the human-readable handle (e.g. `Next-Ride`, `Flamboyant-Subsidiary`) as `pseudonym`; `name` is often an opaque username like `aa99011`.

Useful query params:
- `order=reactionCount` + `ascending=false` → top comments (upvotes)
- `order=createdAt` + `ascending=false` → newest (default)
- `limit=<n>` — up to ~100 per page
- `offset=<n>` — pagination

### Other handy Gamma endpoints

- `/events?active=true&limit=50&order=volume24hr&ascending=false` — trending events
- `/events?tag_id=<id>` — events by tag (tags show in event `tags[].id`, e.g. `78` = Iran, `154` = Middle East)
- `/markets?slug=<market-slug>` — single market lookup
- `/markets/<id>/prices-history?interval=1d&fidelity=60` — price history series

### CLOB (order book, trades)

Real-time order book lives on `https://clob.polymarket.com`. Needed when `bestBid`/`bestAsk` on Gamma are stale (rare) or for trade history. Market-data endpoints don't need auth; order placement does.

```python
# Mid-price from live order book
ob = json.loads(http_get(f"https://clob.polymarket.com/book?token_id={clob_token_id}"))
best_bid = float(ob["bids"][0]["price"]) if ob.get("bids") else None
best_ask = float(ob["asks"][0]["price"]) if ob.get("asks") else None
```

`clob_token_id` comes from `market["clobTokenIds"]` (a JSON-encoded pair `[yes_token_id, no_token_id]`).

## Path 2: Browser DOM extraction (fallback)

Use this only when the API path is unavailable, blocked, or you need exactly-what-user-sees (e.g. A/B variant of the UI, or to corroborate a weird resolution state). The Gamma API is always cheaper.

### Why naive DOM extraction fails

Polymarket's event page renders every outcome row inside nested `<div>`s with **CSS-module class names that change every deploy**. There are **no stable selectors** — no `data-testid`, no `role`, no semantic classes. Three naive approaches that look fine and are actually broken:

1. `document.querySelectorAll('div')` + `innerText` pattern-match — **produces duplicates.** Every ancestor div's `innerText` contains the concatenation of its descendants' text, so "$45,718,857 Vol. · 100% · 99.9¢ · 0.1¢" matches at 4–6 ancestor levels for the same outcome row.
2. Regex on `document.body.innerText` — loses positional structure. You get flat lists of `['99.9¢', '0.1¢', '99.9¢', ...]` and `['April 7', 'April 15', ...]` and can't join them into rows.
3. Picking the first N elements of each list — fragile to header/footer noise (the sidebar also has YES/NO cents for related markets).

### The leaf-div-disambiguation pattern

**Only emit text from DOM leaves** — elements with `children.length === 0`. A leaf node's `innerText` is precisely what it renders, never a concatenation of siblings. Then group adjacent leaves by their **nearest common ancestor** to assemble rows.

```bash
browser-harness <<'PY'
new_tab("https://polymarket.com/event/iran-x-israelus-conflict-ends-by")
wait_for_load()
wait(3.0)   # SPA hydration

# Fingerprints for each cell-type in an outcome row
labels = js(r"""
(()=>{
  const leaves = [...document.querySelectorAll('*')].filter(e => e.children.length === 0);
  const out = [];
  const vol = /^\$[\d,]+\s*Vol\.?$/;
  const pct = /^\d+%$/;
  const price = /^\d+(\.\d+)?¢$/;
  const rows = new Map();   // key = nearest ancestor that contains >=2 fingerprints

  // Find the smallest ancestor that wraps each outcome row. We walk up from every
  // fingerprint leaf, and the first ancestor that ALSO contains another fingerprint
  // leaf of a DIFFERENT kind is the row container.
  const fingerprint = (t) => vol.test(t) ? 'vol' : pct.test(t) ? 'pct' : price.test(t) ? 'price' : null;
  const hit = leaves
    .map(e => ({el:e, text:(e.innerText||'').trim()}))
    .filter(o => fingerprint(o.text));
  for (const o of hit) {
    let node = o.el.parentElement;
    while (node) {
      const inner = node.innerText || '';
      const kinds = new Set();
      if (/\$[\d,]+\s*Vol\.?/.test(inner)) kinds.add('vol');
      if (/\b\d+%/.test(inner)) kinds.add('pct');
      if (/\d+(\.\d+)?¢/.test(inner)) kinds.add('price');
      if (kinds.size >= 2) {
        const txtNodes = [...node.querySelectorAll('*')]
          .filter(e => e.children.length === 0)
          .map(e => (e.innerText||'').trim())
          .filter(Boolean);
        rows.set(node, txtNodes);
        break;
      }
      node = node.parentElement;
    }
  }
  return [...rows.values()];
})()
""")
print(labels)
PY
```

Then assemble rows in Python by matching fingerprints:

```python
import re
VOL   = re.compile(r'^\$[\d,]+\s*Vol\.?$')
PCT   = re.compile(r'^\d+%$')
PRICE = re.compile(r'^\d+(\.\d+)?¢$')

def assemble(leaf_lists):
    rows = []
    for leaves in leaf_lists:
        label = next((l for l in leaves if not VOL.match(l) and not PCT.match(l) and not PRICE.match(l) and len(l) < 40), None)
        vol   = next((l for l in leaves if VOL.match(l)), None)
        pct   = next((l for l in leaves if PCT.match(l)), None)
        prices = [l for l in leaves if PRICE.match(l)]
        rows.append({
            "outcome":    label,
            "yes_cents":  float(prices[0].rstrip("¢")) if len(prices) >= 1 else None,
            "no_cents":   float(prices[1].rstrip("¢")) if len(prices) >= 2 else None,
            "chance_pct": int(pct.rstrip("%")) if pct else None,
            "volume":     vol,
        })
    return rows
```

### Live-measured leaf counts (trial event, April 2026)

```
h1:                "Iran x Israel/US conflict ends by...?"
data-testid count:  0
price-leaves:      ['99.9¢', '0.1¢', '99.9¢', '0.1¢', '99.9¢', '0.1¢', '99.9¢', '0.1¢', '99.9¢', '0.1¢']
vol-leaves:        ['$96,575,491 Vol.', '$45,718,857 Vol.', '$16,801,875 Vol.', '$13,374,944 Vol.', '$5,809,323 Vol.']
pct-leaves:        ['100%', '100%', '100%', '100%', '5%', '4%']
```

Note the first `vol-leaf` is the **event-level total** ($96.5M), while the next four are per-outcome volumes. The first four `pct-leaves` are the outcome chances; `5%` / `4%` are from the related-markets sidebar. Filter by nearest-common-ancestor as above to stay inside the outcome block.

## Gotchas

- **No `data-testid` attributes.** Don't waste time grepping. Confirmed with `document.querySelectorAll('[data-testid]').length === 0` on a live event page.
- **CSS-module class names rotate on deploy.** Never pin to `styles_xxx` classes — they're invalid within a week.
- **`outcomes` and `outcomePrices` are JSON-encoded strings in the Gamma payload.** Run `json.loads()` on them before use. Agents repeatedly trip on this.
- **`lastTradePrice` lags the visible cents.** Use `(bestBid + bestAsk)/2` when both exist, otherwise fall back to `outcomePrices[0]`.
- **Comments live at `gamma-api.polymarket.com/comments`, not `comments-api.polymarket.com`.** The latter hostname doesn't resolve (April 2026).
- **Deleted comments have no `body` field.** The envelope still ships (with `id`, `createdAt`, `profile`, `media`, `parentCommentID`, etc.) but `body` is absent. Always `if "body" not in c: continue` before indexing. `c["body"]` will `KeyError` otherwise.
- **`profile.pseudonym` is the handle.** `profile.name` is an opaque username. Always prefer `pseudonym` for display.
- **Grouped vs single markets.** An event with `ev["markets"]` of length N > 1 is a grouped event — each sub-market is one outcome slot. Length 1 is a traditional binary market; the `question` holds the Yes/No framing.
- **Naive `querySelectorAll('div') + innerText`-match duplicates every row 4–6 times** because ancestor divs' innerText contains their descendants' concatenated text. Always filter to DOM leaves (`children.length === 0`) and group by nearest common ancestor.
- **Hydration wait.** `wait_for_load()` returns before the SPA paints the outcome table. Add `wait(2.5)`–`wait(3.5)` before reading DOM. Irrelevant for the API path.
- **Arc Profile B only on this machine.** Polymarket on Profile A may trigger the wallet-connect modal if a previous session left a wallet linked — Profile B is the clean default.
- **Sidebar sub-markets share the same fingerprints.** Any `vol-leaf` / `pct-leaf` / `price-leaf` outside the main event container is noise. The leaf-disambiguation pattern above filters this by requiring a nearest-ancestor containing ≥2 fingerprint kinds — sidebar related-market cards hold only `pct-leaves`, so they're excluded.

## Always prefer the API

The leaf-disambiguation DOM path exists as a corroboration / fallback tool. If you find yourself writing it for a fresh task, stop and check whether `/events?slug=…` already gives you the fields you need. As of April 2026, it does for: title, resolution status (`closed` + `umaResolutionStatus`), end date, all outcome labels/prices/volumes, comment counts, tags. DOM extraction is only worth it for visual-only UI state (which doesn't exist on Polymarket — the API is the source of truth).
