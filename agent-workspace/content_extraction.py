from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TypeAlias, TypedDict
from urllib.parse import urlparse

JSONScalar: TypeAlias = None | bool | int | float | str
JSONValue: TypeAlias = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]

_SLUG_PARTS = re.compile(r"[^a-z0-9]+")


class ArchivePaths(TypedDict):
    dir: str
    metadata: str
    html: str
    text: str
    links: str
    screenshot: str
    markdown: str


class ArchiveResult(TypedDict):
    status: str
    manifestPath: str
    archiveDir: str


class DefuddleResult(TypedDict, total=False):
    status: str
    markdownPath: str
    stdout: str
    stderr: str
    stats: dict[str, JSONValue]


class CollectionResult(TypedDict):
    status: str
    items: list[dict[str, JSONValue]]


class TablesResult(TypedDict):
    status: str
    tables: list[dict[str, JSONValue]]


class VirtualizedResult(TypedDict):
    status: str
    items: list[dict[str, JSONValue]]
    scrollAttempts: int
    stableRounds: int
    partial: bool
    stopReason: str


class ArchivePhaseError(RuntimeError):
    def __init__(self, phase: str, detail: str) -> None:
        super().__init__(f"archive_current_page failed during {phase}: {detail}")
        self.phase = phase


_LINKS_JS = (
    'return Array.from(document.querySelectorAll("a[href]")).map((link) => ({'
    "href: link.href,"
    'text: (link.innerText || link.textContent || "").trim(),'
    'title: link.title || ""'
    "}));"
)


def _outline_js(scope_selector: str | None) -> str:
    return (
        "const selector = "
        + json.dumps(scope_selector)
        + ";const root = selector ? document.querySelector(selector) : document;"
        "if (!root) return {status:'empty', items:[]};"
        "const items = Array.from(root.querySelectorAll('h1,h2,h3,h4,h5,h6')).map((heading) => ({"
        "level: Number(heading.tagName.slice(1)),"
        "text: (heading.innerText || heading.textContent || '').trim(),"
        "id: heading.id || ''"
        "}));"
        "return {status: items.length ? 'success' : 'empty', items};"
    )


def _extract_links_js(scope_selector: str | None, include_empty: bool) -> str:
    return (
        "const selector = "
        + json.dumps(scope_selector)
        + ";const includeEmpty = "
        + json.dumps(include_empty)
        + ";const root = selector ? document.querySelector(selector) : document;"
        "if (!root) return {status:'empty', items:[]};"
        "const seen = new Set(); const items = [];"
        "for (const link of Array.from(root.querySelectorAll('a[href]'))) {"
        "const text = (link.innerText || link.textContent || '').trim();"
        "if (!includeEmpty && !text) continue;"
        "const href = link.href;"
        "const key = href + '\\n' + text;"
        "if (seen.has(key)) continue;"
        "seen.add(key);"
        "let sameOrigin = false;"
        "try { sameOrigin = new URL(href, location.href).origin === location.origin; } catch (e) {}"
        "items.push({text, href, rel: link.rel || '', target: link.target || '', sameOrigin});"
        "}"
        "return {status: items.length ? 'success' : 'empty', items};"
    )


def _tables_js(scope_selector: str | None) -> str:
    return (
        "const selector = "
        + json.dumps(scope_selector)
        + ";const root = selector ? document.querySelector(selector) : document;"
        "if (!root) return {status:'empty', tables:[]};"
        "const tables = Array.from(root.querySelectorAll('table')).map((table) => {"
        "const rows = Array.from(table.rows).map((row) => Array.from(row.cells).map((cell) => "
        "(cell.innerText || cell.textContent || '').trim()));"
        "const firstRow = table.rows[0];"
        "const hasHeaders = !!firstRow && Array.from(firstRow.cells).some((cell) => cell.tagName.toLowerCase() === 'th');"
        "const headers = hasHeaders ? rows[0] : [];"
        "const dataRows = hasHeaders ? rows.slice(1) : rows;"
        "const rowObjects = hasHeaders ? dataRows.map((row) => Object.fromEntries(headers.map((header, index) => "
        "[header, row[index] || '']))) : [];"
        "const caption = table.caption ? (table.caption.innerText || table.caption.textContent || '').trim() : '';"
        "return {caption, headers, rows, rowObjects};"
        "});"
        "return {status: tables.length ? 'success' : 'empty', tables};"
    )


