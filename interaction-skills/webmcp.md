# WebMCP — calling page-exposed tools via `navigator.modelContext`

Some sites ship **WebMCP**: the page registers agent-callable tools on `navigator.modelContext`. Instead of scraping the DOM or hand-driving clicks, you discover the tool, read its JSON Schema, and call it — the page's own handler does the work (fill a form, run a search, etc.). Treat it the same way you'd treat a private API: prefer it over DOM automation when it's there.

## Detect

```python
res = js(r'''(() => {
  const mc = window.navigator && navigator.modelContext;
  if (!mc) return {webmcp: false};
  return {webmcp: true, api: Object.getOwnPropertyNames(Object.getPrototypeOf(mc) || {})};
})()''')
print(res)
# {'webmcp': True, 'api': ['ontoolchange', 'executeTool', 'getTools', 'registerTool', 'constructor']}
```

The empty enumerable-keys case is normal — the surface lives on the prototype (`getTools`, `executeTool`, `registerTool`, `ontoolchange`).

## List the registered tools

`getTools()` may be sync or return a Promise — handle both. Each tool has `name`, `description`, and `inputSchema` (a JSON Schema; **often a JSON-encoded *string*, not an object** — parse it).

```python
import json
res = js(r'''(async () => {
  const mc = navigator.modelContext;
  let tools = mc.getTools();
  if (tools && typeof tools.then === 'function') tools = await tools;
  return (tools || []).map(t => ({name: t.name, description: t.description, inputSchema: t.inputSchema}));
})()''')
tools = res
for t in tools:
    schema = t["inputSchema"]
    if isinstance(schema, str):
        schema = json.loads(schema)   # inputSchema arrives as a JSON string
    print(t["name"], "→ required:", schema.get("required"))
```

The schema's `required` array tells you exactly which inputs the tool needs — use it to drive a conversational "ask the user for the missing fields" flow before calling.

## Execute a tool — two non-obvious gotchas

`navigator.modelContext.executeTool` is **not** `executeTool(name, argsObject)`. Field-tested against Chrome's implementation (June 2026):

1. **First arg must be the `RegisteredTool` object itself** (the entry you got back from `getTools()`), **not** the tool name as a string. Passing a string → `TypeError: The provided value is not of type 'RegisteredTool'`.
2. **Second arg must be a JSON *string*** of the arguments, **not** a JS object. Passing an object → `UnknownError: Failed to parse input arguments`.

```python
import json
args = {"field_a": "value", "flag": True}

res = js(r'''(async (argsJson) => {
  const mc = navigator.modelContext;
  let tools = mc.getTools();
  if (tools && typeof tools.then === 'function') tools = await tools;
  const tool = tools.find(t => t.name === 'TOOL_NAME_HERE');
  if (!tool) return {ok: false, err: 'tool not found'};
  try {
    let r = mc.executeTool(tool, argsJson);   // (RegisteredTool, jsonString)
    if (r && typeof r.then === 'function') r = await r;
    return {ok: true, result: r};
  } catch (e) { return {ok: false, err: String(e)}; }
})(%s)''' % json.dumps(json.dumps(args)))   # double-encode: a JS string literal holding JSON
print(res)
```

The handler typically returns MCP-shaped content, e.g.
`{"content": [{"type": "text", "text": "..."}]}` — also often a JSON string, so parse it.

## Verify, don't trust the return value

WebMCP handlers may **intentionally not echo** what they did (privacy: "no entered values are returned"). After calling a tool that fills a form, confirm by reading the DOM yourself rather than relying on the result text:

```python
res = js(r'''(() => {
  const out = [];
  document.querySelectorAll('input,select,textarea').forEach(el => {
    if (el.type === 'hidden') return;
    out.push({name: el.name || el.id, value: (el.type==='checkbox'||el.type==='radio') ? el.checked : el.value});
  });
  return out.filter(o => o.value !== '' && o.value !== false);
})()''')
print(res)
```

## Traps

- `inputSchema` and tool results are **JSON-encoded strings** as often as not — always `json.loads` defensively.
- `getTools()` / `executeTool()` may be sync or async — always guard with `typeof r.then === 'function'`.
- A well-behaved form-filling tool **won't submit** (it leaves CAPTCHA + submit to the human). Don't expect a success/redirect — verify field state instead.
- Tools can change at runtime; `ontoolchange` fires on re-registration. Re-`getTools()` if a tool you expected is missing.
- Cross-tab isolation: `navigator.modelContext` only exists in the tab that registered it. You reach it here because the harness runs JS *in that page* over CDP — a separate browser/agent tab cannot see another tab's `modelContext`.
