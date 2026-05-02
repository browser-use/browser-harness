# Jinjiang WeHotel (`bestwehotel.com`) — Hotel Scraping

Field-tested 2026-04-29 against `www.bestwehotel.com` PC web. The official
direct-booking portal of the Jin Jiang group, covering ~50 sub-brands
(锦江/J酒店/昆仑/丽笙/丽筠/丽柏/维也纳/锦江都城/白玉兰/麗枫/喆啡/希岸/IU/7天/锦江之星 etc.).

---

## TL;DR

**Most scrape-friendly of the three Chinese hotel portals tested**:

- Anonymous works on both list and detail pages — no login wall, no
  parameter-schema gate, no `¥?` placeholders.
- `http_get` does not work (SPA shell only). Need a browser session.
- Browser cookies aren't required either — a freshly-opened tab via
  `browser-harness` immediately renders 200+ hotels with prices.
- Detail pages show full rate-plan breakdown (multiple room types ×
  breakfast/cancellation matrix) anonymously.
- Compared to: ly.com forces login for every price; ctrip works only via a
  canonical 6-param URL schema or homepage-driven flow; WeHotel just works.

---

## URL patterns

```
List page:
  https://www.bestwehotel.com/HotelSearch/
    ?checkinDate=YYYY-MM-DD            # NOTE: lower-case  i / d
    &checkoutDate=YYYY-MM-DD            # NOTE: lower-case  o / d
    &cityCode=AR04567                   # WeHotel internal alpha-numeric code
    &cityName=<urlencoded-Chinese>
    &queryWords=                        # optional keyword filter
    &extend=1,2,0,0,0,0                 # rooms,adults,children,...

Hotel detail page:
  https://www.bestwehotel.com/HotelDetail/
    ?hotelId=JJ1888                     # JJ<digits>; "JJ" prefix = Jin Jiang chain
    &checkInDate=YYYY-MM-DD             # NOTE: capital  I and D
    &checkOutDate=YYYY-MM-DD             # NOTE: capital  O and D
    &extend=1,2,0,0,0,0
```

**Param-name capitalization is inconsistent between list and detail.**
List uses `checkinDate/checkoutDate`; detail uses `checkInDate/checkOutDate`.
Get this wrong and the page silently falls back to default dates.

---

## How to land on the list page

The home-page form has 上海 as the default destination and reasonable default
dates, so two equivalent paths work:

### Path A — drive the homepage form

```python
from browser_harness.helpers import new_tab, wait_for_load, click_at_xy, js, type_text
import time

new_tab("https://www.bestwehotel.com/")
wait_for_load(timeout=20)
time.sleep(2)

# Search button is a <div> (and a sibling <a> with same coords) — coordinate click works
btn = js("""
  const b = Array.from(document.querySelectorAll('button, div, a'))
    .find(el => (el.innerText||'').trim() === '搜索' && el.offsetParent !== null);
  const r = b.getBoundingClientRect();
  return {x: r.x+r.width/2, y: r.y+r.height/2};
""")
click_at_xy(btn["x"], btn["y"])
time.sleep(8)            # XHR list fetch
```

### Path B — build the canonical URL (preferred when you know `cityCode`)

```python
url = (
    "https://www.bestwehotel.com/HotelSearch/"
    "?checkinDate=2026-04-30&checkoutDate=2026-05-01"
    "&cityCode=AR04567&cityName=%E4%B8%8A%E6%B5%B7"
    "&queryWords=&extend=1,2,0,0,0,0"
)
new_tab(url)
wait_for_load(timeout=20)
time.sleep(8)
```

WeHotel does **not** redirect-to-login when you skip `provinceId/districtId/countryId`-style
parameters (unlike ctrip). The `cityCode` alone is sufficient.

---

## List page — extracting hotels

The reliable path: walk back from `查看详情` `<a>` tags. Each card emits
**three** `<a>` with the same `hotelId` href but different innerText:
empty, hotel-name, and `查看详情`. Walk up to the smallest ancestor
containing all three.

