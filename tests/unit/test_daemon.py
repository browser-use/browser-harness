import asyncio

from browser_harness.daemon import Daemon


def run(coro):
    return asyncio.run(coro)


def begin(daemon, attempt_id="attempt-1"):
    return run(daemon.handle({"meta": "health_begin", "attempt_id": attempt_id}))


def events_since(daemon, after_sequence, attempt_id="attempt-1"):
    return run(
        daemon.handle(
            {
                "meta": "health_events_since",
                "attempt_id": attempt_id,
                "after_sequence": after_sequence,
            }
        )
    )


def test_health_capabilities_advertise_exact_schema_and_daemon_identity():
    daemon = Daemon(event_max_count=7, event_max_bytes=4096, event_max_item_bytes=512)

    result = run(daemon.handle({"meta": "health_capabilities"}))

    assert result["capabilities"] == {
        "health_events_v1": {
            "schema_version": 1,
            "event_schema_version": 1,
            "operations": ["begin", "events_since", "seal"],
            "sequence_origin": 1,
            "retention": {
                "max_events": 7,
                "max_total_bytes": 4096,
                "max_event_bytes": 512,
            },
        }
    }
    assert result["daemon_fingerprint"]
    assert result["observation"] == {
        "ready": False,
        "target_id": None,
        "session_id": None,
        "target_epoch": 0,
        "session_epoch": 0,
        "subscriptions": {},
    }


def test_daemon_fingerprint_changes_when_daemon_is_replaced():
    first = Daemon()
    replacement = Daemon()

    assert first.daemon_fingerprint != replacement.daemon_fingerprint


def test_begin_and_seal_are_idempotent_and_fix_the_terminal_sequence():
    daemon = Daemon()

    first_begin = begin(daemon)
    daemon._record_health_event("Runtime.consoleAPICalled", {"type": "error"}, "session-1")
    repeated_begin = begin(daemon)
    first_seal = run(
        daemon.handle({"meta": "health_seal", "attempt_id": "attempt-1"})
    )
    daemon._record_health_event("Page.loadEventFired", {}, "session-1")
    repeated_seal = run(
        daemon.handle({"meta": "health_seal", "attempt_id": "attempt-1"})
    )

    assert first_begin == repeated_begin
    assert first_begin["start_sequence"] == 0
    assert first_seal == repeated_seal
    assert first_seal["sealed_through_sequence"] == 1
    result = events_since(daemon, first_begin["start_sequence"])
    assert [event["sequence"] for event in result["events"]] == [1]
    assert result["range"]["sealed_through_sequence"] == 1


def test_events_since_is_non_destructive_and_returns_sequenced_identity():
    daemon = Daemon()
    daemon.target_id = "target-1"
    daemon.session = "session-1"
    daemon.target_epoch = 2
    daemon.session_epoch = 3
    started = begin(daemon)
    daemon._record_health_event(
        "Runtime.exceptionThrown",
        {"exceptionDetails": {"text": "boom"}},
        "session-1",
    )

    first = events_since(daemon, started["start_sequence"])
    repeated = events_since(daemon, started["start_sequence"])

    assert first == repeated
    assert first["overflow"] is None
    assert first["range"] == {
        "requested_after_sequence": 0,
        "available_from_sequence": 1,
        "current_sequence": 1,
        "returned_through_sequence": 1,
        "sealed_through_sequence": None,
        "complete": True,
    }
    assert first["events"] == [
        {
            "sequence": 1,
            "method": "Runtime.exceptionThrown",
            "params": {"exceptionDetails": {"text": "boom"}},
            "session_id": "session-1",
            "daemon_fingerprint": daemon.daemon_fingerprint,
            "target_id": "target-1",
            "target_epoch": 2,
            "session_epoch": 3,
        }
    ]


