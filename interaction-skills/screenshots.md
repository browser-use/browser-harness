# Screenshots

`capture_screenshot()` writes a PNG of the current viewport. The file is in **device pixels** — on a 2× display a 2296×1143 CSS viewport produces a 4592×2286 PNG.

That matters for two reasons:

1. **Click coordinates are CSS pixels.** Don't read a target off the image and pass it to `click_at_xy()` directly without dividing by `devicePixelRatio`. The simplest workflow is to take the screenshot, look at it in a viewer that shows CSS coordinates, or measure relative positions and use `js("window.devicePixelRatio")` to convert.

2. **Some LLMs reject images > 2000 px per side.** Long sessions on 2× displays will eventually hit this. Pass `max_dim=1800` to downscale the file before it gets into the conversation:

```python
capture_screenshot("/tmp/shot.png", max_dim=1800)
```

The downscale only happens when the image actually exceeds `max_dim`, so it's safe to leave on for every shot.

Use full-page screenshots (`full=True`) only when you need to see content below the fold — they are much larger and slower than viewport-only.

## Canvas / rAF pages paint nothing in a background tab

Chrome pauses `requestAnimationFrame` in tabs that are not in the foreground. A page that paints through rAF (scroll-scrubbed canvas animations, WebGL, ASCII/particle engines) opened with `new_tab()` but left unfocused never draws a frame: the DOM screenshots fine, the canvas comes back blank, and it looks like a JS error that isn't there.

- Before screenshotting such a page, foreground the attached tab: `cdp("Page.bringToFront")`, then `wait(0.5)`.
- Quick check that the canvas actually painted: `js("(()=>{const c=document.querySelector('canvas');const d=c.getContext('2d').getImageData(0,0,c.width,c.height).data;let n=0;for(let i=3;i<d.length;i+=28)if(d[i])n++;return n})()")` — 0 means no frame ran.
- Sites that set `html { scroll-behavior: smooth }` animate `window.scrollTo`, so a capture a moment later lands mid-scroll. Set `js("document.documentElement.style.scrollBehavior='auto'")` once, then scroll and capture; print `js("scrollY")` next to each shot to confirm where it landed.

