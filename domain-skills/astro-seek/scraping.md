# Astro-Seek — Scraping Result Pages

Result pages are **fully server-rendered HTML**. `http_get(results_url)` returns ~800KB containing every table, copy-paste block, and chart `<img>` you need. No browser, no JS execution, no auth.

The forms-side workflow lives in `forms.md`; this file is what to do once you have the response HTML.

## What the page contains (in DOM order)

The table below describes a **birth-chart** results page. Other tools differ:

- **Transit chart** (`/calculate-transit-chart/`) does NOT expose a `Planet | Sign | Degree | House | Motion` header — its layout is annual-transits-first and tables are grouped differently. Test `hdr_ok` tool-by-tool before relying on the pattern.
- **Search/calendar tools** (ephemeris, transit-calendar) emit dated rows only — no chart `<img>`, no planet positions table in the shape below. Scrape `<tr>` rows directly.

| # | Block | Selector hint |
|---|---|---|
| 1 | Birth-data summary | `<h1>` text "1 January 1990 - 12:00 (GMT)…" |
| 2 | Chart wheel `<img>` (multiple styles) | `img[src*="horoscope-chart"]` — see `chart-output.md` |
| 3 | Planet positions table | first `<table>` whose first row is `Planet | Sign | Degree | House | Motion` |
| 4 | House cusps table — left half (cusps 1–6) | second `<table>`, rows like `1: | Aries (ASC) | 11°49'53"` |
| 5 | House cusps table — right half (cusps 7–12) | third `<table>`, mirror of #4 starting at `7: | Libra (DESC)` |
| 6 | Major aspects table (Sun–Pluto) | `<table>` with header `Planet | Aspect | Planet | Orb | A/S` |
| 7 | Other aspects table (involving ASC/MC/Node/Lilith/Chiron/Fortune/Vertex) | `<table>` with header `Object | Aspect | Planet | Orb | Aspect` |
| 8 | Parallels table | `<table>` with header `Object | Aspect | Planet | Orb` (no A/S column) |
| 9 | Copy-paste blocks (5 of them — planet positions, house positions, planet aspects, other aspects, parallels) | `<textarea>` or `<div onclick="selectText('positions_chart_gpt')">` |
| 10 | Minor aspects / harmonics table | `<table>` with header `(1*/n of 360°)` |
| 11 | Sun-to-planet arcs table | header `Sun-Planet | ArcPhase Degree | ArcReturns` |
| 12 | Sensitive degrees table | header starts `Deg°` |
| 13 | Tab 5 — full coordinate table | header `Planet | Long | Lat | RA | Decl | Az | Alt | Speed` |
| 14 | Tab 6 — dominant planets | header `Planet | Sign(?) | House(?) | Angle(?) | Ruler(excl.) | Aspects(excl.) | SUMPoints | Dominant%` |

**Tables have no `id` and no class.** Locate them by header content, not by ordinal — astro-seek occasionally inserts ad/info rows between tables and the order shifts between tools.

```python
# Robust pattern: parse all tables, find the one whose first row matches the header you want
import re
def find_table(html, header_re):
    for m in re.finditer(r'<table[^>]*>(.*?)</table>', html, re.S):
        head = re.search(r'<tr[^>]*>(.*?)</tr>', m.group(1), re.S)
        if head and re.search(header_re, head.group(1), re.I):
            return m.group(1)
    return None

planets = find_table(html, r'Planet.{0,40}Sign.{0,40}Degree.{0,40}House')
```

For anything beyond simple regex, parse with `bs4` or `lxml` — both work fine on the response.

## Two ways to read planet positions — pick by need

**Reading numerical positions for verification?** Parse the chart-image URL query string. It carries decimal-degree floats with no entity encoding. See `chart-output.md` for the full param list.

**Reading display-formatted positions (sign + degree + retrograde label)?** Scrape the planet-positions table or the copy-paste text block. The text block (`Sun in Capricorn 10°48', in 10th House`) is a single regex away.

## Degree separators are Unicode, not ASCII

Astro-seek uses fancy quotes for arcminutes and arcseconds:

| Glyph | Codepoint | HTML entity | Meaning |
|---|---|---|---|
| `°` | U+00B0 | `&deg;` | degrees |
| `'` | U+2019 | `&rsquo;` | arcminutes |
| `''` (two) | U+2019 U+2019 | `&rsquo;&rsquo;` | arcseconds |

