# proxywar.xyz / beta.proxywar.xyz

League/replay origin. Two separate Vite entries, never mixed:
`public.html`→`PublicApp.ts` (`assets/public-<hash>.js`) and
`index.html`→`Main.ts` (`assets/main-<hash>.js`).

## Routes

| Route | Shell |
|---|---|
| `/` | `public.html` event lobby |
| `/league` | static mirror `league/index.html` |
| `/watch` | `public.html` — links to real `/ai-league-replay/<runKey>` and `/match/<id>` |
| `/agents` | `public.html` |
| `/build` | `public.html` — self-serve Builder registration wizard |
| `/ai-league-replay/<runKey>` | `index.html` game shell — replay/clip/panel UI lives here |

## `/build` wizard

Custom element `<build-page>`. Step tabs: `build-page button[aria-current]`,
a 7-item NodeList, index 2 = Step 3 "Identity" (the registration form).

Step 3 fields: Agent Name*, Short Code* (2-4 uppercase alphanumeric characters, `/^[A-Z0-9]{2,4}$/`), Tagline, Public
Strategy Description, Your Builder Name*, GitHub username (optional,
`[a-zA-Z0-9-]{1,39}`), Short bio, Links (`<textarea>`, one per line),
Source repository (`<input>`). `*` = required.

Submit: `POST /api/build/registration-submission`, strict-schema JSON body.
Success: `{ok:true, proposedAgent, proposedBuilder, profileFileJson,
githubIssueUrl}`. Failure: `{ok:false, error:"invalid_submission", field,
reason}` — `field` names the exact bad input; `reason` ∈
`format|required|too_short|too_long|invalid`.

No persistence: this endpoint never writes the identity registry. Success
only yields a client-rendered draft plus a prefilled GitHub issue URL —
opening/filing that issue is a separate manual click the wizard never
triggers.

Field-error DOM ids (targets of the input's `aria-describedby`,
`aria-invalid` toggles alongside): `build-step3-github-error`,
`build-step3-links-error`, `build-step3-repo-error`. Any `body.field` not
matching `claimedGithub`/`builderLinks`/`sourceRepositoryRef` falls back to
a generic banner, not tied to any input.

## Replay panel collapse

Shared toggle component, per-overlay state/keys:

- Full Replay (`/ai-league-replay/<runKey>`): localStorage keys
  `ai-league-broadcast-rail-collapsed-v1` (Competitors rail),
  `ai-league-broadcast-war-room-collapsed-v1` (War Room feed).
- Premiere overlay: `replay-premiere-broadcast-rail-collapsed-v1`,
  `replay-premiere-broadcast-war-room-collapsed-v1`.

aria-labels: "Collapse/Expand competitors panel",
"Collapse/Expand War Room panel"; `aria-expanded` mirrors collapsed state on
every render including first paint.

## Social clip control

Render button selector: `[data-ai-league-clip-render]` — same component on
Full Replay and an archived Premiere rewatch. Requires
`GET /api/clip-capabilities` to report generation enabled, else the whole
clip section is `hidden`.

Flow: `POST /api/league-runs/<runKey>/clips` (body `{turn}`) starts a
render, returns a `schemaVersion:1` `pending`/`ready` status envelope. While
pending, client polls `GET /api/league-runs/<runKey>/clips/<bucket>?progress=1`
every 3000ms until terminal.

Terminal poll outcomes: 404 → `"failed"`; any other non-2xx → `429`/`503`
maps to `"busy"`, anything else maps to `"failed"`; both stop polling and
re-enable the render control. Initial selected bucket is not fixed — it can
track the replay's live playhead rather than a constant, so any mocked
response must echo back the bucket the page actually requested.

## Local dev server

`npm run dev` (plain Vite + `src/server/Server.ts`) does not serve `/build`
or any `/api/build/*`/`/api/league-runs/*` route — wrong server entirely.

Use `src/scripts/ai-agent-demo-server.ts` (`npm run agent:demo-server`)
instead. It serves a prebuilt `static/` directory, not live Vite HMR — run
`npm run build-dev` (or `build-prod` for the Full Replay/map asset
manifest) before starting/restarting it. Boot with
`PROXYWAR_LEAGUE_WRAPPER_ONLY=true` to match the league-origin posture (also
skips spawning its own child replay-renderer subprocess). Default port
`AI_LEAGUE_DEMO_PORT` = 8787.

## Verifying a deploy landed

No `/commit.txt` or version-SHA endpoint exists. Compare content-hashed
asset filenames instead: `assets/main-<hash>.js` (served at `/`) and
`assets/public-<hash>.js` (served at `/build`) against the freshly built
local `static/assets/` output — an exact filename match on both confirms
the intended commit is live.
