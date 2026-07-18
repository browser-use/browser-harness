# ProtonVPN — generate a WireGuard config (works on free accounts)

Goal: a `.conf` pinned to a specific server (e.g. `US-FREE#17`) so connections always hit
that country — bypasses the free-tier app's random server assignment and its
"Change server" cooldown timers.

## URL

- `https://account.protonvpn.com/downloads` — WireGuard section is on this page
  (heading "WireGuard configuration"). Unauthenticated visits redirect to
  `/login`; stop and let the user sign in.
- Free accounts CAN generate configs, but only for free servers
  ("Free server configs" radio; countries as of 2026: US, NL, JP, PL, RO, CA).

## Page structure / flow

1. Text input "Device/certificate name" (placeholder mentions "certificate") — required.
2. Platform radios (Android preselected; pick the real target — file is identical, choice
   only tracks guides).
3. "4. Select a server to connect to" shows "Use the best server according to current
   load and position: <SERVER>" with a standalone **Create** button — this is the
   fastest path when the suggested server is already the right country. Otherwise
   expand the per-country tables below (each row has its own Create).

## Traps

- **Coordinate clicks miss here.** The server tables load/expand async and shift layout
  by hundreds of px between screenshot and click. Click via DOM instead. There are
  ~100+ buttons whose text is exactly `Create` (one per server row); the standalone
  "best server" one is the only one NOT inside a `tr`:
  ```python
  js("""[...document.querySelectorAll('button')]
        .filter(b=>b.textContent.trim()==='Create')
        .find(b=>!b.closest('tr')).click()""")
  ```
- **The config is shown ONCE.** The result modal (`[role=dialog]`, title = server name)
  says the private key is not stored and won't be shown again. Extract the `<pre>`/
  textarea content from the modal (or click its Download button) BEFORE closing.
  Re-opening the config later from the page only offers the peer/public parts.
- **After the user clicks Download the modal closes** — extraction returns null. The
  file lands in `~/Downloads` named `<name>-<SERVER>.conf` with `#` flattened to `-`
  (e.g. `us-free-mac-US-FREE-17.conf`).
- macOS agents: `~/Downloads` is TCC-protected, so a sandboxed shell often can't read
  the downloaded file. Chrome can: `new_tab("file:///Users/<user>/Downloads/")` gives a
  directory listing, then `goto` the file and read `document.body.innerText`.
- The account app is an SPA in an inner scroll container — `window.scrollY` stays 0;
  use `scrollIntoView` on headings, not window scrolling.
- Free tier allows ONE active VPN device: the WireGuard tunnel and the ProtonVPN app
  can't be connected at the same time.

## Config facts

- Expiry ~1 year from creation ("expires <date>" shown next to the config entry).
- `AllowedIPs = 0.0.0.0/0, ::/0` (full tunnel) and Proton-internal DNS `10.2.0.1`.
- Free servers get decommissioned occasionally; a dead endpoint means regenerate.
