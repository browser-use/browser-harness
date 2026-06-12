# Kaggle notebook editor (kaggle.com/code)

URL patterns:
- Viewer: `kaggle.com/code/<owner>/<slug>` — 404s over plain HTTP if the notebook is private; even an authenticated in-page `fetch` returns only an ~8 KB SPA shell with no version data. Don't scrape it — use the editor DOM instead.
- Editor: `kaggle.com/code/<owner>/<slug>/edit` — collaborators can edit notebooks owned by another account.

## Replacing a draft with a local .ipynb

File → Import Notebook opens a panel with drag & drop. The reliable file input is `input[data-testid="file-uploader-input"]` (accepts `.ipynb,.py`, `display:none`) — set it with `upload_file(...)`. Beware: the page also has a generic image-upload `input[type=file]`, so prefer the data-testid selector. After the filename chip appears, click the now-enabled Import button. Import replaces the whole draft and strips nothing — upload a cleaned notebook (no outputs) if you want a clean draft.

## Committing a run

"Save Version" button (top right) → dialog with VERSION TYPE "Save & Run All (Commit)" preselected → Save. The version-name text field ignores CDP `Input.insertText` (stays empty); the name is optional, Kaggle auto-names "Version N" — don't fight it. Accelerator/Internet for the committed run come from the right-hand "Session options" panel (GPU choice, Internet toggle, pinned environment); check them before saving.

## Polling run status

The editor page shows an Active Events widget whose text contains `Version #N with GPU T4 x2 | Running: Xm`. Poll `document.body.innerText` for `"Version #N"` + `"Running"`; the entry disappears when the run reaches a terminal state. This survives the user switching tabs (CDP stays attached to the editor target).

## Reading a committed version's outputs

In the editor, the Version History sidebar opens past versions in a "Viewing Version N" mode. The rendered notebook (with cell outputs) lives in an iframe on `kaggleusercontent.com/kf/...` — get it with `iframe_target("kaggleusercontent.com/kf/")` and read `document.body.innerText` from that target. Full metric printouts (e.g. JSON dumps of accuracy) are extractable with regex from that text. DataFrame HTML tables flatten less predictably — prefer values the notebook `print()`s.

## Traps

- The editor opens on whatever mode it was left in (e.g. "Viewing Version N" with history sidebar) — click the top-left back arrow to return to the editable draft before importing.
- Version history "Ran in X minutes" includes queue-free GPU time only; a queued commit shows no duration.
- Committing can fail with `ConcurrencyViolation: Sequence number must match Draft record` ("Failed to save draft" in the title bar) when the draft sequence desyncs — typically after bouncing between version views and imports in one long editor session. The import that preceded the failed commit is **rolled back**. Recover with: `Page.reload` → verify your content is gone (check a new section name in the Table of Contents) → re-import → Save Version again.
- The viewer's default version ("Version N of M") lags behind the latest successful run and can even point at an old version; always select the version explicitly before scraping its output.
- A multi-iteration loop that works: edit the .ipynb locally (json + `ast.parse` each cell), re-import, Save & Run All, poll the Active Events widget, then scrape the new `kf/` iframe (pick the highest numeric kf id across targets — older version views keep their iframes alive in other tabs).
