# Astro-Seek — Gotchas

Field-tested traps. The site is stable and quirk-light, but these will burn time if you don't know.

## Czech field names everywhere

The compute backend was originally Czech. **Most form field names are Czech**, with no English aliases. You can't rename them — the server reads exactly:

- `narozeni_den/mesic/rok/hodina/minuta/sekunda` (birth day/month/year/hour/minute/second)
- `narozeni_city/mesto/stat/podstat` (city/town/state/region)
- `narozeni_sirka/delka` (latitude/longitude)
- `dum_1` … `dum_12` (house cusps)
- `p_slunce/luna/merkur/venuse/…` (planet positions)
- `r_<planet>=ANO` (retrograde — `ANO` is Czech "yes"; absence == direct)
- `muz_` / `zena_` prefixes (man/woman) on relationship/transit forms — opaque keys, not gender markers

Glossary lives in `chart-output.md`. Keep it open while scraping.

## `?lang=en` does almost nothing

The `horoscopes.astro-seek.com` subdomain is English-only; the param is a no-op there. The marketing-side translations live on host-prefixed subdomains (`pt.`, `de.`, etc.) with separate content, not parameter switches. Don't waste time toggling `?lang=`.

## Forms are GET — but prefer driving them anyway

A results URL is a complete permalink, so URL construction *is* possible. But the form's jQuery autocomplete silently writes six lat/lon hidden fields (`narozeni_sirka_stupne/_minuty/_smer` + `narozeni_delka_*`) that the default path has to remember to include. Miss them and the server computes at **lat 0°, lon 0°** — all quadrant house systems collapse to equal-house at the equator, which masks bugs without raising an error. Default path: drive the form. Fast path (bulk scraping): build the URL, and include the six sirka/delka fields. See `forms.md`.

## City autocomplete needs two API calls

The dropdown's API returns suggestions with an `id`, but that `id` is the place id, **not** the timezone id. You must make a second call: `GET /api_gmaps3.php?place_id=<id>` to get `tzid_id`, lat/lon, and country. When you drive the form, the jQuery select handler makes both calls and populates every hidden field; you only touch the API directly on the URL-building fast path. See `forms.md`.

## Hour/minute/second `<select>` option values are zero-padded; day/month are not

`jQuery('[name=narozeni_minuta]').val('0').change()` silently fails because the option value is `"00"`. Same for `narozeni_hodina` and `narozeni_sekunda`. `narozeni_den` and `narozeni_mesic` are `"1".."12"` / `"1".."31"` (unpadded). For URL-building the server accepts either form; for form-driving you must match the option value exactly or the field is omitted from the submitted URL.

## Chart bitmap caching is tool-dependent

The **birth-chart radix** (`chart4def-700__radix_*.gif`) is cached by filename — all three house-system variants (placidus / koch / whole_horizon) return byte-identical bytes. The filename only encodes date + time (`radix_1-1-1990_12-00`), so the server serves the same cached bitmap regardless of cusp or tropical/sidereal settings. For regression-testing the birth-chart tool, diff the URL query string (`dum_*`, `p_*`, `r_*`), not the image bytes.

**Every other tool tested re-renders per query.** Verified as of 2026-04-19:

| Tool | Primary chart | Cache behaviour |
|---|---|---|
| Birth chart | `chart4def-700__radix_` | filename-only cache (md5 identical across house-system variants) |
| Asteroids | `chart1snew-700__radix_` | cusps re-render bitmap; planet-sort-order does NOT |
| Sidereal | `chart1-700__radix_` | ayanamsa re-renders bitmap (server emits `nocache=21` in the URL) |
| Synastry | `synastry-chart23-700__…_p_…` | cusps + `hide_aspects` re-render |
| Composite | `chart4def-700__composite_` | cusps re-render (`metoda_vypoctu` did NOT change bytes in one test) |
| Progressions | `synastry-chart20-700__progressions_` | cusps + `hide_aspects` re-render |

Safer rule: always diff the query string for semantic changes, and md5 the bytes only when you specifically want to test that the bitmap reflects them. Don't rely on the cached-filename shortcut outside the birth chart.

## Form-driven submit URLs can exceed server-handleable length

