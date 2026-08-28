# Webmotors (webmotors.com.br) — Used-car search & listing data

Field-tested against webmotors.com.br on 2026-08-27 from a real Chrome session (CDP).
Brazil's largest car classifieds. Fully behind PerimeterX (HUMAN) — plain HTTP does not work.

## Bot detection: use the page's own fetch, never `http_get`/curl

- `http_get()` / curl on any page **or** on `/api/search/car` returns **403** with a PerimeterX
  captcha JSON (`{"appId":"PX7Vv0zOst", ... "blockScript": ...}`).
- Loading the site in the attached Chrome tab passes silently, and a **same-origin `fetch()` from
  page context** to the internal search API also passes (cookies + PX token ride along).

So the pattern is: `navigate()` to any webmotors.com.br page once, then call the JSON API via `js()`.

## Private search API (10× faster than scraping cards)

The results page itself calls:

```
GET /api/search/car?url=<url-encoded search URL>&displayPerPage=47&actualPage=<n>
    &showMenu=false&showCount=true&showBreadCrumb=false&testAB=false&returnUrl=false
```

`url` is a **search URL of the form `https://www.webmotors.com.br/carros/rj-teresopolis?<filters>`**
(city slug in the path, everything else as query params). The pretty SEO URL the browser shows
(`/carros/rj-teresopolis/suv/de.2022/ate.2026?...`) is *not* what the API wants — passing it
returns `SearchResults: null` / `Count: null`.

Confirmed filter params (query-string on the inner URL):

| param | meaning | example |
|---|---|---|
| `localizacao` | lat,lng + radius | `-22.4169605%2C-42.9756016x50km` |
| `estadocidade` | state-city label | `Rio%20de%20Janeiro-teresopolis` |
| `marca1=suv` | body-type pseudo-brand (also works for hatch/sedan) | `suv` |
| `anode` / `anoate` | model-year min / max | `2022` / `2026` |
| `kmate` / `kmde` | max / min odometer | `50000` |
| `precoate` / `precode` | max / min price | `150000` |
| `ordenarpor` | sort: `1` relevance, `2` price asc | `2` |
| `page` | page number (also pass `actualPage`) | `1` |

`displayPerPage=47` is what the site uses; 47 items per page came back reliably.
`Pagination.PageTotal` tells you how many pages. ~20 pages / 918 rows pulled in ~30 s with a 0.4 s sleep.

```python
import json, time, urllib.parse
navigate("https://www.webmotors.com.br/carros/rj-teresopolis")   # any WM page, once
wait_for_load(); time.sleep(3)

inner = ("https://www.webmotors.com.br/carros/rj-teresopolis?ordenarpor=2&tipoveiculo=carros"
         "&localizacao=-22.4169605%2C-42.9756016x50km&estadocidade=Rio%20de%20Janeiro-teresopolis"
         "&marca1=suv&kmate=50000&anode=2022&anoate=2026&precoate=150000")
rows = []
for p in range(1, 40):
    url = ("/api/search/car?url=" + urllib.parse.quote(inner + f"&page={p}", safe="")
           + f"&displayPerPage=47&actualPage={p}&showMenu=false&showCount=true"
             "&showBreadCrumb=false&testAB=false&returnUrl=false")
    d = json.loads(js("fetch(%s).then(r=>r.text())" % json.dumps(url)))
    res = d.get("SearchResults") or []
    rows += res
    if len(res) < 47: break
    time.sleep(0.4)
```

### Record shape (the useful bits)

```
UniqueId                      -> ad id (needed for the ad URL)
FipePercent                   -> asking price as % of the FIPE table value  ← gold for "is it a deal"
GoodDeal / HotDeal            -> site's own flags (GoodDeal=True ≈ FipePercent ≤ ~99)
Prices.Price                  -> asking price (BRL)
Specification.Title / Make.Value / Model.Value / Version.Value
Specification.YearFabrication (str) / YearModel (float) / Odometer (float)
Specification.BodyType        -> "Utilitário esportivo" | "Hatchback" | "Sedã" | "Picape" | ...
Specification.VehicleAttributes[].Name -> "Único dono", "Garantia de fábrica", "Aceita troca", ...
Specification.Auction (bool), Armored ("N"/"S"), Color.Primary
Seller.City / State / AdType.Value ("Concessionária" | "Loja" | "Pessoa Física") / Id
LongComment                   -> free text; dealers sometimes hide "price is entry + financing" here
```

Traps:
- `marca1=suv` is *not* strict — hatches/sedans still come back. Filter on `Specification.BodyType`.
- Dealer groups list the **same car in several cities** (same title/km/price, different `Seller.City`).
  Dedupe on `(Title, YearFabrication, YearModel, Odometer, Price)`.
- The radius search is straight-line: a 50 km radius from Teresópolis-RJ reached Niterói/São Gonçalo.

## Ad URL pattern

```
https://www.webmotors.com.br/comprar/{make}/{model}/{version-slug}/4-portas/{yearFab}-{yearModel}/{UniqueId}
```

Slug rule that resolved 14/14 ads: lowercase, strip accents, **drop dots** (`1.2` → `12`), replace
every other non-alphanumeric run with `-`. Example:
`/comprar/chevrolet/tracker/12-turbo-flex-premier-automatico/4-portas/2023-2024/78502483`.
A garbage version slug (e.g. `x`) redirects to a search page instead of the ad — the id alone is not enough.

The ad page's `innerText` contains `Valor anunciado\nR$ 103.000` and, below it, the site's own
average (`Webmotors R$ ...`) and `fipe R$ ...` figures.

## Results page (if you must scrape the DOM)

- `__NEXT_DATA__.props.pageProps.dehydratedState` holds the same records as the API.
- Card text is fine for a quick `document.body.innerText` read; count is in
  `/[\d.]+ anúncios encontrados/`.
- `wait_for_load()` then ~3–5 s: the list hydrates after `readyState === "complete"`.
