# Microsoft 365 — custom-domain setup

## Routes

- Admin portal: `https://admin.cloud.microsoft/`.
- Domains: `https://admin.cloud.microsoft/#/Domains`.
- Users: `https://admin.cloud.microsoft/#/users`.
- DKIM: `https://security.microsoft.com/authentication?viewid=DKIM`.

## Domain wizard

Domain verification and DNS setup are separate steps. A verified domain may remain marked as having incomplete setup until its required service records pass validation.

The DNS record groups expand with buttons whose `aria-label` describes the record type and expansion action. Clicking the adjacent heading text may do nothing. In a Dutch portal these labels include `records` and `uitvouwen`.

Advanced service options expose a DKIM checkbox. Read both selector targets from the tenant's wizard rather than generating them from the initial tenant domain: newer Microsoft DKIM targets contain a tenant-specific partition under `dkim.mail.microsoft`.

Wizard transitions may continue asynchronously after the ordinary page-load event. Wait for the next wizard heading or validation result before clicking again.

## User address editor

The Users page may cache its domain list. Reload after verifying a new domain if it is missing from the primary-address or alias dropdown.

Changing the primary address in the dialog is a draft until the dialog's final save succeeds. Verify the user record after saving; a local form update or sign-out alone does not prove the change persisted.

Maintain separation between tenants. When an existing Chrome profile signs into a corporate tenant automatically, use a separate browser context in that same running Chrome instance for a new business tenant, and verify the account shown before any purchase or administrative mutation.
