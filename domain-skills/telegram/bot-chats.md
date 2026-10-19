# Telegram Web K: opening new bot chats

Use `https://web.telegram.org/k/` in the authenticated browser. Stop for the user to complete sign-in when required.

## Finding and opening bots

- Use the sidebar global search with the exact bot username. Verify the selected chat title and username before sending messages; for BotFather, verify the official verified account.
- A direct `#@username` hash navigation to an unseen bot can revert to the previously open conversation. Do not infer the recipient from the requested URL. Use global search or the visible `t.me` link in BotFather, then verify the opened chat.
- A newly created bot chat shows **Start** before normal messaging is enabled. Click it and verify the resulting `/start` message before testing ordinary messages.
- Sidebar rows reorder as messages arrive. Re-screenshot before selecting another chat; old coordinates can select the wrong recipient.

## BotFather secrets

BotFather returns a token in the creation confirmation. Avoid screenshots or dumping the full conversation once that response appears. If extracting it for an authorized local integration, read it without printing it, store it in a private credential file, and keep tokens and user-specific identifiers out of logs and shared artifacts.

Verify an integration with a fresh incoming user message and a visible bot-side reply in each chat. A successful bot identity check alone does not prove the transport reaches the intended agent.
