import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip("mcp")
from mcp_types import CallToolRequestParams
import mcp_server


def call(name, **arguments):
    return asyncio.run(mcp_server.SERVER._handle_call_tool(None, CallToolRequestParams(name=name, arguments=arguments)))


def test_http_works_without_a_browser_and_preserves_headers(monkeypatch):
    seen = []
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.headers.get("X-Test"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"fixture response")
        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    monkeypatch.delenv("BROWSER_USE_API_KEY", raising=False)
    def no_browser():
        raise RuntimeError("Chrome unavailable")
    monkeypatch.setattr(mcp_server, "ensure_daemon", no_browser)
    try:
        result = call("browser_http_get", url=f"http://127.0.0.1:{server.server_port}", timeout=2, headers={"X-Test": "preserved"})
        assert result.is_error is False
        assert json.loads(result.content[0].text) == {"text": "fixture response"}
        assert seen == ["preserved"]
        browser_result = call("browser_page_info")
        assert browser_result.is_error is True
        assert "Chrome unavailable" in browser_result.content[0].text
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_http_options_and_failures_reach_existing_helper(monkeypatch):
    seen = []
    monkeypatch.setattr(mcp_server, "ensure_daemon", lambda: pytest.fail("HTTP started Chrome"))
    def fail(url, headers, timeout):
        seen.append((url, headers, timeout))
        raise TimeoutError("HTTP timed out")
    monkeypatch.setattr(mcp_server, "http_get", fail)
    result = call("browser_http_get", url="https://example.test", headers={"Accept": "application/json"}, timeout=0.5)
    assert result.is_error is True
    assert "HTTP timed out" in result.content[0].text
    assert seen == [("https://example.test", {"Accept": "application/json"}, 0.5)]
