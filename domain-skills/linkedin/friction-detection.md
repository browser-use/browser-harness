# LinkedIn friction detection

Inspect the URL, visible body text, modal text, and after-screenshot before and
after every write. Match case-insensitively and allow surrounding words. Do not
attempt to dismiss, solve, or work around friction.

## Friction signals

| Signal | Detection | Immediate response |
|--------|-----------|--------------------|
| Captcha | Visible text containing `captcha` | Stop all outreach channels for 72 hours |
| Security check | Visible text containing `security check` | Stop all outreach channels for 72 hours |
| Restricted account | Visible text containing `restricted` | Full stop until Marco resolves it |
| Unusual activity | Visible text containing `unusual activity` | Stop all LinkedIn actions for 7 days |
| Re-verification | Visible request to verify or re-verify identity, phone, email, or account | Stop for the day |
| Weekly invitation limit | Visible text containing `weekly invitation limit` or a clear equivalent | Turn connects off for 7 days |
| Checkpoint route | URL contains `/checkpoint` | Full stop |
| Login route | URL contains `/login` | Full stop |

Exact DOM selectors for these surfaces are `TO-VERIFY`. Detect them from the
current URL and visible text, not from guessed classes.

## Halt ladder

1. Stop input at once. Do not click through, retry, refresh in a loop, open
   another LinkedIn tab, or switch routes to test whether the block is local.
2. Take one screenshot of the complete visible state and read back the URL.
3. Record the exact friction text, URL, time, planned action, and active account
   in the run evidence and authoritative `state/caps.json`.
4. Apply the matching halt:
   - Captcha or security check: all outreach channels stop for 72 hours.
   - Unusual activity: 7 days.
   - Re-verification: the rest of the day.
   - Weekly invitation limit: connects off for 7 days.
   - Restricted, `/checkpoint`, or `/login`: full stop until Marco resolves it.
5. Notify Marco with the exact visible string and URL. Do not claim the account
   recovered from a clean feed in another tab.
6. At the end of a timed halt, inspect read-only surfaces first. Resume only
   when no friction remains, then restart at ramp day 1 levels.

## Credential rule

Never type usernames, passwords, passkeys, one-time codes, recovery codes,
phone numbers, or identity details. Never approve a login prompt or perform
account recovery. If LinkedIn asks for any credential or verification input,
stop and leave the page visible for Marco.

## Non-friction harness failure

`WebSocket connection closed` is a stale-daemon symptom, not LinkedIn friction.
Run `admin.restart_daemon()` once, then read back the controlled tab, URL, and
page state. If the page now shows any friction signal, apply the halt ladder.
If the daemon still fails, stop the session without retrying LinkedIn actions.

## Unknown warnings

Treat any unknown warning, challenge, action block, disabled write control, or
unexpected redirect as friction until reviewed. Record its exact text and URL.
Do not invent a selector or classify it as harmless from layout alone.
