#!/usr/bin/env python3
"""Prepare compact renderer review sheets, then export and verify an MP4."""

from __future__ import annotations

import contextlib
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

from . import video


TEMPLATE = Path(__file__).with_name("video-template.html")
MARKER = "__BH_VIDEO_RESULT__="
REVIEW_ARTIFACTS = {
    "composition.js",
    "recording-summary.json",
    "edit-brief.json",
    video.SOURCE_MANIFEST,
    "video.html",
}
OBSOLETE_REVIEW_FILES = {
    "privacy-contact-sheet.jpg",
    "renderer-normal-contact-sheet.jpg",
    "renderer-reduced-contact-sheet.jpg",
    "renderer-click-contact-sheet.jpg",
    "video-audit.json",
}


def load_composition(recording: Path) -> dict:
    return video.load_composition(recording / "composition.js")


def compile_recording(recording: Path, write: bool) -> dict:
    video.verify_source_manifest(recording)
    summary = video.load_json(recording / "recording-summary.json")
    brief = video.load_json(recording / "edit-brief.json")
    composition = video.compile_brief(
        summary, brief, video.HOUSE_STYLE, video.load_revealed_text(recording / "events.jsonl")
    )
    if write:
        video.write_composition(recording / "composition.js", composition)
    return composition


def review_samples(comp: dict) -> list[dict]:
    """One stable state per beat, plus every explanation reveal."""
    samples = []
    start = 0.0
    for index, beat in enumerate(comp.get("beats") or [], 1):
        duration = float(beat.get("dur") or 0)
        if beat.get("kind") == "explanation" and beat.get("points"):
            points = beat["points"]
            first, final_hold = 1.1, 3.0
            span = max(0.0, duration - first - final_hold)
            gap = span / max(1, len(points) - 1)
            for point_index, point in enumerate(points, 1):
                local = min(max(0.05, duration - 0.05), first + (point_index - 1) * gap + 0.2)
                samples.append({
                    "time": round(start + local, 3),
                    "label": f"beat {index} · {point.get('label') or point_index}",
                })
        else:
            local = min(max(0.05, duration - 0.05), 1.0 if beat.get("card") else max(0.12, min(0.5, duration / 2)))
            samples.append({"time": round(start + local, 3), "label": f"beat {index}"})
        start += duration
    return samples


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format, *_args):
        pass


@contextlib.contextmanager
def serve(recording: Path):
    handler = lambda *args, **kwargs: _QuietHandler(  # noqa: E731
        *args, directory=str(recording), **kwargs
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/video.html"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def _harness_command() -> list[str]:
    return [sys.executable, "-m", "browser_harness.run"]


def run_harness(code: str, timeout: float = 60) -> dict:
    env = {**os.environ, "BH_RECORD": "0"}
    proc = subprocess.run(
        _harness_command(),
        input=code,
        text=True,
        capture_output=True,
        env=env,
        timeout=timeout,
        check=False,
    )
    if proc.returncode:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(f"browser review failed: {detail}")
    for line in reversed(proc.stdout.splitlines()):
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER):])
    raise RuntimeError(f"browser review returned no result: {proc.stdout[-1000:]}")


def _review_browser(recording: Path, url: str, samples: list[dict]) -> dict:
    review_dir = recording / ".renderer-review"
    payload = {
        "url": url,
        "samples": samples,
        "reviewDir": str(review_dir),
        "marker": MARKER,
    }
    code = f"""
import json, os, time
cfg = json.loads({json.dumps(json.dumps(payload))})
os.makedirs(cfg['reviewDir'], exist_ok=True)

def ready():
    for _ in range(100):
        if js('window.videoReady && window.videoReady()'):
            return
        time.sleep(0.05)
    raise RuntimeError('video assets did not become ready')

def inspect_mode(name, reduced):
    features = [{{'name':'prefers-reduced-motion','value':'reduce'}}] if reduced else []
    cdp('Emulation.setEmulatedMedia', media='', features=features)
    cdp('Page.reload', ignoreCache=True)
    wait_for_load()
    ready()
    preflight = js('window.videoPreflight()')
    clicks = js('window.clickVisibility()')
    captures = []
    for index, sample in enumerate(cfg['samples'], 1):
        js(f"window.seek({{sample['time']}})")
        path = f"{{cfg['reviewDir']}}/{{name}}-beat-{{index:02d}}.png"
        capture_screenshot(path)
        captures.append({{'path': path, 'time': sample['time'], 'label': sample['label']}})
    click_captures = []
    for index, click in enumerate(clicks, 1):
        for state, key in (('click', 'time'), ('result', 'resultTime')):
            js(f"window.seek({{click[key]}})")
            path = f"{{cfg['reviewDir']}}/{{name}}-click-{{index:02d}}-{{state}}.png"
            capture_screenshot(path)
            click_captures.append({{
                'path': path, 'time': click[key],
                'label': f"beat {{click['beat']}} · {{state}}",
            }})
    return {{'preflight': preflight, 'clicks': clicks, 'captures': captures,
            'clickCaptures': click_captures}}

try:
    previous = current_tab()['targetId']
except Exception:
    previous = None
target = None
try:
    target = new_tab()
    goto_url(cfg['url'])
    wait_for_load()
    ready()
    normal = inspect_mode('normal', False)
    reduced = inspect_mode('reduced', True)
    print(cfg['marker'] + json.dumps({{'normal': normal, 'reduced': reduced}}))
finally:
    try:
        cdp('Emulation.setEmulatedMedia', media='', features=[])
    except Exception:
        pass
    try:
        switch_tab(previous) if previous else new_tab()
    except Exception:
        try:
            new_tab()
        except Exception:
            pass
    if target is not None:
        try:
            close_tab(target)
        except Exception:
            pass
"""
    return run_harness(code, timeout=max(60, len(samples) * 3))


