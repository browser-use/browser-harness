# YouTube playback and transcript extraction

Use this playbook for public desktop video pages when you need reliable metadata or the visible transcript. YouTube lazy-renders the transcript control, so a newly loaded watch page usually does not expose it until the description is expanded.

## Open and hydrate the watch page

Open a new tab rather than replacing the user's active tab, then give the Polymer app a few seconds to hydrate.

```python
tab = new_tab("https://www.youtube.com/watch?v=<VIDEO_ID>")
wait_for_load(tab)
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
js("""
(() => {
  const expand = [...document.querySelectorAll('tp-yt-paper-button#expand')]
    .find(el => el.getClientRects().length);
  if (!expand) return false;
  expand.click();
  return true;
})()
""", target_id=tab)
wait(1)

js("""
(() => {
  const leaf = [...document.querySelectorAll('body *')]
    .find(el => el.children.length === 0 &&
      el.textContent.trim() === 'Show transcript' &&
      el.getClientRects().length);
  const button = leaf?.closest('button, tp-yt-paper-button');
  if (!button) return false;
  button.click();
  return true;
})()
""", target_id=tab)
wait(2)
```

Avoid coordinate clicks here. The description height and transcript-button position vary with viewport, localization, experiments, and description length.

## Extract the rendered transcript

For the standard English desktop UI, the panel text begins at `Transcript\nSearch transcript`. Reading `innerText` after the panel opens returns the timestamps and caption lines in display order:

```python
transcript = js("""
(() => {
  const text = document.body.innerText;
  const marker = 'Transcript\\nSearch transcript';
  const start = text.indexOf(marker);
  return start >= 0 ? text.slice(start) : null;
})()
""", target_id=tab)
```

Treat auto-generated captions as fallible, especially for names, dates, numbers, and technical terms. Preserve timestamps when a questionable claim needs to be checked against the audio.

## Common failure modes

- `Show transcript` is missing: expand the description first, then wait for the action row to render.
- JavaScript returns metadata from the wrong video: pass the watch tab's `target_id` on every call.
- A hidden duplicate receives the click: require `getClientRects().length` for both the expansion control and transcript text leaf.
- The marker is absent: the UI may be localized, captions may be unavailable, or the panel may still be loading. Inspect the screenshot before changing selectors.
