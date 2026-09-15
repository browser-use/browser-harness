# Credential login transaction contract

Browser Harness reserves a daemon-owned named session while a host process supplies opaque login material. This is transport and lifecycle infrastructure only; it does not include a site adapter, credential lookup, browser interaction, or real credentials.

## Scope

- Login transactions are available only when `BU_NAME` is not `default` and the daemon uses a supported local POSIX transport. Windows and Browser Use Cloud (`BU_BROWSER_ID`) fail closed.
- One transaction may be active per named daemon.
- `login_begin` accepts exactly `{"meta":"login_begin","adapter":"credential-form-v1"}` or the fixed S-EDU adapter identifier `sedu-v1`. URLs, selectors, JavaScript, commands, environment names, and credential paths are not accepted.
- Begin binds a random 128-bit transaction ID to the daemon's current target ID, session ID, and session generation for at most 120 seconds.
- While active, ordinary CDP and state-changing metadata requests are rejected with `login_transaction_active`. Ping and shutdown remain available.
- A successful adapter result moves the transaction to `awaiting_handoff`; the reservation remains closed until the same socket owner sends the authenticated handoff ACK. Abort, owner disconnect, timeout, and daemon shutdown erase the transaction without handoff. Non-success adapter outcomes release the reservation after their fixed result is sent.

Responses contain only fixed status/error strings and, on successful begin, the transaction ID. Target/session identifiers and secret data are never returned by this protocol.

## POSIX secret frame

The begin request and response use the existing same-user `0600` AF_UNIX socket. The successful begin connection stays open and becomes the transaction owner. Secret material then uses a binary frame, not JSON:

| Field | Size | Meaning |
| --- | ---: | --- |
| opcode | 1 byte | `1` secret, `2` abort, `3` authenticated handoff ACK |
| transaction ID | 16 bytes | raw value of the begin ID |
| payload length | 4 bytes | unsigned network byte order |
| payload | bounded | opaque secret bytes; empty for abort |

Secret payloads are 1 byte through 16 KiB inclusive; abort and handoff-ACK payloads must be empty. ACK is valid only after the sole success result, on the owning connection, with the same transaction ID. Harness then returns exactly `{"status":"handoff_complete"}` and releases the execution gate. Replay, wrong-owner/wrong-ID, premature, malformed, EOF, and deadline-expired ACKs fail closed. Unknown opcodes, malformed lengths, oversized frames, and truncated frames fail closed without trusting or draining the declared payload. Header, payload, and response-drain operations share the transaction's absolute deadline, so byte trickling cannot extend it. A wrong transaction ID or non-owner frame is rejected. Target/session binding changes invalidate the transaction before a secret can be accepted. The synthetic `credential-form-v1` adapter retains its transport-only `secret_received` response for compatibility. Mutable receive and parser buffers are zeroed after use.

### `sedu-v1` payload and browser sequence

The S-EDU payload is an 8-byte network-order header containing unsigned 32-bit username and password byte lengths, followed by the UTF-8 username bytes and UTF-8 password bytes. Both fields must be non-empty, at most 16,375 bytes, contain no NUL, and account for the complete payload. The complete payload, including the 8-byte length header, must not exceed 16,384 bytes.

The versioned `sedu-v1` result is exactly two JSON string fields with no extensions. Its sole success is `{"status":"success","state":"active"}`. Every failure is `{"status":"failed","state":"<state>"}`, where `<state>` is exactly one of `reauth_required`, `human_challenge`, `locked`, `failed`, or `timeout`. No aliases are part of this schema.

The adapter uses the transaction's pinned target/session/generation and the daemon's exclusive execution gate. It performs exactly one navigation to `https://s-edu.cloud/accounts/login/`, then waits for the redirected document to reach `complete` with the exact HTTPS login URL, POST form, and `username`/`password` inputs before filling and submitting once. It performs no status probe, reload, cache/cookie clear, or login-URL reentry. A pre-fill 429 or human challenge stops without credential entry. One 35-second adapter deadline covers initial navigation, redirect/form wait, fill, submit, and post-submit detection. Post-submit work is additionally capped at 15 seconds but never receives time beyond that adapter deadline. Loading states are allowed during both redirect and post-submit evaluation. An unchanged complete pre-click login document is not immediately classified as reauthentication; the adapter waits for an observed document-state or URL transition or until the bounded deadline.

Immediately before fill, the daemon suppresses and purges every CDP event for the bound session while leaving all CDP domains enabled. This covers synchronous input listeners and Runtime, Log, DOM, Page, Network `postData`, and future event domains through submit/navigation cleanup. The complete bound-session event buffer is purged again before ordinary event capture resumes. Success requires the exact protected path `/npms/`, a complete document, and all three fixed application indicators: the school-list, profile, and logout links. A redirect or any single attacker-influenced anchor is not authentication proof. Post-submit execution-context loss caused by navigation is retried only until the same fixed deadline; origin violations fail immediately. If adapter cancellation does not drain promptly, the daemon quarantines its execution gate, closes the logical CDP transport, and reattaches before handoff; failed recovery remains fail-closed.

The helper `browser_harness._ipc.send_login_secret()` emits the bounded secret frame. Callers must source bytes through a host-private channel; they must not place secrets in command-line arguments, environment variables, JSON, stdout, telemetry, or logs.
Python credential strings cannot be reliably zeroized; their references are kept only for the bounded adapter call. Mutable payload and parser buffers are zeroed after use.

## Windows

Windows currently uses authenticated loopback TCP rather than a same-user Unix socket. Login begin and `send_login_secret()` therefore fail closed with an unsupported-transport error. A later implementation needs an equivalent same-user binary transport before Windows login transactions can be enabled.
