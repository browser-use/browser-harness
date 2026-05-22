# Facebook Pages — full archival of every post + comments + images

Sibling to `pages.md` and `groups.md`. Where those skills are tuned for
**monitoring** (top-N recent posts + outbound URL harvest), this one is tuned
for **preservation**: visit every reachable post on a Page, expand every
comment and reply, download every image, and emit one wiki-compatible markdown
file per post.

**Requires:** a real Chrome driven by Browser Harness, signed in to FB. Logged-out
sessions get interstitials within a handful of posts and cannot expand long
comment threads.

## What this skill is for

1. Build a manifest of **every** post permalink on a Page (not just recent N)
2. For each permalink, scrape full post body + author + timestamp
3. Recursively expand and capture **all** comments + nested replies
4. Download every image attached to the post (skip emoji + tracking pixels)
5. Emit one markdown file per post, structured for ingestion into a wiki

It is NOT for: monitoring (use `pages.md`), commenting/reacting, messaging the
Page, or any write action.

## Two-phase architecture (why)

FB's feed virtualizes aggressively: a post scrolled past gets unmounted from
the DOM, and — critically — comments on a post in the **feed view** are
collapsed to "View N comments" but **clicking that link in feed view does not
fully expand them**. Only the dedicated **permalink view** of a post renders
the full comment tree and lets you walk it.

So archival is two phases, not one:

| Phase | URL | Goal | Output |
|-------|-----|------|--------|
| 1. Manifest | `https://www.facebook.com/{vanity}` (bare Page URL) | Walk the feed top-to-bottom, harvest **every** permalink | JSON list of `{url, time_hint}` |
| 2. Scrape | each permalink in turn | Full post + recursively expanded comments + images | One `.md` per post |

Trying to do both in one pass — "scrape as you scroll" — loses comments on
every post that scrolled off-screen before you got to it. Don't.

## URL patterns

| What | URL |
|------|-----|
| Page (bare — use this for manifest) | `https://www.facebook.com/{vanity_or_id}` |
| Page Posts tab (sometimes bounces, see Gotchas) | `https://www.facebook.com/{vanity_or_id}/posts` |
| Post permalink (vanity, pfbid style) | `https://www.facebook.com/{vanity}/posts/pfbid{...}` |
| Post permalink (legacy) | `https://www.facebook.com/permalink.php?story_fbid={id}&id={page_id}` |
| Post permalink (story) | `https://www.facebook.com/story.php?story_fbid={id}&id={page_id}` |

The bare Page URL is preferred for Phase 1 — `/posts` sometimes 302s back to
`/` anyway (see Gotchas: bouncing `/posts` → `/`) and the bare URL renders the
same Posts widget without the redirect risk.

## DOM anchors (verified during archival of a long-running community Page)

Anchors specific to archival workflow. Post-article anchors are inherited from
`pages.md` and reproduced here for self-containment.

| Anchor | Selector | Notes |
|--------|----------|-------|
| Each post container | `div[role="article"]` | One per post in feed view; one outer + many nested in permalink view (see comment depth below) |
| Permalink (scoped to target Page) | `a[href*="/{vanity}/posts/pfbid"]` | **Filter by vanity** to exclude notification/recommendation leakage |
| Post body text | `div[data-ad-preview="message"], div[data-ad-comet-preview="message"]` | Same as monitoring |
| Post timestamp | `a[href*="/posts/"] abbr, a[role="link"] > span > span` | Hover for absolute |
| Post images | `div[role="article"] img` (filter, see image extraction) | Excludes emoji.php and width<60 |
| "See more" on long post | `div[role="button"]` containing visible text `See more` | Click before reading body |
| "View N comments" | `div[role="button"]` containing `View .* comments?\|previous comments?` | Click in permalink view to expand top-level thread |
| "View N replies" / "Show more replies" | `div[role="button"]` containing `View .* repl(y\|ies)\|more repl(y\|ies)` | Recurse — replies can be nested 3+ deep |
| Comment node | `div[role="article"]` nested under the post `div[role="article"]` | Depth = count of ancestor `div[role="article"]` between this node and the outermost |
| Comment body | `div[dir="auto"]` inside the comment article | Author name is also `div[dir="auto"]` — first one is typically the author |
| Comment author link | `a[role="link"][href*="/user/"], a[role="link"][href*="facebook.com/"]` first inside comment | Profile URL where available |

### The "Chats" H1 misdirection (important)

