# ChatGPT — Composer, mentions and the thread DOM

`https://chatgpt.com` — logged-in React app. Use the user's own Chrome (login lives there).

## Composer

- The composer is a ProseMirror editor, `#prompt-textarea`. `js("...focus()")` does **not** make `type_text` land; `click()` the composer's center first, then `type_text`.
- `#prompt-textarea` can be missing for a moment after `goto("https://chatgpt.com/")` even after `wait_for_load()`; screenshot, then click where the composer is drawn.
- Long prompts make the composer grow from one row to two after ~1 s. Screenshot after it settles.

## @-mentions (plugins, GPTs)

- Typing `@` plus a few letters opens a picker (sections "Plugins", "Custom GPTs", "Files").
- **Trap: pressing Enter on the highlighted picker row selects it and sends the message at once**, with only the mention and none of the text typed afterwards. Click the row instead: find it by its description text (e.g. a TreeWalker for the plugin's tagline) and `click()` its center. Then type the rest of the prompt and press Enter.

## Reading a conversation

- The DOM keeps hidden copies of views: there can be several `main` elements and several `.thread-scroll-container`s, most with a zero-size rect. Filter by `getBoundingClientRect().height > 0` before reading or scrolling.
- `[data-message-author-role]` is not reliable on the current build. Answers render through a generative-UI renderer: the root is `[data-dil-response]`, blocks carry `data-d-component` (`text`, `title`, `box`, `row`, `list`, `list-item`, `table`, `code`). The streamed preamble before tool calls is also a `[data-dil-response]`; the answer is the last one.
- Stages of a reply, as text in the visible `main`: `Thinking` → preamble → a status line (`Analyzing …`) → `Worked for Ns` (collapsible) → the answer → an action row (`.turn-action-controls`). While streaming, the composer's send button is a stop button.
- Turns are virtualized: wrappers get inline `height: Npx` from measured content, so a cloned DOM with edited text keeps the old heights.

## Styles and assets

- All stylesheets are same-origin: `[...document.styleSheets].map(s => [...s.cssRules].map(r => r.cssText))` returns the full CSS (≈3 MB). Some animations are scroll-driven (`anim.timeline` is not a `DocumentTimeline`); setting `currentTime` on those throws.
- Icons are `<use href="/cdn/assets/icons-<hash>.svg#id">`; the sprite URL is on `<html data-icon-sprite-url>`.
- Theme comes from attributes on `<html>` (`class`, `data-theme`, `data-appearance-preset`, inline CSS variables).

## Small windows

`cdp("Emulation.setDeviceMetricsOverride", width=800, height=450, deviceScaleFactor=1.5, mobile=False)` gives the desktop layout with the sidebar collapsible to a 52 px rail. The override outlives your script: `Emulation.clearDeviceMetricsOverride` from a new session does not remove it; restarting the daemon (which detaches the session that set it) does.
