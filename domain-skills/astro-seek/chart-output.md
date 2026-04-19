# Astro-Seek — Chart Output

Charts on astro-seek are **server-rendered bitmaps**, not SVG. Every results page embeds several `<img>` tags pointing at chart URLs whose query strings carry the entire computed dataset (planet positions, house cusps, retrograde flags). You can either download the image as-is or parse the query string for typed numeric data without scraping the HTML tables.

**Bitmap format is not always PNG despite the `.png` extension.** Verified as of 2026-04-19:

| Chart type | Actual file format | Signature |
|---|---|---|
| `horoscope-chart4def-700__radix_*` (birth chart) | GIF87a | `47 49 46 38` |
| `horoscope-chart1snew-700__radix_*` (asteroids) | PNG | `89 50 4e 47` |
| `horoscope-chart1-700__radix_*` (sidereal + house-systems-calculator) | PNG | `89 50 4e 47` |
| `horoscope-chart6-700__radix_comparision_*` (house-systems comparison wheel) | PNG | `89 50 4e 47` |
| `horoscope-chart4def-700__composite_*` (composite) | PNG | `89 50 4e 47` |
| `horoscope-synastry-chart{N}-700__transits_*` (transit bi-wheel) | PNG | `89 50 4e 47` |
| `horoscope-synastry-chart23-700__{d1}_p_{d2}` (synastry — no TYPE) | PNG | `89 50 4e 47` |
| `horoscope-synastry-chart20-700__progressions_*` (progressed) | PNG | `89 50 4e 47` |

Don't hardcode a PNG signature check — the extension lies. `file` on the byte stream, or just trust the `Content-Type`. Only birth-chart radix is GIF; every other tool tested so far is PNG.

**Chart URLs require a `User-Agent` header.** A bare `urllib.request.urlopen(url)` returns **HTTP 403 Forbidden**. `http_get` in the harness works because it sets `User-Agent: Mozilla/5.0`. When downloading outside `http_get`, set the header yourself.

## No SVG anywhere

`document.querySelectorAll('svg').length === 0` on every tool tested. Don't waste time looking for inline SVG.

## Chart URL anatomy

There are **two base paths** on the CDN — single-wheel tools and bi-wheel/relationship tools use different prefixes:

```
Single wheel:  https://horoscopes.astro-seek.com/horoscope-chart{STYLE}-{SIZE}__{TYPE}_{date}.png?{payload}
Bi-wheel:      https://horoscopes.astro-seek.com/horoscope-synastry-chart{N}-{SIZE}__{TYPE}_{d1}_a_{d2}.png?{payload}
Bi-wheel (synastry special case — no TYPE):
               https://horoscopes.astro-seek.com/horoscope-synastry-chart{N}-{SIZE}__{d1}_p_{d2}.png?{payload}
```

Live filenames verified in the DOM:

```
horoscope-chart4def-700__radix_1-1-1990_12-00.png                           # birth chart
horoscope-chart1-700__radix_1-1-1990_12-00.png                              # sidereal (primary)
horoscope-chart1snew-700__radix_1-1-1990_12-00.png                          # asteroids (primary)
horoscope-chart4def-700__composite_1-1-1990_12-00_a_15-6-1992_18-30.png     # composite (primary, single wheel)
horoscope-synastry-chart20-700__transits_1-1-1990_12-0_a_19-4-2026_12-0.png # transit bi-wheel
horoscope-synastry-chart24-700__transits_..._a_..._.png                     # transit, style 24
horoscope-synastry-chart5-700__transits_..._a_..._.png                      # transit, style 5 (whole)
horoscope-synastry-chart23-700__1-1-1990_12-00_p_15-6-1992_18-30.png        # synastry (primary) — no TYPE, _p_ separator
horoscope-synastry-chart20-700__progressions_1-1-1990_12-00_a_19-4-2026.png # progressions (primary) — note: no time on d2
horoscope-synastry-chart24-700__secondary-progressions_..._a_..._.png       # progressions, style 24 — hyphenated TYPE
horoscope-chart6-700__radix_comparision_1-1-1990_12-00.png                  # house-systems-calculator comparison wheel — TYPE is Czech-misspelled "comparision" (missing 's'); carries BOTH cusp sets via dum_1..12 + dum_1_alter..12_alter
```