FB's persistent chat widget renders its own `<h1>` somewhere in the document —
on a permalink page that has the chat sidebar open, `document.querySelector('h1')`
will return **"Chats"**, not the Page name. Don't anchor on global `h1`.

For post content in permalink view, always scope to the post's outer
`div[role="article"]` — typically the **first** article whose nearest ancestor
is `[role="main"]`. Verify with the self-inspection block.

## Phase 1 — building the manifest

Walk top-to-bottom on the bare Page URL. Collect permalinks scoped to the
target Page only. Stop on N consecutive empty scrolls — don't rely on FB
rendering an explicit "no more posts" marker, because often it doesn't.

```python
import json, re, time
from urllib.parse import urlparse

PAGE = "cubacityhistory"     # vanity slug
MAX_SCROLLS = 2000           # generous ceiling for years-old Pages
EMPTY_LIMIT = 8              # consecutive empty scrolls = end of feed
SCROLL_PAUSE = 2.5           # floor per pages.md rate-limit
LONG_PAUSE_EVERY = 50        # extra cool-down every N scrolls
LONG_PAUSE_SECS = 30

new_tab(f"https://www.facebook.com/{PAGE}")
wait_for_load()
wait(3)

permalink_re = re.compile(rf'/{re.escape(PAGE)}/posts/pfbid[A-Za-z0-9]+')

seen = {}  # permalink -> {time_hint}
empty_streak = 0

for i in range(MAX_SCROLLS):
    batch = js(f"""
      Array.from(document.querySelectorAll('div[role="article"]')).flatMap(el => {{
        const links = Array.from(el.querySelectorAll('a[href*="/{PAGE}/posts/pfbid"]'));
        const time = el.querySelector('a[href*="/posts/"] abbr, a[role="link"] > span > span');
        return links.map(a => ({{
          url: a.href.split('?')[0],
          time_hint: time?.innerText || null,
        }}));
      }})
    """) or []

    before = len(seen)
    for p in batch:
        # Defense in depth — JS filter + Python filter on the path
        path = urlparse(p["url"]).path
        if permalink_re.search(path):
            seen.setdefault(p["url"], p)

    if len(seen) == before:
        empty_streak += 1
    else:
        empty_streak = 0

    if empty_streak >= EMPTY_LIMIT:
        break

    scroll(640, 400, dy=900)
    wait(SCROLL_PAUSE)
    if (i + 1) % LONG_PAUSE_EVERY == 0:
        wait(LONG_PAUSE_SECS)

print(json.dumps({"page": PAGE, "count": len(seen),
                  "permalinks": list(seen.keys())}, indent=2))
```

Write the manifest to disk before starting Phase 2 — Phase 2 can take hours on
a busy Page and you don't want to redo Phase 1 if anything crashes.

### Why the permalink filter matters

`a[href*="/posts/pfbid"]` alone matches links from FB's notification rail,
"Suggested for you" cards, and other off-Page leakage that gets injected into
the article-container tree. Filtering on `/{vanity}/posts/pfbid` keeps only
posts that actually belong to the target Page. Earlier attempts without the
vanity scope produced manifests that were ~30% pollution.

## Phase 2 — per-post scrape

Each permalink gets its own scrape. The most robust pattern is one
**subprocess-per-post** — daemon state is fresh, a crash on one post doesn't
poison the next. Within a single harness call, `ensure_real_tab()` between
operations also helps but is less bulletproof for hundreds-of-posts runs.

### Recursive expansion loop

The expansion buttons ("See more", "View N more comments", "View N replies",
"Show more replies") are themselves lazy — clicking one reveals more, which may
contain more such buttons. Run idempotent passes: click everything that
matches, wait for hydration, repeat. Stop when a pass clicks nothing.

```python
EXPAND_MAX_PASSES = 30

def expand_all_once():
    return js("""
      (() => {
        const buttons = Array.from(document.querySelectorAll('div[role="button"]'));
        const patt = /^(See more|View (\\d+|more|previous) (more )?comments?|View (\\d+|more) repl(y|ies)|Show more repl(y|ies)|\\d+ repl(y|ies))$/i;
        let clicks = 0;
        for (const b of buttons) {
          const txt = (b.innerText || '').trim();
          if (!txt) continue;
          if (patt.test(txt)) {
            try { b.click(); clicks++; } catch (e) {}
          }
        }
        return clicks;
      })()
    """) or 0

for _ in range(EXPAND_MAX_PASSES):
    n = expand_all_once()
    wait(2.0)  # hydration floor — same reasoning as pages.md scroll wait
    if n == 0:
        break
```

