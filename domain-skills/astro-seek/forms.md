# Astro-Seek — Forms & City Autocomplete

Every tool form on `horoscopes.astro-seek.com` is a `<form method="get">`. **Default path: drive the form in a browser like a human would.** The form's jQuery autocomplete quietly handles the lat/lon/tzid fields for you, and field names and option values stay in sync with whatever the site changes. URL construction is still supported as a fast path for bulk scraping (see "Fast path" at the bottom).

## Default: drive the form (one tool run, ~10–15 s)

```python
import time, json

# 1. Open the tool's form page in a new tab (not goto — goto clobbers the user's tab).
new_tab("https://horoscopes.astro-seek.com/birth-chart-horoscope-online")
wait_for_load()
time.sleep(1.5)  # let jQuery + autocomplete JS attach

# 2. Set every <select>/<input> via jQuery so .change() fires. Zero-pad H/M/S.
js("""(function() {
  jQuery('[name=narozeni_den]').val('1').change();
  jQuery('[name=narozeni_mesic]').val('1').change();
  jQuery('[name=narozeni_rok]').val('1990').change();
  jQuery('[name=narozeni_hodina]').val('12').change();   // "12", "00"..."23"
  jQuery('[name=narozeni_minuta]').val('00').change();   // "00"..."59"  NOT "0"
  jQuery('[name=narozeni_sekunda]').val('00').change();
  jQuery('[name=house_system]').val('placidus').change();
  return 'set';
})()""")

# 3. Coordinate-click the city input (bypasses password-manager focus overlays),
#    then type + wait for autocomplete + commit with ArrowDown + Enter.
rect = js("""(function(){
  var el = document.querySelector('#city');
  el.scrollIntoView({block:'center'});
  var r = el.getBoundingClientRect();
  return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2});
})()""")
r = json.loads(rect)
click(r["x"], r["y"])
time.sleep(0.3)
js("document.querySelector('#city').value='';")
type_text("London")              # insertText, NOT per-char press_key (see gotchas)
time.sleep(1.8)                   # 300ms debounce + live API call
press_key("ArrowDown")
press_key("Enter")
time.sleep(0.6)

# 4. Verify the autocomplete committed — tzid_id + sirka_* + delka_* are now populated
#    in hidden fields. If tzid_id is empty, the dropdown never opened; retry click + type.
assert js("document.querySelector('[name=narozeni_tzid_id]').value"), "autocomplete didn't commit"

# 5. Submit. Use the form directly — bypasses any stale click handlers.
#    Most tools have exactly one user-facing form so forms[0] is right.
#    Exception: aspect-search has 4 forms; forms[0] is a timezone sub-form, forms[1] is the real search.
#    When in doubt, check `document.forms[N].action` to pick the right N.
js("document.forms[0].submit()")
wait_for_load()
time.sleep(1.2)

# 6. Materialise lazy chart imgs before querying them.
js("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(1.0)
js("window.scrollTo(0, 0);")

# 7. Read the primary chart URL out of the DOM (see chart-output.md for the filter regex).
chart = json.loads(js("""
  JSON.stringify(Array.from(document.querySelectorAll('img'))
    .filter(i => /horoscope-chart4def-700__radix_/.test(i.src)
              && !/minor_aspects|astroseek/.test(i.src))
    .map(i => i.src.replace(/\\s+/g, '')))
"""))[0]
```

**Why this is the default:** the form-driven path mirrors what a human does — the autocomplete populates `narozeni_sirka_stupne/_minuty/_smer` and `narozeni_delka_stupne/_minuty/_smer` automatically. The URL-built path silently defaults to **lat 0°, lon 0° at the equator** when those six fields are omitted, which masks house-system bugs (all quadrant systems agree at the equator).

### Multi-subject tools (synastry, transit, composite, progressions)

Same recipe twice, with prefixes. The transit form has `#muz_city` (Person A / natal) and `#zena_city` (Person B / transit date); fields use `muz_narozeni_*` and `zena_narozeni_*` prefixes. Set each subject's selects, coordinate-click each city input separately, type + commit each autocomplete, then submit once.

```python
# Person A (natal)
js("jQuery('[name=muz_narozeni_rok]').val('1990').change(); ...")
click_city("#muz_city", "London")
# Person B (transit date / partner)
js("jQuery('[name=zena_narozeni_rok]').val('2026').change(); ...")
click_city("#zena_city", "New York")
js("document.forms[0].submit()")
```

**Per-tool city-input differences** — confirm with `document.querySelector('#<id>')` on a new tool:

