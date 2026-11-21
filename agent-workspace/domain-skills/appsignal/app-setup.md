# AppSignal — app creation and notification scope

Applies to `appsignal.com`.

- GitHub sign-in can be followed by AppSignal's own authenticator challenge;
  finishing GitHub authentication does not necessarily finish AppSignal sign-in.
- `/<organization>/sites/new` offers installation paths. Language/framework paths
  can lead only to agent instructions. To create a named app before telemetry arrives,
  follow Configure logs / Add APM later to `/<organization>/sites/create`, then set
  `input[name=name]` and `input[name=environment]`. Confirm the app in the inventory.
- The app's Push & deploy settings can use `/sites/<app-id>/info` or
  `/sites/<app-id>/api_keys`. Distinguish the organization-level Push key from the
  key limited to that app and environment. Hidden tabs can remain in the DOM; select
  each key by its explanatory section, not its position among `code` elements.
- Personal operator API tokens are separate from Push keys and can be shorter than
  generic redaction thresholds. Never emit authenticated page bodies, key sections,
  or credential-bearing URLs. Extract secrets in memory and emit only safe metadata.
- The profile at `/users/edit` displays the personal token under `Your personal API
  token is:`. Its rotation link targets `/users/roll_authentication_token` with
  `data-method="put"` and may have no confirmation prompt. Treat clicking it as
  the rotation itself: verify every credential-store target first, then capture
  the replacement in memory and read-verify each saved copy. A failed verification
  request is not evidence that rotation failed; compare the profile and saved
  copies before retrying. Avoid screenshots of the profile.
- An app's Notifications settings can redirect to organization-wide notifiers.
  Existing notifiers do not automatically include a new app when Enable for new
  apps is disabled. Edit the intended notifier and select only the new app's
  `input[name="notifier[site_ids][]"]` value; preserve recipients, event settings,
  and existing app selections. Save all changes, reload, and verify persistence.
- Compositor clicks on a background tab may be ignored. Avoid interrupting a human
  verification handoff in another tab. For an ordinary HTML checkbox, `click()` on
  the exact observed element dispatches normal change events without activation;
  verify all named form fields before submitting. Unnamed selection shortcuts can
  change as a derived consequence of selecting the final app.
