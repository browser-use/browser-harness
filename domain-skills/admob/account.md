# Google AdMob (admob.google.com)

## Is this Google account the one with the AdMob account?

- `https://admob.google.com/v2/home` opens the dashboard when the signed-in Google account has AdMob.
- Otherwise it redirects to `/signup?sac=true`, a page titled "Continue with this account?" with "Publisher account details". That page can list another Google publisher product (for example AdSense for YouTube) and its Publisher ID. **Its "Continue" button starts creating a new AdMob account** under that publisher, followed by phone verification. Never click it when the task is to find an existing account.
- `?authuser=N` picks another signed-in Google account. `/signup/info/user-age-missing?authuser=N` also means that account has no AdMob account.
- An AdMob App ID looks like `ca-app-pub-{publisherNumber}~{appNumber}`. To tell whether you're in the right Google account, compare its publisher number with the Publisher ID on the signup page. A mismatch means the app lives under a different Google login: stop and ask the user to sign in to that one.

## Traps

- Switching Google accounts (`authuser`) or passing through accounts.google.com can **replace the tab's CDP target**, giving it a new `targetId`. The daemon's session goes stale, and on the next call it re-attaches to the *first* page target, which may be one of the user's tabs. A screenshot or click then lands in the wrong tab. After any Google account switch, find your tab again with `list_tabs()` (match on URL) and `switch_tab()` to it before doing anything else.
- The user may be driving the same tab while you work, e.g. finishing a login or signup. If the URL or step changed without you acting, stop interacting with that tab.
