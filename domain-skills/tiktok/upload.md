# TikTok Studio — Upload Video

URL: `https://www.tiktok.com/tiktokstudio/upload?from=upload&lang=en` (always append `&lang=en`)

## Prerequisites

- Logged into TikTok in the Chrome profile browser-harness is attached to
- Video file on local disk (mp4, <50MB)

## Stale draft banner

TikTok shows "A video you were editing wasn't saved" if a previous upload was abandoned. Dismiss it:

1. Find the banner Discard button (y < 300 in the page)
2. CDP `click_at_xy(x, y)` on it
3. A confirmation modal appears — find the red Discard button (y > 300) and CDP `click_at_xy(x, y)`
4. Repeat if multiple stale drafts are stacked

## Upload flow

### 1. Attach file

```python
upload_file('input[type="file"]', "/path/to/video.mp4")
wait(12)  # processing takes ~10s for 5-10MB
```

### 2. Caption

TikTok pre-fills caption with the filename. Clear it first:

```python
js("document.querySelector('div[contenteditable=\"true\"][role=\"combobox\"]').focus()")
press_key("End")
for _ in range(25): press_key("Backspace")  # clear filename
type_text("your caption here #hashtag1 #hashtag2")
press_key("Escape")  # dismiss hashtag suggestions
click_at_xy(700, 50)        # click away to deselect
```

Verify: `js('document.querySelector(\'div[contenteditable="true"][role="combobox"]\').innerText')`

### 3. Schedule

Click the Schedule radio label:
```python
js("(()=>{var l=document.querySelectorAll('label');for(var i=0;i<l.length;i++){if(l[i].textContent.trim()==='Schedule'){l[i].click();break}}})()")
```

**Time picker** — uses a scroll-wheel list, NOT a native select. Each `scroll(dy=32)` steps +1 unit, `dy=-32` steps -1 unit.

```python
# 1. ScrollIntoView and open the time picker
js("...scrollIntoView the time input...")
click_at_xy(time_input_x, time_input_y)

# 2. Read default time, calculate difference
default_hour, default_min = 13, 5  # from input value
target_hour, target_min = 20, 25

# 3. Scroll hour column (left, x ≈ 349)
for _ in range(target_hour - default_hour):
    scroll(349, dropdown_y, dy=32)  # +1 hour per step

# 4. Scroll minute column (right, x ≈ 437)
for _ in range((target_min - default_min) // 5):
    scroll(437, dropdown_y, dy=32)  # +5 min per step

# 5. Close and verify
press_key("Escape")
```

**Date picker** — click the date input, then click the target day number span.

### 4. AI-generated content disclosure

Under "Show more" section. Toggle is `[aria-checked]` inside the "AI-generated content" parent.

```python
# Expand settings
js("...click 'Show more' span...")
# ScrollIntoView the toggle
js("...scrollIntoView 'ai-generated content' span...")
# Read state and click if false
# A "Turn on" confirmation dialog may appear — click it
```

### 5. Submit

Scroll the Schedule button into view, then CDP `click_at_xy(x, y)`. After success, page redirects to `/tiktokstudio/content`.

```python
js("...scrollIntoView Schedule button (offsetWidth > 100)...")
click_at_xy(button_x, button_y)
wait(6)
assert "content" in page_info()["url"]
```

## Gotchas

- **JS `.click()` doesn't work on TikTok's time picker items** — must use CDP `click_at_xy(x, y)`
- **Time picker uses virtual scroll** — `scroll(x, y, dy=32)` changes value, NOT regular DOM scroll
- **Caption contenteditable appends on type** — always clear with End + Backspace first, never set innerHTML (breaks React state)
- **beforeunload dialog** blocks navigation if upload is in progress — use `cdp("Page.handleJavaScriptDialog", accept=True)` to dismiss (see `interaction-skills/dialogs.md`)
- **Schedule button text** is "Schedule" only after the Schedule radio is selected (otherwise "Post")
- **"Show more" section** expands the page and pushes the time picker off-viewport — collapse it before adjusting time, expand after
- **Unicode narrow no-break space** (char 8239) appears between time and AM/PM in scheduled post listings — use `.indexOf('12:30')` not exact string match
