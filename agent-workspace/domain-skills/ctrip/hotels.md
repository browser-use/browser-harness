# Ctrip (携程 / `ctrip.com`) — Hotel Scraping

Field-tested 2026-04-29 against `hotels.ctrip.com` PC web. Domestic hotels.

---

## TL;DR

**Prices are visible without login** — but only if you reach the list page
through a "natural" navigation flow that produces a complete URL parameter
schema. Direct GETs to a simplified URL get redirected to login.

- Browser session required (the page shell is 144 KB, hotels are loaded by
  XHR after hydration). `http_get` cannot retrieve hotel data.
- Once on a valid list page, prices render as `¥<original> ¥<current> 起`
  pairs. No `¥?` placeholders and no `请登录` interstitial.
- Detail URL `https://hotels.ctrip.com/hotel/<hotelId>.html?checkin=...` works
  pre-login and shows full room-rate breakdown.
- Compared to ly.com (which hides every price behind login) ctrip is far more
  scrape-friendly *if you respect the URL schema*.

---

## URL patterns

```
List page (canonical, anonymous-friendly):
  https://hotels.ctrip.com/hotels/list
    ?flexType=1
    &cityId=<n>          # 2 = 上海, 1 = 北京, etc.
    &provinceId=0
    &districtId=0
    &countryId=1         # 1 = 中国 domestic
    &checkin=YYYY-MM-DD
    &checkout=YYYY-MM-DD

Hotel detail (canonical):
  https://hotels.ctrip.com/hotel/<hotelId>.html?checkin=...&checkout=...
  → server rewrites to /hotels/detail/?... — both work, same data

Login page (when reached unintentionally):
  https://passport.ctrip.com/user/login?backurl=<url-encoded-target>
```

**Critical:** the *simplified* form `https://hotels.ctrip.com/hotels/list?city=2&checkin=...&checkout=...`
(note: `city`, not `cityId`, and missing `provinceId/districtId/countryId/flexType`)
**redirects to login.** This is ctrip's signature anti-scrape gate — it
distinguishes a "real" client (built the URL through the homepage form) from
a scripted client (typed the URL by hand).

---

## How to land on the list page reliably

### Path A — build the canonical URL (preferred when you know cityId)

```python
from browser_harness.helpers import new_tab, wait_for_load
import time
url = (
    "https://hotels.ctrip.com/hotels/list"
    "?flexType=1&cityId=2&provinceId=0&districtId=0&countryId=1"
    "&checkin=2026-04-29&checkout=2026-04-30"
)
new_tab(url)
wait_for_load(timeout=20)
time.sleep(6)            # XHR hotel-list fetch
```

### Path B — simulate the homepage flow (when you only have a city name)

If you only have a city name, drive the home-page form. The 搜索 button is
a `<div>`, not `<button>` (same as ly.com — see "search button gotcha"
below):

```python
from browser_harness.helpers import new_tab, wait_for_load, js, click_at_xy, type_text, press_key
import time

new_tab("https://hotels.ctrip.com/")
wait_for_load(timeout=20)
time.sleep(2)

# Find destination input by placeholder
inp = js("""
  const i = Array.from(document.querySelectorAll("input"))
    .find(i => i.placeholder && /目的地|城市|酒店/.test(i.placeholder));
  if (!i) return null;
  const r = i.getBoundingClientRect();
  return {x: r.x+r.width/2, y: r.y+r.height/2};
""")
if not inp:
    raise RuntimeError("ctrip homepage: destination input not found — page DOM may have changed")
click_at_xy(inp["x"], inp["y"])
time.sleep(0.4)
type_text("上海")
time.sleep(1.5)
press_key("Enter")        # selects first autocomplete suggestion

btn = js("""
  const b = Array.from(document.querySelectorAll("button, div"))
    .find(el => (el.innerText||"").trim() === "搜索"
                && el.getBoundingClientRect().width > 60);
  if (!b) return null;
  const r = b.getBoundingClientRect();
  return {x: r.x+r.width/2, y: r.y+r.height/2};
""")
if not btn:
    raise RuntimeError("ctrip homepage: 搜索 button not found — page DOM may have changed")
click_at_xy(btn["x"], btn["y"])
time.sleep(7)
# now on /hotels/list?... with the full canonical schema
```

This is what the human would do, and it's what makes the parameter schema
match. Cookies set during this flow help future direct-URL requests too.

---

## List page — extracting hotels

Cards are `<div class="list-item">`. **No `data-id`, no `<a href=...>`.**
The hotel ID lives only in the React component closure — to navigate to
detail you either click the card visually (coordinate click) or scrape the
hotel name and re-visit `/hotel/<id>.html` once you've resolved the ID by
some other means (e.g. a mapping you build over time).

```js
// list extraction — runs in browser via js(...)
return Array.from(document.querySelectorAll(".list-item")).slice(0, 30).map(card => {
  const text = (card.innerText || "").replace(/\s+/g, " ");
  const name = text.match(/^([^\s]{2,40}?(?:酒店|宾馆|公寓|民宿)(?:\([^)]*\))?)/)?.[1];
  const score = text.match(/[1-5]\.\d/)?.[0];
  // strip "1,234条点评" before grabbing prices, otherwise ¥1 from "1,234" leaks in
  const priced = text.replace(/\d{1,3}(?:,\d{3})+/g, "").replace(/\d+条点评/g, "");
  const prices = (priced.match(/¥\s*(\d{2,})/g) || []).map(s => parseInt(s.replace(/[^\d]/g, "")));
  const [original, current] = prices;
  return {name, score, price_original: original ?? null, price_current: current ?? null};
});
```

