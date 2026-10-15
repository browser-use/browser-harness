# GitHub - PR and Issue Triage

`https://github.com/{owner}/{repo}/pulls` and `/issues` - read-only triage for
public repositories. Use this when choosing a small contribution, checking
whether a PR is duplicate, or estimating a pull request's scope before review.

## Do this first

**Use the REST API as the source of truth.** The GitHub PR and issue list pages
contain duplicate/auxiliary DOM rows, while the API returns parsed JSON and
works without logging in for public repos.

```python
import json, os

owner = "browser-use"
repo = "browser-harness"
base = f"https://api.github.com/repos/{owner}/{repo}"
token = os.environ.get("GITHUB_TOKEN", "")
headers = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}
if token:
    headers["Authorization"] = f"Bearer {token}"

rate = json.loads(http_get("https://api.github.com/rate_limit", headers=headers))
print(rate["resources"]["core"]["remaining"], rate["resources"]["search"]["remaining"])
```

Use the browser after the API pass only when you need a visual screenshot,
hydrated labels, or manual confirmation of the GitHub page state.

## Common workflows

### PR shortlist (API)

Use `/pulls` for pull requests. Do **not** use `/issues` for a PR shortlist:
GitHub's issues endpoint includes both issues and pull requests.

```python
import json

pulls = json.loads(http_get(
    base + "/pulls?state=open&sort=updated&direction=desc&per_page=20",
    headers=headers,
))

shortlist = []
for pr in pulls:
    shortlist.append({
        "number": pr["number"],
        "title": pr["title"],
        "user": pr["user"]["login"],
        "draft": pr["draft"],
        "updated_at": pr["updated_at"],
        "head_sha": pr["head"]["sha"],
        "base_ref": pr["base"]["ref"],
        "html_url": pr["html_url"],
    })
print(shortlist)
```

Triage signal:
- `draft=True` means do not treat the PR as ready for review.
- `base_ref` should usually be the repository default branch.
- `updated_at` helps find active duplicates before starting a similar PR.

### Pull request detail and files (API)

Fetch PR detail and file changes together. This gives the fastest answer to
"is this PR small and focused?".

```python
import json

pull_number = 481
detail = json.loads(http_get(base + f"/pulls/{pull_number}", headers=headers))
files = json.loads(http_get(
    base + f"/pulls/{pull_number}/files?per_page=100",
    headers=headers,
))

summary = {
    "number": detail["number"],
    "title": detail["title"],
    "state": detail["state"],
    "draft": detail["draft"],
    "mergeable": detail["mergeable"],
    "mergeable_state": detail["mergeable_state"],
    "commits": detail["commits"],
    "additions": detail["additions"],
    "deletions": detail["deletions"],
    "changed_files": detail["changed_files"],
    "issue_comments": detail["comments"],
    "review_comments": detail["review_comments"],
}
changed = [{
    "filename": f["filename"],
    "status": f["status"],
    "changes": f["changes"],
    "additions": f["additions"],
    "deletions": f["deletions"],
} for f in files]
print(summary)
print(changed)
```

For review conversation:

```python
issue_comments = json.loads(http_get(
    base + f"/issues/{pull_number}/comments?per_page=50",
    headers=headers,
))
review_comments = json.loads(http_get(
    base + f"/pulls/{pull_number}/comments?per_page=50",
    headers=headers,
))
reviews = json.loads(http_get(
    base + f"/pulls/{pull_number}/reviews?per_page=50",
    headers=headers,
))
```

For CI/check state, use the PR head SHA:

```python
head_sha = detail["head"]["sha"]
checks = json.loads(http_get(
    base + f"/commits/{head_sha}/check-runs?per_page=50",
    headers=headers,
))
runs = checks.get("check_runs", [])
print([{
    "name": r["name"],
    "status": r["status"],
    "conclusion": r["conclusion"],
    "html_url": r["html_url"],
} for r in runs])
```

Reference path: `/commits/{head_sha}/check-runs`.

### Issue duplicate check (API)

Use `/issues` to list open issues, and GitHub search to check whether your PR
idea already exists in issues or PRs.

```python
import json

items = json.loads(http_get(
    base + "/issues?state=open&sort=updated&direction=desc&per_page=50",
    headers=headers,
))

issues = []
prs_in_issue_feed = []
for item in items:
    target = prs_in_issue_feed if "pull_request" in item else issues
    target.append({
        "number": item["number"],
        "title": item["title"],
        "user": item["user"]["login"],
        "labels": [label["name"] for label in item.get("labels", [])],
        "comments": item["comments"],
        "updated_at": item["updated_at"],
        "html_url": item["html_url"],
    })
print("issues", issues)
print("prs mixed into /issues", prs_in_issue_feed)
```

Search for duplicates before starting a PR:

```python
import json, urllib.parse

query = f"repo:{owner}/{repo} github triage in:title,body is:open"
url = "https://api.github.com/search/issues?q=" + urllib.parse.quote(query) + "&per_page=10"
results = json.loads(http_get(url, headers=headers))
for item in results["items"]:
    kind = "PR" if "pull_request" in item else "ISSUE"
    print(kind, item["number"], item["title"], item["html_url"])
```

For a specific issue's discussion:

```python
issue_number = 479
comments = json.loads(http_get(
    base + f"/issues/{issue_number}/comments?per_page=50",
    headers=headers,
))
print([{"user": c["user"]["login"], "created_at": c["created_at"], "body": c["body"][:200]} for c in comments])
```

Reference path: `/issues/{issue_number}/comments`.

### Browser verification

Use browser navigation only after API triage, usually to capture a screenshot or
confirm the visible list. Keep navigation, wait, extraction, and screenshot in
the same `browser-harness` invocation.

```python
import json

new_tab("https://github.com/browser-use/browser-harness/pulls")
wait_for_load()
wait(2)
rows = json.loads(js(r"""
JSON.stringify(Array.from(document.querySelectorAll('[id^="issue_"]')).map(row => {
  const link = row.querySelector('a[href*="/pull/"]');
  const meta = row.querySelector('.opened-by');
  const labels = Array.from(row.querySelectorAll('a.IssueLabel, span.IssueLabel'))
    .map(x => x.textContent.trim())
    .filter(Boolean);
  return {
    title: link ? link.textContent.trim().replace(/\s+/g, ' ') : null,
    href: link ? link.href : null,
    meta: meta ? meta.textContent.trim().replace(/\s+/g, ' ') : null,
    labels: labels
  };
}).filter(row => row.title && row.href))
"""))
print(rows[:10])
print(capture_screenshot())
```

If browser rows disagree with the API, trust the API and use the browser output
only as visual evidence.

### Quick triage rubric

```python
def classify_pr(detail, files, checks):
    paths = [f["filename"] for f in files]
    runs = checks.get("check_runs", [])
    completed_runs = [r for r in runs if r.get("status") == "completed"]
    return {
        "small": detail["changed_files"] <= 3 and detail["additions"] + detail["deletions"] <= 300,
        "docs_or_skill_only": bool(paths) and all(p.endswith(".md") or "/domain-skills/" in p for p in paths),
        "has_tests_or_docs": any(p.startswith("tests/") or p.endswith(".md") for p in paths),
        "checks_green": bool(runs) and len(completed_runs) == len(runs) and all(
            r.get("conclusion") in {"success", "skipped"} for r in completed_runs
        ),
        "paths": paths,
    }
```

Use this as a rough screen, not a merge decision. For contribution planning,
prefer small PRs with a narrow path set, concrete evidence, and no open duplicate
PR touching the same files.

## Gotchas

- **`/issues` includes PRs.** Any item with a `pull_request` key is a PR, not a
  standalone issue. Use `/pulls?state=open` for a PR list.

- **Search is rate-limited separately.** Unauthenticated search is only
  10 requests/minute. Core REST is 60 requests/hour. Check `/rate_limit` before
  looping.

- **`mergeable` can be `null`.** GitHub computes it asynchronously. If it is
  `null`, wait briefly and refetch `/pulls/{pull_number}`.

- **Changed files are paginated.** `/pulls/{pull_number}/files?per_page=100`
  returns at most 100 files per page. Follow pagination headers for large PRs.

- **Check runs hang off the head commit.** First fetch PR detail, then call
  `/commits/{head_sha}/check-runs`. Branch names are not enough.

- **Issue comments and review comments are different.** `/issues/{n}/comments`
  contains timeline discussion. `/pulls/{n}/comments` contains inline code review
  comments. Fetch both when reviewing PR state.

- **Browser DOM rows are noisy.** The PR list can include duplicate or auxiliary
  rows under `[id^="issue_"]`; filter out rows without a title and href. API data
  is cleaner.

- **Logged-in UI may differ.** The visible page can include reviewer controls,
  subscribed state, or private affordances that do not appear for logged-out
  users. Do not bake those into a public-data triage skill.

## Provenance

Validated on 2026-07-03 against `browser-use/browser-harness` using
`browser-harness` attached to local Chrome:

- `/pulls?state=open&sort=updated&direction=desc&per_page=5` returned open PRs.
- `/pulls/{pull_number}` exposed `draft`, `mergeable_state`, `changed_files`,
  `additions`, `deletions`, `comments`, and `review_comments`.
- `/pulls/{pull_number}/files` returned filenames, statuses, and change counts.
- `/issues/{pull_number}/comments`, `/pulls/{pull_number}/comments`, and
  `/commits/{head_sha}/check-runs` returned PR discussion/check data.
- Browser verification on `/pulls` produced visible PR rows, but also confirmed
  noisy DOM rows, so the API remains the primary path.
