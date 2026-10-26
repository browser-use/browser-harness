# toolify.ai — search & scope

Field-tested 2026-07-24 (keyword research for a non-AI SaaS product).

## Search URL pattern

Path-based, not query-string. The homepage search box (`input[name="toolifySearch"]`) posts to:

```
https://www.toolify.ai/search/<url-encoded query>
```

e.g. `https://www.toolify.ai/search/focus%20training`. `?q=` query-string form (`/search?q=...`) does **not** work — it silently redirects/500s to the homepage. Always use the `/search/<query>` path form.

Page title becomes `"The best <query> AI websites & AI tools - Toolify"` when the search resolves correctly — a quick way to confirm you didn't get redirected.

## Scope warning: this is an AI-tools-only directory

Toolify indexes ~30k *AI* products/SaaS (its own homepage states the count, e.g. "29953 AIs"). It is **not** a general product/app directory. Searching for a non-AI-tools niche (games, cognitive-training tools, browser games, etc.) returns semantically-matched but functionally unrelated AI SaaS products — e.g. searching `focus training` and `attention training` returned an AI photo editor, an AI running coach, an AI ranking-tracker SaaS, etc. None were actually competitors.

**Do not use toolify.ai for keyword/competitor research outside the AI-tools space.** Confirm the target niche is actually "AI tool"-shaped (LLM wrapper, AI-powered SaaS, GPT store entry) before spending time here. For cognitive-training / games / consumer-web-tool niches, Google autocomplete + Trends + direct competitor site scraping is a better source.

## Extraction

Card titles are inside `h2`/`h3`/`h4` wrapped by an `<a>`; a plain `querySelectorAll("a")` scan filtering for a heading child works, e.g.:

```js
Array.from(document.querySelectorAll("a")).filter(a => a.querySelector("h2,h3,h4"))
```
