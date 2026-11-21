# X (x.com) — read a post and download its video

## URL pattern

- A post lives at `https://x.com/<handle>/status/<id>`.
- A logged-in Chrome session shows the post. A logged-out session often shows a login wall.

## Selectors

- The first `article` element is the main post. `article.innerText` gives the text, the time, and the counts.
- `article video` is the player. Its `src` is a `blob:` URL, so you cannot download it directly.
- `video.poster` points to a thumbnail on `pbs.twimg.com/amplify_video_thumb/...`.

## Find the real video URL

The player loads HLS playlists from `video.twimg.com`. Read them from the resource timing list after the player starts:

```python
js("""JSON.stringify(performance.getEntriesByType('resource')
  .map(e => e.name).filter(n => n.includes('video.twimg')))""")
```

- `.../pl/<name>.m3u8?tag=..` is the master playlist.
- `.../pl/avc1/<W>x<H>/<name>.m3u8` is one playlist for each resolution. Use the largest one.
- The playlists need no cookies. `ffmpeg` downloads them directly:

```bash
ffmpeg -i "https://video.twimg.com/amplify_video/<id>/pl/avc1/1920x1080/<name>.m3u8" -c copy out.mp4
```

## Traps

- Wait about 4 seconds after `wait_for_load()`. The player adds the playlist entries after the page load event.
- The video stream and the audio stream have separate playlists. A resolution playlist can contain video only.
- To study a video, build a contact sheet: `ffmpeg -i out.mp4 -vf "fps=2,scale=640:-1,tile=4x5" -frames:v 1 sheet.png`. Without `-frames:v 1`, `ffmpeg` fails when the frames fill more than one sheet.
