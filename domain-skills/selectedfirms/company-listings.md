# SelectedFirms company listings

## Entry and registration

- Entry: `https://selectedfirms.co/get-listed`; sign-in: `/login`.
- Registration first and last names have client-side minimum-length validation. Inspect validation errors rather than assuming initials are accepted.
- The site uses a W3 lazy JavaScript loader. Scripts can remain `type=lazyJs` until normal pointer or scroll interaction. A loaded HTML document does not prove jQuery, validation, or CAPTCHA initialization has completed.
- Use normal browser interaction and wait for the controls to initialize. Useful readiness observations are `typeof window.jQuery === "function"`, CAPTCHA presence, and loader classes such as `w3_js` and `jsload`. Do not inject CAPTCHA scripts or manufacture responses.
- Registration can redirect to the login page without a prominent success receipt. Confirm the account through sign-in or the relevant email before assuming registration failed and resubmitting.

## Company wizard

- Authenticated listing dashboard: `/agency/listing`; first wizard page: `/agency/step1`.
- Steps include basic information, locations, services, and clients/industries.
- Useful basic field names: `company_name`, `tagline`, `website`, `founded`, `company_summary`, `rate_hr`, `strength[0]`, `strength[1]`, `budget[0]`, and `budget[1]`.
- Logo upload control: `input#imageUpload`, name `image`. Inspect the site's current dimensions and cropping dialog.
- Published project budget, headcount, hourly rates, founding year, and client details must come from the company. A marketing budget is not a minimum project budget.
