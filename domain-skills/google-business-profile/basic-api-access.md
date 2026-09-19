# Google Business Profile Basic API Access workflow

## Prerequisites

The Cloud-side API toggle alone is not enough. Before applying, confirm:

- the signed-in Google identity is an owner or manager of the Business Profile;
- the selected profile is verified and has been active for at least 60 days;
- the business has a public website;
- you have the numeric Google Cloud project number, not only the project ID.

If the Business Profile Performance API quota page shows zero requests per minute, the project still needs Basic API Access approval.

## Application path

Open the official support workflow:

`https://support.google.com/business/workflow/16726127`

The current flow is:

1. Confirm the signed-in owner/manager identity.
2. Select the verified Business Profile from the table. The row uses a custom radio control; clicking the visible row may not select it, but clicking the nested `input.scSharedMaterialradionative-control` does.
3. Enter the numeric Cloud project number and public company website.
4. Describe how the form was found and the first-party reason for access.
5. Continue to submit the allowlist request.

The completion page returns a support case ID and an estimated review window. Save that non-secret case ID in the project runbook so future runs do not submit a duplicate application.

## Important boundary

Approval grants quota to the project; it does not replace user OAuth. Business Profile APIs require user authorization (normally the `business.manage` scope) for the Google identity that manages the listing. Do not try to use a service account as a substitute for the profile owner/manager.

