# Pearson MyLab homework

Pearson MyLab homework players are often embedded several cross-origin iframes deep inside the course shell. Compositor-level `click_at_xy` works through these frames, but DOM inspection requires a CDP execution context for the innermost activity frame.

## Navigation and layout

- A homework item can be addressed directly inside the activity frame with `Student/PlayerHomework.aspx?homeworkId=<id>&questionId=<n>&flushed=false&cId=<course-id>`. This is useful when the outer course shell reloads to the homework overview.
- The activity frame may be taller than the browser viewport. Scroll the outer document with `window.scrollTo(0, document.documentElement.scrollHeight)` to expose the fixed graph toolbar and **Check answer** button.
- At normal zoom, graph controls can sit below the visible area. Reducing browser zoom can expose the complete toolbar, but restore the prior zoom after the task when practical.

## Graph questions

- Select graph tools from the toolbar, then click directly on the plotted grid. After creating an object, use the visible label menu to apply the requested label.
- Point objects expose an **Edit coordinates** action. Use it when a click lands near, but not exactly on, the required value.
- Coordinate fields use Pearson's Dojo equation editor rather than a normal text input. Keyboard selection can append text instead of replacing it. The stable widget API is:

```js
const editor = dijit.byId('equation-editor-id');
editor.clear();
editor.setEqText('2100');
editor.setChanged();
```

Read `editor.getEqText()` or the widget node's `aria-label` to verify the exact value before submitting.

## Fill-in dropdowns

Fill-in dropdowns are Dojo widgets such as `FL1`, not native `<select>` elements. Visible choices live under `widget.dropDown.getChildren()`. If a compositor click is unreliable, commit a choice through the same widget handler:

```js
const fill = dijit.byId('FL1');
const choice = fill.dropDown.getChildren()[1];
fill.menuItemClicked.call(choice);
```

Verify `fill.selectedIndex` and `fill.displayNode.innerText` before checking the answer.

## Verification

After every graph edit, dropdown choice, answer check, and success dialog, capture a screenshot. Pearson sometimes needs a short delay after **Check answer** or **Next question** before the score and question content update.
