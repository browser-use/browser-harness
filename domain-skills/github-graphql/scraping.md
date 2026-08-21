# GitHub GraphQL API v4 — Scraping & Data Extraction

`https://api.github.com/graphql` — GitHub's GraphQL API. **Requires a token for every call** — `graphql.limit` is 0 for unauthenticated requests (confirmed 2026-04-18). All data is available over a single `POST` with no browser needed.

## Do this first

**Always check for a token before anything else. Every GraphQL call fails without one.**

```python
import os, json, urllib.request, ssl

token = os.environ.get('GITHUB_TOKEN', '')
if not token:
    raise RuntimeError("GITHUB_TOKEN not set — GitHub GraphQL requires authentication")

GRAPHQL_URL = "https://api.github.com/graphql"
HEADERS = {
    "Authorization": f"bearer {token}",
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0",
    "X-Github-Next-Global-ID": "1",   # opt-in to new global Node IDs
}

def gql(query, variables=None):
    """Execute a GraphQL query. Returns parsed response dict."""
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(GRAPHQL_URL, data=body, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode())
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]
```

**When to use GraphQL v4 over REST v3:**
- Fetch multiple related objects in a single round-trip (e.g., repo + issues + PRs + labels)
- Need nested data (PR reviews, review comments, timeline events)
- Need exact field control (no over-fetching)
- Pagination with cursors (cleaner than REST `Link` headers)
- Repository contributions, project boards, discussions
- Real-time rate limit cost inspection via `rateLimit` field

**When to stick with REST v3 (see `github/scraping.md`):**
- Simple single-object fetches (repo metadata, user profile)
- No token available
- Trending page (browser only)
- Bulk file content via `raw.githubusercontent.com`

---

## Rate limits

GraphQL uses a **point-based** system, not a request count:

| Account type | Points/hour |
|---|---|
| Authenticated user | 5,000 |
| GitHub App (installation) | 15,000 |
| Unauthenticated | 0 (blocked) |

**Points per query = nodes requested** (approximately). A query returning 1 object costs 1 point; returning 100 items in a connection costs ~100 points. Add `rateLimit` to any query to inspect cost and remaining budget:

```python
RATE_LIMIT_FRAGMENT = """
rateLimit {
  cost
  remaining
  resetAt
  limit
  used
  nodeCount
}
"""
```

Check rate limit without consuming points:

```python
data = gql("""
{
  rateLimit {
    limit
    remaining
    resetAt
    used
  }
}
""")
print(data['rateLimit'])
# {'limit': 5000, 'remaining': 4987, 'resetAt': '2026-04-18T15:00:00Z', 'used': 13}
```

---

## Common workflows

### Repo metadata + stats (single call)

```python
data = gql("""
query RepoInfo($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    nameWithOwner
    description
    stargazerCount
    forkCount
    watcherCount: watchers { totalCount }
    openIssues: issues(states: OPEN) { totalCount }
    openPRs: pullRequests(states: OPEN) { totalCount }
    diskUsage
    isPrivate
    isFork
    isArchived
    defaultBranchRef { name }
    primaryLanguage { name }
    licenseInfo { name spdxId }
    createdAt
    pushedAt
    url
    homepageUrl
    topics: repositoryTopics(first: 10) {
      nodes { topic { name } }
    }
  }
  rateLimit { cost remaining }
}
""", {"owner": "browser-use", "name": "browser-use"})

repo = data['repository']
print(repo['stargazerCount'], repo['forkCount'])
print([n['topic']['name'] for n in repo['topics']['nodes']])
# Expected: stargazerCount=88400+, topics list
```

### Issues with labels and pagination

```python
def fetch_issues(owner, name, state="OPEN", first=20, after=None):
    data = gql("""
    query Issues($owner: String!, $name: String!, $state: IssueState!, $first: Int!, $after: String) {
      repository(owner: $owner, name: $name) {
        issues(states: [$state], first: $first, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
          pageInfo { hasNextPage endCursor }
          totalCount
          nodes {
            number
            title
            state
            createdAt
            closedAt
            author { login }
            labels(first: 10) { nodes { name color } }
            comments { totalCount }
            reactions { totalCount }
            url
          }
        }
      }
    }
    """, {"owner": owner, "name": name, "state": state, "first": first, "after": after})
    return data['repository']['issues']

# Paginate all open issues
all_issues = []
cursor = None
while True:
    result = fetch_issues("browser-use", "browser-use", after=cursor)
    all_issues.extend(result['nodes'])
    if not result['pageInfo']['hasNextPage']:
        break
    cursor = result['pageInfo']['endCursor']

print(f"Fetched {len(all_issues)} of {result['totalCount']} issues")
```

