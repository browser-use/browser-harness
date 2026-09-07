# Lazada (lazada.sg) & RedMart — Product Search & Data Extraction

Field-tested against www.lazada.sg on 2026-05-29 (frozen ramen/udon competitor survey).
Unlike Shopee, Lazada SG search works **without login** and is far more reliable. The two
things that wasted calls were (1) large `js()` payloads silently returning `None`, and
(2) product links not following one clean pattern — both solved below.

RedMart lives inside Lazada: `redmart.lazada.sg` redirects to `www.lazada.sg`, RedMart
items appear in normal Lazada search (with a RedMart badge/tab), and clicking one lands on
a `www.lazada.sg/products/...html` PDP with RedMart delivery UI. Treat RedMart as Lazada.

## Navigation

### Search URL (primary entry point — no login needed)
```python
goto_url("https://www.lazada.sg/catalog/?q=frozen+ramen")  # spaces = +
wait(4)
```
- `/catalog/?q=X` frequently 302s to `/tag/X/?q=X&catalog_redirect_tag=true`. That's normal —
  results still load. Confirm with `page_info()["url"]`.
- Product detail URL pattern: `https://www.lazada.sg/products/pdp-i<itemId>.html`
  (sometimes `...-i<itemId>-s<skuId>.html`).

### Load the whole result grid before extracting
Lazada lazy-loads cards on scroll. `window.scrollTo` works here (unlike Shopee), so step
through a few offsets:
```python
for y in (400, 1200, 2200, 3200):
    js("window.scrollTo(0, %d)" % y); wait(0.6)
```

## Two traps that cost real time

### Trap 1 — large `js()` results come back as `None` (IPC size cap)
`js("JSON.stringify(Array.from(document.querySelectorAll('a')).map(...))")` over **all**
anchors (1000+ on a Lazada page) returns `None`/empty: the response exceeds the IPC
`recv(1<<16)` framing and is dropped. **Always filter and cap inside the JS** so the
returned payload is small (≤ ~60 short items). Small `js()` reads (a `.length`, one field)
work fine; it's only the big serialisations that fail.

### Trap 2 — product links have no single clean selector
On search/tag pages, `/products/` anchors are mostly the 2 sponsored ads; the real result
cards use varying markup, so href-filtering misses them. **Anchor on the price instead.**
Find leaf nodes whose text is exactly a price, climb to the enclosing card, read its title
link. This reliably yielded ~39 products per page:

```python
import json
expr = r"""
(function(){
  var out=[], seen={};
  var all=document.querySelectorAll('*');
  for (var i=0;i<all.length;i++){
    var el=all[i];
    if (el.children.length) continue;             // leaf nodes only
    var t=(el.innerText||'').trim();
    if (!/^\$[\d,]+\.\d{2}$/.test(t)) continue;    // a price leaf
    var card=el, title='', link='';
    for (var k=0;k<8 && card;k++){
      card=card.parentElement; if(!card) break;
      var a=card.querySelector('a[title], a[href*=".html"]');
      if (a){ title=(a.getAttribute('title')||a.innerText||'').replace(/\s+/g,' ').trim();
              if (title.length>6) break; }
    }
    if (title.length<6) continue;
    var key=title.slice(0,60); if(seen[key]) continue; seen[key]=1;
    var la=card.querySelector('a[href*=".html"]'); if(la) link=la.href.split('?')[0];
    out.push({name:title.slice(0,130), price:t, href:link});
    if (out.length>=60) break;                     // cap payload — see Trap 1
  }
  return JSON.stringify(out);
})()
"""
items = json.loads(js(expr) or "[]")
```

Note the JS escapes (`\$`, `\d`, `\s`) survive a `cat <<'PY'` heredoc because the delimiter
is quoted. If you instead keep the extractor in `agent-workspace/agent_helpers.py`, you
avoid all heredoc-escaping risk entirely (recommended for repeated runs).

## Single-invocation rule (avoids stale-tab `None`)

Each `browser-harness <<PY` call re-attaches to a tab; a *separate* call can attach to a
different/stale session and return `None` or junk. **Navigate + wait + scroll + extract in
ONE invocation.** If a read looks wrong, `ensure_real_tab()` then re-do the nav+extract in
a single call. Confirm you're live with `js("document.querySelectorAll('a').length")`
(~1000 on a loaded results page; ~8 means not rendered yet).

## Product detail page (PDP) extraction

Grocery/RedMart PDPs expose a clean spec grid in `document.body.innerText`. Scroll deep
(~3000px) first or the grid won't be rendered:

```python
goto_url("https://www.lazada.sg/products/pdp-i303976586.html"); wait(4)
for y in (600,1400,2200,3000): js("window.scrollTo(0,%d)"%y); wait(0.4)
txt = js("document.body.innerText") or ""
```

