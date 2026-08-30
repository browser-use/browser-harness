# Viewport

Set the viewport with `Emulation.setDeviceMetricsOverride`, never by resizing the window. It sets the **layout viewport**, which is what media queries, `innerWidth`, and responsive layout actually respond to.

```python
cdp("Emulation.setDeviceMetricsOverride", width=390, height=844,
    deviceScaleFactor=2, mobile=True)
# ... inspect / screenshot ...
cdp("Emulation.clearDeviceMetricsOverride")   # always restore
```

Confirmed on a page whose CSS narrows its padding at `max-width: 560px`:

| State | `innerWidth` | computed `body` padding |
|---|---|---|
| default window | 756 | 24px |
| override `width=390` | 390 | 20px |
| after `clearDeviceMetricsOverride` | 756 | 24px |

## What `mobile=True` actually changes

Less than the name suggests. It aligns the *window and screen* metrics with the emulated viewport — and nothing else:

| | no override | `mobile=True` | `mobile=False` |
|---|---|---|---|
| `innerWidth` | 756 | 390 | 390 |
| `outerWidth` | 780 | 390 | 780 |
| `screen.width` | 800 | 390 | 800 |
| `devicePixelRatio` | 1 | 2 | 2 |
| `navigator.maxTouchPoints` | 0 | **0** | 0 |
| UA contains `Mobile` | false | **false** | false |

So with `mobile=False` a site that branches on `screen.width` still sees an 800px desktop screen while the layout is 390 wide. And **neither setting touches the user agent or touch support** — a site sniffing either still sees desktop Chrome.

For emulation a site can't see through, add the two companion calls:

```python
IPHONE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 "
             "(KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")

cdp("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
cdp("Emulation.setUserAgentOverride", userAgent=IPHONE_UA)
cdp("Emulation.setTouchEmulationEnabled", enabled=True, maxTouchPoints=5)
goto_url(url); wait_for_load()
# {"iw":390,"screenW":390,"touch":5,"uaMobile":true,"hover":false}
```

Reset all three when done — `setUserAgentOverride` with `userAgent=""` restores the real UA:

```python
cdp("Emulation.setUserAgentOverride", userAgent="")
cdp("Emulation.setTouchEmulationEnabled", enabled=False)
cdp("Emulation.clearDeviceMetricsOverride")
```

Note that touch emulation flips `(hover: hover)` to false, so hover-only menus stop opening — which is usually what you want when testing a phone layout, and surprising when you aren't.

## Checking for real overflow

Measure it — don't eyeball a screenshot. This names the offending elements:

```python
print(js("""JSON.stringify({
  innerWidth: innerWidth,
  scrollWidth: document.documentElement.scrollWidth,
  overflowing: [...document.querySelectorAll('body *')]
    .filter(el => el.getBoundingClientRect().right > innerWidth + 1)
    .map(el => el.tagName + (el.className ? '.' + el.className : ''))
    .slice(0, 8)
})"""))
# {"innerWidth":390,"scrollWidth":390,"overflowing":[]}  -> genuinely clean at 390
```

`scrollWidth > innerWidth` is real horizontal overflow. `scrollWidth == innerWidth` with a screenshot that *looks* cropped means the screenshot is lying — see below.

## Trap: headless Chrome clamps `--window-size` to 500px

If you spawn your own headless Chrome rather than attaching to the user's, **any `--window-size` width below 500 lays out at 500 CSS px** while the screenshot canvas stays at the width you asked for. The extra width is cropped off the right, so the PNG looks like a horizontal-overflow bug that does not exist.

Measured on macOS, Chrome 151, `--headless=new`:

| `--window-size` | actual `innerWidth` |
|---|---|
| 320 | **500** |
| 390 | **500** |
| 450 | **500** |
| 500 | 500 |
| 520 | 520 |
| 800 | 800 |

Nothing is logged when this happens. A page that is genuinely fine at 390px yields a screenshot with every line of text sheared off at the right edge, and the narrower you ask for, the worse it looks.

Detect it by measuring, not by looking:

```python
print(js("JSON.stringify({iw: innerWidth, sw: document.documentElement.scrollWidth})"))
# iw != the width you requested -> you are clamped; the image is cropped, not overflowing
```

`Emulation.setDeviceMetricsOverride` has no such floor — 390 and 320 both come back exact.

## Full-page screenshots at an emulated size

`full=True` renders the whole document at the emulated width, giving one tall image in the mobile layout rather than a viewport-height slice:

```python
cdp("Emulation.setDeviceMetricsOverride", width=390, height=844, deviceScaleFactor=2, mobile=True)
capture_screenshot("/tmp/mobile.png", full=True, max_dim=1800)
cdp("Emulation.clearDeviceMetricsOverride")
```

The PNG is in **device pixels** — 390 CSS px at `deviceScaleFactor=2` is a 780px-wide file — so pass `max_dim` to stay under the image-size limit described in `screenshots.md`.

## Responsive sweep

Each override replaces the previous one, so no reset is needed between iterations — only at the end:

```python
for label, width, height, mobile in [("mobile", 390, 844, True),
                                     ("tablet", 768, 1024, False),
                                     ("desktop", 1440, 900, False)]:
    cdp("Emulation.setDeviceMetricsOverride", width=width, height=height,
        deviceScaleFactor=2, mobile=mobile)
    wait_for_load()
    print(label, js("JSON.stringify({iw:innerWidth, sw:document.documentElement.scrollWidth})"))
    capture_screenshot(f"/tmp/{label}.png", full=True, max_dim=1800)
cdp("Emulation.clearDeviceMetricsOverride")
```

## Coordinate clicks under an override

`click_at_xy()` takes **layout-viewport CSS pixels** — the `width` you passed to the override, not screenshot pixels. With `deviceScaleFactor=2`, a target at x=600 in the PNG is at x=300 for the click.

## Traps

- **Forgetting to reset** leaves the override on that tab for the rest of the session. Clear device metrics, UA, and touch as soon as the responsive check is done.
- **`mobile=True` is not mobile emulation.** It does not change the UA or touch support; add `setUserAgentOverride` and `setTouchEmulationEnabled` if the site sniffs either.
- **Only trust a screenshot's width after checking `innerWidth`.** If they disagree, the image is cropped and any layout conclusion drawn from it is wrong.
