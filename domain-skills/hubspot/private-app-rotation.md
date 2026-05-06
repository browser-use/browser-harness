# HubSpot — rotating a Private App access token

For killing a compromised token and capturing its replacement without the value ever touching a shell, chat, or log. See `private-app-creation.md` for the DOM gotchas that apply generally (I18N-STRING text nodes, React-controlled inputs, TreeWalker patterns) — this file covers only the rotation-specific flow.

## When to rotate

- Token value was exposed (leaked in chat, committed to git, pasted in a screenshot).
- Routine rotation policy.
- You're handing off ownership and want to invalidate any cached copies.

HubSpot Private App tokens are re-revealable indefinitely from the UI, so "I lost the value" is not a reason to rotate — just click **Show token** again.

## URL

```
https://app-<region>.hubspot.com/private-apps/{portalId}/{appId}/auth
```

The Auth tab is where Rotate lives. If you land on the app-detail page, click the "Auth" tab first — it's an `<a role="button">` with innerText "Auth" (no href; client-side routed).

## Flow

1. Navigate to the Auth tab (URL above, or click the Auth tab anchor).
2. Click the **Rotate** button (a `<button>` with innerText "Rotate", not to be confused with "Rotate now" which is inner-modal).
3. First modal asks *when* to expire the previous token:
   - **Rotate and expire this token later** — creates a new token; the old one stays valid during a grace window (exact duration visible in the modal copy). Use for zero-downtime rotation where you control both deploy timing and the rotation.
   - **Rotate and expire this token now** — immediate invalidation. Use when the old token is compromised.
4. A second confirmation modal appears: **Rotate now** vs **Cancel**. Click **Rotate now**.
5. After ~2–4 seconds, the Auth tab re-renders with a new token and the **Hide token** button replacing **Show token** (HubSpot auto-reveals the freshly-minted token once).
6. The token is a text node inside a `<code>` element, matching `^pat-na[0-9]+-<uuid>$` (44 chars).

## Extracting without printing

The safe pattern: run a TreeWalker filtered by the exact token regex (so it only matches unmasked tokens, not the `********-****` display). Read the value into a Python variable, pipe straight into `subprocess.run(["fly", "secrets", "set", ..., f"KEY={token}"])`, and do not echo to stdout.

```python
from browser_harness import *
import subprocess, re, sys

# Switch to the open HubSpot tab rather than creating one — the existing session is authenticated.
for t in list_tabs(include_chrome=False):
    if "private-apps/" in t.get("url", "") and "/auth" in t.get("url", ""):
        switch_tab(t["targetId"])
        break

token = js("""
(() => {
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let n;
  while ((n = walker.nextNode())) {
    const t = (n.nodeValue || "").trim();
    if (/^pat-na[0-9]+-[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(t)) return t;
  }
  return null;
})()
""")

if not token or not re.fullmatch(r"pat-na[0-9]+-[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}", token):
    sys.exit("no token extracted")

# Metadata only — never print the value.
print(f"len={len(token)} prefix={token[:8]}")

r = subprocess.run(
    ["fly", "secrets", "set", "--app", "<app>", f"HUBSPOT_PRIVATE_APP_TOKEN={token}"],
    capture_output=True, text=True,
)
# Scrub in case fly echoes it on error paths.
def scrub(s, secret=token):
    return s.replace(secret, "<TOKEN>") if s else s
print("rc", r.returncode, scrub(r.stderr))
```

### Why subprocess.run with a list, not `fly …` via a shell

`subprocess.run([...])` passes the token directly as `argv[2]` to fly. No shell parses it, no history captures it, and it's visible only in `/proc/<fly-pid>/cmdline` for the ~2-second lifetime of the process. A shell invocation (`bash -c 'fly secrets set ... KEY=$TOKEN'`) would put the expanded value into the shell's argv and expose it to `ps aux` across two processes.

Do NOT use the prefix-env pattern:
```bash
# WRONG — arg-side $TOKEN expands in the outer shell, not the prefix env.
TOKEN="$(cat /tmp/ao_token)" fly secrets set --app X KEY="$TOKEN"
```
The prefix `TOKEN=...` only applies to `fly`'s child environment; the `$TOKEN` in the argument is expanded by the calling shell, where `TOKEN` is usually unset, silently producing `KEY=`. Fly will happily store an empty string and the secret looks set until you SSH in and check its length. You want either the subprocess-list form above, or direct inline substitution:
```bash
fly secrets set --app X KEY="$(cat /tmp/ao_token)"
```

## Verification

After `fly secrets set` (no `--stage`, so it auto-deploys), wait for the rolling restart and then check from inside the VM — the token never has to leave the prod environment:

```bash
fly ssh console --app <app> -C 'node -e "
const t = process.env.HUBSPOT_PRIVATE_APP_TOKEN;
console.log(\"LEN=\" + (t||\"\").length + \" prefix=\" + (t||\"\").slice(0,8));
fetch(\"https://api.hubapi.com/account-info/v3/details\", {
  headers: { Authorization: \"Bearer \" + t }
}).then(async r => {
  const j = await r.json().catch(() => ({}));
  console.log(\"HTTP \" + r.status + \" portalId=\" + j.portalId + \" uiDomain=\" + j.uiDomain);
}).catch(e => console.log(\"ERR \" + e.message));
"'
```

Expected: `LEN=44 prefix=pat-na2- … HTTP 200 portalId=<your portal> uiDomain=app-na2.hubspot.com`.

Slim container lacks `curl` — use `node -e` for inline fetches.

## Gotchas

### The prior token is re-revealable even after rotation if you chose "later"

"Rotate and expire this token later" means the old token stays valid for a grace period shown in the modal. During that window, both tokens authenticate. Don't conflate "I rotated" with "the old value is dead" unless you picked "expire now."

### The masked display is also a text node

An earlier token's masked value (`********-****-…`) coexists on the page with the new token's unmasked value. Don't scan loosely for "pat-" or take the first `<code>` — gate by the full UUID regex so the masked display doesn't match. (It's `*` characters, not hex.)

### Rotation invalidates in-flight refresh tokens too

Irrelevant for Private Apps (which have no OAuth flow — see `private-app-creation.md`) but worth noting if you later switch this app type: Public App rotations invalidate stored HubSpot refresh tokens, forcing a full reauth cycle for every user.