### Pull requests with review status

```python
data = gql("""
query PRs($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: [OPEN], first: 20, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes {
        number
        title
        state
        isDraft
        createdAt
        mergedAt
        author { login }
        headRefName
        baseRefName
        additions
        deletions
        changedFiles
        reviewDecision          # APPROVED | REVIEW_REQUIRED | CHANGES_REQUESTED
        reviews(first: 5) {
          nodes {
            author { login }
            state               # APPROVED | CHANGES_REQUESTED | COMMENTED
            submittedAt
            body
          }
        }
        labels(first: 5) { nodes { name } }
        comments { totalCount }
        url
      }
    }
  }
}
""", {"owner": "browser-use", "name": "browser-use"})

for pr in data['repository']['pullRequests']['nodes']:
    reviews = [r['state'] for r in pr['reviews']['nodes']]
    print(pr['number'], pr['reviewDecision'], pr['additions'], pr['deletions'], reviews)
```

### Repository search

```python
def search_repos(query_str, first=10, after=None):
    data = gql("""
    query SearchRepos($q: String!, $first: Int!, $after: String) {
      search(query: $q, type: REPOSITORY, first: $first, after: $after) {
        repositoryCount
        pageInfo { hasNextPage endCursor }
        nodes {
          ... on Repository {
            nameWithOwner
            stargazerCount
            forkCount
            description
            primaryLanguage { name }
            updatedAt
            url
          }
        }
      }
      rateLimit { cost remaining }
    }
    """, {"q": query_str, "first": first, "after": after})
    return data

result = search_repos("browser automation language:python stars:>500 sort:stars")
for repo in result['search']['nodes']:
    print(repo['nameWithOwner'], repo['stargazerCount'])
print("Query cost:", result['rateLimit']['cost'])

# Search query modifiers:
# language:python  stars:>100  forks:>50  pushed:>2025-01-01
# sort:stars  sort:forks  sort:updated  sort:interactions
# is:public  is:private  archived:false
# topic:machine-learning  license:mit
```

### User/org profile and contributions

```python
data = gql("""
query UserProfile($login: String!) {
  user(login: $login) {
    login
    name
    email
    bio
    company
    location
    websiteUrl
    twitterUsername
    followers { totalCount }
    following { totalCount }
    repositories(ownerAffiliations: OWNER) { totalCount }
    contributionsCollection {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      restrictedContributionsCount
    }
    sponsorshipsAsMaintainer { totalCount }
    createdAt
  }
}
""", {"login": "torvalds"})

user = data['user']
contribs = user['contributionsCollection']
print(user['name'], user['followers']['totalCount'])
print("Commits:", contribs['totalCommitContributions'])
print("PRs:", contribs['totalPullRequestContributions'])
```

### Commit history

```python
data = gql("""
query Commits($owner: String!, $name: String!, $branch: String!) {
  repository(owner: $owner, name: $name) {
    ref(qualifiedName: $branch) {
      target {
        ... on Commit {
          history(first: 20) {
            pageInfo { hasNextPage endCursor }
            nodes {
              oid
              messageHeadline
              message
              committedDate
              additions
              deletions
              changedFilesIfAvailable
              author {
                name
                email
                user { login }
              }
              committer {
                name
                email
              }
            }
          }
        }
      }
    }
  }
}
""", {"owner": "browser-use", "name": "browser-use", "branch": "main"})

history = data['repository']['ref']['target']['history']
for commit in history['nodes']:
    print(commit['oid'][:8], commit['committedDate'][:10], commit['messageHeadline'])
    print(f"  +{commit['additions']} -{commit['deletions']}")
```

### Repository stargazers (who starred)

