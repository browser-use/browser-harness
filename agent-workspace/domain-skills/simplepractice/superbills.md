# SimplePractice — discover and download superbills

Field-tested against authenticated `*.clientsecure.me` billing portals. Use the
existing local Chrome session; stop for passwords, MFA, consent, or account
selection.

## Page shape

- A signed-in billing page exposes a visible `Sign out` button.
- A login wall normally uses a `/sign-in` URL.
- Each available superbill is a table row containing a statement date, amount,
  and a button named `Statement for Insurance Reimbursement #<id>`.
- Clicking that button opens a statement dialog. Its visible `DOWNLOAD`
  button starts the PDF download.

Do not treat the statement date as the service date. The downloaded PDF is the
authority for patient, provider, service dates, and total.

## Deterministic download

Set a unique local directory before clicking any statement:

```python
from pathlib import Path
import time

download_dir = Path("/absolute/path/to/run-inbox")
download_dir.mkdir(parents=True, exist_ok=True)
cdp(
    "Browser.setDownloadBehavior",
    behavior="allow",
    downloadPath=str(download_dir),
    eventsEnabled=True,
)

before = {p.name for p in download_dir.iterdir()}
# Open one statement row, then click the dialog's visible DOWNLOAD button.

deadline = time.time() + 60
candidate = None
last_size = -1
stable = 0
while time.time() < deadline:
    partials = list(download_dir.glob("*.crdownload"))
    pdfs = [p for p in download_dir.glob("*.pdf") if p.name not in before]
    if not partials and len(pdfs) == 1:
        size = pdfs[0].stat().st_size
        stable = stable + 1 if size > 0 and size == last_size else 0
        last_size = size
        if stable >= 2:
            candidate = pdfs[0]
            break
    time.sleep(0.5)
if candidate is None:
    raise RuntimeError("download did not complete deterministically")
```

Afterward, require a PDF signature, nonzero size, readable extracted text, and
domain-specific validation. Close the statement dialog before opening another
row. If a durable statement id is unavailable, download the candidate and
deduplicate it by SHA-256 instead of guessing from the filename.

## Recovery

- Save the provider key and last completed statement after every download.
- A login wall pauses only the affected provider; do not discard already
  downloaded files.
- Re-read the table after reauthentication because statement availability may
  have changed.
- Reject any remaining `.crdownload` file as an incomplete run.