Notes:
- The bi-wheel uses `horoscope-synastry-chart{NUMBER}-...`, NOT `horoscope-chart{STYLE}-...`.
- TYPE tokens are **English plural**: `transits`, `progressions` (NOT `tranzit` / `progres`); the composite TYPE is `composite` (not `composit`); `secondary-progressions` has a literal hyphen.
- The transit-chart results page has multiple bi-wheel styles (chart5 / chart20 / chart24) co-existing.
- **Synastry is the odd one out**: its primary filename has *no* TYPE token and uses `_p_` as the date separator. Don't match with a universal `{TYPE}_{d1}_a_{d2}` regex.
- Some bi-wheel filenames drop the time on the second date (progressed chart20: `_a_19-4-2026`), while others keep it (progressed chart24: `_a_19-4-2026_12-00`). Parse the filename by splitting on `_a_` / `_p_` rather than assuming a fixed `D-M-YYYY_HH-MM` shape on both sides.

Multiple `<img>` tags coexist on a single results page. **`naturalWidth === 700` alone is NOT unique** — both `chart4def-700` and `chart4zone3-700` load at 700×700 when scrolled into view. Filter by style token AND size:

```python
# Birth chart (primary default-style wheel)
js("""
JSON.stringify(Array.from(document.querySelectorAll('img'))
  .filter(i => /horoscope-chart4def-700__radix_/.test(i.src)
            && !/minor_aspects|astroseek/.test(i.src)
            && i.naturalWidth === 700)
  .map(i => i.src))
""")

# Transit bi-wheel (primary colored-aspects style)
js("""
JSON.stringify(Array.from(document.querySelectorAll('img'))
  .filter(i => /horoscope-synastry-chart20-700__transits_/.test(i.src)
            && i.naturalWidth === 700)
  .map(i => i.src))
""")
```

Lazy `<img loading="lazy">` tags report `naturalWidth === 0` until scrolled into view. When scraping `http_get` HTML (no layout), filter by the URL regex alone — naturalWidth is a browser-only signal.

### `src=` attributes contain literal newlines

Astro-seek breaks its chart `src` URLs across multiple lines inside the HTML:

```html
<img src="https://horoscopes.astro-seek.com/horoscope-chart4def-700__radix_1-1-1990_12-00.png?
fortune_asp=1&vertex_asp=1&chiron_asp=1&…
```

A naive `[^"\s]+` regex stops at the first newline and returns a truncated URL. Use `[^"]+` and strip whitespace:

```python
m = re.search(r'src="(https://horoscopes\.astro-seek\.com/horoscope-chart4def-700__radix_[^"]+)"', html, re.S)
chart_url = re.sub(r'\s+', '', m.group(1)) if m else None
```

### Style tokens (single-wheel tools only)

| `STYLE` | Visual / used by |
|---|---|
| `4def` | Default modern, white background, colored aspect lines. **Birth chart + composite primary**. |
| `4zone3` | Astro-Seek branded, dark background, colored planet glyphs. Watermark variant. |
| `3` | Classic line style. Simpler, older look. |
| `4` | Alternate seen on sidereal + composite. |
| `1` | **Sidereal + house-systems-calculator primary**. `chart1-700__radix_…`. |
| `6` | **House-systems comparison wheel** (unique to house-systems-calculator). `chart6-700__radix_comparision_…`. |
| `1snew` | **Asteroids primary**. `chart1snew-700__radix_…`. Variant `8snew` is the watermark counterpart. |

STYLE is tool-dependent. The birth chart regex `chart4def-700__radix_` misses every tool in the bottom half of the table. When you probe a new tool, list all `/horoscope-chart[a-z0-9]+-\d+__/` matches in the DOM and pick whichever is the 700×700 non-watermark.

For bi-wheel tools the `{N}` is a numeric style id. Seen: `5`, `20`, `23`, `24`, `27`. Defaults vary by tool:

