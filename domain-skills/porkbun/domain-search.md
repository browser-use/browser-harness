# Porkbun — domain availability and pricing (single and bulk)

Field-tested against porkbun.com on 2026-09-02 from a logged-out local Chrome session, checking ~190 `.com`/`.ai` candidates. No CAPTCHA seen.

## URL patterns

- `https://porkbun.com/checkout/search?q=<sld>` — bare name: `.com` renders in the **left sidebar box** (id `searchResultRowDomain_<sld>_com`, visible text `.COM`), other TLDs render as rows.
- `https://porkbun.com/checkout/search?q=<sld>.<tld>` — full domain: that exact domain is the **first row**, then Porkbun's suggestions.

## Row structure (both modes)

Every result is a `div.searchResultRow` whose domain cell has id `searchResultRowDomain_<sld>_<tld>` and whose price cell has id `searchResultRowPrice_<sld>_<tld>`. Rows render **immediately with a spinner** and resolve asynchronously:

- pending: domain cell carries class `pendingDomain`, price cell `searchResultRowPricePending`
- available: row class `searchResultRow availableDomainRow`; price text like `At Cost | $82.70 / year | renews at $82.70` (first-year sale prices show a struck-through renewal price)
- taken: row class `searchResultRow unavailableDomainRow`, text `unavailable` plus an `Inquire` (aftermarket) button
- registry premium: the price text says `Premium`

Wait for the row to lose `pendingDomain` before reading it; reading on `readyState == complete` gives you the domain name only.

```python
navigate("https://porkbun.com/checkout/search?q=kepton.ai")
for _ in range(40):
    wait(0.5)
    if js("document.querySelectorAll('.pendingDomain, .searchResultRowPricePending').length") == 0: break
print(js("document.querySelector('#searchResultRowPrice_kepton_ai').innerText"))
```

## Bulk search (up to 100 domains per submission; the fast path)

The search box has a "bulk search" mode with a textarea (`#bulkSearchBoxList`, one domain per line) inside a form that POSTs to `/checkout/search` with `bulkAction=bulkSearchList`. The page exposes `showBulkSearch()` as a global.

```python
navigate("https://porkbun.com/checkout/search"); wait_for_load(); wait(2)
js("showBulkSearch()"); wait(1)
js("document.querySelector('#bulkSearchBoxList').value = " + json.dumps("\n".join(domains)))
js("document.querySelector('#bulkSearchBoxList').closest('form').submit()")
wait(5); wait_for_load()
for _ in range(240):          # ~10-40 s for 50-90 domains
    wait(0.5)
    if js("document.querySelectorAll('[id^=searchResultRowDomain_]').length") and \
       js("document.querySelectorAll('.pendingDomain, .searchResultRowPricePending').length") == 0: break
rows = js("""(()=>{const o={};document.querySelectorAll('[id^=searchResultRowDomain_]').forEach(e=>{
  const id=e.id.slice('searchResultRowDomain_'.length);const p=document.getElementById('searchResultRowPrice_'+id);
  o[id]={cls:(e.closest('.searchResultRow')||{}).className,price:p?p.innerText:null}});return JSON.stringify(o)})()""")
```

Ids use `_` between SLD and TLD (`kepton_ai`); split on the last underscore. Results come back in one page for all domains, no sidebar box.

## Traps

- **A submission of exactly 100 lines came back as an empty bulk form** (no rows, no error); 50 and 89 lines worked. Stay at ≤ 90 per batch.
- **Rapid single-domain queries (one page load every ~5 s, ~10 in a row) left rows pending forever** for the rest of the session. Use bulk search for lists.
- `form.submit()` bypasses the JS handler and works; the visible search button inside `#bulkSearchContainer` is a styled div, `.click()` on it did nothing.

## No-browser shortcuts

- **List prices without auth:** `POST https://api.porkbun.com/api/json/v3/pricing/get` with `{}` returns `pricing[tld].registration/renewal` for every TLD (2026-09-02: `.com` 11.08, `.ai` 82.70). Availability endpoints need API keys.
- Registry status without Porkbun: RDAP (`https://rdap.verisign.com/com/v1/domain/<d>` for `.com`; `https://rdap.org/domain/<d>` as the universal relay). `rdap.nic.ai` refused connections; `rdap.org` resolved `.ai` fine at ~2 s per lookup. 404 = unregistered. Porkbun then only adds the premium flag and the commercial confirmation.
