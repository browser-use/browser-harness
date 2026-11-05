# Content Extraction

Use the cheapest reliable route that preserves the page state you need. Browser
control and content extraction are separate jobs: drive the real page with
`browser-harness`, then archive and clean the rendered result.

## Route Selection

1. Static pages or JSON/API endpoints: use `http_get()` and parse the response.
2. Authenticated, personalized, or rendered pages: use the user's real Chrome
   session through `browser-harness`.
3. Before summarizing or cleaning anything, save a raw archive with
   `archive_current_page()` once that helper is available. Screenshots are
   disabled by default; enable them only for public/redacted pages or when the
   user explicitly approves screenshot capture for that run.
4. Article or documentation pages: run Defuddle on the local rendered HTML
   archive to produce markdown. Defuddle cleans content; it does not control the
   browser, click, log in, or replace CDP.
5. Tables, cards, lists, dashboards, and SPAs: use JavaScript structured
   extractors against the rendered DOM, then include partial-extraction status
   when lazy or virtualized content is detected.
6. Repeated domain-specific pages: promote the route into a domain skill with
   fixtures and a regression smoke.
7. Public high-scale scraping: use Firecrawl, Stagehand, Playwright, or similar
   auxiliary lanes only after an explicit privacy check. Do not upload private,
   authenticated, internal, or user-session snapshots to external services
   unless the user explicitly approves that page and run.

## Attach Smoke

The real-profile smoke must pass before extracting authenticated or rendered
content:

```bash
env -u BU_CDP_URL browser-harness -c 'ensure_real_tab(); print(page_info())'
```

Pass means the output includes `url`, `title`, `w`, `h`, `sx`, `sy`, `pw`, and
`ph` for a non-internal tab. `browser-harness --doctor` is useful context but is
not enough by itself.

If the real Chrome attach is missing, failing, or blocked by a Chrome prompt,
stop and record the blocker. Do not fall through to cloud browsers or isolated
profiles when the task needs the user's logged-in session.

## Evidence

Write milestone artifacts under `evidence/`:

- `evidence/task-N-pre-status.txt` for the dirty-worktree baseline.
- `evidence/task-N-*.txt` or `evidence/task-N-*.json` for command output and
  parser results.
- `evidence/task-N-archive/` for raw page HTML, text, metadata, links, and
  explicitly enabled screenshots.
- `evidence/task-N-*-blocker.txt` when a required browser/user action prevents
  extraction.

Raw archive files are the source of truth. Markdown, tables, cards, and lists
are derived artifacts and must not hide empty or partial extraction.

## Markdown

For rendered articles or docs, archive first and then derive markdown from the
local HTML artifact:

```bash
env -u BU_CDP_URL browser-harness -c 'ensure_real_tab(); print(extract_markdown_from_current_page("evidence/current-page-md", screenshot=False, overwrite=True))'
```

The returned archive keeps `raw/page.html` even when Defuddle is missing or
markdown conversion fails. Check `processed/status.json` before treating
`processed/page.md` as usable.

## Domain Skills

Promote a repeated site into `agent-workspace/domain-skills/` only when at least
one of these is true:

- Two successful extraction artifacts exist for the same domain.
- The user explicitly asks for a recurring domain workflow.

Before creating the skill, identify stable URL patterns, API endpoints or DOM
selectors, auth requirements, known traps, and the privacy boundary. Domain
skills should call helpers such as `archive_current_page()`, `extract_links()`,
`extract_tables()`, `extract_cards()`, and `extract_virtualized_container()`
instead of storing one-off page text.

Current lookup convention: `goto_url()` strips a leading `www.` from the host and
uses the first hostname label as the domain-skill folder. For
`https://www.example.com/`, lookup uses `agent-workspace/domain-skills/example/`.
Avoid dotted folder names such as `example.com/` unless the lookup behavior and
tests are updated together.

Use this template:

```text
# <domain> Content Extraction

## Purpose
## URL patterns
## Auth state
## Use these helpers
## Selectors/API
## Failure modes
## Evidence examples
## Do not
```

Do not include secrets, personal data, task narration, credentials, screenshots
with private data, or pixel coordinates in domain skills.

## Auxiliary Lanes

The core pipeline is local Chrome state plus raw archive, optional local
Defuddle, and JavaScript structured extractors. No API key is required for that
core path.

Use auxiliary tools only when their lane fits the page and privacy boundary:

- Playwright: deterministic E2E QA and semantic locator checks with role, text,
  label, and test-id locators. It is not required for core extraction.
  Source: https://playwright.dev/docs/locators
- Stagehand: optional LLM `act` / `observe` / `extract` workflows for high-value
  public or explicitly approved pages. It is not the private-page default.
  Source: https://docs.stagehand.dev/v3/basics/extract
- Firecrawl: public, unauthenticated pages at scale. Never send private,
  authenticated, internal, or user-session snapshots without explicit approval
  for that page and run.
  Source: https://docs.firecrawl.dev/api-reference/endpoint/scrape
- Browser Use CLI: optional alternate browser/session lane when a task is better
  suited to that stack. It does not replace local `browser-harness` for the core
  archive path.
  Source: https://docs.browser-use.com/open-source/browser-use-cli
- agent-browser: optional CLI/browser automation lane for agent-driven browsing.
  Treat it as an auxiliary lane, not a required dependency.
  Source: https://github.com/vercel-labs/agent-browser/blob/main/README.md

Privacy gate before using an external lane:

```bash
rg -n "firecrawl|stagehand|browser-use|agent-browser|api[_-]?key|requests|httpx|urllib.request" agent-workspace/content_extraction.py tests/unit/test_content_extraction.py
```

Expected for the core path: no external-service calls, no API-key requirement,
and no upload path from raw authenticated artifacts.
