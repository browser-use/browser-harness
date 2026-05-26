# x.com — Long-form Articles (`/i/article/<id>`)

How to extract X long-form articles ("X Articles", formerly Twitter Articles).
Auth-walled — direct fetch / defuddle / Wayback all return near-empty HTML —
so drive the user's logged-in Chrome via the harness.

## URL patterns

- Bookmark form: `https://x.com/i/article/<numeric_id>`
- Canonical form (after redirect): `https://x.com/<author_handle>/article/<canonical_id>`

The redirect happens at navigation time; either form lands on the same page.
The canonical id often differs from the original — record both if you care.

## DOM landmarks

```
[data-testid=twitter-article-title]       — title (clean)
[data-testid=twitterArticleRichTextView]  — body (Draft.js, ~10k chars typical)
[data-testid=twitterArticleReadView]      — wrapper that includes
                                            title + author + body + stats noise
[data-testid=User-Name]                   — author name + @handle + post date
```

Don't use `twitterArticleReadView` directly — its `innerText` includes the
trailing engagement counters ("49\n174\n1.1K\n295K"). Use the title and
rich-text views separately.

## Body structure: Draft.js blocks

The body is rendered by Draft.js — block-level structure is preserved in
class names on the immediate descendants of `twitterArticleRichTextView`:

```
.longform-unstyled              → paragraph
.longform-header-one            → # h1
.longform-header-two            → ## h2
.longform-header-three          → ### h3
.longform-blockquote            → > quote
.longform-unordered-list-item   → - item
.longform-ordered-list-item     → 1. item
.longform-image                 → contains <img src="…">
```

Inline formatting (bold, italic, links) lives inside the block as nested
`<span style="font-weight: bold">` / `<span style="font-style: italic">` /
`<a href="…">`. For a quick clip, `innerText` of each block is fine — it
flattens to plain text but preserves paragraph breaks. For higher fidelity
walk the spans and emit `**bold**` / `*italic*` / `[text](url)`.

Watch out: the block's text nodes contain the unicode "narrow no-break space"
(U+00A0) in many places. Strip / normalize when comparing or counting words.

## Reference implementation

See `bookmark-sync/twitter/article.py` in the user's Projects dir.

## Speed

A single article (3-second post-load wait) clips in ~5s on a warm browser.
46 articles in a row clipped without a hiccup.

## Auth

Requires the user to be logged in to X in the attached Chrome. Logged-out
behavior: the page renders the article behind a login wall and the
`twitterArticleRichTextView` element is absent — the extractor returns None.