```js
return Array.from(document.querySelectorAll("a[href*=HotelDetail]"))
  .filter(a => (a.innerText || "").trim() === "查看详情")
  .slice(0, 30)
  .map(detailA => {
    const id = (detailA.href.match(/hotelId=([A-Z]+\d+)/i) || [])[1];

    // Walk up to the smallest container that includes the hotel-name <a>
    // (an anchor sharing the same hotelId href but whose text is NOT
    // "查看详情" — that text lives on the link body, not in the href, so
    // we filter by anchor identity / innerText, not by attribute selector).
    let card = detailA.parentElement;
    const hasNameAnchor = (el) =>
      Array.from(el.querySelectorAll("a[href*='" + id + "']"))
        .some(a => a !== detailA && (a.innerText || "").trim() && (a.innerText || "").trim() !== "查看详情");
    while (card && !hasNameAnchor(card)) {
      card = card.parentElement;
    }
    if (!card) return null;

    const text = (card.innerText || "").replace(/\s+/g, " ");
    const name = text.match(/(?:\d+\s+)?([^\s]{2,40}?(?:酒店|宾馆|大酒店|饭店))/)?.[1] || null;
    const score = text.match(/(\d\.\d)\s*\/\s*5/)?.[1] || null;
    const grade = (text.match(/(豪华型|高档型|舒适型|经济型)/) || [])[1] || null;
    const distance = (text.match(/距离市中心\s*([\d.]+)\s*km/) || [])[1] || null;
    const fromPrice = (text.match(/(?:¥|￥)\s*(\d+)\s*起/) || [])[1] || null;
    const address = (text.match(/地址：([^|]+?)距离/) || [])[1]?.trim() || null;
    const amenities = (text.match(/(停车场|餐厅|新店|游泳池|健身房|wifi)/g) || []).slice(0, 5);

    return {
      hotelId: id,
      name, score, grade, distance, address,
      price_from: fromPrice ? parseInt(fromPrice) : null,
      amenities,
    };
  })
  .filter(x => x && x.hotelId);
```

The body shows total via `查询到 N 家酒店`.

### Card field shape (observed)

```
<index>
<hotel-name>
地址：<full-address>
距离市中心 X.X km
<rating>/5分
<grade>            # 豪华型/高档型/舒适型/经济型
<amenity tags>     # 停车场/餐厅/新店/...
￥<price>起
查看详情
```

---

## Detail page — extracting room rates

Detail page shows a flat table: `房型 | 早餐 | 取消政策 | 人数上限 | 房价 | <book-button>`.
Each row contains the rate plan and a single `¥<price>` (no original/discount
triplet — list rates are already "from price").

```js
const rows = Array.from(document.querySelectorAll("[class*=room], [class*=Room]"))
  .filter(el => (el.innerText || "").includes("立即预订") || (el.innerText || "").includes("￥"))
  .slice(0, 30);

return rows.map(row => {
  const text = (row.innerText || "").replace(/\s+/g, " ");
  return {
    room_type: text.match(/^(\S+(?:大床房|双床房|套房|标间|双人房)\S*)/)?.[1] || null,
    breakfast: text.match(/(无早餐|含早餐|含\d份早餐|\d份早餐)/)?.[1] || null,
    cancel: text.match(/(限时取消|免费取消|不可取消|订单确认后\d+分钟内可免费取消)/)?.[1] || null,
    price: parseInt((text.match(/(?:¥|￥)\s*(\d+)/) || [])[1] || "0"),
    full: text.slice(0, 200),
  };
}).filter(r => r.price > 0);
```

Title pattern: stays `🟢 锦江酒店WeHotel官网` (the harness 🟢 prefix). The
hotel name is in the page body, not the title — extract via the page header,
which uses generic `[class*=name]` or `[class*=title]` selectors.

---

## Brand matrix (under the WeHotel umbrella)

