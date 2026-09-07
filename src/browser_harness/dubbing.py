#!/usr/bin/env python3
"""AI dubbing for exported videos: turns each beat's sticky narration text into a
Portuguese (BR) speech track via ElevenLabs, timed to match the compiled composition."""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
# "Bella" — a stock ElevenLabs voice that handles pt-BR cleanly via the multilingual model.
DEFAULT_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"


class DubbingError(RuntimeError):
    pass


def api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise DubbingError(
            "ELEVENLABS_API_KEY not set; add it to .env (see .env.example) or export it "
            "before running video export --dub"
        )
    return key


def voice_id() -> str:
    return os.environ.get("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE_ID


def synthesize_clip(text: str, out_path: Path) -> None:
    """Call the ElevenLabs TTS API and write the returned mp3 to out_path."""
    url = ELEVENLABS_TTS_URL.format(voice_id=voice_id())
    payload = json.dumps(
        {
            "text": text,
            "model_id": DEFAULT_MODEL_ID,
            "language_code": "pt",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={
            "xi-api-key": api_key(),
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            out_path.write_bytes(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise DubbingError(f"ElevenLabs TTS failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise DubbingError(f"ElevenLabs TTS request failed: {exc}") from exc


def narration_segments(composition: dict[str, Any]) -> list[tuple[float, float, str]]:
    """Collapse sticky narration text across action beats into (start, end, text)
    spans — a narration line covers every beat until the next one sets new text,
    mirroring what the viewer actually sees on screen."""
    segments: list[tuple[float, float, str]] = []
    t = 0.0
    current_text: str | None = None
    current_start = 0.0
    for beat in composition.get("beats") or []:
        dur = float(beat.get("dur") or 0)
        if not beat.get("card"):
            narration = beat.get("narration")
            if narration:
                if current_text:
                    segments.append((current_start, t, current_text))
                current_text = narration
                current_start = t
        t += dur
    if current_text:
        segments.append((current_start, t, current_text))
    return segments


def build_narration_track(recording: Path, composition: dict[str, Any], total_duration: float) -> Path:
    """Synthesize one clip per narration span and mix them into a single WAV track
    exactly total_duration seconds long, each clip starting at its beat's timestamp."""
    segments = narration_segments(composition)
    track_path = recording / "narration-track.wav"

    if not segments:
        subprocess.run(
            [
                "ffmpeg", "-v", "error", "-y", "-f", "lavfi",
                "-i", f"anullsrc=r=44100:cl=stereo:d={total_duration:.3f}",
                str(track_path),
            ],
            check=True,
        )
        return track_path

    tmp_dir = recording / ".dub-tmp"
    tmp_dir.mkdir(exist_ok=True)
    clips: list[tuple[float, Path]] = []
    for index, (start, _end, text) in enumerate(segments):
        clip_path = tmp_dir / f"seg-{index:02d}.mp3"
        synthesize_clip(text, clip_path)
        clips.append((start, clip_path))

    cmd = ["ffmpeg", "-v", "error", "-y"]
    cmd += ["-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={total_duration:.3f}"]
    for _, clip_path in clips:
        cmd += ["-i", str(clip_path)]

    filter_chain = []
    mix_labels = ["[0:a]"]
    for input_index, (start, _) in enumerate(clips, start=1):
        delay_ms = max(0, round(start * 1000))
        filter_chain.append(f"[{input_index}:a]adelay={delay_ms}|{delay_ms}[d{input_index}]")
        mix_labels.append(f"[d{input_index}]")
    filter_chain.append(
        f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:"
        "dropout_transition=0:normalize=0[aout]"
    )
    cmd += [
        "-filter_complex", ";".join(filter_chain),
        "-map", "[aout]",
        "-t", f"{total_duration:.3f}",
        str(track_path),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise DubbingError(f"ffmpeg narration mix failed: {proc.stderr.strip()}")
    return track_path