def _lists_js(scope_selector: str | None) -> str:
    return (
        "const selector = "
        + json.dumps(scope_selector)
        + ";const root = selector ? document.querySelector(selector) : document;"
        "if (!root) return {status:'not_found', items:[]};"
        "const lists = Array.from(root.querySelectorAll('ul,ol,[role=\"list\"]')).map((list) => {"
        "const itemNodes = Array.from(list.querySelectorAll(':scope > li, :scope > [role=\"listitem\"]'));"
        "const items = itemNodes.map((item) => (item.innerText || item.textContent || '').trim()).filter(Boolean);"
        "const type = list.getAttribute('role') || list.tagName.toLowerCase();"
        "return {type, items, ariaLabel: list.getAttribute('aria-label') || ''};"
        "}).filter((list) => list.items.length);"
        "return {status: lists.length ? 'success' : 'empty', items: lists};"
    )


def _cards_js(card_selector: str, fields: list[str], link_selector: str) -> str:
    return (
        "const cards = Array.from(document.querySelectorAll("
        + json.dumps(card_selector)
        + "));"
        "if (!cards.length) return {status:'not_found', items:[]};"
        "const fields = new Set("
        + json.dumps(fields)
        + ");"
        "const linkSelector = "
        + json.dumps(link_selector)
        + ";"
        "const items = cards.map((card) => {"
        "const visible = !!(card.offsetWidth || card.offsetHeight || card.getClientRects().length);"
        "const headingNode = card.querySelector('h1,h2,h3,h4,h5,h6');"
        "const links = Array.from(card.querySelectorAll(linkSelector)).map((link) => ({"
        "href: link.href, text: (link.innerText || link.textContent || '').trim()"
        "}));"
        "const data = Object.assign({}, card.dataset);"
        "const item = {visible};"
        "if (fields.has('text')) item.text = (card.innerText || card.textContent || '').trim();"
        "if (fields.has('links')) item.links = links;"
        "if (fields.has('heading')) item.heading = headingNode ? (headingNode.innerText || headingNode.textContent || '').trim() : '';"
        "if (fields.has('ariaLabel')) item.ariaLabel = card.getAttribute('aria-label') || '';"
        "if (fields.has('data')) item.data = data;"
        "return item;"
        "}).filter((item) => item.visible);"
        "return {status: items.length ? 'success' : 'empty', items};"
    )


def _virtualized_js(
    container_selector: str | None,
    item_selector: str,
    max_scrolls: int,
    stable_rounds: int,
) -> str:
    return (
        "return (async () => {"
        "const containerSelector = "
        + json.dumps(container_selector)
        + ";const itemSelector = "
        + json.dumps(item_selector)
        + ";const maxScrolls = "
        + json.dumps(max_scrolls)
        + ";const requiredStable = "
        + json.dumps(stable_rounds)
        + ";const container = containerSelector ? document.querySelector(containerSelector) : "
        "(document.scrollingElement || document.documentElement);"
        "if (!container) return {status:'not_found', items:[], scrollAttempts:0, stableRounds:0, partial:true, stopReason:'not_found'};"
        "const seen = new Map(); let stable = 0; let lastCount = -1;"
        "const collect = () => {"
        "for (const item of Array.from(container.querySelectorAll(itemSelector))) {"
        "const text = (item.innerText || item.textContent || '').trim();"
        "const key = item.id || item.getAttribute('data-id') || text;"
        "if (key && !seen.has(key)) seen.set(key, {text, id: item.id || '', data: Object.assign({}, item.dataset)});"
        "}"
        "};"
        "for (let attempt = 0; attempt < maxScrolls; attempt++) {"
        "collect();"
        "stable = seen.size === lastCount ? stable + 1 : 0;"
        "lastCount = seen.size;"
        "if (stable >= requiredStable) {"
        "const items = Array.from(seen.values());"
        "const status = items.length ? 'success' : 'empty';"
        "const reason = items.length ? 'stable' : 'empty';"
        "return {status, items, scrollAttempts:attempt + 1, stableRounds:stable, partial:false, stopReason:reason};"
        "}"
        "container.scrollTop = container.scrollTop + container.clientHeight;"
        "await new Promise((resolve) => setTimeout(resolve, 40));"
        "}"
        "collect();"
        "const items = Array.from(seen.values());"
        "if (!items.length) return {status:'empty', items, scrollAttempts:maxScrolls, stableRounds:stable, partial:false, stopReason:'empty'};"
        "return {status:'partial', items, scrollAttempts:maxScrolls, stableRounds:stable, partial:true, stopReason:'max_scrolls'};"
        "})()"
    )


