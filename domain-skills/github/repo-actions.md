# GitHub — Repo actions (star, unstar, watch)

`https://github.com/{owner}/{repo}` — user-triggered actions on the repo header (Star, Unstar, Watch, Unwatch) are HTML forms that POST back to GitHub with the session's CSRF token already rendered inline. **Submit the form — do not click the button.**

## Do this first

```python
# Precondition: user is logged in
if not js('!!document.querySelector("meta[name=user-login]")'):
    raise RuntimeError("not logged in to GitHub")

# Star the current repo
js("""
(()=>{
  const f = document.querySelector('form[action$="/star"]');
  if (!f) return 'already-starred-or-missing';
  f.submit();
  return 'submitted';
})()
""")
wait(2)
wait_for_load()

# Verify — the toggle swaps which form is present
starred = js('!!document.querySelector(\'form[action$="/unstar"]\')')
```

Same pattern for the reverse (`form[action$="/unstar"]`) and for watch/unwatch (`form[action$="/subscription"]` + a hidden `_method` field, see below).

## Why not click the button

The visible Star button looks like `button[aria-label^="Star "]`, but that selector has two gotchas on the modern repo header:

- **There are two matching buttons.** The first one `querySelector` returns is a hidden fallback inside the sticky sub-header form with `getBoundingClientRect() == {x:0, y:0, w:0, h:0}`. Coordinate-clicking it does nothing because it has no geometry.
- **Synthetic `.click()` on the visible React button does not persist the star.** The click fires, `aria-label` stays `Star ...`, network tab shows no POST. GitHub's component swallows the synthetic event somewhere in its React fiber handler.

`form.submit()` sidesteps both problems — it bypasses React entirely and goes straight to the HTML form's POST. The authenticity token is already in a hidden input inside the form, so there's nothing extra to fetch.

## Watch / Unwatch

The subscription form uses a shared endpoint with a `_method` override:

```python
# Watch (all activity)
js("""
(()=>{
  const f = document.querySelector('form[action$="/subscription"]');
  if (!f) return 'missing';
  f.submit();
  return 'submitted';
})()
""")
```

GitHub renders different form attributes (different `_method` hidden input values) depending on the current state. Re-read the form after every toggle rather than caching a reference.

## Gotchas

- **Star count in the rendered button lags the true count by a hydration tick.** The durable signal that "this worked" is which form is on the page after reload: `form[action$="/star"]` present means unstarred, `form[action$="/unstar"]` means starred. The visible aria-label is reliable once you scroll to the top and wait ~1s after submit; the count inside the button updates on soft navigation and is not a good assertion target.

- **`form.submit()` bypasses the form's `submit` event listeners** — fine for GitHub's case (the handler is a full navigation), but if a future change wires in `e.preventDefault()` to do an XHR, `form.requestSubmit()` is the safer alternative. Worth trying first if `form.submit()` stops working.

- **If the user is not logged in the forms are not rendered at all.** `meta[name="user-login"]` is the cheapest pre-check.

- **For read-only star counts, don't touch the DOM — use the API.** `http_get("https://api.github.com/repos/{owner}/{repo}")` returns `stargazers_count` without any browser interaction. See `scraping.md`. Only use the form-submit pattern when you actually need to *change* state on behalf of the logged-in user.
