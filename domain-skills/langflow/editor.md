# Langflow editor and custom input nodes

These notes apply to the native Langflow canvas/Playground, not a separate
application built on its API. Check the installed version before assuming the
same component schema.

## Navigation and saved state

- Canvas routes are `/flow/<flow-id>`, sometimes followed by `/folder/<folder-id>`.
- The canvas is React Flow. A readable DOM locator for inspection is
  `.react-flow__node[data-id="<node-id>"]`; controls and their positions depend on
  viewport pan/zoom. Use screenshots and compositor clicks for interaction.
- A node can be outside the viewport even though its DOM element exists. Pan
  an empty canvas area to bring the relevant region into view, then zoom around
  the visible node. Do not drag a node header when intending to pan.
- Opening a flow in a new tab preserves an older tab's unsaved editor state.
  A server-side update does not replace the old tab's in-memory graph. Beware
  of saving that stale tab over a newer flow.

## Component updates and dynamic fields

- Nodes store an embedded Python code string and input values in
  `data.node.template`; a server image update alone does not replace those copies.
- Authenticated administrators can validate/build a component template with
  `POST /api/v1/custom_component`, body `{"code":"..."}`. The response includes
  `type` and `data` (the frontend node definition). This instantiates code; use
  trusted source and the deployment's authorization policy.
- `POST /api/v1/custom_component/update` drives dynamic field changes. After
  selecting a dropdown with `real_time_refresh`, allow the request to finish
  before concluding that new fields failed to appear. The initial screenshot
  can still show the preceding configuration.
- A deliberately customized built-in node should carry `data.node.edited=true`.
  Otherwise the editor can present it as an ordinary outdated built-in and
  offer a replacement that loses the custom behavior. Do not blindly choose
  **Update All** when reviewing intentional customizations.
- Retaining a native `ChatInput` identity is useful when customizing its form:
  the Playground frontend explicitly looks for `data.type === "ChatInput"`.
  Returning a `Message` from an arbitrary custom type alone is not equivalent.

## Before-unload dialogs with multiple CDP sessions

When more than one flattened session is attached to a page, a dialog-opening
event may be visible to several sessions. A newly attached session can answer
`No dialog is showing` even while the initiating page remains paused.

Inspect buffered events with `drain_events()`, find
`Page.javascriptDialogOpening` for the intended frame, and pass its
`session_id` explicitly to `cdp("Page.handleJavaScriptDialog", session_id=...,
accept=False)` to cancel navigation without discarding editor changes. Prefer
the session that received the original opening event. Do not treat a failed
handle attempt on another session as evidence that the editor is usable.

Avoid logging unrelated network events, headers, cookies, or saved flow data
while diagnosing this; the latter can contain credentials and private inputs.
