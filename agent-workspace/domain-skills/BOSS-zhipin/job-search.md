# BOSS直聘 — Job Search & Extraction

Field-tested against zhipin.com on 2026-05-01.

---

## Job Search Page (`/web/geek/jobs`)

SPA-based. City auto-detected from IP. Filters are client-side and reflected in DOM, not URL.

### Job Card DOM Structure

```
li.job-card-box
  div.job-info
    div.job-title.clearfix
      a.job-name[href="/job_detail/{ID}.html"]   — job title
      span.job-salary                              — salary range
    ul.tag-list
      li  — experience (e.g. "3-5年")
      li  — education (e.g. "本科")
      li  — skill tags (e.g. "Python", "Django")
  div.job-card-footer
    a.boss-info[href="/gongsi/{ID}.html"]
      img[src]                                     — company logo
      span.boss-name                               — company name
    span.company-location                          — e.g. "上海·徐汇区·龙华"
```

### Extract Job Cards

```python
def extract_job_cards():
    """Extract all visible job cards from the current search page."""
    cards = js("""
    JSON.stringify(Array.from(document.querySelectorAll('.job-card-box')).map(card => ({
        title: card.querySelector('.job-name')?.textContent?.trim() || '',
        salary: card.querySelector('.job-salary')?.textContent?.trim() || '',
        tags: Array.from(card.querySelectorAll('.tag-list li')).map(li => li.textContent.trim()),
        experience: card.querySelector('.tag-list li')?.textContent?.trim() || '',
        company: card.querySelector('.boss-name')?.textContent?.trim() || '',
        location: card.querySelector('.company-location')?.textContent?.trim() || '',
        job_url: card.querySelector('.job-name')?.href || '',
        company_url: card.querySelector('.boss-info')?.href || ''
    })))
    """)
    return json.loads(cards)
```

### Search Input

```python
"input[placeholder='搜索职位、公司']"
```

---

## Salary Text

Salary numbers use private-use Unicode characters (U+E000–U+F8FF) that render via the site's icon font. `textContent` returns the visual rendering correctly.

```python
import re

def clean_salary(raw):
    """Remove private-use area chars from salary text."""
    return re.sub(r'[-]', '', raw).strip()
```

---

## Gotchas

- **SPA routing** — URL doesn't change when filters are applied. Read DOM state, not URL params.
- **Private Unicode in salary** — `textContent` handles this; `innerText` may not.
- **Lazy loading** — only first ~15 cards load initially. Scroll to load more.
- **`wait(2-3)` after navigation** — SPA needs ~2s to hydrate filters and cards.
