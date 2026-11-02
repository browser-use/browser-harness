// Extract a transcript from a claude.ai share URL.
//
// Usage (run inside browser-harness):
//   CLAUDE_SHARE_URL=https://claude.ai/share/<uuid> \
//   OUTPUT_DIR=/path/to/transcripts \
//   browser-harness < agent-workspace/domain-skills/claude-ai/extract-share-transcript.js
//
// Requires: the browser must be signed into claude.ai (share pages render the
// conversation only for authenticated viewers — see share-export.md).
//
// Writes two files into OUTPUT_DIR (which must exist), named from the title slug:
//   <slug>.json  — {title, source_url, turns: [{role, text}]}
//   <slug>.md    — Markdown with ## Human / ## Assistant headers

const shareUrl = env("CLAUDE_SHARE_URL");
const outDir = env("OUTPUT_DIR");
if (!shareUrl || !outDir) throw new Error("set CLAUDE_SHARE_URL and OUTPUT_DIR env vars");

new_tab(shareUrl);
wait_for_load();
wait(2);  // let the conversation tree render

const data = JSON.parse(js(`
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
`));
if (data.error) throw new Error(data.error);

const title = data.title || "claude-share";
const turns = data.turns;
const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "claude-share";
const base = outDir.replace(/\/+$/, "") + "/" + slug;

write_file(base + ".json", JSON.stringify({title, source_url: shareUrl, turns}, null, 2));

const parts = [`# ${title}`, "", `Source: ${shareUrl}`, `Turns: ${turns.length}`, ""];
for (const t of turns) parts.push(`## ${t.role === "user" ? "Human" : "Assistant"}`, "", t.text, "");
write_file(base + ".md", parts.join("\n"));

print(`title: ${title}`);
print(`turns: ${turns.length}`);
print(`json:  ${base}.json`);
print(`md:    ${base}.md`);
