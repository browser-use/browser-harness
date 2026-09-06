# NIH ODS — public fact-sheet capture

Observed on `ods.od.nih.gov` in September 2026.

- Fact-sheet URLs use `/factsheets/<Nutrient>-HealthProfessional/` and
  `/factsheets/<Nutrient>-Consumer/`. Confirm the audience in the visible title.
- Try ordinary HTTP first. A plain request returned 403 while the same public
  page rendered normally in Chrome. Do not archive a denial body as the fact
  sheet; a normal browser visit may provide the public article without login.
- The rendered `article` contains the sheet, references, disclaimer and displayed
  update date. `#fact-sheet` contains the substantive sections. If capturing DOM,
  label it rendered article HTML, not the original HTTP response.
- Locate sections by visible heading text, then use that heading's observed ID.
  Numeric IDs such as `h18` are specific to a sheet's organization, not universal
  identifiers for the same topic on every nutrient page.
- Some headings have duplicate generated IDs (`heading-0`, etc.). Prefer the
  actual heading element within the article rather than a global ID match.
- Inline references include tooltip citation text in the DOM. Naive `textContent`
  or static HTML-to-text extraction can repeat full citations inside paragraphs.
  Keep the original capture, and distinguish displayed prose from tooltip text
  before doing content-length checks or extracting sentences.
- Record the article's **Updated** date separately from retrieval time. A fresh
  capture does not mean the scientific content was updated that day.

The site's linked source records and original publications still need their own
identity and scope checks; the fact-sheet capture is not review of every cited
paper. No account access or form submission is needed for this workflow.
