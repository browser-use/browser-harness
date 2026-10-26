# Cloudflare Pages: OAuth and private previews

## Dashboard and OAuth

- The account dashboard uses `https://dash.cloudflare.com/<account-id>/home`.
- Wrangler's browser OAuth entry point is `/oauth2/auth`. An existing signed-in dashboard session can briefly pass through `/login?login_challenge=...` before the SPA reaches `/oauth/consent-form?consent_challenge=...`. Wait for the rendered page before interpreting the URL as an authentication failure. If an actual credential form remains, stop for the user.
- The consent page identifies Wrangler as a Cloudflare-owned application. Review the displayed account and permissions, use the visible Authorize button, and verify the CLI reports successful login after the localhost callback. Never capture OAuth codes or tokens in domain skills.
- For a Pages-only task, Wrangler 4.152.0 accepts `wrangler login --browser=false --scopes account:read user:read pages:write`. It adds background access itself; passing `offline_access` explicitly to `--scopes` is rejected in that version. Check the installed version's help rather than copying scopes blindly.

## New Pages project delegation trap

Observed with Wrangler 4.152.0:

- Creating a new Pages project may delegate to the newer Workers-backed platform even though the command begins `wrangler pages project create`.
- If that delegation fails with a missing Worker entry point/assets directory, the diagnostic explicitly says nothing was deployed and describes a `--force` retry for direct Pages creation.
- Only when that diagnostic applies and direct Pages is the intended target, rerun the project creation with `--force` and the original project/branch options. The successful result says the project now exists and subsequent commands must omit `--force`.
- Do not keep retrying the unchanged command or add a Worker entry point merely to satisfy a delegation that changes the requested hosting product.

## Privacy covers more than the preview link

- Hashed deployment URLs are shareable and are not inherently private.
- The Pages built-in Access policy for preview deployments does not automatically protect the production `<project>.pages.dev` hostname or custom domains. Verify the intended hostnames, not just the dashboard toggle.
- When using an advanced-mode `_worker.js` for a private review gate, configure its server-side secret before deploying and route every request through authentication, including images, JS, fonts, and direct asset URLs. A missing secret should fail closed.
- Keep review passwords out of client bundles and tracked files. Use encrypted project secrets, secure signed sessions, and private/no-store cache policies appropriate to each response.
- Verify anonymous requests to both the root and an asset, incorrect-password behavior, authenticated asset loading, and the stable production URL as well as the returned hash URL.

## Loading and browser verification

- `document.readyState === 'complete'` does not guarantee that a client-rendered landing page's fonts, lazy images, or entrance animation are ready. Check `document.fonts.status`, relevant `img.complete`/`naturalWidth` values, and a fresh screenshot before declaring assets broken.
- After a password POST redirects back to the same URL, take a new screenshot after the application renders; the first screenshot can catch the entrance animation and pending image requests.

References: [Pages preview access behavior](https://developers.cloudflare.com/pages/configuration/preview-deployments/), [Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/).
