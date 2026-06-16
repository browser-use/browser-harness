# Tongcheng (ly.com / 同程旅行) — Hotel Scraping

Field-tested 2026-04-29 against the PC web (`www.ly.com`). Mobile H5 paths
not yet mapped. All notes below are PC unless stated otherwise.

---

## TL;DR

**Prices are gated behind login. Hotel metadata is not.**

- List page returns `prc=null&cury=null` in the result URLs and renders every
  price as the literal string `￥？` until the user is signed in.
- After login (cookies persist in the user's Chrome), the same DOM nodes
  render real numbers (`¥259 ¥200 ¥59` triplets — see *Price triplet shape*).
- Hotel name / address / metro / star / English name / opening + decorate
  dates are available pre-login from `window.__NUXT__` SSR state.

**Practical implication:** `http_get` is useless for prices. You need a
browser session AND a logged-in user. `browser-harness` connecting to the
user's daily Chrome is the cheapest way — once they log in once via
`passport.ly.com`, the cookie sticks across runs.

---

## URL patterns

```
List page:
  https://www.ly.com/hotel/hotellist?city=<cityId>&inDate=YYYY-MM-DD&outDate=YYYY-MM-DD

Hotel detail page:
  https://www.ly.com/hotel/hoteldetail?hotelId=<hotelId>&inDate=YYYY-MM-DD&outDate=YYYY-MM-DD

Login page (with return URL):
  https://passport.ly.com/?pageurl=<urlencoded-target>
```

`cityId` is Tongcheng's internal id, not GB code. Shanghai = `321`. Get it by
running a search via the home page — the redirect URL contains it.

`hotelId` is per-property, stable. Range observed: 8-digit numerics
(e.g. `92963586`, `50201258`, `93067902`).

The list page also accepts `&keyword=`, `&star=`, etc., but the form fields
on `/hotel/` are the canonical entry — fill them or click the search div and
let the SPA build the URL.

### Mobile H5 — DO NOT use these (404 in our test)

- `https://m.ly.com/scenery/hotel/<hotelId>` — 404
- `https://hotelh5.ly.com/...` — not yet mapped

If you need a mobile path, search from `m.ly.com/` instead of guessing.

---

## Search button is NOT a `<button>`

On `https://www.ly.com/hotel/`, the green "搜索" search button is a `<div>`,
not `<button>` or `<a>`. JS click via `element.click()` does **not** fire the
SPA handler reliably. Two patterns that work:

1. **Coordinate click** (preferred — same shape as the rest of harness):
   ```python
   from browser_harness.helpers import js, click_at_xy
   btns = js("""
     return Array.from(document.querySelectorAll("div"))
       .filter(el => (el.innerText||"").trim() === "搜索")
       .map(el => { const r = el.getBoundingClientRect();
                    return {x: r.x+r.width/2, y: r.y+r.height/2}; });
   """)
   click_at_xy(btns[0]["x"], btns[0]["y"])
   ```

2. **Direct URL navigation** (skip the form entirely): build the
   `/hotel/hotellist?city=<id>&inDate=...&outDate=...` URL yourself.

After clicking, the list renders via XHR. Page shows the loader text
"正在搜寻更多住宿……" — wait ~5–7 s before extracting cards.

---

## List page — extracting hotels

Hotel cards are `<a>` elements with class `listBox` (Tailwind-mangled, so
the full class string is `mb-[20px] flow-root listBox` or similar — match by
`a[class*=listBox]`).

```js
Array.from(document.querySelectorAll("a[class*=listBox]")).slice(0, 20).map(a => {
  const href = a.href;
  const m = href.match(/hotelId=(\d+)/);
  return {
    hotelId: m ? m[1] : null,
    href,
    text: (a.innerText || "").replace(/\s+/g, " ").slice(0, 200),
  };
});
```

The card `innerText` is pipe-separated and contains: hotel name, star tier,
score (4.x), review count, amenity tags, area/metro, then `￥？ 查看详情`
when not logged in (or `¥<n> 预订` after login from the list page — but the
list page often still hides prices and only the detail page shows them
reliably).

The `href` carries a verbose `traceToken` query that's safe to drop when
re-navigating; only `hotelId`, `inDate`, `outDate` matter.

---

## Detail page — Nuxt SSR state

The site is built on Nuxt.js. Pre-login data lives at:

```
window.__NUXT__.data["$<random-hash>"]   // per-page-load, NOT stable
```

The data object contains exactly two keys per page load. The first
(`$VKSoZS1qt0`-style) holds page chrome (header/footer/CSS); the second
holds the actual hotel payload. Find it by shape, not by key:

```js
const dataMap = window.__NUXT__?.data || {};
const hotelEntry = Object.values(dataMap).find(v => v && v.hotelData);
// Prefer the public Vue ref API (`.value`); fall back to `_rawValue` only
// if a future Vue/Nuxt build changes the unwrapping shape.
const meta = hotelEntry?.hotelData?.value ?? hotelEntry?.hotelData?._rawValue;
// meta now has: hotelid, hotelName, hotelNameEn, hotelAddress,
// nearestAreaPosition, hotelArea, starLevel, headPicUrl
```

`detailBaseInfo.value` adds: `openDate`, `decorateDate`, `featureInfo`
(prose paragraph), and the full address again.

**Prices are NOT in `__NUXT__`.** They're loaded by a separate XHR after
hydration. This is server-side gating, not a client-side hide — the price
fields literally don't exist in the SSR payload until the user is
authenticated.

---

## Price extraction (logged in)

Each room/rate card contains a `预订` button (`<button>` or `<a>` —
visibility is `offsetParent !== null`). Walk up to the smallest ancestor
whose `innerText.length > 80` to get the card.

### Price triplet shape

Every visible price block is a 3-tuple in DOM order:

```
[¥<original>] [¥<member_price>] [¥<savings>]
```

For the room "至尊·大床房 (无餐食)" we observed `¥259 ¥200 ¥59`. The
discount is always `original - member_price`, so use it as a sanity check
when the regex catches stray `¥` from neighboring elements.

```js
const text = card.innerText.replace(/\s+/g, " ");
const nums = (text.match(/¥\s*\d+(?:\.\d+)?/g) || [])
              .map(s => parseFloat(s.replace(/[^\d.]/g, "")));
const [original, current, saved] = nums;
// validate: Math.abs((original - current) - saved) < 1
```

Other useful fields in the card text:
- `无餐食` / `1份早餐` / `2份早餐` — meal plan
- `订单确认30分钟内可免费取消` — cancellation policy
- `可开专票` — VAT invoice
- 房型名通常在卡片头部，跟在 `套餐` 之后；面积写作 `<n>-<m>㎡`

The "房间" tab is the default landing tab. If the page lands somewhere else,
scroll to ~`y=1400` (relative to a 6900-tall doc on a 720-viewport) or click
the `房间` tab DOM element to bring rooms into view.

---

## Login flow

Login URL takes a `pageurl` query so the user lands back where they started:

```python
new_tab(f"https://passport.ly.com/?pageurl={urllib.parse.quote(target_url)}")
```

Detection — login is complete when the active URL leaves the `passport.ly.com`
host. Poll `page_info()` every 3 s; bail when:

```python
url = page_info()["url"]
done = "passport.ly.com" not in url and "login" not in url.lower()
```

> Gotcha: while the user is on the login page (and especially when they
> change tabs/swipe through QR steps), `page_info()` can momentarily error
> with "Cannot read properties of null (reading 'scrollWidth')" — the
> document body isn't ready. Wrap each poll in try/except and continue.

Cookies set by `passport.ly.com` are scoped to `.ly.com` and persist in the
user's Chrome profile. They survive across `browser-harness` runs and across
Chrome restarts. There is no need to re-login per session.

---

## XHRs to watch (not yet reverse-engineered)

We observed but did not capture:

- A price-fetch XHR fires after Nuxt hydration on the detail page; it appears
  to gate on the `.ly.com` auth cookie. Reverse-engineering this would let
  you skip the browser entirely once you have a valid token, but the request
  almost certainly carries an anti-replay signature.
- A list-page price-fill XHR fires after the initial render (the `prc=null`
  in the card URL is a placeholder for what would have been written here).

Until one of these is mapped, **prefer DOM extraction over network sniffing.**

---

## Traps

- **`￥？` is real DOM content, not a CSS placeholder.** Don't waste time
  hunting for hidden elements or computed styles — the server simply doesn't
  send a price for unauthenticated requests.
- **`m.ly.com/scenery/hotel/<id>`** returns 404. Don't pattern-match mobile
  URLs without verifying.
- **`__NUXT__` data keys are randomized per page load** (`$VKSoZS1qt0`,
  `$0GffEk0IYv`, ...). Iterate values and detect by shape (presence of
  `hotelData`), don't hardcode the key.
- **`__NUXT__.data.X.hotelData` is a Vue ref.** Read `_rawValue` (or
  `_value`); both contain the same data. Don't try to `JSON.stringify` the
  ref directly — circular refs blow up.
- **The "搜索" search button is a `<div>`, not a button.** `el.click()`
  doesn't trigger the SPA — use coordinate click or build the list URL
  directly.
- **`predict-future` dates** (e.g. `inDate=2099-01-01`) silently coerce to
  the next available night — don't rely on echoing the input back.

---

## Quick start (logged-in user, harness attached)

```python
from urllib.parse import quote
import time, json
from browser_harness.helpers import new_tab, wait_for_load, js, page_info, cdp

HOTEL_ID = "92963586"   # 和颐至尊酒店(上海新国际博览中心世博园店)
url = f"https://www.ly.com/hotel/hoteldetail?hotelId={HOTEL_ID}&inDate=2026-04-29&outDate=2026-04-30"

tid = new_tab(url)
wait_for_load(timeout=20)
time.sleep(4)            # XHR price fetch
js("window.scrollTo(0, 1400)")
time.sleep(2)

rooms = js("""
  const buttons = Array.from(document.querySelectorAll("button, a, div"))
    .filter(el => (el.innerText||"").trim() === "预订" && el.offsetParent !== null);
  const out = [], seen = new Set();
  for (const btn of buttons) {
    let card = btn.parentElement;
    while (card && card.innerText.length < 80) card = card.parentElement;
    if (!card) continue;
    const k = card.innerText.slice(0, 50);
    if (seen.has(k)) continue;
    seen.add(k);
    const text = card.innerText.replace(/\\s+/g, " ");
    const nums = (text.match(/¥\\s*\\d+(?:\\.\\d+)?/g) || [])
                   .map(s => parseFloat(s.replace(/[^\\d.]/g, "")));
    out.push({
      summary: text.slice(0, 120),
      price_original: nums[0] ?? null,
      price_current:  nums[1] ?? null,
      saved:          nums[2] ?? null,
    });
    if (out.length >= 10) break;
  }
  return out;
""")
print(json.dumps(rooms, indent=2, ensure_ascii=False))
cdp("Target.closeTarget", targetId=tid)
```
