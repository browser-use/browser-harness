# BOSS直聘 — Job Search & Extraction

Field-tested against zhipin.com on 2026-05-01.
Login required for API access; job browsing is accessible without auth.

---

## Anti-bot / API verdict

BOSS直聘 is a Vue SPA. There is no SSR JSON blob (`__NEXT_DATA__`, `__INITIAL_STATE__`, etc.) — all data loads via XHR/fetch to internal `/wapi/` endpoints.

**`http_get` does NOT work** — the `/wapi/` endpoints require browser session cookies (not just a CSRF token). All API calls must be made via `js()` + `fetch()` inside the browser session.

**However, the API returns real salary numbers** (`"salaryDesc": "18-22K"`) unlike the DOM which renders salary digits via a custom `@font-face` with private-use Unicode characters (U+E000–U+F8FF). **Always prefer the API over DOM extraction.**

---

## Quickstart

```python
import json

goto_url("https://www.zhipin.com/web/geek/jobs?ka=open_joblist")
wait_for_load()
wait(3)

jobs = json.loads(js("""
(async function() {
    var r = await fetch('/wapi/zpgeek/pc/recommend/job/list.json?page=1&pageSize=15&city=101020100');
    var d = await r.json();
    return JSON.stringify(d.zpData.jobList);
})()
"""))

for j in jobs:
    print(j["salaryDesc"], j["jobName"], "|", j["brandName"])
```

---

## URL Patterns

| Resource | URL |
|----------|-----|
| Job search page | `https://www.zhipin.com/web/geek/jobs` |
| Job search (with prefs) | `https://www.zhipin.com/web/geek/jobs?ka=open_joblist` |
| Job detail page | `https://www.zhipin.com/job_detail/{JOB_ID}.html` |
| Company page | `https://www.zhipin.com/gongsi/{COMPANY_ID}~.html` |

---

## API: Job List

```
GET /wapi/zpgeek/pc/recommend/job/list.json
```

### Query Parameters

| Param | Description | Values |
|-------|-------------|--------|
| `page` | Page number | 1-N |
| `pageSize` | Results per page | 15 (default) |
| `city` | City code | `101020100` = Shanghai, `101010100` = Beijing, `101280100` = Shenzhen |
| `experience` | Experience filter code | `0`=不限, `104`=1-3年, `105`=3-5年, `106`=5-10年 |
| `degree` | Education filter code | `0`=不限 |
| `salary` | Salary filter code | `0`=不限, `405`=10-20K, `406`=20-50K |
| `industry` | Industry filter code | (numeric) |
| `scale` | Company size filter code | `0`=不限, `303`=100-499人, `305`=1000-9999人 |
| `jobType` | Job type | `0`=不限, `1`=全职, `2`=兼职 |
| `encryptExpectId` | Saved preference ID | From user's saved preferences |

Filter codes come from `/wapi/zpgeek/pc/all/filter/conditions.json`.

### Response (`zpData.jobList[]`)

```python
{
    "securityId": "nbyXZvE4kfp6Y...",     # opaque ID for detail API
    "encryptJobId": "cbcbfca3...",          # job detail page ID
    "encryptBossId": "37a64419...",         # recruiter ID
    "jobName": "Aone/GitHub开发工程师",
    "salaryDesc": "18-22K",                 # REAL salary — not font-encoded
    "jobLabels": ["3-5年", "本科", "Java", "Golang"],
    "skills": ["Java", "Golang", "Aone", "GitLab"],
    "jobExperience": "3-5年",
    "jobDegree": "本科",
    "cityName": "上海",
    "areaDistrict": "浦东新区",
    "businessDistrict": "张江",
    "brandName": "软通动力",
    "brandIndustry": "计算机软件",
    "brandScaleName": "10000人以上",
    "brandStageName": "未融资",
    "bossName": "杨女士",
    "bossTitle": "人事",
    "bossOnline": false,
    "bossAvatar": "https://img.bosszhipin.com/...",
    "brandLogo": "https://img.bosszhipin.com/...",
    "welfareList": [],
    "gps": {"longitude": 121.609707, "latitude": 31.185578}
}
```

### Fetch Jobs (browser API)

```python
import json

def fetch_job_list(page=1, page_size=15, city="101020100", **filters):
    """Fetch jobs from the BOSS直聘 API. Must be on a zhipin.com page first."""
    params = f"page={page}&pageSize={page_size}&city={city}"
    for k, v in filters.items():
        if v:
            params += f"&{k}={v}"

    raw = js(f"""
    (async function() {{
        var r = await fetch('/wapi/zpgeek/pc/recommend/job/list.json?{params}');
        var d = await r.json();
        return JSON.stringify({{code: d.code, hasMore: d.zpData.hasMore, jobs: d.zpData.jobList}});
    }})()
    """)
    return json.loads(raw)

# Usage
result = fetch_job_list(page=1, experience=105)  # 3-5年
print(f"Total: {len(result['jobs'])} jobs, hasMore: {result['hasMore']}")
for j in result["jobs"]:
    print(f"  {j['salaryDesc']:12s} {j['jobName']:30s} {j['brandName']}")
```

### Pagination

The API uses `hasMore` (boolean), not a total count. Loop until `hasMore` is `false`:

```python
def fetch_all_jobs(city="101020100", max_pages=10):
    all_jobs = []
    for page in range(1, max_pages + 1):
        result = fetch_job_list(page=page, city=city)
        all_jobs.extend(result["jobs"])
        if not result["hasMore"]:
            break
        wait(0.5)  # polite delay
    return all_jobs
```

