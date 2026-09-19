# ADP Recruiting Management career search

An employer's official career link can use `https://recruiting.adp.com/srccar/public/RTI.home?c=<company-id>&d=External` and redirect in a normal browser to `https://myjobs.adp.com/<tenant>/cx?...`.

## Search and detail views

- A text-only fetch may fail on the redirect while the normal browser reaches the current career site. Prefer the official employer's link and verify the resulting tenant.
- Search controls and job cards may be implemented through nested shadow roots. Use screenshots and native coordinate input first. If DOM inspection is needed, inspect open shadow roots rather than concluding that no inputs or links exist in the page.
- Confirm the typed search value before clicking Search. Wait for the search-results-loaded text or expected result count; document readyState can finish before results arrive.
- Clicking a job title can open a detail pane beside the result list without changing the listing route to a distinct job URL. Record the visible title, requisition number, location and full description; do not identify the role solely from the address bar.
- Old links with an `r=` reference can land on the general career site. A similar job found by search is not proof that it is the same requisition. Keep the unresolved original distinct from any newly selected posting.

These notes describe the observed career-site variant. Other ADP products and employer tenants can use different routes and controls.
