# ChatGPT — image generation with reference images

Drive chatgpt.com (logged-in session) to generate images from a prompt plus uploaded reference photos, then save the result. Verified Nov 2026.

## URL patterns

- `https://chatgpt.com/` — fresh chat. Setting `location.href` to it is the reliable "new chat".
- After the first send the URL becomes `https://chatgpt.com/c/<conversation-id>`. Record it; navigating back to that URL reloads the conversation and its generated images.

## Composer

- Message box: `div.ProseMirror` (contenteditable). `#prompt-textarea` did not match.
- Focus it with JS, then `type_text(prompt)` (`Input.insertText`) works and enables Send. Keep the prompt on one line: Enter sends.
- Send: `button[aria-label="Send"]`. `[data-testid=send-button]` did not match. A JS `.click()` on it sends.

## Uploading reference images

- The page has several `input[type=file]`. Use the one with `multiple` and an empty `accept` (the others are image-only or single-file):

```python
js("(()=>{const i=[...document.querySelectorAll('input[type=file]')].find(i=>i.multiple&&!i.accept);i.setAttribute('data-bh','up')})()")
upload_file("[data-bh=up]", ["/abs/a.png", "/abs/b.png", "/abs/c.png"])
```

- Several files in one `setFileInputFiles` call work. Upload confirmation: one `button[aria-label="Remove <filename>"]` per file appears in the composer.
- File names are visible to the model, so name files after what they show ("Dr_Jane_Doe.png") and refer to the names in the prompt.
- Wait a few seconds after upload before sending; Send is present but the attachments need to finish.

## Reading the result

- Generated images: `main img[alt^="Generated image"]`. Uploaded attachments are `img[alt="User attachment"]`, so filter on `alt`, not on size.
- `src` is a `blob:` URL. Fetch it in the page and return base64 to save the full-resolution file:

```python
b64 = js("""(async()=>{const im=[...document.querySelectorAll('main img[alt^="Generated image"]')].at(-1);
  const b=await (await fetch(im.src)).blob();
  return await new Promise(r=>{const f=new FileReader();f.onload=()=>r(f.result.split(',')[1]);f.readAsDataURL(b)})})()""")
```

- A portrait "4:5" request came back as 1122×1402.

## Waits

- Generation takes roughly 1–3 minutes. While it runs the page shows a dotted placeholder with a percentage. `wait_for_load()` says nothing about it; poll for the generated `img`.
- `button[aria-label*=Stop]` was still present in one run after the finished image was already in the DOM, so do not use it alone as the "done" signal. Poll for the image, then look at the saved file.
- Two tabs can generate at the same time, one conversation each.

## Traps

- If the user clicks a different conversation in the tab you are driving, your tab silently changes conversation. Check `location.href` against the conversation URL you recorded before saving an image.
- Faces from reference photos are re-rendered, not pasted. They come back as close likenesses; compare against the originals before using them.
