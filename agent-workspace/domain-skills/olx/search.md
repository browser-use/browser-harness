# OLX Brasil (olx.com.br) — Car search results

Field-tested against olx.com.br (Autos > Carros, vans e utilitários) on 2026-08-27 from a real
Chrome session (CDP). Needs the browser: `http_get()`/curl get **403** on every search page.

## Search URL

```
https://www.olx.com.br/autos-e-pecas/carros-vans-e-utilitarios/{tipo}/estado-{uf}/{regiao}/{sub-regiao}?{filters}
```

- `{tipo}` is optional body type: `suv`, `hatch`, `sedan`, `pick-up`, ...
- Region slugs come from the site's own location tree, e.g.
  `estado-rj/rio-de-janeiro-e-regiao/teresopolis-e-regiao`, `estado-rj/regiao-serrana` (does not exist for cars — use the former).

Confirmed query params:

| param | meaning |
|---|---|
| `rs` | model-year **from** (`rs=2022`) |
| `re` | model-year **to** |
| `me` | max mileage (km) |
| `pe` | max price (BRL) |
| `ps` | min price |
| `sf=1` | sort: most recent |

Example: `.../suv/estado-rj/rio-de-janeiro-e-regiao/teresopolis-e-regiao?rs=2022&me=50000&pe=150000&sf=1`

Result count is in `innerText` as `/\d+ resultados/`.

## No `__NEXT_DATA__` any more

`window.__NEXT_DATA__` is `undefined` on the 2026 results page (older skills that read
`pageProps.ads` will silently get 0). Read the DOM instead.

## Ad links live on a regional subdomain

Ad anchors point to `https://rj.olx.com.br/...` (state subdomain), **not** `www.olx.com.br`.
Match `a[href*="olx.com.br/"]` and require the numeric id suffix `-\d{9,}` to skip nav links.

```python
cards = json.loads(js(r"""JSON.stringify((()=>{
  const seen=new Set(), out=[];
  for (const a of document.querySelectorAll('a[href*="olx.com.br/"]')) {
    if (!/-\d{9,}/.test(a.href) || seen.has(a.href)) continue;
    seen.add(a.href);
    // walk up to the smallest ancestor holding exactly one price and a km figure
    let el=a, best=null;
    for (let i=0;i<8 && el.parentElement;i++) {
      el=el.parentElement; const t=el.innerText||''; const n=(t.match(/R\$/g)||[]).length;
      if (n===1 && /km/i.test(t)) { best=el; break; }
      if (n>1) break;
    }
    out.push({href:a.href, text:((best||a).innerText||'').replace(/\s+/g,' ').trim()});
  }
  return out;})())"""))
```

Card text looks like:
`Hyundai Creta Platinum 1.0 TB 12V Flex AUT 2023 26.000 km Prata 1.0 R$ 117.900 Teresópolis, Várzea Hoje, 16:03`
→ title (ends with year) · km · colour · engine · optional "Aceita trocas" / "Reduziu o preço" · price · city, neighbourhood · posted.

Traps:
- Only the cards currently rendered have full text; the list is lazy — `scroll()` a few times
  before extracting, or the lower cards come back with the title only.
- The page has "Mais recentes em Carros" and sponsored blocks with the same anchor shape;
  they sit **after** the `Próxima página` pagination text in `innerText` — cut there.
- A dedicated "abaixo da FIPE" filter exists in the sidebar but has no obvious URL param;
  FIPE % is not in the card — compute it yourself.
