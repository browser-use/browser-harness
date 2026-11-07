# Higgsfield — generate an image and a Seedance 2.5 video

Higgsfield (`higgsfield.ai`) is a credit-based AI image and video suite. The user's Chrome profile must be logged in. Check for the avatar button at the top-right of the nav; if the nav shows "Log in", stop and ask the user.

## URLs

- Video tool, Seedance 2.5 preselected: `https://higgsfield.ai/ai/video?model=seedance_2_5`
- Image tool, GPT Image 2 preselected: `https://higgsfield.ai/ai/image?model=gpt_image_2`
- Pricing (credit rates): `https://higgsfield.ai/pricing`. `/settings` and `/billing` are 404.
- Profile: `https://higgsfield.ai/@<handle>` (the avatar click goes here; it does not show credits).

## Credits

- $1 = 20 credits. Seedance 2.5 at 16:9: 30 s costs 480 credits at 1080p and 210 at 720p. 5 s at 1080p costs 80. GPT Image 2 at 2K costs about 6.5 credits per image.
- The credit balance is not printed anywhere on the public pages. The Generate button shows the cost of the current settings. A low-balance toast ("You'll run out of credits in N days") appears after Generate.
- Hovering the avatar or the gift icon to find the balance does not work from the daemon: `mouseMoved` times out. Skip it.

## Image tool (character sheets)

- The prompt box is a plain `textarea` at the bottom. Click it, then `type_text(prompt)`.
- Chips below the box: model, aspect ratio ("Auto" by default), quality, resolution, image count, "Unlimited" toggle. Click a chip to open a list; the aspect list offers 1:1, 3:2, 2:3, 16:9, 9:16, 4:3, 3:4, 21:9.
- Click GENERATE. The page does not navigate. Poll `document.body.innerText` for "Generating" to disappear (about 50 s).
- The result `<img>` goes through `images.higgs.ai/?...&url=<encoded cloudfront url>`. Decode the `url` param to get the original PNG on `d8j0ntlcm91z4.cloudfront.net/user_<id>/hf_<timestamp>_<uuid>.png`. `curl` downloads it without auth.

## Video tool (Seedance 2.5)

Left panel, top to bottom: preset card, References / Extend Video tabs, references drop zone, Prompt editor, Model, Duration, Aspect Ratio, Quality, Bitrate, Unlimited mode, Generate.

### References (image, video, audio)

1. Click the person icon in the "Add references" box. A picker opens with tabs: Uploads, AI Influencer, Elements, Image Generations, Videos.
2. A hidden `input[type=file]` (multiple; images, video, audio) exists only while the picker is open. Use `upload_file("input[type=file]", "/abs/path.png")`.
3. The first upload opens a "Media upload agreement" modal with two checkboxes and "I agree, continue". Tick both checkboxes, then click the button. The modal does not return on later uploads in the same session.
4. The tile appears in the Uploads grid after "Uploading..." clears (a few seconds). Click the tile to attach it. The thumbnail then shows in the references box. Close the picker with the X at its top-right.
5. "Image Generations" tab lists images made in the Image tool, so a character sheet generated on the site can be attached without an upload.

### Prompt editor is a rich-text mention editor, not a textarea

- The box is `div[contenteditable=true]` (ProseMirror-style). `document.querySelector("textarea")` is null.
- `type_text()` with `\n` inside the string drops everything after the first newline. Type one line at a time and send `press_key("Enter", modifiers=8)` (Shift+Enter) between lines. Plain Enter also works for a new paragraph but Shift+Enter is safer. The full prompt (4,000+ chars) arrives intact this way.
- References get an `@` mention. Type `@`, wait ~1.5 s for the "Image 1" popup, then `press_key("Enter")`. Clicking the popup row does not insert the chip; Enter does. Check with `js('return document.querySelector("[contenteditable=true]").innerText')` for "@Image 1".
- `press_key("a", modifiers=4)` then Backspace clears the editor.
- The editor grows with the text and pushes the controls below it down. Re-screenshot or locate buttons by text before you click Duration / Quality / Generate.

### Settings

- Duration is a slider popover (4, 10, 15, 20, 30). Click the far-right end of the track for 30 s.
- Quality is a list: 480p, 720p, 1080p. Locate the row by text:

```python
r = js('''const e=[...document.querySelectorAll("div,button,span")].filter(e=>e.innerText&&e.innerText.trim()==="720p").pop();
const b=e.getBoundingClientRect(); return {x:b.x+b.width/2,y:b.y+b.height/2};''')
click_at_xy(r["x"], r["y"])
```

- Settings persist across page reloads in the same session (duration stayed at 30 s after navigating away).
- Generate button: find by `/^Generate/.test(button.innerText)`; its text carries the credit cost, e.g. "Generate\n210".

### Waiting for the result

- After Generate, a "History" card shows a "Generating" chip and the right rail shows the prompt, quality, duration, ratio and seed. A 30 s Seedance 2.5 720p render took about 4.5 minutes.
- Poll `<video>` elements and ignore `static.higgsfield.ai/...banner...mp4` (the preset card's looping banner). The result src is `https://d8j0ntlcm91z4.cloudfront.net/user_<id>/hf_<timestamp>_<uuid>.mp4`.

```python
st = js('''const t=document.body.innerText;
const vids=[...document.querySelectorAll("video")].map(v=>v.src||v.currentSrc).filter(s=>s && !/static\\.higgsfield\\.ai/.test(s));
return {generating:/Generating/.test(t), vids};''')
```

- `curl -L` the mp4 directly; no cookies needed. 30 s 720p is about 42 MB with audio.

## Traps

- Promo popups ("Unlimited Seedance 2.5", "Don't know where to start?") overlay the page. Close them with their X before you click near the bottom-right or top-center.
- The Seedance landing on `/ai/video` shows a big "Make videos in one click" panel on the right. It is only a tutorial; all controls are in the left panel.
