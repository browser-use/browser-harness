# Captcha-bound APIs — use a browser only as a token oracle

Pattern for sites that gate API calls with reCAPTCHA Enterprise (or similar
session-bound captchas) where token-solving services like 2captcha don't work.

## When this applies

You're trying to script a site and notice:

1. The browser flow works fine (no visible captcha to a real user).
2. Direct API calls (curl/requests/fetch) get rejected with vague errors like
   `"abnormal activity"`, `"verification failed"`, `"please try again"`.
3. The rejection happens *even with no captcha token in the payload* — meaning
   the server isn't validating *what's there*, it's flagging *the absence of
   a real-browser-issued token*.
4. 2captcha / capsolver tokens get rejected the same way.

This is reCAPTCHA Enterprise binding tokens to browser-session signals that
out-of-browser solvers can't replicate (cookies set by the page, JS execution
fingerprints, browser context). Sites like recreation.gov, some banks, some
ticket sites.

## The pattern

**Use a real browser only to generate the captcha token. Do everything else
in plain HTTP.**

```python
# 1. Find the sitekey + action from the page's JS bundle
#    (grep for `recaptcha.execute(`, `enterprise.execute(`, `v3SiteKey`)
SITEKEY = "6LdBIvUZ..."   # from the bundle
ACTION  = "submitForm"    # from the call site

# 2. Open the page in a real browser (browser-harness against user's Chrome,
#    OR a launched Playwright). The page must load grecaptcha — usually any
#    page on the same domain works.
new_tab("https://example.com/some-page")
wait_for_load()

# 3. Call execute() in-page — returns the token directly
token = js(f"() => grecaptcha.enterprise.execute('{SITEKEY}', {{action: '{ACTION}'}})")

# 4. Make the API call from anywhere (Python urllib, Node fetch, curl...)
#    using the token in whatever field the API expects
import urllib.request, json
body = {..., "captcha_token": token, ...}
urllib.request.urlopen(urllib.request.Request(api_url, data=json.dumps(body).encode(),
                       headers={"Content-Type": "application/json"}))
```

The `js()` call returns the token as a string. Pass it to anything.

## Why this beats alternatives

| approach                           | works? | why                                                  |
|------------------------------------|--------|------------------------------------------------------|
| 2captcha v2 checkbox               | ❌      | token issued in 2captcha's browser context           |
| 2captcha v3 enterprise             | ❌      | same — context-bound                                 |
| 2captcha v3 enterprise min_score=0.9| ❌      | doesn't change context binding                      |
| `curl_cffi` w/ chrome impersonation | ❌      | TLS fingerprint is rarely the gate; captcha is       |
| Driving the entire UI with browser | works  | overkill — most UIs are just decoration on the API   |
| **Browser only for captcha + HTTP API** | ✅ | minimum browser surface, full HTTP speed            |

## Discovery checklist

When you suspect a site has this gate:

1. **Capture a HAR** of the working flow (Chrome DevTools Network → "Preserve
   log" → "Save all as HAR with content"). Find the API call that does the
   action. Look at its request body for a token-shaped field
   (`gate_a.value`, `recaptcha_token`, `captcha`, etc.).
2. **Find the sitekey** in the page's JS bundle:
   `fetch('/path/to/bundle.js').then(r=>r.text()).then(t=>t.match(/[\w-]{40}/g))`
   — recaptcha keys are 40-char alphanumeric strings starting with `6L`.
3. **Find the action** by grepping the bundle for `execute(` or by looking at
   the HAR's `recaptcha/enterprise/reload` request body — the action string
   is plaintext in the protobuf payload.
4. **Confirm context-binding** by sending the API call with no token (or a
   fake one) — if you get the *same* error as with a 2captcha token, the
   server isn't even validating the token shape, it's checking session signals.
   Browser-oracle is your only path.

## Headless considerations

If you're launching the browser yourself (Playwright), reCAPTCHA gives a lower
v3 score to headless sessions. If you get `"additional challenge required"`:

```python
browser = pw.chromium.launch(
    headless=False,  # huge improvement vs headless
    args=["--disable-blink-features=AutomationControlled"],
)
context = browser.new_context(
    user_agent="Mozilla/5.0 ...real chrome UA...",
    viewport={"width": 1280, "height": 800},
    locale="en-US",
)
context.add_init_script(
    "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
)
```

Browser-harness against the user's real Chrome always passes (real history,
real IP rep) — that's the discovery environment. For a self-contained script,
launched Playwright with the tweaks above usually works on first try; if the
site is harder, run non-headless or add a brief `page.mouse.move()` jiggle
before `execute()`.

## What to put in your domain skill

When you find a captcha-oracle site, capture in `domain-skills/<site>/`:

- The reCAPTCHA sitekey(s)
- The action(s) used per endpoint
- Where in the request body the token goes (`gate_a.value`, etc.) and any
  sibling fields (`description`, `region`, `success`, `terminal`, etc.)
- That 2captcha doesn't work, so the next agent doesn't waste time
