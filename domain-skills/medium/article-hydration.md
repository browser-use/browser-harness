# Medium — Article Body via DOM

Extract a Medium article's body as clean markdown using the logged-in browser. Use this when API paths in `scraping.md` are blocked or truncated:

- Cloudflare challenge on the `?format=json` endpoint ("Performing security verification")
- Member-only post that the API returns locked (`isSubscriptionLocked=True`) but the logged-in browser can render in full
- JS-only variant where the article is gated behind a client-side paywall modal

If the article is free and the API works, prefer `scraping.md` — it's faster and doesn't need a visible tab.

## URL patterns

- Canonical: `https://medium.com/@<author>/<slug>-<id>`
- Publication: `https://<pub>.medium.com/<slug>-<id>` or `https://medium.com/<pub>/<slug>-<id>`
- Custom domain: some publications (e.g. `towardsdatascience.com`) proxy Medium; the same DOM extractor works there.

All variants render the article body inside a single `<article>` element.

## Site structure

- The article body lives under the page's single `<article>` element.
- Block-level content: `h1`–`h4`, `p`, `pre`, `blockquote`, `ul`, `ol`, `figure`.
- Images are always wrapped in `<figure>` with a `<figcaption>` sibling; the real resolution lives on `miro.medium.com/v2/resize:fit:<N>/...`.
- Code blocks are `<pre>` — no language class is exposed in the DOM, so emit plain fenced blocks.
- Pull quotes render as `<blockquote>` with nested `<p>`.

## Cruft to strip

Medium injects engagement UI **inside** `<article>`. The text "6 2 Listen Share More" at the top is the clap/comment/listen/share button row, not content. Also expect a follow button near the author's name and sometimes a "Help" / "Status" footer.

Safe pattern: take the extracted markdown, then drop leading paragraphs that are shorter than ~12 characters until you hit the first real block (the "Last updated" line, the H1, or the first long paragraph).

## Extractor

````bash
browser-harness <<'PY'
new_tab("https://medium.com/@user/slug-abc123")
wait_for_load()
wait(2.0)  # Medium hydrates more UI after readyState=complete

md = js(r"""
(()=>{
  const article = document.querySelector('article');
  if(!article) return null;
  const blocks = article.querySelectorAll('h1, h2, h3, h4, p, pre, blockquote, ul, ol, figure');
  const out = [];
  const seen = new Set();
  for(const el of blocks){
    let skip = false;
    for(const s of seen){ if(s.contains(el) && s !== el){ skip=true; break; } }
    if(skip) continue;
    seen.add(el);
    const tag = el.tagName;
    const txt = (el.innerText || '').trim();
    if(!txt && tag !== 'FIGURE') continue;
    if(tag === 'H1') out.push('# ' + txt);
    else if(tag === 'H2') out.push('## ' + txt);
    else if(tag === 'H3') out.push('### ' + txt);
    else if(tag === 'H4') out.push('#### ' + txt);
    else if(tag === 'PRE') out.push('```\n' + txt + '\n```');
    else if(tag === 'BLOCKQUOTE') out.push(txt.split('\n').map(l=>'> '+l).join('\n'));
    else if(tag === 'UL' || tag === 'OL'){
      const items = [...el.querySelectorAll(':scope > li')].map((li,i)=>{
        const t = li.innerText.trim();
        return (tag==='OL' ? (i+1)+'. ' : '- ') + t;
      });
      out.push(items.join('\n'));
    }
    else if(tag === 'FIGURE'){
      const img = el.querySelector('img');
      const cap = el.querySelector('figcaption');
      if(img && img.src){
        const alt = img.alt || (cap ? cap.innerText.trim() : '');
        out.push('![' + alt + '](' + img.src + ')');
      }
    }
    else if(tag === 'P') out.push(txt);
  }
  return out.join('\n\n');
})()
""")

# Strip engagement-button cruft from the top
paras = md.split('\n\n')
while paras and len(paras[0]) < 12:
    paras.pop(0)
md = '\n\n'.join(paras)
print(md)
PY
````

The `seen` set avoids double-emitting when an `<li>` matches the block query inside its `<ul>`.

## Waits

- `wait_for_load()` is necessary but not sufficient — Medium continues to hydrate author-card and clap widgets after `readyState=complete`. An additional `wait(2.0)` avoids cases where the article outer frame exists but the first few paragraphs are still skeleton `<div>`s.
- For member-only articles, if `<article>` renders but text length is suspiciously short (<500 chars), the paywall modal intercepted. Confirm the tab is on your logged-in profile and retry.

## Paywall / login detection

```python
state = js("""
(()=>{
  const art = document.querySelector('article');
  const len = art ? art.innerText.length : 0;
  const hasPaywall = !!document.querySelector('[data-testid*="paywall"], [aria-label*="Sign in" i]');
  return {len, hasPaywall};
})()
""")
```

If `hasPaywall` is true or `len < 500`, fall back to `scraping.md` API paths (the article may simply be locked for this account).

## Traps

- **Don't use `article.innerText` alone.** It drops structure — code blocks lose their fences, lists lose their markers, figures disappear. The block walker above preserves each element kind.
- **Don't rely on CSS class names.** Medium's class names are hashed (`pw-post-body-paragraph`, etc.) and rotate; select by tag instead.
- **`<figure>` caption text is often also repeated as `<img alt>`.** Prefer `alt`, fall back to `figcaption`, so you don't emit both.
- **The article ends before the "About the Author" card sometimes, sometimes not.** The walker captures both, which is fine for archival. If you need body-only, cut at the last `h2`/`h3` before a `<hr>`-equivalent divider, or trim by known footer strings (`Follow`, `More from`, `Written by`).
- **Tab marker.** `new_tab()` prepends 🟢 to the title. Don't include `document.title` in the emitted markdown — use the article's `<h1>` instead.
