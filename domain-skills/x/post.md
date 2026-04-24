# X / Twitter — Post with Image(s) or Video(s)

Post text + image(s) and/or video(s) to X.com using the browser harness. Assumes user is already logged in.

## Media Requirements

**Images:** PNG, JPG, WebP, GIF — uploaded as-is.

**Video:** Must be H.264 codec (libx264) + AAC audio. The skill auto-converts non-H.264 video using ffmpeg before uploading. HEVC (ProRes, etc.) files will be rejected by X with "Your video file could not be processed."

## API Design

### Module usage

```python
from x_post import post_to_x

# Single image
result = post_to_x(text="...", media=[{"path": "/path/to/img.png", "type": "image"}])

# Multiple images
result = post_to_x(text="...", media=[
    {"path": "/path/to/img1.png", "type": "image"},
    {"path": "/path/to/img2.jpg", "type": "image"},
])

# Mix of images and video
result = post_to_x(text="...", media=[
    {"path": "/path/to/img.png", "type": "image"},
    {"path": "/path/to/video.mp4", "type": "video"},
])
```

### Script usage

```bash
# Auto-detect type from file extension
uv run python3 x_post.py "text" /path/to/img.png
uv run python3 x_post.py "text" /path/to/video.mp4

# Explicit type prefix (img: / vid:)
uv run python3 x_post.py "text" img:/path/to/img.png vid:/path/to/video.mp4

# Multiple items
uv run python3 x_post.py "text" /path/to/img1.png /path/to/img2.jpg
```

## Selectors

| Element | Selector |
|---------|----------|
| Compose textarea | `[data-testid="tweetTextarea_0_label"]` |
| Post button | `[data-testid="tweetButtonInline"]` |
| Media file input | `[data-testid="fileInput"]` |

## Workflow

```
1. navigate to https://x.com/home
2. wait_for_load()
3. click compose textarea center (coordinate click)
4. type_text(text)       — fills the compose box
5. upload each media item to '[data-testid="fileInput"]'
   — images uploaded first, then videos
   — videos are pre-converted to H.264 if needed (auto-detected by extension)
6. wait 3 seconds (buffer for media to start processing)
7. poll until Post button is enabled (aria-disabled != 'true')
   — for video, this wait is longer since X disables the button during processing
8. js click the Post button (coordinate click fails after media attachment)
9. wait 5s, verify post appears in feed
```

## Key Gotchas

- **Video codec must be H.264** — X rejects HEVC, VP9, ProRes. The skill auto-converts these.
- **Coordinate click on Post button fails** — X re-renders the button after media is attached. Always use JS `.click()` for the Post button.
- **Post button is disabled during video processing** — the button stays `aria-disabled="true"` until the video finishes processing. The polling loop handles this naturally.
- **3-second fixed wait before polling** — ensures media upload starts before we start checking button state.
- **Upload is sequential** — images then videos, 0.5s between each upload call.
- **Auto-detect by extension** — `.mp4/.mov/.avi/.mkv/.webm/.m4v` are treated as video; everything else as image. Use `img:` / `vid:` prefix to override.
- **Verify with JS** — look for `[data-testid="tweet"]` element containing the posted text.

## Files

- `x/x_post.py` — standalone script with `post_to_x()` function
- `x/post.md` — this documentation
