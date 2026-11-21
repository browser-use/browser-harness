# Cloudflare Access applications

Use the existing signed-in dashboard browser. Account IDs below are placeholders.

## Routes

The application list is at:
`https://dash.cloudflare.com/<account-id>/one/access-controls/apps`

Older `one.dash.cloudflare.com/<account-id>/access/apps` links may redirect to a dashboard route that displays "We could not find that page." Read the current Applications link from the dashboard navigation rather than assuming login expired.

An application's policy editor is linked from the application list:
`/<account-id>/one/access-controls/apps/rules/<application-id>/<policy-id>`

## Inspect and change

From the dashboard origin, a same-origin browser fetch to
`/api/v4/accounts/<account-id>/access/apps` returns applications, hostnames and policy summaries. Fetch a specific application and its `/policies` endpoint for fresh details. Keep backups private; never export account configuration or authentication data into this repository.

Use the normal policy editor for writes so the dashboard supplies its current request authentication and CSRF headers. The Emails value field uses chips: type an email into the existing rule's input and press Enter to commit it. Preserve existing chips. Save policy, then fetch the application's policies again to verify the saved include list and stable policy ID. Check the application audience and domains remain unchanged.

The application list may initially show loading skeletons after the load event; wait for actual rows. After saving a policy, the dashboard can return to the application's edit page rather than the application list.

Dashboard authentication does not automatically authenticate the browser to an Access-protected application. A separate application sign-in screen can be expected even when dashboard API requests succeed. Verify anonymous visitors are still sent to Access login, and distinguish policy persistence from testing the target user's actual login.