def safe_slug(value: str, fallback: str) -> str:
    slug = _SLUG_PARTS.sub("-", value.strip().lower()).strip("-")
    if slug:
        return slug
    return _SLUG_PARTS.sub("-", fallback.strip().lower()).strip("-") or "page"


def archive_paths(
    output_dir: str | Path,
    page_info: Mapping[str, JSONScalar],
    timestamp: str | None = None,
) -> ArchivePaths:
    captured_at = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    url_value = page_info.get("url")
    title_value = page_info.get("title")
    url = url_value if isinstance(url_value, str) else ""
    title = title_value if isinstance(title_value, str) else ""
    host = urlparse(url).hostname or "page"
    page_slug = safe_slug(f"{safe_slug(host, 'page')}-{safe_slug(title, 'page')}", "page")
    archive_dir = Path(output_dir) / f"{captured_at}-{page_slug}"
    return {
        "dir": str(archive_dir),
        "metadata": str(archive_dir / "metadata.json"),
        "html": str(archive_dir / "page.html"),
        "text": str(archive_dir / "text.txt"),
        "links": str(archive_dir / "links.json"),
        "screenshot": str(archive_dir / "screenshot.png"),
        "markdown": str(archive_dir / "markdown.md"),
    }


def page_info() -> Mapping[str, JSONScalar]:
    from browser_harness.helpers import page_info as runtime_page_info

    return runtime_page_info()


def js(expression: str) -> JSONValue:
    from browser_harness.helpers import js as runtime_js

    return runtime_js(expression)


def capture_screenshot(path: str | Path) -> str | None:
    from browser_harness.helpers import capture_screenshot as runtime_capture_screenshot

    return runtime_capture_screenshot(str(path))


def json_dump(path: str | Path, data: JSONValue) -> None:
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with path_obj.open("w", encoding="utf-8") as out:
        json.dump(data, out, ensure_ascii=False, indent=2, sort_keys=True)
        out.write("\n")


def _default_markdown_path(html_path: Path) -> Path:
    if html_path.parent.name == "raw":
        return html_path.parent.parent / "processed" / "page.md"
    return html_path.parent / "processed" / "page.md"


def _defuddle_failed(message: str, *, fail_soft: bool) -> DefuddleResult:
    if not fail_soft:
        raise RuntimeError(message)
    return {"status": "failed", "stderr": message}


