# Browser Harness MCP Server

The MCP server in `mcp_server.py` exposes `browser_harness.helpers` as MCP tools.
It reuses the existing helper layer — no second CDP implementation and no changes
inside `src/browser_harness/`.

## Start

From the repo root:

```bash
uv run --extra mcp python -m mcp_server
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
- `browser_set_value`
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
- `browser_start_recording`
- `browser_stop_recording`

Every tool returns JSON text. On error the response is `{"error": "..."}` and the
server process keeps running.

## Example flow

1. `browser_new_tab(url="https://example.com")`
2. `browser_wait_for_load()`
3. `browser_screenshot()` → returns `path`, `width`, `height`, `size_bytes`
4. `browser_page_info()` → returns `url`, `title`, viewport/scroll/page size

## Client configuration

Replace `<path-to-repo>` with your checkout path.

### Claude Code

```bash
claude mcp add browser-harness \
  uv --directory <path-to-repo> run --extra mcp python -m mcp_server
```

### Devin

```bash
devin mcp add -s project browser-harness -- \
  uv --directory <path-to-repo> run --extra mcp python -m mcp_server
```

### Cursor / OpenClaw / other MCP clients

```json
{
  "mcpServers": {
    "browser-harness": {
      "command": "uv",
      "args": [
        "--directory",
        "<path-to-repo>",
        "run",
        "--extra",
        "mcp",
        "python",
        "-m",
        "mcp_server"
      ]
    }
  }
}
```

### MCP Inspector

```bash
npx @modelcontextprotocol/inspector \
  uv --directory <path-to-repo> run --extra mcp python -m mcp_server
```
