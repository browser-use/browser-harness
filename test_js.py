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
