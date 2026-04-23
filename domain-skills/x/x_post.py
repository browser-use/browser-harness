#!/usr/bin/env python3
"""
X Post with Image(s) or Video(s) — browser-harness domain skill

Usage as script:
    uv run python3 x_post.py "text here" /path/to/media.png
    uv run python3 x_post.py "text here" /path/to/img1.png /path/to/img2.png
    uv run python3 x_post.py "text here" /path/to/video.mp4
    uv run python3 x_post.py "text here" img:/path/to/img.png vid:/path/to/video.mp4

Usage as module:
    from x_post import post_to_x

    # Single image
    result = post_to_x(text="...", media=[{"path": "/path/to/img.png", "type": "image"}])

    # Multiple images
    result = post_to_x(text="...", media=[
        {"path": "/path/to/img1.png", "type": "image"},
        {"path": "/path/to/img2.jpg", "type": "image"},
    ])

    # Mix of images and video
    result = post_to_x(text="...", media=[
        {"path": "/path/to/img.png", "type": "image"},
        {"path": "/path/to/video.mp4", "type": "video"},
    ])
"""
import sys, subprocess, os, tempfile, atexit
from pathlib import Path

SKILL_DIR = Path(__file__).parent
sys.path.insert(0, str(SKILL_DIR.parent.parent))
from helpers import *
from admin import ensure_daemon

# Temp video files created by _ensure_h264 that need cleanup after the post
_TEMP_FILES = []


def _cleanup_temp_files():
    for f in _TEMP_FILES:
        try:
            os.unlink(f)
        except Exception:
            pass
    _TEMP_FILES.clear()


atexit.register(_cleanup_temp_files)


def _is_video(path):
    """Check if a file is a video based on extension."""
    video_exts = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v", ".flv", ".wmv"}
    return Path(path).suffix.lower() in video_exts


def _ensure_h264(path):
    """
    Check if a video file is H.264. If not, convert to H.264 using ffmpeg.
    Returns the path to use (original if already H.264, or a temp converted file).
    Skips non-video files and returns them unchanged.
    """
    if not _is_video(path):
        return path

    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_streams", path],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.splitlines():
            if line.startswith("codec_name="):
                if line.split("=", 1)[1] == "h264":
                    return path
                break
    except Exception:
        pass

    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    out_path = tmp.name
    try:
        subprocess.run(
            ["ffmpeg", "-i", path, "-c:v", "libx264", "-c:a", "aac",
             "-movflags", "+faststart", out_path, "-y"],
            check=True, capture_output=True, timeout=300
        )
        _TEMP_FILES.append(out_path)
        return out_path
    except Exception:
        try:
            os.unlink(out_path)
        except Exception:
            pass
        return path


def _parse_media_arg(arg):
    """
    Parse a media argument that may be:
      - a bare path (auto-detected as image or video by extension)
      - "img:/path/to/file.png"  (explicit image)
      - "vid:/path/to/file.mp4"  (explicit video)
    Returns {"path": str, "type": "image"|"video"}
    """
    if arg.startswith("img:") or arg.startswith("vid:"):
        prefix, rest = arg.split(":", 1)
        media_type = "image" if prefix == "img" else "video"
        return {"path": rest, "type": media_type}

    # Auto-detect by extension
    if _is_video(arg):
        return {"path": arg, "type": "video"}
    return {"path": arg, "type": "image"}


def post_to_x(text, media, screenshot_dir=None):
    """
    Post text with image(s) and/or video(s) to X.com.

    Args:
        text:          post body text (with or without hashtags)
        media:         a single path str, or a list of dicts [{"path": str, "type": "image"|"video"}].
                       Type is auto-detected from extension if not specified.
        screenshot_dir: absolute path for verification screenshot (optional)

    Returns:
        {"success": bool, "post_in_feed": bool, "url": str}
    """
    ensure_daemon(wait=60)
    ensure_real_tab()

    try:
        cdp("Page.handleJavaScriptDialog", accept=True)
    except Exception:
        pass

    # Normalize media to list of dicts
    if isinstance(media, str):
        media = [_parse_media_arg(media)]
    else:
        media = [_parse_media_arg(m) if isinstance(m, str) else m for m in media]

    # Separate images and videos
    images = [m["path"] for m in media if m["type"] == "image"]
    videos = [m["path"] for m in media if m["type"] == "video"]

    # Pre-convert videos to H.264 if needed
    videos = [_ensure_h264(v) for v in videos]

    goto("https://x.com/home")
    wait_for_load()

    compose = js("""
        (() => {
            const el = document.querySelector('[data-testid="tweetTextarea_0_label"]');
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return { x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2) };
        })()
    """)
    if not compose:
        return {"success": False, "post_in_feed": False, "error": "compose textarea not found"}

    click(compose["x"], compose["y"])
    wait(0.3)
    type_text(text)
    wait(0.2)

    # Upload images first, then videos
    all_media = images + videos
    for m in all_media:
        upload_file('[data-testid="fileInput"]', m)
        wait(0.5)

    wait(3.0)

    for _ in range(60):
        wait(0.2)
        btn = js("""
            (() => {
                const el = document.querySelector('[data-testid="tweetButtonInline"]');
                if (!el) return null;
                return el.getAttribute('aria-disabled') !== 'true';
            })()
        """)
        if btn:
            break
    else:
        return {"success": False, "post_in_feed": False, "error": "Post button never enabled"}

    js("""(() => { const btn = document.querySelector('[data-testid="tweetButtonInline"]'); if (btn) btn.click(); })()""")

    wait(5)

    if screenshot_dir:
        Path(screenshot_dir).mkdir(parents=True, exist_ok=True)
        screenshot(f"{screenshot_dir}/x_post_result.png")

    posted = js("""
        (() => {
            const posts = document.querySelectorAll('[data-testid="tweet"]');
            for (const p of posts) {
                if (p.textContent.includes(%s)) return true;
            }
            return false;
        })()
    """ % json.dumps(text[:40]))

    _cleanup_temp_files()

    return {
        "success": True,
        "post_in_feed": bool(posted),
        "url": page_info().get("url", ""),
    }


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: uv run python3 x_post.py \"post text\" <media paths or prefixed paths>")
        print("  Bare paths auto-detect type from extension:")
        print("    uv run python3 x_post.py \"text\" /path/to/img.png")
        print("    uv run python3 x_post.py \"text\" /path/to/video.mp4")
        print("  Explicit types with prefix (img: / vid:):")
        print("    uv run python3 x_post.py \"text\" img:/path/to/img.png vid:/path/to/video.mp4")
        print("  Multiple items:")
        print("    uv run python3 x_post.py \"text\" /path/to/img1.png /path/to/img2.jpg")
        sys.exit(1)

    text_arg = sys.argv[1]
    media_args = sys.argv[2:]

    media = [_parse_media_arg(m) for m in media_args]

    ss_dir = str(SKILL_DIR / "screenshots")

    result = post_to_x(text=text_arg, media=media, screenshot_dir=ss_dir)

    print(f"success: {result['success']}, post_in_feed: {result.get('post_in_feed', False)}")
    if not result["success"]:
        sys.exit(1)
