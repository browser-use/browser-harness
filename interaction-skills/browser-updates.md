# macOS Brave: CDP works but pages crash after an update

A live browser connection does not prove that the browser can start a renderer.
An application update can replace the installed Brave bundle while an older
Brave process stays open. If that process's versioned framework and renderer
helper are missing, new pages can crash even though CDP still responds.

The harness attaches to the running process; it does not pin Brave's installed
version. A version difference alone is not evidence of a broken browser.

## Diagnose without restarting

For a Brave installation in `/Applications`, inspect the listener belonging to
its existing profile:

```bash
BRAVE_APP='/Applications/Brave Browser.app'
BRAVE_PROFILE="$HOME/Library/Application Support/BraveSoftware/Brave-Browser"
FRAMEWORK_VERSIONS="$BRAVE_APP/Contents/Frameworks/Brave Browser Framework.framework/Versions"
BRAVE_CDP_PORT="$(sed -n '1p' "$BRAVE_PROFILE/DevToolsActivePort")"
case "$BRAVE_CDP_PORT" in
  ''|*[!0-9]*) printf '%s\n' 'No valid Brave debugging port' >&2; exit 1 ;;
esac
BRAVE_PID="$(/usr/sbin/lsof -nP -iTCP:"$BRAVE_CDP_PORT" -sTCP:LISTEN -t | head -n 1)"
test -n "$BRAVE_PID" || { printf '%s\n' 'No Brave debugging listener' >&2; exit 1; }
/usr/sbin/lsof -a -p "$BRAVE_PID" -d txt -Fn | sed -n '/Brave Browser Framework\.framework\/Versions\//p'
readlink "$FRAMEWORK_VERSIONS/Current"
```

Find the version in the **loaded** `Brave Browser Framework.framework/Versions/`
path. Its path may point into an updater's temporary old app bundle. Check that
the installed app still contains that exact version's framework binary and
`Helpers/Brave Browser Helper (Renderer).app/Contents/MacOS/Brave Browser Helper (Renderer)`.
Do not substitute the version referenced by `Current`.

If those files exist, investigate another cause. If the port file or listener is
absent, follow the connection setup in `install.md` instead.

## Recover the missing version

Recovery changes the installed app bundle. Keep it an explicit recovery action,
with the destination and exact version identified before copying anything.

1. Obtain the matching architecture and **exact running Brave release** from
   [Brave's official releases](https://github.com/brave/brave-browser/releases).
   Verify the archive against the release asset's published digest.
2. Mount the archive read-only. Copy its app into a temporary staging directory
   with `ditto --norsrc --noextattr`, then validate that staged app with:

   ```bash
   codesign --verify --deep --strict \
     -R '=anchor apple generic and certificate leaf[subject.OU] = "KL8N8XSYF4"' \
     '/path/to/staged/Brave Browser.app'
   ```

   Staging removes Finder metadata that can itself make signature validation
   fail. If validation still fails, stop. Do not re-sign the app or disable
   signature checks.
3. Check the staged framework's `Resources/Info.plist`: its
   `CFBundleShortVersionString` must equal the loaded framework version.
   Restore only the **absent** matching `Versions/<running-version>` directory
   using `ditto --norsrc --noextattr`. Do not overwrite an existing directory,
   change `Current`, or replace the main app executable.
4. Open a background test page and verify its URL, title, and
   `document.readyState`. Reload affected crashed tabs. Keep the original
   browser PID and profile; do not clear cookies or create a replacement profile.
5. Close only the test tab and unmount the archive.

## Prevent recurrence

An opt-in local launcher can save the installed and live framework versions
outside the app bundle before an update removes them. Any restoration must
validate the saved version and Brave signature, restore only an absent directory,
and serialize concurrent callers. Bound the cache to the installed and live
versions. Never download or install an arbitrary older version automatically.

A launcher-only check runs when the harness starts. Protecting a long-running
browser also requires a local update watcher or periodic check. Such a watcher
must keep working independently of the harness process. A restored runtime may
still require reloading tabs that already crashed.

## Related reports and proposals

- [Issue #865](https://github.com/browser-use/browser-harness/issues/865) reports
  a live daemon with an unresponsive browser and proposes bounded CDP health
  checks. The failure here is narrower: CDP can respond while renderer files
  are missing. A browser-level probe alone cannot prove that a page loads.
- [PR #773](https://github.com/browser-use/browser-harness/pull/773) proposes
  preserving Cloud browsers after failed CDP health checks. It addresses a
  different transport, but its recovery boundary is relevant: failed health
  checks should not automatically destroy a browser session.