def test_count_eviction_reports_an_explicit_gap():
    daemon = Daemon(event_max_count=2)
    started = begin(daemon)
    for index in range(3):
        daemon._record_health_event("Log.entryAdded", {"index": index}, None)

    result = events_since(daemon, started["start_sequence"])

    assert [event["sequence"] for event in result["events"]] == [2, 3]
    assert result["range"]["complete"] is False
    assert result["overflow"] == {
        "kind": "retention_or_truncation",
        "requested_after_sequence": 0,
        "lost_through_sequence": 1,
        "available_from_sequence": 2,
    }


def test_total_byte_eviction_is_independent_of_count_limit():
    daemon = Daemon(
        event_max_count=20,
        event_max_bytes=900,
        event_max_item_bytes=800,
    )
    started = begin(daemon)
    for index in range(4):
        daemon._record_health_event(
            "Runtime.consoleAPICalled",
            {"index": index, "message": "x" * 260},
            None,
        )

    result = events_since(daemon, started["start_sequence"])

    assert result["overflow"] is not None
    assert result["overflow"]["lost_through_sequence"] >= 1
    assert result["events"][-1]["params"]["index"] == 3


def test_out_of_order_losses_keep_a_monotonic_union_when_gap_storage_is_one():
    daemon = Daemon(event_max_count=1, event_max_item_bytes=300)
    started = begin(daemon)
    daemon._record_health_event("Log.entryAdded", {"text": "retained-1"}, None)
    daemon._record_health_event(
        "Runtime.consoleAPICalled",
        {"args": [{"value": "x" * 600}]},
        None,
    )
    daemon._record_health_event("Log.entryAdded", {"text": "retained-3"}, None)

    result = events_since(daemon, 1)

    assert [event["sequence"] for event in result["events"]] == [3]
    assert result["range"]["complete"] is False
    assert result["overflow"]["lost_through_sequence"] == 2


def test_oversized_event_is_not_retained_and_makes_the_range_incomplete():
    daemon = Daemon(event_max_item_bytes=300)
    started = begin(daemon)
    daemon._record_health_event(
        "Runtime.consoleAPICalled",
        {"args": [{"type": "string", "value": "x" * 600}]},
        None,
    )

    result = events_since(daemon, started["start_sequence"])

    assert result["events"] == []
    assert result["range"]["current_sequence"] == 1
    assert result["range"]["complete"] is False
    assert result["overflow"]["lost_through_sequence"] == 1


def test_response_and_request_bodies_are_removed_before_retention():
    daemon = Daemon()
    begin(daemon)
    daemon._record_health_event(
        "Network.requestWillBeSent",
        {
            "request": {
                "url": "https://example.test/",
                "postData": "password=not-retained",
            },
            "response": {
                "status": 500,
                "body": "not-retained",
                "payloadData": "not-retained",
            },
        },
        None,
    )

    event = events_since(daemon, 0)["events"][0]

    assert event["params"] == {
        "request": {"url": "https://example.test/"},
        "response": {"status": 500},
    }


def test_network_payload_variants_are_removed_without_deleting_ordinary_data():
    daemon = Daemon()
    begin(daemon)
    daemon._record_health_event(
        "Network.requestWillBeSent",
        {
            "request": {
                "url": "https://example.test/",
                "postDataEntries": [{"bytes": "encoded-request-body"}],
                "metadata": {"data": "keep-metadata"},
            }
        },
        None,
    )
    daemon._record_health_event(
        "Network.eventSourceMessageReceived",
        {"eventName": "message", "eventId": "1", "data": "event-stream-body"},
        None,
    )
    daemon._record_health_event(
        "Network.dataReceived",
        {"requestId": "1", "dataLength": 12, "data": "response-body"},
        None,
    )
    daemon._record_health_event(
        "Network.directTCPSocketChunkReceived",
        {"identifier": "socket-1", "data": "socket-body"},
        None,
    )
    daemon._record_health_event(
        "Runtime.consoleAPICalled",
        {"data": "ordinary-runtime-metadata"},
        None,
    )

    params = [event["params"] for event in events_since(daemon, 0)["events"]]

    assert params == [
        {
            "request": {
                "url": "https://example.test/",
                "metadata": {"data": "keep-metadata"},
            }
        },
        {"eventName": "message", "eventId": "1"},
        {"requestId": "1", "dataLength": 12},
        {"identifier": "socket-1"},
        {"data": "ordinary-runtime-metadata"},
    ]