def defuddle_html_file(
    html_path: str | Path,
    *,
    output_path: str | Path | None = None,
    fail_soft: bool = True,
    timeout: int = 30,
) -> DefuddleResult:
    source = Path(html_path)
    if "://" in str(html_path):
        return _defuddle_failed("Defuddle source must be a local HTML file path", fail_soft=fail_soft)
    if not source.exists() or not source.is_file():
        return _defuddle_failed(f"HTML file not found: {source}", fail_soft=fail_soft)

    executable = shutil.which("defuddle")
    if executable is None:
        message = "Defuddle executable not found"
        if not fail_soft:
            raise RuntimeError(message)
        return {"status": "unavailable", "stderr": message}

    target = Path(output_path) if output_path is not None else _default_markdown_path(source)
    existed_before = target.exists()
    target.parent.mkdir(parents=True, exist_ok=True)
    command = [
        executable,
        "parse",
        "--markdown",
        "--output",
        str(target),
        str(source),
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return _defuddle_failed(f"Defuddle timed out after {timeout}s: {exc}", fail_soft=fail_soft)
    except OSError as exc:
        return _defuddle_failed(f"Defuddle failed to start: {exc}", fail_soft=fail_soft)

    if completed.returncode != 0:
        if target.exists() and not existed_before:
            target.unlink()
        message = completed.stderr.strip() or f"Defuddle exited {completed.returncode}"
        return _defuddle_failed(message, fail_soft=fail_soft)

    if not target.exists():
        return _defuddle_failed("Defuddle exited 0 without writing markdown", fail_soft=fail_soft)

    markdown = target.read_text(encoding="utf-8")
    return {
        "status": "success",
        "markdownPath": str(target),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "stats": {
            "markdownChars": len(markdown),
            "sourceHtmlBytes": source.stat().st_size,
        },
    }


def _created_at() -> tuple[str, str]:
    now = datetime.now(UTC)
    return now.isoformat().replace("+00:00", "Z"), now.strftime("%Y%m%dT%H%M%SZ")


def _archive_dir(
    output_dir: str | Path,
    info: Mapping[str, JSONScalar],
    timestamp: str,
    *,
    overwrite: bool,
) -> Path:
    target = Path(output_dir)
    if target.exists() and not target.is_dir():
        raise ArchivePhaseError("prepare", f"{target} exists and is not a directory")
    if overwrite or not target.exists():
        target.mkdir(parents=True, exist_ok=True)
        return target

    child = Path(archive_paths(target, info, timestamp=timestamp)["dir"])
    if not child.exists():
        child.mkdir(parents=True)
        return child

    suffix = 2
    while True:
        candidate = Path(f"{child}-{suffix}")
        if not candidate.exists():
            candidate.mkdir(parents=True)
            return candidate
        suffix += 1


def _clear_managed_files(archive_dir: Path) -> None:
    for path in [
        archive_dir / "manifest.json",
        archive_dir / "raw" / "page-info.json",
        archive_dir / "raw" / "page.html",
        archive_dir / "raw" / "body.txt",
        archive_dir / "raw" / "links.json",
        archive_dir / "raw" / "screenshot.png",
        archive_dir / "processed" / "page.md",
        archive_dir / "processed" / "status.json",
    ]:
        if path.exists() and path.is_file():
            path.unlink()


def _read_text_phase(phase: str, expression: str) -> str:
    try:
        value = js(expression)
    except (RuntimeError, OSError, TypeError, ValueError) as exc:
        raise ArchivePhaseError(phase, str(exc)) from exc
    if not isinstance(value, str):
        raise ArchivePhaseError(phase, f"expected string result, got {type(value).__name__}")
    return value


def _read_links() -> list[dict[str, JSONValue]]:
    try:
        value = js(_LINKS_JS)
    except (RuntimeError, OSError, TypeError, ValueError) as exc:
        raise ArchivePhaseError("links", str(exc)) from exc
    if not isinstance(value, list):
        raise ArchivePhaseError("links", f"expected list result, got {type(value).__name__}")

    links: list[dict[str, JSONValue]] = []
    for item in value:
        if isinstance(item, dict):
            href = item.get("href")
            text = item.get("text")
            title = item.get("title")
            links.append({
                "href": href if isinstance(href, str) else "",
                "text": text if isinstance(text, str) else "",
                "title": title if isinstance(title, str) else "",
            })
    return links


def _info_json(info: Mapping[str, JSONScalar]) -> dict[str, JSONValue]:
    return {str(key): value for key, value in info.items()}


def _collection_result(value: JSONValue, key: str) -> tuple[str, list[dict[str, JSONValue]]]:
    if not isinstance(value, dict):
        return "failed", []
    status_value = value.get("status")
    status = status_value if isinstance(status_value, str) else "success"
    raw_items = value.get(key)
    if not isinstance(raw_items, list):
        return status, []
    items = [item for item in raw_items if isinstance(item, dict)]
    if items:
        return status, items
    if status in {"not_found", "failed", "partial"}:
        return status, items
    return "empty", items


def _status_for_count(status: str, count: int) -> str:
    if count:
        return status
    if status in {"not_found", "failed", "partial"}:
        return status
    return "empty"


def extract_outline(scope_selector: str | None = None) -> CollectionResult:
    status, raw_items = _collection_result(js(_outline_js(scope_selector)), "items")
    items: list[dict[str, JSONValue]] = []
    for item in raw_items:
        level_value = item.get("level")
        text_value = item.get("text")
        id_value = item.get("id")
        items.append({
            "level": level_value if isinstance(level_value, int) else 0,
            "text": text_value if isinstance(text_value, str) else "",
            "id": id_value if isinstance(id_value, str) else "",
        })
    return {"status": _status_for_count(status, len(items)), "items": items}


def extract_links(scope_selector: str | None = None, include_empty: bool = False) -> CollectionResult:
    status, raw_items = _collection_result(js(_extract_links_js(scope_selector, include_empty)), "items")
    items: list[dict[str, JSONValue]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_items:
        href_value = item.get("href")
        text_value = item.get("text")
        rel_value = item.get("rel")
        target_value = item.get("target")
        same_origin_value = item.get("sameOrigin")
        href = href_value if isinstance(href_value, str) else ""
        text = text_value if isinstance(text_value, str) else ""
        if not include_empty and not text:
            continue
        key = (href, text)
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "href": href,
            "text": text,
            "rel": rel_value if isinstance(rel_value, str) else "",
            "target": target_value if isinstance(target_value, str) else "",
            "sameOrigin": same_origin_value if isinstance(same_origin_value, bool) else False,
        })
    return {"status": _status_for_count(status, len(items)), "items": items}