The regex is intentionally tight to avoid clicking "See translation", "Send
message", "Like", etc. If FB renames a button label, expand it here rather than
loosening to a catch-all.

### Comment depth from DOM nesting

Each FB comment and reply renders as its own `div[role="article"]` nested
inside the post's outer `div[role="article"]`. Depth = number of ancestor
`div[role="article"]` elements between this node and the post article.

- Depth 0 = the post itself
- Depth 1 = top-level comment
- Depth 2 = reply to a top-level comment
- Depth 3 = reply to a reply
- ...

```python
comments = js("""
  (() => {
    // Outermost article inside [role=main] is the post
    const main = document.querySelector('[role="main"]');
    if (!main) return [];
    const articles = Array.from(main.querySelectorAll('div[role="article"]'));
    if (articles.length === 0) return [];
    const post = articles[0];
    const out = [];
    for (const el of articles) {
      if (el === post) continue;
      // Depth: count [role=article] ancestors up to but not including post
      let depth = 0;
      let p = el.parentElement;
      while (p && p !== post) {
        if (p.getAttribute && p.getAttribute('role') === 'article') depth++;
        p = p.parentElement;
      }
      // depth so far is "articles between"; top-level comment is depth 1
      depth = depth + 1;
      const blocks = Array.from(el.querySelectorAll('div[dir="auto"]')).map(d => d.innerText).filter(Boolean);
      const authorLink = el.querySelector('a[role="link"][href*="facebook.com/"], a[role="link"][href*="/user/"]');
      const timeLink = el.querySelector('a[href*="/comment_id="], a[href*="?comment_id="]');
      out.push({
        depth: depth,
        author: blocks[0] || null,
        author_url: authorLink?.href || null,
        text: blocks.slice(1).join('\\n') || (blocks[0] && blocks.length === 1 ? blocks[0] : null),
        time_hint: timeLink?.innerText || null,
      });
    }
    return out;
  })()
""") or []
```

Render in markdown by indenting two spaces per depth level — that's compatible
with most wiki markdown ingesters and preserves the reply structure visually.

### Image extraction

Grab `<img>` tags inside the post article. Filter out FB's emoji renderer and
tiny pixels (avatars, tracking, decoration). Heuristic floor: width >= 60.

```python
images = js("""
  (() => {
    const main = document.querySelector('[role="main"]');
    if (!main) return [];
    const post = main.querySelector('div[role="article"]');
    if (!post) return [];
    return Array.from(post.querySelectorAll('img'))
      .filter(img => img.src && !img.src.includes('emoji.php'))
      .filter(img => (img.naturalWidth || img.width || 0) >= 60)
      .map(img => ({
        src: img.src,
        alt: img.alt || null,
        w: img.naturalWidth || img.width || null,
        h: img.naturalHeight || img.height || null,
      }));
  })()
""") or []
```

Download each `src` with `http_get` and write under a per-post directory.
FB's CDN URLs are signed and time-limited — archive promptly, don't store the
URL and expect it to resolve a week later.

```python
import os, hashlib
out_dir = f"./archive/{PAGE}/{post_slug}/images"
os.makedirs(out_dir, exist_ok=True)
for img in images:
    data = http_get(img["src"], as_bytes=True)
    digest = hashlib.sha1(img["src"].encode()).hexdigest()[:10]
    ext = ".jpg"  # FB serves mostly jpg; sniff with imghdr if you need exact
    with open(os.path.join(out_dir, f"{digest}{ext}"), "wb") as f:
        f.write(data)
```

### Wiki-compatible markdown layout

One file per post. Frontmatter for the wiki ingester, then post body, then a
threaded comment block. Indent replies by `depth - 1` levels of two spaces.

