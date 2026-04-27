# SSOForge — Portal Walkthrough

SSOForge is a Codaic-generated dual-platform CIAM product. It ships **two separate React frontends** that look identical at first glance — the portal (canonical user surface) and the service-frontend (component library + the only place ADW agents have write access). Routes can land in one and be invisible from the other. This skill captures the map so the next agent doesn't relearn it.

## URL pattern

| Surface | Default port | What it is |
|---|---|---|
| Portal | `5221` (or `5220` if free) | The canonical user surface. Hit this. |
| Service-frontend dev server | varies, often unrunning | Component library home. Routes here are NOT reachable through the portal unless re-exported via `@ssof/...` aliases. |
| Auth service | `8160` | JWT issuer. `POST /api/v1/auth/login`. |
| Domain service | `8090` | OpenAPI at `/openapi.json`, health at `/health/ready`. |

If the portal port is taken, vite falls through to the next free port (`5221`, `5222`, …). Don't assume `:5220`.

## The two-frontend trap

`services/ssoforge-portal/frontend/src/router.tsx` is the **portal** router (canonical).
`services/ssoforge-service/frontend/src/router.tsx` is the **service-frontend** router.

Codaic ADW agents have write access to `services/ssoforge-service/**` but the portal directory is write-blocked. This means new pages from ADW work consistently land in the service-frontend router, and need a separate operator pass to add re-export shims under `services/ssoforge-portal/frontend/src/modules/ssoforge/pages/` and a `<Route>` entry in the portal router.

When a route returns `body.innerText.length ≈ 5` (just the FORGE button) but the URL accepts navigation, the page exists as a component but isn't wired into the portal router. Check both routers:

```bash
grep -n "<Route path=" services/ssoforge-portal/frontend/src/router.tsx
grep -n "<Route path=" services/ssoforge-service/frontend/src/router.tsx
```

## Stable selectors

| Surface | Selector | Notes |
|---|---|---|
| Sign-in form | `input[name="username"]`, `input[type="password"]`, `button[type="submit"]` | MUI `<TextField>` with name attrs preserved |
| Wizard active step | `.MuiStepLabel-active` | Reliable across MUI versions |
| Wizard Next | `button` with `textContent === 'Next'` | use `js()` to find — the button position changes after step transitions |
| Sidebar nav entries | `a[href^="/ssoforge/"]` | flat list, group headers are sibling elements |
| FORGE FAB | `button` with class containing `forge` | bottom-right; coordinate-clicks at the page edge often hit this by accident |

## Coordinate-click pattern (DPR ≥ 2)

`click_at_xy` takes **CSS pixels**, not device pixels. On Retina (DPR=2), `capture_screenshot()` returns a `2x` image — reading pixel coords directly off the screenshot and clicking with them silently fails (clicks at 2x the intended location, off-screen or on wrong element).

The reliable pattern for SSOForge MUI buttons:

```python
out = js("""
  const btn = Array.from(document.querySelectorAll('button')).find(b => b.textContent.trim() === 'Next');
  btn.scrollIntoView({block: 'center'});
  const r = btn.getBoundingClientRect();
  return {x: Math.round(r.x + r.width/2), y: Math.round(r.y + r.height/2)};
""")
click_at_xy(out['x'], out['y'])
```

`getBoundingClientRect()` returns CSS pixels by definition — same units `click_at_xy` expects.

Re-fetch coords after any state change (step transition, scroll, modal open). MUI re-renders move buttons by tens of pixels.

## Authentication

The portal uses a session JWT from `auth-service`. Login lands on the portal home. Subsequent navigation does NOT auto-attach `Authorization` headers — those flow through the portal's auth context, so navigating to a protected route after login works without explicit token handling.

If a route returns 401 unexpectedly, check that the JWT hasn't expired (default 1 hour) — re-login rather than refreshing the token via API.

## Onboarding wizard structure

Four steps, gated:

1. **Tenant details** — text fields (tenant name, platform type, directory ID, tenant domain). Validates GUID format on directory ID. Next is enabled when all required fields are non-empty.
2. **Graph credentials** — Graph client ID + Graph client secret. **The "no active licence found" enforcement gate fires here on Next** — wizard step 2→3 transition calls `POST /api/v1/tenants` which is `@enforced(action=CREATE_TENANT)`; without a `LicenceActivation` row in the DB, you get a 402-like error rendered as a banner. Operator must run `ssoforge setup --licence-key <key>` first.
3. **Admin consent** — auto-popups a Microsoft Graph admin consent flow (Wave 7.B). For dev environments this is mocked / manual.
4. **Verification** — final review.

