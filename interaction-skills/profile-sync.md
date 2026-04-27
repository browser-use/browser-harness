# Profile sync

Make a remote Browser Use browser start already logged in, by uploading cookies from a local Chrome profile.

## One-time install

```bash
curl -fsSL https://browser-use.com/profile.sh | sh
```

Downloads `profile-use` (macOS / Linux / Windows, x64 / arm64). The Python helpers shell out to it; you don't run `profile-use` directly.

## Python API (pre-imported in `browser-harness -c`)

```python
list_cloud_profiles()
# [{id, name, userId, cookieDomains, lastUsedAt}, ...] — every profile under this API key

list_local_profiles()
# [{BrowserName, ProfileName, DisplayName, ProfilePath, ...}, ...] — detected on this machine

sync_local_profile(local_profile_name, browser=None,
                   cloud_profile_id=None,      # update an existing cloud profile instead of creating new
                   include_domains=None,       # only these domains (and subdomains); leading dot optional
                   exclude_domains=None)       # drop these domains; applied before include
# Shells out to `profile-use sync`. Returns the cloud profile UUID
# (the existing one if cloud_profile_id was passed, else the newly-created one).

start_remote_daemon("work", profileName="my-work")   # name→id resolved client-side
start_remote_daemon("work", profileId="<uuid>")      # or pass UUID directly

stop_remote_daemon("work")                           # shut the daemon and PATCH the cloud browser to stop — billing ends
```

`sync_local_profile` prints `♻️  Using existing cloud profile` when `cloud_profile_id` is accepted, or `📝  Creating remote profile...` → `✓ Profile created: <uuid>` when it creates a new one. Check that line if you want to confirm which path ran.

## Chat-driven flow (don't guess — ask the user)

Cookies are real auth. Don't sync or pick a profile unilaterally.

```python
# 1. Show what's already in the cloud.
for p in list_cloud_profiles():
    print(f"{p['name']:25}  {len(p['cookieDomains']):3} domains  {p['id']}")
```
→ Agent: *"You have these cloud profiles (<N> domains each). Want to reuse one, sync a local profile, or start clean?"*

```python
# 2a. Reuse cloud → one call.
start_remote_daemon("work", profileName="browser-use.com")

# 2b. Sync local first. Show the options:
for lp in list_local_profiles():
    print(lp["DisplayName"])
```
→ Agent: *"Which local profile?"* → user picks → before syncing, inspect domain-level cookie counts with `profile-use inspect --profile <name>` (or `--verbose` for individual cookies) and report the summary; never dump 500 cookies into chat.

```python
# 3. Sync + use. Returns the cloud UUID.
uuid = sync_local_profile("browser-use.com")
start_remote_daemon("work", profileId=uuid)

# 3b. Refresh that same cloud profile later (idempotent — no duplicate profiles).
sync_local_profile("browser-use.com", cloud_profile_id=uuid)

# 3c. Scoped: push *only* Stripe cookies into a dedicated cloud profile.
sync_local_profile("browser-use.com",
                   cloud_profile_id=uuid,
                   include_domains=["stripe.com"])
```

## What actually gets synced

**Cookies only.** No localStorage, no IndexedDB, no extensions. Enough for session-cookie sites (Google, GitHub, Stripe, most SaaS); not for sites that store auth in localStorage.

Cookies mutated during a remote session only persist on a clean `PATCH /browsers/{id} {"action":"stop"}` — the daemon does this on shutdown when `BU_BROWSER_ID` + `BROWSER_USE_API_KEY` are set (default for remote daemons). Sessions that hit the timeout lose in-session state.

## Cloud profile CRUD

- UI: https://cloud.browser-use.com/settings?tab=profiles
- API: `GET /profiles`, `GET/PATCH/DELETE /profiles/{id}` (paths are relative to `BU_API = "https://api.browser-use.com/api/v3"` in `admin.py`). Fields: `id`, `name`, `userId`, `lastUsedAt`, `cookieDomains[]`. `list_cloud_profiles()` wraps this.
- Name → UUID: `profileName=` on `start_remote_daemon` resolves client-side; no API change needed.
- Need the UUID for an existing profile? `matches = [p["id"] for p in list_cloud_profiles() if p["name"] == "<name>"]` — then verify `len(matches) == 1` before using it. Profile names are not unique; syncs create duplicates unless you pass `cloud_profile_id=`.
- Lower-level raw calls: `from admin import _browser_use; _browser_use("/profiles/<id>", "DELETE")`. Pass the path *without* the `/api/v3` prefix — it's already on `BU_API`.

## Traps

- **Default proxy (`proxyCountryCode="us"`) blocks some destinations** with `ERR_TUNNEL_CONNECTION_FAILED` (e.g. `cloud.browser-use.com` itself). `proxyCountryCode=None` disables the BU proxy; a different country code picks a different exit.
- **Prefer a dedicated work profile over your personal one.** Especially while testing.
- **Older than `profile-use` v1.0.5?** Pre-1.0.5 the sync needed the Chrome profile to be closed (exclusive SQLite lock on the `Cookies` DB). v1.0.5+ copies the profile dir to a temp and syncs from the copy — Chrome can stay open.
