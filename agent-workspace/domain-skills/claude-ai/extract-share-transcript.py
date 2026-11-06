"""Extract a transcript from a claude.ai share URL.

Usage (run inside browser-harness):
    CLAUDE_SHARE_URL=https://claude.ai/share/<uuid> \
    OUTPUT_DIR=/path/to/transcripts \
    browser-harness < agent-workspace/domain-skills/claude-ai/extract-share-transcript.py

Requires: the user's running Chrome must be signed into claude.ai (share pages
render the conversation only for authenticated viewers — see share-export.md).

Writes two files into OUTPUT_DIR, named from the conversation title slug:
    <slug>.json  — {title, source_url, turns: [{role, text}]}
    <slug>.md    — Markdown with ## Human / ## Assistant headers
"""
import hashlib, json, os, pathlib, re, sys, time

share_url = os.environ.get("CLAUDE_SHARE_URL")
out_dir = os.environ.get("OUTPUT_DIR")
if not share_url or not out_dir:
    sys.exit("set CLAUDE_SHARE_URL and OUTPUT_DIR env vars")

new_tab(share_url)            # noqa: F821 — provided by browser-harness
wait_for_load()               # noqa: F821
time.sleep(2)                 # let the conversation tree render

js_code = """
(() => {
  const userMsgs = [...document.querySelectorAll("[data-testid=user-message]")];
  if (!userMsgs.length) return JSON.stringify({error: "no user messages found — is the user logged in to claude.ai?"});
  let p = userMsgs[0];
  while (p && !p.contains(userMsgs[userMsgs.length-1])) p = p.parentElement;
  const container = p;
  const turns = [];
  for (const child of container.children) {
    const u = child.querySelector("[data-testid=user-message]");
    const a = child.querySelector(".font-claude-response");
    if (u) turns.push({role: "user", text: u.innerText.trim()});
    else if (a) turns.push({role: "assistant", text: a.innerText.trim()});
  }
  const ph = document.querySelector("[data-testid=page-header]");
  const title = (ph?.innerText.split("\\n")[0] || document.title || "").trim();
  return JSON.stringify({title, turns});
})()
"""
data = json.loads(js(js_code))    # noqa: F821
if data.get("error"):
    sys.exit(data["error"])

title = data["title"] or "claude-share"
turns = data["turns"]
slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-") or "claude-share"

out = pathlib.Path(out_dir)
out.mkdir(parents=True, exist_ok=True)

_MISSING = object()


def _source_url(text, kind):
    if kind == "json":
        try:
            value = json.loads(text)
        except json.JSONDecodeError:
            return None
        return value.get("source_url") if isinstance(value, dict) else None
    for line in text.splitlines():
        if line.startswith("Source: "):
            return line[len("Source: "):]
    return None


def _owner(path, kind):
    if not path.exists():
        return _MISSING
    try:
        return _source_url(path.read_text(encoding="utf-8"), kind)
    except (OSError, UnicodeDecodeError):
        return None


def _remove_reserved(path, handle):
    reserved = os.fstat(handle.fileno())
    handle.close()
    try:
        current = path.stat()
    except FileNotFoundError:
        return
    if (current.st_dev, current.st_ino) == (reserved.st_dev, reserved.st_ino):
        path.unlink()


def _close_opened(opened, remove_created=False):
    for path, handle, created in reversed(opened):
        if created and remove_created:
            _remove_reserved(path, handle)
        else:
            handle.close()


# Reuse only outputs that identify this share; reserve missing paths atomically.
def _open_candidate(json_path, md_path, share_url):
    owners = (_owner(json_path, "json"), _owner(md_path, "md"))
    if any(owner is not _MISSING and owner != share_url for owner in owners):
        return None

    opened = []
    try:
        for path, kind, owner in zip((json_path, md_path), ("json", "md"), owners):
            created = owner is _MISSING
            handle = path.open("x" if created else "r+", encoding="utf-8")
            opened.append((path, handle, created))
            if not created:
                if _source_url(handle.read(), kind) != share_url:
                    raise FileExistsError(path)
                handle.seek(0)
    except (FileExistsError, FileNotFoundError, UnicodeDecodeError):
        _close_opened(opened, remove_created=True)
        return None
    except BaseException:
        _close_opened(opened, remove_created=True)
        raise
    return opened


payload = {"title": title, "source_url": share_url, "turns": turns}
json_text = json.dumps(payload, indent=2, ensure_ascii=False)
parts = [f"# {title}", "", f"Source: {share_url}", f"Turns: {len(turns)}", ""]
for t in turns:
    label = "Human" if t["role"] == "user" else "Assistant"
    parts += [f"## {label}", "", t["text"], ""]
md_text = "\n".join(parts)

base_slug = slug
digest = hashlib.sha256(share_url.encode("utf-8")).hexdigest()[:10]
attempt = 0
while True:
    suffix = "" if attempt == 0 else f"-{digest}" + (f"-{attempt}" if attempt > 1 else "")
    slug = f"{base_slug}{suffix}"
    json_path = out / f"{slug}.json"
    md_path = out / f"{slug}.md"
    opened = _open_candidate(json_path, md_path, share_url)
    if opened is None:
        attempt += 1
        continue

    try:
        for path, handle, _ in opened:
            handle.seek(0)
            handle.truncate()
            handle.write(json_text if path == json_path else md_text)
            handle.flush()
    finally:
        _close_opened(opened)
    break

print(f"title: {title}")
print(f"turns: {len(turns)}")
print(f"json:  {out / (slug + '.json')}")
print(f"md:    {out / (slug + '.md')}")
