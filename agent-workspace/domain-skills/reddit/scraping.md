# Reddit — Scraping & Post Extraction

Reddit's "new" web UI (`reddit.com`) is a Lit / web-components SPA built around custom elements (`shreddit-post`, `shreddit-comment`, `faceplate-*`). This makes DOM extraction unusually reliable — the custom element tags are stable and exposed on the element itself (no hashed class names).

Use the browser when you're logged in (private subreddits, NSFW gates, rate-limit avoidance). **As of 2026 the browser DOM path is also the only reliable path for anonymous public content** — Reddit now hard-blocks the `.json` API for anonymous clients (see Path 1).

## URL patterns

- Full post: `https://www.reddit.com/r/<sub>/comments/<id>/<slug>/`
- Share short-link: `https://www.reddit.com/r/<sub>/s/<hash>` — redirects to the full URL once the page loads. `new_tab(short_url)` + `wait_for_load()` is enough; by the time you read `location.href` it will be the canonical one.
- Old Reddit: append `/.json` to any post URL for anonymous JSON: `https://www.reddit.com/r/<sub>/comments/<id>/.json`.
- Old UI (simpler DOM, no web components): `https://old.reddit.com/r/<sub>/comments/<id>/` — useful fallback when `shreddit-*` selectors change.

## Path 1: JSON API — ⚠️ DEAD for anonymous clients (2026)

The old `append /.json` trick **no longer works anonymously**. Reddit returns **HTTP 403** with a block page (`"You've been blocked by network security. To continue, log in to your Reddit account or use your developer token"`) for `www.reddit.com/.../​.json` and `old.reddit.com/.../​.json` alike. Confirmed dead even with:

