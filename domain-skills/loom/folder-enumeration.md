# Loom — Library Folder Enumeration

Field-tested against loom.com on 2026-04-26.
For private workspace library folders that require an authenticated session.

## TL;DR — When to use this skill vs yt-dlp

Loom has **two** kinds of folder URLs and they need different tools:

| URL pattern | Visibility | Tool |
|---|---|---|
| `loom.com/share/folder/<32-hex>` | Public-shared (anyone with link) | **yt-dlp** — `LoomFolderIE` already supports this. Skip browser-harness entirely. |
| `loom.com/looms/videos/<slug>-<32-hex>` | Private workspace library | **browser-harness** (this skill). yt-dlp doesn't support library folders, and the underlying `/v1/folders/<id>` endpoint returns `Forbidden` even with cookies. |

The library variant is what every Loom user sees in their own workspace sidebar. There is no public read API for it; the only programmatic route is the authenticated session in the user's browser. That's why this skill exists.

For the **download** itself (after enumeration), `yt-dlp --cookies-from-browser chrome -f http-transcoded` is the fast path — a single HTTP MP4 stream rather than the ~125 HLS fragments the default selection grabs. Substantially faster for bulk runs. See "Pipe to yt-dlp" at the bottom.

---

## 1. Attach to the user's open Loom tab

Always attach to the existing tab. **Do not** call `new_tab()` for `loom.com` — it spawns duplicate tabs in the user's Chrome profile (observed: four duplicate Loom tabs accumulated in one debugging session). The user has to clean those up manually afterwards.

```python
import time
tabs = cdp("Target.getTargets")
loom_tid = next(
    (t["targetId"] for t in tabs.get("targetInfos", [])
     if "loom.com/looms/videos/" in t.get("url", "")),
    None,
)
if not loom_tid:
    raise SystemExit("User must open the Loom library folder in Chrome first.")
switch_tab(loom_tid)
time.sleep(0.3)
```

If multiple Loom tabs of the same folder are already open (common after a few sessions), pick the freshest one and close the others with `cdp("Target.closeTarget", targetId=tid)` before scrolling — keeps the user's Chrome tidy and avoids future ambiguity in `Target.getTargets`.

---

## 2. Selector — `[data-videoid]`

Each video card is an `<article data-videoid="<32-hex>">`. Inside, the first text line is the title (with two ARIA prefix/suffix strings to strip):

```python
items = js("""
Array.from(document.querySelectorAll("[data-videoid]")).map(e => [
  e.getAttribute("data-videoid"),
  (e.innerText || "")
    .split("\\n")[0]
    .replace(/^Add /, "")
    .replace(/ for bulk actions$/, "")
    .trim()
])
""")
# items: [[id, title], ...] for the cards currently rendered
```

The visible `<a href>` on the card points at `loom.com/share/<id>`, so once you have the ID you can hand it straight to yt-dlp.

---

## 3. The virtualization quirk — `scrollIntoView`, NOT `scrollTop`

Loom's library uses an aggressive virtual scroller that:
- Renders ~30–60 cards at a time
- **Caps `document.scrollingElement.scrollTop` to a value far smaller than `scrollHeight`** as long as the bottom of the list isn't the bottom of the viewport
- Unmounts cards above the viewport once you scroll past them

Setting `scrollTop = N` directly silently fails (the value snaps back) once you hit the cap. `window.scrollTo` behaves the same way. Mouse-wheel and PageDown via CDP weren't fully tested in our run, but given they end up at the same `scrollingElement` they're unlikely to escape the cap either.

The reliable mechanic is to take the **last currently rendered card** and scroll it into view at the bottom — the virtual scroller responds by mounting the next batch below it:

```python
import time
ids_seen = {}
prev = -1; stuck = 0
js("document.scrollingElement.scrollTop = 0")
time.sleep(0.8)

for i in range(80):
    items = js("""
    Array.from(document.querySelectorAll("[data-videoid]")).map(e => [
      e.getAttribute("data-videoid"),
      (e.innerText||"").split("\\n")[0]
        .replace(/^Add /, "").replace(/ for bulk actions$/, "").trim()
    ])
    """)
    for id_, title in (items or []):
        ids_seen[id_] = title

    js("""
    (() => {
      const a = document.querySelectorAll("[data-videoid]");
      if (a.length) a[a.length - 1].scrollIntoView({block: "end"});
    })()
    """)
    time.sleep(0.6)

    if len(ids_seen) == prev:
        stuck += 1
    else:
        stuck = 0
    prev = len(ids_seen)
    if stuck > 12:
        break

print(f"collected {len(ids_seen)} videos")
```

