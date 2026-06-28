# youtube/upload — publish a video to YouTube via Studio (battle-tested 2026-06-28)

Driving `studio.youtube.com` with browser-harness against the user's logged-in Chrome. This is the durable map of the upload flow — follow it and the first try works. The whole flow is ~5 steps but several controls resist JS selectors and need **coordinate clicks** (noted below).

## Pre-flight
- User must be logged into the target channel in Chrome. Confirm: `page_info()` on `studio.youtube.com` returns `.../channel/<CHANNEL_ID>` and title contains "YouTube Studio".
- **Check for an existing video first.** The channel dashboard "Latest video performance" card shows the most recent upload — don't create a duplicate. To reuse an existing video's URL instead of uploading: go to `.../videos/upload`, scrape `a[href*="/video/"]` → `/video/(<id>)/` and build `https://youtu.be/<id>`.
- Have the absolute path to the local `.mp4` ready.

## The flow

### 1. Open the upload dialog
- Click **Create** (top-right): match `aria-label === "Create"` (an `<button>`/`ytcp-button`). Get rect, `click(cx,cy)`.
- Menu appears with: Create post / **Upload videos** / Go live. Click the element whose trimmed innerText is exactly `Upload videos` (`children.length<=1`, width>0).

### 2. Set the file (this triggers the upload immediately)
- After the dialog opens, find file inputs via CDP and set the **last** one:
  ```python
  doc=cdp("DOM.getDocument", depth=-1, pierce=True)
  nodes=cdp("DOM.querySelectorAll", nodeId=doc["root"]["nodeId"], selector='input[type=file]')["nodeIds"]
  cdp("DOM.setFileInputFiles", files=[ABS_MP4_PATH], nodeId=nodes[-1])
  ```
- Wait ~8s. The dialog shows "Upload complete … Processing will begin shortly". The **public URL is available immediately** in the "Video link" anchor: scrape `a[href*="youtu.be"]` → e.g. `https://youtu.be/qm3aVsWDARY`. Capture it now.

### 3. Details — title + description
- Title and description are **contenteditable `#textbox` divs** (NOT inputs). There are two large ones; sort by `y`: first = Title (pre-filled from filename), second = Description.
- Replace the title: `click()` it → `document.execCommand('selectAll',false,null)` → `cdp("Input.insertText", text=TITLE)`.
- Description: `click()` it → `cdp("Input.insertText", text=DESC)`.
- **Trap:** external links in the description are NOT clickable until the channel completes a one-off verification ("To make external links clickable, first complete a one-off verification"). The link text still shows; fine for a backlink mention.

### 4. Audience — "Made for Kids" (REQUIRED, or Next is blocked)
- Radios are `tp-yt-paper-radio-button`. The "no" option's text is literally **`No, it's not 'Made for Kids'`** (curly quotes around Made for Kids — do NOT match `/not made for kids/`; match `/no,/i` AND `/made for kids/i`).
- `scrollIntoView({block:'center'})` then `click` its left edge (`rect.x+18, rect.y+height/2`). Verify `aria-checked === "true"`.

### 5. Advance + Visibility + Publish
- Click **Next** (trimmed innerText `Next`, width>0) **3×** with ~3s waits: Details → Video elements → Checks → Visibility. Confirm you're on Visibility (`document.body.innerText` contains "Save or publish").
- **Visibility radios resist JS selectors — use COORDINATE clicks.** The three options stack: Private, Unlisted, **Public** (3rd). Selecting any visibility enables the bottom-right button and relabels it `Save`→`Publish`.
  - If a JS query for the radio returns null, click by coordinate. (See coordinate-conversion note below.)
  - Verify selection worked by checking that a `Publish`/`Save` button with `aria-disabled!=="true"` now exists near the bottom (`rect.y>700`).
- Click **Publish**. Success = a **"Video published"** dialog appears with the share link (`youtu.be/<id>`) + Promote button.

## Gotchas (field-tested)
- **Visibility radios: coordinate clicks only.** `[role=radio]`/`tp-yt-paper-radio-button` text matches fail because the label/description live in sibling nodes. Locate the Public row from a screenshot and click it.
- **Coordinate conversion:** screenshots come back at 2× retina (e.g. 3840 wide shown at 2000). For `click(x,y)` (CSS px on a ~1920 viewport): `css = displayed_screenshot_coord × 0.96`.
- **Clicking Publish/Save with no visibility chosen is safely blocked** — a "You need to choose a visibility setting" tooltip shows and the Visibility step turns red; nothing publishes. So a mis-fire here is harmless; just select Public and retry.
- **Auto-save:** the dialog header reads "Saved as private" / "Saving…" throughout — the video exists as private from the moment of upload; publishing flips it to the chosen visibility.
- **Don't re-upload an existing video** — check the dashboard card first.

## Content best-practices (for the human filling fields)
- **Title** ≤100 chars, keyword-first. **Description**: 1–2 line hook + links (with timestamps if long). **Tags** in Show More. **Custom thumbnail** beats auto-generated for CTR. Add **end screens / cards** in the "Video elements" step if you skipped it.
- For embedding in an article (HackerNoon, etc.): paste the `youtu.be/<id>` URL on its own line — most editors auto-embed the player. Public or Unlisted both embed.
