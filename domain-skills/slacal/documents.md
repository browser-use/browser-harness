# SLA-CAL (Surplus Line Association of California) — Finding Official Forms & Documents

Two hosts, and the split is the trap:

- `www.slacal.com` — DNN (DotNetNuke) site. **All document PDFs actually live here** under `/docs/default-source/<category>/<file>.pdf`. Direct `http_get` works, no browser needed.
- `learningcenter.slacal.com` — React SPA ("SLA LC"). Resource/forms *pages* moved here (old `www.slacal.com/brokers/...` URLs 301 to it), but it serves the SPA shell HTML (`<title>SLA LC</title>`) for ANY unknown path — **including paths ending in `.pdf`, with HTTP 200**. Always check `file`/content-type: if you got HTML back, you got the shell, not the document.

## Getting a form PDF without a browser

1. Guess/confirm the `www.slacal.com` DNN path. Known categories:
   - `docs/default-source/general-content-documents/filing-forms/` — broker filing forms (D-1, D-2, SL-1, SL-2, diligent-search addendum)
   - `docs/default-source/general-content-documents/insurer-filing-forms/` — insurer checklists, verifications
   - `docs/default-source/bulletins/<n>.pdf` — bulletins by number
2. Filenames carry revision suffixes, e.g. `d1-form-rev-01-01-2020.pdf`, `d2-form-rev-01-01-2020.pdf`. The bare name (`d1-form.pdf`) 404s.
3. If the live path 404s, enumerate what exists via the Wayback CDX API — it indexes the whole DNN doc tree:

```python
from helpers import http_get
rows = http_get(
    "http://web.archive.org/cdx/search/cdx?url=slacal.com&matchType=domain"
    "&filter=original:.*\\.pdf.*&collapse=urlkey&limit=2000&fl=timestamp,original,statuscode"
)
print([r for r in rows.splitlines() if "filing-forms" in r])
```

Archived URLs usually still work live on `www.slacal.com` (the DNN docs were never taken down — only the *pages* moved to the learning center). `?sfvrsn=` version params are optional.

Verified example (July 2026): official California D-1 disclosure form:
`https://www.slacal.com/docs/default-source/general-content-documents/filing-forms/d1-form-rev-01-01-2020.pdf`

## Learning center SPA internals (if you must)

- Config: `https://learningcenter.slacal.com/env.js` → `SERVER_API_URL: https://learningcenter.slacal.com/api`, plus `RAPID_SERVER_URL: https://rapid.slacal.com` (course content).
- ASP.NET Web API, `/api/{controller}/{action}`. Controllers seen in the bundle: `resources` (faqgroups, notices, bulletins/series, bulletins/byseries/{id}, getsection/{name}, getpagecontent/?url=), `brokerguides`, `courseofferings`, `LcUsers`, `location`.
- `getpagecontent`/`getsection` reject bare GETs with generic errors ("An error occurred…") — likely needs headers/params the SPA sets. Don't burn time here; the CDX + DNN-path route above is faster for documents.
