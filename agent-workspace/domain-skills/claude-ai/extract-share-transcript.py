"""Extract a transcript from a claude.ai share URL.

Usage (run inside browser-harness):
    CLAUDE_SHARE_URL=https://claude.ai/share/<uuid> \
    OUTPUT_DIR=/path/to/transcripts \
    bh -c "$(cat agent-workspace/domain-skills/claude-ai/extract-share-transcript.py)"

Requires: the user's running Chrome must be signed into claude.ai (share pages
render the conversation only for authenticated viewers — see share-export.md).

Writes two files into OUTPUT_DIR, named from the conversation title slug:
    <slug>.json  — {title, source_url, turns: [{role, text}]}
    <slug>.md    — Markdown with ## Human / ## Assistant headers
"""
import json, os, pathlib, re, sys, time

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

payload = {"title": title, "source_url": share_url, "turns": turns}
(out / f"{slug}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

parts = [f"# {title}", "", f"Source: {share_url}", f"Turns: {len(turns)}", ""]
for t in turns:
    label = "Human" if t["role"] == "user" else "Assistant"
    parts += [f"## {label}", "", t["text"], ""]
(out / f"{slug}.md").write_text("\n".join(parts), encoding="utf-8")

print(f"title: {title}")
print(f"turns: {len(turns)}")
print(f"json:  {out / (slug + '.json')}")
print(f"md:    {out / (slug + '.md')}")
