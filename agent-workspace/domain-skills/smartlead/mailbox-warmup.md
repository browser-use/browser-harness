# Smartlead mailbox connection and warmup

## Routes and navigation

- Application: `https://app.smartlead.ai/`.
- Sender accounts: `/app/email-accounts`.
- Account tabs use `/app/email-account/<id>/<tab>`. Replace `<tab>` with `overview`, `general`, `warmup`, `management`, or `campaigns`.
- The profile menu exposes Settings, then Subscription for plan selection.
- New accounts require a verification email before onboarding. The verification link opens a new tab; keep it in the same browser context as the mailbox and Microsoft login.

## Outlook OAuth

- Connect Mailbox opens a provider dialog. Outlook opens a second dialog with Microsoft 365 prerequisites and a Connect Account button.
- Outlook's label is `p.provider-text` inside a clickable `.email-connect-card`; selecting only buttons misses it. Locate the provider by `textContent` and confirm visibility.
- The prerequisite dialog specifies enabled IMAP and Authenticated SMTP for the mailbox. Check the mailbox's actual settings before changing them.
- OAuth navigates the application tab through Microsoft login, account selection, and consent before returning to Smartlead. Verify the selected Microsoft account rather than assuming the current browser identity.
- Confirm Smartlead's connection success message and the sender account row. Microsoft accepting consent alone does not establish a successful connection.
- Navigation and Vue updates can lag behind immediate DOM reads or screenshots. Re-read after the rendered state settles. An isolated HTTP 400 after OAuth was followed by a successful native retry; diagnose the visible error before retrying or changing Microsoft tenant policies.

## Warmup settings

Stable selectors include:

- `[data-sa=email-account-detail-tab-warm-up]`
- `[data-sa=warmup-enable-toggle]`
- `[data-sa=warmup-emails-per-day-input]`
- `[data-sa=warmup-rampup-toggle]`
- `[data-sa=warmup-rampup-increment-input]`
- `[data-sa=warmup-reply-rate-input]`
- `[data-sa=warmup-save-btn]`

The page uses Quasar controls. Switch state is exposed by `aria-checked`; hidden native checkbox inputs are not useful visible targets. The random daily range uses `.q-range[role=slider]`, with `aria-valuenow` formatted as `minimum|maximum`. Inbound replies use a separate slider and are distinct from the reply percentage input.

Changing the total daily limit can reset **both** random-range endpoints to the new limit. Inspect and set the random range after editing the total. The rendered range track can still span a broader numeric scale than its declared `aria-valuemax`; verify the resulting `aria-valuenow` after pointer or keyboard changes rather than inferring it from the track width.

Enable warmup saves the configuration and shows an informational alert. Reopen the account from the sender list to verify persistence. The list has a Warmup Enabled column; Overview shows the enable date and activity counters, which can remain zero immediately after activation.

## Subscription checkout

Plan selection can include optional paid verification credits. Inspect the checkout's selected add-ons, billing interval, first-month total, and renewal price before payment. Promotions shown in the app may apply only to the first month.

Card input is in an iframe titled `Secure card payment input frame`. The purchase modal has its own scrollbar. A floating Smart Assistant ask box can overlap lower controls; dismiss it or scroll the modal to expose the payment fields.
