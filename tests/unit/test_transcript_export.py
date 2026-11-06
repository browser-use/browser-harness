import contextlib
import hashlib
import io
import json
import runpy
import time
from pathlib import Path

import pytest


SCRIPT = (
    Path(__file__).resolve().parents[2]
    / "agent-workspace/domain-skills/claude-ai/extract-share-transcript.py"
)


def _run_export(output_dir, share_url, monkeypatch):
    monkeypatch.setenv("CLAUDE_SHARE_URL", share_url)
    monkeypatch.setenv("OUTPUT_DIR", str(output_dir))
    monkeypatch.setattr(time, "sleep", lambda _: None)
    with contextlib.redirect_stdout(io.StringIO()):
        runpy.run_path(
            str(SCRIPT),
            init_globals={
                "new_tab": lambda *_: None,
                "wait_for_load": lambda: None,
                "js": lambda *_: json.dumps(
                    {
                        "title": "Same Title",
                        "turns": [{"role": "user", "text": "hello"}],
                    }
                ),
            },
        )


def _write_owned_pair(output_dir, slug, share_url):
    (output_dir / f"{slug}.json").write_text(
        json.dumps({"source_url": share_url}), encoding="utf-8"
    )
    (output_dir / f"{slug}.md").write_text(
        f"# Existing\n\nSource: {share_url}\n", encoding="utf-8"
    )


def _digest(share_url):
    return hashlib.sha256(share_url.encode("utf-8")).hexdigest()[:10]


def test_same_title_exports_preserve_other_share_and_reuse_digest(tmp_path, monkeypatch):
    original_url = "https://claude.ai/share/original"
    new_url = "https://claude.ai/share/new"
    _write_owned_pair(tmp_path, "same-title", original_url)
    original_json = (tmp_path / "same-title.json").read_text(encoding="utf-8")
    original_md = (tmp_path / "same-title.md").read_text(encoding="utf-8")

    _run_export(tmp_path, new_url, monkeypatch)
    digest_slug = f"same-title-{_digest(new_url)}"
    exported_json = tmp_path / f"{digest_slug}.json"
    assert json.loads(exported_json.read_text(encoding="utf-8"))["source_url"] == new_url
    assert (tmp_path / "same-title.json").read_text(encoding="utf-8") == original_json
    assert (tmp_path / "same-title.md").read_text(encoding="utf-8") == original_md

    _run_export(tmp_path, new_url, monkeypatch)
    assert json.loads(exported_json.read_text(encoding="utf-8"))["source_url"] == new_url
    assert not (tmp_path / f"{digest_slug}-2.json").exists()


def test_occupied_digest_destination_gets_next_stable_name(tmp_path, monkeypatch):
    new_url = "https://claude.ai/share/new"
    _write_owned_pair(tmp_path, "same-title", "https://claude.ai/share/original")
    digest_slug = f"same-title-{_digest(new_url)}"
    _write_owned_pair(tmp_path, digest_slug, "https://claude.ai/share/other")
    original_json = (tmp_path / f"{digest_slug}.json").read_text(encoding="utf-8")
    original_md = (tmp_path / f"{digest_slug}.md").read_text(encoding="utf-8")

    _run_export(tmp_path, new_url, monkeypatch)

    next_slug = f"{digest_slug}-2"
    assert json.loads((tmp_path / f"{next_slug}.json").read_text(encoding="utf-8"))["source_url"] == new_url
    assert (tmp_path / f"{digest_slug}.json").read_text(encoding="utf-8") == original_json
    assert (tmp_path / f"{digest_slug}.md").read_text(encoding="utf-8") == original_md


def test_invalid_utf8_target_is_preserved_as_unknown(tmp_path, monkeypatch):
    new_url = "https://claude.ai/share/new"
    invalid_json = tmp_path / "same-title.json"
    invalid_json.write_bytes(b"\xff")

    _run_export(tmp_path, new_url, monkeypatch)

    assert invalid_json.read_bytes() == b"\xff"
    assert json.loads(
        (tmp_path / f"same-title-{_digest(new_url)}.json").read_text(encoding="utf-8")
    )["source_url"] == new_url


def test_markdown_only_same_share_is_completed_without_duplicate(tmp_path, monkeypatch):
    share_url = "https://claude.ai/share/same"
    markdown = tmp_path / "same-title.md"
    markdown.write_text(f"# Existing\n\nSource: {share_url}\n", encoding="utf-8")

    _run_export(tmp_path, share_url, monkeypatch)

    assert json.loads((tmp_path / "same-title.json").read_text(encoding="utf-8"))["source_url"] == share_url
    assert "Source: " + share_url in markdown.read_text(encoding="utf-8")
    assert not (tmp_path / f"same-title-{_digest(share_url)}.json").exists()


def test_atomic_reservation_collision_retries_without_overwrite(tmp_path, monkeypatch):
    new_url = "https://claude.ai/share/new"
    existing_url = "https://claude.ai/share/winner"
    original_open = Path.open
    collided = False

    def competing_export(path, mode="r", *args, **kwargs):
        nonlocal collided
        if path == tmp_path / "same-title.json" and mode == "x" and not collided:
            collided = True
            with original_open(path, "x", encoding="utf-8") as file:
                json.dump({"source_url": existing_url}, file)
            with original_open(tmp_path / "same-title.md", "x", encoding="utf-8") as file:
                file.write(f"Source: {existing_url}\n")
            raise FileExistsError(path)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", competing_export)
    _run_export(tmp_path, new_url, monkeypatch)

    assert json.loads((tmp_path / "same-title.json").read_text(encoding="utf-8"))["source_url"] == existing_url
    assert json.loads(
        (tmp_path / f"same-title-{_digest(new_url)}.json").read_text(encoding="utf-8")
    )["source_url"] == new_url
