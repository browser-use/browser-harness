# claude.ai — Export a Shared Conversation

URL pattern: `https://claude.ai/share/<uuid>`

Extracts a full Human/Assistant transcript from a Claude share link as JSON or Markdown.

## Auth requirement

The share page **renders the chat content only when the user is logged into claude.ai**. Logged-out viewers see an app shell without the conversation DOM. Open the URL in a Chrome profile that's already signed in — bh attaches to the user's running Chrome, so this works automatically as long as their profile is logged in.

If the conversation body is empty after navigation, that's the signal you're hitting an unauthenticated session.

## DOM map

Share pages render the conversation as a flat list of sibling `<div>` children inside a single container. There is **no per-turn wrapper element** that includes both messages — turns are alternating siblings.

Stable selectors:

- `[data-testid=user-message]` — user message body (clean text, no prefix)
- `.font-claude-response` — assistant message body
- `[data-testid=page-header]` — first line of `innerText` is the conversation title
- `[data-testid=action-bar-copy]` — per-turn copy button (not needed for export)

Traps to avoid:

- `document.title` returns `"Claude"` — useless for the conversation title; use `[data-testid=page-header]`
- `document.querySelector("h1, h2")` picks up sidebar `Starred` etc — not the chat title
- Each assistant block contains an `H2.sr-only` reading "Claude responded:" — screen-reader only, but `innerText` includes it. Selecting `.font-claude-response` skips it.
- User blocks render a "You said: <preview>" heading separate from the body — `[data-testid=user-message]` returns just the body, so use it directly. Don't use the wrapping turn div's `innerText` or you'll get the preview duplicated.
- `js()` shares a global scope across calls in the same `bh -c` invocation. Wrap extraction in an IIFE — `const`/`let` at top level will collide on re-run. (General bh gotcha, but bites here because you'll iterate selectors.)

## Container-walk pattern

There's no semantic container ID, so find it by walking up from the first user message until you find an ancestor that also contains the last user message:

```javascript
const userMsgs = [...document.querySelectorAll("[data-testid=user-message]")];
let p = userMsgs[0];
while (p && !p.contains(userMsgs[userMsgs.length-1])) p = p.parentElement;
const container = p;
// container.children is now the alternating list of turn divs
```

Then iterate `container.children` and check each child for either `[data-testid=user-message]` (user turn) or `.font-claude-response` (assistant turn). Children that match neither are headers/notices — skip.

## Extraction

A working script lives next to this file: `extract-share-transcript.py`. Run it with:

```bash
CLAUDE_SHARE_URL=https://claude.ai/share/<uuid> \
OUTPUT_DIR=/path/to/transcripts \
bh -c "$(cat agent-workspace/domain-skills/claude-ai/extract-share-transcript.py)"
```

The script reads both via env vars (browser-harness's `-c` doesn't forward extra `argv`, so env vars are the cleanest passthrough).

It produces two files in the output dir, named from the conversation title slug:

- `<slug>.json` — `{title, source_url, turns: [{role, text}]}`
- `<slug>.md` — LLM-friendly transcript with `## Human` / `## Assistant` headers

## What this skill does NOT cover

- Live conversations (`claude.ai/chat/<uuid>`) — different DOM, requires the user's own session and may include streaming/in-progress messages
- Artifacts inside the conversation — captured as plain text only; the artifact panel is a separate iframe-like surface not covered here
- Attachments — the page-header notice mentions "Shared snapshot may contain attachments and data not displayed here"; share exports are text-only by design
