"""Agent-editable browser helpers.

Task-specific extractors for the frozen ramen/udon competitor survey.
Keeping JS here as plain strings avoids shell/heredoc escaping problems.
"""
import json


def _eval(expr):
    from browser_harness.helpers import js
    return js(expr)


def laz_list(limit=60):
    """Lazada: price-anchored card extraction. Walk up from each price node
    to a card container, grab its title. Small payload (filtered in JS)."""
    expr = r"""
    (function(){
      var out=[]; var seen={};
      var all=document.querySelectorAll('*');
      for (var i=0;i<all.length;i++){
        var el=all[i];
        if (el.children.length) continue;            // leaf nodes only
        var t=(el.innerText||'').trim();
        if (!/^\$[\d,]+\.\d{2}$/.test(t)) continue;   // a price leaf
        // climb to a card that also contains a product title link
        var card=el; var title='';
        for (var k=0;k<8 && card;k++){
          card=card.parentElement;
          if (!card) break;
          var a=card.querySelector('a[title], a[href*=".html"]');
          if (a){
            title=(a.getAttribute('title')||a.innerText||'').replace(/\s+/g,' ').trim();
            if (title.length>6) break;
          }
        }
        if (title.length<6) continue;
        var key=title.slice(0,60);
        if (seen[key]) continue; seen[key]=1;
        var link='';
        var la=card.querySelector('a[href*=".html"]');
        if (la) link=la.href.split('?')[0];
        out.push({name:title.slice(0,130), price:t, href:link});
        if (out.length>=LIMIT) break;
      }
      return JSON.stringify(out);
    })()
    """.replace("LIMIT", str(limit))
    r = _eval(expr)
    return json.loads(r) if r else []


def shopee_list():
    """Return list of {name, price, href} for a Shopee search page."""
    expr = r"""
    (function(){
      var out=[]; var seen={};
      var items=document.querySelectorAll('li.shopee-search-item-result__item, .shopee-search-item-result__item');
      if(!items.length){
        var anchors=document.querySelectorAll('a');
        for (var i=0;i<anchors.length;i++){
          var a=anchors[i]; var h=a.href||'';
          if (!/i\.\d+\.\d+/.test(h)) continue;
          var key=h.split('?')[0];
          if (seen[key]) continue; seen[key]=1;
          var txt=(a.innerText||'').replace(/\s+/g,' ').trim();
          if (txt.length>4) out.push({name:txt.slice(0,140), price:'', href:key});
        }
        return JSON.stringify(out);
      }
      for (var i=0;i<items.length;i++){
        var el=items[i];
        var a=el.querySelector('a');
        var h=a?a.href:'';
        var key=h?h.split('?')[0]:'';
        var txt=(el.innerText||'').replace(/\s+/g,' ').trim();
        var m=(el.innerText||'').match(/\$[\d,]+(\.\d+)?/g);
        out.push({name:txt.slice(0,140), price:m?m.join(' / '):'', href:key});
      }
      return JSON.stringify(out);
    })()
    """
    r = _eval(expr)
    return json.loads(r) if r else []


def page_text():
    return _eval("document.body.innerText") or ""


def laz_detail():
    """Parse a Lazada PDP into a dict of useful fields from page innerText."""
    txt = page_text()
    lines = [l.strip() for l in txt.split("\n")]
    d = {"title": "", "brand": "", "pack_size": "", "origin": "",
         "ptype": "", "price": "", "soldby": "", "breadcrumb": ""}
    import re
    # breadcrumb line contains tab-joined path ending in the title
    for l in lines:
        if "Groceries" in l and "\t" not in l and len(l) > 20:
            pass
    # title: the heading repeats right after breadcrumb; take the longest
    # line that looks like a product title
    def nextval(i):
        for j in range(i + 1, min(i + 5, len(lines))):
            if lines[j].strip():
                return lines[j].strip()
        return ""
    for i, l in enumerate(lines):
        if l.startswith("Brand:"):
            d["brand"] = l.replace("Brand:", "").split("More ")[0].strip()
        if l == "Pack Size":
            d["pack_size"] = nextval(i)
        if l == "Net Weight" and not d["pack_size"]:
            d["pack_size"] = nextval(i)
        if l == "Place of Origin":
            d["origin"] = nextval(i)
        if l == "Product Type":
            d["ptype"] = nextval(i)
        if l.startswith("Sold by"):
            d["soldby"] = l.replace("Sold by", "").strip()
    # price: the $x.xx just before the first "Add to cart" (skip $60 banner)
    cut = txt.find("Add to cart")
    seg = txt[:cut] if cut > 0 else txt
    prices = re.findall(r"\$[\d,]+\.\d{2}", seg)
    prices = [p for p in prices if p != "$60.00"]
    if prices:
        d["price"] = prices[-1]
    elif re.search(r"\$[\d,]+\.\d{2}", txt):
        d["price"] = re.search(r"\$[\d,]+\.\d{2}", txt).group(0)
    # title: last segment of the breadcrumb line (tab-joined)
    for l in lines:
        if "\t" in l and ("Groceries" in l or "Frozen" in l):
            d["title"] = l.split("\t")[-1].strip()
            d["breadcrumb"] = " > ".join(l.split("\t"))
            break
    if not d["title"]:
        cands = [l for l in lines[:30] if len(l) > 15 and any(c.isalpha() for c in l)
                 and "FEEDBACK" not in l and "delivery" not in l.lower()]
        if cands:
            d["title"] = max(cands, key=len)
    return d
