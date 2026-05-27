# 贝壳找房 (ke.com) — Data Extraction

Field-tested against ke.com on 2026-04-28.
No authentication required for listing search.
All listing page requests work via `http_get` without a browser.

---

## TL;DR

贝壳找房 (`{city}.ke.com`) returns full HTML for the **first page** of any
search via `http_get`. Subsequent pages and individual property detail pages
are protected by CAPTCHA and require a browser session.

**What you can do with `http_get` (no browser):**
- Scrape the first 30 listings of any city-wide search (二手房 or 租房)
- Extract: title, URL, price, floor/year/layout/area/orientation, community
  name, tags (满五年/地铁 etc.), follower count
- Switch cities by changing the subdomain (`bj`, `sh`, `gz`, `sz`, etc.)

**What requires a browser (`goto` + `js`):**
- District/neighborhood filtering (e.g. `/ershoufang/chaoyangqu/`) — redirects
  to login page via `http_get`
- Page 2 and beyond (302 redirect → CAPTCHA on direct `http_get`)
- Individual property detail pages (CAPTCHA page returned)

---

## Approach 1: 二手房 Listing Search

`GET https://{city}.ke.com/ershoufang/`

Returns the first 30 listings for a city. District/neighborhood filtering
requires a logged-in browser session — `http_get` on `/ershoufang/{district}/`
redirects to the login page.

```python
from helpers import http_get
import re

# City subdomain codes (confirmed working):
# bj=北京, sh=上海, gz=广州, sz=深圳, cd=成都, wh=武汉, hz=杭州, nj=南京

def ke_search_ershoufang(city="bj"):
    """Search 二手房 (resale housing) listings on ke.com.

    Args:
        city: City subdomain, e.g. 'bj' (北京), 'sh' (上海), 'gz' (广州),
              'sz' (深圳), 'cd' (成都), 'hz' (杭州), 'wh' (武汉), 'nj' (南京)

    Returns up to 30 listings from the first page. Each listing contains:
    title, url, total_price, unit_price, info (floor/year/layout/area/orientation),
    community, tags, followers.

    Note: district/neighborhood filtering requires a logged-in browser session.
    """
    url = f"https://{city}.ke.com/ershoufang/"
    html = http_get(url)

    ul = re.search(r'<ul class="sellListContent"[^>]*>(.*?)</ul>', html, re.DOTALL)
    if not ul:
        return []

    listings = []
    for li in re.findall(r'<li class="clear">(.*?)</li>', ul.group(1), re.DOTALL):
        title   = re.search(r'title="([^"]+)"', li)
        href    = re.search(r'href="(https://[a-z]+\.ke\.com/ershoufang/\d+\.html)"', li)
        total   = re.search(r'class="totalPrice[^"]*"[^>]*>.*?<span[^>]*>\s*(\d+)\s*</span>.*?<i>万</i>', li, re.DOTALL)
        unit    = re.search(r'<span>(\d[\d,]+元/平)</span>', li)
        info_m  = re.search(r'class="houseInfo"[^>]*>(.*?)</div>', li, re.DOTALL)
        pos_m   = re.search(r'class="positionInfo"[^>]*>(.*?)</div>', li, re.DOTALL)
        tags    = re.findall(r'class="(?:taxfree|five|subway|matching)[^"]*"[^>]*>\s*([^<]+?)\s*<', li)
        follow  = re.search(r'(\d+)人关注', li)

        info = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', info_m.group(1))).strip() if info_m else None
        pos  = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', pos_m.group(1))).strip() if pos_m else None

        if not title:
            continue
        listings.append({
            "title":       title.group(1),
            "url":         href.group(1) if href else None,
            "total_price": f"{total.group(1)}万" if total else None,   # e.g. "890万"
            "unit_price":  unit.group(1) if unit else None,            # e.g. "61,720元/平"
            "info":        info,        # e.g. "高楼层 (共24层) | 2002年 | 3室2厅 | 144.2平米 | 西南"
            "community":   pos,         # e.g. "盛和家园"
            "tags":        [t.strip() for t in tags],  # e.g. ["满五年", "地铁"]
            "followers":   int(follow.group(1)) if follow else None,
        })
    return listings

listings = ke_search_ershoufang(city="bj")
# [
#   {
#     "title":       "盛和家园 满五年唯一 不临街 观景房 电梯刷卡进入",
#     "url":         "https://bj.ke.com/ershoufang/101133688738.html",
#     "total_price": "890万",
#     "unit_price":  "61,720元/平",
#     "info":        "高楼层 (共24层) | 2002年 | 3室2厅 | 144.2平米 | 西南",
#     "community":   "盛和家园",
#     "tags":        ["满五年"],
#     "followers":   221,
#   },
#   ...  # up to 30 listings
# ]
```

