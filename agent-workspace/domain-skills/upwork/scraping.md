# Upwork — Public Job Posts (title, budget, experience, skills, client country, proposals)

Field-tested against www.upwork.com on 2026-10-23 using a Browser Use cloud browser.

robots.txt (checked 2026-10-23) allows `/freelance-jobs/` including `/freelance-jobs/apply/` (except `/freelance-jobs/fiction-writing/`) and `/o/jobs/browse/?q=` for all user agents, and disallows `/nx/`, `/api*` and `/*?page=*`.

## Quick summary

- Public, logged-out job listings live at `/freelance-jobs/<skill-slug>/` (e.g. `/freelance-jobs/python/`). Each page embeds **30 jobs** in Nuxt's `__NUXT_DATA__` JSON, plus the open-job total for that skill (python: 1,631; web-scraping: 291 on 2026-10-23). The 30 are a recent window sorted oldest-first, not the 30 newest (see Gotchas), and there is no page 2.
- Each job links to a public detail page `/freelance-jobs/apply/<slug>_~<id>/` whose `__NUXT_DATA__` has the fields the listing lacks: **client country** (`buyer.location.country`), **exact proposals count** (`job.clientActivity.totalApplicants`), hourly range, full skill list.
- Plain HTTP is blocked (status 403, Cloudflare challenge page); this skill uses a normal browser session and reads `__NUXT_DATA__` from each loaded page.
- Scale = many skill pages, not deep pagination. The hub `/freelance-jobs/` lists 482 skill pages.
- Stay on `/freelance-jobs/`; `/nx/` (the logged-in search UI) is robots-disallowed.

Field run: 2 skill pages (web-scraping, python) -> 60 cards -> 57 unique jobs, 56 with detail data, in about 5.5 minutes at 2 s pacing. The one miss is a private listing that returns 403 (`detail_error` set, country/proposals `null`).

## What works

### 0. Shared helpers (run before block 1 or 2, in the same script)

Browser-harness script (`new_tab`, `goto_url`, `js` are pre-imported). `open_page` navigates one tab, waits until it shows that URL's finished document, and returns `(http_status, decoded __NUXT_DATA__)`. A challenge page or a 429 raises `Blocked`: stop and back off, nothing is retried.

```python
import json, time
from urllib.parse import quote, urlsplit

BASE = "https://www.upwork.com"
WRAPPERS = ("ShallowReactive", "Reactive", "Ref", "ShallowRef")
STATE = ("JSON.stringify([location.pathname, document.readyState, document.title,"
         " (performance.getEntriesByType('navigation')[0] || {}).responseStatus || 0,"
         " !!document.getElementById('__NUXT_DATA__')])")

class Blocked(Exception):
    """Challenge page, 429, or repeated 403s: stop the run and back off. Never retried."""

def text(v):
    return v if isinstance(v, str) and v else None

def num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

def dget(d, *keys):
    for k in keys:
        d = d.get(k) if isinstance(d, dict) else None
    return d

def decode_nuxt(raw):
    """Decode Nuxt 3 __NUXT_DATA__ (devalue format: one flat array, dict/list values are indexes into it)."""
    flat, memo = json.loads(raw), {}
    def ref(i):
        if not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(flat):   # -1 undefined, -2 null
            return None
        if i not in memo:
            v = flat[i]
            if isinstance(v, list):
                memo[i] = ref(v[1]) if len(v) == 2 and v[0] in WRAPPERS else [ref(x) for x in v]
            elif isinstance(v, dict):
                memo[i] = {k: ref(x) for k, x in v.items()}
            else:
                memo[i] = v
        return memo[i]
    return ref(0)

_tab = {"open": False}

def open_page(url, timeout=30):
    """Navigate, wait for THIS url's complete document, return (http_status, payload or None)."""
    if _tab["open"]:
        goto_url(url)
    else:
        new_tab(url)
        _tab["open"] = True
    want = urlsplit(url).path.rstrip("/")
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(0.5)
        try:
            path, ready, title, status, has_data = json.loads(js(STATE))
        except (TimeoutError, RuntimeError) as e:   # js() can time out while a large page parses
            if isinstance(e, TimeoutError) or "timed out" in str(e):
                continue
            raise
        if path.rstrip("/") != want or ready != "complete":
            continue
        if status == 429 or "Just a moment" in title or (status == 403 and not has_data):
            raise Blocked(f"HTTP {status} {title!r} at {url}")   # challenge or rate limit: stop
        raw = js("(document.getElementById('__NUXT_DATA__') || {}).textContent || ''") if has_data else ""
        return status, decode_nuxt(raw) if isinstance(raw, str) and raw else None
    raise RuntimeError(f"{url} did not load in {timeout} s; tab is at {js('location.href')}")
```

