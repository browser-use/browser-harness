"""Dialog isolation through a real CDP client and daemon IPC connection."""

import asyncio
import contextlib
import json
import tempfile
from pathlib import Path

import pytest
from websockets.asyncio.server import serve as websocket_server

from browser_harness import _ipc as ipc, daemon, helpers


class Browser:
    """The external browser boundary; each tab keeps its own JS dialog."""

    def __init__(self):
        self.connection = None
        self.dialogs = {}
        self.sessions = {"a": "a", "b": "b"}
        self.attachments = {}
        self.evaluations = []
        self.observed = asyncio.Queue()
        self.pages = {
            "a": {"type": "page", "targetId": "a", "url": "https://a.test", "title": "A"},
            "b": {"type": "page", "targetId": "b", "url": "https://b.test", "title": "B"},
        }

    async def connect(self, connection):
        self.connection = connection
        async for raw in connection:
            request = json.loads(raw)
            method = request["method"]
            params = request.get("params", {})
            session = request.get("sessionId")
            if method == "Target.getTargets":
                result = {"targetInfos": list(self.pages.values())}
            elif method == "Target.attachToTarget":
                target = params["targetId"]
                count = self.attachments.get(target, 0) + 1
                self.attachments[target] = count
                sid = target if count == 1 else f"{target}-{count}"
                self.sessions[sid] = target
                result = {"sessionId": sid}
            elif method == "Target.getTargetInfo":
                result = {"targetInfo": self.pages[params["targetId"]]}
            elif method == "Runtime.evaluate":
                self.evaluations.append(session)
                target = self.sessions[session]
                if target in self.dialogs:
                    await connection.send(json.dumps({
                        "id": request["id"], "error": {"code": -32000, "message": "JavaScript is blocked by a dialog"},
                    }))
                    continue
                page = self.pages[target]
                result = {"result": {"type": "string", "value": json.dumps({"url": page["url"], "title": page["title"]})}}
            elif method.endswith(".enable") or method == "Network.disable":
                result = {}
            else:
                raise AssertionError(f"Unexpected browser request: {method}")
            await connection.send(json.dumps({"id": request["id"], "result": result}))

    async def event(self, method, params, session=None):
        message = {"method": method, "params": params}
        if session is not None:
            message["sessionId"] = session
        await self.connection.send(json.dumps(message))
        # The SDK's public callback runs after the daemon records the event.
        await asyncio.wait_for(self.observed.get(), 2)

    async def open_dialog(self, session, message, kind="alert"):
        target = self.sessions[session]
        payload = {"type": kind, "message": message, "url": self.pages[target]["url"]}
        self.dialogs[target] = payload
        await self.event("Page.javascriptDialogOpening", payload, session)
        return {"dialog": payload}

    async def close_dialog(self, session):
        self.dialogs.pop(self.sessions[session], None)
        await self.event("Page.javascriptDialogClosed", {"result": True, "userInput": ""}, session)


@contextlib.asynccontextmanager
async def connected_browser(monkeypatch):
    browser = Browser()
    # Keep Unix socket paths short on macOS; Windows uses the same TCP IPC path
    # as the installed harness. All runtime files belong to this fixture.
    with tempfile.TemporaryDirectory(prefix="bh-dialog-") as directory:
        monkeypatch.setattr(ipc, "_RUNTIME", Path(directory))
        monkeypatch.setattr(ipc, "BH_RUNTIME_DIR", directory)
        monkeypatch.setattr(ipc, "BH_RUNTIME_DIR_SHARED", False)
        monkeypatch.setattr(daemon, "LOG", str(Path(directory) / "daemon.log"))
        monkeypatch.setattr(daemon, "NAME", "default")
        monkeypatch.setattr(helpers, "NAME", "default")
        monkeypatch.setattr(daemon, "BROWSER_KIND", "cdp")
        monkeypatch.setenv("BH_TAB_MARKER", "0")
        async with websocket_server(browser.connect, "127.0.0.1", 0) as endpoint:
            port = endpoint.sockets[0].getsockname()[1]
            monkeypatch.setenv("BU_CDP_WS", f"ws://127.0.0.1:{port}")
            connection = daemon.Daemon()
            await connection.start()
            for register in (
                connection.cdp.register.Page.javascriptDialogOpening,
                connection.cdp.register.Page.javascriptDialogClosed,
                connection.cdp.register.Target.detachedFromTarget,
                connection.cdp.register.Target.targetDestroyed,
            ):
                register(lambda params, session: browser.observed.put_nowait((params, session)))
            server = asyncio.create_task(daemon.serve(connection))
            try:
                async with asyncio.timeout(2):
                    while not await asyncio.to_thread(ipc.ping, "default", 0.1):
                        await asyncio.sleep(0.01)
                # Establish that the full helper -> IPC -> CDP path works.
                assert await asyncio.to_thread(helpers.page_info) == {"url": "https://a.test", "title": "A"}
                browser.evaluations.clear()
                yield browser
            finally:
                connection.stop.set()
                await server
                await connection.cdp.stop()