---

## Approach 2: 租房 Listing Search

`GET https://{city}.ke.com/zufang/`

```python
from helpers import http_get
import re

def ke_search_zufang(city="bj"):
    """Search 租房 (rental) listings on ke.com.

    Args:
        city: City subdomain, e.g. 'bj', 'sh', 'gz'

    Returns up to 30 rental listings from the first page.
    Note: ke.com issues a 302 on first hit; http_get follows the redirect
    automatically and the final response contains full listing HTML.
    """
    html = http_get(f"https://{city}.ke.com/zufang/")

    listings = []
    # Rental pages use a different HTML structure from resale pages
    blocks = re.findall(
        r'href="(/zufang/[A-Z]{2}[\w]+\.html)"[^>]*title="([^"]+)"',
        html
    )
    prices = re.findall(r'(\d+)</em>', html)
    descs  = re.findall(
        r'class="content__list--item--des"[^>]*>(.*?)</p>',
        html, re.DOTALL
    )

    for i, (path_url, title) in enumerate(blocks):
        desc_raw = descs[i] if i < len(descs) else ""
        desc_clean = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '|', desc_raw)).strip()
        parts = [p for p in (x.strip() for x in desc_clean.split('|')) if p and p != '/']

        listings.append({
            "title":       title,
            "url":         f"https://{city}.ke.com{path_url}",
            "price":       f"{prices[i]}元/月" if i < len(prices) else None,
            "district":    parts[0] if len(parts) > 0 else None,   # e.g. "海淀区"
            "area_name":   parts[1] if len(parts) > 1 else None,   # e.g. "马甸"
            "community":   parts[2] if len(parts) > 2 else None,   # e.g. "月季园"
            "desc":        desc_clean,
        })
    return listings

rentals = ke_search_zufang(city="bj")
# [
#   {
#     "title":     "整租·月季园 2室1厅 南/北",
#     "url":       "https://bj.ke.com/zufang/BJ2143777429737439232.html",
#     "price":     "6300元/月",
#     "district":  "海淀区",
#     "area_name": "马甸",
#     "community": "月季园",
#     "desc":      "海淀区 | 马甸 | 月季园 / 57.41㎡ / 南 北 / 2室1厅1卫 / 中楼层 （21层）",
#   },
#   ...
# ]
```

---

## Approach 3: Property Detail Page (Browser Required)

Individual property pages (`/ershoufang/{id}.html`, `/zufang/{id}.html`) return
a CAPTCHA page via `http_get`. Use the browser to load them.

```python
from helpers import goto, wait_for_load, wait, js

def ke_get_detail(property_url):
    """Fetch full property details from a ke.com listing page.

    Requires browser. property_url comes from ke_search_ershoufang() or
    ke_search_zufang(). CSS selectors verified against ke.com detail pages.
    """
    goto(property_url)
    wait_for_load()
    wait(2)

    return js("""
      ({
        title:       document.querySelector('.mainInfo')?.innerText?.trim()
               ||    document.querySelector('h1.title')?.innerText?.trim(),
        total_price: document.querySelector('.total')?.innerText?.trim(),
        unit_price:  document.querySelector('.unitPriceValue')?.innerText?.trim(),
        area:        document.querySelector('.area .mainInfo')?.innerText?.trim(),
        layout:      document.querySelector('.room .mainInfo')?.innerText?.trim(),
        floor:       document.querySelector('.floor .mainInfo')?.innerText?.trim(),
        orientation: document.querySelector('.toward .mainInfo')?.innerText?.trim(),
        decoration:  document.querySelector('.decoration .mainInfo')?.innerText?.trim(),
        community:   document.querySelector('.communityName .info')?.innerText?.trim(),
        district:    document.querySelector('.areaName .info')?.innerText?.trim(),
        description: document.querySelector('.seller-desc')?.innerText?.trim(),
        tags:        Array.from(document.querySelectorAll('.tag-list .content'))
                          .map(e => e.innerText.trim()).filter(Boolean),
      })
    """)
```

