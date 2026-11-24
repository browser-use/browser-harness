# Browser Harness MCP Server

The `browser-harness-mcp` command exposes `browser_harness.helpers` as MCP tools.
It reuses the existing helper layer — no second CDP implementation and no changes
inside `src/browser_harness/`.

## Start

From any directory:

```bash
uvx --from 'browser-harness[mcp]' browser-harness-mcp
```

The server speaks MCP stdio and connects to the same local Chrome CDP endpoint
(9222/9223) used by `browser-harness`. The daemon auto-starts on the first tool
call.

## Tools

The browser control helpers from `browser_harness.helpers` are exposed as MCP
tools with a `browser_` prefix:

- `browser_new_tab`
- `browser_goto`
- `browser_page_info`
- `browser_click`
- `browser_type`
- `browser_fill`
- `browser_press`
- `browser_scroll`
- `browser_screenshot`
- `browser_list_tabs`
- `browser_current_tab`
- `browser_switch_tab`
- `browser_close_tab`
- `browser_ensure_real_tab`
- `browser_wait`
- `browser_wait_for_load`
- `browser_wait_for_element`
- `browser_js`
- `browser_cdp`
- `browser_upload_file`
- `browser_http_get`
- `browser_solve_captcha`
- `browser_start_recording`
- `browser_stop_recording`

Every tool returns JSON text. On error the response is `{"error": "..."}` and the
server process keeps running.

On a Browser Use Cloud browser, a result can have a second text block (or, on
error, end) with `[Captcha solver ...]` lines: a solve is running (wait with
`browser_solve_captcha`; do not reload or navigate) or one just finished.
`BU_CAPTCHA_SOLVER=off` stops `browser_solve_captcha` from switching the solver
on; it does not switch off a solver the browser already has on.

Two more tools need no browser:

- `browser_feedback(message, category)`: tells the Browser Use team what broke in
  browser-harness or what would make it better. Sent even when telemetry is off.
- `browser_report_run(success, failure_reason, gotchas, bot_block)`: the agent's
  own verdict on its task, once at the end. Sent only when telemetry is on.

Each sends at most 3 times per server process. `BROWSER_USE_OFFLINE=1` stops
both; `BROWSER_USE_ZDR=1` sends them without their texts. See the 0.1.14 entry in
`CHANGELOG.md` for exactly what is sent.

## Example flow

1. `browser_new_tab(url="https://example.com")`
2. `browser_wait_for_load()`
3. `browser_screenshot()` → returns `path`, `width`, `height`, `size_bytes`
4. `browser_page_info()` → returns `url`, `title`, viewport/scroll/page size

## Client configuration

### Claude Code

```bash
claude mcp add browser-harness \
  uvx --from 'browser-harness[mcp]' browser-harness-mcp
```

### Devin

```bash
devin mcp add -s project browser-harness -- \
  uvx --from 'browser-harness[mcp]' browser-harness-mcp
```

### Cursor / OpenClaw / other MCP clients

```json
{
  "mcpServers": {
    "browser-harness": {
      "command": "uvx",
      "args": [
        "--from",
        "browser-harness[mcp]",
        "browser-harness-mcp"
      ]
    }
  }
}
```

### MCP Inspector

```bash
npx @modelcontextprotocol/inspector \
  uvx --from 'browser-harness[mcp]' browser-harness-mcp
```

From a repository checkout, `uv run --extra mcp browser-harness-mcp` runs the
same packaged entry point against the current source.
