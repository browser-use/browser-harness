# AgentList Discovery

`https://agentlist.com` — public directory of skills, agents, MCPs, configs, and paid services. Field-tested with browser-harness on 2026-05-03.

## Do This First

Use the public API for read-only discovery. It is faster and returns full listing content without browser UI parsing.

```python
import json

listings = json.loads(http_get("https://agentlist.com/api/listings?category=skill&q=github&limit=10"))
for item in listings:
    print(item["title"], item["id"], item["vote_count"])
```

The web UI is useful for visual verification, voting, signing in with passkeys, and submitting listings.

## Public API

All read endpoints below worked without authentication.

```python
import json

# Search everything
items = json.loads(http_get("https://agentlist.com/api/listings?q=github&limit=10"))

# Filter by category
skills = json.loads(http_get("https://agentlist.com/api/listings?category=skill&q=browser&limit=10"))
agents = json.loads(http_get("https://agentlist.com/api/listings?category=agent&limit=10"))
mcps = json.loads(http_get("https://agentlist.com/api/listings?category=mcp&limit=10"))
configs = json.loads(http_get("https://agentlist.com/api/listings?category=config&limit=10"))
paid = json.loads(http_get("https://agentlist.com/api/listings?category=paid&limit=10"))

# Sort and paginate
new_items = json.loads(http_get("https://agentlist.com/api/listings?sort=new&skip=0&limit=20"))
top_items = json.loads(http_get("https://agentlist.com/api/listings?sort=top&limit=20"))
trending_items = json.loads(http_get("https://agentlist.com/api/listings?sort=trending&limit=20"))

# Fetch one listing
listing = json.loads(http_get("https://agentlist.com/api/listings/6ea8f4f2-83cf-4625-a3cd-98b49d49a7b2"))
```

Useful fields seen on listing objects:

- `id`, `category`, `title`, `description`, `content`
- `author_pubkey`, `vote_count`, `fetch_count`, `viewer_has_voted`
- `created_at`, `updated_at`, `reviewed_at`, `reviewed_by`
- MCP/config/paid-specific fields may be present: `repo_url`, `api_spec_url`, `transport`, `package`, `tools`, `target_tool`, `config_format`, `filename_hint`, `api_base_url`, `pricing_info`, `payment_method`

## Raw Skill Content

Use `/raw/{id}` when you only need the agent-readable content, not metadata.

```python
skill_md = http_get("https://agentlist.com/raw/6ea8f4f2-83cf-4625-a3cd-98b49d49a7b2")
```

For skill-folder loaders, the hosted `skills.agentlist.com` path also works:

```python
skill_md = http_get("https://skills.agentlist.com/skill/6ea8f4f2-83cf-4625-a3cd-98b49d49a7b2/SKILL.md")
```

Detail pages display a "Load in your local or cloud based agent" box with the folder URL:

```text
https://skills.agentlist.com/skill/{id}/
```

## Browser Navigation

```python
new_tab("https://agentlist.com")
wait_for_load()
wait(1)
print(page_info())
```

The homepage is server-rendered enough to read immediately after load. It contains:

- Category buttons: `Skills`, `Agents`, `MCPs`, `Configs`, `Paid For`
- Sort controls: `Top`, `New`, `Trending`
- Search input: `input[type=search]`
- Main listing table with headers `#`, `Title`, `Author`, `Date`, `Votes`

Extract visible rows:

```python
import json

rows = json.loads(js(r"""
JSON.stringify(Array.from(document.querySelectorAll("table:first-of-type tbody tr")).map(tr => {
  const cells = Array.from(tr.children).map(td => td.innerText.trim());
  return {
    rank: cells[0],
    title_description: cells[1],
    author: cells[2],
    date: cells[3],
    votes: cells[4]
  };
}))
"""))
```

Listing title links use `/listing/{uuid}`:

```python
links = json.loads(js(r"""
JSON.stringify(Array.from(document.querySelectorAll('a[href^="/listing/"], a[href*="/listing/"]')).map(a => ({
  text: a.innerText.trim(),
  href: a.href
})))
"""))
```

## UI Search Gotcha

`fill_input("input[type=search]", "github")` double-entered characters during testing (`github` became `ggiitthhuubb`). Prefer direct JS value assignment plus an `input` event, or use the API.

```python
js("""
const input = document.querySelector('input[type=search]');
input.value = 'github';
input.dispatchEvent(new Event('input', {bubbles: true}));
""")
wait(1)
print(page_info())  # URL becomes https://agentlist.com/?q=github
```

## Listing Detail Pages

Detail URL pattern:

```text
https://agentlist.com/listing/{id}
```

On skill detail pages, the rendered content includes raw code blocks, API notes, discussion, and a load URL. Detail pages also keep the homepage table lower on the page, so use scoped selectors when extracting the detail body.

```python
new_tab("https://agentlist.com/listing/6ea8f4f2-83cf-4625-a3cd-98b49d49a7b2")
wait_for_load()
wait(1)

data = json.loads(js(r"""
JSON.stringify({
  title: document.querySelector(".listing-title, h2")?.innerText || null,
  load_urls: Array.from(document.querySelectorAll("code")).map(e => e.innerText.trim()).filter(t => t.includes("skills.agentlist.com/skill/")),
  code_blocks: Array.from(document.querySelectorAll("pre, code")).map(e => e.innerText.slice(0, 300)).slice(0, 20)
})
"""))
```

The top-right user pill and `Sign out` button can appear when already authenticated. Do not assume a logged-out session.

## Submit Page

Submit URL:

```text
https://agentlist.com/submit
```

Observed fields:

- `#title` — title input
- `#description` — short description input
- `input[type=url]` — GitHub import URL
- first `textarea` — Markdown content
- `#scripts_index_html` — optional JavaScript skill payload

Observed category buttons:

```python
buttons = json.loads(js(r"""
JSON.stringify(Array.from(document.querySelectorAll("button.category-btn")).map(b => ({
  text: b.innerText.trim(),
  selected: b.classList.contains("selected")
})))
"""))
```

The GitHub import button is `button.btn.btn-secondary` with text `Import`. The final submit button has text `Submit listing`. Submissions are signed with the user's Nostr identity; do not submit or vote unless the user explicitly asked for that exact action.
