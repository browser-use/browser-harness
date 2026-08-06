# React controlled inputs

Assigning `el.value = "..."` to a React-controlled input does nothing — React overwrites it from state on the next render because the assignment never fires React's own change tracking.

What works, in order of preference:

1. **Real input**: click the field, then type via key events. Most robust.
2. **Native setter + input event** when typing is impractical:

```python
js("""
const el = document.querySelector('#amount');
const setter = Object.getOwnPropertyDescriptor(
  window.HTMLInputElement.prototype, 'value').set;
setter.call(el, '87300');
el.dispatchEvent(new Event('input', { bubbles: true }));
""")
```

The same trick applies to `HTMLTextAreaElement` and `HTMLSelectElement` (swap the prototype). Symptom that you need this: the field visually shows your value for a frame, then snaps back — or downstream state never updates.
