<!-- AUTO-PUSH-RULES:BEGIN v1 (2026-11-26, Barron) -->
## Auto-push 规则 / Auto-push rules

- 每完成一组改动就 `git add <具体文件>` → `git commit` → `git push`。 Commit and push after every finished group of changes.
- 只推当前的非 main/master/production 分支，或 `auto-sync` / `studio-sync` 分支；上线一律走 PR，不直接推 main。 Push only the current non-main branch or an auto-sync/studio-sync branch; releases go through a PR.
- 禁止 force push（含 `--force-with-lease`）、禁止 rebase 已推送的提交、禁止删除远端分支。 No force push, no rebasing pushed commits, no deleting remote branches.
- 不提交 `.env*`、密钥/凭证/token、`node_modules`，以及大于 50MB 的文件（视频等大文件放 Google Drive）。 Never commit `.env*`, secrets, or files larger than 50MB.
- 不执行 `vercel --prod`；生产上线需要 Barron 明确批准。 Never run `vercel --prod`.
- Studio 每天 PT 02:30 由 launchd 作业 `com.barron.grok-runners.repo-autopush` 把未提交/未推送的改动备份到 `studio-sync` 分支（不推 main）；它是兜底，不替代上面的提交习惯。
<!-- AUTO-PUSH-RULES:END -->

<!-- TOKEN-RULES:BEGIN v1 (2026-11-26, Barron) -->
## Token 规则 / Token rules

- 一个会话只做一个任务；上下文到约 200K 就 `/compact`，或写 handoff（RUN-REPORT.md / handoff 文件）后另开新会话。 One task per session; at ~200K context run /compact or write a handoff and start a fresh session.
- 每个会话同时最多 5 个子代理；每轮最多 1 个 verifier/critic；子代理默认用 sonnet 或 haiku，opus 只用于架构和分析。 Max 5 concurrent subagents per session, max 1 verifier/critic per round; subagents default to sonnet/haiku, opus only for architecture/analysis.
- 会话里不 `sleep`、不轮询（不写 `until …; sleep`）；等待交给后台任务通知或 launchd。 No sleep/polling inside the conversation; hand waiting to background notifications or launchd.
- 截图先缩小（例如 `sips -Z 800`）再读，不把原图读进上下文。 Downscale screenshots before reading them.
- 同一个文件不要反复读；第一次读完记下要点（写进 scratchpad/handoff）。 Don't re-read the same file; note the key points once.
<!-- TOKEN-RULES:END -->
