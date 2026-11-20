import importlib.util
import json
import os
import subprocess
import sys
import types
from pathlib import Path


AGENT_WORKSPACE = Path(__file__).resolve().parents[2] / "agent-workspace"
if str(AGENT_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(AGENT_WORKSPACE))

from content_extraction import (
    archive_current_page,
    archive_paths,
    defuddle_html_file,
    extract_cards,
    extract_markdown_from_current_page,
    extract_links,
    extract_lists,
    extract_outline,
    extract_tables,
    extract_virtualized_container,
    json_dump,
    safe_slug,
)


def test_safe_slug_normalizes_text_and_uses_fallback():
    assert safe_slug("  WorldQuant BRAIN / Simulate  ", "page") == "worldquant-brain-simulate"
    assert safe_slug("!!!", "Untitled Page") == "untitled-page"


def test_archive_paths_are_deterministic_and_grouped_by_page(tmp_path):
    info = {
        "url": "https://platform.worldquantbrain.com/simulate?foo=bar",
        "title": "WorldQuant BRAIN",
    }

    paths = archive_paths(tmp_path, info, timestamp="20260605T021500Z")

    assert paths["dir"] == str(tmp_path / "20260605T021500Z-platform-worldquantbrain-com-worldquant-brain")
    assert paths["metadata"].endswith("/metadata.json")
    assert paths["html"].endswith("/page.html")
    assert paths["text"].endswith("/text.txt")
    assert paths["links"].endswith("/links.json")
    assert paths["screenshot"].endswith("/screenshot.png")
    assert paths["markdown"].endswith("/markdown.md")


def test_json_dump_writes_stable_utf8_json(tmp_path):
    path = tmp_path / "metadata.json"

    json_dump(path, {"title": "한글", "url": "https://example.com"})

    assert json.loads(path.read_text(encoding="utf-8")) == {
        "title": "한글",
        "url": "https://example.com",
    }
    assert "\\u" not in path.read_text(encoding="utf-8")


