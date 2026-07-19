# X — Request an account data archive

Use the direct settings route:

```python
new_tab("https://x.com/settings/download_your_data")
wait_for_load()
print(page_info())
```

## Ownership verification is expected

Even an authenticated session is redirected to:

```text
https://x.com/i/flow/verify_account_ownership
```

The flow presents a password textbox (`aria-label` includes `Password`) before
showing the archive request controls. Cookie-only profile sync does not bypass
this step; a session can still load `/home` successfully while this route asks
for the account password.

Treat this as an authentication wall, not as a stale-session signal. Stop and
ask the user to complete verification in the visible browser. Never read,
request in chat, or type the password on the user's behalf. Continue only after
the user confirms verification, then re-read the page before locating the
request control.

## Checks

- `/home` loading proves the cookie session is authenticated; it does not prove
  ownership verification is complete.
- A redirect to the ownership flow is normal for this sensitive setting.
- Re-observe or screenshot after the user completes verification because the
  flow navigation invalidates prior element references.
- Archive generation is asynchronous. A submitted or pending state is success;
  availability and download happen later.
