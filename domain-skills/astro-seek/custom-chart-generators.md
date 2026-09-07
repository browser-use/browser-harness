# Astro-Seek — Custom Chart Generators (bi / tri / quadri-wheel)

A family of tools that **take pasted planet positions instead of birth data**.
Because you supply the positions, these are the way to render *your own* data in
astro-seek's house style — useful for like-for-like visual comparison rather
than benchmarking their ephemeris.

Reachable only from `/advanced-astrology-chart-tools-tables` (the "Astro Tools"
page); they are **not** in the main nav and not linked from the tool index, so
a nav crawl will miss them.

| Tool | Form URL |
|---|---|
| Bi-wheel layout customizer | `/bi-wheel-chart-customizer` |
| Custom bi-wheel generator | `/custom-synastry-chart-generator` |
| Custom **tri**-wheel generator | `/tri-wheel-chart-astrology-calculator` |
| Custom **quadri**-wheel generator | `/quadri-wheel-chart-astrology-calculator` |

Results URL: `/calculate-tri-wheel-chart-astrology-calculator/#chart_generated`
(same shape for the others). GET, so the result is a permalink.

## Field map (tri-wheel; bi/quadri follow with fewer/more letters)

| Field | Meaning |
|---|---|
| `pozice_import_a` / `_b` / `_c` | **textarea** — planet positions, one per line. `a` = inner wheel, `b` = middle, `c` = outer |
| `slovo_chart_a` / `_b` / `_c` | free-text label printed in the chart's corner caption |
| `house_layout` | 0 = aligned outer houses, else non-aligned |
| `barva_planet` | planet colour scheme |
| `barva_stupne` | degree-text colour |
| `partner_domy` | whose houses to draw |
| `markers_hide` | show/hide markers |
| `grey`, `barva_invert` | greyscale / invert |
| `generate_chart` | **the submit button — required** (see gotcha) |

### Position line format

```
Sun,Aries,21°55'
Jupiter,Sagittarius,19°43',R
```

`Name,Sign,DEG°MM'` with an optional `,R` for retrograde. Sign names are English
and full ("Sagittarius", not "Sag"). **Cap: 10 objects per wheel** — an 11th
line is silently dropped, so send the ten majors and leave nodes/Chiron out.

## Gotchas

**`form.submit()` renders nothing.** The submit input is
`input[name=generate_chart]`, and the backend keys chart generation off that
parameter. Calling `document.forms[0].submit()` sends every field *except* the
button's own name/value, so you land on the results URL with your data in the
query string, the textareas correctly repopulated, and **no chart** — which
looks like a silent failure rather than a missing param. Click the element
instead:

```python
js("document.querySelector('input[name=generate_chart]').click()")
```

The same trap applies to any astro-seek form whose submit input carries a name.

**The output image is `chart35custom`, 800×800 — not 700.** Every other chart on
the site is 700px, so a `naturalWidth===700` filter (the usual idiom, see
`chart-output.md`) finds nothing here:

```
horoscope-synastry-chart35custom-700__tri_wheel_astroseek_customized_chart_.png?bdata=1&…
```

Note the filename still says `-700` while the rendered bitmap is 800 — filter on
the `chart35custom` token, or on `naturalWidth > 300`, not on an exact size.

**Fetching the PNG needs the page's own session.** A bare `http_get` of
`horoscopes.astro-seek.com` returns **403** (Cloudflare). Fetch in-page and hand
the bytes back as base64:

```python
b64 = js("""(async()=>{const i=[...document.querySelectorAll('img')].find(i=>i.naturalWidth===800);
const r=await fetch(i.src.replace(/\\s+/g,''));const b=await r.arrayBuffer();
let s='';const u=new Uint8Array(b);for(let k=0;k<u.length;k++)s+=String.fromCharCode(u[k]);return btoa(s);})()""")
open("out.png","wb").write(base64.b64decode(b64))
```

The `.replace(/\s+/g,'')` is required — astro-seek breaks long chart `src` URLs
across lines inside the HTML (see `gotchas.md`).

## Wheel identity in the output

The generator prints the three `slovo_chart_*` labels as corner captions
(`#1: Inner Wheel / <label>` top-left, `#2: Middle Wheel` bottom-left,
`#3: Outer Wheel` bottom-right) rather than an in-figure legend. Worth knowing
if you are scraping which ring is which.
