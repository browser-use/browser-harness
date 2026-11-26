import asyncio
import json
import struct
from unittest.mock import AsyncMock

from browser_harness import daemon, tab_profiles


def _session(root, profile, number, windows):
    directory = root / profile / "Sessions"
    directory.mkdir(parents=True, exist_ok=True)
    records = b"".join(struct.pack("<HBii", 9, 9, window, 1) for window in windows)
    (directory / f"Session_{number}").write_bytes(b"SNSS\x03\0\0\0" + records)


def test_labels_follow_live_windows_not_profile_names(tmp_path):
    profiles = {"Personal": {"name": "Work"}, "Office": {"name": "Work"}}
    (tmp_path / "Local State").write_text(json.dumps({"profile": {"info_cache": profiles}}))
    _session(tmp_path, "Office", 9, [1])  # superseded session
    _session(tmp_path, "Office", 10, [2, 3])
    _session(tmp_path, "Personal", 11, [1, 3])  # ambiguous window 3

    d = daemon.Daemon()
    d.profile_root = tmp_path
    d.cdp = AsyncMock()
    d.cdp.send_raw.side_effect = [{"windowId": 1}, {"windowId": 2}, {"windowId": 3}]
    tabs = [{"targetId": str(i)} for i in range(4)]
    tabs[-1]["owner"] = "taken"
    asyncio.run(d._label_profiles(tabs))

    assert [(t.get("profile_name"), t.get("profile_directory")) for t in tabs] == [
        ("Work", "Personal"), ("Work", "Office"), (None, None), (None, None)
    ]
    assert d.cdp.send_raw.await_count == 3


def test_root_requires_matching_port_and_browser_path(tmp_path):
    (tmp_path / "DevToolsActivePort").write_text("9222\n/devtools/browser/current")
    assert tab_profiles.connected_root([tmp_path], "ws://localhost:9222/devtools/browser/old") is None
    assert tab_profiles.connected_root([tmp_path], "ws://localhost:9222/devtools/browser/current") == tmp_path