def test_compatibility_drain_advances_its_cursor_without_deleting_evidence():
    daemon = Daemon()
    begin(daemon)
    daemon._record_health_event("Network.requestWillBeSent", {"requestId": "1"}, None)

    first_drain = run(daemon.handle({"meta": "drain_events"}))
    second_drain = run(daemon.handle({"meta": "drain_events"}))
    guardian_read = events_since(daemon, 0)

    assert [event["sequence"] for event in first_drain["events"]] == [1]
    assert second_drain["events"] == []
    assert [event["sequence"] for event in guardian_read["events"]] == [1]


class FakeCDP:
    def __init__(self):
        self.attachments = [
            ("target-1", "session-1"),
            ("target-2", "session-2"),
        ]
        self.calls = []

    async def send_raw(self, method, params=None, session_id=None):
        self.calls.append((method, params, session_id))
        if method == "Target.getTargets":
            target_id, _ = self.attachments[0]
            return {
                "targetInfos": [
                    {
                        "targetId": target_id,
                        "type": "page",
                        "url": "https://example.test/",
                    }
                ]
            }
        if method == "Target.attachToTarget":
            _, session_id = self.attachments.pop(0)
            return {"sessionId": session_id}
        return {}


def test_reattachment_restores_all_health_subscriptions_and_emits_continuity():
    daemon = Daemon()
    daemon.cdp = FakeCDP()
    begin_result = begin(daemon)

    run(daemon.attach_first_page(reason="initial_attach"))
    run(daemon.attach_first_page(reason="reattach"))

    enabled = [
        (method, session_id)
        for method, _, session_id in daemon.cdp.calls
        if method.endswith(".enable") or method == "Target.setDiscoverTargets"
    ]
    assert ("Target.setDiscoverTargets", None) in enabled
    for session_id in ("session-1", "session-2"):
        for domain in ("Page", "Runtime", "Log", "Network"):
            assert (f"{domain}.enable", session_id) in enabled

    capability = run(daemon.handle({"meta": "health_capabilities"}))
    assert capability["observation"]["ready"] is True
    assert capability["observation"]["target_id"] == "target-2"
    assert capability["observation"]["session_id"] == "session-2"
    assert capability["observation"]["target_epoch"] == 2
    assert capability["observation"]["session_epoch"] == 2
    assert all(
        proof["enabled"]
        for proof in capability["observation"]["subscriptions"].values()
    )

    continuity = events_since(daemon, begin_result["start_sequence"])["events"]
    assert [event["method"] for event in continuity] == [
        "BrowserHarness.attachmentChanged",
        "BrowserHarness.attachmentChanged",
    ]
    assert continuity[-1]["params"]["reason"] == "reattach"


class BlockingSubscriptionCDP:
    def __init__(self):
        self.subscription_started = asyncio.Event()
        self.allow_subscription = asyncio.Event()

    async def send_raw(self, method, params=None, session_id=None):
        if method == "Target.setDiscoverTargets":
            self.subscription_started.set()
            await self.allow_subscription.wait()
        return {}


