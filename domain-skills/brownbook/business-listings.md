# Brownbook business listings

## Routes and state

- Start at `https://www.brownbook.net/add-business`.
- Public profiles use `/business/<numeric-id>/<slug>`.
- Registration and email activation can be required to claim and manage a listing. A successful registration is not evidence of a published profile.
- The claim flow can offer a separate paid service or trial. It is not necessary to purchase it to complete a basic listing.

## Editing and verification

- The editor's floating save control has ID `save-business-changes`.
- Saving may leave the editor open without a conspicuous receipt. Reload the public profile and check that the description actually persisted before retrying.
- Check the public website anchor as well as the description. A signed-in owner's view is insufficient proof of anonymous access; use a disposable browser context for a signed-out read, then dispose it.
- Raw HTTP can receive a challenge page while the profile loads normally in Chrome. Do not infer the profile's robots directives or link attributes from the challenge response.
- Inspect address and phone requirements at runtime. Leave optional fields blank when the owner has not supplied them.