WeHotel covers all Jin Jiang group brands. Useful when filtering or guessing
hotelId prefixes:

```
LUXURY (奢华尊选):    J酒店, 昆仑
PREMIUM (高端甄选):   锦江, 丽笙精选, 丽笙, 丽筠, 丽芮, 暻阁, 郁锦香, 丽柏, Park Plaza
QUALITY (精品优选):   维也纳国际/酒店/智好/3好, 非繁云居, Park Inn, Renjoy, 锦江都城, 凯里亚德, Lavande
ESSENTIALS (舒适智选): 锦江之星(品尚/风尚), 7天酒店, 7天优品, IU酒店, 派酒店, 白玉兰, 康铂, 麗枫, 喆啡, 希岸, 潮漫
```

All of these are bookable through the same `/HotelDetail/?hotelId=JJ<n>` URL.

---

## Global state — none useful

`window.__INITIAL_STATE__`, `__NUXT__`, `__NEXT_DATA__`, `__APOLLO_STATE__`
are all absent. Hotel data is loaded into Vue/React component state via XHR,
not exposed on `window`. **Use DOM extraction.**

---

## Traps

- **`checkinDate` (lower-case) on list, `checkInDate` (capital I) on detail.**
  Mixing them up causes silent fallback to default dates. Always copy from
  this doc rather than typing.
- **`cityCode` is alpha-numeric, not numeric.** Shanghai = `AR04567`. There's
  no obvious mapping — get it once via the homepage form and cache.
- **Card has 3 `<a>` with the same href.** First is empty (image link),
  second is name, third is `查看详情`. Filter by inner text to dedup.
- **Default dates on the homepage shift daily.** Don't trust the form's
  pre-filled dates — set them explicitly via URL or fill the form before
  clicking 搜索.
- **"价格区间-" filter** in the body text is a UI element, not data —
  don't accidentally extract `¥?` from it.

---

## Quick start

```python
import time, json
from browser_harness.helpers import new_tab, wait_for_load, js, cdp

url = (
    "https://www.bestwehotel.com/HotelSearch/"
    "?checkinDate=2026-04-30&checkoutDate=2026-05-01"
    "&cityCode=AR04567&cityName=%E4%B8%8A%E6%B5%B7"
    "&queryWords=&extend=1,2,0,0,0,0"
)
tid = new_tab(url)
wait_for_load(timeout=20)
time.sleep(8)

hotels = js(r"""
  return Array.from(document.querySelectorAll("a[href*=HotelDetail]"))
    .filter(a => (a.innerText||"").trim() === "查看详情")
    .slice(0, 30)
    .map(detailA => {
      const id = (detailA.href.match(/hotelId=([A-Z]+\d+)/i) || [])[1];
      let card = detailA.parentElement;
      while (card && !card.querySelector(`a[href*='${id}']:not(:where([href*='%E6%9F%A5%E7%9C%8B%E8%AF%A6%E6%83%85']))`)) {
        card = card.parentElement;
        if (!card) break;
      }
      if (!card) return null;
      const text = (card.innerText || "").replace(/\s+/g, " ");
      return {
        hotelId: id,
        name:  text.match(/(?:\d+\s+)?([^\s]{2,40}?(?:酒店|宾馆|大酒店|饭店))/)?.[1] || null,
        score: text.match(/(\d\.\d)\s*\/\s*5/)?.[1] || null,
        grade: (text.match(/(豪华型|高档型|舒适型|经济型)/) || [])[1] || null,
        distance_km: parseFloat((text.match(/距离市中心\s*([\d.]+)/) || [])[1] || "0"),
        price_from: parseInt((text.match(/(?:¥|￥)\s*(\d+)\s*起/) || [])[1] || "0") || null,
      };
    })
    .filter(x => x && x.hotelId && x.name);
""")
print(json.dumps(hotels, indent=2, ensure_ascii=False))
cdp("Target.closeTarget", targetId=tid)
```
