# Downloads

## 1. When to Use `http_get(...)` vs Browser Downloads

If a file has a direct, publicly accessible URL that does not require an active browser session or client-side JavaScript, use `http_get(url)` instead of driving the browser.

When the download requires a logged-in session, form submission, dynamically generated blob, or button click inside the app, use `wait_for_download(...)`.

## 2. Using `wait_for_download`

`wait_for_download` configures `Browser.setDownloadBehavior`, triggers the download action, and waits for the completed file to appear on disk.

```python
# Click a download button and wait for the file to finish writing
path = wait_for_download(lambda: click_at_xy(120, 340))
print(f"Downloaded to {path}")
```

```python
# Trigger download via DOM click
path = wait_for_download(lambda: js("document.querySelector('button.export-csv').click()"))
print(f"File size: {path.stat().st_size} bytes")
```

```python
# Specify a custom download directory
path = wait_for_download(
    action_fn=lambda: click_at_xy(200, 150),
    download_dir="/tmp/my-downloads",
    timeout=60.0,
)
```

## 3. How It Works

1. Sets `Browser.setDownloadBehavior` with `behavior="allow"` and `eventsEnabled=True`.
2. Runs the provided download action.
3. Listens for `Browser.downloadWillBegin` and `Browser.downloadProgress` CDP events.
4. Monitors the target directory to ensure temporary `.crdownload` files finish writing before returning.