- A real browser User-Agent or unique descriptive UA
- Full browser request headers (Accept, Referer, etc.)
- `curl_cffi` Chrome/Safari **TLS impersonation** (still 403 — it's not just a TLS-fingerprint check)
- Fresh **residential proxy** IPs (the IP isn't the trip — the *endpoint* is gated)

The block is endpoint-level: Reddit wants OAuth (a developer token) or a logged-in session for the JSON API. So for anonymous scraping there are two live options:

1. **Browser DOM extraction** (Path 2) — works anonymously. From a datacenter IP you still need a residential proxy *and* a real browser (see the headless+proxy recipe below); the fingerprint and IP must both look human.
2. **Official OAuth API** — register a script app at `reddit.com/prefs/apps`, get `client_id`/`secret`, exchange for a bearer token, then hit `https://oauth.reddit.com/r/<sub>/new?limit=...` with `Authorization: bearer <token>` + a unique UA. Supported, ~100 QPM free, works from datacenter IPs.

### Headless browser + residential proxy (cron-friendly, no GUI)

What revived a server-side bot (Playwright Chromium through an IPRoyal residential proxy). A datacenter-IP browser alone gets the same 403 block page; the residential proxy is what gets you past the network wall.

```python
from playwright.sync_api import sync_playwright
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, args=["--no-sandbox"],
        proxy={"server": "http://geo.iproyal.com:12321", "username": "<user>", "password": "<pass>"})
    ctx = b.new_context(user_agent=UA, locale="en-US", viewport={"width": 1280, "height": 1400})
    pg = ctx.new_page()
    pg.goto("https://www.reddit.com/r/<sub>/new/", wait_until="domcontentloaded", timeout=45000)
    pg.wait_for_timeout(3500)  # SPA hydration
    blocked = pg.evaluate("document.body.innerText.indexOf('blocked by network security') >= 0")
    posts = pg.evaluate("document.querySelectorAll('shreddit-post').length")  # 0 + blocked => bad proxy, rotate
```

Probe each proxy session by checking `blocked` / `shreddit-post count`, and rotate to the next session on failure. `pip install playwright` then `python -m playwright install chromium` — note Playwright pins an exact build revision; a version bump that isn't followed by `playwright install` leaves the browser binary missing (`Executable doesn't exist at .../chromium_headless_shell-<rev>`).

## Path 2: Browser DOM extraction (logged-in)

Core selector: every post renders inside a single `<shreddit-post>` custom element. Top-level comments are `<shreddit-comment depth="0">`.

```bash
browser-harness <<'PY'
new_tab("https://www.reddit.com/r/vibecoding/comments/1kwuqpz/")
wait_for_load()
wait(3.0)  # SPA still hydrating after readyState=complete

# Scroll to force comment tree lazy-load (twice, ~2000px each)
scroll(500, 500, dy=2000); wait(1.0)
scroll(500, 500, dy=2000); wait(1.0)

data = js(r"""
(()=>{
  const postEl = document.querySelector('shreddit-post');
  if(!postEl) return null;
  const title = (postEl.querySelector('h1, [slot="title"]')||{}).innerText?.trim() || '';
  const bodyEl = postEl.querySelector('[slot="text-body"] .md, [slot="text-body"]');
  const body = bodyEl ? bodyEl.innerText.trim() : '';
  const author = (postEl.querySelector('[slot="authorName"] a, a[data-testid="post_author_link"]')||{}).innerText?.trim() || '';
  const subM = location.pathname.match(/^\/r\/([^\/]+)/);
  const subreddit = subM ? subM[1] : '';
  const scoreEl = postEl.querySelector('faceplate-number');
  const score = scoreEl ? scoreEl.getAttribute('number') || scoreEl.innerText : '';
  const comments = [];
  for(const c of document.querySelectorAll('shreddit-comment[depth="0"]')){
    const cBodyEl = c.querySelector('[slot="comment"] .md, [slot="comment"]');
    const cBody = cBodyEl ? cBodyEl.innerText.trim() : '';
    if(!cBody) continue;
    comments.push({
      author: c.getAttribute('author') || '',
      score: c.getAttribute('score') || '',
      body: cBody
    });
    if(comments.length >= 10) break;
  }
  return {subreddit, title, author, score, body, comments, url: location.href};
})()
""")
print(data["title"], "·", len(data["body"]), "chars ·", len(data["comments"]), "comments")
PY
```

### Key selectors

| Target                 | Selector                                                              | Notes                                                                                                   |
| ---------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| Post container         | `shreddit-post`                                                       | One per post page. Attributes include `post-title`, `post-id`, `subreddit-name`, `author`.              |
| Post title             | `shreddit-post h1` or `[slot="title"]`                                | H1 is also the page title.                                                                              |
| Post text body         | `shreddit-post [slot="text-body"] .md`                                | `.md` is the rendered markdown container. For link posts this selector returns null (there is no body). |
| Post author name       | `[slot="authorName"] a`                                               | Plain text.                                                                                             |
| Vote score             | `shreddit-post faceplate-number`                                      | Read the `number` attribute (digit string) — `innerText` is abbreviated ("1.2k").                       |
| Top-level comment      | `shreddit-comment[depth="0"]`                                         | Depth is an attribute — `depth="1"` is a reply, etc.                                                    |
| Comment body           | `shreddit-comment [slot="comment"] .md`                               | Same pattern as post body.                                                                              |
| Comment author / score | `shreddit-comment` attributes: `author`, `score`, `created-timestamp` | Use `getAttribute`, not DOM descendants.                                                                |

### Feed / listing extraction (`/r/<sub>/new/`, `/hot/`, etc.)

The feed renders one `<shreddit-post>` per card with everything you need as **attributes** (no detail-page visit required for a listing digest):

| Attribute            | Example                                    |
| -------------------- | ------------------------------------------ |
| `id`                 | `t3_1ts8jb7` (strip `t3_` for the bare id) |
| `post-title`         | `Kids sports or summer camp?`              |
| `permalink`          | `/r/ThunderBay/comments/1ts8jb7/.../`      |
| `score`              | `5` (exact, not abbreviated)               |
| `comment-count`      | `2`                                        |
| `created-timestamp`  | `2026-05-30T19:08:22.655000+0000`          |
| `post-type`          | `text` / `image` / `link`                  |
| `author`             | `Double-Control7332`                       |

`/new/` is newest-first and lazy-loads on scroll — `page.mouse.wheel(0, 24000)` + wait, looping until the oldest loaded `created-timestamp` passes your time window. Parse the timestamp by normalizing `+0000`→`+00:00` then `datetime.fromisoformat`. Promoted/ad cards may carry a `promoted` attribute or lack a `t3_` id — filter those out.

### Share links

`/s/<hash>` URLs redirect before the SPA mounts. You don't need to resolve them manually — just `new_tab(url)` + `wait_for_load()` + `wait(2)`, then read `location.href` for the canonical path.

### Comment tree lazy-loading

New Reddit renders only the initial visible comments. To get more, **scroll twice**. `ensureReplies` / `more` placeholders exist but clicking them is brittle; scroll is the most reliable trigger. For a deep thread, loop `scroll + wait` until `shreddit-comment` count stabilizes between passes.

### Login / gate detection

```python
state = js("""
(()=>{
  const loginWall = !!document.querySelector('a[href*="/login"], [data-testid="login-button"]');
  const ageGate = !!document.querySelector('[data-testid="nsfw-gate"], shreddit-interstitial');
  return {loginWall, ageGate};
})()
""")
```

If `ageGate` is true and you are logged in but haven't opted into NSFW content, the gate blocks extraction — toggle NSFW in account settings, not programmatically.

## Gotchas

- **`faceplate-number.innerText` is abbreviated** ("1.2k", "16.6k"). Always prefer `getAttribute('number')` for the exact digit count.
- **`shreddit-comment` is a custom element, not a `<div>`.** CSS descendant selectors still work, but older jQuery-style parent traversals may not — stick to standard DOM.
- **`depth="0"` is a string attribute.** `[depth="0"]` in a CSS selector works; `depth=0` (no quotes) also works in the newer parser, but the quoted form is safest.
- **Collapsed comments render with body still in the DOM, but behind `expando-button`.** The `.md` selector still grabs the text — you don't need to expand.
- **Post body can be empty.** For link posts or image posts, `[slot="text-body"]` doesn't exist; null-check before reading `.innerText`.
- **`wait_for_load()` is not enough.** Reddit sometimes paints the post skeleton before the content hydrates. Add `wait(2.0)`–`wait(3.0)` after `wait_for_load()` or retry reads on null `shreddit-post`.
- **Share URLs (`/s/<hash>`) can't be deep-linked into a comment.** They always land at the post top. If the original raindrop captured `/s/...`, the in-DOM permalink (read from `location.href` after load) is the canonical URL worth storing.
- **Old Reddit (`old.reddit.com`) is a separate DOM** — no `shreddit-*` elements, no `faceplate-*`. If your login session was established on new Reddit, `old.reddit.com` will still honor the cookie.
- **For NSFW or quarantined subs**, the browser path requires your account to have opted in. The JSON API requires OAuth with appropriate scope.
- **`[slot="text-body"] .md .md`** — Reddit occasionally double-wraps; the selector `[slot="text-body"] .md` is the outer one and is what you want. Using `[slot="text-body"]` alone works too, but may include meta text.