def extract_tables(scope_selector: str | None = None) -> TablesResult:
    status, raw_tables = _collection_result(js(_tables_js(scope_selector)), "tables")
    tables: list[dict[str, JSONValue]] = []
    for table in raw_tables:
        caption_value = table.get("caption")
        headers_value = table.get("headers")
        rows_value = table.get("rows")
        row_objects_value = table.get("rowObjects")
        headers = [value for value in headers_value if isinstance(value, str)] if isinstance(headers_value, list) else []
        rows = rows_value if isinstance(rows_value, list) else []
        row_objects = row_objects_value if isinstance(row_objects_value, list) else []
        tables.append({
            "caption": caption_value if isinstance(caption_value, str) else "",
            "headers": headers,
            "rows": rows,
            "rowObjects": row_objects,
        })
    return {"status": _status_for_count(status, len(tables)), "tables": tables}


def extract_lists(scope_selector: str | None = None) -> CollectionResult:
    status, raw_items = _collection_result(js(_lists_js(scope_selector)), "items")
    items: list[dict[str, JSONValue]] = []
    for item in raw_items:
        type_value = item.get("type")
        items_value = item.get("items")
        aria_value = item.get("ariaLabel")
        list_items = [value for value in items_value if isinstance(value, str)] if isinstance(items_value, list) else []
        if list_items:
            items.append({
                "type": type_value if isinstance(type_value, str) else "",
                "items": list_items,
                "ariaLabel": aria_value if isinstance(aria_value, str) else "",
            })
    return {"status": _status_for_count(status, len(items)), "items": items}


def extract_cards(
    card_selector: str,
    fields: list[str] | None = None,
    link_selector: str = "a[href]",
) -> CollectionResult:
    selected_fields = fields or ["text", "links", "heading", "ariaLabel", "data"]
    status, raw_items = _collection_result(js(_cards_js(card_selector, selected_fields, link_selector)), "items")
    items: list[dict[str, JSONValue]] = []
    for item in raw_items:
        visible_value = item.get("visible")
        if visible_value is False:
            continue
        normalized: dict[str, JSONValue] = {}
        for field in selected_fields:
            value = item.get(field)
            if isinstance(value, (str, bool, int, float)) or value is None or isinstance(value, list) or isinstance(value, dict):
                normalized[field] = value
        items.append(normalized)
    return {"status": _status_for_count(status, len(items)), "items": items}


