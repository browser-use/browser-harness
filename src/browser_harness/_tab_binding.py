"""Private, per-daemon target binding. Never persist CDP credentials or URLs."""
import hashlib
import json
import os
import tempfile
from urllib.parse import urlsplit


class TabLost(RuntimeError):
    def __init__(self, reason):
        super().__init__(f"TabLost: {reason}; use list_tabs() and switch_tab(targetId), or new_tab(), explicitly")


def browser_key(url, remote_id=None):
    parsed = urlsplit(url)
    identity = f"cloud:{remote_id}" if remote_id else f"{parsed.scheme}://{parsed.hostname}:{parsed.port}{parsed.path}"
    return hashlib.sha256(identity.encode()).hexdigest()


class TabBinding:
    def __init__(self, path, key):
        self.path, self.key = path, key

    def load(self):
        try:
            data = json.loads(self.path.read_text())
        except FileNotFoundError:
            return None
        except (OSError, ValueError):
            raise TabLost("saved tab binding cannot be read") from None
        if not isinstance(data, dict) or data.get("version") != 1:
            raise TabLost("saved tab binding is invalid")
        if data.get("browser") != self.key:
            raise TabLost("the browser changed since the saved tab was selected")
        if not isinstance(data.get("target"), str) or not data["target"]:
            raise TabLost("saved target is invalid")
        if data.get("owned") is not None and not isinstance(data["owned"], str):
            raise TabLost("saved owned target is invalid")
        return data

    def save(self, target, owned):
        data = {"version": 1, "browser": self.key, "target": target, "owned": owned}
        # mkstemp creates mode 0600. Replace atomically: a crash must not leave
        # a truncated binding that looks like a first-ever attachment.
        fd, tmp = tempfile.mkstemp(prefix=self.path.name + ".", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        finally:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass
