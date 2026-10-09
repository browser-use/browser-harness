# flightseats.io

Reward seat availability for Australian frequent flyer programs (Qantas / Virgin Velocity). Useful for finding business/first class award space when a friend has points to gift/book.

## Coverage

| URL | Coverage |
|---|---|
| `/qantas/business-class-finder` | Qantas + all partners (Emirates, Cathay, JAL, BA, Qatar, Finnair, Iberia, Malaysia, Sri Lankan, etc.) |
| `/virgin-australia/business-class-finder` | **Virgin Australia-operated flights only** — essentially domestic. Not useful for long-haul SYD→Europe because Virgin Australia doesn't fly long-haul anymore. |
| `/qatar/business-class-finder` | 404 — does not exist |

For Velocity-points-to-Europe, this site **cannot help** — Velocity members book Qatar Airways as the main partner for Europe, and that inventory isn't surfaced here. Use seats.aero or point.me for Qatar.

## Date picker

- Library: **air-datepicker**
- Day cells: `.air-datepicker-cell.-day-`; passive: `.-other-month-`; disabled: `.-disabled-`; max date: `.-max-date-`
- Month cells: `.air-datepicker-cell.-month-` (textContent like `"Jul"`)
- Click month → calendar shows; click first day → range start; click second day → range end
- Range max = 30 days (label says "Max 30 days")
- **JS click() does NOT work on cells** — use compositor `click(x, y)` via getBoundingClientRect

## Cache limits (signed-out)

- Unregistered: search up to **60 days ahead**
- Free account: 120 days ahead
- Premium: 1 year ahead

If today + 60 days < target date, you have to sign up. Cells beyond the limit show `-disabled-`.

## Filters (post-search)

Buttons above the table: `SEATS`, `ORIGIN`, `DESTINATION`, `AIRLINE`, plus `STOP #`, `STOP`, time/duration, `POINTS`, `TAX`.

Each filter opens a popup with `INCLUDE`/`EXCLUDE` toggle and a `Search...` input. Region quick-selects at the bottom: `Australia (Major)`, `Europe (Major)`, `Europe (Schengen)`, `United Kingdom (UK)`, `London`, `Italy`, `Spain`, `Germany`, `Portugal`, `Scandinavia`, `Poland`, `South East Asia`, `Malaysia`, `Middle East (Hubs)`.

### Filter popup search input

`input[placeholder='Search...']` — there are multiple in the DOM but only one visible at a time (others have width=0). Use `getBoundingClientRect().width > 0` to find the active one.

To clear and re-type:

```python
js("""
(() => {
  const inp = [...document.querySelectorAll('input')].find(e => e.placeholder === 'Search...' && e.getBoundingClientRect().width > 0);
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  setter.call(inp, '');
  inp.dispatchEvent(new Event('input', {bubbles: true}));
})()
""")
```

Then `click(coords)` the input, `type_text("AMS")`, click the matching option.

**Cmd+A select-all does NOT work in this input** — the modifier doesn't propagate. Use the React setter clear pattern above.

### Filter option click

Options render multiple times in the DOM (mobile + desktop layouts). Filter for visible ones:

```python
opts = filter(lambda o: o.bbox.y > 0 and o.bbox.y < 900 and o.bbox.width > 0, options)
```

## SEARCH button

The visible "SEARCH" button is a `<div class="btn btn-primary ...">`, **not a `<button>` element**. Find it like:

```js
[...document.querySelectorAll('div')].find(e => 
  e.className?.includes('btn-primary') && e.textContent.includes('SEARCH') && !e.textContent.includes('SIGN'))
```

After a valid date range is selected, the button label changes to `SEARCH (~6s)` — that's the visual cue the form is submittable. Clicking before then fires no network request (client-side validation blocks).

## Table

Headers: `Date`, `Number & Airline`, `Route`, `Duration`, `Business` (or `Cabin` with first-class enabled).

Cells are concatenated with no separators in `textContent`. Useful regex extraction:

```python
# Route: "SYD-FRA(DXB)25h 5m" → ('SYD', 'FRA')
re.match(r'([A-Z]{3})-([A-Z]{3})', row[2])

# Airline: "A380EK417, A380EK45Emirates"
# Points/tax: "182,9001,723 AUD2 seats availableClick for details"
#   → 182,900 points + AU$1,723 tax + 2 seats
```

The points value is the whole number before the comma+three-digit tax. There's no separator between the two numbers in the rendered text.

## Pagination

`Rows: 10/30/50` select bumps page size (max 50). Below the table there are page numbers + `Prev`/`Next`. There's **no visible total count** — paginate to discover.

## "Live refresh"

Each row has a refresh icon (left-most cell) that queries the supplier directly instead of using cached data. Useful when a row shows good availability but you want to confirm it's still bookable. Costs network round-trip.

## Velocity vs Qantas — which to pick

If the friend has:
- **Qantas points** → use `/qantas/business-class-finder`. Covers Emirates (the big Australia-Europe carrier), Cathay (HKG hub), JAL (HND hub), BA (LHR hub), Qatar (DOH hub), Finnair (HEL hub).
- **Velocity (Virgin) points** → this site does NOT help for international. The Virgin Australia finder is essentially domestic-only. Direct the user to:
  - **seats.aero** (paid, ~$10/mo) for Qatar Airways award availability (Velocity's main Europe partner)
  - **point.me** for multi-program search
  - Virgin Velocity website directly: search Qatar Airways award seats SYD/PER → DOH → European hub

## Known SYD/PER → Europe partner routes (Qantas points)

For reference, what's typically searchable through partners (availability varies):

| Airline | Routing |
|---|---|
| Emirates | SYD/PER → DXB → AMS/CDG/FRA/LHR/BRU/MAD/ZRH/MUC etc. |
| Qatar | SYD/PER → DOH → OSL/CPH/AMS/LHR/FRA/BRU etc. |
| Cathay Pacific | SYD/PER → HKG → LHR/CDG/FRA/AMS/MAD/MXP/ZRH |
| British Airways | SYD → SIN → LHR (codeshare with Qantas) |
| JAL | SYD → HND → LHR/CDG/FRA/HEL |
| Finnair | SYD → HEL (via Singapore, seasonal) |

The Qantas finder surfaces those it knows about, subject to actual award seat release by the operating carrier.
