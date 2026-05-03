# TaskSquad — Authentication

Field-tested against tasksquad.ai on 2026-05-03 using a Chrome session.

## URLs

```
https://tasksquad.ai/auth          # login page (redirects to /dashboard if already signed in)
https://tasksquad.ai/auth/cli      # CLI token auth page
```

## Login page

The login page is a centered card with two OAuth buttons. No email/password form exists — SSO only.

```python
goto_url("https://tasksquad.ai/auth")
wait_for_load()
```

### Sign-in buttons

The card contains exactly two buttons:

| Visible label            | Provider |
|--------------------------|----------|
| "Continue with Google"   | Google   |
| "Continue with GitHub"   | GitHub   |

Both are `<button type="button">` inside a `<div class="px-6 pb-6 flex flex-col gap-3">`. Click by label text:

```python
# Google
click_at_xy(*find_text_coords("Continue with Google"))

# GitHub
click_at_xy(*find_text_coords("Continue with GitHub"))
```

After clicking, a browser popup opens for the OAuth flow. **Stop and ask the user to complete sign-in** — do not attempt to interact with the OAuth popup window.

### Auth-wall pattern

Any route under `/dashboard/*` redirects to `/auth` when the user is not signed in. If you navigate to a dashboard URL and land on `/auth`, the session is unauthenticated — ask the user to sign in before proceeding.

### Redirect after sign-in

Firebase Auth resolves the session client-side. After the OAuth popup closes, React's `onAuthStateChanged` fires and automatically navigates the user to `/dashboard`. Do not click anything — just `wait_for_load()` and verify with `page_info()`.

## Sign-out

There is no dedicated sign-out page. The sign-out action is triggered from the sidebar in `/dashboard`. Look for a `LogOut` icon button in the bottom-left sidebar area.

## Gotchas

- **The page is a React SPA.** Navigating to `/auth` while the app is still hydrating returns the bare `<div id="root">` with no buttons yet. Always call `wait_for_load()` and verify the "Continue with Google" text is present before clicking.
- **No error routes exist for failed OAuth.** On failure, the card renders an inline `<p class="text-sm text-red-500 text-center">` error message below the buttons.
- **`authed === null` loading state.** While Firebase resolves the session on `/auth`, the `<Login>` component is not rendered (the route renders `null`). Wait for buttons to appear before clicking.
