# Copilot Studio agent authoring and workflow tests

## Routes

- New agent authoring: `/environments/{environmentId}/agents/{agentId}` with
  Build, Preview, Evaluate and Monitor tabs.
- Classic agent-flow designer: `/environments/{environmentId}/agent-flows/{flowId}`.
  The newer `/flows/{flowId}` route may instead offer a link to the classic designer.

## Publishing and freshness

- After an authorized configuration change outside the current page, reload the
  agent before publishing. The SPA can show a blank screen or skeleton after
  `document.readyState` is complete; wait for the agent navigation to reappear.
- Publish can start immediately from the top-level button. Do not click repeatedly
  while it says Publishing. A previous successful publish is not proof that the
  new version is available.
- The authoring UI may still show Publishing after the backend completes. When
  using authorized Dataverse diagnostics, inspect the bot's `publishedon` and
  `synchronizationstatus`: the last operation must be the current successful one,
  and the synchronization state must be Synchronized. Preview success alone does
  not prove that the channel uses the updated agent.

## Tool authentication and tests

- Newly attached workflow tools may default to caller/Invoker authentication.
  Inspect their configured authentication mode; do not infer it from the backing
  flow's connection owner. Change it only when authorized for the intended sharing
  and source-access policy.
- In Preview, multiline Enter can insert a newline instead of submitting. Use the
  visible send arrow and verify a new user message appears before retrying.
- A generic `/triggers/manual/run` request is not a reliable Skills-trigger test:
  in the tested environment it started a run but dropped the supplied body.
  Callback URL retrieval can also be unsupported for these triggers. Prefer the
  native Preview tool invocation or designer Test, and confirm actual trigger
  inputs and outputs instead of treating HTTP 200 as success.

## Teams end-to-end verification

- Select the bot from the @-mention suggestion list; typed text alone does not
  create a real mention entity.
- Confirm the composer closes and the new post is visible before assuming Post
  succeeded. An open suggestion popup may consume the first click.
- A new root post gives a clean test request. Record its message ID and verify
  that the delivery reply references that same request and intended channel.
- Channel action repetitions may not appear through run-history APIs until the
  enclosing loop completes. An empty repetitions list while the loop is running
  is not evidence that the message step was skipped.