```python
def render(post_meta, body, images, comments, out_path):
    lines = []
    lines.append("---")
    lines.append(f"source: {post_meta['url']}")
    lines.append(f"page: {PAGE}")
    lines.append(f"time_hint: {post_meta.get('time_hint') or ''}")
    lines.append(f"images: {len(images)}")
    lines.append(f"comments: {len(comments)}")
    lines.append("---")
    lines.append("")
    lines.append(f"# Post — {post_meta.get('time_hint') or post_meta['url']}")
    lines.append("")
    lines.append(body or "_(no body text)_")
    lines.append("")
    if images:
        lines.append("## Images")
        lines.append("")
        for img in images:
            local = f"./images/{hashlib.sha1(img['src'].encode()).hexdigest()[:10]}.jpg"
            alt = (img.get("alt") or "").replace("]", "")
            lines.append(f"![{alt}]({local})")
        lines.append("")
    if comments:
        lines.append("## Comments")
        lines.append("")
        for c in comments:
            indent = "  " * max(0, c["depth"] - 1)
            who = c.get("author") or "_unknown_"
            t = c.get("time_hint") or ""
            lines.append(f"{indent}- **{who}** {f'({t})' if t else ''}")
            for tl in (c.get("text") or "").splitlines():
                lines.append(f"{indent}  {tl}")
        lines.append("")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
```

## Rate-limit discipline

Archival sessions touch the Page far more than monitoring does — hundreds or
thousands of permalink loads, each followed by aggressive button-clicking. Keep
the floors above the `pages.md` ceiling, not at it.

- **≥2.5 seconds between scrolls** in the manifest phase
- **30-second pause every 50 scrolls** in the manifest phase (long-tail cool-down)
- **≥3 seconds between permalink loads** in Phase 2
- **≥2 seconds between expansion passes** within a post
- **No more than ~40 permalinks per hour** for sustained archival
- **Pause for 60s every 25 permalinks** in Phase 2

Symptoms of over-pacing: "See more" stops being clickable, comment-expansion
buttons reappear after being clicked (FB silently rolled the action back), the
URL silently redirects to `/login/device-based/`, or a checkpoint interstitial
appears. If any of those fire, **stop**, let the operator inspect the screen,
and don't auto-resolve.

## Stale daemon recovery

Long sessions stress the harness daemon. Two patterns help:

1. **Subprocess-per-post** — invoke `browser-harness` once per permalink from a
   driver script. Daemon state is fresh on each call; a crash on post #347
   doesn't poison #348. Slower per-post (extra startup), but vastly more
   robust for hundreds-of-posts runs.

2. **`ensure_real_tab()` between operations** — within a single harness call,
   call this between permalink loads. Cheaper than subprocess-per-post but only
   masks intermittent issues, not crashes.

If the daemon stops responding mid-run, restart it once (per the root
`browser-harness/SKILL.md`), reload the last permalink, and continue from the
manifest position you'd reached.

## Self-inspection block (run when selectors stop working)

```python
print(js("""
  ({
    h1_text: document.querySelector('h1')?.innerText || null,  // beware Chats misdirection
    main_present: !!document.querySelector('[role="main"]'),
    articles_total: document.querySelectorAll('div[role="article"]').length,
    articles_in_main: document.querySelectorAll('[role="main"] div[role="article"]').length,
    body_preview_a: document.querySelectorAll('div[data-ad-preview="message"]').length,
    body_preview_b: document.querySelectorAll('div[data-ad-comet-preview="message"]').length,
    pfbid_links_total: document.querySelectorAll('a[href*="/posts/pfbid"]').length,
    expand_candidates: Array.from(document.querySelectorAll('div[role="button"]'))
      .map(b => (b.innerText||'').trim())
      .filter(t => /^(See more|View .* comments?|View .* repl|Show more repl|\\d+ repl)/i.test(t))
      .slice(0, 10),
    imgs_in_first_article: (() => {
      const a = document.querySelector('[role="main"] div[role="article"]');
      return a ? a.querySelectorAll('img').length : 0;
    })(),
  })
"""))
# If `h1_text` says "Chats", don't trust it for the page name — scope to [role=main].
# If `articles_total` is huge but `articles_in_main` is small, the rest are chat
# bubbles in the persistent widget — keep filtering inside [role=main].
```

## Full example — archive one Page end to end

