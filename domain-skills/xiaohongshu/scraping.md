# Xiaohongshu (小红书) — Search & Video Extraction

Xiaohongshu (`xiaohongshu.com`, also known as RED / RedNote) is a Vue 3 SPA. The DOM is mostly thin shells around a Pinia store hung off `window.__INITIAL_STATE__`, so DOM scraping alone misses the data you actually want — the store has it. Video posts in particular cannot be downloaded from the DOM: the `<video>` element's `src` is a `blob:` Media Source Extensions URL.

Use the browser when you're logged in or want recommendations from a real session. The store path below works whether or not you're authenticated, but search/feed results are richer when signed in.

## URL patterns

- Explore feed (logged-in landing): `https://www.xiaohongshu.com/explore`
- Search results: `https://www.xiaohongshu.com/search_result?keyword=<urlencoded>&type=<n>`
  - `type` filter — omit for "All", `type=51` for video posts only. Other tabs (`图文` image-text, `用户` users) are togglable in-page; the URL parameter shape mirrors the tab.
- Search result hrefs say `/search_result/<noteId>?xsec_token=...&xsec_source=` but clicking navigates to `/explore/<noteId>?xsec_token=...&xsec_source=pc_search&source=web_explore_feed`. **`/explore/<id>` is the canonical post URL.**
- The `xsec_token` is a per-result anti-scraping token issued by the search response. You can't reuse it across queries; grab it fresh from each `a.cover` href.

**Search results are non-deterministic.** Reloading the page reshuffles the order — capture all hrefs you need before navigating away, because the order won't match on the way back.

## Path 1: Browser DOM + store extraction (the reliable one)

Search → collect hrefs → open each post → read `__INITIAL_STATE__.note.noteDetailMap[<id>].note.video.media.stream.h264[0].masterUrl`.

```bash
browser-harness <<'PY'
import json, time
from urllib.parse import quote

# 1. Search. URL-encode the full keyword — XHS queries commonly contain
#    Chinese characters, spaces, and ampersands, none of which a naive
#    space-only replace handles.
keyword = "bloc1 攀岩"
goto_url(f"https://www.xiaohongshu.com/search_result?keyword={quote(keyword)}&type=51")
wait_for_load(timeout=20)
for _ in range(15):
    if js('document.querySelectorAll("section.note-item").length'):
        break
    time.sleep(0.5)

# 2. Collect hrefs. Skip the "related searches" widget (no a.cover).
hrefs = json.loads(js('''
var arr = [];
document.querySelectorAll("section.note-item").forEach(function(el){
    var a = el.querySelector("a.cover");
    if (a) arr.push(a.getAttribute("href"));
});
return JSON.stringify(arr);
'''))

# 3. For each post: navigate, wait for the note id to populate in the store,
#    then pull the masterUrl + title.
for path in hrefs[:3]:
    goto_url("https://www.xiaohongshu.com" + path.replace("/search_result/", "/explore/"))
    wait_for_load(timeout=20)
    note_id = path.split("/")[-1].split("?")[0]
    for _ in range(40):
        ready = js('(function(id){var m=window.__INITIAL_STATE__&&window.__INITIAL_STATE__.note&&window.__INITIAL_STATE__.note.noteDetailMap;'
                   'if(!m) return false;'
                   'var e=m[id]; return !!(e&&e.note&&e.note.video&&e.note.video.media&&e.note.video.media.stream&&e.note.video.media.stream.h264&&e.note.video.media.stream.h264[0]);})("'+note_id+'")')
        if ready: break
        time.sleep(0.3)
    info = js('(function(id){try{var nt=window.__INITIAL_STATE__.note.noteDetailMap[id].note;'
              'return JSON.stringify({id:id,title:(nt.title||(nt.desc?nt.desc.split("\\n")[0].slice(0,40):id)),'
              'url:nt.video.media.stream.h264[0].masterUrl})}catch(e){return JSON.stringify({id:id,error:e.message})}})("'+note_id+'")')
    print(info)
PY
```

Once you have a `masterUrl`, plain `curl` with a Referer header is enough to download — the CDN does not require cookies:

```bash
curl -sSL -H "Referer: https://www.xiaohongshu.com/" -o video.mp4 "<masterUrl>"
```

### Key store paths

