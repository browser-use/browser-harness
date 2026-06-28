# devto/publish — publish an article to DEV.to via the markdown editor (battle-tested 2026-06-28)

Driving `dev.to/new` with browser-harness against the user's logged-in Chrome. DEV.to gives an **instant, no-queue, high-DR dofollow backlink** in the article body — ideal for cross-posting an existing technical article. Far simpler than rich editors: it's one markdown textarea with Jekyll front matter.

## Pre-flight
- User logged into dev.to in Chrome. `new_tab("https://dev.to/new")` → if the editor (`textarea#article_body_markdown`) is present you're in; if you see a login wall, pause and ask.
- The "basic markdown editor" puts **everything in one textarea** — title/tags/description go in YAML front matter at the top, body below.

## The flow

### 1. Build the content (front matter + markdown body)
```
---
title: <Title, plain text>
published: true            # true = publish now; false = save as draft
description: <≤ ~150 chars>
tags: programming, ai, webdev, saas    # comma-separated, MAX 4, lowercase, no spaces/hyphens inside a tag
canonical_url: <optional — set to the original if cross-posting, to avoid duplicate-content>
---

<markdown body>
```
- **YouTube / Tweet embeds:** liquid tag on its own line — `{% embed https://youtu.be/<id> %}`.
- Body links are normal markdown `[text](https://...)` and render **dofollow**.

### 2. Insert it (React-safe native setter — don't type)
The editor is one big controlled textarea. Set the value via the native setter + fire input/change (typing char-by-char is slow and flaky):
```python
md = open("/path/post.md").read()
js("""(function(){
  var t=document.querySelector('textarea#article_body_markdown')||
        [].slice.call(document.querySelectorAll('textarea')).sort((a,b)=>b.getBoundingClientRect().height-a.getBoundingClientRect().height)[0];
  var setter=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,'value').set;
  setter.call(t, %s); t.dispatchEvent(new Event('input',{bubbles:true})); t.dispatchEvent(new Event('change',{bubbles:true}));
  return 'set:'+t.value.length;
})()""" % json.dumps(md))
```

### 3. Publish
- Scroll to the bottom; the button is **"Save changes"** (there is no separate "Publish" button in this editor). With `published: true` in the front matter, clicking **Save changes publishes**; with `published: false` it saves a draft.
- Success = the URL changes to `https://dev.to/<user>/<slug>`.

## Gotchas (field-tested)
- **"Invalid authenticity token" (CSRF) on save** — the #1 failure. The Rails CSRF token goes stale if the page sat open a while (or across a failed submit). **Fix: `goto("https://dev.to/new")` to reload (fresh token), re-insert the content, save again.** Don't dwell between loading the editor and submitting.
- **No "Publish" button** — it's "Save changes"; the `published:` front-matter flag decides draft vs live. Don't hunt for a Publish button.
- **Tags:** max 4, lowercase, each a single token (e.g. `webdev`, not `web-dev`); invalid tags can block the save.
- **Cover image** is optional but boosts the home-feed; drag-drop only (skip in automation, the user can add later).
- Cross-posting the same article to multiple sites (HackerNoon, Hashnode, dev.to): set `canonical_url` to the original on the secondary copies if you care about duplicate-content; for pure-backlink plays it's optional.

## Why it's worth it
Instant publish, no moderator queue, DEV.to is high domain authority, and body links are dofollow — so a single cross-post of an existing article = one of the "5 backlinks that matter," in ~3 minutes. Hashnode works the same way (markdown editor + instant publish).
