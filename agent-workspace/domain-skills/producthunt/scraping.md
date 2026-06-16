# Product Hunt Scraping Skills

Field-tested against https://www.producthunt.com on 2026-04-18.
All selectors verified with actual browser runs.

---

## Page Structure Overview

Product Hunt is a React SPA. Key structural facts discovered:

- **No login wall** — all product data is accessible without signing in
- **No cookie banner** — page loads cleanly with no consent dialogs
- **Product URLs use `/products/` not `/posts/`** — the `a[href^="/posts/"]` selector matches nothing
- **`data-test` attributes** are the most reliable selectors throughout the site
- **4 homepage sections**: today, yesterday, last week, last month (5 products each, plus "see all")
- **Today's votes are hidden** for the first 4 hours of each day (`—` instead of count)
- **Homepage has 30 fixed post-items** — scrolling does NOT load more
- **`goto_url()` may return `ERR_ABORTED`** for producthunt.com in some browser sessions — use `new_tab()` instead

---

## Navigation Pattern

```python
# goto_url() may fail on Product Hunt — use new_tab() reliably
tid = new_tab("https://www.producthunt.com")
wait(4)  # React SPA needs time; wait_for_load() alone is insufficient
page = page_info()
# Verify: url should be 'https://www.producthunt.com/'
```

---

## Homepage — Extract Daily Product Feed

The homepage shows today's launches plus rolling sections for yesterday, last week, last month.

### Working selector: `[data-test^="post-item-"]`

```python
# Full extraction with name, tagline, slug, votes, topics
products = js("""
JSON.stringify(
  Array.from(document.querySelectorAll('[data-test^="post-item-"]')).map(el => {
    var id = el.getAttribute('data-test').replace('post-item-', '');
    var nameEl = el.querySelector('[data-test^="post-name-"]');
    var productLink = el.querySelector('a[href^="/products/"]');
    var voteBtn = el.querySelector('[data-test="vote-button"]');
    var voteCount = voteBtn ? voteBtn.textContent.trim() : null;
    var topicLinks = Array.from(el.querySelectorAll('a[href^="/topics/"]')).map(a => a.textContent.trim());
    var name = nameEl ? nameEl.textContent.trim() : '';
    var lines = el.innerText.split('\\n').map(l => l.trim()).filter(l => l);
    var tagline = lines.find(l => l !== name && !topicLinks.includes(l) && l !== '•' && !/^[0-9—]/.test(l) && l.length > 5);
    return {
      id: id,
      name: name,
      slug: productLink ? productLink.getAttribute('href') : null,
      votes: voteCount,
      topics: topicLinks,
      tagline: tagline || null
    };
  })
)
""")
```

**Sample output:**
```json
[
  {"id":"1126372","name":"Vercel Flags","slug":"/products/vercel","votes":"—","topics":["Software Engineering","Developer Tools"],"tagline":"Feature flags, targeting rules, rollouts. All from Vercel."},
  {"id":"1125388","name":"1. Claude Opus 4.7","slug":"/products/claude-opus-4-7","votes":"466","topics":["API","Artificial Intelligence","Development"],"tagline":"Claude's most capable model for reasoning and agentic coding"}
]
```

