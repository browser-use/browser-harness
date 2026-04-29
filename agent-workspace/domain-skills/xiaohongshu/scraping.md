# Xiaohongshu — Search and Sort

URL patterns:
- Home / discovery: `https://www.xiaohongshu.com/explore`
- Search results: `https://www.xiaohongshu.com/search_result?keyword=...`

## Search flow

- Prefer direct navigation to the desktop search results page over automating the home-page search box.
- Reliable primary path: `https://www.xiaohongshu.com/search_result?keyword=<url-encoded keyword>&source=web_explore_feed`
- This route loads the normal desktop results page and avoids home-page input flakiness.
- The search results page can also appear with variants such as `type=51` or other `source` values after in-app navigation; do not treat those as suspicious if the rendered results are correct.
- The top search box on `explore` can work, and searching from the home page has transitioned to `search_result` without a login wall in some sessions.
- The page exposes duplicate search inputs in the DOM with the same placeholder `搜索小红书`.
- The home-page search input can behave like a tightly controlled app field: direct DOM value assignment may be cleared immediately, and harness `type_text()` may fail to populate it even when the input is focused.
- Treat the home-page input as best-effort only. Use it when a human-like interactive flow matters, but for automation default to constructing the `search_result` URL directly.

## Sort behavior

- On the current desktop results layout, `最新` is **not** a top-level tab beside `综合`.
- Open the `筛选` control in the upper-right of the results header to access sort options.
- Inside `筛选`, `排序依据` contains:
  - `综合`
  - `最新`
  - `最多点赞`
  - `最多评论`
  - `最多收藏`
- The `排序依据` row can render duplicate DOM nodes for the same pill text, including non-interactive clones.
- Raw global text search for `最新` can hit the wrong node first. Scope to the `排序依据` section and then choose the visible interactive `.tags` node.
- Prefer semantic filtering such as `aria-hidden != "true"` or section-scoped visible `.tags` selection over style-specific checks.
- When `最新` is active, the `筛选` trigger changes to `已筛选`.
- The rendered feed and the `已筛选` / active-pill UI are more reliable than `window.__INITIAL_STATE__.search.searchContext.sort` for confirming latest sort.

## Stable cues

- Search channel tabs near the top: `全部`, `图文`, `视频`, `用户`
- Sort panel labels: `筛选`, `排序依据`, `最新`
- Filter sections also visible in the panel: `笔记类型`, `发布时间`, `搜索范围`, `位置距离`

## Interaction notes

- DOM `.click()` opened the `筛选` panel reliably.
- DOM `.click()` on the visible `最新` pill inside the open `排序依据` section reliably activated latest sort.
- The reliable DOM pattern was:
  - find the `排序依据` section / `.filters` block
  - search within that block for `.tags`
  - choose the one whose text is `最新` and which is the visible interactive node
  - call `.click()` on that visible node
- Example selector strategy:
  - find `.filters` whose first label is `排序依据`
  - inside it, pick `.tags` where `textContent.trim() === "最新"` and `el.getAttribute("aria-hidden") !== "true"`
- `getClientRects().length > 0` alone may be insufficient to distinguish the working node from a duplicate.
- A broad `document.querySelectorAll("*")` text match for `最新` is not reliable on this page because it may click the hidden duplicate instead of the visible control.
- Coordinate click on the visible `最新` pill also worked and remains a valid fallback if DOM targeting gets confused by future UI changes.
- After selecting `最新`, the grid briefly showed skeleton placeholders before the refreshed results appeared.
- The search page stores the currently rendered note cards in `window.__INITIAL_STATE__.search.feeds._value` as an array of feed entries. For ordinary note cards, the useful fields were:
  - `id`
  - `xsecToken`
  - `noteCard.displayTitle`
  - `noteCard.user.nickname`
- The feed array can contain non-note inserts such as hot-query modules. Filter for entries with `noteCard` before treating an item as a note result.

## Post opening

- Do **not** assume a raw results link like `https://www.xiaohongshu.com/explore/<id>` is directly openable.
- Opening that raw `/explore/<id>` URL in a fresh tab can redirect to the web `404` / app-only gate even when the same post is openable from search results.
- To open a post from search results, click the visible card image / card in-page first.
- That click navigation can land on a tokenized URL like `https://www.xiaohongshu.com/explore/<id>?xsec_token=...&xsec_source=pc_search`, which is a more reliable note URL than the raw `/explore/<id>` form.
- Once the tokenized URL is obtained from the click flow, it can be revisited in-session for extraction.
- If the search results state is already loaded, you can reconstruct the tokenized note URL directly from a feed item without re-clicking:
  - `https://www.xiaohongshu.com/explore/<id>?xsec_token=<xsecToken>&xsec_source=pc_search`

## Post extraction

- On tokenized post pages opened via `pc_search`, `document.body.innerText` can be a useful first-pass extraction source because it often includes the rendered note text, hashtags, timestamp, engagement counts, and visible comments.
- Verify that the note content actually rendered before trusting `document.body.innerText`, because the page can also include substantial navigation, footer, and comment noise.
- Prefer `document.body.innerText` as a fallback or initial probe before writing fragile per-element selectors for post content.

## Gotchas

- Do not assume `Enter` alone finished the workflow until you verify the URL changed to `search_result` or the result grid appeared.
- Do not assume the visible `综合` tab controls all sorting; on this layout, time ordering is hidden inside `筛选`.
- Do not assume the first DOM node whose text is `最新` is the clickable one; this panel duplicates pills and the hidden clone can absorb naive text-based targeting without changing state.
- Do not assume a successfully opened post can be reproduced by stripping query params; preserve the `xsec_token` when reopening results-derived post URLs.
