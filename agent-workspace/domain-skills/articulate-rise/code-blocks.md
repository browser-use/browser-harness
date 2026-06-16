# articulate-rise

Articulate Rise 360 (`rise.{instance}.articulate.com`) — authoring + preview + the sandboxed code blocks. Notes are durable shape only, no per-task narration.

## Authoring vs preview URL patterns

```
authoring  https://rise.{instance}.articulate.com/authoring/{courseId}/lesson/{lessonId}
preview    https://rise.{instance}.articulate.com/preview/{courseId}#/lessons/{lessonId}
```

Authoring has the editable React shell + Redux state. Preview is the rendered learner view. Both load the same code blocks but only authoring lets you mutate them. Use authoring for any edit workflow, preview for visual verification only.

## The two-layer iframe (most important fact on this page)

A Rise "code block" is **two iframes deep**, not one:

```
parent page (rise.{instance}.articulate.com)
└── outer iframe[sandbox]            src = sandbox.articulateusercontent.eu/sandbox/sandbox.html#channel=…
    └── inner iframe                 src = about:srcdoc        ← the bespoke HTML lives HERE
```

- The outer is a thin sandbox shell. Minimal default CSS, no app fonts, no app state.
- The inner `about:srcdoc` is what the author's HTML actually renders into.
- The parent's `document.querySelector('iframe[sandbox]')` selects the **outer**.
- Anything that needs to read or test the *content* (computed styles, fonts, JS state, canvas measurements) must run **inside the inner frame**, never the outer.

If you forget this, you'll silently measure the wrong document and get false negatives — fonts will look unloaded, computed styles will look wrong, etc.

## Walking to the inner frame (canonical pattern)

```python
tree = cdp("Page.getFrameTree")
def find_inner(frame, depth=0):
    url = frame.get("frame", {}).get("url", "")
    children = frame.get("childFrames", []) or []
    if "about:srcdoc" in url and depth >= 2:
        return frame["frame"]["id"]
    for c in children:
        r = find_inner(c, depth + 1)
        if r: return r
    return None
inner_frame_id = find_inner(tree["frameTree"])

iso = cdp("Page.createIsolatedWorld", frameId=inner_frame_id, worldName="probe")
ctx = iso["executionContextId"]
result = cdp("Runtime.evaluate",
    expression="<your JS here>",
    contextId=ctx, returnByValue=True)
```

Don't try to attach to the outer iframe target and reach the inner from there — Rise's nesting + the sandbox attribute makes that flaky. Walk the frame tree from the parent.

## Editing a code block in authoring view

The pencil icon on a block opens the **"Add code"** sidebar panel. Inside:

- The editor is **Ace**, not Monaco.
- Get the instance: `ace.edit(document.querySelector('.ace_editor'))`
- `editor.getValue()` / `editor.setValue(newValue, -1)` both work programmatically.
- The `-1` arg keeps cursor at the top and avoids selecting the whole buffer.
- Programmatic edits do **not** trigger Rise's debounced change listener. The autosave fires on **panel close**, not on edit.
- Closing the panel commits the editor value to Redux. Closing it after a programmatic edit is what makes the change persist.
- There is **no explicit Save button** on a lesson in authoring. Rise autosaves on every panel close. Don't waste time looking for one.
- After save, the live iframe in authoring view does **not** re-render — it keeps showing the pre-edit state until you `location.reload()`. Always reload before verifying.

## Closing the panel

Selector: `.blocks-sidebar__close` (an X button in the panel chrome). Click it via real CDP mouse, or `el.click()` works too — Rise listens to the DOM event, not just visual mouse.

`Escape` does **not** close it.

## DOM gotcha: duplicate `data-block-id`

For each block, **two elements** carry the same `data-block-id` in the DOM:

- inner: `.lesson-blocks__block-type-container[data-block-id=…]`
- outer: `.sparkle-fountain.block[data-block-id=…]`

`iframe.closest('[data-block-id]')` picks the **inner**. The pencil/edit-controls toolbar is only attached to the **outer**. So if you need the controls (pencil, style, format), do a class-aware ancestor walk:

```js
let el = iframe;
while (el && !el.classList?.contains('sparkle-fountain')) el = el.parentElement;
const outerBlockEl = el;  // pencil controls live on this one
```

## Block-controls overlay needs a real mouse event

The pencil/style/format toolbar that floats above a block is rendered on a **React hover state**. A JS-dispatched `mouseover` event is **not enough** — Rise's listener is bound to the framework's synthetic events and only fires on real pointer movement.

Use CDP:

```python
# Get block bounding rect, then:
cdp("Input.dispatchMouseEvent", type="mouseMoved",
    x=rect.x + rect.width/2, y=rect.y + 20, button="none")
# wait ~200ms for React to render the controls
```