**Not** `'` (U+0027) or `"` (U+0022). Match with `°` and `\u2019` (`'`), or strip entities first if you've decoded.

```python
import html as h
text = h.unescape(raw)              # &deg; -> °, &rsquo; -> ’
m = re.match(r"(\d+)°(\d+)\u2019(\d+)\u2019\u2019", text)   # deg, min, sec
```

## Ephemeris / search / calendar row format

Search tools emit no chart `<img>` and no planet-positions table. The row format **differs between search tools** — there is no universal regex. Known layouts:

### Ephemeris search (`/calculate-ephemeris-search-engine/`)

```
July 23, 2026 , 12:00 [noon] UT/GMT    Sun: 0°40' Leo
July 24, 2026 , 12:00 [noon] UT/GMT    Sun: 1°37' Leo
```

English month names, month-first (`Month DD, YYYY`), `HH:MM [noon] UT/GMT` timestamp, planet-colon-sign-degree payload with Unicode `°` and `\u2019` glyphs.

```python
ROW_RE = re.compile(
    r'(January|February|March|April|May|June|July|August|September|October|November|December)'
    r'\s+(\d{1,2}),\s*(\d{4})\s*,\s*(\d{1,2}:\d{2})[^<]*?'      # date + time
    r'([A-Z][a-z]+):\s*(\d+)°(\d+)\u2019\s*([A-Z][a-z]+)',       # planet: deg°min' Sign
    re.S,
)
for tr in re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S):
    txt = re.sub(r'<[^>]+>', ' ', tr)  # strip tags; keep entities and glyphs
    txt = html_.unescape(txt)
    for month, day, year, hm, planet, deg, minute, sign in ROW_RE.findall(txt):
        ...
```

Pass `aya=lahiri` (or other sidereal values) to switch zodiacs; the row format is unchanged, only the sign labels shift.

### Aspect-search engine (`/calculate-astrology-aspects-online-search-engine/`)

Completely different shape. Year-first, **3-letter abbreviated months**, time in parentheses, two degree values side by side (one per planet), no Unicode apostrophe between degrees and minutes, optional `(Rx)` for retrograde:

```
2026, Sep 01 (09:58)   13°39   13°39  (Rx) chart
2028, Sep 21 (11:58)   10°33   10°33  (Rx) chart
```

The planets themselves aren't in the row — they're in the query (`kalendar_planeta_1`, `kalendar_planeta_2`), so you already know which pair the degrees belong to. Use `&nbsp;`-tolerant cleanup and a distinct regex:

```python
import html as h, re
def parse_aspect_rows(html_src):
    for m in re.finditer(r'<tr[^>]*>(.*?)</tr>', html_src, re.S):
        txt = re.sub(r'<[^>]+>', ' ', m.group(1))
        txt = h.unescape(txt)                         # &nbsp; -> \xa0, &deg; -> °
        txt = re.sub(r'\s+', ' ', txt).strip()
        row = re.match(
            r'(\d{4}),\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})'
            r'\s*\((\d{1,2}:\d{2})\)\s*(\d+)°(\d+)\s+(\d+)°(\d+)\s*(\(Rx\))?',
            txt,
        )
        if row:
            yield row.groups()  # year, mon, day, hm, d1deg, d1min, d2deg, d2min, rx
```

Verified tools: ephemeris uses the first format; `/calculate-astrology-aspects-online-search-engine/` uses the second. Probe a new search tool's row shape before reusing either regex.

## Cookies and rate limits

`PHPSESSID` is set on first visit but **not required** for results URLs or for the city API. No rate limiting observed during this session — bulk-fetch with `ThreadPoolExecutor` is fine, but be polite.

## When you do need a browser

- **Tab 3 (Horoscope Shape).** It's a `<div>` placeholder that loads a highslide image gallery only on click. If you need the rendered shape PNG, drive a browser, click the tab, wait, then download the image.
- **Customize-tab download buttons.** Tab 2 lets the user generate `chart4zone3` variants with custom backgrounds. The relevant query params are visible in the DOM but the toggles are JS-driven; building the URL by hand is faster than clicking through.
- **Anything that opens highslide modals** — the modal contents only mount on click.

For everything else, `http_get` is fastest.
