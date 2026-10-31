# YouTube Studio: checks and a Short's related video

Observed in the English Studio interface, October 2026.

## Routes and visible status

- Open the exact video with `https://studio.youtube.com/video/{VIDEO_ID}/edit`.
- The Details page has a right column containing Notices, Visibility, and Related
  video. These cards may be below the initial viewport. Scroll the main content
  and inspect a screenshot before clicking.
- A Notices value of `Checking...` is pending. Clicking it opens a popover with
  `Checks are still running on this video` and
  `Results should be ready soon. Any notices will be shown here as soon as they are found.`
- The Claims navigation item opens a separate claim overview. A clean copyright
  result can read `No claims were found in this video` and
  `No copyrighted content was found in your video.` This does not establish that
  the other checks are finished: Notices can still say `Checking...`.
- After refreshing Details, allow the Polymer interface to hydrate after
  `wait_for_load()`, then inspect the screenshot and status again.

## Verify the related video ID without changing the selection

The visible card presents a title, not the ID. Studio's rendered
`ytcp-shorts-content-links-picker` exposes useful read-only properties:

```python
print(js("""(() => {
  const picker = document.querySelector('ytcp-shorts-content-links-picker');
  return picker ? {
    id: picker.linkedVideoId,
    title: picker.linkedVideoInputText,
    fetched: picker.fetchedLinkedVideo
  } : null;
})()"""))
```

`fetchedLinkedVideo` can contain a `status` of `SUCCESS` and a `data` object with
`videoId`, `title`, `privacy`, and processing `status`. Treat these as internal
read-only properties that can change with Studio releases. Confirm the visible
card too.

Clicking the Related video card opens the `Choose specific video` dialog. Its
`ytcp-entity-card` items contain a thumbnail background URL of the form
`https://i9.ytimg.com/vi/{VIDEO_ID}/...`, which can also disambiguate titles.
Close the dialog if no edit is needed.

The editor setting alone does not prove that the related link appears on the
public Shorts player. Verify that separately on
`https://www.youtube.com/shorts/{VIDEO_ID}` after publication.