---

## API: Job Detail

```
GET /wapi/zpgeek/job/detail.json?securityId={securityId}
```

Use the `securityId` from the job list response (NOT `encryptJobId`).

```python
def fetch_job_detail(security_id):
    raw = js(f"""
    (async function() {{
        var r = await fetch('/wapi/zpgeek/job/detail.json?securityId={security_id}');
        var d = await r.json();
        var zp = d.zpData;
        var job = zp.jobInfo;
        var boss = zp.bossInfo;
        return JSON.stringify({{
            title: job.jobName,
            salary: job.salaryDesc,
            experience: job.experienceName,
            degree: job.degreeName,
            location: job.locationName,
            address: job.address,
            gps: {{lng: job.longitude, lat: job.latitude}},
            description: job.postDescription,
            skills: job.showSkills,
            boss_name: boss.name,
            boss_title: boss.title,
            boss_avatar: boss.large,
            boss_online: boss.online,
            company_name: zp.brandInfo.companyName,
            company_logo: zp.brandInfo.brandLogo,
            company_industry: zp.brandInfo.industry,
            company_scale: zp.brandInfo.scale,
            company_stage: zp.brandInfo.stage
        }});
    }})()
    """)
    return json.loads(raw)
```

---

## API: Filter Conditions

```
GET /wapi/zpgeek/pc/all/filter/conditions.json
```

Returns all available filter options with their numeric codes:

```python
def get_filter_conditions():
    raw = js("""
    (async function() {
        var r = await fetch('/wapi/zpgeek/pc/all/filter/conditions.json');
        var d = await r.json();
        return JSON.stringify(d.zpData);
    })()
    """)
    return json.loads(raw)

# Returns: {
#   experienceList: [{code: 105, name: "3-5年"}, ...],
#   salaryList:     [{code: 406, name: "20-50K", lowSalary: 20, highSalary: 50}, ...],
#   degreeList:     [{code: 203, name: "本科"}, ...],
#   scaleList:      [{code: 305, name: "1000-9999人"}, ...],
#   stageList:      [{code: 807, name: "已上市"}, ...],
#   industryList:   [...],
#   payTypeList:    [...],
#   partTimeList:   [...]
# }
```

---

## City Codes

City is identified by numeric code, not name:

| City | Code |
|------|------|
| 上海 | `101020100` |
| 北京 | `101010100` |
| 深圳 | `101280100` |
| 广州 | `101280100` |
| 杭州 | `101210100` |
| 成都 | `101270100` |

To discover a city code, check the `city` param in the job list API call or use the city data API:

```
GET /wapi/zpgeek/common/data/city/site.json
```

---

## DOM Extraction (fallback)

If the API path is blocked, fall back to DOM extraction. Note that salary text uses font-encoded private-use Unicode characters (U+E000–U+F8FF) — DOM `textContent` returns unreadable PUA codepoints like `"-K"` instead of the rendered digits.

### Job Card DOM

```
li.job-card-box
  div.job-info
    div.job-title.clearfix
      a.job-name[href="/job_detail/{ID}.html"]   — job title
      span.job-salary                              — FONT-ENCODED (see above)
    ul.tag-list
      li  — experience / education / skill tags
  div.job-card-footer
    a.boss-info[href="/gongsi/{ID}~.html"]
      span.boss-name                               — company name
    span.company-location                          — e.g. "上海·徐汇区·龙华"
```

```python
def extract_job_cards_dom():
    raw = js("""
    (function() {
        var cards = document.querySelectorAll('.job-card-box');
        var results = [];
        for (var i = 0; i < cards.length; i++) {
            var card = cards[i];
            function getText(sel) {
                var el = card.querySelector(sel);
                return el ? el.textContent.trim() : '';
            }
            function getHref(sel) {
                var el = card.querySelector(sel);
                return el ? el.href : '';
            }
            var tags = [];
            var tagEls = card.querySelectorAll('.tag-list li');
            for (var t = 0; t < tagEls.length; t++) {
                tags.push(tagEls[t].textContent.trim());
            }
            results.push({
                title: getText('.job-name'),
                salary_raw: getText('.job-salary'),
                tags: tags,
                company: getText('.boss-name'),
                location: getText('.company-location'),
                job_url: getHref('.job-name'),
                company_url: getHref('.boss-info')
            });
        }
        return JSON.stringify(results);
    })()
    """)
    return json.loads(raw)
```

15 cards per page. Scroll to lazy-load more.

---

## Gotchas

- **Always prefer the API** — `salaryDesc` returns human-readable salary. DOM salary uses font-encoded PUA chars that require OCR or font-file reversal to decode.
- **API needs browser session** — `/wapi/` endpoints require cookies from a real browser page load. Use `js()` + `fetch()` inside the browser, not Python `http_get`.
- **securityId vs encryptJobId** — the job detail API uses `securityId` (long opaque string), NOT `encryptJobId`. Both come from the job list response.
- **SPA routing** — URL doesn't change when filters are applied via the DOM. With the API, filters are explicit query params.
- **hasMore pagination** — no total count. Stop when `hasMore` is `false`.
- **City codes are numeric** — not city names. Use the filter conditions API or city/site.json to look up codes.
- **`wait(2-3)` after `goto_url`** — the SPA needs time to establish the session before API calls work.