async def switch_to(session, target=None):
    return await asyncio.to_thread(helpers._send, {
        "meta": "set_session", "session_id": session, "target_id": target or session,
    })


def test_dialog_on_previous_tab_does_not_hide_current_page(monkeypatch):
    async def run():
        async with connected_browser(monkeypatch) as browser:
            dialog_a = await browser.open_dialog("a", "A needs confirmation")
            assert await asyncio.to_thread(helpers.page_info) == dialog_a
            await switch_to("b")
            assert (await asyncio.to_thread(helpers.current_tab))["targetId"] == "b"
            assert await asyncio.to_thread(helpers.page_info) == {"url": "https://b.test", "title": "B"}
            assert browser.evaluations == ["b"]

    asyncio.run(run())


@pytest.mark.parametrize("kind", ["alert", "confirm", "prompt", "beforeunload"])
def test_background_dialog_does_not_replace_current_dialog(monkeypatch, kind):
    async def run():
        async with connected_browser(monkeypatch) as browser:
            await switch_to("b")
            dialog_b = await browser.open_dialog("b", "B needs an answer", kind)
            assert await asyncio.to_thread(helpers.page_info) == dialog_b
            await browser.open_dialog("a", "Background A", kind)
            assert await asyncio.to_thread(helpers.page_info) == dialog_b
            assert browser.evaluations == []

    asyncio.run(run())


def test_closing_background_dialog_keeps_current_dialog(monkeypatch):
    async def run():
        async with connected_browser(monkeypatch) as browser:
            await browser.open_dialog("a", "A")
            await switch_to("b")
            dialog_b = await browser.open_dialog("b", "B")
            assert await asyncio.to_thread(helpers.page_info) == dialog_b
            await browser.close_dialog("a")
            assert await asyncio.to_thread(helpers.page_info) == dialog_b
            await browser.close_dialog("b")
            assert await asyncio.to_thread(helpers.page_info) == {"url": "https://b.test", "title": "B"}
            assert browser.evaluations == ["b"]

    asyncio.run(run())


def test_switching_back_recovers_the_still_open_dialog(monkeypatch):
    async def run():
        async with connected_browser(monkeypatch) as browser:
            dialog_a = await browser.open_dialog("a", "A")
            await switch_to("b")
            dialog_b = await browser.open_dialog("b", "B")
            assert await asyncio.to_thread(helpers.page_info) == dialog_b
            await switch_to("a")
            assert await asyncio.to_thread(helpers.page_info) == dialog_a
            await browser.close_dialog("b")
            assert await asyncio.to_thread(helpers.page_info) == dialog_a
            assert browser.evaluations == []

    asyncio.run(run())


