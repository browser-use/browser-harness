# Scrolling

Separate page scroll, nested containers, virtualized lists, and dropdown menus, and identify which element is actually consuming wheel events before scrolling.

## `scroll()` does not scroll overlays — use `synthesizeScrollGesture`

`scroll()` sends `Input.dispatchMouseEvent {type: "mouseWheel"}`. Chrome routes that through the
compositor, which picks the scroll node from its own hit-test data. A `position: fixed` overlay
added after the page settled is **not** in that data, so the wheel goes to the scroller *underneath*
and the overlay never moves — even though `:hover`, `elementFromPoint` and a real `wheel` listener on
the overlay all confirm the pointer is over it.

Measured symptom (a fixed drawer with `overflow-y: auto`, content 517px in a 373px box):

```python
scroll(1250, 300, dy=-300)
js("document.getElementById('tareasLista').scrollTop")   # 0, every x across the overlay
js("document.getElementById('msgs').scrollTop")          # the element BEHIND it scrolled
```

The wheel listener fired on the overlay with `e.cancelable === false`: the compositor had already
decided, and the main thread only got told. A freshly created bare `position: fixed; overflow: auto`
div reproduces it, so it is not a quirk of any one page's CSS.

Use the real input pipeline instead:

```python
cdp("Input.synthesizeScrollGesture", x=1250, y=300, yDistance=-260, speed=1200,
    gestureSourceType="mouse")
```

Same page, same coordinates: the overlay scrolled to 143.9 and the element behind it did not move.

- `yDistance` is **negative to scroll down** (it is the finger/content delta, same sign as `deltaY`).
- It is a gesture, so it takes real time: wait ~1s, do not read `scrollTop` immediately.
- `gestureSourceType`: `"mouse"` for wheel, `"touch"` for a flick (momentum, `overscroll-behavior`).

Rule of thumb: `scroll()` is fine for the document and for ordinary in-flow containers. The moment
the target is an overlay, drawer, modal or anything `position: fixed`, reach for
`synthesizeScrollGesture` — and never conclude "this panel does not scroll" from `scroll()` alone.