Empirical numbers from one test run on a 78-video folder:
- `scrollTop`-based scrolling: stuck at 60 of 78 (cap hit at `scrollTop ≈ 2967` while `scrollHeight` was `4529`).
- `scrollIntoView`-based scrolling: 78 of 78 in a single pass; `scrollHeight` grew to `5884` as the virtualizer extended.

The `stuck` counter (12 idle iterations) is the right signal for "done" — `paging.total` style metadata is not exposed in the DOM, and the visible "78 videos" header at the top is a separate widget that does not refresh after scroll.

---

## 4. Endpoints that look promising but don't help

For completeness — a few dead ends so the next agent doesn't waste time:

- `https://www.loom.com/v1/folders/<id>?limit=10000` — works for `/share/folder/...` IDs (this is what `LoomFolderIE` uses), returns `Forbidden` for library folder IDs even with the user's cookies.
- `https://www.loom.com/graphql` — fires hundreds of times during page load. A folder-listing operation almost certainly lives in there, but the `query` strings come from the bundled React app and would have to be reverse-engineered from the JS bundle. Likely brittle long-term. Reading the rendered DOM is more durable.
- `performance.getEntriesByType("resource")` — useful for proving these endpoints exist, but only returns URLs/timings, not request bodies.

---

## 5. Pipe to yt-dlp for the actual download

The DOM scrape gives you IDs. Hand them to yt-dlp for the bytes — don't try to grab MP4 URLs yourself. yt-dlp already knows the GraphQL flow for single videos (`LoomIE`), handles CDN signature URLs, and merges audio + video tracks.

```bash
# One-time: cache cookies from Chrome (saves ~2s/video on bulk runs)
yt-dlp --cookies-from-browser chrome --cookies /tmp/loom_cookies.txt \
  --skip-download --no-warnings \
  "https://www.loom.com/share/<any-known-id>" >/dev/null

# Bulk: 16 videos in parallel, single-stream 1080p MP4 (~10× faster than HLS default)
download_one() {
  yt-dlp --cookies /tmp/loom_cookies.txt \
    -f http-transcoded \
    -o "%(title)s.%(ext)s" \
    --no-progress --no-warnings --no-mtime --no-overwrites \
    "https://www.loom.com/share/$1"
}
export -f download_one

cat /tmp/loom_ids.json \
  | python3 -c "import sys, json; [print(k) for k in json.load(sys.stdin)]" \
  | xargs -P 16 -I {} bash -c 'download_one "$@"' _ {}
```

Format notes:
- `-f http-transcoded` is a **single HTTP MP4 stream at 1920×1080**. The default selection picks `hls-raw-3200` + `hls-raw-audio-audio`, which is also 1080p but split into ~125 fragments per video. For bulk runs the single-stream form is dramatically faster (one TCP connection per video at full bandwidth, no per-fragment overhead). For a single video the difference is negligible.
- Loom does not currently expose anything above 1080p for transcoded videos.
- `--no-overwrites` makes the bulk job idempotent: re-running picks up only what's missing.

---

## Gotchas

- **Two different folder URL families.** `loom.com/share/folder/<id>` (public) is yt-dlp territory. `loom.com/looms/videos/<slug>-<id>` (library) needs this skill. Don't mix them up — it's the difference between a one-line yt-dlp call and a DOM scrape.
- **`scrollTop` is silently capped.** Always use `scrollIntoView({block: "end"})` on the last rendered card. Setting `scrollTop` plateaus before the bottom of the list and gives you a partial enumeration that *looks* complete because the loop hits its idle threshold.
- **Never `new_tab()` for Loom.** Attach to the user's existing tab via `Target.getTargets`. New tabs accumulate in the user's Chrome profile across sessions, and the user has to clean them up.
- **Idle-counter is the reliable end-of-list signal.** The "N videos" count in the page header may or may not be in sync with what's actually rendered (we didn't fully verify either direction). Use `len(ids_seen)` going N iterations without growing as the stop condition rather than reading the header.
- **Title strings are wrapped in ARIA noise.** The first line of `innerText` is `Add <title> for bulk actions`. Strip both prefix and suffix before using as a filename.
- **One MP4 per ID via `loom.com/share/<id>`.** Library-internal share links are valid and yt-dlp accepts them — no need to transform IDs into anything fancier.
