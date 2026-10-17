# Local Chrome

The default daemon can keep many tabs and visit many sites; browser-harness has
no per-site, screenshot, or result-count limit that requires a new daemon.
Chrome memory and page complexity are the practical limits. Reuse matching tabs
with `list_tabs()` and `switch_tab()`.

One daemon has one mutable attached/current tab. Many agents can share it when
their browser operations are serialized: treat local Chrome as one shared
browser lane while non-browser work continues in parallel. Sequential tab
switching, input, and screenshot capture are safe. Do not create another local
daemon merely because several agents exist.

Two agents that switch tabs and act simultaneously can race, causing one to act
on or capture the other's tab. For truly simultaneous interactive work, use
separate remote browsers when Browser Use Cloud authentication is already
available. Otherwise serialize browser operations through the default local
daemon. A named local daemon is a last resort when simultaneous isolation is
required, remote auth is unavailable or unsuitable, and the extra Chrome
approval prompt is acceptable. It creates another controller and dedicated tab
in the same local Chrome profile, not another Chrome profile or process.

If the default daemon becomes stale, use its built-in reattachment/recovery
first. A command timeout, truncated output, site change, closed tab, or new task
is not a reason to create another daemon. Run `browser-harness --doctor` and
restart or replace the default daemon only when it is actually dead or cannot
recover.

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
