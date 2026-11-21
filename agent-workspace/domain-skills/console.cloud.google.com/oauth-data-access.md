# Google Cloud Console — OAuth data access

Site: `https://console.cloud.google.com/`

## Account and project context

Account-switch links carry an `authuser` query parameter. Preserve the selected
account context when following Console links; do not replace it with a guessed
account index. Verify the intended project in the Console header after account
switching or navigation, before changing settings. A loaded page alone does not
confirm that the intended account and project are selected.

## Consent configuration and scope persistence

**APIs & Services → OAuth consent screen** leads to **Google Auth Platform**.
Scope configuration lives under **Data Access**.

The **Add or remove scopes** panel has a manual scopes textbox. For an authorized
scope change, the commit sequence is:

1. Enter the requested scope in the manual textbox and choose **Add to table**.
2. Verify the intended scope is selected in the panel, then choose **Update**.
3. On the main **Data Access** page, choose **Save**.
4. Revisit or reload Data Access and verify the saved scope is present.

**Update** applies the panel selection to the page; it does not by itself persist
the main form. Do not report the scope change as saved at that intermediate state.
Restricted Gmail scopes can appear in a separate Gmail scopes section lower on
the Data Access page. Inspect that section before concluding a scope is missing.

## Asynchronous transitions

The scope panel and its tables can finish updating after `wait_for_load()`
returns. Wait for the intended panel or table state, then take a screenshot of
the settled page before deciding the next action. Recheck the main form after
the panel closes and the saved state after navigation; neither a click nor the
document load event proves that the scope change persisted.
