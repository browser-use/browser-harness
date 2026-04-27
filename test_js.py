from unittest.mock import patch
import helpers


def _capture_cdp(runtime_results=None):
    captured = []
    runtime_results = list(runtime_results or [{"result": {"value": None}}])

    def fake_cdp(method, **kwargs):
        captured.append((method, kwargs))
        if method == "Runtime.evaluate" and runtime_results:
            return runtime_results.pop(0)
        return {"result": {"value": None}}

    return fake_cdp, captured


def _evaluated_expression(captured):
    return next(kw["expression"] for m, kw in captured if m == "Runtime.evaluate")


def _evaluated_expressions(captured):
    return [kw["expression"] for m, kw in captured if m == "Runtime.evaluate"]


def test_simple_expression_passes_through():
    fake_cdp, captured = _capture_cdp()
    with patch("helpers.cdp", side_effect=fake_cdp):
        helpers.js("document.title")
    assert _evaluated_expression(captured) == "document.title"


def test_top_level_return_retries_wrapped():
    fake_cdp, captured = _capture_cdp([
        {
            "exceptionDetails": {
                "text": "Uncaught SyntaxError: Illegal return statement",
                "exception": {
                    "className": "SyntaxError",
                    "description": "SyntaxError: Illegal return statement",
                },
            }
        },
        {"result": {"value": 1}},
    ])
    with patch("helpers.cdp", side_effect=fake_cdp):
        assert helpers.js("const x = 1; return x") == 1
    assert _evaluated_expressions(captured) == [
        "const x = 1; return x",
        "(function(){const x = 1; return x})()",
    ]


def test_iife_with_internal_return_is_not_double_wrapped():
    fake_cdp, captured = _capture_cdp()
    with patch("helpers.cdp", side_effect=fake_cdp):
        helpers.js("(function(){ return document.title; })()")
    assert _evaluated_expression(captured) == "(function(){ return document.title; })()"


def test_runtime_error_message_does_not_retry_wrapped():
    fake_cdp, captured = _capture_cdp([
        {
            "exceptionDetails": {
                "text": "Uncaught Error: Illegal return statement",
                "exception": {
                    "className": "Error",
                    "description": "Error: Illegal return statement",
                },
            }
        }
    ])
    expression = "throw new Error('Illegal return statement')"
    with patch("helpers.cdp", side_effect=fake_cdp):
        assert helpers.js(expression) is None
    assert _evaluated_expressions(captured) == [expression]


def test_iife_return_is_not_wrapped():
    fake_cdp, captured = _capture_cdp([{"result": {"value": 1}}])
    expression = "(() => { return 1 })()"
    with patch("helpers.cdp", side_effect=fake_cdp):
        assert helpers.js(expression) == 1
    assert _evaluated_expressions(captured) == [expression]
