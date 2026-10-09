# Claude custom web connectors

## Routes

- Organization connectors are managed at `https://claude.ai/admin-settings/connectors`. Check the organization selector before changing settings.
- Personal `/settings/connectors` may redirect to a settings modal that says connectors have moved to Customize. This is not the organization connector administration page.

## Organization registration

Adding an organization connector requires an Owner account on a Team or Enterprise plan. Other members authorize available connectors individually.

- **Add → Custom** is a submenu. Hover the Custom row to expose **Web** and **Desktop**, then choose Web for an HTTPS MCP server.
- The custom connector dialog has two steps. First enter the name and MCP URL. Continuing probes the server, protected-resource metadata, and authorization provider. Wait for these probes before expecting the second step.
- An unauthenticated MCP 401 followed by metadata 200 is normal for an OAuth server. It does not mean registration failed.
- The second step separates authentication mode from OAuth client registration. For a server that requires OAuth and a pre-registered confidential client, choose **Sign in now** and **Use your own OAuth client**. Supply the registered client ID and required secret.
- Adding the connector opens its details dialog and shows a success toast. Verify persistence in the organization connector table after reloading; a personal Connect button is a separate, per-user authorization step.
- Names are sorted and the table is paginated. Use the search box to verify a new connector instead of assuming the first page will contain it.

## Secrets and access

- The OAuth secret field is a password input. Retrieve a secret through an authorized local secret-store command and pass it to `type_text` in memory; do not print it or include it in a shared domain skill.
- Organization visibility and the MCP server's data authorization are independent. Registration does not grant users access at the server. Preserve the intended server-side allowlist.