```bash
browser-harness <<'PY'
import json, os, re, hashlib, sys, time
from urllib.parse import urlparse

PAGE = "cubacityhistory"
ROOT = f"./archive/{PAGE}"
os.makedirs(ROOT, exist_ok=True)

# ---------------- Phase 1: manifest ----------------
manifest_path = os.path.join(ROOT, "manifest.json")
new_tab(f"https://www.facebook.com/{PAGE}")
wait_for_load()
wait(3)

info = page_info()
if "/checkpoint/" in info["url"] or "/login" in info["url"]:
    sys.exit("AUTH_WALL — re-verify account before archiving.")

permalink_re = re.compile(rf'/{re.escape(PAGE)}/posts/pfbid[A-Za-z0-9]+')
seen = {}
empty_streak = 0
MAX_SCROLLS = 2000
EMPTY_LIMIT = 8

for i in range(MAX_SCROLLS):
    batch = js(f"""
      Array.from(document.querySelectorAll('div[role="article"]')).flatMap(el => {{
        const links = Array.from(el.querySelectorAll('a[href*="/{PAGE}/posts/pfbid"]'));
        const time = el.querySelector('a[href*="/posts/"] abbr, a[role="link"] > span > span');
        return links.map(a => ({{ url: a.href.split('?')[0],
                                  time_hint: time?.innerText || null }}));
      }})
    """) or []
    before = len(seen)
    for p in batch:
        if permalink_re.search(urlparse(p["url"]).path):
            seen.setdefault(p["url"], p)
    empty_streak = empty_streak + 1 if len(seen) == before else 0
    if empty_streak >= EMPTY_LIMIT:
        break
    scroll(640, 400, dy=900)
    wait(2.5)
    if (i + 1) % 50 == 0:
        wait(30)

with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump({"page": PAGE, "count": len(seen),
               "permalinks": list(seen.keys())}, f, indent=2)
print(f"manifest: {len(seen)} permalinks -> {manifest_path}")

# ---------------- Phase 2: per-post ----------------
# In production, prefer subprocess-per-post (see "Stale daemon recovery").
# Inline single-session version below for clarity.

def slug_for(url):
    m = re.search(r'pfbid[A-Za-z0-9]+', url)
    return m.group(0) if m else hashlib.sha1(url.encode()).hexdigest()[:12]

def expand_all_once():
    return js("""
      (() => {
        const buttons = Array.from(document.querySelectorAll('div[role="button"]'));
        const patt = /^(See more|View (\\d+|more|previous) (more )?comments?|View (\\d+|more) repl(y|ies)|Show more repl(y|ies)|\\d+ repl(y|ies))$/i;
        let c = 0;
        for (const b of buttons) {
          const t = (b.innerText || '').trim();
          if (t && patt.test(t)) { try { b.click(); c++; } catch(e){} }
        }
        return c;
      })()
    """) or 0

for idx, url in enumerate(list(seen.keys())):
    post_slug = slug_for(url)
    post_dir = os.path.join(ROOT, post_slug)
    img_dir = os.path.join(post_dir, "images")
    os.makedirs(img_dir, exist_ok=True)
    md_path = os.path.join(post_dir, "post.md")
    if os.path.exists(md_path):
        continue  # idempotent — skip already-archived

    ensure_real_tab()
    goto_url(url)
    wait_for_load()
    wait(3)

    # Recursively expand
    for _ in range(30):
        if expand_all_once() == 0:
            break
        wait(2.0)

    payload = js("""
      (() => {
        const main = document.querySelector('[role="main"]');
        if (!main) return null;
        const articles = Array.from(main.querySelectorAll('div[role="article"]'));
        if (!articles.length) return null;
        const post = articles[0];
        const body = post.querySelector('div[data-ad-preview="message"], div[data-ad-comet-preview="message"]');
        const time = post.querySelector('a[href*="/posts/"] abbr, a[role="link"] > span > span');
        const images = Array.from(post.querySelectorAll('img'))
          .filter(i => i.src && !i.src.includes('emoji.php'))
          .filter(i => (i.naturalWidth || i.width || 0) >= 60)
          .map(i => ({ src: i.src, alt: i.alt || null,
                       w: i.naturalWidth || null, h: i.naturalHeight || null }));
        const comments = [];
        for (const el of articles) {
          if (el === post) continue;
          let depth = 0, p = el.parentElement;
          while (p && p !== post) {
            if (p.getAttribute && p.getAttribute('role') === 'article') depth++;
            p = p.parentElement;
          }
          depth = depth + 1;
          const blocks = Array.from(el.querySelectorAll('div[dir="auto"]'))
            .map(d => d.innerText).filter(Boolean);
          const a = el.querySelector('a[role="link"][href*="facebook.com/"], a[role="link"][href*="/user/"]');
          const t = el.querySelector('a[href*="comment_id="]');
          comments.push({
            depth, author: blocks[0] || null, author_url: a?.href || null,
            text: blocks.slice(1).join('\\n') || null,
            time_hint: t?.innerText || null,
          });
        }
        return {
          body: body?.innerText || null,
          time_hint: time?.innerText || null,
          images, comments,
        };
      })()
    """)
    if not payload:
        print(f"[{idx}] {url} — no payload, skipping")
        continue

    # Download images
    for img in payload["images"]:
        try:
            data = http_get(img["src"], as_bytes=True)
            digest = hashlib.sha1(img["src"].encode()).hexdigest()[:10]
            with open(os.path.join(img_dir, f"{digest}.jpg"), "wb") as f:
                f.write(data)
        except Exception as e:
            print(f"  img fail {img['src'][:60]}... {e}")

    # Render markdown
    lines = ["---",
             f"source: {url}",
             f"page: {PAGE}",
             f"time_hint: {payload.get('time_hint') or ''}",
             f"images: {len(payload['images'])}",
             f"comments: {len(payload['comments'])}",
             "---", "",
             f"# Post — {payload.get('time_hint') or url}", "",
             payload.get("body") or "_(no body text)_", ""]
    if payload["images"]:
        lines += ["## Images", ""]
        for img in payload["images"]:
            d = hashlib.sha1(img["src"].encode()).hexdigest()[:10]
            alt = (img.get("alt") or "").replace("]", "")
            lines.append(f"![{alt}](./images/{d}.jpg)")
        lines.append("")
    if payload["comments"]:
        lines += ["## Comments", ""]
        for c in payload["comments"]:
            indent = "  " * max(0, c["depth"] - 1)
            who = c.get("author") or "_unknown_"
            t = c.get("time_hint") or ""
            lines.append(f"{indent}- **{who}**" + (f" ({t})" if t else ""))
            for tl in (c.get("text") or "").splitlines():
                lines.append(f"{indent}  {tl}")
        lines.append("")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[{idx}] {post_slug} — {len(payload['comments'])} comments, {len(payload['images'])} imgs")

    wait(3)
    if (idx + 1) % 25 == 0:
        wait(60)

print(f"done — archive at {ROOT}")
PY
```

