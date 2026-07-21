# Google Search Console performance reports

Use the user's already-authenticated Chrome session. Stop at the Google sign-in page; never enter credentials from screenshots or local files.

## Stable routes

- Standard Search performance report:
  `https://search.google.com/search-console/performance/search-analytics?resource_id=<URL-encoded property>`
- Generative AI performance report:
  `https://search.google.com/search-console/performance/search-analytics/ai`

For a domain property, encode the complete value such as `sc-domain:example.com` when passing `resource_id`.

## Distinguish the two AI controls

The standard Performance report may show `Customize your Performance report using AI`. This is only an experimental filter/comparison configurator. It is not the separate Generative AI performance report for AI Overviews and AI Mode impressions.

Verify generative-report access independently:

1. Open the normal Performance report and screenshot the left navigation.
2. Check for a Generative AI, AI Overviews, or AI Mode report item.
3. Open the direct `/performance/search-analytics/ai` route.
4. Screenshot the result.

During subset rollout, an unavailable report can redirect to `/search-console/not-found` and visibly render `Page couldn't be found` even while the property is selected and normal Search Console access works. Opening the route without a selected property may instead show `Please select a property`; that is not proof of report access.

## API cross-check limitation

The Search Analytics API `searchAppearance` dimension is useful corroboration, but it is not a substitute for the UI-only Generative AI performance report. Ordinary rows such as `PRODUCT_SNIPPETS` or `TRANSLATED_RESULT` do not indicate AI Overviews or AI Mode report access.

After any navigation, use `page_info()` and a screenshot to verify the selected property, final route, visible report title, and error state.
