# Browser Use Cloud — Programmatic Automation

`https://api.browser-use.com/api/v3` (REST). All five endpoints below were
exercised end-to-end on 2026-05-05 with a real `BROWSER_USE_API_KEY`; the
companion script `cleanup-zombies.py` next to this file *is* the
field-test — running it lists active browsers and stops zombies via the
same wire calls the harness uses internally.

This skill is for users who already start cloud browsers via
`start_remote_daemon()` and want to manage the surrounding lifecycle —
provisioning fleets, cleaning up zombies, listing what's running, sharing
liveUrls — without clicking through `cloud.browser-use.com`.

## Auth

REST uses a custom header (not `Authorization: Bearer` — that path
returns a generic 401 silently):

```python
import os
HEADERS = {
    "X-Browser-Use-API-Key": os.environ["BROWSER_USE_API_KEY"],
    "Content-Type": "application/json",
}
```

The key only authorises actions on browsers and profiles created under
it — there are no organisation-level admin endpoints on the public API.

## Endpoint reference

All paths are under `https://api.browser-use.com/api/v3`. Verified status
codes and shapes from 2026-05-05 below.

### `POST /browsers` — provision a cloud browser

Body (camelCase):

| Key | Type | Notes |
|---|---|---|
| `profileId` | UUID | optional; logged-in cloud profile |
| `profileName` | str | optional; resolved client-side |
| `proxyCountryCode` | ISO2 | default `"us"`; pass `null` to disable BU proxy |
| `timeout` | int | minutes, 1..240 |
| `customProxy` | obj | `{host, port, username, password, ignoreCertErrors}` |
| `browserScreenWidth` / `browserScreenHeight` | int | viewport |
| `allowResizing` | bool | viewport user-resizable |
| `enableRecording` | bool | session recording |

Returns `201` with this shape (also returned by `GET /browsers/{id}`,
`GET /browsers` items, and `PATCH /browsers/{id}`):

```python
{
    "id": str,
    "status": str,                  # e.g. "active"
    "liveUrl": str,                 # host: live.browser-use.com (different from cloud.browser-use.com)
    "cdpUrl": str,                  # https:// — daemon converts to ws via /json/version
    "timeoutAt": str,               # ISO 8601 UTC
    "startedAt": str,
    "finishedAt": None,             # populated only after stop
    "proxyUsedMb": str,             # STRING — cast to float before arithmetic
    "proxyCost": str,               # STRING
    "browserCost": str,             # STRING
    "agentSessionId": None,
    "recordingUrl": None,           # str only when enableRecording=True at create
}
```

The `liveUrl` carries the cdp WebSocket as a `?wss=...` query param, so
sharing the URL alone hands off a viewable session — no extra setup.

### `PATCH /browsers/{id}` — stop (end billing)

Body `{"action": "stop"}`. Returns `200` with the same browser object,
but `liveUrl` and `cdpUrl` come back as `null` and `finishedAt` is
populated. Use the returned `proxyCost` + `browserCost` for final cost.
Always wrap caller code in `try/finally`; every billed minute counts.

### `GET /browsers` — list active sessions

Returns `200` and the standard envelope
`{items: [...], totalItems, pageNumber, pageSize}`. `items[*]` matches
the `POST /browsers` response shape. Already-finished browsers appear in
the listing for a window with `finishedAt` populated — filter them out
when computing age.

### `GET /profiles?pageSize=N&pageNumber=N` — list cloud profiles

`pageSize` caps at 100. Same envelope as `/browsers`.

### `GET /profiles/{id}` — profile detail

Returns the same shape as the listing items:

```python
{
    "id": str,
    "userId": None,                 # null in observed responses
    "name": str,
    "lastUsedAt": str | None,       # null until first use
    "createdAt": str,
    "updatedAt": str,
    "cookieDomains": list[str] | None,  # null on freshly-created profiles
}
```

`browser_harness.admin.list_cloud_profiles()` already wraps the listing
+ per-id GET; prefer it unless you need raw access.

## Companion script: `cleanup-zombies.py`

A self-contained operator script next to this file. Run it with:

```bash
BROWSER_USE_API_KEY=... python agent-workspace/domain-skills/browser-use-cloud/cleanup-zombies.py
# stops every active browser older than 30 minutes (default)

BROWSER_USE_API_KEY=... python .../cleanup-zombies.py --older-than 5 --dry-run
# preview only; no PATCH /stop sent
```

The script is the practical residue of the API verification — running it
exercises four of the five endpoints (`GET /browsers`, plus
`PATCH .../stop` per zombie). Use it as the live regression check
whenever this skill is updated.

