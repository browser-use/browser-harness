from unittest.mock import patch, call
import helpers


def _mk_send(dialog):
    def _send(req):
        if req.get("meta") == "pending_dialog":
            return {"dialog": dialog}
        return {}
    return _send


def test_no_dialog_returns_none_and_does_not_call_cdp():
    with patch("helpers._send", side_effect=_mk_send(None)), \
         patch("helpers.cdp") as mock_cdp:
        result = helpers._check_and_dismiss_dialog()
    assert result is None
    mock_cdp.assert_not_called()


def test_dialog_pending_dismisses_with_accept_true():
    dialog = {"type": "alert", "message": "boom"}
    with patch("helpers._send", side_effect=_mk_send(dialog)), \
         patch("helpers.cdp") as mock_cdp:
        result = helpers._check_and_dismiss_dialog()
    assert result == dialog
    mock_cdp.assert_called_once_with(
        "Page.handleJavaScriptDialog", accept=True, promptText=""
    )


def test_dialog_dismiss_respects_accept_false():
    dialog = {"type": "confirm", "message": "delete?"}
    with patch("helpers._send", side_effect=_mk_send(dialog)), \
         patch("helpers.cdp") as mock_cdp:
        helpers._check_and_dismiss_dialog(accept=False)
    mock_cdp.assert_called_once_with(
        "Page.handleJavaScriptDialog", accept=False, promptText=""
    )


def test_dialog_dismiss_passes_prompt_text():
    dialog = {"type": "prompt", "message": "name?"}
    with patch("helpers._send", side_effect=_mk_send(dialog)), \
         patch("helpers.cdp") as mock_cdp:
        helpers._check_and_dismiss_dialog(prompt_text="alice")
    mock_cdp.assert_called_once_with(
        "Page.handleJavaScriptDialog", accept=True, promptText="alice"
    )


def test_env_var_disables_auto_dismiss(monkeypatch):
    monkeypatch.setenv("BH_NO_AUTO_DISMISS", "1")
    dialog = {"type": "alert", "message": "x"}
    with patch("helpers._send", side_effect=_mk_send(dialog)) as mock_send, \
         patch("helpers.cdp") as mock_cdp:
        result = helpers._check_and_dismiss_dialog()
    assert result is None
    mock_cdp.assert_not_called()
    mock_send.assert_not_called()


def test_click_at_xy_auto_dismisses_dialog():
    dialog = {"type": "alert", "message": "clicked"}
    cdp_calls = []
    def fake_cdp(method, **kwargs):
        cdp_calls.append((method, kwargs))
        return {}
    with patch("helpers._send", side_effect=_mk_send(dialog)), \
         patch("helpers.cdp", side_effect=fake_cdp):
        helpers.click_at_xy(100, 200)
    methods = [c[0] for c in cdp_calls]
    assert "Input.dispatchMouseEvent" in methods
    assert "Page.handleJavaScriptDialog" in methods
    assert methods.index("Page.handleJavaScriptDialog") > methods.index("Input.dispatchMouseEvent")


def test_press_key_auto_dismisses_dialog():
    dialog = {"type": "confirm", "message": "submit?"}
    cdp_calls = []
    def fake_cdp(method, **kwargs):
        cdp_calls.append((method, kwargs))
        return {}
    with patch("helpers._send", side_effect=_mk_send(dialog)), \
         patch("helpers.cdp", side_effect=fake_cdp):
        helpers.press_key("Enter")
    methods = [c[0] for c in cdp_calls]
    assert "Input.dispatchKeyEvent" in methods
    assert "Page.handleJavaScriptDialog" in methods


def test_goto_url_auto_dismisses_beforeunload():
    dialog = {"type": "beforeunload", "message": "leave?"}
    cdp_calls = []
    def fake_cdp(method, **kwargs):
        cdp_calls.append((method, kwargs))
        return {}
    with patch("helpers._send", side_effect=_mk_send(dialog)), \
         patch("helpers.cdp", side_effect=fake_cdp):
        helpers.goto_url("https://example.com")
    methods = [c[0] for c in cdp_calls]
    assert "Page.navigate" in methods
    assert "Page.handleJavaScriptDialog" in methods


def test_click_no_dialog_only_calls_input_dispatch():
    cdp_calls = []
    def fake_cdp(method, **kwargs):
        cdp_calls.append((method, kwargs))
        return {}
    with patch("helpers._send", side_effect=_mk_send(None)), \
         patch("helpers.cdp", side_effect=fake_cdp):
        helpers.click_at_xy(50, 60)
    methods = [c[0] for c in cdp_calls]
    assert "Page.handleJavaScriptDialog" not in methods
    assert methods.count("Input.dispatchMouseEvent") == 2
