# Screenshots

`capture_screenshot()` writes a PNG of the current viewport and returns its path. The file is in **device pixels**: on a 2× display a 2296×1143 CSS viewport produces a 4592×2286 PNG.

```python
capture_screenshot()                       # ~/.config/browser-harness/tmp/shot.png, native resolution
capture_screenshot("/tmp/page.png")        # your path
capture_screenshot("/tmp/page.png", max_dim=1800)   # downscale the long edge
capture_screenshot("/tmp/page.jpg")        # JPEG instead of PNG
```

## Compact mode, for screenshots a model will read

Set `BH_SCREENSHOT_COMPACT=1` to size every capture for an LLM: the long edge is capped at 1568px and the default filename becomes `shot.jpg`.

1568 is not arbitrary. An image-aware LLM scales anything larger than that down to it before the model sees the image, and charges roughly `(width × height) / 750` tokens. Pixels above 1568 therefore cost nothing in tokens and add nothing to legibility. They only enlarge the transcript the screenshot is pasted into, which is the part that grows without bound over a long session.

Measured on a real 3024×1432 capture:

| Output | File | Tokens charged |
|---|---|---|
| 3024px PNG | 360 KB | 1,551 |
| 1568px JPEG q75 | 77 KB | 1,551 |
| 900px JPEG q75 | 40 KB | 511 |

The first two rows are the point: identical cost to the model, no visible difference when read back, 4.7× less transcript.

Going below 1568 does cut tokens, but it is a genuine trade. At 900px body text stays readable while dimmed sidebars, small labels and exact identifiers do not, and a misread that forces a recapture costs more than one clean 1568px shot would have. Downscale further only when you are checking layout rather than reading text.

Capture always happens at native resolution and the resize comes afterwards. That is deliberate: downscaling a supersampled 2× capture is **sharper** than asking Chrome to render at `deviceScaleFactor: 1`.

## Gotchas

**Click coordinates are CSS pixels.** Don't read a target off the image and pass it to `click_at_xy()` without dividing by `devicePixelRatio`, and note that a resized image is neither CSS nor device pixels. Prefer selectors; if you must go by pixels, capture at native resolution with `max_dim=None`.

**Pixel-diff baselines need `max_dim=None`.** Resampling and JPEG are both lossy, so a compact shot is not a valid comparison baseline. An explicit `max_dim` always overrides the environment variable.

**Format follows the extension.** `.jpg`/`.jpeg` writes JPEG, anything else writes PNG, so passing an explicit `.png` path keeps PNG even in compact mode.

**Some LLMs reject images over 2000px per side.** Long sessions on 2× displays will hit this; `max_dim=1800` or compact mode both avoid it.

**`full=True` only when you need content below the fold.** Full-page captures are much larger and slower than viewport-only, and on a long page the long-edge cap squeezes the width badly. Scroll and take viewport shots instead when you need to read text.
