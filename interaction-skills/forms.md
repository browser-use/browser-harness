# Forms and framework-managed inputs

Modern frameworks often keep form state outside the DOM. A visible
`input.value` update can still leave React controlled inputs, Vue `v-model`, or
Ember/Glimmer tracked state unchanged, so submit buttons stay disabled or click
handlers no-op.

## Default helper

Use `fill_input(selector, text, clear_first=True, timeout=...)` before falling
back to lower-level typing:

```python
fill_input("#email", "agent@example.com", timeout=5)
click_at_xy(save_x, save_y)
wait_for_network_idle()
```

`fill_input()` focuses the element, clears it with the platform select-all
shortcut, types via CDP key events, and then fires bubbling `input` and `change`
events. That covers most framework-managed controls better than `type_text()`,
which uses `Input.insertText` and can bypass framework listeners.

## Modal forms

For modal forms, verify three things after filling:

1. The text is visibly present in a screenshot.
2. The submit/save button changed state if it was initially disabled.
3. Clicking submit produces the expected UI change or network activity.

```python
fill_input("input[name='search']", "cats", timeout=5)
capture_screenshot("/tmp/form-filled.png")
click_at_xy(save_x, save_y)
assert wait_for_network_idle(timeout=10)
```

## When DOM value and framework state diverge

If `document.querySelector(selector).value` is correct but submit still no-ops:

- Re-click/focus the field visually and retry `fill_input()`; some components
  ignore events unless focus came from the browser.
- Prefer real coordinate clicks for the submit action; synthetic DOM clicks may
  skip framework or component-library handlers.
- Inspect disabled/error state in the DOM with `js(...)` before inventing a
  framework-specific hook.
- Capture the reusable site-specific path in `agent-workspace/domain-skills/`
  only after it is proven in the browser.

A public no-auth Ember modal/input target for experiments is
`https://www.ember-bootstrap.com/components/modal/` → **Custom markup** →
**Open Modal** → **Search** input → **Save** button. It is useful for testing
modal focus and input mechanics without a LinkedIn account.