After this the pencil button is in the DOM at:

```
.block-controls__btn-icon--type-content
```

Click via querySelector + element bounds + real `mousePressed`/`mouseReleased`.

## Block IDs are NOT unique across cloned courses

When a course is cloned in Rise, the bespoke blocks keep their original IDs. So the *same* `blockId` can show up in two different courses, with completely different HTML in each. Each course holds its own copy of the block's `srcdoc` in its own Redux state — edits to one course do not propagate.

If you're iterating across courses and using `blockId` as a dedupe key, you'll under-count and skip blocks. Dedupe by `(courseId, blockId)` instead.

## Fonts inside code blocks

The single most common bug in bespoke code blocks: the block's CSS uses

```css
font-family: inherit;
```

…assuming `inherit` will pull the brand/theme font from the surrounding Rise page.

It can't. The sandbox iframe is cross-origin (`sandbox.articulateusercontent.eu` vs the Rise origin), so `inherit` resolves to the iframe's own root, which has nothing set, which falls through to **UA default** — Times New Roman on every browser.

To get a brand font rendering inside a code block:

1. Find the brand font's actual WOFF/WOFF2 URLs by walking the parent's stylesheets:

   ```js
   for (const sheet of document.styleSheets) {
     try {
       for (const rule of sheet.cssRules || []) {
         if (rule instanceof CSSFontFaceRule && /YourFontName/i.test(rule.cssText)) {
           console.log(rule.cssText);  // → src: url('https://articulateusercontent.eu/rise/fonts/...')
         }
       }
     } catch (e) { /* cross-origin sheet */ }
   }
   ```

   The URLs are typically served by `articulateusercontent.eu/rise/fonts/{hash}.woff` and have permissive CORS so they're reusable from inside the sandbox.

2. Inline matching `@font-face` rules at the top of the code block's own `<style>`:

   ```css
   @font-face {
     font-family: 'YourFontName';
     src: url('https://articulateusercontent.eu/rise/fonts/{hash}.woff') format('woff');
     font-weight: 400;
     font-display: swap;
   }
   ```

3. Replace `inherit` in the block's CSS with an explicit family stack:

   ```css
   font-family: 'YourFontName', Arial, Helvetica, sans-serif;
   ```

That fixes the rendering at its actual root cause. Native Rise blocks don't have this problem because they live in the parent document and inherit fonts there for free; bespoke code blocks are sandboxed and have to bring their own.

## Tests that lie

- **`document.fonts.check('1em FontName')`** returns `true` even when `FontName` isn't registered. It only confirms the family-name string is parseable. Don't trust it.

- **Running a font/style test in the outer shell instead of the inner srcdoc** will report the outer shell's defaults, not the bespoke content's. This is the #1 false-negative trap.

- **Reading `iframe.srcdoc` from the parent** returns empty for the outer (the outer uses `src=`, not `srcdoc=`) and is cross-origin-blocked for the inner. Don't expect to read content via DOM attributes — go through CDP frame attach.

## Ground-truth font check (canvas glyph width)

The only test that doesn't lie. Run **inside the inner srcdoc frame** via the isolated-world pattern above:

```js
(() => {
  const c = document.createElement('canvas').getContext('2d');
  c.font = '700 24px "YourFontName", sans-serif';
  const named_w = c.measureText('Sample Text').width;
  c.font = '700 24px sans-serif';
  const fallback_w = c.measureText('Sample Text').width;
  return { named_w, fallback_w, loaded: named_w !== fallback_w };
})()
```

If `named_w === fallback_w`, the named font silently fell back. If they differ, the named font is the one actually being painted to pixels.

## Useful endpoints

```
GET  /api/rise-runtime/course_fonts.css?typefaceIds={id1},{id2}    # @font-face for course-themed fonts
GET  /api/rise-runtime/fonts.css                                    # global font catalogue
POST /api/rise-runtime/ducks/rise/courses/GET_COURSE                # full course payload (auth required, exact request shape varies)
```

The `course_fonts.css` endpoint is the easiest place to discover the WOFF URLs for whatever brand font is themed onto the current course — just hit it in DevTools Network tab during a normal load and read the response.

## Don'ts

- Don't try to inject CSS into the iframe from the parent. Cross-origin sandbox blocks all of it (style injection, `parent.document.fonts.add(...)` from inside, postMessage style protocols — none of it works).
- Don't measure anything in the outer sandbox shell. It's not the document the user sees.
- Don't trust `document.fonts.check`. Glyph-width measurement is the only honest test.
- Don't assume blockId is unique across courses.
- Don't expect a Save button. Panel-close is the save event.
