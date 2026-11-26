<!-- AUTO-PUSH-RULES:BEGIN v1 (2026-11-26, Barron) -->
## Auto-push 规则 / Auto-push rules

- 每完成一组改动就 `git add <具体文件>` → `git commit` → `git push`。 Commit and push after every finished group of changes.
- 只推当前的非 main/master/production 分支，或 `auto-sync` / `studio-sync` 分支；上线一律走 PR，不直接推 main。 Push only the current non-main branch or an auto-sync/studio-sync branch; releases go through a PR.
- 禁止 force push（含 `--force-with-lease`）、禁止 rebase 已推送的提交、禁止删除远端分支。 No force push, no rebasing pushed commits, no deleting remote branches.
- 不提交 `.env*`、密钥/凭证/token、`node_modules`，以及大于 50MB 的文件（视频等大文件放 Google Drive）。 Never commit `.env*`, secrets, or files larger than 50MB.
- 不执行 `vercel --prod`；生产上线需要 Barron 明确批准。 Never run `vercel --prod`.
- Studio 每天 PT 02:30 由 launchd 作业 `com.barron.grok-runners.repo-autopush` 把未提交/未推送的改动备份到 `studio-sync` 分支（不推 main）；它是兜底，不替代上面的提交习惯。
<!-- AUTO-PUSH-RULES:END -->
