from unittest.mock import patch

import math

import pytest

from browser_harness import helpers


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
    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        helpers.js("document.title")
    assert _evaluated_expression(captured) == "document.title"


def test_return_statement_gets_wrapped():
    fake_cdp, captured = _capture_cdp()
    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        helpers.js("const x = 1; return x")
    assert _evaluated_expression(captured) == "(function(){const x = 1; return x})()"


def test_iife_with_internal_return_is_not_double_wrapped():
    fake_cdp, captured = _capture_cdp()
    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        helpers.js("(function(){ return document.title; })()")
    assert _evaluated_expression(captured) == "(function(){ return document.title; })()"


def test_js_raises_on_syntax_error_exception_details():
    def fake_cdp(method, **kwargs):
        return {
            "result": {
                "type": "object",
                "subtype": "error",
                "description": "SyntaxError: Invalid or unexpected token",
            },
            "exceptionDetails": {
                "text": "Uncaught",
                "lineNumber": 1,
                "columnNumber": 12,
            },
        }

    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        with pytest.raises(RuntimeError, match="SyntaxError"):
            helpers.js('return "a\n\nb";')


def test_js_raises_on_runtime_error_exception_details():
    def fake_cdp(method, **kwargs):
        return {
            "result": {
                "type": "object",
                "subtype": "error",
                "description": "ReferenceError: missing is not defined",
            },
            "exceptionDetails": {
                "text": "Uncaught",
                "lineNumber": 0,
                "columnNumber": 17,
            },
        }

    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        with pytest.raises(RuntimeError, match="ReferenceError"):
            helpers.js("return missing.value")


def test_js_raises_on_error_result_without_exception_details():
    def fake_cdp(method, **kwargs):
        return {
            "result": {
                "type": "object",
                "subtype": "error",
                "description": "Error: evaluation failed",
            }
        }

    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        with pytest.raises(RuntimeError, match="evaluation failed"):
            helpers.js("throw new Error('evaluation failed')")


def test_return_word_inside_string_does_not_trigger_wrapping():
    fake_cdp, captured = _capture_cdp()
    expr = 'document.body.innerText.includes("return ")'
    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        helpers.js(expr)
    assert _evaluated_expression(captured) == expr


def test_return_word_inside_comment_does_not_trigger_wrapping():
    fake_cdp, captured = _capture_cdp()
    expr = "// return comment\n1 + 1"
    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        helpers.js(expr)
    assert _evaluated_expression(captured) == expr


@pytest.mark.parametrize("expr", ["return\t1", "return\n1"])
def test_top_level_return_with_whitespace_gets_wrapped(expr):
    fake_cdp, captured = _capture_cdp()
    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        helpers.js(expr)
    assert _evaluated_expression(captured) == f"(function(){{{expr}}})()"


@pytest.mark.parametrize(
    ("unserializable", "expected"),
    [
        ("NaN", math.nan),
        ("Infinity", math.inf),
        ("-Infinity", -math.inf),
        ("-0", -0.0),
        ("1n", 1),
    ],
)
def test_js_returns_unserializable_values(unserializable, expected):
    def fake_cdp(method, **kwargs):
        return {"result": {"type": "number", "unserializableValue": unserializable, "description": unserializable}}

    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        value = helpers.js(unserializable)

    if isinstance(expected, float) and math.isnan(expected):
        assert math.isnan(value)
    elif expected == 0:
        assert value == 0
        assert math.copysign(1, value) == math.copysign(1, expected)
    else:
        assert value == expected


def test_js_primitive_exception_message_uses_exception_value():
    def fake_cdp(method, **kwargs):
        return {
            "result": {"type": "string", "value": "boom"},
            "exceptionDetails": {
                "text": "Uncaught",
                "lineNumber": 0,
                "columnNumber": 9,
                "exception": {"type": "string", "value": "boom"},
            },
        }

    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        with pytest.raises(RuntimeError, match="boom"):
            helpers.js("throw value")


def test_js_timeout_error_includes_expression_context():
    def fake_cdp(method, **kwargs):
        raise TimeoutError("timed out")

    with patch("browser_harness.helpers.cdp", side_effect=fake_cdp):
        with pytest.raises(RuntimeError, match="Runtime.evaluate.*document.title"):
            helpers.js("document.title")