The text layout (note the **blank line between label and value**):
```
Groceries	Frozen	Convenience Foods	Ready-to-Eat Meals	<Title>     <- tab-joined breadcrumb
<Title>
Brand:<Brand>More Frozen from <Brand>
Pack Size

477 g
Place of Origin

Japan
Product Type

Frozen
$8.80                <- real price (the $60.00 above is the "free delivery" banner)
Add to cart
...
Sold by <seller>
```

Parser:
```python
import re
lines=[l.strip() for l in txt.split("\n")]
def nextval(i):                       # value sits 1-4 lines below its label (blanks between)
    for j in range(i+1, min(i+5,len(lines))):
        if lines[j].strip(): return lines[j].strip()
    return ""
d={"title":"","brand":"","pack_size":"","origin":"","ptype":"","price":"","soldby":""}
for i,l in enumerate(lines):
    if l.startswith("Brand:"):       d["brand"]=l.replace("Brand:","").split("More ")[0].strip()
    if l=="Pack Size":               d["pack_size"]=nextval(i)
    if l=="Net Weight" and not d["pack_size"]: d["pack_size"]=nextval(i)
    if l=="Place of Origin":         d["origin"]=nextval(i)
    if l=="Product Type":            d["ptype"]=nextval(i)
    if l.startswith("Sold by"):      d["soldby"]=l.replace("Sold by","").strip()
# price: the $x.xx just before "Add to cart", skipping the $60.00 free-delivery banner
cut=txt.find("Add to cart"); seg=txt[:cut] if cut>0 else txt
ps=[p for p in re.findall(r"\$[\d,]+\.\d{2}", seg) if p!="$60.00"]
if ps: d["price"]=ps[-1]
# title: last segment of the tab-joined breadcrumb line
for l in lines:
    if "\t" in l and ("Groceries" in l or "Frozen" in l):
        d["title"]=l.split("\t")[-1].strip(); break
```

Fields available: Brand, Pack Size (or Net Weight), Place of Origin, Product Type
(e.g. "Frozen"), price, Sold-by seller, breadcrumb category. RedMart-fulfilled listings
(sellers like "Kirei Japanese Food Supply", "Soon Seng Huat") reliably populate the grid;
so do most marketplace grocery sellers once you scroll far enough.

## Price gotcha: card price ≠ RSP

Search-result cards may show a **voucher/promo** price (e.g. $6.80) while the PDP shows the
true RSP (e.g. $7.90). For an accurate survey, open the PDP and read its price for RSP, and
record the card price as the promo. The "Platinum save $X / Coin save $X" lines in card
text are loyalty deltas, not the price — ignore them.

## Age-verification popup

Some queries trigger a "you must be at least 21 years" modal that blocks the grid. Dismiss
by button text (don't click pixels — layout shifts):
```python
js("Array.from(document.querySelectorAll('button')).find(b=>b.innerText==='Over 21')?.click()")
wait(1)
```

## Tab hygiene

Reuse one tab; don't `new_tab` per search. Close when done.
```python
tid = new_tab("https://www.lazada.sg/catalog/?q=frozen+ramen"); wait(4)
# ... reuse with goto_url for each subsequent query ...
close_tab(tid)
# end-of-task sweep:
for t in list_tabs(include_chrome=False):
    if "lazada.sg" in t["url"]: close_tab(t["targetId"])
```

## Exhaustiveness tip

One keyword misses SKUs. Run several phrasings and union by product name, e.g. for ramen:
`"frozen ramen"`, `"frozen ramen noodle soup"`, `"japanese frozen ramen"`; for udon:
`"frozen udon"`, `"frozen udon noodle soup"`, `"sanuki udon frozen"`. Lazada/RedMart had
far deeper frozen Japanese-noodle coverage than Shopee — it's the primary source for this
category.

## Gotchas (field-tested)

- **No login wall** — anonymous catalog search works (the opposite of Shopee).
- **Big `js()` serialisations return `None`** — filter + cap (≤~60 items) inside the JS.
- **Price-anchored extraction** beats href/selector hunting on result pages.
- **One invocation per nav+extract** — separate calls re-attach and may return `None`.
- **PDP spec values are 1-4 lines below the label** (blank lines between) — scan forward.
- **First `$` on a PDP is the `$60.00` delivery banner** — take the price before "Add to cart".
- **Card price may be a voucher price**, not RSP — confirm RSP on the PDP.
- **`/catalog/` 302s to `/tag/`** — expected, results still load.
- **Age popup** on some queries — click the "Over 21" button by text.
- **RedMart = Lazada** — same search and PDP; `redmart.lazada.sg` redirects to `www.lazada.sg`.
- **Reuse one tab, close when done** — avoid tab pile-up.
