---
name: framer-editor
description: Framer.com web editor (framer.com/projects/...) — DOM selectors, Monaco code-editor workflow, publish quirks, and the things Framer's React canvas will not let automation touch.
---

# Framer — web editor

Framer is a visual web builder with a code-editor side (Monaco) and a React-canvas side. Automation lives where both meet: DOM interactions succeed on the shell, but the canvas rejects synthetic events on many widgets.

URL shape: `https://framer.com/projects/<project-slug>-<id>` (teamId query param after login). The left rail is tab-driven; the right rail is context-sensitive.

## Stable DOM selectors (verified April 2026)

| Purpose | Selector |
|---|---|
| Pages tab (left rail) | `[data-testid="pages-tab"]` |
| Layers tab | `[data-testid="layers-tab"]` |
| Assets tab | `[data-testid="assets-tab"]` |
| Page row in Pages panel | `[data-testid="page-row"]` |
| Asset row in Assets panel | `[data-testid="asset-row"]` |
| Monaco code editor input | `.monaco-editor textarea` |
| Monaco rendered lines | `.view-line` |
| Monaco error underlines | `.squiggly-error` |
| Project menu button | `[data-testid="projectbar-menu-button"]` |

Prefer `data-testid` over CSS-module class names — the latter are minified and change across deploys.

## Opening a code file in Monaco

Single-click on an `asset-row` only selects it; you need a double-click to open the editor. A plain `element.click()` is not enough — the canvas listens for a full pointer+mouse event chain:

```javascript
const row = document.querySelector('[data-testid="asset-row"][title="VacaturesApp"]');
for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
  row.dispatchEvent(new MouseEvent(type, {bubbles: true, cancelable: true, view: window}));
}
row.dispatchEvent(new MouseEvent('dblclick', {bubbles: true, cancelable: true, view: window, detail: 2}));
```

`detail: 2` matters — without it, Framer treats it as two unrelated single-clicks.

## Pasting into Monaco

Monaco does not accept programmatic `.value =` — it ignores the assignment. The reliable path is clipboard + keystroke:

1. Put the new file contents on the clipboard (e.g. via `pbcopy` on macOS or an OS-level clipboard write).
2. Focus the Monaco textarea: `document.querySelector('.monaco-editor textarea').focus()`.
3. OS-level `Cmd+A` (select all) → `Cmd+V` (paste).
4. **Wait ~3 seconds**. Monaco applies the paste asynchronously; saving before the paste commits produces an empty file.
5. OS-level `Cmd+S` to save.
6. Verify: scroll to top (`Cmd+Up`), dump `document.querySelectorAll('.view-line')` text content, and confirm `document.querySelectorAll('.squiggly-error').length === 0`.

The OS-level keystrokes require an accessibility-permitted input path (macOS System Events, Linux xdotool, etc.). JS-dispatched `KeyboardEvent` does not trigger Monaco's bindings.

## The Publish button

The green **Publish** button in the top-right is only rendered when a page is selected in the Pages tab. While you are inside the Monaco code editor, the button is absent from the DOM. The workflow that works:

1. Pages tab → click the page you want to publish.
2. **Now** the Publish button is mounted.
3. Click it by screen coordinates (via OS-level click), not by synthetic event — the React handler on that button ignores JS-dispatched clicks.

This is the single most common "automation silently did nothing" trap in Framer.

## Right-click / context menus

```javascript
row.dispatchEvent(new MouseEvent('contextmenu', {
  bubbles: true, cancelable: true, view: window,
  button: 2, buttons: 2,
}));
```

The menu renders into a portal; it is not a child of `row`. Navigate items with OS-level arrow-down keystrokes (`key code 125` via AppleScript `System Events`) + Return. Rename flow: context menu → Rename → `Cmd+A` → type new name → Return.

## What Framer will not let automation do

These are canvas-level React interactions that reject synthetic events or use modal right-panel state that is not DOM-traversable:

- **Drag-drop** — component insertion, layer reordering, cross-hierarchy moves.
- **Smart Component variant switching** — the On Tap → Change Variant setup lives in a modal nested panel; no stable selector path.
- **Property binding** (the chain icon on a code-component prop) — exposes only `Fetch (HTTP)` and `Create Variable`; no CMS-field binding available from the UI, let alone scriptable.
- **Page Settings** (SEO title / description / canonical / OG image / "Search Engines" toggle / draft/publish state) — right-rail Page Settings panel is not DOM-automatable.
- **Custom Code Page Settings** (`<head>` injection) — static-only input, does not accept CMS tokens.
- **Site Settings → Redirects** — exact-match only, no wildcards; UI-only.
- **Font uploads, image drops** — filesystem drag source.

For any of these: stop and hand a clickable step-by-step to the human, with selectors for the rail/panel where possible.

## Framer autolayout on Header-like nodes

When a parent node has autolayout + a positioned Header child, any programmatic attempt to set `position`, `left`, or `right` on the Header through Framer's MCP / XML-update API triggers autolayout to force the Header to `left="-1293px"` or similar, visually losing it. The working pattern is "delete the Header, then copy a working one from a known-good page in the same project via `Cmd+C` / `Cmd+V`." This is Framer autolayout preempting your value, not a bug in your update call.

## Edge cache after publish

After a successful publish, `curl` against the live domain may serve stale HTML for 30–60 seconds. For verification, append a cache-buster query param — any unused param works: `?v=<timestamp>`. This doesn't touch Framer's generated routes; it just forces the CDN to fetch a fresh copy.

## Sitemap / robots / redirects observations

- **`/sitemap.xml`** — autogenerated. Static pages only. URLs with query parameters are **not** included. For dynamic routes (`/foo?slug=...`) you must submit them to Google Search Console manually.
- **`robots.txt`** — proxied through Cloudflare on Framer-hosted domains; the default config blocks AI crawlers (Amazonbot, ClaudeBot, GPTBot, Bytespider) while allowing Google.
- **Custom redirects** — exact match only. No regex, no wildcards. Configure in Site Settings → Redirects, one at a time.

## Prerequisites for automation on macOS

- Chrome: "View → Developer → **Allow JavaScript from Apple Events**" checked.
- System Settings → Privacy → **Accessibility** → grant to whichever process drives keystrokes (node, osascript, browser-harness wrapper).
- Framer tab must exist in the front Chrome window; the editor does not tolerate off-screen or backgrounded tabs well during paste flows (Monaco loses focus).
