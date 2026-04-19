# Recreation.gov — booking & account creation

Field-tested 2026-04-19. Everything below is HTTP-driven *except* the reCAPTCHA
Enterprise v3 token, which has to come from a real browser session
(see `interaction-skills/captcha-oracle.md`).

End-to-end working script: <https://github.com/britter21/campgrounds-availability/blob/main/hold.py>

---

## TL;DR

- **No need to click anything.** Skip the React availability grid entirely —
  it's bookable via one POST to `/api/camps/reservations/campgrounds/<id>/multi`.
- **Auth is `Authorization: Bearer <jwt>`**, not cookies. The login response
  body has the JWT.
- **Captcha is the only browser-required step.** Generate a token with
  `grecaptcha.enterprise.execute(...)` in a real browser, then send it in
  `gate_a.value`. 2captcha tokens get rejected as `"abnormal activity from
  your computer network"`.
- **Disposable accounts work.** Registration accepts mail.tm addresses
  (`@deltajohnsons.com` is mail.tm's domain) and confirmation is a clickable
  UUID link, not a 6-digit code.

---

## API map

| step              | method | path                                                          |
|-------------------|--------|---------------------------------------------------------------|
| start signup      | `POST` | `/api/accounts/registration`                                  |
| confirm + set pw  | `POST` | `/api/accounts/registration/<uuid>`                           |
| login             | `POST` | `/api/accounts/login/v2/`                                     |
| availability      | `GET`  | `/api/camps/availability/campground/<id>/month?start_date=…`  |
| **hold**          | `POST` | `/api/camps/reservations/campgrounds/<id>/multi`              |
| cart              | `GET`  | `/api/cart/shoppingcart`                                      |

The full bundle of routes lives in `https://www.recreation.gov/navigation/index-*.js`.
Search for `/api/accounts/[a-z]+` to find current endpoints if any 404.

---

## The hold POST — payload shape

```json
{
  "reservations": [{
    "account_id": "<from JWT>",
    "campsite_id": "999990043",
    "check_in":  "2026-07-16T00:00:00.000Z",
    "check_out": "2026-07-17T00:00:00.000Z",
    "reservation_options": {
      "night_map": {
        "2026-07-16T00:00:00.000Z": {
          "campsite_id": "999990043",
          "campsite_loop": "Loop B",
          "campsite_name": "021"
        }
      },
      "recommendation_referrer": "campground-v1:campgroundPage"
    }
  }],
  "gate_a": {
    "value": "<grecaptcha.enterprise.execute token>",
    "description": "campsiteListBooking",
    "success": true,
    "terminal": "east"
  }
}
```

**`night_map`** must contain one entry per night in `[check_in, check_out)`.
Multi-night holds need every date filled in.

**`gate_a.terminal`** — initial value is `"east"`. On rejection the response
contains `"terminal": "west"` (or south/north) — that's the server *suggesting*
the next gate to try. In practice it's always reject-cycling when the captcha
context is wrong; sending a valid browser-bound token to `"east"` works first try.

---

## reCAPTCHA — sitekeys + actions

| sitekey                                          | type                         |
|--------------------------------------------------|------------------------------|
| `6LdBIvUZAAAAAM02b8GWJew_1LffQJo9rNB5yVTU`       | invisible v3 Enterprise — used for booking, registration, password reset |
| `6LfhXNoZAAAAAMTSVfpSlqoOeBBJmIoHwtI7Gm6v`       | v2 checkbox fallback — only appears when v3 score is too low (`additional challenge required`) |

Actions seen so far: `"campsiteListBooking"`, `"initializeRegistration"`,
`"signup"`, `"passwordreset"`, `"login"`. The action you pass to `execute()`
must match what the server expects for that endpoint.

```js
const token = await grecaptcha.enterprise.execute(
  '6LdBIvUZAAAAAM02b8GWJew_1LffQJo9rNB5yVTU',
  { action: 'campsiteListBooking' }
);
```

**Region field in registration:** the request body has `system.region` —
hardcode `"invisible"` for v3, `"WEST"` only when falling back to the v2
checkbox.

---

## Site → campsite_id resolution

The site number you see on the page (e.g. `"021"`) is *not* the API ID
(`"999990043"`). Resolve with:

```python
month_start = "2026-07-01T00:00:00.000Z"  # any date in the month
url = f"/api/camps/availability/campground/{cgid}/month?start_date={quote(month_start)}"
data = json.loads(http_get(url))
match = next(c for c in data["campsites"].values() if c["site"] == "021")
campsite_id = match["campsite_id"]
loop = match["loop"]  # e.g. "Loop B"
```

The availability endpoint is **public** — no auth needed.

---

## Account creation flow

1. **POST `/api/accounts/registration`** with:
   ```json
   {
     "email": "...",
     "first_name": "...",
     "last_name": "...",
     "cell_phone": "<10 digits>",
     "opt_in": false,
     "system": {
       "section": "initializeRegistration",
       "code": "<recaptcha_token>",
       "region": "invisible"
     }
   }
   ```
   Returns `{"confirmation_code": false, "success": true}`.

2. **Wait for email** to the address you registered. Subject:
   `"Recreation.gov - Confirm Your Email Address"`. Body contains a link:
   `https://www.recreation.gov/account/confirmation/<UUID>`.

3. **POST `/api/accounts/registration/<UUID>`** with:
   ```json
   {"token": "<UUID>", "password": "...", "userAgent": "..."}
   ```
   Returns the JWT and `account.account_id` immediately — account is fully usable.

   The endpoint *also* exists at `PUT /api/accounts/registration/validate`
   with a 6-character code, but that path is for the SMS/MFA flow, not email
   confirmation. The UUID-link path is what email signup uses.

### Phone validation gotchas

- **555 exchanges are rejected** with `{"error":"invalid cellphone"}`. The
  `XXX-555-XXXX` "fictional use" pattern doesn't pass.
- **Random valid area code + random NXX (200-999) + random last-4 works.**
  E.g. `2127340912`. Use a list of real area codes (212, 213, 312, 415, etc.).

### mail.tm

mail.tm's only active domain (as of 2026-04) is `deltajohnsons.com`. recreation.gov
accepts it without flagging. Two gotchas:
1. Wait ~2s between `POST /accounts` and `POST /token` — the new account
   propagates to the auth service asynchronously.
2. Free tier rate-limits aggressively — get 429s on rapid creates. Backoff +
   retry.

---

## Auth — what's where

- **JWT lives in the login response body** (`access_token`). Send as
  `Authorization: Bearer <jwt>` on subsequent requests.
- **`r1s-fingerprint` cookie** is set on every response — HttpOnly, mostly
  cosmetic for an HTTP client (the JWT is what authorizes), but include it.
- **HAR exports strip `Cookie` and `Authorization` headers.** Don't waste time
  guessing — assume Bearer JWT and confirm by hitting
  `/api/cart/shoppingcart/header` (returns `"There are no claims in the auth
  token"` when missing).

---

## Holds expire after ~15 minutes

The hold POST returns `reservation_status: "HOLD"`. To convert to a real booking
you have to log in via the web UI and complete checkout. Holds get auto-released
otherwise — useful for testing (re-running against the same site/date works
once the previous hold expires).

---

## Things that DO NOT work

- **Playwright `.click()` on the React availability grid cells.** The cells
  visually highlight but React's internal state never updates — the Add to Cart
  button stays disabled, no API call fires. Tried `.click()`, `dispatchEvent`,
  CDP `Input.dispatchMouseEvent`, fiber-tree `onClick` invocation. None
  trigger the booking flow.
  → Skip the grid entirely. Use the API.

- **2captcha tokens for `gate_a`.** Always returns `"abnormal activity"` —
  recreation.gov binds reCAPTCHA Enterprise tokens to browser-session signals
  that 2captcha can't replicate. Tested with v2 checkbox, v3 enterprise,
  `min_score=0.9`, with/without enterprise flag, all 4 `terminal` directions,
  with/without warmup requests. Always rejected.

- **`curl_cffi` with chrome impersonation.** TLS fingerprinting wasn't the
  gate — same `"abnormal activity"` error. The captcha-context binding is
  the real check.

The only thing that works is generating the token in a live browser session
(real Chrome via browser-harness, or a launched Playwright Chromium).
