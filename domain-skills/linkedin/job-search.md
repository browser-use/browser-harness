# LinkedIn — Job Search & Scraping

Field-tested against linkedin.com on 2026-04-21.
**Requires:** Browser Harness driving a cloud browser with a persistent profile (cookies for linkedin.com). Login triggers email PIN verification — cannot be fully automated without email access.

## Anti-bot verdict: browser required, no http_get workaround exists

**`http_get` returns HTTP 999 or redirect to auth wall on every LinkedIn job URL.**

Tested endpoints (all blocked):
- `/jobs/search-results/?keywords=...`
- `/jobs/view/{id}/`
- `/jobs/search/`
- `/feed`

**Stack:** LinkedIn's own bot detection (not Cloudflare). Signals: TLS fingerprint, request cadence, cookie presence, JS execution fingerprint.

**Use `goto()` + `wait()` exclusively. A Browser Use Cloud profile with `cookieDomains: ["linkedin.com"]` preserves login state between sessions — first run authenticates manually, subsequent runs reuse cookies.**

---

## Do this first: check auth + dismiss cookie banner

```python
goto("https://www.linkedin.com/")
wait_for_load()
wait(4)

# Dismiss cookie consent — blocks interaction until dismissed
dismissed = js("""
(function() {
  var btn = Array.from(document.querySelectorAll('button')).find(
    b => b.textContent?.includes('Accept') || b.textContent?.includes('Tout accepter')
  );
  if (btn) btn.click();
  return btn ? 'dismissed' : 'no_banner';
})()
""")
if dismissed == 'dismissed':
    wait(1)
```

Cookie banner appears on **every** page navigation in EU/FR locale. Call after every `goto()` + `wait_for_load()`.

---

## URL patterns

| What | URL |
|------|-----|
| Job search results | `https://www.linkedin.com/jobs/search-results/?currentJobId={ID}&keywords={kw}&geoId={geoId}&distance={km}` |
| Job search page 2+ | Append `&start={N}` (increments of 25) |
| Job detail | `https://www.linkedin.com/jobs/view/{JOB_ID}/` |
| Feed (login check) | `https://www.linkedin.com/feed` |
| Login page | `https://www.linkedin.com/login/fr` |

### Query param details

- **`currentJobId`** — **Required.** Without it the detail pane is empty and batch-click extraction fails. Use a real or dummy job ID (e.g. `4401817221`).
- **`keywords`** — Supports LinkedIn search syntax: `director%20or%20executive%20ai%20remote%20posted%20in%20the%20past%2024%20hours`.
- **`geoId`** — Geographic region code. `105073465` = France. Other codes require lookup.
- **`distance`** — Radius in km. `50` is typical.
- **`start`** — Pagination offset. Each page returns up to 25 results. Max safe pagination: 10 pages (250 results).

### Job detail URL

- Trailing slash matters for consistency: `/jobs/view/{ID}/`
- Job IDs are numeric, 8+ digits.
- Dedup regex: `https://www\.linkedin\.com/jobs/view/\d+/`

---

## Authentication flow

LinkedIn requires email PIN verification for every new session. Cloud profiles with persistent cookies avoid re-login.

### 17-step sequence

```
1. goto("https://www.linkedin.com/login/fr"); wait_for_load(); wait(4)
2. Dismiss cookie banner
3. Check if already on login form (input[name="session_key"] present?)
4. If marketing/landing page → click "Sign in" link
5. Fill email: input[name="session_key"] — MUST use native setter (React)
6. Fill password: input[name="session_password"] — MUST use native setter
7. Click sign-in button (text match: "Sign in" or "S'identifier" or type="submit")
8. Wait 5s for redirect
9. Screenshot → classify (LOGIN_PAGE | VERIFICATION_PAGE | LOGGED_IN | OTHER)
10. If VERIFICATION_PAGE → read PIN from email
11. Fill PIN: #input__email_verification_pin — MUST use native setter
12. Click submit (text match: "Submit" or "Soumettre")
13. Wait 5s
14. goto("https://www.linkedin.com/feed"); wait_for_load()
15. Screenshot → classify (LOGGED_IN = success)
16. Save cloud profile (cookies persist for next session)
17. Done
```

### React native value setter (CRITICAL)

LinkedIn uses React. Direct `.value =` assignment does NOT trigger React's state — the input appears filled but the form submits empty values. Use the native setter:

```python
fill_js = json.dumps("""
(function() {
  var el = document.querySelector('SELECTOR');
  if (!el) return 'not_found';
  var nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLInputElement.prototype, 'value'
  ).set;
  nativeSetter.call(el, 'VALUE');
  el.dispatchEvent(new Event('input', {bubbles: true}));
  el.dispatchEvent(new Event('change', {bubbles: true}));
  return 'filled';
})()
""")
```

Apply this to **every** input: email, password, PIN.

### Login form selectors

| Element | Primary | Fallback |
|---------|---------|----------|
| Email input | `input[name="session_key"]` | `input#username` |
| Password input | `input[name="session_password"]` | `input#password` |
| Sign-in button | text match: "Sign in" / "S'identifier" | `button[type="submit"]` |

### PIN verification selectors

| Element | Primary | Fallback |
|---------|---------|----------|
| PIN input | `#input__email_verification_pin` | `input[name="pin"]` |
| Submit button | text match: "Submit" / "Soumettre" | `button[type="submit"]` |

---

## Job search result extraction

### Scroll job results panel (lazy-load trigger)

LinkedIn's job results panel uses a **nested scrollable container**, NOT window scroll. Cards lazy-load on scroll.

```javascript
const panels = document.querySelectorAll('*');
for (const el of panels) {
  const s = window.getComputedStyle(el);
  if ((s.overflowY === 'auto' || s.overflowY === 'scroll')
      && el.scrollHeight > el.clientHeight + 200) {
    el.scrollTop = el.scrollHeight;
  }
}
'scrolled'
```

Heuristic: `scrollHeight > clientHeight + 200` identifies the right scrollable element. After scrolling, wait **2 seconds** for cards to render.

### Batch click all cards + extract IDs

```javascript
const btns = document.querySelectorAll('button[aria-label*="Ignorer l"]');
const results = [];
const seenIds = new Set();
for (let i = 0; i < btns.length; i++) {
  btns[i].parentElement.click();
  const m = window.location.href.match(/currentJobId=(\d+)/);
  const id = m ? m[1] : null;
  if (id && !seenIds.has(id)) {
    seenIds.add(id);
    const title = btns[i].getAttribute("aria-label")
      .replace(/.*?emploi\s*/, "").substring(0, 200);
    results.push({id: id, title: title, category: '__CAT__'});
  }
}
JSON.stringify(results);
```

- `button[aria-label*="Ignorer l"]` is **French-localized** ("Ignorer l'emploi" = "Dismiss job"). English locale: check for `"Dismiss"` or `"Ignore"` in aria-label.
- Clicking the **parent element** of the Ignore button focuses the job card in the detail pane.
- Job ID appears in the URL as `currentJobId=` after the click (LinkedIn sets it via History API).

### Total results count

```javascript
const el = document.querySelector(
  '.jobs-search-results-list__text, [class*="results-list"] .t-black, ' +
  '[class*="job-search-card"]'
) || document.querySelector('span[class*="results"]');
if (el) return el.innerText.match(/\d[\d\s]*/)?.[0]?.replace(/\s/g,'') || '0';
const body = document.body.innerText;
const m = body.match(/(\d[\d\s]*)\s*r[eé]sultat/i);
return m ? m[1].replace(/\s/g,'') : '0';
```

Note: the body regex handles both French "résultat" and English "result".

---

## Job detail page scraping

### Description extraction — fallback chain

Try each selector in order until content ≥ 500 chars:

| Priority | Selector | Notes |
|----------|----------|-------|
| 1 | `.jobs-description__content, .jobs-unified-top-card__description, [class*='jobs-description']` | Most precise |
| 2 | `.jobs-search__job-details--container, .jobs-details__container` | Broader detail pane |
| 3 | `main` | Fallback — entire main element |
| 4 | `body` | Last resort — very noisy |

```javascript
var selectors = [
  '.jobs-description__content, .jobs-unified-top-card__description, [class*="jobs-description"]',
  '.jobs-search__job-details--container, .jobs-details__container',
  'main',
  'body'
];
for (var i = 0; i < selectors.length; i++) {
  var el = document.querySelector(selectors[i]);
  var text = el ? el.innerText.trim() : '';
  if (text.length >= 500) {
    return text.substring(0, 15000);
  }
}
return '';
```

Cap at **15000 chars** to avoid browser-harness IPC limits.

---

