# Gemini Spark skills

## Editing a skill

- Open `https://gemini.google.com/spark/skills`. Locate the card whose title text exactly equals the intended skill name. Read the title separately from the description. A prefix match can select both `Foo` and `Foo Bar`. Stop if the title does not identify one card.
- The editor exposes `Skill description` and `Skill instructions` textboxes, `Save skill`, and `Skills, go back` controls.
- The instruction editor is a rich contenteditable field. After replacing long text, compare rendered text with repeated blank lines normalized rather than comparing raw `textContent`.
- After saving, wait for the `Skill saved` notice to disappear before using `Skills, go back`. Navigating away while the notice is still active can show a misleading `Leave without saving?` dialog even when the save button already says `Saved`.

## Recovering earlier content

Open the completed Spark conversation that created or last edited the intended skill. Completed conversations can retain skill confirmation cards. Find `remy-confirmation-card` elements whose `data-test-id="header"` text exactly equals the skill name. Inspect the matching `data-test-id="body"` content.

Use conversation order and displayed timestamps to identify the last confirmed version before the unwanted edit. If the history does not establish that version, ask the user which content to restore. Reopen the intended skill. Replace its description and instructions with the recovered content. Save the skill. Wait for the save notice to disappear.

Always verify the restored description and instructions by reopening the skill after the final save.
