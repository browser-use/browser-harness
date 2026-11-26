# ChatGPT image generation

Use the user's signed-in browser when the task explicitly asks for ChatGPT image generation there. Open a fresh task-owned chat; do not reuse unrelated conversations. Inspect the page and its available modes before submitting.

## Page controls

- The homepage may open in Work mode. Choose the visible Chat mode when generating images in a conversation.
- The chat composer is a contenteditable `#prompt-textarea`. Focus it, insert text with CDP input, then use the visible send control (`#composer-submit-button` when present).
- The image editor can open as a fullscreen layer with a second composer. Its close control has `aria-label="Close fullscreen view"`. Close that layer before targeting the normal conversation composer.
- The image attachment input can be located by `input[type=file][accept="image/*"]`. Inspect the actual input before using `DOM.setFileInputFiles`; wait until the uploaded reference is visibly attached before sending the edit request.
- Generated result images have descriptive alt text beginning with `Generated image:`. Select the result associated with the completed request, rather than assuming the last image on the whole page is always new.

## Generation and downloading

Request one separate finished asset per turn when every page needs its own file. A request for several individual images can return only one image. For a coherent book or series, keep the same cast/style description in each prompt and review each result before proceeding. Supply exact visible copy when typography must be part of the image.

An image result may exist in the DOM while `naturalWidth` remains zero, especially in a background tab. This alone does not establish that generation is incomplete. Inspect the conversation's generation state and the new image node. Fetching that node's observed `src` within the authenticated page can return a completed image even before the browser paints it. Check the response status and decode the returned blob (for example, with `createImageBitmap`) to verify its dimensions.

Use the image's normal download action, or retrieve the exact URL observed on that authorized result. Do not guess file endpoints. Keep signed URLs, cookies and base64 image bodies out of tool logs; write the returned bytes directly to the task's local asset path. Record the source chat, prompt, dimensions and review status in the project's provenance ledger. Do not claim a particular image-model version unless the interface actually exposes it.

Screenshots and local image inspection remain necessary: successful download does not establish correct text, anatomy, object counts or visual continuity. OCR helps flag missing copy but also produces false negatives for ornamental titles, apostrophes and nearby illustration texture.

## Several owned tabs

When independent agents share one browser daemon, do not call helpers that change its global current session. Create a new target with `Target.createTarget`, attach with `Target.attachToTarget`, then pass that returned `session_id` explicitly on every tab-specific CDP call. Browser-level target creation/attachment can use the browser session. Pin and verify both target and URL before editing; if the user closes a target, re-establish the owned tab deliberately instead of acting on a fallback tab.

The daemon uses one JSON line per request. Large inline data URLs can exceed its incoming line limit. For sizeable reference or audio files, use a file upload or an authorized task-local URL instead of injecting a large base64 literal.

## Corrections within a book conversation

Name the exact earlier surface and folio when correcting it after a later page has generated. Explicitly preserve its copy and layout, and save the correction separately until it has been reviewed. A repeated image description is possible after an edit, so verify the new response position as well as the image's descriptive alt text. Small exact counts (seeds, cherries, buttons) still need visual inspection; a prompt saying "six total" is not a count check.
