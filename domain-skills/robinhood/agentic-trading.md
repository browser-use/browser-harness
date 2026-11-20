# Robinhood Agentic Trading MCP

`https://robinhood.com/us/en/support/articles/agentic-trading-overview/#ConnectyourAIagent`

Robinhood documents the Trading MCP as a Streamable HTTP endpoint:

```bash
codex mcp add robinhood-trading --url https://agent.robinhood.com/mcp/trading
```

For Codex Desktop, use Settings -> MCP servers -> Streamable HTTP and the same URL:

```text
https://agent.robinhood.com/mcp/trading
```

## OAuth and rollout behavior

`codex mcp add` may detect OAuth and start a browser authorization flow. If the account is not yet in the Agentic Trading rollout, the OAuth URL redirects to:

```text
https://robinhood.com/mcp/trading?...oauth params...
```

The page shows "Coming soon: Agentic trading" and "We'll email you once you have access." In that state, Robinhood does not redirect back to the localhost OAuth callback, so the Codex CLI remains waiting and the MCP entry stays configured but `Not logged in`.

Stop the waiting CLI process after confirming the page state, then retry `codex mcp login robinhood-trading` later after access is granted.

## Boundaries

Do not enter Robinhood credentials, MFA codes, or accept financial/account disclosures for the user. Stop at login, MFA, OAuth authorization, or Agentic account onboarding steps and let the user complete those directly.
