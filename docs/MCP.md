# Browser Harness MCP Server

`browser-harness mcp` exposes the browser helpers as MCP tools. It reuses the
same helper layer as snippets, so there is no second CDP implementation.

## Start

From any directory:

```bash
browser-harness mcp
```

The server speaks MCP stdio and connects to the same local Chrome CDP endpoint
(9222/9223) used by `browser-harness`. The daemon auto-starts on the first tool
call.

## Tools

The browser control helpers are exposed as MCP tools with a `browser_` prefix:

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

### Claude Code

```bash
claude mcp add browser-harness -- browser-harness mcp
```

### Devin

```bash
devin mcp add -s project browser-harness -- browser-harness mcp
```

### Cursor / OpenClaw / other MCP clients

```json
{
  "mcpServers": {
    "browser-harness": {
      "command": "browser-harness",
      "args": ["mcp"]
    }
  }
}
```

### MCP Inspector

```bash
npx @modelcontextprotocol/inspector browser-harness mcp
```

From a repository checkout, `./browser-harness mcp` runs the same server built
from the current source.
