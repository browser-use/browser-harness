# CentileBrain — Generate Normative Deviation Values

URL: `https://centilebrain.org/#/model`

Generates z-scores for a single subject's FreeSurfer-derived morphometry
against the CentileBrain normative reference. Three separate modalities
(`SubcorticalVolume`, `CorticalThickness`, `SurfaceArea`), two sexes,
each a distinct Shiny app. Login/account not required.

## Site shape

- The `/#/model` page is a thin wrapper around per-modality/sex **Shiny
  iframes** at `https://centilebrain-app.shinyapps.io/{SV|CT|SA}-{MALE|FEMALE}/`.
- Switching modality swaps the iframe; switching sex swaps the iframe.
  The top-page buttons and toggles are not forms — they just replace
  the iframe `src`.
- The upload form, compute button, and download link all live **inside the iframe**.
  `iframe_target("shinyapps.io/SV-MALE")` (etc.) returns the session to use.
- Requires `upload_file(..., target_id=...)` — the iframe-aware upload helper.

## Form elements (inside the iframe)

| Selector | Purpose |
|---|---|
| `#email` | Required text input. Any valid-looking string works; it does not send mail. |
| `#file1` | The file input. Accepts the official `.xlsx` template for that modality/sex (download from the site to see the expected schema). |
| `#confirm` | The **Compute** button. Click exactly once after upload. |
| `#downloadData1` | **Download Results** link once compute is done. Produces a zip of CSVs + xlsx. |

## Waits

- Upload: after `upload_file`, wait ~3 s for the Shiny server to read the file; the data preview table populates in-place.
- Compute: poll the iframe body text for `"Computation complete"` — typically 30-90 s. `"Computing… This may take a few seconds to a couple of minutes."` is the in-progress marker.
- Download: click `#downloadData1`, then poll the Chrome download directory for a `{SV|CT|SA}_{male|female}_YYYY-MM-DD-HH-MM-SS.zip`. Set `Browser.setDownloadBehavior` with a known `downloadPath` before clicking so you can find it deterministically.

## Traps

- **Iframe target_id goes stale across modality swaps.** After clicking `CORTICAL THICKNESS` or `SURFACE AREA`, re-call `iframe_target("shinyapps.io/CT-MALE")` — the old id from SV-MALE will not work even though `Target.getTargets` may still list it briefly. Add a 2-3 s sleep after the modality-swap click before re-resolving.
- **Sex toggles are MUI switches, not radio buttons.** They are `input[type=checkbox]` with `name=female` / `name=male`. Clicking one does not automatically uncheck the other visibly, but the iframe src changes based on which is `checked`. Easiest: `js("document.querySelector('input[name=male]').click()")`.
- **Top-level buttons scroll off-screen after first interaction.** The modality buttons are at `y ≈ 226`, but after scrolling/iframe expansion they report `y < 0`. Use `js("window.scrollTo(0, 0)")` then click via JS by text (`Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'CORTICAL THICKNESS').click()`) instead of fixed coordinates.

## End-to-end example

```python
import time, os

DL = "/tmp/centilebrain"
os.makedirs(DL, exist_ok=True)
cdp("Browser.setDownloadBehavior", behavior="allow", downloadPath=DL, eventsEnabled=True)

new_tab("https://centilebrain.org/#/model")
wait_for_load()
time.sleep(2)

# Pick modality + sex (SV + male shown; repeat for CT and SA as needed)
js("""Array.from(document.querySelectorAll('button'))
       .find(b => b.innerText.trim() === 'SUBCORTICAL VOLUME').click()""")
time.sleep(1)
js("document.querySelector('input[name=male]').click()")
time.sleep(2)

t = iframe_target("shinyapps.io/SV-MALE")
upload_file("#file1", "/abs/path/JMT_subcortical_volume.xlsx", target_id=t)
time.sleep(3)

js("""const e=document.querySelector('#email');
      e.value='user@example.com';
      e.dispatchEvent(new Event('input',{bubbles:true}));""", target_id=t)

js("document.querySelector('#confirm').click()", target_id=t)
for _ in range(40):
    time.sleep(3)
    if "Computation complete" in js("document.body.innerText", target_id=t):
        break

before = set(os.listdir(DL))
js("document.querySelector('#downloadData1').click()", target_id=t)
for _ in range(30):
    time.sleep(2)
    after = set(os.listdir(DL))
    new = after - before
    if new and not any(f.endswith(".crdownload") for f in after):
        print("downloaded:", new)
        break
```

## Output zip

Unzipped contents (SV example):

```
output_file_YYYY-MM-DD-HH-MM-SS/
  zscore_SubcorticalVolume_male.csv       # per-ROI z-scores
  prediction_SubcorticalVolume_male.csv   # model-predicted raw values
  centile_SubcorticalVolume_male.xlsx     # centile ranks
  MAE_SubcorticalVolume_male.csv          # model accuracy (not per-subject)
  RMSE_SubcorticalVolume_male.csv
  Corr_SubcorticalVolume_male.csv
  EV_SubcorticalVolume_male.csv
```

The `zscore_*.csv` is the file you almost always want. Columns are
`SITE, SubjectID, Vendor, FreeSurfer_Version, age, <ROIs...>`.

## Multi-subject / batch uploads

The `.xlsx` template accepts many rows, and CentileBrain processes them
all in one compute. Same flow, same iframe; the z-score CSV will have
one row per subject. No concurrency needed across modality/sex for a
typical cohort.