| Tool | `#muz_city` | `#zena_city` | `#tranzity_city` |
|---|---|---|---|
| Birth chart, asteroids, sidereal, traditional | — (`#city`) | — | — |
| Transit, synastry | ✓ | ✓ | — |
| Composite | ✓ | ✓ | ✓ (transit date for the bi-wheel overlay; can be left blank) |
| Secondary progressions | ✓ | **none — progression date reuses the natal location; set `zena_narozeni_den/mesic/rok/hodina/minuta` only** | — |

Tools without a city input for a given subject don't need any autocomplete call for that side. Just set the date selects via jQuery and submit.

### Extended-settings panel

`<div id="toggle_prvky_url">` (and friends like `toggle_adjust_coordinates`) start with `display: none`. To set values there, either click the trigger (a `<strong>` with text like "Extended settings" / "+") to expand, **or** set them via `jQuery('[name=foo]').val(...).change()` directly — the inputs are in the form regardless of visibility.

## City autocomplete API (the only private API)

Two endpoints, both on `horoscopes.astro-seek.com`:

| Endpoint | Returns |
|---|---|
| `GET /api_gmaps3.php?term=<query>` (`minLength=3`) | JSON array of suggestions: `[{value, label, id}, …]`. `value` is the display string, `label` adds coordinates, `id` is the place id for the next call. |
| `GET /api_gmaps3.php?place_id=<id>` | JSON object with the city's lat/lon and timezone id: `{mesto, stat_kratky, podstat, podstat_kratky, sirka_stupne, sirka_minuty, sirka_smer, delka_stupne, delka_minuty, delka_smer, tzid_id}` |

The `id` from the first call is **not** the `tzid_id` — you must make the second call to get the timezone. When you drive the form, the jQuery select handler makes both calls and populates the hidden fields for you; you only need to hit the API directly when URL-building.

`sirka_smer` (latitude direction): `"0"` = North, `"1"` = South.
`delka_smer` (longitude direction): `"0"` = East, `"1"` = West.

Autocomplete is jQuery UI with `delay: 300` and `minLength: 3`. Dropdown is `ul.ui-autocomplete.ui-front`; items are `li.ui-menu-item > a.ui-menu-item-wrapper`. The `<ul>`'s id (`#ui-id-1`/`#ui-id-2`/…) increments across interactions — match by class, not id.

## Mechanics reference

### Setting `<select>` values

`document.querySelector('[name=narozeni_rok]').value = '1990'` **often does not stick** — the form submits with the default. Use jQuery:

```js
jQuery('[name=narozeni_rok]').val('1990').change();
```

Option-value quirks that cost debugging time:

| Field | Option-value format |
|---|---|
| `narozeni_den` | `"1"`, `"2"`, … `"31"` (unpadded) |
| `narozeni_mesic` | `"1"`, `"2"`, … `"12"` (unpadded) |
| `narozeni_rok` | `"1800"`, `"1801"`, … `"2099"`; also `"before1800"` |
| `narozeni_hodina` | `"00"`, `"01"`, … `"23"` (**zero-padded**) |
| `narozeni_minuta` | `"00"`, `"01"`, … `"59"` (**zero-padded**) |
| `narozeni_sekunda` | `"00"`, `"01"`, … `"59"` (**zero-padded**). **Not universal** — some tools (e.g. house-systems-calculator) omit the seconds select entirely. Check for the element before setting it. |

Passing `"0"` for minute via jQuery silently leaves the select unchanged and the field never reaches the submitted URL. Zero-pad HMS values.

### City field id is `#city`, not `#narozeni_city`

The `name` is `narozeni_city`; the `id` is bare `#city`. Multi-subject forms use `#muz_city` / `#zena_city`.

### Browser-extension overlays break programmatic focus

If `type_text` after a `.focus()` doesn't cause the dropdown to open (`ul.ui-autocomplete` never appears, `tzid_id` stays empty), a password-manager extension (1Password, LastPass, Bitwarden) is overlaying the input and swallowing programmatic focus. **Coordinate-click the input first** — it lands a real focus event that the overlay can't intercept. Verify: `document.activeElement.id === 'city'` after the click.

### Year out of 1800–2099

The year `<select>` only covers 1800–2099. For out-of-range values, the form exposes a manual text input `narozeni_year_of_birth_input` (toggled by `narozeni_year_of_birth_select`). For form-driving, set the select to the relevant sentinel + write the text input. For URL-building, pass the year directly in `narozeni_rok` — the server accepts any numeric value.

### `press_key` doubles characters in text inputs