## Cookie banner dismissal

```javascript
(function(){
  var btn = Array.from(document.querySelectorAll('button')).find(
    b => b.textContent?.includes('Accept') || b.textContent?.includes('Tout accepter')
  );
  if(btn) btn.click();
  return btn ? 'dismissed' : 'no_banner';
})()
```

Handles both English ("Accept") and French ("Tout accepter"). Must be called after every `goto()` + `wait_for_load()` in EU/FR locale.

---

## Timing requirements

| Action | Wait | Reason |
|--------|------|--------|
| After `goto()` + `wait_for_load()` | 3-4s | React hydration — DOM exists but state not ready |
| After cookie banner dismiss | 1s | Banner removal reflows layout |
| After scroll panel | 2s | Lazy-loaded cards render |
| After fill input (React native setter) | 0.5s | React state commit |
| After sign-in click | 5s | Redirect + auth check |
| After PIN submit | 5s | Redirect to feed |
| Between search pages | 3-6s (random) | Anti-bot cadence enforcement |
| After batch click all cards | 0s | Cards already clicked, no render needed |

**Critical trap:** 3-4s after `goto()` before any DOM interaction. React hydration is not instant — `wait_for_load()` fires when the DOM is stable but React hasn't committed state yet.

---

## Traps — selectors and patterns that DON'T work

| Trap | Why it fails | Fix |
|------|-------------|-----|
| `el.value = "text"` on React inputs | React doesn't see the change — form submits empty | Use `Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, text)` + dispatch input/change events |
| `window.scroll()` / `window.scrollTo()` | LinkedIn's job panel is a nested scrollable container, not the viewport | Scan all elements for `overflowY === 'auto' \|\| 'scroll'` + `scrollHeight > clientHeight + 200` |
| `document.querySelector('.job-card')` | LinkedIn obfuscates CSS classes with hashes (`.job-card-container__123abc`) | Use `aria-label` attributes or data attributes, never class names |
| `document.title` for auth detection | Title is locale-dependent and sometimes generic | Use vision classification or DOM-based checks (presence of login form inputs) |
| English text selectors (`.textContent.includes('Dismiss')`) | LinkedIn serves French UI for FR locale/IP | Use bilingual checks (`'Accept' \|\| 'Tout accepter'`, `'Sign in' \|\| "S'identifier"`) |
| `\u2019` (curly apostrophe) in French text | `"S'identifier"` uses U+2019 (RIGHT SINGLE QUOTATION MARK), not U+0027 | Check for both `'` and `\u2019` or use `includes()` without exact match |
| `currentJobId` omitted from search URL | Detail pane is empty — batch click has nothing to focus | Always include `currentJobId` param, even with a dummy value |
| Rapid page loads (< 2s between gotos) | Triggers anti-bot: CAPTCHA, login wall, or empty results | Wait 3-6s between search pages (randomize) |

---

## Framework quirks

### React hydration

LinkedIn is a React SPA. After `goto()` + `wait_for_load()`, the DOM renders but React state is not yet committed. Wait 3-4s before interacting with form inputs or reading React-managed state.

### Lazy loading

Job search results load via scroll. The panel container has `overflow: auto`. Cards off-screen are not in the DOM until scrolled into view. Always scroll the panel before extracting.

### Split-pane layout

Job search is a two-pane layout: left panel (card list), right panel (detail view). The URL reflects the focused job via `currentJobId=`. Clicking a card in the left panel updates the URL and right pane.

### French localization

LinkedIn serves French UI for FR locale/IP. All `aria-label` texts, button labels, and form placeholders are in French. Always check for both French and English variants.

### URL-based state

The focused job ID is stored in the URL (`currentJobId=`), not in the DOM. Extract it from `window.location.href` after clicking a card.

### Cloud profile persistence

Browser Use Cloud profiles with `cookieDomains: ["linkedin.com"]` persist login cookies between sessions. First run triggers full authentication (email + password + PIN). Subsequent runs with the same profile name skip login entirely.

---

## Quick reference

| Constant | Value |
|----------|-------|
| Results per page | 25 |
| Pagination param | `start=N` (increments of 25) |
| Max safe pages | 10 (250 results) |
| Description char cap | 15000 |
| Min description length | 500 chars (below = selector fallback) |
| France geoId | `105073465` |
| Default distance | `50` km |
| Anti-bot wait between pages | 3-6s (randomized) |