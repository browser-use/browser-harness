# Microsoft Entra admin center — app registrations

`https://entra.microsoft.com` (the Azure AD portal). Registering an OIDC app, adding
redirect URIs, minting a client secret.

## First: don't drive the portal at all if `az` is available

The Azure CLI does this whole job deterministically, and `az login` completes through the
browser's existing Microsoft session — no password typed, often no click at all:

```bash
az login --allow-no-subscriptions          # SSO via the already-signed-in browser
az ad app create --display-name "My App" --sign-in-audience AzureADMyOrg \
  --web-redirect-uris "https://example.org/api/auth/callback/microsoft-entra-id"
az ad sp create --id <appId>
az ad app credential reset --id <appId> --display-name authjs --years 2 --append
az ad app permission add --id <appId> --api 00000003-0000-0000-c000-000000000000 \
  --api-permissions e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope   # Graph User.Read
```

`credential reset` returns the secret as JSON on stdout — pipe it straight to the file that
needs it. Unlike the portal it can be re-run, so a fumbled capture is not fatal.

`az ad app list --display-name "<name>"` first makes the whole thing idempotent.

Reserve the UI route below for when `az` is missing or the account can't use it. Driving
this portal carries a real risk of writing into the *wrong app registration* — see the tab
trap immediately below.

## The one thing that will bite you

**Each `browser-harness -c` invocation can re-attach to a different tab.** The portal is
usually open in several tabs at once, and the daemon's auto-attach does not preserve your
tab across runs. Symptoms: a click "works" but the next screenshot shows an unrelated page,
or typed text lands in some other site (and can fire that site's keyboard shortcuts).

Fix: **start every invocation with `switch_tab(<targetId>)`, and do a whole dialog —
open, fill, submit — inside ONE invocation.**

Worse: `switch_tab` alone is not sufficient proof you are where you think. The hash URL and
the rendered blade can disagree — `page_info()["url"]` can report `CreateApplicationBlade`
while the viewport is rendering *another app's* Authentication blade, because the portal
rewrites the hash before/after it swaps content. **Trust the screenshot, never the URL.**
Before any click that writes, confirm the app name in the rendered breadcrumb, not the hash.
Getting this wrong appends text into a live app's redirect URI field.

```python
ts = list_tabs(include_chrome=False)          # dicts: targetId / title / url
tid = [t["targetId"] for t in ts if "entra.microsoft.com" in t["url"]][0]

# then, in every subsequent run:
switch_tab(tid)
```

## Blade deep links

Blades are hash routes, so you can `goto_url` straight to one instead of clicking through:

```
#view/Microsoft_AAD_RegisteredApps/ApplicationsListBlade
#view/Microsoft_AAD_RegisteredApps/CreateApplicationBlade/quickStartType~/null/isMSAApp~/false
#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/Overview/appId/<appId>/objectId/<objId>/isMSAApp~/false
#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/Authentication/appId/<appId>/objectId/<objId>/isMSAApp~/false
#view/Microsoft_AAD_RegisteredApps/ApplicationMenuBlade/~/Credentials/appId/<appId>/objectId/<objId>/isMSAApp~/false
```

Note `~/Credentials` is the **Certificates & secrets** blade — the URL segment does not
match the menu label. The registration POST redirects to the Overview blade, so the new
`appId` / `objectId` are simply readable out of `page_info()["url"]`.

After a `goto_url` to a blade, `wait_for_load()` is not enough — the blade renders after
a further XHR. Sleep ~6-8s before clicking.

## Reading IDs: innerText works, DOM queries mostly don't

Blade *content* sits in nested frames/shadow roots, so `js("document.querySelectorAll('input')")`
from the top frame commonly returns nothing — but `js("document.body.innerText")` does
surface the blade text. That is the cheap way to pull values and to verify a change landed:

```python
t = js("document.body.innerText")
# "Application (client) ID <uuid>", "Directory (tenant) ID\n:\n<uuid>"
print([l for l in t.split("\n") if "callback" in l])   # verify redirect URIs
```

Because DOM writes are out of reach, **coordinate clicks + screenshots are the tool** for
everything else here.

## Portal inputs: never type into a non-empty field

`type_text` appends, and neither `Meta+a` nor a run of `Backspace` reliably clears a portal
input (backspacing can dismiss the whole dialog). If a field already has the wrong value,
**Cancel the dialog and reopen it** rather than trying to edit in place. A corrupted value
shows up as a red "Must be a valid URL" under the field, with Configure/Add greyed out.

## Redirect URIs (Authentication blade)

`Add Redirect URI` → platform card `Web` → `Select` → type the URI → `Configure`. Each
platform gets its own row group; adding a second URI to an existing Web platform goes
through the same dialog.

A `post_logout_redirect_uri` must itself be a registered redirect URI, so federated sign-out
needs the logout landing page registered too — otherwise skip the parameter and clear your
own session locally.

## Client secrets

Certificates & secrets → Client secrets tab → `New client secret` → description + expiry
(180 days is the default; 730 days / 24 months is the longest preset). **The Value is shown
exactly once, only right after creation** — it is masked on any later page load, and there
is no way to recover it. Leave it on screen for a human to copy; an agent that navigates
away has destroyed it and has to mint a new one.

## Traps

- "Owned applications" can show "this account isn't listed as an owner" immediately after
  you register an app. It is a stale list, not a failure — check **All applications** or
  the app's own blade.
- Screenshots come back at 2x (retina): a 1184x677 viewport screenshots as 2368x1354.
  Click coordinates are CSS pixels, i.e. half the raw image pixels.
- The Authentication blade is in preview and has an "old experience" toggle; the layouts
  differ, so re-screenshot rather than reusing a remembered layout.
- Backing out of a corrupted dialog is safe: `Cancel` on the URI dialog drops to the
  platform picker, and `Cancel` again closes it with **nothing written**. Verify afterwards
  by reopening the blade and diffing the URI list — an unsaved edit leaves no trace.
- Admin consent (`az ad app permission admin-consent`, or the "Consent on behalf of your
  organization" checkbox) is org-wide and belongs to the human. Without it each user simply
  self-consents once on first sign-in, which is a fine default for `User.Read`.