## When to reach for which Facebook skill

| Goal | Skill |
|------|-------|
| Top-N recent posts from a Page + outbound URLs | `pages.md` |
| Top-N recent posts from a Group + outbound URLs | `groups.md` |
| **Every** post from a Page with full comments + images | `page-archival.md` (this file) |
| Marketplace listings | dedicated skill needed — neither of these |
| Personal profile feed | dedicated skill needed — much stricter rate limits |

## Gotchas log (append when you hit something new)

- **Two-phase or you lose comments.** Scrape-as-you-scroll on the feed loses
  comments because feed-view comment expansion is a no-op (or partial). Build
  a manifest first, then visit each permalink.
- **The "Chats" h1.** FB's chat sidebar exposes its own `<h1>`. Don't anchor
  on global `h1` for the Page name in archival mode — scope to `[role="main"]`.
- **Vanity-scoped permalink filter.** `a[href*="/posts/pfbid"]` alone pulls in
  notification/feed-recommendation links. Use
  `a[href*="/{vanity}/posts/pfbid"]` and re-validate in Python.
- **Bouncing `/posts` → `/`.** FB sometimes 302s `/{vanity}/posts` back to
  `/{vanity}/`. Use the bare Page URL for Phase 1 and rely on the Posts widget
  rendering — same content, no redirect risk.
- **End-of-feed isn't announced.** FB rarely shows a "no more posts" marker.
  Use `EMPTY_LIMIT = 8` consecutive empty scrolls as the terminator.
- **Comment expansion is multi-pass.** Each click reveals more comments which
  themselves may contain "View N replies" buttons. Loop until a pass clicks
  zero buttons; cap at 30 passes as a safety net.
- **Depth from nesting, not labels.** Don't try to infer reply depth from
  indentation pixels — they re-flow on viewport changes. Count ancestor
  `div[role="article"]` between the comment node and the post node.
- **CDN URLs expire.** FB's image CDN URLs are signed and short-lived. Archive
  the bytes promptly; don't store the URL for later retrieval.
- **Subprocess-per-post for large runs.** The harness daemon gets twitchy
  after hundreds of permalink loads in one session. A driver script that
  invokes `browser-harness` once per permalink (with the manifest as input) is
  the more robust shape; `ensure_real_tab()` between operations is the cheaper
  but less reliable alternative within a single session.
- **Emoji and tracking pixels masquerade as images.** Filter `emoji.php` and
  `width < 60` before downloading — otherwise the per-post `images/` dir fills
  up with avatars, reaction icons, and 1×1 trackers.
