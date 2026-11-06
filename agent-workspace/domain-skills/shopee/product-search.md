# Shopee (shopee.sg) — Product Search & Data Extraction

Field-tested against shopee.sg on 2026-05-29 using a **logged-in** Chrome session
(competitor price survey for frozen ramen/udon). Shopee SG is heavy, lazy-rendered,
and bot-defended. The patterns below are what actually survived; the naive Playwright
reflexes (wait_for_load, full screenshot, JS scroll, search API) all fail here.

## Prerequisites — you MUST be logged in

Anonymous sessions are blocked. Navigating to any `shopee.sg/...` URL while logged out
redirects to a traffic-verification wall:

```
https://shopee.sg/verify/traffic/error?...&is_logged_in=false&...&type=4
title: "Shopee Singapore | Cheaper, Faster On Shopee"
body : "Page Unavailable — Looks like you're not logged in yet."
```

There is no programmatic bypass. If you land on `/verify/traffic/error`, stop and ask the
user to log into Shopee in their Chrome, then retry. Detect it early:

```python
def shopee_blocked():
    return "/verify/traffic/error" in page_info()["url"]
```

The search API is also blocked — do **not** waste a call on it:
```python
# http_get("https://shopee.sg/api/v4/search/search_items?keyword=...") -> HTTP 403
```
All extraction must go through the rendered DOM in the logged-in browser.

## Tab hygiene (do this — Shopee tabs pile up fast)

Open Shopee **once** with `new_tab`, then reuse that one tab with `goto_url` for every
subsequent search. Close it when the task is done. Do NOT call `new_tab` per search — that
is how you end up with dozens of orphan tabs.

```python
# first search of the session
tid = new_tab("https://shopee.sg/search?keyword=frozen%20ramen")
wait(8)

# every later search: reuse the SAME tab
goto_url("https://shopee.sg/search?keyword=frozen%20udon")
wait(8)

# when finished with Shopee entirely
close_tab(tid)            # or close_tab() to close the current tab
```

If you spawned strays during exploration, sweep them at the end:
```python
for t in list_tabs(include_chrome=False):
    if "shopee.sg" in t["url"]:
        close_tab(t["targetId"])
```

## Navigation

### Search URL (only reliable entry point)
```python
goto_url("https://shopee.sg/search?keyword=frozen%20ramen%20soup")  # spaces = %20 (or +)
wait(8)   # NOT wait_for_load() — see Gotchas
```
- Pagination: append `&page=N` (0-indexed). The UI shows a `1/N` page counter.
- Sort: the UI exposes Relevance / Latest / Top Sales / Price tabs; relevance (default) is fine
  for surveys. Sorting via URL params is unreliable — click the tab if you must.

### Product detail page
Product URLs carry the id pattern `...-i.<shopId>.<itemId>`:
```python
goto_url("https://shopee.sg/product-name-i.123456.7890123")
wait(7)
```

## The three things that WILL bite you

### 1. `wait_for_load()` times out — use a fixed `wait()`
Shopee's main thread stays busy long after `readyState=complete`, so the
`js("document.readyState")` poll inside `wait_for_load()` raises a CDP timeout.
Use a hard `wait(7)`–`wait(9)` after navigation instead.

### 2. Full-page screenshots time out — use `full=False`
The results page is very tall; `capture_screenshot()` (full page) exceeds the IPC
deadline. Always pass `full=False` for a viewport-only grab:
```python
img = capture_screenshot(full=False)
```

### 3. The result grid lazy-renders, and `window.scrollTo` can hang
After navigation the SEARCH FILTER sidebar appears but the product grid is blank until
the viewport scrolls. `js("window.scrollTo(0, N)")` itself sometimes times out because
the main thread is blocked. The reliable nudge is a CDP **keyboard End** event, then wait:

```python
cdp("Input.dispatchKeyEvent", type="keyDown", key="End", windowsVirtualKeyCode=35)
cdp("Input.dispatchKeyEvent", type="keyUp",   key="End", windowsVirtualKeyCode=35)
wait(3)
```

A blank grid shows `len(js("document.body.innerText"))` ≈ 150–200. After the grid
renders it jumps to ~3000+. If a `js()`/screenshot call raises `TimeoutError`, the page
was mid-render — just retry the read in a **separate** call (the page keeps loading in
the background; do not restart the daemon for this).

## Search results extraction — parse innerText, not selectors

The DOM cards (`li.shopee-search-item-result__item`) render lazily and querySelector often
returns 0 right after load. The robust method is parsing `document.body.innerText`, where
each result is laid out as **separate lines** with the `$` on its own line:

```
<product name>
$
12.90
-15%            (optional discount line)
4.9             (rating, optional)
2k+ sold        (optional)
2 Days          (delivery, optional)
SG
Find Similar
```

Parser (find the `$` line, take the line before as name, the line after as price):
```python
import re
txt = js("document.body.innerText") or ""
lines = [l.strip() for l in txt.split("\n") if l.strip()]
out, seen = [], set()
for i, l in enumerate(lines):
    if l == "$" and i+1 < len(lines) and re.match(r"^[\d,]+\.\d{2}$", lines[i+1]):
        name = lines[i-1]
        if len(name) > 8 and "sold" not in name and name not in seen:
            seen.add(name)
            out.append(("$" + lines[i+1], name))
```

Results start just after the line `Search result for '<keyword>'` and the `1/N` counter;
everything before that (trending keywords, filter labels) is chrome — the `len>8` and
`"sold" not in name` guards drop most of it.

Selector fallback (only works once cards are in view — scroll first):
```python
js("document.querySelectorAll('li.shopee-search-item-result__item').length")
```

## Relevance filtering (Shopee search is noisy)

A query like "frozen ramen" returns mostly **instant cup/packet noodles, soup-base
concentrates, and restaurant catering bundles** — not frozen retail packs. Filter by
keyword in the product name and sanity-check the price band. In this survey, genuine
frozen retail ramen/udon was scarce on Shopee; the real catalogue depth was on
Lazada/RedMart. Don't assume an empty/odd result set is a bug — Shopee genuinely may not
stock the SKU.

## Daemon / IPC recovery

Heavy Shopee pages occasionally throw `TimeoutError: timed out` from the IPC layer.
Escalate gently:
1. Retry the same read in a new `browser-harness` call (cheapest; usually enough).
2. `ensure_real_tab()` then retry, if the session looks detached.
3. `restart_daemon()` only as a last resort — on Chrome 144+ it re-triggers the
   "Allow remote debugging?" popup, which the user must click again. Avoid mid-task.

## Gotchas (field-tested)

- **Logged-out = hard wall** at `/verify/traffic/error` (`type=4`). No bypass; ask the user to log in.
- **Search API → 403.** Browser DOM only.
- **`wait_for_load()` times out.** Use `wait(7-9)`.
- **`capture_screenshot()` (full page) times out.** Use `capture_screenshot(full=False)`.
- **`window.scrollTo` can hang.** Nudge with a CDP `End` key event, then `wait(3)`.
- **Prices are split text nodes.** In innerText the `$` and the number are on separate lines — parse accordingly; `querySelector('[class*=price]')` is brittle.
- **Cards render lazily.** querySelector count is 0 until the grid scrolls into view.
- **Reuse one tab.** `goto_url` for repeat searches; `close_tab()` when done. Never `new_tab` per query.
- **Noisy results.** Instant noodles / soup bases / catering dominate "frozen" queries — filter by name.