def extract_virtualized_container(
    container_selector: str | None,
    item_selector: str,
    *,
    max_scrolls: int = 20,
    stable_rounds: int = 2,
) -> VirtualizedResult:
    value = js(_virtualized_js(container_selector, item_selector, max_scrolls, stable_rounds))
    if not isinstance(value, dict):
        return {
            "status": "failed",
            "items": [],
            "scrollAttempts": 0,
            "stableRounds": 0,
            "partial": True,
            "stopReason": "invalid_result",
        }
    items_value = value.get("items")
    items = [item for item in items_value if isinstance(item, dict)] if isinstance(items_value, list) else []
    attempts_value = value.get("scrollAttempts")
    stable_value = value.get("stableRounds")
    partial_value = value.get("partial")
    reason_value = value.get("stopReason")
    status_value = value.get("status")
    return {
        "status": status_value if isinstance(status_value, str) else ("partial" if partial_value else "success"),
        "items": items,
        "scrollAttempts": attempts_value if isinstance(attempts_value, int) else 0,
        "stableRounds": stable_value if isinstance(stable_value, int) else 0,
        "partial": partial_value if isinstance(partial_value, bool) else True,
        "stopReason": reason_value if isinstance(reason_value, str) else "",
    }


def _processed_failure(status: str, message: str) -> dict[str, JSONValue]:
    return {"status": status, "stderr": message}


def _run_markdown(
    html_path: str | Path | None,
    processed_dir: Path,
    markdown_engine: str,
) -> tuple[dict[str, JSONValue], dict[str, JSONValue], dict[str, JSONValue] | None]:
    status_path = processed_dir / "status.json"
    processed_paths: dict[str, JSONValue] = {"status": str(status_path)}
    if html_path is None:
        status = _processed_failure("failed", "raw HTML artifact is unavailable")
        json_dump(status_path, status)
        return processed_paths, status, {"phase": "markdown", "message": "raw HTML artifact is unavailable"}
    if markdown_engine != "defuddle":
        status = _processed_failure("failed", f"unsupported markdown engine: {markdown_engine}")
        json_dump(status_path, status)
        return processed_paths, status, {"phase": "markdown", "message": status["stderr"]}

    markdown_path = processed_dir / "page.md"
    result = defuddle_html_file(html_path, output_path=markdown_path)
    status: dict[str, JSONValue] = {str(key): value for key, value in result.items()}
    result_status = result.get("status")
    result_path = result.get("markdownPath")
    if result_status == "success" and isinstance(result_path, str):
        markdown_file = Path(result_path)
        markdown_text = markdown_file.read_text(encoding="utf-8") if markdown_file.exists() else ""
        if markdown_text.strip():
            processed_paths["markdown"] = result_path
            json_dump(status_path, status)
            return processed_paths, status, None
        markdown_file.unlink(missing_ok=True)
        status = _processed_failure("failed", "Defuddle produced empty markdown")

    message_value = status.get("stderr") or status.get("status") or "markdown conversion failed"
    message = message_value if isinstance(message_value, str) else "markdown conversion failed"
    json_dump(status_path, status)
    return processed_paths, status, {"phase": "markdown", "message": message}


