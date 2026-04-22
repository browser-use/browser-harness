# LinkedIn Easy Apply

Automated job application workflow using browser-harness to apply for jobs on LinkedIn via the Easy Apply feature.

## When to use

- User asks to apply for jobs on LinkedIn
- User wants to batch-apply to Easy Apply listings
- User is logged into LinkedIn in the connected Chrome profile

## Quick apply flow

```python
# 1. Search for jobs with Easy Apply filter
new_tab("https://www.linkedin.com/jobs/search/?f_WT=2&keywords=YOUR_KEYWORDS&f_TPR=r2592000")
wait_for_load()
wait(2)

# 2. Extract job URLs
result = js("""
  (function() {
    var links = document.querySelectorAll('a[href*="jobs/view"]');
    var results = [];
    for (var i = 0; i < links.length; i++) {
      results.push({
        text: links[i].textContent.trim().substring(0, 50),
        href: links[i].href
      });
    }
    return JSON.stringify(results);
  })()
""")

# 3. Navigate to a job page and open Easy Apply
new_tab("https://www.linkedin.com/jobs/view/{JOB_ID}")
wait_for_load()
wait(3)

# 4. Click Easy Apply
js("""
  (function() {
    var all = document.querySelectorAll('a, button');
    for (var i = 0; i < all.length; i++) {
      if (all[i].textContent.trim() === 'Easy Apply') { all[i].click(); return 'clicked'; }
    }
    return 'not found';
  })()
""")
wait(3)

# 5. Fill phone number (email is auto-filled)
js("""
  (function() {
    var inputs = document.querySelectorAll('input[type="text"]');
    for (var i = 0; i < inputs.length; i++) {
      if (inputs[i].id && inputs[i].id.includes('phoneNumber-nationalNumber')) {
        inputs[i].value = 'PHONE';
        inputs[i].dispatchEvent(new Event('input', {bubbles: true}));
        inputs[i].dispatchEvent(new Event('change', {bubbles: true}));
        return 'filled';
      }
    }
    return 'not found';
  })()
""")

# 6. Click Next / Review / Submit application (same pattern each step)
js("document.querySelectorAll('button').forEach(b => { if (b.textContent.trim() === 'Next') b.click() })")
wait(3)

# 7. Fill screening questions
js("""
  (function() {
    var inputs = document.querySelectorAll('input[type="text"]');
    for (var i = 0; i < inputs.length; i++) {
      if (inputs[i].id && inputs[i].id.includes('-numeric')) {
        inputs[i].value = 'YEARS';
        inputs[i].dispatchEvent(new Event('input', {bubbles: true}));
        inputs[i].dispatchEvent(new Event('change', {bubbles: true}));
      }
    }
    return 'filled';
  })()
""")
```

## Key selectors

| Element | Selector pattern | Notes |
|---------|-----------------|-------|
| Easy Apply button | `a` with text "Easy Apply" | It is an `<a>` tag, NOT a `<button>` |
| Phone input | `input[id*="phoneNumber-nationalNumber"]` | ID includes job ID and element ID |
| Numeric question inputs | `input[id*="-numeric"]` | Type is `text`, not `number` |
| Navigation buttons | `button` with text "Next" / "Review" / "Submit application" | All are `<button>` elements |

## Progress steps

- **0%** = Contact info (email auto-filled, phone needs input)
- **33%** = Resume selection (default resume pre-selected)
- **67%** = Screening questions (years of experience, etc.)
- **100%** = Review and submit

## Pitfalls

- **Multiple Chrome profiles**: Verify login by checking for user name in nav bar
- **SDUI**: DOM queries are unreliable; prefer `innerText` parsing
- **Easy Apply is `<a>`**: Use `el.click()` not coordinate clicks
- **Must dispatch events**: After setting values, dispatch both `input` and `change` or LinkedIn ignores the input
- **Rate limiting**: Space applications 30-60s apart to avoid CAPTCHAs
- **External applies**: "Apply" (not "Easy Apply") redirects off-platform; skip these
- **Verify submission**: Look for "Application submitted" text after clicking Submit