**Trap:** review counts like `1,234条点评` and `5,678条点评` will match
`¥\s*\d+` if you don't strip them first — `¥1` and `¥5` will appear as
phantom prices. Always pre-strip thousand-separated numbers and review
counts before the price regex.

The text shape per card:
```
<name> [4.8] [超棒][1,994条点评] <tagline> 近<area> · <metro>查看地图 <room-type> 订单确认后30分钟内免费取消 ... ¥<original> ¥<current> 起 查看详情
```

The "起" suffix means "from"; the actual booked price can be higher
depending on rate plan / breakfast / cancellation.

---

## Detail page

```
https://hotels.ctrip.com/hotel/<hotelId>.html?checkin=YYYY-MM-DD&checkout=YYYY-MM-DD
```

Works pre-login. Server normalizes to `/hotels/detail/?...` but the data is
identical. Title format: `🟢 <hotelName>预订价格,联系电话位置地址【携程酒店】`
(the 🟢 prefix is from `browser-harness`, not ctrip).

Detail page renders multiple room-rate rows with the same `¥orig ¥current`
shape as the list. Look for `<button>` or `<a>` whose text is exactly `预订`
and walk up to the rate card.

If you hit a hotel that no longer exists, the URL silently survives but
shows a generic "预订价格,联系电话位置地址【携程酒店】" title with no
prices — detect by `bodyText.match(/¥\s*\d+/) === null`.

---

## Login redirect signal

When ctrip decides your session is suspicious it redirects to:

```
https://passport.ctrip.com/user/login?backurl=...
```

The login form pre-fills the last phone number from the user's Chrome
form-fill. If you see this URL, **do not type credentials** — bail and
either (a) restart the flow through the homepage form (Path B above), which
fixes the URL schema mismatch, or (b) ask the user to log in interactively.

Detection:
```python
if "passport.ctrip.com" in page_info()["url"]:
    raise RuntimeError("ctrip wants login — restart from homepage")
```

In our test, redirect was triggered by:
- Hitting `/hotels/list?city=2&...` (note: `city`, not `cityId`).
- Direct GET without ever loading `hotels.ctrip.com/` first in the session.

Conversely, *not* triggered by:
- Hitting `/hotels/list?flexType=1&cityId=2&provinceId=0&districtId=0&countryId=1&...`
  cold (zero ctrip cookies pre-set).
- Hitting `/hotel/<id>.html?...` directly.

So the gate is parameter-schema-based, not behavior-based. Get the schema
right and you don't need a login flow.

---

## Global state — don't bother

`window._objAllSearchResult` exists but is empty in the live session.
Ctrip's hotel data lives in React component state, not on `window`.
**Use DOM extraction.** No `__NEXT_DATA__`, no `__APOLLO_STATE__`, no
`window.__INITIAL_STATE__`.

---

## Traps

- **Simplified URL (`?city=`) redirects to login.** Use the canonical
  six-param schema or drive the homepage form.
- **Default homepage tab is 海外酒店 (overseas).** Featured hotels show
  "暂无价格" and pre-select Singapore/Phuket dates. Don't read prices off
  the homepage — go to `/hotels/list?...` instead.
- **Phantom `¥1`, `¥5` prices** from review-count regex bleed-through.
  Strip `\d+,\d+` and `\d+条点评` before applying `¥\d+`.
- **No detail URL on cards.** No `data-id`, no `<a>`. Coordinate click is
  the only reliable navigate-to-detail option without an external ID
  source.
- **`/hotel/{id}.html` for a non-existent ID returns 200** with the brand
  chrome and no error — detect by absence of prices in body text.
- **The 搜索 button is a `<div>`.** Same gotcha as ly.com — coordinate
  click works, `el.click()` is unreliable.
- **`hotels.ctrip.com` is the *domestic* host.** Title says "海外酒店预订"
  on the homepage but `/hotels/list?countryId=1&...` is domestic. The
  overseas equivalent uses `countryId` ≠ 1 (not yet mapped).

---

## Useful cityId values (observed)

| 城市 | cityId |
|------|--------|
| 上海 | 2 |
| 北京 | 1 |
| 广州 | 32 |
| 深圳 | 30 |

Get more by driving the homepage flow once and reading the canonical URL.

---

## Quick start

```python
from browser_harness.helpers import new_tab, wait_for_load, js, cdp
import time, json

url = (
    "https://hotels.ctrip.com/hotels/list"
    "?flexType=1&cityId=2&provinceId=0&districtId=0&countryId=1"
    "&checkin=2026-04-29&checkout=2026-04-30"
)
tid = new_tab(url)
wait_for_load(timeout=20)
time.sleep(6)

hotels = js("""
  return Array.from(document.querySelectorAll(".list-item")).slice(0, 20).map(card => {
    const raw = (card.innerText || "").replace(/\\s+/g, " ");
    const cleaned = raw.replace(/\\d{1,3}(?:,\\d{3})+/g, "").replace(/\\d+条点评/g, "");
    const name = raw.match(/^([^\\s]{2,40}?(?:酒店|宾馆|公寓|民宿)(?:\\([^)]*\\))?)/)?.[1] || null;
    const prices = (cleaned.match(/¥\\s*\\d{2,}/g) || [])
                     .map(s => parseInt(s.replace(/[^\\d]/g, "")));
    const score = raw.match(/[1-5]\\.\\d/)?.[0] || null;
    return {name, score, price_original: prices[0] ?? null, price_current: prices[1] ?? null};
  });
""")
print(json.dumps(hotels, indent=2, ensure_ascii=False))
cdp("Target.closeTarget", targetId=tid)
```
