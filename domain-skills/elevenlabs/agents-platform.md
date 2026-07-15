# ElevenLabs Agents Platform (Conversational AI)

Investigating agents, batch calls, conversations, and webhook health via the web app.

## Residency matters

EU-resident workspaces live on `eu.residency.elevenlabs.io` (API: `api.eu.residency.elevenlabs.io`). The global app (`elevenlabs.io`) will not show EU workspace data — always use the residency host the workspace was created in.

## URL patterns

```
/app/agents/agents/{agent_id}                                   # agent home
/app/agents/agents/{agent_id}/batch-calling                     # batch list
/app/agents/agents/{agent_id}/batch-calling/{batch_id}          # batch detail
/app/settings/webhooks                                          # workspace webhooks
```

Navigation appends `?branchId=agtbrch_...` automatically — safe to omit.

## Private APIs (far faster than DOM scraping)

The SPA authenticates with a bearer token from its own state, so plain `js("fetch(...)")` is NOT authorized. Instead capture the app's own XHRs with CDP Network events:

```python
cdp("Network.enable")
goto(batch_url)
wait_for_load(20); wait(4)
for e in drain_events():
    if e.get("method") == "Network.responseReceived":
        u = e["params"]["response"]["url"]
        if "batch-calling" in u:
            body = cdp("Network.getResponseBody", requestId=e["params"]["requestId"])["body"]
```

High-value responses the pages fetch:

- `GET /v1/convai/batch-calling/{batch_id}` — **every recipient** with `status`
  (`failed` / `voicemail` / `completed`), `conversation_id`, timestamps, and the full
  `conversation_initiation_client_data.dynamic_variables` (whatever per-call vars the
  batch CSV carried). One capture replaces clicking through every row.
- `GET /v1/convai/agents/{agent_id}` — full agent config. Per-agent post-call webhook
  override lives at `platform_settings.workspace_overrides.webhooks`
  (`post_call_webhook_id`, `events: ["transcript", "call_initiation_failure"]`).
- `GET /v1/convai/settings` — workspace-level webhook defaults
  (`webhooks.post_call_webhook_id` is null when only agent overrides are used).
- `GET /v1/workspace/webhooks?include_usages=true` — fetched by the settings/webhooks
  page. Each webhook includes **`most_recent_failure_error_code` +
  `most_recent_failure_timestamp`** (e.g. a 503 from the receiver) and
  **`retry_enabled`** — if false, a failed post-call delivery is dropped permanently.
  This is the fastest way to prove/disprove "the webhook fired but delivery failed".

## Traps

- The UI has no per-delivery webhook log — only the `most_recent_failure_*` fields
  above. For per-event delivery proof you must check the receiver's logs.
- All API timestamps are unix seconds (UTC); the UI renders local time.
- Batch recipient status `failed` means SIP-level failure (no conversation audio) but a
  `conversation_id` still exists and a `call_initiation_failure` webhook event is
  emitted (if enabled) instead of `post_call_transcription`.
