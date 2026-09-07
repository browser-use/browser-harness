# Gemini Spark skills

## Editing a skill

- Open `https://gemini.google.com/spark/skills` and locate the skill card by a button name that starts with the exact skill name followed by a space. Avoid a broad `hasText` match because one skill description can mention another skill name.
- The editor exposes `Skill description` and `Skill instructions` textboxes, `Save skill`, and `Skills, go back` controls.
- The instruction editor is a rich contenteditable field. After replacing long text, compare rendered text with repeated blank lines normalized rather than comparing raw `textContent`.
- After saving, wait for the `Skill saved` notice to disappear before using `Skills, go back`. Navigating away while the notice is still active can show a misleading `Leave without saving?` dialog even when the save button already says `Saved`.

## Recovering earlier content

Completed Spark task conversations can retain skill confirmation cards. Search `remy-confirmation-card` elements whose `data-test-id="header"` text matches the skill name, then inspect the matching `data-test-id="body"` content. Prefer the newest confirmed card that predates the unwanted edit.

Always verify the restored description and instructions by reopening the skill after the final save.
