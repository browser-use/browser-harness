# Coupang Supplier Hub Auth And CDP Session

## Canonical Shape

- Host: `https://supplier.coupang.com/`
- Browser path: `CdpChromeSession` through browser-harness CLI/daemon IPC.
- Use a dedicated non-default Chrome profile. Do not rely on the user's default Chrome profile.
- Fresh workflow session is the default for Coupang 1P. Reuse is allowed only inside one workflow when the code owns cleanup and state checks.
- Public CDP workflows must close the session in `finally`, including failures after artifact capture.

Relevant code:
- `coupang-1p-auto/infrastructure/bots/bot_coupang_1p.py`: `_get_cdp_session`, `cdp_login_if_needed`, `_run_cdp_registration_workflow`, `_run_cdp_download_workflow`, `_close_cdp_session`
- `coupang-1p-auto/infrastructure/external_services/cdp_chrome.py`: `CdpChromeSession`

## Login State Classification

Treat these as hard blocks:
- HTML contains `Access Denied` plus permission/reference wording.
- URL or HTML contains `errors.edgesuite.net`.
- Account lock or human decision pages.

Treat these as normal flow states:
- `xauth.../auth/...` redirect with visible username/password fields.
- Known Supplier Hub paths that render a warning modal but still have the expected business page underneath.

Do not mark a normal auth redirect as an anti-bot wall just because the URL is not the target URL yet.

## Automated Login

The CDP path should:

1. Navigate to a Supplier Hub page.
2. Detect login fields.
3. Fill username/password from the configured credentials source.
4. Click the login button.
5. Wait until either a known Supplier Hub page appears or a hard block is detected.

Do not store real credentials in this skill. Local credentials belong in the existing local variables mechanism such as `.variables.local` and environment variables handled by the app.

## Manual Handoff

Manual login handoff is a separate CDP path, not a reason to fall back to Selenium for side-effecting work.

Manual handoff messages should include:
- Sanitized current URL with query removed.
- Reason code.
- Screenshot/DOM artifact paths when available.
- Clear instruction not to press business action buttons.

After manual login, copy only the session state needed by retained legacy compatibility. The browser profile remains the primary state store for CDP workflows.

## Session Reuse Rule

For Coupang 1P, the safer default is:

- Start or attach a workflow-scoped CDP session.
- Execute one business workflow.
- Capture artifacts on failure.
- Close CDP session and automation-launched Chrome when done.

This avoids stale modal state, old downloads, partially registered forms, and hidden tabs leaking into the next workflow.