**Votes:**
- `"—"` = vote count hidden (today's products during first 4 hours)
- `"466"` = numeric string (yesterday/older products)
- `"2,152"` = comma-formatted for large counts (parse: `voteCount.replace(',', '')`)

**Name prefix**: Ranked products show rank in name: `"1. Claude Opus 4.7"` — strip with `re.sub(r'^\d+\. ', '', name)`.

---

## Daily Leaderboard — Best URL for Complete Daily Lists

The leaderboard shows all products for any given day with actual vote counts.

```
URL: https://www.producthunt.com/leaderboard/daily/YYYY/M/D
Example: https://www.producthunt.com/leaderboard/daily/2026/4/18
```

- Uses zero-padded-free month/day (April = `4`, not `04`)
- Uses same `[data-test^="post-item-"]` selector
- Shows 12–19 products per day
- Same extraction JS as homepage works identically

**Yesterday's results with real vote counts:**
```json
{"id":"1125388","name":"1. Claude Opus 4.7","slug":"/products/claude-opus-4-7","votes":"466","tagline":"Claude's most capable model for reasoning and agentic coding"}
{"id":"1118208","name":"2. Build Check","slug":"/products/build-check-for-outsiders","votes":"396"}
```

---

## Weekly Leaderboard

```
URL: https://www.producthunt.com/leaderboard/weekly/YYYY/WW
Example: https://www.producthunt.com/leaderboard/weekly/2026/16
```

- Week number is ISO week (week 16 = April 13–19, 2026)
- Current week may return 0 items until the week ends
- Same `[data-test^="post-item-"]` selector

---

## Monthly Leaderboard

```
URL: https://www.producthunt.com/leaderboard/monthly/YYYY/M
Example: https://www.producthunt.com/leaderboard/monthly/2026/4
```

---

## Topic Page

URL: `https://www.producthunt.com/topics/developer-tools`

Selector changes on topic pages — uses `[data-test^="product:"]` not `post-item-`.

```python
# Navigate to topic
new_tab("https://www.producthunt.com/topics/developer-tools")
wait(3)

products = js("""
JSON.stringify(
  Array.from(document.querySelectorAll('[data-test^="product:"]')).map(el => {
    var slug = el.getAttribute('data-test').replace('product:', '');
    var link = el.querySelector('a[href^="/products/"]');
    return {
      slug: slug,
      href: link ? link.getAttribute('href') : null,
      text: el.outerText.trim().substring(0, 200)
    };
  })
)
""")
```

**Sample output:**
```json
{"slug":"figma","href":"/products/figma","text":"FigmaThe collaborative interface design tool4.9 (1.4K reviews)..."}
```

Returns ~15 top-rated products in the topic, not recent launches.

---

## Category Page

URL: `https://www.producthunt.com/categories/ai-agents`

Same `[data-test^="product:"]` selector as topics. Returns 15 top-reviewed products in that category.

```json
{"slug":"elevenlabs","href":"/products/elevenlabs","text":"ElevenLabs\nCreate natural AI voices instantly...\n4.9 (165 reviews)"}
```

---

## Product Detail Page

URL: `https://www.producthunt.com/products/claude-opus-4-7`

### Get total vote count (sidebar button)
```python
# Use [data-test="vote-button"] — different from [data-test="action-bar-vote-button"]
vote_text = js("document.querySelector('[data-test=\"vote-button\"]').outerText.trim().replace(/\\s+/g, ' ')")
# Returns: "Upvote • 466 points"
# Parse votes: vote_text.split('•')[1].strip().replace(' points', '').replace(',', '')
```

### Get review count and rating
```python
review_link = js("JSON.stringify(Array.from(document.querySelectorAll('a')).filter(a => a.href && a.href.includes('/reviews') && a.outerText.includes('review')).map(a => a.outerText.trim()).slice(0, 1))")
# Returns: ["1 review"] or ["5.0\n(731 reviews)"]
```

### Get day rank (sidebar shows "#1 Day Rank")
No dedicated `data-test` for rank — parse from sidebar context or use leaderboard position.

### Comments (action-bar-vote-button)
Each comment has its own `[data-test="action-bar-vote-button"]` with text like `"Upvote (13)"`.

---

## Search Results

URL: `https://www.producthunt.com/search?q=AI+agent`

Selector: `[data-test^="spotlight-result-product-"]`

```python
new_tab("https://www.producthunt.com/search?q=AI+agent")
wait(3)

results = js("""
JSON.stringify(
  Array.from(document.querySelectorAll('[data-test^="spotlight-result-product-"]')).map(el => {
    var id = el.getAttribute('data-test').replace('spotlight-result-product-', '');
    var lines = el.outerText.trim().split('\\n').map(l => l.trim()).filter(l => l);
    return {
      id: id,
      name: lines[0] || null,
      tagline: lines[1] || null,
      review_text: lines[2] || null
    };
  })
)
""")
```

**Note:** Search result elements are `<button>` elements (not `<a>` links), so there is no `href` in the DOM. Product URL must be constructed: `https://www.producthunt.com/products/<slug>` where slug must be derived by other means. The element's `data-test` ID matches the numeric product ID, not the slug.

**Sample output:**
```json
{"id":"526014","name":"/ai","tagline":"Access ChatGPT anywhere you type '/ai'","review_text":"2 reviews"}
{"id":"991302","name":"Naoma AI Demo Agent","tagline":"The first video agent that runs conversational product demos","review_text":"5 reviews"}
```

---

## Key Selector Reference

| Page | Selector | Count | Notes |
|------|----------|-------|-------|
| Homepage | `[data-test^="post-item-"]` | 30 | 4 sections × ~5–7 products |
| Homepage | `[data-test^="post-name-"]` | 30 | Product name elements |
| Homepage/Leaderboard | `[data-test="vote-button"]` | varies | `—` for hidden; numeric for visible |
| Topics/Categories | `[data-test^="product:"]` | ~15 | Top-rated products |
| Search | `[data-test^="spotlight-result-product-"]` | 10 | Button elements, no href |
| Product detail | `[data-test="vote-button"]` | 1 | Main vote: "Upvote • N points" |
| Product detail | `[data-test="action-bar-vote-button"]` | many | Comment upvotes: "Upvote (N)" |

---

## Common Pitfalls

1. **`innerText` returns `None` on complex elements** — use `outerText` or break into simple single-property expressions. Avoid chaining DOM traversal inside `JSON.stringify()` on large objects.

2. **`goto_url()` returns `ERR_ABORTED`** for producthunt.com in some browser sessions — always use `new_tab("url")` instead.

3. **`a[href^="/posts/"]` matches nothing** — Product Hunt uses `/products/` for product URLs, not `/posts/`.

4. **Today's votes are always `—`** during the first 4 hours of the day — use yesterday's leaderboard for confirmed vote counts.

5. **Homepage does not lazy-load more products on scroll** — 30 items is the fixed set. Use leaderboard pages for complete daily listings.

6. **JSON.stringify of DOM-heavy objects returns `None`** — serialize only primitives (strings, numbers) not live DOM node properties.

7. **Ranked product names contain rank prefix** — `"1. Claude Opus 4.7"` — strip with regex `re.sub(r'^\d+\.\s+', '', name)`.

8. **`wait(3)` required after `wait_for_load()`** — the React SPA continues rendering after the load event.

---

## Recommended Workflow for Scraping Today's Launches

```python
# 1. Open Product Hunt in a new tab
new_tab("https://www.producthunt.com/leaderboard/daily/2026/4/18")
wait(4)

# 2. Extract all products with metadata
products = js("""
JSON.stringify(
  Array.from(document.querySelectorAll('[data-test^="post-item-"]')).map(el => {
    var id = el.getAttribute('data-test').replace('post-item-', '');
    var nameEl = el.querySelector('[data-test^="post-name-"]');
    var productLink = el.querySelector('a[href^="/products/"]');
    var voteBtn = el.querySelector('[data-test="vote-button"]');
    var topicLinks = Array.from(el.querySelectorAll('a[href^="/topics/"]')).map(a => a.textContent.trim());
    var name = nameEl ? nameEl.textContent.trim() : '';
    var lines = el.innerText.split('\\n').map(l => l.trim()).filter(l => l);
    var tagline = lines.find(l => l !== name && !topicLinks.includes(l) && l !== '•' && !/^[0-9—]/.test(l) && l.length > 5);
    return {
      id: id,
      name: name,
      slug: productLink ? productLink.getAttribute('href') : null,
      votes: voteBtn ? voteBtn.textContent.trim() : null,
      topics: topicLinks,
      tagline: tagline || null
    };
  })
)
""")
import json
data = json.loads(products)
print(f"Found {len(data)} products")
for p in data:
    print(f"  {p['name']} — {p['votes']} votes — {p['tagline']}")
```