```python
def fetch_stargazers(owner, name, first=100, after=None):
    data = gql("""
    query Stargazers($owner: String!, $name: String!, $first: Int!, $after: String) {
      repository(owner: $owner, name: $name) {
        stargazers(first: $first, after: $after, orderBy: {field: STARRED_AT, direction: DESC}) {
          pageInfo { hasNextPage endCursor }
          totalCount
          edges {
            starredAt
            node {
              login
              name
              followers { totalCount }
              company
              location
            }
          }
        }
      }
    }
    """, {"owner": owner, "name": name, "first": first, "after": after})
    return data['repository']['stargazers']

result = fetch_stargazers("browser-use", "browser-use")
print("Total stars:", result['totalCount'])
for edge in result['edges'][:5]:
    print(edge['starredAt'][:10], edge['node']['login'], edge['node']['followers']['totalCount'])
# Returns most recent stargazers first
```

### Fetch multiple repos in one query (batch)

```python
# Use aliases to fetch multiple repos in a single round-trip
data = gql("""
{
  repo1: repository(owner: "browser-use", name: "browser-use") {
    stargazerCount forkCount pushedAt
  }
  repo2: repository(owner: "microsoft", name: "playwright") {
    stargazerCount forkCount pushedAt
  }
  repo3: repository(owner: "puppeteer", name: "puppeteer") {
    stargazerCount forkCount pushedAt
  }
  rateLimit { cost remaining }
}
""")

for key in ["repo1", "repo2", "repo3"]:
    r = data[key]
    print(key, r['stargazerCount'], r['forkCount'])
print("Total cost:", data['rateLimit']['cost'])
# One query, one HTTP call, cost = 3 points (one per repo)
```

### Discussions (GitHub Discussions API)

```python
data = gql("""
query Discussions($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    discussions(first: 10, orderBy: {field: CREATED_AT, direction: DESC}) {
      totalCount
      nodes {
        number
        title
        createdAt
        author { login }
        category { name emoji }
        upvoteCount
        comments { totalCount }
        answerChosenAt
        answer { body author { login } }
        url
      }
    }
  }
}
""", {"owner": "browser-use", "name": "browser-use"})

for d in data['repository']['discussions']['nodes']:
    answered = "ANSWERED" if d['answer'] else "open"
    print(d['number'], answered, d['category']['name'], d['title'][:50])
```

### Labels for a repository

```python
data = gql("""
query Labels($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    labels(first: 50) {
      nodes { name color description issues { totalCount } }
    }
  }
}
""", {"owner": "browser-use", "name": "browser-use"})

for label in data['repository']['labels']['nodes']:
    print(f"#{label['color']} {label['name']}: {label['issues']['totalCount']} issues")
```

### Org members and repos

```python
data = gql("""
query OrgInfo($org: String!) {
  organization(login: $org) {
    name
    description
    membersWithRole { totalCount }
    repositories(first: 10, orderBy: {field: STARGAZERS, direction: DESC}) {
      totalCount
      nodes {
        nameWithOwner
        stargazerCount
        primaryLanguage { name }
        isPrivate
      }
    }
    teams(first: 5) {
      totalCount
      nodes { name slug members { totalCount } }
    }
  }
}
""", {"org": "browser-use"})

org = data['organization']
print(org['name'], "Members:", org['membersWithRole']['totalCount'])
for repo in org['repositories']['nodes']:
    print(" ", repo['nameWithOwner'], repo['stargazerCount'])
```

---

## Pagination pattern

GraphQL uses cursor-based pagination via `pageInfo`:

```python
def paginate_all(query_fn, extract_fn, max_pages=50):
    """Generic paginator. query_fn(after) -> raw data. extract_fn(data) -> (nodes, pageInfo)."""
    all_nodes = []
    cursor = None
    for _ in range(max_pages):
        data = query_fn(after=cursor)
        nodes, page_info = extract_fn(data)
        all_nodes.extend(nodes)
        if not page_info['hasNextPage']:
            break
        cursor = page_info['endCursor']
    return all_nodes

# Example: all open issues
issues = paginate_all(
    query_fn=lambda after: gql("""
        query($owner:String!,$name:String!,$after:String){
          repository(owner:$owner, name:$name){
            issues(states:OPEN, first:100, after:$after){
              pageInfo{hasNextPage endCursor}
              nodes{number title createdAt}
            }
          }
        }
    """, {"owner": "browser-use", "name": "browser-use", "after": after}),
    extract_fn=lambda d: (
        d['repository']['issues']['nodes'],
        d['repository']['issues']['pageInfo']
    )
)
```

