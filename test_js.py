import pytest
from unittest.mock import patch
import helpers


def _capture_cdp():
    captured = []
    def fake_cdp(method, **kwargs):
        captured.append((method, kwargs))
        return {"result": {"value": None}}
    return fake_cdp, captured


def _evaluated_expression(captured):
    return next(kw["expression"] for m, kw in captured if m == "Runtime.evaluate")


def test_simple_expression_passes_through():
    fake_cdp, captured = _capture_cdp()
    with patch("helpers.cdp", side_effect=fake_cdp):
        helpers.js("document.title")
    assert _evaluated_expression(captured) == "document.title"


def test_return_statement_gets_wrapped():
    fake_cdp, captured = _capture_cdp()
    with patch("helpers.cdp", side_effect=fake_cdp):
        helpers.js("const x = 1; return x")
    assert _evaluated_expression(captured) == "(function(){const x = 1; return x})()"


def test_iife_with_internal_return_is_not_double_wrapped():
    fake_cdp, captured = _capture_cdp()
    with patch("helpers.cdp", side_effect=fake_cdp):
        helpers.js("(function(){ return document.title; })()")
    assert _evaluated_expression(captured) == "(function(){ return document.title; })()"


def test_js_raises_on_runtime_exception():
    def fake_cdp(method, **kwargs):
        return {
            "exceptionDetails": {
                "text": "Uncaught ReferenceError",
                "exception": {"description": "ReferenceError: missing is not defined"},
            }
        }

    with patch("helpers.cdp", side_effect=fake_cdp):
        with pytest.raises(RuntimeError, match="missing is not defined"):
            helpers.js("missing.value")


def test_wait_for_js_returns_first_truthy_value():
    with patch("helpers.js", side_effect=[False, None, {"ready": True}]), \
         patch("helpers.time.sleep") as sleep:
        assert helpers.wait_for_js("window.__ready", timeout=1, interval=0.01) == {"ready": True}

    assert sleep.call_count == 2


def test_wait_for_js_propagates_js_errors():
    with patch("helpers.js", side_effect=RuntimeError("JavaScript evaluation failed")), \
         patch("helpers.time.sleep") as sleep:
        with pytest.raises(RuntimeError, match="JavaScript evaluation failed"):
            helpers.wait_for_js("missing.value", timeout=1, interval=0.01)

    sleep.assert_not_called()


def test_wait_for_selector_uses_visible_predicate():
    with patch("helpers.wait_for_js", return_value=True) as wait:
        assert helpers.wait_for_selector("button[aria-label='Save']", timeout=3, visible=True)

    expression = wait.call_args[0][0]
    assert "button[aria-label='Save']" in expression
    assert "getBoundingClientRect" in expression
    assert "visibility !== 'hidden'" in expression
    assert wait.call_args.kwargs == {"timeout": 3, "interval": 0.2}


def test_page_outline_returns_agent_summary():
    outline = [{"tag": "button", "text": "Save", "rect": [10, 20, 80, 30]}]
    with patch("helpers.js", return_value=outline) as run_js:
        assert helpers.page_outline(limit=3) == outline

    expression = run_js.call_args[0][0]
    assert "const limit = 3" in expression
    assert "a,button,input,textarea,select" in expression
    assert "aria-label" in expression


def test_page_outline_clamps_negative_limit():
    with patch("helpers.js", return_value=[]) as run_js:
        assert helpers.page_outline(limit=-1) == []

    assert "const limit = 0" in run_js.call_args[0][0]