After `document.forms[0].submit()`, `location.href` is a ~750-char URL echoing every form field including empty hidden ones. Re-fetching that URL through `http_get` can return **HTTP 500** while a shorter URL-built variant with the same semantic inputs returns 200. If you need the results page twice, cache the browser's rendered HTML or rebuild with the trimmed field set.

## `press_key` doubles characters in text inputs

Harness footgun: the harness's `press_key("a")` sends both a `keyDown` (with `text`) and a `char` event via CDP. Listening sites get the character once, but `<input>` and `<textarea>` insert it twice. Result: typing "London" via `for ch in "London": press_key(ch)` produces `LLoonnddoonn`.

**Fix:** use `type_text("London")` (CDP `Input.insertText`) for free-form text. It inserts once and still fires the `input` event jQuery autocomplete listens to. Reserve `press_key` for special keys (Arrow*, Enter, Escape, Tab).

## Degree glyphs are Unicode `'` (U+2019), not ASCII `'`

Tables and copy-paste blocks render arcminutes as U+2019 RIGHT SINGLE QUOTATION MARK and arcseconds as two of them. HTML entity is `&rsquo;`. ASCII apostrophe regexes will silently miss every value. See `scraping.md`.

## Tables have no id and no class

`<table>`s in the result page are bare. Locate by header content (e.g. "Planet | Sign | Degree | House | Motion"), not ordinal — astro-seek inserts ad/info rows that shift table indices.

## Tab 3 is the only lazy-loaded tab

Tabs 1, 2, 4, 5, 6 are all in the initial HTML. Tab 3 (Horoscope Shape Characteristics) is a `<div>` placeholder that loads a highslide image gallery on click. Skip it for `http_get`; only drive a browser if you specifically need the shape PNG.

## Multiple chart `<img>` tags coexist

Every results page has 3–8 `<img>` tags pointing at different style/size variants of the chart. `naturalWidth === 700` on its own is **not unique** — several chart styles load at 700×700 when scrolled into view. Filter by the style token AND the size (and exclude `minor_aspects` / `astroseek` infixes). The correct style token is **tool-specific**:

| Tool | Primary style token to match |
|---|---|
| Birth chart | `chart4def-700__radix_` |
| Asteroids | `chart1snew-700__radix_` (NOT `chart4def-700`) |
| Sidereal | `chart1-700__radix_` (NOT `chart4def-700`) |
| Composite | `chart4def-700__composite_` (single wheel) |
| Synastry | `synastry-chart23-700__` (with `_p_` separator; NO TYPE token) |
| Transit | `synastry-chart20-700__transits_` |
| Progressions | `synastry-chart20-700__progressions_` |

Example for the birth chart:

```js
img.src.match(/horoscope-chart4def-700__radix_/) &&
  !img.src.match(/minor_aspects|astroseek/) &&
  img.naturalWidth === 700
```

The `4def` style is the default modern look; `4zone3` is the watermark variant; `3` is the classic style. Bi-wheel tools (transit, synastry, progressions) use the `horoscope-synastry-chart…` base path — see `chart-output.md` for the full style-and-TYPE inventory.

## `src=` attributes contain literal newlines

Astro-seek breaks long chart URLs across multiple lines inside `<img src="…">`. A naive `[^"\s]+` regex truncates the URL at the first newline. Use `[^"]+` and then `re.sub(r'\s+', '', url)` to strip the whitespace.

## `.png` extension lies — birth-chart radix is GIF

Birth-chart radix files (`horoscope-chart4def-700__radix_*.png`) are actually GIF87a (signature `47 49 46 38`). Every other tool tested (transit, synastry, composite, progressions, asteroids, sidereal) returns real PNG (`89 50 4e 47`) despite the same `.png` extension. Don't hardcode a PNG signature check — only the birth chart is the GIF-in-PNG-clothing case. See `chart-output.md`.

## Chart download needs a User-Agent

Plain `urllib.request.urlopen(chart_url)` returns **HTTP 403**. Set `User-Agent: Mozilla/5.0` on the request. `http_get` already does this; external curl/wget does it by default; bare urllib does not. Cookies, referer, and auth are still not required.

