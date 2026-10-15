# Example Content Extraction

## Purpose
Read and archive public `example.com` pages as a safe smoke target for content
extraction helpers.

## URL patterns
- `https://example.com/`
- `https://www.example.com/`

## Auth state
No authentication is required. Stop if the page is not the public Example Domain
page.

## Use these helpers
```python
archive_current_page("evidence/example-archive", overwrite=True)
extract_outline()
extract_links()
extract_markdown_from_current_page("evidence/example-md", overwrite=True)
```

## Selectors/API
- Main page text is static HTML.
- Links can be read with `extract_links()`.
- Headings can be read with `extract_outline()`.

## Failure modes
- If navigation leaves `example.com`, stop and record the unexpected URL.
- If markdown conversion is unavailable, keep the raw archive and inspect
  `processed/status.json`.

## Evidence examples
- `evidence/example-archive/manifest.json`
- `evidence/example-md/processed/status.json`

## Do not
- Do not add credentials, private access material, personal data, or task narration.
- Do not store screenshots with private data.
- Do not store pixel coordinates.
- Do not click or submit anything; this skill is read-only.