def contact_sheet(captures: list[dict], output: Path, title: str) -> None:
    cols, tile_w, tile_h, label_h, gap, banner = 4, 400, 225, 34, 8, 42
    rows = max(1, math.ceil(len(captures) / cols))
    sheet = Image.new(
        "RGB",
        (cols * tile_w + (cols + 1) * gap, banner + rows * (tile_h + label_h + gap) + gap),
        "#171a20",
    )
    draw, font = ImageDraw.Draw(sheet), ImageFont.load_default()
    draw.text((gap, 15), title, fill="#ffffff", font=font)
    for index, capture in enumerate(captures):
        image = Image.open(capture["path"]).convert("RGB")
        preview = ImageOps.contain(image, (tile_w, tile_h), Image.Resampling.LANCZOS)
        col, row = index % cols, index // cols
        x, y = gap + col * (tile_w + gap), banner + gap + row * (tile_h + label_h + gap)
        sheet.paste(preview, (x + (tile_w - preview.width) // 2, y))
        label = f"{capture['label']}  {float(capture['time']):.2f}s"
        draw.text((x, y + tile_h + 9), label, fill="#d7dbe3", font=font)
    sheet.save(output, quality=91)


def masked_frame(recording: Path, comp: dict, frame: str) -> Image.Image:
    viewport = comp["viewport"]
    vw, vh = float(viewport["w"]), float(viewport["h"])
    redactions = comp.get("redact") or {}
    privacy = comp.get("privacy") or {}
    mask = privacy.get("mask") or {}
    pad = float(privacy.get("pad") or 8)
    image = Image.open(recording / frame).convert("RGB")
    sx, sy = image.width / vw, image.height / vh
    draw = ImageDraw.Draw(image)
    for rectangle in redactions.get(frame, []):
        rect_pad = float(rectangle.get("pad", pad))
        x0 = max(0, (float(rectangle["x"]) - rect_pad) * sx)
        y0 = max(0, (float(rectangle["y"]) - rect_pad) * sy)
        x1 = min(image.width, (float(rectangle["x"]) + float(rectangle["w"]) + rect_pad) * sx)
        y1 = min(image.height, (float(rectangle["y"]) + float(rectangle["h"]) + rect_pad) * sy)
        fill = rectangle.get("fill", mask.get("fill", "#f2f4f7"))
        stroke = rectangle.get("stroke", mask.get("stroke", "#e2e7ec"))
        radius = float(rectangle.get("radius", mask.get("radius", 7))) * min(sx, sy)
        draw.rounded_rectangle(
            (x0, y0, x1, y1), radius=radius, fill=fill,
            outline=stroke or None, width=max(1, round(min(sx, sy))),
        )
    return image


def privacy_review(recording: Path, comp: dict) -> tuple[Path, list[dict]]:
    review_dir = recording / ".privacy-review"
    review_dir.mkdir(exist_ok=True)
    for stale in review_dir.glob("*.jpg"):
        stale.unlink()
    captures = []
    redactions = comp.get("redact") or {}
    for frame in video.used_frames(comp):
        source = recording / frame
        if not source.is_file():
            raise RuntimeError(f"missing frame: {frame}")
        output = review_dir / frame
        masked_frame(recording, comp, frame).save(output, quality=94)
        captures.append(
            {
                "path": str(output),
                "time": 0,
                "label": f"privacy · {frame} · masks:{len(redactions.get(frame, []))}",
            }
        )
    return review_dir, captures


def review(recording: Path) -> int:
    started = time.monotonic()
    for name in OBSOLETE_REVIEW_FILES:
        (recording / name).unlink(missing_ok=True)
    comp = compile_recording(recording, write=True)
    shutil.copy2(TEMPLATE, recording / "video.html")
    privacy_dir, privacy_captures = privacy_review(recording, comp)
    samples = review_samples(comp)
    review_dir = recording / ".renderer-review"
    review_dir.mkdir(exist_ok=True)
    for stale in review_dir.glob("*.png"):
        stale.unlink()
    with serve(recording) as url:
        result = _review_browser(recording, url, samples)

    errors = []
    warnings = []
    all_captures = list(privacy_captures)
    for mode in ("normal", "reduced"):
        errors.extend(f"{mode}: {error}" for error in result[mode]["preflight"].get("errors", []))
        warnings.extend(
            f"{mode}: {warning}"
            for warning in result[mode]["preflight"].get("warnings", [])
        )
        errors.extend(
            f"{mode}: beat {click['beat']} click is outside the safe viewport"
            for click in result[mode]["clicks"] if not click.get("visible")
        )
        for capture in result[mode]["captures"]:
            all_captures.append({**capture, "label": f"{mode} · {capture['label']}"})
        for capture in result[mode]["clickCaptures"]:
            all_captures.append({**capture, "label": f"{mode} · {capture['label']}"})

    sheet = recording / "video-review-contact-sheet.jpg"
    contact_sheet(all_captures, sheet, "PRIVACY · EVERY BEAT · EXACT CLICK + RESULT")

    report = {
        "errors": errors,
        "warnings": warnings,
        "duration": round(sum(float(beat.get("dur") or 0) for beat in comp.get("beats") or []), 3),
        "artifactHashes": {
            name: video.file_hash(recording / name) for name in sorted(REVIEW_ARTIFACTS)
        },
        "normal": result["normal"],
        "reduced": result["reduced"],
        "contactSheet": str(sheet),
        "privacyReviewDir": str(privacy_dir),
        "elapsedSeconds": round(time.monotonic() - started, 3),
    }
    report_path = recording / "renderer-review.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"review sheet: {sheet}")
    print(f"full-resolution privacy review: {privacy_dir}")
    print(f"renderer review: {len(errors)} error(s) in {report['elapsedSeconds']:.1f}s")
    return 1 if errors else 0


def _start_export(recording: Path, url: str, webm: Path) -> dict:
    payload = {"url": url, "downloadPath": str(recording), "filename": webm.name, "marker": MARKER}
    filename_js = json.dumps(webm.name)
    code = f"""
import json, time
cfg = json.loads({json.dumps(json.dumps(payload))})
try:
    previous = current_tab()['targetId']
except Exception:
    previous = None
target = new_tab()
goto_url(cfg['url'])
wait_for_load()
for _ in range(100):
    if js('window.videoReady && window.videoReady()'):
        break
    time.sleep(0.05)
else:
    raise RuntimeError('video assets did not become ready')
preflight = js('window.videoPreflight()')
clicks = js('window.clickVisibility()')
cdp('Browser.setDownloadBehavior', behavior='allow', downloadPath=cfg['downloadPath'], eventsEnabled=True)
cdp('Page.bringToFront')
started = js('''(() => {{
  window.__exported = null; window.__exportError = null;
  window.exportVideo({filename_js})
    .catch(error => window.__exportError = String(error));
  return true;
}})()''')
print(cfg['marker'] + json.dumps({{'target': target, 'previous': previous, 'preflight': preflight, 'clicks': clicks, 'started': started}}))
"""
    return run_harness(code, timeout=30)


def _close_editor(url: str, previous: str | None = None) -> bool:
    payload = {"url": url, "previous": previous, "marker": MARKER}
    code = f"""
import json
cfg = json.loads({json.dumps(json.dumps(payload))})
downloads_reset = True
try:
    cdp('Browser.setDownloadBehavior', behavior='default', eventsEnabled=False)
except Exception:
    downloads_reset = False
targets = [tab for tab in list_tabs() if tab.get('url') == cfg['url']]
try:
    switch_tab(cfg['previous']) if cfg.get('previous') else new_tab()
except Exception:
    new_tab()
for tab in targets:
    try:
        close_tab(tab)
    except Exception:
        pass
print(cfg['marker'] + json.dumps({{'closed': True, 'downloadsReset': downloads_reset}}))
"""
    try:
        result = run_harness(code, timeout=15)
    except Exception:
        return False
    return result.get("downloadsReset") is True


def _run(command: list[str], cwd: Path, timeout: float = 120) -> subprocess.CompletedProcess:
    proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout).strip())
    return proc


