# Permissions & OS-native popups

Chrome renders permission prompts, file pickers, and print dialogs in **browser chrome**,
not in the page. They are invisible to CDP page screenshots, and
`Input.dispatchMouseEvent` coordinates go to the viewport — they can't click the popup.

CDP event coverage is uneven: `Page.javascriptDialogOpening` (alerts + beforeunload),
`Page.fileChooserOpened` (requires `Page.enable({enableFileChooserOpenedEvent: true})`),
and `Page.downloadWillBegin` do fire. **Permission popups (geolocation, notifications,
camera/mic, ...) emit no CDP event at all** — which is why the harness injects an
in-page wrapper to surface them.

Two things to know:

1. **Pre-empt them.** `Browser.grantPermissions` + `Emulation.setGeolocationOverride`
   resolve the common cases without ever showing a popup.
2. **Detect them.** If one is already open, `page_info()` surfaces a `blockers` key, and
   `pending_blockers()` returns the full log.

## Detection

`page_info()` auto-surfaces blockers. After the usual viewport keys:

```python
info = page_info()
if info.get("blockers"):
    # popup was triggered — Chrome is waiting for the user (or you via CDP)
    print(info["blockers"])
```

`pending_blockers()` gives the full picture, split by source:

```python
b = pending_blockers()
# b["js"]  — permission-gated Web API calls: geolocation, notifications,
#            mediaDevices, clipboard, bluetooth/usb/serial/hid, file pickers,
#            print, requestStorageAccess, <input type=file> clicks
# b["cdp"] — Page.javascriptDialogOpening, Page.fileChooserOpened,
#            Page.downloadWillBegin (fires without JS injection)
```

Why both? Chrome emits **no** CDP event when a permission popup opens, so the daemon
installs a JS wrapper on every document that pushes to `window.__bu_blockers__`. CDP-side
events are captured directly via the event tap.

## Pre-grant — the preferred pattern

Grant at the browser level; the popup never needs to render. Scope is the CDP session,
which maps to "Allow this time" semantics (resets on daemon restart / CDP disconnect).

```python
cdp("Browser.grantPermissions",
    origin="https://www.example.com",
    permissions=["geolocation"])

# For geolocation specifically, pair with an override so the site actually
# receives coords — otherwise Chrome may fall back to OS Core Location, which
# requires a separate macOS-level grant.
cdp("Emulation.setGeolocationOverride",
    latitude=37.7749, longitude=-122.4194, accuracy=50)
```

Permission names: `geolocation`, `notifications`, `videoCapture`, `audioCapture`,
`clipboardReadWrite`, `clipboardSanitizedWrite`, `backgroundSync`, `midi`, `midiSysex`,
`periodicBackgroundSync`, `protectedMediaIdentifier`, `sensors`, `storageAccess`,
`durableStorage`, `paymentHandler`, `backgroundFetch`, `nfc`, `idleDetection`,
`displayCapture`, `captureHandle`, `wakeLockScreen`, `wakeLockSystem`, `windowManagement`,
`localFonts`, `topLevelStorageAccess`.

```python
cdp("Browser.resetPermissions")          # back to 'prompt' for all origins
```

`Browser.setPermission` is the finer-grained alternative — sets one permission at a
time with explicit `setting: 'granted' | 'denied' | 'prompt'`, useful for toggling
mid-session or explicitly denying:

```python
cdp("Browser.setPermission",
    permission={"name": "geolocation"},
    setting="denied",
    origin="https://www.example.com")
```

## Dismissing a popup that already opened

`Browser.grantPermissions` updates the permission *state* but does **not** close an
already-rendered popup. Easiest path: reload the page after granting.

```python
cdp("Browser.grantPermissions", origin=..., permissions=["geolocation"])
cdp("Emulation.setGeolocationOverride", latitude=..., longitude=..., accuracy=50)
cdp("Page.reload")
wait_for_load()
# next navigator.geolocation.getCurrentPosition call returns the overridden coords, no popup.
```

## Proactive state check

`navigator.permissions.query({name: 'geolocation'}).state` returns
`'prompt' | 'granted' | 'denied'` without triggering anything. If it's `'prompt'` and
the site is about to ask, a popup **will** appear — pre-grant before calling the API.

## Rules that held up in practice

- **Native popups are outside the viewport.** `screenshot()` can't see them; use `screencapture -x` on macOS if you need visual proof.
- **Pre-grant beats reactive handling.** `Browser.grantPermissions` before the trigger means no popup, no detection overhead, no race.
- **`Emulation.setGeolocationOverride` is required** when Chrome lacks OS-level Core Location permission — otherwise granted-but-unresolvable requests time out.
- **The wrapper script is installed on every new document** via `Page.addScriptToEvaluateOnNewDocument`. Don't rely on it for iframes attached via a different session (install there too if needed).
- **Callback-based APIs (`getCurrentPosition`) don't resolve promises** the wrapper can hook. A blocker entry means "the site called this" — not "the popup is still open". Use timestamps + state inspection to judge.
- **File pickers from `<input type=file>` clicks** are caught by a capture-phase click listener, not by wrapping. Prefer `upload_file(selector, path)` (CDP `DOM.setFileInputFiles`) to avoid opening the native chooser at all.
- **`Page.setInterceptFileChooserDialog` suppresses the native chooser.** The harness does not enable interception by default — turning it on breaks any normal file-input flow, so only enable per-task if you plan to respond to `Page.fileChooserOpened` yourself.
