# Expedia — Browser Automation

Field-tested against expedia.co.in on 2026-04-27 using `browser-harness` CDP
helpers (`goto`, `js`, `click`, `type_text`, `screenshot`).

---

## TL;DR

**Build your search via URL parameters, not the UI.** The date picker, destination
autocomplete, and traveller widgets are fragile—coordinate clicks frequently
dismiss them or mis-target. Encode everything you can into a `goto()` URL, then
use JS clicks only for what the URL can't express (child ages, price filters).

---

## Hotel Search URL Template

```
https://www.expedia.co.in/Hotel-Search?destination={DEST}&startDate={YYYY-MM-DD}&endDate={YYYY-MM-DD}&rooms={N}&adults={N}&children={N}&childrenAges={age1,age2,...}
```

Example — 2 adults, 2 children (ages 5 and 7), Tokyo, June 2026:

```python
goto("https://www.expedia.co.in/Hotel-Search?"
     "destination=Central+Tokyo,+Tokyo+Prefecture&"
     "startDate=2026-06-01&endDate=2026-06-07&"
     "rooms=1&adults=2&children=2&childrenAges=5,7")
```

**Note:** `childrenAges` in the URL may not always populate the age dropdowns on
the results page. Verify with a screenshot and set them via JS if needed.

---

## Date Picker — DO NOT USE

The calendar widget is extremely unreliable with coordinate-based clicks:

- Clicking a date cell frequently **closes the entire picker** instead of
  selecting the date.
- The picker has month-navigation arrows that are tiny targets.
- "Flexible dates" mode has a different DOM structure with pill-shaped month
  selectors that also mis-fire.
- Dozens of retry attempts across multiple strategies all failed.

**Workaround:** Always pass dates via URL parameters (`startDate`, `endDate`).

---

## Travellers Widget

The travellers stepper panel works with JS `.click()` on the increment/decrement
buttons.

### Opening the panel

```python
js("""
(()=>{
  let btn = document.querySelector('button[data-testid="travelers-field-trigger"]')
           || [...document.querySelectorAll('button')].find(b => b.textContent.includes('traveller'));
  if(btn){ btn.click(); return 'opened'; }
  return 'not found';
})()
""")
```

### Incrementing children count

```python
js("""
(()=>{
  let span = [...document.querySelectorAll('span')].find(s => s.textContent.trim() === 'Children');
  if(!span) return 'no Children label';
  let container = span.closest('div').parentElement;
  let buttons = container.querySelectorAll('button');
  let plus = buttons[buttons.length - 1];  // last button is "+"
  plus.click();
  return 'incremented';
})()
""")
```

### Setting child ages

Child age dropdowns are `<select>` elements with `aria-label` like
"Child 1 age", "Child 2 age", etc.

```python
js("""
(()=>{
  let selects = document.querySelectorAll('select');
  // selects[0] = Child 1 age, selects[1] = Child 2 age, etc.
  let setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
  selects[0].value = '5';
  selects[0].dispatchEvent(new Event('change', {bubbles:true}));
  selects[1].value = '7';
  selects[1].dispatchEvent(new Event('change', {bubbles:true}));
  return 'ages set';
})()
""")
```

### Closing the panel

```python
js("""
(()=>{
  let btn = [...document.querySelectorAll('button')].find(b => b.textContent.trim() === 'Done');
  if(btn){ btn.click(); return 'done'; }
  return 'no Done button';
})()
""")
```

---

## Price Filter

On the results page, the nightly-price filter has two text inputs and two range
sliders.

| Element | Selector |
|---------|----------|
| Min text input | `#price-min` |
| Max text input | `#price-max` |
| Min range slider | `input[type="range"][aria-label*="Minimum"]` |
| Max range slider | `input[type="range"][aria-label*="Maximum"]` |

### Setting max price

The most reliable method is to click the input, select all, type the value, and
press Enter:

```python
click(x, y)  # coordinates of #price-max
js("document.getElementById('price-max').select()")
type_text("20000")
press_key("Enter")
```

Setting the value purely via JS (`dispatchEvent`) does trigger a re-search but
coordinate-click + type is more reliable for actually applying the filter.

---

## Key Lessons

1. **URL-first strategy** — Encode destination, dates, room count, adults,
   children, and child ages in the URL. Only use UI interaction for things the
   URL cannot express.

2. **JS `.click()` over coordinate clicks** — For buttons inside panels
   (traveller stepper, Done), find elements by text/attribute and call `.click()`
   in JS. Coordinate clicks on overlay panels are unreliable.

3. **`dispatchEvent` with `{bubbles: true}`** — Required for React-controlled
   inputs (selects, text fields). Without bubbling, React state won't update.

4. **Wait after navigation** — After `goto()` or pressing Search, call
   `wait_for_load()` + `time.sleep(3)` before interacting. Expedia loads
   results asynchronously.

5. **Indian locale** — `expedia.co.in` shows prices in ₹ (INR). The price
   filter values include the ₹ symbol and commas in the text input but the
   underlying range slider uses plain integers.
