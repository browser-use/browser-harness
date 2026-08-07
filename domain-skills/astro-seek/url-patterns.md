# Astro-Seek — URL Patterns

`https://astro-seek.com` — the astrology-tools site Astrolabi re-implements. Tools live across a few subdomains, all forms submit by **GET**, so a fully-formed URL is a permalink.

This file is the reference for URL *construction* (the fast path for bulk scraping). The default path is form-driving — open the tool page, set selects, type the city, submit — because the form's autocomplete handles several hidden fields for you. See `forms.md` for the form-driving recipe.

## Subdomain map

| Subdomain | What lives here |
|---|---|
| `www.astro-seek.com` | Marketing/blog/zodiac articles. Mixed Czech/English. |
| `horoscopes.astro-seek.com` | All compute tools (birth chart, transit, synastry, ephemeris, asteroids, returns, …). English-only. |
| `mooncalendar.astro-seek.com` | Lunar calendar. |
| `numerology.astro-seek.com` | Numerology tools. |
| `famouspeople.astro-seek.com` | Celebrity natal-chart database. |
| `es.astro-seek.com` / `pt.` / `de.` / `fr.` / `ru.` / `it.` / `tr.` / `ko.` | Localized marketing — different content, not a translation of `horoscopes.*`. |

The `?lang=en` query param has no effect on `horoscopes.astro-seek.com` (it's English already) and does not switch language on the marketing subdomain either — language is host-based.

## Form URL → Results URL

Every tool has a paired form-page URL and results URL. Both are GET. The form's `action` attribute gives the results URL.

| Tool | Form URL | Results URL |
|---|---|---|
| Birth chart | `/birth-chart-horoscope-online` | `/calculate-birth-chart-horoscope-online/` |
| Transit chart | `/transit-chart-planetary-transits` | `/calculate-transit-chart/` (`#tabs_redraw`) — see note below |
| Synastry | `/synastry-chart-online-calculator` | `/calculate-love-compatibility/` (`#tabs_redraw`) |
| Composite | `/composite-chart-horoscope` | `/calculate-composite-chart-horoscope/` (`#tabs_redraw`) |
| Progressions (secondary) | `/astrology-secondary-progressions-directions-chart` | `/calculate-secondary-directions-progressions/` (`#tabs_redraw`) |
| Asteroids | `/asteroids-astrology-online-calculator` | `/calculate-asteroids/` |
| Sidereal | `/sidereal-astrology-chart-calculator` | `/calculate-sidereal-chart/` |
| House-systems comparison | `/astrology-house-systems-calculator` (moved 2026-08; old `/house-systems-...-comparison` 404s) | `/calculate-house-systems/` |
| Ephemeris search | `/ephemeris-search-engine-astrology-planet-positions` | `/calculate-ephemeris-search-engine/` |
| Aspect search | `/astrology-aspects-online-search-engine` | `/calculate-astrology-aspects-online-search-engine/` (`#select_local_tz_anchor`) |
| Traditional | `/traditional-astrology` | same pattern |

Discover the results URL on a new tool by reading `document.forms[0].action`. The action sometimes ends with `#tabs_redraw` — that's a scroll anchor, not a query. **A tool may have multiple forms** — aspect-search has four (`forms[0]` is a timezone sub-form, `forms[1]` is the real search); always read the action of the specific form you plan to submit.

**Transit-chart result page has a surprising primary.** `/calculate-transit-chart/?…` headlines an **annual-transits-in-natal** graph (`horoscope-chart8annual-700__annual_transits_in_natal_chart_…`) plus a natal radix — the **transit bi-wheel** you probably want is rendered further down the page under a different base path (`horoscope-synastry-chart{N}-700__transits_…`). Don't assume the first 700×700 image is what you asked for.

## Query-param prefixes per subject

The compute backend uses Czech field names. Single-person tools use bare names; relationship and transit tools use prefixed names.

| Prefix | Subject | Used by |
|---|---|---|
| (none) | The single chart | Birth chart, asteroids, sidereal, traditional, draconic, kundli, …everything single-subject |
| `muz_` | Person A / natal | Synastry, composite, transit (natal side), progressed synastry, secondary progressions (natal side) |
| `zena_` | Person B / transit date / progression date | Synastry, composite, transit (transit side), progressions. On secondary progressions the zena side has no `#zena_city` — the progression date reuses the natal location. |
| `tranzity_` | Transit date on composite-chart | Composite only — the composite page also renders a composite-vs-transits bi-wheel and `#tranzity_city` is the third autocomplete input |
| `ingres_` | Date for the "current planets" widget at the bottom of every form page | Universal |

`muz` / `zena` are Czech for "man" / "woman". Treat them as opaque keys — the position is by prefix, not gender.

## Universal birth-data fields

For each subject prefix `P` (where `P=""`, `"muz_"`, or `"zena_"`):

```
P + narozeni_den         day, 1-31           (option values unpadded "1".."31")
P + narozeni_mesic       month, 1-12         (option values unpadded "1".."12")
P + narozeni_rok         year, 1800-2099     (out-of-range uses P + year_of_birth_input)
P + narozeni_hodina      hour, 0-23          (option values zero-padded "00".."23")
P + narozeni_minuta      minute, 0-59        (option values zero-padded "00".."59")
P + narozeni_sekunda     second, 0-59        (option values zero-padded "00".."59")
P + narozeni_city        display string, e.g. "London, UK, England"
```

For URL-building the server accepts either padded or unpadded numbers; for form-driving, match the option value exactly or jQuery's `.val()` silently no-ops.

Plus the city-derived hidden fields. **The autocomplete populates all of these automatically when you drive the form** — on the URL fast path, you must supply them all yourself, especially `sirka_*`/`delka_*`. Omitting `sirka_*`/`delka_*` silently computes at lat 0°/lon 0°.

```
P + narozeni_mesto_hidden          city, e.g. "London"
P + narozeni_stat_hidden           ISO country, e.g. "GB"
P + narozeni_podstat_hidden        sub-region, e.g. "England"
P + narozeni_podstat_kratky_hidden short region code, e.g. "NY"
P + narozeni_tzid_id               internal timezone id, e.g. "345"
P + narozeni_sirka_stupne          latitude degrees (REQUIRED for correct cusps)
P + narozeni_sirka_minuty          latitude minutes
P + narozeni_sirka_smer            lat direction: "0"=N, "1"=S
P + narozeni_delka_stupne          longitude degrees (REQUIRED)
P + narozeni_delka_minuty          longitude minutes
P + narozeni_delka_smer            lon direction: "0"=E, "1"=W
P + narozeni_input_hidden          full input string (rarely needed)
```

A submit also needs `send_calculation=1`. Single-subject tools also pass `input_natal=1`.

The results URL itself is the permalink. The page links to its own URL with `&edit_input_data=1` appended for the "Edit birth data" button, so to mutate inputs without losing the chart, append that flag.

## Chart-image URL pattern

Chart bitmaps live on two base paths — see `chart-output.md` for the full anatomy. Quick form:

```
Single wheel (radix, composite):
  horoscope-chart{STYLE}-{SIZE}__{TYPE}_{date}.{png|gif}?{payload}

Bi-wheel (transits, progressions; synastry is a special case, see below):
  horoscope-synastry-chart{N}-{SIZE}__{TYPE}_{d1}_a_{d2}.png?{payload}
```

- Single-wheel `STYLE` tokens seen in the wild: `4def` (default), `4zone3` (watermark), `3` (classic), `1` (sidereal default), `1snew` (asteroids default), `8snew` (asteroids alternate), `4` (sidereal/composite alternate). The STYLE is **tool-dependent** — `4def` is birth chart + composite default, but sidereal emits only `chart1-700` / `chart4-700` and asteroids emits only `chart1snew-700` / `chart8snew-700`. Always inspect the actual DOM rather than assuming `chart4def`.
- Bi-wheel `{N}` is numeric. Seen: `5`, `20`, `23`, `24`, `27`. Defaults also vary by tool — `chart20` is the transit + progressions default, but **synastry's primary is `chart23`**.
- `{TYPE}` for bi-wheels is **English**: `transits`, `synastry`, `progressions` (plural), `secondary-progressions` (hyphenated!), `composite_transits` (composite's bi-wheel overlay). Czech field names (`tranzit`, `synastrie`) do not appear in URLs.
- **Synastry's chart filename omits `{TYPE}` entirely** and uses `_p_` as the date separator: `horoscope-synastry-chart23-700__{d1}_p_{d2}.png`. Don't assume every bi-wheel has an `{TYPE}_` prefix.
- Date: `D-M-YYYY_HH-MM`. Bi-wheel date form: `D-M-YYYY_HH-M_a_D-M-YYYY_HH-M` (minutes occasionally lose their leading zero — don't key off exact format). Progressed-chart20 omits the time on the second date (`_a_19-4-2026`) while chart24 keeps it (`_a_19-4-2026_12-00`) — the two styles on the same page disagree.
- File extension is `.png` everywhere, but the actual bytes are GIF for birth-chart radix and PNG for nearly everything else — see `chart-output.md`.
- Downloads require `User-Agent: Mozilla/5.0` (plain urllib → HTTP 403). `http_get` already sets it.
- Some tools append `nocache=21` to the chart URL (verified on sidereal `chart1-700`). Treat it as a server-side cache-buster — its presence means "this chart is re-rendered per query".

## Chart-less tools

Search / calendar tools (ephemeris, transit-calendar, aspect-search) emit **no chart `<img>`** on their results page. The payload is entirely in HTML rows. Don't try `naturalWidth === 700` filters on these — you will get zero hits.

## Lazy-loaded variants

Several chart styles co-exist on a single results page (modern, zone, classic). `naturalWidth === 700` is not uniquely the primary — `chart4def-700` AND `chart4zone3-700` both render at 700×700 when scrolled into view. Filter by the style token AND size:

```js
Array.from(document.querySelectorAll('img'))
  .filter(i => /horoscope-chart4def-700__radix_/.test(i.src)
            && !/minor_aspects|astroseek/.test(i.src)
            && i.naturalWidth === 700)
```

Also: `<img loading="lazy">` reports `naturalWidth === 0` until scrolled into view. When running against `http_get` HTML (no layout), drop the `naturalWidth` check and trust the URL pattern.
