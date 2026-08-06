# TikTok Creator Search Insights (CSI) — scraping

URL: `https://www.tiktok.com/csi?lang=en`

CSI surfaces what TikTok users are actively searching for, broken down by
category. Auth-walled — `/csi` redirects to `/login` for anonymous users.

## Auth

Requires a logged-in TikTok web session. There's no anonymous fallback. If
the harness lands on `/login`, ask the user to log in once in the attached
Chrome and retry — cookies persist across runs.

Detect the wall by reading `page_info()["url"]` after `wait_for_load()`:

```python
new_tab("https://www.tiktok.com/csi?lang=en")
wait_for_load()
if "/login" in page_info()["url"]:
    print("LOGIN_WALL")
    sys.exit(0)
```

## Regional targeting via `tt-target-idc` cookie

CSI is geo-personalized — the feed reflects the **logged-in account's
region**, not your IP and not anything in the filter UI (there is no
audience/country selector). Israeli accounts default to `tt-target-idc=alisg`
(Alibaba Singapore IDC) and surface heavily Israel-flavored results
("brunch tel aviv", "ethiopian tik toks"). Forcing a different IDC works:

1. Pull cookies via CDP — `cdp("Network.getCookies", urls=["https://www.tiktok.com/"])`.
2. Replace `tt-target-idc` and `store-idc` with the target IDC (e.g.
   `useast1a` for US-East, `useast2a` for US-East-2).
3. **Drop `tt-target-idc-sign`** — it's an HMAC bound to the original IDC
   value; TikTok will fall back to deriving routing from the unsigned
   `tt-target-idc` cookie alone.
4. POST the API endpoint via Python `requests` with the rewritten cookie
   header. No proxy needed — TikTok routes to the requested IDC and
   returns region-appropriate data.

Some personalization still bleeds through deeper offsets (~10–20% of
items can carry account-region keywords like a city name). The `tt-target-idc`
swap gets you most of the way; post-filter obvious geo markers in your
own code rather than trying to fight it further in the API call.

`language_filters: ["en"]` in the body is the sweet spot — `["en-US"]`
sometimes returns 0 items (over-restrictive), and an empty/missing
`language_filters` field surfaces 40%+ non-English-region noise.

## Page structure

Two top-level tabs: **Suggested** (default) and **Trending**. The
Suggested tab is what you want for "what's hot right now in category X".

Filter pills below the tabs: **All** (default), **Content gap**,
**Searches by followers**. "Content gap" surfaces queries with high
search demand and low video supply — the gold for trend hunters; the API
exposes this as `query_labels: ["content_gap"]`.

**Filters dropdown** (top-right button, text "Filters"): opens a panel
with **Category (multi-select)** and **Language** sections. As of
2026-05 the categories were:

- Fashion
- **Food**
- Gaming
- Tourism
- Science
- Sports

Apply via the red **Apply** button at the bottom of the dropdown.

## Private API

The query/filter UI POSTs to:

```
POST https://www.tiktok.com/api/search/inspired_query/recommended_queries
     ?WebIdLastTime=…&aid=1988&app_language=en&app_name=tiktok_web&… (device fingerprint params)
```

The query string is a device-fingerprint blob (`WebIdLastTime`,
`device_id`, `msToken`, `_signature`, etc.). **Do not try to reconstruct
it cold** — capture it from a real session via a `window.fetch` interceptor
installed before triggering the filter:

```js
window.__cap = [];
const orig = window.fetch;
window.fetch = async function(...args) {
  const url = typeof args[0] === "string" ? args[0] : args[0].url;
  const r = await orig.apply(this, args);
  if (url.indexOf("/api/search/inspired_query/recommended_queries") !== -1) {
    window.__cap.push({url, body: args[1] && args[1].body});
  }
  return r;
};
```

Then click Filters → Food → Apply. The captured `url + body` is your
template for paginated re-calls.

### Request body shape

```json
{
  "pagination": {
    "offset": 0,
    "limit": 21,
    "order_by": ["_score", "search_cnt"]
  },
  "tab": "all",
  "accept_inspiration_types": ["ecom", "phototext", "search"],
  "basic_info": {"session_refresh_index": 1},
  "inspiration_vertical_filter": {
    "language_filters": ["en"],
    "category_filters": ["Food"]
  },
  "cli_session_id": "<uuid>",
  "creator_source": "csi_webapp"
}
```

Override `pagination.offset` for paging. `limit` of 50 is accepted (UI
default is 21). Increment `basic_info.session_refresh_index` on each call
so the server treats them as a continuous session.

### Response shape

Top-level: `{inspiration_list, has_more, cursor, status_code, status_msg, banners, cost_tracker, extra, has_follower_searched, session_refresh_index}`.

`status_code: 0` is success. Anything else is a soft error — read
`status_msg` for the reason; do not treat as fatal HTTP error.

Per-item fields worth keeping (rest are debug/scoring noise):

| field                  | meaning                                                              |
| ---------------------- | -------------------------------------------------------------------- |
| `query_text`           | the trending search string (the trend)                               |
| `query_id_str`         | stable identifier                                                    |
| `popularity_v2`        | latest search-volume estimate (UI shows this as "Search popularity") |
| `popularity`           | rank-bucket integer (small — 2–90 range observed)                    |
| `trending_seq_v2`      | ~7-point time series of `popularity_v2`. Growth = `seq[-1]/seq[0]`   |
| `popularity_updated_at`| epoch seconds                                                        |
| `video_num`            | videos already published for this query                              |
| `query_labels`         | list — `["content_gap"]` flags low-supply / high-demand              |
| `textnet`              | hierarchical category path (layer1..layer4)                          |
| `inspiration_types`    | `["search"]` for searches, also `"ecom"` / `"phototext"`             |

### Pagination

`has_more: true` + `cursor: N` means there's more; pass `cursor` as the
next `offset`. The Food category has ~150–200 items total in en. Loop
until `has_more: false` or you get an empty `inspiration_list`.

### Awaiting the response from `js()`

`browser-harness`'s `js()` wraps your code in a **non-async** IIFE, so
top-level `await` inside the expression won't compile. Use a `.then()`
chain that resolves to a `JSON.stringify` payload — `js()` will await the
returned promise via `awaitPromise: true`:

```python
raw = js(
    "return fetch(url, {...}).then(r => r.json()).then(j => JSON.stringify(j));"
)
data = json.loads(raw)
```

For multi-page work, paginate from the Python side — one page per `js()`
call — instead of looping inside a single async block.

## Gotchas

- **Toggling Filters twice closes the dropdown.** If a previous run left
  the panel open, clicking the Filters button collapses it; the Food
  label click then misses. Detect dropdown state or always start from a
  fresh tab (`new_tab(...)`).
- **Cookies tied to TikTok profile, not Chrome profile.** Re-running
  after switching TikTok accounts in the same Chrome window will swap
  the session.
- **`popularity_v2` ≠ `video_num`.** Don't conflate them. A high-popularity,
  low-video term is a content-gap signal; that's exactly what `query_labels`
  flags.
- **Numbers in UI look bigger than the data.** The UI shows trends as
  `7.93M` etc. That's `popularity_v2` formatted, not a separate field.
- **Suggested vs Trending tab.** The default tab is `Suggested` and that
  matches the `tab: "all"` field in the body. The Trending tab uses a
  different `tab` value; not yet captured.
- **Query string is unstable.** The fingerprint params (`msToken`,
  `_signature`, etc.) rotate; cookies do too. Always re-capture the
  template each scrape rather than persisting a fixed URL.
