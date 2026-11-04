# Scryfall - Card Search, Prices and Printings (official API + site)

Field-tested against scryfall.com and api.scryfall.com on 2026-11-04 using a Browser Use cloud browser, logged out. Blocks 1-3 call the official Scryfall API (https://scryfall.com/docs/api) with `fetch()` from a scryfall.com tab; block 4 reads the public site. About 30 API calls and 20 page loads: every answer was HTTP 200 or a documented 400/404, no 429, no challenge, no login or consent wall.

robots.txt (fetched 2026-11-04, identical on both hosts): `User-Agent: *` disallows only `/admin`, `/admin/*/*` and the error pages `/400 /404 /406 /422 /500 /503 /504`; this skill opens `/robots.txt`, `/search` and `/card/<set>/<number>` on scryfall.com and calls `/cards/search`, `/cards/named` and `/cards/<set>/<number>` on api.scryfall.com.

## Quick summary

- **Use the API.** It is public, keyless and documented. Three endpoints cover the task:
  - `/cards/search?q=<scryfall syntax>&unique=cards|prints|art&order=...` - same search language as the site; List object, 175 cards per page, `total_cards`, `has_more`, `next_page`.
  - `/cards/named?exact=<name>` or `?fuzzy=<text>` (optional `&set=<code>`) and `/cards/<set>/<collector number>` - one Card object with `prices` and `purchase_uris`.
  - The card's own `prints_search_uri` (`/cards/search?order=released&q=oracleid:<id>&unique=prints`) - every English print with its own prices.
- **Required headers** (docs): `Accept` must be present, and on-page browser JavaScript must keep the browser's own `User-Agent`. The blocks send `Accept: application/json;q=0.9,*/*;q=0.8` and never touch the User-Agent.
- **Rate limits** (docs): `/cards/search` and `/cards/named` 2 per second, most other endpoints 10 per second. A 429 locks the client out for 30 s and the docs say repeated overload can get you banned. The blocks run one call at a time with 0.5 s between calls and stop on 429.
- **Prices update once a day** (docs) and are strings: `usd`, `usd_foil`, `usd_etched`, `eur`, `eur_foil`, `eur_etched`, `tix`, each `null` when unknown. Scryfall's footer calls them daily estimates from its affiliates; for 2XM #129 `usd`, `eur` and `tix` matched the card page's TCGplayer, Cardmarket and Cardhoarder buttons.
- **The site works too** (block 4): `/search?...&as=checklist` is server-rendered HTML with Set, Number, Name, Cost, Type, Rarity, Language, Artist, USD, EUR and TIX columns, 175 rows per page.

## What works

Blocks 1-3 share the same helpers: `on_scryfall_tab()` opens `https://scryfall.com/robots.txt` once (a tiny allowed page; api.scryfall.com sends CORS headers for it) and later blocks reuse any scryfall.com tab. `api(url)` runs one `fetch()` in that tab, polls for the answer, reads big bodies back in 500,000-character slices, and returns parsed JSON. It raises `NotFound` on 404, exits on 429, retries 5xx and network errors twice with backoff, and raises on anything else, so a failure never looks like an empty result.

### 1. Card search with paging (browser, official API)

```python
import json, time, urllib.parse

QUERIES = ["lightning bolt", "t:dragon", "zzqx no such card 98712"]
MAX_PAGES = 3          # 175 cards per page

API = "https://api.scryfall.com"
PACE = 0.5             # seconds between calls; docs: /cards/search and /cards/named allow 2/s, other endpoints 10/s
CHUNK = 500_000        # characters per js() read when pulling a big body out of the tab
ACCEPT = "application/json;q=0.9,*/*;q=0.8"   # docs: Accept is required; the browser keeps its own User-Agent

class NotFound(Exception):
    """Scryfall answered 404 (object 'error', code 'not_found'): no card matched, or a fuzzy name was ambiguous."""

def on_scryfall_tab():
    """API calls run as fetch() from a logged-out scryfall.com tab (api.scryfall.com sends CORS headers)."""
    try:
        if js("location.origin") == "https://scryfall.com":
            return
    except Exception:
        pass
    new_tab("https://scryfall.com/robots.txt")   # tiny allowed page on the site
    wait_for_load()

START_JS = """(() => { window.__sf = null;
  fetch(%s, {headers: {Accept: %s}, credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__sf = {status: r.status, len: t.length, body: t}; })
    .catch(e => { window.__sf = {status: 0, len: 0, body: '', err: String(e)}; });
  return 1; })()"""

def api(url, tries=3):
    """Serial GET of an api.scryfall.com URL (path or full next_page/prints_search_uri URL). Parsed JSON;
    NotFound on 404; stops on 429; retries 5xx/network errors with backoff, then raises."""
    url = url if url.startswith("https://") else API + url
    if not url.startswith(API + "/"):
        raise ValueError(f"not an api.scryfall.com URL: {url}")
    for attempt in range(tries):
        js(START_JS % (json.dumps(url), json.dumps(ACCEPT)))
        t0 = time.time()
        while not (meta := js("window.__sf && {status: window.__sf.status, len: window.__sf.len, err: window.__sf.err}")):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__sf.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__sf = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            return json.loads(body)
        err = json.loads(body) if body.startswith("{") else {}
        if status == 404:
            raise NotFound(err.get("details") or body[:200])
        if status == 429:
            raise SystemExit("HTTP 429: Scryfall rate-limits this client for 30 s; stop and slow down, do not retry around it")
        if (status >= 500 or status == 0) and attempt < tries - 1:
            time.sleep(5 * 2 ** attempt)
            continue
        raise RuntimeError(f"{url}: HTTP {status} {err.get('code')}: {err.get('details') or meta.get('err') or body[:200]}")

def price_row(c):
    p = c.get("prices") or {}
    return {
        "name": c["name"], "set": c["set"], "number": c["collector_number"], "rarity": c["rarity"],
        "released": c.get("released_at"), "usd": p.get("usd"), "usd_foil": p.get("usd_foil"),
        "eur": p.get("eur"), "tix": p.get("tix"), "url": c["scryfall_uri"].split("?")[0],
    }

def search(q, unique="cards", order="name", max_pages=MAX_PAGES):
    """All pages of /cards/search up to max_pages. Returns (total_cards, rows, warnings, complete)."""
    url = "/cards/search?" + urllib.parse.urlencode({"q": q, "unique": unique, "order": order})
    rows, warnings, pages = [], [], 0
    try:
        while url and pages < max_pages:
            page = api(url)
            pages += 1
            total = page["total_cards"]
            warnings += page.get("warnings") or []
            rows += [price_row(c) for c in page["data"]]
            url = page.get("next_page") if page.get("has_more") else None
    except NotFound as e:
        return 0, [], [str(e)], True
    return total, rows, warnings, url is None

on_scryfall_tab()
results = {}
for q in QUERIES:
    total, rows, warnings, complete = results[q] = search(q)
    print(f"{q!r}: {total} cards, got {len(rows)}{'' if complete else ' (stopped at MAX_PAGES)'}{'; ' + '; '.join(warnings) if warnings else ''}")
    for r in rows[:4]:
        print(f"  {r['name']:<38} {r['set']:>5} #{r['number']:<5} {r['rarity']:<8} usd {r['usd']}  eur {r['eur']}  tix {r['tix']}")
print(json.dumps(results[QUERIES[0]][1][0], indent=1))
```

Output observed on 2026-11-04:

```text
'lightning bolt': 2 cards, got 2
  Emeritus of Conflict // Lightning Bolt   sos #113   mythic   usd 2.39  eur 1.64  tix 0.21
  Lightning Bolt                           msc #806   uncommon usd 0.89  eur 2.04  tix 0.02
't:dragon': 444 cards, got 444
  Acid-Spewer Dragon                       dtk #86    uncommon usd 0.27  eur 0.17  tix 0.03
  Adult Gold Dragon                        afr #216   rare     usd 0.38  eur 0.38  tix 0.02
  Akoum Hellkite                           gn2 #36    rare     usd 0.44  eur 0.27  tix None
  Akul the Unrepentant                     otj #189   rare     usd 0.32  eur 0.19  tix 0.02
'zzqx no such card 98712': 0 cards, got 0; Your query didn’t match any cards. Adjust your search terms or refer to the syntax guide at https://scryfall.com/docs/reference
{
 "name": "Emeritus of Conflict // Lightning Bolt",
 "set": "sos",
 "number": "113",
 "rarity": "mythic",
 "released": "2026-04-24",
 "usd": "2.39",
 "usd_foil": "1.79",
 "eur": "1.64",
 "tix": "0.21",
 "url": "https://scryfall.com/card/sos/113/emeritus-of-conflict-lightning-bolt"
}
```

### 2. A card's prices: by name, fuzzy name, set or exact print (browser, official API)

```python
import json, time, urllib.parse

LOOKUPS = [
    {"exact": "Lightning Bolt"},                 # Scryfall's default print for the name
    {"exact": "lightning bolt", "set": "lea"},   # one set's print; case and punctuation do not matter
    {"set": "2xm", "number": "129"},             # one exact print by set code + collector number
    {"fuzzy": "aust comm"},                      # misspellings / partial words
    {"fuzzy": "bolt"},                           # ambiguous -> 404 with an explanation
    {"exact": "Black Lotus"},
]


API = "https://api.scryfall.com"
PACE = 0.5             # seconds between calls; docs: /cards/search and /cards/named allow 2/s, other endpoints 10/s
CHUNK = 500_000        # characters per js() read when pulling a big body out of the tab
ACCEPT = "application/json;q=0.9,*/*;q=0.8"   # docs: Accept is required; the browser keeps its own User-Agent

class NotFound(Exception):
    """Scryfall answered 404 (object 'error', code 'not_found'): no card matched, or a fuzzy name was ambiguous."""

def on_scryfall_tab():
    """API calls run as fetch() from a logged-out scryfall.com tab (api.scryfall.com sends CORS headers)."""
    try:
        if js("location.origin") == "https://scryfall.com":
            return
    except Exception:
        pass
    new_tab("https://scryfall.com/robots.txt")   # tiny allowed page on the site
    wait_for_load()

START_JS = """(() => { window.__sf = null;
  fetch(%s, {headers: {Accept: %s}, credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__sf = {status: r.status, len: t.length, body: t}; })
    .catch(e => { window.__sf = {status: 0, len: 0, body: '', err: String(e)}; });
  return 1; })()"""

def api(url, tries=3):
    """Serial GET of an api.scryfall.com URL (path or full next_page/prints_search_uri URL). Parsed JSON;
    NotFound on 404; stops on 429; retries 5xx/network errors with backoff, then raises."""
    url = url if url.startswith("https://") else API + url
    if not url.startswith(API + "/"):
        raise ValueError(f"not an api.scryfall.com URL: {url}")
    for attempt in range(tries):
        js(START_JS % (json.dumps(url), json.dumps(ACCEPT)))
        t0 = time.time()
        while not (meta := js("window.__sf && {status: window.__sf.status, len: window.__sf.len, err: window.__sf.err}")):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__sf.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__sf = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            return json.loads(body)
        err = json.loads(body) if body.startswith("{") else {}
        if status == 404:
            raise NotFound(err.get("details") or body[:200])
        if status == 429:
            raise SystemExit("HTTP 429: Scryfall rate-limits this client for 30 s; stop and slow down, do not retry around it")
        if (status >= 500 or status == 0) and attempt < tries - 1:
            time.sleep(5 * 2 ** attempt)
            continue
        raise RuntimeError(f"{url}: HTTP {status} {err.get('code')}: {err.get('details') or meta.get('err') or body[:200]}")

def lookup(spec):
    """One card object. spec: {"exact": name} | {"fuzzy": text} (either may add "set": code) | {"set": code, "number": n}."""
    if "number" in spec:
        return api(f"/cards/{urllib.parse.quote(spec['set'].lower())}/{urllib.parse.quote(str(spec['number']))}")
    return api("/cards/named?" + urllib.parse.urlencode(spec))

on_scryfall_tab()
for spec in LOOKUPS:
    try:
        c = lookup(spec)
    except NotFound as e:
        print(f"{spec}: not found: {e}")
        continue
    p = {k: v for k, v in c["prices"].items() if v is not None}
    stores = sorted((c.get("purchase_uris") or {}).keys())
    print(f"{spec} -> {c['name']} | {c['set_name']} ({c['set'].upper()}) #{c['collector_number']} {c['released_at']} {'/'.join(c['finishes'])}")
    print(f"   prices {p or 'none'} | stores {stores}")
print(json.dumps({k: c[k] for k in ("name", "set", "collector_number", "prices", "purchase_uris", "prints_search_uri", "scryfall_uri")}, indent=1))
```

Output observed on 2026-11-04:

```text
{'exact': 'Lightning Bolt'} -> Lightning Bolt | Marvel Super Heroes Commander (MSC) #806 2026-06-26 nonfoil/foil
   prices {'usd': '0.89', 'usd_foil': '2.51', 'eur': '2.04', 'eur_foil': '2.44', 'tix': '0.02'} | stores ['cardhoarder', 'cardmarket', 'tcgplayer']
{'exact': 'lightning bolt', 'set': 'lea'} -> Lightning Bolt | Limited Edition Alpha (LEA) #161 1993-08-05 nonfoil
   prices {'usd': '630.00', 'eur': '387.57'} | stores ['cardhoarder', 'cardmarket', 'tcgplayer']
{'set': '2xm', 'number': '129'} -> Grim Lavamancer | Double Masters (2XM) #129 2020-08-07 nonfoil/foil
   prices {'usd': '0.35', 'usd_foil': '0.40', 'eur': '0.51', 'eur_foil': '1.00', 'tix': '0.59'} | stores ['cardhoarder', 'cardmarket', 'tcgplayer']
{'fuzzy': 'aust comm'} -> Austere Command | Star Trek Commander (TRC) #418 2026-11-13 nonfoil/foil
   prices none | stores ['cardhoarder', 'cardmarket', 'tcgplayer']
{'fuzzy': 'bolt'}: not found: Too many cards match ambiguous name “bolt”. Add more words to refine your search.
{'exact': 'Black Lotus'} -> Black Lotus | Vintage Masters (VMA) #4 2014-06-16 nonfoil/foil
   prices {'tix': '75.72'} | stores ['cardhoarder', 'cardmarket', 'tcgplayer']
{
 "name": "Black Lotus",
 "set": "vma",
 "collector_number": "4",
 "prices": {
  "usd": null,
  "usd_foil": null,
  "usd_etched": null,
  "eur": null,
  "eur_foil": null,
  "tix": "75.72"
 },
 "purchase_uris": {
  "tcgplayer": "https://partner.tcgplayer.com/c/4931599/1830156/21018?subId1=api&u=https%3A%2F%2Fwww.tcgplayer.com%2Fsearch%2Fmagic%2Fproduct%3FproductLineName%3Dmagic%26q%3DBlack%2BLotus%26view%3Dgrid",
  "cardmarket": "https://www.cardmarket.com/en/Magic/Products/Search?referrer=scryfall&searchString=Black+Lotus&utm_campaign=card_prices&utm_medium=text&utm_source=scryfall",
  "cardhoarder": "https://www.cardhoarder.com/cards/53155?affiliate_id=scryfall&ref=card-profile&utm_campaign=affiliate&utm_medium=card&utm_source=scryfall"
 },
 "prints_search_uri": "https://api.scryfall.com/cards/search?order=released&q=oracleid%3A5089ec1a-f881-4d55-af14-5d996171203b&unique=prints",
 "scryfall_uri": "https://scryfall.com/card/vma/4/black-lotus?utm_source=api"
}
```

### 3. Every printing of a card with its prices (browser, official API)

```python
import json, time, urllib.parse

CARDS = ["Lightning Bolt", "Black Lotus"]
MAX_PAGES = 5          # 175 prints per page


API = "https://api.scryfall.com"
PACE = 0.5             # seconds between calls; docs: /cards/search and /cards/named allow 2/s, other endpoints 10/s
CHUNK = 500_000        # characters per js() read when pulling a big body out of the tab
ACCEPT = "application/json;q=0.9,*/*;q=0.8"   # docs: Accept is required; the browser keeps its own User-Agent

class NotFound(Exception):
    """Scryfall answered 404 (object 'error', code 'not_found'): no card matched, or a fuzzy name was ambiguous."""

def on_scryfall_tab():
    """API calls run as fetch() from a logged-out scryfall.com tab (api.scryfall.com sends CORS headers)."""
    try:
        if js("location.origin") == "https://scryfall.com":
            return
    except Exception:
        pass
    new_tab("https://scryfall.com/robots.txt")   # tiny allowed page on the site
    wait_for_load()

START_JS = """(() => { window.__sf = null;
  fetch(%s, {headers: {Accept: %s}, credentials: 'omit'})
    .then(async r => { const t = await r.text(); window.__sf = {status: r.status, len: t.length, body: t}; })
    .catch(e => { window.__sf = {status: 0, len: 0, body: '', err: String(e)}; });
  return 1; })()"""

def api(url, tries=3):
    """Serial GET of an api.scryfall.com URL (path or full next_page/prints_search_uri URL). Parsed JSON;
    NotFound on 404; stops on 429; retries 5xx/network errors with backoff, then raises."""
    url = url if url.startswith("https://") else API + url
    if not url.startswith(API + "/"):
        raise ValueError(f"not an api.scryfall.com URL: {url}")
    for attempt in range(tries):
        js(START_JS % (json.dumps(url), json.dumps(ACCEPT)))
        t0 = time.time()
        while not (meta := js("window.__sf && {status: window.__sf.status, len: window.__sf.len, err: window.__sf.err}")):
            if time.time() - t0 > 60:
                raise RuntimeError(f"{url}: no answer in 60 s; stopping")
            time.sleep(0.2)
        body = "".join(js(f"window.__sf.body.slice({i}, {i + CHUNK})") for i in range(0, meta["len"], CHUNK))
        js("window.__sf = null")
        time.sleep(PACE)
        status = meta["status"]
        if status == 200:
            return json.loads(body)
        err = json.loads(body) if body.startswith("{") else {}
        if status == 404:
            raise NotFound(err.get("details") or body[:200])
        if status == 429:
            raise SystemExit("HTTP 429: Scryfall rate-limits this client for 30 s; stop and slow down, do not retry around it")
        if (status >= 500 or status == 0) and attempt < tries - 1:
            time.sleep(5 * 2 ** attempt)
            continue
        raise RuntimeError(f"{url}: HTTP {status} {err.get('code')}: {err.get('details') or meta.get('err') or body[:200]}")

def num(v):
    return float(v) if v is not None else None

def printings(name, max_pages=MAX_PAGES):
    """Every English print of a card (paper and digital), newest first, via the card's own prints_search_uri."""
    card = api("/cards/named?" + urllib.parse.urlencode({"exact": name}))
    url, rows, pages = card["prints_search_uri"], [], 0
    while url and pages < max_pages:
        page = api(url)
        pages += 1
        for c in page["data"]:
            p = c.get("prices") or {}
            rows.append({
                "set": c["set"], "set_name": c["set_name"], "number": c["collector_number"],
                "released": c["released_at"], "rarity": c["rarity"], "finishes": c["finishes"],
                "digital": c["digital"], "usd": num(p.get("usd")), "usd_foil": num(p.get("usd_foil")),
                "usd_etched": num(p.get("usd_etched")), "eur": num(p.get("eur")), "tix": num(p.get("tix")),
                "url": c["scryfall_uri"].split("?")[0],
            })
        url = page.get("next_page") if page.get("has_more") else None
    return card["name"], page["total_cards"], rows, url is None

on_scryfall_tab()
for name in CARDS:
    try:
        name, total, rows, complete = printings(name)
    except NotFound as e:
        print(f"{name}: not found: {e}")
        continue
    paper = [r for r in rows if not r["digital"]]
    usd = sorted((r for r in paper if r["usd"] is not None), key=lambda r: r["usd"])
    print(f"{name}: {total} prints ({len(paper)} paper, {len(rows) - len(paper)} digital), "
          f"{len(usd)} paper prints with a nonfoil USD price{'' if complete else '; stopped at MAX_PAGES'}")
    for label, r in (("cheapest", usd[0]), ("priciest", usd[-1])) if usd else ():
        print(f"   {label}: ${r['usd']:,.2f}  {r['set_name']} ({r['set'].upper()}) #{r['number']} {r['released']}  {r['url']}")
    for r in rows[:3]:
        print(f"   newest: {r['released']} {r['set'].upper():>5} #{r['number']:<5} usd {r['usd']} foil {r['usd_foil']} eur {r['eur']} tix {r['tix']} digital={r['digital']}")
```

Output observed on 2026-11-04:

```text
Lightning Bolt: 78 prints (69 paper, 9 digital), 51 paper prints with a nonfoil USD price
   cheapest: $0.10  Summer Magic / Edgar (SUM) #162 1994-06-21  https://scryfall.com/card/sum/162/lightning-bolt
   priciest: $650.00  Secret Lair Promo (SLP) #37 2025-02-21  https://scryfall.com/card/slp/37/lightning-bolt
   newest: 2026-11-02   SLC #83    usd None foil None eur None tix None digital=False
   newest: 2026-10-19  PLST #CLB-187 usd None foil None eur 0.98 tix None digital=False
   newest: 2026-10-02   FDC #163   usd 0.81 foil None eur 1.97 tix 0.68 digital=False
Black Lotus: 16 prints (13 paper, 3 digital), 2 paper prints with a nonfoil USD price
   cheapest: $1,800.00  Collectors' Edition (CED) #233 1993-12-10  https://scryfall.com/card/ced/233/black-lotus
   priciest: $3,299.99  30th Anniversary Edition (30A) #228 2022-11-28  https://scryfall.com/card/30a/228/black-lotus
   newest: 2023-12-08  OVNT #2023NA usd None foil None eur None tix None digital=False
   newest: 2023-11-24  OVNT #2023A usd None foil None eur None tix None digital=False
   newest: 2023-11-17  OVNT #2023EU usd None foil None eur None tix None digital=False
```

### 4. The same data from the site: checklist search and card pages (browser, HTML)

Use this when you need what a person sees on scryfall.com. The API (blocks 1-3) is faster and has more fields.

```python
import json, time, urllib.parse

SEARCHES = ["t:dragon", '!"black lotus"']    # Scryfall syntax, same as the site's search box
CARD_PAGES = [("lea", "161"), ("2xm", "129")]  # (set code, collector number)
MAX_PAGES = 3          # 175 rows per checklist page
PAUSE = 1.0            # seconds between page loads (robots.txt sets no crawl-delay; be polite anyway)

SITE = "https://scryfall.com"

def load(url):
    goto_url(url)
    wait_for_load()
    time.sleep(PAUSE)
    t = (js("document.title") or "").lower()
    if any(s in t for s in ("just a moment", "access denied", "attention required", "too many requests")):
        raise SystemExit(f"challenge or block page on {js('location.href')}: stop and back off, do not retry")

CARD_JS = r"""(() => {
  const txt = s => (document.querySelector(s) || {}).innerText?.replace(/\s+/g, ' ').trim() || null;
  const stores = [...document.querySelectorAll('#stores a')].map(a => {
    const m = a.innerText.replace(/\s+/g, ' ').trim().match(/^Buy (?:(\w+) )?on (\S+)\s*(?:✶ )?(.*)$/) || [];
    return {store: m[2], finish: m[1] || 'nonfoil', price: m[3] || null}; });
  return {url: location.href.split('?')[0], name: [...document.querySelectorAll('.card-text-card-name')].map(e => e.innerText.trim()).join(' // '),
          set: txt('.prints-current-set-name'), details: txt('.prints-current-set-details'), stores};
})()"""

ROWS_JS = r"""(() => {
  const head = [...document.querySelectorAll('#js-checklist thead th')].map(th => th.innerText.replace(/[▲▼]/g, '').trim().toLowerCase());
  const rows = [...document.querySelectorAll('#js-checklist tbody tr')].map(tr => {
    const o = {}; [...tr.cells].forEach((td, i) => o[head[i]] = td.innerText.trim() || null);
    o.url = SITE + tr.querySelector('a').getAttribute('href'); return o; });
  const next = [...document.querySelectorAll('a.button-n')].find(a => a.innerText.trim().startsWith('Next'));
  return {info: (document.querySelector('.search-info') || {}).innerText || null, rows, next: next ? next.getAttribute('href') : null};
})()""".replace("SITE", json.dumps(SITE))

def site_search(q, max_pages=MAX_PAGES):
    """Checklist view of scryfall.com/search: one row per card with set, number, cost, type, rarity, USD/EUR/TIX."""
    load(SITE + "/search?" + urllib.parse.urlencode({"q": q, "unique": "cards", "as": "checklist", "order": "name"}))
    if urllib.parse.urlparse(js("location.href")).path.startswith("/card/"):
        return "1 card (the site redirects a single match to its card page)", [js(CARD_JS)], True
    out, rows, pages = None, [], 0
    while True:
        page = js(ROWS_JS)
        pages += 1
        out = out or page["info"]
        rows += page["rows"]
        if not page["next"] or pages >= max_pages:
            return out, rows, page["next"] is None
        load(SITE + page["next"])

for q in SEARCHES:
    info, rows, complete = site_search(q)
    print(f"{q!r}: {info} | read {len(rows)} rows{'' if complete else ' (stopped at MAX_PAGES)'}")
    for r in rows[:3]:
        print("  ", {k: r.get(k) for k in ("set", "№", "name", "r", "usd", "eur", "tix", "details", "stores") if k in r})
for s, n in CARD_PAGES:
    load(f"{SITE}/card/{s}/{n}")
    print(json.dumps(js(CARD_JS), ensure_ascii=False))
```

Output observed on 2026-11-04:

```text
't:dragon': 1 – 175 of 444 cards where the card types include “dragon” | read 444 rows
   {'set': 'DTK', '№': '86', 'name': 'Acid-Spewer Dragon', 'r': 'U', 'usd': '$0.27', 'eur': '€0.17', 'tix': '0.03'}
   {'set': 'AFR', '№': '216', 'name': 'Adult Gold Dragon', 'r': 'R', 'usd': '$0.38', 'eur': '€0.38', 'tix': '0.02'}
   {'set': 'GN2', '№': '36', 'name': 'Akoum Hellkite', 'r': 'R', 'usd': '$0.44', 'eur': '€0.27', 'tix': None}
'!"black lotus"': 1 card (the site redirects a single match to its card page) | read 1 rows
   {'set': 'Vintage Masters (VMA)', 'name': 'Black Lotus', 'details': '#4 · Bonus · English · Nonfoil/Foil', 'stores': [{'store': 'TCGplayer', 'finish': 'nonfoil', 'price': None}, {'store': 'Cardmarket', 'finish': 'nonfoil', 'price': None}, {'store': 'Cardhoarder', 'finish': 'nonfoil', 'price': '75.72'}]}
{"url": "https://scryfall.com/card/lea/161/lightning-bolt", "name": "Lightning Bolt", "set": "Limited Edition Alpha (LEA)", "details": "#161 · Common · English · Nonfoil", "stores": [{"store": "TCGplayer", "finish": "nonfoil", "price": "$630.00"}, {"store": "Cardmarket", "finish": "nonfoil", "price": "€387.57"}, {"store": "Cardhoarder", "finish": "nonfoil", "price": null}]}
{"url": "https://scryfall.com/card/2xm/129/grim-lavamancer", "name": "Grim Lavamancer", "set": "Double Masters (2XM)", "details": "#129 · Rare · English · Nonfoil/Foil", "stores": [{"store": "TCGplayer", "finish": "nonfoil", "price": "$0.35"}, {"store": "TCGplayer", "finish": "foil", "price": "$0.40"}, {"store": "Cardmarket", "finish": "nonfoil", "price": "€0.51"}, {"store": "Cardmarket", "finish": "foil", "price": "€1.00"}, {"store": "Cardhoarder", "finish": "nonfoil", "price": "0.59"}]}
```

## URL patterns (all observed)

| URL | What it is |
|---|---|
| `api.scryfall.com/cards/search?q=<q>&unique=cards&order=name` | search, 175 per page; follow `next_page` |
| `api.scryfall.com/cards/named?exact=<name>[&set=<code>]` | one card by exact name, case and punctuation ignored |
| `api.scryfall.com/cards/named?fuzzy=<text>` | misspellings and partial words (`aust comm` -> Austere Command) |
| `api.scryfall.com/cards/<set>/<number>` | one exact print (`/cards/2xm/129` = Grim Lavamancer) |
| card `prints_search_uri` | all English prints, newest first |
| `scryfall.com/search?q=<q>&unique=cards&as=checklist&order=name[&page=N]` | site search as a table, 175 rows per page; `as=grid` (the default) shows 60 |
| `scryfall.com/card/<set>/<number>` | card page; the trailing slug is cosmetic (`/card/2xm/129/lightning-bolt` opened Grim Lavamancer) |

## Fields

Card object (API), the parts this task needs:

| Key | Notes |
|---|---|
| `name`, `set`, `set_name`, `collector_number`, `rarity`, `released_at` | `collector_number` is a string (`"CLB-187"`, `"2023NA"`) |
| `prices.usd` / `usd_foil` / `usd_etched` | USD strings or `null` (TCGplayer, per the purchase link) |
| `prices.eur` / `eur_foil` / `eur_etched` | EUR strings or `null` (Cardmarket) |
| `prices.tix` | MTGO event tickets (Cardhoarder) |
| `purchase_uris` | `tcgplayer`, `cardmarket`, `cardhoarder` links (Scryfall affiliate links) |
| `finishes` | `nonfoil`, `foil`, `etched` |
| `digital` | `true` for MTGO/Arena-only prints |
| `prints_search_uri`, `scryfall_uri`, `uri`, `oracle_id`, `tcgplayer_id`, `cardmarket_id` | links and cross-site ids |

List object: `total_cards`, `has_more`, `next_page`, `data[]`, `warnings[]`.

## Gotchas

- **The price on a name lookup or default search row is one print's price, not "the card's price".** `/cards/named?exact=Lightning Bolt` returned the newest print (Marvel Super Heroes Commander #806, $0.89); Limited Edition Alpha was $630.00. `exact=Black Lotus` returned the MTGO-only Vintage Masters print with only a `tix` price. Use block 3 and pick the print you mean.
- **Newest can be unreleased.** `fuzzy=aust comm` returned a Star Trek Commander print dated 2026-11-13 with every price `null`.
- **Prices can be odd.** The Summer Magic / Edgar Lightning Bolt (SUM #162) showed `usd` 0.10, the cheapest of 51 priced paper prints. They are affiliate estimates; check the store link before relying on an outlier.
- **Name search matches faces.** `lightning bolt` (block 1) also returned `Emeritus of Conflict // Lightning Bolt`.
- **Errors are JSON:** no match is a 404 with `code: not_found` (`Your query didn't match any cards...`); an ambiguous fuzzy name is a 404 (`Too many cards match ambiguous name "bolt"...`); a query whose terms are all invalid (`foo:bar`) is a 400 `bad_request`; a partly invalid query (`t:goblin foo:bar`) answers 200 with 561 cards and a `warnings` entry. Block 1 prints warnings; check them.
- **`prints_search_uri` is English only** (78 Lightning Bolt prints: 69 paper, 9 digital). Adding `include_multilingual=true` to that URL returned 167 prints in 11 languages.
- **CORS:** a cross-origin `fetch()` only exposes `cache-control` and `content-type` (plus `content-length` on the 400 seen); no rate-limit headers are readable from the page, so pace yourself.
- **Site search redirects one match to its card page** (`!"black lotus"` -> `/card/vma/4/black-lotus`); block 4 handles that.
- **Bulk needs:** for many cards or all prices, the docs say to use the daily bulk data files (https://scryfall.com/docs/api/bulk-data) instead of the search API, and to cache for at least 24 h.
- On a 429 or a challenge page, stop. Do not retry with a different user agent, session or IP.

## What does not work

- **Price history:** the card object carries only the current daily prices; there is no history endpoint in the API docs.
- **Listing-level prices** (sellers, conditions, quantities): not on Scryfall; follow `purchase_uris` to the store.
- **Calling the API faster than the documented limits:** 429 and a 30 s lockout; not attempted beyond the paced calls above.