def test_detached_session_cannot_leave_a_pending_dialog(monkeypatch):
    async def run():
        async with connected_browser(monkeypatch) as browser:
            dialog_a = await browser.open_dialog("a", "A")
            assert await asyncio.to_thread(helpers.page_info) == dialog_a
            await browser.event("Target.detachedFromTarget", {"sessionId": "a", "targetId": "a"})
            browser.dialogs.pop("a")
            assert await asyncio.to_thread(helpers._send, {"meta": "pending_dialog"}) == {"dialog": None}
            await switch_to("b")
            dialog_b = await browser.open_dialog("b", "B")
            await browser.event("Target.detachedFromTarget", {"sessionId": "a", "targetId": "a"})
            assert await asyncio.to_thread(helpers.page_info) == dialog_b

    asyncio.run(run())


@pytest.mark.parametrize("detach_old", [False, True])
def test_reattaching_tracks_dialog_across_sessions(monkeypatch, detach_old):
    async def run():
        async with connected_browser(monkeypatch) as browser:
            dialog_a = await browser.open_dialog("a", "A")
            await switch_to("b")
            dialog_b = await browser.open_dialog("b", "B")
            attached = await asyncio.to_thread(helpers.cdp, "Target.attachToTarget", targetId="a", flatten=True)
            new_session = attached["sessionId"]
            assert new_session != "a"
            await switch_to(new_session, "a")
            assert await asyncio.to_thread(helpers.page_info) == dialog_a
            if detach_old:
                await browser.event("Target.detachedFromTarget", {"sessionId": "a", "targetId": "a"})
                assert await asyncio.to_thread(helpers.page_info) == dialog_a
            await browser.close_dialog(new_session if detach_old else "a")
            assert await asyncio.to_thread(helpers.page_info) == {"url": "https://a.test", "title": "A"}
            await switch_to("b")
            assert await asyncio.to_thread(helpers.page_info) == dialog_b

    asyncio.run(run())


def test_detaching_current_session_keeps_dialog_observed_by_another_session(monkeypatch):
    async def run():
        async with connected_browser(monkeypatch) as browser:
            dialog_a = await browser.open_dialog("a", "A")
            attached = await asyncio.to_thread(helpers.cdp, "Target.attachToTarget", targetId="a", flatten=True)
            new_session = attached["sessionId"]
            await switch_to(new_session, "a")
            await browser.event("Target.detachedFromTarget", {"sessionId": new_session, "targetId": "a"})
            assert (await asyncio.to_thread(helpers.current_tab))["targetId"] == "a"
            assert await asyncio.to_thread(helpers.page_info) == dialog_a
            assert browser.evaluations == []
            await browser.close_dialog("a")
            assert await asyncio.to_thread(helpers._send, {"meta": "pending_dialog"}) == {"dialog": None}

    asyncio.run(run())


def test_destroying_target_removes_only_its_dialog_and_sessions(monkeypatch):
    async def run():
        async with connected_browser(monkeypatch) as browser:
            await browser.open_dialog("a", "A")
            await switch_to("b")
            dialog_b = await browser.open_dialog("b", "B")
            await browser.event("Target.targetDestroyed", {"targetId": "a"})
            await browser.close_dialog("a")
            assert await asyncio.to_thread(helpers.page_info) == dialog_b
            await browser.event("Target.targetDestroyed", {"targetId": "b"})
            assert await asyncio.to_thread(helpers._send, {"meta": "pending_dialog"}) == {"dialog": None}
            # A queued event from a destroyed target cannot resurrect it.
            await browser.open_dialog("b", "Late B")
            assert await asyncio.to_thread(helpers._send, {"meta": "pending_dialog"}) == {"dialog": None}

    asyncio.run(run())


def test_unscoped_dialog_events_do_not_change_attached_page(monkeypatch):
    async def run():
        async with connected_browser(monkeypatch) as browser:
            dialog_a = await browser.open_dialog("a", "A")
            assert await asyncio.to_thread(helpers.page_info) == dialog_a
            await browser.event("Page.javascriptDialogOpening", {"type": "alert", "message": "Unscoped"})
            await browser.event("Page.javascriptDialogClosed", {"result": True})
            assert await asyncio.to_thread(helpers.page_info) == dialog_a
            assert browser.evaluations == []

    asyncio.run(run())
