# Brella / White-Label Event Networking

Use this when a conference networking app is backed by Brella or a white-label Brella host such as `*.brella.io`.

## Web Access

- Brella events can be available through both the generic web app (`next.brella.io`) and a white-label host (`<org>.brella.io`).
- White-label event URLs commonly look like:
  - `https://<org>.brella.io/join/<event-slug>`
  - `https://<org>.brella.io/events/<event-slug>/people`
- Mobile-only wording in an invite does not prove the attendee list is mobile-only. Check the web app before falling back to mobile automation.

## API Context

- Public event lookup can accept a join code:
  - `GET https://api.brella.io/api/public/events/<join-code>`
- Invite prefill data can be available at:
  - `GET https://api.brella.io/api/public/invites/<join-code>/prefill_data`
- White-label API requests may require the org context header:
  - `brella-organization-slug: <org-slug>`
- Without that header, event join calls can fail with `WRONG_APP` even when the code is valid.

## Joining

- Authenticated event join endpoint observed:
  - `POST https://api.brella.io/api/me/events/join`
  - Body: `{"code":"<join-code>","update_user_based_on_invite":true}`
- A join code may redeem into the currently authenticated account even when the invite email is different from that account. Treat this as site behavior, not a guarantee.
- If `update_user_based_on_invite` is true, Brella can copy invite prefill fields into the current profile. Check and clean up profile name/title/company before any outreach.
- Do not assume the original invite remains usable after redeeming it into another account.

## Networking State

- Me-attendee endpoint:
  - `GET /api/me/events/<event-slug>/me_attendee`
  - `PUT /api/me/events/<event-slug>/me_attendee`
- Onboarding completion endpoint:
  - `PATCH /api/me/events/<event-slug>/me_attendee/complete_onboarding`
- `skip-networking` can block chat/meeting behavior. Read the me-attendee state before assuming People is unavailable.

## People Extraction

- Attendees endpoint observed:
  - `GET /api/events/<event-slug>/attendees?page[number]=1&page[size]=100&order=newest&ignore_networking=true`
- Search works through query params:
  - `search=<term>`
  - `page[number]`, `page[size]`, `order`
- Use `curl --globoff` for URLs containing `page[number]` and `page[size]`; otherwise curl may treat square brackets as glob syntax.
- JSON:API responses include attendees in `data` and linked user profile fields in `included`. Join `data[].relationships.user.data.id` to `included[] | select(.type=="user")`.
- People extraction is much faster through the API than UI scrolling. Keep outreach read-only until the human approves specific targets and text.

## Browser Harness

- For Brella networking work, prefer a dedicated browser profile and CDP port so cookies, login state, and Chrome/Brave remote debugging prompts do not interfere with the user's normal browser.
- Example pattern:
  - profile dir: `~/.openclaw/browser-profiles/<event-name>`
  - Chrome args: `--user-data-dir=<profile-dir> --remote-debugging-port=<port> --no-first-run --no-default-browser-check`
  - harness env: `BU_NAME=<event-name> BU_CDP_URL=http://127.0.0.1:<port>`
- Verify with `page_info()` and a People page URL after login.
