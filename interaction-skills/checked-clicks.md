# Check a node before clicking

Use this when a normal DOM control is offscreen, covered, or has changed since
the last observation. Keep the target and backend node ID from the same fresh
AX snapshot. Re-observe after navigation or a re-render.

Copy this small recipe into `agent-workspace/agent_helpers.py` when needed.
It uses an explicit CDP session for every operation. It rejects detached,
renamed, disabled, hidden, covered, iframe, and shadow-root nodes. A failed
check sends no mouse input. Raw coordinate clicks remain useful for canvas.

```python
def checked_click(session_id, backend_node_id, expected_role, expected_name):
    def send(method, **params):
        return cdp(method, session_id=session_id, **params)

    obj = send("DOM.resolveNode", backendNodeId=backend_node_id)["object"]["objectId"]
    try:
        send("DOM.scrollIntoViewIfNeeded", backendNodeId=backend_node_id)
        nodes = send("Accessibility.getPartialAXTree", backendNodeId=backend_node_id,
                     fetchRelatives=False)["nodes"]
        node = next((n for n in nodes if n.get("backendDOMNodeId") == backend_node_id), None)
        if (not node or node.get("ignored") or
                node.get("role", {}).get("value") != expected_role or
                node.get("name", {}).get("value") != expected_name):
            raise RuntimeError("Node changed; take a fresh AX snapshot")
        result = send("Runtime.callFunctionOn", objectId=obj, returnByValue=True,
                      functionDeclaration="""function() {
            if (!this.isConnected) return {error: 'Node detached'};
            if (window !== window.top || this.ownerDocument !== document ||
                this.getRootNode() !== document)
                return {error: 'Recipe supports the top document only'};
            if (this.matches(':disabled') || this.closest('[aria-disabled="true"], [inert]'))
                return {error: 'Node disabled'};
            if (!this.checkVisibility({checkOpacity:true, checkVisibilityCSS:true}))
                return {error: 'Node hidden'};
            const r = this.getBoundingClientRect();
            const x = r.x + r.width/2, y = r.y + r.height/2;
            if (r.width <= 0 || r.height <= 0 || x < 0 || y < 0 ||
                x >= innerWidth || y >= innerHeight) return {error: 'Node outside viewport'};
            const hit = document.elementFromPoint(x, y);
            if (!hit || (hit !== this && !this.contains(hit))) return {error: 'Node covered'};
            return {x, y};
        }""")
        if result.get("exceptionDetails"):
            raise RuntimeError("Click check failed; inspect the page before retrying")
        point = result.get("result", {}).get("value")
        if not point or "error" in point:
            raise RuntimeError((point or {}).get("error", "Click check returned no point"))
        # Always attempt release if press was sent; preserve the original error.
        try:
            send("Input.dispatchMouseEvent", type="mousePressed", button="left",
                 clickCount=1, x=point["x"], y=point["y"])
        except BaseException:
            try:
                send("Input.dispatchMouseEvent", type="mouseReleased", button="left",
                     clickCount=1, x=point["x"], y=point["y"])
            except BaseException:
                pass
            raise
        send("Input.dispatchMouseEvent", type="mouseReleased", button="left",
             clickCount=1, x=point["x"], y=point["y"])
    finally:
        try:
            send("Runtime.releaseObject", objectId=obj)
        except Exception:
            pass
```

Attach to the intended target, inspect, click once, then verify the actual
effect through that same session. Example for a synchronous local control:

```python
target_id = current_tab()["targetId"]
sid = cdp("Target.attachToTarget", targetId=target_id, flatten=True)["sessionId"]
try:
    nodes = cdp("Accessibility.getFullAXTree", session_id=sid)["nodes"]
    matches = [n for n in nodes if n.get("role", {}).get("value") == "button"
               and n.get("name", {}).get("value") == "Save"]
    assert len(matches) == 1, "Choose the intended control explicitly"
    checked_click(sid, matches[0]["backendDOMNodeId"], "button", "Save")
    result = cdp("Runtime.evaluate", session_id=sid, returnByValue=True,
                 expression="document.querySelector('#status')?.textContent === 'Saved'")
    assert not result.get("exceptionDetails") and result["result"].get("value") is True
finally:
    cdp("Target.detachFromTarget", sessionId=sid)
```

For async effects, poll the specific postcondition on `sid` with a deadline.
Do not repeat a click because its result is uncertain. Inspect the outcome first.
The page can still change between the final hit test and mouse dispatch; this
recipe reduces stale/covered clicks and does not make a click atomic. If a page
animates or changes that quickly, wait for it to settle and re-observe.
