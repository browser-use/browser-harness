# Cloudflare Pages direct upload

Use the user's authenticated Cloudflare dashboard. Confirm permission to publish before deploying; no credentials or session tokens are needed outside the browser.

## Routes and product distinction

- Account application list: `https://dash.cloudflare.com/<account-id>/workers-and-pages`.
- Pages creation choice: `/<account-id>/workers-and-pages/create/pages`.
- Direct Upload form: `/<account-id>/pages/new/upload`.
- Existing project: `/<account-id>/pages/view/<project-name>`.

The current **Create application** screen starts with Workers methods, including **Upload your static files**. For a Pages project, follow **Continue to Pages** beneath that card, then **Drag and drop your files → Get started**. Do not select the Workers upload option when the task specifically requires Pages.

The dashboard is a SPA. `wait_for_load()` can finish while a new screen is blank or still showing its previous state. Wait for the relevant visible step and re-screenshot. Project-name validation also runs asynchronously: enter the name, wait for the valid hostname/check mark, and then select **Create project**. The form advances to an enabled upload step only after creation finishes.

## Upload inputs

The upload area has two hidden inputs:

- ZIP: `input[type="file"][accept=".zip"]`.
- Folder: `input[type="file"][webkitdirectory]`.

The ZIP input is not the directory input. Use `upload_file('input[type="file"][accept=".zip"]', absolute_zip_path)` or CDP `DOM.setFileInputFiles`; hidden inputs have no useful click geometry. For other visible actions, inspect screenshots and use normal coordinate clicks.

Package the **contents** of the static build, with `index.html` at the archive root. ZIP entry names must use forward slashes, including when creating the archive on Windows. Backslash names can flatten or misroute directory paths. Exclude source, environment files and dependencies. Include `_headers` and a top-level `404.html` if the application needs them.

The UI first shows **Preparing upload**, then a file counter and **All files were successfully uploaded**. Wait for all files to complete and the enabled **Deploy site** button before deploying. The successful upload is not yet a published deployment. Publication completes with the success screen and the actual `pages.dev` URL. Read that URL rather than assuming the requested project name always receives an identical hostname.

For an existing Direct Upload project, use its **Create deployment** action and select the intended production or preview environment. A client preview can intentionally use the production alias while its HTML remains noindex.

## Verify the result

Visit the actual HTTPS URL in a new tab. Check both the home and a nested route, refresh the nested route, and verify a truly unknown path returns the intended HTTP 404. Fetch built assets to confirm directory structure and MIME types. `_headers` is configuration; inspect response headers rather than expecting it to be served as a public file.

If the build uses CSP, test real interactions without bypassing CSP. Confirm the external client script loads and contact URLs compose correctly. No messages need to be sent to validate an enquiry link.

Official references: [Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/) and [headers](https://developers.cloudflare.com/pages/configuration/headers/).
