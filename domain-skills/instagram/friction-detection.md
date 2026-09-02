# Instagram friction detection

Inspect visible text, modals, the current URL, and every after-screenshot. Do
not dismiss or work around an action block or account challenge.

## Stop strings

Match case-insensitively and preserve the full visible message:

| Signal | Immediate response |
|--------|--------------------|
| `action blocked` or `block` in a clear action-block notice | Stop Instagram writes for 72 hours |
| `try again later` | Stop Instagram writes for 72 hours |
| `challenge` in an account or security prompt | Stop Instagram writes for 72 hours |
| Any credential, login, or identity verification request | Full stop and leave it for Marco |

The exact URLs and DOM selectors for Instagram action-block and challenge
surfaces are `TO-VERIFY`. Do not invent patterns from LinkedIn or Facebook.

## Halt procedure

1. Stop input at once. Do not retry the action, refresh in a loop, open another
   Instagram tab, switch to another target, or test a different write type.
2. Take one screenshot and read back the current URL.
3. Record the exact visible text, URL, account, attempted action, and time in
   run evidence and the authoritative `state/caps.json`.
4. Stop all Instagram writes for 72 hours for an action block, `try again
   later`, or challenge.
5. Notify Marco with the exact string and URL.
6. After 72 hours, inspect read-only surfaces first. If clear, resume at week 1
   caps. Any repeated signal starts a new 72-hour stop.

## Notifications modal is not an action block

The notifications prompt that may appear on the first `/direct/` open is a UI
trap, not itself a friction signal. Its exact copy and buttons are `TO-VERIFY`.
Take a screenshot and dismiss it only through a clearly labelled safe choice.
If the modal includes security, challenge, login, or verification language,
treat it as friction instead.

## Credential rule

Never type a username, password, passkey, one-time code, recovery code, phone
number, or identity detail. Never approve a login prompt or perform account
recovery. Leave the page visible for Marco.

## Harness failure

`WebSocket connection closed` means the harness daemon may be stale. Run
`admin.restart_daemon()` once, then read back the tab, URL, and visible state.
Do not count or repeat the interrupted action. If a friction string appears,
apply the halt procedure. If the daemon still fails, stop the session.

## Unknown warnings

Treat any unknown warning, disabled write control, unexpected redirect, or
modal that blocks an action as friction until reviewed. Save its exact text and
URL. Do not infer safety from a clean-looking background page.