| Tool | Bi-wheel default |
|---|---|
| Transit | `chart20` |
| Synastry | **`chart23`** (not chart20 — styles 20/24/5 don't appear at all) |
| Progressions | `chart20` (plus `chart24` as `secondary-progressions`) |
| Composite (bi-wheel overlay) | `synastry-chart1-700__composite_transits_…` |

### `TYPE` tokens

| `TYPE` | Chart | Base path |
|---|---|---|
| `radix` | Single natal wheel (birth chart, asteroids, sidereal, traditional, house-systems-calculator, …) | `horoscope-chart` |
| `radix_comparision` | House-systems comparison wheel overlaying two cusp systems (unique to house-systems-calculator). **Note the Czech-origin misspelling: "comparision" has no `s`.** Query carries `dum_1..12` + `dum_1_alter..12_alter` + `vstyl=` visual-style param. | `horoscope-chart` |
| `composite` | Composite (single wheel from two charts) — note the `e`, NOT `composit` | `horoscope-chart` |
| `transits` | Bi-wheel — natal inner, transit outer | `horoscope-synastry-chart` |
| *(none)* | **Synastry — bi-wheel with Person A inner, Person B outer.** Filename is `__{d1}_p_{d2}.png` with no TYPE token. | `horoscope-synastry-chart` |
| `progressions` | Primary progressed bi-wheel (natal + progressed date). Plural, NOT `progres`. | `horoscope-synastry-chart` |
| `secondary-progressions` | Alternate progressed bi-wheel on the same page (chart24 style). Literal hyphen. | `horoscope-synastry-chart` |
| `composite_transits` | Bi-wheel overlaying composite + current transits, rendered on the composite tool page. | `horoscope-synastry-chart` |

The `_minor_aspects` infix and `gif=1` query mean an animated/minor-aspects variant — usually a duplicate of the static chart for the customize tab; ignore it. An `astroseek` infix is a watermark variant; also ignore.

**There is no universal TYPE-aware regex.** Each tool has its own combination of `{base_path, style, TYPE}`. Start by listing what's in the DOM:

```python
# list distinct base paths + TYPE tokens on a new tool's results page
js("""JSON.stringify(Array.from(new Set(
  Array.from(document.querySelectorAll('img'))
    .map(i => i.src.match(/\\/horoscope-[^?]+/))
    .filter(m => m).map(m => m[0].replace(/_\\d+-\\d+-\\d+.*$/,'_<date>'))
)))""")
```

Filename date is `D-M-YYYY_HH-MM` (no leading zeros on D/M, leading zeros on H-MM, e.g. `1-1-1990_12-00`).

## Downloading the chart bitmap

The chart URL is plain HTTP, no cookie required — **but a `User-Agent` header is**. Default Python UA (`Python-urllib/…`) returns `HTTP 403 Forbidden`. Set `Mozilla/5.0` or anything browser-like:

```python
import urllib.request
src = "https://horoscopes.astro-seek.com/horoscope-chart4def-700__radix_1-1-1990_12-00.png?p_slunce=280.8&…"
req = urllib.request.Request(src, headers={"User-Agent": "Mozilla/5.0"})
data = urllib.request.urlopen(req, timeout=20).read()
open("/tmp/chart.gif", "wb").write(data)   # Signature depends on chart type (see table at top)
```

`http_get` returns text and will mangle binary bytes — use `urllib.request` directly for binary downloads, or extract just the URL with `js` and curl from outside the harness.

## Reading data out of the chart query string

The chart URL's query encodes the entire chart dataset as floats. Parsing it is more reliable than scraping the HTML tables, because there are no `&deg;`/`&rsquo;` entities to deal with and angles are already decimal degrees.

| Param | Meaning |
|---|---|
| `p_slunce` | Sun longitude (deg, ecliptic) |
| `p_luna` | Moon |
| `p_merkur` | Mercury |
| `p_venuse` | Venus |
| `p_mars` | Mars |
| `p_jupiter` | Jupiter |
| `p_saturn` | Saturn |
| `p_uran` | Uranus |
| `p_neptun` | Neptune |
| `p_pluto` | Pluto |
| `p_uzel` | North Node |
| `p_lilith` | Lilith (Black Moon) |
| `p_chiron` | Chiron |
| `p_fortune` | Part of Fortune |
| `p_spirit` | Part of Spirit |
| `p_vertex` | Vertex |
| `dum_1` … `dum_12` | House cusps 1–12 (deg) |
| `dum_1_new`, `dum_10_new` | ASC and MC (rounded copies of dum_1 / dum_10) |
| `r_<planet>=ANO` | Retrograde flag — Czech `ANO` ("yes"). Absence == direct. |
| `tolerance` | Aspect orb tolerance setting (echoed from form) |
| `tolerance_paral` | Parallels orb (deg) |
| `nocache` | Cache-buster, ignore. |
| `gif=1` | Animated minor-aspects variant flag. |

Czech-to-English glossary you'll need:
- `slunce`=Sun, `luna`=Moon, `merkur`=Mercury, `venuse`=Venus, `mars`=Mars, `jupiter`=Jupiter, `saturn`=Saturn, `uran`=Uranus, `neptun`=Neptune, `pluto`=Pluto.
- `uzel`=Node, `lilith`=Lilith, `chiron`=Chiron, `fortune`=Part of Fortune, `spirit`=Part of Spirit, `vertex`=Vertex.
- `dum`=house, `radix`=natal, `tranzit`=transit, `synastrie`=synastry, `composit`=composite.
- `ANO`=yes (used for retrograde flags), `NE`=no.

For bi-wheel charts (`transits`, synastry, `progressions`), the query string contains both subjects' planets. **The prefix convention is tool-dependent, not style-dependent** — don't assume chart20 means `p_*` everywhere.

| Tool + chart style | Inner wheel | Outer wheel |
|---|---|---|
| Transit `synastry-chart20` (colored-aspects) | `p_slunce`, `p_luna`, … | `p_p_slunce`, `p_p_luna`, … (double-p) |
| Transit `synastry-chart24` (classic) | `planeta_slunce`, `planeta_luna`, … | `planeta_partner_slunce`, `planeta_partner_luna`, … |
| Transit `synastry-chart5` (whole-sign-style) | `planeta_slunce`, … | `planeta_partner_slunce`, … |
| Synastry `synastry-chart23` (primary) | `p_slunce`, … (plus extras `p_juzel`, `p_bstesti`, `p_bspirit`, `p_spirit`) | `p_p_slunce`, … |
| **Progressed `synastry-chart20`** (same style id, different tool!) | `planeta_slunce`, … | `planeta_partner_slunce`, … |
| Composite bi-wheel `synastry-chart1__composite_transits_` | `planeta_slunce`, … | `planeta_partner_slunce`, … |

Retrograde flags on the outer wheel use `r_partner_<planet>=ANO` (e.g. `r_partner_uzel=ANO`). House cusps on the outer wheel use `dum_partner_1`, `dum_partner_10`, etc. The same outer-wheel `_partner_` convention holds across every bi-wheel tool regardless of prefix choice on the inner wheel.

## Tools with no chart bitmap

Search/calendar tools do **not** emit any `horoscope-chart*` or `horoscope-synastry-chart*` image — the results page is a table of dated events. Confirmed: `/calculate-ephemeris-search-engine/` has zero chart tags. Don't hunt for chart URLs on these tools — scrape the rows instead.

## Capturing chart variants

Each rendering option (house system, sidereal/tropical, asteroid toggles, etc.) is a query param on the form URL. Build the URL for each variant, `http_get` to scrape data, and download the chart `<img>` for the screenshot. Remember: `[^"]+` (not `[^"\s]+`) to handle embedded newlines in the `src` attribute, and a `User-Agent` on the download:

```python
CHART_RE = re.compile(
    r'src="(https://horoscopes\.astro-seek\.com/horoscope-chart4def-700__radix_'
    r'(?!minor_aspects|astroseek)[^"]+)"',
    re.S,
)

def fetch(u):
    req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=20).read()

for variant in [{"house_system": "placidus"}, {"house_system": "koch"}, {"house_system": "whole_horizon"}]:
    url = build_results_url({**common_params, **variant})
    html = http_get(url)
    chart_src = re.sub(r'\s+', '', CHART_RE.search(html).group(1))
    open(f"chart-{variant['house_system']}.gif", "wb").write(fetch(chart_src))
```

## Tabs on the results page

Six tabs share the same DOM, all server-rendered up front (so they're scrapeable from a single `http_get`):

| Tab anchor | Content |
|---|---|
| `#tab1` | Chart wheel + birth-data summary (default visible) |
| `#tab2` | Customize / download options |
| `#tab3` | Horoscope Shape Characteristics — **placeholder only on initial load**, populated lazily via `id="radix_graf_3"` highslide gallery click |
| `#tab4` | Aspectarian — full list of aspects |
| `#tab5` | Technical positions table (Ecliptic, Equatorial, Horizontal coords) |
| `#tab6` | Dominant planets analysis |

Tab 3's content is the only lazy-loaded part. If you need it, click the tab in a real browser and wait for the image gallery to populate. Tabs 1, 2, 4, 5, 6 are present in the initial HTML response — `http_get` is sufficient.