---

## URL Reference

### City Subdomains

| 城市 | 子域名 | 二手房 URL |
|------|--------|-----------|
| 北京 | `bj`   | `https://bj.ke.com/ershoufang/` |
| 上海 | `sh`   | `https://sh.ke.com/ershoufang/` |
| 广州 | `gz`   | `https://gz.ke.com/ershoufang/` |
| 深圳 | `sz`   | `https://sz.ke.com/ershoufang/` |
| 成都 | `cd`   | `https://cd.ke.com/ershoufang/` |
| 杭州 | `hz`   | `https://hz.ke.com/ershoufang/` |
| 武汉 | `wh`   | `https://wh.ke.com/ershoufang/` |
| 南京 | `nj`   | `https://nj.ke.com/ershoufang/` |

### URL Pattern

```
# 二手房 (resale) — city-wide first page only via http_get
https://{city}.ke.com/ershoufang/

# 租房 (rental) — city-wide first page only via http_get
https://{city}.ke.com/zufang/

# 新房 (new development)
https://{city}.ke.com/loupan/

# District filter (browser required — http_get redirects to login)
https://{city}.ke.com/ershoufang/{district}/

# Pagination (browser required — http_get returns CAPTCHA)
https://{city}.ke.com/ershoufang/pg{n}/
https://{city}.ke.com/ershoufang/{district}/pg{n}/

# Property detail (browser required — http_get returns CAPTCHA)
https://{city}.ke.com/ershoufang/{house_id}.html
https://{city}.ke.com/zufang/{house_id}.html
```

- **Common Beijing District Slugs** (browser required for district filtering):
`chaoyangqu` 朝阳 / `haidianqu` 海淀 / `xichengqu` 西城 / `dongchengqu` 东城 /
`fengtaiqu` 丰台 / `shijingshanqu` 石景山 / `changpingqu` 昌平 / `tongzhouqu` 通州

---

## Gotchas

- **Only city-wide first page is accessible via `http_get`** — district filters
  (e.g. `/ershoufang/chaoyangqu/`) redirect to a login page. Page 2+ redirects
  to a CAPTCHA page. Both require a logged-in browser session.
- **Detail pages always return CAPTCHA via `http_get`** — even for the very
  first request. Always use `goto()` + `js()` for detail pages.
- **Rental pages (`/zufang/`) follow a 302 on first hit** — `http_get` follows
  redirects automatically; the final response (141KB+) contains full listing HTML.
- **City subdomains differ from link-on-ke.com** — `bj.ke.com` works;
  `www.ke.com` redirects to the homepage without listing data.
- **`info` field format for 二手房**: pipe-separated string, e.g.
  `"高楼层 (共24层) | 2002年 | 3室2厅 | 144.2平米 | 西南"`. Split on `|` and
  strip whitespace to extract individual attributes.
- **Rental `desc` field format**: pipe/slash-separated, e.g.
  `"海淀区 | 马甸 | 月季园 / 57.41㎡ / 南 北 / 2室1厅1卫 / 中楼层"`.
- **30 listings per page** — confirmed for both 二手房 and 租房.
- **`total_price` is in 万元** (10,000 RMB), e.g. `"890万"` = 8,900,000 RMB.
  `unit_price` is 元/平方米, e.g. `"61,720元/平"`.
