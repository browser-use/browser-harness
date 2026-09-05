# Vercel — project identification and archival checks

Use the existing authenticated browser for project dashboards; prefer the public GitHub API/git for source archival once the repository is known. This guide does not require exporting cookies or environment-variable values.

## Identity and routes

- Team overview: `https://vercel.com/<team>`.
- Project overview: `https://vercel.com/<team>/<project>`.
- Project analytics: `https://vercel.com/<team>/<project>/analytics`.
- Production Deployment on the overview exposes the source repository, branch, abbreviated commit, full commit link, deployment domain, and creation date. Compare the full commit with the archived Git checkout; do not assume default-branch HEAD is deployed.
- A 404 on a known team route may be **account mismatch**, not a missing project. Read the rendered account identity after hydration.
- Multiple logged-in Chrome profiles can expose tabs through one debugging connection. `Target.createTarget` may open in the default profile, even while tabs from another profile are visible. For Linux profile selection, use the user's existing Chrome with `google-chrome --profile-directory='<known profile directory>' --new-tab '<url>'`, then identify the newly created target and attach. Read only profile-name/email metadata to map a user-requested profile; do not copy its credential store.
- Navigation completion is not dashboard hydration completion. After `wait_for_load()`, verify the visible account/project text and take a new screenshot before concluding that a team is unavailable.

## Read-only audit boundaries

The overview may show an Action Required / vulnerable-dependencies banner. Save the visible warning and its destination link. Remediation pages can initialize code-generation workflows, so **do not navigate into a fix workflow merely to inspect a warning**. Repository versions and official advisories are sufficient for initial verification. Do not click Redeploy, Update, or Rotate unless the user authorized that action.

Analytics reports are scoped to the displayed date range and can contain tiny samples. Save the date range alongside counts; do not interpret 100% bounce on a single-page site as proof that all readers disliked it. Custom-event availability depends on the account plan.

## Static media traps

A `.mp4` URL can return HTTP 200 with `Content-Type: video/mp4` but contain a **Git LFS pointer**, not video. The body starts with `version https://git-lfs.github.com/spec/v1` and is only about 130 bytes. Check bytes/magic and decode media, not just status codes.

For a complete source archive:

1. Clone source and record the exact production commit.
2. Fetch needed/all referenced LFS objects and check integrity.
3. Preserve hydrated working-tree media and `.git/lfs/objects`.
4. A `git bundle --all` preserves Git history **but not LFS object bodies**; retain the full source directory too.
5. Capture external CDN delivery URLs separately. Versioned and unversioned URLs can serve identical bytes; record URL-to-hash mappings rather than assuming every URL is a distinct work.
6. Preserve already-broken live responses as evidence and list recovered originals separately. Do not silently replace historical failures with guessed assets.