def test_attachment_transition_never_attests_new_identity_with_old_ready_proof():
    async def scenario():
        daemon = Daemon()
        daemon.cdp = BlockingSubscriptionCDP()
        daemon.target_id = "target-old"
        daemon.session = "session-old"
        daemon.target_epoch = 1
        daemon.session_epoch = 1
        daemon.subscriptions = {
            "Target": {"enabled": True, "scope": "browser", "session_id": None},
            **{
                domain: {
                    "enabled": True,
                    "scope": "session",
                    "session_id": "session-old",
                }
                for domain in ("Page", "Runtime", "Log", "Network")
            },
        }

        transition = asyncio.create_task(
            daemon._set_attachment("target-new", "session-new", "switch")
        )
        await daemon.cdp.subscription_started.wait()

        during = await daemon.handle(
            {"meta": "health_begin", "attempt_id": "during-transition"}
        )
        assert during["observation"]["target_id"] == "target-new"
        assert during["observation"]["session_id"] == "session-new"
        assert during["observation"]["ready"] is False
        assert during["observation"]["subscriptions"] == {}
        assert daemon.health_events.sequence == 0

        daemon.cdp.allow_subscription.set()
        await transition
        after = await daemon.handle({"meta": "health_capabilities"})
        assert after["observation"]["ready"] is True
        assert all(
            proof["session_id"] == "session-new"
            for domain, proof in after["observation"]["subscriptions"].items()
            if domain != "Target"
        )
        assert daemon.health_events.sequence == 1

    run(scenario())


def test_invalidation_during_subscription_discards_stale_attachment_proof():
    async def scenario():
        daemon = Daemon()
        daemon.cdp = BlockingSubscriptionCDP()

        transition = asyncio.create_task(
            daemon._set_attachment("target-new", "session-new", "switch")
        )
        await daemon.cdp.subscription_started.wait()
        daemon._record_cdp_event(
            "Target.targetDestroyed",
            {"targetId": "target-new"},
            None,
        )
        daemon.cdp.allow_subscription.set()
        established = await transition

        assert established is False
        assert daemon.target_id is None
        assert daemon.session is None
        assert daemon.subscriptions == {}
        assert [
            event["method"]
            for event in daemon.health_events.read_after(0)["events"]
        ] == [
            "Target.targetDestroyed",
            "BrowserHarness.attachmentInvalidated",
        ]

    run(scenario())


def ready_daemon():
    daemon = Daemon()
    daemon.target_id = "target-current"
    daemon.session = "session-current"
    daemon.target_epoch = 1
    daemon.session_epoch = 1
    daemon.subscriptions = {
        "Target": {"enabled": True, "scope": "browser", "session_id": None},
        **{
            domain: {
                "enabled": True,
                "scope": "session",
                "session_id": "session-current",
            }
            for domain in ("Page", "Runtime", "Log", "Network")
        },
    }
    return daemon


def test_current_session_detach_invalidates_observation_but_unrelated_detach_does_not():
    daemon = ready_daemon()
    started = begin(daemon)

    daemon._record_cdp_event(
        "Target.detachedFromTarget",
        {"sessionId": "session-other", "targetId": "target-other"},
        None,
    )
    assert daemon._observation()["ready"] is True

    daemon._record_cdp_event(
        "Target.detachedFromTarget",
        {"sessionId": "session-current", "targetId": "target-current"},
        None,
    )
    sealed = run(daemon.handle({"meta": "health_seal", "attempt_id": "attempt-1"}))

    assert daemon.target_id == "target-current"
    assert daemon.session is None
    assert daemon.session_epoch == 2
    assert sealed["observation"]["ready"] is False
    assert sealed["observation"]["subscriptions"] == {}
    methods = [
        event["method"]
        for event in events_since(daemon, started["start_sequence"])["events"]
    ]
    assert methods == [
        "Target.detachedFromTarget",
        "Target.detachedFromTarget",
        "BrowserHarness.attachmentInvalidated",
    ]


def test_current_target_destroy_invalidates_target_session_and_proof():
    daemon = ready_daemon()
    begin(daemon)

    daemon._record_cdp_event(
        "Target.targetDestroyed",
        {"targetId": "target-current"},
        None,
    )

    assert daemon.target_id is None
    assert daemon.session is None
    assert daemon.target_epoch == 2
    assert daemon.session_epoch == 2
    assert daemon._observation()["ready"] is False
    assert daemon._observation()["subscriptions"] == {}
