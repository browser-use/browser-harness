# WARC — Research and PDF extraction

`https://www.warc.com` is a subscription research database. Use an already-authenticated browser session and preserve the user's access boundaries. Do not redistribute downloaded subscription files.

## Search

WARC search accepts a plain query parameter:

```text
https://www.warc.com/en/search?q=share%20of%20search
```

Open promising result pages in the signed-in browser and extract the visible article metadata, population, effect size, design, and limitations. Treat award cases and vendor-authored reports as selected evidence unless a sampling frame or comparison design is disclosed.

## Recover the underlying PDF from article viewers

Some WARC report pages render only a preview or first page in the document viewer. After the viewer has loaded, inspect the page's performance resources from the article target:

```python
resources = js("""
performance.getEntriesByType('resource')
  .map(r => r.name)
  .filter(u => u.includes('cdn.builder.io') && u.toLowerCase().includes('.pdf'))
""", target_id=warc_target_id)
```

Observed PDF resource forms include:

```text
https://cdn.builder.io/o/assets/...pdf
https://cdn.builder.io/api/v1/file/assets/...pdf
```

The exact asset path is page-specific. Discover it from the loaded page; never guess or reuse an asset URL from another report. Fetch it only through the authorized browser context or an authenticated request derived from that context.

## Multi-tab reliability

When many tabs are open, use a known WARC target ID for every JavaScript and CDP call. Global current-tab helpers can attach to the wrong target. Re-list targets after opening a new article and bind extraction to the matching WARC URL.

## Evidence-quality checks

- Record the claim-specific sample and uncertainty when available; a report-level database size is not a substitute.
- Keep percentage points, relative percentages, ROI ratios, market-share effects, and revenue elasticities separate.
- Do not turn WARC case-study outcomes into priors without a credible control or model specification.
- Cite the public WARC article URL even when the detailed evidence came from its subscription PDF.

