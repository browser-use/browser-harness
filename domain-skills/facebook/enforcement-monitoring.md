# Facebook / Meta enforcement monitoring (read-only)

Use the logged-in browser to compare the separate Meta enforcement surfaces without creating cases, submitting appeals, or changing account/business settings.

## Direct routes

| Surface | URL |
|---|---|
| Business Support Home | `https://business.facebook.com/business-support-home/` |
| Personal Facebook-account enforcement | `https://business.facebook.com/business-support-home/{facebook_user_id}/?source=link` |
| Business portfolio status | `https://business.facebook.com/business-support-home/{business_id}/?source=link` |
| Facebook Account Status | `https://www.facebook.com/account_status` |
| Identity Confirmation | `https://www.facebook.com/id/hub/` |
| Facebook Support Inbox | `https://www.facebook.com/support?ref=contextual` |
| Support Inbox — alerts/appeals | `https://www.facebook.com/support/?tab_type=APPEALS` |
| Support Inbox — reports | `https://www.facebook.com/support/?tab_type=REPORTS` |

### Support Inbox route trap

Use `https://www.facebook.com/support?ref=contextual` (no slash before the query) for the inbox landing page. The superficially equivalent `https://www.facebook.com/support/` can redirect to `/hacked` instead of opening Support Inbox.

The canonical route can also be rediscovered from the Facebook profile menu:

1. Open **Your profile**.
2. Open **Help & support**.
3. Read the **Support Inbox** link; its current `href` is the preferred route.

## Stable visible anchors

On the personal-account Business Support page, capture exact visible text for:

- `Account restricted` or the replacement status.
- The enforcement date.
- The explanatory paragraph.
- Every item under `Restrictions`.
- Any controls containing `Request Review`, `What you can do`, `Confirm identity`, `Secure account`, `Contact support`, `Appeal`, or `Specialist`.

The restriction summary may be a non-interactive card: the `Account restricted` text and its ancestors can have no `role`, `href`, or `tabindex`. Do not assume it opens details when clicked; the user-ID route itself is the detail surface.

On Account Status and Identity Confirmation, compare the exact visible headline and explanatory sentence rather than trying to reconcile them with Business Support state. These are separate enforcement surfaces and can legitimately disagree in the UI.

## Support-case checks

Business Support Home has a **Your support cases** section with `Active` and `Resolved` elements using `role="tab"`. It may live below the viewport in an internally scrolling page. Locate the `Resolved` tab whose nearby ancestor text contains `Your support cases`; the earlier `Resolved` tab belongs to **Recent account issues**.

Facebook Support Inbox separates items into:

- the landing/default category (`/support?ref=contextual`),
- alerts/appeals (`?tab_type=APPEALS`), and
- reports about others (`?tab_type=REPORTS`).

Item links use `support/?item_id=...`. Compare each item's exact title, update marker, date, and open/closed label. An old item marked `1 new update` is not evidence of a newly created case without a prior baseline or a recent date.

## Read-only boundaries

- Stop at login, password, passkey, 2FA, or identity-document prompts.
- Do not click controls that create a support case, submit feedback/appeals, begin verification, or change security/business settings.
- Do not inspect or log cookies, tokens, credentials, authentication codes, or identity documents.
- Re-screenshot after opening a read-only tab or category and verify the final URL before interpreting the page.