def archive_current_page(
    output_dir: str | Path = "evidence/archive",
    *,
    screenshot: bool = False,
    full_html: bool = True,
    text: bool = True,
    metadata: bool = True,
    links: bool = True,
    max_text_chars: int | None = None,
    overwrite: bool = False,
    markdown: bool = False,
    markdown_engine: str = "defuddle",
) -> ArchiveResult:
    try:
        info = page_info()
    except (RuntimeError, OSError, TypeError, ValueError) as exc:
        raise ArchivePhaseError("page_info", str(exc)) from exc

    created_at, timestamp = _created_at()
    archive_dir = _archive_dir(output_dir, info, timestamp, overwrite=overwrite)
    if overwrite:
        _clear_managed_files(archive_dir)
    raw_dir = archive_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    raw_artifact_paths: dict[str, JSONValue] = {}
    processed_artifact_paths: dict[str, JSONValue] = {}
    stats: dict[str, JSONValue] = {}
    errors: list[dict[str, JSONValue]] = []

    if metadata:
        page_info_path = raw_dir / "page-info.json"
        json_dump(page_info_path, _info_json(info))
        raw_artifact_paths["pageInfo"] = str(page_info_path)

    if full_html:
        html = _read_text_phase("html", "document.documentElement.outerHTML")
        html_path = raw_dir / "page.html"
        html_path.write_text(html, encoding="utf-8")
        raw_artifact_paths["html"] = str(html_path)
        stats["htmlChars"] = len(html)

    if text:
        body_text = _read_text_phase("text", "document.body ? document.body.innerText : ''")
        truncated = False
        if max_text_chars is not None and len(body_text) > max_text_chars:
            body_text = body_text[:max_text_chars]
            truncated = True
        text_path = raw_dir / "body.txt"
        text_path.write_text(body_text, encoding="utf-8")
        raw_artifact_paths["text"] = str(text_path)
        stats["textChars"] = len(body_text)
        stats["textTruncated"] = truncated

    if links:
        link_data = _read_links()
        links_path = raw_dir / "links.json"
        json_dump(links_path, link_data)
        raw_artifact_paths["links"] = str(links_path)
        stats["links"] = len(link_data)

    if screenshot:
        screenshot_path = raw_dir / "screenshot.png"
        try:
            capture_screenshot(screenshot_path)
            raw_artifact_paths["screenshot"] = str(screenshot_path)
        except (RuntimeError, OSError, TypeError, ValueError) as exc:
            errors.append({"phase": "screenshot", "message": str(exc)})

    processed_status: dict[str, JSONValue] = {"status": "skipped"}
    if markdown:
        processed_dir = archive_dir / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)
        html_artifact = raw_artifact_paths.get("html")
        html_path = html_artifact if isinstance(html_artifact, str) else None
        processed_artifact_paths, processed_status, markdown_error = _run_markdown(
            html_path,
            processed_dir,
            markdown_engine,
        )
        if markdown_error is not None:
            errors.append(markdown_error)

    status = "partial" if errors else "success"
    url_value = info.get("url")
    title_value = info.get("title")
    manifest: dict[str, JSONValue] = {
        "schemaVersion": 1,
        "createdAt": created_at,
        "sourceUrl": url_value if isinstance(url_value, str) else "",
        "title": title_value if isinstance(title_value, str) else "",
        "artifactPaths": {
            "raw": raw_artifact_paths,
            "processed": processed_artifact_paths,
        },
        "raw": {"artifactPaths": raw_artifact_paths},
        "processed": processed_status,
        "stats": stats,
        "privacy": {
            "localOnly": True,
            "externalUpload": False,
            "rawArtifactsRedacted": False,
        },
        "status": status,
    }
    if errors:
        manifest["errors"] = errors

    manifest_path = archive_dir / "manifest.json"
    json_dump(manifest_path, manifest)
    return {
        "status": status,
        "manifestPath": str(manifest_path),
        "archiveDir": str(archive_dir),
    }


def extract_markdown_from_current_page(
    output_dir: str | Path = "evidence/archive",
    *,
    screenshot: bool = False,
    full_html: bool = True,
    text: bool = True,
    metadata: bool = True,
    links: bool = True,
    max_text_chars: int | None = None,
    overwrite: bool = False,
    markdown_engine: str = "defuddle",
) -> ArchiveResult:
    return archive_current_page(
        output_dir,
        screenshot=screenshot,
        full_html=full_html,
        text=text,
        metadata=metadata,
        links=links,
        max_text_chars=max_text_chars,
        overwrite=overwrite,
        markdown=True,
        markdown_engine=markdown_engine,
    )