### 1. Scrape 2+ skill pages and enrich every job from its detail page

Run block 0 first in the same script. A full run writes `upwork_jobs.jsonl`. If `Blocked` stops the run, the jobs read so far go to `upwork_jobs.partial.jsonl` instead, the block prints a `PARTIAL:` line and re-raises `Blocked`, so a stopped run never looks like a full one. Any other error (a skill page that cannot be read) raises before anything is written.

```python
TIER = {1: "Entry level", 2: "Intermediate", 3: "Expert"}   # 0 = not specified
JOB_TYPE = {1: "Fixed-price", 2: "Hourly"}

def skill_page(slug):
    """One /freelance-jobs/<slug>/ page: its 30 jobs + the category's open-job total. Raises on failure."""
    url = f"{BASE}/freelance-jobs/{quote(slug, safe='')}/"
    status, payload = open_page(url)
    if status != 200:
        raise RuntimeError(f"HTTP {status} on {url}")
    for v in (dget(payload, "data") or {}).values():
        if isinstance(v, dict) and isinstance(v.get("jobs"), list) and "totalJobs" in v:
            return v["jobs"], num(v["totalJobs"])
    raise RuntimeError(f"no job list in __NUXT_DATA__ on {url}")

def job_detail(path):
    """Returns (jobDetails dict, error string or None). A miss is explicit, never silent."""
    try:
        status, payload = open_page(BASE + quote(path, safe="/%"))
    except RuntimeError as e:   # page did not finish loading; Blocked is not caught here
        return {}, f"did not load: {e}"
    if status != 200:
        return {}, f"HTTP {status}"
    jd = dget(payload, "vuex", "jobDetails")
    return (jd, None) if isinstance(dget(jd, "job"), dict) else ({}, "no jobDetails in page")

def iso_utc(v):
    s = text(v)   # detail uses "...Z"; the card fallback uses "+0000"
    return s[:-5] + "Z" if s and s.endswith("+0000") else s

def to_record(card, jd, err):
    job, buyer = dget(jd, "job") or {}, dget(jd, "buyer") or {}
    jtype = num(job.get("type")) or num(card.get("type"))
    tier = num(job.get("contractorTier"))
    tier = num(card.get("contractorTier")) if tier is None else tier
    fixed = num(dget(job, "budget", "amount"))
    fixed = num(dget(card, "amount", "amount")) if fixed is None else fixed
    skills = [dget(s, "prefLabel") for s in card.get("ontologySkills") or []]
    skills += [dget(s, "name") for s in dget(jd, "sands", "additionalSkills") or []]
    return {
        "id": text(card.get("ciphertext")),
        "title": text(job.get("title")) or text(card.get("title")),
        "posted_on": iso_utc(job.get("postedOn")) or iso_utc(card.get("createdOn")),
        "posted_ago": text(card.get("ago")),
        "job_type": JOB_TYPE.get(jtype),
        "fixed_budget": fixed if jtype == 1 else None,
        "hourly_min": num(dget(job, "extendedBudgetInfo", "hourlyBudgetMin")) if jtype == 2 else None,
        "hourly_max": num(dget(job, "extendedBudgetInfo", "hourlyBudgetMax")) if jtype == 2 else None,
        "experience_level": TIER.get(tier),
        "skills": list(dict.fromkeys(s for s in skills if text(s))),
        "client_country": text(dget(buyer, "location", "country")),
        "proposals": num(dget(job, "clientActivity", "totalApplicants")),
        "workload": text(job.get("workload")) or text(card.get("engagement")),
        "duration": text(job.get("durationLabel")) or text(card.get("durationLabel")),
        "url": BASE + card["url"],
        "detail_error": err,
    }

SKILLS = ["web-scraping", "python"]      # each slug = 1 listing page + up to 30 detail pages
rows, seen, streak, stopped = [], set(), 0, None
try:
    for slug in SKILLS:
        cards, total = skill_page(slug)  # raises if the listing cannot be read
        print(f"{slug}: {len(cards)} cards of {total} open jobs (no page 2 exists; the rest are not reachable logged out)")
        time.sleep(2)
        for card in cards:
            if not isinstance(card, dict) or not text(card.get("url")):
                print("  card without url, skipped:", card)
                continue
            key = text(card.get("ciphertext")) or card["url"]   # never drop a card just because its id is missing
            if key in seen:
                continue
            seen.add(key)
            jd, err = job_detail(card["url"])
            if err:
                print("  detail failed:", err, card["url"])
            rows.append(to_record(card, jd, err))
            streak = streak + 1 if err == "HTTP 403" else 0
            if streak >= 2:              # one 403 = private listing; two in a row = treat as a block
                raise Blocked(f"2 detail pages in a row returned 403 (last: {card['url']})")
            time.sleep(2)                # polite pacing: ~1 page per 2-4 s
except Blocked as e:
    stopped = e
    print("STOPPED, back off before retrying:", e)

OUT = "upwork_jobs.partial.jsonl" if stopped else "upwork_jobs.jsonl"   # a stopped run never writes the full-run name
with open(OUT, "w") as f:
    for r in rows:
        f.write(json.dumps(r) + "\n")
print(len(rows), "jobs saved to", OUT + ";", sum(r["detail_error"] is not None for r in rows), "without detail data")
print(json.dumps(rows[:2], indent=1))
print("missing country:", sum(r["client_country"] is None for r in rows),
      "missing proposals:", sum(r["proposals"] is None for r in rows))
if stopped:
    print(f"PARTIAL: the run stopped early; {len(rows)} jobs in {OUT} are not all of {SKILLS}")
    raise stopped
```

