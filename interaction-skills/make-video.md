# Making a video from a recording

Turn a session recording into a short, engaging, Screen-Studio-style video.
You are the editor: read the trace, decide the story, write the composition,
watch your own cut, iterate.

A recording is a folder of numbered JPEG frames + `events.jsonl` — per action:
`helper`, click `x`/`y`, focused-input `box`, typed `text`, `url`, viewport
`w`/`h`, and the post-action `frame` filename.

## Editor's brief

- **Short as possible, no shorter.** Omit `dur` — the template computes a
  readability floor (~3.5 caption words/sec); set it only to go *longer*
  (payoff shots). A 4-minute session ≈ 20s.
- **Hook in 2s.** Title card over the first beat, then straight into action.
  Cut loads, waits, retries, and "result" holds — the next beat's frame
  already shows the result.
- **Ration zooms: 2–4 per video** — opener, first action of a repeated
  pattern, the error/payoff that needs reading. Wide and still is the
  default; the oversized typing overlay keeps typed text readable unzoomed.
- **Frame the reaction, not just the click.** Pages respond elsewhere (cart
  flyout, toast, counter): the zoom must contain the click point AND where
  the `after` frame changes — check the after frame before choosing focus.
  If both don't fit, stay wide.
- **Captions carry the narrative.** Short, present tense, personality over
  literalism ("Plot twist: the cart wasn't empty" > "Deleting item 2 of 3").
  One idea each; not every beat needs one.
- **Mistakes are content — make them unmissable.** `error: true` gives a red
  vignette, ⚠ ERROR chip, shake, red caption pill. Zoom on the *evidence*
  (the wrong text, the failed state) so it's readable; caption it honestly.
  Keep one if you have one.
- **Camera calm beats camera clever.** Consecutive actions in one region get
  the SAME zoom target (zero motion between them). One thing moves at a time
  — the template sequences camera → cursor → click → result for you.
- **End on the payoff + flex**: final state wide, then `outro`/`outroSub`
  ("Done in 4m 28s").

## Beats

`window.COMPOSITION = {title, outro, outroSub, viewport, beats: [...]}` —
schema at the top of the template.

- **Click beat**: the frame *before* the click (previous event's `frame`) +
  `cursor: {x, y}`, `click: true`, `zoom` on that point. The *next* beat
  shows the result frame — the reaction shot.
- **Typing beat**: pre-typing frame + `type: {box, text}` verbatim from the
  event; the template animates the text into the box.
- **Navigation beat**: own frame, wide, with `url` (omnibox text) + `tab`
  (tab title) — the template draws a realistic Chrome window.
- **Hold beat** (`hold: true`): freezes the previous camera on a result frame.
- Coordinates are page CSS px — use event `x`/`y`/`box` verbatim; set
  `viewport: {w, h}` from the events once. Never pre-scale for
  devicePixelRatio: frames are captured at dpr, the template maps CSS px.
- Telemetry is automatic (`STEP k/N` + call chips, click crosshairs); `label`
  overrides (e.g. `'goto("site.com")'`). Set `t` = event `ts` − session start
  to drive the fast session clock — it sells the time compression.

## Workflow

1. Read `events.jsonl`; sketch hook → beats → payoff.
2. `cp interaction-skills/video-template.html <rec>/video.html` (no local
   clone: fetch it from this file's GitHub directory); write
   `<rec>/composition.js`.
3. `cd <rec> && python3 -m http.server 8123 &` — must be http, canvas
   capture fails on `file://` (tainted).
4. Open `http://127.0.0.1:8123/video.html` and **review your cut**: scrub
   every beat boundary with `js("seek(4.2)")` + `capture_screenshot()`.
   Caption overlapping the action? Zoom too tight? Silly cursor path? Fix
   composition.js, reload, re-check — at least one full pass.
5. `js("exportVideo('my-video.webm')")` — plays once in realtime (30s video
   takes 30s), downloads to Chrome's download dir. Keep the tab focused
   (background tabs stall rendering), wait ~duration+2s, confirm
   `js("window.__exported")`, move the file where the user wants it.
6. Kill the server; tell the user the path.

Missing frame → that beat renders black; the HUD bottom-left shows
playhead/beat. mp4 wanted? `ffmpeg -i video.webm -c:v libx264 -crf 20
video.mp4` (webm/vp9 is the native output).
