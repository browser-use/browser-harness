"""Match Chrome's live window IDs to the profiles that saved those windows."""
import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit


def connected_root(roots, websocket):
    """Only use session files from the directory advertising this connection."""
    endpoint = urlsplit(websocket)
    matches = []
    for root in roots:
        try:
            active = (root / "DevToolsActivePort").read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        if active == [str(endpoint.port), endpoint.path] and endpoint.path:
            matches.append(root)
    return matches[0] if len(matches) == 1 else None


@lru_cache(maxsize=128)
def _window_ids(path, mtime_ns, size):
    # Chrome's SNSS v3 records have a uint16 length followed by a command byte.
    # Skip navigation payloads. SetWindowType (9) carries the window ID and type.
    windows = set()
    with path.open("rb") as stream:
        if stream.read(8) != b"SNSS\x03\x00\x00\x00":
            return windows
        while len(length := stream.read(2)) == 2:
            count = int.from_bytes(length, "little")
            if not count:
                break
            if stream.read(1) == b"\x09" and count == 9:
                payload = stream.read(8)
                if len(payload) == 8:
                    windows.add(int.from_bytes(payload[:4], "little", signed=True))
            else:
                stream.seek(count - 1, 1)
    return windows


def window_profiles(root):
    try:
        state = json.loads((root / "Local State").read_bytes())
        profiles = state["profile"]["info_cache"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    result = {}
    if not isinstance(profiles, dict):
        return result
    for directory, info in profiles.items():
        if Path(directory).name != directory or directory in ("", ".", "..") or not isinstance(info, dict):
            continue
        try:
            sessions = (root / directory / "Sessions").glob("Session_*")
            latest = max((p for p in sessions if p.name[8:].isdigit()), key=lambda p: int(p.name[8:]), default=None)
            if latest is None:
                continue
            stat = latest.stat()
            windows = _window_ids(latest, stat.st_mtime_ns, stat.st_size)
        except OSError:
            continue
        for window in windows:
            result[window] = None if window in result else (info.get("name"), directory)
    return result