## Credential field autofill trap

(VALID until SSOForge Phase 3 Wave 10 ships W10.C.)

Chrome's saved-password manager auto-fills the Graph client ID + Graph client secret on wizard step 2 when the user has saved credentials for the SSOForge login (same origin). This silently injects the operator's login `username` into the Graph client ID and the password into the Graph client secret — operator can submit without noticing.

Mitigation when scripting: always clear the fields explicitly before typing, regardless of whether they appear empty in `getBoundingClientRect`-time DOM:

```python
js("""
  document.querySelectorAll('input').forEach(i => {
    if (i.offsetParent) {
      const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
      setter.call(i, '');
      i.dispatchEvent(new Event('input', {bubbles: true}));
    }
  });
""")
```

Once W10.C lands the `autoComplete="new-password"` fix, this section can be removed.

## Sidebar gaps to expect

Until Phase 3 Wave 10 ships, the SSOForge module sidebar in the portal is sparse. Many routes either don't exist as portal routes, or exist but aren't linked. Verified-reachable routes via portal:

- `/ssoforge` — module landing
- `/ssoforge/tenants/new` — onboarding wizard
- `/ssoforge/applications/:id` — detail (no list page)
- `/ssoforge/applications/:appId/branding/:themeId` — branding editor
- `/ssoforge/audit` — Wave 7.F audit log

Routes that resolve in the URL bar but render blank (component exists in service-frontend, not wired in portal router):

- `/ssoforge/applications` (list)
- `/ssoforge/identity-providers`, `/ssoforge/policies`, `/ssoforge/deployments`
- `/ssoforge/branding-themes`, `/ssoforge/integration-bundles`
- `/ssoforge/admin/licences`, `/ssoforge/billing`, `/ssoforge/usage-billing`

Confirming a route is genuinely live: `curl -fsS http://localhost:5221/<path>` returns 200 and `body.innerText.length > 50`.

## API patterns

OpenAPI lives at `http://localhost:8090/openapi.json`. Common surfaces:

- `POST /api/v1/auth/login` (port 8160, separate auth service) — returns `{access_token, refresh_token}`. Tenant ID for dev is `00000000-0000-0000-0000-000000000000`.
- `POST /api/v1/tenants` — gated by Wave 9 `@enforced(CREATE_TENANT)`
- `POST /api/v1/applications`, `/identity-providers`, `/policies`, `/deployments`, `/integration-bundles` — all `@enforced` with their respective actions
- `GET /api/v1/audit-log` (list), `GET /api/v1/audit-log/stream` (SSE) — Wave 7.F
- `GET /api/v1/admin/licences/`, `/{id}/usage-history`, `/{id}/enforcement-log` — Wave 9 admin
- `POST /api/v1/webhooks/stripe` — Stripe webhook

For testing, hit the API directly when the UI surface isn't wired — backend works ahead of the portal.

## Codegen / regeneration warnings

SSOForge uses Codaic's DEC-013 codegen safety system. **Never run** the following from inside the platform output dir:

- `codaic codegen generate --overwrite` (without `--yes-really-destroy-custom-code`)
- `codaic add entity --from <single-file.yaml>` (always pass the `entities/` directory)
- `make codegen` if you have uncommitted hand-written changes outside `CODAIC:CUSTOM` markers

The portal is partly hand-wired and partly codegen-managed; aggressive regeneration will rewrite `router.tsx` / `App.tsx` and lose the manually-added routes that W10.A introduces.

## Useful commands

```bash
# Confirm portal is up and SSO routes registered
curl -fsS http://localhost:5221/ | grep -q '<div id="root"' && echo OK

# Inspect routes registered on the backend
curl -sS http://localhost:8090/openapi.json | python3 -c \
  'import json, sys; d=json.load(sys.stdin); [print(p) for p in sorted(d.get("paths", {}))]'

# Check if running ssoforge-service container has Wave 9 source
docker exec ssoforge-ssoforge-service python -c \
  'from ssoforge_service.main import app; print(len(app.routes))'

# Tail audit logs to see Wave 7.F events flowing during a walkthrough
docker exec ssoforge-postgres psql -U ssoforge -d ssoforge \
  -c "SELECT action, resource_type, created_at FROM ssoforge.sso_audit_log_entry ORDER BY created_at DESC LIMIT 20;"
```