## Transit-chart results have a surprising primary image

The `/calculate-transit-chart/?…` page headlines an **annual-transits-in-natal** graph (`horoscope-chart8annual-700__annual_transits_in_natal_chart_…`) plus a natal radix. The actual **transit bi-wheel** is rendered further down the page under the `horoscope-synastry-chart{N}-700__transits_…` path. Don't assume the first 700×700 image is what you asked for.

## Search / calendar tools have no chart image

Ephemeris search, transit-calendar, and similar tools emit zero `horoscope-chart*` tags on the results page. The payload is table rows. Don't waste time hunting for chart URLs on these — scrape `<tr>` directly.

## Transit-chart result tables skip the birth-chart header

`Planet | Sign | Degree | House | Motion` is a **birth-chart-only** header. Transit results lay out the data differently (grouped by natal/transit side). Test your header regex per tool before assuming the pattern in `scraping.md` is universal.

## Single-subject city input id is `#city`, not `#narozeni_city`

The `name` attribute is `narozeni_city`, but the `id` is bare `#city`. `forms.md` has the full id mapping across tool shapes. Multi-subject forms use `#muz_city` / `#zena_city`. Composite adds a third `#tranzity_city` for the transit overlay. Secondary progressions has only `#muz_city` — the progression date reuses the natal location and exposes no `#zena_city`.

## Browser-extension overlays break programmatic focus

If `type_text` after `.focus()` doesn't trigger the city autocomplete (dropdown never appears, `tzid_id` stays empty), the likely culprit is a password-manager extension (1Password, LastPass, Bitwarden) overlaying the text input and swallowing programmatic focus. **Coordinate-click the input first** to land a real focus event, then `type_text`. See `forms.md` "Browser-extension overlays".

## Filename date format is Czech-locale

Chart PNG filenames embed the date as `D-M-YYYY_HH-MM` — no leading zeros on D and M (Czech locale), leading zeros on H and MM. `1-1-1990_12-00.png` not `01-01-1990_12-00.png`.

## Year out of 1800–2099

The year `<select>` only covers 1800–2099. Out-of-range values switch to a manual text input (`narozeni_year_of_birth_input`). For URL submission, just pass any year directly in `narozeni_rok` — the server accepts it without the select-vs-input dance.

## No cookie banner, no captcha, no auth wall

Confirmed clean session. A `PHPSESSID` cookie is set on first visit but isn't required for any read or compute call. No rate limiting observed.

## `#tabs_redraw` fragment in form action

Form `action` URLs sometimes end with `#tabs_redraw` (a JS scroll anchor). Browsers strip fragments from outgoing GET requests; some HTTP libs don't. Strip it before passing to `http_get` to avoid an unnecessary 30x or oddity.

## Tools at unexpected URLs

The "obvious" URL isn't always real — `synastry-chart-online-calculator` works, but `free-synastry-chart-online-calculator-relationship-astrology` 404s. When unsure, find the link from `https://horoscopes.astro-seek.com/` or `https://www.astro-seek.com/` instead of guessing.

Confirmed-wrong guesses to avoid (all 404):

- `/aspect-search-calculator` → real URL is `/astrology-aspects-online-search-engine`
- `/progressed-chart-astrology-online` → real URL is `/astrology-secondary-progressions-directions-chart`
- `/transit-calendar` → real URL is `/personal-transit-calendar-monthly-astrology-transits` (there is no bare `/transit-calendar`)

## `document.forms[0]` is not always the tool's real form

Most tools expose a single user-facing form so `forms[0]` is right. Aspect-search-engine is the known exception: the page has 4 forms (timezone picker + search + current-planets + ingresses). `forms[0]` is the timezone sub-form and submitting it keeps you on the intro page. The real search is **`document.forms[1]`**. When a new tool's submit returns the form page again instead of results, enumerate `document.forms` and check `.action` on each.

## Progressed-chart filename has two inconsistent date formats on one page

