# GitHub — Upload images for a PR or issue body

GitHub's REST and GraphQL APIs have **no endpoint for image attachments**, and
`gh pr create` / `gh pr edit` cannot upload one. The only uploader is the
comment box's drop zone. It hosts a file at a `user-attachments` URL without
posting anything, so a signed-in browser can mint the URLs and `gh` can write
them into the body.

## Do this

```python
# Any PR or issue page, signed in (the new-comment box only renders then).
new_tab("https://github.com/{owner}/{repo}/pull/{n}")
wait_for_load()

# The drop zone's file input sits beside the textarea:
#   textarea#new_comment_field   <- markdown lands here
#   input#fc-new_comment_field   <- type=file, hidden
for path in ["/abs/one.png", "/abs/two.png"]:
    upload_file("#fc-new_comment_field", path)
    for _ in range(30):                      # upload is async, ~1–3s per image
        wait(1)
        v = js('document.querySelector("#new_comment_field").value')
        if "Uploading" not in v and v.count("user-attachments") >= expected_so_far:
            break

markdown = js('document.querySelector("#new_comment_field").value')
# -> '<img width="1560" height="844" alt="one" src="https://github.com/user-attachments/assets/<uuid>" />' per file

# Clear the draft so nothing is posted by accident.
js('(()=>{const t=document.querySelector("#new_comment_field");t.value="";'
   't.dispatchEvent(new Event("input",{bubbles:true}))})()')
```

Then put the `<img …>` tags in the body with `gh pr edit {n} --body-file body.md`.
Nothing gets committed to the repo and no comment is posted.

## Gotchas

- **Wait for the placeholder to go.** While a file uploads, the textarea holds
  `![Uploading one.png…]()`. Reading it too early gets the placeholder, not the URL.
- **Upload one file at a time.** `DOM.setFileInputFiles` with several paths
  works, but checking the textarea after each file makes a failed upload obvious.
- **Private repos:** `user-attachments` URLs render only for people who can see
  the repo. That is fine for a PR body, but don't paste them elsewhere expecting
  them to load.
- An existing comment's edit box has its own pair
  (`textarea#issuecomment-<id>-body`, `input#fc-issuecomment-<id>-body`). Use
  the new-comment pair so no existing comment is changed.
- Verify by reloading the PR and reading
  `[...document.querySelectorAll(".comment-body img")].map(i => i.naturalWidth)`.
  A non-zero width means the image loaded.
