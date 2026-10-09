# FairPrice (fairprice.com.sg) — Product Search & Data Extraction

Field-tested against www.fairprice.com.sg on 2026-05-29 via a focused recon pass
(a few frozen ramen/udon searches + one PDP) during a competitor price survey. Coverage of
edge cases is lighter than the Shopee/Lazada skills, but the core search → extract → PDP
flow below is confirmed working. FairPrice SG is the **easiest of the three SG grocery
sites**: no login wall, no bot/traffic wall, no age popup, and a light page (~50 anchors,
~1–2k chars of text).

## Navigation

### Search URL (no login needed)
```python
goto_url("https://www.fairprice.com.sg/search?query=frozen%20ramen")  # spaces = %20 (or +)
wait(6)   # light page; results render in ~5-6s. wait_for_load() also tends to work here.
```
- Title becomes `Results For <query> | FairPrice`; body shows `Results for "<query>"`.
- No delivery address/postal code is required to see prices (the "Enter your address" /
  "Fees may apply" prompts do **not** block results).
- **Search is fuzzy** — a "frozen udon" query returned a shrimp-fritter ("Bakwan Udang").
  Always filter results by name relevance.

### Product detail URL
Pattern: `/product/<slug>-<numericCode>`, e.g.
`/product/shimadaya-frozen-shoyu-ramen-noodles-with-soup-stock-frozen-477g-90016285`
(some house-brand items are slug-only, e.g. `/product/chicken-collagen-ramen---frozen`).
```python
goto_url("https://www.fairprice.com.sg/product/shimadaya-frozen-shoyu-ramen-noodles-with-soup-stock-frozen-477g-90016285")
wait(5)
```

## Search results extraction

Unlike Lazada, FairPrice result cards use **clean `/product/` anchors**, so anchor on those
and climb to the card that contains the price. Each card's innerText is conveniently rich:
`$<price> <name> <packSize> By <date> Add to cart` (or `... Out of stock`).

```python
import json
expr = r"""
(function(){
  var out=[], seen={};
  var as=document.querySelectorAll('a[href*="/product/"]');
  for(var i=0;i<as.length;i++){
    var a=as[i], h=a.getAttribute('href')||'';
    if(seen[h]) continue; seen[h]=1;
    var card=a;
    for(var k=0;k<6 && card;k++){ card=card.parentElement;
      if(card && /\$[\d,]+\.\d{2}/.test(card.innerText||'')) break; }
    var t=card?(card.innerText||'').replace(/\s+/g,' ').trim():'';
    var p=(t.match(/\$[\d,]+\.\d{2}/g)||[]);
    out.push({href:h, price:p[0]||'', card:t.slice(0,110)});
    if(out.length>=40) break;
  }
  return JSON.stringify(out);
})()
"""
items = json.loads(js(expr) or "[]")
```

Field notes:
- **`price`**: take the **first** `$x.xx` in the card text — that's the selling price.
  FairPrice has no "$60 free-delivery" banner (the Lazada trap), so first-match is safe.
- **Card text begins with the price**, then the name. To get a clean name, strip the leading
  price token: `name = re.sub(r'^\$[\d,]+\.\d{2}\s*', '', card)` then cut at ` By ` /
  ` Add to cart` / ` Out of stock`.
- **Pack size is inline** in the card (e.g. `477 G`, `150 G`, `2 x 150 G`) — already captured
  in the card text, no PDP needed for size.
- Result sets are **small and low-noise** (8 for "frozen ramen", 4 for "frozen udon") — far
  cleaner than Shopee. No pagination/"load more" surfaced for these queries; treat the grid
  as a single set.

## Product detail page (PDP) — richest of the three sites

PDP innerText carries labelled fields, each **value on the line after its label** (except
`Brand:` which is inline):

```
Home  Frozen  Frozen Food  Ready Meals          <- breadcrumb
$8.80                                            <- price (first $ on page)
Shimadaya Frozen Shoyu Ramen Noodles with Soup Stock   <- name
477 G                                            <- pack size
Brand:Shimadaya
Sold by:
Kirei Japanese Food Supply                       <- marketplace seller
KEY INFORMATION
<description: flavour, portions, etc.>
COUNTRY/PLACE OF ORIGIN
Japan
STORAGE INFORMATION
Keep frozen at or below -15 degree C ...         <- confirms frozen vs chilled
```

Parser:
```python
import re
txt = js("document.body.innerText") or ""
lines=[l.strip() for l in txt.split("\n")]
def after(label):
    for i,l in enumerate(lines):
        if l==label:
            for j in range(i+1, min(i+4,len(lines))):
                if lines[j].strip(): return lines[j].strip()
    return ""
d={}
m=re.search(r"\$[\d,]+\.\d{2}", txt); d["price"]=m.group(0) if m else ""
for l in lines:
    if l.startswith("Brand:"): d["brand"]=l.split("Brand:")[1].strip()
d["origin"]   = after("COUNTRY/PLACE OF ORIGIN")
d["storage"]  = after("STORAGE INFORMATION")          # tells frozen vs chilled
d["desc"]     = after("KEY INFORMATION")
d["soldby"]   = after("Sold by:")
# name/packsize: the two non-empty lines right after the price line
```

Fields you can reliably pull: **price, name, pack size, Brand, Sold-by seller,
COUNTRY/PLACE OF ORIGIN, STORAGE INFORMATION (frozen/chilled), KEY INFORMATION
(description/flavour/portions)**. This is the only one of the three sites that exposes a
storage line — useful to confirm a product is genuinely frozen.

## Coverage note

FairPrice carries SKUs **not** on Lazada (e.g. "Shimadaya Reito Tenobe Masari Frozen Udon",
"Kirei Premium Shoyu Tonkotsu Ramen") and overlaps on others (Little Totler, Shimadaya
Shoyu, Kirei, Daisho). Use it as a **complementary source** alongside Lazada/RedMart —
don't assume Lazada coverage is a superset.

## Tab hygiene

Open once, reuse with `goto_url`, close when done — don't `new_tab` per search.
```python
tid = new_tab("https://www.fairprice.com.sg/search?query=frozen%20ramen"); wait(6)
# reuse with goto_url for each subsequent query / PDP ...
close_tab(tid)
# end-of-task sweep:
for t in list_tabs(include_chrome=False):
    if "fairprice.com.sg" in (t.get("url") or ""): close_tab(t["targetId"])
```

## Gotchas (field-tested)

- **No login / bot / age wall** — easiest of the three SG sites; anonymous search works.
- **Light, fast page** — `wait(5-6)` is plenty; no full-page-screenshot or scroll-hang issues like Shopee.
- **`/product/` anchors are clean** — anchor on them directly (no price-walk hack needed, unlike Lazada).
- **Card text starts with the price** — strip the leading `$x.xx` to get the name; pack size is inline in the card.
- **First `$` on a PDP IS the price** — no delivery-banner trap (unlike Lazada's `$60.00`).
- **PDP labels → value on the next line**; `Brand:` is inline. `STORAGE INFORMATION` confirms frozen vs chilled.
- **Fuzzy search** — irrelevant items can appear (e.g. "Udang" matched "udon"); filter by name.
- **Marketplace sellers** ("Sold by: ...") — many Japanese frozen items are 3rd-party marketplace listings, not FairPrice house stock.
- **Unique catalogue** — has SKUs absent from Lazada; treat as complementary, not redundant.
- **Reuse one tab, close when done.**
