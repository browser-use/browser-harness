# Shopify Knowledge Base App — automating FAQ entries

The Knowledge Base App (Shopify Winter '26 Edition) lets merchants control how AI agents (ChatGPT, Perplexity, Claude, Copilot, Gemini) answer questions about their brand. Each entry is a Question / Answer pair. The app currently has no public API and is English-only as of Winter '26 — browser automation is the canonical path.

## URL pattern

```
https://admin.shopify.com/store/<store-handle>/apps/shopify-knowledge-base/app
```

Sub-routes:
- `/app` — overview (FAQ list, top unanswered questions, query log)
- `/app/new` — Add FAQ form
- `/app/pairs/<id>` — entry detail / edit

## Iframe slug

The app runs at iframe URL containing `qa-pairs-app`:

```python
tid = iframe_target("qa-pairs-app")
```

## Adding a single FAQ

See `polaris-inputs.md` for the full canonical pattern. Quick version:

```python
def add_faq(question, answer):
    tid = iframe_target("qa-pairs-app")
    # focus question input via JS, type via CDP, focus answer, type, click Save
    # poll URL for /pairs/<id> success signal
```

## Batching multiple FAQs

After saving an entry, the success page shows "FAQ created. Add another FAQ" link. Click it via JS to skip navigating back to overview:

```python
def click_add_another():
    tid = iframe_target("qa-pairs-app")
    js("""
    (() => {
      const link = Array.from(document.querySelectorAll('a, button'))
        .find(x => x.textContent.trim() === 'Add another FAQ');
      if (link) link.click();
    })()
    """, target_id=tid)
```

Loop:

```python
ENTRIES = [(q1, a1), (q2, a2), ...]
for q, a in ENTRIES:
    click_add_another()
    time.sleep(1.5)  # wait for form to render
    ok, info = add_faq(q, a)
    print(f"{q[:40]} -> {ok} ({info})")
    if not ok: break
```

## Brand voice — what to put in answers

This is application-specific (depends on the merchant). For JING the rule was Aesop founder-letter tone — sentence case, no exclamation points, "JING" not "we", specific over generic.

The Shopify guidance "Provide a brief answer in 1 or 2 sentences" is a soft hint. The textarea accepts longer text and AI agents prefer specific multi-sentence answers. Aim for 2-4 short sentences with concrete details.

## What to put in the Knowledge Base

Categories that materially shape AI agent answers about your brand:

1. **Brand voice / DNA** — "What is your brand?" / "What's your tone?"
2. **Specs** — exact materials, dimensions, weights, sizes (NOT marketing prose)
3. **Comparisons** — "How does X compare to <competitor>?" with concrete differences
4. **Policies** — returns, shipping, care, warranty, contact (in brand voice)
5. **Origin** — founder, where made, why brand exists
6. **Limitations** — what you DON'T do (V1 scope, US-only, etc.) — agents that hallucinate availability hurt conversion

Skip: anything marketing-speak. The Knowledge Base is for **truth, in voice**, not pitch copy.

## Top unanswered questions

The overview shows up to 7 "Top unanswered questions" Shopify auto-detected from query logs. **Answer these first** — they're real shopper queries hitting your store right now. Once answered, the section empties.

## Query log

`/admin/apps/shopify-knowledge-base/app/queries` (or "Query log" in app sidebar) shows what shoppers actually asked AI agents about your brand. Read weekly. New patterns become new FAQ entries.

## Verifying entries surface in AI

After adding an entry, allow 24 hours for AI provider indexing, then test:

- ChatGPT: "Tell me about <your brand>'s return policy" → check if your exact wording surfaces
- Perplexity: same
- Claude: "Compare <your brand> vs <competitor>" → see if your comparison framing appears

If the answer doesn't surface, the entry might be too long, too vague, or contradicted by another source (your homepage, an outdated blog post). Tighten the answer.

## Limits

As of Winter '26 Edition:
- English-only
- No bulk import / CSV upload
- No API for read or write
- Each entry maximum ~500 words (soft cap; UI shows guidance "1 or 2 sentences")
- No version history visible to the merchant

Watch Shopify changelogs for API exposure — likely in Spring '26 or Summer '26 Edition. When it ships, switch to API-driven population.
