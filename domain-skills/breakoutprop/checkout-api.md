# breakoutprop.com — checkout & promo API

## URL patterns
- Pricing: `https://www.breakoutprop.com/pricing` (tier toggle $5K–$200K; "Start Evaluation" anchors open `portal.breakoutprop.com/checkout?productId=<uuid>` in a NEW tab — the pricing tab does not navigate).
- Checkout accepts `?promo=CODE` (or `code=`) as a URL param; the SPA reads it into the cart store (`pendingPromo`).
- The portal checkout SPA can sit on a spinner indefinitely for a fresh logged-out session — use the API directly instead.

## Private API (public, no auth needed)
Base: `https://btg-prod-api.breakoutprop.com`

- `GET /users/products` — full product catalog with UUIDs, sizes, costs, targets. Works logged out.
- `GET /checkout/status`, `GET /checkout/headroom` — availability + funded-cap headroom.
- `POST /checkout/validate` — the price-quote endpoint. Body:
  ```json
  {"items":[{"sku_id":"<productId uuid>","attributes":[],"quantity":1}],
   "email":"required@example.com","platform":"BREAKOUT","profit_split":false,
   "promo_code":"CODE"}
  ```
  Response: `validated_total`, `validated_subtotal`, `validated_discount_amount`,
  `discount_percent`, `code_type` ("affiliate"), `discount_applied`, `promo_error`,
  `discount_scope` ("all" | "none" | "needs_login"), `is_new_user`.
  `email` is a required field (400 without it).
- Other endpoints: `/checkout/session` (card), `/checkout/paypal-session`, `/checkout/confirmo-session` (crypto), `/checkout/finalize`, `/checkout/first-purchase-check`, `/checkout/prefill-email`, `/users/referral`.

## Traps
- **CORS**: `POST /checkout/validate` from a page-context `fetch` on the portal origin fails ("Failed to fetch" on preflight). Workaround: open a tab directly on `https://btg-prod-api.breakoutprop.com/checkout/status`, then `fetch('/checkout/validate', ...)` same-origin — no CORS at all.
- **Cloudflare**: curl from a server IP gets the "Just a moment..." challenge on both portal assets and the API. Go through the browser.
- Simple GETs to the API from any page context work fine (no preflight).

## Promo code facts (verified 2026-08-31)
- Every valid code is `code_type: "affiliate"` at exactly **2%** (DRAFT, INVEST, ASFX, WF8QS6, DQS380, KRAKEN all identical). Coupon-site claims of 20–50% are false; G2KB5D and BREAKOUT return "Invalid or expired code". There is no deeper public discount tier.
