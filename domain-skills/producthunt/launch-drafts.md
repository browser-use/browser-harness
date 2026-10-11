# Product Hunt launch drafts

## Routes and fields

- Start at `/posts/new` and enter the product URL. The wizard uses `/posts/new/submission`.
- Main information fields include `name`, `tagline`, `url`, `description`, `topics`, and `commentBody`.
- The `topics` field is a custom searchable menu. Results need not expose `role=option`. Focus/click the input in the visible tab, wait for the query results, and locate the result by its current visible text. Popular suggestions can appear briefly before search results update.
- Main information cannot advance without a committed launch tag. Merely entering a search term is insufficient.
- The URL importer can supply both a thumbnail and gallery image. Inspect them before uploading duplicates.
- Thumbnail file input ID: `file-input-thumbnailImageUuid`; gallery upload input ID: `file-input-media` (it can appear more than once).

## Draft and launch state

- Additional stages can appear after the maker choice, including shoutouts and investor matching. Optional endorsements and investor introductions can be skipped.
- **Create draft** persists the product and leads to `/products/<slug>?launch=<launch-slug>`. Wait for the new route rather than resubmitting during the transition.
- A persisted draft displays a banner stating that it is not scheduled for launch. It is not evidence of publication.
- **Schedule** opens a date picker. Inspect the displayed local/PT conversion before confirming. The final action is **Confirm scheduled date**.
- Scheduling is separate from draft creation. Keep the accepted launch date and verify the public page after that date.
- Account-age guidance may differ from what the current flow permits. Report the actual enforced state instead of assuming an advertised wait has blocked the account.
