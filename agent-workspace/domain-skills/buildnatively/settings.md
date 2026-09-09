# BuildNatively / Natively Settings

Use a dedicated browser session; the dashboard is a Bubble app and the settings UI is easier to verify through the Bubble Data API than through DOM text alone.

Useful URLs:
- Dashboard: `https://app.buildnatively.com/`
- App settings: `https://app.buildnatively.com/app-dashboard/<app_id>?tab=settings`
- App Android build: `https://app.buildnatively.com/app-dashboard/<app_id>?tab=distribution&sub=android-build`
- App iOS build: `https://app.buildnatively.com/app-dashboard/<app_id>?tab=distribution&sub=ios-build`
- Bubble object read API: `/api/1.1/obj/app__v2_/<app_id>` works from an authenticated browser session and returns persisted fields such as `APP_NAME`, `APP_URL`, `primary_language`, and `INTERNAL_REDIRECT_WHITELIST`.

Settings fields:
- App URL is the text input with placeholder `https://app.nocodenoprob.com/`.
- Primary Language is a disabled-looking Bubble dropdown input with placeholder `Select the primary language`.
- Internal URLs are stored in `INTERNAL_REDIRECT_WHITELIST` as strings that include quote characters, for example `"example.com"`.
- The Internal URLs `Add` button appears beside the `paypal.com` placeholder input after text is entered.
- The `Save` control is a clickable Bubble text/div, not a normal form submit button.

Quirks:
- Public Data API reads are allowed for app objects, but direct `PATCH /api/1.1/obj/app__v2_/<id>` can return `401 Unauthorized`; use the UI workflow for writes.
- The visible Primary Language option set currently includes only the app's configured language options. If a language is not in that option set, setting the input text manually does not persist after save/reload.
- For App URL changes, dispatch native `input` and `change` events on the input or use real typing; Bubble copies the input into the app group's `custom.app_url_` state before saving.
- The build pages show the plan chooser when the app is still on `APP_PLAN: "Preview"`. The top toggle may default to yearly pricing; click it back to monthly before choosing a trial when monthly is required.
- As of 2026-07-12, monthly plans shown in the build chooser were: Essential `$19/month`, 3-day trial, Android+iOS, limited 4 builds then `$9/build`; Unlimited `$49/month`, 14-day trial, Android+iOS, unlimited re-builds. Yearly display showed Essential `$12/month` (`$144 annually`) and Unlimited `$32/month` (`$384 annually`).
- Starting a trial redirects to Stripe Checkout (localized currency, `0.00` due today, first charge after the trial). Checkout still requires a payment method or Stripe Link verification before the trial can be activated.
