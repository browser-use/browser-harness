---
name: topicalmap
description: Create, inspect and export Topical Map AI maps through the user's signed-in browser, distinguishing initial subtopics from completed keyword enrichment.
---

# Topical Map AI

## Routes

- `/maps`: saved maps.
- `/maps/new`: choose SEO, Product Idea, Question or News map.
- `/maps/new/seo`: keyword-map setup.
- `/maps/<map-id>`: saved map, overview, cluster table and exports.
- `/maps/<map-id>/edit`: map editing.
- `/account`: credit balance, plan and optional integrations. Avoid reading credential inputs.

## SEO setup

Inputs expose stable IDs: `mapName`, `niche`, `serviceArea`, `language`.
Advanced options reveal `industry`, `audience`, `goal`, `country`, `amount`
(breadth), and `sitemap`.

Set country explicitly for local research. Service area and country are
separate inputs; adding a service area appends it to the niche in the rendered
map label. Do not assume the language setting determines the country.

Check the displayed credit cost before generation. Importing a sitemap and
connecting Search Console are separate actions, not prerequisites for a map.
Reuse an appropriate existing map before consuming credits on another one.

## Generation is two-stage

1. The app creates topics/subtopics and opens a persistent map route.
2. Keyword generation, deduplication and metrics enrichment continue afterward.

The initial success modal does not establish keyword completion. Look for
`Keywords are still being added` and inspect the All Keywords count. An early
CSV can contain subtopic titles as placeholder keywords, with blank metrics.
After enrichment, subtopics can merge or disappear and the count can change.
Preserve initial and final exports separately if auditing that transition.

Read the final CSV with a real CSV parser. Data rows have numeric `Number`
values; footer rows contain provenance notices and product attribution.

## Exports and metrics

CSV buttons use `title="Download CSV"` or the visible label `CSV`.
An onboarding banner may say export unlocks after generating a brief. Test the
visible export control before assuming a brief is required: CSV exported
successfully without generating one in the observed workflow.

Columns: `Number`, `Keyword`, `Subtopic`, `Topic`, `Volume`, `Competition`.
Blank metrics mean missing data, not zero. Initial exports can explicitly state
that the metric source cannot be verified; later exports can contain values.
The CSV does not necessarily identify provider, reference period or geography.
Do not relabel `Competition` as verified organic keyword difficulty solely
because the UI displays an easy-to-rank badge.

Count parsed keyword rows and compare with the overview. Some summary cards
can disagree with the export. Record the discrepancy instead of silently
substituting one number for another. Similar phrases are not independent
audiences, so summed volumes are not a unique-demand estimate.

Browser exports create a CSV Blob. A download-start event does not prove the
file saved: check completion and parse the local file. Download settings can
be scoped with documented CDP download behavior; restore default behavior
after the task.

## Editorial checks

Cluster assignment is not proof of intent. Kitchen clusters, for example,
can include bathroom-only, whole-home and financing questions. Compare
individual candidates with the site's existing content before commissioning
new articles. A map's unpublished counter also does not mean the user's
existing website lacks that content.

Expect welcome, generation-success, tour and optional Search Console modals.
Dismiss these through their visible controls. Do not connect integrations,
publish content or mark items published merely to complete onboarding.
