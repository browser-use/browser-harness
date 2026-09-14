# Credential login transaction contract

Browser Harness reserves a daemon-owned named session while a host process supplies opaque login material. This is transport and lifecycle infrastructure only; it does not include a site adapter, credential lookup, browser interaction, or real credentials.

## Scope

- Login transactions are available only when `BU_NAME` is not `default` and the daemon uses a supported local POSIX transport. Windows and Browser Use Cloud (`BU_BROWSER_ID`) fail closed.
- One transaction may be active per named daemon.
- `login_begin` accepts exactly `{"meta":"login_begin","adapter":"credential-form-v1"}`. The adapter identifier is fixed; URLs, selectors, JavaScript, commands, environment names, and credential paths are not accepted.
- Begin binds a random 128-bit transaction ID to the daemon's current target ID, session ID, and session generation for at most 120 seconds.
- While active, ordinary CDP and state-changing metadata requests are rejected with `login_transaction_active`. Ping and shutdown remain available.
- Abort, owner disconnect, timeout, and daemon shutdown erase the transaction and release the named-session reservation.

Responses contain only fixed status/error strings and, on successful begin, the transaction ID. Target/session identifiers and secret data are never returned by this protocol.

## POSIX secret frame

The begin request and response use the existing same-user `0600` AF_UNIX socket. The successful begin connection stays open and becomes the transaction owner. Secret material then uses a binary frame, not JSON:

| Field | Size | Meaning |
| --- | ---: | --- |
| opcode | 1 byte | `1` secret, `2` abort |
| transaction ID | 16 bytes | raw value of the begin ID |
| payload length | 4 bytes | unsigned network byte order |
| payload | bounded | opaque secret bytes; empty for abort |

Secret payloads are 1 byte through 16 KiB; abort payloads must be empty. Unknown opcodes, malformed lengths, oversized frames, and truncated frames fail closed without trusting or draining the declared payload. Header, payload, and response-drain operations share the transaction's absolute deadline, so byte trickling cannot extend it. A wrong transaction ID or non-owner frame is rejected. Target/session binding changes invalidate the transaction before a secret can be accepted. Accepted bytes are not retained by this foundation; a future host-side adapter must consume them within the transaction scope and zero mutable buffers where practical.

The helper `browser_harness._ipc.send_login_secret()` emits the bounded secret frame. Callers must source bytes through a host-private channel; they must not place secrets in command-line arguments, environment variables, JSON, stdout, telemetry, or logs.

## Windows

Windows currently uses authenticated loopback TCP rather than a same-user Unix socket. Login begin and `send_login_secret()` therefore fail closed with an unsupported-transport error. A later implementation needs an equivalent same-user binary transport before Windows login transactions can be enabled.