Observed output (trimmed):

```text
web-scraping: 30 cards of 291 open jobs (no page 2 exists; the rest are not reachable logged out)
python: 30 cards of 1631 open jobs (no page 2 exists; the rest are not reachable logged out)
  detail failed: HTTP 403 /freelance-jobs/apply/Port-Viva-com-payment-module-Odoo-and-add-ISV-key_~022113260749740632003/
57 jobs saved to upwork_jobs.jsonl; 1 without detail data
[
 {
  "id": "~022112614550818987209",
  "title": "E-commerce Product Monitoring System",
  "posted_on": "2026-10-20T18:38:54.416Z",
  "posted_ago": "3 days ago",
  "job_type": "Fixed-price",
  "fixed_budget": 100,
  "hourly_min": null,
  "hourly_max": null,
  "experience_level": "Intermediate",
  "skills": ["Selenium", "Data Scraping", "HTML", "Python", "Web Scraping", "Web Scraping Framework", "Playwright", "Data Extraction", "AI Agents", "pandas"],
  "client_country": "IND",
  "proposals": 26,
  "workload": null,
  "duration": "1 to 3 months",
  "url": "https://www.upwork.com/freelance-jobs/apply/commerce-Product-Monitoring-System_~022112614550818987209/",
  "detail_error": null
 },
 ...
]
missing country: 1 missing proposals: 1
```

The stop path was checked locally with this block's code and a stubbed `open_page` that raised `Blocked` on the 3rd detail page: 2 jobs went to `upwork_jobs.partial.jsonl`, no `upwork_jobs.jsonl` was written, and the block printed `PARTIAL:` and re-raised `Blocked`.

Distribution: 31 fixed-price / 26 hourly; Intermediate 34, Expert 19, Entry level 3, unspecified 1; proposals ranged 0 to 660.

### 2. Turn a keyword into skill slugs (the robots-allowed "search")

