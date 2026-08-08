# Scrolling

Separate page scroll, nested containers, virtualized lists, and dropdown menus, and identify which element is actually consuming wheel events before scrolling.

## The signature is (x, y, dy, dx): position first, movement second

```python
scroll(640, 400, dy=1400)    # down 1400px, wheel positioned at x=640 y=400
scroll(640, 400, dy=-1400)   # up
```

`x` and `y` say *where the pointer is*, not which way to go. That matters because
the element under the pointer is the one that receives the wheel event, which is
how you aim at a specific pane (see nested containers below).

This is not the `scroll(direction, amount)` convention most browser tools use,
and reaching for that convention out of habit is the easy mistake:

```python
scroll("down", 1400)   # wrong
```

That binds `x="down"`, `y=1400`, and leaves `dy` at its **default of -300**, so
the intent (down 1400) becomes up 300. There are two errors there and the second
one survives fixing the first: someone who sees the failure, guesses that the
numbers are wrong, and writes `scroll(0, 1400)` still scrolls up 300.

CDP does reject the string, but the message points at the wrong thing:

```
Failed to deserialize params.x - BINDINGS: double value expected at position 26
```

That names a byte offset in the serialized payload and says nothing about `dy`.
`scroll()` now raises `TypeError` on a non-numeric `x` or `y` and names the
correct call instead.

## Debugging a scroll that did not move

Read the position back rather than trusting the call. A wheel event can
legitimately do nothing: already at the end, the page not laid out yet, or some
other element consuming the wheel.

```python
before = page_info()["sy"]
scroll(640, 400, dy=1400)
print(before, "->", page_info()["sy"])
```

## The window did not move but the page clearly scrolls

The page is scrolling an inner container. Position the wheel over that container
rather than over the page background:

```python
box = js("""(()=>{const e=document.querySelector('SELECTOR');
  const r=e.getBoundingClientRect();
  return JSON.stringify({x:r.left+r.width/2, y:r.top+r.height/2});})()""")
import json; c = json.loads(box)
scroll(c["x"], c["y"], dy=1400)
```

If the container still does not take the wheel, drive it directly and skip the
event entirely:

```python
js("document.querySelector('SELECTOR').scrollTop += 1400")
```

## Virtualized feeds drop what you scrolled past

Infinite feeds (social timelines, long search results, big tables) unmount rows
once they leave the viewport. A single extraction after the scroll loop returns
only what is near the viewport at that moment, not everything you scrolled
through, and it looks like a short page rather than a bug.

Collect **inside** the loop, at every step, and de-duplicate afterwards.

```python
seen, rows = set(), []
for _ in range(8):
    for r in js("...extract currently-rendered rows..."):
        if r not in seen:
            seen.add(r); rows.append(r)
    scroll(640, 400, dy=1400)
    wait_for_network_idle()
```

This applies to links as much as to text: `a[href]` on a virtualized feed
returns only the currently-rendered subset, so harvesting permalinks needs the
same per-step collection as harvesting content.

Two more things that bite here:

- **Some sites restore your previous scroll position on load.** Force
  `js("window.scrollTo(0,0)")` before the loop so step one starts at the top.
- **Lazy content needs a beat to arrive.** `wait_for_network_idle()` between
  steps beats a fixed sleep, and both beat scrolling straight to the bottom.
