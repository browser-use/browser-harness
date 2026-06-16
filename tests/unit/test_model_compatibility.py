import sys
from io import StringIO
from unittest.mock import patch

import pytest

from browser_harness import model_compatibility
from browser_harness.model_compatibility import (
    infer_parameter_size_b,
    load_registry,
    models_list,
    models_main,
    parse_size_b,
    print_model_info,
    resolve_model,
)


def test_parse_size_b():
    assert parse_size_b("35b") == 35
    assert parse_size_b("35B") == 35
    assert parse_size_b("8.9b") == 8.9
    assert parse_size_b("70") == 70
    with pytest.raises(ValueError):
        parse_size_b("")


def test_load_registry_smoke():
    rows = load_registry()
    assert isinstance(rows, list)
    assert all("model" in r and "status" in r for r in rows)


def test_infer_parameter_size_b():
    assert infer_parameter_size_b({"model": "x", "parameter_size_b": 12}) == 12.0
    assert infer_parameter_size_b({"model": "foo-70b-bar"}) == 70.0
    assert infer_parameter_size_b({"model": "nope"}) is None


def test_resolve_model_exact_and_substring():
    rows = [
        {"model": "ab", "provider": "p", "status": "works", "notes": "", "last_tested": "2026-01-01"},
        {"model": "abc", "provider": "p", "status": "works", "notes": "", "last_tested": "2026-01-01"},
    ]
    assert resolve_model("abc", rows)["model"] == "abc"
    assert resolve_model("AB", rows)["model"] == "ab"
    amb = resolve_model("a", rows)
    assert isinstance(amb, list) and len(amb) > 1


def test_models_list_filters():
    fake = [
        {
            "model": "big",
            "provider": "ollama",
            "status": "verified",
            "parameter_size_b": 70,
            "notes": "n",
            "last_tested": "2026-01-01",
        },
        {
            "model": "small",
            "provider": "ollama",
            "status": "works",
            "parameter_size_b": 7,
            "notes": "n",
            "last_tested": "2026-01-01",
        },
    ]
    out = StringIO()
    with patch.object(model_compatibility, "load_registry", return_value=fake), patch("sys.stdout", out):
        assert models_list(["list", "--min-size", "35b", "--status", "verified"]) == 0
    lines = out.getvalue().strip().splitlines()
    assert len(lines) == 2  # header + one row
    assert "big" in lines[1]
    assert "small" not in lines[1]


def test_models_list_bad_flag():
    err = StringIO()
    with patch("sys.stderr", err):
        assert models_list(["list", "--nope"]) == 2
    assert "unexpected" in err.getvalue()


def test_models_main_dispatches_list():
    out = StringIO()
    with patch.object(model_compatibility, "load_registry", return_value=[]), patch("sys.stdout", out):
        assert models_main(["list"]) == 0
    assert "model\tprovider" in out.getvalue()


def test_print_model_info_not_found():
    err = StringIO()
    with patch.object(model_compatibility, "load_registry", return_value=[]), patch("sys.stderr", err):
        assert print_model_info("missing-model-xyz") == 1
    assert "no model matched" in err.getvalue()


def test_run_model_info_invocation():
    from browser_harness import run

    out = StringIO()
    err = StringIO()
    with patch.object(sys, "argv", ["browser-harness", "--model-info", "mistral-small"]), \
         patch("sys.stdout", out), \
         patch("sys.stderr", err):
        try:
            run.main()
        except SystemExit as e:
            assert e.code == 0
        else:
            raise AssertionError("expected sys.exit")
    body = out.getvalue()
    assert "mistral-small" in body
    assert "anyscale" in body
