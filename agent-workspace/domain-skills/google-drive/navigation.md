# Google Drive — Navigation & File Access

Field-tested against drive.google.com on 2026-04-30 using browser-harness CDP.

## Multi-Account: authuser Parameter

Google Drive uses `authuser=N` to switch between logged-in Google accounts in the same Chrome profile. The number is determined by login order, not account type.

**Find the right authuser:** Navigate to `https://drive.google.com/drive/home` with different `authuser` values until you see the expected account indicator (storage usage, org logo, profile avatar).

```python
# Example: authuser=2 was the @ebaychina.com corporate account
new_tab("https://drive.google.com/drive/home?authuser=2")
wait_for_load()
```

Once identified, **always append `&authuser=N`** (or `?authuser=N` if first param) to all Drive/Docs/Sheets URLs for that account.

## Search

### Via URL (recommended)

```python
new_tab("https://drive.google.com/drive/search?q=FAS+Infra+SOP&authuser=2")
wait_for_load()
```

URL-encode the query. Spaces become `+` or `%20`.

### Via search bar

The search bar is at the top of Drive. Click it, type the query, press Enter.

```python
click_at_xy(490, 25)
import time
time.sleep(1)
type_text("search terms here")
time.sleep(1)
press_key("Enter")
time.sleep(3)
```

## Extracting File IDs from Search Results

Double-clicking in search results is unreliable via CDP. Instead, extract the file's `data-id` attribute from the DOM and navigate directly.

```python
result = js("""
  const items = document.querySelectorAll("[data-id]");
  const results = [];
  items.forEach(item => {
    const id = item.getAttribute("data-id");
    const text = item.textContent.substring(0, 100);
    results.push({id, text: text.substring(0, 80)});
  });
  return JSON.stringify(results);
""")
print(result)
```

Filter by keyword to find the target:

```python
result = js("""
  const items = document.querySelectorAll("[data-id]");
  const results = [];
  items.forEach(item => {
    const id = item.getAttribute("data-id");
    const text = item.textContent.substring(0, 100);
    if (text.includes("YOUR_KEYWORD")) {
      results.push({id, text: text.substring(0, 80)});
    }
  });
  return JSON.stringify(results);
""")
```

## Opening Files by ID

Once you have the file ID, navigate directly. The URL pattern depends on file type:

| File Type | URL Pattern |
|-----------|-------------|
| Google Docs | `https://docs.google.com/document/d/{id}/edit` |
| Google Sheets | `https://docs.google.com/spreadsheets/d/{id}/edit` |
| Google Slides | `https://docs.google.com/presentation/d/{id}/edit` |
| PDF / other | `https://drive.google.com/file/d/{id}/view` |

The file type can be inferred from the DOM text — look for "Google Docs", "Google Sheets", "Google Slides" prefix in the element's `textContent`.

```python
# Example: open a Google Sheets file
goto_url("https://docs.google.com/spreadsheets/d/1Q8yJNXwyw-aln5X089PanIE_YQ57adDljEQJnYw_0fo/edit")
wait_for_load()
import time
time.sleep(4)  # Sheets/Docs take a few seconds to fully render
```

## Google Docs Navigation

Google Docs with many sections show a **Document tabs** sidebar on the left. Use Ctrl+F to jump to a specific section:

```python
press_key("Control+f")
import time
time.sleep(1)
type_text("Section Name")
time.sleep(2)
# Press Escape to close find bar, then scroll to read
press_key("Escape")
```

## Drive Sidebar Sections

The left sidebar contains:
- Home, Activity
- My Drive, Shared drives
- Shared with me, Recent, Starred
- Spam, Trash, Storage

Clicking sidebar items navigates within Drive. Use `click_at_xy` on the visible label.

## Gotchas

- **Double-click doesn't work reliably** — CDP `click_at_xy` twice in succession toggles selection rather than opening. Always extract `data-id` and navigate directly.

- **`goto_url` can timeout on Drive** — Drive pages are heavy SPAs. If `goto_url` times out, use `new_tab` instead, or call `ensure_real_tab()` to reconnect after a timeout.

- **authuser matters for every URL** — If you open a Docs/Sheets link without the correct `authuser`, it may redirect to a login page or the wrong account's view. Always include it.

- **Drive search results are flat** — The DOM renders all results as `[data-id]` elements regardless of file type. The type indicator (Google Docs/Sheets/etc.) is in the element's text content as a prefix.

- **Google Sheets/Docs take 3-5s to render** — After `wait_for_load()`, add `time.sleep(4)` before screenshotting or interacting with the document content.

- **Storage indicator identifies the account** — Personal accounts show "X GB of 15 GB used". Corporate/Workspace accounts often show "0 bytes of 15 GB" with the org logo (e.g., eBay logo) in the top-right corner.

- **Shared drives vs My Drive** — Corporate files are usually in Shared drives. The search covers both by default.

- **Omnibox popup tabs are fake** — When listing tabs, filter out `chrome://omnibox-popup` entries. They are not real page targets.