Key pagination rules:
- Max `first:` value is **100** for most connections (some allow 100+)
- `after:` takes the `endCursor` string from the previous response
- `before:` / `last:` paginate backwards
- Never use `offset` — GraphQL connections are cursor-only

---

## Introspection (explore the schema)

```python
# List all top-level query fields
data = gql("""
{
  __schema {
    queryType { fields { name description } }
  }
}
""")
for f in data['__schema']['queryType']['fields']:
    print(f['name'], '-', f['description'][:60] if f['description'] else '')

# Inspect a specific type
data = gql("""
{
  __type(name: "Repository") {
    fields {
      name
      description
      type { name kind ofType { name kind } }
    }
  }
}
""")
for f in data['__type']['fields'][:20]:
    print(f['name'], f['type'])
```

---

## Gotchas

- **GraphQL requires auth — no anonymous access.** Unlike REST (60 req/hr unauthenticated), `graphql.limit = 0` without a token. Every call returns HTTP 403. Confirmed 2026-04-18 via `https://api.github.com/rate_limit` → `"graphql": {"limit": 0}`.

- **`bearer` not `Bearer` or `token`** — The `Authorization` header value must be `bearer {token}` (lowercase `bearer`). GitHub's REST API accepts `Bearer` (capital B) but for GraphQL, `bearer` is the documented form. Both work in practice but match the docs.

- **Point cost ≠ request count** — `rateLimit.cost` is charged per call regardless of whether the query returns data. A query for a nonexistent repo still costs 1 point. Always add `rateLimit { cost remaining }` to debug expensive queries.

- **Connections have a max `first:` of 100** — Most connections (`issues`, `pullRequests`, `stargazers`, etc.) reject `first: 101+` with a validation error: `"first" argument must not exceed 100`. Use pagination for large sets.

- **`... on TypeName` fragments required for union/interface fields** — `search()` returns `SearchResultItemConnection` where nodes are a union. Without `... on Repository { ... }`, `nodes` returns empty objects. Same applies to `ref.target` (`... on Commit { ... }`), timeline items, and actor unions.

- **Inline fragments do NOT merge with sibling fields** — If a node is `... on Commit` it will not expose `... on Tree` fields. Only one fragment matches per node.

- **Null vs missing field** — GraphQL returns `null` for nullable fields that have no value (e.g. `closedAt` on an open issue, `email` when hidden). Missing non-nullable fields cause an error at query compile time, not runtime.

- **`author` can be null for deleted accounts** — On commits, issues, and PRs, `author { login }` returns `null` if the account was deleted. Always guard: `commit.get('author') or {}`.

- **`changedFilesIfAvailable` vs `changedFiles`** — Old `changedFiles` field on `Commit` is deprecated; use `changedFilesIfAvailable` which returns `null` for very large diffs (GitHub doesn't compute diff stats for commits touching >1000 files).

- **Search rate limit is separate from GraphQL** — The `search()` query type has an internal abuse limit of ~30 search queries/minute in addition to the 5000 point/hr pool. Space search calls out if running many in a loop.

- **`contributionsCollection` defaults to the current year** — Without `from`/`to` arguments it returns contributions for the past year from the calling date. Specify `contributionsCollection(from: "2025-01-01T00:00:00Z", to: "2025-12-31T23:59:59Z")` for a specific year.

- **Private repo fields require appropriate scopes** — Token needs `repo` scope for private content. With only `public_repo`, private repos return `null` or are omitted from results, not an error.

- **Variables must match declared types exactly** — A query declaring `$first: Int!` will error if you pass `first: "20"` (a string). Always pass Python `int`, not `str`, for `Int` variables.

- **`X-Github-Next-Global-ID: 1` header** — GitHub is migrating to new-format node IDs. Add this header to get the new format proactively. Without it, some IDs returned are legacy format. Doesn't affect query results.

- **Errors array vs HTTP error codes** — GraphQL always returns HTTP 200 even for partial errors. Check `data.get('errors')` — it can co-exist with `data.get('data')` for partial success (some fields returned, some errored). The `gql()` helper above raises on any errors; adjust if you want partial results.

- **Rate limit resets hourly, not per-minute** — The `resetAt` timestamp is always ~1 hour from first use. There's no per-minute sub-limit for non-search GraphQL queries. If you hit 0 remaining, wait until `resetAt`.
