# X (Twitter) — Posting & Auth

## Login

Navigate to `https://x.com/i/flow/login` (not `https://x.com/`) to get the full sign-in modal. The homepage may render a truncated version of the auth buttons.

### Google sign-in (FedCM) — cannot be automated

The "Sign in as <user>" Google button uses Chrome's Federated Credential Management (FedCM) API. CDP mouse events (`Input.dispatchMouseEvent`) do **not** count as a trusted user gesture for FedCM, and the button lives in a sandboxed cross-origin iframe (`accounts.google.com`). Clicking it via automation has no effect.

**If the user wants Google sign-in, ask them to click the button themselves**, then wait for confirmation before proceeding.

### Username / password flow

Use the standard form on `https://x.com/i/flow/login`. Ask the user for credentials — do not guess or read them from screenshots.

## Composing and posting a tweet

Once logged in, the home feed is at `https://x.com/home`.

```python
import json

# Find the compose box and type
result = js(r'''
  var el = document.querySelector("[data-testid=\"tweetTextarea_0\"]");
  if (!el) return null;
  var r = el.getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
''')
if result is None:
    raise RuntimeError("compose textarea not found — are you logged in and on x.com/home?")
pos = json.loads(result)
click_at_xy(pos["x"], pos["y"])
type_text("hello world!")

# Find and click Post
btn = js(r'''
  var b = document.querySelector("[data-testid=\"tweetButtonInline\"]")
       || document.querySelector("[data-testid=\"tweetButton\"]");
  if (!b) return null;
  var r = b.getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)});
''')
if btn is None:
    raise RuntimeError("post button not found — did the compose surface fail to open?")
pos = json.loads(btn)
click_at_xy(pos["x"], pos["y"])
```

### Stable selectors

| Element | Selector |
|---|---|
| Compose textbox | `[data-testid="tweetTextarea_0"]` |
| Post button (home feed inline) | `[data-testid="tweetButtonInline"]` |
| Post button (modal) | `[data-testid="tweetButton"]` |

### Confirmation

A toast "Your post was sent." appears at the bottom of the page after a successful post. Verify with a screenshot.

## Gotchas

- The home feed compose area and the sidebar "Post" button both open a compose surface, but `tweetButtonInline` is specific to the inline feed composer. If you open a modal (e.g. via the sidebar "Post" button), use `tweetButton` instead.
- If the Grok side panel opens unexpectedly, click a neutral area (e.g. left sidebar) to dismiss it before interacting with the compose box.
- `twitter.com` redirects to `x.com` — all canonical URLs use `x.com`.
