# Local Chrome

The default daemon holds the one browser connection, so Chrome asks to Allow
once per Chrome run. It keeps many tabs and many agents at once; browser-harness
has no per-site, screenshot, or result-count limit that requires a new daemon.

Agents running at the same time share it safely: each owner (`BH_OWNER`, else
the agent's session id) has its own tabs, current tab, events and dialogs, and a
command on another owner's tab fails with `tab-taken`. Sub-agents need their own
`BH_OWNER`, since they inherit their parent's session id. Do not create another
local daemon for isolation: it adds another Allow prompt and isolates nothing more.

Timers, in seconds, set in the daemon's environment:

- `BH_OWNER_IDLE` (1800): after this long without a command, an agent's tabs other than its current one are given back (left open; unmarked ones get a clean title), and its current tab can be taken by another agent.
- `BH_OWNER_FORGET` (86400): after this long idle, the agent's current tab is given back too (detached, clean title, left open).
- `BH_CLOSE_IDLE_TABS=1`: also close the unmarked tabs the idle agent opened itself. Off by default.
- `BH_IDLE_EXIT` (1800): an unused named local daemon exits. A `BU_CDP_URL`/`BU_CDP_WS` daemon exits on idle only when this is set for it. The default local daemon, Cloud daemons, and daemons used with `BH_REQUIRE_EXISTING_DAEMON=1` never exit on idle.

A command timeout, truncated output, site change, closed tab, or new task is not
a reason to restart the daemon. Updating browser-harness does not restart it
either. Run `browser-harness --doctor` and restart it only when it is actually
dead or cannot recover.

If the daemon cannot connect, run diagnostics:

```bash
browser-harness --doctor
```

If Chrome is not running at all, the harness launches it automatically and retries.

If Chrome is running but remote debugging is not enabled, the harness opens:

```text
chrome://inspect/#remote-debugging
```

On macOS, when local Chrome asks for remote-debugging permission, keep the
original browser command running and call `mac-approve` in another shell/tool
call. Preserve the exact daemon name: if the waiting command used
`BU_NAME=r7k2`, run:

```text
BU_NAME=r7k2 browser-harness mac-approve
```

For the default daemon, omit the `BU_NAME` prefix. The original command resumes
when the helper returns `ready`; do not rerun it. If the helper reports
`accessibility-required`, ask the user once to grant the app launching
browser-harness (for example Terminal or iTerm) access in System
Settings > Privacy & Security > Accessibility, then call `mac-approve` once
again. This is only for local Chrome; do not call it for `BU_CDP_URL`,
`BU_CDP_WS`, or Browser Use Cloud.

When the shell tool can yield a still-running process, use a short 3-5 second
initial yield for the first local command, not a 30-second wait. If the command
yields with the Allow hint, leave that exact process running, immediately call
`browser-harness mac-approve` in a second tool call, then resume or poll the
original process. With a named daemon, preserve its exact `BU_NAME` for the
helper. Never start the browser command again. If the user clicks Allow first,
the same handshake completes and the original command returning successfully
is the agent's feedback; `mac-approve` also returns `ready` when the daemon is
already connected.

`mac-approve` is macOS-only. On Linux or Windows, keep the original browser
command running and ask the user to click Allow if Chrome presents the approval
dialog. Their click completes the same handshake, so resume or poll the original
process for success; do not rerun it or create a replacement daemon. If that
Chrome build presents no approval dialog, the original command simply connects.
