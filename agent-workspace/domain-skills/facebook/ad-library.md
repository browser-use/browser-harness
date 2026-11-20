# Facebook — Meta Ad Library (facebook.com/ads/library)

Public, works logged out. Lists every *active* commercial ad worldwide, inactive ads only for the EU/UK (past year), and political/issue ads (7 years). A US commercial ad vanishes from the public library the moment it stops running; drafts, in-review, and paused ads never appear. An ad shows up within ~24 h of its first impression.

## URL patterns

- Advertiser (page-scoped): `/ads/library/?active_status=active&ad_type=all&country=ALL&view_all_page_id=<PAGE_ID>&search_type=page&media_type=all`
- Keyword (matches ad text only, never the destination URL): `/ads/library/?active_status=active&ad_type=all&country=ALL&q=<terms>&search_type=keyword_unordered&media_type=all` (`keyword_exact_phrase` for quoted phrases)
- Single ad: `/ads/library/?id=<ad_archive_id>`
- `country=ALL` is valid. `active_status` is `active` | `inactive` | `all`. The site appends `is_targeted_country=false&sort_data[mode]=total_impressions&sort_data[direction]=desc` on its own.

## Two kinds of page ID (trap)

- The public page HTML (`facebook.com/<alias>/`, also reachable via same-origin `fetch('/<alias>/')` from an Ad Library tab) exposes a profile-style ID (`fb://page/1000634…`, `"userID"`). Feeding that to `view_all_page_id` returns the empty state even when the page runs ads.
- The library needs the classic page ID. Get it from the advertiser typeahead below; it returns `page_id`, `name`, `category`, `likes`, `ig_username`, `ig_followers`, `page_alias`, `verification`, `page_is_deleted`.
- Zero-likes pages with category "Product/service" and no alias are usually agency-created ad pages. Search product names as well as the company name; ads often run from a page named after the product.

## Read results as data, not DOM

**First page (30 ads) is embedded in the HTML** as a Relay preload. Grab it right after load:

```python
raw = js("""(()=>{const out=[];for(const s of document.querySelectorAll('script[type="application/json"]')){const t=s.textContent||'';if(t.includes('search_results_connection'))out.push(t);}return JSON.stringify(out);})()""")
```

Walk the JSON to the first dict holding `search_results_connection` (path is `…require[…]…__bbox.result.data.ad_library_main.search_results_connection`, but a recursive search is more robust). It has `count`, `edges[].node.collated_results[]`, and `page_info{end_cursor, has_next_page}`.

Each collated result:

- `ad_archive_id`, `page_id`, `page_name`, `is_active`, `start_date` / `end_date` (unix seconds), `publisher_platform[]`, `collation_count` (variants folded into one card), `ad_id`, `targeted_or_reached_countries`
- `snapshot`: `body.text` (primary text), `title` (headline), `link_description`, `caption` (display domain), `cta_text`, `cta_type`, `link_url`, `display_format` (`IMAGE` | `VIDEO` | `CAROUSEL` | `DCO` | `DPA`), `images[{original_image_url, resized_image_url}]`, `videos[{video_hd_url, video_sd_url, video_preview_image_url}]`, `cards[]` (carousel cards, same text/media fields), `extra_texts`, `extra_links`, `page_profile_uri`, `byline`, `page_like_count`
- `spend`, `impressions_with_index`, `reach_estimate` are null for US commercial ads; only EU-targeted and political ads carry them.

**Pagination** is GraphQL: scrolling to the bottom POSTs `/api/graphql/` with `fb_api_req_friendly_name=AdLibrarySearchPaginationQuery`. Capture the bodies instead of scraping cards:

```python
cdp("Network.enable"); drain_events()
pending, bodies, idle = {}, [], 0
while idle < 3:
    js("window.scrollTo(0, document.documentElement.scrollHeight)"); wait(2.5)
    new = 0
    for e in drain_events():
        if e["method"] == "Network.requestWillBeSent":
            r = e["params"]["request"]
            if "graphql" in r["url"] and "AdLibrarySearchPaginationQuery" in r.get("postData", ""):
                pending[e["params"]["requestId"]] = True; new += 1
    for rid in list(pending):
        try: bodies.append(cdp("Network.getResponseBody", requestId=rid)["body"]); pending.pop(rid); new += 1
        except Exception: pass
    idle = 0 if new else idle + 1
```

Bodies have the same `data.ad_library_main.search_results_connection` shape. Dedupe on `ad_archive_id`.

**Advertiser typeahead** (the search box's page lookup) is callable from the page context, logged out:

```python
lsd = js("""(()=>{for(const s of document.querySelectorAll('script')){const m=(s.textContent||'').match(/\\["LSD",\\[\\],\\{"token":"([^"]+)"/);if(m)return m[1];}return null;})()""")
body = urllib.parse.urlencode({"lsd": lsd, "jazoest": "2"+str(sum(map(ord, lsd))), "__a": "1", "__user": "0", "__comet_req": "1",
    "fb_api_caller_class": "RelayModern", "fb_api_req_friendly_name": "useAdLibraryTypeaheadSuggestionDataSourceQuery",
    "variables": json.dumps({"queryString": "acme", "isMobile": False, "country": "ALL", "adType": "ALL"}),
    "server_timestamps": "true", "doc_id": "9755915494515334"})
r = js("fetch('/api/graphql/',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded','X-FB-LSD':"+json.dumps(lsd)+"},body:"+json.dumps(body)+",credentials:'include'}).then(r=>r.text())")
pages = json.loads(r)["data"]["ad_library_main"]["typeahead_suggestions"]["page_results"]
```

`doc_id` above was observed 2026-09-25 and rotates; if the call errors, type in the search box with `Network.enable` on and read the new `doc_id` from the request's `postData`. The old REST endpoint `/ads/library/async/search_typeahead/` is dead ("Not Found").

## Selectors and UI

- Header search box on results pages: `input[placeholder="Search by keyword or advertiser"]`. The landing page instead shows a disabled "Choose an ad category" box until a category is picked, and the country picker owns `input[placeholder="Search for country"]`, so never take the first `input`.
- Typeahead rows read `Name / @alias · N follow this · Category / @ig · N followers`.
- Page-scoped empty state: "No ads match your search criteria" plus "This advertiser isn't running ads in the selected country and ad category at this time." That is a true zero, not a loading state.
- Result count text near the top of the list: `~24,000 results`. Cards carry the text `Library ID: <id>`, handy for a regex sanity check against the payload.

## Waits

- After `goto`: `wait_for_load()` plus ~5 s. The embedded payload is present at load; the cards render after hydration.
- ~2.5 s after each scroll before draining network events, or the pagination request is missed.

## Traps

- `curl` gets a login-wall shell (a few hundred bytes); a browser session is required. Headless Chrome works logged out once the UA is overridden (`Emulation.setUserAgentOverride` to drop `HeadlessChrome`).
- Keyword search never matches the destination URL or domain, so dark-page ads that avoid the brand name cannot be found by domain; sweep the product's themes and filter results on `link_url`, `caption`, and `page_name` instead.
- `keyword_unordered` tokenizes compound words, so a compound brand name pulls in unrelated advertisers that use its parts. Verify hits by `page_id` or `link_url`.
- The official Ad Library API (`graph.facebook.com/<v>/ads_archive`) returns only political and issue ads for US targeting; `ad_type=ALL` is EU-only. Use the site payloads above for commercial ads.
