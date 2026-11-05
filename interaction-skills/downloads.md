# Downloads

Separate browser-triggered downloads from direct `http_get(...)` fetches.
Authenticated exports and click-triggered files require the browser session.

## Deterministic browser downloads

Configure a unique absolute download directory before clicking the control:

```python
from pathlib import Path
import time

target = Path("/absolute/path/to/download-inbox")
target.mkdir(parents=True, exist_ok=True)
cdp(
    "Browser.setDownloadBehavior",
    behavior="allow",
    downloadPath=str(target),
    eventsEnabled=True,
)

before = {p.name for p in target.iterdir()}
# Perform the browser action that starts the download.

deadline = time.time() + 60
result = None
previous_size = -1
stable_polls = 0
while time.time() < deadline:
    partial = list(target.glob("*.crdownload"))
    complete = [p for p in target.iterdir() if p.name not in before and p.is_file()]
    if not partial and len(complete) == 1:
        size = complete[0].stat().st_size
        stable_polls = stable_polls + 1 if size > 0 and size == previous_size else 0
        previous_size = size
        if stable_polls >= 2:
            result = complete[0]
            break
    time.sleep(0.5)
if result is None:
    raise RuntimeError("download did not complete")
```

Record the directory and pre-click inventory before the action. Completion
requires: no `.crdownload` remains, exactly the expected number of new files
appears, each file is nonzero, and sizes remain stable across polls. Then verify
the expected signature or parser output and compute a checksum.

When several downloads are required, process them serially or bind each click
to its own baseline. Do not identify a download solely by Chrome's suggested
filename.