CDP's `Input.dispatchKeyEvent` fires both `keyDown` (with `text`) and a `char` event. For `<input>`/`<textarea>`, each inserts the character — `for ch in "London": press_key(ch)` produces `LLoonnddoonn`. Use `type_text("London")` (CDP `Input.insertText`); it inserts once and still fires `input` events the autocomplete listens to. Reserve `press_key` for Arrow keys, Enter, Escape, Tab.

### Submit

`js("document.forms[0].submit()")` bypasses any click handlers. There is no CSRF token; `send_calculation=1` is the only "was really submitted" marker and jQuery adds it automatically on submit.

**Don't assume `forms[0]` is the tool's primary form.** Most tools have one user-facing form, but a few — aspect-search-engine is the known case — wrap unrelated widgets (timezone picker, current-planets, planetary-ingresses) in additional `<form>`s that appear *before* the real search form. `document.forms[0]` on aspect-search is the timezone sub-form; the real search is `document.forms[1]`. When a new tool's submit produces the form page again instead of results, list `document.forms` and read each one's `.action` to find the right index.

### Form action often ends in `#tabs_redraw`

Browsers strip fragments from outgoing GET requests; form-driving won't trip on this. Only strip it manually if you're passing the action URL into a Python HTTP library.

## Fast path: `http_get` the results URL directly (bulk scraping)

When you need **the same tool repeated across many inputs** (e.g. 500 birth charts for calibration), skip the browser and build the URL yourself. You pay a documentation tax — every field name plus the lat/lon hidden fields — but you get parallel `http_get` + `ThreadPoolExecutor` with no browser in the loop.

```python
import urllib.parse, json

# 1. Resolve the city — two calls, second one returns tzid + lat/lon
sug = json.loads(http_get("https://horoscopes.astro-seek.com/api_gmaps3.php?term=" + urllib.parse.quote("London")))
place_id = sug[0]["id"]                         # API id, NOT the tzid
city = json.loads(http_get("https://horoscopes.astro-seek.com/api_gmaps3.php?place_id=" + place_id))
# city = {"mesto":"London","stat_kratky":"GB","podstat":"England","podstat_kratky":"",
#         "sirka_stupne":"51","sirka_minuty":"31","sirka_smer":"0",
#         "delka_stupne":"0","delka_minuty":"8","delka_smer":"1","tzid_id":"345"}

# 2. Build the results URL. MUST include the six sirka_/delka_ hidden fields —
#    omitting them silently computes the chart at lat 0°/lon 0° (equator).
params = {
  "send_calculation": "1", "input_natal": "1",
  "narozeni_den": "1", "narozeni_mesic": "1", "narozeni_rok": "1990",
  "narozeni_hodina": "12", "narozeni_minuta": "0", "narozeni_sekunda": "0",
  "narozeni_city": sug[0]["value"],             # "London, UK, England"
  "narozeni_mesto_hidden": city["mesto"],
  "narozeni_stat_hidden": city["stat_kratky"],
  "narozeni_podstat_hidden": city["podstat"],
  "narozeni_tzid_id": city["tzid_id"],
  # The six fields form-driving sets for you via the autocomplete select handler:
  "narozeni_sirka_stupne": str(city["sirka_stupne"]),
  "narozeni_sirka_minuty": str(city["sirka_minuty"]),
  "narozeni_sirka_smer": str(city["sirka_smer"]),
  "narozeni_delka_stupne": str(city["delka_stupne"]),
  "narozeni_delka_minuty": str(city["delka_minuty"]),
  "narozeni_delka_smer": str(city["delka_smer"]),
  "house_system": "placidus",
}
url = "https://horoscopes.astro-seek.com/calculate-birth-chart-horoscope-online/?" + urllib.parse.urlencode(params)
html = http_get(url)
```

The page is fully server-rendered — all planet positions, house cusps, aspect tables, copy-paste blocks, and chart `<img>` URLs appear in that response. No cookies, no CSRF, no rate-limit observed. Parse with the techniques in `scraping.md` and `chart-output.md`.

**Parity:** URL-built and form-driven paths produce byte-identical chart URLs (verified across `p_slunce`, `p_luna`, `p_merkur`, `p_mars`, `dum_1_new`, `dum_10_new`). Once you have the field list right, the two paths are interchangeable for one-shot fetches.

**500 on refetch trap:** long form-driven URLs (≥ ~700 chars with every hidden field) sometimes 500 when `http_get`'d back without a browser session. If you need to refetch, use your trimmed URL-built version, not the browser's `location.href`.
