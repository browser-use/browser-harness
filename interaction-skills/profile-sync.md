# Profile sync

Make a remote Browser Use browser start already logged in, by uploading cookies from a local Chrome profile.

## One-time install

```bash
curl -fsSL https://browser-use.com/profile.sh | sh
```

Downloads `profile-use` (macOS / Linux / Windows, x64 / arm64). The Python helpers shell out to it; you don't run `profile-use` directly.

## Python API (pre-imported in `browser-harness <<'PY'`)

```python
list_cloud_profiles()
# [{id, name, userId, cookieDomains, lastUsedAt}, ...] — every profile under this API key

list_local_profiles()
# [{BrowserName, ProfileName, DisplayName, ProfilePath, ...}, ...] — detected on this machine

sync_local_profile(local_profile_name, browser=None)
# Shells out to `profile-use sync`. Returns the new cloud profile UUID.

start_remote_daemon("work", profileName="my-work")   # name→id resolved client-side
start_remote_daemon("work", profileId="<uuid>")      # or pass UUID directly
```

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
# 3. Sync + use. Returns the new cloud UUID.
uuid = sync_local_profile("browser-use.com")
start_remote_daemon("work", profileId=uuid)
```

## What actually gets synced

**Cookies only.** No localStorage, no IndexedDB, no extensions. Enough for session-cookie sites (Google, GitHub, Stripe, most SaaS); not for sites that store auth in localStorage.

Cookies mutated during a remote session only persist on a clean `PATCH /browsers/{id} {"action":"stop"}` — the daemon does this on shutdown when `BU_BROWSER_ID` + `BROWSER_USE_API_KEY` are set (default for remote daemons). Sessions that hit the timeout lose in-session state.

## Upstream limitations

These need a PR to `browser-use/profile-use` — they can't be fixed inside `browser-harness`:

- `profile-use sync` **always creates a new cloud profile.** No flag to update an existing one by UUID or name. Syncing the same local profile twice produces two cloud profiles — delete the old one first (UI or `DELETE /api/v3/profiles/{id}`) if you want one-to-one mapping.
- `profile-use sync` **uploads every cookie in the local profile.** No `--domain` / `--cookie` filter. For scoped uploads, use a dedicated local Chrome profile containing only what you want synced.

The Browser Use API has no cookie upload/download endpoint — `profile-use` is the only path, so both limitations live upstream.

## Cloud profile CRUD

- UI: https://cloud.browser-use.com/settings?tab=profiles
- API: `GET /api/v3/profiles`, `GET/PATCH/DELETE /api/v3/profiles/{id}`. Fields: `id`, `name`, `userId`, `lastUsedAt`, `cookieDomains[]`. `list_cloud_profiles()` wraps this.
- Name → UUID: `profileName=` on `start_remote_daemon` resolves client-side; no API change needed.

## Traps

- **Close the target Chrome profile before syncing.** `profile-use` reads the `Cookies` SQLite DB, which Chrome holds with an exclusive lock — `sync` hangs otherwise.
- **Default proxy (`proxyCountryCode="us"`) blocks some destinations** with `ERR_TUNNEL_CONNECTION_FAILED` (e.g. `cloud.browser-use.com` itself). `proxyCountryCode=None` disables the BU proxy; a different country code picks a different exit.
- **Prefer a dedicated work profile over your personal one.** Especially while testing.
