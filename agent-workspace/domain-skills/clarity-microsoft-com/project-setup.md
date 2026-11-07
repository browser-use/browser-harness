# Microsoft Clarity — project setup and installation checks

Host: `https://clarity.microsoft.com`

## Useful routes

- `/projects` — authenticated project list and the `New project` action.
- `/projects/view/<project-id>/gettingstarted` — project onboarding.
- `/projects/view/<project-id>/gettingstarted/trackingCode` — the canonical tracking snippet for an existing project.

Going to `/` while signed in normally redirects to `/projects`.

## Account verification lock

Clarity can show an existing project while keeping project actions locked until the account email is verified. This state is easy to mistake for a missing permission or a stale login.

If a project card says access is locked:

1. Use the visible `Verify email` action.
2. Send the verification email from the modal.
3. Complete the link in the same signed-in Chrome profile.
4. Return to `/projects`; the `New project` action should now be enabled.

The verification message is sent by Microsoft Clarity and has a subject similar to `Verify email to access Clarity`. Treat its link as a secret: never print it, store it in a domain skill, or copy it into logs.

## Create a project

From `/projects`, activate `New project` and fill the modal fields:

- Name
- Website URL
- Industry

The industry control is an ARIA listbox. Its choices are exposed as elements with `role="option"`, which is more stable than CSS-module class names.

After creation, Clarity navigates to `/projects/view/<project-id>/gettingstarted`. Read the public project ID from the URL or the tracking-code route; do not infer it from the project name.

## Verify the installed tag

The project-specific script URL is:

```text
https://www.clarity.ms/tag/<project-id>
```

For a consent-gated integration, verify both states in the browser:

```python
# Before consent: there should be no Clarity script or resource request.
scripts = js("[...document.scripts].map(s => s.src).filter(u => u.includes('clarity.ms'))")
resources = js("performance.getEntriesByType('resource').map(e => e.name).filter(u => u.includes('clarity.ms'))")
assert scripts == []
assert resources == []
```

After accepting consent, reload with the Network domain enabled and inspect events returned by `drain_events()`:

```python
cdp("Network.enable")
drain_events()
cdp("Page.reload", ignoreCache=True)
wait(6)
events = drain_events()

responses = []
for event in events:
    if event.get("method") != "Network.responseReceived":
        continue
    response = event.get("params", {}).get("response", {})
    if "clarity.ms" in response.get("url", ""):
        responses.append((response["url"], response.get("status")))
```

Expected signals are HTTP 200 for the project tag and Clarity runtime, followed by HTTP 204 responses from `https://s.clarity.ms/collect`. The consent banner should also be gone and the site's own consent cookie should show the accepted state.

## Traps

- A successful project creation does not prove the production site is collecting. Verify the exact public project ID and a live `collect` response.
- Clarity's dashboard can take time to reflect a new installation. Browser network proof is the faster acceptance check.
- Avoid relying on generated CSS classes. Prefer visible button text, ARIA roles, direct routes, and the project ID in the URL.
- Never document verification links, cookies, session tokens, or share URLs containing access tokens.