There is no public keyword search with pagination under `/freelance-jobs/`. The hub page `/freelance-jobs/` embeds the 482 skill pages it links to (`id`, `url`, `title`). Match your keyword against them (capped at `max_slugs`, default 5), then feed the slugs to block 1. Run block 0 first in the same script.

```python
ROBOTS_DISALLOWED = {"fiction-writing"}   # robots.txt: Disallow: /freelance-jobs/fiction-writing/

status, payload = open_page(f"{BASE}/freelance-jobs/")
skill_pages = None
for v in (dget(payload, "data") or {}).values():
    if isinstance(v, dict) and "categories" in v and isinstance(v.get("jobs"), list):
        skill_pages = [p for p in v["jobs"] if isinstance(p, dict) and text(p.get("id"))]
if not skill_pages:
    raise RuntimeError(f"HTTP {status}: skill list not found in __NUXT_DATA__ on {BASE}/freelance-jobs/")
print(len(skill_pages), "skill listing pages")

def find_skill_slugs(keyword, max_slugs=5):
    """Capped: each slug costs block 1 up to 31 page loads (~2 min at 2 s pacing)."""
    kw = keyword.lower().strip()
    return [p["id"] for p in skill_pages
            if p["id"] not in ROBOTS_DISALLOWED
            and (kw in p["id"].replace("-", " ") or kw in (text(p.get("title")) or "").lower())][:max_slugs]

for kw in ["scraping", "react", "data entry", "python", "design"]:
    print(kw, "->", find_skill_slugs(kw))
```

Observed output:

```text
482 skill listing pages
scraping -> ['data-scraping', 'web-scraping']
react -> ['react-js', 'react-native']
data entry -> ['data-entry']
python -> ['python-script', 'python']
design -> ['visual-design', 'packaging-design', 'social-media-design', 'book-design', 'adobe-indesign']
```

Opening `https://www.upwork.com/o/jobs/browse/?q=<keyword>` (URL-encode the keyword with `quote(kw, safe='')`) in the browser redirected to the matching skill page for known skills (`shopify` -> `/freelance-jobs/shopify/`, `data entry` -> `/freelance-jobs/data-entry/`, `react native` -> `/freelance-jobs/react-native/`); a nonsense query (`zzqxv`) showed a Cloudflare "Worker threw exception" page instead.

## Fields

Block 1 returns one dict per job with exactly these keys. Listing card = item in the skill page's `data[...].jobs`. Detail = `vuex.jobDetails` on the job page.

| Output field | Source | Notes |
|---|---|---|
| `id` | card `ciphertext` | e.g. `~022112614550818987209`; used to dedupe across skill pages (falls back to `url` if missing) |
| `title` | detail `job.title` / card `title` | |
| `posted_on` | detail `job.postedOn` (fallback card `createdOn`) | ISO UTC; the card's `+0000` suffix is rewritten to `Z`. Card has `renewedOn` (`null` unless renewed) |
| `posted_ago` | card `ago` | e.g. `"1 day ago"`, `"9 hours ago"` |
| `job_type` | `type` | `1` = Fixed-price, `2` = Hourly |
| `fixed_budget` | detail `job.budget.amount` / card `amount.amount` | USD, fixed-price only (`null` for hourly; card `amount.amount` is `0` there) |
| `hourly_min`, `hourly_max` | detail `job.extendedBudgetInfo.hourlyBudgetMin/Max` | Hourly only; `null` when the job sets no range. Not read from the card |
| `experience_level` | `contractorTier` | `1` Entry level, `2` Intermediate, `3` Expert, `0` not specified -> `null` (labels checked against the rendered page) |
| `skills` | card `ontologySkills[].prefLabel` + detail `sands.additionalSkills[].name` | Detail adds skills the page hides behind "+ N more" |
| `client_country` | detail `buyer.location.country` | Not on listing cards. Mixed formats, see Gotchas |
| `proposals` | detail `job.clientActivity.totalApplicants` | Exact integer. The page shows a bucket such as "20 to 50" |
| `workload` | detail `job.workload` / card `engagement` | `null` on fixed-price jobs |
| `duration` | `durationLabel` | e.g. `"1 to 3 months"` |
| `url` | `https://www.upwork.com` + card `url` | `/freelance-jobs/apply/<slug>_~<ciphertext>/` |
| `detail_error` | | `null` when the detail page was read; else why not (`"HTTP 403"`, `"no jobDetails in page"`, `"did not load: ..."`). Country, proposals and hourly range are `null` then |

