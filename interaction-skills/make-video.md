# Make a video

Use captured frames as evidence. Never reenact a finished task or fabricate a
cleaner result.

## Workflow

Use the exact recording selected under `SKILL.md`; never replay browser work to
manufacture missing footage. For a post-task recording, verify `meta.json` and
`events.jsonl` match the task.

```bash
browser-harness video init <recording> --require-explicit
# write <recording>/edit-brief.json
browser-harness video review <recording>
# inspect video-review-contact-sheet.jpg and every image in .privacy-review/
browser-harness video export <recording> --reviewed
```

Omit `--require-explicit` only for a verified post-task recording. In a source
checkout use `./browser-harness`. Never edit generated `composition.js` or
`video.html`; change the brief or shared implementation. Export never
overwrites an existing video, so use `--output video-v2.mp4` for another cut.

## Cut

- Optimize for first-time comprehension; the raw trace is the debugging
  artifact. Start with the task and a 2–5 step plan, then end on verified
  outcomes.
- Build one causal chain: intent → action → visible result. Remove waits,
  retries, and repetition that add no understanding, but show every item or
  state explicitly claimed by the outcome.
- Narration is optional and sticky. Set a short present-tense thought only when
  it changes, then omit `narration` while 2–3 screenshots advance underneath
  it. Text and screenshots should not share a mechanical cadence.
- Preserve representative captured clicks, cursor motion, typing, and result
  frames. Pair clicks with `afterEvent`; use `context: true` only to orient.
- Keep a useful wrong turn when it changed the approach. Explain it once as
  Observed → Mistake → Correction; remove failures that teach nothing.
- Keep raw frames unlabelled. Subtitles and progress stay outside the app.
  Use semantic routes and let the compiler own timing, camera, motion, and
  visual style. The 22-second budget and 380 WPM cards are pause-friendly.

## Edit brief

Events are one-based entries in `recording-summary.json`; chapters are
zero-based plan entries. `frameEvent` may select a cleaner pre-action frame and
`afterEvent` should show the click result.

```json
{
  "task": "Extract the top five stories and comments",
  "summary": "Collect each discussion and save structured JSON.",
  "plan": ["Collect stories", "Capture discussions", "Verify JSON"],
  "actions": [
    {
      "event": 3,
      "frameEvent": 2,
      "afterEvent": 4,
      "chapter": 0,
      "route": "Hacker News / Front page",
      "afterRoute": "Hacker News / Discussion",
      "narration": "Open the first discussion.",
      "label": "Open discussion"
    },
    {
      "event": 8,
      "afterEvent": 9,
      "chapter": 1,
      "route": "Hacker News / Discussion",
      "afterRoute": "Hacker News / Next discussion",
      "label": "Continue in rank order"
    }
  ],
  "explanations": [{
    "afterAction": 2,
    "title": "Why the first approach failed",
    "observed": "Navigation links appeared in the result",
    "mistake": "I selected every page link",
    "correction": "Restrict extraction to story rows"
  }],
  "outcomeTitle": "Five discussions captured",
  "outcomeSummary": "The requested JSON is verified.",
  "outcomes": ["Five current stories saved", "Comment trees preserved"],
  "privacy": {
    "reviewedFrames": ["0002.jpg", "0004.jpg", "0008.jpg", "0009.jpg"],
    "redact": {"0004.jpg": [{"x": 10, "y": 10, "w": 120, "h": 32}]}
  }
}
```

Keep only actions that change the viewer's understanding. Each action requires
`event`, `chapter`, and a short semantic `route`; optional fields are
`frameEvent`, `afterEvent`, `afterRoute`, `narration`, `label`, `detour`,
`error`, `context`, and `showTyping`. Narration is at most seven words; when
omitted, the previous narration persists across the new screenshot.
Explanations reveal Observed → Mistake → Correction. Outcomes must be verified.

Typed text is hidden unless inspected and explicitly enabled with
`showTyping: true`; passwords cannot be revealed. Private app URLs, identities,
credentials, tokens, tenant data, and unrelated people stay private. Use opaque
redaction rectangles in page coordinates and list every used frame in
`privacy.reviewedFrames` only after inspecting its final full-resolution image.
Public task evidence such as authors, post text, and link domains may remain.
The detector is a backstop, not a privacy guarantee.
