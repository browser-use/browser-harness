# BOSS直聘 — Site Navigation & Structure

Field-tested against zhipin.com on 2026-05-01.

---

## URL Patterns

| Page | URL |
|------|-----|
| Home (redirects to city) | `https://www.zhipin.com/` → `https://www.zhipin.com/{city}/` |
| Job search | `https://www.zhipin.com/web/geek/jobs` |
| Company search | `https://www.zhipin.com/gongsi/` |
| Messages / Chat | `https://www.zhipin.com/web/geek/chat` |
| Personal center | `https://www.zhipin.com/web/geek/recommend` |

### Special channels

| Page | URL |
|------|-----|
| Campus recruitment | `https://www.zhipin.com/school/` |
| Returnee / Overseas talent | `https://www.zhipin.com/returnee_jobs/` |
| Overseas jobs | `https://www.zhipin.com/overseas/` |
| Accessibility jobs | `https://www.zhipin.com/accessible_job/` |
| Youle (career community) | `https://youle.zhipin.com/recommend/selected/` |

---

## Top Navigation Bar

```
BOSS直聘 | 首页 | 职位 | 公司 | 校园 | 海归 | APP | 有了 | 海外 | 无障碍专区
```

Always visible. First item (BOSS直聘 logo) links to root domain.

---

## User Menu (login required)

Dropdown on the right side of the top bar. Shows user's real name when logged in. Entries include:

- 消息 — chat with recruiters
- 简历 — resume management
- 升级VIP — paid membership
- 规则中心 — platform rules
- 切换为招聘者/切换为求职者 — **dual-mode switch** between job-seeker and recruiter

---

## Home Page

Root URL redirects to city-specific page based on IP (e.g. `/shanghai/`). Shows industry category selector and recommended jobs.

### Industry Categories (top-level)

互联网/AI, 电子/电气/通信, 产品, 客服/运营, 销售, 人力/行政/法务, 财务/审计/税务, 生产制造, etc.

Each expands to sub-specialties (e.g. 互联网/AI → Java, Python, 前端, AI工程师...).

### Search Bar

```python
"input[placeholder='搜索职位、公司']"
```

---

## Gotchas

- **Root URL redirects to city** — `zhipin.com` → `zhipin.com/{city}/` based on IP. Always check final URL after navigation.
- **Dual-mode accounts** — same account switches between job-seeker and recruiter. UI changes completely.
- **Search is SPA-based** — `/web/geek/jobs` uses client-side routing. URL params don't reflect active filters.
- **city slug is pinyin** — `/shanghai/`, `/beijing/`, `/shenzhen/`, `/hangzhou/`, etc. (English transliteration, not Chinese characters). Note: the job search API uses numeric city codes (e.g. `city=101020100`), not pinyin slugs — see the city code table in job-search.md.
- **`wait_for_load()` may not be enough** — heavy SPA, add `wait(2)` for hydration.
