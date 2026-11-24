# Cross-Origin Iframes

Focus on `iframe_target(...)`, target attachment, and when compositor-level coordinate clicks are lower-friction than cross-target DOM work.

```python
frame = iframe_target("pay.example")       # only iframes inside your current tab
print(js("document.title", target_id=frame))
```

An iframe of a tab you do not hold fails with `frame-not-yours`; `switch_tab()` to its tab first.