def test_agent_helpers_exposes_archive_current_page(monkeypatch):
    pkg = types.ModuleType("browser_harness")
    helpers = types.ModuleType("browser_harness.helpers")
    helpers.cdp = lambda method, **kwargs: {}
    helpers._KEYS = {}
    pkg.helpers = helpers
    monkeypatch.setitem(sys.modules, "browser_harness", pkg)
    monkeypatch.setitem(sys.modules, "browser_harness.helpers", helpers)

    path = AGENT_WORKSPACE / "agent_helpers.py"
    spec = importlib.util.spec_from_file_location("agent_helpers_under_test", path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert callable(module.archive_current_page)
    assert callable(module.extract_markdown_from_current_page)
    assert callable(module.extract_outline)
    assert callable(module.extract_links)
    assert callable(module.extract_tables)
    assert callable(module.extract_lists)
    assert callable(module.extract_cards)
    assert callable(module.extract_virtualized_container)


def _patch_runtime(monkeypatch, tmp_path, *, title="Demo", body="alpha beta", screenshot_ok=True):
    def fake_page_info():
        return {
            "url": "https://example.com/demo",
            "title": title,
            "w": 1200,
            "h": 800,
            "sx": 0,
            "sy": 0,
            "pw": 1200,
            "ph": 1600,
        }

    def fake_js(expr):
        if "outerHTML" in expr:
            return "<html><body><main><p>alpha beta</p></main></body></html>"
        if "querySelectorAll" in expr:
            return [{"href": "https://example.com/next", "text": "Next", "title": ""}]
        if "innerText" in expr:
            return body
        raise AssertionError(expr)

    def fake_screenshot(path, **kwargs):
        if not screenshot_ok:
            raise RuntimeError("shot failed")
        Path(path).write_bytes(b"png")
        return str(path)

    monkeypatch.setattr("content_extraction.page_info", fake_page_info)
    monkeypatch.setattr("content_extraction.js", fake_js)
    monkeypatch.setattr("content_extraction.capture_screenshot", fake_screenshot)
    return tmp_path / "archive"


def test_archive_current_page_writes_raw_artifacts(monkeypatch, tmp_path):
    output_dir = _patch_runtime(monkeypatch, tmp_path)

    result = archive_current_page(output_dir, screenshot=True, overwrite=True)

    archive_dir = Path(result["archiveDir"])
    raw_dir = archive_dir / "raw"
    assert result["status"] == "success"
    assert Path(result["manifestPath"]).exists()
    assert (raw_dir / "page-info.json").exists()
    assert (raw_dir / "page.html").read_text(encoding="utf-8").startswith("<html>")
    assert (raw_dir / "body.txt").read_text(encoding="utf-8") == "alpha beta"
    assert json.loads((raw_dir / "links.json").read_text(encoding="utf-8"))[0]["text"] == "Next"
    assert (raw_dir / "screenshot.png").read_bytes() == b"png"


def test_archive_current_page_omits_screenshot_by_default(monkeypatch, tmp_path):
    output_dir = _patch_runtime(monkeypatch, tmp_path)

    result = archive_current_page(output_dir, overwrite=True)

    raw_dir = Path(result["archiveDir"]) / "raw"
    assert result["status"] == "success"
    assert not (raw_dir / "screenshot.png").exists()
    manifest = json.loads(Path(result["manifestPath"]).read_text(encoding="utf-8"))
    assert "screenshot" not in manifest["artifactPaths"]["raw"]


def test_archive_current_page_accepts_empty_title_and_body(monkeypatch, tmp_path):
    output_dir = _patch_runtime(monkeypatch, tmp_path, title="", body="")

    result = archive_current_page(output_dir, screenshot=False, overwrite=True)

    manifest = json.loads(Path(result["manifestPath"]).read_text(encoding="utf-8"))
    assert result["status"] == "success"
    assert manifest["title"] == ""
    assert manifest["stats"]["textChars"] == 0


def test_archive_current_page_does_not_overwrite_existing_target(monkeypatch, tmp_path):
    output_dir = _patch_runtime(monkeypatch, tmp_path)
    output_dir.mkdir()
    old_file = output_dir / "old.txt"
    old_file.write_text("keep", encoding="utf-8")

    result = archive_current_page(output_dir, screenshot=False, overwrite=False)

    archive_dir = Path(result["archiveDir"])
    assert old_file.read_text(encoding="utf-8") == "keep"
    assert archive_dir.parent == output_dir
    assert archive_dir != output_dir
    assert (archive_dir / "manifest.json").exists()


def test_archive_current_page_marks_screenshot_failure_partial(monkeypatch, tmp_path):
    output_dir = _patch_runtime(monkeypatch, tmp_path, screenshot_ok=False)

    result = archive_current_page(output_dir, screenshot=True, overwrite=True)

    archive_dir = Path(result["archiveDir"])
    manifest = json.loads(Path(result["manifestPath"]).read_text(encoding="utf-8"))
    assert result["status"] == "partial"
    assert (archive_dir / "raw" / "page.html").exists()
    assert manifest["status"] == "partial"
    assert manifest["errors"][0]["phase"] == "screenshot"


def test_archive_current_page_markdown_success_updates_manifest(monkeypatch, tmp_path):
    output_dir = _patch_runtime(monkeypatch, tmp_path)

    def fake_defuddle(html_path, **kwargs):
        assert Path(html_path).exists()
        output_path = Path(kwargs["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("# Demo\n\nalpha beta", encoding="utf-8")
        return {
            "status": "success",
            "markdownPath": str(output_path),
            "stats": {"markdownChars": len("# Demo\n\nalpha beta")},
        }

    monkeypatch.setattr("content_extraction.defuddle_html_file", fake_defuddle)

    result = archive_current_page(output_dir, markdown=True, screenshot=False, overwrite=True)

    manifest = json.loads(Path(result["manifestPath"]).read_text(encoding="utf-8"))
    assert result["status"] == "success"
    assert Path(manifest["artifactPaths"]["raw"]["html"]).exists()
    assert Path(manifest["artifactPaths"]["processed"]["markdown"]).exists()
    assert Path(manifest["artifactPaths"]["processed"]["status"]).exists()
    assert manifest["processed"]["status"] == "success"


def test_markdown_failure_preserves_raw(monkeypatch, tmp_path):
    output_dir = _patch_runtime(monkeypatch, tmp_path)

    def fake_defuddle(html_path, **kwargs):
        return {"status": "failed", "stderr": "empty markdown"}

    monkeypatch.setattr("content_extraction.defuddle_html_file", fake_defuddle)

    result = archive_current_page(output_dir, markdown=True, screenshot=False, overwrite=True)

    archive_dir = Path(result["archiveDir"])
    manifest = json.loads(Path(result["manifestPath"]).read_text(encoding="utf-8"))
    assert result["status"] == "partial"
    assert (archive_dir / "raw" / "page.html").exists()
    assert not (archive_dir / "processed" / "page.md").exists()
    assert json.loads((archive_dir / "processed" / "status.json").read_text(encoding="utf-8"))["status"] == "failed"
    assert manifest["processed"]["status"] == "failed"


def test_empty_markdown_output_is_removed(monkeypatch, tmp_path):
    output_dir = _patch_runtime(monkeypatch, tmp_path)

    def fake_defuddle(html_path, **kwargs):
        output_path = Path(kwargs["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("   \n", encoding="utf-8")
        return {"status": "success", "markdownPath": str(output_path), "stats": {"markdownChars": 4}}

    monkeypatch.setattr("content_extraction.defuddle_html_file", fake_defuddle)

    result = archive_current_page(output_dir, markdown=True, screenshot=False, overwrite=True)

    archive_dir = Path(result["archiveDir"])
    assert result["status"] == "partial"
    assert not (archive_dir / "processed" / "page.md").exists()
    assert json.loads((archive_dir / "processed" / "status.json").read_text(encoding="utf-8"))["status"] == "failed"


def test_extract_markdown_wrapper_enables_markdown(monkeypatch, tmp_path):
    output_dir = _patch_runtime(monkeypatch, tmp_path)

    def fake_defuddle(html_path, **kwargs):
        output_path = Path(kwargs["output_path"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("alpha beta", encoding="utf-8")
        return {"status": "success", "markdownPath": str(output_path), "stats": {"markdownChars": 10}}

    monkeypatch.setattr("content_extraction.defuddle_html_file", fake_defuddle)

    result = extract_markdown_from_current_page(output_dir, screenshot=False, overwrite=True)

    assert result["status"] == "success"
    assert (Path(result["archiveDir"]) / "processed" / "page.md").exists()


def test_outline_empty_returns_status(monkeypatch):
    monkeypatch.setattr("content_extraction.js", lambda expr: {"status": "empty", "items": []})

    result = extract_outline()

    assert result == {"status": "empty", "items": []}


def test_outline_multiple_headings(monkeypatch):
    monkeypatch.setattr(
        "content_extraction.js",
        lambda expr: {
            "status": "success",
            "items": [
                {"level": 1, "text": "Report", "id": "report"},
                {"level": 2, "text": "Details", "id": ""},
            ],
        },
    )

    result = extract_outline()

    assert result["items"][0] == {"level": 1, "text": "Report", "id": "report"}
    json.dumps(result)


def test_links_empty_returns_status(monkeypatch):
    monkeypatch.setattr("content_extraction.js", lambda expr: {"status": "empty", "items": []})

    result = extract_links()

    assert result == {"status": "empty", "items": []}


def test_links_deduplicates_exact_href_and_text(monkeypatch):
    monkeypatch.setattr(
        "content_extraction.js",
        lambda expr: {
            "status": "success",
            "items": [
                {"href": "https://example.com/a", "text": "A", "rel": "", "target": "", "sameOrigin": True},
                {"href": "https://example.com/a", "text": "A", "rel": "", "target": "", "sameOrigin": True},
                {"href": "https://example.com/a", "text": "Different", "rel": "", "target": "", "sameOrigin": True},
            ],
        },
    )

    result = extract_links()

    assert [item["text"] for item in result["items"]] == ["A", "Different"]
    json.dumps(result)


def test_tables_empty_returns_status(monkeypatch):
    monkeypatch.setattr("content_extraction.js", lambda expr: {"status": "empty", "tables": []})

    result = extract_tables()

    assert result == {"status": "empty", "tables": []}


def test_tables_headers_include_row_objects(monkeypatch):
    monkeypatch.setattr(
        "content_extraction.js",
        lambda expr: {
            "status": "success",
            "tables": [
                {
                    "caption": "Scores",
                    "headers": ["Name", "Score"],
                    "rows": [["Name", "Score"], ["Alpha", "7"]],
                    "rowObjects": [{"Name": "Alpha", "Score": "7"}],
                }
            ],
        },
    )

    result = extract_tables()

    assert result["tables"][0]["rowObjects"][0] == {"Name": "Alpha", "Score": "7"}
    json.dumps(result)


def test_lists_extracts_list_items(monkeypatch):
    monkeypatch.setattr(
        "content_extraction.js",
        lambda expr: {"status": "success", "items": [{"type": "ul", "items": ["One", "Two"], "ariaLabel": ""}]},
    )

    result = extract_lists()

    assert result["items"][0]["items"] == ["One", "Two"]
    json.dumps(result)


def test_cards_missing_selector_returns_not_found(monkeypatch):
    monkeypatch.setattr("content_extraction.js", lambda expr: {"status": "not_found", "items": []})

    result = extract_cards(".missing")

    assert result == {"status": "not_found", "items": []}


def test_cards_hidden_content_is_filtered(monkeypatch):
    monkeypatch.setattr(
        "content_extraction.js",
        lambda expr: {
            "status": "success",
            "items": [
                {"visible": False, "text": "Hidden", "links": [], "heading": "", "ariaLabel": "", "data": {}},
                {"visible": True, "text": "Shown", "links": [], "heading": "Shown", "ariaLabel": "", "data": {}},
            ],
        },
    )

    result = extract_cards(".card")

    assert [item["text"] for item in result["items"]] == ["Shown"]


def test_virtualized_stable_stop(monkeypatch):
    monkeypatch.setattr(
        "content_extraction.js",
        lambda expr: {
            "status": "success",
            "items": [{"text": "A"}],
            "scrollAttempts": 3,
            "stableRounds": 2,
            "partial": False,
            "stopReason": "stable",
        },
    )

    result = extract_virtualized_container(".list", ".item", max_scrolls=5, stable_rounds=2)

    assert result["partial"] is False
    assert result["stopReason"] == "stable"


def test_virtualized_empty_items_are_not_success(monkeypatch):
    def fake_js(expr):
        assert "const status = items.length ? 'success' : 'empty'" in expr
        assert "if (!items.length) return {status:'empty'" in expr
        return {
            "status": "empty",
            "items": [],
            "scrollAttempts": 2,
            "stableRounds": 1,
            "partial": False,
            "stopReason": "empty",
        }

    monkeypatch.setattr("content_extraction.js", fake_js)

    result = extract_virtualized_container(".list", ".missing", max_scrolls=5, stable_rounds=1)

    assert result["status"] == "empty"
    assert result["items"] == []
    assert result["stopReason"] == "empty"


def test_virtualized_partial_on_max_scrolls(monkeypatch):
    monkeypatch.setattr(
        "content_extraction.js",
        lambda expr: {
            "status": "partial",
            "items": [{"text": "A"}],
            "scrollAttempts": 2,
            "stableRounds": 0,
            "partial": True,
            "stopReason": "max_scrolls",
        },
    )

    result = extract_virtualized_container(".list", ".item", max_scrolls=2, stable_rounds=2)

    assert result["partial"] is True
    assert result["stopReason"] == "max_scrolls"


def test_defuddle_unavailable_returns_structured_fallback(monkeypatch, tmp_path):
    html_path = tmp_path / "raw" / "page.html"
    html_path.parent.mkdir()
    html_path.write_text("<article>alpha</article>", encoding="utf-8")
    monkeypatch.setattr("content_extraction.shutil.which", lambda name: None)

    result = defuddle_html_file(html_path)

    assert result["status"] == "unavailable"
    assert "markdownPath" not in result


def test_defuddle_unavailable_can_raise(monkeypatch, tmp_path):
    html_path = tmp_path / "page.html"
    html_path.write_text("<article>alpha</article>", encoding="utf-8")
    monkeypatch.setattr("content_extraction.shutil.which", lambda name: None)

    try:
        defuddle_html_file(html_path, fail_soft=False)
    except RuntimeError as exc:
        assert "Defuddle executable not found" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_defuddle_nonzero_returns_failed_without_markdown(monkeypatch, tmp_path):
    html_path = tmp_path / "raw" / "page.html"
    html_path.parent.mkdir()
    html_path.write_text("<article>alpha</article>", encoding="utf-8")
    output_path = tmp_path / "processed" / "page.md"
    monkeypatch.setattr("content_extraction.shutil.which", lambda name: "/bin/defuddle")
    monkeypatch.setattr(
        "content_extraction.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 2, "", "bad parse"),
    )

    result = defuddle_html_file(html_path, output_path=output_path)

    assert result["status"] == "failed"
    assert "bad parse" in result["stderr"]
    assert "markdownPath" not in result
    assert not output_path.exists()


def test_defuddle_success_writes_markdown_and_stats(monkeypatch, tmp_path):
    html_path = tmp_path / "raw" / "page.html"
    html_path.parent.mkdir()
    html_path.write_text("<article>alpha beta</article>", encoding="utf-8")
    monkeypatch.setattr("content_extraction.shutil.which", lambda name: "/bin/defuddle")

    def fake_run(args, **kwargs):
        output_path = Path(args[args.index("--output") + 1])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("# Alpha\n\nbeta", encoding="utf-8")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("content_extraction.subprocess.run", fake_run)

    result = defuddle_html_file(html_path)

    markdown_path = Path(result["markdownPath"])
    assert result["status"] == "success"
    assert markdown_path == tmp_path / "processed" / "page.md"
    assert markdown_path.read_text(encoding="utf-8").startswith("# Alpha")
    assert result["stats"]["markdownChars"] == len("# Alpha\n\nbeta")
