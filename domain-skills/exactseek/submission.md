# ExactSeek submissions

- Start at `https://www.exactseek.com/add.html`.
- The submission action can open its receipt in a separate page target while the original form remains unchanged. Inspect new targets before retrying the original submit button.
- A receipt page can use `/cgi-bin/eadd-t-new.cgi` and require email confirmation.
- Confirmation URLs use `/cgi-bin/everify.cgi`. Keep query strings and tokens out of shared notes.
- An empty HTTP 200 confirmation page is inconclusive. Check for a visible confirmation, follow-up email, or account state before calling the email verified.
- Inspect mandatory mailing-list membership and paid upgrade choices before submitting.
