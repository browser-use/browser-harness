# X (Twitter) — read a post, its thread, and its video without logging in

## What works logged out

- A single post URL `https://x.com/<user>/status/<id>` renders the post, the author's own thread replies, and quoted posts. No login needed.
- Profile timelines, search, and "Show more replies" from other users need a login. Stop and ask the user if you hit the login wall for those.
- The daemon attaches to whatever Chrome profile is running. That profile may be logged out of X even if the user is logged in elsewhere. Check with:

```python
js('return !!document.querySelector(\'[data-testid="SideNav_AccountSwitcher_Button"]\')')  # True = logged in
```

## Reading post text

- Each post is an `<article>`. `article.innerText` gives author, handle, date, text, and counts in one blob. Fast and reliable.
- `[data-testid="tweetText"]` exists but can return empty on the logged-out page. Use `article.innerText` instead.
- Long posts are truncated with a "Show more" link. Open the post's own status URL, then click `[data-testid="tweet-text-show-more-link"]` and re-read. The full text (thousands of chars, with newlines) is then in `innerText`.
- The status link of each article: `article.querySelector('a[href*="/status/"]').getAttribute("href")`.

```python
goto_url("https://x.com/<user>/status/<id>"); wait_for_load(); wait(3)
js('[...document.querySelectorAll(\'[data-testid="tweet-text-show-more-link"]\')].forEach(x=>x.click())')
wait(2)
posts = js('''return [...document.querySelectorAll("article")].map(a=>({
  url: a.querySelector('a[href*="/status/"]')?.getAttribute("href"), txt: a.innerText}))''')
```

## Loading a thread

- The thread below a post lazy-loads. Scroll the page (`scroll(700, 600, dy=1500)` a few times with `wait(1.2)`) before you collect articles.
- Author replies appear in order below the root post. Other people's replies come after.

## Grabbing frames from a post video

- The `<video>` src is a `blob:` URL. You cannot `http_get` it. The poster image is on `pbs.twimg.com/amplify_video_thumb/...`.
- Seeking the paused `<video>` with JS does nothing until it has played once. Click the center of the player (`click_at_xy`) to start playback, then seek:

```python
click_at_xy(x, y)   # center of the player, from a screenshot
wait(2)
for t in [1, 4, 7, 11, 16, 22, 28]:
    js(f'(()=>{{const v=document.querySelector("video"); v.currentTime={t}; v.play();}})()')
    wait(0.8)
    js('(()=>{const v=document.querySelector("video"); v.pause();})()')
    wait(0.6)
    capture_screenshot(f"/tmp/frame_{t}.png")
```

- Wrap `const v=...` in an IIFE as above. A bare `const` at top level fails on the second `js()` call with "Identifier 'v' has already been declared".
- Crop the screenshots to the player rect (`video.getBoundingClientRect()`) and tile them with PIL to review the whole clip in one image.

## Traps

- The daemon's `cdp("Input.dispatchMouseEvent", type="mouseMoved", ...)` can time out on x.com. Clicks and scrolls work. Do not hover; click or read the DOM.
- The clipboard (`pbpaste`) often holds the link the user means by "this post". Check it before you ask.