def _probe(path: Path) -> dict:
    proc = _run([
        "ffprobe", "-v", "error", "-show_entries",
        "format=duration,size:stream=codec_name,width,height,pix_fmt,r_frame_rate",
        "-of", "json", str(path),
    ], path.parent)
    return json.loads(proc.stdout)


def export(recording: Path, output_name: str, reviewed: bool) -> int:
    if not reviewed:
        raise RuntimeError("inspect the review sheet and full-resolution privacy frames, then rerun with --reviewed")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg and ffprobe are required")
    review_path = recording / "renderer-review.json"
    if not review_path.is_file():
        raise RuntimeError("run browser-harness video review first")
    review_report = json.loads(review_path.read_text(encoding="utf-8"))
    if review_report.get("errors"):
        raise RuntimeError("renderer review has blocking errors")
    video.verify_source_manifest(recording)
    comp = load_composition(recording)
    expected_comp = compile_recording(recording, write=False)
    if comp != expected_comp:
        raise RuntimeError("composition.js is not the current compiled brief; rerun review")
    artifact_hashes = review_report.get("artifactHashes") or {}
    if set(artifact_hashes) != REVIEW_ARTIFACTS:
        raise RuntimeError("renderer review lacks content hashes; rerun it")
    for name, expected_hash in artifact_hashes.items():
        path = recording / name
        if not path.is_file() or video.file_hash(path) != expected_hash:
            raise RuntimeError(f"{name} changed after review; rerun it")
    renderer = recording / "video.html"
    if video.file_hash(renderer) != video.file_hash(TEMPLATE):
        raise RuntimeError("renderer is not the current shared template; rerun review")

    output = Path(output_name)
    if not output.is_absolute():
        output = recording / output
    if output.suffix.lower() != ".mp4":
        raise RuntimeError("--output must end in .mp4")
    webm = output.with_suffix(".webm")
    for path in (webm, output):
        if path.exists() or path.with_name(path.name + ".crdownload").exists():
            raise RuntimeError(f"refusing to overwrite {path}")

    expected = sum(float(beat.get("dur") or 0) for beat in comp.get("beats") or [])
    started = time.monotonic()
    with serve(recording) as url:
        browser = None
        try:
            browser = _start_export(recording, url, webm)
            if browser["preflight"].get("errors"):
                raise RuntimeError(
                    "export preflight failed: " + "; ".join(browser["preflight"]["errors"])
                )
            if any(not click.get("visible") for click in browser["clicks"]):
                raise RuntimeError("export click visibility failed")
            deadline = time.monotonic() + expected + 30
            partial = webm.with_name(webm.name + ".crdownload")
            while time.monotonic() < deadline:
                if webm.is_file() and not partial.exists() and webm.stat().st_size:
                    size = webm.stat().st_size
                    time.sleep(0.25)
                    if webm.stat().st_size == size:
                        break
                time.sleep(0.25)
            else:
                raise RuntimeError(f"timed out waiting for {webm}")
        finally:
            if not _close_editor(url, (browser or {}).get("previous")):
                raise RuntimeError(
                    "could not restore Chrome download behavior; restart Chrome"
                )
    capture_seconds = time.monotonic() - started

    conversion_started = time.monotonic()
    _probe(webm)
    _run([
        "ffmpeg", "-v", "error", "-i", str(webm), "-c:v", "libx264",
        "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ], recording)
    conversion_seconds = time.monotonic() - conversion_started

    verify_started = time.monotonic()
    probe = _probe(output)
    actual = float(probe["format"]["duration"])
    if abs(actual - expected) > max(1.0, expected * 0.08):
        raise RuntimeError(f"export duration {actual:.2f}s does not match composition {expected:.2f}s")
    _run(["ffmpeg", "-v", "error", "-err_detect", "explode", "-i", str(output), "-f", "null", "-"], recording)

    review_dir = recording / ".renderer-review"
    final_captures = []
    for index, at in enumerate((min(1.0, expected / 4), expected / 2, max(0.0, expected - 0.8)), 1):
        path = review_dir / f"final-{index:02d}.jpg"
        _run(["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.3f}", "-i", str(output), "-frames:v", "1", str(path)], recording)
        final_captures.append({"path": str(path), "time": at, "label": ("intro", "middle", "outcome")[index - 1]})
    final_sheet = recording / "renderer-final-contact-sheet.jpg"
    contact_sheet(final_captures, final_sheet, "FINAL MP4 SAMPLE")
    verify_seconds = time.monotonic() - verify_started

    report = {
        "output": str(output),
        "webm": str(webm),
        "expectedDuration": round(expected, 3),
        "actualDuration": actual,
        "captureSeconds": round(capture_seconds, 3),
        "conversionSeconds": round(conversion_seconds, 3),
        "verificationSeconds": round(verify_seconds, 3),
        "elapsedSeconds": round(time.monotonic() - started, 3),
        "sha256": video.file_hash(output),
        "probe": probe,
        "finalContactSheet": str(final_sheet),
    }
    report_path = recording / "video-export.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"video: {output}")
    print(f"final review: {final_sheet}")
    print(f"verified {actual:.2f}s MP4 in {report['elapsedSeconds']:.1f}s")
    return 0