Also present but not returned: detail `job.clientActivity` has `totalHired`, `totalInvitedToInterview`, `invitationsSent`, `unansweredInvites`, `lastBuyerActivity`; `buyer.stats` has `totalCharges.amount` (client spend), `totalAssignments`, `score`; plus `job.category.name`, `job.description`. Card `maxAmount.amount` is the max hourly rate (`-1` when unset).

## Gotchas

- **30 jobs per skill page, oldest-first, no page 2.** Cards come in ascending `createdOn` order (one swap per page seen). The 27 python jobs not also on web-scraping were all posted 2026-10-22 04:58-15:06 UTC although the category has 1,631 open jobs; web-scraping (291) spanned 2026-10-20 18:38 to 2026-10-23 09:03. So a big category is not shown as its 30 newest jobs. `/freelance-jobs/python/2/` returned 404, and `?page=` is robots-disallowed. To get more jobs, scrape more skill slugs and dedupe on `id` (web-scraping and python shared 3 jobs).
- **"Load more jobs" only reveals what is already embedded.** The rendered python page showed 10 cards; one click on "Load more jobs" showed 20 and the button disappeared. No new job request was made and all shown ids were among the 30 in `__NUXT_DATA__`. The data-entry page rendered all 30 with no button. Read the payload, not the DOM.
- **Client country formats are mixed in the source**, and the page renders them as-is: full names (`"United States"`, `"India"`) and 3-letter codes (`"USA"`, `"IND"`, `"CAN"`, `"GBR"`) appeared in the same run. Normalize if you group by country.
- **JSON-LD is misleading for country.** The detail page's `JobPosting` JSON-LD had `jobLocation.address.addressCountry: "US"` for a client located in India. Use `buyer.location.country`.
- **Private listings return 403 with a normal Upwork page.** One job (`...Port-Viva-com-payment-module-Odoo-and-add-ISV-key_~022113260749740632003/`) loaded in the browser with navigation status 403, a `__NUXT_DATA__` payload and the text "This job is a private listing." Block 1 keeps its card-level fields, sets `detail_error: "HTTP 403"` and moves on. A 403 page without `__NUXT_DATA__`, a "Just a moment" title, a 429, or two 403s in a row raise `Blocked` and stop the run: block 1 saves what it has to `upwork_jobs.partial.jsonl`, prints `PARTIAL:` and re-raises.
- **No consent banner or login wall** appeared on `/freelance-jobs/` pages in the cloud browser.
- The HTTP status comes from `performance.getEntriesByType('navigation')[0].responseStatus` (Chrome 109+).
- `js()` calls time out after 5 s, so do not run slow multi-request `fetch()` loops inside the page; navigate instead.
- Pages are large (~1.0-1.4 MB HTML each). Keep 2-3 s between page loads; the 60-page runs at that pace saw no 429.

## What does not work

- **Plain HTTP** (`urllib` with a truthful client User-Agent): blocked (status 403, Cloudflare challenge page titled "Challenge - Upwork") on 2026-10-23 for `/freelance-jobs/` and `/freelance-jobs/python/`. Not used; this skill uses a normal browser session.
- **`/nx/search/jobs/?q=...` (the real search UI)**: disallowed by `robots.txt`; not used.
- **`/sitemap.xml`**: plain HTTP is blocked (status 403); not used.
- **`?page=N` on skill pages**: disallowed by `robots.txt` (`/*?page=*`); not used.
- **Getting more than 30 jobs from one skill page**: not possible logged out. There is no page 2, and "Load more jobs" does not fetch beyond the 30 embedded jobs.
- **Freelancer profiles**: out of scope here (`/freelancers/public/api/` and `/search/profiles/*` are disallowed by `robots.txt`).
