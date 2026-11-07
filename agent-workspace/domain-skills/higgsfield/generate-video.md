# Higgsfield — generate an image and a Seedance 2.5 video

Higgsfield (`higgsfield.ai`) is a credit-based AI image and video suite. The user's Chrome profile must be logged in. Check for the avatar button at the top-right of the nav; if the nav shows "Log in", stop and ask the user.

## URLs

- Video tool, Seedance 2.5 preselected: `https://higgsfield.ai/ai/video?model=seedance_2_5`
- Image tool, GPT Image 2 preselected: `https://higgsfield.ai/ai/image?model=gpt_image_2`
- Pricing (credit rates): `https://higgsfield.ai/pricing`. `/settings` and `/billing` are 404.
- Profile: `https://higgsfield.ai/@<handle>` (the avatar click goes here; it does not show credits).
- Account pages (direct, logged in): `/me/settings` (credits left, % of pool), `/me/settings/subscription` (plan, credits per month, renewal date, active unlimited models), `/me/settings/usage` (per-generation credit log with timestamps and a dollar total). These are the fastest way to read the balance and to audit what a session cost.

## Credits

- $1 = 20 credits. Seedance 2.5 at 16:9: 30 s costs 480 credits at 1080p and 210 at 720p. 5 s at 1080p costs 80. GPT Image 2 at 2K costs about 6.5 credits per image.
- The balance and plan live in the account menu behind the avatar. A coordinate click on the avatar navigates to `/@handle` instead; click the button by its aria-label and read the popover:

```python
js('[...document.querySelectorAll("button")].find(e=>e.getAttribute("aria-label")==="Account menu").click()')
wait(4)   # the menu says "Loading..." for a few seconds
js('return document.querySelector("[role=menu],[data-radix-popper-content-wrapper]").innerText')
# -> "<handle>\n\nPro Plan\n...\nCredits\n393 left\nTop-up credits\n...\nManage Account\n..."
```

- The Generate button shows the cost of the current settings. A low-balance toast ("You'll run out of credits in N days") appears after Generate; its "Add credits" button opens the top-up modal, which does not show the balance either.
- Hovering the avatar or the gift icon does not work from the daemon: `mouseMoved` times out. Use the aria-label click above.

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
- `type_text()` with `\n` inside the string drops everything after the first newline. Type one line at a time and send `press_key("Enter", modifiers=8)` (Shift+Enter) between lines.
- Focus gets stolen mid-prompt (toasts, the low-credit banner, re-renders). When that happens the rest of the lines vanish silently. Re-focus the editor and move the caret to the end before every line, and verify the length grew:

```python
def ed(): return js('return document.querySelector("[contenteditable=true]").innerText')
def focus_end():
    js('''(()=>{const e=document.querySelector("[contenteditable=true]"); e.focus();
      const r=document.createRange(); r.selectNodeContents(e); r.collapse(false);
      const s=window.getSelection(); s.removeAllRanges(); s.addRange(r);})()''')
def typed(line):
    for _ in range(3):
        n=len(ed()); focus_end(); type_text(line); wait(0.25)
        if len(ed())>n: return True
for para in prompt.split("\n\n"):
    for i,line in enumerate(para.split("\n")):
        if i: focus_end(); press_key("Enter", modifiers=8)
        typed(line)
    focus_end(); press_key("Enter", modifiers=8); press_key("Enter", modifiers=8)
```

- Do not trust a coordinate click on the editor's bounding-box center: the left panel scrolls, so the box can extend above the viewport and the click lands on another control. Use `focus_end()` instead.
- References get an `@` mention. Type `@`, wait ~1.5 s for the "Image 1" popup, then `press_key("Enter")`. Clicking the popup row does not insert the chip; Enter does. Check with `js('return document.querySelector("[contenteditable=true]").innerText')` for "@Image 1".
- `press_key("a", modifiers=4)` then Backspace clears the editor.
- The editor grows with the text and pushes the controls below it down. Re-screenshot or locate buttons by text before you click Duration / Quality / Generate.

### Settings

- Duration is a Radix slider popover (`[role=slider][aria-valuemax="30"]`, min 4, step 1). Click the Duration box, click the track at `x + (target-4)/26 * width`, then nudge with ArrowLeft/ArrowRight until `aria-valuenow` reads the target. 4, 10, 15, 20, 30 are only tick labels; any integer works.
- Cost at 16:9: 10 s 480p = 30 credits, 30 s 720p = 210, 30 s 1080p = 480, 5 s 1080p = 80.
- Pro allows parallel videos (up to 3). Clicking Generate while another card says "Generating" queues a second card; the editor and settings stay as they were, so you can change the prompt and fire again at once.
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

## Genjutsu (motion transfer from a reference video)

URL: `https://higgsfield.ai/ai/video?model=genjutsu`. Tabs in the left panel: Motion transfer / Objects swap, an optional Style, a reference-video box (4 to 30 s), a character-images box (up to 30), a Prompt toggle, Model, Quality (720p), a "Use free generations" toggle, Generate.

- Cost shows only after a reference video is attached: a 19 s 9:16 clip at 720p read "Generate 133". Pro includes a few free Genjutsu runs ("1 left"); with the free toggle on the button reads "Generate 133 Free" and no credits are charged.
- Reference video: click the "Add a reference video" box, `upload_file("input[type=file]", path)` (the input accepts video only and exists only while the picker is open). Confirm in the "Edit reference" crop/trim dialog (button text "Confirm"). The video is NOT attached until you click its tile in the Uploads grid afterwards, then Confirm again. Check the box text no longer starts with "Add a reference video".
- Character image: click the "Add your characters" box. Its picker has Uploads / Generations / Liked tabs. Earlier uploads (the character sheet) are there; click the tile. A green check marks it; the thumbnail appears in the box.
- The Prompt editor only exists while the Prompt switch (`[role=switch]` next to the text "Prompt") reads `aria-checked="true"`. With the switch off, the `[contenteditable]` still reports a size but the Model button sits on top of it, so clicks and keystrokes go to the Model search box instead and open a "No models found" popup. Check `document.elementFromPoint` hits the editor before typing.
- The `@` popup lists `Video 1` before `Image 1`. Enter takes the first row, so plain Enter inserts `@Video 1`. Use ArrowDown before Enter, or just write "the attached character image"; the attached image is used either way.
- A 19 s motion transfer at 720p took about N minutes (see History). The result mp4 is on the same cloudfront host as other generations.

## Motion Control (Kling 3.0)

URL: `https://higgsfield.ai/ai/video/motion?model=kling-3-motion-control`. Motion video (3 to 30 s) + a character image with a visible face and body. "Scene control mode" picks whether the background comes from the image or the video. The Generate button read "7" with nothing attached; expect it to scale with duration. The model list also offers Seedance 2.5, Genjutsu, Kling 4.0 and Kling 4.0 Flash for motion control.

## Traps

- Promo popups ("Unlimited Seedance 2.5", "Don't know where to start?") overlay the page. Close them with their X before you click near the bottom-right or top-center.
- The Seedance landing on `/ai/video` shows a big "Make videos in one click" panel on the right. It is only a tutorial; all controls are in the left panel.
