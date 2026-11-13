# YouTube playback and transcript extraction

Use this playbook for public desktop video pages when you need reliable metadata or the visible transcript. YouTube lazy-renders the transcript control, so a newly loaded watch page usually does not expose it until the description is expanded.

## Open and hydrate the watch page

Open a new tab rather than replacing the user's active tab, then give the Polymer app a few seconds to hydrate.

```python
tab = new_tab("https://www.youtube.com/watch?v=<VIDEO_ID>")
wait_for_load()
wait(4)
```

Keep using `target_id=tab` for later calls. YouTube pages can create or reuse additional targets, and target-free JavaScript may otherwise run in a different watch tab.

## Read stable metadata

The hydrated player response is more stable than scraping rendered title and channel elements:

```python
metadata = js("""
(() => {
  const response = window.ytInitialPlayerResponse;
  if (!response) return null;
  const details = response.videoDetails || {};
  const microformat = response.microformat?.playerMicroformatRenderer || {};
  return {
    id: details.videoId,
    title: details.title,
    author: details.author,
    duration_seconds: Number(details.lengthSeconds || 0),
    views: Number(details.viewCount || 0),
    publish_date: microformat.publishDate || null,
    description: details.shortDescription || "",
    caption_tracks:
      response.captions?.playerCaptionsTracklistRenderer?.captionTracks || []
  };
})()
""", target_id=tab)
```

If the response is briefly absent, wait for hydration and retry before falling back to DOM scraping.

## Open the transcript panel

1. Expand the description using the visible `#expand` control. YouTube may keep hidden duplicates in the DOM, so filter by rendered geometry.
2. After expansion, find a leaf whose trimmed text is exactly `Show transcript`; click its closest semantic button.
3. Wait for the side panel to render.

```python
expanded = js("""
(() => {
  const transcriptButton = [...document.querySelectorAll('button, tp-yt-paper-button')]
    .find(el => el.getClientRects().length && el.innerText.trim() === 'Show transcript');
  if (transcriptButton) return true;
  const expand = [...document.querySelectorAll('tp-yt-paper-button#expand')]
    .find(el => el.getClientRects().length);
  if (!expand) return false;
  expand.click();
  return true;
})()
""", target_id=tab)
if not expanded:
    raise RuntimeError("Inspect the description before opening its transcript")
wait(1)

opened = js("""
(() => {
  const leaf = [...document.querySelectorAll('body *')]
    .find(el => el.children.length === 0 &&
      (el.innerText || '').trim() === 'Show transcript' &&
      el.getClientRects().length);
  const button = leaf?.closest('button, tp-yt-paper-button');
  if (!button) return false;
  button.click();
  return true;
})()
""", target_id=tab)
if not opened:
    raise RuntimeError("The transcript control is absent; inspect the page before retrying")
wait(2)
```

Avoid coordinate clicks here. The description height and transcript-button position vary with viewport, localization, experiments, and description length.

## Extract the rendered transcript

Read only the visible transcript panel. Keep its timestamps and caption lines in display order:

```python
transcript = js("""
(() => {
  const panel = [...document.querySelectorAll('ytd-transcript-renderer')]
    .find(el => el.getClientRects().length);
  return panel ? panel.innerText : null;
})()
""", target_id=tab)
```

If `transcript` is empty, inspect the panel and retry before reporting a transcript.

Treat auto-generated captions as fallible, especially for names, dates, numbers, and technical terms. Preserve timestamps when a questionable claim needs to be checked against the audio.

## Read on-screen content from video frames

Use this when the needed text is shown in the video itself (slides, code, a prompt on screen) and is absent from the description and transcript.

A tab opened with `new_tab()` stays in the background. In a background tab `document.visibilityState` is `hidden`, the player does not decode frames (`video.videoWidth` stays `0`, `readyState` stays `0`), and a screenshot shows only the poster thumbnail. Captions and the progress bar still advance, so the page looks alive. Make the tab visible before reading frames:

```python
switch_tab(tab, activate=True)
```

Then seek with the `<video>` element and screenshot each position. Pause first, and wait about 2.5 seconds after each seek so the frame is decoded at full quality.

```python
js("""(() => {
  const v = document.querySelector("video");
  v.muted = true;
  // Captions cover on-screen text; turn them off.
  const cc = document.querySelector(".ytp-subtitles-button");
  if (cc && cc.getAttribute("aria-pressed") === "true") cc.click();
  // Theater mode makes the frame larger in the screenshot.
  document.querySelector(".ytp-size-button")?.click();
})()""", target_id=tab)

for seconds in (186, 192, 198):
    js(f"""(() => {{ const v = document.querySelector("video"); v.pause(); v.currentTime = {seconds}; }})()""", target_id=tab)
    wait(2.5)
    capture_screenshot(f"/tmp/frame-{seconds}.png")
```

- Use the chapter list in `videoDetails.shortDescription` to pick the seek range.
- A pre-roll advertisement can play first. While `.ad-showing` exists on the player, `video.duration` is `NaN` and seeks go to the advertisement. Poll until `.ad-showing` is gone, and click `.ytp-skip-ad-button` when it is present.
- `&t=185s` in the URL sets the start position, but it does not make a background tab decode frames.

## Common failure modes

- `Show transcript` is missing: expand the description first, then wait for the action row to render.
- JavaScript returns metadata from the wrong video: pass the watch tab's `target_id` on every call.
- A hidden duplicate receives the click: require `getClientRects().length` for both the expansion control and transcript text leaf.
- The transcript panel is absent: the UI may be localized, captions may be unavailable, or the panel may still be loading. Inspect the screenshot before changing selectors.
- A screenshot shows only the thumbnail and `video.videoWidth` is `0`: the tab is in the background. Activate it before reading frames.
