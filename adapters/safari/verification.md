# Verification and open gaps

This adapter is experimental. Deterministic checks, controlled Safari tests, and
agent/model-quality evaluations are separate evidence tracks.

## Deterministic checks

The package contains 15 Python and 12 Node tests. Relevant regression cases include:

- **D1, selection failures:** no selection, failed transport/local selection and
  creation, zero subsequent fill/click/JS/navigation transport calls, and explicit
  successful recovery. Distinct tab references and error variants are covered.
- **D2, stale references:** closed windows, changed URLs, and duplicate identical
  tabs are rejected in bridge mocks. Same-URL/title replacement is not covered.
- **D3, execution-time URL changes:** the actual bridge executes in a Node VM;
  cross-origin and same-origin URL changes after host validation reject before
  caller-body execution or synthetic writes. A matching-target control runs once.
- Serialization, unsupported CDP, permission/timeout failures, and window-order
  comparison have tests. Actual tab moves, metadata changes, missing/added tabs,
  and duplicates remain unequal even when window stacking order is ignored.

These tests do not establish live Safari race protection. Executable upload/Promise
rejection, invalid-response coverage, and artifact/preference checks remain incomplete.

## Controlled Safari runs

Fixture v3 passed three consecutive runs on Safari 26.6.2 and macOS 26.6.2 using
Python 3.12.14. Each run verified:

- Exactly one new window and unchanged pre-existing tab references.
- Load and reuse through a separate CLI process in under 30 seconds.
- The synthetic same-origin sessionStorage marker in the existing Safari tab.
- Stale-index rejection and invalid-creation-URL rejection followed by explicit recovery.
- Three exact textarea values containing Unicode, quotes, backslashes, newlines,
  HTML-shaped and shell-shaped text; exactly one click and an exact read afterward.

Load plus reuse took 0.803, 0.781, and 0.780 seconds; each run observed a click count
of one. The [recorded evidence](https://github.com/tompulsarlabs/browser-harness/blob/78463db777b24174cbaf4b7f1e10a71c771200b8/adapters/safari/evals/results/live-runs.json)
contains timestamps, commands, synthetic stdout links, and source hashes. Runtime,
skill, fixture, and regression sources in this contribution match those hashes.
These are prior observed runs against identical source, not new runs on this branch.

An earlier fixture failed because Safari enumerated unchanged windows in a different
order. Instrumentation reproduced identical references by window/index with zero
changed URL/title fields or added/missing references. Fixture v3 fixes that comparison;
the three passes are a fresh sequence after the correction.

## Unverified behavior

Same-URL/title document replacement, live adversarial tab races, native navigation
races, file-fixture loading, and multi-profile semantics remain unresolved. No
agent/model-quality evaluations or general production-safety pass are claimed.
