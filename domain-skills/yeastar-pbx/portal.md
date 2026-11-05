# Yeastar P-Series web portal (self-hosted PBX admin)

Ant Design v3-era React SPA. Field-tested quirks that cost real debugging time:

## Saving — the big trap

- **JS-dispatched `.click()` on Save can silently discard the form**: the UI
  returns to the list view with no error and no persistence. A real
  coordinate click on the Save button saves and shows an "Operation
  Succeeded" toast. Always verify persistence by reopening the record, not
  by trusting navigation.
- Most changes also need the orange **Apply** button (top bar) after Save.
- Navigating away (or a daemon-restart page reload) discards unsaved form
  state with no warning.

## Inputs

- **Native-setter value injection binds visually but not to the form
  model** on many forms (masked inputs like DID patterns, emergency caller
  ID). Use: focus + `element.select()` + CDP `Input.insertText` — or plain
  clicks and typing. Three separate clicks do NOT select-all; they reposition
  the caret and insertText appends.
- Time pickers are antd-v3 3-column (`.ant-time-picker-panel` with `ul>li`
  columns: hour/minute/AM-PM); typed text is rejected. Click the `li` cells;
  values commit per-click. Close the panel by clicking a neutral area — the
  panel swallows the next click otherwise.
- Selects are `.ant-select`; options render into a detached
  `.ant-select-dropdown`. A dropdown that won't open usually means a leftover
  invisible `.ant-modal-wrap` overlay is eating clicks — check
  `document.elementFromPoint`, click `.ant-modal-close`, retry.

## Uploads

- File dialogs can be bypassed: click the Upload button, then
  `DOM.setFileInputFiles` on the revealed `input[type=file]`. Prompt/greeting
  audio must be wav/mp3/gsm ≤8MB (PCM 8k 16-bit accepted).

## Structure

- Sessions idle out within minutes; expect the login page on return.
- URL routes are path-based (e.g. `/call_control/inbound_routes`,
  `/call_features/voicemail`, `/call_control/emergency_number`) and
  deep-link fine after login.
- List rows expose `[class*=ops-edit]` icons — DOM-clickable, unlike Save.
- Inbound-route ordering is drag/arrow-only in the UI and impossible via the
  OpenAPI; new routes append below the catch-all default.