## Dashboard navigation (when API isn't enough)

The dashboard at `cloud.browser-use.com` requires a logged-in session;
the unauthenticated root redirects to `/signup` (verified 2026-05-05).
Beyond `/signup` the slugs below are *inferred from typical SaaS layout*
— confirm in your own browser before relying on the literal paths:

```
/signup                 (verified)
/dashboard              [verify]
/browsers               [verify] — likely the dashboard mirror of GET /browsers
/browsers/<id>          [verify]
/profiles               [verify]
/api-keys               [verify]
```

There is no `/usage` page mirror — `GET /usage` on the API returns 404,
so per-session cost has to come from each browser record (`proxyCost` +
`browserCost`). The dashboard surfaces aggregate billing somewhere, but
that's outside the API surface and not useful from inside `bh`.

For dashboard scraping, attach to your real Chrome and read cookies:

```python
cookies = cdp("Network.getCookies", urls=["https://cloud.browser-use.com"])
parts = [c["name"] + "=" + c["value"] for c in cookies.get("cookies", [])]
dash_headers = {"Cookie": "; ".join(parts), "Accept": "text/html,application/json"}
```

Empty cookie jar = not logged in; open `cloud.browser-use.com` in your
real Chrome once, then retry.

## Traps to avoid

- **Auth header name** is `X-Browser-Use-API-Key`. `Authorization:
  Bearer ...` silently fails with a generic 401.
- **Cost fields are strings**, not numbers. `proxyCost`, `browserCost`,
  `proxyUsedMb` come back as quoted strings (`"0.0123"`); cast to
  `float` before arithmetic.
- **`cookieDomains` can be `None`** on freshly-created profiles, despite
  what `admin.py:list_cloud_profiles`'s docstring says. Guard with
  `c or []`.
- **`liveUrl` host is `live.browser-use.com`**, not
  `cloud.browser-use.com`. They're separate surfaces.
- **`start_remote_daemon` overwrites `BU_CDP_WS`** in the daemon env;
  re-read from `browser["cdpUrl"]` if you need the value afterwards.
  (PR #300 stops `run.py` from clobbering an explicit `BU_CDP_URL`, but
  the daemon env still gets set.)
- **`liveUrl` is single-session** — after stop, the URL no longer
  resolves; don't cache across calls.
- **`_browser_use` has a 60s timeout** in `admin.py`; long-running ops
  (large profile sync) need their own polling.
- **`profile-use` CLI is a separate install**:
  `curl -fsSL https://browser-use.com/profile.sh | sh`.
- **`pageSize` caps at 100** silently — paginate via `pageNumber`.
  `totalItems` in the envelope lets you size loops up front.
- **`proxyCountryCode` defaults to `"us"`** when omitted; pass `None` to
  disable BU proxy entirely. Wrong country = wrong egress IP = breaks
  geo-locked auth.

## What this skill does NOT cover

- **Billing / payment methods** — dashboard only, intentionally
  sensitive.
- **Organisation / team admin** — outside the per-API-key surface.
- **SDK features** — Browser Use ships official SDKs separately; this
  skill is the raw-HTTP path for power users inside `bh`.
- **Cross-API-key reads** — every endpoint is scoped to the calling key.

## Provenance

Live-tested 2026-05-05 against `https://api.browser-use.com/api/v3`:

| Endpoint | Method | Status | Notes |
|---|---|---|---|
| `/profiles?pageSize=100&pageNumber=1` | GET | 200 | shape verified |
| `/profiles/{id}` | GET | 200 | `cookieDomains=None` observed on a fresh profile |
| `/browsers` | POST | 201 | `liveUrl` host is `live.browser-use.com` |
| `/browsers/{id}` (`{action:"stop"}`) | PATCH | 200 | returns final cost |
| `/browsers` | GET | 200 | paginated `{items,totalItems,pageNumber,pageSize}` |
| `/usage` | GET | 404 | **no public endpoint** |
| `/` | GET | 404 | no root metadata |

Companion script `cleanup-zombies.py` re-runs the listing + stop subset
end-to-end and is the regression artefact for this skill. A full E2E
loop (spawn → list → stop → re-list) was executed on 2026-05-05 against
the production API and printed:

```
[STOP] 3ac4c964-...-d3d3e1ad7508  age=  0.0min  cost=$0.0020
summary: 1 active session(s), stopped 1
```

Re-running the script in `--dry-run` mode against an empty pool is the
cheapest smoke test (no `PATCH /stop` calls, ~$0).