| Target               | Path                                                                                  | Notes                                                                                                |
| -------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Note detail map      | `window.__INITIAL_STATE__.note.noteDetailMap`                                         | Map of `{ <noteId>: { note: {...}, comments: {...} } }`. **Has zombie keys `""` and `"undefined"`** — filter to the hex-id keys. |
| Note core fields     | `noteDetailMap[<id>].note`                                                            | `.title`, `.desc`, `.user`, `.video`, `.imageList`, `.tagList`.                                       |
| Video master URL     | `noteDetailMap[<id>].note.video.media.stream.h264[0].masterUrl`                       | Signed MP4 URL; valid ~24h. **Use h264 for compatibility, h265 (`stream.h265[0]`) for smaller size.** |
| Image post URLs      | `noteDetailMap[<id>].note.imageList[i].urlDefault`                                    | Photo posts only. `urlPre` is the low-res preview.                                                    |
| User                 | `noteDetailMap[<id>].note.user`                                                       | `.userId`, `.nickname`, `.avatar`.                                                                    |
| Comments             | `noteDetailMap[<id>].comments.list`                                                   | Top-level only; replies live in `.subComments`.                                                       |

### Key DOM selectors

| Target            | Selector                              | Notes                                                                                            |
| ----------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------ |
| Search result tile | `section.note-item`                   | Repeats per result. Includes a "related searches" tile with **no `a.cover`** — filter on that.    |
| Post link        | `section.note-item a.cover`           | Path is `/search_result/<id>?xsec_token=…`; rewrite to `/explore/<id>?…` for the canonical URL. |
| Video player     | `video`                               | `src` is `blob:` (MSE) — **useless for download**. Read the store instead.                       |

## Path 2: Pure HTTP (limited)

Anonymous `http_get` of `xiaohongshu.com/explore/<id>` will return the HTML shell with `__INITIAL_STATE__` inlined as a `<script>` tag, but XHS heavily fingerprints non-browser clients and most requests get a placeholder/empty state (no `note.noteDetailMap`). Stick with the browser path unless you're already inside an authenticated session and want a faster batch — even then you usually need at least the `xsec_token` from the originating search query.

## Vue 3 reactivity trap

`__INITIAL_STATE__` is a live Pinia store, not a plain JSON snapshot. Three things break naive readers:

- **`JSON.stringify(state.note)` throws** `Converting circular structure to JSON ... starting at object with constructor 'em' ... property 'computed' closes the circle` — Vue's reactive proxies set up cycles between `dep` and `computed`. Walk fields manually instead of stringifying branches.
- **Skip keys starting with `__v_`, plus `dep`, `_dep`, `deps`, `computed`.** Those are Vue internals.
- **`noteDetailMap` keys include `""` and `"undefined"`.** The store eagerly initializes empty entries before the real one loads. Filter to keys that look like the 24-char hex note id (`/^[0-9a-f]{24}$/`) or just `k && k !== "undefined"`.

When you only need primitive values, return them one at a time:

```javascript
js('window.__INITIAL_STATE__.note.noteDetailMap["<id>"].note.video.media.stream.h264[0].masterUrl')
```

## Signed CDN URLs

`masterUrl` is shaped like `http://sns-video-ak.xhscdn.com/stream/.../<file>.mp4?sign=<hex>&t=<hex>`. The `t=` parameter is a hex-encoded Unix timestamp (the expiry, ~24h after issue). If a download 404s a day later, **re-fetch the post page to get a fresh URL** rather than trying to re-sign — the signing scheme is server-side.

The CDN does not require cookies. The minimum headers for `curl` to succeed are no headers at all, but `Referer: https://www.xiaohongshu.com/` is courteous and avoids any future tightening.

## Gotchas

- **`<video>` `src` is `blob:`** — MSE. The actual streamable URL is in the store, not the DOM.
- **Search results reshuffle on every page load** — collect all hrefs you need before navigating away, because the order won't be the same when you come back.
- **Search-page hrefs use `/search_result/<id>` but the canonical post URL is `/explore/<id>`.** Both load the same post; rewrite to `/explore/` for clarity and to match the `xsec_source=pc_search` flow.
- **`xsec_token` is per-result and per-query.** You can't share tokens across searches.
- **Skeleton placeholders linger.** `wait_for_load()` returns long before `noteDetailMap` is populated — poll the store until your note id is present.
- **`nt.title` is empty for many posts** — fall back to `nt.desc.split("\n")[0]` for a usable filename.
- **`type=51` is the video filter.** The `视频` tab in the UI flips to that. Other type codes exist for `图文` and `用户` but the URL form is the same.
- **Image posts have a different shape** — `nt.video` is null; use `nt.imageList[i].urlDefault` instead.