The secondary-progressions results page renders both `synastry-chart20-700__progressions_` and `synastry-chart24-700__secondary-progressions_` bi-wheels. The chart20 filename drops the time on the second date (`…_a_19-4-2026.png`) while the chart24 filename keeps it (`…_a_19-4-2026_12-00.png`). Parse the date block by splitting on `_a_` (or `_p_` for synastry) rather than regexing for a fixed `D-M-YYYY_HH-MM` shape on both sides.

## Astro-seek's `r_<planet>=ANO` retrograde flags ARE ephemerally correct (2026-08 correction)

**Correction (2026-08-06):** this file previously claimed `r_venuse=ANO` for 1990-01-01 noon London was wrong ("Venus was direct"). That claim was itself the error — Venus was retrograde Dec 29 1989 – Feb 8 1990; astro-seek's flag, Swiss Ephemeris speed sign, and the page's own coordinate-table speeds all agree. Benchmarks against the `r_<planet>` payload flags have since matched Swiss Ephemeris across natal, transit, progressed, and return charts with zero discrepancies. Trust the flags.

## Sidereal tool defaults to `whole`-sign houses, not placidus

The `<select name=house_system>` on `/sidereal-astrology-chart-calculator` defaults to `whole` (the Vedic convention), not `placidus` like the other tools. If you don't explicitly set `house_system` the submitted URL will carry `house_system=whole`. Don't assume placidus is universal.

## Aspect-search uses Czech aspect keys + abbreviated months

`kalendar_aspekt` takes Czech values (`konjunkce`, `sextil`, `kvadratura`, `trigon`, `opozice`, `minor`, `hard`, `konjunkce_opozice`), and the result-row format uses **3-letter English month abbreviations** (`Jan`, `Feb`, `Sep`) with a completely different shape from the ephemeris search tool. Don't reuse the ephemeris row regex. See `scraping.md`.

## 2026-08 updates (benchmark campaign, 14 cloud sessions)

- **Cloudflare now challenges plain HTTP.** Every non-browser request (curl,
  `http_get`) to `horoscopes.astro-seek.com` gets `403 cf-mitigated: challenge`
  ("Just a moment…"). The April-era bulk-HTTP fast path is dead. Browser Use
  cloud browsers (stealth + residential proxy) were never challenged across 14
  sessions. In-page bulk capture still works: submit the form, then dump
  `document.documentElement.outerHTML` and parse offline.
- **Ephemeris-search row format changed.** Visible rows are now just
  `YYYY, Mon DD (display chart)`; the full 13-body noon-UT ephemeris (with R/st
  flags) moved into each row's `onmouseover` tooltip. The row regex documented
  in scraping.md no longer matches the visible text — parse the tooltip HTML.
  Results are day-granular noon-UT snapshots (an ingress after noon lands on
  the following day's row).
- **House-systems form URL moved.** `/house-systems-astrology-calculator-comparison`
  now 404s; live page is `/astrology-house-systems-calculator` (19 systems,
  no seconds select).
- **There is no tools index page.** `/astrology-tools-online` 404s — discover
  tools from the homepage `#calculations` section and footer nav.
- **Timezone handling is correct and tz-aware.** Transit/mansion/return pages
  apply historical DST (e.g. 2026-04-19 12:00 London = 11:00 UT, banner says
  BST). Payload decimals are TRUNCATED, not rounded — compare with one-sided
  tolerance 10^(−decimals).
- **Best-precision sources per page family:** birth chart tab-5 coordinate
  table (arcseconds); progressions payload `luna_denni_00/_24` (11 decimals);
  sidereal payload `aya_posun` (12-decimal ayanamsa); retrograde calendar
  "shadow" links (station longitudes to arcseconds); ZR results' plain-text
  export tabs (cleanest structured export on the whole site).
- **Aspect-search extras:** `kalendar_aspekt` also accepts `trioktil` (135°)
  and `kvinkunx` (150°) beyond the documented keys. Sign/aspect in result rows
  live ONLY in `img alt` attributes; degrees use plain ASCII (no U+2019) unlike
  chart pages.
- **Cloud-browser death mode:** a Browser Use browser can die mid-session
  (daemon websocket keepalive timeout; v4 API still says "active" but `cdpUrl`
  is null and `/json/version` 503s). Stop it via PATCH and provision a fresh
  browser — no in-place recovery.
