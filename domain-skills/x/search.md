# X (Twitter) — web search against the logged-in session

Drive the user's **logged-in** Chrome at `x.com/search` to read search results with
the **full advanced-search operator set**. This reaches windows the public v2
"recent search" API can't (that API is ~7 days); the web index + `since:`/`until:`
reach much further back. No cookie-stealing — it's the user's real session.

## URL pattern

```
https://x.com/search?q=<URL-encoded query>&f=live
```

- `f=live` → Latest (chronological). `f=top` → Top (engagement-ranked). `f=user` → people.
- Always URL-encode `q`. Operators below go **inside** `q`.
- `&src=typed_query` is appended by the UI but not required.

## Advanced search operators (this is the whole point)

Put these in `q` — combine freely:

| Operator | Effect |
|---|---|
| `"exact phrase"` | exact match |
| `from:user` / `to:user` / `@user` | author / replies-to / mentions |
| `since:YYYY-MM-DD` `until:YYYY-MM-DD` | **arbitrary date window** (not limited to 7d) |
| `min_faves:N` `min_retweets:N` `min_replies:N` | engagement floors — great for cutting noise |
| `filter:links` `filter:media` `filter:images` `filter:videos` | content type |
| `-is:retweet` `-is:reply` `is:verified` `filter:quote` | post-type filters |
| `lang:en` | language |
| `(a OR b) c` | boolean groups |
| `url:domain.com` | links to a domain |

Example — high-signal posts on a topic over a specific month:
`"claude code" since:2026-05-01 until:2026-06-01 min_faves:25 -is:retweet lang:en`

## Login wall — STOP, don't auth

If the tab lands on `/login` or `/i/flow/login`, the profile isn't logged into X.
**Stop and tell the user** — never type credentials from a screenshot. Detect it:

```python
info = page_info()
if "/login" in info.get("url", "") or "/i/flow/login" in info.get("url", ""):
    raise SystemExit("LOGIN_WALL: not logged into X in this Chrome profile")
```

## Loading results — scroll, it's virtualized

The timeline lazy-loads on scroll and **recycles** DOM nodes (off-screen tweets are
removed). So extract *as you scroll*, accumulating by tweet id — don't scroll to the
bottom and then read, or you'll only see the last window. ~6–10 `scroll(dy=2400)`
steps with a short wait between covers a few hundred posts. Keep query volume modest;
aggressive scrolling on a real session can trip rate/bot walls.

## Selectors (stable as of 2026)

- Tweet: `article[data-testid="tweet"]`
- Body text: `[data-testid="tweetText"]` (`.innerText`)
- Permalink + timestamp + handle + id: `a[href*="/status/"] > time` — the `<a>`'s
  `href` is `/<handle>/status/<id>`; the `<time datetime>` is the ISO post time.
- **Exact engagement counts:** `[role="group"][aria-label]` on the action bar. The
  **visible** numbers are truncated ("1.2K"), but the `aria-label` carries the
  **exact** integers, e.g. `"12 replies, 5 reposts, 132 likes, 8 bookmarks, 23045 views"`.
  Parse those — never scrape the truncated visible text.

## Extractor — emits SourceItems directly

One `js()` over the currently-rendered articles. Returns the universal
`SourceItem` shape (counts exact, from aria-label). Call it repeatedly while
scrolling and merge by `item_id`.

```python
EXTRACT = r'''
(() => {
  const out = [];
  for (const art of document.querySelectorAll('article[data-testid="tweet"]')) {
    const textEl = art.querySelector('[data-testid="tweetText"]');
    const text = textEl ? textEl.innerText.trim() : "";
    if (!text) continue;
    const timeEl = art.querySelector('a[href*="/status/"] time');
    const a = timeEl && timeEl.closest('a[href*="/status/"]');
    const m = a && a.getAttribute('href').match(/^\/([^/]+)\/status\/(\d+)/);
    if (!m) continue;
    const handle = m[1], id = m[2];
    const iso = timeEl ? timeEl.getAttribute('datetime') : null;
    const grp = art.querySelector('[role="group"][aria-label]');
    const label = grp ? grp.getAttribute('aria-label') : "";
    const num = (kw) => { const r = label.match(new RegExp('([\\d,]+)\\s+' + kw)); return r ? parseInt(r[1].replace(/,/g,''),10) : null; };
    const eng = {}; const put = (k,v)=>{ if(v!=null) eng[k]=v; };
    put('replies', num('repl')); put('reposts', num('repost')); put('likes', num('like'));
    put('bookmarks', num('bookmark')); put('impressions', num('view'));
    out.push({
      item_id: "x-"+id, source: "x", title: text.slice(0,120), body: text,
      url: "https://x.com/"+handle+"/status/"+id, author: handle,
      published_at: iso ? iso.slice(0,10) : null,
      date_confidence: iso ? "high" : "low",
      engagement: eng, relevance_hint: 0.7,
      why_relevant: "X web search (logged-in, advanced filters)", metadata: {}
    });
  }
  return out;
})()
'''
```

## Full capture snippet

```python
from urllib.parse import quote
import json, time
from pathlib import Path

QUERY = '"claude code" since:2026-05-12 min_faves:20 -is:retweet lang:en'
OUT   = "/tmp/l30/walled_x_web.json"

new_tab("https://x.com/search?q=" + quote(QUERY) + "&f=live")
wait_for_load()
info = page_info()
if "/login" in info.get("url","") or "/i/flow/login" in info.get("url",""):
    raise SystemExit("LOGIN_WALL: not logged into X — ask the user to log in")

seen, items = {}, []
for _ in range(8):
    for o in (js(EXTRACT) or []):
        if o["item_id"] not in seen:
            seen[o["item_id"]] = 1; items.append(o)
    scroll(640, 400, dy=2400); time.sleep(0.9)

Path(OUT).parent.mkdir(parents=True, exist_ok=True)
Path(OUT).write_text(json.dumps(items, ensure_ascii=False, indent=2))
print(f"captured {len(items)} X posts -> {OUT}")
```

## Traps

- **Truncated counts.** Visible engagement is rounded ("1.2K"); aria-label is exact. Use aria-label.
- **Virtualized list recycles nodes.** Extract-while-scrolling; don't read once at the end.
- **`since:`/`until:` reach further than the API, but the web search index still
  thins out for very old / low-engagement posts** — absence ≠ "nothing happened".
- **Long tweets** may have `tweetText` truncated with a "Show more"; the first ~280
  chars are usually enough for ranking. Open the permalink only if you need the full body.
- **Rate/bot walls** appear as an empty timeline or a challenge — back off, lower volume.
- **Quoted/embedded tweets** render a nested `article`; `querySelectorAll('article')`
  may pick up the inner one. Scoping to `data-testid="tweet"` and de-duping by id handles it.
